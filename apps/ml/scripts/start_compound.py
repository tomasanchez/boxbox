"""Con qué compuesto larga la parrilla, y por qué no es el mismo para todos.

``prerace_export.py`` le daba medio a los veintidós y lo declaraba como supuesto:
«antes de la carrera no se sabe con qué larga cada uno, y darles el mismo deja
que lo único que los separe sea el puesto y el ritmo, que sí están medidos». El
argumento es razonable y el dato que le falta es éste: **una grilla de un solo
compuesto no existe**. En las catorce fechas de 2026 conviven entre uno y tres
compuestos de salida por carrera, y el reparto depende de dónde larga el auto.

Lo que se mide acá es el compuesto del primer stint de cada piloto contra su
puesto de largada. Es un dato del domingo a la tarde, así que no entra a ninguna
predicción como insumo del auto que se está proyectando — entra como la
distribución de la que se **sortea** el compuesto de los rivales, que es lo mismo
que ya se hace con sus planes.

Dos recortes, los dos declarados. Se descartan los pilotos que largaron con
intermedio o con lluvia extrema: el modelo de estrategia es de seco y no tiene
nada que decir de ellos. Y se descartan los que no tienen puesto de grilla, que
es el pit lane.

Correr con ``uv run python scripts/start_compound.py``.
"""

from __future__ import annotations

import warnings

import fastf1
import pandas as pd

from boxbox_ml import cache, strategy

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)
SEP = "=" * 88

#: Rondas de 2026 ya corridas, las mismas que usa ``quali_to_race_pace.py``.
ROUNDS = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14)

#: Los cortes de grilla, por el último puesto de cada banda. Cuatro y no veintidós
#: porque veintidós bandas de catorce carreras dan catorce observaciones cada una,
#: que no es una distribución sino un ruido; y cuatro y no dos porque el salto que
#: importa está en el fondo y una mediana partida al medio lo promediaría con la
#: zona media. Son los mismos cortes que espera
#: ``prerace_export.START_COMPOUND_SHARES``.
GRID_BANDS = ((5, "P1-5"), (10, "P6-10"), (15, "P11-15"), (99, "P16-22"))

cache.enable()


def band(grid_position: int) -> str:
    """En qué banda de la grilla cae un puesto de largada."""
    return next(name for last, name in GRID_BANDS if grid_position <= last)


def first_stints(year: int, rnd: int) -> list[dict]:
    """Con qué largó cada piloto de una carrera, y desde dónde.

    Args:
        year: Temporada.
        rnd: Número de fecha.

    Returns:
        Una fila por piloto con puesto de grilla y compuesto de salida. El stint
        de salida es el de número más bajo y no el primero de la tabla: un piloto
        cuyas primeras vueltas no quedaron registradas arrancaría en otro.
    """
    session = fastf1.get_session(year, rnd, "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    laps, results = session.laps, session.results
    if laps.empty or results.empty:
        return []

    grid = dict(zip(results["Abbreviation"], results["GridPosition"], strict=True))
    opening = laps[laps["Stint"].eq(laps.groupby("Driver")["Stint"].transform("min"))]
    return [
        {
            "round": rnd,
            "driver": driver,
            "grid": grid.get(driver, 0),
            "compound": stint["Compound"].iloc[0],
        }
        for driver, stint in opening.groupby("Driver")
    ]


records: list[dict] = []
for rnd in ROUNDS:
    try:
        records.extend(first_stints(2026, rnd))
    except Exception as error:  # noqa: BLE001 - una ronda que falla no es fatal
        print(f"  ronda {rnd}: no se pudo cargar ({type(error).__name__})")

raw = pd.DataFrame(records)
data = raw[raw["compound"].isin(strategy.DRY) & raw["grid"].gt(0)].copy()
data["grid"] = data["grid"].astype(int)
data["band"] = data["grid"].map(band)

print(SEP)
print("### CON QUE LARGA LA PARRILLA")
print()
print(f"  {len(raw)} pilotos-carrera sobre {raw['round'].nunique()} carreras de 2026")
print(f"  {len(data)} después de sacar los que no largaron en seco o desde la grilla:")
print(f"  {raw['compound'].value_counts().to_dict()}")
print()
print("  reparto sobre toda la parrilla, sin mirar desde dónde larga:")
print(f"  {data['compound'].value_counts(normalize=True).round(3).to_dict()}")

print("\n" + SEP)
print("### UNA GRILLA DE UN SOLO COMPUESTO NO EXISTE")
print("Es lo que el supuesto anterior describía, y no se parece a ninguna carrera.")
print()
distintos = data.groupby("round")["compound"].nunique()
print(f"  compuestos de salida distintos por carrera: {distintos.to_dict()}")
print(f"  mediana {distintos.median():.1f}, rango {distintos.min()} a {distintos.max()}")
print(f"  carreras con un solo compuesto en toda la grilla: {int(distintos.eq(1).sum())}")

print("\n" + SEP)
print("### Y DEPENDE DE DONDE LARGA EL AUTO")
order = [name for _, name in GRID_BANDS]
table = (
    data.groupby("band")["compound"]
    .value_counts(normalize=True)
    .unstack(fill_value=0.0)
    .reindex(order)
    .reindex(columns=list(strategy.DRY), fill_value=0.0)
)
table.insert(0, "n", data.groupby("band").size().reindex(order))
print(table.round(3).to_string())
print()
print("  El frente converge al medio y el fondo se dispersa. La lectura es la")
print("  misma que la del apetito de riesgo: el que larga adelante tiene algo que")
print("  proteger y hace lo que hacen todos, y el que larga atrás no tiene nada")
print("  que perder y se desmarca — para arriba con el blando, que le da una")
print("  largada, o para abajo con el duro, que le compra una parada menos.")

print("\n" + SEP)
print("### LA CONSTANTE QUE ENTRA AL EXPORT")
print()
print("START_COMPOUND_SHARES = {")
for name in order:
    row = ", ".join(f'"{c}": {table.loc[name, c]:.3f}' for c in strategy.DRY)
    print(f'    "{name}": {{{row}}},')
print("}")
print()
print("  Uso: el compuesto de salida de cada RIVAL se sortea de la fila que le")
print("  toca por su puesto de grilla. El del auto focal no se sortea: se corre")
print("  la búsqueda con los tres y se elige, que es lo que una recomendación")
print("  pre-carrera tiene que contestar.")
