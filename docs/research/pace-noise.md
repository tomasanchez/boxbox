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

Everything about a stop is drawn, not decided: **how many, when, with what, and what it costs.** The
first version of this had one stop per car, placed in its window, on a compound picked by a rule —
three decisions dressed up as certainties.

Measured with `scripts/stop_plans.py`, over cars that saw the flag, with free stops (tyre changes
under a red flag) and wet races excluded.

### How many

Stops still to come from lap 30 of 72, which is where the simulation starts:

| Stops left | Zandvoort | All circuits |
|---|---|---|
| 0 | 0.151 | 0.249 |
| 1 | 0.493 | 0.586 |
| 2 | 0.192 | 0.122 |
| 3 | 0.164 | 0.026 |

n = 73 cars at Zandvoort over 4 dry races; 1,686 across all circuits. Zandvoort stops noticeably
more, and there is a mechanism rather than only noise: **36% of its strategic stops happen under a
neutralisation**, against 23% globally. Where a stop is cheap, teams take it. Still, 73 cars over
four races is thin, and the all-circuit column is the conservative reading.

The simulator uses the Zandvoort column, because it is simulating Zandvoort.

### When

The first stop lands inside the car's projected window when it has one — that window is this
project's own model output and knows more about *this* car than an aggregate does. Any further stop
is drawn from where late stops actually fall here, as a share of race distance:

| p5 | p25 | p50 | p75 | p95 |
|---|---|---|---|---|
| 0.458 | 0.597 | 0.722 | 0.778 | 0.817 |

Over 109 late stops. Drawn laps are sorted and forced at least 6 laps apart, and a stop inside the
last 6 laps is dropped — there is no race left to amortise 23 seconds against.

### With what

Drawn from the measured transition matrix over 1,768 late stops:

| From ↓ / To → | HARD | MEDIUM | SOFT |
|---|---|---|---|
| HARD | 0.409 | 0.379 | 0.212 |
| MEDIUM | 0.501 | 0.172 | 0.327 |
| SOFT | 0.104 | 0.264 | 0.632 |

This looks like it violates B6.3.8 — 41% of stops from hard fit hard again — but these are real stops
from races that complied: the car had already used the other compound earlier. Forcing a change at
every stop would produce *less* realistic races, not more. What cannot be verified here is
compliance across the whole race: the frozen lap-30 snapshot does not record which sets each car
used before it.

### What it costs

Drawn from a triangular over the measured Zandvoort green-flag quartiles: **median 23.5 s, p25 20.6,
p75 31.3**, over 164 stops. That agrees with the global 22.2 s in
[`pit-loss-under-neutralisation.md`](pit-loss-under-neutralisation.md).

The cost is applied as time spent stationary, not as distance subtracted. A car in the pit lane does
not move backwards — it stops advancing — and the field order is derived from distance travelled, so
subtracting would have moved cars backwards along the track.

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

- **Stops do not react to the race.** 36% of Zandvoort's real stops happen under a neutralisation,
  because that is when a stop is nearly free — and demonstrating exactly that is this project's
  central claim. Here the plan is drawn up front and does not respond to the safety car, because the
  track status is a manual control in this simulator with no history: there is no "the safety car
  came out on lap 41" for the plan to react to. This is the most valuable thing still missing.
- **Compliance with B6.3.8 is not checked.** The compound draw reproduces real, legal behaviour in
  aggregate, but the frozen lap-30 snapshot does not record which sets a car used before it, so
  whether a given simulated car ends the race having used two dry compounds is unknown.
- **The pit window is a projection, not a plan.** A car can have an open window and draw no stop, or
  stop without ever having one. The window column keeps showing the model's projection and goes blank
  once that stop is made; it deliberately does not show the drawn plan, because the two are different
  kinds of statement.
- **The neutralised discount is not applied to the stop itself.** Stopping under a safety car costs
  the same seconds here as under green. What it actually saves is *positions*, not seconds, and that
  is already measured - but wiring it in needs the track status at the stop lap, which is a manual
  control in this simulator rather than part of the race.
- **One noise scale for all dry compounds and all circuits.** The measurement supports the first
  (0.426–0.471) but says nothing about the second — per-circuit noise was not measured.
