"""Core value types shared by every layer of the agent.

Everything here is plain stdlib so the agent can run in a bare container.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

MS_PER_MINUTE = 60_000

TIMEFRAME_MS: Dict[str, int] = {
    "1m": 1 * MS_PER_MINUTE,
    "3m": 3 * MS_PER_MINUTE,
    "5m": 5 * MS_PER_MINUTE,
    "15m": 15 * MS_PER_MINUTE,
    "30m": 30 * MS_PER_MINUTE,
    "1h": 60 * MS_PER_MINUTE,
    "2h": 120 * MS_PER_MINUTE,
    "4h": 240 * MS_PER_MINUTE,
    "6h": 360 * MS_PER_MINUTE,
    "12h": 720 * MS_PER_MINUTE,
    "1d": 1440 * MS_PER_MINUTE,
}


def timeframe_ms(timeframe: str) -> int:
    try:
        return TIMEFRAME_MS[timeframe]
    except KeyError as exc:  # pragma: no cover - guard rail
        raise ValueError(f"unsupported timeframe {timeframe!r}") from exc


def bars_per_year(timeframe: str) -> float:
    return (365.0 * 24.0 * 60.0 * MS_PER_MINUTE) / float(timeframe_ms(timeframe))


@dataclass(frozen=True)
class Candle:
    ts: int  # open time, epoch milliseconds
    open: float
    high: float
    low: float
    close: float
    volume: float

    def as_row(self) -> List[float]:
        return [self.ts, self.open, self.high, self.low, self.close, self.volume]

    @staticmethod
    def from_row(row) -> "Candle":
        return Candle(
            ts=int(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
        )


@dataclass
class Signal:
    """A strategy's opinion at one point in time."""

    direction: int  # -1 short, 0 flat, +1 long
    score: float  # blended conviction in [-1, 1]
    reason: str
    features: Dict[str, float] = field(default_factory=dict)
    regime: str = "unknown"

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


@dataclass
class Fill:
    ts: int
    side: str  # "buy" | "sell"
    qty: float
    price: float
    fee: float


@dataclass
class Position:
    symbol: str
    qty: float  # signed: >0 long, <0 short
    entry_price: float
    entry_ts: int
    stop: Optional[float] = None
    take_profit: Optional[float] = None
    genome_id: str = ""
    regime: str = "unknown"
    bars_held: int = 0

    @property
    def side(self) -> str:
        return "long" if self.qty > 0 else "short"

    def unrealized(self, price: float) -> float:
        return (price - self.entry_price) * self.qty

    def unrealized_pct(self, price: float) -> float:
        if self.entry_price <= 0:
            return 0.0
        return (price / self.entry_price - 1.0) * (1.0 if self.qty > 0 else -1.0)


@dataclass
class Trade:
    """A round trip, written to Brain 1 and distilled into Brain 2."""

    symbol: str
    side: str
    qty: float
    entry_ts: int
    entry_price: float
    exit_ts: int
    exit_price: float
    pnl: float
    pnl_pct: float
    fees: float
    reason_open: str
    reason_close: str
    genome_id: str
    regime: str
    id: Optional[int] = None

    def summary(self) -> str:
        verdict = "win" if self.pnl > 0 else "loss"
        return (
            f"{self.side} {self.symbol} in regime '{self.regime}' opened on "
            f"'{self.reason_open}' closed on '{self.reason_close}' -> {verdict} "
            f"{self.pnl_pct * 100:.2f}% (genome {self.genome_id})"
        )


@dataclass
class BacktestMetrics:
    total_return: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    trades: int = 0
    avg_trade_pct: float = 0.0
    exposure: float = 0.0
    final_equity: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


@dataclass
class BacktestResult:
    metrics: BacktestMetrics
    equity_curve: List[float] = field(default_factory=list)
    trades: List[Trade] = field(default_factory=list)

    @property
    def fitness(self) -> float:
        return fitness_score(self.metrics)


def fitness_score(m: BacktestMetrics, min_trades: int = 3) -> float:
    """Risk-adjusted score used as the GA's selection pressure.

    Sharpe is the backbone; drawdown is punished multiplicatively so a strategy
    cannot buy its way to a high score with a single lucky, deep-underwater run.
    Strategies that barely trade are pushed down: a two-trade sample proves
    nothing and would otherwise dominate the population by luck.
    """
    if m.trades < min_trades:
        # Still ordered by return so the population can climb out of "never trades".
        return -1.0 + 0.01 * math.tanh(m.total_return)
    dd_penalty = 1.0 / (1.0 + 4.0 * max(0.0, m.max_drawdown))
    churn_penalty = 1.0 + 0.002 * max(0, m.trades - 200)
    base = m.sharpe if math.isfinite(m.sharpe) else 0.0
    base = max(-10.0, min(10.0, base))
    # A dazzling Sharpe over eight trades is mostly luck. Shrinking it toward
    # zero by sample size stops the population from converging on whichever
    # genome got the best small-sample draw.
    sample_confidence = m.trades / (m.trades + 10.0)
    return (base * dd_penalty * sample_confidence + 0.5 * math.tanh(m.total_return)) / churn_penalty


@dataclass
class Lesson:
    """A natural-language memory written into Brain 2."""

    text: str
    kind: str = "reflection"  # trade | reflection | regime | evolution
    weight: float = 1.0
    meta: Dict[str, Any] = field(default_factory=dict)
