# options-research-engine

A backtesting engine for options strategies, built to answer one question
honestly: **would this rule have made money, executed mechanically, at real
prices?** — and engineered so the answer can be *audited*, not just admired.

This is the public architecture showcase of a private research platform that
tested ~9,000 signals across 13 years of real CME futures-options settlements
and OPRA equity options data. The private build's strategies, thresholds, and
findings stay private; everything here — the engine design, the validation
discipline, and the war stories — is the transferable engineering.

> Writeup: *"I tested whether my own trading beliefs survive 9,000 real
> trades — most of them died."* (findings summary, sauce-free) — see the
> pinned link on my profile.

## Run the demo (no API keys, no data spend, ~5 seconds)

```bash
pip install -r requirements.txt
python demo/run_demo.py
python tests/test_pricing.py
```

The demo pushes a deliberately naive strategy (MA-cross put selling on a
synthetic tape) through the full pipeline: D+1 execution, delta-targeted
strike placement, mechanical exits, max-adverse-excursion tracking, and a
coverage audit that fails the run if any signal lacks a recorded outcome.
The strategy is worthless on purpose — the demo showcases the machine.

## Architecture

```
prices ──► Strategy.signals() ──► engine.run() ──► Ledger (trades + skips)
                                     │                  │
                       price_option(entry, cfg)     audit.coverage()
                       [real chains in research     [every signal must
                        build; synthetic here]       have an outcome]
                                     │
                              ore/pricing.py
                       Black-76 · IV (Brent) · Δ→strike
```

- **`ore/pricing.py`** — Black-76/BS pricing, implied vol via Brent, analytic
  delta→strike inversion (place a 16Δ strike without scanning the chain).
- **`ore/store.py`** — cache-first store for paid APIs: atomic writes,
  transient-only retries, spend guard, and a provable OFFLINE mode.
- **`ore/engine.py`** — mechanical execution: D+1 entries, profit/time exits,
  one-position-at-a-time, explicit skips. If a rule isn't code, it wasn't
  tested.
- **`ore/audit.py`** — the coverage join. The most dangerous backtest bug is
  a silently dropped trade; drops cluster on chaotic days, i.e. losers.

## The docs are the point

- [`docs/methodology.md`](docs/methodology.md) — the validation discipline:
  real prices, D+1, coverage audits, pre-registered forecasts, out-of-sample
  freezing, sweep-over-point-estimate, and why the graveyard is kept.
- [`docs/split-bug-postmortem.md`](docs/split-bug-postmortem.md) — how
  split-adjusted prices silently corrupted pre-split option strikes, why it
  surfaced as a result that was *too good*, and the checks that caught it.
- [`docs/data-notes.md`](docs/data-notes.md) — field notes on OPRA/CME
  historical data: recycled instrument IDs, expiry-calendar survivorship
  traps, ticker changes, per-product cost models.

## Results (from the private research build)

Selected, deliberately parameter-free:

- A three-condition volatility-state filter flipped an equity short-premium
  book from **−$21 to +$88 per trade across 4,364 trades** (identical
  entries; the filter is most of the edge).
- Hard dollar stops on high-probability premium **roughly doubled** realized
  losses versus mechanical time/profit exits.
- The out-of-sample year (rules frozen, then tested blind on the following
  12 months) reproduced the backtest win rate to the percentage point.

## Author

Built solo over ~4 months. Python · pandas · SciPy · Databento (CME GLBX,
OPRA) · SQLite · Streamlit · Pine Script. I'm a data engineer working as a
quantitative developer; open to roles in market-data / quant platform
engineering (US · Dubai).
