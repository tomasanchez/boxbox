# The 2026 regulation reset — impact on this project

Measured on 2026-08-25 across **24 races / 27,595 laps** (2024 R01–R12 vs 2026 R01–R12) using
this repo's own feature pipeline. Reproduce with `uv run python scripts/era_compare.py`.

## Verdict

2026 data is available and complete, but **the two eras cannot be pooled into one training
set**. The compound hierarchy has inverted. A model trained on 2018–2025 would learn that soft
wears fastest — exactly backwards for 2026.

Separately, the headline strategic story of 2026 — energy deployment — is **not observable**.
F1 does not publish it. That is a hard limitation on what this system can be, and it has to be
declared rather than worked around.

## Data availability

12 races were run and are loadable (R01 Australia through R12 Netherlands, 2026-08-23). R13
Italy onward have not happened yet. Columns are **identical** to previous seasons — no new
fields were added for the new regulations.

| Column | 2026 R01 completeness |
|---|---|
| `Stint`, `Compound`, `TyreLife`, `FreshTyre`, `TrackStatus`, `IsAccurate` | 100.0% |
| `LapTime` | 99.4% |
| `Position` | 99.8% |
| `PitInTime` | 3.3% |

**2026-only dataset size: 14,095 laps, 527 positive labels across 12 races.** That is enough to
train on, which is the important conclusion.

Grid is now 11 teams / 22 drivers — Audi and Cadillac both appear in the team list.

## Finding 1 — the compound hierarchy has inverted

Median fitted degradation rate, s/lap, positive means losing time as the tyre ages:

| Era | HARD | MEDIUM | SOFT | Fastest-wearing |
|---|---|---|---|---|
| 2024 | 0.0388 | 0.0376 | **0.0673** | SOFT |
| 2026 | **0.0436** | 0.0239 | 0.0142 | HARD |

The inversion is real and it is large: soft went from the fastest-wearing compound to the
slowest. This is the single fact that forbids pooling the eras.

### Where our numbers disagree with published analysis

Secondary reporting ([f1chronicle](https://f1chronicle.com/2026-f1-tyre-degradation-data/))
claims the 2026 compound spread is 0.008 s/lap, the narrowest of the ground-effect era, against
0.041 in 2025. **We do not reproduce that.** We measure a spread of 0.0293 s/lap in 2026 against
0.0297 in 2024 — essentially unchanged.

The inversion replicates; the spread collapse does not. The likely cause is estimator choice:
we emit a rolling 5-lap slope per lap and take the median, they fit one line per stint. Those
are different statistics and are not directly comparable.

Do not cite either figure in the TP without resolving this. It is tracked as an open item.

## Finding 2 — races were *not* neutralised less; they were neutralised far more

| Era | SC laps | VSC laps | Any neutralisation |
|---|---|---|---|
| 2024 | 4.00% | 1.21% | 5.07% |
| 2026 | 5.21% | 4.40% | **9.61%** |

> **Correction, 2026-08-25.** "Nearly doubled" overstates it — see
> [`neutralisation-rates.md`](neutralisation-rates.md). That comparison used 2024 as the only
> baseline, and 2024 was unusually quiet. Against 2022 (12.6% of laps neutralised) the 2026
> figure of 16.5% is elevated but not a doubling. 2026 *is* the most neutralised season in the
> sample and its VSC frequency is genuinely the highest, so the direction holds; the magnitude
> was an artifact of picking the quietest comparator.

Neutralised laps rose sharply against 2024, and VSC laps more than tripled against it. This **promotes the SC/VSC
rules (R2, R3 in the conceptualización) from a footnote to the highest-value part of the
system**: the cheap-stop window is now open roughly one lap in ten.

## Finding 3 — slightly more stops (corrected for free stops)

> **Correction, 2026-08-25.** The first version of this section counted red-flag tyre changes
> as pit stops. They are not decisions: while the race is suspended a tyre change costs no
> track time. Across these 24 races **8.1% of all "stops" were free** (7.5% of 2024, 8.7% of
> 2026), and they cluster hard — 2024 Monaco was 69.6% free stops, 2026 Zandvoort 30.9%. The
> table below is corrected; `features.add_labels` now emits `free_stop` and `strategic_stop`.

Strategic stops only, per driver-race:

| Era | Mean | Median | 1-stop | 2-stop | 3+ |
|---|---|---|---|---|---|
| 2024 | 1.77 | 2.0 | 26.5% | 51.7% | 14.2% |
| 2026 | 1.87 | 2.0 | 35.4% | 37.4% | 23.0% |

2026 still runs slightly more stops, so that conclusion survives. The "one-stop becomes the
default" story is visible in the rising one-stop share (26.5% → 35.4%), but two-stop races fell
much further (51.7% → 37.4%) and 3+ stop races rose, so the field is **more spread across
strategies**, not more conservative.

**What did not survive the correction:** the earlier claim that 2026 had driver-races with 5, 6
and 7 stops against a 2024 maximum of 4. Corrected, 2026 tops out at 6 (0.8% of driver-races)
and 2024 at 5 (0.4%). The tail is fatter in 2026, but nothing like as dramatically as first
reported.

Label balance: **3.74% positive in 2026 vs 3.36% in 2024** (uncorrected `boxed`).

> Methodology note: this table counts `boxed` events; `scripts/era_compare.py` derives stops
> from distinct `Stint` values, which differs slightly when a red flag splits a stint without a
> recorded `PitInTime`. Prefer the `strategic_stop` count.

## Finding 4 — energy management is invisible, and so is DRS

Confirmed empirically: 2026 `car_data` channels are unchanged —
`RPM, Speed, nGear, Throttle, Brake, DRS` — with no battery, deployment or wing-state channel.

The FastF1 maintainer confirms this is F1's decision, not a library gap
([discussion #861](https://github.com/theOehrly/Fast-F1/discussions/861), 2026-03-14):

> F1 has decided to not make any data on active aero and ERS state available publicly.

Active aero was trialled in the pre-season feed and then removed. DRS was replaced by active
aero in the regulations, so the surviving `DRS` column should be treated as **vestigial and
untrustworthy for 2026** until verified.

### Why this matters more than it looks

Under the 2026 rules roughly 50% of power comes from the MGU-K, and battery state of charge and
Manual Override are genuinely part of the strategic calculus now. **None of it is in the data.**

The honest framing for the TP: the system models the *tyre and track-position* half of the
strategy problem and explicitly declares the *energy* half out of scope, because the data does
not exist publicly. That is a legitimate, defensible scope boundary — and a much stronger
position than silently pretending the variable is not there.

## Consequences for this repo

- [ ] **Do not pool eras.** Either train 2026-only, or carry a regulation-era feature and
      accept that pre-2026 rows teach an inverted hierarchy.
- [ ] **Re-fit the fuel coefficient for 2026.** `features.FUEL_EFFECT_S_PER_LAP` is hardcoded at
      0.035 s/lap, calibrated on the old era. 2026 cars are ~32 kg lighter and carry less fuel;
      published analysis tests the range 0.03–0.08. This constant is now the weakest assumption
      in the pipeline.
- [ ] **Reweight the rule base toward SC/VSC.** Neutralisation doubled; R2/R3 now carry most of
      the value.
- [ ] **Resolve the spread discrepancy** — add a per-stint linear-fit estimator alongside the
      rolling slope and compare like with like.
- [ ] **Add `era` to the conceptualización** as an attribute of the Circuito/Carrera concept.
- [ ] Verify whether the `DRS` column carries anything meaningful in 2026 or is dead.

## Sources

- [FastF1 discussion #861 — 2026 ERS deployment & energy management data](https://github.com/theOehrly/Fast-F1/discussions/861)
- [FastF1 discussion #895 — the 2026 regulations](https://github.com/theOehrly/Fast-F1/discussions/895)
- [f1chronicle — 2026 F1 tyre degradation data](https://f1chronicle.com/2026-f1-tyre-degradation-data/)
