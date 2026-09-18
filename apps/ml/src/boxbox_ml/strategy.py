"""Genetic search for a pit-stop plan, scored against a drawn race.

This is the piece the whole project points at. Everything else measures; this
decides. A plan is a sequence of stops — when, and onto what — and the search
looks for the one whose *distribution* of outcomes is best, not the one that
looks best against a single guessed race.

## Why a genetic algorithm

The space is small but awkward: variable length (one stop or four), mixed types
(a lap number and a compound), and constrained (stops cannot be adjacent, and the
regulations require two dry compounds). Gradients do not exist here, and
enumerating gets wasteful once three stops are allowed. Crossover between two
good plans genuinely produces a third — "stop early like this one, but fit the
hard like that one" is a real strategic idea — which is the situation the
operator is for.

The operators are the ones named in the proposal: one-point crossover on the stop
list, and mutation that lengthens a stint, shortens it, changes its compound, or
adds and drops a stop.

## Why the fitness is a distribution

Every input is uncertain and measured to be so: how the tyres will wear, what the
stop will cost, whether a safety car comes out and when. A plan is therefore not
a number but a spread of finishing positions, and different cars want different
things from that spread. See :class:`Objective`.

## Two things the snapshot cannot be trusted about

**The car's own wear rate barely predicts.** Each car arrives carrying
``degradation_rate``, a slope fitted over its trailing five laps. Measured against
what those stints went on to do — 2,492 of them, comparing the slope at lap 10
against the slope actually run from lap 11 — the correlation is **0.183**, and the
rolling estimate is three and a half times too dispersed (sd 0.466 against 0.127).
So it is shrunk hard: the future rate is drawn from the compound's distribution
and the car's own deviation is admitted at the measured attenuation, about **5%**.
Projecting the raw figure was not a small error: one car in the Zandvoort snapshot
carries −0.549 s/lap, which extrapolated over thirty laps claims it will gain four
minutes, and the search duly recommended a plan that had it winning from ninth.

**Cars are not equally fast.** Accumulating only the change in tyre state quietly
assumes they are, and the consequence was equally absurd: a car eleventh and
sixty-two seconds back, sitting on a twenty-five-lap medium, was projected to
finish fourth purely because it had the most to gain from fresh rubber. The
snapshot cannot separate car pace from tyre state directly, but a car that is
``gap_leader_s`` behind after ``from_lap`` laps has been losing that much per lap
on average; subtract the tyre deficit it carries now and what is left is its
baseline, which persists whatever it does with its tyres.

That estimate is rough. It folds in the start, any incident, and any stop already
taken — a car that has pitted once carries about twenty-two seconds of pit lane in
its gap, inflating its apparent baseline by roughly 0.7 s/lap over thirty laps.
Better would be the gap's *rate of change*, which one lap of data cannot give.

## Traffic, which is what makes the lap of a stop matter

A stop priced only in seconds makes lap 38 and lap 44 differ by arithmetic alone.
What separates them in a real race is *who you come out behind*, and that is now
in the model: after each stop the search looks at where every rival is on that
lap, takes the gap to the nearest car ahead, and charges the measured penalty for
a drawn number of laps.

The penalty is measured within a driver's own stint with tyre age controlled, over
81,719 laps: **0.544 s/lap inside one second**, decaying to nothing past five.
23.4% of green laps are run inside that second, and the episodes last a median of
two laps with a 95th percentile of ten. Against a 22.6 s pit loss that is 7% to
29% — small in the mean, but unlike the pit loss it depends entirely on the lap
chosen, which is exactly what a search can exploit.

## What is still not modelled

No on-track blocking as such: a faster car is assumed to eventually get past, and
what it pays for the privilege is the traffic term above rather than a genuine
overtaking model. No reliability, no driver error beyond the measured lap noise.
Rivals do not react to the focal car's plan — their plans are drawn once per race
and held, which is why their traces can be computed once and reused across every
candidate. That approximation is what makes the search cheap, and it is wrong in
exactly the case where two cars are fighting each other directly.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path

import numpy as np

#: Championship points for the first ten places. Eleventh onward scores nothing,
#: which is the discontinuity that makes strategy interesting outside the top ten.
POINTS = (25, 18, 15, 12, 10, 8, 6, 4, 2, 1)

#: Dry compounds, hardest first.
DRY = ("HARD", "MEDIUM", "SOFT")

#: Laps a stint has to run before it counts as one.
MIN_STINT = 6

#: How many distinct dry compounds a dry race must use. FIA 2026 Sporting
#: Regulations, article B6.3.8: at least two specifications of dry-weather tyre
#: must be used, and not doing so is a disqualification — the harshest constraint
#: in the whole problem, and the only one where breaking it costs everything.
#:
#: It is only checkable for a plan that starts from lap 1. A plan that picks up
#: mid-race cannot be verified, because the snapshot does not record which sets
#: the car already used; those are left alone rather than guessed at.
REQUIRED_COMPOUNDS = 2

#: Probabilities at which every measured distribution below is cut.
CUT_AT = np.array([0.05, 0.15, 0.25, 0.35, 0.5, 0.65, 0.75, 0.85, 0.95])

#: How much of a car's own five-lap wear slope survives into the projection.
#: Measured attenuation: the rolling estimate correlates 0.183 with what the stint
#: went on to do and is 3.7x too dispersed, so 0.183 * 0.127 / 0.466.
RATE_SHRINK = 0.05

#: Median of that rolling slope across the field, which the shrinkage centres on.
ROLLING_MEDIAN_S = 0.022

#: How much of a qualifying gap is still there in race pace, per lap.
#:
#: This is what lets a pre-race plan know where the car started. Measured over 277
#: driver-races across the fourteen rounds of 2026 run so far, on fuel-corrected
#: green laps only: r = 0.880, pooled slope 0.835. Unusually for this project it
#: **replicates** — the per-race slope runs 0.63 to 1.10 with a median of 0.92 —
#: and leave-one-race-out puts the error at 0.554 s/lap against 0.935 for assuming
#: every car is equally fast, a 40.7% gain.
#:
#: Contrast with the practice-to-race wear calibration, which looked just as good
#: on a leave-one-out and then failed on the first circuit it had not seen. The
#: difference is n: nine circuits there, fourteen races and 277 cars here.
QUALI_TO_RACE_PACE = 0.835


def pace_from_qualifying(gap_to_pole_s: float) -> float:
    """Race pace deficit per lap implied by a qualifying gap.

    Args:
        gap_to_pole_s: The car's best qualifying lap minus pole, in seconds.

    Returns:
        Seconds per lap slower than the fastest car, for use as :attr:`Car.pace_s`.
    """
    return QUALI_TO_RACE_PACE * gap_to_pole_s


#: Cuánto más lento es cada compuesto con goma nueva, en segundos por vuelta,
#: respecto del duro. **La pieza que faltaba**, y la que le da al duro una razón
#: de existir que no sea sólo el reglamento.
#:
#: No se puede medir dentro de una carrera. Los compuestos se corren en momentos
#: distintos —el medio en la mediana del 26% de la distancia, el duro en el 61%—
#: y separar el neumático de veinticinco vueltas de combustible y evolución de
#: pista pide una corrección más fina de la que existe. Medido así daba 0,02 a
#: 0,04 s/vuelta entre compuestos, y de ahí salió la conclusión equivocada de que
#: no había diferencia medible.
#:
#: Sí se puede en las prácticas: mismo piloto, misma sesión, poco combustible,
#: tandas cortas separadas por minutos. Sobre 8.422 vueltas de 2026 en 26
#: sesiones, comparando la mejor vuelta de cada piloto en cada compuesto:
#:
#:     blando - medio   -0,947 s/vuelta   (n=279)
#:     medio  - duro    -0,957            (n= 44)
#:     blando - duro    -1,027            (n=115)
#:
#: Un segundo entre compuestos vecinos, treinta veces lo que daba la carrera.
#:
#: Los tres pares no son transitivos, así que estos valores salen de un ajuste
#: ponderado por tamaño de muestra sobre los tres a la vez.
#:
#: **Dos advertencias que van con el número.** Una vuelta de práctica es lanzada
#: y con poco combustible, y en carrera los escalones se achican: esto es una
#: cota superior. Y el eslabón medio-duro descansa en 44 observaciones porque
#: casi nadie prueba los dos en la misma sesión — es justamente el par que decide
#: si el duro sirve, y es el peor medido. Un ajuste alternativo sobre los niveles
#: en vez de las medianas llega a poner el medio *más lento* que el duro, lo que
#: da la medida de cuán poco determinado está.
#: **Y por qué está en cero.** Meter el número medido produce disparates: con el
#: blando a −1,245 s/vuelta el optimizador recomienda tandas de blando para toda
#: la carrera, que es algo que ningún equipo hace. Se probó bajando la escala
#: hasta el 10% y sigue eligiendo blando; se probó además apretando el tope de
#: tanda de la vida p90 a la mediana, y entonces elige blando con cuatro paradas.
#:
#: El motivo es que una vuelta de práctica mide el pico de agarre con poco
#: combustible, y esa ventaja se derrite con carga y con vueltas. El modelo la
#: aplicaría como una ventaja constante durante veinticinco vueltas, que es
#: exactamente lo que no es.
#:
#: O sea que hay dos afirmaciones y las dos son ciertas: la conclusión anterior
#: de que «no hay diferencia medible entre compuestos secos» era **falsa**, y
#: meter la diferencia medida en práctica también da mal. Lo que falta es el
#: escalón *en condiciones de carrera*, y eso pide o telemetría o un modelo de
#: combustible bastante mejor que el que hay.
#:
#: Se deja definido y en cero: el número queda documentado para quien lo
#: necesite, y el modelo no lo usa hasta que se pueda transferir. Poner la cifra
#: de práctica sería peor que no tener ninguna.
COMPOUND_OFFSET_S: dict[str, float] = {
    "HARD": 0.0,
    "MEDIUM": 0.0,
    "SOFT": 0.0,
}

#: Lo medido en práctica, conservado para cuando se pueda calibrar a carrera.
COMPOUND_OFFSET_PRACTICE_S: dict[str, float] = {
    "HARD": 0.0,
    "MEDIUM": -0.388,
    "SOFT": -1.245,
}

#: Largest per-lap deficit versus fresh rubber that has been measured, in seconds:
#: the 99th percentile late in a stint. Past this the set gets changed.
MAX_DEFICIT_S = 4.4

#: What a car loses per lap for having someone in front of it, by how big the gap
#: is. Measured within a driver's own stint with tyre age controlled, over 81,719
#: laps across 4,579 stints. Clear air past five seconds is the reference.
#:
#: The bias runs one way and it helps: a quick car catches the one ahead and gets
#: stuck, a slow one drops back into clear air, so being close correlates with
#: being quick and that pushes the penalty *down*. These are lower bounds.
#:
#: This is the term that makes the **lap** of a stop matter and not only the fact
#: of it. Without it, stopping on lap 38 and on lap 44 differ by arithmetic alone.
#: See ``scripts/traffic_cost.py``.
TRAFFIC_GAP_S = (0.5, 1.5, 2.5, 4.0, 6.0)
TRAFFIC_PENALTY_S = (0.544, 0.214, 0.086, 0.042, 0.0)

#: Measured for reference, and deliberately **not** used: how many consecutive
#: laps a car stays within a second of the one ahead, over 5,888 episodes, as cuts
#: of that distribution. Median two laps, 95th percentile ten.
#:
#: A first version drew from this at the moment of the stop. That was wrong twice
#: over. Traffic is not an event at the rejoin, it is a condition of the whole
#: stint — the car that fits fresh rubber *catches* the one ahead ten laps later
#: and then sits there. And the gap right after a stop is typically 16 seconds in
#: this field, so charging only at the rejoin charged almost nothing: the term was
#: inert and the search's advantage did not move.
#:
#: Charging every lap on the gap of that lap makes the duration emerge instead of
#: being drawn, which is both more physical and self-limiting.
TRAFFIC_EPISODE_CUTS_UNUSED = (1.0, 1.0, 1.0, 1.0, 2.0, 3.0, 4.0, 6.0, 10.0)

#: No circuit scaling, and the reason is a correction.
#:
#: A first pass bucketed circuits by *overtaking difficulty* and found +0.713
#: s/lap in the hard group against +0.485 in the easy one, and concluded that
#: difficulty modulates the traffic cost. Measuring the penalty **per circuit**
#: directly does not support that. Across the 24 circuits the two correlate at
#: Pearson 0.384 — but at **0.157 with Monaco removed**. The apparent
#: relationship was almost entirely one circuit being extreme on both axes.
#:
#: The per-circuit penalty does vary enormously — Monaco 1.379 s/lap against Miami
#: 0.218 — but it does not replicate: correlating each circuit's 2022-23 estimate
#: against its 2024-26 one gives **−0.042**. Same lesson as the overtaking
#: difficulty and the race-progress coefficient: with four or five races per
#: circuit, the spread is noise.
#:
#: The bucketed figure also assigned Zandvoort a 1.31x multiplier because it ranks
#: fifth hardest to pass. Its own measured penalty is 0.369, a multiplier of 0.68 —
#: the bucket nearly doubled it in the wrong direction.
#:
#: So the pooled 0.544 is used everywhere. Monaco is the one circuit where a
#: per-circuit figure would be defensible, and it is not the one being simulated.
TRAFFIC_SCALE = 1.0

#: Longest stint the evidence covers, per compound: the 90th percentile of
#: measured stint length over 2,002 hard, 2,240 medium and 1,152 soft stints.
#:
#: This is a limit on what the model is allowed to *claim*, not a physical limit.
#: Measured deficit against stint lap peaks around lap 20-25 and then **falls**,
#: which no tyre does — it is survivorship: the sets that run past thirty laps are
#: the ones that held, and the ones that did not were changed. Extrapolating a
#: fitted slope past that point is extrapolating into a region the data describes
#: optimistically and thinly, and the search noticed: given the chance it
#: recommended running forty-two laps on one set for half the grid.
MAX_STINT: dict[str, int] = {"HARD": 41, "MEDIUM": 31, "SOFT": 25}

#: Wear rate per compound, as cuts of the measured Zandvoort stint-slope
#: distribution. 98, 79 and 80 stints. See ``docs/research/pace-noise.md``.
#:
#: **Those counts are across every season, not 2026.** It is worth being explicit
#: because it was not: 2026 alone has 20, 11 and 28 stints here, and its medium
#: wears 0.1004 s/lap against the 0.0625 these cuts carry — a 60% difference
#: between two numbers both called "Zandvoort". The generator
#: (``scripts/zandvoort_distributions.py``) filters by circuit and not by year.
#:
#: That pooling contradicts the project's own stated policy, which measures wear
#: per compound on **2026 only**, because this is the season the compound order
#: inverted. :meth:`RaceModel.for_circuit` does follow that policy, which is why
#: the two disagree. Changing these cuts would move every published figure, so it
#: is a decision on its own and not a side effect of documenting the conflict.
#:
#: Re-derived after ``RACE_PROGRESS_S_PER_LAP`` was fitted at 0.056 instead of the
#: asserted 0.035. The effect is exact and uniform: every slope moves up by the
#: difference, 0.021 s/lap, because the correction is linear in the lap number.
#: The distribution's *shape* is untouched, so the non-normality finding stands —
#: but the median wear rate goes from 0.034-0.040 to 0.055-0.062, and the fifth
#: percentile of the medium and the hard moves from clearly negative to about
#: zero. Most of the "stints that get faster" were the under-correction.
#: Per-circuit wear, measured and shrunk. Written by ``scripts/circuit_wear.py``
#: and read lazily, because most callers never ask for a circuit.
_CIRCUIT_WEAR_PATH = Path(__file__).with_name("circuit_wear.json")
_circuit_wear: dict | None = None


def circuit_wear_table() -> dict:
    """The measured per-circuit wear table, loaded once.

    Returns an empty table if the file is missing, so a checkout that has not run
    the measurement still works — on the season average, which is the honest
    fallback anyway.
    """
    global _circuit_wear
    if _circuit_wear is None:
        try:
            _circuit_wear = json.loads(_CIRCUIT_WEAR_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _circuit_wear = {"celdas": {}, "nivel_temporada_s_vuelta": {}}
    return _circuit_wear


WEAR_CUTS: dict[str, tuple[float, ...]] = {
    "SOFT": (-0.163, -0.0003, 0.032, 0.0394, 0.0611, 0.0759, 0.0979, 0.1085, 0.1592),
    "MEDIUM": (-0.0063, 0.0322, 0.0421, 0.0547, 0.0625, 0.0749, 0.0885, 0.101, 0.1277),
    "HARD": (-0.0143, 0.0219, 0.0342, 0.0427, 0.0554, 0.0646, 0.0708, 0.0847, 0.1176),
}


@dataclass(frozen=True)
class RaceModel:
    """Everything drawn during a simulated race, all of it measured.

    Defaults are Zandvoort pooled across every season — **not 2026**, which the
    docstring claimed for a while and which :data:`WEAR_CUTS` explains. For a
    circuit the current season has visited, :meth:`for_circuit` is the one that
    follows the project's policy. See ``docs/research/strategy-search.md``.
    """

    total_laps: int = 72
    #: Residual sd of a lap around its stint's wear line. 4,407 stints.
    lap_noise_s: float = 0.457
    #: Wear rate per compound, as measured distribution cuts.
    wear_cuts: dict[str, tuple[float, ...]] = field(default_factory=lambda: dict(WEAR_CUTS))
    #: Effective pit loss under green — seconds conceded to the field. 2,614 stops.
    pit_loss_green: tuple[float, float, float] = (20.2, 22.6, 25.5)
    #: The same under a safety car. 264 stops, and far wider: timing matters.
    pit_loss_sc: tuple[float, float, float] = (7.5, 19.5, 31.5)
    #: Probability a race sees at least one safety car. 103 races; Zandvoort 0.600.
    #: Kept for the older single-period draw; the richer model below supersedes it.
    p_safety_car: float = 0.600

    #: How many periods of each kind a race sees, as probabilities over 0, 1, 2
    #: and 3+. Measured over 103 races, wet ones included — a safety car is a
    #: safety car whether it rains or not.
    #:
    #: The single most important number here is not any one of these: it is that
    #: **44.7% of races see two or more neutralisation periods**, and the previous
    #: model drew exactly one. Monza 2026 had a red flag on lap 3 and a VSC on lap
    #: 27, and the model could represent neither the pair nor the red flag.
    n_red: tuple[float, ...] = (0.883, 0.107, 0.000, 0.010)
    n_sc: tuple[float, ...] = (0.456, 0.427, 0.087, 0.030)
    n_vsc: tuple[float, ...] = (0.524, 0.320, 0.126, 0.030)

    #: Where each kind starts, as cuts of the share-of-distance distribution.
    #:
    #: Red flags and safety cars are **front-loaded**: half of each begins in the
    #: first third of the race, and the lower quartile of a red flag is lap 3 of
    #: 100. That is where the cars are packed and where they crash. VSC is much
    #: flatter — 36% first third, 29% middle, 36% last — because it is called for
    #: debris and stopped cars, which happen anywhere.
    red_start_cuts: tuple[float, ...] = (
        0.017,
        0.019,
        0.028,
        0.051,
        0.286,
        0.465,
        0.764,
        0.878,
        0.949,
    )
    sc_start_cuts_full: tuple[float, ...] = (
        0.014,
        0.018,
        0.033,
        0.120,
        0.306,
        0.457,
        0.619,
        0.744,
        0.877,
    )
    vsc_start_cuts: tuple[float, ...] = (
        0.027,
        0.102,
        0.218,
        0.314,
        0.414,
        0.667,
        0.715,
        0.792,
        0.937,
    )

    #: Median duration in laps: a red flag stops the race for one lap of racing,
    #: a safety car eats four, a VSC three.
    red_laps: int = 1
    vsc_laps: int = 3

    #: What a stop costs under a red flag. The race is stopped and the tyres are
    #: changed in the pit lane at no cost in track position — this is the case the
    #: model was missing entirely, and at Monza 2026 it applied to 22 of 32 stops.
    pit_loss_red: tuple[float, float, float] = (0.0, 0.0, 0.5)
    #: And under a VSC. 199 stops measured.
    pit_loss_vsc: tuple[float, float, float] = (14.8, 18.8, 27.1)
    #: Where it starts, as cuts of the share-of-distance distribution. 72 periods.
    sc_start_cuts: tuple[float, ...] = (
        0.014,
        0.018,
        0.033,
        0.120,
        0.306,
        0.457,
        0.619,
        0.744,
        0.877,
    )
    #: How many laps it lasts. Zandvoort median 5.5; the global median is 4.
    sc_laps: int = 5
    #: Multiplier on the traffic penalty. One, because the per-circuit estimates
    #: do not replicate across eras — see :data:`TRAFFIC_SCALE`.
    traffic_scale: float = TRAFFIC_SCALE

    @classmethod
    def for_circuit(cls, circuit: str, **overrides) -> RaceModel:
        """A model carrying that circuit's own measured wear, where it exists.

        The defaults are Zandvoort's pooled across seasons, and running every
        circuit on them is what made the model recommend the wrong tyre at Monza.

        Two questions hide here and they have opposite answers, which is why this
        looked harder than it is. Measured in ``scripts/circuit_wear.py``:

        * Does a circuit's wear carry across a **regulation change**? Barely —
          r = 0.143 over 27 circuit-compound pairs, and using the old figure is
          3.4% worse than the season average. So a circuit with no data from the
          current season gets the average, which is what Madrid got.
        * Is a circuit's measurement reliable **within** the current season? Very
          — split-half gives 0.81, which Spearman-Brown corrects to **0.89** for
          the full measurement, 0.95 on the medium and 0.96 on the hard.

        The simulator always faces the second question, because a circuit it is
        simulating is one the season has already visited. So the circuit's own
        number is used, shrunk by the measured reliability rather than believed
        whole.

        Args:
            circuit: Circuit key as :func:`boxbox_ml.neutralisation.canonical_circuit`
                spells it — "Monza", "Zandvoort", "Barcelona".
            **overrides: Any other field, ``total_laps`` above all.

        Returns:
            A model with ``wear_cuts`` rescaled to that circuit, or the plain
            defaults when the circuit has no measurement.
        """
        table = circuit_wear_table()
        cells = table.get("celdas", {}).get(circuit)
        if not cells:
            return cls(**overrides)

        level = table.get("nivel_temporada_s_vuelta", {})
        cuts = {}
        for compound, base in WEAR_CUTS.items():
            shrunk = cells.get(compound, {}).get("encogido", 0.0)
            target = level.get(compound, base[4]) + shrunk
            # Rescale the whole measured shape, so the spread travels with the
            # median instead of being pinned to Zandvoort's.
            factor = target / base[4] if base[4] else 1.0
            cuts[compound] = tuple(value * factor for value in base)
        return cls(wear_cuts=cuts, **overrides)


class Objective(StrEnum):
    """What the plan is trying to achieve — and it is not the same for every car.

    This is the question of whether a car outside the top ten can "win". It can,
    but not by the same measure as the car leading, and picking the wrong one here
    produces confident nonsense: telling a car in eighteenth to protect its
    position is telling it to score zero carefully.

    ``POINTS``    expected championship points. The default, because it is the
                  currency the sport pays in, and because its cliff at tenth does
                  the right thing on its own — a car in eleventh has nothing to
                  lose and should take variance, a car leading has everything to
                  lose and should not.
    ``POSITION``  expected finishing position. Treats a place gained at the front
                  and at the back as worth the same, which is false, but is the
                  honest choice when the run is about race craft, not points.
    ``TIME``      expected finishing time. Ignores the field entirely. A baseline,
                  and right for a car with nobody within reach.
    ``PODIUM``    probability of finishing in the top three.
    ``IN_POINTS`` probability of finishing in the top ten.
    ``ADAPTIVE``  points where points are reachable, position where they are not.
                  Not a hedge: for a car whose every plan scores zero, expected
                  points is a **flat** objective and the search has nothing to
                  climb. Measured on the Zandvoort grid, a car in eighteenth under
                  POINTS ends with its population spread across one to four stops
                  in almost equal measure — noise — while under POSITION the same
                  car converges on one stop at 0.87. A flat fitness does not
                  produce a cautious recommendation; it produces a random one.
    """

    ADAPTIVE = "adaptive"
    POINTS = "points"
    POSITION = "position"
    TIME = "time"
    PODIUM = "podium"
    IN_POINTS = "in_points"


class Risk(StrEnum):
    """How much of the spread the plan is allowed to gamble.

    Every objective above was a **mean**, which is risk-neutral, and a real pit
    wall is not. The clearest case is the last points-paying place. A car tenth
    holds one point: losing it costs one, gaining ninth gains one. Under an
    expected value, a fifty-fifty between eighth and twelfth scores ``0.5*4 +
    0.5*0 = 2`` against ``1`` for staying put, so the search **takes the gamble**.
    No team does that. The car tenth defends.

    The fix is not a rule per position — it is to stop reducing the spread by its
    mean. The draws are already there; what changes is which part of them the
    plan is scored on. Measured on a car starting tenth at Madrid, two plans the
    mean cannot separate properly:

    ====================  =========  ==============  ===============
    plan                  posición   cuarto peor     cuarto mejor
    ====================  =========  ==============  ===============
    una parada M15-H41      10.73        13.74            7.36
    dos paradas M17-H19     11.01        12.44            9.58
    ====================  =========  ==============  ===============

    The one-stopper is better on average and better in the good quarter, and
    worse in the bad one: it is the gamble, and the mean hides that. AVERSE picks
    the two-stopper, SEEKING the one-stopper, and both are defensible — for
    different cars.

    **One honest limitation.** On the points objective the tail goes flat for
    exactly the cars this was built for: the worst quarter of a bubble car's races
    finishes outside the top ten, so every plan scores zero there and the search
    has nothing to climb. What rescues it is the fallback that was already in
    place — ``Objective.ADAPTIVE`` drops to ``POSITION`` when points are flat, and
    that is where the table above lives. Risk appetite therefore bites on
    position, not on points, and the table is the evidence that it bites.

    ``NEUTRAL``   the mean. What every objective did before, and still the right
                  choice when nothing is being protected.
    ``AVERSE``    the 25th percentile of the maximised value: make the bad case
                  good. A plan that sometimes wins and sometimes finishes twelfth
                  loses to one that reliably finishes eighth.
    ``SEEKING``   the 75th percentile: make the good case great. Correct for a car
                  with nothing to lose, where the mean undervalues the upside that
                  a safety car or a contrarian stint might hand it.
    ``ADAPTIVE``  averse while there is something to protect, seeking when there
                  is not — resolved from whether the car is in the points at all.

    Note that the leader being the most cautious car on the grid does **not** need
    this: it already falls out of the points table, where slipping one place costs
    seven. What this adds is the car on the bubble, which the table alone gets
    backwards.
    """

    NEUTRAL = "neutral"
    AVERSE = "averse"
    SEEKING = "seeking"
    ADAPTIVE = "adaptive"


#: Which tail each appetite scores on: ``(fraction, worst)``, or ``None`` for the
#: mean over everything.
#:
#: **A mean over the tail, not the quantile that bounds it.** The first attempt
#: used the quartile itself and it does not work, for a reason worth keeping: the
#: quantile of a discrete quantity is discrete. Finishing position is an integer
#: and championship points take eleven values, so the p25 of either is a step
#: function — measured, whole columns of candidate plans tied on exactly -12.00,
#: and a fitness that cannot tell two plans apart gives the search nothing to
#: climb. It kept whichever seed it seeded with.
#:
#: Averaging the tail fixes it: the mean of the worst quarter moves continuously
#: as probability shifts between outcomes, even when the outcomes themselves are
#: coarse. This is expected shortfall, the same measure risk desks use, and for
#: the same reason.
#:
#: A quarter is deliberately not extreme. Score the worst 5% and the plan is
#: chosen by the disaster case alone, which for a race car is a first-lap crash
#: that no strategy prevents.
RISK_TAIL: dict[Risk, tuple[float, bool] | None] = {
    Risk.NEUTRAL: None,
    Risk.AVERSE: (0.25, True),
    Risk.SEEKING: (0.25, False),
}


@dataclass(frozen=True)
class Car:
    """A car's state at the moment the plan is drawn up."""

    code: str
    compound: str
    tyre_age: int
    #: Seconds per lap currently lost to wear, versus fresh rubber.
    degradation_s: float
    #: Seconds per lap that loss is still growing by. Heavily shrunk; see above.
    degradation_rate: float
    #: Seconds behind the leader right now. The leader is 0.
    gap_leader_s: float
    #: Lap the plan starts from.
    from_lap: int
    #: Seconds per lap this car is slower than the fastest, with tyre state taken
    #: out. ``None`` means "infer it from the ground already lost", which is the
    #: only option once a race is running and **impossible before it starts**: a
    #: grid gap is a one-off offset, not a rate.
    #:
    #: Pass it explicitly for a pre-race plan. Qualifying measures exactly this —
    #: a lap time difference is already a per-lap quantity — and
    #: :func:`pace_from_qualifying` converts one into the other.
    pace_s: float | None = None


@dataclass(frozen=True)
class Stop:
    """One pit stop: the lap it happens on, and what goes on the car."""

    lap: int
    compound: str


@dataclass(frozen=True)
class Plan:
    """A sequence of stops for the rest of the race."""

    stops: tuple[Stop, ...]

    @property
    def count(self) -> int:
        return len(self.stops)

    def describe(self, car: Car, total_laps: int) -> str:
        """Stint list the way a pit wall would say it: ``M8-H34``."""
        parts = []
        compound, previous = car.compound, car.from_lap
        for stop in self.stops:
            parts.append(f"{compound[0]}{stop.lap - previous}")
            compound, previous = stop.compound, stop.lap
        parts.append(f"{compound[0]}{total_laps - previous}")
        return "-".join(parts)


def _from_cuts(cuts: Sequence[float], u: np.ndarray) -> np.ndarray:
    """Invert a distribution given by cuts, clamping outside the measured range.

    Beyond the 5th and 95th percentiles there is no data, and extrapolating a
    straight line there invents exactly in the tail, which is where it shows.
    """
    return np.interp(u, CUT_AT, np.asarray(cuts, dtype=float))


def _triangular(
    rng: np.random.Generator, spread: tuple[float, float, float], size: int
) -> np.ndarray:
    """Draw from a triangular over (p25, median, p75)."""
    low, mode, high = spread
    return rng.triangular(low, mode, high, size)


def _stints(plan: Plan, car: Car, total_laps: int) -> list[tuple[str, int, int]]:
    """Break a plan into ``(compound, start_lap, end_lap)`` stints."""
    out = []
    compound, start = car.compound, car.from_lap
    for stop in plan.stops:
        out.append((compound, start, stop.lap))
        compound, start = stop.compound, stop.lap
    out.append((compound, start, total_laps))
    return out


def draw_safety_car(model: RaceModel, rng: np.random.Generator, draws: int) -> np.ndarray:
    """Lap the safety car comes out on in each drawn race, ``-1`` for none."""
    happens = rng.random(draws) < model.p_safety_car
    share = _from_cuts(model.sc_start_cuts, rng.random(draws))
    lap = np.rint(share * model.total_laps).astype(int)
    return np.where(happens, lap, -1)


def _traffic_penalty(
    own: np.ndarray,
    rival_trace: np.ndarray | None,
    lap_index: int,
    model: RaceModel,
) -> np.ndarray:
    """Seconds lost on *this* lap for having someone in front.

    Charged every lap, on the gap of that lap, rather than once at the rejoin.
    Traffic is a condition of the whole stint: a car that fits fresh rubber catches
    the one ahead some laps later and then sits behind it, and the lap a stop
    happens on determines whether and when that occurs.

    It is also self-limiting, which is the right behaviour. A car inside a second
    is slowed, so the gap opens, so next lap the penalty is smaller — the pair
    settles near the pace of whoever is in front, which is what being stuck means.

    Args:
        own: The car's cumulative time at the end of this lap, per draw.
        rival_trace: ``(rivals, laps + 1, draws)``. ``None`` leaves traffic out.
        lap_index: Which row of the trace this lap is.
        model: Carries the circuit's traffic multiplier.

    Returns:
        Seconds to add, per draw. Zero in clear air.
    """
    if rival_trace is None or rival_trace.size == 0:
        return np.zeros_like(own)

    # Gap to the nearest car *ahead*: a rival whose cumulative time is smaller is
    # in front, and the smallest such difference is who you are looking at.
    at_lap = rival_trace[:, lap_index, :]
    ahead = np.where(at_lap < own, own - at_lap, np.inf)
    gap = ahead.min(axis=0)

    penalty = np.interp(gap, TRAFFIC_GAP_S, TRAFFIC_PENALTY_S) * model.traffic_scale
    return np.where(np.isfinite(gap), penalty, 0.0)


#: Codes for what flag a lap is run under, ordered by how cheap a stop is on it.
GREEN, VSC_FLAG, SC_FLAG, RED_FLAG = 0, 1, 2, 3


def _draw_count(weights: Sequence[float], rng: np.random.Generator, draws: int) -> np.ndarray:
    """How many periods of one kind each drawn race gets."""
    return rng.choice(len(weights), size=draws, p=np.asarray(weights) / np.sum(weights))


def draw_neutralisations(model: RaceModel, rng: np.random.Generator, draws: int) -> np.ndarray:
    """What flag every lap of every drawn race is run under.

    Replaces the old single-safety-car draw. Each race gets its own number of red
    flags, safety cars and VSCs from the measured distributions, each starting
    where they actually start and lasting as long as they actually last.

    That matters more than it sounds. Nearly half of real races see two or more
    periods, and the previous model drew one; and red flags were not represented
    at all, though a red-flag tyre change is **free** and is the single cheapest
    thing that can happen to a strategy. Monza 2026 turned on exactly that.

    Where periods overlap, the cheaper flag wins: a lap under both a safety car
    and a red flag is a red-flag lap, because that is what the stop costs.

    Returns:
        ``(total_laps + 1, draws)`` of flag codes, indexed by lap number.
    """
    flags = np.zeros((model.total_laps + 1, draws), dtype=np.int8)

    for weights, cuts, length, code in (
        (model.n_vsc, model.vsc_start_cuts, model.vsc_laps, VSC_FLAG),
        (model.n_sc, model.sc_start_cuts_full, model.sc_laps, SC_FLAG),
        (model.n_red, model.red_start_cuts, model.red_laps, RED_FLAG),
    ):
        counts = _draw_count(weights, rng, draws)
        for period in range(int(counts.max()) if counts.size else 0):
            active = counts > period
            if not active.any():
                continue
            share = _from_cuts(cuts, rng.random(draws))
            start = np.clip(np.rint(share * model.total_laps).astype(int), 1, model.total_laps)
            for offset in range(length):
                lap = np.clip(start + offset, 0, model.total_laps)
                # The cheaper flag wins where they overlap.
                np.maximum.at(flags, (lap[active], np.flatnonzero(active)), code)

    return flags


def _pit_cost(
    flags: np.ndarray, lap: int, model: RaceModel, rng: np.random.Generator, draws: int
) -> np.ndarray:
    """What a stop on ``lap`` costs in each drawn race, given the flag it meets."""
    green = _triangular(rng, model.pit_loss_green, draws)
    vsc = _triangular(rng, model.pit_loss_vsc, draws)
    sc = _triangular(rng, model.pit_loss_sc, draws)
    red = _triangular(rng, model.pit_loss_red, draws)

    at_lap = flags[min(lap, flags.shape[0] - 1)]
    cost = green.copy()
    cost = np.where(at_lap == VSC_FLAG, vsc, cost)
    cost = np.where(at_lap == SC_FLAG, sc, cost)
    return np.where(at_lap == RED_FLAG, red, cost)


def race_trace(
    plan: Plan,
    car: Car,
    model: RaceModel,
    rng: np.random.Generator,
    draws: int,
    flags: np.ndarray | None = None,
    rival_trace: np.ndarray | None = None,
) -> np.ndarray:
    """Cumulative time at the end of every remaining lap, across ``draws`` races.

    Each lap adds two things: the car's baseline pace deficit, which it carries
    whatever it does, and its tyre deficit, which resets when it stops. The
    current gap to the leader anchors the total. A stop adds the pit loss and,
    when ``rival_trace`` is supplied, the cost of whatever it drops the car behind.

    ``degradation_s`` never enters as an absolute — it is measured against each
    stint's own reference lap and is not comparable between cars. What it means is
    how much *this* car stands to gain by fitting fresh rubber, and that is the
    only role it plays.

    Args:
        plan: The stops to run.
        car: Its state now.
        model: The measured distributions to draw from.
        rng: Generator, so a reported plan is reproducible.
        draws: How many races to run.
        flags: ``(total_laps + 1, draws)`` from :func:`draw_neutralisations`.
            Shared across cars so every car in a given draw meets the *same* race
            — a safety car that helps one hurts another, and drawing it per car
            would wash that out. ``None`` runs every race green.
        rival_trace: ``(rivals, laps + 1, draws)`` for pricing traffic. Omit to
            leave the traffic term out entirely.

    Returns:
        ``(laps + 1, draws)``. Row 0 is the current gap; the last row is the flag.
    """
    laps_left = model.total_laps - car.from_lap
    trace = np.empty((laps_left + 1, draws), dtype=float)
    total = np.full(draws, car.gap_leader_s, dtype=float)
    trace[0] = total

    current = float(np.clip(car.degradation_s, -MAX_DEFICIT_S, MAX_DEFICIT_S))
    # Baseline pace: seconds per lap this car gives away to the fastest, tyre
    # state excluded. There are two ways to know it and they apply at different
    # moments.
    #
    # Given explicitly (``pace_s``), it is used as-is. That is the pre-race case,
    # where qualifying measures it directly.
    #
    # Otherwise it is inferred from ground already lost. Before the race has run
    # there is no such history — a grid gap is a one-off offset, not a rate — and
    # charging it per lap put a car nineteenth on the grid 4.75 s/lap behind,
    # which over 71 laps is five and a half minutes. So the inference yields zero
    # at lap 1, and a car built without ``pace_s`` gets the same plan from pole as
    # from twentieth. That is wrong, and ``pace_s`` is how it gets fixed.
    if car.pace_s is not None:
        baseline = car.pace_s
    elif car.from_lap <= 1:
        baseline = 0.0
    else:
        baseline = car.gap_leader_s / (car.from_lap - 1) - current
    stop_at = {stop.lap: stop for stop in plan.stops}

    rate = _from_cuts(model.wear_cuts[car.compound], rng.random(draws)) + RATE_SHRINK * (
        car.degradation_rate - ROLLING_MEDIAN_S
    )
    deficit = np.full(draws, current)
    # El escalón entra RELATIVO al compuesto que el auto lleva ahora, igual que
    # todo lo demás en esta función: el gap actual ya refleja con qué anda, así
    # que la tanda en curso aporta cero y sólo se cobran los cambios.
    own_offset = COMPOUND_OFFSET_S.get(car.compound, 0.0)
    step = 0.0

    for offset in range(laps_left):
        lap = car.from_lap + offset
        total = total + baseline + deficit + step
        # A tyre never gets faster than new, and never worse than the measured
        # 99th percentile, so the deficit is clamped at both ends.
        deficit = np.clip(deficit + rate, 0.0, MAX_DEFICIT_S)
        total = total + rng.normal(0.0, model.lap_noise_s, draws)
        total = total + _traffic_penalty(total, rival_trace, offset + 1, model)

        stop = stop_at.get(lap + 1)
        if stop is not None:
            total = total + _pit_cost(flags, stop.lap, model, rng, draws)

            # Fresh rubber: the deficit restarts, which is the gain from stopping.
            rate = _from_cuts(model.wear_cuts[stop.compound], rng.random(draws))
            deficit = np.zeros(draws)
            step = COMPOUND_OFFSET_S.get(stop.compound, 0.0) - own_offset

        trace[offset + 1] = total

    return trace


def race_time(
    plan: Plan,
    car: Car,
    model: RaceModel,
    rng: np.random.Generator,
    draws: int,
    flags: np.ndarray | None = None,
    rival_trace: np.ndarray | None = None,
) -> np.ndarray:
    """Finishing time only. See :func:`race_trace` for what it is made of."""
    return race_trace(plan, car, model, rng, draws, flags, rival_trace)[-1]


def _enforce_two_compounds(stops: tuple[Stop, ...], car: Car, model: RaceModel) -> tuple[Stop, ...]:
    """Make a plan legal under B6.3.8 by changing what the last stop fits.

    Only applies to a plan that starts on lap 1, because only then is the full
    set of compounds known. A plan taken up mid-race cannot be checked and is
    returned untouched.

    The repair is deliberately minimal: change the compound of the final stop to
    something the car has not used. Adding a stop would be cheaper to write and
    much more expensive to run, and a team facing this problem changes what it
    fits rather than stopping again.

    A plan with no stops at all cannot be made legal, and is returned as it is —
    the fitness will price it, and it will lose.
    """
    if car.from_lap > 1 or not stops:
        return stops

    used = {car.compound, *(stop.compound for stop in stops)}
    if len(used) >= REQUIRED_COMPOUNDS:
        return stops

    # Everything so far is the same compound. Swap the last stop for the most
    # durable alternative, which is the one least likely to cost time.
    alternative = next(c for c in DRY if c not in used)
    return (*stops[:-1], replace(stops[-1], compound=alternative))


def _repair(stops: Sequence[Stop], car: Car, model: RaceModel) -> tuple[Stop, ...]:
    """Turn any stop list into a plan the evidence can actually price.

    Three things are enforced: stops in order and at least ``MIN_STINT`` apart, no
    stop so late that there is no race left to amortise it, and no stint longer
    than :data:`MAX_STINT` for its compound. The last one binds more often than it
    sounds — the first stint already carries ``car.tyre_age`` laps of wear, so a
    set thirteen laps old only has the remainder of its budget left.

    A stint that would run over budget gets a stop inserted at the limit rather
    than being thrown away. Throwing it away would bias the search toward whatever
    happened to be legal by accident; inserting the stop keeps the idea and makes
    it affordable.
    """
    fixed: list[Stop] = []
    previous = car.from_lap
    compound = car.compound
    age = car.tyre_age

    def budget(on: str, used: int) -> int:
        return max(MIN_STINT, MAX_STINT.get(on, 40) - used)

    for stop in sorted(stops, key=lambda s: s.lap):
        lap = max(stop.lap, previous + MIN_STINT)
        # Force a stop before the current set runs past what has been measured.
        limit = previous + budget(compound, age)
        if lap > limit:
            lap = limit
        if lap > model.total_laps - MIN_STINT:
            break
        fixed.append(replace(stop, lap=lap))
        previous, compound, age = lap, stop.compound, 0

    # The final stint has the same budget, so keep stopping until it fits.
    while previous + budget(compound, age) < model.total_laps:
        lap = previous + budget(compound, age)
        # Whatever covers the rest; hard if nothing shorter will.
        nxt = next(
            (c for c in ("SOFT", "MEDIUM", "HARD") if MAX_STINT[c] >= model.total_laps - lap),
            "HARD",
        )
        # Running the current set to its limit can leave a stop so late it is
        # worthless. Pull it forward instead — far enough that the *new* set
        # covers what is left, which is the earliest lap that solves both stints.
        if lap > model.total_laps - MIN_STINT:
            lap = max(previous + MIN_STINT, model.total_laps - MAX_STINT["HARD"])
            nxt = "HARD"
        if lap > model.total_laps - MIN_STINT:
            break  # nothing legal left: the race is too short to fix it
        fixed.append(Stop(lap, nxt))
        previous, compound, age = lap, nxt, 0

    return _enforce_two_compounds(tuple(fixed), car, model)


def _heuristic_plan(car: Car, model: RaceModel, stops: int) -> Plan:
    """The obvious plan: split what is left evenly, on the most durable compound."""
    if stops <= 0:
        return Plan(_repair([], car, model))
    step = (model.total_laps - car.from_lap) // (stops + 1)
    laps = [car.from_lap + step * (index + 1) for index in range(stops)]
    return Plan(_repair([Stop(lap, "HARD") for lap in laps], car, model))


def _tyre_life_plan(car: Car, model: RaceModel) -> Plan:
    """Stop when the set reaches its measured median life here. The pit-wall rule."""
    life = {"HARD": 24, "MEDIUM": 22, "SOFT": 12}
    stops: list[Stop] = []
    lap, compound = car.from_lap, car.compound
    remaining = life.get(compound, 24) - car.tyre_age
    while lap + max(remaining, MIN_STINT) < model.total_laps - MIN_STINT:
        lap += max(remaining, MIN_STINT)
        compound = "HARD"
        remaining = life[compound]
        stops.append(Stop(lap, compound))
    return Plan(_repair(stops, car, model))


def _random_plan(car: Car, model: RaceModel, rng: np.random.Generator, max_stops: int) -> Plan:
    """A plan drawn from nowhere in particular, to seed the population.

    Zero stops is a legal candidate. It was not, at first, and that quietly
    removed the most conservative option there is — a car that has already used
    two compounds and is holding a points place may well be right to stay out.
    Whether it *has* used two is something the lap-30 snapshot cannot say, so a
    zero-stop winner is reported and left to the reader rather than filtered.
    """
    count = int(rng.integers(0, max_stops + 1))
    room = max(MIN_STINT + 1, model.total_laps - MIN_STINT - car.from_lap)
    laps = car.from_lap + rng.integers(MIN_STINT, room, count)
    return Plan(_repair([Stop(int(lap), str(rng.choice(DRY))) for lap in laps], car, model))


def _crossover(a: Plan, b: Plan, car: Car, model: RaceModel, rng: np.random.Generator) -> Plan:
    """One-point crossover: early stops from one parent, later ones from the other.

    Cutting on lap rather than on index is what makes this meaningful. The child
    inherits a coherent first half of the race from one parent and a coherent
    second half from the other, instead of interleaving two unrelated plans.
    """
    cut = int(rng.integers(car.from_lap, model.total_laps))
    stops = [s for s in a.stops if s.lap <= cut] + [s for s in b.stops if s.lap > cut]
    return Plan(_repair(stops, car, model))


def _mutate(plan: Plan, car: Car, model: RaceModel, rng: np.random.Generator) -> Plan:
    """Lengthen a stint, shorten it, change its compound, or add and drop a stop."""
    stops = list(plan.stops)
    choice = rng.random()

    if choice < 0.15 and len(stops) < 4:
        lap = int(rng.integers(car.from_lap + MIN_STINT, model.total_laps))
        stops.append(Stop(lap, str(rng.choice(DRY))))
    elif choice < 0.3 and stops:
        stops.pop(int(rng.integers(0, len(stops))))
    elif stops:
        index = int(rng.integers(0, len(stops)))
        if choice < 0.65:
            stops[index] = replace(stops[index], lap=stops[index].lap + int(rng.integers(-6, 7)))
        else:
            stops[index] = replace(stops[index], compound=str(rng.choice(DRY)))

    return Plan(_repair(stops, car, model))


def _positions(times: np.ndarray, rival_times: np.ndarray) -> np.ndarray:
    """Finishing position per draw: one plus however many rivals came home first."""
    if rival_times.size == 0:
        return np.ones_like(times, dtype=int)
    return 1 + (rival_times < times).sum(axis=0)


def _position_histogram(position: np.ndarray) -> dict[int, int]:
    """En cuántas de las carreras sorteadas el plan terminó en cada puesto.

    Las muestras de posición ya están: la media y el desvío salen de ellas y
    después se tiraban. Conservarlas contadas es lo que permite responder
    P(podio) o P(zona de puntos) sin volver a sortear — y volver a sortear daría
    otro número, porque serían otras carreras que las que eligieron el plan.

    Args:
        position: Puesto de llegada por sorteo, como lo devuelve :func:`_positions`.

    Returns:
        Puesto -> cantidad de carreras que terminaron ahí, ordenado por puesto y
        sin los puestos que no ocurrieron. La suma es la cantidad de sorteos.
    """
    places, races = np.unique(position, return_counts=True)
    return {int(place): int(count) for place, count in zip(places, races, strict=True)}


def _points(position: np.ndarray) -> np.ndarray:
    """Championship points for a finishing position, zero from eleventh."""
    table = np.array((*POINTS, *([0] * 60)), dtype=float)
    return table[np.clip(position - 1, 0, len(table) - 1)]


#: Below this many expected points, the points objective carries no gradient and
#: position is used instead. One tenth of a point is a hundredth of tenth place.
POINTS_FLOOR = 0.1


#: Distributional objectives: already a probability over the spread, so there is
#: no per-draw value to take a quantile of. An indicator's quantile is 0 or 1.
_PROBABILITY_OBJECTIVES = (Objective.PODIUM, Objective.IN_POINTS)


def _values(times: np.ndarray, rival_times: np.ndarray, objective: Objective) -> np.ndarray:
    """The quantity being maximised, **one value per drawn race**.

    Keeping the spread instead of collapsing it immediately is what lets the
    search express risk appetite: see :class:`Risk`.
    """
    if objective is Objective.TIME:
        return -times
    position = _positions(times, rival_times)
    if objective is Objective.POSITION:
        return -position.astype(float)
    if objective is Objective.PODIUM:
        return (position <= 3).astype(float)
    if objective is Objective.IN_POINTS:
        return (position <= 10).astype(float)
    return _points(position)


def _tail_mean(values: np.ndarray, fraction: float, worst: bool) -> float:
    """Mean of the worst (or best) ``fraction`` of outcomes — expected shortfall."""
    keep = max(1, int(round(len(values) * fraction)))
    ordered = np.sort(values)
    return float(ordered[:keep].mean() if worst else ordered[-keep:].mean())


def _score(
    times: np.ndarray,
    rival_times: np.ndarray,
    objective: Objective,
    tail: tuple[float, bool] | None = None,
) -> float:
    """Collapse the spread of outcomes into the single number being maximised.

    Args:
        times: Finishing time per drawn race.
        rival_times: The same for each rival, one row each.
        objective: What counts as better.
        tail: ``None`` takes the mean over every draw, which is risk-neutral.
            ``(fraction, worst)`` averages that share of the distribution: the bad
            end protects, the good end gambles. See :data:`RISK_TAIL`. Ignored for
            the probability objectives, which are already summaries of the spread
            rather than per-draw quantities.

    Returns:
        The value to maximise.
    """
    values = _values(times, rival_times, objective)
    if tail is None or objective in _PROBABILITY_OBJECTIVES:
        return float(values.mean())
    return _tail_mean(values, *tail)


class Engine(StrEnum):
    """Which evolution loop runs the search.

    Both share everything that matters — the same seeds, the same fitness with
    common random numbers, the same repair, crossover and mutation, the same
    held-out scoring. Only the loop differs, which is what makes them comparable.

    ``BUILTIN``  the loop written for this project: elitism on the top quarter,
                 one parent drawn from the elite and one from the whole
                 population, mutation at 0.6.
    ``DEAP``     the same operators registered on a ``deap.base.Toolbox`` and run
                 through ``algorithms.eaMuPlusLambda``, which is the tool the
                 cátedra recommends for Unit 3.
    """

    BUILTIN = "builtin"
    DEAP = "deap"


@dataclass(frozen=True)
class Generation:
    """La población en un momento de la evolución, para ver cómo converge.

    Lo que hace visible que esto es un algoritmo genético y no una tabla de
    consulta no es el plan que sale al final: es la población moviéndose. Arranca
    sembrada con las heurísticas y termina concentrada en una cantidad de paradas
    — o no termina de concentrarse, que también dice algo, y está medido acá
    mismo: un auto decimoctavo bajo ``POINTS`` se queda repartido entre una y
    cuatro paradas en partes casi iguales, y bajo ``POSITION`` converge a una sola
    en 0,87. Ver :class:`Objective`.

    Se anota una generación **más** que las que se corren, porque la cero es la
    población sembrada —las heurísticas y los planes al azar— antes de la primera
    selección. Sin ella no se ve desde dónde arrancó la búsqueda, que es contra lo
    que hay que medir lo que encontró.
    """

    #: Número de generación. La cero es la población sembrada.
    index: int
    #: Mejor aptitud de la generación, **en muestra**: sobre los mismos sorteos
    #: contra los que corre la búsqueda. No es comparable con :attr:`Search.score`,
    #: que se mide sobre sorteos retenidos, y por la misma razón de siempre: el
    #: máximo de muchas estimaciones ruidosas se elige en parte por suerte.
    best: float
    #: Cómo se reparte la población entre cantidades de parada, en el mismo formato
    #: que :attr:`Search.stop_distribution`.
    stop_distribution: dict[int, float]
    #: El plan que sacó esa aptitud. Sin él el registro muestra que la búsqueda
    #: mejora pero no **qué** encontró, y la diferencia entre «el valor subió en la
    #: generación 12» y «en la generación 12 pasó de dos paradas al duro a tres»
    #: es la diferencia entre un gráfico y una explicación.
    #:
    #: ``None`` sólo si la población llegó vacía, que no pasa.
    best_plan: Plan | None = None


def _stop_shares(plans: Sequence[Plan]) -> dict[int, float]:
    """Cómo se reparte una población entre cantidades de parada.

    Acumula ``1/n`` una vez por plan en lugar de dividir el conteo al final. Es lo
    mismo salvo por el último bit de coma flotante, y ese bit está en cifras ya
    publicadas en ``docs/tp/informe.md``.

    Args:
        plans: La población, en el orden en que venga.

    Returns:
        Cantidad de paradas -> fracción de la población, ordenado por paradas.
    """
    shares: dict[int, float] = {}
    for plan in plans:
        shares[plan.count] = shares.get(plan.count, 0.0) + 1.0 / len(plans)
    return dict(sorted(shares.items()))


def _generation(index: int, scored: Sequence[tuple[Plan, float]]) -> Generation:
    """Anotar el estado de una población sin exigirle que venga ordenada."""
    champion = max(scored, key=lambda pair: pair[1])
    return Generation(
        index=index,
        best=champion[1],
        stop_distribution=_stop_shares([plan for plan, _ in scored]),
        best_plan=champion[0],
    )


def _evolve(
    scored: list[tuple[Plan, float]],
    fitness: Callable[[Plan], float],
    car: Car,
    model: RaceModel,
    rng: np.random.Generator,
    population: int,
    generations: int,
    history: bool = False,
) -> tuple[list[tuple[Plan, float]], tuple[Generation, ...]]:
    """The hand-written loop: elitist, with one parent always from the elite.

    Args:
        scored: Población inicial ya evaluada.
        fitness: La aptitud, con números aleatorios comunes.
        car: El auto que se optimiza.
        model: Distribuciones medidas de la carrera.
        rng: Generador, compartido con los operadores.
        population: Individuos por generación.
        generations: Rondas de selección.
        history: Anotar cada generación. Apagado por defecto porque son
            ``generations + 1`` registros que casi ninguna llamada mira. Anotar no
            toca el generador aleatorio ni el orden en que se lo consume, así que
            encenderlo no cambia el plan que sale.

    Returns:
        La población final puntuada y el registro por generación, vacío si no se
        pidió.
    """
    log: list[Generation] = []
    for index in range(generations):
        if history:
            log.append(_generation(index, scored))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        # Elitism on the top quarter: a good plan is never lost to a bad draw.
        elite = scored[: max(2, population // 4)]
        children: list[tuple[Plan, float]] = list(elite)

        while len(children) < population:
            a = elite[int(rng.integers(0, len(elite)))][0]
            b = scored[int(rng.integers(0, len(scored)))][0]
            child = _crossover(a, b, car, model, rng)
            if rng.random() < 0.6:
                child = _mutate(child, car, model, rng)
            children.append((child, fitness(child)))

        scored = children

    if history:
        log.append(_generation(generations, scored))
    return scored, tuple(log)


@dataclass(frozen=True)
class Search:
    """What the search found."""

    car: str
    objective: Objective
    #: The appetite actually used. Worth reporting because ``Risk.ADAPTIVE``
    #: resolves to one of the others before the search runs, and which one it
    #: picked is part of the recommendation.
    risk: Risk
    best: Plan
    #: Value of the objective for ``best``, on **held-out draws**: a fresh set of
    #: races the search never saw. This is the number to report.
    score: float
    #: The same, on the draws the search optimised against. Always at least as
    #: good, and the difference is how much the search flattered itself.
    score_in_sample: float
    #: Probability mass over stop counts across the final population — how sure
    #: the search is, which is more honest than reporting one plan as the answer.
    stop_distribution: dict[int, float]
    mean_position: float
    #: Spread of finishing position under ``best``. How much risk the plan takes,
    #: which is the objective's doing: points punish variance at the front, where
    #: a place costs seven, and reward it around tenth, where the downside is
    #: already zero.
    sd_position: float
    mean_points: float
    #: What the choice is worth: best score minus the worst in the final
    #: population. Near zero means every plan is equivalent and the recommendation
    #: is arbitrary — worth knowing before acting on it.
    decision_value: float
    #: Runner-up plans, best first, for showing alternatives. Scored in-sample.
    alternatives: tuple[tuple[Plan, float], ...]
    #: En cuántas de las carreras sorteadas ``best`` terminó en cada puesto:
    #: puesto -> cantidad, ordenado por puesto y sin los puestos que no ocurrieron,
    #: de modo que los valores suman ``draws``.
    #:
    #: Es la distribución que hay detrás de ``mean_position``, que hasta ahora se
    #: resumía en dos números y se tiraba. De acá salen P(ganar), P(podio) y
    #: P(zona de puntos) sin volver a sortear: son cuentas sobre las **mismas**
    #: carreras que eligieron el plan, no sobre otras nuevas.
    #:
    #: Vacío cuando la búsqueda corrió sin instrumentar, que es el caso por
    #: omisión. Vale lo mismo que ``mean_position``: es una posición proyectada
    #: contra rivales que no reaccionan, no una probabilidad de la carrera real.
    position_histogram: dict[int, int] = field(default_factory=dict)
    #: Una entrada por generación, la cero siendo la población sembrada. Vacío
    #: cuando la búsqueda corrió sin instrumentar. Ver :class:`Generation`.
    history: tuple[Generation, ...] = ()

    @property
    def optimism(self) -> float:
        """How much better the search thought it did than it did.

        A Monte Carlo fitness is noisy, and selecting the maximum of many noisy
        estimates selects partly for luck — the same reason a model scored on its
        training set looks better than it is. Measured here at 6.9 s of race time
        with 200 draws, falling to about 1 s by 1,500. Reporting the in-sample
        figure would have overstated every plan in this project.
        """
        return self.score_in_sample - self.score


def optimise(
    car: Car,
    rivals: Sequence[Car],
    rival_plans: Sequence[Plan],
    model: RaceModel | None = None,
    *,
    objective: Objective = Objective.POINTS,
    risk: Risk = Risk.NEUTRAL,
    engine: Engine = Engine.BUILTIN,
    population: int = 48,
    generations: int = 30,
    draws: int = 1200,
    max_stops: int = 4,
    seed: int = 0,
    instrument: bool = False,
) -> Search:
    """Search for the plan that best serves ``objective``.

    Rivals are simulated once, before the search starts, and their whole lap-by-lap
    trace reused for every candidate. That is what makes this cheap, and it rests
    on rivals not reacting to the focal car — wrong precisely when two cars are
    racing each other wheel to wheel.

    One asymmetry follows from that and is worth naming: the focal car pays a
    traffic penalty and the rivals do not, because pricing traffic for a rival
    would need its own neighbours' traces, which is circular. The effect is to
    flatter every rival slightly, so the focal car's projected position is a
    little pessimistic. It applies equally to every candidate plan, so it does not
    bias the *choice* between them.

    All cars are assumed to share ``from_lap``, which holds for a snapshot taken
    at one moment of one race.

    Args:
        car: The car being optimised.
        rivals: Everyone else still running.
        rival_plans: One plan per rival, in the same order. Drawn, not optimised:
            giving every car the optimum would describe a race nobody has run.
        model: Measured distributions; 2026 Zandvoort defaults if omitted.
        objective: What "better" means. See :class:`Objective`.
        risk: How much of the spread to gamble. See :class:`Risk`. The default is
            neutral, which is the mean and is what every earlier result used.
        engine: Which evolution loop to run. See :class:`Engine`.
        population: Plans held per generation.
        generations: Rounds of selection.
        draws: Races simulated per fitness evaluation. **1,200 is a floor, not a
            preference.** A single evaluation at 400 draws has a standard error of
            1.2 s of race time, against differences between plans of a couple of
            seconds, and at that level the search picks the plan that got lucky:
            measured, it came out 0.71 s per race *worse* than a napkin rule. At
            1,200 it matches or beats the rule. Below this the answer is noise
            wearing a confident face.
        max_stops: Cap on stops in a plan.
        seed: Reproducibility.
        instrument: Conservar lo que la búsqueda calcula y hoy tira: el histograma
            de puestos de llegada del plan ganador y el registro por generación.
            Apagado por omisión, porque son miles las llamadas que no los miran y
            cada una pagaría memoria por ellos. **Encenderlo no cambia el
            resultado**: no se sortea ninguna carrera de más ni se toca el orden en
            que se consume el generador, se guarda lo que ya estaba calculado.

    Returns:
        The best plan found, its score **on held-out draws**, the spread of stop
        counts the population settled on, and a few runners-up. Con ``instrument``
        también el histograma de puestos y el registro por generación.

        The held-out score is the one to report. A Monte Carlo fitness is noisy,
        and taking the maximum over a population selects partly for which plan got
        lucky on those particular races. Measured, the in-sample figure overstates
        by about 7 seconds of race time at 200 draws and 1 second at 1,500.
    """
    model = model or RaceModel()
    rng = np.random.default_rng(seed)
    wanted = objective
    if objective is Objective.ADAPTIVE:
        objective = Objective.POINTS

    # Every neutralisation the race throws, shared by everyone in it.
    flags = draw_neutralisations(model, rng, draws)

    # Rivals get the full lap-by-lap trace, not only a finishing time, because
    # pricing traffic needs to know where they are on the lap the focal car stops.
    # They are still simulated once and reused, which is what keeps this cheap:
    # rivals do not react to the focal car's plan.
    rival_trace = (
        np.stack(
            [
                race_trace(plan, rival, model, rng, draws, flags)
                for rival, plan in zip(rivals, rival_plans, strict=True)
            ]
        )
        if rivals
        else np.empty((0, model.total_laps - car.from_lap + 1, draws))
    )
    rival_times = rival_trace[:, -1, :] if rivals else np.empty((0, draws))

    # Risk appetite has to be settled before the search, because it changes what
    # the fitness *is*. ADAPTIVE resolves it from whether the car has anything
    # worth protecting: score the obvious plan neutrally and see if it is in the
    # points at all. One extra evaluation, against a whole search.
    if risk is Risk.ADAPTIVE:
        probe = _heuristic_plan(car, model, 1)
        probe_gen = np.random.default_rng(seed + 4441)
        holding = _score(
            race_time(probe, car, model, probe_gen, draws, flags, rival_trace),
            rival_times,
            Objective.POINTS,
        )
        risk = Risk.AVERSE if holding >= POINTS_FLOOR else Risk.SEEKING
    tail = RISK_TAIL[risk]

    def fitness(plan: Plan) -> float:
        # **Common random numbers.** Every candidate is evaluated against the
        # *same* drawn races, by restarting the generator at a fixed seed rather
        # than letting the shared one advance.
        #
        # This is not a detail. Measured, a single fitness evaluation at 400 draws
        # has a standard error of 1.2 s of race time, against real differences
        # between plans of a couple of seconds — and with an advancing generator
        # each candidate met a different set of races, so the comparison carried
        # that noise twice over. The same plan scored anywhere between 126.6 and
        # 136.0 s. The search was selecting on luck.
        #
        # Sharing the draws does not reduce the error on any single estimate. It
        # reduces the error on the *difference* between two plans, which is the
        # only quantity a search actually uses.
        common = np.random.default_rng(seed + 4441)
        times = race_time(plan, car, model, common, draws, flags, rival_trace)
        return _score(times, rival_times, objective, tail)

    # Seed the population with the obvious plans as well as random ones.
    #
    # Purely random seeding does not work here and the reason is instructive. A
    # plan has to get the laps *and* the compounds right at the same time, and
    # with three compounds per stop only one combination in nine is the good one.
    # Measured on this grid: 118 random two-stop plans, and the best scored 93.3 s
    # against 91.0 for a hand-built even split on hards — the search space
    # contained the answer and the seeds never landed near it, while one-stop
    # plans scored 93.6 and looked just as good.
    #
    # Seeding with the heuristics also settles the comparison honestly. The search
    # now starts from the napkin rule, so it can only match or beat it, and the
    # question becomes whether it finds anything better rather than whether it
    # rediscovers the obvious.
    seeds = [_heuristic_plan(car, model, stops) for stops in range(max_stops + 1)]
    seeds += [_tyre_life_plan(car, model)]
    seeds += [_random_plan(car, model, rng, max_stops) for _ in range(population - len(seeds))]
    scored = [(plan, fitness(plan)) for plan in seeds]

    if engine is Engine.DEAP:
        from boxbox_ml.deap_search import evolve as evolve_deap

        scored, history = evolve_deap(
            scored, fitness, car, model, rng, population, generations, instrument
        )
    else:
        scored, history = _evolve(
            scored, fitness, car, model, rng, population, generations, instrument
        )

    scored.sort(key=lambda pair: pair[1], reverse=True)
    best, in_sample = scored[0]

    # Held-out draws: a fresh race set the search never optimised against. The
    # maximum of many noisy estimates is biased upward, so the in-sample figure
    # flatters whatever won — exactly like scoring a model on its training set.
    holdout = np.random.default_rng(seed + 9973)
    holdout_flags = draw_neutralisations(model, holdout, draws)
    holdout_rivals = (
        np.stack(
            [
                race_trace(plan, rival, model, holdout, draws, holdout_flags)
                for rival, plan in zip(rivals, rival_plans, strict=True)
            ]
        )
        if rivals
        else np.empty((0, model.total_laps - car.from_lap + 1, draws))
    )
    holdout_times = race_time(best, car, model, holdout, draws, holdout_flags, holdout_rivals)
    holdout_rival_times = holdout_rivals[:, -1, :] if rivals else np.empty((0, draws))
    score = _score(holdout_times, holdout_rival_times, objective, tail)

    # Where the points objective runs out of gradient — and it runs out in two
    # different ways, which the first version of this conflated.
    #
    # The test used to compare the **risk-adjusted** score against the floor. For
    # a cautious car that score is the mean of the worst quarter, and for anyone
    # near the points cliff that quarter is all zeros by construction. So a car
    # eleventh on the grid with a **31.7% chance of scoring** was being sent to
    # optimise position, because its bad quarter never scores. The comment said
    # "points unreachable"; what was flat was the tail, which is not the same
    # thing. Measured, that cost the bubble cars about a third of their expected
    # points.
    #
    # Now the two cases are separated:
    #
    # * Points genuinely out of reach — the **expected** value is under the floor.
    #   Position is the right objective; there is nothing to score.
    # * Points reachable but the chosen tail is flat. Falling to position throws
    #   away the whole points structure for a car whose entire race is about one
    #   place. What it actually wants is the **probability of finishing in the
    #   points**, which has gradient exactly where the tail does not — and which
    #   is the same thing a pit wall means by "hold tenth".
    if wanted is Objective.ADAPTIVE and objective is Objective.POINTS:
        expected = _score(holdout_times, holdout_rival_times, Objective.POINTS)
        fallback = None
        if expected < POINTS_FLOOR:
            fallback = Objective.POSITION
        elif score < POINTS_FLOOR:
            fallback = Objective.IN_POINTS
        if fallback is not None:
            return optimise(
                car,
                rivals,
                rival_plans,
                model,
                objective=fallback,
                risk=risk,
                engine=engine,
                population=population,
                generations=generations,
                draws=draws,
                max_stops=max_stops,
                seed=seed,
                instrument=instrument,
            )

    position = _positions(race_time(best, car, model, rng, draws, flags, rival_trace), rival_times)

    seen = {best.stops}
    alternatives: list[tuple[Plan, float]] = []
    for plan, value in scored[1:]:
        if plan.stops in seen:
            continue
        seen.add(plan.stops)
        alternatives.append((plan, value))
        if len(alternatives) == 3:
            break

    return Search(
        car=car.code,
        objective=objective,
        risk=risk,
        best=best,
        score=score,
        score_in_sample=in_sample,
        stop_distribution=_stop_shares([plan for plan, _ in scored]),
        mean_position=float(position.mean()),
        sd_position=float(position.std()),
        mean_points=float(_points(position).mean()),
        decision_value=float(score - scored[-1][1]),
        alternatives=tuple(alternatives),
        # El mismo array de posiciones del que salen la media y el desvío: contar
        # es gratis, volver a sortear daría otro número.
        position_histogram=_position_histogram(position) if instrument else {},
        history=history,
    )
