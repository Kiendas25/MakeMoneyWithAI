"""Event-driven backtester.

Deliberately pessimistic: fees on both sides, slippage on every fill, stops
assumed to be hit before targets inside a bar, gap-through stops filling at the
open, and position sizing identical to the live risk model. A backtester that
flatters the strategy is worse than none, because evolution will happily breed a
population that exploits its optimism.
"""

from __future__ import annotations

import math
import statistics
from typing import List, Optional, Sequence, Tuple

from ..config import Config
from ..core.types import (
    BacktestMetrics,
    BacktestResult,
    Candle,
    Position,
    Trade,
    bars_per_year,
)
from . import rules
from .genome import Genome


def position_size(
    equity: float,
    price: float,
    stop: Optional[float],
    cfg: Config,
    risk_scale: float,
    cash: Optional[float] = None,
) -> float:
    """Risk-based sizing: lose ``risk_per_trade`` of equity if the stop hits.

    The same function sizes live orders, so a strategy cannot be tuned against
    one sizing model and then deployed under another.
    """
    if price <= 0 or equity <= 0:
        return 0.0
    risk_amount = equity * cfg.risk_per_trade * max(0.05, risk_scale)
    stop_distance = abs(price - stop) if stop else price * 0.05
    if stop_distance <= 0:
        return 0.0
    qty = risk_amount / stop_distance
    notional_cap = equity * cfg.max_position_pct
    qty = min(qty, notional_cap / price)
    if cash is not None:
        qty = min(qty, max(0.0, cash) / price)
    if qty * price < cfg.min_notional:
        return 0.0
    return qty


def simulate(
    genome: Genome,
    candles: Sequence[Candle],
    cfg: Config,
    start_cash: Optional[float] = None,
) -> BacktestResult:
    if len(candles) < 60:
        return BacktestResult(BacktestMetrics(final_equity=start_cash or cfg.start_cash))

    frame = rules.compute_frame(genome, candles)
    fee_rate = cfg.fee_bps / 10_000.0
    slip = cfg.slippage_bps / 10_000.0

    cash = float(start_cash if start_cash is not None else cfg.start_cash)
    position: Optional[Position] = None
    open_fees = 0.0
    open_reason = ""
    equity_curve: List[float] = []
    trades: List[Trade] = []
    bars_in_market = 0

    for i in range(frame.warmup, len(candles)):
        candle = candles[i]
        signal = rules.signal_at(genome, frame, i)

        if position is not None:
            position.bars_held += 1
            position.stop = rules.update_trailing_stop(genome, frame, i, position)
            reason = rules.exit_reason(genome, frame, i, position, signal)
            if reason:
                raw_price = rules.exit_price_for(reason, position, candle)
                fill = raw_price * (1 - slip) if position.qty > 0 else raw_price * (1 + slip)
                proceeds = position.qty * fill
                fee = abs(proceeds) * fee_rate
                cash += proceeds - fee
                pnl = (fill - position.entry_price) * position.qty - fee - open_fees
                cost_basis = abs(position.entry_price * position.qty)
                trades.append(
                    Trade(
                        symbol=cfg.symbol,
                        side=position.side,
                        qty=abs(position.qty),
                        entry_ts=position.entry_ts,
                        entry_price=position.entry_price,
                        exit_ts=candle.ts,
                        exit_price=fill,
                        pnl=pnl,
                        pnl_pct=pnl / cost_basis if cost_basis else 0.0,
                        fees=fee + open_fees,
                        reason_open=open_reason,
                        reason_close=reason,
                        genome_id=genome.id,
                        regime=position.regime,
                    )
                )
                position = None
                open_fees = 0.0

        if position is None and signal.direction != 0:
            equity_now = cash
            entry_raw = candle.close
            fill = entry_raw * (1 + slip) if signal.direction > 0 else entry_raw * (1 - slip)
            stop, take_profit = rules.initial_stops(genome, frame, i, fill, signal.direction)
            qty = position_size(
                equity_now,
                fill,
                stop,
                cfg,
                float(genome.genes["risk_scale"]),
                cash=cash if signal.direction > 0 else None,
            )
            if qty > 0:
                signed_qty = qty * signal.direction
                fee = qty * fill * fee_rate
                cash -= signed_qty * fill + fee
                open_fees = fee
                open_reason = signal.reason
                position = Position(
                    symbol=cfg.symbol,
                    qty=signed_qty,
                    entry_price=fill,
                    entry_ts=candle.ts,
                    stop=stop,
                    take_profit=take_profit,
                    genome_id=genome.id,
                    regime=signal.regime,
                )

        mark = cash + (position.qty * candle.close if position else 0.0)
        equity_curve.append(mark)
        if position:
            bars_in_market += 1

    if position is not None:  # close at the last price so metrics are honest
        last = candles[-1]
        fill = last.close * (1 - slip) if position.qty > 0 else last.close * (1 + slip)
        proceeds = position.qty * fill
        fee = abs(proceeds) * fee_rate
        cash += proceeds - fee
        pnl = (fill - position.entry_price) * position.qty - fee - open_fees
        cost_basis = abs(position.entry_price * position.qty)
        trades.append(
            Trade(
                symbol=cfg.symbol,
                side=position.side,
                qty=abs(position.qty),
                entry_ts=position.entry_ts,
                entry_price=position.entry_price,
                exit_ts=last.ts,
                exit_price=fill,
                pnl=pnl,
                pnl_pct=pnl / cost_basis if cost_basis else 0.0,
                fees=fee + open_fees,
                reason_open=open_reason,
                reason_close="end_of_data",
                genome_id=genome.id,
                regime=position.regime,
            )
        )
        equity_curve[-1] = cash

    metrics = compute_metrics(
        equity_curve,
        trades,
        cfg.timeframe,
        start_equity=float(start_cash if start_cash is not None else cfg.start_cash),
        exposure=bars_in_market / max(1, len(equity_curve)),
    )
    return BacktestResult(metrics=metrics, equity_curve=equity_curve, trades=trades)


def compute_metrics(
    equity_curve: Sequence[float],
    trades: Sequence[Trade],
    timeframe: str,
    start_equity: float,
    exposure: float,
) -> BacktestMetrics:
    if not equity_curve:
        return BacktestMetrics(final_equity=start_equity)

    final = equity_curve[-1]
    total_return = final / start_equity - 1.0 if start_equity else 0.0

    returns: List[float] = []
    for prev, cur in zip(equity_curve, equity_curve[1:]):
        returns.append(cur / prev - 1.0 if prev > 0 else 0.0)

    sharpe = sortino = 0.0
    if len(returns) > 2:
        mean = statistics.fmean(returns)
        sd = statistics.pstdev(returns)
        scale = math.sqrt(bars_per_year(timeframe))
        if sd > 0:
            sharpe = mean / sd * scale
        downside = [r for r in returns if r < 0]
        if downside:
            dsd = math.sqrt(statistics.fmean([r * r for r in downside]))
            if dsd > 0:
                sortino = mean / dsd * scale

    peak = equity_curve[0]
    max_dd = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            max_dd = max(max_dd, (peak - value) / peak)

    wins = sum(1 for t in trades if t.pnl > 0)
    return BacktestMetrics(
        total_return=total_return,
        sharpe=sharpe,
        sortino=sortino,
        max_drawdown=max_dd,
        win_rate=wins / len(trades) if trades else 0.0,
        trades=len(trades),
        avg_trade_pct=statistics.fmean([t.pnl_pct for t in trades]) if trades else 0.0,
        exposure=exposure,
        final_equity=final,
    )


def walk_forward(
    genome: Genome, candles: Sequence[Candle], cfg: Config
) -> Tuple[BacktestResult, BacktestResult]:
    """Fit-window and hold-out results.

    The GA selects on the in-sample score but promotes on the out-of-sample one.
    Overfitting is the default outcome of any search over strategy parameters;
    the hold-out is the only thing standing between the agent and a champion
    that has memorised noise.
    """
    # A fixed bar count would leave a short history with no fit window at all,
    # so the hold-out is the smaller of the configured size and a third of what
    # is available.
    hold_out = min(cfg.oos_bars, max(150, int(len(candles) * 0.35)))
    split = max(0, len(candles) - hold_out)
    in_sample = candles[:split] if split > 100 else candles
    out_sample = candles[split:] if split > 100 else candles[-hold_out:]
    is_result = simulate(genome, in_sample, cfg)
    oos_result = simulate(genome, out_sample, cfg)
    return is_result, oos_result
