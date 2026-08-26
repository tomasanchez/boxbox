"""Measure per-circuit Safety Car, VSC and red-flag rates.

These become the draw parameters for the Monte Carlo simulator. Uses the
ground-effect era (2022 onward) so the cars are broadly comparable, and reports
2026 separately because it neutralises far more than the seasons before it.

Run with ``uv run python scripts/safety_car_rates.py``; add ``--offline`` to use
only what is already cached.

**FastF1 rate-limits at 500 API calls per hour.** A full multi-season ingest blows
through that and every remaining race is skipped, so build the cache up over
several sessions and then run this offline.
"""

from __future__ import annotations

import argparse
import warnings

import fastf1
import pandas as pd

from boxbox_ml import cache, ingest, neutralisation

warnings.filterwarnings("ignore")
pd.set_option("display.width", 220)
pd.set_option("display.max_rows", 60)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--offline",
    action="store_true",
    help="use only cached sessions — makes no API calls and cannot hit the rate limit",
)
parser.add_argument("--seasons", type=int, nargs="+", default=[2022, 2023, 2024, 2025, 2026])
args = parser.parse_args()

print(f"cache: {cache.enable()}")
if args.offline:
    fastf1.Cache.offline_mode(True)
    print("mode:  OFFLINE — cached sessions only, no API calls\n")
else:
    print("mode:  online — will download uncached sessions (500 calls/h limit)\n")

print("--- ingesting ---")
frame = ingest.build_dataset(args.seasons)
races = neutralisation.summarise_races(frame)
races["neutralised_share"] = races["neutralised_laps"] / races["total_laps"]

print(f"\nraces summarised: {len(races)}  across {races['circuit'].nunique()} circuits")

print("\n" + "=" * 90)
print("### BASELINE BY SEASON — the era shift, and why circuit effects are multipliers")
season = races.groupby("year").agg(
    races=("round", "count"),
    p_sc=("sc_periods", lambda s: (s > 0).mean()),
    p_vsc=("vsc_periods", lambda s: (s > 0).mean()),
    p_red=("red_periods", lambda s: (s > 0).mean()),
    sc_periods_per_race=("sc_periods", "mean"),
    neutralised_share=("neutralised_share", "mean"),
)
print(season.round(3).to_string())

print("\n" + "=" * 90)
print("### PER-CIRCUIT: P(at least one Safety Car)")
print("  raw_rate is what was observed; shrunk_rate pools it toward the global rate")
print("  with a fitted Beta prior, because a handful of visits cannot support a")
print("  confident number. multiplier = shrunk_rate / global rate.\n")
sc = neutralisation.circuit_rates(races, "sc")
print(
    sc[["visits", "occurred", "raw_rate", "shrunk_rate", "multiplier", "mean_neutralised_share"]]
    .round(3)
    .to_string()
)
print(f"\n  prior strength (alpha+beta): {sc['prior_strength'].iloc[0]:.2f} pseudo-visits")
print(f"  global P(SC): {(races['sc_periods'] > 0).mean():.3f}")

print("\n" + "=" * 90)
print("### PER-CIRCUIT: P(at least one VSC)")
vsc = neutralisation.circuit_rates(races, "vsc")
print(vsc[["visits", "occurred", "raw_rate", "shrunk_rate", "multiplier"]].round(3).to_string())
print(f"\n  global P(VSC): {(races['vsc_periods'] > 0).mean():.3f}")

print("\n" + "=" * 90)
print("### PER-CIRCUIT: P(at least one RED FLAG)")
red = neutralisation.circuit_rates(races, "red")
print(
    red[red["occurred"] > 0][["visits", "occurred", "raw_rate", "shrunk_rate", "multiplier"]]
    .round(3)
    .to_string()
)
print(f"\n  global P(red): {(races['red_periods'] > 0).mean():.3f}")
print("  (circuits that never threw one are omitted; their shrunk rate is the floor)")

print("\n" + "=" * 90)
print("### WHEN DO NEUTRALISATIONS START? (fraction of race distance)")
profile = neutralisation.start_lap_profile(races, frame)
print(
    profile.groupby("event")["race_fraction"]
    .describe(percentiles=[0.25, 0.5, 0.75])
    .round(3)
    .to_string()
)
print("\n  first-quarter share of each event type:")
early = profile.assign(early=profile["race_fraction"] <= 0.25).groupby("event")["early"].mean()
print(early.round(3).to_string())

print("\n" + "=" * 90)
print("### CIRCUITS ON THE REMAINING 2026 CALENDAR")
print("  Shrunk SC rate for the circuits still to be raced this season.\n")
remaining = [
    "Monza", "Barcelona", "Baku", "Sakhir", "Marina Bay",
    "Austin", "Mexico City", "São Paulo", "Las Vegas", "Lusail", "Yas Island",
]
known = sc.index.tolist()
for name in remaining:
    match = [c for c in known if name.lower() in str(c).lower()]
    if match:
        row = sc.loc[match[0]]
        print(
            f"  {match[0]:<22} visits={int(row['visits'])}  raw={row['raw_rate']:.2f}  "
            f"shrunk={row['shrunk_rate']:.2f}  x{row['multiplier']:.2f}"
        )
    else:
        print(f"  {name:<22} not matched in the ingested set")
