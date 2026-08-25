"""Is 2026 alone enough data to train the box/stay-out classifier?

Answers three questions with measurements rather than rules of thumb:

1. How many *independent* units are there — laps are not independent samples.
2. Does a baseline model beat the trivial "never box" strategy at all?
3. Is performance still climbing with more races, i.e. would waiting for the rest
   of the season help?

Run with ``uv run python scripts/feasibility.py``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import average_precision_score, precision_recall_curve
from sklearn.model_selection import GroupKFold

from boxbox_ml import cache, features, ingest

pd.set_option("display.width", 220)

SEASON = 2026
ROUNDS = list(range(1, 13))

#: Features known at the *start* of the lap. Anything derived from this lap's own
#: pace is lagged by one lap — see the leakage note below.
LAGGED = [
    "degradation_s",
    "degradation_rate_s_per_lap",
    "lap_time_fuel_corrected",
    "gap_ahead_s",
    "gap_behind_s",
    "Position",
]
DIRECT = [
    "stint_lap",
    "TyreLife",
    "laps_remaining",
    "total_laps",
    "TrackTemp",
    "AirTemp",
]
FLAGS = ["FreshTyre", "is_neutralised", "sc", "vsc", "yellow"]
CATEGORICAL = ["Compound", "circuit"]

print(f"cache: {cache.enable()}\n")

frames = []
for round_number in ROUNDS:
    try:
        frames.append(ingest.load_race(SEASON, round_number))
    except Exception as exc:  # noqa: BLE001
        print(f"  skip R{round_number:02d}: {type(exc).__name__}")
frame = features.build(pd.concat(frames, ignore_index=True))

print("=" * 78)
print("### 1. HOW MUCH DATA IS THERE, REALLY?")
print(f"  laps                 {len(frame):>7,}")
pos = int(frame["boxed"].sum())
print(f"  positives (boxed)    {pos:>7,}  ({100 * frame['boxed'].mean():.2f}%)")
print(f"  races                {frame.groupby(['year', 'round']).ngroups:>7,}")
print(f"  driver-races         {frame.groupby(['year', 'round', 'Driver']).ngroups:>7,}")
print(f"  driver-stints        {frame.groupby(features.STINT_KEYS).ngroups:>7,}")
print("\n  Laps are not independent samples: consecutive laps of one stint are")
print("  near-duplicates. The honest unit for splitting is the RACE, and there")
print("  are only 12 of those.")

# --- leakage guard -----------------------------------------------------------
print("\n" + "=" * 78)
print("### 2. LEAKAGE CHECK")
boxed_rep = frame.loc[frame["boxed"], "degradation_s"].notna().mean()
other_rep = frame.loc[~frame["boxed"], "degradation_s"].notna().mean()
print(f"  degradation_s present on boxed laps:     {100 * boxed_rep:5.1f}%")
print(f"  degradation_s present on non-boxed laps: {100 * other_rep:5.1f}%")
print("\n  An in-lap is never 'representative', so its pace features are NaN. Feeding")
print("  them raw would let the model read the answer off the missingness pattern.")
print("  Every pace feature is therefore LAGGED one lap: we predict 'will this driver")
print("  box at the end of this lap?' using only what was known at its start.")

order = [*features.RACE_KEYS, "Driver", "LapNumber"]
frame = frame.sort_values(order)
grouped = frame.groupby([*features.RACE_KEYS, "Driver"], dropna=False)
for column in LAGGED:
    frame[f"prev_{column}"] = grouped[column].shift(1)

feature_columns = [f"prev_{c}" for c in LAGGED] + DIRECT + FLAGS + CATEGORICAL
model_frame = frame.dropna(subset=["prev_lap_time_fuel_corrected"]).copy()
for column in CATEGORICAL:
    model_frame[column] = model_frame[column].astype("category")
for column in FLAGS:
    model_frame[column] = model_frame[column].astype(int)

X = model_frame[feature_columns]
y = model_frame["boxed"].astype(int)
groups = model_frame["round"]

print(f"\n  modelling rows after lagging: {len(model_frame):,}  positives: {int(y.sum()):,}")
epv = y.sum() / len(feature_columns)
print(f"  features: {len(feature_columns)}   events per feature: {epv:.1f}")


def evaluate(x: pd.DataFrame, target: pd.Series, group: pd.Series, n_splits: int = 5) -> dict:
    """Cross-validate grouped by race, so no race appears in both train and test."""
    oof = np.zeros(len(target))
    for train_idx, test_idx in GroupKFold(n_splits=n_splits).split(x, target, group):
        model = LGBMClassifier(
            n_estimators=300,
            learning_rate=0.05,
            num_leaves=31,
            scale_pos_weight=float((target == 0).sum() / max((target == 1).sum(), 1)),
            verbose=-1,
            random_state=0,
        )
        model.fit(x.iloc[train_idx], target.iloc[train_idx])
        oof[test_idx] = model.predict_proba(x.iloc[test_idx])[:, 1]

    ap = average_precision_score(target, oof)
    precision, recall, thresholds = precision_recall_curve(target, oof)
    f1 = np.divide(
        2 * precision * recall, precision + recall,
        out=np.zeros_like(precision), where=(precision + recall) > 0,
    )
    best = int(np.argmax(f1))
    return {
        "pr_auc": ap,
        "best_f1": f1[best],
        "precision": precision[best],
        "recall": recall[best],
        "threshold": thresholds[best] if best < len(thresholds) else 1.0,
    }


print("\n" + "=" * 78)
print("### 3. DOES A BASELINE MODEL BEAT CHANCE?")
result = evaluate(X, y, groups)
baseline_ap = y.mean()
print(f"  PR-AUC (average precision)  {result['pr_auc']:.4f}")
print(f"  PR-AUC of random guessing   {baseline_ap:.4f}   <- the positive rate")
print(f"  lift over chance            {result['pr_auc'] / baseline_ap:.1f}x")
print(f"\n  best F1                     {result['best_f1']:.4f}")
print(f"    precision at that point   {result['precision']:.4f}")
print(f"    recall at that point      {result['recall']:.4f}")
print("\n  'Never box' scores 96.3% accuracy and 0.0 F1. Accuracy is meaningless here.")

print("\n" + "=" * 78)
print("### 4. IS PERFORMANCE STILL CLIMBING WITH MORE RACES?")
print("  Trained on the first N races, always tested on the rest.\n")
print(f"  {'races':>6} {'train rows':>11} {'positives':>10} {'PR-AUC':>8} {'best F1':>8}")
for n_races in (3, 6, 9, 12):
    subset = model_frame[model_frame["round"] <= n_races]
    if subset["round"].nunique() < 3:
        continue
    sub_x = subset[feature_columns]
    sub_y = subset["boxed"].astype(int)
    splits = min(5, subset["round"].nunique())
    scores = evaluate(sub_x, sub_y, subset["round"], n_splits=splits)
    print(
        f"  {n_races:>6} {len(subset):>11,} {int(sub_y.sum()):>10,} "
        f"{scores['pr_auc']:>8.4f} {scores['best_f1']:>8.4f}"
    )

print("\n" + "=" * 78)
print("### 5. WHAT THE MODEL LEANS ON")
final = LGBMClassifier(
    n_estimators=300, learning_rate=0.05, num_leaves=31,
    scale_pos_weight=float((y == 0).sum() / max((y == 1).sum(), 1)),
    verbose=-1, random_state=0,
)
final.fit(X, y)
importance = (
    pd.Series(final.feature_importances_, index=feature_columns)
    .sort_values(ascending=False)
    .head(12)
)
print(importance.to_string())
