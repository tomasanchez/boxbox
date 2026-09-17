"""Madrid 2026: la predicción antes de mirar la carrera.

Madrid es la fecha 14 y **nunca se corrió un Gran Premio ahí**. Es el caso que
``scripts/new_circuit.py`` dejó planteado: el modelo pide desgaste por circuito y
no hay ninguno. La diferencia es que ahora sí hay algo — 1.299 vueltas de
práctica del propio fin de semana — y la pregunta es si sirven.

La regla de este script es una sola: **no se carga la sesión de carrera**. Todo lo
que entra es calendario, prácticas y clasificación, que existen antes de que se
apaguen las luces. Lo que sale se congela en un JSON y recién después se compara.

Lo que se mide acá y no estaba medido antes:

* **La práctica predice el desgaste de carrera, pero sólo en el medio.** Sobre los
  12 circuitos de 2026 donde se conocen las dos cosas, un leave-one-circuit-out da
  47% menos error que el promedio global para el medio, 9% para el duro, y 77%
  **más** error para el blando. La práctica también exagera: la recta de
  calibración es ``carrera = 0,50 * práctica`` en el medio.
* **En Madrid el duro no existe.** 32 vueltas en todo el fin de semana contra 615
  del medio y 650 del blando, y cero tandas largas utilizables.

Correr con ``uv run python scripts/madrid_2026.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from boxbox_ml import strategy
from boxbox_ml.strategy import Car, Objective, Plan, RaceModel, optimise

pd.set_option("display.width", 200)
SEP = "=" * 88

# --------------------------------------------------------------------- insumos

#: Largo de vuelta integrando la telemetría de velocidad de FP3, 68 vueltas
#: rápidas. La integración subestima ~2% contra el largo oficial, así que el
#: número real ronda los 5,4 km. Se prueba la sensibilidad a esto más abajo.
LAP_LENGTH_M = 5339.0
RACE_DISTANCE_M = 305_000
LAPS = int(np.ceil(RACE_DISTANCE_M / LAP_LENGTH_M))

#: Desgaste medido en las tandas largas de práctica de Madrid, s/vuelta, con la
#: corrección de combustible ya aplicada. El duro no tiene ninguna tanda larga.
PRACTICE_WEAR: dict[str, float | None] = {"SOFT": 0.2487, "MEDIUM": 0.1737, "HARD": None}
PRACTICE_RUNS = {"SOFT": 7, "MEDIUM": 10, "HARD": 0}

#: Rectas de calibración práctica -> carrera, ajustadas sobre los 12 circuitos de
#: 2026 con ambas mediciones. Sólo la del medio sobrevive al leave-one-out.
CALIBRATION = {"SOFT": (0.275, 0.0597), "MEDIUM": (0.502, 0.0012), "HARD": (0.135, 0.0489)}
LOO_GAIN = {"SOFT": -76.7, "MEDIUM": 47.4, "HARD": 8.7}

#: Mediana global del desgaste medido en carrera, todas las eras. El fallback.
GLOBAL_WEAR = {"SOFT": 0.0839, "MEDIUM": 0.0622, "HARD": 0.0539}

#: Escalón de ritmo entre compuestos en Madrid: mejor vuelta por piloto dentro de
#: cada sesión de práctica, que descuenta auto, combustible y casi toda la
#: evolución de pista. 42 pares blando/medio. Duro/medio no es medible: 3 pares.
MADRID_OFFSET_S = {"HARD": 0.0, "MEDIUM": 0.0, "SOFT": -0.893}

#: Neutralizaciones en circuitos urbanos, 35 carreras, contra 69 permanentes.
#: Madring es mixto — trazado urbano alrededor de IFEMA con tramos construidos —
#: y se le aplica el prior urbano, que es el más severo de los dos.
STREET_RED = (0.886, 0.086, 0.000, 0.029)
STREET_SC = (0.371, 0.429, 0.143, 0.057)
STREET_VSC = (0.457, 0.257, 0.229, 0.057)

#: Clasificación del sábado. Posición, piloto, y hueco a la pole en segundos.
GRID = [
    (1, "NOR", 0.000),
    (2, "ANT", 0.011),
    (3, "VER", 0.140),
    (4, "HAM", 0.189),
    (5, "LEC", 0.195),
    (6, "RUS", 0.325),
    (7, "PIA", 0.470),
    (8, "LAW", 0.492),
    (9, "COL", 1.079),
    (10, "LIN", 1.217),
    (11, "HUL", 1.399),
    (12, "BOR", 1.564),
    (13, "OCO", 1.843),
    (14, "GAS", 1.929),
    (15, "TSU", 2.260),
    (16, "ALB", 3.483),
    (17, "SAI", 3.488),
    (18, "ALO", 3.564),
    (19, "PER", 4.089),
    (20, "BOT", 6.187),
]
POLE_S = 91.824

DRY = ("SOFT", "MEDIUM", "HARD")


def scaled_cuts(targets: dict[str, float]) -> dict[str, tuple[float, ...]]:
    """Reescalar la forma medida en Zandvoort a la mediana estimada del circuito."""
    out = {}
    for compound, cuts in strategy.WEAR_CUTS.items():
        factor = targets[compound] / cuts[4]
        out[compound] = tuple(round(value * factor, 5) for value in cuts)
    return out


def calibrated(compound: str) -> float | None:
    """Desgaste de carrera implícito en la práctica de Madrid, o None si no hay."""
    raw = PRACTICE_WEAR[compound]
    if raw is None:
        return None
    slope, intercept = CALIBRATION[compound]
    return slope * raw + intercept


_medium = calibrated("MEDIUM")
_soft = calibrated("SOFT")
assert _medium is not None and _soft is not None

#: Los tres escenarios de desgaste que se ponen a prueba.
WEAR_GLOBAL = dict(GLOBAL_WEAR)
WEAR_MAIN = {
    # El medio es el único compuesto donde la práctica le gana al promedio.
    "MEDIUM": round(_medium, 4),
    "SOFT": GLOBAL_WEAR["SOFT"],
    "HARD": GLOBAL_WEAR["HARD"],
}
WEAR_FULL = {
    "MEDIUM": round(_medium, 4),
    "SOFT": round(_soft, 4),
    "HARD": GLOBAL_WEAR["HARD"],
}

SCENARIOS = {
    "global (el fallback de hoy)": WEAR_GLOBAL,
    "práctica donde valida": WEAR_MAIN,
    "práctica en todo": WEAR_FULL,
}


def model_for(wear: dict[str, float], laps: int = LAPS) -> RaceModel:
    """Un RaceModel de Madrid: desgaste reescalado y prior urbano de banderas."""
    return RaceModel(
        total_laps=laps,
        wear_cuts=scaled_cuts(wear),
        n_red=STREET_RED,
        n_sc=STREET_SC,
        n_vsc=STREET_VSC,
    )


MADRID = model_for(WEAR_MAIN)
SEARCH = dict(population=40, generations=25, draws=1200)


def car_on(compound: str) -> Car:
    """Un auto en la grilla con ese compuesto: goma nueva, sin historia de ritmo."""
    return Car(compound[0], compound, 0, 0.0, strategy.ROLLING_MEDIAN_S, 0.0, 1)


def recommend(compound: str, model: RaceModel, seed: int = 11):
    return optimise(car_on(compound), [], [], model, objective=Objective.TIME, seed=seed, **SEARCH)


def score(car: Car, plan: Plan, model: RaceModel, draws: int = 6000) -> float:
    """Tiempo medio de carrera sobre los mismos sorteos para todos los planes."""
    gen = np.random.default_rng(11)
    flags = strategy.draw_neutralisations(model, gen, draws)
    return float(strategy.race_time(plan, car, model, gen, draws, flags).mean())


def line_for(model: RaceModel, laps: int) -> str:
    """Una línea con el plan recomendado para cada compuesto de salida."""
    parts = []
    for compound in DRY:
        found = recommend(compound, model)
        plan = found.best.describe(car_on(compound), laps)
        parts.append(f"{compound[0]}:{found.best.count}p {plan}")
    return "  ".join(parts)


# --------------------------------------------------------------- 1. los insumos

print(SEP)
print("### 1. LOS INSUMOS, Y DE DONDE SALE CADA UNO")
print()
print(f"  vueltas          {LAPS}   (largo medido {LAP_LENGTH_M:.0f} m por telemetría de FP3)")
print(f"  pole             {POLE_S:.3f} s")
print("  parada           global, 22,6 s — Madrid no tiene historia de pit lane")
print("  neutralización   prior de circuito urbano, 35 carreras")
print()
print("  desgaste s/vuelta:")
head = f"    {'compuesto':10s} {'práctica':>9s} {'tandas':>7s} {'calibrado':>10s}"
print(f"{head} {'global':>8s} {'LOO':>8s}")
for compound in DRY:
    raw = PRACTICE_WEAR[compound]
    cal = calibrated(compound)
    print(
        f"    {compound:10s} {('—' if raw is None else f'{raw:+.4f}'):>9s}"
        f" {PRACTICE_RUNS[compound]:>7d} {('—' if cal is None else f'{cal:.4f}'):>10s}"
        f" {GLOBAL_WEAR[compound]:>8.4f} {LOO_GAIN[compound]:>+7.1f}%"
    )
print()
print("  LOO = cuánto mejor (o peor) predice la práctica que el promedio global,")
print("  escondiendo un circuito por vez sobre los 12 de 2026 con ambas medidas.")
print("  Sólo el medio gana de verdad. El blando es peor que no mirar.")
print()
print("  escalón de ritmo (práctica, mejor vuelta por piloto y sesión):")
print(f"    blando vs medio  {MADRID_OFFSET_S['SOFT']:+.3f} s/vuelta   (42 pares)")
print("    duro   vs medio   no medible                (3 pares)")
print()
print("  uso de compuestos en práctica: MEDIO 615 vueltas, BLANDO 650, DURO 32.")
print("  Al duro no lo probó nadie, y no dejó una sola tanda larga utilizable.")

# ------------------------------------------------------- 2. la recomendación

print("\n" + SEP)
print("### 2. LA RECOMENDACIÓN")
print(f"Desde la vuelta 1 de {LAPS}, objetivo TIEMPO: la forma más rápida de cubrir")
print("la distancia. Es lo que una recomendación previa a la carrera puede contestar.")
print()
rows = []
for compound in DRY:
    found = recommend(compound, MADRID)
    spread = " ".join(f"{k}:{v:.2f}" for k, v in found.stop_distribution.items())
    rows.append(
        {
            "larga en": compound,
            "plan": found.best.describe(car_on(compound), LAPS),
            "paradas": found.best.count,
            "tiempo": round(-found.score, 1),
            "convergencia": spread,
        }
    )
print(pd.DataFrame(rows).to_string(index=False))

print("\n  ¿con qué compuesto conviene largar?")
ranked = []
for compound in DRY:
    found = recommend(compound, MADRID)
    ranked.append((compound, score(car_on(compound), found.best, MADRID), found))
ranked.sort(key=lambda item: item[1])
reference = ranked[0][1]
for compound, value, found in ranked:
    plan = found.best.describe(car_on(compound), LAPS)
    print(f"    {compound:7s} {value:8.1f} s   {value - reference:+6.2f}   {plan}")

# ------------------------------------------------------- 3. la ventana

print("\n" + SEP)
print("### 3. LA VENTANA DE PARADA")
print("Veinte búsquedas con semillas distintas; dónde cae cada parada.")
print()
windows = {}
for compound in DRY:
    firsts, seconds, counts = [], [], []
    for seed in range(20):
        found = recommend(compound, MADRID, seed=seed)
        stops = found.best.stops
        counts.append(len(stops))
        if stops:
            firsts.append(stops[0].lap)
        if len(stops) > 1:
            seconds.append(stops[1].lap)
    line = f"  {compound:7s} paradas {int(np.median(counts))}"
    window: dict[str, object] = {"paradas": int(np.median(counts))}
    if firsts:
        low, high = int(np.percentile(firsts, 10)), int(np.percentile(firsts, 90))
        line += f"   1ra vuelta {low}-{high}"
        window["primera"] = [low, high]
    if seconds:
        low, high = int(np.percentile(seconds, 10)), int(np.percentile(seconds, 90))
        line += f"   2da vuelta {low}-{high}"
        window["segunda"] = [low, high]
    windows[compound] = window
    print(line)

# ------------------------------------------------------- 4. sensibilidad

print("\n" + SEP)
print("### 4. SENSIBILIDAD — ¿de qué depende la respuesta?")
print()
print("  a) del escenario de desgaste:")
for label, wear in SCENARIOS.items():
    print(f"    {label:28s} {line_for(model_for(wear), LAPS)}")

print()
print("  b) de cuántas vueltas tiene la carrera:")
for laps in (56, 57, 58):
    body = line_for(model_for(WEAR_MAIN, laps=laps), laps)
    print(f"    {laps} vueltas                    {body}")

print()
print("  c) del escalón de ritmo entre compuestos:")
saved = dict(strategy.COMPOUND_OFFSET_S)
OFFSET_CASES = (("sin escalón (como hoy)", saved), ("con el medido en Madrid", MADRID_OFFSET_S))
for label, offsets in OFFSET_CASES:
    strategy.COMPOUND_OFFSET_S.update(offsets)
    print(f"    {label:28s} {line_for(MADRID, LAPS)}")
strategy.COMPOUND_OFFSET_S.update(saved)
print()
print("  El escalón da vuelta la respuesta: de una parada a dos. Y es justo el")
print("  insumo que no se puede validar contra carrera. Está declarado, no escondido.")

# ------------------------------------------------ 4bis. el duro fuera de la mesa

print("\n" + SEP)
print("### 4bis. ¿Y SI EL DURO NO ES UNA OPCIÓN?")
print("El modelo propone tandas de 34 vueltas con duro, y al duro no lo corrió nadie:")
print("32 vueltas en todo el fin de semana. Si los equipos no lo van a montar, la")
print("pregunta real es la mejor estrategia con medio y blando solamente.")
print()
saved_dry = strategy.DRY
saved_off = dict(strategy.COMPOUND_OFFSET_S)
strategy.DRY = ("MEDIUM", "SOFT")  # type: ignore[assignment]
strategy.COMPOUND_OFFSET_S.update(MADRID_OFFSET_S)

best_guess = {}
for compound in ("MEDIUM", "SOFT"):
    found = recommend(compound, MADRID)
    plan = found.best.describe(car_on(compound), LAPS)
    spread = " ".join(f"{k}:{v:.2f}" for k, v in found.stop_distribution.items())
    used_hard = "H" in plan
    best_guess[compound] = {"plan": plan, "paradas": found.best.count}
    flag = "   (¡el reparador metió duro igual!)" if used_hard else ""
    print(f"    larga en {compound:7s} {found.best.count} paradas   {plan:<20s} {spread}{flag}")

firsts, counts = [], []
for seed in range(20):
    found = recommend("MEDIUM", MADRID, seed=seed)
    counts.append(found.best.count)
    if found.best.stops:
        firsts.append(found.best.stops[0].lap)
window_bg = [int(np.percentile(firsts, 10)), int(np.percentile(firsts, 90))] if firsts else None
print()
print(f"    ventana de la primera parada (medio, 20 semillas): {window_bg}")
print(f"    paradas modales: {int(np.median(counts))}")

strategy.DRY = saved_dry  # type: ignore[assignment]
strategy.COMPOUND_OFFSET_S.clear()
strategy.COMPOUND_OFFSET_S.update(saved_off)
print()
print("  Ésta es la predicción que de verdad se sostiene: combina lo único que se")
print("  validó (desgaste del medio desde práctica), lo que se midió pero no se")
print("  pudo validar (el escalón de ritmo), y un hecho observado del fin de semana")
print("  (nadie tocó el duro).")

# ------------------------------------------------------- 5. neutralizaciones

print("\n" + SEP)
print("### 5. QUÉ TAN PROBABLE ES QUE LA CARRERA SE NEUTRALICE")
print()
p_sc = 1 - STREET_SC[0]
p_vsc = 1 - STREET_VSC[0]
p_red = 1 - STREET_RED[0]
p_any = 1 - STREET_SC[0] * STREET_VSC[0] * STREET_RED[0]
print(f"  safety car        {p_sc:.1%}")
print(f"  VSC               {p_vsc:.1%}")
print(f"  bandera roja      {p_red:.1%}")
print(f"  alguna            {p_any:.1%}")
print()
print("  En circuitos urbanos el 60% de las carreras ve dos o más períodos, contra")
print("  el 38% de los permanentes. Monza enseñó que ahí se decide la estrategia:")
print("  con las paradas gratis, la cantidad óptima se da vuelta.")

# ------------------------------------------------------- 6. predicciones

print("\n" + SEP)
print("### 6. LAS PREDICCIONES, PARA COMPARAR DESPUÉS")

plans = {compound: recommend(compound, MADRID) for compound in DRY}

predictions = {
    "circuito": "Madrid",
    "fecha": "2026-09-13",
    "ronda": 14,
    "generado_con": "calendario + FP1/FP2/FP3 + clasificación; la carrera NO se cargó",
    "vueltas_estimadas": LAPS,
    "desgaste_estimado_s_vuelta": WEAR_MAIN,
    "plan_recomendado": {
        compound: plans[compound].best.describe(car_on(compound), LAPS) for compound in DRY
    },
    "paradas_recomendadas": {compound: plans[compound].best.count for compound in DRY},
    "ventana": windows,
    "mejor_compuesto_de_salida": ranked[0][0],
    "apuesta_principal": {
        "supuestos": [
            "desgaste del medio calibrado desde práctica (único método validado)",
            "escalón de ritmo medido en Madrid: blando -0,893 s/vuelta",
            "el duro fuera de la mesa: 32 vueltas en todo el fin de semana",
        ],
        "planes": best_guess,
        "ventana_primera_parada": window_bg,
    },
    "p_safety_car": round(p_sc, 3),
    "p_vsc": round(p_vsc, 3),
    "p_bandera_roja": round(p_red, 3),
    "p_alguna_neutralizacion": round(p_any, 3),
    "afirmaciones_falsables": [
        "el duro corre menos del 10% de las vueltas de la carrera",
        "la mayoría de la parrilla larga en MEDIO",
        "la cantidad modal de paradas del top 10 es la que dice la tabla de arriba",
        f"al menos una neutralización (SC, VSC o roja): {p_any:.0%}",
    ],
}
print(json.dumps(predictions, indent=2, ensure_ascii=False))

out = Path(__file__).resolve().parents[1] / "data" / "madrid2026_prediccion.json"
out.write_text(json.dumps(predictions, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\ncongelado en {out.name}")
