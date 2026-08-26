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

from crypto_agent.brain.memory import DualBrain
from crypto_agent.config import Config
from crypto_agent.core.types import BacktestMetrics, Candle, fitness_score
from crypto_agent.data.providers import SyntheticProvider
from crypto_agent.evolution.engine import EvolutionEngine
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
        result = simulate(genome, candles, cfg)
        bh = buy_and_hold(candles, cfg)
        self.assertAlmostEqual(result.metrics.benchmark_return, bh.total_return, places=9)
        self.assertAlmostEqual(
            result.metrics.excess_return,
            result.metrics.total_return - bh.total_return,
            places=9,
        )


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
