"""¿Cuánto vale sembrar la población con las heurísticas, y qué aporta exactamente?

La población de la búsqueda arranca con seis planes obvios —una división pareja
para cero a cuatro paradas, más el de vida de goma— y treinta y cuatro al azar.
La pregunta razonable, y la hizo el usuario mirando que el mejor de HAM no se
movía en veinticinco generaciones, es si eso tiene sentido: sembrar garantiza
que la búsqueda no puede salir peor que la regla, pero también impide distinguir
si el algoritmo **encontró** la respuesta o si simplemente se quedó con la
semilla.

Este script lo mide corriendo la grilla entera de las dos formas.

## La respuesta, y no es la que parecía con tres autos

Soltando la siembra, sobre los veintidós:

    peor en  7/22      mejor en  2/22      igual en 13/22
    diferencia mediana  +0,000      media  -2,871

La mediana es cero y la media es catastrófica, que es la firma de un efecto que
no le pasa a casi nadie y arruina a unos pocos. Los siete que se caen no se caen
un poco: GAS, TSU, HUL y COL pierden **más de quince puntos**.

## Qué aportan las semillas, exactamente

El plan, no el puntaje. Mirando a HUL y COL:

    sembrada   H41-M30       una parada
    libre      H23-H28-S20   dos paradas

Las semillas aportan **la región de pocas paradas con tandas largas**, y es la
que el azar no alcanza. Un plan de una parada necesita una tanda de cuarenta
vueltas; generarlo al azar exige acertar a la vez la vuelta y el compuesto, y
`_repair` además separa las paradas por ``MIN_STINT``, así que sortear dos o tres
paradas es muchísimo más probable que sortear una. La heurística de una parada lo
construye a propósito.

Y a quién le importa eso: a los autos de la **burbuja de los puntos**. GAS, TSU,
HUL y COL puntúan cerca de cero sembrados, o sea que están justo en el borde de
la zona de puntos, y ahí acertar una parada en vez de dos es la diferencia entre
sumar y no sumar. Arriba y abajo de la tabla no cambia nada: catorce de los
veintidós dan idéntico.

No es que el azar no pueda llegar nunca —OCO, BOT y PER encuentran `H40-M31` sin
ayuda— es que no llega de forma confiable.

## Lo que esto corrige

El comentario que justificaba la siembra en ``strategy.py`` citaba la evidencia
equivocada: 118 planes al azar cuyo mejor daba 93,3 s contra 91,0 de una división
pareja. Eso es sobre la población **inicial**, y la objeción obvia es que para
eso está la evolución. La evidencia correcta es ésta, que mide el resultado
después de evolucionar, y sostiene la misma conclusión con mucha más fuerza.

También descarta la salida fácil de darle más tiempo: con 100 y con 300
generaciones el resultado es **idéntico** al de 25. Todas las corridas convergen
alrededor de la generación 21 y se quedan quietas. El problema no es que falte
buscar, es que esa región del espacio no se alcanza sorteando.

Correr con ``uv run python scripts/seeding_value.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from boxbox_ml import strategy as st
from boxbox_ml.strategy import Car, Objective, Plan, RaceModel, Risk, Stop, optimise

SEP = "=" * 88
EXPORT = Path(__file__).resolve().parents[3] / "docs" / "research" / "prerace-zandvoort.json"

export = json.loads(EXPORT.read_text(encoding="utf-8"))
laps = int(export["race"]["total_laps"])
model = RaceModel.for_circuit("Zandvoort", total_laps=laps)

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

print(SEP)
print("### CON Y SIN SEMILLAS, LOS VEINTIDOS AUTOS")
print()
print(f"  {'auto':5s} {'sembrada':>9s} {'plan':18s} {'libre':>9s} {'plan':18s} {'dif':>8s}")

rows = []
for index, focal in enumerate(cars):
    rivals = [c for i, c in enumerate(cars) if i != index]
    rival_plans = [p for i, p in enumerate(plans) if i != index]
    found = {}
    for sown in (True, False):
        search = optimise(
            focal,
            rivals,
            rival_plans,
            model,
            objective=Objective.ADAPTIVE,
            risk=Risk.ADAPTIVE,
            population=40,
            generations=25,
            draws=1200,
            seed=11,
            seed_heuristics=sown,
            instrument=True,
        )
        best = [gen.best for gen in search.history]
        settled = max(i for i, v in enumerate(best) if i == 0 or v > best[i - 1] + 1e-9)
        found[sown] = (search.score, search.best.describe(focal, laps), settled, search.best.count)
    rows.append((focal.code, found))
    sown, free = found[True], found[False]
    print(
        f"  {focal.code:5s} {sown[0]:9.3f} {sown[1]:18s} {free[0]:9.3f} {free[1]:18s}"
        f" {free[0] - sown[0]:+8.3f}"
    )

gaps = [f[False][0] - f[True][0] for _code, f in rows]
print()
worse = sum(1 for g in gaps if g < -1e-6)
better = sum(1 for g in gaps if g > 1e-6)
print(f"  libre peor en {worse}/22, mejor en {better}/22")
print(f"  diferencia mediana {np.median(gaps):+.3f}, media {np.mean(gaps):+.3f}")
print()
print("  La mediana en cero con la media por el piso es la firma de un efecto que")
print("  no le pasa a casi nadie y arruina a unos pocos.")

print("\n" + SEP)
print("### A QUIEN LE PASA, Y QUE LE APORTAN LAS SEMILLAS")
print()
hurt = [(code, f) for code, f in rows if f[False][0] - f[True][0] < -1.0]
print(f"  {'auto':5s} {'sembrada':>9s} {'paradas':>8s}   {'libre':>9s} {'paradas':>8s}")
for code, f in hurt:
    print(f"  {code:5s} {f[True][0]:9.3f} {f[True][3]:8d}   {f[False][0]:9.3f} {f[False][3]:8d}")
print()
print("  Lo que las semillas aportan es el PLAN, no el puntaje: la región de")
print("  pocas paradas con tandas largas, que es la que el azar no alcanza. Un")
print("  plan de una parada necesita una tanda de cuarenta vueltas, y sortearlo")
print("  exige acertar a la vez la vuelta y el compuesto mientras `_repair`")
print("  separa las paradas por MIN_STINT. La heurística lo construye a propósito.")
print()
print("  Y le importa a los autos de la BURBUJA DE LOS PUNTOS: puntúan cerca de")
print("  cero sembrados, o sea que están en el borde, y ahí acertar una parada en")
print("  vez de dos es la diferencia entre sumar y no sumar.")

print("\n" + SEP)
print("### LO QUE NO CAMBIA")
print()
same = sum(1 for _code, f in rows if f[True][1] == f[False][1])
print(f"  mismo plan en {same}/22: arriba y abajo de la tabla la siembra da igual.")
settled_sown = np.median([f[True][2] for _code, f in rows])
settled_free = np.median([f[False][2] for _code, f in rows])
print(
    f"  generación de la última mejora, mediana:"
    f" sembrada g{settled_sown:.0f}, libre g{settled_free:.0f}"
)
flat_sown = sum(1 for _code, f in rows if f[True][2] == 0)
flat_free = sum(1 for _code, f in rows if f[False][2] == 0)
print(f"  autos cuyo mejor no se mueve nunca: sembrada {flat_sown}, libre {flat_free}")
print()
print("  La corrida libre SI muestra más evolución, que era la objeción estética")
print("  de fondo. Pero la paga con siete autos mucho peor, y cuatro de ellos")
print("  perdiendo más de quince puntos.")
