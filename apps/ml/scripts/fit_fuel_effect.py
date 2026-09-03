"""Fit the fuel-load coefficient instead of asserting it.

``features.FUEL_EFFECT_S_PER_LAP = 0.035`` is a constant borrowed from the
previous era, and it is the weakest assumption in the whole pipeline. It blocks
three things at once: the pace offset between compounds, the pit window for half
the grid, and part of the measured spread in wear rate.

## Two confounds, and one trap

Inside one stint, ``stint_lap`` and fuel remaining move together — the tyre ages
exactly as the tank empties — so a within-stint regression cannot separate them.
The usual fix is to compare **fresh-tyre laps from different stints of the same
race**: a car on new rubber at lap 5 and on new rubber at lap 45 differs almost
only in how much fuel it carries.

That leaves a second confound. **Track evolution** also makes later laps faster,
because the circuit rubbers in over the afternoon. Both fuel and evolution are
functions of the lap number, so within one race they cannot be told apart. What
separates them is **race length**: at lap 30 of a 44-lap race a car carries 14
laps of fuel with the track 68% evolved; at lap 30 of a 78-lap race it carries 48
laps of fuel with the track 38% evolved.

**The trap, which this script fell into first.** The natural move is to throw in a
fixed effect per driver-race to absorb car pace, and regress on ``laps_remaining``
and ``race_share`` together. That does not work, and it does not fail loudly — it
returns a confident, physically impossible answer. Within a driver-race
``total_laps`` is constant, so

    laps_remaining = L - L * race_share

makes the two regressors exactly affine: their within-race correlation is −1.000.
The fixed effect absorbs ``L``, which is precisely the variation that identified
them. The regression came back with **beta = −0.043 s/lap** — carrying fuel makes
you faster — and per-season estimates scattered from −0.12 to −0.02, which is the
signature of an unidentified split rather than a real effect.

## The design that works

Keep the two stages separate, so the between-race variation survives.

**Stage 1**, within each driver-race, on fresh laps only: regress lap time on lap
number. Since ``lap_time = c + beta*(L - n) + gamma*(n/L)``, the slope is

    theta_i = -beta + gamma / L_i

**Stage 2**, across driver-races: regress ``theta_i`` on ``1 / L_i``. The
intercept is ``-beta`` and the slope is ``gamma``. Race length now enters as
between-race variation, which is where it lives.

Run with ``uv run python scripts/fit_fuel_effect.py``.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from boxbox_ml import cache, features, neutralisation, track_status

warnings.filterwarnings("ignore")
pd.set_option("display.width", 180)

#: Stint laps counted as "fresh rubber". Lap 1 of a stint is an out-lap and never
#: settled; past this the tyre has started to go away.
FRESH = (2, 7)

#: A driver-race is only usable if its fresh laps span this many race laps, which
#: in practice means it made at least one stop.
MIN_SPAN = 12

SEP = "=" * 88

raw = pd.read_parquet(cache.cache_dir().parent / "laps_overtaking.parquet")
raw["circuit"] = raw["circuit"].map(lambda c: neutralisation.CIRCUIT_ALIASES.get(c, c))
frame = features.add_stint_position(features.mark_representative(track_status.add_flags(raw)))

rain = frame.groupby(["year", "round"])["Rainfall"].mean()
wet = set(rain[rain > 0.2].index)
clean = frame[
    frame["is_representative"]
    & ~frame["is_neutralised"]
    & ~frame["red"]
    & ~frame["yellow"]
    & frame["Compound"].isin(["SOFT", "MEDIUM", "HARD"])
    & ~pd.MultiIndex.from_frame(frame[["year", "round"]]).isin(wet)
].copy()
clean["driver_race"] = (
    clean["year"].astype(str) + "-" + clean["round"].astype(str) + "-" + clean["Driver"]
)

print(SEP)
print("### THE SAMPLE")
print(f"clean green laps:       {len(clean):,}")
print(f"driver-races:           {clean['driver_race'].nunique():,}")
print(f"race lengths:           {sorted(int(v) for v in clean['total_laps'].unique())}")

# ------------------------------------------------------------------ the trap

print("\n" + SEP)
print("### WHY THE OBVIOUS DESIGN FAILS")
one = clean[clean["driver_race"] == clean["driver_race"].iloc[0]]
lr = one["total_laps"] - one["LapNumber"]
sh = one["LapNumber"] / one["total_laps"]
print(f"one driver-race ({one['driver_race'].iloc[0]}, {int(one['total_laps'].iloc[0])} laps):")
print(f"  corr(laps_remaining, race_share) within it = {np.corrcoef(lr, sh)[0, 1]:.4f}")
print("A fixed effect per driver-race absorbs total_laps, and with total_laps held")
print("fixed the two regressors are affine. The split between fuel and evolution")
print("becomes arbitrary, and the answer it returns is physically impossible.")

# ------------------------------------------------------- stage 1: per driver-race

fresh = clean[clean["stint_lap"].between(*FRESH)]
rows = []
for key, sample in fresh.groupby("driver_race"):
    laps = sample["LapNumber"].to_numpy(dtype=float)
    times = sample["LapTime"].to_numpy(dtype=float)
    if len(laps) < 6 or laps.max() - laps.min() < MIN_SPAN:
        continue
    if not np.isfinite(times).all():
        continue
    # Lap number and stint lap together: the second mops up any residual tyre
    # ageing inside the fresh window, so the first is fuel plus evolution alone.
    design = np.column_stack([np.ones_like(laps), laps, sample["stint_lap"].to_numpy(dtype=float)])
    coef, *_ = np.linalg.lstsq(design, times, rcond=None)
    rows.append(
        {
            "driver_race": key,
            "year": int(sample["year"].iloc[0]),
            "total_laps": float(sample["total_laps"].iloc[0]),
            "theta": float(coef[1]),
            "laps": len(laps),
        }
    )

stage1 = pd.DataFrame(rows)
print("\n" + SEP)
print("### STAGE 1 — the 'later is faster' slope, one per driver-race")
print(f"driver-races usable: {len(stage1):,} of {clean['driver_race'].nunique():,}")
print(f"(needs >= 6 fresh laps spanning >= {MIN_SPAN} race laps, i.e. at least one stop)")
print()
print(stage1["theta"].describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95]).round(4).to_string())
print("\nNegative means later laps are faster, which is what fuel burn and track")
print("evolution together produce.")

# ---------------------------------------------------- stage 2: across driver-races


def stage2(sample: pd.DataFrame, label: str) -> tuple[float, float, float]:
    """Regress theta on 1/L. Intercept is -beta, slope is track evolution."""
    inverse = 1.0 / sample["total_laps"].to_numpy(dtype=float)
    theta = sample["theta"].to_numpy(dtype=float)
    weights = np.sqrt(sample["laps"].to_numpy(dtype=float))

    design = np.column_stack([np.ones_like(inverse), inverse]) * weights[:, None]
    coef, *_ = np.linalg.lstsq(design, theta * weights, rcond=None)
    residual = theta * weights - design @ coef
    dof = max(1, len(theta) - 2)
    sigma2 = float(residual @ residual) / dof
    covariance = sigma2 * np.linalg.inv(design.T @ design)
    stderr = np.sqrt(np.diag(covariance))

    beta = -float(coef[0])
    gamma = float(coef[1])
    ci = 1.96 * float(stderr[0])
    print(f"\n--- {label} ---")
    print(f"  n driver-races  {len(sample):,}")
    print(f"  beta            {beta:+.4f} s/lap  ±{ci:.4f}   ({beta - ci:+.4f} a {beta + ci:+.4f})")
    print(f"  track evolution {gamma:+.2f} s   (over the whole race, from 1/L slope)")
    return beta, gamma, ci


print("\n" + SEP)
print("### STAGE 2 — separating fuel from track evolution with race length")
beta_all, gamma_all, ci_all = stage2(stage1, "all seasons")

print("\nby season:")
per_season = []
for year in sorted(stage1["year"].unique()):
    sample = stage1[stage1["year"] == year]
    if len(sample) < 60:
        continue
    beta, gamma, ci = stage2(sample, str(year))
    per_season.append({"year": year, "beta": round(beta, 4), "ci": round(ci, 4), "n": len(sample)})

# ------------------------------------------------------------------- verdict

print("\n" + SEP)
print("### VERDICT")
print(f"  asserted   {features.FUEL_EFFECT_S_PER_LAP:.4f} s/lap")
print(f"  fitted     {beta_all:+.4f} s/lap  ±{ci_all:.4f}")
print(f"  ratio      {beta_all / features.FUEL_EFFECT_S_PER_LAP:.2f}x the asserted value")
print()
print(pd.DataFrame(per_season).to_string(index=False))

print("\n" + SEP)
print("### DOES IT FIX THE SYMPTOM?")
print("The test that exposed the problem: after correcting, the median lap time of")
print("a race should trend UPWARD at roughly the average wear rate (~+0.04 s/lap).")
print("With the asserted beta it comes out flat, the signature of under-correction.")
zand = clean[clean["circuit"] == "Zandvoort"]
remaining = zand["total_laps"] - zand["LapNumber"]
for label, beta in (
    ("asserted 0.0350", features.FUEL_EFFECT_S_PER_LAP),
    (f"fitted {beta_all:.4f}", beta_all),
):
    trend = (zand["LapTime"] - beta * remaining).groupby(zand["LapNumber"]).median()
    slope = float(np.polyfit(trend.index, trend.to_numpy(), 1)[0])
    print(f"  {label:20s} trend {slope:+.4f} s per race lap")
