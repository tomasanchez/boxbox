"""Fit the distributions the Zandvoort simulator draws from.

Until now the simulator drew wear rates from a normal with a measured standard
deviation. A normal is symmetric and the real thing is not: a stint can go badly
wrong in ways it cannot go equally right, so the right tail is longer than the
left. This measures the **empirical** distribution instead and hands over its
quantiles, which the simulator inverts to sample. No shape is assumed.

Four things come out, all for Zandvoort:

  wear rate       per compound, as deciles of the fitted stint slope
  stint length    how long a set actually lasts here
  stop lap        where in the race the stops happen, as a share of distance
  pit loss        how much a stop costs, in seconds, green and neutralised

Zandvoort alone is a thin sample, so every table reports its own count and the
all-circuits 2026 figure beside it. Where Zandvoort is too thin to fit, the
script says so rather than fitting anyway.

Run with ``uv run python scripts/zandvoort_distributions.py --offline --reuse``.
"""

from __future__ import annotations

import argparse
import warnings

import fastf1
import numpy as np
import pandas as pd

from boxbox_ml import cache, features, ingest, neutralisation, track_status

warnings.filterwarnings("ignore")
pd.set_option("display.width", 220)
pd.set_option("display.max_rows", 60)

#: Laps a stint needs before its slope means anything.
MIN_STINT_LAPS = 8

SEP = "=" * 90

#: Deciles handed to the simulator. Nine cut points describe the shape well
#: enough to sample by interpolation and stay small enough to read.
DECILES = [0.05, 0.15, 0.25, 0.35, 0.5, 0.65, 0.75, 0.85, 0.95]

CIRCUIT = "Zandvoort"

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--offline", action="store_true", help="cached sessions only, no API calls")
parser.add_argument("--seasons", type=int, nargs="+", default=[2022, 2023, 2024, 2025, 2026])
parser.add_argument("--reuse", action="store_true", help="reuse the cached parquet")
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

frame["circuit"] = frame["circuit"].map(lambda c: neutralisation.CIRCUIT_ALIASES.get(c, c))
frame = track_status.add_flags(frame)
frame = features.mark_representative(frame)
frame = features.add_fuel_correction(frame)
frame = features.add_stint_position(frame)

green = frame[
    frame["is_representative"] & ~frame["is_neutralised"] & ~frame["red"] & ~frame["yellow"]
]

# ---------------------------------------------------------------- wear rate

rows = []
for keys, stint in green.groupby(features.STINT_KEYS, dropna=False):
    pace = stint["lap_time_fuel_corrected"].to_numpy(dtype=float)
    position = stint["stint_lap"].to_numpy(dtype=float)
    if len(pace) < MIN_STINT_LAPS or not np.isfinite(pace).all():
        continue
    slope = float(np.polyfit(position, pace, 1)[0])
    rows.append(
        {
            "year": keys[0],
            "round": keys[1],
            "circuit": stint["circuit"].iloc[0],
            "compound": stint["Compound"].iloc[0],
            "slope": slope,
        }
    )

stints = pd.DataFrame(rows)
dry = stints[stints["compound"].isin(["SOFT", "MEDIUM", "HARD"])]
here = dry[dry["circuit"] == CIRCUIT]
era = dry[dry["year"] == 2026]

print("\n" + "=" * 90)
print(f"### WEAR RATE — sample sizes, and whether {CIRCUIT} can carry its own fit")
print(
    pd.DataFrame(
        {
            f"{CIRCUIT} stints": here.groupby("compound").size(),
            "2026 all-circuit stints": era.groupby("compound").size(),
            "all stints": dry.groupby("compound").size(),
        }
    )
    .fillna(0)
    .astype(int)
)


def quantiles(values: pd.Series) -> pd.Series:
    """Deciles of a sample, indexed by the probability they cut at."""
    return values.quantile(DECILES)


print(f"\n--- deciles of the stint slope, {CIRCUIT} only (s/lap) ---")
if len(here):
    print(here.groupby("compound")["slope"].apply(quantiles).unstack().round(4))
print("\n--- deciles of the stint slope, 2026 all circuits (s/lap) ---")
print(era.groupby("compound")["slope"].apply(quantiles).unstack().round(4))

print("\n--- shape: is a normal defensible? ---")
for label, sample in ((CIRCUIT, here), ("2026 all circuits", era)):
    if not len(sample):
        continue
    described = sample.groupby("compound")["slope"].agg(
        n="count",
        mean="mean",
        median="median",
        sd="std",
        skew="skew",
        # Excess kurtosis: 0 is normal, positive means fatter tails.
        kurtosis=lambda s: s.kurtosis(),
    )
    print(f"\n{label}:")
    print(described.round(3))

# ------------------------------------------------------------- stint length

print("\n" + "=" * 90)
print("### STINT LENGTH — how long a set lasts, in laps")
# Every stint, not only the ones long enough to fit a slope: a three-lap stint is
# a real outcome and dropping it would bias the lengths upward.
lengths = (
    frame.groupby([*features.STINT_KEYS, "circuit", "Compound"], dropna=False)["stint_lap"]
    .max()
    .reset_index(name="laps")
)
lengths["year"] = lengths["year"].astype(int)
zand_len = lengths[
    (lengths["circuit"] == CIRCUIT) & lengths["Compound"].isin(["SOFT", "MEDIUM", "HARD"])
]
print(f"\n{CIRCUIT}, by compound:")
print(
    zand_len.groupby("Compound")["laps"]
    .agg(
        stints="count",
        median="median",
        p10=lambda s: s.quantile(0.1),
        p90=lambda s: s.quantile(0.9),
    )
    .round(1)
)

# ----------------------------------------------------------------- stop lap

print("\n" + "=" * 90)
print("### STOP LAP — where in the race the stops actually happen")
# A stop is an in-lap. Lap 1 in-laps are start-line incidents, not strategy.
stops = frame[frame["pit_in"].astype(bool) & (frame["LapNumber"] > 1)].copy()
stops["share"] = stops["LapNumber"] / stops["total_laps"]
zand_stops = stops[stops["circuit"] == CIRCUIT]
print(f"\n{CIRCUIT}: {len(zand_stops)} stops over {zand_stops['year'].nunique()} races")
print(zand_stops["share"].quantile(DECILES).round(3).to_string())
print(f"\nall circuits: {len(stops)} stops")
print(stops["share"].quantile(DECILES).round(3).to_string())

print("\nstops per car per race:")
per_car = stops.groupby([*features.RACE_KEYS, "Driver", "circuit"]).size().reset_index(name="stops")
print(
    per_car[per_car["circuit"] == CIRCUIT]["stops"]
    .value_counts()
    .sort_index()
    .rename(f"{CIRCUIT} cars")
    .to_string()
)

# ---------------------------------------------------------------- pit loss

print(SEP)
print("### PIT LOSS - what a stop costs, in seconds")
# One stop is **two** laps: the in-lap and the out-lap that follows it. A first
# attempt grouped by stint, which splits them - the in-lap closes stint N and the
# out-lap opens stint N+1 - and reported a 5-second lower quartile, which is not
# a pit stop, it is half of one. They are paired by lap number instead.
#
# The cost is what those two laps took above the race's own median green lap,
# which is the comparison a strategist makes.
median_lap = (
    frame[frame["is_representative"] & ~frame["is_neutralised"]]
    .groupby(features.RACE_KEYS)["LapTime"]
    .median()
)
timed = frame.join(median_lap.rename("race_median"), on=features.RACE_KEYS).copy()
timed["excess"] = timed["LapTime"] - timed["race_median"]

in_laps = timed[timed["pit_in"].astype(bool) & (timed["LapNumber"] > 1)][
    ["year", "round", "Driver", "circuit", "LapNumber", "excess", "is_neutralised"]
].rename(columns={"excess": "excess_in", "is_neutralised": "neutral_in"})
out_laps = timed[timed["pit_out"].astype(bool)][
    ["year", "round", "Driver", "LapNumber", "excess", "is_neutralised"]
].rename(columns={"excess": "excess_out", "is_neutralised": "neutral_out"})
out_laps["LapNumber"] = out_laps["LapNumber"] - 1  # pair to the in-lap before it

stop = in_laps.merge(out_laps, on=["year", "round", "Driver", "LapNumber"], how="inner")
stop["loss"] = stop["excess_in"] + stop["excess_out"]
stop["neutralised"] = stop["neutral_in"] | stop["neutral_out"]
stop = stop[stop["loss"].between(0, 120)]

print("")
print("NOTE: under a neutralisation the in-lap and out-lap are themselves slow,")
print("because the whole field is slow, so seconds overstate the cost there. What")
print("matters under a safety car is positions lost, not seconds, and that is")
print("measured in docs/research/pit-loss-under-neutralisation.md.")

for where, sample in ((CIRCUIT, stop[stop["circuit"] == CIRCUIT]), ("all circuits", stop)):
    print("")
    print(f"{where}:")
    print(
        sample.groupby("neutralised")["loss"]
        .agg(
            stops="count",
            median="median",
            p25=lambda s: s.quantile(0.25),
            p75=lambda s: s.quantile(0.75),
        )
        .round(1)
    )

print("\n" + "=" * 90)
print("### FOR THE SIMULATOR — paste into apps/web/src/tyres.ts")
source = here if len(here) >= 30 else era
label = CIRCUIT if len(here) >= 30 else "2026 all circuits"
print(f"wear-rate deciles taken from: {label}")
for compound in ("SOFT", "MEDIUM", "HARD"):
    sample = source[source["compound"] == compound]["slope"]
    if len(sample) < 10:
        sample = era[era["compound"] == compound]["slope"]
        note = f"  // {len(sample)} tandas · 2026 todos los circuitos (Zandvoort no alcanza)"
    else:
        note = f"  // {len(sample)} tandas · {label}"
    cuts = ", ".join(f"{v:.4f}" for v in sample.quantile(DECILES))
    print(f"  {compound}: [{cuts}],{note}")
print(f"\n  probabilities: [{', '.join(str(p) for p in DECILES)}]")
