"""End-to-end smoke check of the ingest -> features pipeline.

Run with ``uv run python scripts/smoke.py``. Uses two races chosen for contrast:
Monza 2019 ran under VSC, Monza 2023 ran green from lights to flag.
"""

from __future__ import annotations

import pandas as pd

from boxbox_ml import cache, features, ingest

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 40)

print(f"cache: {cache.enable()}\n")

raw = pd.concat(
    [ingest.load_race(2019, "Italian Grand Prix"), ingest.load_race(2023, "Italian Grand Prix")],
    ignore_index=True,
)
print(f"raw laps: {len(raw):,}  columns: {len(raw.columns)}")

frame = features.build(raw)
print(f"featured: {len(frame):,} rows\n")

print("--- label balance ---")
counts = frame["boxed"].value_counts()
positive = counts.get(True, 0)
print(f"  boxed=True  {positive:>5}  ({100 * positive / len(frame):.2f}%)")
print(f"  boxed=False {counts.get(False, 0):>5}")

print("\n--- representative laps ---")
rep = frame["is_representative"].sum()
print(f"  {rep:,} of {len(frame):,} ({100 * rep / len(frame):.1f}%) usable for pace fitting")

print("\n--- track status flags (lap counts) ---")
for flag in ("yellow", "sc", "vsc", "vsc_ending", "red", "is_neutralised"):
    print(f"  {flag:<15} {int(frame[flag].sum()):>5}")

print("\n--- feature coverage (non-null %) ---")
for column in (
    "lap_time_fuel_corrected",
    "degradation_s",
    "degradation_rate_s_per_lap",
    "gap_ahead_s",
    "gap_behind_s",
    "stint_lap",
):
    pct = 100 * frame[column].notna().sum() / len(frame)
    print(f"  {column:<28} {pct:6.1f}%")

print("\n--- degradation by compound (representative laps only) ---")
rep_frame = frame[frame["is_representative"]]
print(
    rep_frame.groupby("Compound")["degradation_rate_s_per_lap"]
    .agg(["count", "mean", "median"])
    .round(4)
    .to_string()
)

print("\n--- Leclerc 2019 stint 1: scrubbed-tyre check ---")
lec = frame[(frame["year"] == 2019) & (frame["Driver"] == "LEC") & (frame["Stint"] == 1)]
print(
    lec[["LapNumber", "stint_lap", "TyreLife", "FreshTyre", "Compound", "degradation_s"]]
    .head(6)
    .round(3)
    .to_string(index=False)
)

print("\n--- the boxed laps (2023 Monza, first 8) ---")
boxed = frame[(frame["year"] == 2023) & frame["boxed"]]
print(
    boxed[["Driver", "LapNumber", "Compound", "next_compound", "TyreLife", "gap_ahead_s"]]
    .head(8)
    .round(2)
    .to_string(index=False)
)
