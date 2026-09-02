# Per-circuit overtaking difficulty

Measured 2026-09-01 over **95 races** (2022–2026, 25 circuits) after excluding wet races.
Reproduce with `uv run python scripts/overtake_difficulty.py --offline`, or `--reuse` to skip
re-parsing the FastF1 cache.

## Verdict

**Only the extremes survive.** Monaco is genuinely the hardest circuit to pass at — 0.17 on-track
position exchanges per green racing lap against a field average of 0.68 — and Las Vegas and Monza
are genuinely the easiest at 1.45 and 1.21. **The middle of the table is not separable.** A
split-half test puts the reliability of a full-sample circuit estimate at **0.346**, meaning about
two thirds of the apparent spread between circuits is race-to-race noise.

For the UI this means the gauge is a **ranking position, not a measurement of the circuit**, and it
is labelled that way: hovering it reports the raw rate and how many races it rests on.

## What counts as a pass

For each pair of consecutive laps, drivers who swap order have exchanged a position. Three things
inflate that count without being overtakes, and all three are excluded:

| Excluded | Why |
|---|---|
| Any driver touching the pit lane on either lap | A car that stops drops several places without being passed |
| Neutralised and red-flag laps | Overtaking is banned outright; the order moves for other reasons |
| Races with rain on >20% of laps | The weather reshuffles the order, not the layout |

The rate is exchanges per **green racing lap**, so a 78-lap race and a 44-lap race are comparable.

### Rain mattered, but not the way expected

Eight races were dropped as wet:

| Race | Rain share |
|---|---|
| 2022 R18 Suzuka | 90% |
| 2024 R21 São Paulo | 73% |
| 2024 R12 Silverstone | 43% |
| 2022 R07 Monaco | 39% |
| 2025 R01 Melbourne | 33% |
| 2022 R13 Budapest | 29% |
| 2024 R09 Montréal | 25% |
| 2023 R13 Zandvoort | 23% |

Dropping them moved individual circuits a long way — Zandvoort went from 0.626 exchanges/lap to
0.502 and from 12th to 5th hardest, because its wet 2023 race alone read 1.121 against 0.302 for
the dry 2022 one on the same tarmac.

**But it did not make the measure more reliable.** Split-half correlation went from 0.236 with wet
races included to 0.209 without them. Rain was a confound worth removing on its own terms, and
removing it did not reveal a stable signal underneath — the noise is ordinary race-to-race
variation, not weather.

## Reliability, and the shrinkage it forces

Correlating each circuit's 2022–23 mean against its 2024–26 mean tests whether the ranking is a
property of the circuit. Across the 23 circuits present in both halves:

- split-half correlation **0.209**
- full-sample reliability, Spearman-Brown **0.346**

Every circuit is therefore pulled toward the grand mean of 0.683 by that factor. The effect on the
spread is severe and honest:

| | Range |
|---|---|
| Raw | 0.172 – 1.451 |
| Shrunk | 0.506 – 0.949 |

## The table

Difficulty is the shrunk value rescaled to 0–1 across the measured set. It is a position within
these 24 circuits, not an absolute scale — there is no such thing as an absolutely un-overtakeable
circuit.

| # | Circuit | Races | Exchanges/lap | Difficulty |
|---|---|---|---|---|
| 1 | Monaco | 4 | 0.17 | 1.00 |
| 2 | Budapest | 4 | 0.41 | 0.82 |
| 3 | Lusail | 3 | 0.45 | 0.78 |
| 4 | Baku | 4 | 0.49 | 0.75 |
| 5 | **Zandvoort** | 4 | **0.50** | **0.74** |
| 6 | Imola | 3 | 0.52 | 0.73 |
| 7 | Spielberg | 5 | 0.54 | 0.72 |
| 8 | Suzuka | 4 | 0.58 | 0.68 |
| 9 | Mexico City | 4 | 0.59 | 0.67 |
| 10 | Barcelona | 5 | 0.60 | 0.67 |
| 11 | Melbourne | 4 | 0.63 | 0.64 |
| 12 | São Paulo | 3 | 0.63 | 0.64 |
| 13 | Miami | 5 | 0.68 | 0.60 |
| 14 | Marina Bay | 4 | 0.69 | 0.60 |
| 15 | Silverstone | 3 | 0.69 | 0.60 |
| 16 | Sakhir | 4 | 0.70 | 0.59 |
| 17 | Montréal | 4 | 0.70 | 0.59 |
| 18 | Spa-Francorchamps | 5 | 0.80 | 0.51 |
| 19 | Jeddah | 4 | 0.82 | 0.49 |
| 20 | Austin | 4 | 0.88 | 0.44 |
| 21 | Yas Island | 4 | 0.93 | 0.41 |
| 22 | Shanghai | 3 | 0.95 | 0.39 |
| 23 | Monza | 4 | 1.21 | 0.19 |
| 24 | Las Vegas | 3 | 1.45 | 0.00 |

Le Castellet was measured but dropped from the shipped table: one race, and it is no longer on the
calendar.

### Zandvoort, race by race

| Season | Exchanges | Green transitions | Per lap |
|---|---|---|---|
| 2022 | 19 | 63 | 0.302 |
| 2024 | 36 | 71 | 0.507 |
| 2025 | 25 | 53 | 0.472 |
| 2026 | 48 | 66 | 0.727 |

2023 excluded as wet. The 2026 figure being the highest of the four is consistent with the wider
2026 finding that the season races differently, but four races cannot establish that.

## Season baselines

| Season | Races | Exchanges/lap | Median |
|---|---|---|---|
| 2022 | 19 | 0.763 | 0.794 |
| 2023 | 20 | 0.867 | 0.757 |
| 2024 | 21 | 0.566 | 0.507 |
| 2025 | 23 | 0.543 | 0.472 |
| 2026 | 12 | 0.723 | 0.759 |

The 2024–25 dip and the 2026 recovery are larger than most of the between-circuit differences,
which is another way of saying the season matters more than the track.

## Known weaknesses

- **Shrinkage is uniform, not weighted by sample size.** A circuit with three races is pulled toward
  the mean by the same factor as one with five. Proper empirical Bayes would shrink the three-race
  circuits harder. Zandvoort has four races, near the median, so the shipped number is not much
  affected — but Lusail, Imola, São Paulo, Silverstone, Shanghai and Las Vegas are each on three.
- **A swap is not always an overtake.** Two cars can exchange order because one had a slow lap or a
  problem. Excluding pit laps removes the biggest source; the rest is left in.
- **Weather exclusion depends on the `Rainfall` column.** Some sessions log `Failed to load weather
  data!`; those races have no rain share and are kept by default. A wet race with missing weather
  data would survive the filter.
- **The measure ignores where on the lap passes happen.** A circuit with one huge DRS zone and a
  circuit with three mediocre ones can score the same.

## What it is used for

`apps/web/src/overtaking.ts` carries the shipped table, and the «Battle Forecast» card reads it for
the difficulty gauge. It is presentation only: the catch-up projection itself does not use it,
because the model has no dirty-air term and pretending otherwise would be worse than admitting the
gap.
