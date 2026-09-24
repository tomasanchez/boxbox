"""¿Cuántos autos terminan doblados, en la realidad y en el modelo?

Una carrera no termina cuando el primero cruza la meta: termina cuando cada auto
cruza **después** de que el primero lo hizo. El que va doblado nunca corre la
última vuelta. El simulador corría la distancia completa para los veintidós, y
:func:`boxbox_ml.strategy.chequered` lo corrige.

Buscando eso apareció algo más grande, y este script lo deja medido.

## El modelo dobla al doble de autos que la realidad

    vueltas abajo    modelo    real
        0             45,2%    71,6%
        1             29,1%    23,3%
        2             22,9%     3,4%
        3              2,8%     0,7%

Al menos una vuelta abajo: **54,8% contra 28,4%**. Y el cajón de dos abajo es
siete veces más grande de lo que debería.

## Por qué

:func:`boxbox_ml.strategy.pace_from_qualifying` toma el hueco de clasificación y
lo extrapola como un déficit **constante por vuelta** durante toda la carrera. El
último de la grilla queda 2,87 s/vuelta más lento, que sobre 71 vueltas son 223
segundos, que a 77,8 s/vuelta son casi tres vueltas.

En una carrera real el fondo de parrilla no pierde su déficit de clasificación
todas las vueltas: corre en aire limpio, administra, y el que lo dobla pierde
tiempo en doblarlo. El factor 0,835 se validó con r=0,880 sobre 277
piloto-carreras comparando hueco de quali contra ritmo de carrera, y eso es
autoconsistente — lo que nunca se chequeó fue **la consecuencia**, que es cuánta
gente termina doblada.

No se corrige acá: tocar el ritmo mueve cada cifra publicada del informe. Queda
medido para que la decisión se tome con el tamaño a la vista.

Correr con ``uv run python scripts/laps_down.py``.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from boxbox_ml import cache, neutralisation
from boxbox_ml import strategy as st
from boxbox_ml.strategy import Car, Plan, RaceModel, Stop

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)
SEP = "=" * 88
EXPORT = Path(__file__).resolve().parents[3] / "docs" / "research" / "prerace-zandvoort.json"

#: Menos de esta fracción de la distancia del ganador no es un clasificado, es
#: un abandono, y contarlo como "muchas vueltas abajo" ensuciaría el reparto.
CLASSIFIED = 0.9

frame = pd.read_parquet(cache.cache_dir().parent / "laps_overtaking.parquet")
frame["circuit"] = frame["circuit"].map(lambda c: neutralisation.CIRCUIT_ALIASES.get(c, c))
frame["LapNumber"] = frame["LapNumber"].astype(int)

rows = []
for _keys, race in frame.groupby(["year", "round"]):
    last = race.groupby("Driver")["LapNumber"].max()
    winner = int(last.max())
    for _driver, done in last.items():
        if done < CLASSIFIED * winner:
            continue
        rows.append(winner - int(done))
real = pd.Series(rows)

print(SEP)
print("### 1. LA REALIDAD")
print()
print(f"  {len(real)} autos clasificados en {frame.groupby(['year', 'round']).ngroups} carreras")
print()
observed = real.value_counts(normalize=True).sort_index()
for key in sorted(observed.index)[:5]:
    print(f"  {key} abajo  {100 * observed[key]:5.1f}%  {'#' * int(round(observed[key] * 50))}")
print(f"  al menos una abajo: {100 * (real >= 1).mean():.1f}%   máximo {real.max()}")

export = json.loads(EXPORT.read_text(encoding="utf-8"))
laps = int(export["race"]["total_laps"])
model = RaceModel.for_circuit("Zandvoort", total_laps=laps)
draws = 2000
rng = np.random.default_rng(11)
flags = st.draw_neutralisations(model, rng, draws)
cars, plans = [], []
for entry in export["cars"]:
    cars.append(
        Car(
            entry["code"],
            entry["start_compound"],
            0,
            0.0,
            st.ROLLING_MEDIAN_S,
            0.0,
            1,
            pace_s=entry["pace_s"],
            team=entry["team"],
        )
    )
    plans.append(Plan(tuple(Stop(int(s["lap"]), s["compound"]) for s in entry["stops"])))
field = np.stack(
    [
        st.race_trace(p, c, model, np.random.default_rng(7), draws, flags)
        for c, p in zip(cars, plans, strict=True)
    ]
)
done, _times = st.chequered(field, model)
down = (field.shape[1] - 1) - done

print("\n" + SEP)
print("### 2. EL MODELO, Y LA COMPARACION")
print()
print(f"  {'abajo':>6s} {'modelo':>8s} {'real':>8s}")
share = np.bincount(down.ravel(), minlength=5) / down.size
for key in range(5):
    print(f"  {key:6d} {100 * share[key]:7.1f}% {100 * observed.get(key, 0.0):7.1f}%")
print()
mine, theirs = 100 * (down >= 1).mean(), 100 * (real >= 1).mean()
print(f"  al menos una abajo: modelo {mine:.1f}%, real {theirs:.1f}%")
print()
print("  El modelo dobla al doble de autos, y el cajón de DOS abajo es siete")
print("  veces más grande. La causa es `pace_from_qualifying`: extrapola el hueco")
print("  de clasificación como un déficit constante por vuelta durante toda la")
print("  carrera, y el último de la grilla termina casi tres vueltas abajo.")

print("\n" + SEP)
print("### 3. DE DONDE SALE, AUTO POR AUTO")
print()
print(f"  {'auto':5s} {'s/vuelta':>9s} {'s al final':>11s} {'vueltas abajo':>14s}")
for index, car in enumerate(cars):
    if index % 4 and index != len(cars) - 1:
        continue
    behind = float(np.median(field[index, -1] - field[:, -1, :].min(axis=0)))
    print(f"  {car.code:5s} {car.pace_s:9.2f} {behind:11.1f} {int(np.median(down[index])):14d}")
print()
print(f"  A {model.green_lap_s:.1f} s la vuelta, 223 segundos son casi tres vueltas.")
print("  La validación del factor 0,835 (r=0,880) comparó hueco de quali contra")
print("  ritmo de carrera, que es autoconsistente. Lo que nunca se chequeó fue la")
print("  CONSECUENCIA: cuánta gente termina doblada.")
