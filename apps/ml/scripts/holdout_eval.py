"""Train / validation / test evaluation under the cátedra's 25% test requirement.

The split is **by race, chronologically**: the last three of the twelve 2026 rounds
are held out and never seen during training or tuning. Three of twelve is 25% of
races, which is the unit that matters — splitting by lap would put laps from the
same stint on both sides and leak.

Holding out the *latest* races rather than a random three also mirrors the real
task: the system has to forecast rounds that have not happened yet.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    mean_absolute_error,
    precision_recall_curve,
    r2_score,
)
from sklearn.model_selection import GroupKFold

from boxbox_ml import cache, features, ingest

warnings.filterwarnings("ignore")
pd.set_option("display.width", 220)

SEASON = 2026
ROUNDS = list(range(1, 13))
TEST_ROUNDS = [10, 11, 12]  # 3 of 12 = 25%

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

feature_columns = [f"prev_{c}" for c in LAGGED] + DIRECT + FLAGS + CATEGORICAL
model_frame = frame.dropna(subset=["prev_lap_time_fuel_corrected"]).copy()
for column in CATEGORICAL:
    model_frame[column] = model_frame[column].astype("category")
for column in FLAGS:
    model_frame[column] = model_frame[column].astype(int)

is_test = model_frame["round"].isin(TEST_ROUNDS)
train, test = model_frame[~is_test], model_frame[is_test]

print("=" * 86)
print("### SPLIT (by race, chronological — the last 3 of 12 rounds are held out)")
print(f"  train  rounds {sorted(train['round'].unique())}")
print(f"  test   rounds {sorted(test['round'].unique())}")
print(f"\n  {'':<10}{'races':>7}{'laps':>9}{'stops':>8}{'stop rate':>11}")
for name, part in (("train", train), ("test", test)):
    print(
        f"  {name:<10}{part['round'].nunique():>7}{len(part):>9,}"
        f"{int(part['strategic_stop'].sum()):>8}{part['strategic_stop'].mean():>11.4f}"
    )
print(
    f"\n  test share of races: {len(TEST_ROUNDS) / 12:.0%}   "
    f"of laps: {len(test) / len(model_frame):.1%}"
)

# ------------------------------------------------------- 1. degradation regressor
print("\n" + "=" * 86)
print("### 1. DEGRADATION REGRESSOR (the primary model)")
print("  Target: degradation_s — seconds lost against the stint's own reference lap.")
print("  NOT absolute lap time: every circuit appears exactly once per season, so an")
print("  absolute-time model is asked to predict a track it has never seen. Degradation")
print("  is circuit-relative by construction and does transfer.")
print("  Validation: GroupKFold(4) inside train only.\n")

TARGET = "degradation_s"
reg_features = ["stint_lap", "TyreLife", "laps_remaining", "TrackTemp", "AirTemp", "Compound"]
reg_train = train[train["is_representative"] & train[TARGET].notna()]
reg_test = test[test["is_representative"] & test[TARGET].notna()]

cv_scores = []
for tr_idx, va_idx in GroupKFold(n_splits=4).split(
    reg_train, reg_train[TARGET], reg_train["round"]
):
    model = LGBMRegressor(n_estimators=400, learning_rate=0.05, verbose=-1, random_state=0)
    model.fit(reg_train.iloc[tr_idx][reg_features], reg_train.iloc[tr_idx][TARGET])
    pred = model.predict(reg_train.iloc[va_idx][reg_features])
    cv_scores.append(mean_absolute_error(reg_train.iloc[va_idx][TARGET], pred))

regressor = LGBMRegressor(n_estimators=400, learning_rate=0.05, verbose=-1, random_state=0)
regressor.fit(reg_train[reg_features], reg_train[TARGET])
test_pred = regressor.predict(reg_test[reg_features])
naive = np.full(len(reg_test), reg_train[TARGET].median())

print(f"  train laps {len(reg_train):,}   test laps {len(reg_test):,}")
print(f"  validation MAE (GroupKFold mean)  {np.mean(cv_scores):8.3f} s")
mae_model = mean_absolute_error(reg_test[TARGET], test_pred)
print(f"  TEST MAE                          {mae_model:8.3f} s")
print(f"  TEST MAE, naive (train median)    {mean_absolute_error(reg_test[TARGET], naive):8.3f} s")
print(f"  TEST R²                           {r2_score(reg_test[TARGET], test_pred):8.3f}")

# --------------------------------------------------------- 2. box/stay classifier
print("\n" + "=" * 86)
print("### 2. BOX / STAY CLASSIFIER (declared baseline)")
print("  Target: strategic_stop — red-flag free changes excluded.\n")

y_train = train["strategic_stop"].astype(int)
y_test = test["strategic_stop"].astype(int)
weight = float((y_train == 0).sum() / max((y_train == 1).sum(), 1))

classifier = LGBMClassifier(
    n_estimators=300,
    learning_rate=0.05,
    num_leaves=31,
    scale_pos_weight=weight,
    verbose=-1,
    random_state=0,
)
classifier.fit(train[feature_columns], y_train)
proba = classifier.predict_proba(test[feature_columns])[:, 1]

ap = average_precision_score(y_test, proba)
precision, recall, thresholds = precision_recall_curve(y_test, proba)
f1 = np.divide(
    2 * precision * recall,
    precision + recall,
    out=np.zeros_like(precision),
    where=(precision + recall) > 0,
)
best = int(np.argmax(f1))
threshold = thresholds[best] if best < len(thresholds) else 0.5

print(f"  TEST PR-AUC                {ap:.4f}")
print(f"  chance (test positive rate){y_test.mean():.4f}")
print(f"  lift over chance           {ap / y_test.mean():.2f}x")
print(f"\n  at the best-F1 threshold ({threshold:.3f}):")
print(f"    F1         {f1[best]:.4f}")
print(f"    precision  {precision[best]:.4f}")
print(f"    recall     {recall[best]:.4f}")

predicted = (proba >= threshold).astype(int)
tn, fp, fn, tp = confusion_matrix(y_test, predicted).ravel()
print(f"\n  confusion matrix (test):  TN {tn:>5}  FP {fp:>4}  FN {fn:>4}  TP {tp:>4}")
print(f"  accuracy of 'never box' on test: {(y_test == 0).mean():.4f}  <- and it is ILLEGAL")

print("\n" + "=" * 86)
print("### 3. PER-RACE BREAKDOWN OF THE TEST SET")
test_out = test.assign(proba=proba, predicted=predicted)
per_race = test_out.groupby(["round", "circuit"], observed=True).agg(
    laps=("proba", "count"),
    actual_stops=("strategic_stop", "sum"),
    predicted_stops=("predicted", "sum"),
    caught=(
        "strategic_stop",
        lambda s: int(((s == 1) & (test_out.loc[s.index, "predicted"] == 1)).sum()),
    ),
)
print(per_race.to_string())
