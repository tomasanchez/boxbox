"""La instrumentación opcional de la búsqueda: histograma de puestos e historia.

Lo que se prueba acá no es que la búsqueda encuentre un buen plan —eso lo miden
los scripts— sino que lo que hoy calcula y tira quede guardado cuando se lo pide,
y que pedirlo **no cambie nada**. Esa segunda parte es la que importa: el archivo
produce los resultados publicados en el informe.

El motor de DEAP no entra en la comparación de igualdad y el motivo conviene que
quede escrito: ``eaMuPlusLambda``, ``varOr`` y ``selTournament`` usan el
generador global de ``random``, que nadie siembra, así que **dos corridas de DEAP
con los mismos parámetros ya daban distinto antes de este cambio**. De DEAP se
prueba que el registro sale y tiene la forma correcta, no que se repita.
"""

from __future__ import annotations

import pytest

from boxbox_ml import strategy
from boxbox_ml.strategy import Car, Engine, Objective, Plan, RaceModel, Search, Stop, optimise

#: Una carrera chica: la prueba mide instrumentación, no calidad de la búsqueda.
MODEL = RaceModel(total_laps=40)
DRAWS = 120
GENERATIONS = 4
POPULATION = 12


@pytest.fixture
def focal() -> Car:
    """El auto que se optimiza."""
    return Car("FOC", "MEDIUM", 0, 0.0, strategy.ROLLING_MEDIAN_S, 0.0, 1, pace_s=0.3)


@pytest.fixture
def rivals() -> list[Car]:
    """Cuatro rivales, para que haya puesto de llegada y no sólo tiempo."""
    return [
        Car(f"R{i}", "MEDIUM", 0, 0.0, strategy.ROLLING_MEDIAN_S, 0.8 * i, 1, pace_s=0.1 * i)
        for i in range(4)
    ]


@pytest.fixture
def rival_plans(rivals: list[Car]) -> list[Plan]:
    """Un plan por rival: sorteados, no optimizados."""
    return [Plan((Stop(16 + i, "HARD"),)) for i, _ in enumerate(rivals)]


def search(
    focal: Car,
    rivals: list[Car],
    rival_plans: list[Plan],
    *,
    instrument: bool = False,
    engine: Engine = Engine.BUILTIN,
) -> Search:
    """Correr la búsqueda con los parámetros chicos de esta prueba."""
    return optimise(
        focal,
        rivals,
        rival_plans,
        MODEL,
        objective=Objective.POSITION,
        engine=engine,
        population=POPULATION,
        generations=GENERATIONS,
        draws=DRAWS,
        seed=3,
        instrument=instrument,
    )


def test_por_omision_no_se_instrumenta(
    focal: Car, rivals: list[Car], rival_plans: list[Plan]
) -> None:
    """DADA una búsqueda con los parámetros de siempre, NO guarda nada de más."""
    # WHEN nadie pide la instrumentación
    found = search(focal, rivals, rival_plans)

    # THEN los dos campos nuevos vienen vacíos y no pesan
    assert found.position_histogram == {}
    assert found.history == ()


@pytest.mark.parametrize("engine", [Engine.BUILTIN, Engine.DEAP])
def test_el_histograma_suma_los_sorteos(
    focal: Car, rivals: list[Car], rival_plans: list[Plan], engine: Engine
) -> None:
    """DADA la instrumentación encendida, el histograma cubre todas las carreras."""
    # WHEN se pide la instrumentación
    found = search(focal, rivals, rival_plans, instrument=True, engine=engine)

    # THEN hay una carrera contada por sorteo, ni una más ni una menos
    assert sum(found.position_histogram.values()) == DRAWS
    # AND los puestos son puestos: del primero al último del campo
    assert set(found.position_histogram) <= set(range(1, len(rivals) + 2))
    assert list(found.position_histogram) == sorted(found.position_histogram)


@pytest.mark.parametrize("engine", [Engine.BUILTIN, Engine.DEAP])
def test_el_histograma_es_el_de_la_posicion_informada(
    focal: Car, rivals: list[Car], rival_plans: list[Plan], engine: Engine
) -> None:
    """DADO el histograma, su media es la misma ``mean_position`` que ya se informaba.

    Es la prueba de que sale del MISMO array de posiciones y no de una corrida
    nueva: otra corrida daría otras carreras y otro número.
    """
    # WHEN se instrumenta la búsqueda
    found = search(focal, rivals, rival_plans, instrument=True, engine=engine)

    # THEN reconstruir la media desde el histograma da la media informada
    total = sum(place * count for place, count in found.position_histogram.items())
    assert total / DRAWS == pytest.approx(found.mean_position)


@pytest.mark.parametrize("engine", [Engine.BUILTIN, Engine.DEAP])
def test_la_historia_tiene_una_generacion_mas(
    focal: Car, rivals: list[Car], rival_plans: list[Plan], engine: Engine
) -> None:
    """DADA la instrumentación, hay un registro por generación más la sembrada."""
    # WHEN se instrumenta la búsqueda en cualquiera de los dos motores
    found = search(focal, rivals, rival_plans, instrument=True, engine=engine)

    # THEN la generación cero es la población sembrada y después va una por ronda
    assert len(found.history) == GENERATIONS + 1
    assert [gen.index for gen in found.history] == list(range(GENERATIONS + 1))

    for gen in found.history:
        # AND cada generación reparte la población entera entre cantidades de parada
        assert sum(gen.stop_distribution.values()) == pytest.approx(1.0)
        assert set(gen.stop_distribution) <= set(range(5))  # el tope es max_stops
        assert isinstance(gen.best, float)


def test_la_ultima_generacion_es_la_que_eligio_el_plan(
    focal: Car, rivals: list[Car], rival_plans: list[Plan]
) -> None:
    """DADA la historia, su última entrada describe la población final."""
    # WHEN se instrumenta el motor propio, que es el determinista
    found = search(focal, rivals, rival_plans, instrument=True)

    # THEN coincide con lo que la búsqueda informa de esa misma población
    assert found.history[-1].stop_distribution == found.stop_distribution
    assert found.history[-1].best == found.score_in_sample

    # AND la búsqueda nunca empeora, porque el motor propio es elitista: el mejor
    # cuarto pasa entero a la generación siguiente. DEAP no da esa garantía —
    # selecciona por torneo sobre padres e hijos y el mejor se puede perder.
    mejores = [gen.best for gen in found.history]
    assert mejores == sorted(mejores)


def test_instrumentar_no_cambia_el_resultado(
    focal: Car, rivals: list[Car], rival_plans: list[Plan]
) -> None:
    """DADOS los mismos parámetros, instrumentar devuelve EXACTAMENTE el mismo plan.

    La instrumentación no puede tocar el orden en que se consume el generador
    aleatorio: si lo tocara, correría otro Monte Carlo y movería cifras ya
    publicadas.
    """
    # WHEN se corre la misma búsqueda con y sin instrumentar
    apagada = search(focal, rivals, rival_plans)
    encendida = search(focal, rivals, rival_plans, instrument=True)

    # THEN todo lo que ya se informaba da igual, al bit
    assert encendida.best == apagada.best
    assert encendida.score == apagada.score
    assert encendida.score_in_sample == apagada.score_in_sample
    assert encendida.stop_distribution == apagada.stop_distribution
    assert encendida.mean_position == apagada.mean_position
    assert encendida.sd_position == apagada.sd_position
    assert encendida.mean_points == apagada.mean_points
    assert encendida.decision_value == apagada.decision_value
    assert encendida.alternatives == apagada.alternatives


@pytest.mark.parametrize("engine", [Engine.BUILTIN, Engine.DEAP])
def test_cada_generacion_trae_el_plan_que_saco_ese_valor(
    focal: Car, rivals: list[Car], rival_plans: list[Plan], engine: Engine
) -> None:
    """Sin el plan, el registro muestra que la búsqueda mejora pero no qué encontró.

    Se verifica lo que de verdad importa, que no es que el campo esté lleno sino
    que el plan anotado sea **el que saca ese valor**: la última generación es la
    que eligió el plan final, así que tienen que coincidir, y su valor tiene que
    ser el puntaje en muestra que la búsqueda reporta.
    """
    found = search(focal, rivals, rival_plans, instrument=True, engine=engine)

    assert all(one.best_plan is not None for one in found.history)
    assert found.history[-1].best_plan.stops == found.best.stops
    assert found.history[-1].best == pytest.approx(found.score_in_sample)
    # El mejor nunca empeora: la élite sobrevive a cada generación.
    valores = [one.best for one in found.history]
    assert valores == sorted(valores)
