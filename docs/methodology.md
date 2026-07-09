# Validation methodology

The engine exists to answer one question honestly: *would this rule have made
money, executed mechanically, at real prices?* Every design choice below
exists because its absence produces flattering lies.

## Real prices only
Futures options are priced from exchange settlement records (every listed
strike settles daily, including untraded ones); equity options from OPRA
records. No modeled fills where a real mark exists. Where the research build
models anything (strike placement before pulling a path), the model was first
validated against real chains.

## D+1 execution
Signals computed on day D's close trade at day D+1 prices. Filling on the
signal bar is unintentional clairvoyance; several results in the research
build changed materially — one flipped sign — under honest lag.

## Coverage audits (see `ore/audit.py`)
Every generated signal must terminate in a recorded outcome: a trade or an
explicit skip with a reason. Unexplained signals fail the run. Silent drops
are biased toward chaotic days, i.e. losers; a pipeline that skips hard days
manufactures alpha out of exceptions.

## Pre-registered forecasts
Before each experiment, the expected outcome is written down. Wrong forecasts
are kept and logged. This converts hindsight into a measurable error rate —
and it turned out to matter: several confident predictions were refuted, in
both directions.

## Out-of-sample discipline
Rules were frozen on data ending at a cutoff date; the following twelve
months were pulled only afterwards and tested blind. The headline check is
not the P&L but the *character match*: win rate, loss shapes, and exit-reason
distribution should look like the backtest. (They did — win rate matched to
the percentage point; one concurrency loophole surfaced and became a rule.)

## Parameter sweeps over point estimates
No parameter ships from a single lucky value. Lookbacks, profit targets, and
entry lags were swept; the acceptable outcomes are a plateau (robust) or a
smooth monotonic trade-off (a dial). A spike at one value is treated as
overfitting and rejected.

## Costs and structure
Per-product commissions, exchange fees, and slippage at per-product tick
sizes. Getting slippage units wrong once (price-points vs ticks) fabricated a
0%-win-rate market out of a mediocre one — units bugs are results bugs.

## The graveyard is kept
Failed strategies are documented with the same rigor as survivors, with the
dollar cost of each lesson. A research process that deletes its failures
cannot be audited, and its survivors cannot be trusted.
