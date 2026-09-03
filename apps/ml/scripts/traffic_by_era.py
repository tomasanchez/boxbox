"""Is the traffic penalty the same in every season and at every circuit?

Two reasons to doubt it. The 2026 regulations changed the aerodynamics, and dirty
air is an aerodynamic effect — if following got easier or harder, the penalty
measured over 2022-2025 does not describe the season being simulated. And a
circuit's layout plainly matters: a lap that is one long straight punishes
following less than a lap that is all medium-speed corners.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from boxbox_ml import cache, features, neutralisation, track_status

warnings.filterwarnings("ignore")
pd.set_option("display.width", 180)

raw = pd.read_parquet(cache.cache_dir().parent / "laps_overtaking.parquet")
raw["circuit"] = raw["circuit"].map(lambda c: neutralisation.CIRCUIT_ALIASES.get(c, c))
f = features.add_stint_position(
    features.add_fuel_correction(features.mark_representative(track_status.add_flags(raw)))
)
rain = f.groupby(["year", "round"])["Rainfall"].mean()
c = f[
    f["is_representative"]
    & ~f["is_neutralised"]
    & ~f["red"]
    & ~f["yellow"]
    & ~pd.MultiIndex.from_frame(f[["year", "round"]]).isin(set(rain[rain > 0.2].index))
].copy()

c = c.sort_values(["year", "round", "LapNumber", "Time"])
c["gap"] = c["Time"] - c.groupby(["year", "round", "LapNumber"])["Time"].shift(1)
c["sk"] = (
    c["year"].astype(str)
    + "-"
    + c["round"].astype(str)
    + "-"
    + c["Driver"]
    + "-"
    + c["Stint"].astype(str)
)
u = c[c["gap"].between(0, 60) & c["stint_lap"].between(2, 40)].copy()
u["close"] = (u["gap"] < 1.0).astype(float)
u["mid"] = u["gap"].between(1, 3).astype(float)


def penalty(sample: pd.DataFrame) -> tuple[float, float, int]:
    """Within-stint fixed effect, tyre age controlled. Returns (penalty, ci, n)."""
    cols = ["lap_time_fuel_corrected", "stint_lap", "close", "mid"]
    d = sample.dropna(subset=cols).copy()
    if d["sk"].nunique() < 40:
        return np.nan, np.nan, len(d)
    for col in cols:
        d[col] = d[col] - d.groupby("sk")[col].transform("mean")
    X = d[["stint_lap", "close", "mid"]].to_numpy(float)
    y = d["lap_time_fuel_corrected"].to_numpy(float)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ coef
    s2 = float(r @ r) / max(1, len(y) - 3)
    se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    return float(coef[1]), float(1.96 * se[1]), len(y)


SEP = "=" * 86
print(SEP)
print("### POR TEMPORADA — ¿cambió con el reglamento aerodinámico?")
rows = []
for year in sorted(u["year"].unique()):
    p, ci, n = penalty(u[u["year"] == year])
    rows.append({"año": year, "vueltas": n, "castigo <1s": round(p, 4), "±": round(ci, 4)})
print(pd.DataFrame(rows).to_string(index=False))

print("\n" + SEP)
print("### POR CIRCUITO — y si se repite entre eras")
rows = []
for circuit in sorted(u["circuit"].unique()):
    p, ci, n = penalty(u[u["circuit"] == circuit])
    if np.isnan(p):
        continue
    rows.append({"circuito": circuit, "vueltas": n, "castigo": round(p, 3), "±": round(ci, 3)})
byc = pd.DataFrame(rows).sort_values("castigo", ascending=False)
print(byc.to_string(index=False))

early, late = {}, {}
for circuit in byc["circuito"]:
    sub = u[u["circuit"] == circuit]
    a, _, _ = penalty(sub[sub["year"] <= 2023])
    b, _, _ = penalty(sub[sub["year"] >= 2024])
    if not (np.isnan(a) or np.isnan(b)):
        early[circuit], late[circuit] = a, b
both = pd.DataFrame({"2022-23": early, "2024-26": late}).dropna()
print(f"\ncircuitos en las dos mitades: {len(both)}")
print(f"correlación entre eras:      {both['2022-23'].corr(both['2024-26']):.3f}")

print("\n" + SEP)
print("### REZAGADOS — ¿se puede medir el tráfico de doblados?")
# El hueco de arriba exige la MISMA vuelta, así que excluye a los doblados por
# construcción. Acá se mira si hay algún auto en pista con menos vueltas dadas.
lead = c.groupby(["year", "round", "LapNumber"])["Time"].min().rename("lider")
pos = c.join(lead, on=["year", "round", "LapNumber"])
laps_done = c.groupby(["year", "round", "Driver"])["LapNumber"].max()
total = c.groupby(["year", "round"])["total_laps"].max()
lapped = (
    laps_done.reset_index()
    .join(total.rename("total"), on=["year", "round"])
    .assign(doblado=lambda d: d["LapNumber"] < d["total"] - 1)
)
print(f"pilotos-carrera: {len(lapped):,}")
print(f"terminaron al menos una vuelta abajo: {lapped['doblado'].mean():.1%}")
print()
print("La medición de tráfico exige que los dos autos estén en la misma vuelta,")
print("así que el tráfico de doblados queda fuera por construcción. Medirlo")
print("necesita comparar por tiempo de sesión y no por número de vuelta.")
