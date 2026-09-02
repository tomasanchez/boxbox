# The genetic search, and what "winning" means

Built 2026-09-02. `apps/ml/src/boxbox_ml/strategy.py`; run it with
`uv run python scripts/strategy_search.py`. Output for the Zandvoort grid is in
[`strategy-zandvoort.json`](strategy-zandvoort.json) and ships to the UI as
`apps/web/src/plans.ts`.

## What it does

For one car, search the space of pit-stop plans — how many stops, on which laps, onto which
compound — and return the plan whose *distribution* of outcomes is best over hundreds of drawn
races. Everything drawn is measured: tyre wear from the empirical Zandvoort stint-slope
distribution, pit loss from the effective-loss quartiles, and the safety car from its own measured
rate, onset and duration.

Operators are the ones named in the proposal: one-point crossover on the stop list, cut on **lap**
rather than index so a child inherits a coherent first half of the race from one parent and a
coherent second half from the other; and mutation that lengthens a stint, shortens it, changes its
compound, or adds and drops a stop.

## The safety car is in the fitness, not decoration

Each drawn race gets one safety car or none — 60% at Zandvoort over 5 races, 54% over all 103 — on a
lap drawn from where they actually start, lasting five laps. A stop that falls inside that window
pays the neutralised cost instead of the green one. The draw is **shared across every car in that
race**: a safety car that helps one hurts another, and drawing it per car would wash that out
entirely.

| | Median | p25 | p75 | Stops |
|---|---|---|---|---|
| Green | 22.6 s | 20.2 | 25.5 | 2,614 |
| Safety car | 19.5 s | 7.5 | 31.5 | 264 |
| VSC | 18.8 s | 14.8 | 27.1 | 199 |

### The discount is smaller than the commentary suggests, and the spread is the story

In seconds conceded to the field, a safety-car stop is only **14% cheaper** than a green one. That
sits awkwardly against the earlier finding in
[`pit-loss-under-neutralisation.md`](pit-loss-under-neutralisation.md) that a neutralised stop costs
**zero positions** against two under green, and this document does not resolve it.

What the spread does say is that the median hides two different events. The lower quartile of
safety-car stops is **7.5 s** — a third of the green cost, which is the cheap stop the commentary
means — while the upper quartile is **31.5 s**, worse than green. Reacting immediately and reacting
late are not the same decision, and the measurement here cannot tell them apart because it does not
record how far into the period the stop fell. That is the obvious next measurement.

### A measurement error that had to be fixed first

The first attempt compared the in-lap and out-lap against the race's **median green lap**. Under a
neutralisation the whole field is slow on those laps too, so that charged the stopping car for a
slowness everyone shared, and reported the safety-car stop as *more* expensive than a green one —
49.2 s against 20.0. The baseline has to be the field's own median on **those same laps**.

## Two things the snapshot cannot be trusted about

Both were found by the search producing nonsense, and both are worth recording because they are
properties of the data, not bugs in the code.

### The car's own wear rate barely predicts

Each car arrives carrying `degradation_rate`, a slope fitted over its trailing five laps. Comparing
that estimate at lap 10 against the slope those stints actually went on to run from lap 11, over
2,492 stints:

| | Value |
|---|---|
| Correlation | **0.183** |
| sd of the rolling estimate | 0.466 |
| sd of what actually happened | 0.127 |

The rolling figure is three and a half times too dispersed and correlates weakly. So it is shrunk to
the measured attenuation, **0.183 × 0.127 / 0.466 ≈ 0.05**: the future rate is drawn from the
compound's distribution, and the car's own deviation is admitted at 5%.

Projecting it raw was not a small error. One car in the snapshot carries −0.549 s/lap; extrapolated
over thirty laps that claims it will gain four minutes, and the search duly recommended a plan that
had it **winning from ninth**.

### Cars are not equally fast

Accumulating only the change in tyre state quietly assumes they are. A car eleventh and 62 seconds
back on a 25-lap medium was then projected to finish **fourth**, purely because it had the most to
gain from fresh rubber.

A car `gap_leader_s` behind after `from_lap` laps has been losing that much per lap on average;
subtract the tyre deficit it is carrying and what is left is its baseline pace, which persists
whatever it does with its tyres. Rough — it folds in the start, any incident, and any stop already
taken, which adds roughly 0.7 s/lap of phantom baseline to a car that has pitted once. Better would
be the gap's *rate of change*, which one lap of data cannot give.

## What "winning" means

**Yes, a car outside the top ten can win — but not by the same measure, and using the wrong one
produces a random answer rather than a cautious one.**

Expected championship points is the default, because it is the currency the sport pays in and
because the cliff at tenth does the right thing on its own: a car in eleventh has nothing to lose
and should take variance, a car leading has everything to lose and should not.

But for a car whose every plan scores zero, expected points is a **flat** objective and the search
has nothing to climb. Measured on this grid, a car in eighteenth:

| Objective | Best plan | Population spread over stop counts |
|---|---|---|
| Points | H8-M34 | 1: 0.21 · 2: 0.33 · 3: 0.17 · 4: 0.29 — noise |
| Position | H7-H35 | 1: 0.87 · 2: 0.12 — converged |

So the shipped default is `ADAPTIVE`: points where points are reachable, position where they are
not. `PODIUM` and `IN_POINTS` are also available, and they behave differently in the way you would
expect — asked to maximise the chance of reaching the top ten, the race leader is told to make an
extra stop it does not need, because that objective is saturated for it and any plan scores the
same.

## Does the reward behave the way the points table implies?

The fitness is the **absolute** points at the flag, averaged over the drawn races — not places
gained. Holding a points position therefore scores well by construction: hold fifth and every draw
pays 10, which a plan that half the time yields third and half the time eighth (0.5x15 + 0.5x4 =
9.5) cannot beat. The table is non-linear, so what a place is worth depends on where you are:

| Losing one place | Costs |
|---|---|
| P1 to P2 | 7 points |
| P4 to P5 | 2 |
| P9 to P10 | 1 |
| P10 to P11 | 1 — but that is the whole score |

The prediction is that the search should be most cautious at the front and most willing to gamble
where the downside is already nothing. Measured on this grid:

| | Car | Finishes | Spread | Choice worth |
|---|---|---|---|---|
| P1 | ANT | 1.50 | **±0.74** | 6.17 pts |
| P2 | NOR | 1.93 | ±0.94 | **8.64 pts** |
| P5 | LEC | 2.31 | ±1.13 | 7.14 pts |
| P8 | ALO | 9.63 | **±1.45** | 1.62 pts |
| P10 | TSU | 11.37 | ±1.09 | **0.32 pts** |
| P11 | LIN | 8.39 | ±0.92 | 1.48 pts |

The leader takes the least risk and the car on the edge of the points takes the most, which is what
the table predicts. In between the pattern is noisy at 300 draws and should not be read as a trend.

The second column was not part of the prediction and is the more useful one: **the decision is worth
almost nothing at the back.** For TSU the best plan in the final population beats the worst by 0.32
points, against 8.64 for NOR. A confident recommendation there is a confident presentation of noise,
so the number is carried through to `plans.ts`.

## Not stopping was not on the ballot, and then it won everything

The first version could not consider a zero-stop plan: the seed drew at least one stop, and any
child that ended up empty was thrown away. That silently removed the most conservative option there
is — a car that has already used two compounds and is holding a points place may well be right to
stay out.

Allowing it flipped half the grid to running 42 laps on one set, which is where the next finding
came from.

### Degradation flattens, and it is survivorship

Mean deficit against stint lap, over 91,000 laps:

| Stint lap | SOFT | MEDIUM | HARD |
|---|---|---|---|
| 1-5 | 0.14 | 0.15 | 0.11 |
| 11-15 | 0.64 | 0.34 | 0.30 |
| 16-20 | 0.75 | 0.48 | 0.41 |
| 21-25 | 0.70 | 0.48 | 0.49 |
| 26-30 | 0.52 | 0.43 | 0.46 |
| 31-35 | 0.55 | 0.30 | 0.38 |
| 46-70 | — | 0.14 | 0.39 |

It peaks around lap 20-25 and then **falls**. No tyre does that. The sets that run past thirty laps
are the ones that held; the ones that did not were changed. A quadratic fit comes out concave for
all three compounds, which is the same artefact in another form.

So the data cannot price a long stint, and what it does say is optimistic. Rather than invent a
cliff there is no evidence for, the search is **forbidden from proposing a stint longer than the
90th percentile of what has actually been run** — 41 laps on the hard, 31 on the medium, 25 on the
soft, counting the laps already on the set. That is a limit on what the model may claim, not a claim
about the tyre.

With the constraint in place every car returns to one stop.

## The recommendation for the Zandvoort grid, lap 30 of 72

Every car converges on **one stop**, at confidences between 0.59 and 0.94.

| | Car | Plan | Finishes | Points | Objective |
|---|---|---|---|---|---|
| P1 | ANT | H16-H26 | 1.50 | 22.03 | points |
| P2 | NOR | H16-H26 | 1.93 | 19.81 | points |
| P3 | RUS | H15-H27 | 3.59 | 13.72 | points |
| P4 | PIA | H13-H29 | 2.78 | 16.20 | points |
| P5 | LEC | M6-H36 | 2.31 | 18.37 | points |
| P6 | HAM | H6-H36 | 4.54 | 11.17 | points |
| P8 | ALO | S6-H36 | 9.63 | 1.80 | points |
| P11 | LIN | M6-H36 | 8.39 | 3.35 | points |
| P14 | ALB | H20-H22 | 12.86 | 0.02 | position |
| P18 | COL | H6-H36 | 15.82 | 0.00 | position |

One stop is the modal recommendation everywhere, which is what the measured distribution says too:
from 41.7% of race distance, 49% of Zandvoort cars have exactly one stop left and 19% have two. The
broadcast's "two to three stops" is a whole-race figure; from lap 30 most of that is already spent.

## Known gaps

- **No on-track blocking.** A faster car is assumed to get past. Generous at Monaco, roughly fair at
  Zandvoort — and it is exactly the assumption that makes the rival-times-computed-once shortcut
  valid, so removing one means removing the other.
- **Rivals do not react.** Their plans are drawn once and held. Wrong precisely where two cars are
  racing each other directly, which is the case the recommendation matters most in.
- **The safety car does not move the plan mid-race.** The optimiser knows a safety car *might* come
  and prices it in, but the plan it returns is fixed. A real pit wall re-plans the moment the board
  goes yellow, and 36% of Zandvoort's real stops happen under a neutralisation.
- **One snapshot.** Everything is computed from lap 30 and never re-run as the race develops.
- **B6.3.8 is not enforced.** The frozen snapshot does not record which sets a car used before lap
  30, so whether a plan leaves it having used two dry compounds cannot be checked. That is also why
  a zero-stop winner is reported rather than filtered: it may be perfectly legal, and the data
  cannot say.
- **Long stints are bounded by evidence, not physics.** The cap is the 90th percentile of what has
  been run, so the search cannot propose the genuinely long one-stopper that occasionally wins a real
  race. Measuring the cliff — deficit against stint lap, corrected for the survivorship above — would
  replace the constraint with a model.
