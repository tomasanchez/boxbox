"""Feature engineering for the pit-stop decision model.

Every domain assumption in this project lives here. The chain is:

1. drop laps that cannot describe pace (in-laps, out-laps, deleted, inaccurate),
2. remove the fuel effect so laps of different stints are comparable,
3. measure degradation *within* a stint against a settled reference lap,
4. derive the on-track gaps that make an undercut cheap or expensive,
5. attach the label: did this driver box at the end of this lap?
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from boxbox_ml import track_status

#: Seconds per lap that a race lap gets faster as the race runs on — **fitted**,
#: over 1,627 driver-races. See ``scripts/fit_fuel_effect.py`` and
#: ``scripts/fit_race_progress.py``.
#:
#: The name says "race progress" and not "fuel" on purpose. Two things make later
#: laps faster: the tank emptying, and the circuit rubbering in. Within one race
#: both are linear in the lap number, so they are **not separately identifiable
#: from lap timing** — a first attempt to split them with a driver-race fixed
#: effect returned beta = −0.043 s/lap, which would mean carrying fuel makes a car
#: faster. The fixed effect absorbs the race length, which was the only variation
#: telling the two apart.
#:
#: For measuring tyre wear the split does not matter: what has to come off the lap
#: time is the whole race-progress effect, whatever its cause. That combined
#: figure *is* identifiable and comes out at **0.056 s/lap** (median over
#: driver-races; p25 0.078, p75 0.036; 0.047–0.062 across the five seasons).
#:
#: The previous value of 0.035 was borrowed from the earlier era and removed only
#: about **63%** of the effect. That under-correction is what left half the grid
#: reading as flat or improving degradation at mid-race, and what made the hard
#: compound look faster than the medium — the hard runs 25 laps later on average,
#: so an under-correction hands it a spurious 0.3 s/lap.
#:
#: It is deliberately **global, not per circuit**. Per-circuit estimates range
#: from 0.031 to 0.093, but they correlate only **0.150** across eras, so almost
#: all of that spread is race-to-race noise — the same lesson as the per-circuit
#: overtaking difficulty.
RACE_PROGRESS_S_PER_LAP = 0.056

#: Kept as the old name so nothing breaks silently. It never was only fuel.
FUEL_EFFECT_S_PER_LAP = RACE_PROGRESS_S_PER_LAP

#: Which *settled* lap of a stint is the degradation baseline. Counting settled
#: laps rather than raw lap numbers matters: lap 1 of a race carries a PitOutTime
#: (cars leave the grid through the pit exit) and so is never settled, which would
#: otherwise shift the baseline by one for every opening stint.
REFERENCE_STINT_LAP = 3

#: Window, in laps, over which the degradation rate is fitted.
DEGRADATION_WINDOW = 5

#: Keys identifying one continuous run on one set of tyres.
STINT_KEYS = ["year", "round", "Driver", "Stint"]

#: Keys identifying one race.
RACE_KEYS = ["year", "round"]


def mark_representative(laps: pd.DataFrame) -> pd.DataFrame:
    """Flag the laps whose time actually describes race pace.

    In-laps and out-laps carry the pit-lane transit, deleted laps were struck by
    the stewards, and laps failing FastF1's own ``IsAccurate`` check have unsynced
    start/end times. All four are excluded from pace fitting — but kept in the
    frame, because an in-lap is exactly where the label lives.
    """
    out = laps.copy()
    # .eq(True) rather than .fillna(False).astype(bool): these columns arrive as
    # object dtype, and fillna on object dtype is deprecated in pandas 2.x.
    out["is_representative"] = (
        out["LapTime"].notna()
        & out["IsAccurate"].eq(True)
        & ~out["Deleted"].eq(True)
        & ~out["pit_in"].astype(bool)
        & ~out["pit_out"].astype(bool)
    )
    return out


def add_fuel_correction(laps: pd.DataFrame, beta: float = RACE_PROGRESS_S_PER_LAP) -> pd.DataFrame:
    """Put every lap of a race on a common footing by removing race progress.

    A lap run with ``n`` laps still to go is roughly ``beta * n`` seconds slower
    than the same lap would be at the end: the car is heavier and the circuit has
    had less rubber laid on it. Subtracting that term is what makes a lap-8 time
    comparable to a lap-45 one, and without it tyre wear is invisible — the tyre
    slows the car down at about the same rate that race progress speeds it up.

    ``beta`` is :data:`RACE_PROGRESS_S_PER_LAP`, fitted rather than assumed, and
    it covers fuel **and** track evolution together because lap timing cannot
    separate them. See that constant for why, and for what the old 0.035 cost.

    The output column keeps the name ``lap_time_fuel_corrected`` for
    compatibility with the notebooks and scripts already written against it.
    """
    out = laps.copy()
    laps_remaining = out["total_laps"] - out["LapNumber"]
    out["lap_time_fuel_corrected"] = out["LapTime"] - beta * laps_remaining
    return out


def add_stint_position(laps: pd.DataFrame) -> pd.DataFrame:
    """Number each lap within its stint, starting at 1.

    ``TyreLife`` cannot be used for this: a driver who starts on a set scrubbed in
    qualifying begins the race at ``TyreLife = 4``, as Leclerc did at Monza 2019.
    ``FreshTyre`` records whether the set was new; ``stint_lap`` records how far
    into *this* run the lap is. The two are different questions.
    """
    out = laps.sort_values([*STINT_KEYS, "LapNumber"]).copy()
    out["stint_lap"] = out.groupby(STINT_KEYS, dropna=False).cumcount() + 1
    out["stint_length"] = out.groupby(STINT_KEYS, dropna=False)["stint_lap"].transform("max")
    return out


def add_degradation(laps: pd.DataFrame) -> pd.DataFrame:
    """Measure degradation against a settled reference lap within each stint.

    ``degradation_s`` is how much slower this lap is than the stint's reference —
    the :data:`REFERENCE_STINT_LAP`-th *settled* lap, not the third lap by number.
    ``degradation_rate_s_per_lap`` is the slope fitted over the trailing
    :data:`DEGRADATION_WINDOW` laps, which is the number a strategist actually
    reasons with.
    """
    out = add_stint_position(laps)
    pace = out["lap_time_fuel_corrected"].where(out["is_representative"])
    out["_pace"] = pace

    def _reference(group: pd.Series) -> float:
        settled = group.dropna()
        if settled.empty:
            return np.nan
        # Prefer the designated reference lap; fall back to the first settled lap
        # for stints too short to have one.
        by_position = settled.reset_index(drop=True)
        index = min(REFERENCE_STINT_LAP - 1, len(by_position) - 1)
        return float(by_position.iloc[index])

    reference = out.groupby(STINT_KEYS, dropna=False)["_pace"].transform(_reference)
    out["stint_reference_s"] = reference
    out["degradation_s"] = out["_pace"] - reference

    def _slope(window: pd.Series) -> float:
        values = window.dropna()
        if len(values) < 2:
            return np.nan
        return float(np.polyfit(np.arange(len(values)), values.to_numpy(), 1)[0])

    out["degradation_rate_s_per_lap"] = (
        out.groupby(STINT_KEYS, dropna=False)["_pace"]
        .rolling(DEGRADATION_WINDOW, min_periods=2)
        .apply(_slope, raw=False)
        .reset_index(level=list(range(len(STINT_KEYS))), drop=True)
    )

    return out.drop(columns="_pace")


def add_gaps(laps: pd.DataFrame) -> pd.DataFrame:
    """Derive the on-track gap to the car ahead and to the car behind, in seconds.

    ``Time`` is the session clock at the end of the lap, so for two cars on the
    same lap the difference in ``Time`` is the gap between them. Cars a lap down
    make this meaningless, so gaps are only emitted where both cars completed the
    same lap number.
    """
    out = laps.sort_values([*RACE_KEYS, "LapNumber", "Position"]).copy()
    grouped = out.groupby([*RACE_KEYS, "LapNumber"], dropna=False)["Time"]
    out["gap_ahead_s"] = out["Time"] - grouped.shift(1)
    out["gap_behind_s"] = grouped.shift(-1) - out["Time"]
    return out


def add_labels(laps: pd.DataFrame) -> pd.DataFrame:
    """Attach the supervised target.

    ``boxed`` is true on the lap the driver entered the pit lane — FastF1 populates
    ``PitInTime`` on exactly those laps, about 3% of the field's laps in a normal
    race. That imbalance is the central modelling problem and is not smoothed over
    here.

    ``free_stop`` separates out the stops that were not decisions. A tyre change
    made while the race is suspended under a red flag costs no track time, so it is
    not the ~20-second trade-off the rest of this pipeline models. Roughly **8% of
    all stops** are these (7.5% of 2024 and 8.7% of 2026 stops measured over 24
    races), and they cluster catastrophically: 2024 Monaco was 70% free stops and
    2026 Zandvoort 31%. Training on them unfiltered teaches the model that boxing is
    sometimes free.

    Callers should either drop ``free_stop`` rows or pass the flag as a feature —
    never treat ``boxed`` alone as "the team chose to pit".
    """
    out = laps.copy()
    out["boxed"] = out["pit_in"].astype(bool)
    out["free_stop"] = out["boxed"] & out["red"].astype(bool)
    out["strategic_stop"] = out["boxed"] & ~out["free_stop"]
    out["laps_remaining"] = out["total_laps"] - out["LapNumber"]
    out["next_compound"] = (
        out.sort_values([*RACE_KEYS, "Driver", "LapNumber"])
        .groupby([*RACE_KEYS, "Driver"], dropna=False)["Compound"]
        .shift(-1)
        .where(out["boxed"])
    )
    return out


def build(laps: pd.DataFrame) -> pd.DataFrame:
    """Run the full feature pipeline over a raw ingest frame."""
    frame = mark_representative(laps)
    frame = track_status.add_flags(frame)
    frame = add_fuel_correction(frame)
    frame = add_degradation(frame)
    frame = add_gaps(frame)
    frame = add_labels(frame)
    return frame.sort_values([*RACE_KEYS, "Driver", "LapNumber"]).reset_index(drop=True)
