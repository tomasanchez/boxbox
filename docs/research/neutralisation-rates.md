# Per-circuit Safety Car, VSC and red-flag rates

Measured 2026-08-25 over **56 races** (2022, 2023 partial, 2024 partial, 2026 R01–R12) across
23 circuits. Reproduce with `uv run python scripts/safety_car_rates.py --offline`.

## Verdict

**There is no statistically detectable per-circuit Safety Car effect in this sample.** The raw
rates look dramatic — Jeddah 3/3, Barcelona 0/4 — but a properly fitted hierarchical model
shrinks every circuit to within **0.86×–1.09×** of the global rate. With at most four visits per
circuit, those differences are indistinguishable from coin flips.

Red flags are the exception: Monaco and Suzuka survive shrinkage at **3.5×** and **2.9×** the
global rate.

For the simulator this means: **draw Safety Cars from a single global rate, not a per-circuit
one.** Use per-circuit numbers only for red flags, and only for those two circuits.

## Baseline by season

| Season | Races | P(SC) | P(VSC) | P(red) | SC periods/race | Neutralised lap share |
|---|---|---|---|---|---|---|
| 2022 | 22 | 0.727 | 0.682 | 0.136 | 0.909 | 0.126 |
| 2023 | 10 | 0.500 | 0.400 | 0.100 | 0.800 | 0.060 |
| 2024 | 12 | 0.417 | 0.333 | 0.167 | 0.500 | 0.065 |
| 2026 | 12 | 0.500 | 0.667 | 0.167 | 0.500 | **0.165** |

> **Correction to an earlier claim.** [`2026-regulations.md`](2026-regulations.md) reported that
> neutralisation "nearly doubled" in 2026, comparing 5.07% of laps in 2024 to 9.61%. That
> comparison used a single baseline season, and 2024 turns out to have been unusually quiet.
> Against 2022 (0.126 share) the 2026 figure of 0.165 is elevated but **not** a doubling. 2026 is
> the most neutralised season in the sample, and VSC frequency (0.667) is genuinely the highest —
> but "doubled" overstated it by picking the quietest comparator.

Season counts are uneven because the ingest hit a rate limit (below), so 2023 and 2024 are
partial. Treat the season baselines as indicative, not final.

## Safety Car — everything shrinks to the mean

Global P(SC) = **0.571**. Fitted prior strength: **24.1 pseudo-visits**, against circuits with
1–4 actual visits. The prior therefore dominates, which is the correct answer given the sample.

| Circuit | Visits | Raw | Shrunk | ×global |
|---|---|---|---|---|
| Jeddah | 3 | 1.000 | 0.620 | 1.09 |
| Shanghai | 2 | 1.000 | 0.606 | 1.06 |
| Spa-Francorchamps | 2 | 1.000 | 0.606 | 1.06 |
| Monaco | 4 | 0.750 | 0.598 | 1.05 |
| Miami | 4 | 0.750 | 0.598 | 1.05 |
| Montréal | 4 | 0.750 | 0.598 | 1.05 |
| Silverstone | 3 | 0.667 | 0.583 | 1.02 |
| Suzuka | 3 | 0.667 | 0.583 | 1.02 |
| Monza | 2 | 0.500 | 0.568 | 0.99 |
| Baku | 2 | 0.500 | 0.568 | 0.99 |
| Zandvoort | 2 | 0.500 | 0.568 | 0.99 |
| Sakhir | 3 | 0.333 | 0.547 | 0.96 |
| Spielberg | 4 | 0.250 | 0.527 | 0.92 |
| Barcelona | 4 | 0.000 | 0.492 | 0.86 |

Total spread after shrinkage: **1.09× down to 0.86×.** That is not a usable signal.

Note what shrinkage is doing for you here. Barcelona has *never* thrown a Safety Car in four
observed visits — the naive estimate is 0.00, which in a simulator would mean "a Safety Car at
Barcelona is impossible". The shrunk 0.49 is the honest statement.

## VSC — slightly more spread, still weak

Global P(VSC) = 0.554. Range after shrinkage: **1.31× (Melbourne, Spielberg — both 4/4) down to
0.68× (Suzuka, 0/3).** Wider than the SC spread but still built on ≤4 observations per circuit.

## Red flags — the one real circuit effect

Global P(red) = 0.143, and here the shrinkage does *not* erase the differences:

| Circuit | Visits | Raw | Shrunk | ×global |
|---|---|---|---|---|
| **Monaco** | 4 | 0.750 | 0.494 | **3.46** |
| **Suzuka** | 3 | 0.667 | 0.407 | **2.85** |
| Zandvoort | 2 | 0.500 | 0.283 | 1.98 |
| Silverstone | 3 | 0.333 | 0.235 | 1.64 |
| Melbourne | 4 | 0.250 | 0.200 | 1.40 |

Monaco at ~3.5× and Suzuka at ~2.9× survive because the base rate is low, so three occurrences
in four visits is genuinely surprising under the global rate. These two are worth encoding.

This matters more than the raw probability suggests, because a red flag grants a **free tyre
change** — see [`case-zandvoort-2026.md`](case-zandvoort-2026.md).

## When neutralisations start

As a fraction of race distance:

| Event | n | Median | 25% | 75% | First quarter |
|---|---|---|---|---|---|
| Red flag | 10 | 0.103 | 0.021 | 0.758 | **60%** |
| Safety Car | 40 | 0.325 | 0.079 | 0.690 | 43% |
| VSC | 49 | 0.552 | 0.310 | 0.721 | 16% |

**Red flags and Safety Cars are front-loaded; VSCs are not.** Six of ten red flags came in the
first quarter of the race — first-lap contact is the mechanism. VSCs cluster around mid-race,
median 55% distance, consistent with single-car retirements rather than start incidents.

For a simulator this is as important as the rate: an early Safety Car reshapes the whole
strategy, a lap-55 VSC only affects whoever has not yet stopped.

## Remaining 2026 calendar

| Circuit | Visits | Raw | Shrunk P(SC) | ×global |
|---|---|---|---|---|
| Monza | 2 | 0.50 | 0.57 | 0.99 |
| Barcelona | 4 | 0.00 | 0.49 | 0.86 |
| Baku | 2 | 0.50 | 0.57 | 0.99 |
| Sakhir | 3 | 0.33 | 0.55 | 0.96 |
| Marina Bay | 1 | 1.00 | 0.59 | 1.03 |
| Austin | 1 | 1.00 | 0.59 | 1.03 |
| Mexico City | 1 | 0.00 | 0.55 | 0.96 |
| São Paulo | 1 | 1.00 | 0.59 | 1.03 |
| Yas Island | 1 | 0.00 | 0.55 | 0.96 |
| Las Vegas | — | — | — | not in the ingested set |
| Lusail | — | — | — | not in the ingested set |

For **R13 Monza on 2026-09-06**, the honest simulator input is `P(SC) ≈ 0.57`, i.e. the global
rate. There is no evidence Monza differs.

## Two bugs found and fixed

**Circuit names are not stable across seasons.** FastF1's `Location` reports Monaco as
`Monte Carlo` and Miami as `Miami Gardens` in 2026 but `Monaco` and `Miami` earlier. That
silently split each circuit's history into two under-observed halves — Monaco appeared as a
3-visit circuit and a 1-visit circuit. `neutralisation.CIRCUIT_ALIASES` normalises them.

**Method of moments is the wrong prior estimator here.** The first version fitted the Beta prior
by MoM and got a prior worth **0.79 pseudo-visits** — essentially no shrinkage, so a circuit seen
once with one Safety Car was reported at 0.83. With 1–2 visits per circuit the spread of observed
rates is dominated by binomial noise, and MoM reads that noise as real between-circuit variation.
Beta-Binomial maximum likelihood accounts for the sampling variance and returns 24.1
pseudo-visits. Every number in the first draft of this file was wrong; these are the corrected
ones.

## Operational finding: FastF1 rate-limits at 500 calls/hour

`RateLimitExceededError: any API: 500 calls/h`. A five-season ingest exceeds it partway through
and every remaining race is skipped — which is why 2023 and 2024 are partial here. Build the
cache up across several sessions, then run with `--offline` (added for this reason), which makes
zero API calls and cannot hit the limit.

## Open items

- [ ] Finish the cache: 2023, 2024 and 2025 in full, then re-run. More visits per circuit is the
      only thing that will resolve whether circuit effects are real.
- [ ] Model SC *duration* as well as occurrence — a 5-lap SC and a 1-lap VSC are different
      strategic objects.
- [ ] Las Vegas and Lusail are missing entirely and are both on the remaining calendar.
- [ ] Consider a Poisson model for period *counts* rather than Bernoulli for occurrence.
