# Postmortem: the split-adjustment bug, or how a result gets *too good*

## Symptom

A covered-call variant backtest returned **+$8,692 per trade** on one name.
Real edges in liquid options are measured in tens of dollars per trade.
A number like that isn't a discovery; it's a stack trace wearing a suit.

## Root cause

Two data sources disagreeing about what a share is:

- **Price series** (retail sources like Yahoo): *split-adjusted*. GOOGL's
  2021 prices are shown around **$140** so charts look continuous through
  the July 2022 20-for-1 split.
- **Historical option records** (OPRA): *raw, as traded*. A GOOGL option
  from 2021 has a strike near **$2,800**, because that's what the stock
  actually cost that day.

Mix the two and every pre-split trade breaks silently. The strike selector,
asked to find a strike near "spot = $140," snapped to the lowest listed
strike on a $2,800 chain — a deep-ITM contract nobody intended. Premiums
then flowed through P&L on the raw scale (thousands of dollars) against a
stock leg on the adjusted scale. On names that never split (MSFT), results
were perfectly clean, which made the bug harder to see: it lived only in
specific names, only before specific dates.

## Why it wasn't caught earlier

The engine's internal math was *self-consistent* wherever both legs came
from the same source. Option-only strategies (credit collected and closed
against the same contract's marks) stayed on one scale and produced sane
numbers. The corruption only detonated in strategies that mixed the stock
leg with the option leg — a reminder that "the numbers look reasonable" is a
property of a code path, not of a pipeline.

## Detection heuristics that actually worked

1. **Too-good-to-be-true triage.** Any per-trade figure an order of
   magnitude above the strategy class's known range is treated as a bug
   until proven otherwise. This is the cheapest test in quant engineering
   and it fires more often than any linter.
2. **Ladder-vs-spot check.** If the median strike on the selected expiry is
   more than ~60% away from the provided spot, the scales disagree. The fix
   infers the integer split factor from that ratio (2, 3, 4, 10, 20, 40 —
   composite splits compound) and refuses to trade if no factor reconciles.
3. **Cross-validation by unaffected cohort.** Names with no split history
   act as a control group. If the anomaly clusters exactly on the
   split/no-split boundary, the diagnosis writes itself.

## Fixes

- The strike selector now detects scale mismatch from the chain itself and
  rescales spot before placing the strike (and refuses when unrecognizable).
- Strategies mixing stock and option legs normalize premiums and strikes by
  the inferred factor.
- An independently built parallel pipeline hit the same bug the same week
  and converged on the same fix — two implementations agreeing on a subtle
  defect is the closest thing backtesting has to peer review.

## The general lesson

Corporate actions are where financial pipelines go to lie to you. Splits,
symbol changes (FB→META options predate the ticker most sources report),
special dividends, expiry-calendar gaps — none of them throw exceptions.
They just make your results quietly, flatteringly wrong. The defense isn't
cleverness; it's audits that make silence impossible: coverage joins,
scale checks, control cohorts, and suspicion of good news.
