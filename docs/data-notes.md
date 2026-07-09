# Field notes: historical options data in practice

Hard-won operational knowledge from building against CME (GLBX.MDP3) and
OPRA (OPRA.PILLAR) historical data. None of this is in the vendor docs in
quite these words; all of it cost either money or a debugging night.

## OPRA instrument IDs are recycled daily
An `instrument_id` maps to a different contract tomorrow. Any multi-day
request keyed by instrument ID returns spliced garbage — silently. Key
everything by `raw_symbol` (the OCC-style symbol) for time series.

## Settlements price the whole chain
Exchanges settle every listed strike daily, traded or not. For end-of-day
research this is strictly better than trade-based bars, which are sparse and
stale in the wings (a last-trade mark from four days ago prices like an
11% IV in a 30% world). Definition + settlement is the reliable EOD pair.

## Expiry calendars have survivorship traps
ES quarterly options existed long before the monthly (EOM) series. Query
only the quarterly root and entire crash windows (e.g. Feb-2020) simply have
no expiry inside a 30-45 DTE target window — those signals get skipped, and
the skipped days are precisely the interesting ones. The monthly series
lives under a different root; both must be merged. Same trap in bond
options: monthlies expire ~25 days before their underlying month, so a
30-45 DTE window can fall between listings; a fallback rule (nearest expiry
past a floor, capped) is required, not optional.

## Corporate actions corrupt cross-source joins
Retail price feeds are split-adjusted; historical option strikes are raw.
Every pre-split trade in a splitter (GOOGL, AMZN, NVDA, TSLA) silently
mis-strikes unless the scale factor is inferred and reconciled. Composite
splits compound (NVDA: 4:1 then 10:1 = 40x vs today's series). Full
postmortem in `split-bug-postmortem.md`.

## Tickers are not stable
META options before 2022-06-09 trade under FB. The symbol change is
invisible in the adjusted price feed and fatal in the options query.

## FX and metals options quote tiny deltas honestly
Currency-futures IVs are single digits; a vol floor tuned for equities (10%)
silently turns a 16-delta request into a 10-delta strike. Floors must be
per-asset-class.

## Slippage units are per-product
One tick means $10 on one product and $12.50 on another; applying a
cents-times-multiplier heuristic across products fabricated a $400/trade
cost on one market and made it look unshortable. Cost models need a
per-product table, not a formula.

## Billing reality (Databento specifics)
Historical usage is metered per volume, not per request. Definition pulls
dominate cost in options work (chains are wide); settlement paths for single
contracts are nearly free. A cache-first store with an offline mode (see
`ore/store.py`) makes spend a one-time property of a dataset rather than a
recurring property of a workflow — and makes "this rerun cost $0" provable.
