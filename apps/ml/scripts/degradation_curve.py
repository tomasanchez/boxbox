"""Is tyre degradation linear in stint length? Measured, per compound.

The optimiser extrapolates a fitted slope across a whole stint. That is only
valid if the deficit really does grow in a straight line. If it curves upward —
the cliff every commentator talks about — then extrapolating a slope fitted over
a short stint badly understates what a long one costs, and the search will
happily recommend never stopping.
"""

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
g = f[
    f["is_representative"]
    & ~f["is_neutralised"]
    & ~f["red"]
    & f["degradation_s"].between(-3, 8)
    & f["Compound"].isin(["SOFT", "MEDIUM", "HARD"])
]

print("### MEAN DEFICIT BY STINT LAP - seconds versus the stint's settled reference")
buckets = [(1, 5), (6, 10), (11, 15), (16, 20), (21, 25), (26, 30), (31, 35), (36, 45), (46, 70)]
rows = []
for low, high in buckets:
    window = g[g["stint_lap"].between(low, high)]
    row = {"laps": f"{low}-{high}", "n": len(window)}
    for compound in ("SOFT", "MEDIUM", "HARD"):
        sample = window[window["Compound"] == compound]["degradation_s"]
        row[compound] = round(sample.mean(), 3) if len(sample) > 30 else None
    rows.append(row)
print(pd.DataFrame(rows).to_string(index=False))

print("\n### LINEAR OR NOT - fit deficit = a*k + b*k^2 over the whole sample")
for compound in ("SOFT", "MEDIUM", "HARD"):
    sample = g[g["Compound"] == compound]
    k = sample["stint_lap"].to_numpy(dtype=float)
    d = sample["degradation_s"].to_numpy(dtype=float)
    quad = np.polyfit(k, d, 2)
    lin = np.polyfit(k, d, 1)
    # Residual variance tells whether the curve buys anything.
    r_quad = float(np.var(d - np.polyval(quad, k)))
    r_lin = float(np.var(d - np.polyval(lin, k)))
    print(
        f"  {compound:7s} n={len(sample):6d}  linear slope {lin[0]:.4f}"
        f"   quadratic {quad[0]:+.5f}k^2 {quad[1]:+.4f}k"
        f"   var {r_lin:.3f} -> {r_quad:.3f}"
    )

print("\n### WHAT A LONG STINT ACTUALLY COSTS - deficit at lap k, from the quadratic")
for compound in ("SOFT", "MEDIUM", "HARD"):
    sample = g[g["Compound"] == compound]
    quad = np.polyfit(
        sample["stint_lap"].to_numpy(dtype=float),
        sample["degradation_s"].to_numpy(dtype=float),
        2,
    )
    at = {k: round(float(np.polyval(quad, k)), 2) for k in (10, 20, 30, 40, 50)}
    print(f"  {compound:7s} " + "  ".join(f"L{k}: {v:5.2f}s" for k, v in at.items()))

print("\n### HOW OFTEN A SET ACTUALLY RUNS THAT LONG")
life = f.groupby([*features.STINT_KEYS, "Compound"], dropna=False)["stint_lap"].max()
life = life.reset_index(name="laps")
life = life[life["Compound"].isin(["SOFT", "MEDIUM", "HARD"])]
print(
    life.groupby("Compound")["laps"]
    .agg(
        stints="count",
        median="median",
        p90=lambda s: s.quantile(0.9),
        p99=lambda s: s.quantile(0.99),
        max="max",
        over_40=lambda s: (s > 40).mean(),
    )
    .round(3)
)
