# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 1 · Los datos y su limpieza
#
# Este cuaderno documenta **de dónde salen los datos y qué se les hace antes de
# medir nada**. Cada decisión de limpieza se muestra con el antes y el después,
# porque varias cambian los resultados de forma grande y nada obvia.
#
# El orden es el de la tubería real (`boxbox_ml.ingest` → `boxbox_ml.features`),
# así que lo que se ve acá es lo que efectivamente corre.
#
# **Fuente:** FastF1 3.8.3 sobre el archivo de cronometraje oficial de la F1.
# **Alcance:** temporadas 2022 a 2026, era de efecto suelo.

# %%
from __future__ import annotations

import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from boxbox_ml import cache, features, neutralisation, track_status

warnings.filterwarnings("ignore")
pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 40)
plt.rcParams.update({"figure.figsize": (9, 3.6), "figure.dpi": 110, "font.size": 9})

# La ingesta cruda tarda unos ocho minutos porque parsea el caché de FastF1
# sesión por sesión. Se guarda en parquet para que este cuaderno sea instantáneo.
PARQUET = cache.cache_dir().parent / "laps_overtaking.parquet"
raw = pd.read_parquet(PARQUET)
print(f"filas crudas: {len(raw):,}")
print(f"carreras:     {raw.groupby(['year', 'round']).ngroups}")
print(f"temporadas:   {sorted(raw['year'].unique())}")

# %% [markdown]
# ## 1.1 Qué trae una fila
#
# Una fila es **un piloto en una vuelta**. FastF1 entrega el cronometraje por
# sector, el estado del neumático, el estado de pista y una muestra de clima
# alineada a esa vuelta.

# %%
raw[
    [
        "year",
        "round",
        "circuit",
        "Driver",
        "LapNumber",
        "Stint",
        "Compound",
        "TyreLife",
        "LapTime",
        "TrackStatus",
        "Position",
        "IsAccurate",
        "pit_in",
        "Rainfall",
    ]
].head(4)

# %% [markdown]
# ## 1.2 Tres trampas del formato
#
# Ninguna está documentada de forma prominente y las tres producen resultados
# equivocados en silencio.

# %% [markdown]
# ### Trampa 1 · `TrackStatus` es una cadena concatenada, no un código
#
# Cuando en una vuelta se solapan dos estados, FastF1 devuelve **los dígitos
# pegados**. Un `"45"` no es el estado cuarenta y cinco: es «safety car» (4) y
# «bandera roja» (5) en la misma vuelta. Compararlo por igualdad pierde todo lo
# que no sea un estado puro.

# %%
counts = raw["TrackStatus"].astype(str).value_counts().head(12)
print("valores más frecuentes de TrackStatus:")
print(counts.to_string())

pure = raw["TrackStatus"].astype(str).str.len().eq(1)
compuestos = [v for v in counts.index if len(str(v)) > 1]
print(f"\nvalores compuestos entre los 12 más frecuentes: {compuestos}")
print(f"vueltas con estado compuesto: {(~pure).sum():,} de {len(raw):,} ({(~pure).mean():.1%})")
print("Compararlas por igualdad las perdería a todas.")

# %%
# `track_status.add_flags` decodifica por dígito contenido, no por igualdad.
flagged = track_status.add_flags(raw)
print(
    flagged[["yellow", "sc", "vsc", "vsc_ending", "red", "is_neutralised"]]
    .mean()
    .mul(100)
    .round(2)
    .rename("% de vueltas")
    .to_string()
)

# %% [markdown]
# ### Trampa 2 · El nombre del circuito no es estable entre temporadas
#
# `Location` cambia de una temporada a otra para el mismo circuito. Agrupar por
# ese campo parte un circuito en dos y arruina cualquier tasa por circuito.

# %%
por_circuito = flagged.groupby("circuit")["year"].agg(temporadas=lambda s: sorted(s.unique()))
sospechosos = por_circuito[por_circuito["temporadas"].map(len) <= 2]
print("circuitos presentes en dos temporadas o menos (candidatos a alias):")
print(sospechosos.to_string())
print(f"\nalias que aplica el proyecto: {neutralisation.CIRCUIT_ALIASES}")

# %%
canon = flagged.copy()
canon["circuit"] = canon["circuit"].map(lambda c: neutralisation.CIRCUIT_ALIASES.get(c, c))
print(f"circuitos antes del alias:  {flagged['circuit'].nunique()}")
print(f"circuitos después:          {canon['circuit'].nunique()}")

# %% [markdown]
# ### Trampa 3 · El límite de peticiones trunca en silencio
#
# FastF1 corta a las 500 llamadas por hora. Al pasarse **no falla**: devuelve
# sesiones vacías y la ingesta sigue como si nada. Una corrida temprana de este
# proyecto quedó con 2023 y 2024 a medio cargar y 2025 ausente, y el caché
# incompleto sesgó la degradación del blando de 2023 un **60%**, de 0,0664 a
# 0,0403 s/vuelta.
#
# La defensa es contar carreras por temporada antes de creerle a nada.

# %%
por_temporada = canon.groupby("year").agg(
    carreras=("round", "nunique"),
    vueltas=("LapNumber", "size"),
    pilotos=("Driver", "nunique"),
)
por_temporada["esperadas"] = [22, 22, 24, 24, 24]
por_temporada["completa"] = por_temporada["carreras"] >= por_temporada["esperadas"] - 1
por_temporada

# %% [markdown]
# 2026 tiene 12 carreras porque **la temporada está en curso**, no porque falte
# nada. Las otras cuatro están completas.

# %% [markdown]
# ## 1.3 Qué vuelta sirve para medir ritmo
#
# La mayoría de las vueltas de una carrera **no describen ritmo de carrera**. Se
# marcan cuatro clases como no representativas, y se dejan en la tabla en vez de
# borrarlas: la vuelta de entrada a boxes es exactamente donde vive la etiqueta
# que el modelo quiere predecir.

# %%
marked = features.mark_representative(canon)
razones = pd.DataFrame(
    {
        "sin LapTime": marked["LapTime"].isna(),
        "IsAccurate falso": ~marked["IsAccurate"].eq(True),
        "borrada por comisarios": marked["Deleted"].eq(True),
        "entrada a boxes": marked["pit_in"].astype(bool),
        "salida de boxes": marked["pit_out"].astype(bool),
    }
)
resumen = razones.sum().rename("vueltas").to_frame()
resumen["% del total"] = (resumen["vueltas"] / len(marked) * 100).round(2)
print(resumen.to_string())
print(
    f"\nrepresentativas: {marked['is_representative'].sum():,} de {len(marked):,} "
    f"({marked['is_representative'].mean():.1%})"
)

# %% [markdown]
# ## 1.4 Corrección por avance de carrera
#
# Una vuelta corrida con `n` vueltas por delante es aproximadamente `beta * n`
# segundos más lenta que la misma vuelta al final. Sin descontarlo, la
# degradación queda **invisible**: el neumático frena al auto a más o menos el
# mismo ritmo al que el avance de la carrera lo acelera.
#
# El nombre dice «avance de carrera» y no «combustible» a propósito, y esa es la
# historia de esta sección.

# %% [markdown]
# ### Por qué no se puede separar el combustible de la evolución de la pista
#
# Dos cosas hacen que las vueltas tardías sean más rápidas: el tanque que se
# vacía y la pista que se va engomando. Dentro de una misma carrera **las dos son
# lineales en el número de vuelta**, así que son indistinguibles.
#
# Lo que las separaría es el largo de la carrera: en la vuelta 30 de una de 44
# quedan 14 vueltas de combustible con la pista al 68% de su evolución, y en la
# vuelta 30 de una de 78 quedan 48 con la pista al 38%.
#
# El primer intento fue meter un efecto fijo por carrera-piloto y regresar contra
# las dos variables juntas. **No funciona, y no falla a los gritos**: devuelve un
# número confiado e imposible. Con el largo de carrera fijo dentro de una
# carrera-piloto, `vueltas_restantes = L − L·fracción`, o sea que los dos
# regresores son afines: su correlación intra-carrera es exactamente −1,000. El
# efecto fijo absorbe `L`, que era justamente la variación que los identificaba.
# El ajuste devolvió **beta = −0,043 s/vuelta** —llevar combustible te haría más
# rápido— y estimaciones por temporada desparramadas de −0,12 a −0,02.
#
# Para medir desgaste la separación **no hace falta**: lo que hay que sacarle al
# tiempo de vuelta es el efecto completo, sea cual sea su causa. Y ese efecto
# combinado sí se identifica, ajustando dentro de cada carrera-piloto la
# pendiente contra el número de vuelta usando las vueltas de goma nueva de tandas
# distintas.
#
# El resultado, sobre **1.627 carreras-piloto**: `beta = 0,056 s/vuelta`
# (p25 0,078, p75 0,036), estable entre 0,047 y 0,062 en las cinco temporadas.
# Los 0,035 que estaban asumidos sacaban apenas el **63%** del efecto.
#
# Se usa un número **global y no por circuito**: las estimaciones por circuito van
# de 0,031 a 0,093, pero correlacionan sólo **0,150** entre eras, así que casi
# toda esa diferencia es ruido. Reproducible con
# `scripts/fit_fuel_effect.py` y `scripts/fit_race_progress.py`.

# %%
print(f"beta en uso: {features.RACE_PROGRESS_S_PER_LAP} s/vuelta")
print("antes:       0.035 s/vuelta (asumido, prestado de la era anterior)")

# %%
fuelled = features.add_fuel_correction(marked)
rep = fuelled[fuelled["is_representative"]]
zand = rep[rep["circuit"] == "Zandvoort"]

fig, axes = plt.subplots(1, 2, sharey=True)
for ax, columna, titulo in (
    (axes[0], "LapTime", "sin corregir"),
    (axes[1], "lap_time_fuel_corrected", "corregido por combustible"),
):
    ax.scatter(zand["LapNumber"], zand[columna], s=1, alpha=0.06, color="#1f77b4")
    tendencia = zand.groupby("LapNumber")[columna].median()
    ax.plot(tendencia.index, tendencia.to_numpy(), color="#d62728", lw=1.4)
    ax.set_title(f"Zandvoort · {titulo}")
    ax.set_xlabel("vuelta de carrera")
    ax.set_ylim(70, 95)
axes[0].set_ylabel("segundos")
plt.tight_layout()
plt.show()

# %%
for columna, etiqueta in (("LapTime", "sin corregir"), ("lap_time_fuel_corrected", "corregido")):
    tendencia = zand.groupby("LapNumber")[columna].median()
    pendiente = np.polyfit(tendencia.index, tendencia.to_numpy(), 1)[0]
    print(f"{etiqueta:12s} pendiente {pendiente:+.4f} s por vuelta de carrera")

print("\ncon los 0,035 asumidos la corregida quedaba en +0,0013 s/vuelta, o sea plana:")
print("esa es la firma de una corrección que se queda corta. Con el beta ajustado")
print("queda claramente positiva, del orden del desgaste medio.")

# %% [markdown]
# ### Qué desbloqueó el ajuste, medido
#
# Dos cosas estaban bloqueadas por esta constante, y una se arregló del todo.
#
# **El diferencial de ritmo entre compuestos.** Comparando dentro del mismo
# piloto y la misma carrera, con goma joven:
#
# | | Con 0,035 | Con 0,056 |
# |---|---|---|
# | medio − duro | **+0,189** | −0,024 |
# | blando − medio | −0,160 | −0,015 |
# | blando − duro | +0,187 | +0,040 |
#
# Con la constante vieja el duro salía sistemáticamente el más rápido de los
# tres, en las cinco temporadas. No era un dato del neumático: el duro se corre
# en la mediana del 61% de la carrera y el medio en el 26%, veinticinco vueltas
# de diferencia, y una corrección que se queda corta le regala esa ventaja al que
# corre más tarde. Con el beta ajustado los tres quedan **a menos de 0,04 s/vuelta
# entre sí, con los cuartiles cruzando el cero**: no hay diferencia de ritmo
# medible entre compuestos secos. Difieren en desgaste y en vida, no en ritmo con
# goma nueva.
#
# **Las ventanas de parada, a medias.** Los autos con ritmo de caída plano o
# negativo —para los que `insights.pit_window` no puede proyectar nada— bajan del
# **42,3% al 36,8%** de las vueltas, y la mediana del ritmo pasa de +0,028 a
# +0,049. En la vuelta 30 de Zandvoort 2026, 13 de 18 autos cronometrados tienen
# ventana proyectable donde antes era cerca de la mitad. El 37% que queda es otra
# causa: la pendiente rodante de cinco vueltas es ruidosa de por sí, con un
# desvío de 0,466 contra 0,127 de lo que realmente pasa (cuaderno 3, §3.4).

# %% [markdown]
# ## 1.5 La fuga de datos que hubo que tapar
#
# `degradation_s` se calcula contra una vuelta de referencia de la propia tanda.
# En la primera versión **el valor de la vuelta actual entraba como predictor de
# lo que pasaba en esa misma vuelta**. Como la vuelta de entrada a boxes no es
# representativa, su degradación quedaba nula, y el modelo aprendía a leer eso en
# vez de aprender estrategia.

# %%
featured = features.add_labels(features.add_degradation(fuelled))
fuga = pd.DataFrame(
    {
        "con degradation_s definida": [
            featured.loc[~featured["boxed"], "degradation_s"].notna().mean(),
            featured.loc[featured["boxed"], "degradation_s"].notna().mean(),
        ]
    },
    index=["vueltas normales", "vueltas de entrada a boxes"],
)
print((fuga * 100).round(1).to_string())
print("\nUna columna presente en casi todas las vueltas de un grupo y en ninguna")
print("del otro no es un predictor: es la etiqueta escrita al revés. La tubería")
print("la desplaza una vuelta antes de usarla para entrenar.")

# %% [markdown]
# ## 1.6 Paradas que no fueron decisiones
#
# Un cambio de gomas con la carrera **detenida por bandera roja** no cuesta los
# ~23 segundos que este proyecto modela: es gratis. Contarlas como estrategia
# enseña que parar a veces no cuesta nada.

# %%
paradas = featured[featured["boxed"] & (featured["LapNumber"] > 1)]
por_anio = paradas.groupby("year")["free_stop"].agg(paradas="size", gratis="mean")
por_anio["gratis %"] = (por_anio["gratis"] * 100).round(1)
print(por_anio[["paradas", "gratis %"]].to_string())

peores = (
    paradas.groupby(["year", "round", "circuit"])["free_stop"]
    .agg(paradas="size", gratis="mean")
    .sort_values("gratis", ascending=False)
    .head(5)
)
peores["gratis %"] = (peores["gratis"] * 100).round(1)
print("\ncarreras con mayor proporción de paradas gratis:")
print(peores[["paradas", "gratis %"]].to_string())

# %% [markdown]
# El caso que obligó a separarlas es Zandvoort 2026: **21 de 22 autos «pararon»
# en la vuelta 2** detrás de una bandera roja. Sin el filtro, esa carrera enseña
# que parar temprano es gratis y frecuente.

# %%
z26 = featured[(featured["year"] == 2026) & (featured["circuit"] == "Zandvoort")]
temprano = z26[z26["boxed"] & (z26["LapNumber"] <= 3)]
print(f"autos que 'pararon' en las tres primeras vueltas: {temprano['Driver'].nunique()}")
print(f"de esas paradas, gratis bajo bandera roja: {int(temprano['free_stop'].sum())} de {len(temprano)}")

# %% [markdown]
# ## 1.7 La lluvia
#
# Una carrera mojada reordena la parrilla por motivos que pertenecen al clima, no
# al trazado ni a la estrategia. Se descarta **entera**, no vuelta por vuelta:
# una pista secándose sigue produciendo adelantamientos y paradas mucho después
# de que dejó de llover.

# %%
lluvia = featured.groupby(["year", "round"])["Rainfall"].mean()
mojadas = lluvia[lluvia > 0.2]
tabla = mojadas.rename("lluvia").to_frame()
tabla["circuito"] = [
    featured[(featured["year"] == y) & (featured["round"] == r)]["circuit"].iloc[0]
    for y, r in mojadas.index
]
tabla["lluvia %"] = (tabla["lluvia"] * 100).round(0)
print(
    f"carreras con lluvia en más del 20% de las vueltas: {len(mojadas)} de "
    f"{featured.groupby(['year', 'round']).ngroups}"
)
print(tabla[["circuito", "lluvia %"]].to_string())

# %% [markdown]
# El efecto sobre una medición concreta —cambios de posición por vuelta en verde,
# en Zandvoort, medido en el cuaderno 2:
#
# | Temporada | Cambios por vuelta |
# |---|---|
# | 2022 seca | 0,302 |
# | **2023 mojada** | **1,121** |
# | 2024 seca | 0,507 |
# | 2025 seca | 0,472 |
# | 2026 seca | 0,727 |
#
# La carrera mojada marca 3,7 veces la seca sobre el mismo asfalto. Con ella
# adentro Zandvoort era el 12.º circuito más difícil de 25; sin ella, el 5.º.
# Una sola carrera movía siete puestos.

# %% [markdown]
# ## 1.8 Las vueltas neutralizadas, y un filtro que resultó redundante
#
# Bajo safety car, VSC o bandera roja el orden cambia por motivos que no son
# carrera, y adelantar está prohibido. Toda medición de ritmo las excluye.
#
# Cuánto pesan, sobre las vueltas cronometradas que no tocan boxes:

# %%
crono = featured[
    featured["LapTime"].notna()
    & ~featured["pit_in"].astype(bool)
    & ~featured["pit_out"].astype(bool)
]
comparacion = crono.groupby("is_neutralised")["LapTime"].agg(
    vueltas="size", mediana="median", media="mean"
)
comparacion.index = ["verde", "neutralizada"]
print(comparacion.round(2).to_string())
delta = comparacion.loc["neutralizada", "mediana"] - comparacion.loc["verde", "mediana"]
print(f"\ndiferencia de mediana: {delta:+.1f} s por vuelta")
print("Dejarlas adentro arrasa con cualquier promedio de ritmo.")

# %% [markdown]
# Ahora lo inesperado. Al escribir este cuaderno la comparación falló porque el
# `groupby` devolvía **un solo grupo**: entre las vueltas representativas no hay
# ni una neutralizada.

# %%
solapamiento = pd.crosstab(
    featured["is_representative"].rename("representativa"),
    featured["is_neutralised"].rename("neutralizada"),
)
print(solapamiento.to_string())
print(
    "\nvueltas representativas Y neutralizadas: "
    f"{int((featured['is_representative'] & featured['is_neutralised']).sum())}"
)

# %% [markdown]
# **El `IsAccurate` de FastF1 ya descarta todas las vueltas neutralizadas.** Los
# dos filtros se solapan por completo, así que para medir ritmo el filtro de
# neutralización no quita nada que el otro no haya quitado ya.
#
# No es motivo para sacarlo. Sigue haciendo falta para las mediciones que **no**
# usan `is_representative` —el conteo de adelantamientos trabaja sobre
# `Position`, no sobre tiempos, y ahí sí hay vueltas neutralizadas que
# descontar— y depender de un efecto lateral de una bandera de otra librería
# sería frágil. Pero conviene saber que en la tubería de ritmo es redundante, en
# vez de atribuirle un efecto que no tiene.

# %% [markdown]
# ## 1.9 El embudo completo

# %%
total = len(featured)
verde_rep = featured["is_representative"] & ~featured["is_neutralised"] & ~featured["red"]
sin_lluvia = ~pd.MultiIndex.from_frame(featured[["year", "round"]]).isin(set(mojadas.index))

embudo = pd.DataFrame(
    [
        ("ingesta cruda", total, "todo lo que devuelve FastF1"),
        ("con LapTime", int(featured["LapTime"].notna().sum()), "descarta vueltas sin cronometrar"),
        (
            "representativas",
            int(featured["is_representative"].sum()),
            "sin boxes, sin borradas, IsAccurate",
        ),
        ("+ sólo verde", int(verde_rep.sum()), "sin SC, VSC ni bandera roja"),
        ("+ sin lluvia", int((verde_rep & sin_lluvia).sum()), "descarta 8 carreras enteras"),
    ],
    columns=["paso", "vueltas", "para qué"],
)
embudo["% del crudo"] = (embudo["vueltas"] / total * 100).round(1)
embudo

# %% [markdown]
# Queda alrededor de **dos tercios de las vueltas crudas** para medir ritmo. El
# tercio restante no se tira: las vueltas de boxes son la etiqueta, y las
# neutralizadas son el objeto de estudio de la mitad del proyecto.
#
# Las mediciones que se apoyan en esta base están en `02-mediciones.ipynb`.
