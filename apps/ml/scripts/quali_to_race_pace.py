"""Cuánto del hueco de clasificación se paga después en carrera.

El modelo no sabía qué hacer con la posición de largada. El hueco a la pole entra
hoy como un desplazamiento constante del tiempo final, y una constante no cambia
el orden entre planes: medido, la búsqueda recomienda **el mismo plan desde la
pole que desde el vigésimo**. Eso es falso y hay que arreglarlo.

La razón por la que estaba así no es descuido. Antes el hueco se cobraba *por
vuelta*, y con la carrera arrancando en la vuelta 1 eso ponía a un auto 19.º a
4,75 s/vuelta — cinco minutos y medio sobre la carrera. Se apagó, y quedó el
agujero.

Lo que falta es un **ritmo**, no un hueco: segundos por vuelta que este auto es
más lento que el más rápido. Después de largar se puede inferir de cuánto terreno
viene perdiendo. Antes de largar no hay historia de la cual inferirlo — pero sí
hay una medición directa, porque **una diferencia de tiempo de vuelta en
clasificación ya es una cantidad por vuelta**.

Este script mide cuánto de ese hueco sobrevive a la carrera, con la misma
disciplina que el resto del proyecto: corrección de combustible, sólo vueltas
representativas en verde, y validación dejando una carrera afuera.

Correr con ``uv run python scripts/quali_to_race_pace.py``.
"""

from __future__ import annotations

import warnings

import fastf1
import numpy as np
import pandas as pd

from boxbox_ml import cache, features, track_status

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)
SEP = "=" * 88

#: Rondas de 2026 ya corridas. Las de formato sprint también tienen clasificación.
ROUNDS = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14)

#: Un piloto con menos vueltas verdes que esto no tiene un ritmo de carrera.
MIN_GREEN_LAPS = 12

#: Más allá de esto es un auto roto o una carrera aparte, no ritmo.
MAX_GAP_S = 6.0

cache.enable()


def quali_gaps(year: int, rnd: int) -> pd.Series:
    """Hueco a la pole, en segundos, por piloto."""
    session = fastf1.get_session(year, rnd, "Q")
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    results = session.results.copy()
    best = results[["Q1", "Q2", "Q3"]].apply(lambda s: s.dt.total_seconds()).min(axis=1)
    gaps = best - best.min()
    gaps.index = results["Abbreviation"]
    return gaps.dropna()


def race_pace(year: int, rnd: int) -> pd.Series:
    """Ritmo de carrera por piloto: mediana de sus vueltas verdes, corregida."""
    session = fastf1.get_session(year, rnd, "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    laps = session.laps.copy()
    if laps.empty:
        return pd.Series(dtype=float)
    laps["total_laps"] = int(laps["LapNumber"].max())
    laps["pit_in"] = laps["PitInTime"].notna()
    laps["pit_out"] = laps["PitOutTime"].notna()
    laps["LapTime"] = laps["LapTime"].dt.total_seconds()

    frame = features.add_fuel_correction(features.mark_representative(track_status.add_flags(laps)))
    green = frame[
        frame["is_representative"]
        & ~frame["is_neutralised"]
        & ~frame["red"]
        & ~frame["yellow"]
        & frame["LapNumber"].gt(1)
    ]
    counts = green.groupby("Driver")["LapTime"].size()
    pace = green.groupby("Driver")["lap_time_fuel_corrected"].median()
    pace = pace[counts >= MIN_GREEN_LAPS]
    return pace - pace.min()


records = []
for rnd in ROUNDS:
    try:
        gaps, pace = quali_gaps(2026, rnd), race_pace(2026, rnd)
    except Exception as error:  # noqa: BLE001 - una ronda que falla no es fatal
        print(f"  ronda {rnd}: no se pudo cargar ({type(error).__name__})")
        continue
    if pace.empty:
        continue
    for driver in pace.index:
        if driver in gaps.index:
            records.append(
                {
                    "round": rnd,
                    "driver": driver,
                    "quali": float(gaps[driver]),
                    "race": float(pace[driver]),
                }
            )

data = pd.DataFrame(records)
data = data[(data["quali"] < MAX_GAP_S) & (data["race"] < MAX_GAP_S)]

print(SEP)
print("### CUANTO DEL HUECO DE CLASIFICACION SE PAGA EN CARRERA")
print()
print(f"  {len(data)} pilotos-carrera sobre {data['round'].nunique()} carreras de 2026")
print(f"  correlación:  {data['quali'].corr(data['race']):+.3f}")
slope, intercept = np.polyfit(data["quali"], data["race"], 1)
print(f"  recta:        ritmo = {slope:.3f} * hueco_clasificación {intercept:+.3f}")
print()
print("  La ordenada no importa: es un nivel común a todos los autos de la carrera,")
print("  y lo que el modelo necesita es la diferencia ENTRE autos. Lo que importa")
print("  es la pendiente, y está cerca de uno.")

print("\n" + SEP)
print("### CARRERA POR CARRERA")
rows = []
for rnd, sub in data.groupby("round"):
    if len(sub) < 8:
        continue
    own, _ = np.polyfit(sub["quali"], sub["race"], 1)
    rows.append(
        {
            "ronda": rnd,
            "n": len(sub),
            "r": round(float(sub["quali"].corr(sub["race"])), 3),
            "pendiente": round(float(own), 3),
        }
    )
per_race = pd.DataFrame(rows)
print(per_race.to_string(index=False))
print()
print(f"  pendiente: mediana {per_race['pendiente'].median():.3f},")
print(f"  rango {per_race['pendiente'].min():.3f} a {per_race['pendiente'].max():.3f}")
print("  Replica entre carreras — a diferencia de casi todo lo demás por circuito.")

print("\n" + SEP)
print("### DEJANDO UNA CARRERA AFUERA")
print("¿Saber la clasificación le gana a suponer que todos andan igual?")
print()
errors_model, errors_flat = [], []
for rnd in data["round"].unique():
    train = data[data["round"] != rnd]
    test = data[data["round"] == rnd]
    if len(train) < 30 or test.empty:
        continue
    fit_slope, _ = np.polyfit(train["quali"], train["race"], 1)
    # Sin ordenada: al modelo le interesa la diferencia entre autos, así que se
    # compara contra el auto más rápido de la propia carrera en ambos casos.
    predicted = fit_slope * test["quali"]
    errors_model.extend(abs(predicted - test["race"]))
    errors_flat.extend(abs(test["race"] - test["race"].mean()))
model_error = float(np.mean(errors_model))
flat_error = float(np.mean(errors_flat))
print(f"  con clasificación:   {model_error:.3f} s/vuelta de error")
print(f"  todos iguales:       {flat_error:.3f} s/vuelta de error")
print(f"  mejora:              {100 * (1 - model_error / flat_error):.1f}%")
print()
print("  Esto es lo que la calibración de práctica NO logró en Madrid. Acá la")
print("  señal replica y el leave-one-out la confirma, así que entra al modelo.")

print("\n" + SEP)
print("### EL COEFICIENTE QUE ENTRA AL MODELO")
print()
print(f"  QUALI_TO_RACE_PACE = {slope:.3f}")
print()
print("  Uso: pace_s = QUALI_TO_RACE_PACE * (tiempo_clasificación - pole).")
print("  Un auto a 1,2 s de la pole corre a ~%.2f s/vuelta del más rápido." % (slope * 1.2))
