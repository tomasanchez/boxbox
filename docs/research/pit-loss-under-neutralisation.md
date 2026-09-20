# What a pit stop really costs under Safety Car and VSC

Measured 2026-08-25 over **413 strategic stops across 2026 R01–R12**. Reproduce with
`uv run python scripts/pit_loss.py`.

## The short version

Commentary says a stop under Safety Car or VSC is cheap. **That is correct.** Our first
measurement appeared to contradict it, and the measurement was asking the wrong question.

| Currency | Green | VSC | Safety Car |
|---|---|---|---|
| **Seconds lost** vs the field | 22.2 s | 23.2 s | 32.6 s |
| **Positions lost** (median) | **+2** | **0** | **0** |

Both rows are true. A stop under neutralisation costs *more clock seconds* and *fewer
positions* — and positions are what wins races. The conceptualización's `k` factor was framed in
seconds, and seconds is the wrong currency when the field is bunched.

## Why seconds mislead under neutralisation

Under a Safety Car the field median lap goes from **85.0 s to 128.0 s** — every car is 43 s
slower. The pit-lane transit itself does not change: it is the same physical drive at the same
limiter speed, plus the same stationary time.

So the raw seconds a pitting car loses against a car circulating on track can be *larger* under
SC. But that car is crawling in a compressed queue. When the pitting car rejoins, it slots back
into the same queue at almost the same place. The clock says thirty seconds; the running order
says nothing happened.

The position column measures this directly and unambiguously:

| Condition | Stops | Median position delta |
|---|---|---|
| Green | 286 | **+2.0** |
| VSC (settled) | 61 | 0.0 |
| SC (settled) | 48 | 0.0 |

A green-flag stop costs two places. A neutralised stop costs none. That is the entire
commentary claim, confirmed.

## Teams behave as if they believe it

| | |
|---|---|
| Share of all laps neutralised | 9.6% |
| Share of all stops taken under neutralisation | **30.8%** |
| Over-representation | **3.20×** |

If stops were driven purely by tyre condition they would land under neutralisation at the
background rate. Three times over-represented is the pit wall reacting, and it is the strongest
behavioural evidence in this repo that the cheap-window rule is real.

## Two confounds in the seconds figure

**Double-stacking.** Teams bring both cars in on the same lap under a Safety Car, and the second
car waits. It contaminates the SC number badly:

| Condition | Single stop | Double-stacked | Share double-stacked |
|---|---|---|---|
| Green | 22.2 s (n=280) | 17.9 s (n=6) | 2% |
| SC settled | 25.6 s (n=30) | **37.6 s** (n=18) | **38%** |
| VSC settled | 21.2 s (n=37) | 27.6 s (n=24) | 39% |

Nearly 40% of neutralised stops are double-stacked against 2% of green stops. Restricting to
single stops brings SC down from 32.6 s to **25.6 s** — most of the apparent penalty was
teammates queueing, not the stop being expensive.

> **Correction, 2026-09-20. The twelve seconds are not there.** The paragraph above compares the
> double-stacked *group* against the single-stop *group*, with **n=18** under SC and no pairing.
> That comparison mixes two things: that the second car queues, and that teams choose to stack
> precisely when a stop is cheap. Subtracting **within the same pair** — same team, same lap, same
> race, so the second effect cancels — the surcharge the second car pays is:
>
> | | n | median | mean | second loses more |
> |---|---|---|---|---|
> | Green | 63 | **+1.0 s** | +1.9 s | 65% of pairs |
> | Safety car | 47 | **+3.5 s** | +3.9 s | 72% of pairs |
> | VSC | 42 | **+3.2 s** | +2.8 s | 81% of pairs |
>
> Three and a half seconds, not twelve. That **reverses the strategic reading**: stacking is cheap,
> which is why teams do it in 70% of the cases where they bring both cars in during the same
> neutralisation. The original figure was not a calculation error — it was the wrong comparison,
> on a sample too small to notice. Measured by `scripts/rival_reaction.py`, which also supplies the
> reaction policy the simulator now uses.

**Mid-lap deployment.** A lap flagged `sc` may have been run mostly at racing speed before the
car came out. Splitting by whether the flag was already active on the previous lap:

| Condition | n | Median |
|---|---|---|
| SC deployed this lap | 3 | 36.0 s |
| SC settled | 48 | 30.7 s |
| VSC deployed this lap | 15 | 26.2 s |
| VSC settled | 61 | 21.6 s |

Settled laps are consistently cheaper than transition laps, as expected. The `sc`/`vsc` flags
are per-lap and cannot resolve within-lap timing.

## Consequences

- **Correct the conceptualización.** `PitLoss_SC = PitLoss × k` with `k = 0.45 / 0.60` is wrong
  in seconds and right in spirit. Restate the rule in **positions or gap-to-rival**, not seconds:
  under neutralisation a stop costs roughly **zero track position**, against two places green.
- **Rules R2 and R3 are vindicated.** "Box under SC/VSC if a stop is pending" is correct, and
  the 3.20× over-representation shows real pit walls agree.
- **The simulator should model position, not clock time**, as the cost of a stop. This changes
  what the Monte Carlo optimises.
- ~~Exclude or flag double-stacked stops before fitting anything to pit-loss seconds.~~ Superseded
  by the correction above: the paired surcharge is +3.5 s under SC, so double-stacked stops are not
  a contaminant worth excluding. They are modelled explicitly instead — see ADR-014.

## Open items

- [ ] Measure gap-to-rival in seconds rather than position rank, for finer resolution than
      whole places.
- [ ] Derive a within-lap deployment timestamp from race control messages so transition laps can
      be handled properly.
- [ ] Re-run over 2022–2024 to check the position result is not 2026-specific.
