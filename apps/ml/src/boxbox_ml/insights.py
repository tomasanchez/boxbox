"""Broadcast-style strategy insights: pit window and undercut battle.

Modelled on the F1 Insights graphics shown on the world feed — *Pit Window*
(«ventana de boxes: vueltas X–Y») and *Pit Strategy Battle* («si para ahora, sale
a N s del rival, con P% de chance de pasarlo»).

Those graphics are the right output shape for this project, and for the reason
this repo arrived at independently: they express a **range of laps** and a
**delta against a named rival**, never a single predicted lap.

## The undercut model

At lap ``L`` the chaser ``A`` is ``gap`` seconds behind leader ``B``. If ``A``
pits now and ``B`` responds ``k`` laps later, both pay the same pit loss, so the
pit losses cancel out of the final gap. What decides the battle is the pace
difference over those ``k`` laps:

* ``A`` fits fresh rubber and recovers the degradation it had accumulated —
  ``deg_a`` seconds per lap;
* ``B`` stays out and keeps degrading at ``rate_b`` seconds per lap, so its
  penalty grows with each lap.

Cumulative gain for ``A`` over ``k`` laps::

    gain(k) = k * deg_a + rate_b * k * (k + 1) / 2

and the projected gap once ``B`` has also stopped::

    gap_after(k) = gap - gain(k)

Negative means ``A`` comes out ahead: the undercut worked.

**What this model leaves out**, and must be stated wherever it is reported:
traffic on the out-lap, the leader's ability to respond immediately, and any
neutralisation during the exchange. Under a Safety Car the arithmetic changes
completely — a stop then costs about zero track position rather than two places.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: Measured green-flag pit loss, 2026 (median and interquartile range), in seconds.
#: See docs/research/pit-loss-under-neutralisation.md.
PIT_LOSS_GREEN = 22.2
PIT_LOSS_P25 = 19.0
PIT_LOSS_P75 = 26.3

#: Draws used when estimating the probability of a successful undercut.
DRAWS = 4000


@dataclass(frozen=True)
class Driver:
    """A car's state at the moment of the decision."""

    code: str
    compound: str
    tyre_age: int
    #: Seconds per lap currently being lost to degradation, versus fresh rubber.
    degradation_s: float
    #: Seconds per lap the loss is still growing by.
    degradation_rate: float


@dataclass(frozen=True)
class BattleResult:
    """Projected outcome of an undercut attempt."""

    gap_now: float
    best_response_lap: int
    gap_after: float
    works: bool
    probability: float
    per_lap_gain: float

    def headline(self) -> str:
        """One-line summary in the register a broadcast graphic would use.

        The verdict is driven by the **probability**, not by the point estimate.
        A projected gap of −0.1 s with a 47% chance of working is a coin flip, and
        announcing "comes out ahead" there would be misleading.
        """
        if self.probability >= 0.65:
            verdict, tail = "SALE ADELANTE", "de ventaja"
        elif self.probability <= 0.35:
            verdict, tail = "SIGUE ATRÁS", "por detrás"
        else:
            return (
                f"A CARA O CRUZ — {abs(self.gap_after):.1f}s proyectados, "
                f"{100 * self.probability:.0f}% de chance"
            )
        return (
            f"{verdict} — {abs(self.gap_after):.1f}s {tail}, "
            f"{100 * self.probability:.0f}% de chance"
        )


def undercut_gain(chaser: Driver, leader: Driver, laps: int) -> float:
    """Seconds the chaser gains over the leader across ``laps`` on fresh rubber."""
    if laps <= 0:
        return 0.0
    recovered = laps * max(chaser.degradation_s, 0.0)
    growing = max(leader.degradation_rate, 0.0) * laps * (laps + 1) / 2
    return recovered + growing


def strategy_battle(
    chaser: Driver,
    leader: Driver,
    gap: float,
    response_laps: int = 2,
    draws: int = DRAWS,
    seed: int = 0,
) -> BattleResult:
    """Project the outcome if ``chaser`` pits now and ``leader`` responds later.

    Args:
        chaser: The car attempting the undercut.
        leader: The car ahead on track.
        gap: Current gap in seconds, positive means the leader is ahead.
        response_laps: Laps before the leader reacts. Two is the usual assumption.
        draws: Monte Carlo draws for the probability estimate.
        seed: Seed, so a reported probability is reproducible.

    Returns:
        The projected gap after both stops, and the probability it is favourable.
    """
    gain = undercut_gain(chaser, leader, response_laps)
    gap_after = gap - gain

    # Uncertainty comes from the measured spread of pit loss and of degradation.
    rng = np.random.default_rng(seed)
    pit_delta = rng.triangular(
        PIT_LOSS_P25 - PIT_LOSS_GREEN, 0.0, PIT_LOSS_P75 - PIT_LOSS_GREEN, draws
    )
    deg_noise = rng.normal(0.0, 0.15, draws) * response_laps
    sampled = gap - (gain + deg_noise) + pit_delta

    return BattleResult(
        gap_now=gap,
        best_response_lap=response_laps,
        gap_after=gap_after,
        works=gap_after < 0,
        probability=float((sampled < 0).mean()),
        per_lap_gain=gain / response_laps if response_laps else 0.0,
    )


def pit_window(
    driver: Driver,
    laps_remaining: int,
    expected_stint_life: int,
    tolerance_s: float = 1.0,
) -> tuple[int, int] | None:
    """Estimate the lap range over which stopping is close to optimal.

    The window opens once degradation is projected to pass ``tolerance_s`` and
    closes when the remaining distance would no longer fill a sensible stint.

    Returns ``None`` when no window can be projected, which happens more often
    than one might expect. A car whose measured degradation rate is flat or
    **negative** — still improving as fuel burns off — has no projectable
    crossing point, and inventing one would be worse than admitting it. Roughly
    half the field is in that state at any given mid-race lap, which is itself a
    finding: it is the fixed fuel coefficient (0,035 s/lap, calibrated on the
    previous era) under-correcting 2026 cars.

    Args:
        driver: Current tyre state.
        laps_remaining: Laps left in the race.
        expected_stint_life: Laps the next set is expected to last.
        tolerance_s: Degradation the team is willing to absorb before stopping.

    Returns:
        ``(opens_in, closes_in)`` as offsets in laps from now, or ``None``.
    """
    if laps_remaining <= 0:
        return None

    deficit = tolerance_s - driver.degradation_s
    if deficit <= 0:
        opens_in = 0  # already past the tolerance: the window is open now
    elif driver.degradation_rate <= 1e-3:
        return None  # flat or improving — no crossing point to project
    else:
        opens_in = int(np.ceil(deficit / driver.degradation_rate))

    if opens_in > laps_remaining:
        return None  # the window would open after the flag

    closes_in = int(np.clip(laps_remaining - expected_stint_life, opens_in, laps_remaining))
    return int(opens_in), closes_in
