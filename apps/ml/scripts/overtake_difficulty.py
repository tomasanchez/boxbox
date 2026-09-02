"""Measure how hard it is to overtake at each circuit.

The broadcast «Battle Forecast» graphic shows an *overtake difficulty* gauge
next to the projected catch-up. This measures it instead of asserting it.

**What counts as a pass.** For each pair of consecutive laps, two drivers who
swap order have exchanged a position. That raw count is inflated by three things
that are not overtakes, so all three are excluded:

  * pit stops — a car that stops drops several places without anyone passing it
    on track, so any driver touching the pit lane on either lap is dropped from
    that transition, along with every pair they are part of;
  * neutralisations — under safety car, VSC or a red flag the order changes for
    reasons that have nothing to do with racing, and overtaking is banned
    outright, so only green-to-green transitions are counted;
  * rain — a wet race reshuffles the order for reasons that belong to the
    weather, not the layout. This was measured with wet races left in first, and
    they dominated: Zandvoort read 1.121 exchanges per lap in the wet 2023 race
    against 0.302 in the dry 2022 one, on the same tarmac.

**Why a rate and not a total.** Races differ in length, and a circuit that hosts
a 78-lap race is not harder to pass at than one that hosts 44. The rate is
exchanges per green racing lap, which is comparable across circuits and seasons.

**Why the estimate is shrunk.** Four or five races per circuit is not much. The
split-half test below measures how much of the spread between circuits repeats
across eras and how much is race-to-race noise, and each circuit is pulled toward
the overall mean by exactly that much. Without it, a circuit measured three times
gets to sit at the end of the ranking on the strength of one chaotic afternoon.

Run with ``uv run python scripts/overtake_difficulty.py --offline``. The parsed
laps are cached to parquet; add ``--reuse`` to skip re-parsing on later runs.
"""

from __future__ import annotations

import argparse
import warnings

import fastf1
import numpy as np
import pandas as pd

from boxbox_ml import cache, ingest, neutralisation, track_status

warnings.filterwarnings("ignore")
pd.set_option("display.width", 220)
pd.set_option("display.max_rows", 80)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--offline",
    action="store_true",
    help="use only cached sessions — makes no API calls and cannot hit the rate limit",
)
parser.add_argument("--seasons", type=int, nargs="+", default=[2022, 2023, 2024, 2025, 2026])
parser.add_argument(
    "--reuse",
    action="store_true",
    help="reuse the parquet from a previous run instead of re-parsing the FastF1 cache",
)
parser.add_argument(
    "--wet-share",
    type=float,
    default=0.2,
    help="drop a race when it rained on more than this share of its laps",
)
args = parser.parse_args()

print(f"cache: {cache.enable()}")
if args.offline:
    fastf1.Cache.offline_mode(True)
    print("mode:  OFFLINE — cached sessions only, no API calls\n")

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
frame["circuit"] = frame["circuit"].map(lambda c: neutralisation.CIRCUIT_ALIASES.get(c, c))

# Rain is the single biggest confound: it changes the order for reasons that have
# nothing to do with the circuit. A race counts as wet when it rained on more than
# a fifth of its laps, and is dropped whole rather than lap by lap — a drying
# track keeps producing weather-driven passes long after the rain stops.
if "Rainfall" in frame.columns:
    wet_share = frame.groupby(["year", "round"])["Rainfall"].mean()
    wet = sorted(wet_share[wet_share > args.wet_share].index)
    print(f"\n--- dropping {len(wet)} wet races (rain on >{args.wet_share:.0%} of laps) ---")
    for year, rnd in wet:
        row = frame[(frame["year"] == year) & (frame["round"] == rnd)].iloc[0]
        print(
            f"  {year} R{rnd:02d} {row['circuit']:<20} rain on {wet_share[(year, rnd)]:.0%} of laps"
        )
    keep = ~pd.MultiIndex.from_frame(frame[["year", "round"]]).isin(wet)
    frame = frame[keep].reset_index(drop=True)
else:
    print("\n  WARNING: no Rainfall column — wet races could NOT be excluded")


def exchanges_between(before: pd.DataFrame, after: pd.DataFrame) -> tuple[int, int]:
    """Count order swaps between two laps, and how many drivers they cover.

    Args:
        before: Rows for one lap.
        after: Rows for the next lap.

    Returns:
        ``(exchanges, drivers)`` — pairs that swapped order, and the drivers left
        after dropping anyone who touched the pit lane. Fewer than two drivers
        means the transition carries no information and is thrown away.
    """
    joined = before.merge(after, on="Driver", suffixes=("_a", "_b"))
    clean = joined[
        ~joined["pit_in_a"] & ~joined["pit_out_a"] & ~joined["pit_in_b"] & ~joined["pit_out_b"]
    ]
    if len(clean) < 2:
        return 0, 0

    first = clean["Position_a"].to_numpy()
    second = clean["Position_b"].to_numpy()
    # Discordant pairs: ahead on one lap, behind on the next.
    swapped = np.sign(first[:, None] - first[None, :]) != np.sign(second[:, None] - second[None, :])
    return int(np.triu(swapped, 1).sum()), len(clean)


rows = []
for (year, rnd), race in frame.groupby(["year", "round"], sort=True):
    green = race[~race["is_neutralised"] & ~race["red"]]
    by_lap = {lap: g for lap, g in green.groupby("LapNumber")}

    exchanges = 0
    counted = 0
    for lap in sorted(by_lap):
        # Only green-to-green: a transition into or out of a neutralisation is not
        # a racing lap, and the order there moves for other reasons.
        if lap + 1 not in by_lap:
            continue
        swaps, drivers = exchanges_between(by_lap[lap], by_lap[lap + 1])
        if drivers < 2:
            continue
        exchanges += swaps
        counted += 1

    if counted < 10:  # too little green running to say anything about the circuit
        continue
    rows.append(
        {
            "year": year,
            "round": rnd,
            "circuit": race["circuit"].iloc[0],
            "exchanges": exchanges,
            "green_transitions": counted,
            "per_lap": exchanges / counted,
        }
    )

races = pd.DataFrame(rows)
print(f"\nraces measured: {len(races)}  across {races['circuit'].nunique()} circuits")

print("\n" + "=" * 90)
print("### BY SEASON — the baseline each circuit is measured against")
print(
    races.groupby("year").agg(
        races=("round", "count"),
        exchanges_per_lap=("per_lap", "mean"),
        median=("per_lap", "median"),
    )
)

by_circuit = (
    races.groupby("circuit")
    .agg(races=("round", "count"), per_lap=("per_lap", "mean"), sd=("per_lap", "std"))
    .sort_values("per_lap")
)

print("\n" + "=" * 90)
print("### BY CIRCUIT — raw exchanges per green racing lap, hardest first")
print(by_circuit.round(3))

print("\n" + "=" * 90)
print("### SPLIT-HALF RELIABILITY — how much of that spread is real?")
# If the ranking is a property of the circuit it has to repeat. Correlating each
# circuit's early-era mean against its late-era mean estimates the reliability of
# a half-sample; Spearman-Brown steps that up to the full sample.
early = races[races["year"] <= 2023].groupby("circuit")["per_lap"].mean()
late = races[races["year"] >= 2024].groupby("circuit")["per_lap"].mean()
both = pd.concat([early.rename("2022-23"), late.rename("2024-26")], axis=1).dropna()
half = both["2022-23"].corr(both["2024-26"])
reliability = max(0.0, (2 * half) / (1 + half)) if half > -1 else 0.0
print(f"circuits present in both halves: {len(both)}")
print(f"split-half correlation:          {half:.3f}")
print(f"full-sample reliability (S-B):   {reliability:.3f}")
print(both.round(3).sort_values("2024-26"))

print("\n" + "=" * 90)
print("### BY CIRCUIT — shrunk toward the mean by the measured reliability")
grand = races["per_lap"].mean()
by_circuit["shrunk"] = grand + reliability * (by_circuit["per_lap"] - grand)
lo, hi = by_circuit["shrunk"].min(), by_circuit["shrunk"].max()
span = hi - lo
by_circuit["difficulty"] = 1 - (by_circuit["shrunk"] - lo) / span if span > 0 else 0.5
print(f"grand mean: {grand:.3f} exchanges per green racing lap")
raw_lo, raw_hi = by_circuit["per_lap"].min(), by_circuit["per_lap"].max()
print(f"shrunk range: {lo:.3f} to {hi:.3f}  (raw range {raw_lo:.3f} to {raw_hi:.3f})")
print(by_circuit.sort_values("shrunk").round(3))

print("\n" + "=" * 90)
print("### TABLE FOR THE UI — paste into apps/web/src/overtaking.ts")
ordered = by_circuit.sort_values("difficulty", ascending=False)
for circuit, row in ordered.iterrows():
    print(
        f"  '{circuit}': {row['difficulty']:.2f}, "
        f"// {row['races']:.0f} carreras · {row['per_lap']:.2f} cambios/vuelta"
    )
print(f"  default: {(1 - (grand - lo) / span) if span > 0 else 0.5:.2f},")

print("\n" + "=" * 90)
print("### ZANDVOORT — the circuit the simulator runs")
zand = races[races["circuit"] == "Zandvoort"]
print(zand.round(3).to_string(index=False) if len(zand) else "not measured")
if "Zandvoort" in by_circuit.index:
    row = by_circuit.loc["Zandvoort"]
    rank = list(ordered.index).index("Zandvoort") + 1
    print(
        f"\nZandvoort: {row['per_lap']:.3f} exchanges/lap raw, {row['shrunk']:.3f} shrunk, "
        f"difficulty {row['difficulty']:.3f}, rank {rank} of {len(by_circuit)} (1 = hardest)"
    )
