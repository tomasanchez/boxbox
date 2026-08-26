"""Circuit-specific pace estimated from practice, before the race is run.

This module exists because of a hard constraint on forecasting: at a circuit the
season has not visited yet, there is **no 2026 race data**. The regulations reset
this year, so earlier seasons at that circuit describe different cars on different
tyres. Practice is the only 2026 pace signal that exists before lights out.

Availability depends on the weekend format:

* ``conventional`` — FP1, FP2 and FP3, roughly 1,400–1,800 laps.
* ``sprint_qualifying`` — FP1 only, roughly 600–700 laps.

Fuel is the catch. Practice long runs carry unknown and varying fuel loads, and
fuel burns off *during* a run, which makes the car faster as the tyre gets older.
A raw practice slope therefore **understates** degradation. We add the fuel effect
back in, using laps-into-run as the proxy for fuel burned — the mirror of the
correction :mod:`boxbox_ml.features` applies to race laps.
"""

from __future__ import annotations

import fastf1
import numpy as np
import pandas as pd

from boxbox_ml.features import FUEL_EFFECT_S_PER_LAP

#: A run shorter than this cannot support a slope worth fitting.
MIN_RUN_LAPS = 5

#: Practice sessions to try, in order. Missing ones are skipped, not fatal.
SESSIONS = ("FP1", "FP2", "FP3")


def _run_slope(times: pd.Series) -> float:
    """Fit seconds-per-lap degradation over one practice run, fuel-corrected."""
    values = times.dropna()
    if len(values) < MIN_RUN_LAPS:
        return np.nan
    laps_into_run = np.arange(len(values))
    # Add the fuel-burn gain back: without this the slope is biased optimistic.
    corrected = values.to_numpy() + FUEL_EFFECT_S_PER_LAP * laps_into_run
    return float(np.polyfit(laps_into_run, corrected, 1)[0])


def load_practice_pace(year: int, round_number: int) -> pd.DataFrame:
    """Summarise circuit pace per compound from every available practice session.

    Args:
        year: Season.
        round_number: Round number of the event.

    Returns:
        One row per compound with the median fitted degradation slope, the median
        representative lap time, and how many runs backed each figure. Empty if no
        practice session yielded usable long runs.
    """
    records: list[dict] = []

    for code in SESSIONS:
        try:
            session = fastf1.get_session(year, round_number, code)
            session.load(laps=True, telemetry=False, weather=False, messages=False)
        except Exception:  # noqa: BLE001 - a missing session is normal on sprint weekends
            continue

        laps = session.laps
        if laps.empty:
            continue

        clean = laps[
            laps["LapTime"].notna()
            & laps["IsAccurate"].eq(True)
            & laps["PitInTime"].isna()
            & laps["PitOutTime"].isna()
            & laps["Compound"].notna()
        ].copy()
        if clean.empty:
            continue
        clean["seconds"] = clean["LapTime"].dt.total_seconds()

        for (driver, stint), run in clean.sort_values("LapNumber").groupby(["Driver", "Stint"]):
            if len(run) < MIN_RUN_LAPS:
                continue
            records.append(
                {
                    "session": code,
                    "driver": driver,
                    "stint": stint,
                    "compound": run["Compound"].iloc[0],
                    "run_laps": len(run),
                    "slope": _run_slope(run["seconds"]),
                    "median_pace": float(run["seconds"].median()),
                }
            )

    if not records:
        return pd.DataFrame(
            columns=["compound", "fp_deg_slope", "fp_median_pace", "fp_runs", "fp_laps"]
        )

    runs = pd.DataFrame(records)
    summary = (
        runs.groupby("compound")
        .agg(
            fp_deg_slope=("slope", "median"),
            fp_median_pace=("median_pace", "median"),
            fp_runs=("slope", "count"),
            fp_laps=("run_laps", "sum"),
        )
        .reset_index()
    )
    summary["year"] = year
    summary["round"] = round_number
    return summary


def load_many(year: int, rounds: list[int]) -> pd.DataFrame:
    """Concatenate :func:`load_practice_pace` over several rounds, skipping failures."""
    frames = []
    for round_number in rounds:
        summary = load_practice_pace(year, round_number)
        if not summary.empty:
            frames.append(summary)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
