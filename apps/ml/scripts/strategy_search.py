"""Run the genetic search over the Zandvoort grid and report what it recommends.

Answers the question the recommendation depends on: what counts as winning. The
same car is optimised under each objective, and the plans come out different —
which is the point. A car in eighteenth told to protect its position is being
told to score zero carefully.

Run with ``uv run python scripts/strategy_search.py``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from boxbox_ml.strategy import (
    DRY,
    MIN_STINT,
    Car,
    Objective,
    Plan,
    RaceModel,
    Stop,
    optimise,
)

# 2026 R12 Zandvoort, lap 30 — the same snapshot the web simulator runs on.
GRID = [
    Car("ANT", "HARD", 9, 0.38, 0.093, 0.0, 30),
    Car("NOR", "HARD", 9, 0.25, 0.064, 0.69, 30),
    Car("RUS", "HARD", 13, 0.36, 0.024, 7.79, 30),
    Car("PIA", "HARD", 12, 0.63, 0.005, 9.65, 30),
    Car("LEC", "MEDIUM", 9, 0.96, 0.161, 10.08, 30),
    Car("HAM", "HARD", 5, 0.53, 0.037, 15.35, 30),
    Car("LAW", "MEDIUM", 9, 0.51, 0.112, 31.85, 30),
    Car("ALO", "SOFT", 28, 0.0, 0.005, 47.94, 30),
    Car("HUL", "SOFT", 11, -1.57, -0.549, 55.3, 30),
    Car("TSU", "HARD", 12, -0.1, -0.399, 59.26, 30),
    Car("LIN", "MEDIUM", 25, 1.77, -0.008, 62.28, 30),
    Car("GAS", "HARD", 12, 1.29, -0.113, 62.58, 30),
    Car("BOR", "MEDIUM", 19, 1.21, 0.205, 63.29, 30),
    Car("ALB", "HARD", 4, 0.0, 0.376, 64.05, 30),
    Car("SAI", "SOFT", 28, 0.0, 0.279, 66.06, 30),
    Car("OCO", "HARD", 14, -1.88, 0.049, 67.55, 30),
    Car("STR", "HARD", 15, 0.13, -0.133, 71.81, 30),
    Car("COL", "HARD", 9, 0.54, 0.378, 81.71, 30),
    Car("PER", "HARD", 1, 0.0, 0.0, 98.35, 30),
    Car("BOT", "HARD", 4, 0.45, 0.0, 99.46, 30),
]

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--draws", type=int, default=400)
parser.add_argument("--generations", type=int, default=30)
parser.add_argument("--population", type=int, default=48)
parser.add_argument("--seed", type=int, default=7)
parser.add_argument("--out", type=Path, help="write the grid-wide result as JSON")
args = parser.parse_args()

MODEL = RaceModel()
rng = np.random.default_rng(args.seed)


def drawn_plan(car: Car) -> Plan:
    """A rival's plan: drawn from the measured stop distribution, not optimised.

    Rivals do not get a search of their own. Giving everyone the optimum would
    describe a race nobody has ever run.
    """
    count = int(rng.choice([0, 1, 2, 3], p=[0.151, 0.493, 0.192, 0.164]))
    stops, previous = [], car.from_lap
    for _ in range(count):
        share = float(np.interp(rng.random(), [0.05, 0.5, 0.95], [0.458, 0.722, 0.817]))
        lap = max(int(share * MODEL.total_laps), previous + MIN_STINT)
        if lap > MODEL.total_laps - MIN_STINT:
            break
        stops.append(Stop(lap, str(rng.choice(DRY))))
        previous = lap
    return Plan(tuple(stops))


PLANS = {car.code: drawn_plan(car) for car in GRID}


def others(code: str) -> tuple[list[Car], list[Plan]]:
    rest = [c for c in GRID if c.code != code]
    return rest, [PLANS[c.code] for c in rest]


print("=" * 92)
print("### WHAT 'WINNING' MEANS - the same car, four objectives")
for code in ("ANT", "LEC", "COL"):
    car = next(c for c in GRID if c.code == code)
    rest, plans = others(code)
    place = GRID.index(car) + 1
    print(f"\n{code} (P{place}, {car.compound} {car.tyre_age} laps, {car.gap_leader_s:.1f}s back)")
    for objective in (Objective.POINTS, Objective.POSITION, Objective.IN_POINTS, Objective.TIME):
        found = optimise(
            car,
            rest,
            plans,
            MODEL,
            objective=objective,
            population=args.population,
            generations=args.generations,
            draws=args.draws,
            seed=args.seed,
        )
        spread = " ".join(f"{k}:{v:.2f}" for k, v in found.stop_distribution.items())
        print(
            f"  {objective.value:<10} {found.best.describe(car, MODEL.total_laps):<14}"
            f" pos {found.mean_position:5.2f}  pts {found.mean_points:5.2f}   paradas {spread}"
        )

print("\n" + "=" * 92)
print("### THE RECOMMENDATION FOR EVERY CAR - points where reachable, else position")
results = {}
for index, car in enumerate(GRID, start=1):
    rest, plans = others(car.code)
    found = optimise(
        car,
        rest,
        plans,
        MODEL,
        objective=Objective.ADAPTIVE,
        population=args.population,
        generations=args.generations,
        draws=args.draws,
        seed=args.seed,
    )
    alternatives = [
        {"plan": p.describe(car, MODEL.total_laps), "stops": p.count, "score": round(v, 3)}
        for p, v in found.alternatives
    ]
    results[car.code] = {
        "from_position": index,
        "plan": found.best.describe(car, MODEL.total_laps),
        "stops": [{"lap": s.lap, "compound": s.compound} for s in found.best.stops],
        "stop_distribution": {str(k): round(v, 3) for k, v in found.stop_distribution.items()},
        "mean_position": round(found.mean_position, 2),
        "mean_points": round(found.mean_points, 2),
        "objective": found.objective.value,
        "alternatives": alternatives,
    }
    spread = " ".join(f"{k}:{v:.2f}" for k, v in found.stop_distribution.items())
    print(
        f"P{index:<3}{car.code}  {found.best.describe(car, MODEL.total_laps):<16}"
        f" pos {found.mean_position:5.2f}  pts {found.mean_points:5.2f}"
        f"  [{found.objective.value[:3]}]   {spread}"
    )

if args.out:
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nwritten to {args.out}")
