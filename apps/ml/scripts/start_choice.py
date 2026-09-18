"""Qué compuesto se elige de verdad, cuando la elección llega a significar algo.

Zandvoort 2026 tuvo bandera roja en la vuelta 2 y **veintiuno de los veintidós
autos pararon ahí**. El compuesto con el que largaron duró dos vueltas y después
todos cambiaron gratis. Comparar la recomendación del modelo contra esa grilla es
comparar contra una elección que casi no tuvo consecuencia — y peor: sabiendo que
el reglamento obliga a usar dos compuestos secos, largar con el que menos gusta y
cambiarlo gratis en la vuelta 2 es exactamente la jugada con la que Antonelli ganó
Monza. Varios de esos blandos pueden haber sido **tanda de cumplimiento** y no una
preferencia de ritmo.

Así que la pregunta de este script es: ¿qué eligen los equipos en las carreras
donde la elección **sí** se paga? O sea, las que no tuvieron neutralización
temprana.

Si el reparto es parecido en las dos clases, la elección de compuesto es una
preferencia real y sirve para juzgar al modelo. Si es distinto, la muestra que
teníamos estaba contaminada por el cumplimiento y no se puede juzgar nada con
ella.

Correr con ``uv run python scripts/start_choice.py``.
"""

from __future__ import annotations

import warnings

import fastf1
import numpy as np
import pandas as pd

from boxbox_ml import cache, track_status

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)
SEP = "=" * 88

DRY = ("SOFT", "MEDIUM", "HARD")

#: Hasta qué vuelta cuenta como «temprana» una neutralización. Cinco vueltas es
#: donde una parada gratis todavía convierte la tanda inicial en un trámite: más
#: allá, el compuesto ya corrió lo suficiente como para que la elección importe.
EARLY_LAPS = 5

#: Vueltas mínimas de la tanda inicial para que la elección se haya pagado. Por
#: debajo de esto la tanda es de cumplimiento, no de estrategia.
REAL_STINT = 6

ROUNDS = range(1, 15)

cache.enable()
fastf1.Cache.offline_mode(True)

races = []
for rnd in ROUNDS:
    try:
        session = fastf1.get_session(2026, rnd, "R")
        session.load(laps=True, telemetry=False, weather=False, messages=True)
    except Exception:  # noqa: BLE001 - una ronda que falta no es fatal
        continue
    laps = session.laps.copy()
    if laps.empty:
        continue
    laps["circuit"] = "x"
    laps["year"] = 2026
    laps["round"] = rnd
    laps["total_laps"] = int(laps["LapNumber"].max())
    laps["pit_in"] = laps["PitInTime"].notna()
    laps["pit_out"] = laps["PitOutTime"].notna()
    laps["LapTime"] = laps["LapTime"].dt.total_seconds()
    flagged = track_status.add_flags(laps)

    per_lap = flagged.groupby("LapNumber")[["is_neutralised", "red"]].max()
    early = bool(per_lap.loc[per_lap.index <= EARLY_LAPS].to_numpy().any())

    first = flagged.sort_values("LapNumber").groupby("Driver").first()
    lengths = flagged[flagged["Stint"] == flagged.groupby("Driver")["Stint"].transform("min")]
    opening = lengths.groupby("Driver")["LapNumber"].size()

    results = session.results.set_index("Abbreviation")
    for driver, row in first.iterrows():
        compound = row["Compound"]
        if compound not in DRY or driver not in results.index:
            continue
        grid = results.loc[driver, "GridPosition"]
        races.append(
            {
                "round": rnd,
                "event": session.event["EventName"],
                "driver": driver,
                "grid": int(grid) if grid and grid > 0 else np.nan,
                "compound": compound,
                "opening_laps": int(opening.get(driver, 0)),
                "early_neutral": early,
            }
        )

data = pd.DataFrame(races)

print(SEP)
print("### 1. QUE CARRERAS TUVIERON NEUTRALIZACION TEMPRANA")
print(f"(en las primeras {EARLY_LAPS} vueltas)")
print()
by_race = data.groupby(["round", "event"]).agg(
    autos=("driver", "size"),
    temprana=("early_neutral", "first"),
    tanda_inicial=("opening_laps", "median"),
)
print(by_race.to_string())
clean = int((~by_race["temprana"]).sum())
print()
print(f"  limpias: {clean} de {len(by_race)}")
print("  Fijate en la mediana de la tanda inicial: donde hubo neutralización")
print("  temprana se desploma, que es la firma del cumplimiento.")

print("\n" + SEP)
print("### 2. QUE LARGARON, SEGUN SI LA ELECCION SE PAGO")
print()
share = pd.crosstab(data["early_neutral"], data["compound"], normalize="index").round(3)
share.index = ["sin neutralización temprana", "con neutralización temprana"]
counts = data.groupby("early_neutral").size()
print(share.to_string())
print()
print(f"  n: limpias {counts.get(False, 0)} pilotos-carrera, sucias {counts.get(True, 0)}")

print("\n" + SEP)
print("### 3. LO MISMO, PERO EXIGIENDO QUE LA TANDA HAYA CORRIDO DE VERDAD")
print(f"(al menos {REAL_STINT} vueltas con el compuesto de largada)")
print()
real = data[data["opening_laps"] >= REAL_STINT]
print(real["compound"].value_counts(normalize=True).round(3).to_string())
print(f"\n  n = {len(real)} pilotos-carrera de {len(data)}")
print()
compliance = data[data["opening_laps"] < REAL_STINT]
if len(compliance):
    print("  Y las tandas de cumplimiento, para contrastar:")
    print(compliance["compound"].value_counts(normalize=True).round(3).to_string())
    print(f"  n = {len(compliance)}")

print("\n" + SEP)
print("### 4. POR BANDA DE GRILLA, SOLO CON TANDAS REALES")
print()
banded = real.dropna(subset=["grid"]).copy()
banded["banda"] = pd.cut(
    banded["grid"], [0, 5, 10, 15, 22], labels=["P1-5", "P6-10", "P11-15", "P16-22"]
)
table = pd.crosstab(banded["banda"], banded["compound"], normalize="index").round(3)
print(table.to_string())
print()
print(f"  n por banda: {banded['banda'].value_counts().sort_index().to_dict()}")
print()
print("  Ésta es la tabla que sirve para juzgar al modelo: la elección de")
print("  compuesto de los autos que después corrieron con ella.")
