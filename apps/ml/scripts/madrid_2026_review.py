"""Madrid 2026: la predicción contra lo que pasó.

``scripts/madrid_2026.py`` dejó una predicción congelada en
``data/madrid2026_prediccion.json``, generada sin cargar la sesión de carrera.
Este script carga la carrera y la compara. El orden importa: una predicción que
se escribe después de ver el resultado no mide nada.

El resumen, porque es incómodo y conviene decirlo primero: **el modelo base
acertó la estructura y todas las capas que le agregué encima la empeoraron.**

* acertó la cantidad modal de paradas (una), y la forma del plan ganador —
  medio corto y después una tanda larga de duro;
* falló el desgaste por un factor de tres, y falló en la dirección que más
  duele: estimó a Madrid como un circuito severo cuando fue el más suave de la
  temporada;
* falló la ventana de parada, que la decidió un VSC en la vuelta 14;
* y falló feo la lectura de los compuestos: predije que el duro correría menos
  del 10% de las vueltas y corrió el 76%.

Lo más útil está en la descomposición del final: **con el desgaste real medido en
la carrera, y sin tocar nada más, la búsqueda propone M15-H41 y el ganador hizo
M14-H43.** El algoritmo nunca estuvo roto; los insumos sí.

Correr con ``uv run python scripts/madrid_2026_review.py``.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import fastf1
import numpy as np
import pandas as pd

from boxbox_ml import cache, features, strategy, track_status
from boxbox_ml.strategy import Car, Objective, Plan, RaceModel, Stop, optimise

warnings.filterwarnings("ignore")
pd.set_option("display.width", 220)
SEP = "=" * 88

PREDICTION = json.loads(
    (Path(__file__).resolve().parents[1] / "data" / "madrid2026_prediccion.json").read_text(
        encoding="utf-8"
    )
)

# ------------------------------------------------------------------ la carrera

cache.enable()
session = fastf1.get_session(2026, 14, "R")
session.load(laps=True, telemetry=False, weather=False, messages=True)

laps = session.laps.copy()
laps["circuit"] = "Madrid"
laps["year"] = 2026
laps["round"] = 14
laps["total_laps"] = int(laps["LapNumber"].max())
laps["pit_in"] = laps["PitInTime"].notna()
laps["pit_out"] = laps["PitOutTime"].notna()
laps["LapTime"] = laps["LapTime"].dt.total_seconds()

frame = features.add_stint_position(
    features.add_fuel_correction(features.mark_representative(track_status.add_flags(laps)))
)
green = frame[
    frame["is_representative"] & ~frame["is_neutralised"] & ~frame["red"] & ~frame["yellow"]
]

TOTAL_LAPS = int(laps["LapNumber"].max())

# --------------------------------------------------------- desgaste y boxes real

records = []
for _keys, stint in green.groupby(["Driver", "Stint"], dropna=False):
    pace = stint["lap_time_fuel_corrected"].to_numpy(dtype=float)
    position = stint["stint_lap"].to_numpy(dtype=float)
    if len(pace) < 8 or not np.isfinite(pace).all():
        continue
    records.append(
        {"compound": stint["Compound"].iloc[0], "slope": float(np.polyfit(position, pace, 1)[0])}
    )
measured = pd.DataFrame(records).groupby("compound")["slope"].median()
REAL_WEAR = {c: round(float(measured[c]), 4) for c in ("SOFT", "MEDIUM", "HARD")}

reference = (
    frame[frame["is_representative"] & ~frame["is_neutralised"]]
    .groupby("LapNumber")["LapTime"]
    .median()
)
losses = []
for _driver, entries in frame.groupby("Driver"):
    entries = entries.sort_values("LapNumber")
    for _, lap in entries[entries["pit_in"]].iterrows():
        number = int(lap["LapNumber"])
        pair = entries[entries["LapNumber"].isin([number, number + 1])]["LapTime"].sum()
        expected = reference.get(number, np.nan) + reference.get(number + 1, np.nan)
        if np.isfinite(pair) and np.isfinite(expected) and pair > 0:
            losses.append(pair - expected)
loss = np.array(losses)
REAL_PIT = (
    round(float(np.percentile(loss, 25)), 1),
    round(float(np.median(loss)), 1),
    round(float(np.percentile(loss, 75)), 1),
)

# ------------------------------------------------------------- 1. el marcador

print(SEP)
print("### 1. EL MARCADOR")
print()

first_compound = frame.sort_values("LapNumber").groupby("Driver").first()["Compound"]
usage = frame["Compound"].value_counts()
hard_share = usage.get("HARD", 0) / usage.sum()

sequences = []
for driver, entries in frame.groupby("Driver"):
    parts = []
    for _stint, stint in entries.groupby("Stint"):
        compound = stint["Compound"].iloc[0]
        if pd.isna(compound):
            continue
        parts.append(f"{str(compound)[0]}{len(stint)}")
    sequences.append(
        {"drv": driver, "paradas": max(len(parts) - 1, 0), "secuencia": "-".join(parts)}
    )
strategies = pd.DataFrame(sequences)
finished = strategies[strategies["paradas"] > 0]
modal_stops = int(finished["paradas"].mode().iloc[0])

neutral_laps = sorted(
    int(x)
    for x in frame.groupby("LapNumber")[["is_neutralised", "red"]]
    .max()
    .query("is_neutralised or red")
    .index
)

checks = [
    (
        "vueltas de carrera",
        PREDICTION["vueltas_estimadas"],
        TOTAL_LAPS,
        abs(PREDICTION["vueltas_estimadas"] - TOTAL_LAPS) <= 1,
    ),
    (
        "paradas modales (modelo base)",
        PREDICTION["paradas_recomendadas"]["MEDIUM"],
        modal_stops,
        PREDICTION["paradas_recomendadas"]["MEDIUM"] == modal_stops,
    ),
    (
        "paradas (apuesta principal)",
        PREDICTION["apuesta_principal"]["planes"]["MEDIUM"]["paradas"],
        modal_stops,
        PREDICTION["apuesta_principal"]["planes"]["MEDIUM"]["paradas"] == modal_stops,
    ),
    ("duro < 10% de las vueltas", "<10%", f"{hard_share:.0%}", hard_share < 0.10),
    (
        "mayoría larga en MEDIO",
        "MEDIUM",
        str(first_compound.value_counts().idxmax()),
        first_compound.value_counts().idxmax() == "MEDIUM",
    ),
    (
        "al menos una neutralización",
        f"{PREDICTION['p_alguna_neutralizacion']:.0%}",
        f"{len(neutral_laps)} vueltas",
        len(neutral_laps) > 0,
    ),
]
for label, predicted, actual, ok in checks:
    print(
        f"  {'OK ' if ok else 'MAL'}  {label:32s}"
        f" predicho {str(predicted):>10s}   real {str(actual):>10s}"
    )

print()
print(f"  ventana de la 1ra parada predicha: {PREDICTION['ventana']['MEDIUM']['primera']}")
stop_laps = frame[frame["pit_in"]]["LapNumber"].astype(int)
print(f"  paradas reales por vuelta:         {stop_laps.value_counts().sort_index().to_dict()}")
print(f"  vueltas neutralizadas:             {neutral_laps}")

# --------------------------------------------------- 2. los insumos, uno por uno

print("\n" + SEP)
print("### 2. LOS INSUMOS, UNO POR UNO")
print()
print(f"  {'insumo':22s} {'predicho':>10s} {'real':>10s}   comentario")
for compound in ("SOFT", "MEDIUM", "HARD"):
    predicted = PREDICTION["desgaste_estimado_s_vuelta"][compound]
    actual = REAL_WEAR[compound]
    factor = predicted / actual if actual else float("inf")
    print(
        f"  desgaste {compound:13s} {predicted:10.4f} {actual:10.4f}   sobreestimado {factor:.1f}x"
    )
print(
    f"  {'pérdida de boxes':22s} {22.6:10.1f} {REAL_PIT[1]:10.1f}"
    f"   subestimada {REAL_PIT[1] - 22.6:.1f} s"
)
print()
print("  Madrid resultó el circuito MAS SUAVE de la temporada, no uno severo.")
print("  El duro degradó 0,0026 s/vuelta: prácticamente nada. Por eso doce autos")
print("  largaron con duro y por eso corrió el 76% de las vueltas.")

# ------------------------------------------------------- 3. de dónde vino el error

print("\n" + SEP)
print("### 3. DE DONDE VINO EL ERROR")
print("Se cambia un supuesto por vez y se mira si el plan del ganador pasa a ganar.")
print()

STREET = dict(
    n_red=(0.886, 0.086, 0.000, 0.029),
    n_sc=(0.371, 0.429, 0.143, 0.057),
    n_vsc=(0.457, 0.257, 0.229, 0.057),
)


def cuts_for(targets: dict[str, float]) -> dict[str, tuple[float, ...]]:
    return {
        compound: tuple(round(v * targets[compound] / base[4], 5) for v in base)
        for compound, base in strategy.WEAR_CUTS.items()
    }


def model(wear: dict[str, float], pit: tuple[float, float, float]) -> RaceModel:
    return RaceModel(total_laps=TOTAL_LAPS, wear_cuts=cuts_for(wear), pit_loss_green=pit, **STREET)


CAR = Car("M", "MEDIUM", 0, 0.0, strategy.ROLLING_MEDIAN_S, 0.0, 1)
# El duro de Madrid aguanta toda la carrera: MAX_STINT global (41) no lo permite,
# y sin esto el reparador parte en dos la tanda que ANT realmente corrió.
strategy.MAX_STINT.update({"HARD": 50, "MEDIUM": 40, "SOFT": 30})


def plan_of(*stops: tuple[int, str]) -> Plan:
    return Plan(
        strategy._repair(
            [Stop(lap, compound) for lap, compound in stops], CAR, model(REAL_WEAR, REAL_PIT)
        )
    )


def score(plan: Plan, race: RaceModel, draws: int = 8000) -> float:
    gen = np.random.default_rng(4242)
    flags = strategy.draw_neutralisations(race, gen, draws)
    return float(strategy.race_time(plan, CAR, race, gen, draws, flags).mean())


RECOMMENDED = plan_of((23, "HARD"))
WINNER = plan_of((14, "HARD"))
print(f"  plan del modelo:  {RECOMMENDED.describe(CAR, TOTAL_LAPS)}")
print(f"  plan de ANT:      {WINNER.describe(CAR, TOTAL_LAPS)}")
print()
rows = []
for label, wear, pit in (
    ("supuestos previos", PREDICTION["desgaste_estimado_s_vuelta"], (20.2, 22.6, 25.5)),
    ("+ desgaste real", REAL_WEAR, (20.2, 22.6, 25.5)),
    ("+ pérdida de boxes real", REAL_WEAR, REAL_PIT),
):
    race = model(wear, pit)
    rows.append(
        {
            "escenario": label,
            "modelo": round(score(RECOMMENDED, race), 2),
            "ANT": round(score(WINNER, race), 2),
            "dif": round(score(WINNER, race) - score(RECOMMENDED, race), 2),
        }
    )
print(pd.DataFrame(rows).to_string(index=False))
print()
print("  El signo se da vuelta al corregir UNA sola cosa: el desgaste. Con los")
print("  supuestos previos el modelo le decía a ANT que estaba equivocado por 4,1 s;")
print("  con el desgaste real, ANT le gana al modelo por 3,9 s. La pérdida de boxes")
print("  mueve los tiempos absolutos y casi no mueve la comparación.")

# ------------------------------------------------ 4. el algoritmo no estaba roto

print("\n" + SEP)
print("### 4. EL ALGORITMO NO ESTABA ROTO")
strategy.MAX_STINT.update({"HARD": 41, "MEDIUM": 31, "SOFT": 25})
race = model(REAL_WEAR, REAL_PIT)
found = optimise(
    CAR, [], [], race, objective=Objective.TIME, population=40, generations=25, draws=1200, seed=11
)
winner_real = strategies.set_index("drv").loc["ANT", "secuencia"]
print()
print(f"  búsqueda con los insumos REALES:  {found.best.describe(CAR, TOTAL_LAPS)}")
print(f"  lo que hizo ANT:                  {winner_real}")
print()
print("  Una vuelta de diferencia en la parada. Dándole los números correctos, la")
print("  búsqueda reproduce la estrategia ganadora; con los números estimados antes")
print("  de la carrera, no. Todo el error estuvo en los insumos.")

# --------------------------------------------------------------- 5. qué aprender

print("\n" + SEP)
print("### 5. QUE APRENDER")
print()
err_prac = abs(PREDICTION["desgaste_estimado_s_vuelta"]["MEDIUM"] - REAL_WEAR["MEDIUM"])
err_glob = abs(0.0622 - REAL_WEAR["MEDIUM"])
print("  1. La calibración práctica->carrera no sobrevivió al circuito 13. El")
print("     leave-one-out sobre 9 circuitos prometía 47% menos error en el medio;")
print(f"     en Madrid dio {err_prac:.4f} contra {err_glob:.4f} del global. Peor que no mirar.")
print()
print("  2. El uso de compuestos en práctica mide gestión de juegos, no intención")
print("     de carrera. Leí '32 vueltas con duro' como 'nadie lo va a usar'. Es al")
print("     revés: no lo gastan en práctica PORQUE lo quieren para la carrera.")
print()
print("  3. Cada capa que le agregué al modelo base lo empeoró: el escalón de")
print("     ritmo (pasó de 1 parada a 2, y la respuesta era 1), el desgaste de")
print("     práctica, y sacar el duro de la mesa. Las tres.")
print()
print("  4. La ventana la decidió un VSC en la vuelta 14, que se llevó 10 de las 28")
print("     paradas. Es Monza otra vez: se puede predecir QUE va a haber una")
print("     neutralización, no CUANDO, y el cuándo es lo que fija la ventana.")
