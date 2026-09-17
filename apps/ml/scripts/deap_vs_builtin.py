"""El motor propio contra DEAP, sobre los mismos problemas.

El port a DEAP es un re-alojamiento: mismas semillas, misma aptitud con números
aleatorios comunes, mismo reparador, misma cruza y misma mutación. Lo único que
cambia es el bucle — el propio, elitista sobre el cuarto superior, contra
``algorithms.eaMuPlusLambda`` con selección por torneo.

Si el port está bien hecho los dos tienen que encontrar planes de valor
equivalente. No idénticos: son bucles distintos y el espacio tiene mesetas donde
varios planes valen lo mismo. Lo que importa es que ninguno le gane al otro de
forma sistemática.

Este script corre los dos sobre una grilla de problemas — tres compuestos de
salida, cuatro posiciones, tres objetivos, tres apetitos de riesgo, cinco
semillas — y compara el puntaje **fuera de muestra**, que es el único honesto.

Correr con ``uv run python scripts/deap_vs_builtin.py``.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

from boxbox_ml import strategy
from boxbox_ml.strategy import (
    Car,
    Engine,
    Objective,
    RaceModel,
    Risk,
    optimise,
    pace_from_qualifying,
)

pd.set_option("display.width", 210)
SEP = "=" * 88

LAPS = 57
MODEL = RaceModel(total_laps=LAPS)
SEARCH = dict(population=40, generations=25, draws=1200)

#: Huecos a la pole de Madrid 2026, para dar un campo con ritmo real.
MADRID_GAPS = (
    0.000,
    0.011,
    0.140,
    0.189,
    0.195,
    0.325,
    0.470,
    0.492,
    1.079,
    1.217,
    1.399,
    1.564,
    1.843,
    1.929,
    2.260,
    3.483,
    3.488,
    3.564,
    4.089,
    6.187,
)

FIELD = [
    Car(
        code=f"P{slot + 1}",
        compound="MEDIUM",
        tyre_age=0,
        degradation_s=0.0,
        degradation_rate=strategy.ROLLING_MEDIAN_S,
        gap_leader_s=gap,
        from_lap=1,
        pace_s=pace_from_qualifying(gap),
    )
    for slot, gap in enumerate(MADRID_GAPS)
]
_generator = np.random.default_rng(7)
FIELD_PLANS = [strategy._random_plan(car, MODEL, _generator, 3) for car in FIELD]


def others(slot: int):
    rivals = [car for index, car in enumerate(FIELD) if index != slot]
    plans = [plan for index, plan in enumerate(FIELD_PLANS) if index != slot]
    return rivals, plans


# ------------------------------------------------------ 1. qué registra el port

print(SEP)
print("### 1. LO QUE EL PORT REGISTRA EN EL TOOLBOX")
print()
print("  evaluate   la aptitud del proyecto: tiempo de carrera sobre sorteos")
print("             compartidos, resumido según el objetivo y el apetito")
print("  mate       cruza de un punto sobre la lista de paradas, y repara")
print("  mutate     alarga, acorta, cambia compuesto, agrega o saca una parada")
print("  select     tools.selTournament, tamaño 3")
print("  algoritmo  algorithms.eaMuPlusLambda, cxpb=0.6 mutpb=0.4")
print()
print("  Los operadores de caja de DEAP no sirven acá: el individuo es de largo")
print("  variable (una a cuatro paradas) y mezcla un entero con un compuesto, y")
print("  cxTwoPoint asume largo fijo y no sabe nada de las restricciones.")
print()
print("  El caché de aptitud de DEAP, que con Monte Carlo suele estar mal, acá es")
print("  correcto: con números aleatorios comunes la aptitud de un plan dado es")
print("  determinística. Si se saca la semilla fija, hay que desactivarlo.")

# ---------------------------------------------------------- 2. la comparación

print("\n" + SEP)
print("### 2. LOS DOS MOTORES SOBRE LOS MISMOS PROBLEMAS")
print()

CASES = []
for compound in ("SOFT", "MEDIUM", "HARD"):
    for seed in range(5):
        CASES.append(
            {
                "problema": f"pre-carrera {compound}",
                "car": Car("X", compound, 0, 0.0, strategy.ROLLING_MEDIAN_S, 0.0, 1),
                "rivals": [],
                "plans": [],
                "objective": Objective.TIME,
                "risk": Risk.NEUTRAL,
                "seed": seed,
            }
        )
for slot in (0, 9, 12, 19):
    rivals, plans = others(slot)
    for appetite in (Risk.NEUTRAL, Risk.AVERSE, Risk.SEEKING):
        for seed in range(5):
            CASES.append(
                {
                    "problema": f"grilla P{slot + 1} {appetite}",
                    "car": FIELD[slot],
                    "rivals": rivals,
                    "plans": plans,
                    "objective": Objective.ADAPTIVE,
                    "risk": appetite,
                    "seed": seed,
                }
            )

records = []
for case in CASES:
    row = {"problema": case["problema"], "semilla": case["seed"]}
    for engine in (Engine.BUILTIN, Engine.DEAP):
        started = time.perf_counter()
        found = optimise(
            case["car"],
            case["rivals"],
            case["plans"],
            MODEL,
            objective=case["objective"],
            risk=case["risk"],
            engine=engine,
            seed=case["seed"],
            **SEARCH,
        )
        row[f"{engine}_score"] = found.score
        row[f"{engine}_plan"] = found.best.describe(case["car"], LAPS)
        row[f"{engine}_s"] = time.perf_counter() - started
    records.append(row)

data = pd.DataFrame(records)
data["dif"] = data["deap_score"] - data["builtin_score"]
data["mismo plan"] = data["deap_plan"] == data["builtin_plan"]

summary = (
    data.groupby("problema")
    .agg(
        n=("dif", "size"),
        builtin=("builtin_score", "mean"),
        deap=("deap_score", "mean"),
        dif=("dif", "mean"),
        mismo_plan=("mismo plan", "mean"),
    )
    .round(3)
)
print(summary.to_string())

print("\n" + SEP)
print("### 3. EL VEREDICTO")
print()
wins = int((data["dif"] > 1e-9).sum())
losses = int((data["dif"] < -1e-9).sum())
ties = len(data) - wins - losses
print(f"  casos:              {len(data)}")
print(f"  DEAP mejor:         {wins}")
print(f"  propio mejor:       {losses}")
print(f"  empatan:            {ties}")
print(f"  mismo plan exacto:  {data['mismo plan'].mean():.1%}")
print(f"  diferencia media:   {data['dif'].mean():+.4f}")
print(f"  |diferencia| media: {data['dif'].abs().mean():.4f}")
print()
print(f"  tiempo propio:      {data['builtin_s'].mean():.2f} s por búsqueda")
print(f"  tiempo DEAP:        {data['deap_s'].mean():.2f} s por búsqueda")
print()
if abs(data["dif"].mean()) < 0.05 * max(data["builtin_score"].abs().mean(), 1e-9):
    print("  Ninguno le gana al otro de forma sistemática: el port es fiel y lo que")
    print("  queda es la variación propia de dos bucles distintos sobre un espacio")
    print("  con mesetas.")
else:
    print("  Hay una diferencia sistemática y hay que mirarla antes de confiar en")
    print("  el port.")

worst = data.reindex(data["dif"].abs().sort_values(ascending=False).index).head(5)
print("\n  los cinco casos donde más difieren:")
print(
    worst[["problema", "semilla", "builtin_plan", "deap_plan", "builtin_score", "deap_score"]]
    .round(3)
    .to_string(index=False)
)
