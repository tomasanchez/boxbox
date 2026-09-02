"""How far a stint's pace deficit actually travels, and how fast."""

from __future__ import annotations

import warnings

import fastf1
import numpy as np
import pandas as pd

from boxbox_ml import cache, features, track_status

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)
cache.enable()
fastf1.Cache.offline_mode(True)
f = pd.read_parquet(cache.cache_dir().parent / "laps_overtaking.parquet")
f = features.add_degradation(
    features.add_fuel_correction(features.mark_representative(track_status.add_flags(f)))
)
g = f[f["is_representative"] & ~f["is_neutralised"] & ~f["red"]]

print("### degradation_s - deficit versus the stint's own settled reference lap")
print(
    g["degradation_s"]
    .describe(percentiles=[0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    .round(3)
    .to_string()
)

print("\n### the same, only late in a stint (lap 20+), where a cliff would show")
late = g[g["stint_lap"] >= 20]
print(
    late["degradation_s"]
    .describe(percentiles=[0.05, 0.5, 0.75, 0.9, 0.95, 0.99])
    .round(3)
    .to_string()
)

print("\n### degradation_rate_s_per_lap - the 5-lap rolling slope the snapshot carries")
print(
    g["degradation_rate_s_per_lap"]
    .describe(percentiles=[0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    .round(3)
    .to_string()
)

print("\n### is the rolling slope a good predictor of the rest of the stint?")
# For each stint, compare the slope measured at lap 10 against the whole-stint slope.
rows = []
for _, st in g.groupby(features.STINT_KEYS, dropna=False):
    st = st.sort_values("stint_lap")
    if len(st) < 18:
        continue
    at10 = st[st["stint_lap"] == 10]["degradation_rate_s_per_lap"]
    rest = st[st["stint_lap"] > 10]
    if at10.empty or at10.isna().all() or len(rest) < 6:
        continue
    whole = np.polyfit(rest["stint_lap"], rest["lap_time_fuel_corrected"], 1)[0]
    rows.append({"rolling": float(at10.iloc[0]), "actual": float(whole)})
cmp = pd.DataFrame(rows).dropna()
print(f"stints compared: {len(cmp)}")
r = cmp["rolling"].corr(cmp["actual"])
print(f"correlation between the 5-lap slope and what the stint went on to do: {r:.3f}")
print(cmp.describe(percentiles=[0.05, 0.5, 0.95]).round(4).to_string())
