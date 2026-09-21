"""¿Los equipos estiran la tanda cuando la goma aguanta, y qué calzan bajo VSC?

Dos preguntas que el simulador contesta hoy con un supuesto, y las dos resultan
tener respuesta medida.

## El plan dice la vuelta 27 y el auto para en la 27

El desgaste del modelo **es** probabilístico —cada sorteo le da a la goma un
ritmo de caída distinto de la distribución medida— pero el plan fija la vuelta y
el auto para ahí en todos los sorteos, le esté sobrando goma o se le esté
cayendo a pedazos. El modelo sortea la incertidumbre y después la ignora. Es un
plan a **lazo abierto**, y lo único que tiene de lazo cerrado es ``MAX_STINT``,
que fuerza la parada cuando la tanda se pasa del límite medido.

Medido, el muro sí corre a lazo cerrado, y vale entre tres y cuatro vueltas y
media de tanda. La caída se estima sobre las **primeras ocho vueltas** y se
pregunta si predice cuánto va a durar; ajustarla sobre la tanda entera sería
usar el futuro para predecir el futuro.

El efecto sobrevive el control que lo podría explicar. Una tanda temprana lleva
más nafta, y quemarla hace que los tiempos mejoren, lo cual mete una pendiente
negativa que no tiene nada que ver con la goma. Dentro del **mismo compuesto y
la misma tanda** el efecto sigue ahí: el medio en la primera tanda da r=-0,290,
con 23,0 vueltas cuando la goma aguanta contra 18,5 cuando se cae.

## Y qué calzan cuando la neutralización llega temprano

Bajo VSC temprano el **75,4%** calza duro, contra el 62,3% de los que paran
temprano en verde, y esa tanda de duro dura **29,7 vueltas** contra 26,3. El
37% llega a la bandera a cuadros sin volver a parar, contra el 24%. La
neutralización temprana no sólo adelanta la parada: **cambia a qué se cambia**,
y con la intención de estirar hasta el final.

Correr con ``uv run python scripts/stint_extension.py``.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from boxbox_ml import cache, features, neutralisation, track_status

warnings.filterwarnings("ignore")
pd.set_option("display.width", 220)
SEP = "=" * 88

#: Vueltas que se miran para estimar cómo viene la goma. Cortas a propósito: la
#: pregunta es si lo que el muro ve TEMPRANO predice cuánto va a estirar, y
#: ajustar la caída sobre la tanda entera usaría el futuro para predecir el
#: futuro.
EARLY = 8
DRY = ("SOFT", "MEDIUM", "HARD")

frame = pd.read_parquet(cache.cache_dir().parent / "laps_overtaking.parquet")
frame["circuit"] = frame["circuit"].map(lambda c: neutralisation.CIRCUIT_ALIASES.get(c, c))
frame = features.mark_representative(track_status.add_flags(frame))
frame["LapNumber"] = frame["LapNumber"].astype(int)

rows = []
for (year, rnd), race in frame.groupby(["year", "round"]):
    total = int(race["total_laps"].iloc[0])
    flags = race.groupby("LapNumber")[["is_neutralised", "red", "vsc"]].max()
    for (driver, stint), block in race.groupby(["Driver", "Stint"]):
        block = block.sort_values("LapNumber")
        compound = str(block["Compound"].iloc[0])
        if compound not in DRY:
            continue
        clean = block[block["is_representative"] & ~block["is_neutralised"] & ~block["red"]]
        length = int(block["LapNumber"].max() - block["LapNumber"].min() + 1)
        start = int(block["LapNumber"].min())
        # La última tanda no la decide el muro, la decide la bandera a cuadros.
        ended_racing = int(block["LapNumber"].max()) < total - 1
        early = clean[clean["TyreLife"] <= clean["TyreLife"].min() + EARLY]
        slope = np.nan
        if len(early) >= 5:
            slope = float(np.polyfit(early["TyreLife"], early["LapTime"], 1)[0])
        rows.append(
            {
                "year": year,
                "round": rnd,
                "circuit": race["circuit"].iloc[0],
                "driver": driver,
                "stint": int(stint),
                "compound": compound,
                "start": start,
                "length": length,
                "early_slope": slope,
                "ended_racing": ended_racing,
                "started_under_vsc": bool(flags["vsc"].get(start - 1, False))
                or bool(flags["vsc"].get(start, False)),
                "started_neutral": bool(flags["is_neutralised"].get(start - 1, False))
                or bool(flags["red"].get(start - 1, False)),
            }
        )

data = pd.DataFrame(rows)
print(f"{len(data)} tandas secas sobre {frame.groupby(['year', 'round']).ngroups} carreras")

print("\n" + SEP)
print("### 1. ¿ESTIRAN CUANDO LA GOMA AGUANTA?")
print()
print("La caída se estima sobre las PRIMERAS ocho vueltas de la tanda y se")
print("pregunta si predice cuánto va a durar. Ajustarla sobre la tanda entera")
print("sería usar el futuro para predecir el futuro.")
print()
work = data[data["ended_racing"] & data["early_slope"].notna() & (data["length"] >= 10)]
print(f"  {len(work)} tandas que terminaron en boxes y no con la bandera a cuadros")
print()
for compound in DRY:
    block = work[work["compound"] == compound]
    if len(block) < 40:
        continue
    r = block["early_slope"].corr(block["length"])
    q = pd.qcut(block["early_slope"], 3, labels=["aguanta", "medio", "se cae"])
    by = block.groupby(q)["length"].agg(tandas="size", vueltas="mean").round(1)
    print(f"  {compound}  n={len(block)}   correlación caída-duración: {r:+.3f}")
    print(
        "     "
        + "  ".join(
            f"{k}: {v['vueltas']:.1f} vueltas (n={int(v['tandas'])})" for k, v in by.iterrows()
        )
    )
    print()
print("  Si el muro corriera a lazo cerrado la correlación sería NEGATIVA: goma")
print("  que se cae rápido, tanda corta. Cero quiere decir que el plan manda.")

print("\n" + SEP)
print("### 2. QUE CALZAN CUANDO HAY VSC TEMPRANO")
print()
early_stop = data[(data["stint"] >= 2) & (data["start"] <= 20)]
print(f"  {len(early_stop)} tandas que empiezan en la vuelta 20 o antes,")
print("  o sea justo después de una parada temprana")
print()
for label, block in (
    ("bajo VSC", early_stop[early_stop["started_under_vsc"]]),
    ("en verde", early_stop[~early_stop["started_neutral"]]),
):
    if len(block) < 20:
        print(f"  {label:10s} n={len(block)} — muestra fina")
        continue
    share = block["compound"].value_counts(normalize=True)
    dur = block.groupby("compound")["length"].mean()
    print(f"  {label:10s} n={len(block)}")
    for c in DRY:
        if c in share:
            print(
                f"     {c:7s} {100 * share[c]:5.1f}%   dura {dur.get(c, float('nan')):.1f} vueltas"
            )
    tail = block[block["compound"] == "HARD"]
    if len(tail) >= 10:
        to_end = tail["ended_racing"].mean()
        share = 100 * (1 - to_end)
        print(f"     de los que calzan duro, {share:.0f}% llega a la bandera sin parar de nuevo")
    print()

print("\n" + SEP)
print("### 3. CONTROL: ¿ES LA DECISION O ES EL COMBUSTIBLE?")
print()
print("Una tanda temprana lleva más nafta, y quemarla hace que los tiempos")
print("MEJOREN: eso mete una pendiente negativa que no tiene nada que ver con")
print("la goma. Si el efecto fuera eso, se caería al mirar dentro del mismo")
print("número de tanda, y más todavía dentro del mismo compuesto.")
print()
print(f"  {'tanda':>6s} {'n':>5s} {'r':>8s}   aguanta -> se cae")
for stint in (1, 2, 3):
    block = work[work["stint"] == stint]
    if len(block) < 60:
        continue
    r = block["early_slope"].corr(block["length"])
    tercile = pd.qcut(block["early_slope"], 3, labels=["a", "m", "c"])
    mean = block.groupby(tercile)["length"].mean()
    print(f"  {stint:>6d} {len(block):5d} {r:+8.3f}   {mean['a']:.1f} -> {mean['c']:.1f} vueltas")
print()
print("  Mismo compuesto Y misma tanda, que es el control más duro:")
print(f"  {'':16s} {'n':>5s} {'r':>8s}   aguanta -> se cae")
for compound in ("MEDIUM", "HARD"):
    for stint in (1, 2):
        block = work[(work["compound"] == compound) & (work["stint"] == stint)]
        if len(block) < 60:
            continue
        r = block["early_slope"].corr(block["length"])
        tercile = pd.qcut(block["early_slope"], 3, labels=["a", "m", "c"])
        mean = block.groupby(tercile)["length"].mean()
        print(
            f"  {compound:8s} t{stint}     {len(block):5d} {r:+8.3f}"
            f"   {mean['a']:.1f} -> {mean['c']:.1f} vueltas"
        )
print()
print("  Sigue ahí. No es la nafta: es el muro mirando la goma y decidiendo.")
