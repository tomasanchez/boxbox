"""Case study: 2026 Dutch GP (Zandvoort, R12) — why point-forecasting fails.

This race is the cleanest illustration of the finding in
``docs/research/forecasting-strategy.md``: strategy is driven by race events, not
by tyre physics. It had a red flag, virtual safety cars and three-stop races, and
our leave-one-race-out model scored 4.5% exact accuracy on its stop counts.

It also surfaces a data-quality problem: a red-flag tyre change is free, and our
``boxed`` label cannot tell it apart from a strategic stop.
"""

from __future__ import annotations

import warnings

import pandas as pd

from boxbox_ml import cache, features, ingest

warnings.filterwarnings("ignore")
pd.set_option("display.width", 220)
pd.set_option("display.max_rows", 120)

SEASON, ROUND = 2026, 12

print(f"cache: {cache.enable()}\n")

import fastf1  # noqa: E402

session = fastf1.get_session(SEASON, ROUND, "R")
session.load(laps=True, telemetry=False, weather=True, messages=True)

frame = features.build(ingest.load_race(SEASON, ROUND))
total_laps = int(frame["total_laps"].iloc[0])

print("=" * 78)
print(f"### {session.event['EventName']} — {session.event['EventDate'].date()}")
print(f"  {total_laps} laps  |  {frame['Driver'].nunique()} drivers  |  {len(frame):,} lap records")

# ------------------------------------------------------------ event timeline
print("\n" + "=" * 78)
print("### 1. WHAT ACTUALLY HAPPENED — neutralisation timeline")

by_lap = (
    frame.groupby("LapNumber")[["yellow", "sc", "vsc", "vsc_ending", "red"]].max().astype(int)
)
active = by_lap[by_lap.sum(axis=1) > 0]


def _runs(series: pd.Series) -> list[str]:
    """Collapse a boolean lap series into human-readable lap ranges."""
    laps = series[series == 1].index.astype(int).tolist()
    if not laps:
        return []
    spans, start, prev = [], laps[0], laps[0]
    for lap in laps[1:]:
        if lap != prev + 1:
            spans.append((start, prev))
            start = lap
        prev = lap
    spans.append((start, prev))
    return [f"{a}" if a == b else f"{a}-{b}" for a, b in spans]


for flag in ("red", "sc", "vsc", "yellow"):
    spans = _runs(by_lap[flag])
    label = {"red": "RED FLAG", "sc": "Safety Car", "vsc": "VSC", "yellow": "Yellow"}[flag]
    print(f"  {label:<12} {len(spans):>2} period(s)  laps: {', '.join(spans) if spans else '-'}")

neutralised_laps = set(by_lap[(by_lap['sc'] | by_lap['vsc'] | by_lap['red']) > 0].index.astype(int))
print(f"\n  laps under some neutralisation: {len(neutralised_laps)}/{total_laps} "
      f"({100 * len(neutralised_laps) / total_laps:.0f}%)")

print("\n  --- race control messages mentioning the red flag / SC / VSC ---")
rcm = session.race_control_messages
if rcm is not None and len(rcm):
    pattern = "RED|SAFETY CAR|VSC|VIRTUAL"
    hits = rcm[rcm["Message"].str.upper().str.contains(pattern, na=False)]
    for _, row in hits.head(18).iterrows():
        lap = "" if pd.isna(row.get("Lap")) else f"L{int(row['Lap']):>2} "
        print(f"    {lap}{row['Message'][:88]}")

# ------------------------------------------------------------ stops & stints
print("\n" + "=" * 78)
print("### 2. STOPS AND STINTS")

stints = (
    frame.groupby([*features.STINT_KEYS], dropna=False)
    .agg(
        compound=("Compound", "first"),
        start=("LapNumber", "min"),
        end=("LapNumber", "max"),
        laps=("LapNumber", "count"),
    )
    .reset_index()
    .sort_values(["Driver", "start"])
)
per_driver = stints.groupby("Driver").agg(
    stops=("Stint", "count"), plan=("compound", lambda s: "-".join(c[0] for c in s))
)
per_driver["stops"] -= 1

print("  stop-count distribution:")
print("   ", per_driver["stops"].value_counts().sort_index().to_dict())
print(f"    modal strategy: {per_driver['stops'].mode().iloc[0]} stops")
print("\n  most common plans:")
print(per_driver["plan"].value_counts().head(8).to_string())

# --------------------------------------------------- do stops follow events?
print("\n" + "=" * 78)
print("### 3. DO THE STOPS FOLLOW THE EVENTS?")

boxed = frame[frame["boxed"]].copy()
boxed["on_neutralised"] = boxed["LapNumber"].astype(int).isin(neutralised_laps)
share = boxed["on_neutralised"].mean()
print(f"  pit stops at Zandvoort:                 {len(boxed)}")
print(f"  taken on a neutralised lap:             {int(boxed['on_neutralised'].sum())} "
      f"({100 * share:.0f}%)")
print(f"  neutralised share of all laps:          {100 * len(neutralised_laps) / total_laps:.0f}%")
print("\n  If stops were tyre-driven they would land on neutralised laps at roughly")
print("  the background rate. Landing far above it means the field is reacting to")
print("  the race, not to the rubber.")

print("\n  --- pit stops per lap (laps with 3+ stops) ---")
per_lap = boxed.groupby(boxed["LapNumber"].astype(int)).size()
busy = per_lap[per_lap >= 3]
for lap, count in busy.items():
    flags = []
    for flag in ("red", "sc", "vsc"):
        if int(by_lap.loc[lap, flag]) if lap in by_lap.index else 0:
            flags.append(flag.upper())
    print(f"    lap {lap:>2}: {count:>2} stops   {' '.join(flags) if flags else '(green)'}")

# --------------------------------------------- the red-flag labelling problem
print("\n" + "=" * 78)
print("### 4. THE LABELLING PROBLEM A RED FLAG CREATES")
red_laps = set(by_lap[by_lap["red"] == 1].index.astype(int))
if red_laps:
    red_boxed = boxed[boxed["LapNumber"].astype(int).isin(red_laps)]
    print(f"  laps under red flag: {sorted(red_laps)}")
    print(f"  'boxed' labels recorded on those laps: {len(red_boxed)}")
    print("\n  A red-flag tyre change is FREE — the race is stopped, so it costs no")
    print("  track time. Our `boxed` label is derived from PitInTime and cannot tell")
    print("  it apart from a strategic stop that costs ~20s. Training on these teaches")
    print("  the model that boxing is sometimes free, which is only true under red.")
    print("\n  Fix: add a `free_stop` flag from the red-flag track status and either")
    print("  exclude those rows or feed the flag as a feature. Logged as an open item.")
else:
    print("  No red-flag laps detected in the track status for this race.")
    print("  Note: a red flag can appear in race control messages without every")
    print("  driver's lap carrying status code 5 — cross-check both sources.")

# --------------------------------------------------- how our model did here
print("\n" + "=" * 78)
print("### 5. HOW OUR FORECAST MODEL DID HERE")
print("  From scripts/forecast_test.py, leave-one-race-out at Zandvoort:")
print("    exact stop-count accuracy   0.045  (1 driver in 22)")
print("    naive baseline              0.045")
print("    MAE                         1.27 stops")
print("\n  The model predicted a normal race. Zandvoort was not one — and no")
print("  pre-race feature could have said otherwise. This is the case for")
print("  forecasting a DISTRIBUTION over strategies rather than a point estimate.")
