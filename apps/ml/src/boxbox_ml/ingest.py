"""Pull race sessions from FastF1 into a tidy lap-level dataset.

One row per driver-lap. This is the raw table every downstream feature and label
is derived from; it is deliberately close to what FastF1 returns, so that
``features.py`` stays the only place where domain assumptions live.

Coverage note: lap timing with tyre data starts at the **2018** season. Earlier
years resolve through the Ergast-compatible feed and carry results but not the
per-lap compound/stint columns this project needs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import fastf1
import pandas as pd

from boxbox_ml import cache

#: Columns taken verbatim from ``Session.laps``.
_LAP_COLUMNS = [
    "Driver",
    "DriverNumber",
    "Team",
    "LapNumber",
    "Stint",
    "Compound",
    "TyreLife",
    "FreshTyre",
    "LapTime",
    "Sector1Time",
    "Sector2Time",
    "Sector3Time",
    "PitInTime",
    "PitOutTime",
    "TrackStatus",
    "Position",
    "IsAccurate",
    "Deleted",
    "Time",
    "LapStartTime",
]

#: Weather columns merged onto each lap via ``Laps.get_weather_data()``.
_WEATHER_COLUMNS = ["AirTemp", "TrackTemp", "Humidity", "Pressure", "Rainfall", "WindSpeed"]

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _to_seconds(series: pd.Series) -> pd.Series:
    """Convert a Timedelta column to float seconds, preserving NaT as NaN."""
    return series.dt.total_seconds()


def load_race(year: int, event: str | int) -> pd.DataFrame:
    """Load a single race and return its tidy lap-level frame.

    Args:
        year: Season, 2018 or later.
        event: Round number or event name accepted by :func:`fastf1.get_session`.

    Returns:
        One row per driver-lap, with lap timing, tyre state, track status and the
        weather sample aligned to that lap.

    Raises:
        ValueError: If the session loads but contains no laps.
    """
    session = fastf1.get_session(year, event, "R")
    session.load(laps=True, telemetry=False, weather=True, messages=False)

    laps = session.laps
    if laps.empty:
        raise ValueError(f"{year} {event}: session loaded but returned no laps")

    weather = laps.get_weather_data().reset_index(drop=True)
    frame = laps[_LAP_COLUMNS].reset_index(drop=True)

    for column in _WEATHER_COLUMNS:
        if column in weather.columns:
            frame[column] = weather[column].to_numpy()

    for column in ("LapTime", "Sector1Time", "Sector2Time", "Sector3Time", "Time", "LapStartTime"):
        frame[column] = _to_seconds(frame[column])

    # PitInTime / PitOutTime are only populated on the ~3% of laps that touch the
    # pit lane; that sparsity is the signal, so they are kept as booleans plus the
    # raw session time.
    frame["pit_in"] = laps["PitInTime"].reset_index(drop=True).notna()
    frame["pit_out"] = laps["PitOutTime"].reset_index(drop=True).notna()
    frame["PitInTime"] = _to_seconds(frame["PitInTime"])
    frame["PitOutTime"] = _to_seconds(frame["PitOutTime"])

    frame.insert(0, "year", year)
    frame.insert(1, "round", session.event["RoundNumber"])
    frame.insert(2, "event", session.event["EventName"])
    frame.insert(3, "circuit", session.event["Location"])
    frame["total_laps"] = frame["LapNumber"].max()

    return frame


def build_dataset(seasons: list[int], rounds: list[int] | None = None) -> pd.DataFrame:
    """Load every race of the given seasons into one frame.

    Races that fail to load (cancelled events, incomplete feeds) are reported on
    stderr and skipped rather than aborting the run.

    Args:
        seasons: Seasons to ingest; 2018 or later.
        rounds: Optional round-number filter applied to every season.

    Returns:
        The concatenation of every race that loaded successfully.
    """
    frames: list[pd.DataFrame] = []

    for year in seasons:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
        for _, event in schedule.iterrows():
            round_number = int(event["RoundNumber"])
            if rounds and round_number not in rounds:
                continue
            label = f"{year} R{round_number:02d} {event['EventName']}"
            try:
                frames.append(load_race(year, round_number))
                print(f"  ok    {label}", flush=True)
            except Exception as exc:  # noqa: BLE001 - one bad race must not stop the sweep
                print(f"  SKIP  {label}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)

    if not frames:
        raise RuntimeError("no races loaded — check the seasons requested and the network")

    return pd.concat(frames, ignore_index=True)


def main() -> int:
    """CLI entry point: ``boxbox-ingest --seasons 2022 2023 2024``."""
    parser = argparse.ArgumentParser(description="Ingest F1 race laps into a parquet dataset")
    parser.add_argument(
        "--seasons",
        type=int,
        nargs="+",
        default=[2022, 2023, 2024],
        help="seasons to ingest (2018 or later)",
    )
    parser.add_argument("--rounds", type=int, nargs="*", help="optional round-number filter")
    parser.add_argument(
        "--out",
        type=Path,
        default=DATA_DIR / "laps.parquet",
        help="output parquet path",
    )
    args = parser.parse_args()

    too_early = [year for year in args.seasons if year < 2018]
    if too_early:
        parser.error(f"lap/tyre data starts in 2018; refusing seasons {too_early}")

    print(f"cache: {cache.enable()}")
    frame = build_dataset(args.seasons, args.rounds)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(args.out, index=False)

    print(
        f"\nwrote {len(frame):,} laps from {frame.groupby(['year', 'round']).ngroups} races "
        f"-> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
