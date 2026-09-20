"""Apetito de riesgo: por qué el décimo defiende y el undécimo apuesta.

Todos los objetivos del buscador eran un **promedio**, o sea neutrales al riesgo,
y un muro de boxes no lo es. El caso más claro es el último puesto pagador. El
que va décimo tiene un punto: perderlo cuesta uno y ganar el noveno gana uno. Ante
un 50/50 entre octavo y duodécimo el valor esperado calcula ``0,5*4 + 0,5*0 = 2``
contra ``1`` por quedarse quieto, así que el modelo **toma la apuesta**. Ningún
equipo hace eso.

La solución no es una regla por posición: es dejar de resumir la distribución por
su media. Los sorteos ya están; lo que cambia es sobre qué parte de ellos se
puntúa el plan.

Dos cosas que costaron y conviene que queden escritas:

1. **El cuantil no sirve, la media de la cola sí.** El primer intento puntuaba
   sobre el cuartil mismo. Pero un cuantil de una cantidad discreta es discreto —
   la posición es un entero — y columnas enteras de planes empataban en -12,00
   exacto. Una aptitud que no distingue dos planes no le da nada que escalar a la
   búsqueda. Promediar la cola lo arregla porque se mueve de a poco.
2. **Sobre los puntos la cola se aplana**, y justo para los autos que esto venía a
   ayudar: el cuarto peor de las carreras de un auto de la burbuja termina fuera
   de los diez, así que todos los planes valen cero ahí. Lo salva el respaldo que
   ya existía — ``Objective.ADAPTIVE`` cae a ``POSITION`` cuando los puntos se
   aplanan — y el riesgo termina mordiendo sobre la posición, no sobre los puntos.

Correr con ``uv run python scripts/risk_appetite.py``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from boxbox_ml import strategy
from boxbox_ml.strategy import (
    RISK_TAIL,
    Car,
    Objective,
    Plan,
    RaceModel,
    Risk,
    Stop,
    _positions,
    _score,
    draw_neutralisations,
    optimise,
    pace_from_qualifying,
    race_time,
    race_trace,
)

pd.set_option("display.width", 210)
SEP = "=" * 88

#: Madrid 2026: hueco a la pole por posición de grilla.
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
DRAWS = 8000

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


def others(slot: int) -> tuple[list[Car], list[Plan]]:
    """Todos menos el auto en ``slot``, con sus planes sorteados."""
    rivals = [car for index, car in enumerate(FIELD) if index != slot]
    plans = [plan for index, plan in enumerate(FIELD_PLANS) if index != slot]
    return rivals, plans


# ------------------------------------------- 1. el vuelco, sobre dos planes fijos

print(SEP)
print("### 1. EL VUELCO: DOS PLANES PARA EL AUTO QUE LARGA DECIMO")
print("Mismas carreras sorteadas para los dos. Lo único que cambia es sobre qué")
print("parte de la distribución se los puntúa.")
print()

SLOT = 9
car = FIELD[SLOT]
rivals, rival_plans = others(SLOT)
generator = np.random.default_rng(11)
flags = draw_neutralisations(MODEL, generator, DRAWS)
rival_trace = np.stack(
    [
        race_trace(plan, rival, MODEL, generator, DRAWS, flags)
        for rival, plan in zip(rivals, rival_plans, strict=True)
    ]
)
rival_times = rival_trace[:, -1, :]


def plan_of(*stops: tuple[int, str]) -> Plan:
    return Plan(strategy._repair([Stop(lap, compound) for lap, compound in stops], car, MODEL))


CANDIDATES = {
    "una parada": plan_of((16, "HARD")),
    "dos paradas": plan_of((18, "HARD"), (37, "HARD")),
}

shape: dict[str, list[tuple[int, int]]] = {
    str(a): [] for a in (Risk.NEUTRAL, Risk.AVERSE, Risk.SEEKING)
}
rows = []
for label, plan in CANDIDATES.items():
    times = race_time(plan, car, MODEL, np.random.default_rng(4242), DRAWS, flags, rival_trace)
    position = _positions(times, rival_times)
    rows.append(
        {
            "plan": f"{label} {plan.describe(car, LAPS)}",
            "puntos medios": round(_score(times, rival_times, Objective.POINTS, None), 2),
            "posición media": round(float(position.mean()), 2),
            "cuarto peor": round(
                -_score(times, rival_times, Objective.POSITION, RISK_TAIL[Risk.AVERSE]), 2
            ),
            "cuarto mejor": round(
                -_score(times, rival_times, Objective.POSITION, RISK_TAIL[Risk.SEEKING]), 2
            ),
            "P(top10)": round(float((position <= 10).mean()), 3),
            "sd posición": round(float(position.std()), 2),
        }
    )
table = pd.DataFrame(rows)
print(table.to_string(index=False))
print()
# Los dos números salen de la tabla, no escritos a mano: son la misma cifra que
# la columna «cuarto peor» de arriba y se movieron cuando cambió la pérdida de
# boxes. Copiarlos al texto es cómo se envejece una conclusión sin notarlo.
_one, _two = (table.set_index("plan").loc[k, "cuarto peor"] for k in table["plan"])
print("  El paradón es mejor en media, mejor en el cuarto bueno, y PEOR en el malo.")
print("  Eso es una apuesta, y el promedio la esconde. Las dos paradas cuestan")
print(f"  posición esperada y compran el mal caso: {_two:.1f} en vez de {_one:.1f}.")
print()
print("  AVERSE elige el de dos paradas, SEEKING el de una, y las dos respuestas")
print("  son correctas — para autos distintos.")

# ------------------------------------------------- 2. lo que elige la búsqueda

print("\n" + SEP)
print("### 2. LO QUE ELIGE LA BUSQUEDA, SEGUN EL APETITO")
print()
rows = []
for slot in (0, 4, 8, 9, 10, 12, 15, 19):
    focal = FIELD[slot]
    rivals, rival_plans = others(slot)
    row: dict[str, object] = {"larga": slot + 1}
    for appetite in (Risk.NEUTRAL, Risk.AVERSE, Risk.SEEKING):
        found = optimise(
            focal, rivals, rival_plans, MODEL, objective=Objective.ADAPTIVE, risk=appetite, **SEARCH
        )
        row[str(appetite)] = f"{found.best.describe(focal, LAPS)} {str(found.objective)[:3]}"
        shape[str(appetite)].append((found.best.count, found.best.stops[0].lap))
    resolved = optimise(
        focal,
        rivals,
        rival_plans,
        MODEL,
        objective=Objective.ADAPTIVE,
        risk=Risk.ADAPTIVE,
        **SEARCH,
    )
    row["adaptativo elige"] = str(resolved.risk)
    row["paradas"] = resolved.best.count
    rows.append(row)
print(pd.DataFrame(rows).to_string(index=False))
print()
# El patrón se LEE del cuadro en vez de estar escrito a mano. Una versión
# anterior afirmaba que el conservador parte la carrera en más tandas, y dejó de
# ser cierto cuando la pérdida de boxes pasó de una triangular a su distribución
# medida: con la cola representada, parar dos veces expone dos veces a una
# parada mala, y el conservador dejó de comprar previsibilidad con una parada
# extra. La afirmación sobrevivió tres corridas a su propia evidencia. Ahora no
# puede: sale del dato.
mean_stops = {k: sum(c for c, _ in v) / len(v) for k, v in shape.items()}
mean_lap = {k: sum(lap for _, lap in v) / len(v) for k, v in shape.items()}
AV, SK = str(Risk.AVERSE), str(Risk.SEEKING)
print(f"  paradas promedio   AVERSE {mean_stops[AV]:.2f}   SEEKING {mean_stops[SK]:.2f}")
print(f"  primera parada     AVERSE vuelta {mean_lap[AV]:.1f}   SEEKING vuelta {mean_lap[SK]:.1f}")
print()
if mean_stops[AV] > mean_stops[SK] + 0.1:
    print("  El conservador parte la carrera en más tandas y el arriesgado se juega")
    print("  a menos: un paradón apuesta a que la goma aguante y a que salga un")
    print("  safety car, y una parada extra compra previsibilidad.")
elif mean_lap[AV] > mean_lap[SK] + 1.0:
    print("  Los dos apetitos paran la MISMA cantidad de veces, y se separan en")
    print("  CUANDO. El arriesgado para temprano y se juega una tanda final larga")
    print("  a que la goma aguante; el conservador estira la primera tanda y parte")
    print("  la carrera más parejo, que es la apuesta más chica de las dos.")
else:
    print("  Los dos apetitos eligen planes de forma parecida en este cuadro: la")
    print("  diferencia que separa AVERSE de SEEKING no se lee acá.")
print()
print("  Y el apetito adaptativo hace lo que pediste: AVERSE mientras haya algo que")
print("  defender, SEEKING cuando ya no queda nada que perder.")

# ------------------------------------------------------- 3. lo que no funcionó

print("\n" + SEP)
print("### 3. LO QUE NO FUNCIONO, Y POR QUE")
print()
print("Sobre los PUNTOS, la cola mala del auto de la burbuja es cero en todo plan:")
rows = []
for label, plan in CANDIDATES.items():
    times = race_time(plan, car, MODEL, np.random.default_rng(4242), DRAWS, flags, rival_trace)
    rows.append(
        {
            "plan": label,
            "puntos, media": round(_score(times, rival_times, Objective.POINTS, None), 2),
            "puntos, cuarto peor": round(
                _score(times, rival_times, Objective.POINTS, RISK_TAIL[Risk.AVERSE]), 2
            ),
        }
    )
print(pd.DataFrame(rows).to_string(index=False))
print()
print("  Los dos valen cero, así que sobre puntos la aptitud se aplana justo para")
print("  el auto que esto venía a ayudar. No es un error de implementación: el")
print("  cuarto peor de las carreras de un auto décimo termina fuera de los diez.")
print()
print("  Lo salva el respaldo que ya existía: ADAPTIVE cae a POSICION cuando los")
print("  puntos no tienen gradiente, y ahí el riesgo sí muerde. Por eso la tabla")
print("  de la sección 1 está en posiciones y no en puntos.")
