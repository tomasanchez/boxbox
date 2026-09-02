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

## The distribution is not normal, and the difference matters

A follow-up measurement — `scripts/zandvoort_distributions.py` — fitted the same stint slopes at
Zandvoort alone (80 HARD, 79 MEDIUM, 98 SOFT stints) and asked what shape they take. They are not
remotely normal:

| Compound | n | Median | sd | Skew | Excess kurtosis |
|---|---|---|---|---|---|
| HARD | 80 | 0.034 | 0.085 | -6.29 | **48.6** |
| MEDIUM | 79 | 0.042 | 0.073 | 4.69 | **32.8** |
| SOFT | 98 | 0.040 | 0.664 | -4.63 | **20.2** |

A normal has excess kurtosis 0. A handful of catastrophic stints stretch the tails and make the
standard deviation lie: Zandvoort SOFT has sd 0.664 s/lap, but its 5th-to-95th percentile range is
only -0.184 to 0.138. Drawing from `N(0, 0.664)` would produce impossible stints several times a
race.

So the simulator stopped assuming a shape. It carries nine cut points of the measured distribution
and samples by interpolating between them, clamping rather than extrapolating past the 5th and 95th
percentiles - beyond those there is no data, and a straight line there invents exactly in the tail.

| Compound | p5 | p25 | p50 | p75 | p95 |
|---|---|---|---|---|---|
| SOFT | -0.184 | 0.011 | 0.040 | 0.077 | 0.138 |
| MEDIUM | -0.027 | 0.021 | 0.042 | 0.068 | 0.107 |
| HARD | -0.035 | 0.013 | 0.034 | 0.050 | 0.097 |

## Pit stops

The simulator now stops. Each car with a projectable window enters on a lap drawn **uniformly**
inside it - with only a range to go on, uniform is the maximum-entropy choice, and any other shape
would smuggle in a belief about when teams stop that no measurement supports.

Pit loss is drawn from a triangular over the measured Zandvoort green-flag quartiles: **median
23.5 s, p25 20.6, p75 31.3**, over 164 stops. That agrees with the global 22.2 s in
[`pit-loss-under-neutralisation.md`](pit-loss-under-neutralisation.md).

The cost is applied as time spent stationary, not as distance subtracted. A car in the pit lane does
not move backwards - it stops advancing - and the field order is derived from distance travelled, so
subtracting would have moved cars backwards along the track.

Compound choice follows B6.3.8: the mandatory dry compound the car does not have on, choosing
between medium and hard by whether the remaining distance fits a set's measured life here - **HARD
28 laps, MEDIUM 22, SOFT 15** (medians over 90, 94 and 155 stints).

### A measurement error worth recording

The first pit-loss figure from this script was wrong: it grouped the in-lap and the out-lap by
stint, which splits them, because the in-lap closes stint N and the out-lap opens stint N+1. It
reported a lower quartile of 5.3 s, which is not a pit stop - it is half of one. They are paired by
lap number instead.

## What the simulator does with it

`apps/web/src/tyres.ts`:

- **once per stint**, each car draws a wear rate by inverting the measured Zandvoort distribution for
  its compound. For a stint already in progress the car keeps its own measured rate and takes the
  draw as a deviation from that distribution's median, so the measurement is not thrown away; for a
  set fitted at a stop there is nothing measured yet, so the rate is drawn outright. This
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

- **Half the field never stops.** Only 12 of the 20 running cars have a projectable pit window; the
  other 8 have flat or improving measured degradation, so `insights.pit_window` returns `None` and
  there is no lap to stop them on. Those cars run the whole distance on one set, which is illegal
  under B6.3.8 and visibly wrong - they climb the order because everyone else pits. Giving them an
  invented window would hide the real problem, which is the fuel coefficient under-correcting.
- **One stop per car.** No window is projected after the first stop, so the window column and the
  strategy-duel card go blank for a car that has already stopped.
- **The neutralised discount is not applied to the stop itself.** Stopping under a safety car costs
  the same seconds here as under green. What it actually saves is *positions*, not seconds, and that
  is already measured - but wiring it in needs the track status at the stop lap, which is a manual
  control in this simulator rather than part of the race.
- **One noise scale for all dry compounds and all circuits.** The measurement supports the first
  (0.426–0.471) but says nothing about the second — per-circuit noise was not measured.
