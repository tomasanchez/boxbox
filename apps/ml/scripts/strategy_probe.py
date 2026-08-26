"""Can we forecast the STRATEGY of a race that has not happened yet?

Not the result — the plan: how many stops each car makes, how long each stint
runs, and on which compound.

Three questions:

1. Is there a usable stint-level dataset, and how is it censored?
2. Are practice sessions loadable? They are the only 2026 pace data that exists
   at a circuit the season has not raced at yet.
3. Does leave-one-race-out prediction work — training on 11 races and forecasting
   the twelfth is exactly the prospective task, simulated.
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

# ---------------------------------------------------------------- stint table
print("=" * 78)
print("### 1. THE STINT-LEVEL DATASET")

stints = (
    frame.groupby([*features.STINT_KEYS, "circuit"], dropna=False)
    .agg(
        compound=("Compound", "first"),
        start_lap=("LapNumber", "min"),
        end_lap=("LapNumber", "max"),
        length=("LapNumber", "count"),
        tyre_life_start=("TyreLife", "min"),
        fresh=("FreshTyre", "first"),
        total_laps=("total_laps", "first"),
        ended_in_pit=("boxed", "max"),
    )
    .reset_index()
)
stints["stint_index"] = stints.groupby(["year", "round", "Driver"])["start_lap"].rank().astype(int)
stints["n_stints"] = stints.groupby(["year", "round", "Driver"])["Stint"].transform("count")
stints["stops"] = stints["n_stints"] - 1
stints["reached_flag"] = stints["end_lap"] >= stints["total_laps"] - 1

print(f"  stints total            {len(stints):>6,}")
print(f"  ended in a pit stop     {int(stints['ended_in_pit'].sum()):>6,}  <- uncensored")
print(f"  ran to the flag         {int(stints['reached_flag'].sum()):>6,}  <- RIGHT-CENSORED")
print("\n  A stint that ends at the chequered flag did not end because the tyre was")
print("  done. Training 'how long does a stint last' on those teaches the model to")
print("  under-predict. They are excluded from the length model below.")

print("\n  --- stint length distribution (laps), uncensored only ---")
unc = stints[stints["ended_in_pit"] & ~stints["reached_flag"]]
print("   ", unc["length"].describe().round(1).to_dict())

print("\n  --- compound sequence per driver-race (top 10) ---")
seq = (
    stints.sort_values("start_lap")
    .groupby(["year", "round", "Driver"])["compound"]
    .apply(lambda s: "-".join(c[0] for c in s))
)
print(seq.value_counts().head(10).to_string())
print(f"\n  distinct sequences: {seq.nunique()} across {len(seq)} driver-races")

print("\n  --- stops per driver-race ---")
per_race = stints.groupby(["year", "round", "Driver"])["stops"].first()
print("   ", per_race.value_counts().sort_index().to_dict())

# ------------------------------------------------------- practice availability
print("\n" + "=" * 78)
print("### 2. ARE PRACTICE SESSIONS LOADABLE?")
print("  Practice is the ONLY 2026 pace data at a circuit the season has not raced")
print("  at yet. Without it, forecasting an unvisited circuit is guesswork.\n")

import fastf1  # noqa: E402

for round_number, name in ((12, "Dutch GP (conventional-ish)"), (9, "British GP (sprint)")):
    for code in ("FP1", "FP2", "FP3"):
        try:
            practice = fastf1.get_session(SEASON, round_number, code)
            practice.load(laps=True, telemetry=False, weather=False, messages=False)
            laps = practice.laps
            if laps.empty:
                print(f"  R{round_number:02d} {code:<4} loaded, 0 laps")
                continue
            long_runs = (
                laps.groupby(["Driver", "Stint"])["LapNumber"].count().pipe(lambda s: s[s >= 5])
            )
            print(
                f"  R{round_number:02d} {code:<4} {len(laps):>4} laps, "
                f"{laps['Compound'].nunique()} compounds, "
                f"{len(long_runs)} runs of 5+ laps  ({name})"
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  R{round_number:02d} {code:<4} {type(exc).__name__}: {str(exc)[:50]}")

# -------------------------------------------------- leave-one-race-out forecast
print("\n" + "=" * 78)
print("### 3. LEAVE-ONE-RACE-OUT: can we forecast a race we have never seen?")
print("  Train on 11 races, forecast the 12th. This is the prospective task,")
print("  simulated on races we already have the answer for.\n")

from lightgbm import LGBMRegressor  # noqa: E402
from sklearn.metrics import mean_absolute_error  # noqa: E402

model_stints = unc.copy()
model_stints["compound"] = model_stints["compound"].astype("category")
model_stints["circuit_cat"] = model_stints["circuit"].astype("category")
predictors = ["compound", "stint_index", "start_lap", "tyre_life_start", "total_laps"]

rows = []
for held_out in sorted(model_stints["round"].unique()):
    train = model_stints[model_stints["round"] != held_out]
    test = model_stints[model_stints["round"] == held_out]
    if len(test) < 5:
        continue
    model = LGBMRegressor(n_estimators=250, learning_rate=0.05, verbose=-1, random_state=0)
    model.fit(train[predictors], train["length"])
    pred = model.predict(test[predictors])
    naive = np.full(len(test), train["length"].median())
    rows.append(
        {
            "round": held_out,
            "circuit": test["circuit"].iloc[0],
            "stints": len(test),
            "mae_model": mean_absolute_error(test["length"], pred),
            "mae_naive": mean_absolute_error(test["length"], naive),
        }
    )

results = pd.DataFrame(rows)
results["beats_naive"] = results["mae_model"] < results["mae_naive"]
print(results.round(2).to_string(index=False))
print(
    f"\n  mean MAE model {results['mae_model'].mean():.2f} laps"
    f"   |  naive (median stint) {results['mae_naive'].mean():.2f} laps"
)
wins = int(results["beats_naive"].sum())
print(f"  model beats the naive baseline on {wins}/{len(results)} races")
