"""Cuánto creerle al desgaste de un circuito, según cuántas tandas lo respaldan.

Dos errores propios con la misma causa, y por eso se arreglan juntos.

**El primero: dos «Zandvoort» distintos en el mismo repo.**
:data:`boxbox_ml.strategy.WEAR_CUTS` está documentado como «2026 Zandvoort» y da
0,0625 s/vuelta para el medio, mientras que ``RaceModel.for_circuit("Zandvoort")``
da 0,1022. Reproduciendo ``scripts/zandvoort_distributions.py`` se ve de dónde
sale la diferencia: el filtro es ``dry[dry["circuit"] == CIRCUIT]``, **sin filtro
de año**, así que los cortes salen de Zandvoort en TODAS las eras — 79 tandas de
medio, contra las 11 que tiene 2026. La etiqueta está mal.

Y eso choca con la política que el propio informe declara: el desgaste por
compuesto se mide **sólo con 2026**, porque este año se invirtió el orden de los
compuestos. Pooleamos eras justo en la cantidad donde dijimos que no se puede.

**El segundo: el encogimiento por circuito es uniforme donde los datos no lo son.**
``circuit_wear.json`` aplica un factor único de 0,892 a celdas que van de **una**
tanda (Silverstone en blando) a **veintinueve** (Spielberg en medio). Silverstone
sale de una sola medición y se lo trata como casi certeza.

La solución es la misma para los dos: **encoger según cuántas tandas hay detrás.**
Es el modelo jerárquico de siempre. Si la media verdadera de cada circuito se
reparte alrededor de la mediana de la temporada con varianza ``entre``, y cada
celda la estima con error ``dentro/n``, entonces el peso que hay que darle a la
medición del circuito es::

    w = entre / (entre + dentro/n)

Con muchas tandas ``w`` tiende a uno y se le cree al circuito; con pocas tiende a
cero y se cae a la mediana de la temporada. No hay que elegir entre «por circuito»
y «promedio»: la cantidad de datos elige sola, celda por celda.

Correr con ``uv run python scripts/wear_shrinkage.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from boxbox_ml import cache, features, neutralisation, strategy, track_status

pd.set_option("display.width", 200)
SEP = "=" * 88

DRY = ("SOFT", "MEDIUM", "HARD")

#: Tandas mínimas para que una celda entre en el ajuste. Con menos de tres no hay
#: con qué estimar su dispersión interna, aunque igual reciben su peso al final.
MIN_FOR_VARIANCE = 3

#: Tandas mínimas para que una celda sirva para ESTIMAR el ruido y la señal.
#: Con pocas, el error de su mediana es enorme y contamina la estimación — es
#: exactamente el error que se comenta más abajo.
MIN_FOR_LEVEL = 12

#: Remuestreos para el error estándar de la mediana. La mediana no tiene una
#: fórmula de varianza tan limpia como la media, así que se mide.
BOOTSTRAP = 400


def load_stints() -> pd.DataFrame:
    """Una fila por tanda: circuito, año, compuesto y ritmo de caída ajustado."""
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
    green = frame[
        frame["is_representative"]
        & ~frame["is_neutralised"]
        & ~frame["red"]
        & ~frame["yellow"]
        & ~pd.MultiIndex.from_frame(frame[["year", "round"]]).isin(wet)
    ]

    rows = []
    for _keys, stint in green.groupby(features.STINT_KEYS, dropna=False):
        pace = stint["lap_time_fuel_corrected"].to_numpy(dtype=float)
        position = stint["stint_lap"].to_numpy(dtype=float)
        if len(pace) < 8 or not np.isfinite(pace).all():
            continue
        rows.append(
            {
                "circuit": stint["circuit"].iloc[0],
                "year": int(stint["year"].iloc[0]),
                "compound": stint["Compound"].iloc[0],
                "slope": float(np.polyfit(position, pace, 1)[0]),
            }
        )
    stints = pd.DataFrame(rows)
    return stints[stints["compound"].isin(DRY)]


def median_error(values: np.ndarray, rng: np.random.Generator) -> float:
    """Error estándar de la mediana, por remuestreo."""
    if len(values) < 2:
        return float("nan")
    draws = rng.choice(values, size=(BOOTSTRAP, len(values)), replace=True)
    return float(np.median(draws, axis=1).std(ddof=1))


stints = load_stints()
season = stints[stints["year"] == 2026]

print(SEP)
print("### 1. DE DONDE SALE CADA NUMERO DE ZANDVOORT")
print()
zand = stints[stints["circuit"] == "Zandvoort"]
rows = []
for compound in DRY:
    todas = zand[zand["compound"] == compound]["slope"]
    solo26 = zand[(zand["compound"] == compound) & (zand["year"] == 2026)]["slope"]
    rows.append(
        {
            "compuesto": compound,
            "WEAR_CUTS": strategy.WEAR_CUTS[compound][4],
            "todas las eras": round(float(todas.median()), 4),
            "n": len(todas),
            "sólo 2026": round(float(solo26.median()), 4),
            "n 2026": len(solo26),
        }
    )
print(pd.DataFrame(rows).to_string(index=False))
print()
print("  WEAR_CUTS coincide con la columna de TODAS LAS ERAS, no con 2026. La")
print("  etiqueta del código («2026 Zandvoort») está mal, y contradice la política")
print("  que el informe declara para esta cantidad.")

# ------------------------------------------------- 2. el modelo jerárquico

print("\n" + SEP)
print("### 2. CUANTO PESA UNA TANDA, MEDIDO")
print()

generator = np.random.default_rng(11)
cells = []
for (circuit, compound), group in season.groupby(["circuit", "compound"]):
    values = group["slope"].to_numpy(dtype=float)
    cells.append(
        {
            "circuit": circuit,
            "compound": compound,
            "n": len(values),
            "median": float(np.median(values)),
            "se": median_error(values, generator) if len(values) >= MIN_FOR_VARIANCE else np.nan,
        }
    )
cell = pd.DataFrame(cells)

# El nivel de cada compuesto en la temporada: hacia ahí se encoge.
level = cell.groupby("compound").apply(
    lambda g: np.average(g["median"], weights=g["n"]), include_groups=False
)
cell["deviation"] = cell["median"] - cell["compound"].map(level)

# **Un error propio que vale la pena dejar escrito, porque casi cambia el modelo.**
#
# El primer intento estimaba el ruido como el promedio de ``se**2`` sobre TODAS
# las celdas —incluidas las de tres tandas, cuyo error es enorme— y lo comparaba
# contra la varianza de las desviaciones de todas. Las celdas chicas inflaban el
# ruido por encima de la señal, la varianza verdadera entre circuitos daba
# NEGATIVA, y el modelo concluía que ningún circuito se distingue del promedio.
#
# Era falso, y lo delataba que contradecía la partición por mitades, que sobre
# las mismas celdas da correlaciones de 0,68 a 0,84. El ruido hay que estimarlo
# donde se lo puede estimar: en las celdas con suficientes tandas.
solid = cell[cell["n"] >= MIN_FOR_LEVEL].dropna(subset=["se"])

# Ruido de UNA tanda, que es lo que se escala por n. Sale de la dispersión
# interna medida, no de extrapolar el error de la mediana.
within = float(
    np.average(
        [
            season[(season["circuit"] == r.circuit) & (season["compound"] == r.compound)][
                "slope"
            ].var(ddof=1)
            for r in solid.itertuples()
        ],
        weights=solid["n"],
    )
)
# Cuánto de la dispersión entre celdas sobrevive a descontarle su propio ruido.
observed = float(np.var(solid["deviation"], ddof=1))
noise = float(np.mean(solid["se"] ** 2))
between = max(observed - noise, 1e-9)

# El error de una mediana no es sigma^2/n sino algo mayor; se mide la constante
# en vez de suponer normalidad.
inflation = float(np.average(solid["se"] ** 2 * solid["n"] / within, weights=solid["n"]))

print(f"  celdas con al menos {MIN_FOR_LEVEL} tandas      {len(solid)} de {len(cell)}")
print(f"  ruido de una sola tanda             {within:.6f}   (sd {np.sqrt(within):.4f})")
print(f"  dispersión observada entre celdas   {observed:.6f}")
print(f"  parte que es ruido de medición      {noise:.6f}")
senal = 100 * (1 - noise / observed)
print(f"  dispersión verdadera entre circuitos {between:.6f}   ({senal:.0f}% es señal)")
print()
half = inflation * within / between
print(f"  **Una celda con {half:.1f} tandas merece medio peso.**")
print("  Con muchas más, se le cree al circuito; con muchas menos, a la temporada.")

cell["peso"] = between / (between + inflation * within / cell["n"])
cell["encogido"] = cell["peso"] * cell["deviation"]

print("\n" + SEP)
print("### 3. QUE CAMBIA, CELDA POR CELDA")
print()
show = cell.sort_values("n")[
    ["circuit", "compound", "n", "median", "deviation", "peso", "encogido"]
]
show = pd.concat([show.head(6), show.tail(6)])
print(show.round(4).to_string(index=False))
print()
print("  El factor único de 0,892 que usaba circuit_wear.json le daba a la celda de")
print("  una tanda el mismo crédito que a la de veintinueve. Ahora Silverstone en")
print("  blando —una sola medición— casi no se mueve del promedio, y Spielberg en")
print("  medio —veintinueve— se queda casi entero con su número.")

print("\n" + SEP)
print("### 4. ZANDVOORT, QUE ERA EL CASO QUE DESTAPO ESTO")
print()
for compound in DRY:
    row = cell[(cell["circuit"] == "Zandvoort") & (cell["compound"] == compound)]
    if row.empty:
        continue
    row = row.iloc[0]
    target = float(level[compound]) + float(row["encogido"])
    print(
        f"  {compound:7s} n={int(row['n']):2d}  peso {row['peso']:.2f}  "
        f"medido {row['median']:.4f}  ->  {target:.4f}"
        f"   (antes: {strategy.WEAR_CUTS[compound][4]:.4f} con todas las eras)"
    )

payload = {
    "metodo": "encogimiento jerarquico: w = entre / (entre + dentro/n), por celda",
    "tandas_para_medio_peso": round(half, 1),
    "dispersion_entre_circuitos": round(between, 6),
    "ruido_de_una_tanda": round(within, 6),
    "nivel_temporada_s_vuelta": {c: round(float(level[c]), 5) for c in DRY if c in level},
    "celdas": {
        circuit: {
            row["compound"]: {
                "n": int(row["n"]),
                "peso": round(float(row["peso"]), 3),
                "encogido": round(float(row["encogido"]), 5),
            }
            for _, row in group.iterrows()
        }
        for circuit, group in cell.groupby("circuit")
    },
}
out = Path(__file__).resolve().parents[1] / "src" / "boxbox_ml" / "circuit_wear.json"
out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nescrito en {out.name}")
