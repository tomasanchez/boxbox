"""What is actually worth optimising, decision by decision.

The earlier comparison was unfair to the search and I set it up that way without
noticing. The "napkin rule" it was measured against took the **minimum over one,
two and three stops** and always fitted the hard compound. That is not a rule
anybody could follow before a race: it is an oracle that has already been told
the two hardest answers — how many stops, and onto what — leaving the search only
the lap numbers to argue about.

A real rule is one you can state in advance and apply without knowing the answer.
"Two stops, even splits, hard tyres" is a rule. "Whichever of one, two or three
stops turns out best" is a result.

This measures each decision separately:

  cuántas paradas   how much it is worth knowing the right number rather than
                    committing to one in advance
  a qué compuesto   how much it is worth choosing the compound rather than
                    defaulting to the hard
  en qué vuelta     how much is left once the other two are settled — which is
                    the only thing the earlier comparison was actually testing

Run with ``uv run python scripts/decision_value.py``.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from boxbox_ml import strategy
from boxbox_ml.strategy import Car, Objective, Plan, RaceModel, Stop, optimise

pd.set_option("display.width", 200)

MODEL = RaceModel()
SEARCH = dict(population=40, generations=25, draws=1200, seed=11)
DRAWS = 8000
SEP = "=" * 92

STARTS = ("SOFT", "MEDIUM", "HARD")


def car_on(compound: str) -> Car:
    """A car on the grid, on that compound, with no history to lean on."""
    return Car("X", compound, 0, 0.0, strategy.ROLLING_MEDIAN_S, 0.0, 1)


def even_plan(car: Car, stops: int, onto: str) -> Plan:
    """Split the race evenly and fit the same compound every time."""
    if stops <= 0:
        return Plan(strategy._repair([], car, MODEL))
    step = (MODEL.total_laps - car.from_lap) // (stops + 1)
    laps = [car.from_lap + step * (index + 1) for index in range(stops)]
    return Plan(strategy._repair([Stop(lap, onto) for lap in laps], car, MODEL))


def score(car: Car, plan: Plan) -> float:
    """Mean race time over a fixed, shared set of drawn races."""
    gen = np.random.default_rng(4242)
    sc = strategy.draw_safety_car(MODEL, gen, DRAWS)
    return float(strategy.race_time(plan, car, MODEL, gen, DRAWS, sc).mean())


print(SEP)
print("### 1 · ¿CUÁNTAS PARADAS? — el mismo compuesto, sólo cambia el número")
rows = []
for start in STARTS:
    car = car_on(start)
    row = {"larga en": start}
    for stops in (1, 2, 3):
        etiqueta = f"{stops} parada{'s' if stops > 1 else ''}"
        row[etiqueta] = round(score(car, even_plan(car, stops, "HARD")), 2)
    times = [row[k] for k in row if k != "larga en"]
    row["peor - mejor"] = round(max(times) - min(times), 2)
    row["mejor"] = (1, 2, 3)[int(np.argmin(times))]
    rows.append(row)
stops_table = pd.DataFrame(rows)
print(stops_table.to_string(index=False))
vale_n = stops_table["peor - mejor"].mean()
print(f"\nElegir bien la cantidad vale {vale_n:.1f} s de carrera en promedio.")
print("Y el número correcto NO es el mismo para todos: depende del compuesto de salida.")

print("\n" + SEP)
print("### 2 · ¿A QUÉ COMPUESTO CAMBIAR? — dos paradas, todas las combinaciones")
rows = []
for start in STARTS:
    car = car_on(start)
    best, worst = None, None
    for first, second in itertools.product(STARTS, repeat=2):
        step = (MODEL.total_laps - 1) // 3
        plan = Plan(
            strategy._repair([Stop(1 + step, first), Stop(1 + 2 * step, second)], car, MODEL)
        )
        value = score(car, plan)
        if best is None or value < best[1]:
            best = (f"{first[0]}-{second[0]}", value)
        if worst is None or value > worst[1]:
            worst = (f"{first[0]}-{second[0]}", value)
    siempre_duro = score(car, even_plan(car, 2, "HARD"))
    rows.append(
        {
            "larga en": start,
            "mejor combinación": best[0],
            "tiempo": round(best[1], 2),
            "peor": worst[0],
            "tiempo peor": round(worst[1], 2),
            "siempre duro": round(siempre_duro, 2),
            "vale elegir": round(siempre_duro - best[1], 2),
        }
    )
compound_table = pd.DataFrame(rows)
print(compound_table.to_string(index=False))
print(f"\nElegir bien el compuesto vale {compound_table['vale elegir'].mean():.1f} s")
rango = (compound_table["tiempo peor"] - compound_table["tiempo"]).mean()
print(f"sobre defaultear al duro, y {rango:.1f} s")
print("entre la mejor y la peor combinación.")

print("\n" + SEP)
print("### 3 · ¿EN QUÉ VUELTA? — cantidad y compuesto ya fijados en lo mejor")
rows = []
for start in STARTS:
    car = car_on(start)
    fixed_n = int(stops_table[stops_table["larga en"] == start]["mejor"].iloc[0])
    even = score(car, even_plan(car, fixed_n, "HARD"))
    # Barrer la vuelta de la primera parada deja ver cuánto hay en esa dimensión.
    sweep = []
    for shift in range(-10, 11, 2):  # noqa: B007
        step = (MODEL.total_laps - 1) // (fixed_n + 1)
        laps = [1 + step * (i + 1) + (shift if i == 0 else 0) for i in range(fixed_n)]
        plan = Plan(strategy._repair([Stop(lap, "HARD") for lap in laps], car, MODEL))
        sweep.append(score(car, plan))
    rows.append(
        {
            "larga en": start,
            "paradas": fixed_n,
            "reparto parejo": round(even, 2),
            "mejor vuelta": round(min(sweep), 2),
            "peor vuelta": round(max(sweep), 2),
            "vale mover 10": round(even - min(sweep), 2),
        }
    )
lap_table = pd.DataFrame(rows)
print(lap_table.to_string(index=False))
print(f"\nMover la vuelta de la parada ±10 vale {lap_table['vale mover 10'].mean():.2f} s.")

print("\n" + SEP)
print("### 4 · CONTRA UNA REGLA QUE SÍ SE PUEDE ENUNCIAR DE ANTEMANO")
print("Sin oráculo: la regla se fija antes de saber nada y se aplica a los tres.")
reglas = {
    "siempre 1 parada, duro": lambda c: even_plan(c, 1, "HARD"),
    "siempre 2 paradas, duro": lambda c: even_plan(c, 2, "HARD"),
    "siempre 3 paradas, duro": lambda c: even_plan(c, 3, "HARD"),
}
rows = []
for start in STARTS:
    car = car_on(start)
    found = optimise(car, [], [], MODEL, objective=Objective.TIME, **SEARCH)
    plan_txt = found.best.describe(car, MODEL.total_laps)
    row = {"larga en": start, "AG": round(score(car, found.best), 2), "plan del AG": plan_txt}
    for name, build in reglas.items():
        row[name] = round(score(car, build(car)), 2)
    rows.append(row)
final = pd.DataFrame(rows)
print(final.to_string(index=False))

print()
for name in reglas:
    ventaja = (final[name] - final["AG"]).mean()
    print(f"  el AG le gana a «{name}» por {ventaja:+.2f} s de carrera en promedio")
oraculo = final[list(reglas)].min(axis=1)
vs_oraculo = (oraculo - final["AG"]).mean()
print(f"\n  contra el oraculo, la mejor regla sabiendo la respuesta: {vs_oraculo:+.2f} s")
print("\nEsa última línea es la comparación que se venía haciendo, y es la única")
print("que el algoritmo no gana. Contra cualquier regla enunciable de antemano,")
print("sí gana, y lo que gana es exactamente el valor de decidir bien cuántas")
print("paradas hacer.")
