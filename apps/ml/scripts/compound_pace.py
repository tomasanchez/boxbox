"""Compound pace offset, measured WITHIN a driver-race.

Comparing across cars conflates the compound with who chose to run it: in 2026
that reads the soft as 0.65 s/lap slower than the hard, which is not a tyre fact,
it is who was on softs. The only clean comparison is the same driver, in the same
race, on two different compounds at comparable tyre age.
"""

from __future__ import annotations

import warnings

import pandas as pd

from boxbox_ml import cache, features, neutralisation, track_status

warnings.filterwarnings("ignore")
pd.set_option("display.width", 180)

raw = pd.read_parquet(cache.cache_dir().parent / "laps_overtaking.parquet")
raw["circuit"] = raw["circuit"].map(lambda c: neutralisation.CIRCUIT_ALIASES.get(c, c))
base = features.add_degradation(
    features.add_fuel_correction(features.mark_representative(track_status.add_flags(raw)))
)
rain = base.groupby(["year", "round"])["Rainfall"].mean()
dry = base[~pd.MultiIndex.from_frame(base[["year", "round"]]).isin(set(rain[rain > 0.2].index))]

clean = dry[
    dry["is_representative"]
    & ~dry["is_neutralised"]
    & ~dry["red"]
    & dry["stint_lap"].between(3, 12)
    & dry["Compound"].isin(["SOFT", "MEDIUM", "HARD"])
]

# Mediana del ritmo de cada (piloto, carrera, compuesto) en vueltas jóvenes.
per = (
    clean.groupby(["year", "round", "Driver", "Compound"])["lap_time_fuel_corrected"]
    .agg(pace="median", laps="size")
    .reset_index()
)
per = per[per["laps"] >= 4]
wide = per.pivot_table(index=["year", "round", "Driver"], columns="Compound", values="pace")

print("### Pares del mismo piloto en la misma carrera, con goma joven (tanda 3-12)")
for a, b in (("SOFT", "MEDIUM"), ("MEDIUM", "HARD"), ("SOFT", "HARD")):
    rows = []
    for year in sorted(wide.index.get_level_values("year").unique()):
        sub = wide[wide.index.get_level_values("year") == year][[a, b]].dropna()
        if len(sub) < 8:
            continue
        d = sub[a] - sub[b]
        rows.append(
            {
                "año": year,
                "pares": len(sub),
                "mediana": round(d.median(), 3),
                "p25": round(d.quantile(0.25), 3),
                "p75": round(d.quantile(0.75), 3),
            }
        )
    todo = wide[[a, b]].dropna()
    d = todo[a] - todo[b]
    rows.append(
        {
            "año": "todas",
            "pares": len(todo),
            "mediana": round(d.median(), 3),
            "p25": round(d.quantile(0.25), 3),
            "p75": round(d.quantile(0.75), 3),
        }
    )
    print(f"\n{a} menos {b}  (negativo = {a} más rápido), s/vuelta")
    print(pd.DataFrame(rows).to_string(index=False))
