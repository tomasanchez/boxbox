"""El análisis de datos: volumen, embudo de filtrado y la matriz de columnas.

Escribe tablas en **markdown** a ``apps/ml/data/dataset_profile.md`` para pegarlas
en el informe. El informe tiene que llevar los números, no una cita a este
archivo: citar un script no es evidencia, es una promesa.

Cinco tablas:

1. **Volumen por temporada** — de dónde salen las filas.
2. **Embudo de filtrado** — cuántas filas sobreviven a cada criterio y por qué.
   Es la tabla que dice si una métrica se midió sobre 117.000 vueltas o sobre
   8.000, que no es lo mismo.
3. **La matriz de columnas** — cada variable que los modelos consumen, con su
   tipo, sus nulos y su rango. Separadas por rol: las que entran al regresor de
   degradación, las que entran al clasificador de parada, y las derivadas que
   sólo sirven de insumo.
4. **El objetivo por compuesto** — qué se intenta predecir y cómo se reparte.
5. **Cobertura por circuito y compuesto** — dónde hay datos y dónde no, que es
   lo que decide qué circuitos el simulador puede correr con números propios.

Correr con ``uv run python scripts/dataset_profile.py``.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from boxbox_ml import cache, features

warnings.filterwarnings("ignore")
pd.set_option("display.width", 220)

#: Qué consume cada modelo. Se copian de `scripts/holdout_eval.py`, que es donde
#: se entrenan, para que la tabla describa lo que de verdad se usa.
REGRESOR = ["stint_lap", "TyreLife", "laps_remaining", "TrackTemp", "AirTemp", "Compound"]
RETARDADAS = [
    "degradation_s",
    "degradation_rate_s_per_lap",
    "lap_time_fuel_corrected",
    "gap_ahead_s",
    "gap_behind_s",
    "Position",
]
DIRECTAS = ["stint_lap", "TyreLife", "laps_remaining", "total_laps", "TrackTemp", "AirTemp"]
BANDERAS = ["FreshTyre", "is_neutralised", "sc", "vsc", "yellow"]
CATEGORICAS = ["Compound", "circuit"]
OBJETIVO = "degradation_s"

GLOSARIO = {
    "stint_lap": "vuelta dentro de la tanda, 1 en la primera",
    "TyreLife": "vueltas que lleva el juego, incluye las de práctica",
    "laps_remaining": "vueltas que faltan para la bandera",
    "total_laps": "largo de la carrera",
    "TrackTemp": "temperatura de pista (°C)",
    "AirTemp": "temperatura del aire (°C)",
    "Compound": "blando / medio / duro",
    "circuit": "el trazado",
    "FreshTyre": "el juego salió nuevo",
    "is_neutralised": "la vuelta corrió bajo alguna bandera",
    "sc": "safety car",
    "vsc": "safety car virtual",
    "yellow": "bandera amarilla",
    "degradation_s": "segundos perdidos contra la referencia de la propia tanda",
    "degradation_rate_s_per_lap": "pendiente de esa caída",
    "lap_time_fuel_corrected": "vuelta con el efecto de combustible descontado",
    "gap_ahead_s": "hueco al auto de adelante",
    "gap_behind_s": "hueco al de atrás",
    "Position": "puesto en esa vuelta",
}

SALIDA = Path(__file__).resolve().parents[1] / "data" / "dataset_profile.md"
FIGURAS = Path(__file__).resolve().parents[3] / "docs" / "tp" / "figuras"
bloques: list[str] = []


def emitir(titulo: str, cuerpo: str) -> None:
    bloques.append(f"#### {titulo}\n\n{cuerpo}\n")
    print("\n" + "=" * 90)
    print(titulo)
    print("=" * 90)
    print(cuerpo)


def md(frame: pd.DataFrame) -> str:
    return frame.to_markdown(index=False)


crudo = pd.read_parquet(cache.cache_dir().parent / "laps_overtaking.parquet")
frame = features.build(crudo)

# ------------------------------------------------------- 1. volumen por temporada

por_temporada = (
    frame.groupby("year")
    .agg(
        carreras=("round", "nunique"),
        circuitos=("circuit", "nunique"),
        pilotos=("Driver", "nunique"),
        vueltas=("LapNumber", "size"),
    )
    .reset_index()
    .rename(columns={"year": "temporada"})
)
por_temporada["vueltas"] = por_temporada["vueltas"].map("{:,}".format)
carreras = int(frame["round"].groupby(frame["year"]).nunique().sum())
total = f"| **total** | **{carreras}** | | | **{len(frame):,}** |"
emitir(
    "Volumen por temporada",
    md(por_temporada) + "\n" + total,
)

# --------------------------------------------------------- 2. embudo de filtrado

neutralizadas = frame[frame["is_neutralised"]]
representativas = frame[frame["is_representative"]]
secas_rep = representativas[representativas["Compound"].isin(("SOFT", "MEDIUM", "HARD"))]
pasos = [
    ("vueltas crudas de FastF1", len(frame), "todo lo que devuelve la API"),
    (
        "con tiempo de vuelta",
        int(frame["LapTime"].notna().sum()),
        "descarta abandonos y vueltas sin cronometrar",
    ),
    (
        "representativas",
        len(representativas),
        "y además: no es entrada ni salida de boxes, no fue borrada por los comisarios, "
        "y pasa el control `IsAccurate` de FastF1",
    ),
    (
        "en seco",
        len(secas_rep),
        "fuera intermedio y lluvia, que el simulador no representa",
    ),
]
filas = []
anterior = len(frame)
for nombre, n, por_que in pasos:
    filas.append(
        {
            "paso": nombre,
            "vueltas": f"{n:,}",
            "% del crudo": f"{n / len(frame):.1%}",
            "pierde": f"{anterior - n:,}" if anterior != n else "—",
            "qué exige": por_que,
        }
    )
    anterior = n

# El dato que hace falta decir, porque si no la tabla parece que le falta un
# filtro: NO hay un paso «en verde» aparte. Las vueltas neutralizadas fallan
# TODAS el control `IsAccurate`, asi que el filtro de representativas ya se las
# llevo. Es redundancia, no un error: el conjunto de ajuste siempre fue de
# vueltas limpias. Lo que estaba mal era contarlo como dos filtros distintos.
cruce = int((frame["is_representative"] & frame["is_neutralised"]).sum())
SALTO = chr(10) + chr(10)
nota = (
    SALTO
    + "**No hay un paso «en verde» aparte, y conviene explicar por qué.** "
    + f"De las {len(neutralizadas):,} vueltas corridas bajo alguna bandera, "
    + "**todas fallan el control `IsAccurate` de FastF1**, así que el filtro de "
    + f"representativas ya se las llevó: quedan {cruce} vueltas neutralizadas en "
    + "el conjunto de ajuste. Filtrar por bandera después no saca ninguna fila "
    + "más: es redundante, no incorrecto."
    + SALTO
    + "Y el objetivo `degradation_s` resulta no nulo **exactamente** en esas "
    + f"mismas {len(representativas):,} filas, porque se calcula contra una "
    + "referencia que sólo existe cuando la tanda tiene vueltas representativas."
)
emitir("Embudo de filtrado", md(pd.DataFrame(filas)) + nota)

# ------------------------------------------------------- 3. la matriz de columnas

usable = frame[frame["is_representative"] & ~frame["is_neutralised"]]


#: Los tres secos. Intermedio y lluvia existen en los datos pero el simulador no
#: los representa, así que describirlos acá confundiría la lectura.
SECOS = ("SOFT", "MEDIUM", "HARD")


def describir(columnas: list[str], rol: str, marco: pd.DataFrame | None = None) -> pd.DataFrame:
    filas = []
    base = usable if marco is None else marco
    for c in columnas:
        s = base[c]
        if s.dtype == bool or s.dtype == object:
            top = s.value_counts(normalize=True)
            rango = (
                f"{len(top)} valores · más común {top.index[0]} ({top.iloc[0]:.0%})"
                if len(top)
                else "—"
            )
        else:
            rango = f"{s.min():.1f} … {s.median():.1f} … {s.max():.1f}"
        filas.append(
            {
                "columna": c,
                "qué es": GLOSARIO.get(c, ""),
                "tipo": str(s.dtype),
                "nulos": f"{s.isna().mean():.1%}",
                "mín · mediana · máx": rango,
                "rol": rol,
            }
        )
    return pd.DataFrame(filas)


matriz = pd.concat(
    [
        describir(REGRESOR, "regresor"),
        describir([c for c in DIRECTAS if c not in REGRESOR], "clasificador"),
        # Las banderas se describen sobre TODO el marco: en el subconjunto en
        # verde valen False por construcción y la tabla diría «100% False».
        describir(BANDERAS, "clasificador", marco=frame),
        describir([c for c in CATEGORICAS if c not in REGRESOR], "clasificador"),
        describir(RETARDADAS, "clasificador (de la vuelta anterior)"),
    ],
    ignore_index=True,
).drop_duplicates(subset="columna", keep="first")
emitir(
    f"La matriz de columnas · {len(matriz)} variables sobre {len(usable):,} vueltas en verde",
    md(matriz),
)

# ---------------------------------------------------------- 4. el objetivo

obj = usable[usable[OBJETIVO].notna() & usable["Compound"].isin(SECOS)]
por_compuesto = (
    obj.groupby("Compound")[OBJETIVO]
    .agg(
        vueltas="size",
        p10=lambda s: s.quantile(0.10),
        mediana="median",
        p90=lambda s: s.quantile(0.90),
        desvio="std",
    )
    .round(3)
    .reset_index()
    .rename(columns={"Compound": "compuesto"})
)
por_compuesto["vueltas"] = por_compuesto["vueltas"].map("{:,}".format)
emitir(
    f"El objetivo: `{OBJETIVO}`, segundos perdidos contra la referencia de la tanda",
    md(por_compuesto) + "\n\nEl desvío es **mayor que la mediana en los tres compuestos**: la "
    "incertidumbre de una vuelta es más grande que la señal que se intenta predecir, "
    "y eso es lo que justifica simular en vez de estimar un valor puntual.",
)

# ------------------------------------------------- 5. cobertura por circuito

cobertura = (
    obj[obj["year"] == 2026]
    .pivot_table(index="circuit", columns="Compound", values=OBJETIVO, aggfunc="size")
    .fillna(0)
    .astype(int)
)
cobertura = cobertura.reindex(columns=["SOFT", "MEDIUM", "HARD"], fill_value=0)
cobertura["total"] = cobertura.sum(axis=1)
cobertura = cobertura.sort_values("total", ascending=False).reset_index()
cobertura.columns = ["circuito", "blando", "medio", "duro", "total"]
vacias = int((cobertura[["blando", "medio", "duro"]] == 0).sum().sum())
emitir(
    "Cobertura 2026 por circuito y compuesto (vueltas en verde con objetivo medible)",
    md(cobertura)
    + f"\n\n**{vacias} celdas vacías** de {len(cobertura) * 3}. Un circuito sin celdas "
    "propias se corre con el promedio de la temporada, que es exactamente lo que se "
    "hizo con Madrid y con Bakú.",
)


# --------------------------------------------------- 6. la matriz de correlación

NUMERICAS = [
    "degradation_s",
    "stint_lap",
    "TyreLife",
    "laps_remaining",
    "total_laps",
    "TrackTemp",
    "AirTemp",
    "gap_ahead_s",
    "gap_behind_s",
    "Position",
    "lap_time_fuel_corrected",
]
secas = usable[usable["Compound"].isin(SECOS)]
# Spearman y no Pearson: varias de estas columnas tienen colas largas —el hueco al
# de adelante llega a 1.144 s— y una correlación lineal las dejaría dominar.
corr = secas[NUMERICAS].corr(method="spearman")

emitir(
    f"Matriz de correlación de Spearman · {len(secas):,} vueltas",
    md(corr.round(2).reset_index().rename(columns={"index": ""})),
)

figura, ax = plt.subplots(figsize=(7.6, 6.4))
im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
ax.set_xticks(range(len(NUMERICAS)), NUMERICAS, rotation=45, ha="right", fontsize=7.5)
ax.set_yticks(range(len(NUMERICAS)), NUMERICAS, fontsize=7.5)
ax.grid(False)
for i in range(len(NUMERICAS)):
    for j in range(len(NUMERICAS)):
        v = corr.iat[i, j]
        ax.text(
            j,
            i,
            f"{v:.2f}",
            ha="center",
            va="center",
            fontsize=6.6,
            color="white" if abs(v) > 0.55 else "#1a202c",
        )
figura.colorbar(im, ax=ax, shrink=0.78, label="Spearman")
ax.set_title("Correlación entre las variables del modelo", fontsize=10, pad=10)
figura.tight_layout()
FIGURAS.mkdir(parents=True, exist_ok=True)
figura.savefig(FIGURAS / "fig-correlacion.png", dpi=160)
plt.close(figura)
print("figura: fig-correlacion.png")

SALIDA.parent.mkdir(parents=True, exist_ok=True)
SALIDA.write_text("\n".join(bloques), encoding="utf-8")
print(f"\n\nmarkdown para el informe en {SALIDA}")
