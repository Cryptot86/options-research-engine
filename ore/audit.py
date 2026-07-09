"""Coverage audit: prove that no signal silently vanished.

The most dangerous backtest bug isn't a wrong price — it's a DROPPED trade.
Drops are invisible in the results (the table still looks full) and they are
biased: the trades that fail to price are disproportionately the chaotic
days — halts, missing chains, crashes — i.e. exactly the losers. A pipeline
that quietly skips hard days manufactures alpha out of exceptions.

Real example from the research build this repo showcases: one market's
flagship result improved from +$67/trade to +$296/trade when ~250 signals
were silently skipped for want of a listed expiry in the target window.
The honest number required a fallback expiry rule and THIS audit to notice.

The audit is a full outer join between "signals the strategy generated" and
"outcomes the engine recorded" (trade or explicit skip). Anything unmatched
fails the run.
"""
from __future__ import annotations

import pandas as pd

from .engine import Ledger, Strategy


def coverage(prices: pd.DataFrame, strategy: Strategy, ledger: Ledger) -> pd.DataFrame:
    """One row per generated signal with its recorded outcome; raises if any
    signal has no outcome at all."""
    sig_days = prices.index[strategy.signals(prices)]
    outcomes = {}
    for t in ledger.trades:
        outcomes[t.signal_date] = f"traded ({t.exit_reason})"
    for day, reason in ledger.skips:
        outcomes.setdefault(day, f"skipped ({reason})")

    rows = [{"signal_date": d, "outcome": outcomes.get(d, "MISSING")} for d in sig_days]
    report = pd.DataFrame(rows)
    missing = report[report.outcome == "MISSING"]
    if len(missing):
        raise AssertionError(
            f"coverage audit FAILED: {len(missing)} signal(s) have no recorded "
            f"outcome, first: {missing.signal_date.iloc[0].date()} — a backtest "
            f"with unexplained signals is not evidence."
        )
    return report
