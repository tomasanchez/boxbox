"""El mismo algoritmo genético, escrito sobre DEAP.

DEAP es la herramienta que recomienda la cátedra para la Unidad 3, y el port es
deliberadamente un **re-alojamiento, no un rediseño**: las semillas, la aptitud
con números aleatorios comunes, el reparador, la cruza y la mutación son
exactamente los mismos objetos que usa :func:`boxbox_ml.strategy.optimise`. Lo
único que cambia es el bucle de evolución, que pasa a ser
``algorithms.eaMuPlusLambda``. Eso es lo que hace comparables a los dos motores:
``scripts/deap_vs_builtin.py`` los corre sobre los mismos problemas.

Lo que DEAP aporta de verdad:

* los operadores quedan **registrados y nombrados** en un ``Toolbox``, que es la
  forma en que se espera leer un AG;
* ``HallOfFame``, ``Statistics`` y ``Logbook`` salen gratis, y con ellos el
  registro generación a generación que antes no existía — hoy es el que alimenta
  ``Search.history`` cuando se pide, sin inventar nada: son los números que el
  propio ``eaMuPlusLambda`` anota;
* deja la puerta abierta a multiobjetivo (``selNSGA2``) sin reescribir nada, que
  es la forma natural de mirar tiempo contra riesgo.

## Tres cosas que hay que saber para que esto sea correcto

**El individuo es de largo variable.** Un plan tiene una a cuatro paradas, así que
los operadores de caja de DEAP (``cxTwoPoint`` y compañía) no sirven: asumen largo
fijo y no saben nada de las restricciones. Se registran los propios, que ya
reparan.

**El caché de aptitud de DEAP acá es correcto, y no era obvio.** DEAP no reevalúa
un individuo cuyo ``fitness.valid`` sigue en pie, lo cual es un error clásico con
aptitudes ruidosas de Monte Carlo. Pero la nuestra usa números aleatorios comunes
con semilla fija, así que **para un plan dado la aptitud es determinística** y el
caché es legítimo. Si alguna vez se saca la semilla fija, hay que desactivarlo.

**El reparador manda.** Toda cruza y toda mutación devuelven un plan ya reparado,
porque las restricciones —tandas mínimas, vida de la goma, B6.3.8— no son
preferencias: un plan ilegal es una descalificación, no un plan malo.
"""

from __future__ import annotations

import random
from collections.abc import Callable

import numpy as np
from deap import algorithms, base, creator, tools

from boxbox_ml.strategy import (
    Car,
    Generation,
    Plan,
    RaceModel,
    _crossover,
    _mutate,
    _stop_shares,
)

#: Probabilidad de cruza y de mutación en ``eaMuPlusLambda``. Tienen que sumar
#: como mucho uno: DEAP aplica una o la otra a cada hijo, nunca las dos.
CXPB = 0.6
MUTPB = 0.4

#: Tamaño del torneo de selección. Tres es el estándar y mantiene presión sin
#: matar la diversidad, que acá importa porque el espacio es chico y engañoso.
TOURNAMENT = 3

_CREATED = False


def _ensure_types() -> None:
    """Declarar los tipos de DEAP una sola vez.

    ``creator.create`` escribe en un registro global del módulo y protesta si se
    la llama dos veces con el mismo nombre, cosa que pasa en cuanto un script
    corre más de una búsqueda.
    """
    global _CREATED
    if _CREATED:
        return
    creator.create("FitnessMax", base.Fitness, weights=(1.0,))
    creator.create("Individual", list, fitness=creator.FitnessMax)
    _CREATED = True


def _build_toolbox(
    fitness: Callable[[Plan], float],
    car: Car,
    model: RaceModel,
    rng: np.random.Generator,
) -> base.Toolbox:
    """Registrar aptitud, cruza, mutación y selección sobre un ``Toolbox``."""
    _ensure_types()
    toolbox = base.Toolbox()

    def evaluate(individual: list) -> tuple[float]:
        return (fitness(Plan(tuple(individual))),)

    def mate(first: list, second: list) -> tuple[list, list]:
        # _crossover devuelve UN hijo; eaMuPlusLambda espera dos, así que se cruza
        # en los dos sentidos. No es un parche: la cruza no es simétrica, porque
        # el reparador resuelve los choques hacia adelante desde el primer padre.
        left = _crossover(Plan(tuple(first)), Plan(tuple(second)), car, model, rng)
        right = _crossover(Plan(tuple(second)), Plan(tuple(first)), car, model, rng)
        return _as_individual(left), _as_individual(right)

    def mutate(individual: list) -> tuple[list]:
        return (_as_individual(_mutate(Plan(tuple(individual)), car, model, rng)),)

    toolbox.register("evaluate", evaluate)
    toolbox.register("mate", mate)
    toolbox.register("mutate", mutate)
    toolbox.register("select", tools.selTournament, tournsize=TOURNAMENT)
    return toolbox


def _as_individual(plan: Plan):
    """Envolver un plan en el tipo de individuo de DEAP."""
    _ensure_types()
    return creator.Individual(list(plan.stops))


def _shares_of(individuals: list) -> tuple[tuple[int, float], ...]:
    """El reparto de paradas de una población, **como pares y no como diccionario**.

    ``Logbook.record`` trata cualquier valor que sea un ``dict`` como un capítulo
    anidado y lo vuelve a desarmar en argumentos por nombre, así que un reparto
    ``{1: 0.5, ...}`` lo hace explotar con claves que son enteros. Se anota como
    pares y el diccionario se rearma al leer.
    """
    return tuple(_stop_shares([Plan(tuple(individual)) for individual in individuals]).items())


def _champion_of(individuals: list) -> tuple:
    """Las paradas del mejor individuo de la población.

    Se anota como tupla de :class:`~boxbox_ml.strategy.Stop` y no como texto,
    porque el registro tiene que servir para reconstruir el plan y no sólo para
    mostrarlo. Un ``dict`` acá volvería a romper ``Logbook.record``; una tupla de
    dataclasses la anota tal cual.
    """
    best = max(individuals, key=lambda individual: individual.fitness.values[0])
    return tuple(best)


def _stop_statistics() -> tools.Statistics:
    """Estadística que mira el individuo entero y no su aptitud.

    El reparto de paradas no sale del número de aptitud sino del plan, así que
    necesita su propia clave. Es la razón de que el registro use
    ``MultiStatistics``: es la forma en que DEAP junta dos claves distintas en un
    mismo ``Logbook``, una por capítulo.
    """
    statistics = tools.Statistics()
    statistics.register("shares", _shares_of)
    statistics.register("champion", _champion_of)
    return statistics


def _history(logbook: tools.Logbook) -> tuple[Generation, ...]:
    """Traducir el ``Logbook`` de DEAP al registro por generación de la búsqueda.

    ``eaMuPlusLambda`` anota ``ngen + 1`` veces —la primera es la población
    sembrada, antes de la primera selección— que es exactamente el convenio del
    motor propio, así que los dos registros se leen igual y son comparables.
    """
    return tuple(
        Generation(
            index=int(gen),
            best=float(best),
            stop_distribution=dict(shares),
            best_plan=Plan(tuple(champion)),
        )
        for gen, best, shares, champion in zip(
            logbook.select("gen"),
            logbook.chapters["fitness"].select("max"),
            logbook.chapters["stops"].select("shares"),
            logbook.chapters["stops"].select("champion"),
            strict=True,
        )
    )


def evolve(
    scored: list[tuple[Plan, float]],
    fitness: Callable[[Plan], float],
    car: Car,
    model: RaceModel,
    rng: np.random.Generator,
    population: int,
    generations: int,
    history: bool = False,
) -> tuple[list[tuple[Plan, float]], tuple[Generation, ...]]:
    """Correr la evolución con DEAP y devolver la población final puntuada.

    La firma es la misma que la de :func:`boxbox_ml.strategy._evolve`, para que
    ``optimise`` pueda elegir uno u otro sin saber nada del bucle.

    Args:
        scored: Población inicial ya evaluada — las mismas semillas heurísticas
            que usa el motor propio, porque sembrar al azar no funciona acá.
        fitness: La aptitud, con números aleatorios comunes.
        car: El auto que se optimiza.
        model: Distribuciones medidas de la carrera.
        rng: Generador, compartido con los operadores.
        population: Individuos por generación.
        generations: Rondas de selección.
        history: Anotar cada generación. Acá el registro es **real y no una
            equivalencia inventada**: sale del ``Logbook`` que ``eaMuPlusLambda``
            ya devolvía y que hasta ahora se descartaba, con el máximo de aptitud
            que la ``Statistics`` de siempre calcula y el reparto de paradas
            agregado como segundo capítulo. Apagado por omisión.

    Returns:
        La población final como pares ``(plan, aptitud)``, ordenada como venga, y
        el registro por generación, vacío si no se pidió.
    """
    # **Sembrar el generador global de ``random``, que DEAP usa y nunca sembró.**
    #
    # ``eaMuPlusLambda``, ``varOr`` y ``selTournament`` no toman un generador: van
    # directo al módulo ``random``. Sin esto el motor DEAP era **no
    # determinístico**, y no de forma sutil — dos llamadas seguidas con los
    # mismos parámetros daban planes distintos, y la comparación de
    # ``scripts/deap_vs_builtin.py`` medía en parte esa aleatoriedad suelta en vez
    # de la diferencia entre los dos bucles.
    #
    # La semilla sale del propio ``rng`` que ya comparte ``optimise``, así que dos
    # búsquedas con el mismo ``seed`` dan el mismo resultado sin agregar un
    # parámetro nuevo. Se toca el estado global del proceso, que es feo, pero es
    # la única superficie que DEAP ofrece.
    random.seed(int(rng.integers(0, 2**32)))

    toolbox = _build_toolbox(fitness, car, model, rng)

    individuals = []
    for plan, value in scored:
        individual = _as_individual(plan)
        # La semilla ya se evaluó en optimise; se le pasa el valor para no pagar
        # la evaluación dos veces.
        individual.fitness.values = (value,)
        individuals.append(individual)

    fitness_stats = tools.Statistics(lambda ind: ind.fitness.values[0])
    fitness_stats.register("max", np.max)
    fitness_stats.register("avg", np.mean)
    # Sin registro se le pasa la misma Statistics de siempre, tal cual: el motor
    # no se entera de que la instrumentación existe.
    statistics = (
        tools.MultiStatistics(fitness=fitness_stats, stops=_stop_statistics())
        if history
        else fitness_stats
    )
    hall = tools.HallOfFame(1)

    final, logbook = algorithms.eaMuPlusLambda(
        individuals,
        toolbox,
        mu=population,
        lambda_=population,
        cxpb=CXPB,
        mutpb=MUTPB,
        ngen=generations,
        stats=statistics,
        halloffame=hall,
        verbose=False,
    )
    scored_final = [(Plan(tuple(individual)), individual.fitness.values[0]) for individual in final]
    return scored_final, (_history(logbook) if history else ())
