"""Qué hace un equipo cuando sale una neutralización, y cuándo apila sus dos autos.

El simulador puntúa el plan del auto focal contra rivales que corren un **plan
fijo sorteado**: nadie reacciona a nada. Este script mide el comportamiento que
va a reemplazar ese supuesto, y emite las constantes que la política de reacción
necesita. Es el insumo de ADR-012 a ADR-016.

## El supuesto que se cae primero

Una neutralización **no es una parada automática**. Bajo VSC para el 24,2% de los
autos, bajo safety car el 43,0%, y sólo bajo bandera roja —donde la carrera está
detenida y el cambio no cuesta posición— para casi todo el mundo, el 94,9%.

## Y el segundo: no son monedas independientes

El reparto por período es enorme. Bajo safety car la cuota de autos que paran va
de 0,05 en el percentil 10 a 0,85 en el 90: hay períodos de estampida y períodos
en los que no se mueve nadie. La varianza de la cuenta de paradas es **1,9 veces**
la que darían monedas independientes bajo safety car, y **2,8 veces** bajo VSC.

Eso no es un detalle estadístico. Un modelo de monedas independientes produciría
siempre más o menos la mitad del campo parando bajo safety car, y **nunca** el
escenario que de verdad le duele a un plan: que pare todo el mundo menos vos. Por
eso la política lleva un efecto de período compartido, y por eso este script lo
calibra en vez de elegirlo.

## Qué decide que un auto pare

La edad de la goma, y con fuerza. Bajo safety car va del 17,0% con goma de menos
de cinco vueltas al 93,8% con más de treinta. La obligación reglamentaria
—B6.3.8, que al auto le falte el segundo compuesto seco— **no** predice limpio:
bajo safety car los que no deben parar paran más, y bajo VSC al revés. Está
confundida con la edad de goma y no se usa.

## Dos errores propios que esto destapó

**Uno.** ``docs/research/pit-loss-under-neutralisation.md`` afirma que apilar los
dos autos infla el costo de una parada bajo safety car en unos doce segundos, y
que «la mayor parte de la penalidad aparente eran compañeros haciendo cola». Esa
cifra comparaba el grupo apilado contra el no apilado con **n=18 y sin parear**.
Pareado dentro del mismo par —que es la comparación limpia, porque el primero del
par no hace cola y el segundo sí— el recargo es de **+3,5 s**, no de doce. Cambia
la conclusión estratégica: apilar sale barato, y por eso lo hacen el 70% de las
veces que meten los dos autos.

**Dos.** Una primera versión de la pregunta «cuando el equipo mete un solo auto,
¿cuál mete?» dio 50%, o sea una moneda, y casi queda escrito que no hay regla. Lo
que pasaba es que en el 44% de esos casos los dos compañeros tenían la goma con
la misma edad, así que no había nada que elegir y el desempate era arbitrario.
Separando por cuánto difieren, la regla aparece nítida: con más de cinco vueltas
de diferencia entra el de goma más vieja el **91%** de las veces.

**Tres, y es del mismo día.** Una primera pasada reportó una sobredispersión de
9,4 veces bajo safety car. Comparaba la varianza de la cuenta de paradas **entre
períodos** contra la varianza binomial **dentro** de un período, promediada. Son
dos cosas distintas: la de arriba incluye que los períodos difieren en cuántos
autos hay y en qué goma llevan, y eso no es azar compartido, es composición. La
comparación que vale es contra una simulación con **las mismas composiciones** y
sin efecto de período, que es lo que hace :func:`calibrate_period_effect`. Da 1,9
y 2,8. La sobredispersión existe y el efecto de período hace falta, pero era la
mitad de grande de lo que dijo la primera cuenta, y bajo VSC es *mayor* que bajo
safety car, al revés de lo que decía.

Correr con ``uv run python scripts/rival_reaction.py``.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from boxbox_ml import cache, features, neutralisation, track_status

warnings.filterwarnings("ignore")
pd.set_option("display.width", 220)
SEP = "=" * 88

#: Bordes de los tramos de edad de goma, en vueltas. El último es abierto.
AGE_EDGES = [-1, 5, 10, 15, 20, 25, 30, 200]
AGE_LABELS = ["0-5", "6-10", "11-15", "16-20", "21-25", "26-30", "31+"]

#: Banderas que se miden, en el orden en que se reportan.
KINDS = ("red", "sc", "vsc")

#: Un período con menos autos que esto no dice nada sobre la dispersión: la
#: cuenta de paradas está acotada por arriba antes de que el azar importe.
MIN_CARS_FOR_SPREAD = 8

#: Sorteos por período al calibrar el efecto de período. Con menos, el propio
#: ruido de la calibración se confunde con lo que se quiere medir.
CALIBRATION_DRAWS = 4_000

#: Fuera de esta franja no hay una parada: hay una carrera detenida, un auto que
#: se quedó en boxes, o un cronometraje roto. Es el corte de `effective_pit_loss`.
LOSS_RANGE_S = (-10.0, 90.0)


def load() -> pd.DataFrame:
    """Todas las vueltas de todas las temporadas, con banderas y alias resueltos."""
    frame = pd.read_parquet(cache.cache_dir().parent / "laps_overtaking.parquet")
    frame["circuit"] = frame["circuit"].map(lambda c: neutralisation.CIRCUIT_ALIASES.get(c, c))
    frame = track_status.add_flags(frame)
    frame["LapNumber"] = frame["LapNumber"].astype(int)
    return frame


def periods_of(race: pd.DataFrame) -> list[dict]:
    """Tramos contiguos de vueltas con la misma bandera, a nivel carrera.

    La bandera es de la pista, no del auto, así que se toma el máximo sobre los
    autos de esa vuelta. Un tramo se corta cuando la vuelta deja de ser contigua.
    """
    state = race.groupby("LapNumber")[list(KINDS)].max()
    out: list[dict] = []
    for kind in KINDS:
        laps = sorted(state.index[state[kind].astype(bool)])
        if not laps:
            continue
        start = previous = laps[0]
        for lap in [*laps[1:], None]:
            if lap is not None and lap == previous + 1:
                previous = lap
                continue
            out.append({"kind": kind, "start": start, "end": previous})
            if lap is not None:
                start = previous = lap
    return out


def car_by_period(frame: pd.DataFrame) -> pd.DataFrame:
    """Una fila por (auto, período): en qué estado llegó y si paró.

    Un auto que ya había abandonado no cuenta: no decidió no parar, no estaba.
    Y una roja se traga el safety car que la acompaña, así que un tramo de SC o
    VSC que se solape con vueltas de roja se descarta para no contarlo dos veces.
    """
    rows = []
    for _keys, race in frame.groupby(["year", "round"]):
        red_laps = set(race.loc[race["red"].astype(bool), "LapNumber"].unique())
        last_lap = race.groupby("Driver")["LapNumber"].max()
        for period in periods_of(race):
            span = set(range(period["start"], period["end"] + 1))
            if period["kind"] != "red" and span & red_laps:
                continue
            window = race[race["LapNumber"].between(period["start"], period["end"])]
            for driver, block in race.groupby("Driver"):
                if last_lap[driver] < period["start"]:
                    continue
                here = window[window["Driver"] == driver]
                if here.empty:
                    continue
                first = here.iloc[0]
                pit_laps = here.loc[here["pit_in"].astype(bool), "LapNumber"]
                rows.append(
                    {
                        "year": _keys[0],
                        "round": _keys[1],
                        "kind": period["kind"],
                        "start": period["start"],
                        "end": period["end"],
                        "length": period["end"] - period["start"] + 1,
                        "driver": driver,
                        "team": block["Team"].iloc[0],
                        "tyre_age": float(first["TyreLife"])
                        if pd.notna(first["TyreLife"])
                        else np.nan,
                        "position": float(first["Position"]),
                        "pitted": bool(len(pit_laps)),
                        "pit_lap": int(pit_laps.iloc[0]) if len(pit_laps) else -1,
                    }
                )
    out = pd.DataFrame(rows)
    out["bin"] = pd.cut(out["tyre_age"], AGE_EDGES, labels=AGE_LABELS)
    return out


def calibrate_period_effect(data: pd.DataFrame, kind: str, table: pd.Series) -> tuple[float, dict]:
    """Cuánta dispersión compartida hace falta para reproducir lo observado.

    El modelo es el más chico que puede funcionar: a cada auto se le toma su
    probabilidad por edad de goma, se la lleva a escala logit, y se le suma un
    corrimiento ``u`` **compartido por todos los autos de ese período**. Un solo
    parámetro, la desviación de ``u``, y se lo elige por el valor que iguala la
    varianza simulada de la cuenta de paradas con la observada.

    Se calibra contra la varianza y no contra la media a propósito: la media ya
    la clava la tabla por edad de goma, y lo que la tabla no puede dar —y es todo
    el punto— es que algunos períodos muevan al campo entero y otros a nadie.
    """
    blocks = [
        block for _key, block in data[data["kind"] == kind].groupby(["year", "round", "start"])
    ]
    blocks = [b for b in blocks if len(b) >= MIN_CARS_FOR_SPREAD]
    observed = float(np.var([int(b["pitted"].sum()) for b in blocks], ddof=1))

    base = [
        np.clip(block["bin"].map(table).to_numpy(dtype=float), 1e-4, 1 - 1e-4) for block in blocks
    ]
    logits = [np.log(p / (1 - p)) for p in base]
    rng = np.random.default_rng(20260920)

    def simulated(sigma: float) -> float:
        counts = []
        for base_logit in logits:
            shift = rng.normal(0.0, sigma, (CALIBRATION_DRAWS, 1))
            p = 1 / (1 + np.exp(-(base_logit[None, :] + shift)))
            counts.append((rng.random(p.shape) < p).sum(axis=1))
        return float(np.var(np.concatenate(counts), ddof=1))

    independent = simulated(0.0)
    grid = np.arange(0.0, 4.01, 0.05)
    values = [simulated(float(s)) for s in grid]
    sigma = float(grid[int(np.argmin([abs(v - observed) for v in values]))])
    # El objetivo se estima con UNA realización por período, así que tiene su
    # propio error: para una varianza, cerca de `var * sqrt(2/(n-1))`. Sin esto
    # el sigma se lee como si estuviera clavado, y no lo está.
    error = observed * np.sqrt(2 / (len(blocks) - 1))
    return sigma, {
        "periodos": len(blocks),
        "observada": observed,
        "error": error,
        "independiente": independent,
        "sobredispersion": observed / independent if independent else float("nan"),
        "con_sigma": simulated(sigma),
    }


def stacking_surcharge(frame: pd.DataFrame) -> pd.DataFrame:
    """Lo que paga el SEGUNDO auto del par, pareado contra su propio compañero.

    El pareado no es un refinamiento, es la medición. Comparar el grupo apilado
    contra el no apilado mezcla dos cosas: que el segundo hace cola, y que los
    equipos apilan justo cuando parar sale barato. Restando dentro del mismo par
    —mismo equipo, misma vuelta, misma carrera— la segunda desaparece.
    """
    laps = features.add_labels(frame)
    racing = laps[~laps["pit_in"].astype(bool) & ~laps["pit_out"].astype(bool)]
    field = racing.groupby([*features.RACE_KEYS, "LapNumber"])["LapTime"].median()
    work = laps.join(field.rename("field"), on=[*features.RACE_KEYS, "LapNumber"])
    work["over"] = work["LapTime"] - work["field"]

    ins = work[work["pit_in"].astype(bool) & (work["LapNumber"] > 1)][
        [
            "year",
            "round",
            "Driver",
            "Team",
            "LapNumber",
            "over",
            "PitInTime",
            "red",
            "sc",
            "vsc",
            "vsc_ending",
        ]
    ].rename(columns={"over": "in_lap"})
    outs = work[work["pit_out"].astype(bool)][
        ["year", "round", "Driver", "LapNumber", "over"]
    ].rename(columns={"over": "out_lap"})
    outs["LapNumber"] -= 1
    stop = ins.merge(outs, on=["year", "round", "Driver", "LapNumber"], how="inner")
    stop["loss"] = stop["in_lap"] + stop["out_lap"]
    stop = stop[stop["loss"].between(*LOSS_RANGE_S)]
    stop["estado"] = np.where(
        stop["red"],
        "RED",
        np.where(stop["sc"], "SC", np.where(stop["vsc"] | stop["vsc_ending"], "VSC", "GREEN")),
    )
    key = ["year", "round", "LapNumber", "Team"]
    stop["del_equipo"] = stop.groupby(key)["Driver"].transform("size")
    stop["orden"] = stop.groupby(key)["PitInTime"].rank(method="first")
    stop["rol"] = np.where(stop["orden"] == 1, "primero", "segundo")
    pairs = (
        stop[stop["del_equipo"] == 2]
        .pivot_table(index=[*key, "estado"], columns="rol", values="loss")
        .dropna()
    )
    pairs["recargo"] = pairs["segundo"] - pairs["primero"]
    return pairs.reset_index()


frame = load()
data = car_by_period(frame)

print(SEP)
print("### 1. UNA NEUTRALIZACION NO ES UNA PARADA AUTOMATICA")
print()
quota = data.groupby("kind").agg(casos=("pitted", "size"), paran=("pitted", "mean"))
for kind in KINDS:
    row = quota.loc[kind]
    share, n = 100 * row["paran"], int(row["casos"])
    print(f"  {kind.upper():4s} para el {share:5.1f}% de los autos en carrera   (n={n})")
print()
print("  La roja es el caso trivial: la carrera está detenida y el cambio no")
print("  cuesta posición. Los otros dos son decisiones, y la mayoría decide que no.")

print("\n" + SEP)
print("### 2. NO ES UN PROMEDIO: EL REPARTO POR PERIODO")
print()
per = data.groupby(["year", "round", "kind", "start"]).agg(
    autos=("pitted", "size"), paran=("pitted", "sum")
)
per["cuota"] = per["paran"] / per["autos"]
for kind in ("sc", "vsc"):
    share = per.xs(kind, level="kind")["cuota"]
    cuts = "  ".join(
        f"p{int(q * 100)}={share.quantile(q):.2f}" for q in (0.1, 0.25, 0.5, 0.75, 0.9)
    )
    print(f"  {kind.upper():4s} {len(share):3d} períodos   {cuts}")
    print(
        f"        no para nadie en el {100 * (share == 0).mean():.0f}% de los períodos,"
        f" y para más de la mitad en el {100 * (share > 0.5).mean():.0f}%"
    )

print("\n" + SEP)
print("### 3. LO QUE DECIDE: LA EDAD DE LA GOMA")
print()
tables: dict[str, pd.Series] = {}
rows = []
for kind in KINDS:
    block = data[data["kind"] == kind]
    table = block.groupby("bin")["pitted"].mean()
    counts = block.groupby("bin")["pitted"].size()
    tables[kind] = table
    rows.append(pd.Series({f"{label}": table[label] for label in AGE_LABELS}, name=kind.upper()))
    rows.append(pd.Series({f"{label}": counts[label] for label in AGE_LABELS}, name=f"  n {kind}"))
print(pd.DataFrame(rows).round(3).to_string())
print()
print("  Bajo safety car va del 17% al 94%. Es el predictor y alcanza con él: la")
print("  obligación de B6.3.8 no predice limpio —bajo SC los que NO deben parar")
print("  paran más— porque está confundida con la edad de goma. No se usa.")

print("\n" + SEP)
print("### 4. CONTRA EL VERDE, A IGUAL EDAD DE GOMA")
print()
green = frame[~frame["is_neutralised"] & ~frame["red"] & (frame["LapNumber"] > 1)].copy()
green["bin"] = pd.cut(green["TyreLife"], AGE_EDGES, labels=AGE_LABELS)
hazard = green.groupby("bin")["pit_in"].mean()
rows = []
for label in AGE_LABELS:
    per_lap = float(hazard[label])
    over_three = 1 - (1 - per_lap) ** 3
    rows.append(
        {
            "edad": label,
            "verde, por vuelta": round(per_lap, 4),
            "verde, en 3 vueltas": round(over_three, 3),
            "VSC": round(float(tables["vsc"][label]), 3),
            "SC": round(float(tables["sc"][label]), 3),
            "salto SC": f"{tables['sc'][label] / over_three:.1f}x",
        }
    )
print(pd.DataFrame(rows).to_string(index=False))
print()
print("  Con goma de 16 a 20 vueltas, tres vueltas de verde dan 12% de chance de")
print("  parar y un safety car da 73%. Ese salto es la ventana barata, medida en")
print("  el comportamiento del pit wall y no en segundos.")

print("\n" + SEP)
print("### 5. EL EFECTO DE PERIODO, CALIBRADO")
print()
sigmas: dict[str, float] = {}
for kind in ("sc", "vsc"):
    sigma, report = calibrate_period_effect(data, kind, tables[kind])
    sigmas[kind] = sigma
    print(f"  {kind.upper():4s} {report['periodos']} períodos de {MIN_CARS_FOR_SPREAD} autos o más")
    print(
        f"        varianza observada de la cuenta de paradas   {report['observada']:7.2f}"
        f"  ± {report['error']:.1f}"
    )
    print(f"        la misma composición, sin efecto de período  {report['independiente']:7.2f}")
    print(f"        sobredispersión                              {report['sobredispersion']:7.1f}x")
    print(f"        sigma que la iguala                          {sigma:7.2f}")
    print(f"        varianza simulada con ese sigma              {report['con_sigma']:7.2f}")
print()
print("  La referencia NO es la varianza binomial dentro de un período: eso")
print("  compara contra otra cosa y da una sobredispersión inflada, porque los")
print("  períodos también difieren en cuántos autos hay y en qué goma llevan, y")
print("  eso es composición y no azar compartido. La referencia es una simulación")
print("  con LAS MISMAS composiciones y sin efecto de período.")
print()
print("  El corrimiento es compartido por todos los autos del período, así que")
print("  produce lo que las monedas no pueden: la estampida, y el período en que")
print("  no se mueve nadie. Sin esto el modelo nunca sortearía «paró todo el")
print("  mundo menos yo», que es el escenario que le duele a un plan.")

print("\n" + SEP)
print("### 6. EL EQUIPO: NINGUNO, UNO O LOS DOS")
print()
team = (
    data[data["kind"] != "red"]
    .groupby(["year", "round", "kind", "start", "team"])
    .agg(
        autos=("pitted", "size"),
        paran=("pitted", "sum"),
        primera=("pit_lap", lambda s: s[s > 0].min() if (s > 0).any() else -1),
        ultima=("pit_lap", lambda s: s[s > 0].max() if (s > 0).any() else -1),
    )
)
splits: dict[str, tuple[float, float, float]] = {}
for kind in ("sc", "vsc"):
    both_out = team.xs(kind, level="kind")
    both_out = both_out[both_out["autos"] == 2]
    share = tuple(float((both_out["paran"] == n).mean()) for n in (0, 1, 2))
    splits[kind] = share
    print(
        f"  {kind.upper():4s} n={len(both_out)}   ninguno {100 * share[0]:5.1f}%"
        f"   UNO SOLO {100 * share[1]:5.1f}%   los dos {100 * share[2]:5.1f}%"
    )
both = team[(team["autos"] == 2) & (team["paran"] == 2)]
same_lap = float((both["primera"] == both["ultima"]).mean())
print()
print(f"  Cuando meten los dos, el {100 * same_lap:.0f}% es en la MISMA vuelta (n={len(both)}).")
print("  Ahí no paran a la vez: el segundo hace cola, y lo que paga está en §8.")

print("\n" + SEP)
print("### 7. CUANDO METEN UNO SOLO, ¿CUAL?")
print()
alone = team[(team["autos"] == 2) & (team["paran"] == 1)].index
pair = data[data["kind"] != "red"].set_index(["year", "round", "kind", "start", "team"])
pair = pair.loc[pair.index.intersection(alone)].reset_index()
group = ["year", "round", "kind", "start", "team"]
pair["mas_vieja"] = pair.groupby(group)["tyre_age"].rank(ascending=False, method="first")
pair["brecha"] = pair.groupby(group)["tyre_age"].transform(lambda s: abs(s.iloc[0] - s.iloc[1]))
chosen = pair[pair["pitted"]]
print(f"  {len(chosen)} casos. Entra el de goma MAS VIEJA, según cuánto difieran:")
rule = []
for low, high, label in ((0, 1, "0-1 vuelta"), (2, 5, "2-5 vueltas"), (6, 200, "más de 5")):
    block = chosen[chosen["brecha"].between(low, high)]
    if len(block) < 20:
        continue
    share = float((block["mas_vieja"] == 1).mean())
    rule.append((label, share, len(block)))
    print(f"    {label:12s} {100 * share:3.0f}%   (n={len(block)})")
print()
print("  Una primera versión midió esto de una sola vez y dio 50%, y casi queda")
print("  escrito que no hay regla. Lo que pasaba es que en el 44% de los casos")
print("  los dos tenían la goma con la misma edad: no había nada que elegir y el")
print("  desempate era arbitrario. Separado por la brecha, la regla es nítida.")

print("\n" + SEP)
print("### 8. LO QUE PAGA EL SEGUNDO DEL PAR, PAREADO")
print()
pairs = stacking_surcharge(frame)
surcharge: dict[str, float] = {}
for state in ("GREEN", "SC", "VSC"):
    block = pairs[pairs["estado"] == state]
    if len(block) < 15:
        continue
    surcharge[state] = float(block["recargo"].median())
    print(
        f"  {state:6s} n={len(block):3d}   mediana {block['recargo'].median():+5.1f} s"
        f"   media {block['recargo'].mean():+5.1f} s"
        f"   el segundo pierde más en el {100 * (block['recargo'] > 0).mean():.0f}% de los pares"
    )
print()
print("  CORRECCION. `docs/research/pit-loss-under-neutralisation.md` dice que")
print("  apilar infla el número de safety car en unos doce segundos, medido con")
print("  n=18 y SIN parear. Pareado dentro del mismo par el recargo es de tres y")
print("  medio. Cambia la conclusión: apilar sale barato, y por eso lo hacen el")
print(f"  {100 * same_lap:.0f}% de las veces que meten los dos autos.")

print("\n" + SEP)
print("### 9. PARA PEGAR EN boxbox_ml/reaction.py")
print()
print(f"AGE_EDGES = {AGE_EDGES}")
print(f"AGE_LABELS = {AGE_LABELS}")
print()
print("#: Probabilidad de parar durante el período, por edad de goma al empezarlo.")
print("REACT: dict[str, tuple[float, ...]] = {")
for kind in KINDS:
    values = ", ".join(f"{tables[kind][label]:.3f}" for label in AGE_LABELS)
    print(f'    "{kind}": ({values}),  # n={int(quota.loc[kind, "casos"])}')
print("}")
print()
print("#: Desvío del corrimiento logit compartido por período. Calibrado contra la")
print("#: sobredispersión observada de la cuenta de paradas; la roja no lo lleva")
print("#: porque para casi todo el mundo y no queda dispersión que explicar.")
print("PERIOD_SIGMA: dict[str, float] = {")
for kind in ("sc", "vsc"):
    print(f'    "{kind}": {sigmas[kind]:.2f},')
print("}")
print()
print("#: Reparto de cuántos de sus dos autos mete un equipo: (ninguno, uno, los dos).")
print("TEAM_SPLIT: dict[str, tuple[float, float, float]] = {")
for kind in ("sc", "vsc"):
    print(f'    "{kind}": ({splits[kind][0]:.3f}, {splits[kind][1]:.3f}, {splits[kind][2]:.3f}),')
print("}")
print()
print("#: Cuando mete los dos, probabilidad de que sea en la misma vuelta.")
print(f"SAME_LAP = {same_lap:.2f}")
print()
print("#: Cuando mete uno solo, probabilidad de que entre el de goma más vieja,")
print("#: según cuántas vueltas de diferencia haya entre los compañeros.")
print("OLDER_FIRST: tuple[tuple[int, float], ...] = (")
for label, share, n in rule:
    bound = 1 if label.startswith("0-1") else (5 if label.startswith("2-5") else 999)
    print(f"    ({bound}, {share:.2f}),  # {label}, n={n}")
print(")")
print()
print("#: Lo que paga el SEGUNDO auto del par por hacer cola, en segundos.")
print("STACK_SURCHARGE_S: dict[str, float] = {")
for state, value in surcharge.items():
    print(f'    "{state}": {value:.1f},')
print("}")


def cover_pairs(frame: pd.DataFrame) -> pd.DataFrame:
    """Para cada parada en verde, cómo reaccionó cada otro auto de la carrera.

    El hueco se mide con el reloj de la vuelta anterior a la parada, y es con
    signo: **negativo quiere decir que el rival va adelante**, que es el que un
    undercut amenaza.
    """
    rows = []
    for _keys, race in frame.groupby(["year", "round"]):
        state = race.groupby("LapNumber")[["is_neutralised", "red"]].max()
        clock = race.pivot_table(index="LapNumber", columns="Driver", values="Time")
        # El `fillna(False)` no es cosmético: un auto sin registro en esa vuelta
        # deja un NaN, y `bool(nan)` es True, así que sin esto todo auto ausente
        # contaba como que paró. Inflaba los pares de 48.860 a 52.131.
        boxed = (
            race.pivot_table(index="LapNumber", columns="Driver", values="pit_in", aggfunc="max")
            .fillna(False)
            .astype(bool)
        )
        place = race.pivot_table(index="LapNumber", columns="Driver", values="Position")
        drivers = list(clock.columns)
        for lap in sorted(clock.index):
            if lap < 3 or lap + 1 not in clock.index or lap - 1 not in clock.index:
                continue
            if bool(state.loc[lap, "is_neutralised"]) or bool(state.loc[lap, "red"]):
                continue
            for stopper in drivers:
                if not bool(boxed.loc[lap, stopper]):
                    continue
                theirs = clock.loc[lap - 1, stopper]
                if not np.isfinite(theirs):
                    continue
                for other in drivers:
                    mine = clock.loc[lap - 1, other]
                    if other == stopper or not np.isfinite(mine):
                        continue
                    rows.append(
                        {
                            "gap": float(mine - theirs),
                            "covers": bool(boxed.loc[lap, other] or boxed.loc[lap + 1, other]),
                            "place": float(place.loc[lap, other])
                            if pd.notna(place.loc[lap, other])
                            else np.nan,
                        }
                    )
    return pd.DataFrame(rows)


print("")
print(SEP)
print("### 10. CUANDO UN AUTO PARA EN VERDE, ¿QUIEN LO CUBRE?")
print()
pairs = cover_pairs(frame)
races = frame.groupby(["year", "round"]).ngroups
print(f"  {len(pairs)} pares (auto que para, otro auto) sobre {races} carreras")
print()
print("  El control es el ESPEJO: mismo hueco, un lado y el otro. El de adelante")
print("  está amenazado por el undercut y el de atrás no, así que la diferencia")
print("  entre las dos mitades a igual distancia es el efecto, con la cercanía a")
print("  la acción ya descontada.")
print()
print(
    f"  {'hueco':>10s} {'adelante':>9s} {'atrás':>8s} {'efecto':>8s} {'±95%':>7s}"
    f" {'puesto adel':>12s} {'puesto atrás':>13s}"
)
COVER_BANDS = [(0, 2), (2, 5), (5, 10), (10, 20), (20, 60)]
effects = []
for low, high in COVER_BANDS:
    ahead = pairs[(pairs["gap"] <= -low) & (pairs["gap"] > -high)]
    behind = pairs[(pairs["gap"] >= low) & (pairs["gap"] < high)]
    effect = ahead["covers"].mean() - behind["covers"].mean()
    error = 1.96 * np.sqrt(
        ahead["covers"].var() / len(ahead) + behind["covers"].var() / len(behind)
    )
    effects.append((high, effect, error, ahead["place"].mean(), behind["place"].mean()))
    print(
        f"  {low:4d}-{high:<5d} {ahead['covers'].mean():9.3f} {behind['covers'].mean():8.3f}"
        f" {effect:+8.3f} {error:7.3f} {ahead['place'].mean():12.1f} {behind['place'].mean():13.1f}"
    )
print()
_, _, _, near_a, near_b = effects[0]
_, last_effect, _, far_a, far_b = effects[-1]
print("  LEER CON CUIDADO LAS DOS ULTIMAS COLUMNAS. El espejo sólo controla algo")
print("  mientras las dos mitades sean autos comparables, y dejan de serlo rápido:")
print(
    f"  a 0-2 s van {near_a:.1f} y {near_b:.1f} de puesto medio, pero en la última"
    f" fila van {far_a:.1f} y {far_b:.1f}."
)
print("  A esa distancia la comparación ya no mide cobertura, mide frente de")
print("  parrilla contra fondo — y por eso el efecto REAPARECE en la última fila")
print(f"  después de haberse apagado. Ese {last_effect:+.2f} es un artefacto y no se usa.")
print()
print("  Queda un solo número limpio, el de 0-2 s, y uno aceptable con reparo, el")
print("  de 2-5 s. Más allá el diseño no puede separar el efecto de la posición,")
print("  y se declara cero en vez de pegar un número que se sabe contaminado.")
print()
print("  COVER_EXTRA: tuple[tuple[float, float], ...] = (")
for high, effect, _error, _a, _b in effects[:2]:
    print(f"      ({float(high)}, {max(effect, 0.0):.3f}),")
print("  )")
