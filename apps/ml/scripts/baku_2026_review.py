"""Bakú 2026: la predicción contra lo que pasó.

``docs/research/prediccion-baku-2026.md`` quedó congelada en el commit 418e90f,
escrita con la clasificación cargada y la carrera no. Este script carga la
carrera y la compara. El orden importa: una predicción que se escribe después de
ver el resultado no mide nada.

El resumen, porque conviene decirlo antes que los números: **las dos predicciones
perdieron, y perdieron por el mismo motivo, que no es el desgaste.** Bakú 2026 se
decidió en un safety car de diez vueltas. Treinta y cinco de las treinta y ocho
paradas de la carrera se hicieron ahí adentro, y casi todo el campo paró **dos
veces bajo la misma neutralización**. Yo predije una parada porque el historial
dice una parada; el modelo predijo una parada porque a ese desgaste alcanza con
una. Los dos teníamos razón sobre la carrera que no hubo.

Lo que sí se separa limpio, y es lo que este script mide:

* la estructura de paradas **estratégicas** —las tomadas en verde— fue de una o
  ninguna, que es lo que los dos dijimos; la cuenta cruda de dos paradas es un
  artefacto del safety car y no una refutación del pronóstico;
* el compuesto de salida lo erré yo y lo erró el modelo, en direcciones
  opuestas: yo dije blando ≤3 y hubo 10, el modelo dijo duro 9 y hubo **0**;
* **nadie calzó un duro en toda la carrera**, y las dos predicciones lo tenían
  como segundo juego. Ése es el error compartido y el más caro;
* el desgaste medido en carrera es muchísimo más suave que el promedio de la
  temporada (0,0554) con el que el simulador corrió el circuito, y esa
  comparación se sostiene porque los dos números salen del mismo pipeline. La
  regla «para un circuito sin datos del año en curso, usá el promedio» le erró
  acá, y este script mide cuánto;
* y el contrafáctico destapó algo que no venía a buscar: con una pendiente de
  desgaste **negativa** como insumo, la búsqueda prefiere no parar nunca, que es
  ilegal bajo B6.3.8 y que nada en la aptitud castiga.

Correr con ``uv run python scripts/baku_2026_review.py``.
"""

from __future__ import annotations

import warnings

import fastf1
import numpy as np
import pandas as pd

from boxbox_ml import cache, features, strategy, track_status
from boxbox_ml.strategy import Car, Objective, RaceModel, optimise

warnings.filterwarnings("ignore")
pd.set_option("display.width", 220)
SEP = "=" * 88

#: Lo que quedó escrito en 418e90f, antes de cargar la carrera. Se copia acá en
#: vez de leerse de un JSON porque la predicción de Bakú se pre-registró en prosa;
#: el commit es lo que fecha el orden, y es lo que hace que esto signifique algo.
MINE = {"MEDIUM": (12, 17), "HARD": (4, 8), "SOFT": (0, 3)}
MINE_POINT = {"MEDIUM": 14, "HARD": 5, "SOFT": 3}
MODEL_POINT = {"HARD": 9, "SOFT": 7, "MEDIUM": 6}

#: Desgaste con el que el simulador corrió Bakú (promedio de la temporada) y el
#: que sale del historial del circuito, que la regla de `circuit_wear.py` descarta.
SEASON_WEAR = 0.0554
HISTORIC_HARD = 0.0068

DRY = ("SOFT", "MEDIUM", "HARD")

# ------------------------------------------------------------------ la carrera

cache.enable()
session = fastf1.get_session(2026, 15, "R")
session.load(laps=True, telemetry=False, weather=False, messages=True)

laps = session.laps.copy()
laps["circuit"] = "Baku"
laps["year"] = 2026
laps["round"] = 15
laps["LapNumber"] = laps["LapNumber"].astype(int)
laps["total_laps"] = int(laps["LapNumber"].max())
laps["pit_in"] = laps["PitInTime"].notna()
laps["pit_out"] = laps["PitOutTime"].notna()
laps["LapTime"] = laps["LapTime"].dt.total_seconds()

TOTAL_LAPS = int(laps["LapNumber"].max())

frame = features.add_stint_position(
    features.add_fuel_correction(features.mark_representative(track_status.add_flags(laps)))
)
green = frame[
    frame["is_representative"] & ~frame["is_neutralised"] & ~frame["red"] & ~frame["yellow"]
]

# Una fila por auto: con qué largó, cuántas veces paró, qué secuencia corrió.
rows = []
for driver, block in laps.groupby("Driver"):
    block = block.sort_values("LapNumber")
    stints = (
        block.groupby("Stint")
        .agg(compound=("Compound", "first"), n=("LapNumber", "size"), start=("LapNumber", "min"))
        .sort_values("start")
    )
    rows.append(
        {
            "drv": driver,
            "larga": stints["compound"].iloc[0],
            "paradas": int(block["pit_in"].sum()),
            "fin": int(block["LapNumber"].max()),
            "secuencia": "-".join(f"{r.compound[0]}{r.n}" for r in stints.itertuples()),
            "compuestos": "-".join(c[0] for c in stints["compound"]),
        }
    )
cars = pd.DataFrame(rows)
# Clasificado es el 90% de la distancia del ganador, el mismo corte que usa el
# resto del proyecto para decidir qué auto cuenta.
cars["clasificado"] = cars["fin"] >= 0.9 * TOTAL_LAPS
classified = cars[cars["clasificado"]]

real = cars["larga"].value_counts().reindex(DRY).fillna(0).astype(int)

# El ganador sale del clasificador oficial, no del orden alfabético del groupby.
results = session.results.set_index("Abbreviation")
WINNER_CODE = str(results["Position"].idxmin())

# ------------------------------------------------------------- 1. el marcador

print(SEP)
print("### 1. EL MARCADOR")
print()
print(f"  {TOTAL_LAPS} vueltas, {len(cars)} autos, {len(classified)} clasificados")
print()

hits = []


def verdict(ok: bool) -> str:
    return "ACIERTO" if ok else "ERROR  "


compound_ok = bool(MINE["MEDIUM"][0] <= real["MEDIUM"] <= MINE["MEDIUM"][1] and real["SOFT"] <= 3)
hits.append(("compuesto de salida", compound_ok))
print(f"  [{verdict(compound_ok)}] compuesto de salida")
for compound in ("MEDIUM", "HARD", "SOFT"):
    low, high = MINE[compound]
    inside = low <= real[compound] <= high
    state = "dentro" if inside else "FUERA"
    print(f"            {compound:7s} predicho {low}-{high:<3d} real {real[compound]:2d}   {state}")
print("            el medio cayó justo en el borde de la banda y el blando la reventó:")
print("            dije «en Bakú nunca largó nadie en blando» y largaron diez.")
print()

modal = classified["paradas"].value_counts()
share = modal.max() / len(classified)
stops_ok = bool(modal.idxmax() == 1 and share >= 0.60)
hits.append(("paradas", stops_ok))
print(f"  [{verdict(stops_ok)}] paradas: predicho «una, 60% o más»")
print(f"            real: modal {modal.idxmax()} paradas con {share:.0%} de los clasificados")
print(f"            reparto {modal.sort_index().to_dict()}")
print()

seq = classified["compuestos"].value_counts()
top = str(seq.index[0])
seq_ok = top.startswith("M-H")
hits.append(("secuencia", seq_ok))
print(f"  [{verdict(seq_ok)}] secuencia: predicho «medio -> duro la más común»")
print(f"            real: {top} ({seq.iloc[0]} autos). Reparto {seq.to_dict()}")
print()

flags = frame.groupby("LapNumber")[["sc", "vsc", "red"]].max()
sc_laps = flags.index[flags["sc"] > 0].tolist()
neutral_ok = bool(len(sc_laps) > 0 or flags["vsc"].sum() > 0)
hits.append(("neutralización", neutral_ok))
print(f"  [{verdict(neutral_ok)}] neutralización: predicho «al menos una»")
print(
    f"            real: safety car en las vueltas {sc_laps[0]}-{sc_laps[-1]}"
    f" ({len(sc_laps)} vueltas),"
)
print(f"            VSC en {int(flags['vsc'].sum())}, roja en {int(flags['red'].sum())}")
print()
print(f"  {sum(ok for _, ok in hits)} de {len(hits)} criterios.")

# ------------------------------------------ 1b. mi reparto contra el del modelo

print("\n" + SEP)
print("### 1b. MI REPARTO CONTRA EL DEL MODELO")
print()
print("  El criterio se escribió antes: gana el que quede más cerca del real,")
print("  en puntos porcentuales sumados sobre los tres compuestos.")
print()
total = len(cars)
table = []
for compound in DRY:
    table.append(
        {
            "compuesto": compound,
            "real": f"{real[compound]:2d} ({real[compound] / total:.0%})",
            "mío": f"{MINE_POINT[compound]:2d} ({MINE_POINT[compound] / total:.0%})",
            "modelo": f"{MODEL_POINT[compound]:2d} ({MODEL_POINT[compound] / total:.0%})",
        }
    )
print(pd.DataFrame(table).to_string(index=False))
print()
mine_err = sum(abs(MINE_POINT[c] - real[c]) for c in DRY) / total * 100
model_err = sum(abs(MODEL_POINT[c] - real[c]) for c in DRY) / total * 100
print(f"  desvío total   mío {mine_err:.0f} pp   modelo {model_err:.0f} pp")
print(f"  gana: {'el historial (yo)' if mine_err < model_err else 'el modelo'}")
print()
print("  Pero la lectura honesta no es «gané». Gané por el medio y perdí por el")
print("  blando, que era mi afirmación más fuerte y la más específica. El modelo")
print("  —que no tiene motivo para preferir un compuesto, porque COMPOUND_OFFSET_S")
print("  vale cero— acertó que el blando iba a correr mucho, por la razón")
print("  equivocada. Y los dos pusimos el duro donde no estuvo.")

# --------------------------------------------- 2. las paradas no fueron decisión

print("\n" + SEP)
print("### 2. LAS PARADAS NO FUERON UNA DECISION")
print()
stop_laps = laps[laps["pit_in"]]["LapNumber"]
per_lap = stop_laps.value_counts().sort_index()
neutralised_laps = set(flags.index[(flags["sc"] > 0) | (flags["vsc"] > 0)])
under = int(stop_laps.isin(neutralised_laps).sum())
print(f"  paradas por vuelta: {per_lap.to_dict()}")
print(f"  vueltas neutralizadas: {sorted(neutralised_laps)}")
print()
print(
    f"  {under} de {len(stop_laps)} paradas se hicieron bajo neutralización"
    f" ({under / len(stop_laps):.0%})."
)
print()
# Paradas estratégicas: las tomadas en verde. Es la cuenta que se puede comparar
# contra una predicción, porque es la única que fue una decisión.
strategic = (
    laps[laps["pit_in"] & ~laps["LapNumber"].isin(neutralised_laps)]
    .groupby("Driver")
    .size()
    .reindex(classified["drv"])
    .fillna(0)
    .astype(int)
)
print("  paradas EN VERDE por auto, entre los clasificados (las que fueron una decisión):")
print(f"    {strategic.value_counts().sort_index().to_dict()}")
print()
print("  El safety car salió en la vuelta 29 y volvió en la 38. El campo paró en")
print("  la 30-31 y VOLVIO A PARAR en la 36, sin que la neutralización terminara:")
print("  dos juegos gratis en el mismo período. Por eso la última tanda de los")
print("  dieciséis clasificados mide exactamente 15 vueltas.")
print()
print("  Esto es lo que ninguna de las dos predicciones podía acertar, y también")
print("  lo que el simulador NO representa: `draw_neutralisations` sortea períodos")
print("  y la política de rivales reactivos deja parar UNA vez por período. Un")
print("  segundo juego gratis bajo el mismo safety car no está en el modelo.")

# -------------------------------------------------------- 3. el duro no existió

print("\n" + SEP)
print("### 3. EL DURO NO EXISTIO")
print()
lap_share = laps["Compound"].value_counts(normalize=True)
print("  vueltas corridas por compuesto:")
for compound in DRY:
    print(f"    {compound:7s} {lap_share.get(compound, 0.0):.1%}")
print()
longest = int(laps.groupby(["Driver", "Stint"]).size().max())
print(f"  tanda más larga de la carrera: {longest} vueltas")
# `MAX_STINT` acota la EDAD de la goma al entrar a boxes, y una tanda que termina
# en la vuelta L cubre L vueltas contando la de la parada. Así que la tanda más
# larga que el reparador permite es MAX_STINT + 1, y comparar el diccionario
# crudo contra una tanda real mezcla dos convenciones — exactamente el desfasaje
# de una vuelta que este proyecto ya se comió una vez.
print(
    "  tanda más larga que el simulador permite: "
    + ", ".join(f"{c} {strategy.MAX_STINT[c] + 1}" for c in ("MEDIUM", "HARD", "SOFT"))
)
print()
print(f"  La tanda real más larga ({longest}, el medio de HUL) cae EXACTO en el tope")
print("  del medio. No lo viola, pero no sobra nada: si Bakú hubiera pedido una")
print("  vuelta más de medio, el reparador habría partido en dos una tanda que")
print("  en la realidad existió.")
print()
print("  Todos los clasificados cumplieron B6.3.8 con medio + blando. El duro no")
print("  hizo una sola vuelta, y los dos pronósticos lo tenían como segundo juego.")

# -------------------------------------------------------------- 4. los insumos

print("\n" + SEP)
print("### 4. EL DESGASTE, MEDIDO EN LA CARRERA")
print()
records = []
for _keys, stint in green.groupby(["Driver", "Stint"], dropna=False):
    pace = stint["lap_time_fuel_corrected"].to_numpy(dtype=float)
    position = stint["stint_lap"].to_numpy(dtype=float)
    if len(pace) < 8 or not np.isfinite(pace).all():
        continue
    records.append(
        {"compound": stint["Compound"].iloc[0], "slope": float(np.polyfit(position, pace, 1)[0])}
    )
measured = pd.DataFrame(records)
by_compound = measured.groupby("compound")["slope"].agg(["median", "size"])
print(by_compound.round(4).to_string())
print()
print(f"  promedio de temporada con el que el simulador corrió Bakú: {SEASON_WEAR:.4f}")
print(f"  Bakú histórico (2022-2025), duro:                          {HISTORIC_HARD:.4f}")
print()
print("  Lo medido queda del lado del histórico, no del promedio. `circuit_wear.py`")
print("  midió que el desgaste NO se transfiere entre eras (r = 0,143) y concluyó")
print("  que para un circuito sin datos del año corresponde el promedio. Para Bakú")
print("  esa regla eligió mal: la personalidad del circuito —callejero, liso, de")
print("  degradación casi nula— sobrevivió al cambio de reglamento aunque el")
print("  promedio de los 27 pares diga que en general no sobrevive.")
print()
print("  Es UN caso contra una regla medida sobre 27 pares, y no la da vuelta.")
print("  Lo que sí muestra es dónde la regla es cara: en los circuitos cuya")
print("  desviación respecto del promedio es grande, que son justo los que más")
print("  necesitan una respuesta distinta del promedio.")
print()
print("  DOS ADVERTENCIAS SOBRE ESTOS NUMEROS, porque salen negativos:")
print()
print("  1. El signo no significa que la goma mejore. `insights.py` ya lo declara:")
print("     el coeficiente de combustible es fijo (0,035 s/vuelta) y está")
print("     calibrado sobre la era anterior, así que SUB-CORRIGE a los autos de")
print("     2026 y deja la pendiente medida por debajo de la real. Medio campo")
print("     mide plano o negativo en cualquier vuelta de cualquier carrera.")
print()
print("  2. Por eso la comparación que vale es contra el promedio de 2026 y no")
print("     contra el Bakú histórico. Los dos números de 2026 —el de acá y el")
print("     0,0554 de la temporada— salen del MISMO pipeline sub-corregido, así")
print("     que la diferencia entre ellos es real. La comparación contra 0,0068")
print("     cruza eras y pipelines, y es la pata débil del argumento.")
print()
print("  Con esa salvedad puesta: Bakú 2026 fue muchísimo más suave que la")
print("  temporada 2026, y eso se sostiene.")

# ------------------------------------- 5. la búsqueda con el desgaste verdadero

print("\n" + SEP)
print("### 5. QUE PROPONE LA BUSQUEDA CON EL DESGASTE REAL")
print()
real_wear = {c: float(by_compound["median"].get(c, np.nan)) for c in DRY}
# El duro no corrió, así que no hay nada medido: se le deja el promedio de la
# temporada, que es lo que el simulador ya usaba. No inventarlo es el punto.
if not np.isfinite(real_wear["HARD"]):
    real_wear["HARD"] = SEASON_WEAR
    print(f"  (el duro no corrió: se le deja el promedio de temporada {SEASON_WEAR})")


def cuts_for(targets: dict[str, float]) -> dict[str, tuple[float, ...]]:
    return {
        compound: tuple(round(v * targets[compound] / base[4], 5) for v in base)
        for compound, base in strategy.WEAR_CUTS.items()
    }


CAR = Car("M", "MEDIUM", 0, 0.0, strategy.ROLLING_MEDIAN_S, 0.0, 1)
race = RaceModel.for_circuit("Baku", total_laps=TOTAL_LAPS, wear_cuts=cuts_for(real_wear))
found = optimise(
    CAR, [], [], race, objective=Objective.TIME, population=40, generations=25, draws=1200, seed=11
)
winner = cars.set_index("drv").loc[WINNER_CODE, "secuencia"]
print(f"  búsqueda con el desgaste REAL: {found.best.describe(CAR, TOTAL_LAPS)}")
print(f"  lo que hizo el ganador ({WINNER_CODE}):    {winner}")
print()
print("  **La primera tanda coincide dentro de una vuelta, y el orden de compuestos")
print("  coincide entero.** RUS corrió el medio 31 vueltas y se pasó al blando; la")
print("  búsqueda dice medio 32 y después blando. Todo lo que las separa son las")
print("  dos paradas que RUS hizo gratis bajo el safety car de la vuelta 29.")
print()
print("  O sea: la decisión ESTRATEGICA de la carrera —hasta cuándo estirar el")
print("  medio y qué calzar después— el algoritmo la reproduce. Lo que no tiene")
print("  manera de reproducir es un regalo. Es la misma lectura que dejó Madrid:")
print("  el algoritmo no estaba roto, los insumos sí, y acá ni siquiera los")
print("  insumos alcanzan a explicar la diferencia — la explica la bandera.")
print()
print("  Con una salvedad que no conviene esconder, y que se mide en vez de")
print("  afirmarse: ¿llega a M32 porque encontró que 32 es lo mejor, o porque el")
print("  tope del medio la frena ahí? Se levanta el tope y se vuelve a buscar.")
print()
# El tope se levanta y se restaura: es global y lo lee el reparador de todo el
# módulo, así que dejarlo tocado contaminaría cualquier corrida posterior.
original = strategy.MAX_STINT["MEDIUM"]
strategy.MAX_STINT["MEDIUM"] = TOTAL_LAPS
free = optimise(
    CAR, [], [], race, objective=Objective.TIME, population=40, generations=25, draws=1200, seed=11
)
strategy.MAX_STINT["MEDIUM"] = original
print(f"  sin tope de medio: {free.best.describe(CAR, TOTAL_LAPS)}")
print()
if free.best.describe(CAR, TOTAL_LAPS) != found.best.describe(CAR, TOTAL_LAPS):
    print("  Se estira: el tope estaba atando la respuesta, y que M32 coincidiera con")
    print("  las 31 vueltas de RUS es en parte mérito del tope y no del algoritmo.")
else:
    print("  No se mueve: el tope no estaba atando nada y la coincidencia con RUS es")
    print("  del algoritmo, no del límite.")

# ------------------------------------- 6. lo que destapó el contrafáctico

print("\n" + SEP)
print("### 6. UN DESGASTE NEGATIVO ROMPE LA REGLA DE LOS DOS COMPUESTOS")
print()
free_used = {CAR.compound, *(stop.compound for stop in free.best.stops)}
legal = len(free_used) >= strategy.REQUIRED_COMPOUNDS
print(
    f"  el plan sin tope usa {len(free_used)} compuesto(s): B6.3.8 "
    f"{'se cumple' if legal else 'QUEDA VIOLADA'}"
)
print()
print("  `_enforce_two_compounds` arregla la ilegalidad cambiando el compuesto de")
print("  la ULTIMA parada, y su docstring dice que un plan sin ninguna parada «no")
print("  se puede hacer legal, y la aptitud lo va a castigar y va a perder».")
print("  Con el desgaste de la temporada eso es cierto: probado a 40, 44 y 51")
print("  vueltas la búsqueda devuelve siempre un plan de una parada y legal,")
print("  aunque un solo juego de duros alcance para la distancia.")
print()
print("  Con el desgaste MEDIDO EN BAKU deja de ser cierto, y se ve por qué: si la")
print("  pendiente es negativa, la goma vieja es más rápida, no parar nunca es")
print("  óptimo, y no hay nada en la aptitud que lo penalice.")
print()
print("  O sea que el artefacto del punto 1 de la sección 4 no es sólo ruido de")
print("  medición: realimentado como insumo del modelo, vuelve preferible una")
print("  estrategia ILEGAL. No afecta ninguna cifra publicada —el simulador corre")
print("  con desgastes positivos— pero es la razón concreta por la que una")
print("  pendiente medida no se puede enchufar como insumo sin mirarle el signo.")
print()
print(SEP)
