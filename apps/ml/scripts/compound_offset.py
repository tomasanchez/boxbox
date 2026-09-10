"""How much faster one compound is than another, measured where it can be.

The race cannot answer this. Compounds are run at systematically different points
of a Grand Prix — the medium at the 26% mark on average, the hard at 61% — and
separating a tyre effect from twenty-five laps of fuel burn and track evolution
needs a correction far more precise than the one that exists. Measured that way
the three dry compounds came out within 0.04 s/lap of each other, which cannot be
right: nobody would carry a hard tyre if it were free.

Practice can answer it. In FP1 and FP2 a driver runs short low-fuel stints on
different compounds within the same session, minutes apart, on the same car and
roughly the same track. Comparing a driver's **best lap on each compound within
one session** removes the car, the fuel and most of the track evolution, and
leaves the tyre.

Two things are still imperfect and are worth naming. Track evolution continues
inside a session, so whichever compound is run later gets a small unearned
advantage; and a driver does not always push equally on every set. Both add
noise rather than a systematic bias toward any compound, because the running
order of compounds varies between drivers and sessions.

Run with ``uv run python scripts/compound_offset.py``.
"""

from __future__ import annotations

import warnings

import fastf1
import numpy as np
import pandas as pd

from boxbox_ml import cache

warnings.filterwarnings("ignore")
pd.set_option("display.width", 190)
SEP = "=" * 88

cache.enable()
fastf1.Cache.offline_mode(True)

DRY = ("SOFT", "MEDIUM", "HARD")

rows = []
for rnd in range(1, 14):
    for name in ("FP1", "FP2", "FP3"):
        try:
            session = fastf1.get_session(2026, rnd, name)
            session.load(laps=True, telemetry=False, weather=False, messages=False)
            laps = session.laps
            if laps is None or laps.empty:
                continue
            good = laps.pick_accurate() if hasattr(laps, "pick_accurate") else laps
        except Exception:  # noqa: BLE001 - a missing session must not stop the sweep
            continue
        for _, lap in good.iterrows():
            if lap["Compound"] not in DRY or pd.isna(lap["LapTime"]):
                continue
            rows.append(
                {
                    "round": rnd,
                    "session": name,
                    "driver": lap["Driver"],
                    "compound": lap["Compound"],
                    "seconds": lap["LapTime"].total_seconds(),
                }
            )

practice = pd.DataFrame(rows)
print(SEP)
print("### LA MUESTRA")
print(f"vueltas de práctica utilizables: {len(practice):,}")
print(f"sesiones: {practice.groupby(['round', 'session']).ngroups}")
print(f"rondas:   {sorted(practice['round'].unique())}")

# Best lap per driver, session and compound: the low-fuel reference.
best = practice.groupby(["round", "session", "driver", "compound"])["seconds"].min().unstack()

print("\n" + SEP)
print("### DIFERENCIA ENTRE COMPUESTOS — mismo piloto, misma sesión")
pairs = [("SOFT", "MEDIUM"), ("MEDIUM", "HARD"), ("SOFT", "HARD")]
summary = []
for first, second in pairs:
    if first not in best or second not in best:
        continue
    delta = (best[first] - best[second]).dropna()
    if len(delta) < 10:
        continue
    summary.append(
        {
            "par": f"{first} - {second}",
            "n": len(delta),
            "mediana": round(float(delta.median()), 3),
            "p25": round(float(delta.quantile(0.25)), 3),
            "p75": round(float(delta.quantile(0.75)), 3),
        }
    )
table = pd.DataFrame(summary)
print(table.to_string(index=False))
print("\nNegativo quiere decir que el primero es más rápido.")

print("\n" + SEP)
print("### POR CIRCUITO — dónde el escalón es grande y dónde no")
per_round = []
for rnd, group in best.groupby(level="round"):
    row = {"ronda": rnd}
    for first, second in pairs:
        if first in group and second in group:
            delta = (group[first] - group[second]).dropna()
            valor = round(float(delta.median()), 3) if len(delta) >= 4 else np.nan
            row[f"{first[0]}-{second[0]}"] = valor
    per_round.append(row)
print(pd.DataFrame(per_round).to_string(index=False))

print("\n" + SEP)
print("### CONTRA LO QUE DABA LA CARRERA")
print("Medido dentro de la carrera, con la corrección por avance aplicada:")
print("  blando - medio  -0,015 s/vuelta")
print("  medio  - duro   -0,024")
print("  blando - duro   +0,040")
print()
if len(table):
    for row in table.itertuples():
        print(f"Medido en práctica: {row.par:18s} {row.mediana:+.3f} s   (n={row.n})")
print()
print("Si los números de práctica son mucho mayores, la conclusión de que «no hay")
print("diferencia medible entre compuestos secos» era un artefacto de intentar")
print("medirla dentro de la carrera, y el duro tiene una razón propia de existir")
print("además del reglamento.")


print("")
print(SEP)
print("### UN ESCALON CONSISTENTE, PARA METER EN EL MODELO")
print("Los tres pares de arriba no son transitivos, porque cada uno sale de un")
print("conjunto distinto de sesiones. Un ajuste por minimos cuadrados sobre TODAS")
print("las observaciones a la vez da tres numeros que si cierran entre si:")
print()
print("    tiempo = (efecto de la sesion y el piloto) + (escalon del compuesto)")
print()
practice["key"] = (
    practice["round"].astype(str) + "-" + practice["session"] + "-" + practice["driver"]
)
fastest = practice.groupby(["key", "compound"])["seconds"].min().unstack()
usable = fastest[fastest.notna().sum(axis=1) >= 2]
keys = list(usable.index)
position = {key: index for index, key in enumerate(keys)}
free = ["MEDIUM", "SOFT"]  # el duro es la referencia: su escalon es cero por definicion

design, target = [], []
for key in keys:
    for compound in DRY:
        value = usable.loc[key, compound]
        if pd.isna(value):
            continue
        row = [0.0] * (len(keys) + len(free))
        row[position[key]] = 1.0
        if compound in free:
            row[len(keys) + free.index(compound)] = 1.0
        design.append(row)
        target.append(float(value))

design = np.array(design)
target = np.array(target)
coefficients, *_ = np.linalg.lstsq(design, target, rcond=None)
offsets = {"HARD": 0.0, "MEDIUM": float(coefficients[-2]), "SOFT": float(coefficients[-1])}

print(f"sesiones-piloto con dos o mas compuestos: {len(keys)}   observaciones: {len(target)}")
residual = target - design @ coefficients
print(f"desvio del residuo: {residual.std():.3f} s")
print()
for compound in DRY:
    print(f"  {compound:7s} {offsets[compound]:+.3f} s/vuelta respecto del duro")
paso = offsets["SOFT"] - offsets["MEDIUM"]
print("")
print(f"  blando respecto del medio: {paso:+.3f}")
print()
print("Estos son los que entran al modelo. La advertencia va con ellos: una")
print("vuelta de practica es lanzada y con poco combustible, y en carrera los")
print("escalones se achican. Son una cota superior, no el numero de carrera.")
