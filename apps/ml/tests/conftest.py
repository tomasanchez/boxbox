"""Las piezas que comparten las pruebas del motor de estrategia.

El archivo de instrumentación arma sus propios autos porque prueba la búsqueda
entera. Lo que sigue prueba funciones sueltas del motor, y ahí lo único que se
repite es el auto de referencia: uno que sale desde la parrilla con goma nueva.

Vive en un solo lugar a propósito. Media docena de copias del mismo auto es
media docena de oportunidades de que una prueba diga ``tyre_age=0`` y la de al
lado ``tyre_age=1`` sin que nadie lo note, y la edad de la goma es justamente
una de las cosas que estas pruebas miden.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from boxbox_ml import strategy
from boxbox_ml.strategy import Car


@pytest.fixture
def coche() -> Callable[..., Car]:
    """Fábrica del auto de referencia; cada prueba cambia sólo lo que le importa.

    ``pace_s`` va explícito porque sin él un plan previo a la carrera no sabe
    desde dónde larga: un hueco de parrilla es un offset, no un ritmo por vuelta,
    y el propio módulo avisa que inferirlo antes de largar da cero.
    """

    def crear(**cambios: Any) -> Car:
        campos: dict[str, Any] = {
            "code": "FOC",
            "compound": "MEDIUM",
            "tyre_age": 0,
            "degradation_s": 0.0,
            "degradation_rate": strategy.ROLLING_MEDIAN_S,
            "gap_leader_s": 0.0,
            "from_lap": 1,
            "pace_s": 0.3,
        }
        return Car(**(campos | cambios))

    return crear
