"""Technical indicators in pure Python.

Each function takes a list of floats (or candles) and returns a list of the same
length, padded at the front with ``None`` until the indicator has enough data.
Keeping the alignment identical to the input is what lets the backtester and the
live loop share one code path.
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence

from ..core.types import Candle

Series = List[Optional[float]]


def sma(values: Sequence[float], length: int) -> Series:
    if length <= 0:
        raise ValueError("length must be positive")
    out: Series = [None] * len(values)
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= length:
            running -= values[i - length]
        if i >= length - 1:
            out[i] = running / length
    return out


def ema(values: Sequence[float], length: int) -> Series:
    if length <= 0:
        raise ValueError("length must be positive")
    out: Series = [None] * len(values)
    if len(values) < length:
        return out
    alpha = 2.0 / (length + 1.0)
    prev = sum(values[:length]) / length  # seed with an SMA, as most charts do
    out[length - 1] = prev
    for i in range(length, len(values)):
        prev = values[i] * alpha + prev * (1.0 - alpha)
        out[i] = prev
    return out


def rsi(values: Sequence[float], length: int = 14) -> Series:
    """Wilder's RSI."""
    out: Series = [None] * len(values)
    if len(values) <= length:
        return out
    gains = 0.0
    losses = 0.0
    for i in range(1, length + 1):
        change = values[i] - values[i - 1]
        gains += max(change, 0.0)
        losses += max(-change, 0.0)
    avg_gain = gains / length
    avg_loss = losses / length
    out[length] = _rsi_from(avg_gain, avg_loss)
    for i in range(length + 1, len(values)):
        change = values[i] - values[i - 1]
        avg_gain = (avg_gain * (length - 1) + max(change, 0.0)) / length
        avg_loss = (avg_loss * (length - 1) + max(-change, 0.0)) / length
        out[i] = _rsi_from(avg_gain, avg_loss)
    return out


def _rsi_from(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def true_range(candles: Sequence[Candle]) -> Series:
    out: Series = [None] * len(candles)
    for i, c in enumerate(candles):
        if i == 0:
            out[i] = c.high - c.low
        else:
            prev_close = candles[i - 1].close
            out[i] = max(c.high - c.low, abs(c.high - prev_close), abs(c.low - prev_close))
    return out


def atr(candles: Sequence[Candle], length: int = 14) -> Series:
    """Wilder's ATR (smoothed true range)."""
    trs = true_range(candles)
    out: Series = [None] * len(candles)
    if len(candles) < length + 1:
        return out
    window = [t for t in trs[1: length + 1] if t is not None]
    if len(window) < length:
        return out
    prev = sum(window) / length
    out[length] = prev
    for i in range(length + 1, len(candles)):
        tr = trs[i] or 0.0
        prev = (prev * (length - 1) + tr) / length
        out[i] = prev
    return out


def stdev(values: Sequence[float], length: int) -> Series:
    out: Series = [None] * len(values)
    if length < 2:
        raise ValueError("length must be >= 2")
    for i in range(length - 1, len(values)):
        window = values[i - length + 1: i + 1]
        mean = sum(window) / length
        var = sum((v - mean) ** 2 for v in window) / (length - 1)
        out[i] = math.sqrt(var)
    return out


def bollinger_z(values: Sequence[float], length: int = 20) -> Series:
    """How many standard deviations price sits from its own mean."""
    mid = sma(values, length)
    sd = stdev(values, length)
    out: Series = [None] * len(values)
    for i in range(len(values)):
        if mid[i] is None or sd[i] is None or sd[i] == 0:
            continue
        out[i] = (values[i] - mid[i]) / sd[i]
    return out


def macd_hist(values: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Series:
    fast_line = ema(values, fast)
    slow_line = ema(values, slow)
    diff: List[float] = []
    first_valid = None
    for i in range(len(values)):
        if fast_line[i] is None or slow_line[i] is None:
            diff.append(0.0)
        else:
            if first_valid is None:
                first_valid = i
            diff.append(fast_line[i] - slow_line[i])
    out: Series = [None] * len(values)
    if first_valid is None:
        return out
    tail = diff[first_valid:]
    sig = ema(tail, signal)
    for j, s in enumerate(sig):
        if s is not None:
            out[first_valid + j] = tail[j] - s
    return out


def donchian_position(candles: Sequence[Candle], length: int = 20) -> Series:
    """Where close sits inside the N-bar range, mapped to [-1, 1]."""
    out: Series = [None] * len(candles)
    for i in range(length - 1, len(candles)):
        window = candles[i - length + 1: i + 1]
        hi = max(c.high for c in window)
        lo = min(c.low for c in window)
        if hi <= lo:
            out[i] = 0.0
            continue
        out[i] = 2.0 * (candles[i].close - lo) / (hi - lo) - 1.0
    return out


def roc(values: Sequence[float], length: int = 10) -> Series:
    out: Series = [None] * len(values)
    for i in range(length, len(values)):
        base = values[i - length]
        if base:
            out[i] = values[i] / base - 1.0
    return out


def realized_vol(values: Sequence[float], length: int = 20) -> Series:
    """Stdev of log returns over the window (per-bar, not annualised)."""
    rets: List[float] = [0.0]
    for i in range(1, len(values)):
        prev, cur = values[i - 1], values[i]
        rets.append(math.log(cur / prev) if prev > 0 and cur > 0 else 0.0)
    sd = stdev(rets, length)
    return sd


def slope(values: Sequence[float], length: int = 10) -> Series:
    """Least-squares slope over the window, normalised by the window mean."""
    out: Series = [None] * len(values)
    xs = list(range(length))
    x_mean = sum(xs) / length
    denom = sum((x - x_mean) ** 2 for x in xs)
    for i in range(length - 1, len(values)):
        window = values[i - length + 1: i + 1]
        y_mean = sum(window) / length
        if denom == 0 or y_mean == 0:
            continue
        num = sum((xs[j] - x_mean) * (window[j] - y_mean) for j in range(length))
        out[i] = (num / denom) / abs(y_mean)
    return out


def last_valid(series: Series, default: float = 0.0) -> float:
    for value in reversed(series):
        if value is not None:
            return value
    return default


def clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))
