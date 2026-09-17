"""La clasificación del sábado, que es lo único que mide el ritmo antes de largar.

Antes de que se apaguen las luces no hay historia de carrera: no hay terreno
perdido del cual inferir cuánto le da un auto al más rápido. Lo único que mide
esa diferencia es la clasificación, porque **una diferencia de tiempo de vuelta
ya es una cantidad por vuelta**. Cuánto de ese hueco sobrevive a la carrera está
medido —r = 0,880 sobre 277 pilotos-carrera, pendiente 0,835, ver
``scripts/quali_to_race_pace.py``— y se aplica con
:func:`boxbox_ml.strategy.pace_from_qualifying`.

Este módulo existe porque había scripts inventando la parrilla. El peor caso era
``prerace_strategy.py``, que armaba el campo con una escalera de 0,25 s por
puesto y la describía como «the measured spread of a starting grid»: ese número
no salía de ninguna medición. Un hueco inventado no es un detalle estético —
alimenta el ritmo de cada auto, y el ritmo es lo que ordena la carrera. Ver
ADR-004.

Lo que **no** se lee acá es la sesión de carrera. Todo lo que devuelve este
módulo existe el sábado a la tarde, que es la disciplina que hace que una
predicción pre-carrera sea una predicción y no una descripción.
"""

from __future__ import annotations

from dataclasses import dataclass

import fastf1
import pandas as pd

from boxbox_ml import cache
from boxbox_ml.neutralisation import canonical_circuit

#: Los tres segmentos, y por qué el mejor tiempo es el mínimo de los tres. El que
#: llega a Q3 mejora ahí y ese es su tiempo; el que se queda en Q1 tiene ahí su
#: única referencia. Tomar sólo Q3 dejaría sin ritmo a la mitad de la parrilla.
SEGMENTS = ("Q1", "Q2", "Q3")


@dataclass(frozen=True)
class Entry:
    """Un piloto con tiempo, y lo que le sacó la pole."""

    code: str
    driver: str
    team: str
    #: Puesto en la clasificación. Es el de largada salvo sanción, que se aplica
    #: después de la sesión y que este módulo no mira.
    grid_position: int
    best_lap_s: float
    #: Segundos por vuelta detrás de la pole. Insumo de
    #: :func:`boxbox_ml.strategy.pace_from_qualifying`.
    gap_to_pole_s: float


@dataclass(frozen=True)
class Excluded:
    """Un piloto que queda afuera del campo, con el motivo declarado.

    No se lo rellena con un tiempo estimado. Un piloto sin vuelta no tiene hueco
    a la pole, y ponerle uno sería exactamente el número inventado que este
    módulo vino a sacar.
    """

    code: str
    reason: str


@dataclass(frozen=True)
class Qualifying:
    """Una sesión de clasificación, ordenada y lista para armar un campo."""

    year: int
    #: Número de fecha en el calendario de esa temporada.
    round: int
    event: str
    #: Clave estable de circuito, la misma que espera
    #: :meth:`boxbox_ml.strategy.RaceModel.for_circuit`.
    circuit: str
    #: Mejor vuelta de la sesión, en segundos: el cero de ``gap_to_pole_s``.
    pole_s: float
    #: Los pilotos con tiempo, del primero al último.
    entries: tuple[Entry, ...]
    #: Los que no dejaron ninguno.
    excluded: tuple[Excluded, ...]

    @property
    def gaps(self) -> tuple[float, ...]:
        """Los huecos a la pole en orden de grilla, que es lo que reemplazó a la
        escalera inventada."""
        return tuple(entry.gap_to_pole_s for entry in self.entries)


def _best_lap_s(results: pd.DataFrame) -> pd.Series:
    """Mejor tiempo de cada piloto en segundos, NaN si no dejó ninguno."""
    segments = [
        pd.to_timedelta(results[segment], errors="coerce").dt.total_seconds()
        for segment in SEGMENTS
    ]
    return pd.concat(segments, axis=1).min(axis=1)


def load(year: int, rnd: int, *, offline: bool = True) -> Qualifying:
    """Leer una clasificación de FastF1 y devolverla ordenada por puesto.

    Args:
        year: Temporada.
        rnd: Número de fecha, como lo numera el calendario de FastF1.
        offline: Encender el modo offline de FastF1 antes de pedir la sesión. Es
            un interruptor **global** de FastF1 y queda encendido para el resto
            del proceso. Por omisión sí: la caché del repo ya tiene las sesiones
            que los scripts usan, y la API de live timing corta a los 500 pedidos
            por hora — una corrida distraída gasta ese presupuesto sin avisar.
            Pasar ``False`` es pedir la descarga a propósito.

    Returns:
        La sesión con los pilotos con tiempo ordenados por puesto, y aparte los
        que no dejaron ninguno.

    Raises:
        ValueError: Si la sesión carga y nadie dejó un tiempo. Eso no es un
            resultado: es una caché incompleta, y devolver un campo vacío haría
            que el error apareciera veinte funciones más adelante.
    """
    cache.enable()
    if offline:
        fastf1.Cache.offline_mode(True)

    session = fastf1.get_session(year, rnd, "Q")
    # Sin vueltas ni telemetría: el resultado oficial ya trae los tres segmentos,
    # y cargar las vueltas de una sesión que sólo se mira por sus tiempos cuesta
    # de más.
    session.load(laps=False, telemetry=False, weather=False, messages=False)

    results = session.results
    best = _best_lap_s(results)
    if not best.notna().any():
        raise ValueError(f"{year} fecha {rnd}: la clasificación cargó sin ningún tiempo")
    pole = float(best.min())

    entries: list[Entry] = []
    excluded: list[Excluded] = []
    for _, row in results.assign(best_lap_s=best).sort_values("Position").iterrows():
        code = str(row["Abbreviation"])
        lap = row["best_lap_s"]
        if pd.isna(lap):
            excluded.append(Excluded(code, "sin tiempo en Q1, Q2 ni Q3"))
            continue
        if pd.isna(row["Position"]):
            excluded.append(Excluded(code, "con tiempo pero sin puesto en el resultado"))
            continue
        entries.append(
            Entry(
                code=code,
                driver=str(row["FullName"]),
                team=str(row["TeamName"]),
                grid_position=int(row["Position"]),
                best_lap_s=float(lap),
                # A la milésima, que es la precisión con la que el cronómetro
                # mide y publica. Restar dos flotantes deja basura en el
                # decimoquinto decimal, y esa basura viaja después al ritmo de
                # carrera y de ahí al JSON.
                gap_to_pole_s=round(float(lap) - pole, 3),
            )
        )

    return Qualifying(
        year=year,
        round=rnd,
        event=str(session.event["EventName"]),
        circuit=canonical_circuit(session.event["Location"]),
        pole_s=pole,
        entries=tuple(entries),
        excluded=tuple(excluded),
    )
