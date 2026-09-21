"""How a rival decides whether to take a neutralisation.

The simulator used to run every rival on a fixed drawn plan, so a safety car
moved nobody. This is the policy that replaces that assumption. Every number
here is measured by ``scripts/rival_reaction.py`` over 2,828 car-by-period cases
across 2022-2026, and the reasoning behind each is in ADR-013 and ADR-014.

The module deliberately knows nothing about :mod:`boxbox_ml.strategy`. It speaks
in flag *names* rather than the simulator's flag codes, so the dependency runs
one way only and the tables can be tested on their own.

## What the policy is

Three claims, in order of how much they change the model.

**A neutralisation is not an automatic stop.** Under a VSC only 24.2% of the
cars running pit; under a safety car 43.0%. Only under a red flag — where the
race is stopped and a tyre change costs no track position — does almost everyone
come in, 94.9%. The old model had no opinion about this at all, which amounted
to assuming the answer was whatever the fixed plan happened to say.

**Tyre age decides.** Under a safety car the share goes from 17.0% on rubber
less than five laps old to 93.8% past thirty. The regulatory obligation — the car
still owing its second dry compound under B6.3.8 — does *not* predict cleanly:
under a safety car the cars that do not owe one stop *more*. It is confounded
with tyre age and is not used.

**And the cars are not independent coins.** Real periods are stampedes or
freezes: under a safety car the share of the field that pits runs from 0.05 at
the tenth percentile to 0.85 at the ninetieth. Modelled as independent draws the
count of stops would be far too stable — 1.9× too stable under a safety car, 2.8×
under a VSC — and the field would split down the middle every time. That is not
a cosmetic problem. The scenario that actually hurts a plan is *everyone took a
cheap stop and I did not*, and independent coins essentially never produce it.

So each period draws one shared shift in logit space, :data:`PERIOD_SIGMA`, and
every car in that period feels it. One parameter, calibrated against the observed
variance rather than chosen.
"""

from __future__ import annotations

import numpy as np

#: Upper bound of each tyre-age band, in laps. The last band is open above.
#: A car's band is ``np.digitize(age, AGE_EDGES, right=True)``.
AGE_EDGES: tuple[int, ...] = (5, 10, 15, 20, 25, 30)

#: Human labels for the bands, same order. For reports, not for arithmetic.
AGE_LABELS: tuple[str, ...] = ("0-5", "6-10", "11-15", "16-20", "21-25", "26-30", "31+")

#: The flags a car can meet, named. The simulator's integer codes map onto these.
KINDS: tuple[str, ...] = ("red", "sc", "vsc")

#: Probability that a car pits during the period, by flag and tyre-age band.
#:
#: Red is flat and near one from the first band: the race is stopped, so there is
#: nothing to trade off and almost nobody declines. The two real decisions are the
#: other rows, and both climb steeply with tyre age.
#:
#: The thin cells are in the red row — two cases in the 16-20 band — which is why
#: red is treated as a near-certainty rather than as a curve.
REACT: dict[str, tuple[float, ...]] = {
    "red": (0.924, 0.982, 1.000, 1.000, 1.000, 1.000, 1.000),  # n=276
    "sc": (0.170, 0.473, 0.605, 0.730, 0.825, 0.737, 0.938),  # n=1198
    "vsc": (0.088, 0.169, 0.356, 0.324, 0.246, 0.444, 0.447),  # n=1354
}

#: Standard deviation of the logit shift shared by every car in one period.
#:
#: Calibrated so the simulated variance of the stop count matches the observed
#: one, against a baseline that uses the *same* period compositions — not against
#: the binomial variance inside a period, which is a different quantity and
#: inflates the apparent overdispersion. Red carries none: at 94.9% there is no
#: dispersion left to explain.
PERIOD_SIGMA: dict[str, float] = {
    "red": 0.00,
    "sc": 1.80,
    "vsc": 1.15,
}

#: How many of its two cars a team brings in: (neither, one only, both).
#:
#: Not a generator — the policy decides car by car and this is what the result is
#: checked against. Bringing in one car only is as common as bringing in both,
#: which is the part a per-car model has to earn rather than assume.
TEAM_SPLIT: dict[str, tuple[float, float, float]] = {
    "sc": (0.433, 0.280, 0.287),  # n=571 team-periods
    "vsc": (0.635, 0.240, 0.124),  # n=620
}

#: Given a team brings both cars in, how often it is on the same lap. n=241.
SAME_LAP: float = 0.70

#: Given a team brings in one car only, the probability it is the one on older
#: rubber, as ``(largest age gap this applies to, probability)``.
#:
#: The gap matters and nearly hid the rule. Measured in one pass the answer was
#: 50% — a coin, no rule — because in 44% of those cases the two team-mates were
#: on rubber of the same age and there was nothing to choose between them. Split
#: by how far apart they are, the rule is sharp.
OLDER_FIRST: tuple[tuple[int, float], ...] = (
    (1, 0.51),  # 0-1 lap apart, n=136: a coin, and correctly so
    (5, 0.67),  # 2-5 apart, n=42
    (999, 0.91),  # more than 5 apart, n=128
)

#: What the second car of a stacked pair pays for queueing, in seconds.
#:
#: Paired inside the same pair — same team, same lap, same race — which is what
#: makes it a measurement rather than a selection effect. Comparing the stacked
#: *group* against the single *group* mixes the queue with the fact that teams
#: stack precisely when a stop is cheap, and that comparison once produced a
#: twelve-second figure in this repo that does not survive pairing.
STACK_SURCHARGE_S: dict[str, float] = {
    "GREEN": 1.0,  # n=63 pairs
    "SC": 3.5,  # n=47
    "VSC": 3.2,  # n=42
}


#: How much more likely a car is to pit because the car *behind* it just did,
#: as ``(gap in seconds, extra probability)`` bands. Beyond the last band, zero.
#:
#: The direction is the surprise, and it is the right way round. The car that
#: reacts is the one **ahead** of the stopper, not the one behind: a stop from
#: behind is an undercut attempt aimed at you, while a stop from ahead leaves you
#: nothing to answer. It is the same point of view the interface's undercut card
#: already takes — the threat belongs to the car in front.
#:
#: Measured over 48,860 (stopper, other car) pairs on green-flag stops across 106
#: races, controlled by **mirroring**: the same gap on the other side. A car two
#: seconds ahead and a car two seconds behind are equally close to the action and
#: only one of them is threatened, so the difference between them is the effect
#: with proximity already netted out.
#:
#: The mirror only controls while the two halves are comparable cars, and they
#: stop being comparable fast. At 0-2 s they average 10.7 and 10.4 in the order;
#: by 20-60 s they average 5.0 and 13.6, which is the front of the field against
#: the back. That is why the effect appears to come *back* at long range after
#: fading — +0.07 at 20-60 s, an artefact of who is being compared, not coverage.
#: Past five seconds this design cannot separate the effect from track position,
#: so it is declared zero rather than filled with a number known to be wrong.
COVER_EXTRA: tuple[tuple[float, float], ...] = (
    (2.0, 0.078),  # n=1242 ahead / 1725 behind, ±0.029
    (5.0, 0.071),  # n=2268 / 2321, ±0.024 — a mild position confound remains
)


def cover_extra(gap_ahead_s: np.ndarray) -> np.ndarray:
    """Extra chance of pitting for a car ``gap_ahead_s`` in front of the stopper.

    Negative gaps — cars behind — get nothing: they are not the ones threatened.
    """
    out = np.zeros(np.shape(gap_ahead_s), dtype=float)
    assigned = np.zeros(np.shape(gap_ahead_s), dtype=bool)
    for bound, extra in COVER_EXTRA:
        here = ~assigned & (gap_ahead_s > 0) & (gap_ahead_s <= bound)
        out[here] = extra
        assigned |= here
    return out


def band(tyre_age: np.ndarray) -> np.ndarray:
    """Which tyre-age band each value falls in. Vectorised over draws."""
    return np.digitize(tyre_age, AGE_EDGES, right=True)


def base_probability(kind: str, tyre_age: np.ndarray) -> np.ndarray:
    """Chance this car pits during a period of ``kind``, before the period shift."""
    return np.asarray(REACT[kind], dtype=float)[band(tyre_age)]


def pit_probability(kind: str, tyre_age: np.ndarray, shift: np.ndarray) -> np.ndarray:
    """The same, with the period's shared shift applied in logit space.

    ``shift`` is a standard normal per draw, shared by every car in that period;
    it is scaled here by :data:`PERIOD_SIGMA` so the caller does not have to know
    which flag it drew. Clipping keeps the logit finite where the measured table
    is a flat 1.000, which happens in the red row.
    """
    base = np.clip(base_probability(kind, tyre_age), 1e-6, 1 - 1e-6)
    logit = np.log(base / (1 - base)) + PERIOD_SIGMA[kind] * shift
    return 1 / (1 + np.exp(-logit))


def older_first_probability(age_gap: np.ndarray) -> np.ndarray:
    """Chance the older set is the one brought in, given only one car comes in."""
    out = np.empty(np.shape(age_gap), dtype=float)
    remaining = np.ones(np.shape(age_gap), dtype=bool)
    for bound, share in OLDER_FIRST:
        here = remaining & (np.abs(age_gap) <= bound)
        out[here] = share
        remaining &= ~here
    out[remaining] = OLDER_FIRST[-1][1]
    return out
