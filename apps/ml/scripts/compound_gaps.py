"""Two things the inventory says we never measured."""

from __future__ import annotations

import warnings

import pandas as pd

from boxbox_ml import cache, features, neutralisation, track_status

warnings.filterwarnings("ignore")
pd.set_option("display.width", 180)

raw = pd.read_parquet(cache.cache_dir().parent / "laps_overtaking.parquet")
raw["circuit"] = raw["circuit"].map(lambda c: neutralisation.CIRCUIT_ALIASES.get(c, c))
base = features.add_labels(
    features.add_degradation(
        features.add_fuel_correction(features.mark_representative(track_status.add_flags(raw)))
    )
)
rain = base.groupby(["year", "round"])["Rainfall"].mean()
dry = base[~pd.MultiIndex.from_frame(base[["year", "round"]]).isin(set(rain[rain > 0.2].index))]

print("=" * 86)
print("### A · ¿La cantidad de paradas depende del compuesto de largada?")
start = (
    dry[dry["LapNumber"] == 1]
    .groupby(["year", "round", "Driver"])["Compound"]
    .first()
    .rename("largada")
)
ran = dry.groupby(["year", "round", "Driver"]).agg(l=("LapNumber", "max"), t=("total_laps", "max"))
fin = ran[ran["l"] >= 0.9 * ran["t"]]
n = (
    dry[dry["strategic_stop"] & (dry["LapNumber"] > 1)]
    .groupby(["year", "round", "Driver"])
    .size()
    .rename("paradas")
)
plan = fin.join(start).join(n).fillna({"paradas": 0})
plan["paradas"] = plan["paradas"].astype(int)
plan = plan[plan["largada"].isin(["SOFT", "MEDIUM", "HARD"])]
tab = pd.crosstab(plan["largada"], plan["paradas"], normalize="index").round(3)
print(f"n = {len(plan)} autos que vieron la bandera\n")
print(tab.to_string())
print("\nparadas promedio por compuesto de largada:")
print(
    plan.groupby("largada")["paradas"]
    .agg(autos="size", media="mean", mediana="median")
    .round(2)
    .to_string()
)

print("\n" + "=" * 86)
print("### B · ¿Cuánto más rápido es un compuesto que otro, a igual antigüedad?")
# Se compara dentro de la misma carrera y la misma vuelta de tanda, para que la
# pista, el combustible y el desgaste no se metan en la comparación.
young = dry[
    dry["is_representative"]
    & ~dry["is_neutralised"]
    & ~dry["red"]
    & dry["stint_lap"].between(3, 8)
    & dry["Compound"].isin(["SOFT", "MEDIUM", "HARD"])
].copy()
ref = young.groupby(["year", "round"])["lap_time_fuel_corrected"].transform("median")
young["rel"] = young["lap_time_fuel_corrected"] - ref
print(f"vueltas jóvenes (tanda 3-8) medidas: {len(young):,}\n")
print(
    young.groupby(["year", "Compound"])["rel"]
    .agg(n="size", mediana="median")
    .round(3)
    .unstack()
    .to_string()
)
print("\nagrupado, 2026:")
y26 = young[young["year"] == 2026]
print(
    y26.groupby("Compound")["rel"]
    .agg(n="size", mediana="median", p25=lambda s: s.quantile(0.25), p75=lambda s: s.quantile(0.75))
    .round(3)
    .to_string()
)
soft = y26[y26["Compound"] == "SOFT"]["rel"].median()
hard = y26[y26["Compound"] == "HARD"]["rel"].median()
print(f"\ndiferencia blando-duro con goma joven, 2026: {soft - hard:+.3f} s/vuelta")
