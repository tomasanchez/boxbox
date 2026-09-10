"""Every neutralisation a race can throw, with how many and when.

The simulator draws **one** safety car per race at a flat probability and knows
nothing about red flags. Monza 2026 showed what that costs: a red flag on lap 3
gave all twenty-two cars a free tyre change and a VSC on lap 27 made the second
stop cheap, and the model could represent neither. Its recommendation was wrong
by twenty-one seconds of race time.

This measures what the draw should actually look like: for each of red flag,
safety car and VSC, how many periods a race sees, where they start, and how long
they last. The three are kept separate because they cost completely different
things — a red flag makes a tyre change free, a safety car makes it cheap, and a
VSC makes it slightly cheap.

Wet races are **not** excluded here. A safety car is a safety car whether it is
raining or not, and a strategy model has to price the race it might get.

Run with ``uv run python scripts/neutralisation_model.py``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from boxbox_ml import cache, features, neutralisation, track_status

pd.set_option("display.width", 200)

CUTS = [0.05, 0.15, 0.25, 0.35, 0.5, 0.65, 0.75, 0.85, 0.95]
SEP = "=" * 88

raw = pd.read_parquet(cache.cache_dir().parent / "laps_overtaking.parquet")
raw["circuit"] = raw["circuit"].map(lambda c: neutralisation.CIRCUIT_ALIASES.get(c, c))
frame = track_status.add_flags(raw)

# One row per race-lap: was any car under this flag on that lap.
per_lap = (
    frame.groupby([*features.RACE_KEYS, "circuit", "LapNumber", "total_laps"])[["sc", "vsc", "red"]]
    .any()
    .reset_index()
)
per_lap["share"] = per_lap["LapNumber"] / per_lap["total_laps"]

periods = []
for (year, rnd), race in per_lap.groupby(features.RACE_KEYS):
    race = race.sort_values("LapNumber")
    for kind in ("red", "sc", "vsc"):
        active = race[kind].to_numpy()
        laps = race["LapNumber"].to_numpy()
        shares = race["share"].to_numpy()
        start = None
        for index, flag in enumerate(np.append(active, False)):
            if flag and start is None:
                start = index
            elif not flag and start is not None:
                periods.append(
                    {
                        "year": year,
                        "round": rnd,
                        "circuit": race["circuit"].iloc[0],
                        "kind": kind,
                        "start_lap": int(laps[start]),
                        "start_share": float(shares[start]),
                        "laps": int(laps[index - 1] - laps[start] + 1),
                    }
                )
                start = None

periods = pd.DataFrame(periods)
races = per_lap[features.RACE_KEYS].drop_duplicates()
counts = (
    periods.groupby([*features.RACE_KEYS, "kind"])
    .size()
    .unstack(fill_value=0)
    .reindex(pd.MultiIndex.from_frame(races), fill_value=0)
)
counts = counts.join(per_lap.groupby(features.RACE_KEYS)["circuit"].first())

print(SEP)
print(f"### HOW OFTEN — over {len(races)} races")
for kind in ("red", "sc", "vsc"):
    dist = counts[kind].value_counts(normalize=True).sort_index()
    body = "  ".join(f"{k}:{v:.3f}" for k, v in dist.items())
    print(
        f"\n{kind.upper():4s} P(al menos uno) = {(counts[kind] > 0).mean():.3f}"
        f"   media por carrera = {counts[kind].mean():.2f}"
    )
    print(f"     reparto: {body}")

print("\n" + SEP)
print("### POR TEMPORADA — la intuición era que 2026 trae una bandera roja por carrera")
by_year = counts.join(per_lap.groupby(features.RACE_KEYS)["total_laps"].first()).reset_index()
season = by_year.groupby("year").agg(
    carreras=("round", "count"),
    p_roja=("red", lambda s: (s > 0).mean()),
    rojas_por_carrera=("red", "mean"),
    p_sc=("sc", lambda s: (s > 0).mean()),
    p_vsc=("vsc", lambda s: (s > 0).mean()),
)
print(season.round(3).to_string())
print()
p26 = season.loc[2026, "p_roja"]
n26 = season.loc[2026, "rojas_por_carrera"]
print(f"2026: bandera roja en el {p26:.0%} de las carreras, {n26:.2f} por carrera.")
if p26 < 0.8:
    print("Menos que 'una por carrera', pero muy por encima de las temporadas previas.")

print("\n" + SEP)
print("### CUÁNDO — fracción de la carrera en que empieza cada una")
for kind in ("red", "sc", "vsc"):
    sample = periods[periods["kind"] == kind]["start_share"]
    if len(sample) < 8:
        continue
    q = sample.quantile(CUTS)
    print(f"\n{kind.upper():4s} n={len(sample):3d}   mediana {sample.median():.3f}")
    print("     cortes: " + ", ".join(f"{v:.3f}" for v in q))
    tercio = pd.cut(sample, [0, 1 / 3, 2 / 3, 1.01], labels=["primer", "medio", "último"])
    reparto = tercio.value_counts(normalize=True).sort_index()
    print("     por tercio: " + "  ".join(f"{k}:{v:.2f}" for k, v in reparto.items()))

print("\n" + SEP)
print("### CUÁNTO DURAN — en vueltas")
print(
    periods.groupby("kind")["laps"]
    .agg(
        n="count",
        p25=lambda s: s.quantile(0.25),
        mediana="median",
        p75=lambda s: s.quantile(0.75),
        media="mean",
    )
    .round(2)
    .to_string()
)

print("\n" + SEP)
print("### ¿SE JUNTAN? — carreras con más de una clase de neutralización")
combos = counts[["red", "sc", "vsc"]].gt(0)
print(f"  sin ninguna:                {(~combos.any(axis=1)).mean():.3f}")
print(f"  una sola clase:             {(combos.sum(axis=1) == 1).mean():.3f}")
print(f"  dos clases:                 {(combos.sum(axis=1) == 2).mean():.3f}")
print(f"  las tres:                   {(combos.sum(axis=1) == 3).mean():.3f}")
print()
dos_o_mas = (counts[["red", "sc", "vsc"]].sum(axis=1) >= 2).mean()
print(f"  al menos dos períodos en total: {dos_o_mas:.3f}")
print("\nEse último número es el que importa: el simulador sortea UNA sola")
print("neutralización, y en más de la mitad de las carreras hay dos o más.")

print("\n" + SEP)
print("### PARA EL SIMULADOR")
for kind, label in (("red", "BANDERA ROJA"), ("sc", "SAFETY CAR"), ("vsc", "VSC")):
    dist = counts[kind].value_counts(normalize=True).sort_index()
    probs = [round(float(dist.get(n, 0.0)), 3) for n in range(0, 4)]
    probs[3] = round(1 - sum(probs[:3]), 3)
    sample = periods[periods["kind"] == kind]
    q = sample["start_share"].quantile(CUTS)
    print(f"\n  {label}")
    print(f"    cantidad (0,1,2,3+): {probs}")
    print(f"    inicio, cortes:      [{', '.join(f'{v:.3f}' for v in q)}]")
    print(f"    duración mediana:    {sample['laps'].median():.0f} vueltas")
