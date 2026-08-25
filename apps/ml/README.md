# BoxBox ML

FastF1 ingest, feature engineering and tyre-degradation models for the pit-stop strategy
advisor.

## Layout

```text
apps/ml/
  src/boxbox_ml/
    cache.py          # FastF1 cache bootstrap — must run before any other FastF1 call
    ingest.py         # race sessions -> tidy lap-level parquet
    track_status.py   # decode the concatenated TrackStatus string (SC / VSC / yellow / red)
    features.py       # fuel correction, stint degradation, gaps, labels
  scripts/
    smoke.py          # end-to-end check of ingest -> features
  data/               # gitignored: FastF1 cache + generated parquet
```

## Quick start

```powershell
uv sync
uv run python scripts/smoke.py          # verify the pipeline on two known races
uv run boxbox-ingest --seasons 2022 2023 2024
```

The first ingest downloads from the F1 live-timing API and is slow; every run after that hits
the local cache in `data/ff1cache` and takes seconds. Override the cache location with
`BOXBOX_FF1_CACHE`.

Seasons before **2018** are rejected: lap-level compound and stint data does not exist before
then.

## The feature pipeline

`features.build()` runs five steps in order, and every domain assumption lives in that module:

1. **`mark_representative`** — flag laps whose time describes race pace. In-laps and out-laps
   carry the pit-lane transit, deleted laps were struck by the stewards, and laps failing
   FastF1's `IsAccurate` check have unsynced start/end times. All four are excluded from pace
   fitting but kept in the frame, because an in-lap is exactly where the label lives.
2. **`add_fuel_correction`** — subtract `0.035 s × laps_of_fuel_remaining` so a lap-8 time is
   comparable to a lap-45 one. The coefficient is currently a constant and should be fitted.
3. **`add_degradation`** — measure each lap against a settled reference lap (the 3rd of the
   stint) and fit a slope over the trailing 5 laps.
4. **`add_gaps`** — difference the session clock between cars on the same lap to get the gap
   ahead and behind.
5. **`add_labels`** — `boxed` is true on the lap the driver entered the pit lane.

## Two traps this code already handles

**`TyreLife` is not "laps into this stint."** Leclerc started the 2019 Italian GP on a set
already showing `TyreLife = 4` — scrubbed in qualifying. `add_stint_position()` derives
`stint_lap` by counting within the stint instead; `FreshTyre` answers the separate question of
whether the set was new.

**`TrackStatus` is a concatenated string.** A green lap is `"1"`; a lap where the VSC deployed
and then ended is `"167"`. `track_status.py` tests by containment, never equality.

## Class balance

`boxed` is true on roughly **3% of laps**. Evaluate on F1 and recall — a model that predicts
"stay out" every lap is 97% accurate and completely useless.

See [`docs/research/fastf1.md`](../../docs/research/fastf1.md) for the measured column
completeness and the rest of the findings.
