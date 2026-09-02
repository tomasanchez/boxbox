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

## What is not modelled

No on-track blocking: a car that is faster is assumed to get past, which is
generous at Monaco and roughly fair at Zandvoort. No traffic on out-laps, no
reliability, no driver error beyond the measured lap noise. Rivals do not react to
the focal car's plan — their plans are drawn once per race and held, which is why
a rival's finishing time can be computed once and reused across every candidate.
That approximation is what makes the search cheap, and it is wrong in exactly the
case where two cars are fighting each other directly.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum

import numpy as np

#: Championship points for the first ten places. Eleventh onward scores nothing,
#: which is the discontinuity that makes strategy interesting outside the top ten.
POINTS = (25, 18, 15, 12, 10, 8, 6, 4, 2, 1)

#: Dry compounds, hardest first.
DRY = ("HARD", "MEDIUM", "SOFT")

#: Laps a stint has to run before it counts as one.
MIN_STINT = 6

#: Probabilities at which every measured distribution below is cut.
CUT_AT = np.array([0.05, 0.15, 0.25, 0.35, 0.5, 0.65, 0.75, 0.85, 0.95])

#: How much of a car's own five-lap wear slope survives into the projection.
#: Measured attenuation: the rolling estimate correlates 0.183 with what the stint
#: went on to do and is 3.7x too dispersed, so 0.183 * 0.127 / 0.466.
RATE_SHRINK = 0.05

#: Median of that rolling slope across the field, which the shrinkage centres on.
ROLLING_MEDIAN_S = 0.022

#: Largest per-lap deficit versus fresh rubber that has been measured, in seconds:
#: the 99th percentile late in a stint. Past this the set gets changed.
MAX_DEFICIT_S = 4.4

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
WEAR_CUTS: dict[str, tuple[float, ...]] = {
    "SOFT": (-0.184, -0.0213, 0.011, 0.0184, 0.0401, 0.0549, 0.0769, 0.0875, 0.1382),
    "MEDIUM": (-0.0273, 0.0112, 0.0211, 0.0337, 0.0415, 0.0539, 0.0675, 0.08, 0.1067),
    "HARD": (-0.0353, 0.0009, 0.0132, 0.0217, 0.0344, 0.0436, 0.0498, 0.0637, 0.0966),
}


@dataclass(frozen=True)
class RaceModel:
    """Everything drawn during a simulated race, all of it measured.

    Defaults are 2026 Zandvoort. See ``docs/research/strategy-search.md``.
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
    p_safety_car: float = 0.600
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


def race_time(
    plan: Plan,
    car: Car,
    model: RaceModel,
    rng: np.random.Generator,
    draws: int,
    sc_lap: np.ndarray | None = None,
) -> np.ndarray:
    """Finishing time for one car under one plan, across ``draws`` races.

    Each lap adds two things: the car's baseline pace deficit, which it carries
    whatever it does, and its tyre deficit, which resets when it stops. The
    current gap to the leader anchors the total.

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
        sc_lap: Lap the safety car starts on in each draw, ``-1`` for none. Shared
            across cars so every car in a given draw meets the *same* race — a
            safety car that helps one hurts another, and drawing it per car would
            wash that out.

    Returns:
        Seconds behind the current leader's pace at the flag, one per draw.
    """
    total = np.full(draws, car.gap_leader_s, dtype=float)
    current = float(np.clip(car.degradation_s, -MAX_DEFICIT_S, MAX_DEFICIT_S))
    baseline = car.gap_leader_s / max(1, car.from_lap - 1) - current

    for index, (compound, start, end) in enumerate(_stints(plan, car, model.total_laps)):
        laps = end - start
        if laps <= 0:
            continue

        rate = _from_cuts(model.wear_cuts[compound], rng.random(draws))
        if index == 0:
            rate = rate + RATE_SHRINK * (car.degradation_rate - ROLLING_MEDIAN_S)
            deficit = np.full(draws, current)
        else:
            # Fresh rubber: the deficit restarts, which is the gain from stopping.
            deficit = np.zeros(draws)

        for _ in range(laps):
            total += baseline + deficit
            # A tyre never gets faster than new, and never worse than the measured
            # 99th percentile, so the deficit is clamped at both ends.
            deficit = np.clip(deficit + rate, 0.0, MAX_DEFICIT_S)

        total += rng.normal(0.0, model.lap_noise_s, draws) * math.sqrt(laps)

    for stop in plan.stops:
        under_sc = (
            np.zeros(draws, dtype=bool)
            if sc_lap is None
            else (sc_lap >= 0) & (stop.lap >= sc_lap) & (stop.lap < sc_lap + model.sc_laps)
        )
        green = _triangular(rng, model.pit_loss_green, draws)
        neutral = _triangular(rng, model.pit_loss_sc, draws)
        total += np.where(under_sc, neutral, green)

    return total


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

    return tuple(fixed)


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


def _points(position: np.ndarray) -> np.ndarray:
    """Championship points for a finishing position, zero from eleventh."""
    table = np.array((*POINTS, *([0] * 60)), dtype=float)
    return table[np.clip(position - 1, 0, len(table) - 1)]


#: Below this many expected points, the points objective carries no gradient and
#: position is used instead. One tenth of a point is a hundredth of tenth place.
POINTS_FLOOR = 0.1


def _score(times: np.ndarray, rival_times: np.ndarray, objective: Objective) -> float:
    """Turn a spread of finishing times into the single number being maximised."""
    if objective is Objective.TIME:
        return -float(times.mean())

    position = _positions(times, rival_times)
    if objective is Objective.POSITION:
        return -float(position.mean())
    if objective is Objective.PODIUM:
        return float((position <= 3).mean())
    if objective is Objective.IN_POINTS:
        return float((position <= 10).mean())
    return float(_points(position).mean())


@dataclass(frozen=True)
class Search:
    """What the search found."""

    car: str
    objective: Objective
    best: Plan
    #: Value of the objective for ``best``.
    score: float
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
    #: Runner-up plans, best first, for showing alternatives.
    alternatives: tuple[tuple[Plan, float], ...]


def optimise(
    car: Car,
    rivals: Sequence[Car],
    rival_plans: Sequence[Plan],
    model: RaceModel | None = None,
    *,
    objective: Objective = Objective.POINTS,
    population: int = 48,
    generations: int = 30,
    draws: int = 400,
    max_stops: int = 4,
    seed: int = 0,
) -> Search:
    """Search for the plan that best serves ``objective``.

    Rivals are simulated once, before the search starts, and their finishing times
    reused for every candidate. That is what makes this cheap, and it rests on
    rivals not reacting to the focal car — wrong precisely when two cars are racing
    each other wheel to wheel.

    Args:
        car: The car being optimised.
        rivals: Everyone else still running.
        rival_plans: One plan per rival, in the same order. Drawn, not optimised:
            giving every car the optimum would describe a race nobody has run.
        model: Measured distributions; 2026 Zandvoort defaults if omitted.
        objective: What "better" means. See :class:`Objective`.
        population: Plans held per generation.
        generations: Rounds of selection.
        draws: Races simulated per fitness evaluation.
        max_stops: Cap on stops in a plan.
        seed: Reproducibility.

    Returns:
        The best plan found, its score, the spread of stop counts the population
        settled on, and a few runners-up.
    """
    model = model or RaceModel()
    rng = np.random.default_rng(seed)
    wanted = objective
    if objective is Objective.ADAPTIVE:
        objective = Objective.POINTS

    # One safety car per drawn race, shared by everyone in it.
    sc_lap = draw_safety_car(model, rng, draws)

    rival_times = (
        np.vstack(
            [
                race_time(plan, rival, model, rng, draws, sc_lap)
                for rival, plan in zip(rivals, rival_plans, strict=True)
            ]
        )
        if rivals
        else np.empty((0, draws))
    )

    def fitness(plan: Plan) -> float:
        return _score(race_time(plan, car, model, rng, draws, sc_lap), rival_times, objective)

    seeds = [_random_plan(car, model, rng, max_stops) for _ in range(population)]
    scored = [(plan, fitness(plan)) for plan in seeds]

    for _ in range(generations):
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

    scored.sort(key=lambda pair: pair[1], reverse=True)
    best, score = scored[0]

    # Points unreachable: the objective was flat, so the winner is noise. Search
    # again on position, where there is still a gradient to follow.
    if wanted is Objective.ADAPTIVE and objective is Objective.POINTS and score < POINTS_FLOOR:
        return optimise(
            car,
            rivals,
            rival_plans,
            model,
            objective=Objective.POSITION,
            population=population,
            generations=generations,
            draws=draws,
            max_stops=max_stops,
            seed=seed,
        )

    counts: dict[int, float] = {}
    for plan, _ in scored:
        counts[plan.count] = counts.get(plan.count, 0.0) + 1.0 / len(scored)

    position = _positions(race_time(best, car, model, rng, draws, sc_lap), rival_times)

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
        best=best,
        score=score,
        stop_distribution=dict(sorted(counts.items())),
        mean_position=float(position.mean()),
        sd_position=float(position.std()),
        mean_points=float(_points(position).mean()),
        decision_value=float(score - scored[-1][1]),
        alternatives=tuple(alternatives),
    )
