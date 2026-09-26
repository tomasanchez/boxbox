"""Cuántas veces sale el safety car, contra cuántos períodos cuenta el proyecto.

Salió de Bakú 2026. La secuencia del ganador era ``M31-S5-S15`` —un juego de
blandos tirado a las cinco vueltas— y eso sólo tiene sentido si la parada fue
gratis. La dirección de carrera lo explica: el coche de seguridad salió en la
vuelta 31, entró en la 35 y **volvió a salir en la 36**, porque el relanzamiento
terminó en un choque en la curva 1. Dos despliegues, dos oleadas de boxes.

:func:`neutralisation._count_periods` informa **un** período para esa carrera, y
no se equivoca en lo que dice contar: cuenta corridas contiguas de vueltas
neutralizadas, y entre los dos despliegues no se completó ni una vuelta en verde
—el coche entró al final de la 35 y el choque fue en la curva 1 de la 36—, así
que el tramo neutralizado efectivamente es uno solo de diez vueltas.

Lo que subcuenta son los **despliegues**, y esa es la cantidad que decide cuántas
veces se puede parar gratis. Este script mide la diferencia comparando el conteo
del proyecto contra los mensajes ``SAFETY CAR DEPLOYED`` de la dirección de
carrera, que son la fuente de verdad sobre cuántas veces salió.

**Qué mueve y qué no.** Las *vueltas* neutralizadas están bien contadas, así que
la probabilidad de toparse una neutralización en una vuelta dada —de donde sale
el costo de parar, y con él las cifras publicadas del informe— no cambia. Lo que
queda subestimado es el número de *oportunidades distintas*, que es justo lo que
usa la política de rivales reactivos, porque deja parar una vez por período. Esa
política está detrás de una bandera, así que esto es una limitación declarada y
no una corrección de resultados.

Correr con ``uv run python scripts/sc_redeployments.py``.
"""

from __future__ import annotations

import warnings

import fastf1
import pandas as pd

from boxbox_ml import cache, neutralisation

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)
cache.enable()
SEP = "=" * 88

#: Temporada y hasta qué fecha. Se mide 2026 porque es la que el simulador corre:
#: `n_sc` sale de esta temporada y es la que la política reactiva usa.
SEASON = 2026
ROUNDS = range(1, 16)


def survey() -> pd.DataFrame:
    """Una fila por carrera: períodos contados y despliegues reales."""
    rows = []
    for rnd in ROUNDS:
        session = fastf1.get_session(SEASON, rnd, "R")
        session.load(laps=True, telemetry=False, weather=False, messages=True)

        laps = session.laps.copy()
        laps["LapNumber"] = laps["LapNumber"].astype(int)
        laps["circuit"] = session.event["EventName"]
        laps["year"] = SEASON
        laps["round"] = rnd
        laps["total_laps"] = int(laps["LapNumber"].max())

        summary = neutralisation.summarise_race(laps)
        control = session.race_control_messages
        rows.append(
            {
                "fecha": rnd,
                "circuito": summary["circuit"],
                "periodos": summary["sc_periods"],
                "despliegues": int(
                    control["Message"].str.contains("SAFETY CAR DEPLOYED", na=False).sum()
                ),
                "vueltas_sc": summary["sc_laps"],
            }
        )
    return pd.DataFrame(rows)


races = survey()
races["faltan"] = races["despliegues"] - races["periodos"]

print(SEP)
print(f"### SAFETY CARS DE {SEASON}: DESPLIEGUES CONTRA PERIODOS CONTADOS")
print()
print(races.to_string(index=False))

missed = races[races["faltan"] > 0]
print()
print(f"  despliegues reales:            {int(races['despliegues'].sum())}")
print(f"  períodos que cuenta el código: {int(races['periodos'].sum())}")
print(
    f"  subconteo:                     {int(races['faltan'].sum())}"
    f" ({races['faltan'].sum() / max(races['despliegues'].sum(), 1):.0%})"
)
print()
print(f"  carreras afectadas: {len(missed)} de {len(races)}")
if len(missed):
    print(f"    {', '.join(missed['circuito'])}")
print()
print("  El subconteo no está repartido al azar: cae entero en las RE-SALIDAS")
print("  rápidas, donde el coche entra y vuelve a salir sin que se corra una")
print("  vuelta en verde. Y ésas son exactamente las que regalan una segunda")
print("  parada, porque el auto que ya paró en la primera oleada puede volver a")
print("  parar en la segunda sin perder posición contra nadie que esté en pista.")
print()
print(SEP)
