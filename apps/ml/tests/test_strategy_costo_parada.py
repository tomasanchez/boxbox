"""Lo que cuesta parar según la bandera con la que uno se encuentra.

Toda la estrategia de una carrera cabe en esta diferencia. Parar en verde cuesta
unos veintitrés segundos de posición en pista; parar con bandera roja no cuesta
nada, porque la carrera está detenida y se cambian las gomas en el pit lane sin
conceder nada a nadie. En Monza 2026 eso se aplicó a 22 de 32 paradas, y un
modelo que no lo representa no entiende esa carrera.

Ninguna cifra esperada está escrita acá: todas se leen de las tuplas del
``RaceModel``, que son cortes de distribuciones medidas —2.614 paradas en verde,
264 con auto de seguridad, 199 con VSC— y que se van a mover cuando se vuelvan a
medir. Lo que se fija es la **relación** entre ellas, que es lo que el modelo
afirma: roja casi gratis, auto de seguridad y VSC más baratos que verde, y cada
bandera cobrando su propia distribución y no la del vecino.

Las medianas se comparan contra el corte del 50% con una tolerancia derivada del
corte siguiente: la mediana muestral tiene que caer más cerca de la mediana
medida que del percentil 65, que es una forma de decir "acá" sin inventar un
umbral.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest

from boxbox_ml import strategy
from boxbox_ml.strategy import Car, Plan, RaceModel, Stop

MODELO = RaceModel(total_laps=40)
#: Suficientes sorteos para que la mediana muestral se quede quieta, y siguen
#: siendo cuatro operaciones vectorizadas: la prueba corre en milisegundos.
SORTEOS = 20_000
#: Índice del corte del 50% dentro de ``CUT_AT``, buscado y no escrito a mano.
MEDIANA = int(np.flatnonzero(strategy.CUT_AT == 0.5)[0])

#: Cada bandera con la distribución de costo que le corresponde.
COSTOS = {
    "verde": (strategy.GREEN, MODELO.pit_loss_green),
    "vsc": (strategy.VSC_FLAG, MODELO.pit_loss_vsc),
    "sc": (strategy.SC_FLAG, MODELO.pit_loss_sc),
    "roja": (strategy.RED_FLAG, MODELO.pit_loss_red),
}


def costo_bajo(codigo: int, sorteos: int = SORTEOS, semilla: int = 17) -> np.ndarray:
    """Lo que cuesta parar en ``sorteos`` carreras, todas bajo la misma bandera."""
    bajo = np.full(sorteos, codigo, dtype=np.int8)
    return strategy._cost_under(bajo, MODELO, np.random.default_rng(semilla), sorteos)


def cerca_de_la_mediana_medida(muestra: np.ndarray, cortes: tuple[float, ...]) -> None:
    """La mediana muestral cae más cerca del corte del 50% que del siguiente corte."""
    medida = cortes[MEDIANA]
    margen = (cortes[MEDIANA + 1] - medida) / 2
    assert float(np.median(muestra)) == pytest.approx(medida, abs=margen)


@pytest.mark.parametrize("bandera", list(COSTOS), ids=list(COSTOS))
def test_cada_bandera_cobra_su_propia_distribucion_medida(bandera: str) -> None:
    """DADA una bandera, lo que cuesta parar sale de SU distribución y de ninguna otra.

    Cuatro distribuciones y un ``np.where`` encadenado: equivocarse de rama deja
    a una bandera cobrando lo de la de al lado, y eso no se nota en ninguna cifra
    agregada.
    """
    codigo, cortes = COSTOS[bandera]

    costo = costo_bajo(codigo)

    # Fuera de los cortes no hay datos, así que la distribución está recortada.
    assert costo.min() >= cortes[0]
    assert costo.max() <= cortes[-1]
    cerca_de_la_mediana_medida(costo, cortes)


def test_la_bandera_roja_es_practicamente_gratis() -> None:
    """DADA una parada con bandera roja, cuesta décimas y no decenas de segundos.

    La única de las cuatro que no está medida: con la carrera detenida no hay
    campo contra el cual medir lo que se concede. Son décimas supuestas, y la
    prueba fija que sigan siendo décimas.
    """
    costo = costo_bajo(strategy.RED_FLAG)

    cerca_de_la_mediana_medida(costo, MODELO.pit_loss_red)
    # Cien paradas con bandera roja cuestan menos que una sola en verde.
    assert float(np.median(costo)) * 100 < MODELO.pit_loss_green[MEDIANA]


@pytest.mark.parametrize("bandera", ["sc", "vsc"], ids=["auto-de-seguridad", "vsc"])
def test_parar_bajo_neutralizacion_sale_mas_barato_que_en_verde(bandera: str) -> None:
    """DADA una neutralización, la mediana de parar es más barata que en verde.

    En la mediana y no siempre: las dos distribuciones tienen colas caras y se
    superponen —el auto de seguridad llega a 53 segundos— así que afirmar que
    cada parada concreta sale más barata sería falso y la prueba estaría mal.
    """
    codigo, cortes = COSTOS[bandera]

    assert np.median(costo_bajo(codigo)) < np.median(costo_bajo(strategy.GREEN))
    assert cortes[MEDIANA] < MODELO.pit_loss_green[MEDIANA]


def test_ninguna_parada_en_verde_le_gana_a_una_con_bandera_roja() -> None:
    """DADO un sorteo mezclado, la peor parada con roja es más barata que la mejor en verde.

    Acá sí vale el "siempre": las dos distribuciones no se superponen ni un poco,
    y por eso la roja no es una parada barata sino otra cosa.
    """
    bajo = np.tile(np.array([strategy.GREEN, strategy.RED_FLAG], dtype=np.int8), SORTEOS // 2)

    costo = strategy._cost_under(bajo, MODELO, np.random.default_rng(19), SORTEOS)

    assert costo[bajo == strategy.RED_FLAG].max() < costo[bajo == strategy.GREEN].min()


def test_el_costo_lo_decide_la_vuelta_en_la_que_se_para() -> None:
    """DADA una bandera en una vuelta puntual, sólo parar EN esa vuelta sale gratis.

    Es el desfasaje que haría que una estrategia aprovechara una bandera roja una
    vuelta antes de que exista.
    """
    sorteos = 500
    banderas = np.zeros((MODELO.total_laps + 1, sorteos), dtype=np.int8)
    banderas[17] = strategy.RED_FLAG

    en_la_roja = strategy._pit_cost(banderas, 17, MODELO, np.random.default_rng(1), sorteos)
    una_despues = strategy._pit_cost(banderas, 18, MODELO, np.random.default_rng(1), sorteos)

    assert en_la_roja.max() <= MODELO.pit_loss_red[-1]
    assert una_despues.min() >= MODELO.pit_loss_green[0]


def test_una_vuelta_pasada_del_final_usa_la_ultima_fila() -> None:
    """DADA una parada más allá de la última vuelta, se lee la última fila y no se rompe.

    El reparador no deja planes así, pero el recorte está escrito en el código y
    una prueba es más barata que descubrir el ``IndexError`` en medio de una
    búsqueda de media hora.
    """
    sorteos = 100
    banderas = np.zeros((MODELO.total_laps + 1, sorteos), dtype=np.int8)
    banderas[-1] = strategy.RED_FLAG

    costo = strategy._pit_cost(
        banderas, MODELO.total_laps + 99, MODELO, np.random.default_rng(1), sorteos
    )

    assert costo.max() <= MODELO.pit_loss_red[-1]


def test_sin_banderas_la_carrera_corre_toda_en_verde(coche: Callable[..., Car]) -> None:
    """DADO ``flags=None``, la traza corre en verde en vez de romperse."""
    traza = strategy.race_trace(
        Plan((Stop(20, "HARD"),)), coche(), MODELO, np.random.default_rng(1), 4, None
    )

    assert traza.shape == (MODELO.total_laps + 1, 4)
