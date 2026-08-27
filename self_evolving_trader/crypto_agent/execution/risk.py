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
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..config import Config
from ..core.types import Candle, Signal, Trade, timeframe_ms
from ..brain.hippocampus import Hippocampus
from ..data.correlation import Correlation, cluster_symbols
from ..strategy.backtest import position_size

RISK_STATE_KEY = "risk.state"
CORRELATION_CACHE_PREFIX = "risk.correlation"


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
        an agent that can un-halt itself has no kill switch.

        Clearing ``halted`` alone is not a real resume: ``peak_equity`` would
        stay at the pre-crash high, so the very next ``observe_equity()``
        recomputes the identical drawdown and re-halts before a single order
        goes out, and ``day_start_equity`` would stay there too, so
        ``daily_loss_pct()`` instantly exceeds the daily limit as well. Both
        watermarks are re-baselined here to the current equity, so the agent
        resumes measuring from where it actually is instead of from a peak
        it will never see again.
        """
        equity = self._current_equity()
        self.state.update({
            "halted": False,
            "halt_reason": "",
            "peak_equity": equity,
            "day_start_equity": equity,
        })
        self._save()
        self.brain.log_event("resume", f"risk halt cleared by operator at equity {equity:.2f}")

    def _current_equity(self) -> float:
        """Best available estimate of current equity, for re-baselining on resume.

        Brain 1 records an equity snapshot on every cycle (see
        ``Hippocampus.record_equity``), stamped with the same reading that
        ``observe_equity()`` just saw - including the one that caused the
        halt - so the newest row is what the operator is actually looking at
        when they resume. Fall back to the last known peak, then to the
        configured starting cash, for the rare case of a resume with no
        recorded equity history at all (e.g. a fresh state in a test).
        """
        curve = self.brain.equity_curve(limit=1)
        if curve:
            return float(curve[0]["equity"])
        return float(self.state.get("peak_equity", self.cfg.start_cash))

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
        price_history: Optional[Dict[str, Sequence[Candle]]] = None,
        holdings: Optional[Dict[str, float]] = None,
    ) -> RiskDecision:
        """Approve or refuse a new entry, sizing it within every active limit.

        ``price_history`` and ``holdings`` are optional and only needed to
        judge correlated-cluster exposure: a map of symbol -> recent candles
        (enough to measure correlation, typically ``cfg.correlation_window``
        bars) and a map of symbol -> notional currently held. Callers that
        omit them get every other check unchanged and simply skip the
        correlation check, since there is nothing to measure it from.
        """
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
        if qty * price > equity * self.cfg.max_position_pct * 1.0001:
            qty = equity * self.cfg.max_position_pct / price

        if signal.direction > 0:
            # position_size() already fitted the order to the cash on hand, but
            # the memory multiplier and the notional cap above both rescale
            # after it - and the notional cap is a fraction of *equity*, which
            # exceeds cash whenever another position is open. Without this final
            # clamp a 1.5x memory bias could spend money the account does not
            # have; on a real exchange that is a rejected order, and on paper it
            # silently books negative cash. The broker fills a buy at
            # price * (1 + slippage) and charges the fee on that, so both have
            # to come out of the same cash.
            cost_per_unit = (
                price
                * (1.0 + self.cfg.slippage_bps / 10_000.0)
                * (1.0 + self.cfg.fee_bps / 10_000.0)
            )
            affordable = max(0.0, cash) / cost_per_unit if cost_per_unit > 0 else 0.0
            qty = min(qty, affordable)

        if qty * price < self.cfg.min_notional:
            return RiskDecision(False, 0.0, "size below minimum notional")

        if price_history:
            refusal = self._correlated_exposure_reason(
                market, qty * price, equity, price_history, holdings or {}
            )
            if refusal:
                return RiskDecision(False, 0.0, refusal)

        return RiskDecision(True, qty, "within risk limits")

    # ------------------------------------------------------------------
    def _correlated_exposure_reason(
        self,
        market: str,
        new_notional: float,
        equity: float,
        price_history: Dict[str, Sequence[Candle]],
        holdings: Dict[str, float],
    ) -> Optional[str]:
        """None if the new position is fine; otherwise the refusal reason.

        A new entry is refused - rather than resized - when it would push the
        total notional held across one correlated cluster over
        ``cfg.max_correlated_exposure_pct`` of equity. Refusing (like the
        other entries in this method) keeps the risk manager's contract
        simple: every veto here is a flat no, so a caller never has to guess
        whether a returned size was silently shrunk for a reason it did not
        ask about.
        """
        if market not in price_history or equity <= 0:
            return None  # nothing to measure the requested market's cluster from

        clusters, pairs = self._correlation_clusters(price_history)
        cluster = next((c for c in clusters if market in c), [market])
        if len(cluster) <= 1:
            return None  # not correlated enough with anything else to matter

        cluster_set = set(cluster)
        held = sum(v for s, v in holdings.items() if s in cluster_set and s != market)
        total = held + new_notional
        cap = equity * self.cfg.max_correlated_exposure_pct
        if total <= cap * 1.0001:
            return None

        partner, value = _strongest_partner(market, cluster_set, pairs, self.cfg.correlation_threshold)
        if value is None:
            # A connected cluster of size > 1 always has at least one edge
            # touching `market`, but refusing on a cluster we cannot name a
            # reason for would produce an unreadable lesson - so stand down.
            return None

        pct = total / equity * 100.0
        cap_pct = self.cfg.max_correlated_exposure_pct * 100.0
        return (
            f"would hold {pct:.0f}% of equity in one cluster "
            f"({market}, {partner} correlated {value:.2f}, cap {cap_pct:.0f}%)"
        )

    def _correlation_clusters(
        self, price_history: Dict[str, Sequence[Candle]]
    ) -> Tuple[List[List[str]], Dict[Tuple[str, str], Correlation]]:
        """Cluster the given symbols by correlation, cached per bar in Brain 1.

        Five 200-bar Pearson correlations recomputed in pure Python on every
        single decision is wasted work when the candles behind them have not
        changed since the last closed bar. The cache key covers which symbols
        were measured and the most recent bar timestamp among them, so a new
        bar - or a different universe - invalidates it automatically without
        needing an explicit eviction.
        """
        symbols = sorted(price_history)
        bar_ts = max((series[-1].ts for series in price_history.values() if series), default=0)
        # One key per symbol set, with the bar stamped inside it. Putting the
        # timestamp in the key instead would leave a dead kv row behind on
        # every single bar, forever.
        cache_key = f"{CORRELATION_CACHE_PREFIX}.{'|'.join(symbols)}"

        cached = self.brain.get_state(cache_key)
        if cached is not None and cached.get("bar_ts") != bar_ts:
            cached = None  # stale: recompute for this bar
        if cached is not None:
            clusters = cached["clusters"]
            pairs = {
                tuple(key.split("|")): Correlation(row["value"], row["n"], row["reason"])
                for key, row in cached["pairs"].items()
            }
            return clusters, pairs

        # Measure correlation over the trailing window the operator configured,
        # not over however much history the caller happens to be holding -
        # otherwise cfg.correlation_window is documented but silently ignored,
        # and a stale correlation from months ago outweighs the last few days.
        window = self.cfg.correlation_window
        windowed = {
            sym: series[-window:] if window > 0 else series
            for sym, series in price_history.items()
        }
        clusters, pairs = cluster_symbols(windowed, self.cfg.correlation_threshold)
        self.brain.set_state(cache_key, {
            "bar_ts": bar_ts,
            "clusters": clusters,
            "pairs": {
                f"{a}|{b}": {"value": r.value, "n": r.n, "reason": r.reason}
                for (a, b), r in pairs.items()
            },
        })
        return clusters, pairs

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


def _strongest_partner(
    market: str,
    cluster: set,
    pairs: Dict[Tuple[str, str], Correlation],
    threshold: float,
) -> Tuple[Optional[str], Optional[float]]:
    """The cluster member `market` is most directly correlated with.

    A symbol only joins a cluster of size > 1 via an edge that touches it
    (connected components cannot add a node any other way), so this is
    guaranteed to find a partner for any `market` that is genuinely in a
    multi-symbol cluster - it exists to pick the most legible one to quote
    back to the operator when several qualify.
    """
    best_partner: Optional[str] = None
    best_value: Optional[float] = None
    for (a, b), corr in pairs.items():
        if not corr.known or corr.value < threshold:
            continue
        if a == market and b in cluster:
            other = b
        elif b == market and a in cluster:
            other = a
        else:
            continue
        if best_value is None or corr.value > best_value:
            best_partner, best_value = other, corr.value
    return best_partner, best_value
