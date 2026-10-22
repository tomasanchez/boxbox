"""Los dos compuestos secos obligatorios: la regla que cuesta todo si se rompe.

Artículo B6.3.8 del reglamento deportivo 2026: una carrera en seco tiene que usar
al menos dos especificaciones de neumático, y no hacerlo es **descalificación**.
Es la única restricción del problema entera, sin gradiente: un plan que la
incumple no es un plan un poco peor, es cero puntos.

Por eso el reparador la aplica al final de todo y por eso vale probarla aparte:
un plan ilegal que la búsqueda igual sabe puntuar gana por ser ilegal —se ahorra
una parada o corre el compuesto rápido toda la carrera— y después se publica.

Las tres cosas que esta función **no** hace también se prueban, porque son
decisiones y no olvidos, y están escritas en su docstring: no toca un plan que
ya es legal, no toca un plan que empieza a mitad de carrera (la foto no dice qué
juegos se usaron antes, y adivinarlo es peor que no saberlo) y no arregla un plan
sin paradas, que no tiene arreglo posible salvo inventarle una parada.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from boxbox_ml import strategy
from boxbox_ml.strategy import Car, RaceModel, Stop

MODELO = RaceModel(total_laps=40)


def compuestos_usados(car: Car, stops: tuple[Stop, ...]) -> set[str]:
    """Todo lo que el auto se calzó: con lo que largó más cada cambio."""
    return {car.compound, *(parada.compound for parada in stops)}


@pytest.mark.parametrize("compuesto", strategy.DRY)
def test_un_plan_de_un_solo_compuesto_cambia_la_ultima_parada(
    compuesto: str, coche: Callable[..., Car]
) -> None:
    """DADO un plan de un compuesto solo, sale legal cambiando la ÚLTIMA parada.

    Cambiar y no agregar es deliberado: una parada más cuesta veinte segundos y
    un equipo en este aprieto cambia lo que calza, no para otra vez. Que sea la
    última también: es la que menos carrera tiene por delante para pagar la
    diferencia de ritmo entre compuestos.
    """
    car = coche(compound=compuesto)
    crudo = (Stop(14, compuesto), Stop(26, compuesto))

    legal = strategy._enforce_two_compounds(crudo, car, MODELO)

    assert len(compuestos_usados(car, legal)) >= strategy.REQUIRED_COMPOUNDS
    assert legal[:-1] == crudo[:-1]
    assert legal[-1].lap == crudo[-1].lap
    assert legal[-1].compound != compuesto


@pytest.mark.parametrize("compuesto", strategy.DRY)
def test_el_reemplazo_es_un_compuesto_seco_que_el_auto_no_uso(
    compuesto: str, coche: Callable[..., Car]
) -> None:
    """DADO el cambio obligado, lo que entra es goma seca que el auto todavía no usó.

    Suena obvio y no lo es: cambiar la última parada por el mismo compuesto deja
    el plan igual de ilegal, y el único control que existe está acá.
    """
    car = coche(compound=compuesto)

    legal = strategy._enforce_two_compounds((Stop(20, compuesto),), car, MODELO)

    assert legal[-1].compound in strategy.DRY
    assert legal[-1].compound != compuesto


def test_un_plan_que_ya_es_legal_no_se_toca(coche: Callable[..., Car]) -> None:
    """DADO un plan con dos compuestos, vuelve idéntico.

    El plan legal es la enorme mayoría de lo que pasa por acá, así que una
    "corrección" de más sería un sesgo sistemático del buscador y no un caso raro.
    """
    car = coche(compound="MEDIUM")
    crudo = (Stop(14, "HARD"), Stop(26, "MEDIUM"))

    assert strategy._enforce_two_compounds(crudo, car, MODELO) == crudo


def test_el_compuesto_de_largada_ya_cuenta_como_uno_de_los_dos(
    coche: Callable[..., Car],
) -> None:
    """DADO un auto que largó en medio y para a duro, una sola parada ya alcanza.

    Los dos compuestos incluyen con el que se largó. Contar sólo las paradas
    haría que un plan legal de una parada se "corrija" a algo peor.
    """
    car = coche(compound="MEDIUM")
    crudo = (Stop(20, "HARD"),)

    assert strategy._enforce_two_compounds(crudo, car, MODELO) == crudo


@pytest.mark.parametrize("desde", [2, 18, 30])
def test_un_plan_que_empieza_a_mitad_de_carrera_se_devuelve_intacto(
    desde: int, coche: Callable[..., Car]
) -> None:
    """DADO un auto que ya corrió, el plan vuelve sin tocar aunque parezca ilegal.

    No es un descuido: la foto de la vuelta 30 no registra qué juegos usó el auto
    antes, así que la regla no es verificable. Entre adivinar y no tocar, el
    módulo elige no tocar, y eso tiene que seguir siendo así o el simulador en
    vivo empezaría a cambiarle el compuesto a planes que ya cumplían.
    """
    car = coche(compound="MEDIUM", from_lap=desde)
    crudo = (Stop(desde + 6, "MEDIUM"),)

    assert strategy._enforce_two_compounds(crudo, car, MODELO) == crudo


def test_un_plan_sin_paradas_se_devuelve_tal_cual(coche: Callable[..., Car]) -> None:
    """DADO un plan sin paradas, vuelve vacío: no hay nada que cambiar.

    Comportamiento documentado, no bug. Un plan sin paradas usa un compuesto y no
    hay forma de hacerlo legal cambiando algo —habría que agregar una parada, que
    es otra decisión—; la función lo devuelve y el fitness le cobra la multa.
    """
    car = coche(compound="MEDIUM")

    assert strategy._enforce_two_compounds((), car, MODELO) == ()


@pytest.mark.parametrize("compuesto", strategy.DRY)
def test_el_reparador_entrega_planes_con_dos_compuestos(
    compuesto: str, coche: Callable[..., Car]
) -> None:
    """DADO un plan de un compuesto, el reparador completo lo devuelve ya legal.

    La prueba de que la regla está enchufada donde tiene que estar: ``_repair``
    es la única puerta de la búsqueda y aplica el control al final de todo.
    """
    car = coche(compound=compuesto)

    reparado = strategy._repair([Stop(14, compuesto), Stop(26, compuesto)], car, MODELO)

    assert len(compuestos_usados(car, reparado)) >= strategy.REQUIRED_COMPOUNDS
