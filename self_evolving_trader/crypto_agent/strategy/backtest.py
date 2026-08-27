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
from dataclasses import dataclass, field
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
            # Test the stop that was already in force *before* this bar opened.
            # Ratcheting with bar i's close and then checking that new level
            # against bar i's own low/high is lookahead: it uses information
            # only known at the bar's end to decide something about the whole
            # bar, including the part that came before that close printed. The
            # ratchet computed from bar i's close is applied below only when
            # the position survives the bar, so it takes effect starting bar
            # i + 1, once that close is actually old news.
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
            else:
                # The position survived bar i's own stop check, so now - and
                # only now - fold bar i's close into the trailing stop for
                # bar i + 1 to test.
                position.stop = rules.update_trailing_stop(genome, frame, i, position)

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

    # Every result is measured against the trivial "just buy it" strategy on
    # the same window, so a genome that only out-trades a falling market still
    # reads as the failure it is. That window must be exactly the bars the
    # strategy was allowed to trade - candles[frame.warmup:] - not the full
    # history including candles the genome never saw a signal for. Pricing
    # the benchmark over the full range mixes in pre-warmup drift the
    # strategy could not possibly have captured or avoided, and skews
    # excess_return, which carries most of the fitness weight.
    benchmark_return = buy_and_hold(candles[frame.warmup:], cfg).total_return
    metrics = compute_metrics(
        equity_curve,
        trades,
        cfg.timeframe,
        start_equity=float(start_cash if start_cash is not None else cfg.start_cash),
        exposure=bars_in_market / max(1, len(equity_curve)),
        benchmark_return=benchmark_return,
    )
    return BacktestResult(metrics=metrics, equity_curve=equity_curve, trades=trades)


def buy_and_hold(candles: Sequence[Candle], cfg: Config) -> BacktestMetrics:
    """The trivial "buy once and do nothing" strategy, priced the same way
    ``simulate`` prices everything else, so the two are directly comparable.

    Only the entry pays a fee. An investor who buys once and never trades
    again never re-crosses the spread a second time, and charging an exit fee
    here would understate what plain holding actually returns relative to a
    strategy that pays fees on every round trip.
    """
    start_cash = float(cfg.start_cash)
    if len(candles) < 2 or candles[0].close <= 0:
        return BacktestMetrics(final_equity=start_cash)
    fee_rate = cfg.fee_bps / 10_000.0
    entry_price = candles[0].close
    fee = start_cash * fee_rate
    qty = (start_cash - fee) / entry_price
    equity_curve = [qty * c.close for c in candles[1:]]
    return compute_metrics(
        equity_curve,
        trades=[],
        timeframe=cfg.timeframe,
        start_equity=start_cash,
        exposure=1.0,
    )


def compute_metrics(
    equity_curve: Sequence[float],
    trades: Sequence[Trade],
    timeframe: str,
    start_equity: float,
    exposure: float,
    benchmark_return: float = 0.0,
) -> BacktestMetrics:
    if not equity_curve:
        return BacktestMetrics(final_equity=start_equity, benchmark_return=benchmark_return)

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
        benchmark_return=benchmark_return,
        excess_return=total_return - benchmark_return,
    )


@dataclass
class Fold:
    """One anchored walk-forward split: everything up to a point to fit on,
    and the untouched bars right after it to test on.

    ``fit_range``/``hold_range`` are half-open ``(start, end)`` indices into
    the original candle sequence, kept around so callers (and tests) can
    confirm the folds actually advance through time instead of re-testing the
    same window.
    """

    fit: BacktestResult
    hold_out: BacktestResult
    fit_range: Tuple[int, int]
    hold_range: Tuple[int, int]


@dataclass
class WalkForwardResult:
    """Aggregate in-sample and out-of-sample results, plus the fold-by-fold
    detail they were pooled from.

    Unpacks as a 2-tuple of ``(in_sample, out_sample)`` so callers that only
    want the headline BacktestResults - as the previous, single-split
    ``walk_forward`` returned - keep working unchanged.
    """

    in_sample: BacktestResult
    out_sample: BacktestResult
    folds: List[Fold] = field(default_factory=list)

    def __iter__(self):
        return iter((self.in_sample, self.out_sample))


def _aggregate_metrics(results: Sequence[BacktestResult]) -> BacktestMetrics:
    """Pool several fold results into one summary metric set.

    Trade counts sum outright - more folds is strictly more evidence. Return,
    Sharpe, Sortino and exposure are weighted by how many bars each fold
    actually ran over, so a fold that barely produced any bars cannot outvote
    one built on ten times the data. Drawdown takes the worst fold rather than
    an average, because a strategy that blew up in any one window is not made
    safe by having behaved in the others.
    """
    metrics = [r.metrics for r in results]
    weights = [max(1, len(r.equity_curve)) for r in results]
    total_weight = float(sum(weights))

    def wmean(getter) -> float:
        return sum(getter(m) * w for m, w in zip(metrics, weights)) / total_weight

    total_trades = sum(m.trades for m in metrics)
    total_wins = sum(round(m.win_rate * m.trades) for m in metrics)
    all_pnls = [t.pnl_pct for r in results for t in r.trades]
    return BacktestMetrics(
        total_return=wmean(lambda m: m.total_return),
        sharpe=wmean(lambda m: m.sharpe),
        sortino=wmean(lambda m: m.sortino),
        max_drawdown=max((m.max_drawdown for m in metrics), default=0.0),
        win_rate=(total_wins / total_trades) if total_trades else 0.0,
        trades=total_trades,
        avg_trade_pct=statistics.fmean(all_pnls) if all_pnls else 0.0,
        exposure=wmean(lambda m: m.exposure),
        final_equity=wmean(lambda m: m.final_equity),
        benchmark_return=wmean(lambda m: m.benchmark_return),
        excess_return=wmean(lambda m: m.excess_return),
    )


def walk_forward(genome: Genome, candles: Sequence[Candle], cfg: Config) -> WalkForwardResult:
    """Anchored, multi-fold walk-forward evaluation.

    A single fixed hold-out at the tail of history gets implicitly selected on
    every time evolution calls this against it; after hundreds of generations
    it has been used to pick a winner about as many times as the fit window
    has, and stops being out-of-sample in any meaningful sense. Splitting into
    ``cfg.walk_forward_folds`` successive folds - each fitting on everything
    seen so far and testing on the untouched bars right after - means
    different generations, and different points in evolution, land on
    different hold-out windows, so no single stretch of history quietly
    becomes part of the training signal.
    """
    n = len(candles)
    folds_n = max(1, cfg.walk_forward_folds)
    min_fit = 100  # simulate() itself refuses fewer than 60 bars; leave headroom

    def _single_fold() -> WalkForwardResult:
        # Not enough history for an honest fit/hold-out split at all: fall
        # back to evaluating on everything, same as having no hold-out.
        only = simulate(genome, candles, cfg)
        return WalkForwardResult(
            in_sample=only, out_sample=only, folds=[Fold(only, only, (0, n), (0, n))]
        )

    if n <= min_fit + 50:
        return _single_fold()

    remaining = n - min_fit
    hold_size = max(50, remaining // folds_n)
    hold_size = min(hold_size, cfg.oos_bars)

    folds: List[Fold] = []
    fit_end = min_fit
    while fit_end < n and len(folds) < folds_n:
        hold_start = fit_end
        hold_end = min(n, hold_start + hold_size)
        if hold_end - hold_start < 30:
            break
        fit_slice = candles[:fit_end]
        hold_slice = candles[hold_start:hold_end]
        fit_result = simulate(genome, fit_slice, cfg)
        hold_result = simulate(genome, hold_slice, cfg)
        folds.append(Fold(fit_result, hold_result, (0, fit_end), (hold_start, hold_end)))
        fit_end = hold_end  # anchor: next fold's fit window absorbs this hold-out

    if not folds:  # pragma: no cover - guarded by the length check above
        return _single_fold()

    in_sample = BacktestResult(
        metrics=_aggregate_metrics([f.fit for f in folds]),
        equity_curve=folds[-1].fit.equity_curve,
        trades=[t for f in folds for t in f.fit.trades],
    )
    out_sample = BacktestResult(
        metrics=_aggregate_metrics([f.hold_out for f in folds]),
        equity_curve=folds[-1].hold_out.equity_curve,
        trades=[t for f in folds for t in f.hold_out.trades],
    )
    return WalkForwardResult(in_sample=in_sample, out_sample=out_sample, folds=folds)
