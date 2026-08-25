# Is 2026 alone enough data to model with?

Measured 2026-08-25 on 2026 R01–R12. Reproduce with `scripts/feasibility.py` and
`scripts/horizon.py`.

## Verdict

**Rows: yes. Signal at the "box this lap" framing: weak — and more races will not fix it.**

The volume is adequate by every conventional check. What is thin is the number of
*independent* units, and what is genuinely hard is the target. The right response is not to
wait for more races; it is to put the rule engine, not the classifier, at the centre of the
system — which is what the conceptualización already proposed.

## How much data there actually is

| Unit | Count |
|---|---|
| Laps | 14,095 |
| Positive labels (boxed) | 527 (3.74%) |
| Driver-races | 257 |
| Driver-stints | 756 |
| **Races** | **12** |

Laps are not independent samples — consecutive laps of a stint are near-duplicates. The honest
unit for splitting is the **race**, and there are twelve. Every evaluation below uses
`GroupKFold` on race, so no race appears in both train and test.

After lagging (below): 13,644 rows, 505 positives, 19 features — **26.6 events per feature**,
comfortably above the usual 10–20 rule of thumb. Sample size is not the binding constraint.

## The leakage that had to be fixed first

| | `degradation_s` present |
|---|---|
| Boxed laps | **0.0%** |
| Non-boxed laps | 87.2% |

An in-lap is never "representative" — it carries the pit-lane transit — so all its pace
features are `NaN`. Feeding them raw lets the model read the answer straight off the
missingness pattern and score near-perfectly while learning nothing.

Every pace feature is therefore **lagged one lap**: the question is "will this driver box at
the end of this lap, given only what was known at its start". Any future work on this dataset
has to preserve that.

## What a baseline model achieves

LightGBM, class-weighted, race-grouped 5-fold CV:

| Metric | Value |
|---|---|
| PR-AUC | 0.1028 |
| PR-AUC of random guessing | 0.0370 |
| **Lift over chance** | **2.8x** |
| Best F1 | 0.1940 |
| Precision / recall at that point | 0.127 / 0.410 |

"Never box" scores **96.3% accuracy and 0.0 F1**. Accuracy must not appear in the report.

## The learning curve goes *down*

Trained on the first N races:

| Races | Train rows | Positives | PR-AUC | Best F1 |
|---|---|---|---|---|
| 3 | 2,936 | 83 | **0.3163** | 0.3429 |
| 6 | 6,541 | 218 | 0.1353 | 0.2161 |
| 9 | 10,143 | 366 | 0.1089 | 0.1722 |
| 12 | 13,644 | 505 | 0.1028 | 0.1940 |

This is the most important table here, and it is easy to misread. Performance is **not**
degrading because data is hurting. With three races the CV has three groups, each test fold is
a single race, and the model latches onto circuit-specific patterns that happen to repeat —
the 0.3163 is tiny-fold optimism, not a real score. Adding diverse races reveals the true
difficulty.

**The implication is direct: waiting for rounds 13–23 will not rescue this framing.** The
plateau near 0.10 is the honest number.

## Reframing the target helps less than it appears

Identical features, only the label changes:

| Horizon | Positive rate | PR-AUC | Lift | Best F1 | Precision | Recall |
|---|---|---|---|---|---|---|
| this lap | 3.70% | 0.1028 | **2.8x** | 0.1940 | 0.127 | 0.410 |
| next 2 | 7.09% | 0.1868 | 2.6x | 0.2779 | 0.193 | 0.494 |
| next 3 | 10.33% | 0.2255 | 2.2x | 0.3334 | 0.247 | 0.512 |
| next 5 | 16.67% | 0.3313 | **2.0x** | 0.4405 | 0.361 | 0.566 |

F1 more than doubles, from 0.19 to 0.44 — but **lift over chance falls**, from 2.8x to 2.0x.
The model is not learning more; it is being graded on an easier exam, because a wider window
has more positives to hit. Reporting the 0.44 as an improvement without the lift column would
be dishonest.

A window target is still the better *product* — "we are in the pit window" is what a strategist
actually wants — but it must be justified on those grounds, not on the F1 number.

## What the model leans on

```
prev_gap_behind_s                  1239
prev_degradation_s                 1103
prev_degradation_rate_s_per_lap    1082
prev_gap_ahead_s                    960
laps_remaining                      822
prev_lap_time_fuel_corrected        719
stint_lap                            609
```

The ordering is at least sane: track position and degradation lead, exactly as the
conceptualización's tactical rules assume. The features are not noise — the target is hard.

## Prior art, and where the novelty actually is

The general problem is **well-trodden**, and the TP must say so:

- **Peer-reviewed**: *Data-driven pit stop decision support for Formula 1 using deep learning
  models* (Frontiers in AI, 2025) predicts pit-stop windows from FastF1 data for **2020–2024**
  using Bi-LSTM, TCN-GRU, GRU, InceptionTime and CNN-BiLSTM. Best result: Bi-LSTM at
  **precision 0.77, recall 0.86, F1 0.81**.
- Multiple public GitHub projects (XGBoost optimisers, RL simulators) on 2020–2024.

Our 0.19–0.44 is far below that 0.81. Plausible reasons, in order of likelihood: they model the
stint as a **sequence** rather than as per-lap tabular snapshots; they train on ~5 seasons
(~100 races) rather than 12; their window definition may be wider than ours. Their setup was
not independently verified.

**The novelty is not the problem — it is the season.** No published work can have used 2026
data: the regulations reset this year, the compound hierarchy inverted (see
[`2026-regulations.md`](2026-regulations.md)), and round 12 was three days ago. A 2026-only
study is genuinely fresh, and the 2025 paper becomes an ideal **prior-art baseline to cite and
compare against** — which is worth more to the report than pretending nobody had the idea.

## Recommendation

Do not make the classifier the deliverable. The conceptualización already put it in the right
place — as a *contrast model* — and this data agrees:

| Component | Data support | Verdict |
|---|---|---|
| Degradation **regression** | 22,378 fitted slopes | **Strong.** This is the real ML deliverable |
| Rule engine over SC/VSC windows | Neutralised laps doubled to 9.61% | **Strong, and newly valuable in 2026** |
| Box/stay **classification** | 505 positives, lift 2.0–2.8x | **Weak.** Keep as a declared baseline |

Reporting the classifier honestly as a weak baseline, next to a working degradation model and
an auditable rule engine, is a better *Entrega 4* than a single overfitted number — and the
declining learning curve is itself a finding worth a slide.

## Open items

- [ ] Try a sequence model over stint history, the one clear methodological gap versus the
      2025 paper.
- [ ] Re-run once rounds 13–23 complete, to confirm the plateau rather than assume it.
- [ ] Test pooling eras with a regulation-era feature: ~130 races may beat 12 despite the
      inverted hierarchy.
- [ ] Re-fit `FUEL_EFFECT_S_PER_LAP` for 2026 before trusting any degradation figure.
