# Can we forecast the strategy of a race that has not happened yet?

Measured 2026-08-25 on 2026 R01–R12, leave-one-race-out. Reproduce with
`scripts/strategy_probe.py` and `scripts/forecast_test.py`.

## Verdict

**Point-forecasting stint lengths and stop counts does not work.** Neither race-side features
nor practice pace beat simply predicting the median. This was tested twice, including one
hypothesis that turned out to be wrong.

That does **not** kill the idea. It changes the output from a point prediction to a
**distribution over strategies**, produced by simulation rather than regression — which is both
more honest and closer to what a pit wall actually reasons with.

## The stint dataset, and how it is censored

| | Count |
|---|---|
| Stints total | 756 |
| Ended in a pit stop (**uncensored**) | 527 |
| Ran to the chequered flag (**right-censored**) | 178 |
| Ended in retirement | 51 |

A stint that ends at the flag did not end because the tyre was finished. Training "how long
does a stint last" on those teaches the model to under-predict, so they are excluded. This is a
survival-analysis shape, and treating it as plain regression is a modelling choice worth
stating in the report.

Uncensored stint length: **mean 16.7 laps, median 17, sd 10.6, range 1–59.** That spread is the
whole problem.

## Strategy is high-cardinality

Compound sequences per driver-race:

| Sequence | Count |
|---|---|
| M-H | 67 |
| M-H-S | 23 |
| M-H-H | 23 |
| M-H-M | 9 |
| M (no stop) | 9 |

**73 distinct sequences across 257 driver-races.** The top three cover only 44%. Stop counts
run 0 through 7, with the mode at one stop (94) and two stops close behind (81).

## Attempt 1 — race-side features only

Leave-one-race-out, LightGBM on compound, stint index, start lap, tyre life, race length:

- **MAE 8.13 laps** against a naive "predict the median stint" baseline of **8.02 laps**.
- Beat the baseline on 6 of 12 races. A coin flip.

## Attempt 2 — add practice pace (hypothesis: this is the missing ingredient)

The reasoning was sound: at a circuit the season has not visited, there is no 2026 race data,
and practice is the only pre-race pace signal that exists. `boxbox_ml.practice` fits a
fuel-corrected degradation slope per compound from every available practice session. Coverage
was excellent — **97.2% of stints got a practice slope for their compound**, from 35
compound-round summaries across 717 long runs.

**It made things worse.**

| Model | Mean MAE |
|---|---|
| Naive (median stint) | **8.02 laps** |
| Race features only | 8.13 laps |
| + practice pace | 8.74 laps |

Practice helped on 5 of 12 races; the combined model beat naive on 6 of 12.

Stop-count prediction per driver-race was no better: **32.1% exact accuracy against a naive
32.0%**, MAE 0.90 stops.

### Why it failed

1. **Twelve training races cannot support more features.** Adding three practice columns to a
   12-group leave-one-out is an invitation to overfit, and that is what the numbers show.
2. **Practice fuel loads are unknown and wildly variable.** A qualifying simulation on low fuel
   and a race simulation on high fuel land in the same slope estimate. The constant fuel
   correction we apply cannot separate them.
3. **Stint length is event-driven, not tyre-driven.** This is the real finding, and everything
   else in this repo agrees with it: the 2026 compound spread is small (0.029 s/lap), neutralised
   laps doubled to 9.61%, and the stop distribution has a fat tail. Monaco produced 89 stints
   and a modal *five* stops. No amount of practice pace predicts a Safety Car.

## Where this leaves the idea

The forecasting goal survives; the output type has to change.

**Do not** predict "Verstappen will stop on lap 22 and again on lap 41." The evidence says that
number is not knowable, and claiming it would be the single easiest thing for the cátedra to
falsify — round 13 will simply disagree.

**Do** predict a distribution, via Monte Carlo over the rule engine:

1. Estimate degradation per compound at the circuit (practice, plus 2026 season priors).
2. Draw a Safety Car / VSC realisation from the circuit's empirical rate — now measurable, and
   materially higher in 2026 than before.
3. Run the rule engine from the conceptualización lap by lap over the simulated race.
4. Repeat a few thousand times, and report **P(1 stop), P(2 stops), the modal compound
   sequence, and a credible interval on the first stop lap.**

Scoring then becomes a calibration question — was the actual strategy inside the predicted
interval, and did the stated probabilities hold up across races — rather than a point-error
question the data cannot support.

This also puts the components where the evidence supports them: the degradation regression
(22,378 fitted slopes) drives the simulation, the rule engine makes the decisions, and nothing
is asked to point-predict an event-driven outcome.

## The prospective test is still the best part

11 races remain, and **10 of them are conventional weekends** with full FP1/FP2/FP3 (only
Singapore, R17, is a sprint with FP1 only).

| Round | Event | Date | Format |
|---|---|---|---|
| 13 | Italian GP (Monza) | 2026-09-06 | conventional |
| 14 | Spanish GP | 2026-09-13 | conventional |
| 15 | Azerbaijan GP | 2026-09-26 | conventional |
| 16 | Bahrain GP | 2026-10-04 | conventional |
| 17 | Singapore GP | 2026-10-11 | sprint |
| 18–23 | Austin → Abu Dhabi | Oct–Dec | conventional |

Committing a **timestamped, locked forecast** before each race and scoring it afterwards is
worth more to the report than any cross-validation table. It cannot be accused of leakage, it
cannot be retrofitted, and it is something almost no student project does. Round 13 is twelve
days out.

## Open items

- [ ] Build the Monte Carlo simulator over the rule engine; that is now the core deliverable.
- [ ] Measure per-circuit SC/VSC rates from 2026 to drive the draw.
- [ ] Try a survival model (Cox / accelerated failure time) that uses the 178 censored stints
      instead of discarding them.
- [ ] Separate practice runs by inferred fuel load before trusting a practice slope.
- [ ] Lock and publish a forecast for R13 Monza before 2026-09-06.
