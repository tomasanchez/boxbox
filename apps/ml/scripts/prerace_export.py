"""Todo lo que la vista pre-carrera va a mostrar, en un JSON y de una sola corrida.

La pregunta de la vista no es la de ``prerace_strategy.py``. Ahí se pregunta cuál
es la forma más rápida de cubrir la distancia, que es un problema de un solo auto
y no necesita al campo. Acá se pregunta **dónde va a terminar cada uno**, y eso
sin rivales no existe: un puesto de llegada es una comparación. Por eso cada auto
se optimiza desde la vuelta 1 contra todos los demás, cada uno con un plan
sorteado.

Lo que sale es un archivo y no un servicio. La búsqueda tarda diez minutos —tres
corridas por auto, una por compuesto de salida—, la web es estática, y el patrón
ya está: ``strategy_search.py --out`` genera el JSON que ``apps/web/src/plans.ts``
consume. Ver ADR-002.

## Las cuatro probabilidades

El pedido hablaba de «% de éxito». Ese número no existía: lo único parecido que la
búsqueda calculaba era ``stop_distribution``, que mide la confianza del
OPTIMIZADOR sobre cuántas paradas, no el resultado de la carrera. Mostrarla como
éxito sería mentir.

Lo que sí existe son las carreras sorteadas con el plan ganador, que ahora quedan
contadas en ``position_histogram``. De ese histograma salen las cuatro
probabilidades que se exportan —ganar, podio, zona de puntos y mejorar la
largada— y el lector elige la que le importa según desde dónde larga su piloto.
Son cuentas sobre las **mismas** carreras que eligieron el plan, no sobre otras
nuevas. Ver ADR-001 y ADR-003.

## Con qué larga cada uno

Largar en duro, en medio o en blando es una decisión, y hasta acá se regalaba:
``START_COMPOUND = "MEDIUM"`` para los veintidós. Que la elección pesa ya estaba
medido —en ``prerace_strategy.py``, con el auto de referencia, el duro da 89,6 s
contra 90,1 del medio— y una grilla de un solo compuesto además no existe: en las
catorce fechas de 2026 conviven entre uno y tres compuestos de salida por carrera.

Ahora el auto focal **elige**: la búsqueda entera se corre una vez por compuesto
de salida, y las tres quedan en el JSON y no sólo la ganadora. Elegir entre ellas
tiene una trampa que conviene nombrar. ``Objective.ADAPTIVE`` resuelve a
``points``, ``in_points`` o ``position`` según lo que el auto tenga al alcance, y
puede resolver **distinto para cada compuesto de salida**: tres puntajes en tres
unidades no se ordenan, y quedarse con el mayor sería comparar peras con manzanas.
Por eso la comparación se hace con una vara común, decidida una vez por auto y
sobre las tres corridas juntas — puntos esperados si alguna deja los puntos al
alcance, puesto esperado si ninguna. Las dos salen del mismo
``position_histogram`` del que salen las cuatro probabilidades, así que son
cuentas sobre las mismas carreras que eligieron cada plan.

Los rivales no eligen: su compuesto de salida se **sortea** del reparto medido
por banda de grilla (ver :data:`START_COMPOUND_SHARES`), con su propia semilla.

Y el auto focal, cuando aparece como rival de los otros veintiuno, lleva el
compuesto **sorteado** y no el optimizado. Es la misma razón por la que sus
planes también se sortean: veintiún rivales todos optimizados describen una
carrera que nadie corrió.

## Qué es medido y qué es supuesto

Medido: el hueco de clasificación de cada auto (sesión real, ver ADR-004), el
desgaste por compuesto de Zandvoort, la pérdida de boxes, las tasas de
neutralización, el costo del tráfico, el ruido de vuelta, la conversión de hueco
de clasificación a ritmo de carrera y el reparto del compuesto de salida por
banda de grilla.

Supuesto, y declarado también dentro del JSON:

* **Los planes de los rivales.** Se sortean con ``_random_plan``, que reparte
  uniforme entre cero y tres paradas. La distribución **medida** de paradas
  reales es otra —0,151 / 0,493 / 0,192 / 0,164, la que usa
  ``strategy_search.py``— así que este sorteo le da más peso del real a los planes
  de tres paradas. Darles a todos el óptimo sería peor: describiría una carrera
  que nadie corrió.

## Lo que estos números NO son

Una posición proyectada contra rivales que no reaccionan. El auto focal paga
tráfico y los rivales no —cobrárselo pediría las trazas de sus propios vecinos, y
eso es circular—, así que cada auto se proyecta a sí mismo un poco pesimista. El
efecto se ve en la suma de P(ganar) sobre el campo, que el script informa al
final: si diera exactamente 1, las búsquedas serían todas la misma carrera, y no
lo son.

Y no hay abandonos. El simulador no modela confiabilidad ni error de piloto más
allá del ruido de vuelta medido, así que los dos primeros de la parrilla salen con
P(zona de puntos) = 1,000 exacto: en las 1.200 carreras sorteadas no se caen
nunca. Eso es una afirmación sobre el modelo, no sobre la carrera, y la vista
tiene que decirlo antes que el número.

Correr con
``uv run python scripts/prerace_export.py --out ../../docs/research/prerace-zandvoort.json``.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from boxbox_ml import insights, qualifying, strategy
from boxbox_ml.qualifying import Entry, Qualifying
from boxbox_ml.strategy import (
    Car,
    Objective,
    Plan,
    RaceModel,
    Risk,
    Search,
    optimise,
    pace_from_qualifying,
)

#: Zandvoort 2026, fecha 12: el circuito que la web ya dibuja y uno de los que
#: tienen desgaste propio medido. Ver ADR-004.
YEAR, ROUND = 2026, 12

#: Vueltas de la carrera: las 72 que corrió la fecha 12 de 2026, que son también
#: el default de :class:`RaceModel`. Ver ``docs/research/case-zandvoort-2026.md``.
TOTAL_LAPS = 72

#: Las tres salidas que se le corren a cada auto focal, en el orden en que se
#: comparan. Es ``strategy.DRY``, del más duro al más blando; el orden sólo se
#: nota al desempatar, y ahí gana el más duro, que es el que menos supone sobre
#: cuántos juegos frescos le quedan al auto.
START_COMPOUNDS = strategy.DRY

#: Los cortes de grilla del reparto de abajo, por el último puesto de cada banda:
#: el frente, la media alta, la media baja y el fondo.
GRID_BANDS: tuple[tuple[int, str], ...] = (
    (5, "P1-5"),
    (10, "P6-10"),
    (15, "P11-15"),
    (22, "P16-22"),
)

#: Con qué compuesto larga cada banda de la grilla. **Medido**, no supuesto: el
#: compuesto del primer stint de cada piloto contra su puesto de largada, sobre
#: 294 pilotos-carrera de las catorce fechas de 2026 —66, 68, 66 y 94 por banda—,
#: descartando los siete que largaron con intermedio. Ver
#: ``scripts/start_compound.py``.
#:
#: ::
#:
#:                DURO   MEDIO   BLANDO
#:     P1-5      0,015   0,788   0,197
#:     P6-10     0,044   0,779   0,176
#:     P11-15    0,136   0,727   0,136
#:     P16-22    0,223   0,479   0,298
#:
#: El frente converge al medio y el fondo se dispersa: el que larga atrás no
#: tiene nada que perder y se desmarca, que es la misma lectura con la que
#: ``Risk.ADAPTIVE`` le da apetito de riesgo al auto que ya no tiene puntos que
#: proteger. Reemplaza al supuesto de que los veintidós largaban en medio, que
#: describía una grilla que no existe.
#:
#: Las filas están redondeadas a la milésima y dos de ellas suman 0,999, así que
#: el sorteo las normaliza. Renormalizar es preferible a retocar a mano un número
#: medido para que cierre.
START_COMPOUND_SHARES: dict[str, dict[str, float]] = {
    "P1-5": {"HARD": 0.015, "MEDIUM": 0.788, "SOFT": 0.197},
    "P6-10": {"HARD": 0.044, "MEDIUM": 0.779, "SOFT": 0.176},
    "P11-15": {"HARD": 0.136, "MEDIUM": 0.727, "SOFT": 0.136},
    "P16-22": {"HARD": 0.223, "MEDIUM": 0.479, "SOFT": 0.298},
}

#: Tope de paradas de un plan del buscador, que es el default de ``optimise``.
MAX_STOPS = 4

#: Tope de paradas de un plan sorteado de rival, igual que en
#: ``scripts/grid_position.py``.
RIVAL_MAX_STOPS = 3

#: Hasta qué puesto paga la zona de puntos, leído de la tabla de puntos en vez de
#: escrito acá: son diez lugares porque la tabla tiene diez.
IN_POINTS = len(strategy.POINTS)

#: Hasta qué puesto es podio.
PODIUM = 3

#: Cómo se imprime el objetivo resuelto. Los tres primeros caracteres no sirven:
#: «points» y «position» empiezan igual, y la columna que distingue al auto que
#: pelea puntos del que ya sólo pelea puestos sería ilegible.
OBJECTIVE_LABEL = {Objective.POINTS: "puntos", Objective.POSITION: "puesto"}

#: Cómo se imprime el compuesto de salida, en castellano como el resto de la
#: tabla. La inicial no alcanza: la usa ``Plan.describe`` para las tandas y verla
#: dos veces con dos significados en la misma fila se lee mal.
COMPOUND_LABEL = {"HARD": "duro", "MEDIUM": "medio", "SOFT": "blando"}

SEP = "=" * 96


@dataclass(frozen=True)
class Chances:
    """Las cuatro probabilidades del ADR-001, contadas sobre las mismas carreras.

    No hay una definición única de éxito, y por eso son cuatro: ganar significa
    algo distinto desde la pole que desde el fondo, y el que lee elige. Por
    construcción ``p_ganar <= p_podio <= p_puntos``, porque cada una acumula sobre
    la anterior. ``p_mejora`` no está en esa cadena, y para la pole vale cero por
    definición: no hay puesto mejor que el primero.
    """

    p_ganar: float
    p_podio: float
    p_puntos: float
    p_mejora: float


def chances(histogram: dict[int, int], grid_position: int) -> Chances:
    """Las cuatro probabilidades, a partir del histograma de puestos.

    Args:
        histogram: Puesto -> cantidad de carreras sorteadas que terminaron ahí,
            como lo devuelve una búsqueda instrumentada. Los valores suman los
            sorteos.
        grid_position: Desde dónde larga el auto, para saber qué es mejorar.

    Returns:
        Las cuatro probabilidades, cada una como fracción de las carreras
        sorteadas.
    """
    races = sum(histogram.values())

    def upto(place: int) -> float:
        """Fracción de carreras que terminaron en ``place`` o mejor."""
        return sum(count for finish, count in histogram.items() if finish <= place) / races

    return Chances(
        p_ganar=upto(1),
        p_podio=upto(PODIUM),
        p_puntos=upto(IN_POINTS),
        # Mejorar es terminar delante de donde se largó, o sea un puesto antes. El
        # puesto de largada es el de la clasificación: si alguien hubiera quedado
        # afuera del campo por no dejar tiempo, ese número tendría un agujero, y
        # el agujero es preferible a rearmar una grilla que no existió.
        p_mejora=upto(grid_position - 1),
    )


def expected_points(histogram: dict[int, int]) -> float:
    """Puntos de campeonato esperados, sobre las mismas carreras del histograma.

    Args:
        histogram: Puesto -> cantidad de carreras sorteadas que terminaron ahí.

    Returns:
        Media de puntos sobre las carreras sorteadas. Del undécimo en adelante no
        se suma nada, que es el acantilado del que vive toda la estrategia.

    Da lo mismo que ``Search.mean_points`` —el histograma cuenta ese mismo array
    de posiciones— y se recalcula acá igual, para que la vara con la que se
    eligió el compuesto y las cuatro probabilidades salgan del mismo lugar y el
    lector del JSON pueda rehacer las dos cuentas con lo que está publicado.
    """
    races = sum(histogram.values())
    scored = sum(
        strategy.POINTS[place - 1] * count
        for place, count in histogram.items()
        if place <= IN_POINTS
    )
    return scored / races


def expected_position(histogram: dict[int, int]) -> float:
    """Puesto de llegada esperado, sobre las mismas carreras del histograma.

    Args:
        histogram: Puesto -> cantidad de carreras sorteadas que terminaron ahí.

    Returns:
        Media del puesto de llegada. **Menor es mejor**, al revés que todo lo
        demás que este archivo compara. Da lo mismo que ``Search.mean_position``,
        por el mismo motivo que :func:`expected_points`.
    """
    races = sum(histogram.values())
    return sum(place * count for place, count in histogram.items()) / races


def grid_band(grid_position: int) -> str:
    """En qué banda de la grilla cae un puesto de largada.

    Args:
        grid_position: Puesto de largada, empezando en uno.

    Returns:
        El nombre de la banda, tal como lo indexa :data:`START_COMPOUND_SHARES`.
    """
    for last, band in GRID_BANDS:
        if grid_position <= last:
            return band
    # Una grilla más larga que la última banda cae igual en el fondo: el corte de
    # arriba dice hasta dónde se midió, no cuántos autos puede tener la parrilla.
    return GRID_BANDS[-1][1]


def draw_start_compound(grid_position: int, rng: np.random.Generator) -> str:
    """Sortea con qué compuesto larga un rival, del reparto medido de su banda.

    Args:
        grid_position: Desde dónde larga, que es lo único que elige la banda.
        rng: Generador del sorteo de compuestos. Va aparte del de los planes para
            que agregar este sorteo no corra el otro y mueva cifras ya publicadas.

    Returns:
        Uno de los tres compuestos secos.
    """
    shares = START_COMPOUND_SHARES[grid_band(grid_position)]
    weights = np.array([shares[compound] for compound in START_COMPOUNDS], dtype=float)
    return str(rng.choice(START_COMPOUNDS, p=weights / weights.sum()))


def field_from(quali: Qualifying, compounds: Sequence[str]) -> list[Car]:
    """Los autos en la grilla, uno por piloto con tiempo.

    Goma nueva, sin historia de desgaste propia —nadie corrió todavía, así que el
    encogimiento no tiene nada que encoger y la mediana de la población es el punto
    de partida honesto— y el ritmo declarado explícitamente desde el hueco de
    clasificación. Eso último es lo que hace que la búsqueda vea la posición de
    largada: sin ``pace_s``, un auto en la vuelta 1 no tiene historia de la cual
    inferir su ritmo y el modelo lo trata como si fuera tan rápido como la pole.

    Este es el campo tal como lo ven **los demás**: cada auto con su compuesto
    sorteado. El auto que se está optimizando entra por separado, con el compuesto
    que se le esté probando.

    Args:
        quali: La clasificación ya leída.
        compounds: Con qué larga cada piloto, en el mismo orden que las entradas.

    Returns:
        Un auto por piloto, en orden de grilla.
    """
    return [
        Car(
            code=entry.code,
            compound=compound,
            tyre_age=0,
            degradation_s=0.0,
            degradation_rate=strategy.ROLLING_MEDIAN_S,
            gap_leader_s=entry.gap_to_pole_s,
            from_lap=1,
            pace_s=pace_from_qualifying(entry.gap_to_pole_s),
        )
        for entry, compound in zip(quali.entries, compounds, strict=True)
    ]


@dataclass(frozen=True)
class StartOption:
    """Una de las tres salidas corridas para un auto, con su vara ya calculada.

    Existe porque elegir entre las tres necesita más que sus ``score``: con
    ``Objective.ADAPTIVE`` cada corrida puede haber resuelto a un objetivo
    distinto, y entonces los tres puntajes están en tres unidades. Acá cada
    corrida llega además con los dos números que sí se comparan entre sí, los dos
    contados sobre el mismo histograma de puestos.
    """

    compound: str
    car: Car
    found: Search
    odds: Chances
    #: Puntos de campeonato esperados de esta salida.
    points: float
    #: Puesto de llegada esperado. Menor es mejor.
    position: float


def start_option(compound: str, car: Car, found: Search, grid_position: int) -> StartOption:
    """Medir una corrida para poder compararla con las otras dos.

    Args:
        compound: Con qué compuesto se corrió.
        car: El auto que se optimizó, ya con ese compuesto.
        found: Lo que devolvió la búsqueda, instrumentada.
        grid_position: Desde dónde larga, para saber qué es mejorar.

    Returns:
        La salida con sus cuatro probabilidades, sus puntos y su puesto esperados.
    """
    return StartOption(
        compound=compound,
        car=car,
        found=found,
        odds=chances(found.position_histogram, grid_position),
        points=expected_points(found.position_histogram),
        position=expected_position(found.position_histogram),
    )


def choose(options: Sequence[StartOption]) -> tuple[StartOption, str]:
    """Con qué compuesto larga el auto, y con qué vara se decidió.

    El problema no es cuál corrida tiene mejor ``score``. ``Objective.ADAPTIVE``
    resuelve a puntos, a probabilidad de puntos o a posición según lo que el auto
    tenga al alcance, y puede resolver **distinto para cada compuesto de salida**:
    si largar en duro resuelve a puntos y en blando a posición, quedarse con el
    mayor de los dos sería comparar peras con manzanas.

    La vara se decide una vez por auto y mirando las tres corridas juntas. Si
    alguna deja los puntos al alcance —el mismo ``POINTS_FLOOR`` con el que
    ``optimise`` decide que el objetivo de puntos tiene gradiente— se compara por
    puntos esperados. Si ninguna, por puesto esperado, que es lo único que le
    queda al auto que no puntúa en ninguna de las tres.

    Args:
        options: Las tres salidas corridas, en el orden de :data:`START_COMPOUNDS`.

    Returns:
        La elegida y el nombre de la vara, ``"points"`` o ``"position"``. Un
        empate exacto lo rompe el orden de la lista, que va del más duro al más
        blando.
    """
    if max(option.points for option in options) >= strategy.POINTS_FLOOR:
        return max(options, key=lambda option: option.points), "points"
    return min(options, key=lambda option: option.position), "position"


@dataclass(frozen=True)
class CarRun:
    """Todo lo que se corrió para un auto: las tres salidas y la que ganó."""

    entry: Entry
    options: tuple[StartOption, ...]
    chosen: StartOption
    #: Con qué se compararon las tres, ``"points"`` o ``"position"``.
    yardstick: str
    #: El mismo auto tal como aparece en la carrera de los OTROS veintiuno:
    #: compuesto y plan sorteados, no optimizados. Si acá entrara su óptimo, cada
    #: auto se estaría enfrentando a veintiún rivales todos optimizados, que
    #: describe una carrera que nadie corrió.
    rival: Car
    rival_plan: Plan


def race_meta(quali: Qualifying) -> dict:
    """Qué carrera es esta, y quién quedó afuera del campo."""
    return {
        "circuit": quali.circuit,
        "event": quali.event,
        "year": quali.year,
        "round": quali.round,
        "total_laps": TOTAL_LAPS,
        "pole_s": quali.pole_s,
        "cars": len(quali.entries),
        # Ya no hay un compuesto de salida de la carrera: cada auto tiene el suyo,
        # el elegido en ``cars[].start_compound`` y el sorteado en
        # ``cars[].rival_start_compound``.
        "excluded": [{"code": out.code, "reason": out.reason} for out in quali.excluded],
    }


def model_meta(model: RaceModel) -> dict:
    """Las distribuciones con las que se sortearon las carreras.

    Sale del modelo y no de una transcripción a mano: si mañana cambia una
    medición, cambia el JSON, y no hay dos versiones del mismo número.
    """
    return {
        "wear_median_s_lap": {
            compound: round(cuts[4], 4) for compound, cuts in model.wear_cuts.items()
        },
        "wear_cuts_s_lap": {
            compound: [round(value, 5) for value in cuts]
            for compound, cuts in model.wear_cuts.items()
        },
        "cut_probabilities": [float(cut) for cut in strategy.CUT_AT],
        "pit_loss_s": {
            "green": list(model.pit_loss_green),
            "vsc": list(model.pit_loss_vsc),
            "sc": list(model.pit_loss_sc),
            "red": list(model.pit_loss_red),
        },
        "neutralisations": {
            "n_red": list(model.n_red),
            "n_sc": list(model.n_sc),
            "n_vsc": list(model.n_vsc),
            "red_laps": model.red_laps,
            "sc_laps": model.sc_laps,
            "vsc_laps": model.vsc_laps,
        },
        "lap_noise_s": model.lap_noise_s,
        "max_stint_laps": dict(strategy.MAX_STINT),
        "traffic_gap_s": list(strategy.TRAFFIC_GAP_S),
        "traffic_penalty_s_lap": list(strategy.TRAFFIC_PENALTY_S),
        "quali_to_race_pace": strategy.QUALI_TO_RACE_PACE,
    }


def search_meta(args: argparse.Namespace) -> dict:
    """Con qué parámetros corrió la búsqueda, para que se pueda repetir igual."""
    return {
        "engine": "builtin",
        "objective": Objective.ADAPTIVE.value,
        "risk": Risk.ADAPTIVE.value,
        "population": args.population,
        "generations": args.generations,
        "draws": args.draws,
        "max_stops": MAX_STOPS,
        "seed": args.seed,
        "rival_seed": args.rival_seed,
        "rival_max_stops": RIVAL_MAX_STOPS,
        # Las tres salidas que corrió cada auto focal, y de dónde salió la de cada
        # rival. Con estas tres cosas el archivo se vuelve a armar igual.
        "start_compounds": list(START_COMPOUNDS),
        "compound_seed": args.compound_seed,
        "rival_start_compound_shares": START_COMPOUND_SHARES,
    }


#: Los supuestos, en el archivo y no sólo en el docstring. Quien lea el JSON sin
#: abrir el script tiene que poder separar lo medido de lo asumido.
ASSUMPTIONS = [
    "El compuesto de salida del auto focal es una recomendación, no un supuesto: "
    "la búsqueda entera se corre una vez por compuesto y las tres quedan "
    "publicadas en start_options. Los tres puntajes no se comparan entre sí "
    "porque el objetivo adaptativo puede resolver distinto en cada una, así que "
    "la comparación usa una vara común por auto: puntos esperados si alguna de "
    "las tres los tiene al alcance, puesto esperado si ninguna.",
    "El compuesto de salida de los RIVALES se sortea del reparto medido por banda "
    "de grilla (294 pilotos-carrera de las catorce fechas de 2026), no se elige. "
    "El auto focal también lo lleva sorteado cuando aparece como rival de los "
    "otros veintiuno: darles a los veintiuno el óptimo describiría una carrera "
    "que nadie corrió.",
    "Los planes de los rivales se sortean uniformes entre cero y tres paradas. La "
    "distribución medida de paradas reales (0,151 / 0,493 / 0,192 / 0,164) es "
    "otra, así que este sorteo sobrerrepresenta los planes de tres paradas.",
    "El puesto de largada es el de la clasificación. Las sanciones de grilla se "
    "aplican después de la sesión y este export no las mira.",
    "Los rivales no reaccionan al plan del auto focal, y sólo el focal paga "
    "tráfico: cada auto se proyecta a sí mismo algo pesimista.",
    "No hay abandonos: el simulador no modela confiabilidad ni error de piloto "
    "más allá del ruido de vuelta medido. Por eso hay autos con P(zona de "
    "puntos) = 1,000, que es una afirmación sobre el modelo y no sobre la carrera.",
]


def option_entry(option: StartOption, chosen: bool, laps: int) -> dict:
    """Qué daba una de las tres salidas, para que la elección quede explicada.

    Exportar sólo la ganadora convertiría la recomendación en un veredicto: el
    lector no podría ver cuánto costaba la otra, ni si las tres estaban empatadas.
    Va el resumen y no la corrida entera —histograma e historia pesan, y la de la
    ganadora ya está completa un nivel más arriba— pero va lo suficiente para
    reconstruir la decisión: las cuatro probabilidades y los dos números con los
    que se comparó.

    Args:
        option: La salida ya medida.
        chosen: Si es la que la vara eligió.
        laps: Vueltas de la carrera, para describir el plan por tandas.

    Returns:
        El objeto que va a la lista ``start_options`` de un auto.
    """
    return {
        "compound": option.compound,
        "plan": option.found.best.describe(option.car, laps),
        "stops": [{"lap": stop.lap, "compound": stop.compound} for stop in option.found.best.stops],
        # Resueltos por la búsqueda, y pueden no coincidir entre las tres: es
        # justamente por eso que los ``score`` no se comparan directamente.
        "objective": option.found.objective.value,
        "risk": option.found.risk.value,
        "p_ganar": round(option.odds.p_ganar, 4),
        "p_podio": round(option.odds.p_podio, 4),
        "p_puntos": round(option.odds.p_puntos, 4),
        "p_mejora": round(option.odds.p_mejora, 4),
        "expected_position": round(option.position, 3),
        "sd_position": round(option.found.sd_position, 3),
        "expected_points": round(option.points, 3),
        "score": round(option.found.score, 4),
        "decision_value": round(option.found.decision_value, 3),
        "chosen": chosen,
    }


#: Cuánto desgaste está dispuesto a absorber un equipo antes de parar, en
#: segundos por vuelta. Es el mismo valor por omisión de :func:`insights.pit_window`
#: y el que usa ``scripts/broadcast_demo.py``.
WINDOW_TOLERANCE_S = 1.0

#: Vueltas que se espera que dure el PRÓXIMO juego, para saber cuándo la ventana
#: se cierra por quedarse sin carrera.
#:
#: Es el mismo valor que usa ``scripts/broadcast_demo.py``, para que los dos
#: productos digan lo mismo. Y es del próximo juego y no del actual: pasar la vida
#: del compuesto que el auto lleva puesto hacía que el duro —que dura más— cerrara
#: su ventana ANTES que el blando, que es al revés de lo razonable. Antes de
#: largar no se sabe con qué va a cambiar, así que el valor es neutral: la mediana
#: medida de vida de una tanda va de 13 vueltas en blando a 25 en duro.
EXPECTED_NEXT_STINT = 22


def projected_window(car: Car, model: RaceModel) -> dict[str, int] | None:
    """La ventana de parada proyectada para un auto que todavía no largó.

    Es una cantidad distinta del plan y hay que mantenerlas separadas: la ventana
    dice **cuándo podría** parar y el plan dice **cuándo va a**. La web ya las
    distingue en pantalla; acá se exportan las dos.

    El ritmo de caída con el que se proyecta **no es el del auto**, porque antes
    de largar ningún auto tiene historia de la cual sacarlo. Es el del **compuesto
    con el que larga**, medido en este circuito. Eso hace que la ventana
    diferencie por compuesto y por nada más, que es exactamente lo que se sabe en
    la grilla: dos autos que largan con lo mismo tienen la misma ventana, y está
    bien que así sea.

    Args:
        car: El auto, con el compuesto que la búsqueda le eligió.
        model: El modelo del circuito, de donde sale el desgaste medido.

    Returns:
        ``{"opens_lap", "closes_lap"}`` en numeración de vueltas de carrera, o
        ``None`` si no hay cruce proyectable.
    """
    rate = model.wear_cuts[car.compound][len(strategy.CUT_AT) // 2]
    driver = insights.Driver(
        code=car.code,
        compound=car.compound,
        tyre_age=car.tyre_age,
        degradation_s=car.degradation_s,
        degradation_rate=rate,
    )
    window = insights.pit_window(
        driver,
        laps_remaining=model.total_laps - car.from_lap,
        expected_stint_life=EXPECTED_NEXT_STINT,
        tolerance_s=WINDOW_TOLERANCE_S,
    )
    if window is None:
        return None
    opens, closes = window
    return {"opens_lap": car.from_lap + opens, "closes_lap": car.from_lap + closes}


def car_entry(run: CarRun, laps: int, model: RaceModel) -> dict:
    """Todo lo que la vista necesita de un auto, en un objeto.

    Los campos de siempre describen la salida **elegida**, que es la
    recomendación; las otras dos van completas en ``start_options``.

    Args:
        run: Las tres salidas del auto, la elegida y la vara con la que se eligió.
        laps: Vueltas de la carrera, para describir el plan por tandas.

    Returns:
        El objeto que va a la lista ``cars`` del JSON.
    """
    entry, car, found = run.entry, run.chosen.car, run.chosen.found
    odds = run.chosen.odds
    return {
        "code": entry.code,
        "driver": entry.driver,
        "team": entry.team,
        "grid_position": entry.grid_position,
        "best_lap_s": entry.best_lap_s,
        "gap_to_pole_s": entry.gap_to_pole_s,
        "pace_s": round(car.pace_s or 0.0, 4),
        "start_compound": car.compound,
        # La ventana proyectada, que NO es el plan. Ver projected_window: acá dice
        # cuándo podría parar y `stops` dice cuándo va a parar. Sin esto, las
        # gráficas de ventana y de amenaza de undercut quedan inertes en este
        # origen, que es como estaban hasta ahora.
        "pit_window": projected_window(car, model),
        # Con qué se compararon las tres salidas. Sin esto, «eligió el duro» no
        # dice si lo eligió por puntos o por puestos, que no es lo mismo.
        "start_yardstick": run.yardstick,
        # Y con qué larga este mismo auto cuando es rival de los otros veintiuno:
        # sorteado, no elegido. Va exportado porque es parte de la carrera que se
        # simuló y de otro modo sólo se recupera volviendo a correr la semilla.
        "rival_start_compound": run.rival.compound,
        "rival_plan": run.rival_plan.describe(run.rival, laps),
        "plan": found.best.describe(car, laps),
        "stops": [{"lap": stop.lap, "compound": stop.compound} for stop in found.best.stops],
        # Resueltos, no pedidos: los dos entraron como ADAPTIVE y la búsqueda los
        # conmutó. Cuál eligió es parte de la recomendación — puntos donde son
        # alcanzables y posición donde la aptitud se aplana, averso mientras haya
        # algo que proteger y arriesgado cuando no hay nada que perder.
        "objective": found.objective.value,
        "risk": found.risk.value,
        "p_ganar": round(odds.p_ganar, 4),
        "p_podio": round(odds.p_podio, 4),
        "p_puntos": round(odds.p_puntos, 4),
        "p_mejora": round(odds.p_mejora, 4),
        "mean_position": round(found.mean_position, 3),
        "sd_position": round(found.sd_position, 3),
        "mean_points": round(found.mean_points, 3),
        "decision_value": round(found.decision_value, 3),
        "score": round(found.score, 4),
        "score_in_sample": round(found.score_in_sample, 4),
        "optimism": round(found.optimism, 4),
        "stop_distribution": {str(k): round(v, 4) for k, v in found.stop_distribution.items()},
        # El histograma va entero y sin normalizar: los conteos suman los sorteos,
        # así que quien lo lea puede recalcular cualquier otra probabilidad —y
        # verificar las cuatro de arriba— sin volver a correr nada.
        "position_histogram": {str(k): v for k, v in found.position_histogram.items()},
        "alternatives": [
            {"plan": plan.describe(car, laps), "stops": plan.count, "score": round(value, 4)}
            for plan, value in found.alternatives
        ],
        # La generación cero es la población sembrada, antes de la primera
        # selección: es contra ella que se mide lo que la evolución encontró.
        "history": [
            {
                "generation": generation.index,
                "best": round(generation.best, 4),
                "stop_distribution": {
                    str(k): round(v, 4) for k, v in generation.stop_distribution.items()
                },
                # El plan que sacó ese valor, para que el registro muestre QUÉ
                # encontró la búsqueda y no sólo que mejoró.
                "best_plan": (
                    generation.best_plan.describe(car, laps)
                    if generation.best_plan is not None
                    else None
                ),
                "best_stops": (
                    [
                        {"lap": stop.lap, "compound": stop.compound}
                        for stop in generation.best_plan.stops
                    ]
                    if generation.best_plan is not None
                    else []
                ),
            }
            for generation in found.history
        ],
        # Las tres salidas, en orden de compuesto y no de resultado: la ganadora
        # se reconoce por ``chosen``, y ordenarlas por mérito escondería que
        # también se corrieron las otras dos.
        "start_options": [
            option_entry(option, option is run.chosen, laps) for option in run.options
        ],
    }


def parse_args() -> argparse.Namespace:
    """Los parámetros de la corrida, con los defaults que se usaron para exportar."""
    default_out = Path(__file__).resolve().parents[3] / "docs/research/prerace-zandvoort.json"
    parser = argparse.ArgumentParser(description="Export pre-carrera de Zandvoort 2026.")
    parser.add_argument("--out", type=Path, default=default_out, help="dónde escribir el JSON")
    parser.add_argument("--population", type=int, default=40, help="planes por generación")
    parser.add_argument("--generations", type=int, default=25, help="rondas de selección")
    parser.add_argument(
        "--draws",
        type=int,
        default=1200,
        help="carreras sorteadas por evaluación; 1.200 es un piso medido, no un gusto",
    )
    parser.add_argument("--seed", type=int, default=11, help="semilla de la búsqueda")
    parser.add_argument(
        "--rival-seed", type=int, default=7, help="semilla del sorteo de planes rivales"
    )
    parser.add_argument(
        "--compound-seed",
        type=int,
        default=13,
        # Va aparte de ``--rival-seed`` a propósito: si los dos sorteos
        # compartieran generador, agregar el del compuesto correría el de los
        # planes y cambiaría planes rivales ya publicados.
        help="semilla del sorteo del compuesto de salida de los rivales",
    )
    return parser.parse_args()


def main() -> None:
    """Correr la búsqueda sobre toda la parrilla y escribir el JSON."""
    args = parse_args()
    started = time.perf_counter()

    quali = qualifying.load(YEAR, ROUND)
    model = RaceModel.for_circuit(quali.circuit, total_laps=TOTAL_LAPS)

    # El compuesto de salida de cada rival se sortea UNA vez, de la banda de
    # grilla que le toca y con su propia semilla. Aparte de la de los planes: si
    # compartieran generador, agregar este sorteo correría el otro y cambiaría
    # planes rivales ya publicados.
    compound_rng = np.random.default_rng(args.compound_seed)
    drawn = [draw_start_compound(entry.grid_position, compound_rng) for entry in quali.entries]
    field = field_from(quali, drawn)

    # Los planes de los rivales se sortean UNA vez, con su propia semilla, y se
    # comparten entre todas las búsquedas: si cada auto sorteara los suyos, cada
    # uno estaría corriendo una carrera distinta y los resultados no se podrían
    # mirar juntos. Por lo mismo todas las búsquedas usan la misma semilla, que es
    # lo que hace que a todos los autos les toquen las mismas neutralizaciones.
    #
    # Se sortean sobre el campo YA con su compuesto sorteado, porque el plan
    # depende de con qué larga: ``_repair`` hace cumplir la regla de los dos
    # compuestos, y sortearlo contra otra salida daría un plan que no es legal
    # para el auto que lo va a correr.
    rival_rng = np.random.default_rng(args.rival_seed)
    rival_plans = [strategy._random_plan(car, model, rival_rng, RIVAL_MAX_STOPS) for car in field]

    print(SEP)
    print(f"### {quali.event} {quali.year}: la parrilla real, {TOTAL_LAPS} vueltas")
    print(f"pole {quali.pole_s:.3f} s, {len(field)} autos con tiempo, {len(quali.excluded)} sin él")
    for out in quali.excluded:
        print(f"  afuera: {out.code} - {out.reason}")
    wear = {c: round(cuts[4], 4) for c, cuts in model.wear_cuts.items()}
    print(f"desgaste mediano de {quali.circuit}, s/vuelta: {wear}")
    print(f"pérdida de boxes en verde (p25, mediana, p75): {model.pit_loss_green}")
    print(f"safety car en {1 - model.n_sc[0]:.0%} de las carreras, VSC en {1 - model.n_vsc[0]:.0%}")
    print(
        f"búsqueda: población {args.population}, {args.generations} generaciones, "
        f"{args.draws} sorteos, semilla {args.seed} (rivales {args.rival_seed})"
    )
    print(
        "el auto focal corre las tres salidas y elige; los rivales la sortean del "
        f"reparto\nmedido por banda de grilla (semilla {args.compound_seed}): "
        f"{dict(Counter(drawn))}"
    )

    print("\n" + SEP)
    print("### LO QUE LA BUSQUEDA RECOMIENDA, AUTO POR AUTO")
    print("Una fila por compuesto de salida; la marcada es la elegida, y al lado")
    print("con qué vara se eligió — puntos si alguna de las tres los tiene al")
    print("alcance, puesto si ninguna.")
    print(
        f"{'sale':>4} {'auto':<4} {'larga':<7} {'plan':<17} {'obj/riesgo':<15}"
        f" {'gana':>5} {'podio':>5} {'ptos':>5} {'mejor':>5} {'llega':>6} {'ptos':>6} {'seg':>5}"
    )

    runs: list[CarRun] = []
    for index, entry in enumerate(quali.entries):
        rivals = [other for slot, other in enumerate(field) if slot != index]
        plans = [plan for slot, plan in enumerate(rival_plans) if slot != index]

        options: list[StartOption] = []
        for compound in START_COMPOUNDS:
            # El mismo auto con la sola diferencia del compuesto de salida, y con
            # la MISMA semilla que las otras dos corridas: los tres compuestos se
            # miden contra las mismas carreras sorteadas, que es lo que hace que
            # la diferencia entre ellos no cargue además el ruido del Monte Carlo.
            focal = replace(field[index], compound=compound)
            at = time.perf_counter()
            found = optimise(
                focal,
                rivals,
                plans,
                model,
                objective=Objective.ADAPTIVE,
                risk=Risk.ADAPTIVE,
                population=args.population,
                generations=args.generations,
                draws=args.draws,
                max_stops=MAX_STOPS,
                seed=args.seed,
                instrument=True,
            )
            took = time.perf_counter() - at
            option = start_option(compound, focal, found, entry.grid_position)
            options.append(option)
            label = OBJECTIVE_LABEL.get(found.objective, found.objective.value)
            print(
                f"{entry.grid_position:>4} {entry.code:<4}"
                f" {COMPOUND_LABEL[compound]:<7}"
                f" {found.best.describe(focal, model.total_laps):<17}"
                f" {label}/{found.risk.value:<8}"
                f" {option.odds.p_ganar:>5.2f} {option.odds.p_podio:>5.2f}"
                f" {option.odds.p_puntos:>5.2f} {option.odds.p_mejora:>5.2f}"
                f" {option.position:>6.2f} {option.points:>6.2f} {took:>5.1f}",
                flush=True,
            )

        chosen, yardstick = choose(options)
        runs.append(
            CarRun(
                entry=entry,
                options=tuple(options),
                chosen=chosen,
                yardstick=yardstick,
                rival=field[index],
                rival_plan=rival_plans[index],
            )
        )
        print(
            f"{'':>4} {'':<4} --> larga en {COMPOUND_LABEL[chosen.compound]}, "
            f"por {'puntos esperados' if yardstick == 'points' else 'puesto esperado'}"
            f"; como rival larga en {COMPOUND_LABEL[field[index].compound]}",
            flush=True,
        )

    cars = [car_entry(run, model.total_laps, model) for run in runs]
    every = [option for run in runs for option in run.options]

    payload = {
        "race": race_meta(quali),
        "model": model_meta(model),
        "search": search_meta(args),
        "assumptions": ASSUMPTIONS,
        "checks": {
            "draws": args.draws,
            # Cada auto se simula contra planes SORTEADOS de los rivales, no contra
            # el óptimo de todos, así que las búsquedas no son la misma carrera y
            # esto no tiene por qué dar exactamente 1. Cuánto se aleja es
            # información sobre el modelo, y por eso se publica en vez de esconderse.
            "p_ganar_total": round(sum(one["p_ganar"] for one in cars), 4),
            # Los tres invariantes se verifican sobre las TRES salidas de cada
            # auto y no sólo sobre la elegida: las otras dos también se publican,
            # así que también tienen que estar bien.
            "start_options": len(START_COMPOUNDS),
            "position_histogram_sums_draws": all(
                sum(option.found.position_histogram.values()) == args.draws for option in every
            ),
            "history_generations": args.generations + 1,
            "history_complete": all(
                len(option.found.history) == args.generations + 1 for option in every
            ),
            # P(ganar) <= P(podio) <= P(zona de puntos) por construcción: cada una
            # acumula sobre la anterior. Si alguna vez no diera, el histograma y
            # las probabilidades habrían dejado de salir del mismo lugar.
            "chances_ordered": all(
                option.odds.p_ganar <= option.odds.p_podio <= option.odds.p_puntos
                for option in every
            ),
        },
        "cars": cars,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    elapsed = time.perf_counter() - started

    print("\n" + SEP)
    print("### COHERENCIA")
    print(f"P(ganar) suma {payload['checks']['p_ganar_total']:.3f} sobre los {len(cars)} autos.")
    print("No tiene por qué dar 1: cada auto corre contra planes sorteados de los demás")
    print("y sólo el focal paga tráfico. Lo lejos que quede es el tamaño de esa")
    print("aproximación, y por eso el número se publica.")
    print(
        f"histograma suma los {args.draws} sorteos en las {len(every)} corridas: "
        f"{payload['checks']['position_histogram_sums_draws']}"
    )
    print(
        f"historia con {args.generations + 1} generaciones en las {len(every)} corridas: "
        f"{payload['checks']['history_complete']}"
    )
    print(
        f"P(ganar) <= P(podio) <= P(puntos) en las tres salidas de cada auto: "
        f"{payload['checks']['chances_ordered']}"
    )

    print("\n" + SEP)
    print("### CON QUE ELIGIO LARGAR CADA UNO")
    elegidos = Counter(run.chosen.compound for run in runs)
    print(f"elegidos por la búsqueda: {dict(elegidos)}")
    print(f"sorteados para los rivales: {dict(Counter(drawn))}")
    print("El sorteo tiene que parecerse al reparto medido; la elección no tiene")
    print("por qué. Una es la grilla que la evidencia describe y la otra es lo que")
    print("la búsqueda recomienda, y que no coincidan es justamente el resultado.")
    print()
    print(f"{'sale':>4} {'auto':<4} {'elige':<7} {'sorteado':<9} {'vara':<9} {'ventaja'}")
    for run in runs:
        otras = [option for option in run.options if option is not run.chosen]
        if run.yardstick == "points":
            margen = run.chosen.points - max(option.points for option in otras)
            gap = f"{margen:+.2f} puntos"
        else:
            margen = min(option.position for option in otras) - run.chosen.position
            gap = f"{margen:+.2f} puestos"
        print(
            f"{run.entry.grid_position:>4} {run.entry.code:<4}"
            f" {COMPOUND_LABEL[run.chosen.compound]:<7}"
            f" {COMPOUND_LABEL[run.rival.compound]:<9} {run.yardstick:<9} {gap}"
        )

    print(f"\nescrito en {args.out} ({args.out.stat().st_size / 1024:.0f} KB) en {elapsed:.0f} s")


if __name__ == "__main__":
    main()
