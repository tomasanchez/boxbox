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
#: Re-derived after ``RACE_PROGRESS_S_PER_LAP`` was fitted at 0.056 instead of the
#: asserted 0.035. The effect is exact and uniform: every slope moves up by the
#: difference, 0.021 s/lap, because the correction is linear in the lap number.
#: The distribution's *shape* is untouched, so the non-normality finding stands —
#: but the median wear rate goes from 0.034-0.040 to 0.055-0.062, and the fifth
#: percentile of the medium and the hard moves from clearly negative to about
#: zero. Most of the "stints that get faster" were the under-correction.
WEAR_CUTS: dict[str, tuple[float, ...]] = {
    "SOFT": (-0.163, -0.0003, 0.032, 0.0394, 0.0611, 0.0759, 0.0979, 0.1085, 0.1592),
    "MEDIUM": (-0.0063, 0.0322, 0.0421, 0.0547, 0.0625, 0.0749, 0.0885, 0.101, 0.1277),
    "HARD": (-0.0143, 0.0219, 0.0342, 0.0427, 0.0554, 0.0646, 0.0708, 0.0847, 0.1176),
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
    #: Multiplier on the traffic penalty. One, because the per-circuit estimates
    #: do not replicate across eras — see :data:`TRAFFIC_SCALE`.
    traffic_scale: float = TRAFFIC_SCALE


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


def race_trace(
    plan: Plan,
    car: Car,
    model: RaceModel,
    rng: np.random.Generator,
    draws: int,
    sc_lap: np.ndarray | None = None,
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
        sc_lap: Lap the safety car starts on in each draw, ``-1`` for none. Shared
            across cars so every car in a given draw meets the *same* race — a
            safety car that helps one hurts another, and drawing it per car would
            wash that out.
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
    baseline = car.gap_leader_s / max(1, car.from_lap - 1) - current
    stop_at = {stop.lap: stop for stop in plan.stops}

    rate = _from_cuts(model.wear_cuts[car.compound], rng.random(draws)) + RATE_SHRINK * (
        car.degradation_rate - ROLLING_MEDIAN_S
    )
    deficit = np.full(draws, current)

    for offset in range(laps_left):
        lap = car.from_lap + offset
        total = total + baseline + deficit
        # A tyre never gets faster than new, and never worse than the measured
        # 99th percentile, so the deficit is clamped at both ends.
        deficit = np.clip(deficit + rate, 0.0, MAX_DEFICIT_S)
        total = total + rng.normal(0.0, model.lap_noise_s, draws)
        total = total + _traffic_penalty(total, rival_trace, offset + 1, model)

        stop = stop_at.get(lap + 1)
        if stop is not None:
            under_sc = (
                np.zeros(draws, dtype=bool)
                if sc_lap is None
                else (sc_lap >= 0) & (stop.lap >= sc_lap) & (stop.lap < sc_lap + model.sc_laps)
            )
            green = _triangular(rng, model.pit_loss_green, draws)
            neutral = _triangular(rng, model.pit_loss_sc, draws)
            total = total + np.where(under_sc, neutral, green)

            # Fresh rubber: the deficit restarts, which is the gain from stopping.
            rate = _from_cuts(model.wear_cuts[stop.compound], rng.random(draws))
            deficit = np.zeros(draws)

        trace[offset + 1] = total

    return trace


def race_time(
    plan: Plan,
    car: Car,
    model: RaceModel,
    rng: np.random.Generator,
    draws: int,
    sc_lap: np.ndarray | None = None,
    rival_trace: np.ndarray | None = None,
) -> np.ndarray:
    """Finishing time only. See :func:`race_trace` for what it is made of."""
    return race_trace(plan, car, model, rng, draws, sc_lap, rival_trace)[-1]


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

    # Rivals get the full lap-by-lap trace, not only a finishing time, because
    # pricing traffic needs to know where they are on the lap the focal car stops.
    # They are still simulated once and reused, which is what keeps this cheap:
    # rivals do not react to the focal car's plan.
    rival_trace = (
        np.stack(
            [
                race_trace(plan, rival, model, rng, draws, sc_lap)
                for rival, plan in zip(rivals, rival_plans, strict=True)
            ]
        )
        if rivals
        else np.empty((0, model.total_laps - car.from_lap + 1, draws))
    )
    rival_times = rival_trace[:, -1, :] if rivals else np.empty((0, draws))

    def fitness(plan: Plan) -> float:
        times = race_time(plan, car, model, rng, draws, sc_lap, rival_trace)
        return _score(times, rival_times, objective)

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

    position = _positions(race_time(best, car, model, rng, draws, sc_lap, rival_trace), rival_times)

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
