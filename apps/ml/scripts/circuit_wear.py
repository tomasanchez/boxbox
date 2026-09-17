"""Desgaste por circuito: cuánto de lo medido en un circuito sirve para el próximo.

El simulador corre todos los circuitos con los números de Zandvoort. Monza y
Madrid mostraron, cada uno a su manera, que eso da la respuesta equivocada.

**Una advertencia sobre las cifras de Monza que circulan en el informe.** Ahí se
dice que en Monza el medio degrada 0,0331 s/vuelta y el duro 0,0463, o sea que el
medio es el mejor neumático del circuito. Ese número sale de **todas las eras
juntas**. Restringido a 2026 el orden se da vuelta: duro 0,0306 contra medio
0,0362, con apenas trece y doce tandas detrás. La explicación del compuesto
obligatorio (B6.3.8) no depende de cuál degrada menos, así que sigue en pie —
pero la premisa "el medio es el mejor neumático de Monza" es dependiente de la
era, y esta tabla usa 2026, que es lo que corresponde para simular 2026.

La tentación es usar el número medido de cada circuito y listo. Pero este proyecto
viene midiendo que casi nada por circuito replica: dificultad para adelantar 0,21,
avance de carrera 0,15, tráfico -0,04. Así que antes de creerle hay que medir
cuánto de lo medido es señal, y encoger el resto hacia el promedio:

    encogido = promedio + r * (circuito - promedio)

**Lo importante que salió de acá es que son dos preguntas distintas, con
respuestas opuestas**, y confundirlas es lo que hacía parecer que el desgaste por
circuito era un problema difícil.

*¿Sirve lo medido en un circuito para predecirlo bajo OTRO reglamento?* Casi
nada: r = 0,143 sobre 27 pares. Y encogerlo tampoco salva — predecir el 2026 de
un circuito con lo de antes da 3,4% más error que usar el promedio de la
temporada. Para un circuito sin datos del año en curso, el promedio es la
respuesta correcta, que es exactamente lo que se hizo con Madrid.

*¿Es confiable lo medido en un circuito DENTRO de la temporada en curso?* Mucho:
partiendo las tandas de cada circuito en dos mitades al azar, las mitades
correlacionan 0,81, que corregido por Spearman-Brown da **0,89** para la medición
completa — 0,95 en el medio y 0,96 en el duro.

Y ésa es la pregunta que el simulador necesita, porque cuando corre Monza 2026
tiene los datos de Monza 2026 y no hay nada que transferir. La respuesta es que
hay que creerle casi entero.

**Las eras se comparan en desviación, no en nivel.** 2026 cambió reglamento,
autos y gomas, y el desgaste medio de la temporada se movió. Comparar niveles
crudos mide ese corrimiento y no la personalidad del circuito.

Correr con ``uv run python scripts/circuit_wear.py``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from boxbox_ml import cache, features, neutralisation, track_status

pd.set_option("display.width", 200)
SEP = "=" * 88

#: Tandas mínimas para que la mediana de un circuito y compuesto signifique algo.
MIN_STINTS = 6

DRY = ("SOFT", "MEDIUM", "HARD")


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


stints = load_stints()
stints["era"] = np.where(stints["year"] >= 2026, "2026", "previo")

print(SEP)
print("### 1. LO MEDIDO, POR ERA")
print()
summary = stints.groupby(["era", "compound"])["slope"].agg(["median", "size"]).round(4)
print(summary.to_string())
print()
print("  El nivel se movió entre eras, que es exactamente por qué las")
print("  comparaciones de abajo son en desviación y no en nivel crudo.")

# Una mediana por circuito, compuesto y era, con suficientes tandas detrás.
grouped = stints.groupby(["era", "circuit", "compound"])["slope"].agg(["median", "size"])
grouped = grouped[grouped["size"] >= MIN_STINTS].reset_index()

# Desviación respecto del promedio de su propia era y compuesto: la personalidad
# del circuito, con el corrimiento de era descontado.
era_level = grouped.groupby(["era", "compound"])["median"].transform("median")
grouped["deviation"] = grouped["median"] - era_level

pivot = grouped.pivot_table(index=["circuit", "compound"], columns="era", values="deviation")
paired = pivot.dropna().reset_index()

print("\n" + SEP)
print("### 2. ¿LA PERSONALIDAD DEL CIRCUITO SOBREVIVE AL CAMBIO DE ERA?")
print()
print(f"  {len(paired)} pares circuito-compuesto con datos en las dos eras")
rows = []
for compound in DRY:
    sub = paired[paired["compound"] == compound]
    if len(sub) < 4:
        rows.append({"compuesto": compound, "n": len(sub), "r": None})
        continue
    rows.append(
        {
            "compuesto": compound,
            "n": len(sub),
            "r": round(float(sub["previo"].corr(sub["2026"])), 3),
        }
    )
overall = float(paired["previo"].corr(paired["2026"]))
rows.append({"compuesto": "TODOS", "n": len(paired), "r": round(overall, 3)})
print(pd.DataFrame(rows).to_string(index=False))
print()
print("  Ese r es el factor de encogimiento. Es lo que hay que creerle a la")
print("  medición de un circuito, y el resto va al promedio.")

ERA_TRANSFER = max(0.0, min(1.0, overall))
print()
print("  OJO: esto responde una pregunta, y no es la que el simulador necesita.")
print("  Mide si la personalidad del circuito cruza un cambio de REGLAMENTO. Sirve")
print("  para un circuito sin datos de 2026. Pero cuando el simulador corre Monza")
print("  2026 tiene los datos de Monza 2026, y ahí no hay que transferir nada: hay")
print("  que saber si esa medición es señal o ruido. Eso es lo de abajo.")

print("\n" + SEP)
print("### 2b. DENTRO DE 2026: ¿LA MEDICION DE UN CIRCUITO ES SEÑAL O RUIDO?")
print("Se parten las tandas de cada circuito en dos mitades al azar y se mira si")
print("las dos mitades coinciden. Corregido por Spearman-Brown, porque cada mitad")
print("tiene la mitad de los datos que tendría la medición completa.")
print()
generator = np.random.default_rng(11)
halves = []
for (circuit, compound), group in stints[stints["era"] == "2026"].groupby(["circuit", "compound"]):
    if len(group) < 2 * MIN_STINTS:
        continue
    shuffled = group.sample(frac=1.0, random_state=int(generator.integers(0, 10_000)))
    first, second = np.array_split(shuffled["slope"].to_numpy(dtype=float), 2)
    halves.append(
        {
            "circuit": circuit,
            "compound": compound,
            "a": float(np.median(first)),
            "b": float(np.median(second)),
        }
    )
split = pd.DataFrame(halves)
rows = []
for compound in (*DRY, "TODOS"):
    sub = split if compound == "TODOS" else split[split["compound"] == compound]
    if len(sub) < 4:
        rows.append({"compuesto": compound, "n": len(sub), "media mitad": None, "completa": None})
        continue
    # Dentro de cada compuesto, correlación entre las dos mitades.
    if compound == "TODOS":
        centred = sub.copy()
        for _name, block in sub.groupby("compound"):
            centred.loc[block.index, "a"] = block["a"] - block["a"].median()
            centred.loc[block.index, "b"] = block["b"] - block["b"].median()
        half_r = float(centred["a"].corr(centred["b"]))
    else:
        half_r = float(sub["a"].corr(sub["b"]))
    full = 2 * half_r / (1 + half_r) if half_r > -1 else 0.0
    rows.append(
        {
            "compuesto": compound,
            "n": len(sub),
            "media mitad": round(half_r, 3),
            "completa": round(full, 3),
        }
    )
print(pd.DataFrame(rows).to_string(index=False))
split_full = next(r["completa"] for r in rows if r["compuesto"] == "TODOS")
print()
print("  'completa' es la confiabilidad de la medición tal como el simulador la")
print("  usaría. Ése es el factor de encogimiento correcto para un circuito del")
print("  que SÍ hay datos de la temporada en curso.")

RELIABILITY = max(0.0, min(1.0, float(split_full)))

print("\n" + SEP)
print("### 3. ¿ENCOGER LE GANA AL PROMEDIO? (predecir 2026 con lo previo)")
print()
errors = {"global": [], "crudo": [], "encogido": []}
for _, row in paired.iterrows():
    truth = float(row["2026"])
    measured = float(row["previo"])
    errors["global"].append(abs(0.0 - truth))  # el promedio es desviación cero
    errors["crudo"].append(abs(measured - truth))
    errors["encogido"].append(abs(ERA_TRANSFER * measured - truth))
table = pd.DataFrame(
    [
        {
            "método": name,
            "error medio": round(float(np.mean(values)), 4),
            "mejora vs global": (
                "—"
                if name == "global"
                else f"{100 * (1 - np.mean(values) / np.mean(errors['global'])):+.1f}%"
            ),
        }
        for name, values in errors.items()
    ]
)
print(table.to_string(index=False))
print()
print("  'global' = suponer que todo circuito desgasta como el promedio, que es")
print("  lo que el simulador hace hoy. 'crudo' = creerle entero a la medición.")

# ------------------------------------------------------- 4. la tabla resultante

print("\n" + SEP)
print("### 4. LA TABLA QUE ENTRA AL SIMULADOR")
print()
print("Desviación encogida respecto del promedio, en s/vuelta. Positivo = el")
print("circuito castiga más la goma que un circuito promedio.")
print()
recent = grouped[grouped["era"] == "2026"]
shrunk = recent.copy()
shrunk["encogido"] = RELIABILITY * shrunk["deviation"]
wide = shrunk.pivot_table(index="circuit", columns="compound", values="encogido").round(4)
print(wide.sort_values("MEDIUM").to_string())

# **Este script ya no escribe la tabla que consume el simulador.** La escribe
# ``scripts/wear_shrinkage.py``, que encoge cada celda según cuántas tandas la
# respaldan en vez de aplicar un factor único. El factor único que salía de acá le
# daba el mismo crédito a Silverstone en blando —UNA tanda— que a Spielberg en
# medio, con veintinueve. Lo que queda acá es el análisis entre eras, que sigue
# valiendo y que la otra no repite.
print()
print("  NOTA: la tabla que consume RaceModel.for_circuit() la escribe ahora")
print("  scripts/wear_shrinkage.py, con encogimiento que depende de n.")

# ------------------------------------------------------------- 5. ¿y cambia algo?

print("\n" + SEP)
print("### 5. ¿CAMBIA LA RECOMENDACION?")
print("La misma búsqueda, con los defaults contra la tabla que escribe wear_shrinkage.")
print()

from boxbox_ml import strategy  # noqa: E402 - después de escribir la tabla que lee
from boxbox_ml.strategy import Car, Objective, RaceModel, optimise  # noqa: E402

LAPS = {
    "Zandvoort": 72,
    "Monza": 53,
    "Barcelona": 66,
    "Budapest": 70,
    "Spielberg": 71,
    "Monaco": 78,
}
SEARCH = dict(population=40, generations=25, draws=1200, seed=11)

rows = []
for circuit, laps in LAPS.items():
    generic = RaceModel(total_laps=laps)
    own = RaceModel.for_circuit(circuit, total_laps=laps)
    for compound in ("MEDIUM", "HARD"):
        car = Car("X", compound, 0, 0.0, strategy.ROLLING_MEDIAN_S, 0.0, 1)
        before = optimise(car, [], [], generic, objective=Objective.TIME, **SEARCH)
        after = optimise(car, [], [], own, objective=Objective.TIME, **SEARCH)
        rows.append(
            {
                "circuito": circuit,
                "larga": compound,
                "con Zandvoort": f"{before.best.count}p {before.best.describe(car, laps)}",
                "con lo propio": f"{after.best.count}p {after.best.describe(car, laps)}",
                "cambia": "SI" if before.best.stops != after.best.stops else "-",
                "paradas": ("SI" if before.best.count != after.best.count else "-"),
            }
        )
impact = pd.DataFrame(rows)
print(impact.to_string(index=False))
print()
print(f"  el plan cambia en {(impact['cambia'] == 'SI').sum()} de {len(impact)} casos")
print(f"  la CANTIDAD de paradas cambia en {(impact['paradas'] == 'SI').sum()} de {len(impact)}")
print()
print("  Barcelona es el caso grande: de una parada a tres. Su medio degrada")
print("  0,19 s/vuelta, tres veces el de Zandvoort, y correrlo con los números")
print("  prestados daba una respuesta que ningún equipo habría seguido.")
