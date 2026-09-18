"""Todo lo que la vista pre-carrera va a mostrar, en un JSON y de una sola corrida.

La pregunta de la vista no es la de ``prerace_strategy.py``. Ahí se pregunta cuál
es la forma más rápida de cubrir la distancia, que es un problema de un solo auto
y no necesita al campo. Acá se pregunta **dónde va a terminar cada uno**, y eso
sin rivales no existe: un puesto de llegada es una comparación. Por eso cada auto
se optimiza desde la vuelta 1 contra todos los demás, cada uno con un plan
sorteado.

Lo que sale es un archivo y no un servicio. La búsqueda tarda minutos, la web es
estática, y el patrón ya está: ``strategy_search.py --out`` genera el JSON que
``apps/web/src/plans.ts`` consume. Ver ADR-002.

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

## Qué es medido y qué es supuesto

Medido: el hueco de clasificación de cada auto (sesión real, ver ADR-004), el
desgaste por compuesto de Zandvoort, la pérdida de boxes, las tasas de
neutralización, el costo del tráfico, el ruido de vuelta y la conversión de hueco
de clasificación a ritmo de carrera.

Supuesto, y declarado también dentro del JSON:

* **El compuesto de salida.** Todos largan en medio. Antes de la carrera no se
  sabe con qué larga cada uno, y darles el mismo deja que lo único que los separe
  sea el puesto y el ritmo, que sí están medidos.
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
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from boxbox_ml import qualifying, strategy
from boxbox_ml.qualifying import Entry, Qualifying
from boxbox_ml.strategy import (
    Car,
    Objective,
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

#: Compuesto con el que larga todo el campo. **Supuesto, no medido.** Antes de la
#: carrera nadie sabe con qué larga cada auto: la elección se ve recién en la
#: grilla y se decide hasta último momento. Se le da el mismo a todos a propósito,
#: para que lo único que separe a un auto de otro sea su puesto y su ritmo, que sí
#: están medidos. El día que se sepa la elección real entra acá y nada más cambia.
START_COMPOUND = "MEDIUM"

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


def field_from(quali: Qualifying) -> list[Car]:
    """Los autos en la grilla, uno por piloto con tiempo.

    Goma nueva, sin historia de desgaste propia —nadie corrió todavía, así que el
    encogimiento no tiene nada que encoger y la mediana de la población es el punto
    de partida honesto— y el ritmo declarado explícitamente desde el hueco de
    clasificación. Eso último es lo que hace que la búsqueda vea la posición de
    largada: sin ``pace_s``, un auto en la vuelta 1 no tiene historia de la cual
    inferir su ritmo y el modelo lo trata como si fuera tan rápido como la pole.

    Args:
        quali: La clasificación ya leída.

    Returns:
        Un auto por piloto, en orden de grilla.
    """
    return [
        Car(
            code=entry.code,
            compound=START_COMPOUND,
            tyre_age=0,
            degradation_s=0.0,
            degradation_rate=strategy.ROLLING_MEDIAN_S,
            gap_leader_s=entry.gap_to_pole_s,
            from_lap=1,
            pace_s=pace_from_qualifying(entry.gap_to_pole_s),
        )
        for entry in quali.entries
    ]


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
        "start_compound": START_COMPOUND,
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
    }


#: Los supuestos, en el archivo y no sólo en el docstring. Quien lea el JSON sin
#: abrir el script tiene que poder separar lo medido de lo asumido.
ASSUMPTIONS = [
    "Todos los autos largan en MEDIUM: antes de la carrera no se sabe con qué "
    "larga cada uno, y darles el mismo compuesto deja que lo único que los separe "
    "sea el puesto y el ritmo, que sí están medidos.",
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


def car_entry(entry: Entry, car: Car, found: Search, laps: int) -> dict:
    """Todo lo que la vista necesita de un auto, en un objeto.

    Args:
        entry: El piloto tal como salió de la clasificación.
        car: El auto que se optimizó.
        found: Lo que devolvió la búsqueda, instrumentada.
        laps: Vueltas de la carrera, para describir el plan por tandas.

    Returns:
        El objeto que va a la lista ``cars`` del JSON.
    """
    odds = chances(found.position_histogram, entry.grid_position)
    return {
        "code": entry.code,
        "driver": entry.driver,
        "team": entry.team,
        "grid_position": entry.grid_position,
        "best_lap_s": entry.best_lap_s,
        "gap_to_pole_s": entry.gap_to_pole_s,
        "pace_s": round(car.pace_s or 0.0, 4),
        "start_compound": car.compound,
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
    return parser.parse_args()


def main() -> None:
    """Correr la búsqueda sobre toda la parrilla y escribir el JSON."""
    args = parse_args()
    started = time.perf_counter()

    quali = qualifying.load(YEAR, ROUND)
    model = RaceModel.for_circuit(quali.circuit, total_laps=TOTAL_LAPS)
    field = field_from(quali)

    # Los planes de los rivales se sortean UNA vez, con su propia semilla, y se
    # comparten entre todas las búsquedas: si cada auto sorteara los suyos, cada
    # uno estaría corriendo una carrera distinta y los resultados no se podrían
    # mirar juntos. Por lo mismo todas las búsquedas usan la misma semilla, que es
    # lo que hace que a todos los autos les toquen las mismas neutralizaciones.
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
    print(f"supuesto declarado: todos largan en {START_COMPOUND}")

    print("\n" + SEP)
    print("### LO QUE LA BUSQUEDA RECOMIENDA, AUTO POR AUTO")
    print(
        f"{'sale':>4} {'auto':<4} {'hueco':>6} {'ritmo':>6} {'plan':<17} {'obj/riesgo':<15}"
        f" {'gana':>5} {'podio':>5} {'ptos':>5} {'mejor':>5} {'llega':>13} {'seg':>5}"
    )

    cars: list[dict] = []
    for index, (entry, car) in enumerate(zip(quali.entries, field, strict=True)):
        rivals = [other for slot, other in enumerate(field) if slot != index]
        plans = [plan for slot, plan in enumerate(rival_plans) if slot != index]

        at = time.perf_counter()
        found = optimise(
            car,
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

        exported = car_entry(entry, car, found, model.total_laps)
        cars.append(exported)
        label = OBJECTIVE_LABEL.get(found.objective, found.objective.value)
        print(
            f"{entry.grid_position:>4} {entry.code:<4} {entry.gap_to_pole_s:>6.3f}"
            f" {car.pace_s or 0.0:>6.2f} {exported['plan']:<17}"
            f" {label}/{found.risk.value:<8}"
            f" {exported['p_ganar']:>5.2f} {exported['p_podio']:>5.2f}"
            f" {exported['p_puntos']:>5.2f} {exported['p_mejora']:>5.2f}"
            f" {found.mean_position:>6.2f} +-{found.sd_position:<4.2f} {took:>5.1f}",
            flush=True,
        )

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
            "position_histogram_sums_draws": all(
                sum(one["position_histogram"].values()) == args.draws for one in cars
            ),
            "history_generations": args.generations + 1,
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
        f"histograma suma los {args.draws} sorteos en todos los autos: "
        f"{payload['checks']['position_histogram_sums_draws']}"
    )
    print(
        f"historia con {args.generations + 1} generaciones en todos los autos: "
        f"{all(len(one['history']) == args.generations + 1 for one in cars)}"
    )
    print(f"\nescrito en {args.out} ({args.out.stat().st_size / 1024:.0f} KB) en {elapsed:.0f} s")


if __name__ == "__main__":
    main()
