"""Per-circuit Safety Car, VSC and red-flag rates.

These are the draw parameters for a Monte Carlo race simulation: before you can
simulate whether a stop lands in a cheap window, you need to know how often that
circuit produces one.

**The estimation problem is small-n, not big-data.** A circuit appears once per
season. Five seasons gives five Bernoulli trials per circuit, so a circuit that
threw a Safety Car in 3 of 5 visits has an observed rate of 0.60 with a standard
error around 0.22. Taking that at face value would have the simulator confidently
asserting differences that are noise.

Two things are done about it:

* **Partial pooling.** Every circuit rate is shrunk toward the global rate with a
  Beta-Binomial empirical-Bayes prior fitted by maximum likelihood. Circuits with
  few visits move a long way toward the mean; circuits with many barely move.
* **Era separation.** 2026 neutralises far more than the seasons before it, so the
  season baseline is reported per era and circuit effects are expressed as a
  multiplier on that baseline rather than as an absolute rate.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import betaln

from boxbox_ml import track_status

#: FastF1's ``Location`` is not stable across seasons — 2026 reports Monaco as
#: "Monte Carlo" and Miami as "Miami Gardens", which silently splits a circuit's
#: history into two under-observed halves. Normalise before grouping.
CIRCUIT_ALIASES = {
    "Monte Carlo": "Monaco",
    "Miami Gardens": "Miami",
    "Montreal": "Montréal",
    "Sao Paulo": "São Paulo",
    "Mexico": "Mexico City",
    "Abu Dhabi": "Yas Island",
    # Found on the *forward* 2026 calendar, not in the historical data: the
    # schedule calls round 23 "Yas Marina" while every past season records it as
    # "Yas Island". Without this the circuit reads as brand new and the model
    # falls back to the global average for a track it has four races of.
    "Yas Marina": "Yas Island",
}


def canonical_circuit(name: str) -> str:
    """Map a FastF1 ``Location`` onto a stable circuit key."""
    return CIRCUIT_ALIASES.get(str(name).strip(), str(name).strip())


#: Columns describing one race's neutralisation.
RACE_COLUMNS = [
    "year",
    "round",
    "circuit",
    "total_laps",
    "sc_periods",
    "vsc_periods",
    "red_periods",
    "sc_laps",
    "vsc_laps",
    "red_laps",
    "neutralised_laps",
]


def _count_periods(flagged_laps: set[int]) -> int:
    """Count contiguous runs of lap numbers — i.e. distinct neutralisation periods."""
    if not flagged_laps:
        return 0
    ordered = sorted(flagged_laps)
    periods = 1
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if current != previous + 1:
            periods += 1
    return periods


def summarise_race(laps: pd.DataFrame) -> dict:
    """Reduce one race's lap frame to its neutralisation summary.

    Args:
        laps: A single race's laps, already carrying a ``TrackStatus`` column.

    Returns:
        One record matching :data:`RACE_COLUMNS`.
    """
    flagged = track_status.add_flags(laps)
    total_laps = int(flagged["total_laps"].iloc[0])

    def laps_with(flag: str) -> set[int]:
        return set(flagged.loc[flagged[flag], "LapNumber"].dropna().astype(int))

    sc, vsc, red = laps_with("sc"), laps_with("vsc"), laps_with("red")
    return {
        "year": int(flagged["year"].iloc[0]),
        "round": int(flagged["round"].iloc[0]),
        "circuit": canonical_circuit(flagged["circuit"].iloc[0]),
        "total_laps": total_laps,
        "sc_periods": _count_periods(sc),
        "vsc_periods": _count_periods(vsc),
        "red_periods": _count_periods(red),
        "sc_laps": len(sc),
        "vsc_laps": len(vsc),
        "red_laps": len(red),
        "neutralised_laps": len(sc | vsc | red),
    }


def summarise_races(frame: pd.DataFrame) -> pd.DataFrame:
    """Apply :func:`summarise_race` to every race in a multi-race frame."""
    records = [summarise_race(race) for _, race in frame.groupby(["year", "round"], dropna=False)]
    return pd.DataFrame(records, columns=RACE_COLUMNS)


def fit_beta_prior(successes: np.ndarray, trials: np.ndarray) -> tuple[float, float]:
    """Fit a Beta prior to per-group rates by Beta-Binomial maximum likelihood.

    Method of moments is the textbook approach and it fails badly here. With one
    or two visits per circuit, the spread of the observed rates is dominated by
    binomial noise — a circuit seen once scores 0.0 or 1.0 and nothing else. MoM
    reads that noise as real between-circuit variation, returns a prior worth well
    under one pseudo-visit, and shrinks almost nothing. Maximum likelihood accounts
    for the sampling variance explicitly and does not have that failure mode.

    Args:
        successes: Count of successes per group.
        trials: Count of trials per group; must be positive.

    Returns:
        The ``(alpha, beta)`` of the fitted prior.
    """
    usable = trials > 0
    s = successes[usable].astype(float)
    n = trials[usable].astype(float)

    if len(s) < 2:
        return 1.0, 1.0

    def negative_log_likelihood(params: np.ndarray) -> float:
        alpha, beta = np.exp(params)  # keep both strictly positive
        return -float(np.sum(betaln(s + alpha, n - s + beta) - betaln(alpha, beta)))

    mean = float(np.sum(s) / np.sum(n))
    mean = min(max(mean, 1e-3), 1 - 1e-3)
    # Start from a prior worth ~4 pseudo-visits centred on the pooled rate.
    start = np.log([max(mean * 4, 1e-2), max((1 - mean) * 4, 1e-2)])

    result = minimize(negative_log_likelihood, start, method="Nelder-Mead")
    if not result.success:
        strength = 4.0
        return mean * strength, (1 - mean) * strength

    alpha, beta = np.exp(result.x)
    # Guard against a degenerate fit running off to a near-infinite prior.
    if not np.isfinite(alpha) or not np.isfinite(beta) or alpha + beta > 500:
        strength = 4.0
        return mean * strength, (1 - mean) * strength
    return float(alpha), float(beta)


def circuit_rates(races: pd.DataFrame, event: str = "sc") -> pd.DataFrame:
    """Estimate P(at least one ``event``) per circuit, with partial pooling.

    Args:
        races: Output of :func:`summarise_races`.
        event: One of ``"sc"``, ``"vsc"``, ``"red"``, or ``"neutralised"``.

    Returns:
        One row per circuit: visits, raw rate, shrunk rate, and the multiplier the
        shrunk rate represents against the global rate. Sorted most chaotic first.
    """
    column = f"{event}_periods" if event != "neutralised" else "neutralised_laps"
    grouped = races.assign(had=races[column] > 0).groupby("circuit")
    table = grouped.agg(
        visits=("had", "count"),
        occurred=("had", "sum"),
        mean_neutralised_share=(
            "neutralised_laps",
            lambda s: float(np.mean(s / races.loc[s.index, "total_laps"])),
        ),
    )

    alpha, beta = fit_beta_prior(table["occurred"].to_numpy(), table["visits"].to_numpy())
    table["raw_rate"] = table["occurred"] / table["visits"]
    table["shrunk_rate"] = (table["occurred"] + alpha) / (table["visits"] + alpha + beta)

    global_rate = float((races[column] > 0).mean())
    table["multiplier"] = table["shrunk_rate"] / global_rate if global_rate else np.nan
    table["prior_strength"] = alpha + beta

    return table.sort_values("shrunk_rate", ascending=False)


def start_lap_profile(races: pd.DataFrame, laps: pd.DataFrame) -> pd.DataFrame:
    """Describe *when* in a race neutralisations begin, as a fraction of distance.

    A simulator needs this as well as the rate: a lap-2 red flag and a lap-55 VSC
    are entirely different strategic events.
    """
    rows = []
    for (year, round_number), race in laps.groupby(["year", "round"], dropna=False):
        flagged = track_status.add_flags(race)
        total = int(flagged["total_laps"].iloc[0])
        for flag in ("sc", "vsc", "red"):
            hit = flagged.loc[flagged[flag], "LapNumber"].dropna().astype(int)
            if hit.empty:
                continue
            ordered = sorted(set(hit))
            starts = [ordered[0]] + [
                current
                for previous, current in zip(ordered, ordered[1:], strict=False)
                if current != previous + 1
            ]
            rows.extend(
                {
                    "year": year,
                    "round": round_number,
                    "circuit": canonical_circuit(flagged["circuit"].iloc[0]),
                    "event": flag,
                    "start_lap": start,
                    "race_fraction": start / total,
                }
                for start in starts
            )
    return pd.DataFrame(rows)
