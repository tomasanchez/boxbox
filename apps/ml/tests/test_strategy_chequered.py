"""La bandera a cuadros: cuántas vueltas completa cada auto, no cuántas corre.

Una carrera no termina cuando el primero cruza la meta: termina cuando cada auto
cruza **después** de que el primero lo hizo. El doblado nunca corre la última
vuelta, y el simulador le cobraba vueltas de desgaste y de reloj que nunca
habría hecho.

El error que se cometió al escribir esto la primera vez es el que esta prueba
custodia, y es un error de unidades: **contar segundos como si fueran vueltas**.
Un auto a un segundo del ganador no está una vuelta abajo —toma la bandera en su
próximo cruce y completa la misma distancia— pero si se mide el hueco en
segundos y se lo compara contra uno, el 100% del campo termina doblado. La
cuenta correcta es ``floor(hueco / vuelta verde)``, con la vuelta verde del
modelo, que en Zandvoort son casi 78 segundos.

Las trazas se arman a mano, como una rampa de una vuelta verde por vuelta, por
dos razones: la prueba no depende de que el motor de simulación esté bien, y los
tiempos esperados se pueden escribir exactos en vez de aproximados.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pytest

from boxbox_ml import strategy
from boxbox_ml.strategy import RaceModel

MODELO = RaceModel(total_laps=40)
VUELTAS = 40
SORTEOS = 3


def campo(huecos: Sequence[float], vueltas: int = VUELTAS, sorteos: int = SORTEOS) -> np.ndarray:
    """Trazas sintéticas ``(autos, vueltas + 1, sorteos)``: una rampa por auto.

    Cada auto suma una vuelta verde por vuelta y arrastra su hueco con el líder
    desde la vuelta cero, que es como se comporta un auto más lento y constante.
    """
    rampa = np.arange(vueltas + 1, dtype=float)[None, :, None] * MODELO.green_lap_s
    trazas = rampa + np.asarray(huecos, dtype=float)[:, None, None]
    return np.repeat(trazas, sorteos, axis=2)


def test_la_forma_es_una_fila_por_auto_y_una_columna_por_sorteo() -> None:
    """DADO un campo, las vueltas y los tiempos salen por auto y por sorteo."""
    vueltas, tiempos = strategy.chequered(campo([0.0, 1.0, 200.0]), MODELO)

    assert vueltas.shape == (3, SORTEOS)
    assert tiempos.shape == (3, SORTEOS)


def test_el_lider_completa_la_distancia_entera() -> None:
    """DADO un campo, el más rápido completa todas las vueltas simuladas.

    El líder es el que define la bandera, así que su cuenta no puede depender de
    nada: completa la distancia entera siempre.
    """
    vueltas, _ = strategy.chequered(campo([5.0, 0.0, 200.0]), MODELO)

    assert vueltas[1].tolist() == [VUELTAS] * SORTEOS


def test_un_segundo_no_es_una_vuelta() -> None:
    """DADO un auto a un segundo del ganador, completa la misma distancia que él.

    El bug, dicho en una línea. Un segundo es un segundo; hace falta una vuelta
    verde entera —casi ochenta segundos— para perder una vuelta.
    """
    vueltas, _ = strategy.chequered(campo([0.0, 1.0]), MODELO)

    assert vueltas[1].tolist() == vueltas[0].tolist() == [VUELTAS] * SORTEOS


@pytest.mark.parametrize("multiplo", [0.0, 0.5, 0.99, 1.4, 2.25, 3.9])
def test_las_vueltas_abajo_son_el_hueco_dividido_la_vuelta_verde(multiplo: float) -> None:
    """DADO un hueco de N vueltas verdes, el auto termina ``floor(N)`` vueltas abajo.

    Se eligen múltiplos que no son enteros a propósito: el borde exacto depende
    del último bit de un flotante y probarlo ahí sería probar la aritmética de
    la máquina, no la regla.
    """
    hueco = multiplo * MODELO.green_lap_s

    vueltas, _ = strategy.chequered(campo([0.0, hueco]), MODELO)

    assert vueltas[1].tolist() == [VUELTAS - int(multiplo)] * SORTEOS


def test_un_auto_mas_de_una_vuelta_abajo_completa_menos_vueltas() -> None:
    """DADO un auto a dos vueltas y media, completa dos vueltas menos que el líder."""
    vueltas, _ = strategy.chequered(campo([0.0, 2.5 * MODELO.green_lap_s]), MODELO)

    assert (vueltas[1] < vueltas[0]).all()
    assert vueltas[1].tolist() == [VUELTAS - 2] * SORTEOS


def test_el_tiempo_informado_es_el_del_ultimo_cruce() -> None:
    """DADO un auto doblado, se informa el tiempo de la vuelta en que tomó la bandera.

    Es lo único que el cálculo cambia respecto de antes: el tiempo del doblado ya
    no incluye vueltas fantasma. En la rampa, ese tiempo es exactamente el de su
    última vuelta real más su hueco.
    """
    hueco = 2.5 * MODELO.green_lap_s

    vueltas, tiempos = strategy.chequered(campo([0.0, hueco]), MODELO)

    assert tiempos[0] == pytest.approx(VUELTAS * MODELO.green_lap_s)
    assert tiempos[1] == pytest.approx(vueltas[1] * MODELO.green_lap_s + hueco)


def test_el_orden_de_llegada_no_cambia() -> None:
    """DADO un campo, quien termina antes la distancia entera sigue siendo el primero.

    Lo que esta función NO toca, y conviene dejarlo clavado: un auto doblado tarda
    más, así que ordenar por tiempo a distancia completa da la misma clasificación
    que la real. Por eso el bug nunca salió como un puesto mal asignado.
    """
    trazas = campo([120.0, 0.0, 2.5 * MODELO.green_lap_s])

    vueltas, tiempos = strategy.chequered(trazas, MODELO)

    por_distancia = np.argsort(trazas[:, -1, 0])
    # Más vueltas primero y, a igualdad de vueltas, menos tiempo.
    por_bandera = np.lexsort((tiempos[:, 0], -vueltas[:, 0]))
    assert por_bandera.tolist() == por_distancia.tolist()


def test_un_hueco_imposible_no_deja_vueltas_negativas() -> None:
    """DADO un hueco absurdo, el auto completa al menos una vuelta.

    El recorte existe para que un auto que se rompió en la vuelta dos no termine
    con vueltas negativas e indexando la traza al revés.
    """
    hueco = 10 * VUELTAS * MODELO.green_lap_s

    vueltas, tiempos = strategy.chequered(campo([0.0, hueco]), MODELO)

    assert vueltas[1].tolist() == [1] * SORTEOS
    assert np.isfinite(tiempos).all()


def test_un_campo_vacio_no_rompe() -> None:
    """DADO un campo sin autos, salen dos arrays vacíos y ninguna excepción.

    Pasa de verdad: el buscador puede quedarse sin rivales vivos.
    """
    vueltas, tiempos = strategy.chequered(np.empty((0, 0, 0)), MODELO)

    assert vueltas.size == 0
    assert tiempos.size == 0
