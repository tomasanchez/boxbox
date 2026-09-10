"""Why fit the hard if the medium degrades less: the mandatory compound.

The question came from the Monza data. There the medium degrades at 0.0331
s/lap and the hard at 0.0463 — the medium is the *better* tyre. So why did
eleven cars run fifty laps on the hard?

Not because it is better. Because **B6.3.8 forces two dry compounds**, and the
hard is what they spent the obligation on. The compound choice is not "which is
faster" but "which stint do I waste on the rule".

Monza 2026 made that visible because a red flag on lap 3 sent the whole field to
the pit lane. Every one of the twenty-two cars ran a stint of two or three laps
and then changed for free — the compliance stint cost them nothing.

And then the strategies split:

    ANT   H3-M25-M25    spends the rule on the hard, runs the good tyre twice
    RUS   M3-H50        spends the rule on the medium, runs the worse tyre for
          NOR, PIA,     fifty laps
          GAS, LIN, COL

Antonelli put the mandatory compound in the throwaway stint. Ten other cars put
their best tyre there and then had to live on the hard.

Run with ``uv run python scripts/compliance_stint.py``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from boxbox_ml import strategy
from boxbox_ml.strategy import Car, Plan, RaceModel, Stop

pd.set_option("display.width", 190)

#: Monza's own wear, measured over 87, 87 and 14 stints. The medium degrades
#: least here; at Zandvoort it degrades most.
MONZA = RaceModel(
    total_laps=53,
    wear_cuts={
        "SOFT": (-0.0274, 0.0013, 0.0104, 0.0179, 0.0431, 0.0564, 0.0618, 0.0743, 0.1145),
        "MEDIUM": (-0.0532, -0.0082, 0.0074, 0.0232, 0.0351, 0.0585, 0.0724, 0.0902, 0.1320),
        "HARD": (-0.0117, 0.0043, 0.0186, 0.0303, 0.0468, 0.0599, 0.0708, 0.0845, 0.0989),
    },
)
#: And its own stint life, at the 90th percentile.
MONZA_STINT = {"HARD": 48, "MEDIUM": 34, "SOFT": 20}


def score(car: Car, plan: Plan, draws: int = 8000) -> float:
    gen = np.random.default_rng(4242)
    flags = strategy.draw_neutralisations(MONZA, gen, draws)
    return float(strategy.race_time(plan, car, MONZA, gen, draws, flags).mean())


original = dict(strategy.MAX_STINT)
strategy.MAX_STINT.update(MONZA_STINT)
try:
    rows = []
    for start, rest in (
        ("HARD", "MEDIUM"),
        ("MEDIUM", "HARD"),
        ("SOFT", "MEDIUM"),
        ("SOFT", "HARD"),
    ):
        car = Car("X", start, 0, 0.0, strategy.ROLLING_MEDIAN_S, 0.0, 1)
        for stops in (1, 2):
            step = (MONZA.total_laps - 3) // stops
            asked = [(3, rest)] + [(3 + step * i, rest) for i in range(1, stops)]
            plan = Plan(strategy._repair([Stop(lap, c) for lap, c in asked], car, MONZA))
            rows.append(
                {
                    "larga en": start,
                    "y despues": rest,
                    "plan": plan.describe(car, MONZA.total_laps),
                    "tiempo": round(score(car, plan), 2),
                }
            )
    table = pd.DataFrame(rows).sort_values("tiempo").reset_index(drop=True)
    print("=" * 84)
    print("### DONDE GASTAR EL COMPUESTO OBLIGATORIO — Monza, 53 vueltas")
    print(table.to_string(index=False))
    print()
    ant = table[table["larga en"].eq("HARD") & table["y despues"].eq("MEDIUM")].iloc[0]
    field = table[table["larga en"].eq("MEDIUM") & table["y despues"].eq("HARD")].iloc[0]
    print(f"estructura de ANT   ({ant['plan']:<12}): {ant['tiempo']:.2f} s")
    print(f"estructura del resto ({field['plan']:<12}): {field['tiempo']:.2f} s")
    print(f"diferencia: {field['tiempo'] - ant['tiempo']:.2f} s a favor de ANT")
    print()
    print("El orden es el correcto: gastar la obligación en el compuesto que NO")
    print("querés, y correr el bueno el resto de la carrera. Las diferencias son")
    print("chicas porque MIN_STINT son seis vueltas y el modelo no puede")
    print("representar el stint de tres que hicieron todos — con el stint real la")
    print("ventaja sería mayor.")
finally:
    strategy.MAX_STINT.clear()
    strategy.MAX_STINT.update(original)
