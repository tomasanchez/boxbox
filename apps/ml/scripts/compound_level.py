"""El escalón de ritmo entre compuestos, medido donde todavía no hay desgaste.

Hay un agujero conocido en el modelo y este script va a buscarlo. El simulador
mide el desgaste de cada compuesto como la **pendiente** de su tanda, y para eso
compara cada vuelta contra la referencia de su propia tanda. Eso cancela el nivel
absoluto del compuesto: si el duro arranca medio segundo más lento que el medio y
después se estabiliza, la medición ve la misma pendiente y no ve el escalón.

:data:`boxbox_ml.strategy.COMPOUND_OFFSET_S` es ese escalón, y está en **cero**.

La consecuencia es concreta y se descubrió al dejar que la búsqueda eligiera con
qué largar: en Zandvoort el modelo cree que el medio se gasta 1,48 veces más
rápido que el duro y dura un 24% menos, así que queda **estrictamente dominado** y
la búsqueda lo elige una vez de veintidós. En la realidad, el 79% del frente de la
grilla larga en medio. Veintidós equipos no se equivocan sistemáticamente.

## Por qué este intento puede salir distinto del anterior

Ya se intentó medir esto dentro de la carrera y se abandonó, con razón: los
compuestos se corren en momentos sistemáticamente distintos —el medio al 26% de
la carrera, el duro al 61%— y separar el neumático de veinticinco vueltas de
combustible y evolución de pista pedía una corrección más fina que la que hay.

Acá cambian dos cosas.

**Se mira sólo el arranque de cada tanda.** Con la goma casi nueva el desgaste
todavía no acumuló, así que lo que queda es el nivel del compuesto, que es
justamente lo que falta. Se saltea la vuelta de salida, que trae el pit lane.

**Se compara dentro del mismo piloto y la misma carrera.** Con efectos fijos por
piloto-carrera, el auto, el piloto, el circuito y el clima se cancelan, y el
compuesto se identifica comparando tandas del mismo auto en la misma tarde.

Lo que **no** se cancela es el avance de carrera, porque dos tandas del mismo auto
están en momentos distintos. Para eso está la corrección de combustible ya
ajustada, y como es el supuesto que puede tumbar todo, se prueba su sensibilidad
al final en vez de confiar en ella.

Correr con ``uv run python scripts/compound_level.py``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from boxbox_ml import cache, features, neutralisation, track_status
from boxbox_ml.features import RACE_PROGRESS_S_PER_LAP

pd.set_option("display.width", 200)
SEP = "=" * 88

DRY = ("SOFT", "MEDIUM", "HARD")

#: Vueltas de la tanda que se miran. La 1 es la de salida de boxes y trae el pit
#: lane, así que se descarta; de la 2 a la 5 la goma está prácticamente nueva.
FIRST_LAP, LAST_LAP = 2, 5

#: Un piloto-carrera sólo sirve si corrió al menos dos compuestos distintos: con
#: uno solo no aporta nada a una comparación entre compuestos.
MIN_COMPOUNDS = 2


def load() -> pd.DataFrame:
    """Vueltas verdes representativas, con corrección de combustible y tanda."""
    parts = [pd.read_parquet(cache.cache_dir().parent / "laps_overtaking.parquet")]
    for extra in ("monza2026.parquet",):
        path = cache.cache_dir().parent / extra
        if path.exists():
            parts.append(pd.read_parquet(path))
    raw = pd.concat(parts, ignore_index=True)
    raw["circuit"] = raw["circuit"].map(lambda c: neutralisation.CIRCUIT_ALIASES.get(c, c))

    frame = features.add_stint_position(
        features.add_fuel_correction(features.mark_representative(track_status.add_flags(raw)))
    )
    rain = frame.groupby(["year", "round"])["Rainfall"].mean()
    wet = set(rain[rain > 0.2].index)
    return frame[
        frame["is_representative"]
        & ~frame["is_neutralised"]
        & ~frame["red"]
        & ~frame["yellow"]
        & ~pd.MultiIndex.from_frame(frame[["year", "round"]]).isin(wet)
        & frame["Compound"].isin(DRY)
    ]


def openings(green: pd.DataFrame, beta: float) -> pd.DataFrame:
    """El ritmo de arranque de cada tanda, corregido por avance de carrera.

    Args:
        green: Vueltas verdes representativas.
        beta: Segundos por vuelta que se le devuelven al reloj por cada vuelta que
            falta. Es el parámetro cuya sensibilidad se prueba después.

    Returns:
        Una fila por tanda: piloto-carrera, compuesto y el ritmo medio de sus
        primeras vueltas.
    """
    window = green[green["stint_lap"].between(FIRST_LAP, LAST_LAP)].copy()
    window["pace"] = window["LapTime"] - beta * (window["total_laps"] - window["LapNumber"])
    rows = window.groupby([*features.STINT_KEYS], dropna=False).agg(
        year=("year", "first"),
        round=("round", "first"),
        driver=("Driver", "first"),
        circuit=("circuit", "first"),
        compound=("Compound", "first"),
        pace=("pace", "mean"),
        laps=("pace", "size"),
    )
    rows = rows[rows["laps"] >= 2].reset_index(drop=True)
    rows["unit"] = rows["year"].astype(str) + "-" + rows["round"].astype(str) + "-" + rows["driver"]
    return rows


def offsets(stints: pd.DataFrame) -> tuple[dict[str, float], int, int]:
    """El escalón por compuesto, con efectos fijos por piloto-carrera.

    Centrar cada tanda contra la media de su propio piloto-carrera **es** el
    efecto fijo: lo que queda es la desviación dentro de esa tarde, y ahí el auto
    y el circuito ya no están.

    Returns:
        El escalón de cada compuesto respecto del duro, cuántas tandas lo
        sostienen y cuántos piloto-carrera aportaron.
    """
    usable = stints.groupby("unit")["compound"].transform("nunique") >= MIN_COMPOUNDS
    inner = stints[usable].copy()
    inner["centred"] = inner["pace"] - inner.groupby("unit")["pace"].transform("mean")

    # Los pesos de cada compuesto no son iguales dentro de cada unidad, así que la
    # media centrada arrastra un residuo. Se resuelve con mínimos cuadrados sobre
    # las variables indicadoras, que es lo mismo que el efecto fijo bien hecho.
    dummies = pd.get_dummies(inner["compound"]).astype(float)
    dummies = dummies.sub(dummies.groupby(inner["unit"].to_numpy()).transform("mean"))
    coef, *_ = np.linalg.lstsq(dummies.to_numpy(), inner["centred"].to_numpy(), rcond=None)
    raw = dict(zip(dummies.columns, coef, strict=True))
    base = raw.get("HARD", 0.0)
    return ({c: raw.get(c, 0.0) - base for c in DRY}, len(inner), inner["unit"].nunique())


green = load()

print(SEP)
print("### 1. DE DONDE SALE LA MEDICION")
print()
stints = openings(green, RACE_PROGRESS_S_PER_LAP)
print(f"  tandas con arranque utilizable (vueltas {FIRST_LAP}-{LAST_LAP}): {len(stints)}")
print(f"  piloto-carrera distintos: {stints['unit'].nunique()}")
print()
print(stints.groupby("compound")["pace"].agg(["size", "median"]).round(3).to_string())
print()
print("  Esas medianas NO son el escalón: cada compuesto se corre en momentos y")
print("  en autos distintos. Para eso están los efectos fijos de abajo.")

print("\n" + SEP)
print("### 2. EL ESCALON, DENTRO DEL MISMO PILOTO Y LA MISMA CARRERA")
print()
step, n_stints, n_units = offsets(stints)
print(f"  {n_stints} tandas sobre {n_units} piloto-carrera que corrieron 2+ compuestos")
print()
for compound in DRY:
    print(f"  {compound:7s} {step[compound]:+.3f} s/vuelta respecto del duro")
print()
print("  Negativo = más rápido que el duro con goma nueva.")

print("\n" + SEP)
print("### 3. POR TEMPORADA — ¿SE MUEVE?")
print()
rows = []
for year, block in stints.groupby("year"):
    if block["unit"].nunique() < 30:
        continue
    step_y, n_s, n_u = offsets(block)
    rows.append(
        {
            "año": int(year),
            "tandas": n_s,
            "unidades": n_u,
            **{c.lower(): round(step_y[c], 3) for c in DRY},
        }
    )
print(pd.DataFrame(rows).to_string(index=False))

print("\n" + SEP)
print("### 4. LA PRUEBA QUE PUEDE TUMBARLO: ¿DEPENDE DE BETA?")
print()
print("El avance de carrera es lo único que los efectos fijos NO cancelan, porque")
print("dos tandas del mismo auto están en momentos distintos. Si el escalón se")
print("mueve mucho al cambiar beta, lo que se midió es beta y no el compuesto.")
print()
rows = []
for beta in (0.0, 0.028, RACE_PROGRESS_S_PER_LAP, 0.084, 0.112):
    step_b, _, _ = offsets(openings(green, beta))
    rows.append(
        {
            "beta": beta,
            "medio vs duro": round(step_b["MEDIUM"], 3),
            "blando vs duro": round(step_b["SOFT"], 3),
        }
    )
table = pd.DataFrame(rows)
print(table.to_string(index=False))
print()
span = table["medio vs duro"].max() - table["medio vs duro"].min()
print(f"  el escalón del medio se mueve {span:.3f} s/vuelta entre beta=0 y beta=0,112")
print(f"  (beta ajustado es {RACE_PROGRESS_S_PER_LAP}; el rango probado es de cero al doble)")
