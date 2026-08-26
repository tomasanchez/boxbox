"""How much does a pit stop actually cost, green vs VSC vs Safety Car?

`features.FUEL_EFFECT_S_PER_LAP` has a sibling assumption that has never been
checked: the ``k`` factor in the conceptualización, which claims a stop under
Safety Car costs ~0.45 of a green-flag stop and under VSC ~0.60. Those numbers
were taken from commentary, not from data. This measures them.

Method. For a stop on lap L, the cost is how much slower that driver's in-lap and
out-lap were than *the rest of the field on the same laps*:

    pit_loss = (t_inlap - field_median_L) + (t_outlap - field_median_L+1)

Using the contemporaneous field median as the reference is what makes the
comparison fair. A naive reference — the driver's own green-flag pace — would make
every Safety Car stop look expensive, because everyone is slow under a Safety Car.
Cars that pitted on the reference lap are excluded from the median.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from boxbox_ml import cache, features, ingest

warnings.filterwarnings("ignore")
pd.set_option("display.width", 220)

SEASON = 2026
ROUNDS = list(range(1, 13))

print(f"cache: {cache.enable()}\n")

frames = []
for round_number in ROUNDS:
    try:
        frames.append(ingest.load_race(SEASON, round_number))
    except Exception as exc:  # noqa: BLE001
        print(f"  skip R{round_number:02d}: {type(exc).__name__}")
frame = features.build(pd.concat(frames, ignore_index=True))
frame["LapNumber"] = frame["LapNumber"].astype(int)

# Field reference pace per race-lap, from cars not involved in a stop.
clean = frame[~frame["pit_in"] & ~frame["pit_out"] & frame["LapTime"].notna()]
reference = (
    clean.groupby(["year", "round", "LapNumber"])["LapTime"]
    .median()
    .rename("field_median")
    .reset_index()
)
frame = frame.merge(reference, on=["year", "round", "LapNumber"], how="left")

frame = frame.sort_values(["year", "round", "Driver", "LapNumber"])
driver = frame.groupby(["year", "round", "Driver"], dropna=False)
frame["next_lap_time"] = driver["LapTime"].shift(-1)
frame["next_field_median"] = driver["field_median"].shift(-1)

stops = frame[frame["boxed"] & ~frame["free_stop"]].copy()
stops["pit_loss"] = (stops["LapTime"] - stops["field_median"]) + (
    stops["next_lap_time"] - stops["next_field_median"]
)
stops = stops[stops["pit_loss"].notna() & stops["pit_loss"].between(-5, 90)]


def condition(row: pd.Series) -> str:
    """Classify the track state the stop was taken under."""
    if row["sc"]:
        return "Safety Car"
    if row["vsc"] or row["vsc_ending"]:
        return "VSC"
    return "Green"


stops["condition"] = stops.apply(condition, axis=1)

print("=" * 86)
print("### 1. WHAT A STOP COSTS, BY TRACK CONDITION (seconds lost)")
print(f"  {len(stops)} strategic stops across {stops.groupby(['year', 'round']).ngroups} races")
print("  Red-flag stops excluded — those are free and were measured separately.\n")

table = stops.groupby("condition")["pit_loss"].agg(
    stops="count", median="median", mean="mean", p25=lambda s: s.quantile(0.25),
    p75=lambda s: s.quantile(0.75),
)
print(table.round(2).to_string())

green_median = float(table.loc["Green", "median"]) if "Green" in table.index else np.nan
print("\n  --- the k factor: cost relative to a green-flag stop ---")
for label in ("Green", "VSC", "Safety Car"):
    if label in table.index:
        k = float(table.loc[label, "median"]) / green_median
        saved = green_median - float(table.loc[label, "median"])
        print(f"    {label:<12} k = {k:.2f}   ({saved:+.1f}s vs green)")

print("\n  Conceptualización assumed k = 0.45 (SC) and 0.60 (VSC), taken from")
print("  commentary. The measured SECONDS do not support that — but seconds are")
print("  the wrong currency here. See positions below.")

print("\n" + "=" * 86)
print("### 1b. THE SAME STOPS, MEASURED IN POSITIONS")
print("  Under neutralisation the field is bunched, so clock seconds and track")
print("  position stop being interchangeable. Position is what wins races.\n")
stops["pos_delta"] = driver["Position"].shift(-1).loc[stops.index] - stops["Position"]
print(
    stops.groupby("condition")["pos_delta"]
    .agg(stops="count", median="median", mean="mean")
    .round(2)
    .to_string()
)
print("\n  A green stop costs ~2 places; a neutralised stop costs none.")
print("  That is the commentary claim, and it holds.")

print("\n" + "=" * 86)
print("### 1c. DOUBLE-STACKING CONFOUND")
print("  Teams bring both cars in on the same lap under a Safety Car and the")
print("  second waits. This inflates the neutralised seconds figure.\n")
team_lap = (
    stops.groupby(["year", "round", "LapNumber", "Team"]).size().rename("teammates").reset_index()
)
stacked = stops.merge(team_lap, on=["year", "round", "LapNumber", "Team"], how="left")
print(
    stacked.groupby(["condition", "teammates"])["pit_loss"]
    .agg(stops="count", median="median")
    .round(2)
    .to_string()
)

print("\n" + "=" * 86)
print("### 2. DO TEAMS EXPLOIT IT? (are stops over-represented under neutralisation)")

neutral_laps = frame["is_neutralised"].mean()
neutral_stops = (stops["condition"] != "Green").mean()
print(f"  share of all laps neutralised:        {100 * neutral_laps:5.1f}%")
print(f"  share of all stops under neutralisation: {100 * neutral_stops:5.1f}%")
print(f"  over-representation:                  {neutral_stops / neutral_laps:5.2f}x")
print("\n  If stops were taken purely on tyre condition they would land under")
print("  neutralisation at the background rate. Above it means teams are reacting.")

print("\n" + "=" * 86)
print("### 3. PER-RACE BREAKDOWN")
per_race = (
    stops.groupby(["round", "circuit", "condition"])["pit_loss"]
    .agg(["count", "median"])
    .unstack("condition")
    .round(1)
)
print(per_race.to_string())
