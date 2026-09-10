"""Does the search beat a napkin rule earlier in the race, where more is undecided?"""

from __future__ import annotations

import warnings
from dataclasses import replace

import numpy as np
import pandas as pd

from boxbox_ml import strategy
from boxbox_ml.strategy import Car, Objective, Plan, RaceModel, Stop, optimise

warnings.filterwarnings("ignore")
pd.set_option("display.width", 170)

MODEL = RaceModel()
SEARCH = dict(population=24, generations=12, draws=200, seed=7)
DRAWS = 2000

GRID = [
    Car("ANT", "HARD", 9, 0.38, 0.093, 0.0, 30),
    Car("NOR", "HARD", 9, 0.25, 0.064, 0.69, 30),
    Car("RUS", "HARD", 13, 0.36, 0.024, 7.79, 30),
    Car("PIA", "HARD", 12, 0.63, 0.005, 9.65, 30),
    Car("LEC", "MEDIUM", 9, 0.96, 0.161, 10.08, 30),
    Car("HAM", "HARD", 5, 0.53, 0.037, 15.35, 30),
    Car("LAW", "MEDIUM", 9, 0.51, 0.112, 31.85, 30),
    Car("ALO", "SOFT", 28, 0.0, 0.005, 47.94, 30),
    Car("TSU", "HARD", 12, -0.1, -0.399, 59.26, 30),
    Car("LIN", "MEDIUM", 25, 1.77, -0.008, 62.28, 30),
]

rng = np.random.default_rng(7)


def drawn(car: Car) -> Plan:
    n = int(rng.choice([0, 1, 2, 3], p=[0.151, 0.493, 0.192, 0.164]))
    stops, prev = [], car.from_lap
    for _ in range(n):
        share = float(np.interp(rng.random(), [0.05, 0.5, 0.95], [0.458, 0.722, 0.817]))
        lap = max(int(share * MODEL.total_laps), prev + strategy.MIN_STINT)
        if lap > MODEL.total_laps - strategy.MIN_STINT:
            break
        stops.append(Stop(lap, str(rng.choice(strategy.DRY))))
        prev = lap
    return Plan(tuple(stops))


def score(car, plan, rest, plans):
    gen = np.random.default_rng(SEARCH["seed"])
    flags = strategy.draw_neutralisations(MODEL, gen, DRAWS)
    riv = np.vstack(
        [
            strategy.race_time(p, c, MODEL, gen, DRAWS, flags)
            for c, p in zip(rest, plans, strict=True)
        ]
    )
    mine = strategy.race_time(plan, car, MODEL, gen, DRAWS, flags)
    pos = 1 + (riv < mine).sum(axis=0)
    return float(strategy._points(pos).mean())


def halfway(car):
    lap = car.from_lap + (MODEL.total_laps - car.from_lap) // 2
    return Plan(strategy._repair([Stop(lap, "HARD")], car, MODEL))


def now(car):
    return Plan(strategy._repair([Stop(car.from_lap + strategy.MIN_STINT, "HARD")], car, MODEL))


def late(car):
    return Plan(strategy._repair([Stop(MODEL.total_laps - strategy.MIN_STINT, "HARD")], car, MODEL))


for from_lap in (10, 20, 30, 45):
    grid = [
        replace(c, from_lap=from_lap, tyre_age=max(1, c.tyre_age - (30 - from_lap))) for c in GRID
    ]
    rows = []
    for car in grid:
        rest = [c for c in grid if c.code != car.code]
        plans = [drawn(c) for c in rest]
        found = optimise(car, rest, plans, MODEL, objective=Objective.POINTS, **SEARCH)
        ga = score(car, found.best, rest, plans)
        alt = max(score(car, f(car), rest, plans) for f in (halfway, now, late))
        rows.append({"car": car.code, "ga": ga, "alt": alt, "edge": ga - alt})
    table = pd.DataFrame(rows)
    wins = (table["edge"] > 0.01).sum()
    print(
        f"desde la vuelta {from_lap:2d}  ({MODEL.total_laps - from_lap} por correr):"
        f"  gana {wins:2d}/{len(table)}   ventaja media {table['edge'].mean():+.3f}"
        f"   ventaja máx {table['edge'].max():+.2f}"
    )
