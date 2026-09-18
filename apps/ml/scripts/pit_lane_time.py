"""Cuánto tarda un auto dentro del pit lane, y qué parte de eso es la parada.

La transmisión muestra un recuadro «IN PIT» con dos números que no son el mismo:
el **tiempo detenido** —los dos segundos y medio con el auto en los gatos— y el
**total perdido en el pit lane**, que incluye entrar, recorrer el carril a
velocidad limitada y salir.

Este script mide lo que se puede medir y dice cuál de los dos no se puede.

## Lo que hay en el dato

``PitInTime`` y ``PitOutTime`` no viven en la misma vuelta: la entrada se anota en
la vuelta que termina en boxes y la salida en la siguiente. Restarlas da el
**tránsito completo por el pit lane**, que es lo que la transmisión llama total.

El tiempo detenido no está. FastF1 expone las dos marcas de tiempo y nada entre
medio, así que los segundos en los gatos no se pueden separar del recorrido por
el carril. Se dice y no se inventa.

## Por qué no es lo mismo que la pérdida de boxes que ya usa el simulador

:attr:`boxbox_ml.strategy.RaceModel.pit_loss_green` son **22,6 s** y el tránsito
mide **23,0**. Que se parezcan es casualidad: miden cosas distintas y sobre
ventanas distintas.

El tránsito va de la línea de entrada a la de salida del pit lane, y es tiempo de
reloj. La pérdida de boxes se mide sobre **dos vueltas** —la de entrada y la de
salida— contra la mediana del campo en esas mismas dos vueltas, así que incluye
también la vuelta de entrada levantando el pie y la de salida con la goma fría, y
descuenta lo que el auto habría tardado igual en recorrer ese tramo.

Las dos van a la pantalla porque la transmisión muestra las dos. Confundirlas es
fácil justo porque el número se parece.

Correr con ``uv run python scripts/pit_lane_time.py``.
"""

from __future__ import annotations

import warnings

import fastf1
import numpy as np
import pandas as pd

from boxbox_ml import cache, track_status

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)
SEP = "=" * 88

ROUNDS = range(1, 15)

#: Más que esto no es una parada: es una bandera roja con la carrera detenida, o
#: un auto que entró a boxes y se quedó. Medido, el corte separa limpio.
MAX_TRANSIT_S = 120.0

cache.enable()
fastf1.Cache.offline_mode(True)

rows = []
for rnd in ROUNDS:
    try:
        session = fastf1.get_session(2026, rnd, "R")
        session.load(laps=True, telemetry=False, weather=False, messages=True)
    except Exception:  # noqa: BLE001 - una ronda que falta no es fatal
        continue
    laps = session.laps.copy()
    if laps.empty:
        continue
    laps["circuit"] = str(session.event["Location"])
    laps["year"] = 2026
    laps["round"] = rnd
    laps["total_laps"] = int(laps["LapNumber"].max())
    laps["pit_in"] = laps["PitInTime"].notna()
    laps["pit_out"] = laps["PitOutTime"].notna()
    laps["LapTime"] = laps["LapTime"].dt.total_seconds()
    flagged = track_status.add_flags(laps)
    state = flagged.groupby("LapNumber")[["is_neutralised", "red"]].max()

    for driver, block in laps.groupby("Driver"):
        block = block.sort_values("LapNumber")
        entries = block[block["PitInTime"].notna()]
        for _, lap in entries.iterrows():
            number = int(lap["LapNumber"])
            following = block[block["LapNumber"] == number + 1]
            if following.empty or following["PitOutTime"].isna().all():
                continue
            transit = (following["PitOutTime"].iloc[0] - lap["PitInTime"]).total_seconds()
            if not np.isfinite(transit) or transit <= 0 or transit > MAX_TRANSIT_S:
                continue
            rows.append(
                {
                    "circuit": laps["circuit"].iloc[0],
                    "round": rnd,
                    "driver": driver,
                    "lap": number,
                    "transit_s": transit,
                    "red": bool(state["red"].get(number, False)),
                    "neutralised": bool(state["is_neutralised"].get(number, False)),
                }
            )

data = pd.DataFrame(rows)

print(SEP)
print("### 1. TRANSITO POR EL PIT LANE, MEDIDO")
print()
print(f"  {len(data)} paradas sobre {data['round'].nunique()} carreras de 2026")
print(f"  descartadas por durar más de {MAX_TRANSIT_S:.0f} s: carrera detenida, no parada")
print()
green = data[~data["neutralised"] & ~data["red"]]
print(f"  en verde ({len(green)} paradas):")
for label, q in (("p10", 0.10), ("p25", 0.25), ("mediana", 0.50), ("p75", 0.75), ("p90", 0.90)):
    print(f"    {label:8s} {green['transit_s'].quantile(q):6.2f} s")

print("\n" + SEP)
print("### 2. POR CIRCUITO — EL LARGO DEL PIT LANE ES DEL CIRCUITO")
print()
by_circuit = (
    green.groupby("circuit")["transit_s"].agg(["size", "median"]).round(2).sort_values("median")
)
by_circuit.columns = ["paradas", "mediana s"]
print(by_circuit.to_string())
print()
spread = by_circuit["mediana s"].max() - by_circuit["mediana s"].min()
print(f"  entre el más corto y el más largo hay {spread:.1f} s de diferencia.")
print("  Es la cantidad por circuito más fácil de justificar de todo el proyecto:")
print("  no depende del auto ni del año, depende de cuán largo es el carril.")

print("\n" + SEP)
print("### 3. CONTRA LO QUE EL SIMULADOR LLAMA «PERDIDA DE BOXES»")
print()
print(
    "  tránsito por el pit lane   mediana {:.1f} s   (lo que este script mide)".format(
        green["transit_s"].median()
    )
)
print("  pérdida de boxes            mediana 22,6 s   (lo que usa el simulador)")
print()
print("  Que se parezcan es CASUALIDAD: miden cosas distintas sobre ventanas")
print("  distintas. El tránsito es reloj, de la línea de entrada a la de salida.")
print("  La pérdida se mide sobre DOS vueltas contra la mediana del campo, así")
print("  que incluye la vuelta de entrada levantando el pie y la de salida con la")
print("  goma fría, y descuenta el tramo que el auto habría recorrido igual.")

print("\n" + SEP)
print("### 4. LO QUE NO SE PUEDE MEDIR")
print()
print("  El TIEMPO DETENIDO —los segundos en los gatos— no está en el dato.")
print("  FastF1 expone la marca de entrada y la de salida, y nada entre medio,")
print("  así que los segundos parado no se pueden separar del recorrido por el")
print("  carril. La transmisión los muestra porque tiene su propio cronometraje.")
print()
print("  Si la pantalla va a mostrar un «IN PIT», tiene que decir tránsito y no")
print("  tiempo detenido, o estaría inventando el número más visible de la tarjeta.")
