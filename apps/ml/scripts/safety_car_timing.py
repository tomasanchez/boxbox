"""When a safety car comes out, and how long it lasts.

The strategy optimiser draws whole races: it needs to know not only that 57% of
races see a safety car but where in the race it lands and how many laps it eats,
because a plan is only worth what it is worth against the safety car it meets.
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
frame = track_status.add_flags(frame)

# One row per race-lap: was any car under this status on that lap.
per_lap = (
    frame.groupby([*features.RACE_KEYS, "circuit", "LapNumber", "total_laps"])[["sc", "vsc", "red"]]
    .any()
    .reset_index()
)
per_lap["share"] = per_lap["LapNumber"] / per_lap["total_laps"]

rows = []
for (year, rnd), race in per_lap.groupby(features.RACE_KEYS):
    race = race.sort_values("LapNumber")
    for kind in ("sc", "vsc"):
        active = race[kind].to_numpy()
        laps = race["LapNumber"].to_numpy()
        shares = race["share"].to_numpy()
        start = None
        for i, on in enumerate(active):
            if on and start is None:
                start = i
            elif not on and start is not None:
                rows.append(
                    {
                        "year": year,
                        "round": rnd,
                        "kind": kind,
                        "circuit": race["circuit"].iloc[0],
                        "start_lap": int(laps[start]),
                        "start_share": float(shares[start]),
                        "laps": int(laps[i - 1] - laps[start] + 1),
                    }
                )
                start = None
        if start is not None:
            rows.append(
                {
                    "year": year,
                    "round": rnd,
                    "kind": kind,
                    "circuit": race["circuit"].iloc[0],
                    "start_lap": int(laps[start]),
                    "start_share": float(shares[start]),
                    "laps": int(laps[-1] - laps[start] + 1),
                }
            )

periods = pd.DataFrame(rows)
races = per_lap[features.RACE_KEYS].drop_duplicates()
print(f"races: {len(races)}   periods found: {len(periods)}")

print("\n" + "=" * 84)
print("### HOW MANY PERIODS PER RACE")
counts = periods.groupby([*features.RACE_KEYS, "kind"]).size().unstack(fill_value=0)
counts = races.set_index(features.RACE_KEYS).join(counts).fillna(0).astype(int)
for kind in ("sc", "vsc"):
    dist = counts[kind].value_counts(normalize=True).sort_index()
    print(f"\n{kind.upper()}: " + "  ".join(f"{k}:{v:.3f}" for k, v in dist.items()))
    any_of = (counts[kind] > 0).mean()
    print(f"  P(at least one) = {any_of:.3f}   mean per race = {counts[kind].mean():.2f}")

print("\n" + "=" * 84)
print("### WHEN IT STARTS - share of race distance")
for kind in ("sc", "vsc"):
    q = periods[periods["kind"] == kind]["start_share"].quantile(
        [0.05, 0.15, 0.25, 0.35, 0.5, 0.65, 0.75, 0.85, 0.95]
    )
    print(f"  {kind.upper()}: " + ", ".join(f"{v:.3f}" for v in q))

print("\n" + "=" * 84)
print("### HOW LONG IT LASTS - laps")
print(
    periods.groupby("kind")["laps"]
    .agg(
        n="count",
        p25=lambda s: s.quantile(0.25),
        median="median",
        p75=lambda s: s.quantile(0.75),
        p90=lambda s: s.quantile(0.9),
        mean="mean",
    )
    .round(2)
)

print("\n" + "=" * 84)
print("### ZANDVOORT")
z = periods[periods["circuit"] == "Zandvoort"]
zc = counts.join(per_lap.groupby(features.RACE_KEYS)["circuit"].first())
zc = zc[zc["circuit"] == "Zandvoort"]
p_sc, p_vsc = (zc["sc"] > 0).mean(), (zc["vsc"] > 0).mean()
print(f"races: {len(zc)}   P(SC) = {p_sc:.3f}   P(VSC) = {p_vsc:.3f}")
print(z.groupby("kind")["laps"].agg(n="count", median="median", mean="mean").round(2))
