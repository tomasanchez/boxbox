"""The pre-race question, which is a different question.

AWS publishes a recommended strategy on the first lap: how many stops and on
which compounds. It cannot be optimising expected points there, because before
the race nobody knows where anyone will finish. What it can optimise — and what
its description implies, combining track history, projected pace, compound data
and weather — is the **fastest way to cover the race distance**.

That is a single-car problem. It needs tyre life, degradation per compound and
pit loss, and it does not need the field at all. It is a different product from
the in-race "Pit Strategy Battle", which is about beating one specific rival.

This script runs the genetic search on the pre-race question and asks the thing
that has been open all along: does the search beat a napkin rule **when the space
is genuinely multi-dimensional**? From lap 30 there is one stop left and one
variable; from lap 1 there are two or three stops and a compound sequence, and
that is where a search should earn its keep.

**Una corrección, y vale la pena escribirla.** Este script armaba la grilla con
una escalera de 0,25 s por puesto: un número inventado, descripto en su propio
comentario como «the measured spread of a starting grid». Ahora la parrilla sale
de la clasificación real de Zandvoort 2026 (ver ADR-004 y
:mod:`boxbox_ml.qualifying`). El error tenía además una segunda mitad: las tres
filas de cada tabla salían de tres autos distintos —el primero de la grilla que
llevara cada compuesto—, así que la columna de tiempo comparaba compuestos y de
paso se llevaba puesto el hueco de grilla entre ellos. Ahora las tres son el
mismo auto.

Run with ``uv run python scripts/prerace_strategy.py``.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from boxbox_ml import qualifying, strategy
from boxbox_ml.strategy import (
    Car,
    Objective,
    Plan,
    RaceModel,
    Stop,
    optimise,
    pace_from_qualifying,
)

pd.set_option("display.width", 180)

MODEL = RaceModel()
SEARCH = dict(population=40, generations=25, draws=400, seed=11)
DRAWS = 3000
SEP = "=" * 88

#: Median wear rate per compound at Zandvoort, from the measured distribution.
#: A car on the grid has no history to shrink toward, so this is all there is.
MEDIAN_WEAR = {c: strategy.WEAR_CUTS[c][4] for c in strategy.DRY}

#: La clasificación real de Zandvoort 2026, fecha 12, leída de la caché de FastF1.
#: Es lo que reemplaza a la escalera inventada de 0,25 s por puesto. Ver ADR-004.
QUALI = qualifying.load(2026, 12)

#: Compuesto con el que larga el campo. **Supuesto**: antes de la carrera no se
#: sabe con qué larga cada uno. Acá no decide ninguna respuesta —las tablas de
#: abajo comparan los tres compuestos sobre el mismo auto— pero la grilla tiene
#: que arrancar con alguno.
START_COMPOUND = "MEDIUM"

#: La parrilla, ahora medida: cada piloto con su hueco a la pole y el ritmo por
#: vuelta que ese hueco implica. Este script optimiza con objetivo TIME, que
#: ignora al campo por definición, así que el campo entra como insumo declarado y
#: no como rival — el que lo corre de verdad contra el campo es
#: ``scripts/prerace_export.py``.
FIELD = [
    Car(
        code=entry.code,
        compound=START_COMPOUND,
        tyre_age=0,
        degradation_s=0.0,
        # No history: the shrinkage has nothing to shrink, so the population
        # median is the honest starting point.
        degradation_rate=strategy.ROLLING_MEDIAN_S,
        gap_leader_s=entry.gap_to_pole_s,
        from_lap=1,
        # Sin esto, un auto en la vuelta 1 no tiene historia de la cual inferir su
        # ritmo y el modelo lo trata como si fuera tan rápido como la pole.
        pace_s=pace_from_qualifying(entry.gap_to_pole_s),
    )
    for entry in QUALI.entries
]


def car_on(compound: str) -> Car:
    """El auto de la pole, largando con ``compound``.

    Las tres filas de cada tabla tienen que ser el mismo auto. Antes no lo eran:
    el script tomaba el primero de la grilla que llevara cada compuesto, y como
    cada uno estaba en un puesto distinto, la columna de tiempo mezclaba el
    escalón entre compuestos con el hueco de grilla entre esos tres autos. Con el
    auto de referencia —hueco cero, ritmo cero— lo único que cambia entre filas es
    con qué goma larga, que es la pregunta.

    Args:
        compound: Con qué compuesto arranca.

    Returns:
        El auto de la pole con ese compuesto de salida.
    """
    return replace(FIELD[0], compound=compound)


print(SEP)
print("### THE QUESTION")
print("From lap 1 of 72, what is the fastest way to cover the distance?")
print("No field, no positions: TIME is the objective, which is what a pre-race")
print("recommendation can actually answer.")
print()
print(f"median wear per compound: { ({k: round(v, 4) for k, v in MEDIAN_WEAR.items()}) }")
print(f"longest stint the evidence covers: {strategy.MAX_STINT}")
print(f"pit loss (p25, median, p75): {MODEL.pit_loss_green}")
print()
print(f"parrilla: {QUALI.event} {QUALI.year}, pole {QUALI.pole_s:.3f} s, {len(FIELD)} autos")
ultimo = QUALI.gaps[-1]
print(
    f"hueco del último a la pole: {ultimo:.3f} s, o sea "
    f"{pace_from_qualifying(ultimo):.2f} s/vuelta de ritmo"
)
print("La escalera inventada que había acá ponía 0,25 s por puesto —5,25 s en ese")
print("lugar— y encima entraba sin ritmo declarado, así que movía el tiempo informado")
print("y no el plan. Ahora es la clasificación real. Ver ADR-004.")

# ------------------------------------------------------------- the recommendation

print("\n" + SEP)
print("### WHAT THE SEARCH RECOMMENDS, PER STARTING COMPOUND")
rows = []
for compound in ("SOFT", "MEDIUM", "HARD"):
    car = car_on(compound)
    found = optimise(car, [], [], MODEL, objective=Objective.TIME, **SEARCH)
    spread = " ".join(f"{k}:{v:.2f}" for k, v in found.stop_distribution.items())
    rows.append(
        {
            "larga en": compound,
            "plan": found.best.describe(car, MODEL.total_laps),
            "paradas": found.best.count,
            "tiempo": round(-found.score, 1),
            "convergencia": spread,
        }
    )
print(pd.DataFrame(rows).to_string(index=False))

# ------------------------------------------------------------- napkin rules


def evenly(car: Car, stops: int) -> Plan:
    """Split the race into equal stints, all on the hard. The obvious rule."""
    step = (MODEL.total_laps - car.from_lap) // (stops + 1)
    laps = [car.from_lap + step * (i + 1) for i in range(stops)]
    return Plan(strategy._repair([Stop(lap, "HARD") for lap in laps], car, MODEL))


def at_tyre_life(car: Car) -> Plan:
    """Stop when the set reaches its measured median life. The strategist's rule."""
    life = {"HARD": 24, "MEDIUM": 22, "SOFT": 12}
    stops, lap, compound = [], car.from_lap, car.compound
    while lap + life[compound] < MODEL.total_laps - strategy.MIN_STINT:
        lap += life[compound]
        compound = "HARD"
        stops.append(Stop(lap, compound))
    return Plan(strategy._repair(stops, car, MODEL))


def score(car: Car, plan: Plan) -> float:
    """Mean finishing time over common random numbers."""
    gen = np.random.default_rng(SEARCH["seed"])
    flags = strategy.draw_neutralisations(MODEL, gen, DRAWS)
    return float(strategy.race_time(plan, car, MODEL, gen, DRAWS, flags).mean())


print("\n" + SEP)
print("### DOES THE SEARCH BEAT A NAPKIN RULE HERE?")
print("Lower is better; every plan is scored over the same drawn races.")
rows = []
for compound in ("SOFT", "MEDIUM", "HARD"):
    car = car_on(compound)
    found = optimise(car, [], [], MODEL, objective=Objective.TIME, **SEARCH)
    row = {
        "larga en": compound,
        "AG": round(score(car, found.best), 1),
        "1 parada": round(score(car, evenly(car, 1)), 1),
        "2 paradas": round(score(car, evenly(car, 2)), 1),
        "3 paradas": round(score(car, evenly(car, 3)), 1),
        "vida de goma": round(score(car, at_tyre_life(car)), 1),
    }
    alternatives = [row[k] for k in ("1 parada", "2 paradas", "3 paradas", "vida de goma")]
    row["mejor regla"] = min(alternatives)
    row["ventaja"] = round(row["mejor regla"] - row["AG"], 1)
    rows.append(row)
table = pd.DataFrame(rows)
print(table.to_string(index=False))
print()
print(f"ventaja media del AG: {table['ventaja'].mean():+.1f} s sobre la carrera")

print("\n" + SEP)
print("### WHERE THE ADVANTAGE COMES FROM")
print("A napkin rule splits the race evenly and fits the same compound. The search")
print("can put the stops where the tyre actually runs out and mix compounds, which")
print("is a two-dimensional choice the rule has no way to express.")
car = car_on("MEDIUM")
found = optimise(car, [], [], MODEL, objective=Objective.TIME, **SEARCH)
print(f"\nsalida en medio, plan del AG:  {found.best.describe(car, MODEL.total_laps)}")
iguales = evenly(car, found.best.count).describe(car, MODEL.total_laps)
print(f"                 stints iguales:  {iguales}")
print(f"                 por vida de goma: {at_tyre_life(car).describe(car, MODEL.total_laps)}")
print("\nalternativas que quedaron cerca:")
for plan, value in found.alternatives:
    print(f"  {plan.describe(car, MODEL.total_laps):<18} {-value:8.1f} s (en muestra)")

print("\n" + SEP)
print("### AND THE SAME SEARCH FROM MID-RACE, FOR CONTRAST")
mid = Car("MED", "MEDIUM", 9, 0.96, 0.161, 10.08, 30)
found_mid = optimise(mid, [], [], MODEL, objective=Objective.TIME, **SEARCH)
mid_alt = min(score(mid, evenly(mid, n)) for n in (1, 2))
uno = score(car, found.best)
treinta = score(mid, found_mid.best)
print(f"desde la vuelta  1: AG {uno:8.1f} s   mejor regla {table.loc[1, 'mejor regla']:8.1f} s")
print(f"desde la vuelta 30: AG {treinta:8.1f} s   mejor regla {mid_alt:8.1f} s")
print("\nEs el mismo algoritmo. Lo que cambia es cuántas dimensiones tiene la")
print("decisión, y con ella cuánto hay para encontrar.")
