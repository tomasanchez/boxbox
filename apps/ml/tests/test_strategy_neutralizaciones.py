"""El sorteo de banderas y la numeración de los períodos que arma encima.

Cada carrera sorteada recibe sus propios autos de seguridad, sus VSC y sus
banderas rojas, cada uno empezando donde empiezan de verdad y durando lo que
duran. El modelo anterior sorteaba **un** auto de seguridad y nada más, y eso
dejaba afuera las dos cosas que más mueven una estrategia: que casi la mitad de
las carreras ven dos o más neutralizaciones, y que un cambio de gomas con
bandera roja es **gratis**. Monza 2026 se decidió exactamente ahí.

Dos propiedades se prueban con cuidado porque no son evidentes leyendo el
código:

* **Donde se superponen gana la más barata.** Una vuelta que está a la vez bajo
  auto de seguridad y bandera roja es una vuelta de bandera roja, porque eso es
  lo que cuesta parar en ella. El sorteo lo resuelve con un ``maximum`` sobre
  los códigos, lo cual funciona sólo porque los códigos están ordenados de caro
  a barato — un detalle frágil que merece una prueba que lo fije.
* **Un período es una corrida máxima de vueltas consecutivas bajo la MISMA
  bandera.** Se deriva de las banderas ya resueltas y no del sorteo, así que un
  auto de seguridad que una bandera roja se tragó deja de ser un período de auto
  de seguridad. Esa numeración es la que después reparte un único sorteo de
  comportamiento entre todos los autos que están adentro.

Para fijar superposiciones y duraciones se usan modelos con los cortes de inicio
todos iguales: así ``_from_cuts`` devuelve siempre la misma fracción de
distancia y el período cae donde la prueba lo necesita, sin depender de la
semilla.
"""

from __future__ import annotations

import numpy as np
import pytest

from boxbox_ml import strategy
from boxbox_ml.strategy import RaceModel

VUELTAS = 40
SORTEOS = 120

#: Cortes constantes: el período arranca siempre a mitad de carrera.
A_MITAD = (0.5,) * len(strategy.CUT_AT)
#: Pesos que apagan un tipo de bandera: cero períodos con probabilidad uno.
NUNCA = (1.0, 0.0, 0.0, 0.0)
#: Pesos que lo encienden exactamente una vez.
SIEMPRE_UNO = (0.0, 1.0, 0.0, 0.0)

#: Cada tipo de bandera con el campo de ``RaceModel`` que lo cuenta.
TIPOS = {
    "vsc": (strategy.VSC_FLAG, "n_vsc"),
    "sc": (strategy.SC_FLAG, "n_sc"),
    "red": (strategy.RED_FLAG, "n_red"),
}


def periodos_de_referencia(columna: np.ndarray) -> list[int]:
    """Numera los períodos de una carrera a mano, recorriéndola vuelta por vuelta.

    Escrita como la contaría una persona mirando la planilla, que es lo contrario
    de como la calcula el módulo (sumas acumuladas sobre toda la matriz de una).
    Dos caminos distintos al mismo número es lo que hace que comparar sirva.
    """
    ids: list[int] = []
    actual, anterior = 0, strategy.GREEN
    for bandera in columna.tolist():
        if bandera == strategy.GREEN:
            ids.append(0)
        else:
            if bandera != anterior:
                actual += 1
            ids.append(actual)
        anterior = bandera
    return ids


def test_la_forma_es_una_fila_por_vuelta_mas_la_cero() -> None:
    """DADO un sorteo, hay una fila por vuelta de carrera más la vuelta cero.

    La fila cero existe para que un plan pueda preguntar por cualquier vuelta
    indexando derecho, sin corregir el índice en cada lugar que lo usa.
    """
    banderas = strategy.draw_neutralisations(
        RaceModel(total_laps=VUELTAS), np.random.default_rng(1), SORTEOS
    )

    assert banderas.shape == (VUELTAS + 1, SORTEOS)
    assert set(np.unique(banderas).tolist()) <= {
        strategy.GREEN,
        strategy.VSC_FLAG,
        strategy.SC_FLAG,
        strategy.RED_FLAG,
    }


def test_una_carrera_sin_neutralizaciones_sale_toda_en_verde() -> None:
    """DADOS pesos que no dan ningún período, no aparece una sola bandera.

    El caso de control: sin él, una prueba que mide banderas puede estar midiendo
    un sorteo que siempre dispara.
    """
    modelo = RaceModel(total_laps=VUELTAS, n_red=NUNCA, n_sc=NUNCA, n_vsc=NUNCA)

    banderas = strategy.draw_neutralisations(modelo, np.random.default_rng(2), SORTEOS)

    assert (banderas == strategy.GREEN).all()


@pytest.mark.parametrize("tipo", list(TIPOS), ids=list(TIPOS))
def test_apagar_un_tipo_lo_saca_del_sorteo(tipo: str) -> None:
    """DADO un tipo con peso cero, su código no aparece y los otros sí pueden.

    Cada tipo tiene su propia distribución de cantidad; esto comprueba que no se
    cruzaron los cables entre ellas, que es el error de copiar y pegar que este
    bucle de tres ramas invita a cometer.
    """
    codigo, campo = TIPOS[tipo]
    modelo = RaceModel(total_laps=VUELTAS, **{campo: NUNCA})

    banderas = strategy.draw_neutralisations(modelo, np.random.default_rng(3), SORTEOS)

    assert not (banderas == codigo).any()


def test_un_periodo_dura_las_vueltas_que_tiene_medidas() -> None:
    """DADO un solo auto de seguridad a mitad de carrera, ocupa ``sc_laps`` vueltas.

    La duración es dato medido, no supuesto, y esta prueba la lee del modelo: el
    día que la mediana de Zandvoort cambie, cambia con ella.
    """
    modelo = RaceModel(
        total_laps=VUELTAS,
        n_red=NUNCA,
        n_vsc=NUNCA,
        n_sc=SIEMPRE_UNO,
        sc_start_cuts_full=A_MITAD,
    )

    banderas = strategy.draw_neutralisations(modelo, np.random.default_rng(4), SORTEOS)

    bajo_sc = banderas == strategy.SC_FLAG
    assert bajo_sc.sum(axis=0).tolist() == [modelo.sc_laps] * SORTEOS
    arranque = int(round(0.5 * VUELTAS))
    assert np.flatnonzero(bajo_sc[:, 0]).tolist() == list(
        range(arranque, arranque + modelo.sc_laps)
    )


def test_donde_se_superponen_gana_la_mas_barata() -> None:
    """DADA una roja encima de un auto de seguridad, esa vuelta es de roja.

    Parar bajo bandera roja es gratis y parar bajo auto de seguridad no, así que
    la vuelta tiene que quedar marcada por lo que la parada de verdad costaría.
    El resto del período sigue siendo auto de seguridad: la roja no lo borra, lo
    pisa donde se superponen.
    """
    modelo = RaceModel(
        total_laps=VUELTAS,
        n_vsc=NUNCA,
        n_sc=SIEMPRE_UNO,
        n_red=SIEMPRE_UNO,
        sc_start_cuts_full=A_MITAD,
        red_start_cuts=A_MITAD,
    )

    banderas = strategy.draw_neutralisations(modelo, np.random.default_rng(5), SORTEOS)

    arranque = int(round(0.5 * VUELTAS))
    assert (banderas[arranque] == strategy.RED_FLAG).all()
    assert (banderas[arranque + 1 : arranque + modelo.sc_laps] == strategy.SC_FLAG).all()


def test_los_periodos_numeran_cada_corrida_de_la_misma_bandera() -> None:
    """DADA una carrera escrita a mano, cada corrida máxima recibe su propio número.

    Incluye el caso que una implementación descuidada junta en uno: dos banderas
    distintas pegadas, sin verde en el medio, son dos períodos.
    """
    carrera = np.array([[0], [0], [2], [2], [0], [1], [1], [1], [0], [3], [2]], dtype=np.int8)

    ids = strategy.period_ids(carrera)

    assert ids.ravel().tolist() == [0, 0, 1, 1, 0, 2, 2, 2, 0, 3, 4]


def test_las_vueltas_en_verde_van_en_cero() -> None:
    """DADO un sorteo cualquiera, período cero es exactamente "no hay bandera"."""
    banderas = strategy.draw_neutralisations(
        RaceModel(total_laps=VUELTAS), np.random.default_rng(6), SORTEOS
    )

    ids = strategy.period_ids(banderas)

    assert ids.shape == banderas.shape
    assert ((ids == 0) == (banderas == strategy.GREEN)).all()


def test_la_numeracion_coincide_con_contarlos_a_mano() -> None:
    """DADO un sorteo con los tres tipos activos, la numeración es la que se cuenta sola.

    Se compara contra una implementación ingenua, vuelta por vuelta, sobre
    carreras sorteadas de verdad: ahí aparecen las superposiciones y los períodos
    pegados que un ejemplo escrito a mano no se le ocurre poner.
    """
    banderas = strategy.draw_neutralisations(
        RaceModel(total_laps=VUELTAS), np.random.default_rng(7), SORTEOS
    )

    ids = strategy.period_ids(banderas)

    assert [periodos_de_referencia(banderas[:, i]) for i in range(SORTEOS)] == (ids.T.tolist())


def test_cada_sorteo_numera_desde_uno_y_sin_saltos() -> None:
    """DADA una carrera con períodos, se numeran 1, 2, 3… dentro de cada sorteo.

    La numeración indexa el sorteo de comportamiento compartido, así que un
    agujero o un arranque en cero haría que todo un período leyera la fila de
    relleno y se comportara como si no pasara nada.
    """
    banderas = strategy.draw_neutralisations(
        RaceModel(total_laps=VUELTAS), np.random.default_rng(8), SORTEOS
    )

    ids = strategy.period_ids(banderas)

    for sorteo in range(SORTEOS):
        presentes = sorted(set(ids[:, sorteo].tolist()) - {0})
        assert presentes == list(range(1, len(presentes) + 1))
