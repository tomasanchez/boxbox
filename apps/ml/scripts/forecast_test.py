"""Does practice pace make race strategy forecastable?

`scripts/strategy_probe.py` showed a stint-length model built only from race-side
features fails to beat predicting the median (MAE 8.13 vs 8.02 laps). The obvious
missing ingredient is how the tyre actually behaves *at that circuit*, which for an
unvisited circuit can only come from practice.

This tests that directly, leave-one-race-out: train on 11 races, forecast the 12th
using only information that existed before its lights went out.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_absolute_error

from boxbox_ml import cache, features, ingest, practice

warnings.filterwarnings("ignore")
pd.set_option("display.width", 220)

SEASON = 2026
ROUNDS = list(range(1, 13))

print(f"cache: {cache.enable()}\n")

print("--- loading races ---")
race_frames = []
for round_number in ROUNDS:
    try:
        race_frames.append(ingest.load_race(SEASON, round_number))
    except Exception as exc:  # noqa: BLE001
        print(f"  skip R{round_number:02d}: {type(exc).__name__}")
frame = features.build(pd.concat(race_frames, ignore_index=True))

print("--- loading practice (this is the slow part) ---")
fp = practice.load_many(SEASON, ROUNDS)
print(f"  practice summaries: {len(fp)} compound-rounds")
print(fp.groupby("round")["fp_runs"].sum().to_string())

# ------------------------------------------------------------- stint table
stints = (
    frame.groupby([*features.STINT_KEYS, "circuit"], dropna=False)
    .agg(
        compound=("Compound", "first"),
        start_lap=("LapNumber", "min"),
        end_lap=("LapNumber", "max"),
        length=("LapNumber", "count"),
        tyre_life_start=("TyreLife", "min"),
        total_laps=("total_laps", "first"),
        ended_in_pit=("boxed", "max"),
    )
    .reset_index()
)
stints["stint_index"] = stints.groupby(["year", "round", "Driver"])["start_lap"].rank().astype(int)
stints["reached_flag"] = stints["end_lap"] >= stints["total_laps"] - 1

# Only stints that ended because the team chose to pit are uncensored.
model_stints = stints[stints["ended_in_pit"] & ~stints["reached_flag"]].copy()
model_stints = model_stints.merge(fp, on=["year", "round", "compound"], how="left")

coverage = model_stints["fp_deg_slope"].notna().mean()
print(f"\n  stints with a practice slope for their compound: {100 * coverage:.1f}%")

BASE = ["stint_index", "start_lap", "tyre_life_start", "total_laps"]
WITH_FP = [*BASE, "fp_deg_slope", "fp_median_pace", "fp_runs"]

model_stints["compound"] = model_stints["compound"].astype("category")


def leave_one_race_out(predictors: list[str]) -> pd.DataFrame:
    """Train on every race but one, forecast the held-out race."""
    columns = [*predictors, "compound"]
    rows = []
    for held_out in sorted(model_stints["round"].unique()):
        train = model_stints[model_stints["round"] != held_out]
        test = model_stints[model_stints["round"] == held_out]
        if len(test) < 5:
            continue
        model = LGBMRegressor(n_estimators=250, learning_rate=0.05, verbose=-1, random_state=0)
        model.fit(train[columns], train["length"])
        pred = model.predict(test[columns])
        naive = np.full(len(test), train["length"].median())
        rows.append(
            {
                "round": held_out,
                "circuit": test["circuit"].iloc[0],
                "stints": len(test),
                "mae": mean_absolute_error(test["length"], pred),
                "mae_naive": mean_absolute_error(test["length"], naive),
            }
        )
    return pd.DataFrame(rows)


print("\n" + "=" * 78)
print("### STINT LENGTH, LEAVE-ONE-RACE-OUT (MAE in laps, lower is better)")

base = leave_one_race_out(BASE).rename(columns={"mae": "mae_base"})
with_fp = leave_one_race_out(WITH_FP).rename(columns={"mae": "mae_with_fp"})
merged = base.merge(
    with_fp[["round", "mae_with_fp"]], on="round"
)
merged["fp_helps"] = merged["mae_with_fp"] < merged["mae_base"]
print(merged.round(2).to_string(index=False))

print(
    f"\n  naive (median stint)      {merged['mae_naive'].mean():.2f} laps"
    f"\n  race features only        {merged['mae_base'].mean():.2f} laps"
    f"\n  + practice pace           {merged['mae_with_fp'].mean():.2f} laps"
)
print(
    f"\n  practice helps on {int(merged['fp_helps'].sum())}/{len(merged)} races;"
    f" beats naive on {int((merged['mae_with_fp'] < merged['mae_naive']).sum())}/{len(merged)}"
)

# ------------------------------------------------- stop count, the coarser target
print("\n" + "=" * 78)
print("### NUMBER OF STOPS PER DRIVER-RACE (the coarser, more useful target)")

per_driver = (
    stints.groupby(["year", "round", "circuit", "Driver"])
    .agg(stops=("Stint", "count"), total_laps=("total_laps", "first"))
    .reset_index()
)
per_driver["stops"] -= 1
fp_race = fp.groupby(["year", "round"]).agg(
    fp_deg_mean=("fp_deg_slope", "mean"),
    fp_deg_spread=("fp_deg_slope", lambda s: s.max() - s.min()),
    fp_runs=("fp_runs", "sum"),
).reset_index()
per_driver = per_driver.merge(fp_race, on=["year", "round"], how="left")

rows = []
for held_out in sorted(per_driver["round"].unique()):
    train = per_driver[per_driver["round"] != held_out]
    test = per_driver[per_driver["round"] == held_out]
    model = LGBMRegressor(n_estimators=200, learning_rate=0.05, verbose=-1, random_state=0)
    cols = ["total_laps", "fp_deg_mean", "fp_deg_spread", "fp_runs"]
    model.fit(train[cols], train["stops"])
    pred = np.rint(model.predict(test[cols]))
    naive = np.full(len(test), round(train["stops"].median()))
    rows.append(
        {
            "round": held_out,
            "circuit": test["circuit"].iloc[0],
            "drivers": len(test),
            "actual_mode": int(test["stops"].mode().iloc[0]),
            "exact_model": (pred == test["stops"]).mean(),
            "exact_naive": (naive == test["stops"]).mean(),
            "mae_model": mean_absolute_error(test["stops"], pred),
        }
    )
stops_result = pd.DataFrame(rows)
print(stops_result.round(3).to_string(index=False))
print(
    f"\n  exact-stop-count accuracy: model {stops_result['exact_model'].mean():.3f}"
    f"  |  naive {stops_result['exact_naive'].mean():.3f}"
    f"  |  MAE {stops_result['mae_model'].mean():.2f} stops"
)
