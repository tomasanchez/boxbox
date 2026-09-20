"""Monza 2026 against the model: what it would have said, and what happened.

Antonelli started nineteenth on the hard, pitted twice, and won on mediums. The
model, asked before the race, recommends one stop onto the hard for a car
starting on hards. It was wrong, and *why* it was wrong is the whole point.

Monza was a race where **almost nobody paid for a pit stop**. A red flag on lap 3
sent all twenty-two cars to the pit lane for a free tyre change, and a VSC on
laps 27-29 made the second stop cheap for the ten cars that took one. 90.6% of
the strategic stops in that race happened under a neutralisation, against the
23% measured across 103 races.

The whole model is built around a stop costing 22.6 seconds at the median. At Monza that price
was paid by hardly anyone, and the optimum flipped: with free stops, three are
better than two and two are better than one.

**One limitation this exposes.** ``MIN_STINT`` is six laps, so the repair rules
cannot even represent a stop on lap 3 — the reconstruction of Antonelli's race
below comes out as H6-M21-M25 rather than H3-M25-M25. A red-flag stop on the
opening laps is a real and common event that the search is not allowed to
propose.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from boxbox_ml import strategy
from boxbox_ml.strategy import Car, Objective, Plan, RaceModel, Stop, optimise

pd.set_option("display.width", 200)

# Monza is 53 laps, not Zandvoort's 72.
MONZA = RaceModel(total_laps=53)
# La parada gratis: con la carrera detenida no cuesta posición. Nueve cortes
# planos porque eso es lo que `RaceModel` espera; que sean todos casi cero es el
# punto, no una distribución medida.
_FREE_CUTS = (0.0,) * 8 + (0.1,)
FREE = RaceModel(total_laps=53, pit_loss_green=_FREE_CUTS, pit_loss_sc=_FREE_CUTS)
SEP = "=" * 88

ant = Car("ANT", "HARD", 0, 0.0, strategy.ROLLING_MEDIAN_S, 0.0, 1)


def plan_of(*stops: tuple[int, str]) -> Plan:
    return Plan(strategy._repair([Stop(lap, comp) for lap, comp in stops], ant, MONZA))


def score(plan: Plan, model: RaceModel, draws: int = 8000) -> float:
    gen = np.random.default_rng(4242)
    flags = strategy.draw_neutralisations(model, gen, draws)
    return float(strategy.race_time(plan, ant, model, gen, draws, flags).mean())


print(SEP)
print("### LO QUE EL MODELO HABRIA RECOMENDADO")
found = optimise(
    ant, [], [], MONZA, objective=Objective.TIME, population=40, generations=25, draws=1200, seed=11
)
print(f"  plan:     {found.best.describe(ant, MONZA.total_laps)}")
print(f"  paradas:  {found.best.count}")
spread = " ".join(f"{k}:{v:.2f}" for k, v in found.stop_distribution.items())
print(f"  confianza: {spread}")

print("\n" + SEP)
print("### LO QUE ANT HIZO DE VERDAD")
real = plan_of((3, "MEDIUM"), (28, "MEDIUM"))
print(f"  plan:     {real.describe(ant, MONZA.total_laps)}")
print("  parada 1: vuelta 3, BANDERA ROJA  -> gratis")
print("  parada 2: vuelta 28, VSC          -> barata")
print("  llega:    1ro, desde el 19no de la grilla")

print("\n" + SEP)
print("### COMO PUNTUAN LOS DOS PLANES, SEGUN LO QUE COSTARON LAS PARADAS")
rows = []
for label, model in (("precio normal", MONZA), ("paradas gratis", FREE)):
    rows.append(
        {
            "escenario": label,
            "recomendado": round(score(found.best, model), 2),
            "lo de ANT": round(score(real, model), 2),
            "diferencia": round(score(real, model) - score(found.best, model), 2),
        }
    )
table = pd.DataFrame(rows)
print(table.to_string(index=False))
print()
print("Con las paradas a precio de lista, el plan de ANT es peor: pagar dos veces")
print("el precio de una parada no lo compensa el neumatico mas fresco. Con las")
print("paradas gratis se da vuelta, y por mucho.")
vuelco = table.loc[0, "diferencia"] - table.loc[1, "diferencia"]
print(f"\nEl vuelco vale {vuelco:.1f} s de carrera. Eso es lo que valieron las dos")
print("neutralizaciones, y es la tesis del proyecto medida en un caso real.")

print("\n" + SEP)
print("### CUANTAS PARADAS CONVIENEN, SEGUN SI SALEN GRATIS")
for label, model in (("precio normal", MONZA), ("gratis", FREE)):
    print(f"\n  {label}:")
    for n in (1, 2, 3):
        step = (model.total_laps - 1) // (n + 1)
        p = plan_of(*[(1 + step * (i + 1), "MEDIUM") for i in range(n)])
        print(f"    {n} parada{'s' if n > 1 else ''} al medio: {score(p, model):7.2f} s")
