# FastF1 — research notes

Everything below was **verified by running it** against real sessions on 2026-08-25, not
read off the docs. Probe script and raw output: `apps/ml/scripts/smoke.py`.

## Verdict

FastF1 is a viable primary data source for this project. The four columns the pit-strategy
model depends on — `Stint`, `Compound`, `TyreLife`, `FreshTyre` — came back **100% populated**
on every race probed, across three seasons. The idea is not blocked on data.

## Environment

| Item | Value |
|---|---|
| Version tested | **3.8.3** |
| Python tested | 3.13.5 (works) |
| Declared support | Python ≥ 3.10; classifiers list 3.10–3.14 |
| License | MIT |
| Install | `uv add fastf1` — pulls pandas, numpy, scipy, matplotlib, requests-cache, signalrcore |

## Coverage

Lap timing with tyre data starts at the **2018** season. Earlier years resolve through the
Ergast-compatible feed and carry results, but not the per-lap compound/stint columns this
project needs. `apps/ml` refuses seasons before 2018 at the CLI.

Rough dataset size: ~1,000 laps per race × ~22 races × 7 seasons ≈ **150,000 labelled laps**.

## Caching is not optional

`fastf1.Cache.enable_cache(path)` must be called **before any other FastF1 call**. Without
it every run re-downloads from the live-timing API. `boxbox_ml.cache.enable()` handles this;
the cache lands in `apps/ml/data/ff1cache` and is gitignored.

## Columns confirmed present on `Session.laps`

```
Time, Driver, DriverNumber, LapTime, LapNumber, Stint, PitOutTime, PitInTime,
Sector1Time, Sector2Time, Sector3Time, Sector1SessionTime, Sector2SessionTime,
Sector3SessionTime, SpeedI1, SpeedI2, SpeedFL, SpeedST, IsPersonalBest, Compound,
TyreLife, FreshTyre, Team, LapStartTime, LapStartDate, TrackStatus, Position,
Deleted, DeletedReason, FastF1Generated, IsAccurate
```

### Measured completeness

| Column | 2019 Monza | 2023 Monza | 2024 Monza |
|---|---|---|---|
| `Stint` | 100.0% | 100.0% | 100.0% |
| `Compound` | 100.0% | 100.0% | 100.0% |
| `TyreLife` | 100.0% | 100.0% | 100.0% |
| `FreshTyre` | 100.0% | 100.0% | 100.0% |
| `TrackStatus` | 100.0% | 100.0% | 100.0% |
| `IsAccurate` | 100.0% | 100.0% | 100.0% |
| `LapTime` | 99.9% | 99.1% | 100.0% |
| `Position` | 99.9% | 99.1% | 100.0% |
| `PitInTime` | 3.0% | 2.7% | 3.1% |
| `PitOutTime` | 2.9% | 2.6% | 3.0% |

Lap counts: 991 / 957 / 1008 rows respectively.

## Four findings that change the modelling

### 1. `PitInTime` sparsity *is* the label — and the class balance problem

`PitInTime` is populated on exactly the laps where the driver entered the pit lane: **~3% of
all laps**. That is the supervised target, and it confirms the imbalance flagged in the
conceptualización. Evaluate on F1 and recall, never on accuracy — a model that predicts
"SEGUIR" every lap scores 97% accurate and is worthless.

### 2. `TyreLife` ≠ laps into the stint

Leclerc started the 2019 Italian GP on a set already showing `TyreLife = 4` — tyres scrubbed
in qualifying. Using `TyreLife` as "laps into this stint" silently corrupts the degradation
curve for every driver who starts on a used set.

`FreshTyre` records whether the set was new. `features.add_stint_position()` derives
`stint_lap` by counting within the stint instead. The two are different questions and the
model wants both.

### 3. `TrackStatus` is a concatenated string, not a code

A lap run entirely green is `"1"`. A lap where the VSC was deployed and then ended is `"167"`.
Test with substring containment, never equality. Codes:

| Code | Meaning |
|---|---|
| `1` | All clear |
| `2` | Yellow |
| `4` | Safety Car deployed |
| `5` | Red flag |
| `6` | VSC deployed |
| `7` | VSC ending |

2019 Monza showed codes `1, 2, 6, 7` present; 2023 and 2024 Monza were `1` only — **most races
are fully green**. Sampling races for the SC/VSC part of the model needs deliberate selection,
not a random draw.

### 4. Weather and race control are usable as-is

`session.weather_data` → `Time, AirTemp, Humidity, Pressure, Rainfall, TrackTemp,
WindDirection, WindSpeed` (156 samples at 2023 Monza; `TrackTemp` 39.3–44.4 °C). Align it
per-lap with `laps.get_weather_data()`, which returns rows matching the laps index.

`session.race_control_messages` → `Time, Category, Message, Status, Flag, Scope, Sector,
RacingNumber, Lap` (43 rows at 2023 Monza; categories `Other`, `Flag`, `Drs`). Requires
`session.load(messages=True)`, and `Deleted` / `DeletedReason` on laps depend on it too.

## What FastF1 does *not* give

**Pit stop duration.** There is no stationary-time column. `PitInTime`/`PitOutTime` bracket
the whole pit-lane transit, not the stop itself. If the model needs stationary time, it has
to come from the Ergast-compatible API.

Ergast is deprecated; **jolpica-f1** is the community successor, Ergast-compatible at
`http://api.jolpi.ca/ergast/f1/`. Volunteer-run on roughly $45/month of hosting — treat it as
a secondary source and cache aggressively. Its pit-stop endpoint has **not** been verified
yet; do that before depending on stationary time.

## Open items

- [ ] Verify the jolpica pit-stop endpoint shape and rate limits.
- [ ] Pick a race set that actually contains Safety Car periods — Monza is a poor sample.
- [ ] Fit the fuel-effect coefficient from data instead of the 0.035 s/lap constant currently
      hardcoded in `features.FUEL_EFFECT_S_PER_LAP`.
- [ ] Check whether 2018 (the first supported season) has the same column completeness as 2019+.

## Sources

- [FastF1 documentation](https://docs.fastf1.dev/)
- [FastF1 core / Laps reference](https://docs.fastf1.dev/core.html)
- [fastf1 on PyPI](https://pypi.org/project/fastf1/)
- [jolpica-f1](https://github.com/jolpica/jolpica-f1)
