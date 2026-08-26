# Case study — 2026 Dutch GP, Zandvoort (R12, 2026-08-23)

Reproduce with `uv run python scripts/zandvoort.py`.

This race is the clearest single illustration of why point-forecasting strategy fails, and it
is where a labelling bug in our own pipeline surfaced. 72 laps, 22 drivers, 1,368 lap records.

## What happened

| Event | Laps |
|---|---|
| **Red flag** | 2 |
| Safety Car | — |
| VSC | 52–57, 67–70 |
| Yellow | 1–5, 52–55 |

Neutralised for **11 of 72 laps (15%)**. Race control confirms the sequence: safety car lights
on lap 1, `RED FLAG - RACE SUSPENDED` on lap 2, restart, then `VSC DEPLOYED` at lap 55 and again
at lap 70.

## The strategies

Stop-count distribution: `{0: 2, 2: 1, 3: 14, 4: 5}` — **modal three stops**, with five drivers
making four. Most common plans were `S-S-H-S` (3 drivers), `S-S-M-H-S` and `M-S-H-H` (2 each).
Twenty-two drivers produced sixteen distinct plans.

## Stops followed the events, not the tyres

| | |
|---|---|
| Pit stops | 68 |
| Taken on a neutralised lap | **27 (40%)** |
| Neutralised share of all laps | 15% |

If stops were tyre-driven they would land on neutralised laps at roughly the background rate.
**40% against a 15% baseline is a 2.7× over-representation** — the field was reacting to the
race, not to the rubber.

The busy laps make it obvious:

| Lap | Stops | Condition |
|---|---|---|
| 2 | **21** | RED FLAG |
| 18 | 3 | green |
| 21 | 5 | green |
| 55 | 3 | VSC |

## The bug this exposed

**Twenty-one of twenty-two drivers "boxed" on lap 2** — because the race was red-flagged and
everyone changed tyres in the pit lane for free.

Our `boxed` label came straight from `PitInTime`, so it could not tell a free red-flag change
from a strategic stop costing ~20 seconds. Training on that teaches the model that boxing is
sometimes free, which is true only under a red flag it cannot see coming.

### How far it spread

Audited across all 24 races in the comparison set:

| Season | Stops | Free (red-flag) | Share |
|---|---|---|---|
| 2024 | 454 | 34 | 7.5% |
| 2026 | 527 | 46 | 8.7% |

Small in aggregate, brutal where it lands:

| Race | Stops | Free | Share |
|---|---|---|---|
| 2024 Monaco | 23 | 16 | **69.6%** |
| 2024 Suzuka | 55 | 18 | 32.7% |
| 2026 Monte Carlo | 89 | 25 | 28.1% |
| 2026 Zandvoort | 68 | 21 | **30.9%** |

> **Correction, 2026-08-25.** An earlier version said the 89 stints at Monaco 2026 were explained
> by its two red-flag periods. That is incomplete and mostly wrong. **Article B6.3.8 of the 2026
> Sporting Regulations imposes a mandatory three-set minimum at Monaco** — effectively a
> compulsory two-stop — on top of the usual two-compound requirement. 89 stints across 22 drivers
> is ~4.05 stints each, which is what a mandated two-stop plus free red-flag changes produces.
> The regulation is the structural driver; the red flags are secondary.

### Fixed

`features.add_labels` now emits `free_stop` (boxed under red) and `strategic_stop` (boxed
otherwise) alongside `boxed`. Callers must not treat `boxed` alone as "the team chose to pit".

The corrected stop counts are in [`2026-regulations.md`](2026-regulations.md); the change
retired one earlier claim (2026 driver-races with 5, 6 and 7 stops) as an artifact.

## How our model did here

Leave-one-race-out at Zandvoort, from `scripts/forecast_test.py`:

| Metric | Value |
|---|---|
| Exact stop-count accuracy | 0.045 — one driver in 22 |
| Naive baseline | 0.045 |
| MAE | 1.27 stops |

The model forecast a normal race. Zandvoort was not one, and **no pre-race feature could have
said otherwise** — a lap-2 red flag is not in the practice data, the weather, or the tyre
allocation.

## Why this is the argument, not the excuse

A point forecast of "three stops at Zandvoort" would have been right by luck and for the wrong
reason: the modal three stops includes one free change nobody chose. A distribution forecast
conditioned on a drawn Safety Car / red flag realisation would have said something honest —
*"most likely two strategic stops; 15–20% chance of a neutralisation-driven race with three or
more"* — and been scoreable either way.

That is the case for the Monte Carlo approach in
[`forecasting-strategy.md`](forecasting-strategy.md), made by a race rather than by an argument.

## Open items

- [ ] Re-run the feasibility and forecast tests with `strategic_stop` as the target and
      `free_stop` excluded, and see how much the earlier numbers move.
- [ ] Detect red flags from race control messages as well as track status — the status code and
      the message did agree here, but that should not be assumed.
- [ ] Measure per-circuit red-flag and SC/VSC rates to drive the Monte Carlo draw. Zandvoort and
      Monaco are clearly not Barcelona.
