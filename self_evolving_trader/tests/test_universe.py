"""Multi-market behaviour: one process, one champion, one shared memory."""

import tempfile
import unittest

from crypto_agent.agent import TradingAgent
from crypto_agent.brain.memory import DualBrain
from crypto_agent.config import Config
from crypto_agent.core.types import Position, Signal, timeframe_ms
from crypto_agent.data.providers import SyntheticProvider
from crypto_agent.evolution.engine import EvolutionEngine, _as_markets
from crypto_agent.execution.broker import PaperBroker
from crypto_agent.execution.risk import RiskManager
from crypto_agent.strategy.genome import seed_population
from tests.test_memory import make_trade

UNIVERSE = "ETH/USDT,SOL/USDT"


class TestSymbolList(unittest.TestCase):
    def test_primary_comes_first_and_duplicates_collapse(self):
        cfg = Config(symbol="BTC/USDT", symbols="eth/usdt, BTC/USDT ,SOL/USDT")
        self.assertEqual(cfg.symbol_list, ["BTC/USDT", "ETH/USDT", "SOL/USDT"])

    def test_a_bare_symbol_is_a_universe_of_one(self):
        self.assertEqual(Config(symbol="BTC/USDT").symbol_list, ["BTC/USDT"])

    def test_malformed_symbols_are_rejected(self):
        with self.assertRaises(ValueError):
            Config.load(None, symbols="BTCUSDT")


class TestMultiAssetBook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(data_dir=self.tmp.name, symbols=UNIVERSE, start_cash=10_000.0,
                          fee_bps=0.0, slippage_bps=0.0)
        self.brain = DualBrain(self.cfg)
        self.broker = PaperBroker(self.cfg, self.brain.b1)

    def tearDown(self):
        self.brain.close()
        self.tmp.cleanup()

    def test_holdings_are_tracked_per_symbol(self):
        self.broker.market_order("buy", 1.0, 100.0, 0, "ETH/USDT")
        self.broker.market_order("buy", 5.0, 20.0, 0, "SOL/USDT")
        self.assertAlmostEqual(self.broker.qty_of("ETH/USDT"), 1.0)
        self.assertAlmostEqual(self.broker.qty_of("SOL/USDT"), 5.0)
        self.assertAlmostEqual(self.broker.cash, 10_000.0 - 100.0 - 100.0)

    def test_equity_marks_every_holding(self):
        self.broker.market_order("buy", 1.0, 100.0, 0, "ETH/USDT")
        self.broker.market_order("buy", 5.0, 20.0, 0, "SOL/USDT")
        equity = self.broker.equity({"ETH/USDT": 110.0, "SOL/USDT": 30.0})
        self.assertAlmostEqual(equity, 9_800.0 + 110.0 + 150.0)

    def test_selling_one_market_leaves_the_other_alone(self):
        self.broker.market_order("buy", 1.0, 100.0, 0, "ETH/USDT")
        self.broker.market_order("buy", 5.0, 20.0, 0, "SOL/USDT")
        self.broker.market_order("sell", 1.0, 120.0, 1, "ETH/USDT")
        self.assertEqual(self.broker.qty_of("ETH/USDT"), 0.0)
        self.assertAlmostEqual(self.broker.qty_of("SOL/USDT"), 5.0)

    def test_a_single_symbol_book_is_migrated(self):
        """A brain written before the universe existed keeps its position."""
        self.brain.b1.set_state("broker.state", {"cash": 5_000.0, "qty": 2.0})
        migrated = PaperBroker(self.cfg, self.brain.b1)
        self.assertAlmostEqual(migrated.qty_of(self.cfg.symbol), 2.0)
        self.assertAlmostEqual(migrated.equity({self.cfg.symbol: 100.0}), 5_200.0)

    def test_positions_are_keyed_by_symbol(self):
        eth = Position("ETH/USDT", 1.0, 100.0, 0)
        sol = Position("SOL/USDT", 5.0, 20.0, 0)
        self.brain.b1.save_position("ETH/USDT", eth)
        self.brain.b1.save_position("SOL/USDT", sol)
        self.assertEqual(set(self.brain.b1.load_positions()), {"ETH/USDT", "SOL/USDT"})
        self.brain.b1.save_position("ETH/USDT", None)
        self.assertEqual(set(self.brain.b1.load_positions()), {"SOL/USDT"})
        self.assertIsNone(self.brain.b1.load_position("ETH/USDT"))

    def test_a_legacy_unkeyed_position_is_adopted(self):
        self.brain.b1.set_state("open_position", {
            "symbol": "ETH/USDT", "qty": 1.0, "entry_price": 100.0, "entry_ts": 0,
            "stop": 90.0, "take_profit": 120.0, "genome_id": "abc", "regime": "range_low_vol",
            "bars_held": 3,
        })
        book = self.brain.b1.load_positions()
        self.assertIn("ETH/USDT", book)
        self.assertAlmostEqual(book["ETH/USDT"].entry_price, 100.0)
        self.assertIsNone(self.brain.b1.get_state("open_position"))


class TestPortfolioRisk(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(data_dir=self.tmp.name, symbols=UNIVERSE, max_open_positions=2,
                          cooldown_bars_after_loss=3, max_trades_per_day=99)
        self.brain = DualBrain(self.cfg)
        self.risk = RiskManager(self.cfg, self.brain.b1)
        self.signal = Signal(1, 0.5, "long", {}, "uptrend_low_vol")
        self.ts = 1_700_000_000_000
        self.risk.observe_equity(10_000, self.ts)

    def tearDown(self):
        self.brain.close()
        self.tmp.cleanup()

    def test_the_position_cap_is_portfolio_wide(self):
        allowed = self.risk.check_entry(10_000, 10_000, 100.0, 95.0, self.signal, 1.0,
                                        now_ms=self.ts, symbol="SOL/USDT", open_positions=1)
        self.assertTrue(allowed.approved)
        blocked = self.risk.check_entry(10_000, 10_000, 100.0, 95.0, self.signal, 1.0,
                                        now_ms=self.ts, symbol="SOL/USDT", open_positions=2)
        self.assertFalse(blocked.approved)
        self.assertIn("already holding", blocked.reason)

    def test_a_loss_cools_down_only_the_coin_that_caused_it(self):
        loss = make_trade(pnl_pct=-0.03, ts=self.ts)
        loss.symbol, loss.exit_ts = "SOL/USDT", self.ts
        self.risk.on_trade_closed(loss, 9_900)
        later = self.ts + timeframe_ms(self.cfg.timeframe)

        cooled = self.risk.check_entry(9_900, 9_900, 100.0, 95.0, self.signal, 1.0,
                                       now_ms=later, symbol="SOL/USDT")
        self.assertFalse(cooled.approved)
        self.assertIn("SOL/USDT", cooled.reason)

        other = self.risk.check_entry(9_900, 9_900, 100.0, 95.0, self.signal, 1.0,
                                      now_ms=later, symbol="ETH/USDT")
        self.assertTrue(other.approved)


class TestEvolutionAcrossMarkets(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(data_dir=self.tmp.name, symbols=UNIVERSE, population_size=4,
                          elite_count=1, history_bars=700, oos_bars=200)
        self.brain = DualBrain(self.cfg)
        self.engine = EvolutionEngine(self.cfg, self.brain)
        self.history = {
            symbol: SyntheticProvider(seed=i + 1).fetch_ohlcv(symbol, "1h", 700)
            for i, symbol in enumerate(self.cfg.symbol_list)
        }

    def tearDown(self):
        self.brain.close()
        self.tmp.cleanup()

    def test_a_bare_series_is_treated_as_the_primary_market(self):
        rows = self.history[self.cfg.symbol]
        self.assertEqual(list(_as_markets(rows, "BTC/USDT")), ["BTC/USDT"])
        self.assertEqual(list(_as_markets({}, "BTC/USDT")), [])

    def test_fitness_is_scored_on_every_market(self):
        genome = seed_population(__import__("random").Random(1), 4, False)[0]
        ev = self.engine.evaluate(genome, self.history)
        self.assertEqual(set(ev.per_symbol), set(self.cfg.symbol_list))
        self.assertEqual(
            ev.pooled_oos_trades,
            sum(int(v["trades"]) for v in ev.per_symbol.values()),
        )

    def test_a_generation_runs_over_the_universe(self):
        report = self.engine.run_generation(self.history)
        self.assertEqual(report.evaluated, self.cfg.population_size)
        self.assertEqual(self.brain.b1.last_generation(), 1)


class TestAgentUniverse(unittest.TestCase):
    """The full loop, three markets, deterministic offline data."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(
            data_dir=self.tmp.name, provider="synthetic", timeframe="1h",
            symbol="BTC/USDT", symbols=UNIVERSE, history_bars=700, oos_bars=200,
            population_size=4, elite_count=1, evolve_every_steps=0,
            consolidate_every_steps=0, max_open_positions=2, max_trades_per_day=999,
            seed=5,
        )
        self.agent = TradingAgent(self.cfg)
        self.step_ms = timeframe_ms("1h")
        rows = SyntheticProvider(seed=5).fetch_ohlcv("BTC/USDT", "1h", 700)
        self.start_ts = rows[0].ts

    def tearDown(self):
        self.agent.close()
        self.tmp.cleanup()

    def _replay(self, bars=180, warmup=300):
        return [self.agent.cycle(now_ms=self.start_ts + (warmup + i) * self.step_ms)
                for i in range(bars)]

    def test_every_market_is_decided_on_each_cycle(self):
        cycle = self.agent.cycle(now_ms=self.start_ts + 400 * self.step_ms)
        self.assertEqual({r.symbol for r in cycle.results}, set(self.cfg.symbol_list))

    def test_trading_happens_across_markets_and_respects_the_cap(self):
        cycles = self._replay()
        traded = {r.symbol for c in cycles for r in c.results if r.action.startswith("open")}
        self.assertGreaterEqual(len(traded), 2, "expected entries in more than one market")
        most_open = max(
            len([r for r in c.results if r.action == "hold"]) for c in cycles
        )
        self.assertLessEqual(most_open, self.cfg.max_open_positions)

    def test_trades_are_booked_against_the_right_symbol(self):
        self._replay()
        trades = self.agent.brain.b1.recent_trades(50)
        self.assertTrue(trades)
        for trade in trades:
            self.assertIn(trade.symbol, self.cfg.symbol_list)
            self.assertIn(trade.symbol, trade.summary())

    def test_equity_equals_cash_plus_every_holding(self):
        self._replay()
        prices = {}
        for symbol in self.cfg.symbol_list:
            rows = self.agent.brain.b1.load_candles(symbol, self.cfg.timeframe, 1)
            if rows:
                prices[symbol] = rows[-1].close
        expected = self.agent.broker.cash + sum(
            qty * prices.get(sym, 0.0) for sym, qty in self.agent.broker.holdings.items()
        )
        self.assertAlmostEqual(self.agent.broker.equity(prices), expected, places=6)

    def test_the_primary_symbol_still_has_a_single_step_view(self):
        result = self.agent.step(now_ms=self.start_ts + 400 * self.step_ms)
        self.assertEqual(result.symbol, self.cfg.symbol)

    def test_status_reports_the_whole_book(self):
        self._replay(bars=60)
        status = self.agent.status()
        self.assertEqual(status["symbols"], self.cfg.symbol_list)
        self.assertLessEqual(len(status["positions"]), self.cfg.max_open_positions)
        for symbol in status["positions"]:
            self.assertIn(symbol, self.cfg.symbol_list)

    def test_one_broken_market_does_not_stop_the_others(self):
        working = self.agent.provider

        class Flaky:
            name = "flaky"

            def fetch_ohlcv(self, symbol, timeframe, limit):
                if symbol == "SOL/USDT":
                    raise ConnectionError("simulated outage")
                return working.fetch_ohlcv(symbol, timeframe, limit)

        self.agent.provider = Flaky()
        cycle = self.agent.cycle(now_ms=self.start_ts + 400 * self.step_ms)
        decided = {r.symbol for r in cycle.results}
        self.assertNotIn("SOL/USDT", decided)
        self.assertIn("BTC/USDT", decided)


if __name__ == "__main__":
    unittest.main()
