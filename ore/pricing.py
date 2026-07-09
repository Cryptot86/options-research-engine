"""Option pricing: Black-Scholes (equities) and Black-76 (futures options).

Everything here is standard textbook math, implemented the way a backtesting
engine needs it: vectorizable, defensive about edge cases (expiry day, zero
vol), and invertible (price -> implied vol via Brent's method).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.optimize import brentq
from scipy.stats import norm


def _d1_d2(f: float, k: float, t: float, sigma: float) -> tuple[float, float]:
    sig_sqrt_t = sigma * math.sqrt(t)
    d1 = (math.log(f / k) + 0.5 * sigma * sigma * t) / sig_sqrt_t
    return d1, d1 - sig_sqrt_t


def black76(f: float, k: float, t: float, sigma: float, r: float = 0.0,
            kind: str = "put") -> float:
    """Black-76 price of a European option on a forward/future."""
    if t <= 0 or sigma <= 0:
        intrinsic = max(k - f, 0.0) if kind == "put" else max(f - k, 0.0)
        return intrinsic
    d1, d2 = _d1_d2(f, k, t, sigma)
    df = math.exp(-r * t)
    if kind == "put":
        return df * (k * norm.cdf(-d2) - f * norm.cdf(-d1))
    return df * (f * norm.cdf(d1) - k * norm.cdf(d2))


def delta(f: float, k: float, t: float, sigma: float, kind: str = "put") -> float:
    """Black-76 delta (forward delta, no rate carry)."""
    if t <= 0 or sigma <= 0:
        if kind == "put":
            return -1.0 if k > f else 0.0
        return 1.0 if f > k else 0.0
    d1, _ = _d1_d2(f, k, t, sigma)
    return norm.cdf(d1) - 1.0 if kind == "put" else norm.cdf(d1)


def strike_for_delta(f: float, t: float, sigma: float, target_delta: float,
                     kind: str = "put") -> float:
    """Invert delta -> strike analytically.

    Used to place e.g. a "16-delta put" without scanning the whole chain:
    snap the analytic strike to the nearest listed one afterwards.
    """
    if kind == "put":
        z = norm.ppf(1.0 - target_delta)   # target_delta given as +0.16
    else:
        z = norm.ppf(target_delta)
    sig_sqrt_t = sigma * math.sqrt(t)
    return f * math.exp(0.5 * sigma * sigma * t - z * sig_sqrt_t)


def implied_vol(price: float, f: float, k: float, t: float, r: float = 0.0,
                kind: str = "put", lo: float = 1e-4, hi: float = 5.0) -> float | None:
    """Brent-solve Black-76 for sigma. Returns None when no root exists
    (price below intrinsic, stale marks, crossed quotes...)."""
    if t <= 0 or price <= 0:
        return None

    def objective(sigma: float) -> float:
        return black76(f, k, t, sigma, r, kind) - price

    try:
        if objective(lo) * objective(hi) > 0:
            return None
        return float(brentq(objective, lo, hi, xtol=1e-6))
    except ValueError:
        return None


@dataclass(frozen=True)
class OptionQuote:
    """A priced strike as the engine consumes it."""
    strike: float
    dte: int
    mid: float
    iv: float | None
    delta: float | None
