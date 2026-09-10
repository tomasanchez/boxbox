"""What to do about a circuit nobody has raced on.

Madrid is round 14 of 2026 and has never held a Grand Prix. The model reaches for
per-circuit tyre degradation and there is none, so the question is what to fall
back on and how much that fallback costs.

The honest way to answer is a **leave-one-circuit-out** test: hide a circuit the
model has actually seen, predict its degradation without it, and measure the
error. Whatever that error is, it is what a new circuit costs.

Three fallbacks are compared:

  global          the average across all circuits — the assumption the model
                  makes today without saying so
  velocidad       plus average speed, derived from race distance and lap time.
                  A slow, twisty lap loads the tyre differently from a fast one
  vuelta          plus lap time on its own

Circuit length is not in the data directly, but a Grand Prix is regulated to
about 305 km, so ``305 km / total_laps`` recovers it closely enough, and dividing
by lap time gives average speed. Neither needs a single extra download.

Run with ``uv run python scripts/new_circuit.py``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from boxbox_ml import cache, features, neutralisation, track_status

pd.set_option("display.width", 200)
SEP = "=" * 88

#: Regulated minimum race distance, in metres. Used to recover lap length.
RACE_DISTANCE_M = 305_000

parts = [pd.read_parquet(cache.cache_dir().parent / "laps_overtaking.parquet")]
monza = cache.cache_dir().parent / "monza2026.parquet"
if monza.exists():
    parts.append(pd.read_parquet(monza))
raw = pd.concat(parts, ignore_index=True)
raw["circuit"] = raw["circuit"].map(lambda c: neutralisation.CIRCUIT_ALIASES.get(c, c))

frame = features.add_stint_position(
    features.add_fuel_correction(features.mark_representative(track_status.add_flags(raw)))
)
rain = frame.groupby(["year", "round"])["Rainfall"].mean()
wet = set(rain[rain > 0.2].index)
green = frame[
    frame["is_representative"]
    & ~frame["is_neutralised"]
    & ~frame["red"]
    & ~frame["yellow"]
    & ~pd.MultiIndex.from_frame(frame[["year", "round"]]).isin(wet)
]

rows = []
for _keys, stint in green.groupby(features.STINT_KEYS, dropna=False):
    pace = stint["lap_time_fuel_corrected"].to_numpy(dtype=float)
    position = stint["stint_lap"].to_numpy(dtype=float)
    if len(pace) < 8 or not np.isfinite(pace).all():
        continue
    rows.append(
        {
            "circuit": stint["circuit"].iloc[0],
            "compound": stint["Compound"].iloc[0],
            "slope": float(np.polyfit(position, pace, 1)[0]),
        }
    )
stints = pd.DataFrame(rows)
stints = stints[stints["compound"].isin(["SOFT", "MEDIUM", "HARD"])]

# One row per circuit: its features and its measured wear per compound.
shape = green.groupby("circuit").agg(
    total_laps=("total_laps", "median"), lap_time=("LapTime", "median")
)
shape["largo_m"] = RACE_DISTANCE_M / shape["total_laps"]
shape["velocidad_kmh"] = shape["largo_m"] / shape["lap_time"] * 3.6

wear = stints.groupby(["circuit", "compound"])["slope"].agg(["median", "size"]).unstack()
table = shape.join(wear["median"]).join(wear["size"], rsuffix="_n")

print(SEP)
print("### LOS CIRCUITOS, SU FORMA Y SU DESGASTE")
show = table[["total_laps", "lap_time", "largo_m", "velocidad_kmh", "SOFT", "MEDIUM", "HARD"]]
print(show.round(3).sort_values("velocidad_kmh").to_string())

print("\n" + SEP)
print("### ¿EL DESGASTE SE PUEDE PREDECIR DE LA FORMA DEL CIRCUITO?")
print("Correlación entre la velocidad media y el desgaste de cada compuesto:")
for compound in ("SOFT", "MEDIUM", "HARD"):
    sub = table[["velocidad_kmh", "lap_time", compound]].dropna()
    if len(sub) < 8:
        continue
    r_vel = sub["velocidad_kmh"].corr(sub[compound])
    r_lap = sub["lap_time"].corr(sub[compound])
    print(f"  {compound:7s} n={len(sub):2d}   con velocidad {r_vel:+.3f}   con vuelta {r_lap:+.3f}")

print("\n" + SEP)
print("### LEAVE-ONE-CIRCUIT-OUT — cuánto cuesta un circuito nuevo")
print("Se esconde un circuito, se predice su desgaste sin él, y se mide el error.")
results = []
for compound in ("SOFT", "MEDIUM", "HARD"):
    sub = table[["velocidad_kmh", "lap_time", compound]].dropna()
    if len(sub) < 8:
        continue
    errors: dict[str, list[float]] = {"global": [], "velocidad": [], "vuelta": []}
    for name in sub.index:
        train = sub.drop(index=name)
        truth = float(sub.loc[name, compound])

        errors["global"].append(abs(float(train[compound].median()) - truth))
        for label, feature in (("velocidad", "velocidad_kmh"), ("vuelta", "lap_time")):
            slope, intercept = np.polyfit(train[feature], train[compound], 1)
            predicted = slope * float(sub.loc[name, feature]) + intercept
            errors[label].append(abs(predicted - truth))

    row = {"compuesto": compound, "circuitos": len(sub)}
    row.update({k: round(float(np.mean(v)), 4) for k, v in errors.items()})
    row["desvío entre circuitos"] = round(float(sub[compound].std()), 4)
    results.append(row)
loo = pd.DataFrame(results)
print(loo.to_string(index=False))
print()
print("El error del método 'global' es lo que se paga por no tener historia. Si")
print("las columnas con features no le ganan, la forma del circuito no ayuda y")
print("lo honesto para Madrid es usar el promedio y decir que es el promedio.")

print("\n" + SEP)
print("### QUÉ SE PUEDE DECIR DE MADRID")
best = loo.set_index("compuesto")[["global", "velocidad", "vuelta"]].idxmin(axis=1)
for compound in loo["compuesto"]:
    error = loo.set_index("compuesto").loc[compound, best[compound]]
    central = table[compound].median()
    print(
        f"  {compound:7s} mejor estimación: {central:.4f} s/vuelta"
        f"   ± {error:.4f} esperado   (método: {best[compound]})"
    )
print()
print("Para poner esos números en escala: el desgaste típico va de 0,03 a 0,07")
print("s/vuelta, así que un error de esa magnitud es del tamaño del efecto.")
print("Una recomendación para Madrid sale, pero con una incertidumbre que hay")
print("que declarar, no esconder.")
