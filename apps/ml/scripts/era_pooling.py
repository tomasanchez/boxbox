"""Are pre-2026 seasons useless, or does pooling them help?

The "2026 only" decision rested on one measured fact: the compound degradation
hierarchy inverted in 2026, so a model trained on earlier seasons would learn
that soft wears fastest — backwards for 2026.

That argument covers the *compound* signal. It says nothing about pit loss,
undercut kinematics, circuit character or Safety Car propensity, all of which
plausibly transfer. This script tests the claim directly: train on 2026 alone,
then train on everything cached with an explicit ``season`` feature, and score
both on the same held-out 2026 races.

    uv run python scripts/era_pooling.py
"""

from __future__ import annotations

import contextlib
import warnings

import fastf1
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.metrics import average_precision_score, mean_absolute_error, precision_recall_curve

from boxbox_ml import cache, features, ingest

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)

TEST_ROUNDS = [10, 11, 12]  # held-out 2026 races, 25%
POOL_SEASONS = [2022, 2023, 2024, 2025]

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

print(f"cache: {cache.enable()}")
fastf1.Cache.offline_mode(True)
print("mode:  OFFLINE — cached races only\n")

frames = []
for round_number in range(1, 13):
    # A missing race is normal: the cache is built up in batches.
    with contextlib.suppress(Exception):
        frames.append(ingest.load_race(2026, round_number))
print(f"2026: {len(frames)} carreras")

pooled = []
for season in POOL_SEASONS:
    got = 0
    for round_number in range(1, 26):
        try:
            pooled.append(ingest.load_race(season, round_number))
            got += 1
        except Exception:  # noqa: BLE001
            pass
    print(f"{season}: {got} carreras")

frame = features.build(pd.concat(frames + pooled, ignore_index=True))
frame["season"] = frame["year"]
frame["nueva_era"] = (frame["year"] >= 2026).astype(int)

order = [*features.RACE_KEYS, "Driver", "LapNumber"]
frame = frame.sort_values(order)
driver = frame.groupby([*features.RACE_KEYS, "Driver"], dropna=False)
for column in LAGGED:
    frame[f"prev_{column}"] = driver[column].shift(1)

base_features = [f"prev_{c}" for c in LAGGED] + DIRECT + FLAGS + CATEGORICAL
model_frame = frame.dropna(subset=["prev_lap_time_fuel_corrected"]).copy()
for column in CATEGORICAL:
    model_frame[column] = model_frame[column].astype("category")
for column in FLAGS:
    model_frame[column] = model_frame[column].astype(int)

is_2026 = model_frame["year"] == 2026
test = model_frame[is_2026 & model_frame["round"].isin(TEST_ROUNDS)]
train_2026 = model_frame[is_2026 & ~model_frame["round"].isin(TEST_ROUNDS)]
train_pooled = model_frame[~is_2026 | ~model_frame["round"].isin(TEST_ROUNDS)]

print(f"\n{'=' * 84}")
print("### CONJUNTOS")
print(f"  test          2026 R{TEST_ROUNDS}      {len(test):>7,} vueltas")
print(f"  train 2026    2026 R1-9              {len(train_2026):>7,} vueltas")
print(f"  train pooled  2022-2025 + 2026 R1-9  {len(train_pooled):>7,} vueltas")
print(f"  factor de datos: {len(train_pooled) / max(len(train_2026), 1):.1f}x")


def score_classifier(train: pd.DataFrame, cols: list[str], label: str) -> dict:
    """Fit and score the box/stay classifier on the fixed 2026 test set."""
    y_train = train["strategic_stop"].astype(int)
    y_test = test["strategic_stop"].astype(int)
    model = LGBMClassifier(
        n_estimators=300, learning_rate=0.05, num_leaves=31, verbose=-1, random_state=0,
        scale_pos_weight=float((y_train == 0).sum() / max((y_train == 1).sum(), 1)),
    )
    model.fit(train[cols], y_train)
    proba = model.predict_proba(test[cols])[:, 1]
    ap = average_precision_score(y_test, proba)
    precision, recall, _ = precision_recall_curve(y_test, proba)
    f1 = np.divide(2 * precision * recall, precision + recall,
                   out=np.zeros_like(precision), where=(precision + recall) > 0)
    return {"modelo": label, "vueltas": len(train), "PR-AUC": ap,
            "lift": ap / y_test.mean(), "F1": f1.max()}


def score_regressor(train: pd.DataFrame, cols: list[str], label: str) -> dict:
    """Fit and score the degradation regressor on the fixed 2026 test set."""
    target = "degradation_s"
    tr = train[train["is_representative"] & train[target].notna()]
    te = test[test["is_representative"] & test[target].notna()]
    model = LGBMRegressor(n_estimators=400, learning_rate=0.05, verbose=-1, random_state=0)
    model.fit(tr[cols], tr[target])
    mae = mean_absolute_error(te[target], model.predict(te[cols]))
    naive = mean_absolute_error(te[target], np.full(len(te), tr[target].median()))
    return {"modelo": label, "vueltas": len(tr), "MAE": mae, "MAE ingenuo": naive,
            "gana": mae < naive}


era_features = [*base_features, "season", "nueva_era"]

print(f"\n{'=' * 84}")
print("### CLASIFICADOR — evaluado siempre sobre 2026 R10-12")
rows = [
    score_classifier(train_2026, base_features, "solo 2026"),
    score_classifier(train_pooled, base_features, "pooled, sin variable de era"),
    score_classifier(train_pooled, era_features, "pooled + season + nueva_era"),
]
print(pd.DataFrame(rows).round(4).to_string(index=False))

print(f"\n{'=' * 84}")
print("### REGRESOR DE DEGRADACIÓN — evaluado siempre sobre 2026 R10-12")
reg_base = ["stint_lap", "TyreLife", "laps_remaining", "TrackTemp", "AirTemp", "Compound"]
rows = [
    score_regressor(train_2026, reg_base, "solo 2026"),
    score_regressor(train_pooled, reg_base, "pooled, sin era"),
    score_regressor(train_pooled, [*reg_base, "season", "nueva_era"], "pooled + era"),
]
print(pd.DataFrame(rows).round(4).to_string(index=False))

print(f"\n{'=' * 84}")
print("### QUÉ TAN DISTINTAS SON LAS TEMPORADAS (degradación mediana s/vuelta)")
rep = frame[frame["is_representative"] & frame["degradation_rate_s_per_lap"].notna()]
dry = rep[rep["Compound"].isin(["SOFT", "MEDIUM", "HARD"])]
table = dry.groupby(["year", "Compound"])["degradation_rate_s_per_lap"].median().unstack()
print(table.round(4).to_string())
print("\n  orden de desgaste por temporada (de mayor a menor):")
for year in table.index:
    row = table.loc[year].dropna().sort_values(ascending=False)
    print(f"    {year}: {' > '.join(row.index)}")
