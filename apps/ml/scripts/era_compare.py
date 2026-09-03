"""Compare tyre degradation and stop counts across regulation eras.

The 2026 power-unit and chassis reset is not a cosmetic change for this project:
if degradation behaves differently, a model trained on earlier seasons does not
transfer. This script measures that directly with our own feature pipeline rather
than trusting secondary reporting.

Run with ``uv run python scripts/era_compare.py``.
"""

from __future__ import annotations

import pandas as pd

from boxbox_ml import cache, features, ingest

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)

#: Rounds compared per era. 2026 is capped at the rounds actually run so far.
ERAS: dict[str, tuple[int, list[int]]] = {
    "2024 (previous rules)": (2024, list(range(1, 13))),
    "2026 (new rules)": (2026, list(range(1, 13))),
}

print(f"cache: {cache.enable()}\n")

frames: list[pd.DataFrame] = []
for label, (year, rounds) in ERAS.items():
    print(f"--- loading {label} ---")
    for round_number in rounds:
        try:
            raw = ingest.load_race(year, round_number)
            raw["era"] = label
            frames.append(raw)
            print(f"  ok   R{round_number:02d}  {len(raw):>5} laps")
        except Exception as exc:  # noqa: BLE001
            print(f"  skip R{round_number:02d}  {type(exc).__name__}: {str(exc)[:60]}")

frame = features.build(pd.concat(frames, ignore_index=True))
rep = frame[frame["is_representative"] & frame["degradation_rate_s_per_lap"].notna()]

print(f"\n\n{'=' * 78}")
print(f"total laps: {len(frame):,}   representative with a fitted slope: {len(rep):,}")

print(f"\n{'=' * 78}")
print("### DEGRADATION RATE (s/lap) BY ERA AND COMPOUND")
print("Positive = losing time as the tyre ages. Median is the honest statistic here;")
print("the mean is dragged around by traffic and by laps behind a Safety Car.\n")
dry = rep[rep["Compound"].isin(["SOFT", "MEDIUM", "HARD"])]
# NOTE: this counts *laps* carrying a fitted slope, not stints. Our estimator is a
# rolling 5-lap slope emitted per lap, not one linear fit per stint, so figures
# here are not directly comparable to published per-stint degradation numbers.
table = (
    dry.groupby(["era", "Compound"])["degradation_rate_s_per_lap"]
    .agg(laps="count", median="median", mean="mean")
    .round(4)
)
print(table.to_string())

print(f"\n{'=' * 78}")
print("### COMPOUND SPREAD PER ERA (max median - min median)")
medians = dry.groupby(["era", "Compound"])["degradation_rate_s_per_lap"].median().unstack()
for era in medians.index:
    row = medians.loc[era].dropna()
    fastest_wearing = row.idxmax()
    print(
        f"  {era:<24} spread={row.max() - row.min():.4f} s/lap"
        f"   fastest-wearing={fastest_wearing}   slowest-wearing={row.idxmin()}"
    )

print(f"\n{'=' * 78}")
print("### STOPS PER DRIVER PER RACE")
stints = (
    frame.groupby(["era", "year", "round", "Driver"])["Stint"]
    .nunique()
    .rename("stints")
    .reset_index()
)
stints["stops"] = stints["stints"] - 1
print(stints.groupby("era")["stops"].agg(["count", "mean", "median"]).round(3).to_string())
print("\n  distribution of stop counts (% of driver-races):")
dist = (
    stints.groupby("era")["stops"]
    .value_counts(normalize=True)
    .mul(100)
    .round(1)
    .unstack()
    .fillna(0)
)
print(dist.to_string())

print(f"\n{'=' * 78}")
print("### LABEL BALANCE (the positive class)")
print(
    frame.groupby("era")["boxed"]
    .agg(laps="count", boxed="sum")
    .assign(pct=lambda d: (100 * d["boxed"] / d["laps"]).round(2))
    .to_string()
)

print(f"\n{'=' * 78}")
print("### NEUTRALISED LAPS (SC / VSC) — the cheap-stop windows")
print(
    frame.groupby("era")[["sc", "vsc", "is_neutralised"]]
    .mean()
    .mul(100)
    .round(2)
    .rename(columns=lambda c: f"{c}_pct_of_laps")
    .to_string()
)
