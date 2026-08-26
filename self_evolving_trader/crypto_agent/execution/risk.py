"""Risk manager - the part that is allowed to say no.

Evolution optimises for return; this module is the fixed constitution it cannot
mutate. Limits are checked before every order and the state behind them
(drawdown kill switch, daily loss, trade count, cooldown) lives in Brain 1, so a
halted agent stays halted across restarts instead of forgetting its own
accident.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..config import Config
from ..core.types import Signal, Trade, timeframe_ms
from ..brain.hippocampus import Hippocampus
from ..strategy.backtest import position_size

RISK_STATE_KEY = "risk.state"


@dataclass
class RiskDecision:
    approved: bool
    qty: float
    reason: str

    def __bool__(self) -> bool:  # pragma: no cover - convenience
        return self.approved


class RiskManager:
    def __init__(self, cfg: Config, brain: Hippocampus) -> None:
        self.cfg = cfg
        self.brain = brain
        self.state: Dict[str, Any] = brain.get_state(RISK_STATE_KEY) or {
            "halted": False,
            "halt_reason": "",
            "day": _utc_day(),
            "day_start_equity": cfg.start_cash,
            "trades_today": 0,
            "cooldown_until": 0,
            "peak_equity": cfg.start_cash,
        }

    # ------------------------------------------------------------------
    def _save(self) -> None:
        self.brain.set_state(RISK_STATE_KEY, self.state)

    def _roll_day(self, equity: float, now_ms: Optional[int] = None) -> None:
        today = _utc_day(now_ms)
        if self.state.get("day") != today:
            self.state.update({"day": today, "day_start_equity": equity, "trades_today": 0})
            self._save()

    @property
    def halted(self) -> bool:
        return bool(self.state.get("halted"))

    def halt(self, reason: str) -> None:
        self.state["halted"] = True
        self.state["halt_reason"] = reason
        self._save()
        self.brain.log_event("halt", reason, level="ERROR")

    def resume(self) -> None:
        """Manual restart after a kill switch. Never called automatically -
        an agent that can un-halt itself has no kill switch."""
        self.state.update({"halted": False, "halt_reason": ""})
        self.state["day_start_equity"] = self.state.get("peak_equity", self.cfg.start_cash)
        self._save()
        self.brain.log_event("resume", "risk halt cleared by operator")

    # ------------------------------------------------------------------
    def observe_equity(self, equity: float, now_ms: Optional[int] = None) -> None:
        """Update the drawdown watermark and trip the kill switch if breached."""
        self._roll_day(equity, now_ms)
        peak = max(float(self.state.get("peak_equity", equity)), equity)
        self.state["peak_equity"] = peak
        drawdown = (peak - equity) / peak if peak > 0 else 0.0
        self._save()
        if drawdown >= self.cfg.max_drawdown_pct and not self.halted:
            self.halt(
                f"max drawdown breached: {drawdown * 100:.1f}% from peak {peak:.2f} "
                f"(limit {self.cfg.max_drawdown_pct * 100:.1f}%)"
            )

    def daily_loss_pct(self, equity: float) -> float:
        start = float(self.state.get("day_start_equity") or equity)
        if start <= 0:
            return 0.0
        return max(0.0, (start - equity) / start)

    # ------------------------------------------------------------------
    def check_entry(
        self,
        equity: float,
        cash: float,
        price: float,
        stop: Optional[float],
        signal: Signal,
        risk_scale: float,
        size_mult: float = 1.0,
        now_ms: Optional[int] = None,
        symbol: Optional[str] = None,
        open_positions: int = 0,
    ) -> RiskDecision:
        now = now_ms if now_ms is not None else int(time.time() * 1000)
        self._roll_day(equity, now)
        market = symbol or self.cfg.symbol

        if self.halted:
            return RiskDecision(False, 0.0, f"halted: {self.state.get('halt_reason')}")
        if signal.direction == 0:
            return RiskDecision(False, 0.0, "no signal")
        if signal.direction < 0 and not self.cfg.allow_short:
            return RiskDecision(False, 0.0, "shorting disabled by config")
        if open_positions >= self.cfg.max_open_positions:
            return RiskDecision(
                False, 0.0,
                f"already holding {open_positions} positions "
                f"(cap {self.cfg.max_open_positions})")
        # A loss cools down the coin that produced it, not the whole book: one
        # bad trade in SOL is no reason to stand aside in BTC.
        if now < int(self._cooldowns().get(market, 0)):
            return RiskDecision(False, 0.0, f"cooling down after a loss in {market}")
        if int(self.state.get("trades_today", 0)) >= self.cfg.max_trades_per_day:
            return RiskDecision(False, 0.0, "daily trade cap reached")

        daily_loss = self.daily_loss_pct(equity)
        if daily_loss >= self.cfg.max_daily_loss_pct:
            return RiskDecision(
                False, 0.0, f"daily loss limit hit ({daily_loss * 100:.1f}%)"
            )

        qty = position_size(equity, price, stop, self.cfg, risk_scale, cash=cash if signal.direction > 0 else None)
        qty *= max(0.0, size_mult)
        if qty * price < self.cfg.min_notional:
            return RiskDecision(False, 0.0, "size below minimum notional")
        if qty * price > equity * self.cfg.max_position_pct * 1.0001:
            qty = equity * self.cfg.max_position_pct / price
        return RiskDecision(True, qty, "within risk limits")

    # ------------------------------------------------------------------
    def _cooldowns(self) -> Dict[str, int]:
        book = self.state.get("cooldowns")
        if isinstance(book, dict):
            return book
        legacy = int(self.state.get("cooldown_until", 0) or 0)
        return {self.cfg.symbol: legacy} if legacy else {}

    def on_trade_closed(self, trade: Trade, equity: float) -> None:
        self.state["trades_today"] = int(self.state.get("trades_today", 0)) + 1
        if trade.pnl < 0 and self.cfg.cooldown_bars_after_loss > 0:
            cooldowns = self._cooldowns()
            cooldowns[trade.symbol] = trade.exit_ts + timeframe_ms(
                self.cfg.timeframe
            ) * self.cfg.cooldown_bars_after_loss
            self.state["cooldowns"] = cooldowns
        self._save()
        self.observe_equity(equity, trade.exit_ts)
        if self.daily_loss_pct(equity) >= self.cfg.max_daily_loss_pct:
            self.brain.log_event(
                "risk_pause",
                f"daily loss limit reached ({self.daily_loss_pct(equity) * 100:.1f}%); "
                "no new entries until the next UTC day",
                level="WARNING",
            )

    def snapshot(self) -> Dict[str, Any]:
        return dict(self.state)


def _utc_day(now_ms: Optional[int] = None) -> str:
    """The trading day of a *market* timestamp.

    Deriving the day from the bar being processed rather than from the wall
    clock keeps daily limits meaningful during replays and backfills, and makes
    them testable without freezing time.
    """
    if now_ms is None:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return datetime.fromtimestamp(now_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
