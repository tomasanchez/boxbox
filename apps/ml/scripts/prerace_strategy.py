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

Run with ``uv run python scripts/prerace_strategy.py``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from boxbox_ml import strategy
from boxbox_ml.strategy import Car, Objective, Plan, RaceModel, Stop, optimise

pd.set_option("display.width", 180)

MODEL = RaceModel()
SEARCH = dict(population=40, generations=25, draws=400, seed=11)
DRAWS = 3000
SEP = "=" * 88

#: Median wear rate per compound at Zandvoort, from the measured distribution.
#: A car on the grid has no history to shrink toward, so this is all there is.
MEDIAN_WEAR = {c: strategy.WEAR_CUTS[c][4] for c in strategy.DRY}

#: The 2026 Zandvoort grid, as it lined up. Everyone on fresh rubber, nobody with
#: a measured degradation rate yet, and the gap to pole is grid slot times the
#: measured spread of a starting grid.
GRID_ORDER = [
    ("NOR", "MEDIUM"),
    ("RUS", "MEDIUM"),
    ("ANT", "MEDIUM"),
    ("PIA", "MEDIUM"),
    ("HAM", "SOFT"),
    ("LEC", "MEDIUM"),
    ("VER", "SOFT"),
    ("LAW", "MEDIUM"),
    ("ALO", "HARD"),
    ("HUL", "HARD"),
    ("TSU", "MEDIUM"),
    ("LIN", "SOFT"),
    ("GAS", "MEDIUM"),
    ("BOR", "HARD"),
    ("ALB", "MEDIUM"),
    ("SAI", "SOFT"),
    ("OCO", "HARD"),
    ("STR", "HARD"),
    ("COL", "MEDIUM"),
    ("BEA", "SOFT"),
]

#: Seconds per grid slot. A starting grid is roughly two tenths a place in pace
#: terms once the field settles; it only sets who is where, not the answer.
GRID_GAP_S = 0.25

FIELD = [
    Car(
        code=code,
        compound=compound,
        tyre_age=0,
        degradation_s=0.0,
        # No history: the shrinkage has nothing to shrink, so the population
        # median is the honest starting point.
        degradation_rate=strategy.ROLLING_MEDIAN_S,
        gap_leader_s=slot * GRID_GAP_S,
        from_lap=1,
    )
    for slot, (code, compound) in enumerate(GRID_ORDER)
]

print(SEP)
print("### THE QUESTION")
print("From lap 1 of 72, what is the fastest way to cover the distance?")
print("No field, no positions: TIME is the objective, which is what a pre-race")
print("recommendation can actually answer.")
print()
print(f"median wear per compound: { ({k: round(v, 4) for k, v in MEDIAN_WEAR.items()}) }")
print(f"longest stint the evidence covers: {strategy.MAX_STINT}")
print(f"pit loss (p25, median, p75): {MODEL.pit_loss_green}")

# ------------------------------------------------------------- the recommendation

print("\n" + SEP)
print("### WHAT THE SEARCH RECOMMENDS, PER STARTING COMPOUND")
rows = []
for compound in ("SOFT", "MEDIUM", "HARD"):
    car = next(c for c in FIELD if c.compound == compound)
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
    car = next(c for c in FIELD if c.compound == compound)
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
car = next(c for c in FIELD if c.compound == "MEDIUM")
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
