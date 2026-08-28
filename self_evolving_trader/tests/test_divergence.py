"""Tests for ``crypto_agent.analysis.divergence``.

The two behavioural tests build the "live" ledger *from* a real
``backtest.simulate()`` run of the same genome and candles, rather than
hand-typing prices - so the expected divergence numbers are known by
construction: either every modelled trade is copied into Brain 1 with a
shifted fill price (a pure fill-model divergence, no vetoes logged), or none
of them are copied and a memory veto is logged at every entry the model took
instead (a pure behavioural divergence, no fills to compare). Comparing the
two verdicts against each other is what proves the module actually tells
them apart rather than reporting one blended number.
"""

from __future__ import annotations

import math
import random
import tempfile
import unittest
from pathlib import Path

from crypto_agent import dashboard
from crypto_agent.analysis import divergence
from crypto_agent.brain.memory import DualBrain
from crypto_agent.config import Config
from crypto_agent.core.types import Candle, Signal, Trade
from crypto_agent.strategy import backtest
from crypto_agent.strategy.genome import seed_population


def make_candles(n: int = 260, seed: int = 3) -> list[Candle]:
    """A synthetic series with a slow, noisy oscillating drift - long enough
    to warm up any genome's indicators and produce several round trips from
    the trend-following archetype used below."""
    rng = random.Random(seed)
    price = 100.0
    out = []
    for i in range(n):
        drift = math.sin(i / 20.0) * 0.6 + 0.05
        price *= 1 + drift / 100 + rng.uniform(-0.004, 0.004)
        open_price = price
        close = price * (1 + rng.uniform(-0.003, 0.003))
        high = max(open_price, close) * 1.002
        low = min(open_price, close) * 0.998
        out.append(Candle(i * 3_600_000, open_price, high, low, close, 10.0))
        price = close
    return out


def trend_follower_genome():
    """The archetype ``seed_population`` seeds first - reliably trades on
    the oscillating series above."""
    return seed_population(random.Random(1), 4, allow_short=False)[0]


class DivergenceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(data_dir=self.tmp.name, symbol="BTC/USDT", timeframe="1h",
                          slippage_bps=5.0, fee_bps=10.0)
        self.brain = DualBrain(self.cfg)
        self.candles = make_candles()
        self.genome = trend_follower_genome()

    def tearDown(self) -> None:
        self.brain.close()
        self.tmp.cleanup()

    def _install_champion(self) -> None:
        self.brain.b1.save_genome(
            self.genome.id, self.genome.generation, self.genome.to_dict(),
            fitness=1.0, oos_fitness=1.0, metrics={}, status="champion",
        )

    def _modelled_trades(self):
        self.brain.b1.save_candles("BTC/USDT", "1h", self.candles)
        result = backtest.simulate(self.genome, self.candles, self.cfg)
        self.assertGreaterEqual(len(result.trades), 3, "fixture must actually trade")
        return result.trades


class TestFillDivergence(DivergenceTestCase):
    """Live fills that are worse than the model assumed, with every entry
    matched and no vetoes logged - a pure modelling discrepancy."""

    def setUp(self) -> None:
        super().setUp()
        self._install_champion()
        modelled = self._modelled_trades()
        for t in modelled:
            shifted_entry = t.entry_price * 1.005  # 50 bps worse than modelled
            signed_qty = t.qty if t.side == "long" else -t.qty
            pnl = (t.exit_price - shifted_entry) * signed_qty - t.fees
            cost_basis = abs(shifted_entry * t.qty)
            self.brain.b1.record_trade(Trade(
                symbol="BTC/USDT", side=t.side, qty=t.qty, entry_ts=t.entry_ts,
                entry_price=shifted_entry, exit_ts=t.exit_ts, exit_price=t.exit_price,
                pnl=pnl, pnl_pct=pnl / cost_basis if cost_basis else 0.0, fees=t.fees,
                reason_open=t.reason_open, reason_close=t.reason_close,
                genome_id=self.genome.id, regime=t.regime,
            ))
            sig = Signal(1 if t.side == "long" else -1, 0.5, "matched entry")
            self.brain.b1.record_decision(
                t.entry_ts, "BTC/USDT", f"open:{t.side}", sig, self.genome.id, executed=True
            )
        self.modelled = modelled
        self.report = divergence.measure_divergence(self.brain, self.cfg)

    def test_every_entry_matches_and_no_vetoes_are_seen(self):
        sym = self.report.per_symbol["BTC/USDT"]
        self.assertEqual(sym.realised_trades, len(self.modelled))
        self.assertEqual(sym.modelled_trades, len(self.modelled))
        self.assertEqual(sym.matched_entries, len(self.modelled))
        self.assertEqual(sym.memory_declined, 0)
        self.assertEqual(sym.risk_declined, 0)
        self.assertEqual(sym.unexplained_backtest_only, 0)
        self.assertEqual(sym.unexplained_live_only, 0)

    def test_entry_slippage_is_measured_at_roughly_fifty_bps(self):
        sym = self.report.per_symbol["BTC/USDT"]
        self.assertIsNotNone(sym.mean_entry_slippage_bps)
        self.assertAlmostEqual(sym.mean_entry_slippage_bps, 50.0, delta=0.5)
        # Exits were left untouched, so they should show ~0 divergence.
        self.assertIsNotNone(sym.mean_exit_slippage_bps)
        self.assertAlmostEqual(sym.mean_exit_slippage_bps, 0.0, delta=0.5)

    def test_pooled_matches_the_single_symbol(self):
        sym = self.report.per_symbol["BTC/USDT"]
        pooled = self.report.pooled
        self.assertEqual(pooled.matched_entries, sym.matched_entries)
        self.assertEqual(pooled.realised_trades, sym.realised_trades)
        self.assertAlmostEqual(pooled.mean_entry_slippage_bps, sym.mean_entry_slippage_bps, places=6)

    def test_verdict_names_the_fill_model_not_the_agents_choices(self):
        verdict = self.report.verdict.lower()
        self.assertIn("fill", verdict)
        self.assertNotIn("veto", verdict)
        self.assertNotIn("memory bias", verdict)


class TestBehaviouralDivergence(DivergenceTestCase):
    """No live trades at all - every entry the model would have taken was
    vetoed by memory, and logged as such. A pure behavioural discrepancy,
    with nothing to compare a fill on."""

    def setUp(self) -> None:
        super().setUp()
        self._install_champion()
        self.modelled = self._modelled_trades()
        for t in self.modelled:
            sig = Signal(1 if t.side == "long" else -1, 0.5, "would have entered")
            self.brain.b1.record_decision(
                t.entry_ts, "BTC/USDT", "veto:memory", sig, self.genome.id, executed=False
            )
        self.report = divergence.measure_divergence(self.brain, self.cfg)

    def test_nothing_is_matched_and_every_gap_is_a_memory_veto(self):
        sym = self.report.per_symbol["BTC/USDT"]
        self.assertEqual(sym.realised_trades, 0)
        self.assertEqual(sym.modelled_trades, len(self.modelled))
        self.assertEqual(sym.matched_entries, 0)
        self.assertEqual(sym.memory_declined, len(self.modelled))
        self.assertEqual(sym.risk_declined, 0)
        self.assertEqual(sym.unexplained_backtest_only, 0)
        self.assertEqual(sym.entry_fills, [])
        self.assertIsNone(sym.mean_entry_slippage_bps)

    def test_verdict_blames_the_agents_choice_not_the_model(self):
        verdict = self.report.verdict.lower()
        self.assertIn("memory", verdict)
        self.assertNotIn("fill", verdict)
        self.assertIn("not evidence the model", verdict)

    def test_differs_from_the_fill_divergence_verdict(self):
        """The two scenarios must not collapse into the same generic text -
        this is the "distinction actually discriminates" requirement."""
        other = TestFillDivergence()
        other.setUp()
        try:
            self.assertNotEqual(self.report.verdict, other.report.verdict)
        finally:
            other.tearDown()


class TestRiskVeto(DivergenceTestCase):
    """A risk veto is classified separately from a memory veto."""

    def setUp(self) -> None:
        super().setUp()
        self._install_champion()
        self.modelled = self._modelled_trades()
        for t in self.modelled:
            sig = Signal(1 if t.side == "long" else -1, 0.5, "would have entered")
            self.brain.b1.record_decision(
                t.entry_ts, "BTC/USDT", "veto:risk", sig, self.genome.id, executed=False
            )
        self.report = divergence.measure_divergence(self.brain, self.cfg)

    def test_counted_as_risk_not_memory(self):
        sym = self.report.per_symbol["BTC/USDT"]
        self.assertEqual(sym.risk_declined, len(self.modelled))
        self.assertEqual(sym.memory_declined, 0)
        self.assertIn("risk manager", self.report.verdict.lower())


class TestUnexplainedGap(DivergenceTestCase):
    """A missed entry with no veto logged at all is neither a fill problem
    nor a deliberate choice - it is flagged as unexplained."""

    def setUp(self) -> None:
        super().setUp()
        self._install_champion()
        self.modelled = self._modelled_trades()
        # Deliberately log nothing: no trade, no decision.
        self.report = divergence.measure_divergence(self.brain, self.cfg)

    def test_every_gap_is_unexplained(self):
        sym = self.report.per_symbol["BTC/USDT"]
        self.assertEqual(sym.unexplained_backtest_only, len(self.modelled))
        self.assertEqual(sym.memory_declined, 0)
        self.assertEqual(sym.risk_declined, 0)
        self.assertIn("no logged veto", self.report.verdict.lower())


class TestGracefulDegradation(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(data_dir=self.tmp.name, symbol="BTC/USDT", timeframe="1h")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_completely_empty_brain_does_not_raise(self):
        with DualBrain(self.cfg) as brain:
            report = divergence.measure_divergence(brain, self.cfg)
        self.assertIsNone(report.champion_id)
        self.assertIsNone(report.window)
        self.assertEqual(report.per_symbol, {})
        self.assertIn("no champion", report.verdict.lower())

    def test_champion_with_no_candles_or_trades_is_graceful(self):
        with DualBrain(self.cfg) as brain:
            genome = trend_follower_genome()
            brain.b1.save_genome(genome.id, 0, genome.to_dict(), 1.0, 1.0, {}, status="champion")
            report = divergence.measure_divergence(brain, self.cfg)
        self.assertEqual(report.champion_id, genome.id)
        self.assertIsInstance(report.verdict, str)
        self.assertTrue(report.verdict)
        # Too little history cached to backtest against - noted, not fatal.
        sym = report.per_symbol.get("BTC/USDT")
        self.assertIsNotNone(sym)
        self.assertTrue(sym.note)

    def test_champion_with_candles_but_no_live_trades_is_graceful(self):
        """Candles are cached and the model may well find entries in them,
        but with no live trade and no decision logged for any of them, every
        one of those bars reads as unexplained rather than raising - there
        is simply no live record yet to compare against."""
        with DualBrain(self.cfg) as brain:
            genome = trend_follower_genome()
            brain.b1.save_genome(genome.id, 0, genome.to_dict(), 1.0, 1.0, {}, status="champion")
            brain.b1.save_candles("BTC/USDT", "1h", make_candles(80))
            report = divergence.measure_divergence(brain, self.cfg)
        sym = report.per_symbol["BTC/USDT"]
        self.assertEqual(sym.realised_trades, 0)
        self.assertEqual(sym.memory_declined, 0)
        self.assertEqual(sym.risk_declined, 0)
        self.assertEqual(sym.unexplained_backtest_only, sym.modelled_trades)
        self.assertIsInstance(report.verdict, str)
        self.assertTrue(report.verdict)


class TestDashboardIntegration(unittest.TestCase):
    """The dashboard must render (and stay self-contained) whether or not
    there is divergence data to show."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _assert_self_contained(self, page: str) -> None:
        self.assertIn("<!doctype html>", page)
        for external in ("http://", "https://", "<script"):
            self.assertNotIn(external, page)

    def test_renders_without_any_divergence_data(self):
        cfg = Config(data_dir=self.tmp.name, symbol="BTC/USDT", timeframe="1h")
        with DualBrain(cfg) as brain:
            page = dashboard.render(brain, cfg)
        self._assert_self_contained(page)
        self.assertIn("Live vs backtest divergence", page)
        self.assertIn("no champion", page.lower())

    def test_renders_with_populated_divergence_data(self):
        cfg = Config(data_dir=self.tmp.name, symbol="BTC/USDT", timeframe="1h",
                     slippage_bps=5.0, fee_bps=10.0)
        with DualBrain(cfg) as brain:
            candles = make_candles()
            brain.b1.save_candles("BTC/USDT", "1h", candles)
            genome = trend_follower_genome()
            brain.b1.save_genome(genome.id, 0, genome.to_dict(), 1.0, 1.0, {}, status="champion")
            result = backtest.simulate(genome, candles, cfg)
            for t in result.trades:
                brain.remember_trade(Trade(
                    symbol="BTC/USDT", side=t.side, qty=t.qty, entry_ts=t.entry_ts,
                    entry_price=t.entry_price, exit_ts=t.exit_ts, exit_price=t.exit_price,
                    pnl=t.pnl, pnl_pct=t.pnl_pct, fees=t.fees, reason_open=t.reason_open,
                    reason_close=t.reason_close, genome_id=genome.id, regime=t.regime,
                ))
                sig = Signal(1 if t.side == "long" else -1, 0.5, "matched")
                brain.b1.record_decision(t.entry_ts, "BTC/USDT", f"open:{t.side}", sig,
                                         genome.id, executed=True)
                brain.b1.record_equity(t.exit_ts, cfg.start_cash + t.pnl, cfg.start_cash, 0.0)
            page = dashboard.render(brain, cfg)
        self._assert_self_contained(page)
        self.assertIn("Live vs backtest divergence", page)
        self.assertIn("Matched fills", page)
        self.assertIn("Entry slippage", page)

    def test_write_still_produces_a_file(self):
        cfg = Config(data_dir=self.tmp.name, symbol="BTC/USDT", timeframe="1h")
        with DualBrain(cfg) as brain:
            written = dashboard.write(brain, cfg, str(Path(self.tmp.name) / "out" / "dash.html"))
        self.assertTrue(Path(written).exists())


if __name__ == "__main__":
    unittest.main()
