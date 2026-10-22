"""El desfasaje de una vuelta: la carrera simulada tiene que durar la carrera.

Esto es una regresión, no una prueba de diseño. Durante meses el simulador corrió
``total_laps - from_lap`` vueltas, o sea **71 de 72** saliendo desde la parrilla,
y el error no se veía por ningún lado porque no rompe nada: todos los autos
corrían la misma distancia equivocada, el orden de llegada salía bien y los
tiempos salían parejamente cortos. Se veía en un solo lugar, en el plan escrito
—``S20-H27-H24`` suma 71— y ahí nadie lo miraba.

Lo que se prueba es la identidad que lo delata, que es más fuerte que mirar el
número: **lo que el plan dice que corre y lo que la traza corre son lo mismo**.
Una vuelta de diferencia entre esas dos cosas es exactamente el bug, venga del
lado que venga.

``chequered`` entra al final porque es la función que convierte esa distancia en
vueltas completadas, y su propio aviso de que el líder termina en 71 quedó
viejo: hoy termina en 72. Dejar la prueba acá es lo que mantiene honesto al
aviso.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest

from boxbox_ml import strategy
from boxbox_ml.strategy import Car, Plan, RaceModel, Stop

MODELO = RaceModel(total_laps=40)
SORTEOS = 8

#: Planes con cero, una, dos y tres paradas. Un plan sin paradas es candidato
#: legal del buscador, así que entra en la cuenta como cualquier otro.
PLANES: dict[str, Plan] = {
    "sin-paradas": Plan(()),
    "una-parada": Plan((Stop(20, "HARD"),)),
    "dos-paradas": Plan((Stop(12, "SOFT"), Stop(26, "HARD"))),
    "tres-paradas": Plan((Stop(9, "SOFT"), Stop(19, "MEDIUM"), Stop(30, "HARD"))),
}


def vueltas_descritas(plan: Plan, car: Car, total_laps: int) -> int:
    """Cuántas vueltas suma el plan tal como lo escribiría el muro de boxes."""
    return sum(int(tanda[1:]) for tanda in plan.describe(car, total_laps).split("-"))


def verde(total_laps: int, sorteos: int) -> np.ndarray:
    """Una carrera entera en verde: sin banderas no hay nada que confunda la cuenta."""
    return np.zeros((total_laps + 1, sorteos), dtype=np.int8)


@pytest.mark.parametrize("plan", list(PLANES.values()), ids=list(PLANES))
def test_un_plan_desde_la_parrilla_suma_la_carrera_entera(
    plan: Plan, coche: Callable[..., Car]
) -> None:
    """DADO un plan desde la parrilla, sus tandas suman ``total_laps`` exactas.

    Ni una menos: la vuelta que faltaba era la primera, porque ``from_lap`` es la
    primera vuelta que **falta correr** y entra en la cuenta.
    """
    car = coche(from_lap=1)

    assert vueltas_descritas(plan, car, MODELO.total_laps) == MODELO.total_laps


@pytest.mark.parametrize("desde", [2, 15, 30, 39])
def test_un_plan_que_empieza_a_mitad_suma_lo_que_queda(
    desde: int, coche: Callable[..., Car]
) -> None:
    """DADO un plan tomado a mitad de carrera, suma las vueltas que faltan y no más.

    El uso en vivo del simulador es este: una foto en la vuelta 30 y qué hacer con
    lo que queda. Si la cuenta de "lo que queda" está corrida, está corrido todo.
    """
    car = coche(from_lap=desde)
    plan = Plan(())

    faltan = MODELO.total_laps - desde + 1
    assert vueltas_descritas(plan, car, MODELO.total_laps) == faltan


@pytest.mark.parametrize("plan", list(PLANES.values()), ids=list(PLANES))
@pytest.mark.parametrize("desde", [1, 15])
def test_la_traza_corre_exactamente_las_vueltas_que_el_plan_dice(
    plan: Plan, desde: int, coche: Callable[..., Car]
) -> None:
    """DADO un plan, la traza simulada tiene una fila por vuelta descrita, más la cero.

    Ésta es la prueba que importa: ata el texto del plan al cómputo. Las dos
    cuentas de vueltas viven en funciones distintas y se pueden desincronizar sin
    que nadie proteste, que es precisamente lo que pasó.
    """
    car = coche(from_lap=desde)
    plan_valido = Plan(tuple(p for p in plan.stops if p.lap > desde))

    traza = strategy.race_trace(
        plan_valido,
        car,
        MODELO,
        np.random.default_rng(11),
        SORTEOS,
        verde(MODELO.total_laps, SORTEOS),
    )

    assert traza.shape == (vueltas_descritas(plan_valido, car, MODELO.total_laps) + 1, SORTEOS)


@pytest.mark.parametrize("plan", list(PLANES.values()), ids=list(PLANES))
def test_las_tandas_internas_miden_lo_mismo_que_las_escritas(
    plan: Plan, coche: Callable[..., Car]
) -> None:
    """DADO un plan, las tandas que usa el simulador son las que muestra el plan escrito.

    ``_stints`` y ``describe`` cuentan lo mismo dos veces, en dos funciones. Una
    de ellas se puede arreglar sola, y entonces el informe diría una cosa y la
    simulación haría otra.
    """
    car = coche(from_lap=1)

    tandas = strategy._stints(plan, car, MODELO.total_laps)

    escritas = [int(tanda[1:]) for tanda in plan.describe(car, MODELO.total_laps).split("-")]
    assert [fin - inicio for _, inicio, fin in tandas] == escritas


def test_la_bandera_le_da_al_lider_la_carrera_entera(coche: Callable[..., Car]) -> None:
    """DADO un campo que largó de la parrilla, el líder completa ``total_laps``.

    De punta a punta: tres autos simulados de verdad, apilados como campo, y la
    bandera contada sobre eso. Es la forma de comprobar el desfasaje sin leer
    ninguna forma de array a mano.
    """
    autos = [coche(code=f"C{i}", pace_s=0.1 * i) for i in range(3)]
    plan = Plan((Stop(20, "HARD"),))
    banderas = verde(MODELO.total_laps, SORTEOS)
    campo = np.stack(
        [
            strategy.race_trace(plan, car, MODELO, np.random.default_rng(7 + i), SORTEOS, banderas)
            for i, car in enumerate(autos)
        ]
    )

    vueltas, _ = strategy.chequered(campo, MODELO)

    assert vueltas.max() == MODELO.total_laps
