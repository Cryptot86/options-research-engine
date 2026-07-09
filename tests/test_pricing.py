"""Sanity tests for the pricing module — the invariants a pricing engine must
never violate, whatever the market does."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ore.pricing import black76, delta, implied_vol, strike_for_delta


def test_put_call_parity():
    f, k, t, sigma = 100.0, 95.0, 0.25, 0.3
    call = black76(f, k, t, sigma, kind="call")
    put = black76(f, k, t, sigma, kind="put")
    assert abs((call - put) - (f - k)) < 1e-9        # C - P = F - K (r=0)


def test_iv_round_trip():
    f, k, t, sigma = 4500.0, 4200.0, 40 / 365, 0.22
    price = black76(f, k, t, sigma, kind="put")
    recovered = implied_vol(price, f, k, t, kind="put")
    assert recovered is not None and abs(recovered - sigma) < 1e-4


def test_strike_for_delta_round_trip():
    f, t, sigma, target = 100.0, 40 / 365, 0.35, 0.16
    k = strike_for_delta(f, t, sigma, target, kind="put")
    assert k < f                                      # a 16d put is OTM
    assert abs(abs(delta(f, k, t, sigma, kind="put")) - target) < 1e-6


def test_expiry_day_is_intrinsic():
    assert black76(90.0, 100.0, 0.0, 0.3, kind="put") == 10.0
    assert black76(110.0, 100.0, 0.0, 0.3, kind="put") == 0.0


def test_no_vol_no_root():
    # price below intrinsic must return None, not a garbage vol
    assert implied_vol(0.5, 90.0, 100.0, 0.1, kind="put") is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
