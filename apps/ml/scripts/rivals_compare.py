"""Correr un piloto contra rivales de plan fijo y contra rivales reactivos.

Es la forma de usar la feature de rivales reactivos mientras la interfaz todavía
no tiene el interruptor. Toma la parrilla real de Zandvoort del export
pre-carrera, elige un piloto, y corre la misma búsqueda en los dos modos sobre
las mismas carreras sorteadas.

::

    uv run python scripts/rivals_compare.py                 # NOR
    uv run python scripts/rivals_compare.py --driver BEA
    uv run python scripts/rivals_compare.py --driver LIN --draws 2000

## Cómo leer la salida, porque se lee al revés de lo que parece

**Un puntaje mejor bajo reactivo no es un plan mejor.** Los rivales reactivos
paran más veces que lo que decía su plan —2,11 contra 1,86 de los autos reales—
y cada parada de más les cuesta tiempo. Sobre las mismas carreras el campo
termina **1,35 s más lento**, así que el auto elegido mejora su puntaje sin haber
cambiado de plan: no mejoró él, empeoró el campo.

Ese 1,35 está medido con 12.000 sorteos. Con los 1.200 de por defecto la cifra
del campo se mueve como un segundo para cada lado de una corrida a otra: es un
promedio sobre 22 autos y le sobra ruido. Para leerla en serio, ``--draws 12000``.

Lo que sí se puede leer es **si el plan cambia**. Ahí la pregunta es si tener
rivales que toman las ventanas baratas y que cubren tu parada mueve la
recomendación, y eso es lo que la feature vino a contestar.

La fila de abajo del cuadro muestra lo que hace el campo en cada modo, que es
donde la diferencia se ve de verdad.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from boxbox_ml import strategy as st
from boxbox_ml.strategy import Car, Objective, Plan, RaceModel, RivalMode, Stop, optimise

SEP = "=" * 88
DEFAULT_EXPORT = (
    Path(__file__).resolve().parents[3] / "docs" / "research" / "prerace-zandvoort.json"
)


def load(path: Path) -> tuple[int, list[Car], list[Plan]]:
    """La parrilla del export, con el equipo de cada auto ya puesto."""
    export = json.loads(path.read_text(encoding="utf-8"))
    laps = int(export["race"]["total_laps"])
    cars, plans = [], []
    for entry in export["cars"]:
        cars.append(
            Car(
                entry["code"],
                entry["start_compound"],
                0,
                0.0,
                st.ROLLING_MEDIAN_S,
                0.0,
                1,
                pace_s=entry["pace_s"],
                team=entry["team"],
            )
        )
        plans.append(Plan(tuple(Stop(int(s["lap"]), s["compound"]) for s in entry["stops"])))
    return laps, cars, plans


def field_cost(
    cars: list[Car], plans: list[Plan], model: RaceModel, draws: int, mode: RivalMode
) -> tuple[float, float]:
    """Tiempo final medio del campo y paradas medias por auto, en un modo."""
    rng = np.random.default_rng(101)
    flags = st.draw_neutralisations(model, rng, draws)
    ids = st.period_ids(flags)
    shift = st.draw_period_shift(ids, rng)
    times, stops = [], []
    for car, plan in zip(cars, plans, strict=True):
        gen = np.random.default_rng(7)
        if mode is RivalMode.REACTIVE:
            mask = np.zeros((model.total_laps - car.from_lap + 1, draws), dtype=bool)
            trace = st.reactive_trace(
                plan, car, model, gen, draws, flags, ids, shift, stops_out=mask
            )
            stops.append(mask.sum(axis=0).mean())
        else:
            trace = st.race_trace(plan, car, model, gen, draws, flags)
            stops.append(float(len(plan.stops)))
        times.append(trace[-1].mean())
    return float(np.mean(times)), float(np.mean(stops))


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--driver", default="NOR", help="código del piloto a simular")
parser.add_argument("--draws", type=int, default=1200, help="carreras sorteadas")
parser.add_argument("--export", type=Path, default=DEFAULT_EXPORT, help="de dónde sale la parrilla")
parser.add_argument("--seed", type=int, default=11)
args = parser.parse_args()

laps, cars, plans = load(args.export)
model = RaceModel.for_circuit("Zandvoort", total_laps=laps)
codes = [c.code for c in cars]
if args.driver not in codes:
    parser.error(f"{args.driver} no está en la parrilla. Hay: {', '.join(codes)}")
who = codes.index(args.driver)
focal = cars[who]
rest = [c for i, c in enumerate(cars) if i != who]
rest_plans = [p for i, p in enumerate(plans) if i != who]

print(SEP)
print(f"### {focal.code}, QUE LARGA {who + 1}º EN ZANDVOORT")
print(f"  equipo {focal.team}, ritmo {focal.pace_s:+.2f} s/vuelta contra la pole")
print(f"  {args.draws} carreras sorteadas, las mismas para los dos modos")
print()

rows = []
for mode in (RivalMode.FIXED, RivalMode.REACTIVE):
    started = time.time()
    found = optimise(
        focal,
        rest,
        rest_plans,
        model,
        objective=Objective.ADAPTIVE,
        population=40,
        generations=25,
        draws=args.draws,
        seed=args.seed,
        rivals_mode=mode,
    )
    rows.append((mode, found, time.time() - started))

print(f"  {'modo':10s} {'plan':18s} {'paradas':>8s} {'puntaje':>9s} {'objetivo':>9s} {'seg':>6s}")
for mode, found, elapsed in rows:
    print(
        f"  {str(mode):10s} {found.best.describe(focal, laps):18s} {found.best.count:8d}"
        f" {found.score:9.2f} {str(found.objective):>9s} {elapsed:6.1f}"
    )

same = rows[0][1].best.describe(focal, laps) == rows[1][1].best.describe(focal, laps)
print()
print(f"  ¿cambia el plan? {'NO' if same else 'SI'}")
print()
print(SEP)
print("### LO QUE HACE EL CAMPO EN CADA MODO")
print()
print(f"  {'modo':10s} {'tiempo final medio':>20s} {'paradas por auto':>18s}")
base = None
for mode in (RivalMode.FIXED, RivalMode.REACTIVE):
    seconds, stops = field_cost(cars, plans, model, args.draws, mode)
    marker = "" if base is None else f"   ({seconds - base:+.2f} s)"
    base = seconds if base is None else base
    print(f"  {str(mode):10s} {seconds:17.2f} s {stops:18.2f}{marker}")
print()
print("  ACA ESTA LA TRAMPA. Un puntaje mejor arriba no quiere decir que el plan")
print("  sea mejor: los rivales reactivos paran de más y eso los hace más lentos,")
print("  así que el auto elegido sube sin haber cambiado nada. No mejoró él,")
print("  empeoró el campo. Los puntajes se comparan DENTRO de un modo.")
print()
print("  Lo que sí se lee entre modos es si el plan cambia, que es la pregunta")
print("  que la feature vino a contestar.")
