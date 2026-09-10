"""How many sets a driver actually has, which the model ignores entirely.

The search treats compounds as an unlimited resource: it will happily recommend
three stints on new hards. A team does not have three new hards. The FIA allots
thirteen sets of slicks for a weekend and most of them are used up in practice
and qualifying, so what reaches the race is a small and lopsided pool.

This measures what the pool actually looks like, from the sets that got fitted:
how many distinct sets a driver runs in a race, how many of them are fresh, and
how that splits by compound. It is the first step toward a constraint the model
does not have.

``FreshTyre`` is what makes this measurable — it records whether the set had been
run before, which is a different question from ``TyreLife`` counting laps on it.

Run with ``uv run python scripts/tyre_allocation.py``.
"""

from __future__ import annotations

import pandas as pd

from boxbox_ml import cache, features, neutralisation, track_status

pd.set_option("display.width", 200)
SEP = "=" * 88

raw = pd.read_parquet(cache.cache_dir().parent / "laps_overtaking.parquet")
raw["circuit"] = raw["circuit"].map(lambda c: neutralisation.CIRCUIT_ALIASES.get(c, c))
frame = track_status.add_flags(raw)

# One row per stint: which compound, whether the set was new, how long it ran.
stints = (
    frame.groupby([*features.STINT_KEYS], dropna=False)
    .agg(
        circuit=("circuit", "first"),
        compound=("Compound", "first"),
        fresh=("FreshTyre", "first"),
        laps=("LapNumber", "size"),
        total_laps=("total_laps", "first"),
    )
    .reset_index()
)
dry = stints[stints["compound"].isin(["SOFT", "MEDIUM", "HARD"])]

print(SEP)
print("### CUÁNTOS JUEGOS USA UN AUTO EN UNA CARRERA")
per_race = dry.groupby([*features.RACE_KEYS, "Driver"]).agg(
    juegos=("Stint", "size"), frescos=("fresh", "sum")
)
print(per_race["juegos"].value_counts(normalize=True).sort_index().round(3).to_string())
print(f"\nmedia: {per_race['juegos'].mean():.2f} juegos por carrera")
print(f"de esos, frescos: {per_race['frescos'].mean():.2f}")
print(f"o sea que {1 - per_race['frescos'].sum() / per_race['juegos'].sum():.1%} de los juegos")
print("montados en carrera ya venían usados.")

print("\n" + SEP)
print("### CUÁNTOS JUEGOS FRESCOS DE CADA COMPUESTO")
fresh_by = (
    dry[dry["fresh"].eq(True)]
    .groupby([*features.RACE_KEYS, "Driver", "compound"])
    .size()
    .unstack(fill_value=0)
)
for compound in ("SOFT", "MEDIUM", "HARD"):
    if compound not in fresh_by:
        continue
    dist = fresh_by[compound].value_counts(normalize=True).sort_index()
    body = "  ".join(f"{k}:{v:.3f}" for k, v in dist.items())
    print(f"  {compound:7s} media {fresh_by[compound].mean():.2f}   reparto {body}")
print("\nEl reparto es la respuesta a «cuántos juegos nuevos de cada compuesto")
print("puede montar un auto en la carrera», que es la restricción que falta.")

print("\n" + SEP)
print("### ¿SE MONTAN JUEGOS USADOS, Y CUÁNDO?")
used = dry[~dry["fresh"].eq(True)].copy()
used["share"] = 0.0
print(f"stints con juego usado: {len(used):,} de {len(dry):,} ({len(used) / len(dry):.1%})")
print()
print("por compuesto, qué fracción de los stints usa un juego ya rodado:")
share = dry.groupby("compound")["fresh"].agg(stints="size", frescos=lambda s: s.eq(True).mean())
share["usados"] = (1 - share["frescos"]).round(3)
print(share[["stints", "usados"]].to_string())
print()
print("El blando es el que más se monta usado: es el que más se gasta en la")
print("clasificación, así que a la carrera llegan pocos nuevos.")

print("\n" + SEP)
print("### LO QUE ESTO LE PROHÍBE AL MODELO")
tres_frescos = (fresh_by.sum(axis=1) >= 3).mean() if len(fresh_by) else 0.0
print(f"autos que montaron 3 o más juegos frescos en la carrera: {tres_frescos:.1%}")
if "HARD" in fresh_by:
    dos_duros = (fresh_by["HARD"] >= 2).mean()
    print(f"autos que montaron 2 o más duros frescos:              {dos_duros:.1%}")
print()
print("El optimizador recomienda planes de dos y tres paradas con duro en cada")
print("stint. Si dos duros frescos casi no se ven en la realidad, esos planes no")
print("son ejecutables, y el modelo no tiene forma de saberlo.")
