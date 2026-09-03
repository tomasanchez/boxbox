"""What does it cost to be stuck behind another car?

The genetic search prices a pit stop purely in seconds, so stopping on lap 38 and
stopping on lap 44 differ only by arithmetic — never by *who you come out
behind*. That is the mechanism this measures, and it is the main remaining
suspect for why the search barely beats a napkin rule.

## Traffic is not overtaking difficulty

They get conflated and they are different quantities:

* **Overtaking difficulty** is a property of the circuit — how hard it is to pass
  here at all. One number per track, already measured, and mostly noise outside
  the extremes.
* **Traffic** is a property of a moment — whether there is anyone in front of
  *this* car on *this* lap. It is what makes a pit-stop lap matter, because
  rejoining into a pack throws away the fresh-tyre advantage you just paid 22
  seconds for.

The cost of traffic is roughly *P(landing behind someone)* times *how long you
stay stuck* times *what you lose per lap while stuck*. Overtaking difficulty only
enters the middle term. This script measures the third.

## The measurement

The gap to the car ahead comes from the session clock: on each lap of each race,
sort the cars by elapsed time and difference it. Then, **within one driver's
stint**, compare the pace on laps spent close behind someone against the pace on
laps in clear air, controlling for how old the tyre is.

Within-stint is what makes it credible. Across cars, "close behind" would just
select fast cars.

**The bias runs one way, and it helps.** A car that is quick catches the one
ahead and gets stuck; a car that is slow drops back into clear air. So being
close behind correlates with being fast, which pushes the measured penalty
*down*. Whatever comes out is a lower bound on the real cost.

Run with ``uv run python scripts/traffic_cost.py``.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from boxbox_ml import cache, features, neutralisation, track_status

warnings.filterwarnings("ignore")
pd.set_option("display.width", 180)

#: Gap buckets, in seconds. The first is DRS range and dirty air; the last is
#: clear air and the reference everything is compared against.
BUCKETS = [(0.0, 1.0), (1.0, 2.0), (2.0, 3.0), (3.0, 5.0), (5.0, 1e9)]

SEP = "=" * 88

raw = pd.read_parquet(cache.cache_dir().parent / "laps_overtaking.parquet")
raw["circuit"] = raw["circuit"].map(lambda c: neutralisation.CIRCUIT_ALIASES.get(c, c))
frame = features.add_stint_position(
    features.add_fuel_correction(features.mark_representative(track_status.add_flags(raw)))
)

rain = frame.groupby(["year", "round"])["Rainfall"].mean()
wet = set(rain[rain > 0.2].index)
clean = frame[
    frame["is_representative"]
    & ~frame["is_neutralised"]
    & ~frame["red"]
    & ~frame["yellow"]
    & ~pd.MultiIndex.from_frame(frame[["year", "round"]]).isin(wet)
].copy()

# ------------------------------------------------------------------ gap ahead

# `Time` is the session clock at the end of the lap, so on a given lap of a given
# race the difference between two cars is the gap between them. Cars a lap down
# are excluded by requiring the same LapNumber.
clean = clean.sort_values(["year", "round", "LapNumber", "Time"])
grouped = clean.groupby(["year", "round", "LapNumber"])["Time"]
clean["gap_ahead"] = clean["Time"] - grouped.shift(1)
clean["place_on_lap"] = grouped.rank(method="first")

usable = clean[clean["gap_ahead"].between(0, 60) & clean["stint_lap"].between(2, 40)].copy()
print(SEP)
print("### THE SAMPLE")
print(f"clean green laps:            {len(clean):,}")
print(f"with a car ahead within 60s: {len(usable):,}")
print(f"driver-stints:               {usable.groupby(features.STINT_KEYS).ngroups:,}")

print("\n" + SEP)
print("### HOW OFTEN IS A CAR IN TRAFFIC?")
share = pd.DataFrame(
    [
        {
            "gap ahead": f"{low:.0f}-{high:.0f}s" if high < 1e8 else ">5s",
            "laps": int(usable["gap_ahead"].between(low, high).sum()),
        }
        for low, high in BUCKETS
    ]
)
share["% of laps"] = (share["laps"] / len(usable) * 100).round(1)
print(share.to_string(index=False))
print(
    f"\nWithin one second of the car ahead: {usable['gap_ahead'].lt(1).mean():.1%} of green laps."
)

# ------------------------------------------------------- the pace penalty

print("\n" + SEP)
print("### WHAT IT COSTS — within a driver's own stint, tyre age controlled")


def bucket_of(gap: float) -> str:
    for low, high in BUCKETS:
        if low <= gap < high:
            return f"{low:.0f}-{high:.0f}" if high < 1e8 else ">5"
    return ">5"


usable["bucket"] = usable["gap_ahead"].map(bucket_of)

# Design: driver-stint fixed effect, a linear tyre-age term, and one dummy per
# gap bucket with clear air (>5s) as the reference.
usable["stint_key"] = (
    usable["year"].astype(str)
    + "-"
    + usable["round"].astype(str)
    + "-"
    + usable["Driver"]
    + "-"
    + usable["Stint"].astype(str)
)
buckets_used = ["0-1", "1-2", "2-3", "3-5"]
for name in buckets_used:
    usable[f"in_{name}"] = (usable["bucket"] == name).astype(float)

columns = ["lap_time_fuel_corrected", "stint_lap", *[f"in_{n}" for n in buckets_used]]
model = usable.dropna(subset=columns).copy()
# Demeaning within stint is the fixed effect.
for column in columns:
    model[column] = model[column] - model.groupby("stint_key")[column].transform("mean")

design = model[["stint_lap", *[f"in_{n}" for n in buckets_used]]].to_numpy(dtype=float)
target = model["lap_time_fuel_corrected"].to_numpy(dtype=float)
coef, *_ = np.linalg.lstsq(design, target, rcond=None)
residual = target - design @ coef
dof = max(1, len(target) - design.shape[1])
covariance = (float(residual @ residual) / dof) * np.linalg.inv(design.T @ design)
stderr = np.sqrt(np.diag(covariance))

names = ["tyre age (s/lap)", *[f"gap {n}s vs clear air" for n in buckets_used]]
print(f"\nn = {len(target):,} laps across {model['stint_key'].nunique():,} stints")
for name, value, se in zip(names, coef, stderr, strict=True):
    print(f"  {name:26s} {value:+.4f}  ±{1.96 * se:.4f}")

print("\nPositive means slower. Clear air (>5s) is the reference, so the numbers are")
print("what a car gives up by having someone in front of it.")

# ----------------------------------------------------- what it means for a stop

print("\n" + SEP)
print("### WHAT THIS MEANS FOR A PIT STOP")
penalty = float(coef[1])
print(f"Being within a second costs {penalty:.3f} s/lap.")
print()
print("A car rejoining into traffic and taking a few laps to clear it therefore")
print("gives up:")
for laps in (3, 5, 8, 12):
    print(f"  {laps:2d} laps stuck  ->  {penalty * laps:5.2f} s")
print()
print("Against a measured green pit loss of 22.6 s, that is between")
print(f"{penalty * 3 / 22.6:.0%} and {penalty * 12 / 22.6:.0%} of the cost of the stop itself —")
print("and unlike the stop, it depends entirely on WHICH lap you choose.")
print("That is the term the search is currently blind to.")

print("\n" + SEP)
print("### HOW LONG DOES A CAR STAY STUCK?")
# Runs of consecutive laps within one second of the car ahead.
runs = []
for _key, stint in usable.sort_values("LapNumber").groupby("stint_key"):
    close = stint["gap_ahead"].lt(1.0).to_numpy()
    length = 0
    for flag in np.append(close, False):
        if flag:
            length += 1
        elif length:
            runs.append(length)
            length = 0
runs = pd.Series(runs)
print(f"episodes of consecutive laps within 1s: {len(runs):,}")
print(runs.describe(percentiles=[0.5, 0.75, 0.9, 0.95]).round(1).to_string())

print("\n" + SEP)
print("### DOES CIRCUIT DIFFICULTY CHANGE THE PENALTY?")
print("If overtaking difficulty and traffic cost are the same thing, the penalty")
print("should be much larger where passing is hard.")
hard = ["Monaco", "Budapest", "Zandvoort", "Baku", "Imola"]
easy = ["Las Vegas", "Monza", "Shanghai", "Yas Island", "Austin"]
for label, circuits in (("hard to pass", hard), ("easy to pass", easy)):
    sample = model[model.index.isin(usable[usable["circuit"].isin(circuits)].index)]
    if len(sample) < 2000:
        continue
    d = sample[["stint_lap", *[f"in_{n}" for n in buckets_used]]].to_numpy(dtype=float)
    t = sample["lap_time_fuel_corrected"].to_numpy(dtype=float)
    c, *_ = np.linalg.lstsq(d, t, rcond=None)
    print(f"  {label:14s} within 1s costs {c[1]:+.4f} s/lap   (n={len(sample):,})")
