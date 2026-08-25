"""Market data providers.

Three sources, one interface:

* ``SyntheticProvider``  - deterministic regime-switching price simulator. Runs
  with no network at all, which is what makes tests and offline demos possible.
* ``BinancePublicProvider`` - public REST klines, stdlib ``urllib`` only.
* ``CcxtProvider`` - any of the ~100 exchanges supported by ccxt, imported
  lazily so ccxt stays an optional dependency.

``CachedProvider`` wraps any of them with Brain 1 as a durable cache: an agent
that loses its network keeps trading on the last known history instead of
crashing, and every candle it ever saw stays on disk.
"""

from __future__ import annotations

import json
import logging
import math
import random
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Protocol, Sequence

from ..core.types import Candle, timeframe_ms

log = logging.getLogger(__name__)


class MarketDataProvider(Protocol):
    name: str

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> List[Candle]:
        ...


# ----------------------------------------------------------------------------
# Synthetic


class SyntheticProvider:
    """Regime-switching geometric brownian motion with fat tails.

    Not a claim about real markets - it exists so the whole agent (evolution,
    memory, risk, execution) can be exercised deterministically and offline.
    """

    name = "synthetic"

    REGIMES = {
        # name: (drift per bar, vol per bar, mean persistence in bars)
        "bull": (0.0016, 0.012, 180),
        "bear": (-0.0014, 0.016, 120),
        "chop": (0.0000, 0.008, 220),
        "crash": (-0.0090, 0.045, 14),
    }

    def __init__(self, seed: int = 7, start_price: float = 30_000.0) -> None:
        self.seed = seed
        self.start_price = start_price
        self._cache: Dict[tuple, List[Candle]] = {}

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> List[Candle]:
        # Cached so repeated calls inside one process return the identical
        # series; a replay must not shift under the agent's feet.
        key = (symbol, timeframe, limit)
        if key not in self._cache:
            self._cache[key] = self._generate(symbol, timeframe, limit)
        return list(self._cache[key])

    def _generate(self, symbol: str, timeframe: str, limit: int) -> List[Candle]:
        step = timeframe_ms(timeframe)
        now = int(time.time() * 1000) // step * step
        start = now - step * limit
        rng = random.Random(f"{self.seed}:{symbol}:{timeframe}")
        price = self.start_price
        regime = "chop"
        candles: List[Candle] = []
        for i in range(limit):
            drift, vol, persistence = self.REGIMES[regime]
            if rng.random() < 1.0 / persistence:
                regime = rng.choices(
                    list(self.REGIMES), weights=[0.36, 0.26, 0.34, 0.04], k=1
                )[0]
            shock = rng.gauss(0.0, 1.0)
            if rng.random() < 0.01:  # fat tail
                shock *= 3.5
            ret = drift + vol * shock
            open_price = price
            close = max(1e-6, open_price * math.exp(ret))
            wick = abs(rng.gauss(0.0, vol)) * open_price
            high = max(open_price, close) + wick
            low = max(1e-9, min(open_price, close) - wick)
            volume = abs(rng.gauss(1000.0, 250.0)) * (1.0 + abs(ret) * 40.0)
            candles.append(
                Candle(start + i * step, open_price, high, low, close, volume)
            )
            price = close
        return candles


# ----------------------------------------------------------------------------
# Binance public REST


class BinancePublicProvider:
    """Public klines endpoint. No API key, no dependencies, read-only."""

    name = "binance"
    BASE = "https://api.binance.com/api/v3/klines"
    MAX_PER_CALL = 1000

    def __init__(self, timeout: float = 15.0, retries: int = 3) -> None:
        self.timeout = timeout
        self.retries = retries

    @staticmethod
    def to_exchange_symbol(symbol: str) -> str:
        return symbol.replace("/", "").replace("-", "").upper()

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> List[Candle]:
        step = timeframe_ms(timeframe)
        pair = self.to_exchange_symbol(symbol)
        remaining = limit
        end_time: Optional[int] = None
        chunks: List[List[Candle]] = []
        while remaining > 0:
            take = min(remaining, self.MAX_PER_CALL)
            url = f"{self.BASE}?symbol={pair}&interval={timeframe}&limit={take}"
            if end_time is not None:
                url += f"&endTime={end_time}"
            rows = self._get(url)
            if not rows:
                break
            batch = [Candle.from_row(r) for r in rows]
            chunks.append(batch)
            remaining -= len(batch)
            end_time = batch[0].ts - step
            if len(batch) < take:
                break
        out: List[Candle] = []
        for batch in reversed(chunks):
            out.extend(batch)
        out.sort(key=lambda c: c.ts)
        return _dedupe(out)[-limit:]

    def _get(self, url: str) -> List[list]:
        last_error: Optional[Exception] = None
        for attempt in range(self.retries):
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "self-evolving-trader/1.0"}
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode())
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                last_error = exc
                sleep_for = 2.0**attempt
                log.warning("binance fetch failed (%s), retrying in %.0fs", exc, sleep_for)
                time.sleep(sleep_for)
        raise ConnectionError(f"binance request failed after {self.retries} tries: {last_error}")


# ----------------------------------------------------------------------------
# ccxt (optional)


class CcxtProvider:
    """Any ccxt exchange. ``pip install ccxt`` to enable."""

    name = "ccxt"

    def __init__(self, exchange_id: str = "binance", params: Optional[Dict] = None) -> None:
        try:
            import ccxt  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional path
            raise ImportError(
                "provider 'ccxt' needs the ccxt package: pip install ccxt"
            ) from exc
        if not hasattr(ccxt, exchange_id):
            raise ValueError(f"ccxt has no exchange {exchange_id!r}")
        self.exchange = getattr(ccxt, exchange_id)({"enableRateLimit": True, **(params or {})})

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> List[Candle]:
        step = timeframe_ms(timeframe)
        since = int(time.time() * 1000) - step * (limit + 2)
        rows = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)
        return _dedupe([Candle.from_row(r) for r in rows])[-limit:]


# ----------------------------------------------------------------------------
# Cache wrapper


class CachedProvider:
    """Persist every candle in Brain 1 and survive network outages."""

    def __init__(self, inner: MarketDataProvider, store) -> None:
        self.inner = inner
        self.store = store
        self.name = f"cached:{getattr(inner, 'name', 'unknown')}"

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> List[Candle]:
        try:
            fresh = self.inner.fetch_ohlcv(symbol, timeframe, limit)
            if fresh:
                self.store.save_candles(symbol, timeframe, fresh)
        except Exception as exc:  # network trouble must not stop the agent
            log.warning("live fetch failed (%s); falling back to cached history", exc)
        return self.store.load_candles(symbol, timeframe, limit)


def _dedupe(candles: Sequence[Candle]) -> List[Candle]:
    seen: Dict[int, Candle] = {}
    for c in candles:
        seen[c.ts] = c
    return [seen[ts] for ts in sorted(seen)]


def make_provider(cfg, store=None) -> MarketDataProvider:
    if cfg.provider == "synthetic":
        provider: MarketDataProvider = SyntheticProvider(seed=cfg.seed)
    elif cfg.provider == "binance":
        provider = BinancePublicProvider()
    elif cfg.provider == "ccxt":
        provider = CcxtProvider(cfg.exchange)
    else:  # pragma: no cover - Config.validate rejects this first
        raise ValueError(f"unknown provider {cfg.provider!r}")
    if store is not None:
        return CachedProvider(provider, store)
    return provider
