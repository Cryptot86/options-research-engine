"""Backtest engine: mechanical execution of a signal against option prices.

The engine enforces the discipline that makes results trustworthy:

- D+1 execution: a signal computed on day D's close trades at day D+1's
  prices. Backtests that fill on the signal bar are quietly clairvoyant.
- Mechanical exits only (profit target / time stop). If a rule isn't in
  code, it wasn't tested, and untested rules don't ship.
- Every signal produces a row — either a trade or an explicit skip with a
  reason. Silent drops are how survivorship bias gets into "clean" results
  (see ore.audit).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

import pandas as pd


class Strategy(Protocol):
    """A strategy marks entry days on a daily price frame."""
    name: str

    def signals(self, prices: pd.DataFrame) -> pd.Series:
        """Boolean series indexed like `prices`: True = signal at this close."""
        ...


@dataclass
class TradeConfig:
    target_delta: float = 0.16
    dte_target: int = 40
    take_profit_pct: float = 0.50     # close at 50% of collected credit
    manage_dte: int = 21              # or at 21 DTE, whichever comes first
    kind: str = "put"


@dataclass
class Trade:
    signal_date: pd.Timestamp
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp | None = None
    strike: float = float("nan")
    credit: float = float("nan")
    pnl: float = float("nan")
    exit_reason: str = ""
    max_adverse: float = 0.0          # worst mark-to-market while open


@dataclass
class Ledger:
    """Trades AND skips. A backtest that can't explain every signal is
    a backtest you can't trust."""
    trades: list[Trade] = field(default_factory=list)
    skips: list[tuple[pd.Timestamp, str]] = field(default_factory=list)

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame([vars(t) for t in self.trades])


def run(prices: pd.DataFrame, strategy: Strategy, cfg: TradeConfig,
        price_option: Callable[[pd.Timestamp, TradeConfig], "OptionPath | None"],
        ) -> Ledger:
    """Walk the price history; enter D+1 after each signal; manage mechanically.

    `price_option(entry_date, cfg)` abstracts the data source: the private
    research build resolves a real listed contract and its daily settlement
    path; the demo synthesizes one. The engine cannot tell the difference,
    which is the point — execution discipline is identical either way.
    """
    ledger = Ledger()
    idx = prices.index
    sig = strategy.signals(prices)
    open_until: pd.Timestamp | None = None

    for day in idx[sig]:
        pos = idx.searchsorted(day) + 1               # D+1: trade tomorrow, not today
        if pos >= len(idx):
            ledger.skips.append((day, "signal_on_last_bar"))
            continue
        entry = idx[pos]
        if open_until is not None and entry <= open_until:
            ledger.skips.append((day, "position_open"))  # one position at a time
            continue

        path = price_option(entry, cfg)
        if path is None:
            ledger.skips.append((day, "no_contract"))
            continue

        trade = Trade(signal_date=day, entry_date=entry,
                      strike=path.strike, credit=path.entry_price)
        worst = 0.0
        for dt, mark, dte in path.walk():
            worst = min(worst, trade.credit - mark)
            if mark <= trade.credit * (1 - cfg.take_profit_pct):
                trade.exit_date, trade.exit_reason = dt, "take_profit"
                trade.pnl = (trade.credit - mark) * path.multiplier
                break
            if dte <= cfg.manage_dte:
                trade.exit_date, trade.exit_reason = dt, "time_exit"
                trade.pnl = (trade.credit - mark) * path.multiplier
                break
        else:                                          # path ended: settle at expiry
            trade.exit_date, trade.exit_reason = path.last_date, "expiry"
            trade.pnl = (trade.credit - path.settle_value()) * path.multiplier
        trade.max_adverse = worst * path.multiplier
        ledger.trades.append(trade)
        open_until = trade.exit_date

    return ledger


class OptionPath(Protocol):
    """Daily marks for one contract from entry to expiry."""
    strike: float
    entry_price: float
    multiplier: float
    last_date: pd.Timestamp

    def walk(self):  # yields (date, mark, dte)
        ...

    def settle_value(self) -> float:
        ...
