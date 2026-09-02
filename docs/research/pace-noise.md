# Lap-to-lap pace noise and wear-rate spread

Measured 2026-09-01 over **4,407 stints** (2022–2026, ≥8 representative green laps each).
Reproduce with `uv run python scripts/pace_noise.py --offline --reuse`.

## Verdict

Two numbers, and the second is the interesting one.

**Per-lap noise: sd 0.457 s.** What is left of a lap time after the stint's own wear line and the
fuel correction are removed — traffic, driver, wind, a wide entry. Remarkably stable: 0.440–0.487
across five seasons, 0.426–0.471 across the three dry compounds.

**Wear-rate spread: sd 0.069–0.178 s/lap** depending on compound, against a **median rate of about
0.045 s/lap**. The spread is two to four times the signal. How a given stint will wear is, in large
part, not predictable from the compound — which is the strongest single argument in this project's
data for a system that outputs distributions instead of a number.

## Method

For each stint with at least 8 representative green laps, fit a straight line of fuel-corrected lap
time against stint lap. The slope is that stint's wear rate; the standard deviation of the residuals
is its lap-to-lap noise.

Excluded: in-laps, out-laps, deleted laps, laps failing FastF1's `IsAccurate` check, and anything
under a neutralisation or a yellow. A safety-car lap is 40 seconds slow and would swamp the residual
entirely. The extreme 0.5% of residual sds at each end is trimmed — those sit on restarts or damaged
cars.

95,429 of 114,414 laps survive as representative green laps.

## Lap-to-lap noise

| | Residual sd (s) |
|---|---|
| 10th percentile | 0.229 |
| 25th | 0.316 |
| **median** | **0.457** |
| 75th | 0.683 |
| 90th | 1.060 |

By compound:

| Compound | Stints | Median sd |
|---|---|---|
| MEDIUM | 1,762 | 0.426 |
| SOFT | 651 | 0.438 |
| HARD | 1,743 | 0.471 |
| INTERMEDIATE | 201 | 1.095 |
| WET | 17 | 1.206 |

The dry compounds are within 0.045 s of each other, so the simulator uses one number for all three.
Wet running is two and a half times noisier, which is its own finding but not one this simulator
uses yet — it runs a dry race.

By season — 0.476, 0.440, 0.467, 0.440, 0.487 for 2022 through 2026. Flat enough to justify a single
constant.

## Wear-rate spread

All seasons, dry compounds:

| Compound | Stints | Median | sd | p10 | p90 |
|---|---|---|---|---|---|
| HARD | 1,743 | 0.0329 | 0.0987 | −0.0416 | 0.1023 |
| MEDIUM | 1,762 | 0.0423 | 0.1326 | −0.0689 | 0.1333 |
| SOFT | 651 | 0.0630 | 0.2964 | −0.0353 | 0.2022 |

2026 only, which is the season the simulator runs:

| Compound | Stints | Median | sd | p10 | p90 |
|---|---|---|---|---|---|
| HARD | 243 | 0.0466 | 0.0686 | −0.0221 | 0.1208 |
| MEDIUM | 219 | 0.0450 | 0.1124 | −0.0677 | 0.1381 |
| SOFT | 91 | 0.0450 | 0.1776 | −0.1295 | 0.2207 |

Two things worth stating plainly:

**The three 2026 medians are the same to three decimals** — 0.0466, 0.0450, 0.0450. Consistent with
the compound inversion recorded in [`2026-regulations.md`](2026-regulations.md): whatever separated
the compounds in the previous era has largely collapsed.

**p10 is negative for every compound.** A large minority of stints get *faster* over their length.
Some of that is genuine — track evolution, a car coming good as the fuel burns off — and some of it
is `FUEL_EFFECT_S_PER_LAP = 0.035` under-correcting, which is already flagged as the weakest
assumption in the feature set. The wear-rate spread is therefore an upper bound: part of it is fuel
model error, not tyre behaviour.

## What the simulator does with it

`apps/web/src/tyres.ts`:

- **once per stint**, each car draws a wear-rate deviation from `N(0, sd)` for its compound. This
  accumulates, and it is what turns one projection into a distribution — a car can turn out to be
  kind to its tyres, or not, and the race finds out;
- **every lap**, each car draws a pace deviation from `N(0, 0.457)`. This does not accumulate, and it
  is what stops two cars with identical tyre state running identically forever.

Both are drawn by hashing `(car, lap, seed)` rather than from a running generator, so scrubbing back
to an earlier lap replays the same race instead of rewriting it. Changing the seed is, in miniature,
a Monte Carlo draw.

### Lap time, and a calibration error it exposed

Converting "seconds lost per lap" into a fraction of pace needs the lap time. Measured for the race
the simulator runs — 2026 Zandvoort, 1,119 representative green laps:

| Season | Median green lap |
|---|---|
| 2022 | 76.929 s |
| 2023 | 76.910 s |
| 2024 | 76.310 s |
| 2025 | 76.080 s |
| **2026** | **77.861 s** |

`useField.ts` had been using a hand-set constant equivalent to a 45-second lap, so every pace
difference was acting about **1.7× too strong** and the field reordered faster than it should. It now
divides by the measured lap time.

## Known gaps

- **No pit stops.** Nobody changes tyres, so degradation only ever grows: by lap 72 a car that
  started the simulation on lap 30 is on a notional 51-lap-old set with over 7 seconds of
  degradation. In a real race the stint is cut long before that. Simulating stops needs pit loss and
  compound choice as well, or a stop becomes a free lunch.
- **Pit windows are static.** They come from the frozen lap-30 data and do not move as the tyre state
  evolves, even though `insights.pit_window` would recompute them.
- **The wear-rate draw is per car, not per stint**, because there is only ever one stint. That
  becomes wrong the moment stops exist.
- **One noise scale for all dry compounds and all circuits.** The measurement supports the first
  (0.426–0.471) but says nothing about the second — per-circuit noise was not measured.
