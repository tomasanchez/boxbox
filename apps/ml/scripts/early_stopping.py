"""¿La última generación del algoritmo genético es la mejor?

Salió de dibujar la curva de validación, que es para lo que sirven esas curvas.
Con la aptitud en muestra el algoritmo mejora monótonamente —el motor propio es
elitista, el mejor nunca empeora— pero **medido sobre carreras que la búsqueda
nunca vio, la última generación a veces es peor que una anterior.**

El caso que lo destapó: la búsqueda cambia en la generación 6 de ``M24-H24-H24``
a ``M24-H28-H20``, gana 0,07 s en muestra, y sobre 80.000 sorteos independientes
el plan nuevo es **0,608 s más lento** (error estándar 0,053 — once veces el
error, así que no es ruido). Cambió una ganancia de medición por una pérdida
real.

Este script mide si pasa seguido, sobre ocho semillas y los tres compuestos de
salida. El arreglo, si pasa, es el mismo que en cualquier modelo entrenado:
**parada temprana** — quedarse con la generación que mejor puntúa fuera de
muestra en vez de con la última.

Lo que está en juego no es poco: la ventaja del algoritmo sobre la mejor regla
enunciable es de unas décimas, así que una pérdida de ese orden por no parar a
tiempo se come buena parte de lo que el algoritmo aporta.

Correr con ``uv run python scripts/early_stopping.py``. Deja los números en
``apps/ml/data/early_stopping.json`` para ``scripts/validation_plots.py``.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from boxbox_ml import strategy
from boxbox_ml.strategy import Car, Objective, RaceModel, draw_neutralisations, race_time

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)

#: Sorteos para juzgar un plan. Muy por encima de los 1.200 con los que corre la
#: búsqueda: acá no se busca, se arbitra, y el arbitraje tiene que ser más
#: preciso que lo que juzga.
SORTEOS = 20_000
SEMILLAS = range(8)
SALIDAS = ("MEDIUM", "HARD", "SOFT")


def medir() -> pd.DataFrame:
    """Una fila por corrida: cuánto pierde quedarse con la última generación."""
    model = RaceModel()
    # TRES juegos de carreras, y hacen falta los tres.
    #
    # Elegir la mejor generación y puntuarla sobre el MISMO juego no mide nada:
    # el mínimo de veintiséis estimaciones ruidosas está sesgado hacia abajo por
    # construcción, que es el mismo error que este proyecto ya documenta cuando
    # reporta `score` en vez de `score_in_sample`. Así que la generación se elige
    # en VALIDACION y se la puntúa en PRUEBA, que la elección nunca vio.
    #
    # La búsqueda corre contra su propio juego interno, que no es ninguno de estos.
    validacion = draw_neutralisations(model, np.random.default_rng(4242), SORTEOS)
    prueba = draw_neutralisations(model, np.random.default_rng(8615), SORTEOS)

    filas = []
    for seed in SEMILLAS:
        for salida in SALIDAS:
            car = Car("F", salida, 0, 0.0, strategy.ROLLING_MEDIAN_S, 0.0, 1)
            vacio = np.empty((0, model.total_laps - car.from_lap + 2, SORTEOS))
            hallado = strategy.optimise(
                car,
                [],
                [],
                model,
                objective=Objective.TIME,
                population=40,
                generations=25,
                draws=1200,
                seed=seed,
                instrument=True,
            )
            registro = [g for g in hallado.history if g.best_plan is not None]

            def tiempo(plan, flags, car=car, vacio=vacio) -> float:
                # `car` y `vacio` se atan por omisión: sin eso la función tomaría
                # el valor que la variable tenga al llamarla, no al definirla.
                gen = np.random.default_rng(31)
                return float(race_time(plan, car, model, gen, SORTEOS, flags, vacio).mean())

            # La elección se hace acá...
            elegida = int(np.argmin([tiempo(g.best_plan, validacion) for g in registro]))
            # ...y se la juzga acá, sobre carreras que no intervinieron en elegirla.
            en_prueba_elegida = tiempo(registro[elegida].best_plan, prueba)
            en_prueba_ultima = tiempo(registro[-1].best_plan, prueba)
            filas.append(
                {
                    "semilla": seed,
                    "larga": salida,
                    "ultima_s": en_prueba_ultima,
                    "elegida_s": en_prueba_elegida,
                    "perdida_s": en_prueba_ultima - en_prueba_elegida,
                    "gen_elegida": registro[elegida].index,
                    "plan_ultima": registro[-1].best_plan.describe(car, model.total_laps),
                    "plan_elegida": registro[elegida].best_plan.describe(car, model.total_laps),
                }
            )
    return pd.DataFrame(filas)


corridas = medir()
# Un umbral para no contar como «pierde» una diferencia que es redondeo.
pierde = corridas[corridas["perdida_s"] > 0.01]

print("=" * 92)
print("### ¿CONVIENE PARAR ANTES? ELECCION EN VALIDACION, JUICIO EN PRUEBA")
print()
print(corridas.round(3).to_string(index=False))
print()
print(f"  corridas donde parar antes GANA en prueba: {len(pierde)} de {len(corridas)}")
print(f"  ganancia media cuando gana:              {pierde['perdida_s'].mean():.3f} s")
print(f"  ganancia máxima:                         {corridas['perdida_s'].max():.3f} s")
print(f"  ganancia media sobre TODAS las corridas: {corridas['perdida_s'].mean():+.3f} s")
print(f"  corridas donde parar antes PIERDE:       {int((corridas['perdida_s'] < -0.01).sum())}")
print()
print("  La lectura: con la aptitud en muestra la búsqueda nunca empeora —el motor")
print("  es elitista— pero eso no garantiza nada afuera. Elegir el máximo de muchas")
print("  estimaciones ruidosas elige en parte por suerte, y en la mitad larga de las")
print("  corridas la suerte se agota después de la generación que de verdad servía.")
print()
print("  El arreglo es el de cualquier modelo entrenado: PARADA TEMPRANA sobre un")
print("  juego retenido. No está implementado; queda declarado y medido.")

destino = Path(__file__).resolve().parents[1] / "data" / "early_stopping.json"
destino.parent.mkdir(parents=True, exist_ok=True)
destino.write_text(
    json.dumps(
        {
            "sorteos": SORTEOS,
            "corridas": corridas.to_dict(orient="records"),
            "resumen": {
                "total": int(len(corridas)),
                "pierden": int(len(pierde)),
                "perdida_media_cuando_pierde": float(pierde["perdida_s"].mean()),
                "perdida_maxima": float(corridas["perdida_s"].max()),
                "perdida_media_global": float(corridas["perdida_s"].mean()),
            },
        },
        indent=2,
    ),
    encoding="utf-8",
)
print(f"\nnúmeros volcados en {destino}")
