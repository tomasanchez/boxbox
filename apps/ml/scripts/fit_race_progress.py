import warnings

import numpy as np
import pandas as pd

from boxbox_ml import cache, features, neutralisation, track_status

warnings.filterwarnings("ignore")
pd.set_option("display.width", 180)

raw = pd.read_parquet(cache.cache_dir().parent / "laps_overtaking.parquet")
raw["circuit"] = raw["circuit"].map(lambda c: neutralisation.CIRCUIT_ALIASES.get(c, c))
f = features.add_stint_position(features.mark_representative(track_status.add_flags(raw)))
rain = f.groupby(["year", "round"])["Rainfall"].mean()
wet = set(rain[rain > 0.2].index)
c = f[
    f["is_representative"]
    & ~f["is_neutralised"]
    & ~f["red"]
    & ~f["yellow"]
    & f["Compound"].isin(["SOFT", "MEDIUM", "HARD"])
    & ~pd.MultiIndex.from_frame(f[["year", "round"]]).isin(wet)
].copy()
c["dr"] = c["year"].astype(str) + "-" + c["round"].astype(str) + "-" + c["Driver"]

fresh = c[c["stint_lap"].between(2, 7)]
rows = []
for _key, s in fresh.groupby("dr"):
    n = s["LapNumber"].to_numpy(float)
    t = s["LapTime"].to_numpy(float)
    if len(n) < 6 or n.max() - n.min() < 12 or not np.isfinite(t).all():
        continue
    X = np.column_stack([np.ones_like(n), n, s["stint_lap"].to_numpy(float)])
    coef = np.linalg.lstsq(X, t, rcond=None)[0]
    rows.append(
        {
            "year": int(s["year"].iloc[0]),
            "round": int(s["round"].iloc[0]),
            "circuit": s["circuit"].iloc[0],
            "theta": float(coef[1]),
            "laps": len(n),
        }
    )
st = pd.DataFrame(rows)

print("### La correccion combinada, por temporada")
print(
    st.groupby("year")["theta"]
    .agg(
        carreras_piloto="size",
        mediana="median",
        p25=lambda s: s.quantile(0.25),
        p75=lambda s: s.quantile(0.75),
    )
    .round(4)
    .to_string()
)

print("\n### Por circuito (mediana de sus carreras-piloto)")
byc = (
    st.groupby("circuit")["theta"]
    .agg(n="size", mediana="median", p25=lambda s: s.quantile(0.25), p75=lambda s: s.quantile(0.75))
    .sort_values("mediana")
)
print(byc.round(4).to_string())

print("\n### Zandvoort, carrera por carrera")
z = st[st["circuit"] == "Zandvoort"].groupby("year")["theta"].agg(pilotos="size", mediana="median")
print(z.round(4).to_string())

print("\n### Estabilidad: se repite el theta de un circuito entre eras?")
early = st[st.year <= 2023].groupby("circuit")["theta"].median()
late = st[st.year >= 2024].groupby("circuit")["theta"].median()
both = pd.concat([early.rename("a"), late.rename("b")], axis=1).dropna()
print(f"circuitos en las dos mitades: {len(both)}   correlacion: {both['a'].corr(both['b']):.3f}")

print("\n### Verificacion: cuanto queda de tendencia con cada correccion")
print("(deberia quedar del orden del desgaste medio, ~ +0.04 s/vuelta)")
zl = c[c["circuit"] == "Zandvoort"]
rem = zl["total_laps"] - zl["LapNumber"]
theta_z = -float(z.loc[2026, "mediana"]) if 2026 in z.index else None
for label, beta in [
    ("0.0350 (actual)", 0.035),
    ("0.0560 (mediana global)", 0.056),
    (f"{theta_z:.4f} (Zandvoort 2026)", theta_z),
]:
    tr = (zl["LapTime"] - beta * rem).groupby(zl["LapNumber"]).median()
    print(f"  {label:28s} {float(np.polyfit(tr.index, tr.to_numpy(), 1)[0]):+.4f} s/vuelta")
