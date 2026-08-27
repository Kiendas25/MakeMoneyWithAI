"""Turning a genome plus price history into a decision.

One rule engine serves both the backtester and the live loop. The backtester
calls ``signal_at(frame, i)`` walking forward through history; the live agent
calls it with ``i = len(candles) - 1``. There is no second implementation to
drift out of sync, which is the usual way a bot's paper results stop matching
its live ones.

Everything reads only closed candles at or before ``i``: no lookahead.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Sequence

from ..core.types import Candle, Position, Signal
from ..data import indicators as ind
from .genome import Genome

MODULES = ("trend", "macd", "breakout", "meanrev", "rsi")


@dataclass
class Frame:
    """All indicator series a genome needs, computed once over the history."""

    candles: Sequence[Candle]
    ema_fast: ind.Series
    ema_slow: ind.Series
    rsi: ind.Series
    atr: ind.Series
    macd: ind.Series
    donchian: ind.Series
    bb_z: ind.Series
    vol: ind.Series
    slope: ind.Series
    warmup: int

    def __len__(self) -> int:
        return len(self.candles)


def compute_frame(genome: Genome, candles: Sequence[Candle]) -> Frame:
    closes = [c.close for c in candles]
    g = genome.genes
    warmup = max(
        int(g["ema_slow"]),
        int(g["rsi_len"]) + 1,
        int(g["atr_len"]) + 1,
        int(g["breakout_len"]),
        int(g["bb_len"]),
        int(g["vol_len"]),
        int(g["slope_len"]),
        35,  # MACD's own seeding
    ) + 1
    return Frame(
        candles=candles,
        ema_fast=ind.ema(closes, int(g["ema_fast"])),
        ema_slow=ind.ema(closes, int(g["ema_slow"])),
        rsi=ind.rsi(closes, int(g["rsi_len"])),
        atr=ind.atr(candles, int(g["atr_len"])),
        macd=ind.macd_hist(closes),
        donchian=ind.donchian_position(candles, int(g["breakout_len"])),
        bb_z=ind.bollinger_z(closes, int(g["bb_len"])),
        vol=ind.realized_vol(closes, int(g["vol_len"])),
        slope=ind.slope(closes, int(g["slope_len"])),
        warmup=warmup,
    )


def regime_at(frame: Frame, i: int) -> str:
    """A coarse, human-readable label. Brain 2 groups its lessons by this, so it
    has to be stable and few-valued rather than precise."""
    slope = frame.slope[i]
    vol = frame.vol[i]
    if slope is None or vol is None:
        return "unknown"
    if slope > 0.002:
        trend = "uptrend"
    elif slope < -0.002:
        trend = "downtrend"
    else:
        trend = "range"
    if vol > 0.035:
        vol_band = "high_vol"
    elif vol < 0.012:
        vol_band = "low_vol"
    else:
        vol_band = "mid_vol"
    return f"{trend}_{vol_band}"


def module_scores(genome: Genome, frame: Frame, i: int) -> Dict[str, float]:
    """Each module votes in [-1, 1]. Positive means "be long"."""
    g = genome.genes
    c = frame.candles[i]
    atr = frame.atr[i] or 0.0
    scores: Dict[str, float] = {m: 0.0 for m in MODULES}

    if frame.ema_fast[i] is not None and frame.ema_slow[i] is not None and atr > 0:
        scores["trend"] = math.tanh((frame.ema_fast[i] - frame.ema_slow[i]) / atr)

    if frame.macd[i] is not None and atr > 0:
        scores["macd"] = math.tanh(frame.macd[i] / atr * 2.0)

    if frame.donchian[i] is not None:
        # Sitting at the top of the range is bullish for a breakout trader.
        scores["breakout"] = ind.clamp(frame.donchian[i])

    if frame.bb_z[i] is not None:
        z = frame.bb_z[i] / max(0.1, float(g["bb_entry_z"]))
        scores["meanrev"] = ind.clamp(-math.tanh(z))  # cheap when stretched low

    if frame.rsi[i] is not None:
        r = frame.rsi[i]
        if r <= g["rsi_buy"]:
            scores["rsi"] = ind.clamp((g["rsi_buy"] - r) / max(1.0, g["rsi_buy"]))
        elif r >= g["rsi_sell"]:
            scores["rsi"] = -ind.clamp((r - g["rsi_sell"]) / max(1.0, 100.0 - g["rsi_sell"]))

    _ = c  # candle kept for future modules; silence linters without hiding intent
    return scores


def blended_score(genome: Genome, scores: Dict[str, float]) -> float:
    g = genome.genes
    weights = {m: float(g[f"w_{m}"]) for m in MODULES}
    total = sum(weights.values())
    if total <= 0:
        return 0.0
    return ind.clamp(sum(scores[m] * weights[m] for m in MODULES) / total)


def signal_at(genome: Genome, frame: Frame, i: int) -> Signal:
    regime = regime_at(frame, i)
    if i < frame.warmup:
        return Signal(0, 0.0, "warming up", {}, regime)

    scores = module_scores(genome, frame, i)
    score = blended_score(genome, scores)
    g = genome.genes

    vol = frame.vol[i]
    if vol is not None and vol > float(g["max_vol"]):
        return Signal(
            0,
            score,
            f"volatility {vol:.3f} above genome ceiling {g['max_vol']:.3f}",
            {**scores, "vol": vol},
            regime,
        )

    threshold = float(g["entry_threshold"])
    direction = 0
    if score >= threshold:
        direction = 1
    elif score <= -threshold and bool(g["allow_short"]):
        direction = -1

    lead = max(scores.items(), key=lambda kv: abs(kv[1]))
    reason = (
        f"{'long' if direction > 0 else 'short' if direction < 0 else 'stand aside'} "
        f"score {score:+.2f} vs {threshold:.2f}, led by {lead[0]} ({lead[1]:+.2f})"
    )
    features = {**scores, "score": score, "vol": vol or 0.0, "atr": frame.atr[i] or 0.0}
    return Signal(direction, score, reason, features, regime)


def initial_stops(genome: Genome, frame: Frame, i: int, entry_price: float,
                  direction: int) -> tuple[Optional[float], Optional[float]]:
    atr = frame.atr[i]
    if not atr or atr <= 0:
        return None, None
    g = genome.genes
    stop_dist = float(g["stop_atr_mult"]) * atr
    tp_dist = float(g["tp_atr_mult"]) * atr
    if direction > 0:
        return entry_price - stop_dist, entry_price + tp_dist
    return entry_price + stop_dist, entry_price - tp_dist


def update_trailing_stop(genome: Genome, frame: Frame, i: int, position: Position) -> Optional[float]:
    """Ratchet the stop toward price using bar ``i``'s close; never loosen it.

    The close of bar ``i`` is only known once bar ``i`` has finished
    printing, so the level this returns must not be tested against bar
    ``i`` itself - callers must check ``exit_reason`` against the stop
    already in force *before* calling this, and only store this return
    value for bar ``i + 1`` onward. Testing bar i's low/high against a stop
    this same call just moved is lookahead: it lets the exit see the end of
    the bar before deciding what happened during the bar.
    """
    mult = float(genome.genes["trail_atr_mult"])
    atr = frame.atr[i]
    if mult <= 0 or not atr:
        return position.stop
    close = frame.candles[i].close
    if position.qty > 0:
        candidate = close - mult * atr
        return candidate if position.stop is None else max(position.stop, candidate)
    candidate = close + mult * atr
    return candidate if position.stop is None else min(position.stop, candidate)


def exit_reason(genome: Genome, frame: Frame, i: int, position: Position,
                signal: Signal) -> Optional[str]:
    """Why this position should close now, or ``None`` to hold.

    Checked against the *current* bar's extremes, with the stop taking priority
    over the target when a single bar spans both - the pessimistic assumption,
    because assuming the good fill is how backtests learn to lie.

    ``position.stop`` must be the level that was already in force before bar
    ``i`` opened - i.e. whatever ``update_trailing_stop`` returned for bar
    ``i - 1``, not a ratchet computed from bar ``i``'s own close. Checking a
    bar against a stop derived from that same bar's close is lookahead: the
    stop would be "known" before the bar's low/high happened, when it was
    really only known after.
    """
    candle = frame.candles[i]
    long = position.qty > 0

    if position.stop is not None:
        hit = candle.low <= position.stop if long else candle.high >= position.stop
        if hit:
            # A stop that has ratcheted past the entry is a profit-taking exit,
            # not a loss. Brain 2 groups its lessons by this label, so blurring
            # the two would teach the agent that its stops are too tight when
            # they are in fact working.
            locked_in = position.stop > position.entry_price if long else position.stop < position.entry_price
            return "trailing_stop" if locked_in else "stop_loss"
    if position.take_profit is not None:
        if long and candle.high >= position.take_profit:
            return "take_profit"
        if not long and candle.low <= position.take_profit:
            return "take_profit"
    if position.bars_held >= int(genome.genes["max_bars_held"]):
        return "time_stop"

    exit_threshold = float(genome.genes["exit_threshold"])
    if long and signal.score < -exit_threshold:
        return "signal_flip"
    if not long and signal.score > exit_threshold:
        return "signal_flip"
    return None


def exit_price_for(reason: str, position: Position, candle: Candle) -> float:
    """Where a given exit reason actually fills."""
    if reason in ("stop_loss", "trailing_stop") and position.stop is not None:
        # Gaps fill at the open, not at the stop we hoped for.
        return min(position.stop, candle.open) if position.qty > 0 else max(position.stop, candle.open)
    if reason == "take_profit" and position.take_profit is not None:
        return position.take_profit
    return candle.close


def warmup_bars(genome: Genome) -> int:
    g = genome.genes
    return max(int(g["ema_slow"]), int(g["breakout_len"]), int(g["bb_len"]), 40) + 2
