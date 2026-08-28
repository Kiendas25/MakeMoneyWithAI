"""Tests for the buy-and-hold benchmark, anchored walk-forward folds, and
the trials deflation applied on top of them.

These three land together because they all answer the same question from
different angles: is a fitness number actually evidence of skill, or just of
a rising market and a search that has been allowed to keep rolling the dice
against the same hold-out?
"""

import random
import tempfile
import unittest
from dataclasses import replace

from crypto_agent.brain.memory import DualBrain
from crypto_agent.config import Config
from crypto_agent.core.types import BacktestMetrics, Candle, Position, Signal, fitness_score
from crypto_agent.data.providers import SyntheticProvider
from crypto_agent.evolution.engine import EvolutionEngine
from crypto_agent.strategy import rules
from crypto_agent.strategy.backtest import buy_and_hold, simulate, walk_forward
from crypto_agent.strategy.genome import seed_population


def ramp_candles(prices):
    """A deterministic price path with no wicks, so the arithmetic in a test
    can be worked out by hand."""
    out = []
    ts = 0
    for price in prices:
        out.append(Candle(ts, price, price, price, price, 10.0))
        ts += 3_600_000
    return out


class TestBuyAndHold(unittest.TestCase):
    def test_matches_known_arithmetic_on_a_ramp(self):
        candles = ramp_candles([100.0, 120.0, 150.0, 200.0])  # price doubles
        cfg = Config(start_cash=10_000.0, fee_bps=0.0, timeframe="1h")
        m = buy_and_hold(candles, cfg)
        self.assertAlmostEqual(m.total_return, 1.0, places=6)
        self.assertAlmostEqual(m.final_equity, 20_000.0, places=4)

        # A 1% one-off entry fee should shave exactly 1% off the doubling,
        # since buy_and_hold only ever pays the fee once.
        cfg_fee = Config(start_cash=10_000.0, fee_bps=100.0, timeframe="1h")
        m_fee = buy_and_hold(candles, cfg_fee)
        expected = 0.99 * 2.0 - 1.0
        self.assertAlmostEqual(m_fee.total_return, expected, places=6)

    def test_too_short_a_series_is_a_no_op(self):
        cfg = Config(start_cash=5_000.0)
        m = buy_and_hold(ramp_candles([100.0]), cfg)
        self.assertEqual(m.total_return, 0.0)
        self.assertEqual(m.final_equity, 5_000.0)

    def test_simulate_records_what_it_beat_or_lost_to(self):
        genome = seed_population(random.Random(1), 4, allow_short=False)[0]
        cfg = Config(symbol="BTC/USDT", timeframe="1h", start_cash=10_000.0)
        candles = SyntheticProvider(seed=2).fetch_ohlcv("BTC/USDT", "1h", 500)
        frame = rules.compute_frame(genome, candles)
        result = simulate(genome, candles, cfg)
        # The strategy could only ever trade candles[frame.warmup:], so that
        # is the only window it can honestly be benchmarked against.
        bh = buy_and_hold(candles[frame.warmup:], cfg)
        self.assertAlmostEqual(result.metrics.benchmark_return, bh.total_return, places=9)
        self.assertAlmostEqual(
            result.metrics.excess_return,
            result.metrics.total_return - bh.total_return,
            places=9,
        )

    def test_benchmark_is_priced_over_the_strategys_tradeable_window_only(self):
        """BUG 1 regression: pricing the benchmark over the full candle range
        (rather than candles[frame.warmup:]) mixes pre-warmup drift the
        strategy never had a chance to trade into the number it is scored
        against. Both the windowed and full-range returns here are known by
        construction from just two prices each (buy-and-hold's total_return
        depends only on the first and last close of whatever slice it is
        given), so this pins down exactly which window ``simulate`` must use.
        """
        genome = seed_population(random.Random(3), 4, allow_short=False)[0]
        # warmup depends only on genome genes, not on candle content or count,
        # so any short throwaway series is enough to read it off.
        warmup = rules.compute_frame(genome, ramp_candles([100.0, 100.0, 100.0])).warmup
        cfg = Config(symbol="BTC/USDT", timeframe="1h", start_cash=10_000.0, fee_bps=0.0)

        # Pre-warmup: a steep slide from 100 down to 90 that the strategy
        # never sees a signal for. From frame.warmup onward: a much gentler
        # slide from 60 down to 50 - the only bars the strategy could act on.
        prices = [100.0] + [90.0] * (warmup - 1) + [60.0] + [55.0] * 250 + [50.0]
        candles = ramp_candles(prices)
        self.assertEqual(len(candles), warmup + 252)  # sanity check on construction

        result = simulate(genome, candles, cfg)
        windowed = buy_and_hold(candles[warmup:], cfg)
        full_range = buy_and_hold(candles, cfg)

        self.assertAlmostEqual(windowed.total_return, 50.0 / 60.0 - 1.0, places=9)
        self.assertAlmostEqual(full_range.total_return, 50.0 / 100.0 - 1.0, places=9)
        # The two windows disagree by a lot (~33pp) - exactly the kind of gap
        # that used to leak into excess_return before this fix.
        self.assertNotAlmostEqual(windowed.total_return, full_range.total_return, places=2)

        self.assertAlmostEqual(result.metrics.benchmark_return, windowed.total_return, places=9)
        self.assertNotAlmostEqual(result.metrics.benchmark_return, full_range.total_return, places=2)


class TestBenchmarkAwareFitness(unittest.TestCase):
    def test_beating_the_benchmark_outranks_a_higher_sharpe_that_lost_to_it(self):
        # Modest numbers, but it beat a falling market by 15 points.
        beat_it = BacktestMetrics(
            total_return=0.10, sharpe=1.0, max_drawdown=0.05, trades=40,
            benchmark_return=-0.05, excess_return=0.15,
        )
        # A flashier Sharpe and a bigger return, but the market itself ran
        # +60% and this strategy captured barely half of it.
        lost_to_it = BacktestMetrics(
            total_return=0.30, sharpe=3.0, max_drawdown=0.05, trades=40,
            benchmark_return=0.60, excess_return=-0.30,
        )
        self.assertGreater(fitness_score(beat_it), fitness_score(lost_to_it))

    def test_benchmark_weight_of_zero_falls_back_to_pure_risk_adjustment(self):
        # With no benchmark pressure at all, excess return cannot matter -
        # only the drawdown-penalised, sample-shrunk Sharpe read can.
        higher_sharpe = BacktestMetrics(total_return=0.1, sharpe=2.0, max_drawdown=0.05,
                                        trades=40, excess_return=-1.0)
        lower_sharpe = BacktestMetrics(total_return=0.1, sharpe=0.5, max_drawdown=0.05,
                                       trades=40, excess_return=1.0)
        self.assertGreater(
            fitness_score(higher_sharpe, benchmark_weight=0.0),
            fitness_score(lower_sharpe, benchmark_weight=0.0),
        )

    def test_default_signature_still_ranks_drawdown_and_sample_size(self):
        """The pre-existing contract: fitness_score(metrics) with no other
        arguments must still behave as documented for callers that never
        touch benchmark_weight."""
        good = BacktestMetrics(total_return=0.4, sharpe=2.0, max_drawdown=0.05, trades=40)
        deep = BacktestMetrics(total_return=0.4, sharpe=2.0, max_drawdown=0.6, trades=40)
        thin = BacktestMetrics(total_return=0.4, sharpe=2.0, max_drawdown=0.05, trades=1)
        self.assertGreater(fitness_score(good), fitness_score(deep))
        self.assertGreater(fitness_score(good), fitness_score(thin))
        self.assertLess(fitness_score(thin), 0.0)


def _flat_frame(candles, atr_values):
    """A minimal Frame for exercising update_trailing_stop/exit_reason in
    isolation: only ``candles`` and ``atr`` matter to those two functions, so
    everything else is filled with harmless Nones."""
    n = len(candles)
    return rules.Frame(
        candles=candles,
        ema_fast=[None] * n,
        ema_slow=[None] * n,
        rsi=[None] * n,
        atr=atr_values,
        macd=[None] * n,
        donchian=[None] * n,
        bb_z=[None] * n,
        vol=[None] * n,
        slope=[None] * n,
        warmup=0,
    )


def _run_position_management(genome, frame, position, use_buggy_order):
    """Replays the per-bar stop/exit handling for one held position across a
    frame, in either ordering.

    ``use_buggy_order=True`` reproduces the pre-fix sequence: ratchet the
    stop with bar i's close, then test bar i's own low/high against that
    freshly-moved stop. ``use_buggy_order=False`` reproduces the fix: test
    the stop already in force before bar i, and only ratchet with bar i's
    close for bars after i. Returns the count of stop-type exits ("stop_loss"
    or "trailing_stop") the position racked up before closing.
    """
    pos = replace(position)
    signal = Signal(0, 0.0, "hold", {}, "range_mid_vol")
    stop_exits = 0
    for i in range(len(frame.candles)):
        if pos is None:
            break
        pos.bars_held += 1
        if use_buggy_order:
            pos.stop = rules.update_trailing_stop(genome, frame, i, pos)
            reason = rules.exit_reason(genome, frame, i, pos, signal)
        else:
            reason = rules.exit_reason(genome, frame, i, pos, signal)
            if reason is None:
                pos.stop = rules.update_trailing_stop(genome, frame, i, pos)
        if reason in ("stop_loss", "trailing_stop"):
            stop_exits += 1
            pos = None
    return stop_exits


class TestTrailingStopLookahead(unittest.TestCase):
    """BUG 2 regression: the stop must be tested against the level known
    before a bar opened, and only ratcheted with that bar's close for the
    *next* bar - never both against the same bar."""

    def setUp(self):
        self.genome = seed_population(random.Random(1), 1, allow_short=False)[0]
        self.genome.genes["trail_atr_mult"] = 1.0

    def test_ratchet_from_bar_i_does_not_apply_to_bar_i_itself(self):
        # A bar that dips hard intrabar (low 95) and recovers by the close
        # (104). A stop of 90.0 was already in force before this bar opened.
        candle = Candle(ts=0, open=105.0, high=106.0, low=95.0, close=104.0, volume=10.0)
        frame = _flat_frame([candle], atr_values=[5.0])
        position = Position(
            symbol="BTC/USDT", qty=1.0, entry_price=100.0, entry_ts=-1,
            stop=90.0, take_profit=None, genome_id=self.genome.id, regime="range_mid_vol",
        )
        signal = Signal(0, 0.0, "hold", {}, "range_mid_vol")

        # Correct order: check the pre-existing stop (90) against this bar
        # first. 90 sits below the bar's low (95), so nothing fires.
        reason = rules.exit_reason(self.genome, frame, 0, position, signal)
        self.assertIsNone(reason)

        # Only now may bar 0's close feed the ratchet, and the result is for
        # bar 1 onward, not bar 0.
        new_stop = rules.update_trailing_stop(self.genome, frame, 0, position)
        self.assertAlmostEqual(new_stop, 104.0 - 1.0 * 5.0, places=9)  # 99.0
        self.assertGreater(new_stop, candle.low)  # would wrongly clip this bar's own low

        # This is exactly the bug: feed that freshly-ratcheted stop back into
        # a check of the *same* bar, and it fires on a low the price had
        # already recovered from before that stop ever existed.
        lookahead_position = replace(position, stop=new_stop)
        lookahead_reason = rules.exit_reason(self.genome, frame, 0, lookahead_position, signal)
        self.assertEqual(lookahead_reason, "stop_loss")
        fill = rules.exit_price_for(lookahead_reason, lookahead_position, candle)
        # The bogus fill (99.0) sits inside a range the bar had already
        # traded through (95-106) *before* its close produced that stop.
        self.assertTrue(candle.low <= fill <= candle.high)

    def test_stop_exit_count_drops_once_lookahead_is_removed(self):
        """On a constructed two-bar series, the buggy ordering manufactures a
        stop exit on the dip-and-recover bar that the fixed ordering does
        not - the count must move in that direction, not just differ."""
        bar0 = Candle(ts=0, open=105.0, high=106.0, low=95.0, close=104.0, volume=10.0)
        bar1 = Candle(ts=3_600_000, open=104.0, high=107.0, low=103.0, close=106.0, volume=10.0)
        frame = _flat_frame([bar0, bar1], atr_values=[5.0, 5.0])
        position = Position(
            symbol="BTC/USDT", qty=1.0, entry_price=100.0, entry_ts=-1,
            stop=90.0, take_profit=None, genome_id=self.genome.id, regime="range_mid_vol",
        )

        buggy_count = _run_position_management(self.genome, frame, position, use_buggy_order=True)
        fixed_count = _run_position_management(self.genome, frame, position, use_buggy_order=False)

        self.assertEqual(buggy_count, 1)  # the lookahead-only exit on bar 0
        self.assertEqual(fixed_count, 0)  # survives both bars once fixed
        self.assertLess(fixed_count, buggy_count)


class TestAnchoredWalkForward(unittest.TestCase):
    def setUp(self):
        self.cfg = Config(symbol="BTC/USDT", timeframe="1h", start_cash=10_000.0,
                          history_bars=1200, oos_bars=200, walk_forward_folds=3)
        self.genome = seed_population(random.Random(1), 4, allow_short=False)[0]
        self.candles = SyntheticProvider(seed=5).fetch_ohlcv("BTC/USDT", "1h", 1000)

    def test_folds_advance_through_time_without_overlapping_their_holdout(self):
        wf = walk_forward(self.genome, self.candles, self.cfg)
        self.assertGreaterEqual(len(wf.folds), 2)

        prev_hold_end = -1
        for fold in wf.folds:
            fit_start, fit_end = fold.fit_range
            hold_start, hold_end = fold.hold_range
            self.assertEqual(fit_start, 0)  # anchored: the fit window always starts at bar 0
            self.assertGreater(hold_end, hold_start)
            self.assertEqual(fit_end, hold_start)  # fit stops exactly where its hold-out begins
            self.assertGreaterEqual(hold_start, prev_hold_end)  # never re-tests an earlier hold-out
            prev_hold_end = hold_end

        hold_windows = {fold.hold_range for fold in wf.folds}
        self.assertEqual(len(hold_windows), len(wf.folds))  # every fold saw a distinct window

    def test_result_unpacks_as_a_two_tuple_for_older_callers(self):
        wf = walk_forward(self.genome, self.candles, self.cfg)
        in_sample, out_sample = wf  # must not raise
        self.assertIs(in_sample, wf.in_sample)
        self.assertIs(out_sample, wf.out_sample)
        self.assertLessEqual(len(out_sample.equity_curve), self.cfg.oos_bars)
        self.assertGreater(len(in_sample.equity_curve), len(out_sample.equity_curve))

    def test_short_history_falls_back_to_a_single_fold(self):
        short = self.candles[:120]
        wf = walk_forward(self.genome, short, self.cfg)
        self.assertEqual(len(wf.folds), 1)
        self.assertIs(wf.in_sample, wf.out_sample)


class TestEvaluateAndDeflation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(data_dir=self.tmp.name, symbol="BTC/USDT", timeframe="1h",
                          population_size=4, elite_count=1, history_bars=900,
                          oos_bars=200, trials_penalty=True)
        self.brain = DualBrain(self.cfg)
        self.engine = EvolutionEngine(self.cfg, self.brain)
        self.genome = seed_population(random.Random(2), 4, allow_short=False)[0]
        self.series = SyntheticProvider(seed=7).fetch_ohlcv(self.cfg.symbol, "1h", 900)

    def tearDown(self):
        self.brain.close()
        self.tmp.cleanup()

    def test_deflation_reduces_score_as_trials_rise(self):
        fresh = self.engine.evaluate(self.genome, self.series, trials=0)
        seasoned = self.engine.evaluate(self.genome, self.series, trials=500)
        self.assertLess(seasoned.fitness, fresh.fitness)
        self.assertLess(seasoned.oos_fitness, fresh.oos_fitness)
        self.assertGreater(seasoned.deflation_penalty, fresh.deflation_penalty)

    def test_deflation_off_leaves_score_unchanged_by_trials(self):
        cfg = Config(**{**self.cfg.to_dict(), "trials_penalty": False})
        brain = DualBrain(cfg)
        engine = EvolutionEngine(cfg, brain)
        try:
            fresh = engine.evaluate(self.genome, self.series, trials=0)
            seasoned = engine.evaluate(self.genome, self.series, trials=500)
            self.assertAlmostEqual(seasoned.fitness, fresh.fitness, places=9)
            self.assertAlmostEqual(seasoned.oos_fitness, fresh.oos_fitness, places=9)
        finally:
            brain.close()

    def test_evaluate_accepts_a_bare_candle_series(self):
        ev = self.engine.evaluate(self.genome, self.series)
        self.assertEqual(set(ev.per_symbol), {self.cfg.symbol})

    def test_evaluate_accepts_a_symbol_to_candles_dict(self):
        other = SyntheticProvider(seed=8).fetch_ohlcv("ETH/USDT", "1h", 900)
        history = {self.cfg.symbol: self.series, "ETH/USDT": other}
        ev = self.engine.evaluate(self.genome, history)
        self.assertEqual(set(ev.per_symbol), {self.cfg.symbol, "ETH/USDT"})
        self.assertEqual(
            ev.pooled_oos_trades,
            sum(int(v["trades"]) for v in ev.per_symbol.values()),
        )

    def test_run_generation_advances_the_trials_counter(self):
        before = self.engine._trials_seen()
        self.engine.run_generation(self.series)
        after = self.engine._trials_seen()
        self.assertEqual(after, before + 1)


if __name__ == "__main__":
    unittest.main()
