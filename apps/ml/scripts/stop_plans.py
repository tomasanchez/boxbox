"""Measure the stop plan a car actually runs: how many, when, and with what.

The simulator was stopping every car with a window exactly once, on a compound
picked by a rule. Both are decisions, and decisions vary — this measures the
distribution they vary over.

Free stops are excluded throughout. A tyre change under a red flag is not the
~23-second trade-off being modelled, and Zandvoort is the worst offender in the
whole dataset: 31% of its stops are free.

Wet races are excluded too. Zandvoort measured with them in reads 21% of cars on
a four-stop plan, which is not a Zandvoort fact — it is the 2023 race being wet,
and the compound table gives it away with 21.5% of stops fitting intermediates.

The simulator starts at lap 30 of 72, so the number that matters is not how many
stops a car makes over a whole race but how many it has **left** from 41.7% of
the distance. That is measured separately at the end.
"""

from __future__ import annotations

import warnings

import fastf1
import pandas as pd

from boxbox_ml import cache, features, neutralisation, track_status

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)

cache.enable()
fastf1.Cache.offline_mode(True)
frame = pd.read_parquet(cache.cache_dir().parent / "laps_overtaking.parquet")
frame["circuit"] = frame["circuit"].map(lambda c: neutralisation.CIRCUIT_ALIASES.get(c, c))
frame = features.add_labels(track_status.add_flags(frame))

# Wet races out: they change the plan for reasons that belong to the weather.
if "Rainfall" in frame.columns:
    share = frame.groupby(features.RACE_KEYS)["Rainfall"].mean()
    wet = set(share[share > 0.2].index)
    frame = frame[~pd.MultiIndex.from_frame(frame[features.RACE_KEYS]).isin(wet)]
    print(f"dropped {len(wet)} wet races")

SEP = "=" * 88
CIRCUIT = "Zandvoort"

# A car that retired mid-race has a truncated plan; only cars that saw the flag
# describe a full strategy. Approximated by having run at least 90% of the laps.
ran = frame.groupby([*features.RACE_KEYS, "Driver"]).agg(
    laps=("LapNumber", "max"), total=("total_laps", "max"), circuit=("circuit", "first")
)
finishers = ran[ran["laps"] >= 0.9 * ran["total"]]

stops = (
    frame[frame["strategic_stop"] & (frame["LapNumber"] > 1)]
    .groupby([*features.RACE_KEYS, "Driver"])
    .size()
)
plan = finishers.join(stops.rename("stops")).fillna({"stops": 0})
plan["stops"] = plan["stops"].astype(int)

print(SEP)
print("### HOW MANY STRATEGIC STOPS — cars that saw the flag")
for where, sample in ((CIRCUIT, plan[plan["circuit"] == CIRCUIT]), ("all circuits", plan)):
    counts = sample["stops"].value_counts(normalize=True).sort_index()
    print(f"\n{where}  (n={len(sample)})")
    for k, v in counts.items():
        print(f"  {k} stops  {v:.3f}")

print("\n" + SEP)
print("### WHERE THE STOPS FALL — share of race distance, by stop number")
ordered = frame[frame["strategic_stop"] & (frame["LapNumber"] > 1)].sort_values(
    [*features.RACE_KEYS, "Driver", "LapNumber"]
)
ordered["nth"] = ordered.groupby([*features.RACE_KEYS, "Driver"]).cumcount() + 1
ordered["share"] = ordered["LapNumber"] / ordered["total_laps"]
here = ordered[ordered["circuit"] == CIRCUIT]
for where, sample in ((CIRCUIT, here), ("all circuits", ordered)):
    print(f"\n{where}:")
    print(
        sample[sample["nth"] <= 3]
        .groupby("nth")["share"]
        .agg(
            stops="count",
            p10=lambda s: s.quantile(0.1),
            median="median",
            p90=lambda s: s.quantile(0.9),
        )
        .round(3)
    )

print("\n" + SEP)
print("### WHAT THEY FIT — compound taken at a strategic stop")
fitted = ordered[ordered["next_compound"].notna()]
for where, sample in ((CIRCUIT, fitted[fitted["circuit"] == CIRCUIT]), ("all circuits", fitted)):
    print(f"\n{where}:")
    table = (
        sample[sample["Compound"].isin(["SOFT", "MEDIUM", "HARD"])]
        .groupby(["Compound", "next_compound"])
        .size()
        .unstack(fill_value=0)
    )
    print((table.T / table.sum(axis=1)).T.round(3))

print(SEP)
print("### WHAT THE SIMULATOR NEEDS - stops still to come from lap 30 of 72")
FROM = 30 / 72
late = ordered[ordered["share"] > FROM]
remaining = late.groupby([*features.RACE_KEYS, "Driver"]).size().rename("left")
plan_left = finishers.join(remaining).fillna({"left": 0})
plan_left["left"] = plan_left["left"].astype(int)
for where, sample in (
    (CIRCUIT, plan_left[plan_left["circuit"] == CIRCUIT]),
    ("all circuits", plan_left),
):
    counts = sample["left"].value_counts(normalize=True).sort_index()
    print("")
    print(f"{where}  (n={len(sample)})")
    for k, v in counts.items():
        print(f"  {k} stops left  {v:.3f}")

print("")
print("where those late stops fall, as share of race distance:")
CUTS = [0.05, 0.15, 0.25, 0.35, 0.5, 0.65, 0.75, 0.85, 0.95]
for where, sample in ((CIRCUIT, late[late["circuit"] == CIRCUIT]), ("all circuits", late)):
    q = sample["share"].quantile(CUTS)
    print(f"  {where} (n={len(sample)}): " + ", ".join(f"{v:.3f}" for v in q))

print("")
print("compound taken at those late stops, all circuits:")
late_fit = late[late["next_compound"].isin(["SOFT", "MEDIUM", "HARD"])]
tbl = (
    late_fit[late_fit["Compound"].isin(["SOFT", "MEDIUM", "HARD"])]
    .groupby(["Compound", "next_compound"])
    .size()
    .unstack(fill_value=0)
)
print((tbl.T / tbl.sum(axis=1)).T.round(3))

print("\n" + SEP)
print("### HOW MANY STOPS HAPPEN UNDER A NEUTRALISATION")
neutral = ordered.groupby("circuit")["is_neutralised"].agg(stops="count", under_sc="mean")
print(f"\nall circuits: {ordered['is_neutralised'].mean():.3f} of strategic stops")
print(f"{CIRCUIT}: {here['is_neutralised'].mean():.3f}")
print("\nby circuit, top and bottom:")
print(
    pd.concat(
        [neutral.sort_values("under_sc").head(4), neutral.sort_values("under_sc").tail(4)]
    ).round(3)
)
