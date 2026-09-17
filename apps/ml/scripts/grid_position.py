"""La posición de largada, que el modelo no estaba mirando.

Hasta ahora el hueco a la pole entraba como un desplazamiento constante del
tiempo final. Una constante no cambia el orden entre planes, así que la búsqueda
recomendaba **el mismo plan desde la pole que desde el vigésimo**. Este script
muestra el agujero, lo tapa, y mide qué cambia.

La pieza que faltaba es un *ritmo*, no un hueco: segundos por vuelta que el auto
da al más rápido. Después de largar se infiere del terreno perdido; antes de
largar no hay historia — pero la clasificación lo mide directamente, porque una
diferencia de tiempo de vuelta ya es una cantidad por vuelta.
:data:`boxbox_ml.strategy.QUALI_TO_RACE_PACE` es cuánto de eso sobrevive: 0,835,
medido sobre 277 pilotos-carrera en ``scripts/quali_to_race_pace.py``.

Dos cosas que conviene entender del resultado:

* **Bajo TIME sigue sin cambiar nada, y está bien.** Un déficit constante por
  vuelta se suma igual a todos los candidatos. "La forma más rápida de cubrir la
  distancia" genuinamente no depende de dónde largaste. Lo que la posición
  desbloquea es el campo.
* **Donde sí cambia es en la burbuja de los puntos.** Los autos que pelean el
  último puesto pagador paran antes — el undercut — y los que están cómodos
  adentro o afuera, no.

Correr con ``uv run python scripts/grid_position.py``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from boxbox_ml import strategy
from boxbox_ml.strategy import Car, Objective, RaceModel, optimise, pace_from_qualifying

pd.set_option("display.width", 200)
SEP = "=" * 88

#: Madrid 2026, la clasificación real: hueco a la pole por posición de grilla.
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
LAPS = 57
MODEL = RaceModel(total_laps=LAPS)
SEARCH = dict(population=40, generations=25, draws=1200, seed=11)
SHOWN = (0, 1, 4, 7, 9, 10, 12, 15, 19)


def car_at(slot: int, compound: str = "MEDIUM", *, with_pace: bool) -> Car:
    """Un auto largando desde ``slot`` (base cero), con o sin ritmo declarado."""
    gap = MADRID_GAPS[slot]
    return Car(
        code=f"P{slot + 1}",
        compound=compound,
        tyre_age=0,
        degradation_s=0.0,
        degradation_rate=strategy.ROLLING_MEDIAN_S,
        gap_leader_s=gap,
        from_lap=1,
        pace_s=pace_from_qualifying(gap) if with_pace else None,
    )


print(SEP)
print("### 1. EL AGUJERO: OBJETIVO TIEMPO, SIN RITMO DECLARADO")
print("Mismo compuesto de salida, sólo cambia la posición.")
print()
rows = []
for slot in SHOWN:
    car = car_at(slot, with_pace=False)
    found = optimise(car, [], [], MODEL, objective=Objective.TIME, **SEARCH)
    rows.append(
        {
            "larga": slot + 1,
            "hueco pole": MADRID_GAPS[slot],
            "plan": found.best.describe(car, LAPS),
            "tiempo": round(-found.score, 1),
        }
    )
print(pd.DataFrame(rows).to_string(index=False))
print()
print("  El plan es idéntico en toda la grilla. El hueco mueve el tiempo y no el")
print("  plan, porque se suma igual a cada candidato.")

print("\n" + SEP)
print("### 2. CON EL RITMO DECLARADO, PERO TODAVIA OBJETIVO TIEMPO")
print()
rows = []
for slot in SHOWN:
    car = car_at(slot, with_pace=True)
    found = optimise(car, [], [], MODEL, objective=Objective.TIME, **SEARCH)
    rows.append(
        {
            "larga": slot + 1,
            "pace s/vuelta": round(car.pace_s or 0.0, 2),
            "plan": found.best.describe(car, LAPS),
            "tiempo": round(-found.score, 1),
        }
    )
print(pd.DataFrame(rows).to_string(index=False))
print()
print("  Sigue igual, y tiene que seguir igual: TIME ignora al campo por")
print("  definición. Lo que cambió es que ahora el tiempo refleja el ritmo real,")
print("  que es lo que los objetivos con campo necesitan para ordenar la carrera.")

print("\n" + SEP)
print("### 3. CON EL CAMPO: OBJETIVO ADAPTATIVO")
print("Veinte autos con su ritmo de clasificación, cada uno con un plan sorteado.")
print()
field = [car_at(slot, with_pace=True) for slot in range(len(MADRID_GAPS))]
generator = np.random.default_rng(7)
rival_plans = [strategy._random_plan(car, MODEL, generator, 3) for car in field]

rows = []
for slot in SHOWN:
    car = field[slot]
    rivals = [other for index, other in enumerate(field) if index != slot]
    plans = [plan for index, plan in enumerate(rival_plans) if index != slot]
    found = optimise(car, rivals, plans, MODEL, objective=Objective.ADAPTIVE, **SEARCH)
    spread = " ".join(f"{k}:{v:.2f}" for k, v in found.stop_distribution.items())
    rows.append(
        {
            "larga": slot + 1,
            "pace": round(car.pace_s or 0.0, 2),
            "plan": found.best.describe(car, LAPS),
            "objetivo": str(found.objective),
            "valor": round(found.score, 2),
            "convergencia": spread,
        }
    )
table = pd.DataFrame(rows)
print(table.to_string(index=False))
print()
print("  Dos cosas que antes no podían pasar:")
print()
print("  1. El objetivo se conmuta solo. Del primero al decimotercero la búsqueda")
print("     optimiza PUNTOS; del decimosexto para atrás los puntos son inalcanzables,")
print("     la aptitud se aplana, y ADAPTIVE pasa a POSICION.")
print("  2. Los autos de la burbuja paran ANTES. Es el undercut: al que pelea el")
print("     último puesto pagador le sirve la posición de pista, y al que está")
print("     cómodo adentro o afuera no.")

print("\n" + SEP)
print("### LO QUE ESTO TODAVIA NO HACE")
print()
print("  La aptitud sigue siendo un PROMEDIO, o sea neutral al riesgo. El que va")
print("  décimo tiene un punto: perderlo cuesta uno y ganar el noveno gana uno, así")
print("  que ante un 50/50 entre octavo y duodécimo el modelo calcula 2 contra 1 y")
print("  TOMA la apuesta. Ningún equipo real hace eso.")
print()
print("  Para que el décimo defienda hace falta optimizar un cuantil en vez de la")
print("  media: el de adelante el p25 (que el mal caso sea bueno), el de atrás el")
print("  p75 (que el buen caso sea excelente). Los sorteos ya están; falta usarlos.")
