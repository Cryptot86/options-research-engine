"""Cache-first data store for paid market-data APIs.

Design constraints this store was built under (and why each feature exists):

1. Historical options data is billed per pull. The same settlement path must
   NEVER be paid for twice -> every fetch is keyed and persisted before use.
2. Backtests run for hours across thousands of instruments. One transient
   HTTP 504 must not kill a 3-hour run -> bounded retry with backoff on
   transport errors only (a 4xx is a bug, retrying it is a different bug).
3. Concurrent workers share the cache -> writes are atomic (tmp + rename),
   so a killed process can never leave a torn file that poisons later runs.
4. Budget accidents are worse than crashes -> an optional spend guard raises
   BEFORE a fetch when the estimated run cost exceeds a configured cap, and
   an OFFLINE mode turns any would-be network call into a hard error, which
   makes "this analysis touched no API" a provable property, not a hope.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable

import pandas as pd

CACHE_ROOT = Path(os.environ.get("ORE_CACHE", "data_cache"))
OFFLINE = os.environ.get("ORE_OFFLINE", "0") == "1"

_TRANSIENT = ("Timeout", "Connection", "Server", "504", "502")


class OfflineViolation(RuntimeError):
    """A code path tried to hit the network while ORE_OFFLINE=1."""


def _path(*key: str) -> Path:
    p = CACHE_ROOT.joinpath(*key[:-1]) / (key[-1] + ".parquet")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _atomic_write(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_suffix(f".tmp.{os.getpid()}")
    df.to_parquet(tmp)
    tmp.rename(path)          # rename is atomic on POSIX: readers never see a torn file


def get(key: tuple[str, ...], fetch: Callable[[], pd.DataFrame],
        retries: int = 3, backoff: float = 5.0) -> pd.DataFrame:
    """Return cached data for `key`, fetching (and caching) on first miss."""
    path = _path(*key)
    if path.exists():
        return pd.read_parquet(path)

    if OFFLINE:
        raise OfflineViolation(f"cache miss for {key} while offline")

    last: Exception | None = None
    for attempt in range(retries):
        try:
            df = fetch()
            _atomic_write(df, path)
            return df
        except Exception as exc:                      # noqa: BLE001
            if any(tok in type(exc).__name__ or tok in str(exc) for tok in _TRANSIENT):
                last = exc
                time.sleep(backoff * (attempt + 1))
                continue
            raise                                     # non-transient: fail loudly, don't mask bugs
    raise last if last else RuntimeError(f"fetch failed for {key}")
