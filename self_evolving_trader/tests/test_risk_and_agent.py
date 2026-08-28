import tempfile
import unittest

from crypto_agent.agent import TradingAgent
from crypto_agent.brain.memory import DualBrain
from crypto_agent.config import Config
from crypto_agent.core.types import Signal, timeframe_ms
from crypto_agent.data.providers import SyntheticProvider
from crypto_agent.execution.broker import PaperBroker
from crypto_agent.execution.risk import RiskManager
from crypto_agent.evolution.reflect import HeuristicReflector, validate_hints
from tests.test_memory import make_trade


class TestConfig(unittest.TestCase):
    def test_env_and_file_overrides_are_typed(self):
        cfg = Config.load(None, symbol="ETH/USDT", risk_per_trade="0.02", allow_short="true",
                          population_size="8")
        self.assertEqual(cfg.symbol, "ETH/USDT")
        self.assertEqual(cfg.risk_per_trade, 0.02)
        self.assertIs(cfg.allow_short, True)
        self.assertEqual(cfg.population_size, 8)

    def test_invalid_values_are_rejected(self):
        for bad in ({"timeframe": "7h"}, {"mode": "yolo"}, {"risk_per_trade": 0.9},
                    {"max_drawdown_pct": 3.0}, {"population_size": 2}, {"nonsense": 1}):
            with self.assertRaises(ValueError, msg=str(bad)):
                Config.load(None, **bad)


class TestPaperBroker(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(data_dir=self.tmp.name, start_cash=10_000.0, fee_bps=10.0,
                          slippage_bps=5.0)
        self.brain = DualBrain(self.cfg)
        self.broker = PaperBroker(self.cfg, self.brain.b1)

    def tearDown(self):
        self.brain.close()
        self.tmp.cleanup()

    def test_buy_then_sell_at_the_same_price_loses_exactly_the_costs(self):
        self.broker.market_order("buy", 0.1, 100.0, 0)
        self.broker.market_order("sell", 0.1, 100.0, 1)
        # two crossings of a 5bp spread plus two 10bp fees on ~10 notional
        self.assertLess(self.broker.equity(100.0), 10_000.0)
        self.assertGreater(self.broker.equity(100.0), 10_000.0 - 0.1)
        self.assertEqual(self.broker.qty, 0.0)

    def test_equity_marks_the_open_position_to_market(self):
        self.broker.market_order("buy", 1.0, 100.0, 0)
        self.assertAlmostEqual(self.broker.equity(110.0) - self.broker.equity(100.0), 10.0, places=6)

    def test_balances_survive_a_restart(self):
        self.broker.market_order("buy", 0.5, 100.0, 0)
        cash, qty = self.broker.cash, self.broker.qty
        reopened = PaperBroker(self.cfg, self.brain.b1)
        self.assertAlmostEqual(reopened.cash, cash)
        self.assertAlmostEqual(reopened.qty, qty)

    def test_bad_orders_are_refused(self):
        with self.assertRaises(ValueError):
            self.broker.market_order("buy", 0.0, 100.0, 0)
        with self.assertRaises(ValueError):
            self.broker.market_order("hodl", 1.0, 100.0, 0)


class TestRiskManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(data_dir=self.tmp.name, start_cash=10_000.0, max_drawdown_pct=0.2,
                          max_daily_loss_pct=0.04, max_trades_per_day=3,
                          cooldown_bars_after_loss=2, min_notional=10.0)
        self.brain = DualBrain(self.cfg)
        self.risk = RiskManager(self.cfg, self.brain.b1)
        self.signal = Signal(1, 0.5, "long", {}, "uptrend_low_vol")
        # Daily limits key off market time, so the tests pin a bar timestamp
        # instead of depending on when they happen to run.
        self.ts = 1_700_000_000_000
        self.risk.observe_equity(10_000, self.ts)

    def tearDown(self):
        self.brain.close()
        self.tmp.cleanup()

    def test_a_normal_entry_is_approved(self):
        decision = self.risk.check_entry(10_000, 10_000, 100.0, 95.0, self.signal, 1.0,
                                         now_ms=self.ts)
        self.assertTrue(decision.approved)
        self.assertGreater(decision.qty, 0)

    def test_drawdown_kill_switch_halts_and_persists(self):
        self.risk.observe_equity(7_000, self.ts)  # -30% from the peak
        self.assertTrue(self.risk.halted)
        self.assertFalse(self.risk.check_entry(7_000, 7_000, 100.0, 95.0, self.signal, 1.0,
                                               now_ms=self.ts).approved)
        reloaded = RiskManager(self.cfg, self.brain.b1)
        self.assertTrue(reloaded.halted)
        reloaded.resume()
        self.assertFalse(RiskManager(self.cfg, self.brain.b1).halted)

    def test_daily_loss_limit_blocks_new_entries(self):
        decision = self.risk.check_entry(9_500, 9_500, 100.0, 95.0, self.signal, 1.0,
                                         now_ms=self.ts)
        self.assertFalse(decision.approved)
        self.assertIn("daily loss", decision.reason)

    def test_a_new_market_day_resets_the_daily_counters(self):
        self.risk.state["trades_today"] = 99
        next_day = self.ts + 86_400_000
        decision = self.risk.check_entry(10_000, 10_000, 100.0, 95.0, self.signal, 1.0,
                                         now_ms=next_day)
        self.assertTrue(decision.approved)
        self.assertEqual(self.risk.state["trades_today"], 0)

    def test_trade_cap_and_cooldown(self):
        self.risk.state["trades_today"] = 3
        self.assertIn("daily trade cap", self.risk.check_entry(
            10_000, 10_000, 100.0, 95.0, self.signal, 1.0, now_ms=self.ts).reason)
        self.risk.state["trades_today"] = 0
        loss = make_trade(pnl_pct=-0.02, ts=self.ts)
        loss.exit_ts = self.ts
        self.risk.on_trade_closed(loss, 9_990)
        blocked = self.risk.check_entry(9_990, 9_990, 100.0, 95.0, self.signal, 1.0,
                                        now_ms=self.ts + timeframe_ms(self.cfg.timeframe))
        self.assertIn("cooling down", blocked.reason)

    def test_shorting_is_refused_when_disabled(self):
        short = Signal(-1, -0.5, "short", {}, "downtrend_high_vol")
        self.assertFalse(self.risk.check_entry(10_000, 10_000, 100.0, 105.0, short, 1.0,
                                               now_ms=self.ts).approved)

    def test_memory_size_multiplier_scales_the_order(self):
        full = self.risk.check_entry(10_000, 10_000, 100.0, 95.0, self.signal, 1.0,
                                     size_mult=1.0, now_ms=self.ts)
        half = self.risk.check_entry(10_000, 10_000, 100.0, 95.0, self.signal, 1.0,
                                     size_mult=0.5, now_ms=self.ts)
        self.assertAlmostEqual(half.qty, full.qty * 0.5, places=6)


class TestReflector(unittest.TestCase):
    def test_stop_heavy_history_suggests_wider_stops(self):
        trades = [make_trade(pnl_pct=-0.01, ts=i * 1000, reason_close="stop_loss")
                  for i in range(10)]
        lessons = HeuristicReflector().reflect(trades, {"fees": 5.0, "net_pnl": -50.0})
        hints = {g: v for l in lessons for g, v in l.meta["gene_hints"].items()}
        self.assertGreater(hints.get("stop_atr_mult", 0), 0)

    def test_hints_are_whitelisted_and_bounded(self):
        clean = validate_hints({"stop_atr_mult": 99, "not_a_gene": 1, "tp_atr_mult": "x"})
        self.assertEqual(clean, {"stop_atr_mult": 2.0})

    def test_thin_history_yields_no_conclusions(self):
        self.assertEqual(HeuristicReflector().reflect([make_trade()], {}), [])


class TestAgentEndToEnd(unittest.TestCase):
    """The whole loop on deterministic offline data."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(
            data_dir=self.tmp.name, provider="synthetic", mode="paper", timeframe="1h",
            history_bars=900, oos_bars=200, population_size=6, elite_count=2,
            evolve_every_steps=40, consolidate_every_steps=20, poll_seconds=0.0, seed=11,
            max_trades_per_day=1000, start_cash=10_000.0,
        )
        self.agent = TradingAgent(self.cfg)
        candles = SyntheticProvider(seed=self.cfg.seed).fetch_ohlcv(
            self.cfg.symbol, self.cfg.timeframe, self.cfg.history_bars
        )
        self.start_ts = candles[0].ts
        self.step_ms = timeframe_ms(self.cfg.timeframe)

    def tearDown(self):
        self.agent.close()
        self.tmp.cleanup()

    def _replay(self, bars=260, warmup=200):
        results = []
        for i in range(bars):
            now = self.start_ts + (warmup + i) * self.step_ms
            results.append(self.agent.step(now_ms=now))
        return results

    def test_replay_produces_decisions_trades_and_generations(self):
        results = self._replay()
        actions = [r.action for r in results]
        self.assertTrue(any(a.startswith("open") for a in actions), actions[:20])
        self.assertTrue(any(a.startswith("close") for a in actions))
        self.assertGreater(self.agent.brain.b1.trade_stats()["trades"], 0)
        self.assertGreater(len(self.agent.brain.b1.recent_decisions(5)), 0)
        self.assertGreaterEqual(self.agent.brain.b1.last_generation(), 1)
        self.assertGreater(self.agent.brain.b2.count(), 0)

    def test_equity_accounting_is_consistent(self):
        self._replay()
        curve = self.agent.brain.b1.equity_curve(limit=10_000)
        self.assertTrue(curve)
        price = self.agent.brain.b1.load_candles(self.cfg.symbol, self.cfg.timeframe, 1)[-1].close
        self.assertAlmostEqual(
            self.agent.broker.equity(price),
            self.agent.broker.cash + self.agent.broker.qty * price,
            places=6,
        )
        self.assertTrue(all(row["equity"] > 0 for row in curve))

    def test_a_second_pass_over_the_same_bar_does_nothing(self):
        now = self.start_ts + 240 * self.step_ms
        self.agent.step(now_ms=now)
        again = self.agent.step(now_ms=now)
        self.assertEqual(again.action, "waiting")

    def test_state_survives_a_restart_mid_run(self):
        self._replay(bars=120)
        steps = self.agent.brain.b1.get_state("agent.steps")
        position = self.agent.brain.b1.load_position(self.cfg.symbol)
        trades = self.agent.brain.b1.trade_stats()["trades"]
        self.agent.close()

        self.agent = TradingAgent(self.cfg)
        self.assertEqual(self.agent.brain.b1.get_state("agent.steps"), steps)
        self.assertEqual(self.agent.brain.b1.trade_stats()["trades"], trades)
        reloaded = self.agent.brain.b1.load_position(self.cfg.symbol)
        if position is None:
            self.assertIsNone(reloaded)
        else:
            self.assertAlmostEqual(reloaded.qty, position.qty)
            self.assertAlmostEqual(reloaded.entry_price, position.entry_price)

    def test_status_reports_a_champion_and_memory_counts(self):
        self._replay(bars=100)
        status = self.agent.status()
        self.assertEqual(status["mode"], "paper")
        self.assertIsNotNone(status["champion"])
        self.assertIn("brain1", status["memory"])
        self.assertIn("brain2", status["memory"])

    def test_evolution_improves_or_holds_the_champion_out_of_sample(self):
        candles = self.agent.closed_candles(self.start_ts + 800 * self.step_ms)
        before = self.agent.engine.champion()
        reports = self.agent.engine.evolve(candles, generations=2)
        self.assertEqual(len(reports), 2)
        record = self.agent.engine.champion_record()
        self.assertIsNotNone(record)
        if record["id"] != before.id:
            # A promotion must be justified out-of-sample, never in-sample only.
            self.assertGreater(record["oos_fitness"], 0.0)

    def test_halted_risk_stops_new_entries_in_the_loop(self):
        self.agent.risk.halt("test halt")
        results = self._replay(bars=60)
        self.assertFalse(any(r.action.startswith("open") for r in results))


if __name__ == "__main__":
    unittest.main()


class TestProcessLiveness(unittest.TestCase):
    """The lockfile's liveness probe must never be able to kill anything."""

    def test_current_process_is_alive(self):
        import os as _os

        from crypto_agent.agent import _pid_alive

        self.assertTrue(_pid_alive(_os.getpid()))

    def test_absent_and_invalid_pids_are_dead(self):
        from crypto_agent.agent import _pid_alive

        self.assertFalse(_pid_alive(0))
        self.assertFalse(_pid_alive(-1))

    def test_a_reaped_child_is_reported_dead(self):
        import subprocess
        import sys

        from crypto_agent.agent import _pid_alive

        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        proc.wait()
        self.assertFalse(_pid_alive(proc.pid))

    def test_windows_probe_never_calls_os_kill(self):
        """os.kill on Windows terminates; the probe must not go near it."""
        import os as _os
        import unittest.mock as mock

        from crypto_agent import agent as agent_module

        with mock.patch.object(_os, "name", "nt"), \
             mock.patch.object(_os, "kill", side_effect=AssertionError("os.kill must not be called on Windows")), \
             mock.patch.object(agent_module, "_pid_alive_windows", return_value=True) as probe:
            self.assertTrue(agent_module._pid_alive(4242))
        probe.assert_called_once_with(4242)
