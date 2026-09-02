"""Measure how much lap pace and wear rate actually vary.

The simulator runs every car on a fixed degradation figure, which makes two cars
with the same tyre state run identically forever and gaps evolve on rails. Real
wear is not like that, and this measures by how much it is not — the two numbers
the simulator needs to draw from instead of asserting.

**Lap-to-lap noise.** Within one stint, fit a straight line to fuel-corrected lap
time against stint lap and take the standard deviation of the residuals. That is
what is left after tyre wear and fuel burn are accounted for: traffic, driver,
wind, a wide entry. It is the noise on a single lap.

**Between-stint spread of the wear rate.** Two cars on the same compound do not
wear it at the same rate — track position, driving style, how the set was
prepared. The spread of fitted slopes across stints of the same compound says how
much a car's rate is worth doubting, and it is what turns one projection into a
distribution.

Only green, representative laps count: in-laps, out-laps, deleted laps, laps
failing FastF1's ``IsAccurate`` check, and anything under a neutralisation are
excluded. A safety car lap is 40 seconds slow and would swamp everything.

Run with ``uv run python scripts/pace_noise.py --offline --reuse``.
"""

from __future__ import annotations

import argparse
import warnings

import fastf1
import numpy as np
import pandas as pd

from boxbox_ml import cache, features, ingest, track_status

warnings.filterwarnings("ignore")
pd.set_option("display.width", 220)
pd.set_option("display.max_rows", 60)

#: Laps a stint needs before its residual spread means anything. Below this the
#: line has too few points and the sd is mostly a fitting artefact.
MIN_STINT_LAPS = 8

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--offline", action="store_true", help="cached sessions only, no API calls")
parser.add_argument("--seasons", type=int, nargs="+", default=[2022, 2023, 2024, 2025, 2026])
parser.add_argument(
    "--reuse", action="store_true", help="reuse the parquet written by overtake_difficulty.py"
)
args = parser.parse_args()

print(f"cache: {cache.enable()}")
if args.offline:
    fastf1.Cache.offline_mode(True)
    print("mode:  OFFLINE\n")

PARQUET = cache.cache_dir().parent / "laps_overtaking.parquet"

print("--- ingesting ---")
if args.reuse and PARQUET.exists():
    frame = pd.read_parquet(PARQUET)
    print(f"  reused {PARQUET.name}: {len(frame):,} laps")
else:
    frame = ingest.build_dataset(args.seasons)
    frame.to_parquet(PARQUET)
    print(f"  cached {len(frame):,} laps to {PARQUET.name}")

frame = track_status.add_flags(frame)
frame = features.mark_representative(frame)
frame = features.add_fuel_correction(frame)
frame = features.add_stint_position(frame)

clean = frame[
    frame["is_representative"] & ~frame["is_neutralised"] & ~frame["red"] & ~frame["yellow"]
].copy()
print(f"\nrepresentative green laps: {len(clean):,} of {len(frame):,}")

rows = []
for keys, stint in clean.groupby(features.STINT_KEYS, dropna=False):
    pace = stint["lap_time_fuel_corrected"].to_numpy(dtype=float)
    position = stint["stint_lap"].to_numpy(dtype=float)
    if len(pace) < MIN_STINT_LAPS or not np.isfinite(pace).all():
        continue

    slope, intercept = np.polyfit(position, pace, 1)
    residual = pace - (slope * position + intercept)
    rows.append(
        {
            "year": keys[0],
            "round": keys[1],
            "driver": keys[2],
            "compound": stint["Compound"].iloc[0],
            "laps": len(pace),
            "slope": slope,
            "residual_sd": float(residual.std(ddof=2)),
        }
    )

stints = pd.DataFrame(rows)
# A handful of stints sit on a safety-car restart or a damaged car and produce
# absurd fits. Trimming the extreme 1% each side keeps them from setting the scale.
lo, hi = stints["residual_sd"].quantile([0.005, 0.995])
trimmed = stints[stints["residual_sd"].between(lo, hi)]
print(f"stints fitted: {len(stints):,} (>= {MIN_STINT_LAPS} laps), {len(trimmed):,} after trimming")

print("\n" + "=" * 90)
print("### LAP-TO-LAP NOISE — residual sd around the stint's own wear line, in seconds")
print(trimmed["residual_sd"].describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]).round(3).to_string())

print("\nby compound:")
print(
    trimmed.groupby("compound")
    .agg(
        stints=("laps", "count"),
        median_sd=("residual_sd", "median"),
        mean_sd=("residual_sd", "mean"),
    )
    .sort_values("median_sd")
    .round(3)
)

print("\nby season — is the noise scale stable enough to use one number?")
print(
    trimmed.groupby("year")
    .agg(stints=("laps", "count"), median_sd=("residual_sd", "median"))
    .round(3)
)

print("\n" + "=" * 90)
print("### WEAR RATE — how much stints of the same compound differ, in seconds per lap")
dry = trimmed[trimmed["compound"].isin(["SOFT", "MEDIUM", "HARD"])]
rate = dry.groupby("compound")["slope"].agg(
    stints="count",
    median="median",
    mean="mean",
    sd="std",
    p10=lambda s: s.quantile(0.1),
    p90=lambda s: s.quantile(0.9),
)
print(rate.round(4))

print("\nsame, for 2026 only — the era the simulator runs:")
dry26 = dry[dry["year"] == 2026]
if len(dry26):
    print(
        dry26.groupby("compound")["slope"]
        .agg(
            stints="count",
            median="median",
            sd="std",
            p10=lambda s: s.quantile(0.1),
            p90=lambda s: s.quantile(0.9),
        )
        .round(4)
    )

print("\n" + "=" * 90)
print("### FOR THE SIMULATOR")
lap_sd = trimmed["residual_sd"].median()
rate_sd = dry26["slope"].std() if len(dry26) > 2 else dry["slope"].std()
print(f"per-lap pace noise      sd = {lap_sd:.3f} s   (median across {len(trimmed):,} stints)")
print(f"wear-rate spread        sd = {rate_sd:.4f} s/lap  (across stints of the same compound)")
print(
    "\nThe first is redrawn every lap and is what stops two identical cars running\n"
    "identically. The second is drawn once per stint and is what makes one\n"
    "projection into a distribution — a car can turn out to be kind to its tyres\n"
    "or not, and the race finds out."
)
