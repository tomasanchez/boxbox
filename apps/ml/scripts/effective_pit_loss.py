"""Effective pit loss: seconds lost *relative to the field*, by track status.

An earlier attempt compared the in-lap and out-lap against the race's median
green lap. That is wrong under a neutralisation: the whole field is slow on those
laps too, so the comparison charged the stopping car for a slowness everybody
shared and reported the safety-car stop as *more* expensive than a green one.

The right baseline is the field's own median on **those same laps**. What is left
is what the car actually conceded to its rivals, which is the number a strategy
optimiser needs.
"""

from __future__ import annotations

import warnings

import fastf1
import pandas as pd

from boxbox_ml import cache, features, neutralisation, track_status

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)

cache.enable()
fastf1.Cache.offline_mode(True)
frame = pd.read_parquet(cache.cache_dir().parent / "laps_overtaking.parquet")
frame["circuit"] = frame["circuit"].map(lambda c: neutralisation.CIRCUIT_ALIASES.get(c, c))
frame = features.add_labels(track_status.add_flags(frame))

# Baseline: the median lap time of every car on that exact lap of that race.
# Cars in the pit lane are excluded from their own baseline.
racing = frame[~frame["pit_in"].astype(bool) & ~frame["pit_out"].astype(bool)]
baseline = racing.groupby([*features.RACE_KEYS, "LapNumber"])["LapTime"].median()

work = frame.join(baseline.rename("field_lap"), on=[*features.RACE_KEYS, "LapNumber"])
work["over_field"] = work["LapTime"] - work["field_lap"]


def status_of(row: pd.Series) -> str:
    if row["red"]:
        return "RED"
    if row["sc"]:
        return "SC"
    if row["vsc"] or row["vsc_ending"]:
        return "VSC"
    return "GREEN"


ins = work[work["pit_in"].astype(bool) & (work["LapNumber"] > 1)][
    [
        "year",
        "round",
        "circuit",
        "Driver",
        "LapNumber",
        "over_field",
        "red",
        "sc",
        "vsc",
        "vsc_ending",
    ]
].copy()
ins["status"] = ins.apply(status_of, axis=1)
ins = ins.rename(columns={"over_field": "in_lap"})

outs = work[work["pit_out"].astype(bool)][
    ["year", "round", "Driver", "LapNumber", "over_field"]
].copy()
outs["LapNumber"] -= 1
outs = outs.rename(columns={"over_field": "out_lap"})

stop = ins.merge(outs, on=["year", "round", "Driver", "LapNumber"], how="inner")
stop["loss"] = stop["in_lap"] + stop["out_lap"]
stop = stop[stop["loss"].between(-10, 90)]

print("=" * 84)
print("### EFFECTIVE PIT LOSS - seconds conceded to the field, all circuits")
print(
    stop.groupby("status")["loss"]
    .agg(
        stops="count",
        p25=lambda s: s.quantile(0.25),
        median="median",
        p75=lambda s: s.quantile(0.75),
        p90=lambda s: s.quantile(0.9),
    )
    .round(1)
)

print("")
print("### ZANDVOORT")
z = stop[stop["circuit"] == "Zandvoort"]
print(
    z.groupby("status")["loss"]
    .agg(
        stops="count",
        p25=lambda s: s.quantile(0.25),
        median="median",
        p75=lambda s: s.quantile(0.75),
    )
    .round(1)
)

print("")
print("### THE DISCOUNT - what a neutralised stop saves, as a fraction of the green cost")
green = stop[stop["status"] == "GREEN"]["loss"].median()
for label in ("SC", "VSC", "RED"):
    sample = stop[stop["status"] == label]["loss"]
    if len(sample) < 20:
        continue
    med = sample.median()
    print(f"  {label:5s} {med:6.1f} s   {med / green:.2f} x green   (n={len(sample)})")
print(f"  GREEN {green:6.1f} s   1.00 x green")
