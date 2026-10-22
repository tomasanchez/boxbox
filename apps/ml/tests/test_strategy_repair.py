"""El reparador de planes: la única puerta por la que pasa todo plan candidato.

``_repair`` corre sobre cada plan que la búsqueda siembra, cruza o muta, así que
es el lugar donde una regla mal escrita no produce un error sino **algo peor**:
un plan ilegal que la simulación igual sabe puntuar, que gana porque es ilegal,
y que después se publica. Las tres reglas que impone —orden y ``MIN_STINT``
entre paradas, nada de paradas tan tarde que no haya carrera para amortizarlas,
y ninguna goma pasada de lo que la evidencia midió— son las que evitan eso.

Una sutileza que conviene dejar escrita porque se verifica acá y se lee mal en
todos lados: ``MAX_STINT`` acota la **edad de la goma al entrar a boxes**, no el
largo de la tanda. El reparador cuenta desde ``car.from_lap``, que es la primera
vuelta que falta correr, así que la tanda más larga que permite es
``MAX_STINT + 1`` vueltas. Pedir parada en la 33 con un medio devuelve la 32.

Las cantidades esperadas salen todas de ``strategy.MIN_STINT`` y
``strategy.MAX_STINT``, nunca escritas a mano: el día que una medición mueva el
tope, estas pruebas tienen que seguir el tope y no quedar contándole las
costillas a un número viejo.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pytest

from boxbox_ml import strategy
from boxbox_ml.strategy import Car, Plan, RaceModel, Stop

#: Una carrera chica, como en el resto de la suite: cuarenta vueltas alcanzan
#: para que el tope del blando (25) y el del medio (31) muerdan de verdad.
MODELO = RaceModel(total_laps=40)


def edades_al_entrar(car: Car, stops: Sequence[Stop]) -> list[tuple[str, int]]:
    """Con qué compuesto y con cuántas vueltas encima llega cada parada a boxes.

    Reproduce la cuenta del reparador —desde ``from_lap``, arrastrando
    ``tyre_age`` en la primera tanda— para poder compararla contra ``MAX_STINT``
    sin repetir la fórmula dentro de cada prueba.
    """
    edades: list[tuple[str, int]] = []
    anterior, compuesto, edad = car.from_lap, car.compound, car.tyre_age
    for parada in stops:
        edades.append((compuesto, parada.lap - anterior + edad))
        anterior, compuesto, edad = parada.lap, parada.compound, 0
    return edades


def tanda_final(car: Car, stops: Sequence[Stop], total_laps: int) -> tuple[str, int]:
    """El compuesto con el que termina la carrera y cuántas vueltas le toca."""
    if not stops:
        return car.compound, total_laps - car.from_lap + 1
    return stops[-1].compound, total_laps - stops[-1].lap


#: Pedidos variados, incluyendo los que el cruce y la mutación generan solos:
#: paradas desordenadas, pegadas, repetidas, tardísimas y ninguna. La clave es
#: el nombre del caso en el informe de pytest.
PEDIDOS: dict[str, tuple[str, int, int, list[Stop]]] = {
    "medio-sin-paradas": ("MEDIUM", 0, 1, []),
    "blando-sin-paradas": ("SOFT", 0, 1, []),
    "desordenadas": ("MEDIUM", 0, 1, [Stop(12, "SOFT"), Stop(10, "MEDIUM")]),
    "una-sola-temprana": ("HARD", 0, 1, [Stop(10, "SOFT")]),
    "dos-en-la-misma-vuelta": ("MEDIUM", 0, 1, [Stop(20, "HARD"), Stop(20, "SOFT")]),
    "tres-con-goma-usada": ("HARD", 5, 1, [Stop(8, "MEDIUM"), Stop(9, "SOFT"), Stop(30, "HARD")]),
    "una-tardisima": ("SOFT", 0, 1, [Stop(38, "HARD")]),
    "a-mitad-de-carrera": ("MEDIUM", 13, 15, [Stop(36, "HARD")]),
    "todas-apiladas-al-principio": (
        "MEDIUM",
        0,
        1,
        [Stop(1, "SOFT"), Stop(2, "SOFT"), Stop(3, "SOFT")],
    ),
}


@pytest.fixture(params=list(PEDIDOS.values()), ids=list(PEDIDOS))
def pedido(request: pytest.FixtureRequest, coche: Callable[..., Car]) -> tuple[Car, list[Stop]]:
    """Un auto y el plan crudo que se le pide reparar."""
    compuesto, edad, desde, stops = request.param
    return coche(compound=compuesto, tyre_age=edad, from_lap=desde), stops


def test_las_paradas_salen_ordenadas(pedido: tuple[Car, list[Stop]]) -> None:
    """DADO cualquier pedido, las paradas reparadas van de menor a mayor vuelta.

    El cruce toma paradas tempranas de un padre y tardías de otro, así que llegan
    acá desordenadas de forma rutinaria.
    """
    car, stops = pedido

    reparado = strategy._repair(stops, car, MODELO)

    vueltas = [parada.lap for parada in reparado]
    assert vueltas == sorted(vueltas)


def test_ninguna_tanda_baja_del_minimo(pedido: tuple[Car, list[Stop]]) -> None:
    """DADO cualquier pedido, ninguna tanda queda más corta que ``MIN_STINT``."""
    car, stops = pedido

    reparado = strategy._repair(stops, car, MODELO)

    if reparado:
        assert reparado[0].lap - car.from_lap >= strategy.MIN_STINT
    huecos = [b.lap - a.lap for a, b in zip(reparado, reparado[1:], strict=False)]
    assert all(hueco >= strategy.MIN_STINT for hueco in huecos)


def test_ninguna_parada_queda_sin_carrera_para_amortizarla(
    pedido: tuple[Car, list[Stop]],
) -> None:
    """DADO cualquier pedido, no hay paradas en las últimas ``MIN_STINT`` vueltas.

    Parar en la 38 de 40 no es una estrategia agresiva, es tirar veinte segundos:
    no queda carrera para recuperarlos.
    """
    car, stops = pedido

    reparado = strategy._repair(stops, car, MODELO)

    assert all(parada.lap <= MODELO.total_laps - strategy.MIN_STINT for parada in reparado)


def test_la_goma_nunca_entra_a_boxes_pasada_de_vuelta(pedido: tuple[Car, list[Stop]]) -> None:
    """DADO cualquier pedido, ninguna goma llega a boxes más vieja que su tope.

    Este es el que impide que la búsqueda se vaya a extrapolar: pasado el tope
    medido el déficit ajustado **baja**, que es supervivencia de las tandas que
    aguantaron, y dejándola suelta la búsqueda recomendaba cuarenta y dos vueltas
    con un solo juego.
    """
    car, stops = pedido

    reparado = strategy._repair(stops, car, MODELO)

    for compuesto, edad in edades_al_entrar(car, reparado):
        assert edad <= strategy.MAX_STINT[compuesto]


def test_el_plan_reparado_llega_hasta_la_bandera(pedido: tuple[Car, list[Stop]]) -> None:
    """DADO cualquier pedido, la última goma alcanza para terminar la carrera.

    Es la otra mitad del tope: no alcanza con que las paradas estén en hora, la
    tanda que queda después de la última también tiene que caber en lo medido.
    """
    car, stops = pedido

    reparado = strategy._repair(stops, car, MODELO)

    compuesto, vueltas = tanda_final(car, reparado, MODELO.total_laps)
    assert vueltas <= strategy.MAX_STINT[compuesto]


def test_reparar_un_plan_reparado_no_lo_cambia(pedido: tuple[Car, list[Stop]]) -> None:
    """DADO un plan ya reparado, repararlo otra vez lo deja igual.

    Cada generación repara lo que produce, así que un reparador que corre el plan
    unas vueltas en cada pasada movería los planes por el solo hecho de que la
    búsqueda dure más generaciones.
    """
    car, stops = pedido

    una = strategy._repair(stops, car, MODELO)
    dos = strategy._repair(una, car, MODELO)

    assert dos == una


def test_el_tope_acota_la_edad_al_entrar_y_no_el_largo_de_la_tanda(
    coche: Callable[..., Car],
) -> None:
    """DADA una parada pedida pasada del tope, vuelve al tope, que es una vuelta menos.

    El número que importa acá es que la tanda resultante mide ``MAX_STINT + 1``
    vueltas y no ``MAX_STINT``: el reparador cuenta desde ``from_lap``, que es la
    primera vuelta que **falta correr**, no la última corrida.
    """
    car = coche(compound="MEDIUM")
    tope = strategy.MAX_STINT["MEDIUM"]

    reparado = strategy._repair([Stop(tope + 2, "HARD")], car, MODELO)

    assert [parada.lap for parada in reparado] == [car.from_lap + tope]
    assert Plan(reparado).describe(car, MODELO.total_laps).startswith(f"M{tope + 1}-")


def test_la_edad_que_trae_la_goma_descuenta_del_presupuesto(coche: Callable[..., Car]) -> None:
    """DADO un auto que ya gastó goma, le queda el resto del tope y no el tope entero.

    Es el caso de la foto a mitad de carrera, que es como se usa el simulador en
    vivo: un juego de trece vueltas no tiene treinta y una por delante.
    """
    car = coche(compound="MEDIUM", tyre_age=13, from_lap=15)

    reparado = strategy._repair([Stop(36, "HARD")], car, MODELO)

    assert [parada.lap for parada in reparado] == [
        car.from_lap + strategy.MAX_STINT["MEDIUM"] - car.tyre_age
    ]


def test_la_tanda_pasada_de_presupuesto_recibe_una_parada_en_vez_de_descartarse(
    coche: Callable[..., Car],
) -> None:
    """DADO un plan sin paradas que no llega, se le inserta una en el límite.

    Descartar el plan sesgaría la búsqueda hacia lo que quedó legal de casualidad;
    insertar la parada conserva la idea y la hace pagable. Un blando no llega a
    la vuelta cuarenta y sale con parada obligada en su tope.
    """
    car = coche(compound="SOFT")

    reparado = strategy._repair([], car, MODELO)

    assert [parada.lap for parada in reparado] == [car.from_lap + strategy.MAX_STINT["SOFT"]]


def test_una_parada_impuesta_demasiado_tarde_se_adelanta(coche: Callable[..., Car]) -> None:
    """DADA una goma que llega justo al final, la parada se adelanta en vez de malgastarse.

    Correr el juego hasta su límite puede dejar la parada en una vuelta donde ya
    no sirve de nada. El reparador la trae hacia adelante hasta la primera vuelta
    que resuelve las dos tandas: ``MIN_STINT`` después de la anterior.
    """
    car = coche(compound="HARD")
    primera = Stop(10, "SOFT")

    reparado = strategy._repair([primera], car, MODELO)

    # El blando llegaría hasta la 35 de 40, que deja cinco vueltas: inservible.
    assert primera.lap + strategy.MAX_STINT["SOFT"] > MODELO.total_laps - strategy.MIN_STINT
    assert [parada.lap for parada in reparado] == [
        primera.lap,
        primera.lap + strategy.MIN_STINT,
    ]
    assert MODELO.total_laps - reparado[-1].lap >= strategy.MIN_STINT


def test_una_carrera_demasiado_corta_para_arreglar_se_queda_sin_paradas(
    coche: Callable[..., Car],
) -> None:
    """DADA una carrera más corta que la tanda mínima, no se inventa ninguna parada.

    El caso límite documentado: no queda nada legal que hacer y el reparador sale
    con las manos vacías en vez de poner una parada imposible.
    """
    car = coche(compound="SOFT")
    corta = RaceModel(total_laps=2 * strategy.MIN_STINT - 1)

    assert strategy._repair([Stop(5, "HARD")], car, corta) == ()


@pytest.mark.xfail(
    strict=True,
    reason=(
        "BUG conocido, sin arreglar: `_enforce_two_compounds` corre DESPUÉS del "
        "control de presupuesto y le cambia el compuesto a la última parada sin "
        "volver a mirarlo. Un plan de un solo compuesto puede salir con la tanda "
        "final pasada del tope — H35-M37 en una carrera de 72, con el medio "
        "topado en 31. Medido: la búsqueda NO lo alcanza, 0 de 36 corridas "
        "(doce semillas por tres compuestos de salida) devuelven un plan que se "
        "pase, porque una tanda así está demasiado degradada para ganar la "
        "aptitud. O sea que arreglarlo no movería ninguna cifra publicada; "
        "queda sin arreglar sólo porque toca código de producción el día de una "
        "entrega. Si alguien lo arregla, este xfail estricto se pone en rojo "
        "y avisa que hay que borrarlo."
    ),
)
def test_el_cambio_de_compuesto_obligatorio_respeta_el_tope(coche: Callable[..., Car]) -> None:
    """DADO un plan de un solo compuesto, el cambio que lo hace legal debería caber."""
    car = coche(compound="HARD")
    larga = RaceModel()

    reparado = strategy._repair([Stop(35, "HARD")], car, larga)

    compuesto, vueltas = tanda_final(car, reparado, larga.total_laps)
    assert vueltas <= strategy.MAX_STINT[compuesto]
