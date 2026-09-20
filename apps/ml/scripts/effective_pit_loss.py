"""Effective pit loss: seconds lost *relative to the field*, by track status.

An earlier attempt compared the in-lap and out-lap against the race's median
green lap. That is wrong under a neutralisation: the whole field is slow on those
laps too, so the comparison charged the stopping car for a slowness everybody
shared and reported the safety-car stop as *more* expensive than a green one.

The right baseline is the field's own median on **those same laps**. What is left
is what the car actually conceded to its rivals, which is the number a strategy
optimiser needs.
"""

from __future__ import annotations

import warnings

import fastf1
import pandas as pd

from boxbox_ml import cache, features, neutralisation, strategy, track_status

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)

cache.enable()
fastf1.Cache.offline_mode(True)
frame = pd.read_parquet(cache.cache_dir().parent / "laps_overtaking.parquet")
frame["circuit"] = frame["circuit"].map(lambda c: neutralisation.CIRCUIT_ALIASES.get(c, c))
frame = features.add_labels(track_status.add_flags(frame))

# Baseline: the median lap time of every car on that exact lap of that race.
# Cars in the pit lane are excluded from their own baseline.
racing = frame[~frame["pit_in"].astype(bool) & ~frame["pit_out"].astype(bool)]
baseline = racing.groupby([*features.RACE_KEYS, "LapNumber"])["LapTime"].median()

work = frame.join(baseline.rename("field_lap"), on=[*features.RACE_KEYS, "LapNumber"])
work["over_field"] = work["LapTime"] - work["field_lap"]


def status_of(row: pd.Series) -> str:
    if row["red"]:
        return "RED"
    if row["sc"]:
        return "SC"
    if row["vsc"] or row["vsc_ending"]:
        return "VSC"
    return "GREEN"


ins = work[work["pit_in"].astype(bool) & (work["LapNumber"] > 1)][
    [
        "year",
        "round",
        "circuit",
        "Driver",
        "LapNumber",
        "over_field",
        "red",
        "sc",
        "vsc",
        "vsc_ending",
    ]
].copy()
ins["status"] = ins.apply(status_of, axis=1)
ins = ins.rename(columns={"over_field": "in_lap"})

outs = work[work["pit_out"].astype(bool)][
    ["year", "round", "Driver", "LapNumber", "over_field"]
].copy()
outs["LapNumber"] -= 1
outs = outs.rename(columns={"over_field": "out_lap"})

stop = ins.merge(outs, on=["year", "round", "Driver", "LapNumber"], how="inner")
stop["loss"] = stop["in_lap"] + stop["out_lap"]
stop = stop[stop["loss"].between(-10, 90)]

print("=" * 84)
print("### EFFECTIVE PIT LOSS - seconds conceded to the field, all circuits")
print(
    stop.groupby("status")["loss"]
    .agg(
        stops="count",
        p25=lambda s: s.quantile(0.25),
        median="median",
        p75=lambda s: s.quantile(0.75),
        p90=lambda s: s.quantile(0.9),
    )
    .round(1)
)

print("")
print("### ZANDVOORT")
z = stop[stop["circuit"] == "Zandvoort"]
print(
    z.groupby("status")["loss"]
    .agg(
        stops="count",
        p25=lambda s: s.quantile(0.25),
        median="median",
        p75=lambda s: s.quantile(0.75),
    )
    .round(1)
)

print("")
print("### THE DISCOUNT - what a neutralised stop saves, as a fraction of the green cost")
green = stop[stop["status"] == "GREEN"]["loss"].median()
for label in ("SC", "VSC", "RED"):
    sample = stop[stop["status"] == label]["loss"]
    if len(sample) < 20:
        continue
    med = sample.median()
    print(f"  {label:5s} {med:6.1f} s   {med / green:.2f} x green   (n={len(sample)})")
print(f"  GREEN {green:6.1f} s   1.00 x green")

print("")
print("=" * 84)
print("### LOS NUEVE CORTES - la distribución empírica, sin asumirle forma")
print("")
print("El simulador sorteaba esta pérdida de una TRIANGULAR ajustada a los tres")
print("cuartiles de arriba. El desgaste, en cambio, se sortea de la distribución")
print("empírica con nueve cortes, y el script que lo midió argumenta por qué:")
print("una tanda puede salir muy mal de maneras en que no puede salir igual de")
print("bien. Eso vale palabra por palabra para una parada —una rueda trabada, una")
print("salida insegura, tráfico en el carril— y ahí sí se le asumía una forma.")
print("")
print("Una triangular NO PUEDE PASARSE DE SU MAXIMO, y su máximo acá era el p75.")
print("Eso deja UN CUARTO de las paradas reales fuera del alcance del modelo, por")
print("construcción y no por casualidad. Lo que se pierde es todo lo que hay más")
print("allá, que es donde vive el riesgo de parar:")
print("")
for label in ("GREEN", "SC", "VSC"):
    sample = stop[stop["status"] == label]["loss"]
    if len(sample) < 20:
        continue
    top = sample.quantile(0.75)
    beyond = sample[sample > top]
    print(
        f"  {label:5s} tope {top:5.1f} s   el cuarto que queda afuera mediaba"
        f" {beyond.mean():5.1f} s y llegó hasta {sample.max():5.1f}"
    )

print("")
print("Los cortes, a las mismas probabilidades que ya usa el desgaste:")
print(f"  {tuple(float(p) for p in strategy.CUT_AT)}")
print("")
for label, name in (("GREEN", "green"), ("SC", "sc"), ("VSC", "vsc")):
    sample = stop[stop["status"] == label]["loss"]
    if len(sample) < 20:
        print(f"    # {name}: n={len(sample)}, muestra fina — se deja como está")
        continue
    cuts = ", ".join(f"{v:.1f}" for v in sample.quantile(strategy.CUT_AT))
    print(f"    pit_loss_{name}: tuple[float, ...] = ({cuts})")
print("    # la roja no se mide: con la carrera detenida el cambio no cuesta")
print("    # posición, y el modelo ya la representa con una pérdida de cero")

print("")
print("=" * 84)
print("### Y LOS DE ZANDVOORT, PARA apps/web/src/tyres.ts")
print("")
print("La pantalla sortea la parada de la distribución de SU circuito, no de la de")
print("todos. El largo del pit lane es del circuito y es la cantidad por circuito")
print("más fácil de justificar de todo el proyecto.")
print("")
zg = stop[(stop["circuit"] == "Zandvoort") & (stop["status"] == "GREEN")]["loss"]
z_cuts = ", ".join(f"{v:.1f}" for v in zg.quantile(strategy.CUT_AT))
print(f"  const PIT_LOSS_CUTS = [{z_cuts}]  // {len(zg)} paradas en verde")
print("")
print("Estos cortes salen de la MEDIANA DEL CAMPO EN ESA MISMA VUELTA, que es la")
print("referencia que este script existe para usar. `zandvoort_distributions.py`")
print("mide lo mismo contra la mediana verde DE LA CARRERA —un solo número— y le")
print("carga al auto el combustible, la evolución de la pista y el tráfico de esa")
print("vuelta. Con una triangular la diferencia era chica y pasaba inadvertida: los")
print("tres cuartiles daban 19,8 / 22,7 / 26,7 acá contra 20,6 / 23,5 / 31,3 allá.")
print("Con los nueve cortes la diferencia se ve donde importa: el p95 da 41,1 acá y")
print("64,7 allá. Pasar a la distribución empírica no creó el problema, lo mostró.")
