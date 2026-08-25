"""Does reframing the target from "this lap" to "within the next N laps" help?

`scripts/feasibility.py` shows that predicting the exact lap a driver boxes is
weak (best F1 ~0.19) and does not improve with more races. That is a symptom of
the target, not of the sample size: a strategist does not ask "box this lap,
yes or no", they ask "are we in the window".

This script tests horizons of 1, 2, 3 and 5 laps on identical features.
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
HORIZONS = (1, 2, 3, 5)

LAGGED = [
    "degradation_s",
    "degradation_rate_s_per_lap",
    "lap_time_fuel_corrected",
    "gap_ahead_s",
    "gap_behind_s",
    "Position",
]
DIRECT = ["stint_lap", "TyreLife", "laps_remaining", "total_laps", "TrackTemp", "AirTemp"]
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

order = [*features.RACE_KEYS, "Driver", "LapNumber"]
frame = frame.sort_values(order)
driver = frame.groupby([*features.RACE_KEYS, "Driver"], dropna=False)
for column in LAGGED:
    frame[f"prev_{column}"] = driver[column].shift(1)

# Horizon labels: boxes at the end of this lap, or within the next N-1 laps.
for horizon in HORIZONS:
    frame[f"box_within_{horizon}"] = (
        driver["boxed"]
        .transform(lambda s, h=horizon: s.iloc[::-1].rolling(h, min_periods=1).max().iloc[::-1])
        .astype(bool)
    )

feature_columns = [f"prev_{c}" for c in LAGGED] + DIRECT + FLAGS + CATEGORICAL
model_frame = frame.dropna(subset=["prev_lap_time_fuel_corrected"]).copy()
for column in CATEGORICAL:
    model_frame[column] = model_frame[column].astype("category")
for column in FLAGS:
    model_frame[column] = model_frame[column].astype(int)

X = model_frame[feature_columns]
groups = model_frame["round"]


def evaluate(target: pd.Series) -> dict:
    """Race-grouped cross-validation, so no race is in both train and test."""
    oof = np.zeros(len(target))
    for train_idx, test_idx in GroupKFold(n_splits=5).split(X, target, groups):
        model = LGBMClassifier(
            n_estimators=300,
            learning_rate=0.05,
            num_leaves=31,
            scale_pos_weight=float((target == 0).sum() / max((target == 1).sum(), 1)),
            verbose=-1,
            random_state=0,
        )
        model.fit(X.iloc[train_idx], target.iloc[train_idx])
        oof[test_idx] = model.predict_proba(X.iloc[test_idx])[:, 1]

    precision, recall, _ = precision_recall_curve(target, oof)
    f1 = np.divide(
        2 * precision * recall, precision + recall,
        out=np.zeros_like(precision), where=(precision + recall) > 0,
    )
    best = int(np.argmax(f1))
    return {
        "rate": target.mean(),
        "pr_auc": average_precision_score(target, oof),
        "f1": f1[best],
        "precision": precision[best],
        "recall": recall[best],
    }


print("=" * 78)
print("### TARGET HORIZON SWEEP — identical features, only the label changes")
print(f"\n  {'horizon':>8} {'pos rate':>9} {'PR-AUC':>8} {'chance':>8} {'lift':>6} "
      f"{'best F1':>8} {'prec':>7} {'recall':>7}")
for horizon in HORIZONS:
    target = model_frame[f"box_within_{horizon}"].astype(int)
    scores = evaluate(target)
    label = "this lap" if horizon == 1 else f"next {horizon}"
    print(
        f"  {label:>8} {100 * scores['rate']:>8.2f}% {scores['pr_auc']:>8.4f} "
        f"{scores['rate']:>8.4f} {scores['pr_auc'] / scores['rate']:>5.1f}x "
        f"{scores['f1']:>8.4f} {scores['precision']:>7.4f} {scores['recall']:>7.4f}"
    )

print("\n  'lift' is PR-AUC divided by the positive rate — how much better than")
print("  guessing at random. A lift near 1.0 means the model has learned nothing.")
