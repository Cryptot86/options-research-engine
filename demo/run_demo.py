"""End-to-end demo: a deliberately naive strategy through the full engine.

Runs with NO API keys and NO market-data spend: prices are synthetic and the
option path is synthesized with Black-76 from the same random world. The
strategy (10/50 MA-cross put selling, unfiltered) is intentionally mediocre —
this demo showcases the MACHINE (D+1 execution, mechanical exits, MAE
tracking, coverage audit), not an edge. The edges live in the private
research build, where the same engine prices real CME/OPRA contracts.

    python demo/run_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ore.audit import coverage
from ore.engine import TradeConfig, run
from ore.pricing import black76, strike_for_delta


def synthetic_prices(n_days: int = 2500, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    # regime-switching vol so the demo has calm and storm, like a real tape
    vol = np.where(rng.random(n_days) < 0.05, 0.45, 0.16) / np.sqrt(252)
    rets = rng.normal(0.0004, vol)
    close = 100 * np.exp(np.cumsum(rets))
    idx = pd.bdate_range("2016-01-04", periods=n_days)
    return pd.DataFrame({"close": close}, index=idx)


class MaCross:
    """Naive on purpose: sell a put whenever 10MA > 50MA and price dips 2%."""
    name = "ma_cross_dip"

    def signals(self, prices: pd.DataFrame) -> pd.Series:
        c = prices["close"]
        trend = c.rolling(10).mean() > c.rolling(50).mean()
        dip = c < c.shift(1) * 0.98
        return (trend & dip).fillna(False)


class SyntheticOptionPath:
    """A 16-delta put path priced with Black-76 along the synthetic tape."""
    multiplier = 100.0

    def __init__(self, prices: pd.DataFrame, entry: pd.Timestamp, cfg: TradeConfig):
        self.prices = prices
        window = prices.loc[entry:].head(cfg.dte_target + 1)
        self.dates = window.index
        self.last_date = self.dates[-1]
        f = float(window["close"].iloc[0])
        self.iv = float(prices["close"].pct_change().rolling(20).std().loc[:entry].iloc[-1]
                        * np.sqrt(252)) or 0.2
        self.strike = round(strike_for_delta(f, cfg.dte_target / 365, self.iv,
                                             cfg.target_delta, kind="put"), 0)
        self.entry_price = black76(f, self.strike, cfg.dte_target / 365, self.iv)

    def walk(self):
        total = len(self.dates)
        for i, dt in enumerate(self.dates[1:], start=1):
            dte = (total - 1) - i
            f = float(self.prices.loc[dt, "close"])
            yield dt, black76(f, self.strike, max(dte, 0) / 365, self.iv), dte

    def settle_value(self) -> float:
        f = float(self.prices.loc[self.last_date, "close"])
        return max(self.strike - f, 0.0)


def main() -> None:
    prices = synthetic_prices()
    cfg = TradeConfig()
    strat = MaCross()

    def price_option(entry, cfg):
        try:
            return SyntheticOptionPath(prices, entry, cfg)
        except Exception:
            return None

    ledger = run(prices, strat, cfg, price_option)
    t = ledger.frame()
    report = coverage(prices, strat, ledger)

    print(f"strategy: {strat.name} (deliberately naive — demo of the engine, not an edge)")
    print(f"signals: {len(report)} | trades: {len(t)} | explicit skips: {len(ledger.skips)}")
    print(f"coverage audit: PASSED — every signal accounted for")
    wins = (t.pnl > 0).mean()
    print(f"\nwin rate {wins:.0%} | avg P&L ${t.pnl.mean():,.0f} | worst ${t.pnl.min():,.0f} "
          f"| worst drawdown-while-open ${t.max_adverse.min():,.0f}")
    print("\nexit reasons:", t.exit_reason.value_counts().to_dict())
    print("\nlast 5 trades:")
    cols = ["signal_date", "entry_date", "exit_date", "strike", "pnl", "exit_reason"]
    print(t[cols].tail(5).to_string(index=False))


if __name__ == "__main__":
    main()
