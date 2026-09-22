"""¿La ventana de parada depende de qué medición de Zandvoort se use?

En el repositorio conviven dos mediciones del desgaste de Zandvoort y difieren
mucho: la que usa el simulador se queda con 2026 y la de la vista de mitad de
carrera junta todas las temporadas. En el medio difieren un 49,5%. ADR-009 ya
decidió que cada vista sortee con la suya y que la diferencia quede declarada;
lo que nunca se midió es **cuánto le importa eso a la ventana**, que es una
cifra que la pantalla publica.

La respuesta es que casi nada, y no era obvio.

    corrimiento del centro   mediana +0,0 vueltas   rango -1 a +2
    cambio de ancho          mediana +0,0 vueltas   rango -1 a +5

Doce de los veintidós dan idénticos. Cambiar el desgaste un 11% en blando, un
14% en duro y un 49,5% en medio mueve la ventana de la mitad de la grilla cero
vueltas.

El motivo es que la ventana es una comparación **entre vueltas del mismo
modelo**, no un valor absoluto: escalar el desgaste corre un poco el óptimo pero
deja la forma de la curva casi igual. Y se puntúa en puestos, que son discretos
y gruesos, así que hace falta bastante tiempo para mover uno.

**La excepción es el medio, y es la que había que vigilar.** STR es el único auto
que larga en medio, y es el que más se mueve: el centro se corre 2,5 vueltas y el
ancho pasa de 13 a 18. Es el compuesto con el 49,5% de diferencia y con la celda
más fina del circuito, once tandas. Con un solo auto no se puede decir más que
eso, y queda dicho.

Correr con uv run python scripts/window_sensitivity.py.
"""

import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from boxbox_ml import strategy as st
from boxbox_ml.strategy import Car, Plan, RaceModel, Stop

# Los cortes de TODAS las temporadas, tal como los emite
# scripts/zandvoort_distributions.py y los lleva apps/web/src/tyres.ts.
ALL_ERAS = {
    "SOFT": (-0.163, -0.0003, 0.032, 0.0394, 0.0611, 0.0759, 0.0979, 0.1085, 0.1592),
    "MEDIUM": (-0.0063, 0.0322, 0.0421, 0.0547, 0.0625, 0.0749, 0.0885, 0.101, 0.1277),
    "HARD": (-0.0143, 0.0219, 0.0342, 0.0427, 0.0554, 0.0646, 0.0708, 0.0847, 0.1176),
}

EXPORT = Path(__file__).resolve().parents[3] / "docs" / "research" / "prerace-zandvoort.json"
export = json.loads(EXPORT.read_text(encoding="utf-8"))
laps = int(export["race"]["total_laps"])
only26 = RaceModel.for_circuit("Zandvoort", total_laps=laps)
cuts = dict(only26.wear_cuts)
cuts.update({k: tuple(v) for k, v in ALL_ERAS.items()})
alleras = replace(only26, wear_cuts=cuts)

mid = len(st.CUT_AT) // 2
print("desgaste mediano, s/vuelta:")
for c in ("SOFT", "MEDIUM", "HARD"):
    a, b = only26.wear_cuts[c][mid], alleras.wear_cuts[c][mid]
    print(f"  {c:7s} 2026 {a:.4f}   todas {b:.4f}   dif {100 * (a - b) / b:+6.1f}%")
print()

D = 1200
rng = np.random.default_rng(11)
flags = st.draw_neutralisations(only26, rng, D)
cars, plans = [], []
for e in export["cars"]:
    cars.append(
        Car(
            e["code"],
            e["start_compound"],
            0,
            0.0,
            st.ROLLING_MEDIAN_S,
            0.0,
            1,
            pace_s=e["pace_s"],
            team=e["team"],
        )
    )
    plans.append(Plan(tuple(Stop(int(s["lap"]), s["compound"]) for s in e["stops"])))

print(
    f"{'auto':5s} {'larga':7s} {'2026':>12s} {'anc':>4s}"
    f"  {'todas':>12s} {'anc':>4s}  {'centro':>7s}"
)
shifts, widths = [], []
for who, focal in enumerate(cars):
    rivals = [c for i, c in enumerate(cars) if i != who]
    rp = [p for i, p in enumerate(plans) if i != who]
    out = {}
    for label, m in (("2026", only26), ("todas", alleras)):
        rt = np.stack(
            [
                st.race_trace(plan, rival, m, np.random.default_rng(7), D, flags)
                for rival, plan in zip(rivals, rp, strict=True)
            ]
        )
        out[label] = st.stop_window(plans[who], focal, rivals, rt, m, rng, D, flags)
    a, b = out["2026"], out["todas"]
    if a is None or b is None:
        print(f"{focal.code:5s} {focal.compound:7s} {str(a):>12s}      {str(b):>12s}")
        continue
    ca, cb = (a[0] + a[1]) / 2, (b[0] + b[1]) / 2
    shifts.append(cb - ca)
    widths.append((b[1] - b[0] + 1) - (a[1] - a[0] + 1))
    print(
        f"{focal.code:5s} {focal.compound:7s} {str(a):>12s} {a[1] - a[0] + 1:4d}"
        f"  {str(b):>12s} {b[1] - b[0] + 1:4d}  {cb - ca:+7.1f}"
    )
print()
print(
    f"corrimiento del centro: mediana {np.median(shifts):+.1f} vueltas, "
    f"rango {min(shifts):+.0f} a {max(shifts):+.0f}"
)
print(
    f"cambio de ancho:        mediana {np.median(widths):+.1f} vueltas, "
    f"rango {min(widths):+.0f} a {max(widths):+.0f}"
)
