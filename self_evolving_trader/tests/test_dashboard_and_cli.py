import json
import tempfile
import unittest
from pathlib import Path

from crypto_agent import dashboard
from crypto_agent.brain.memory import DualBrain
from crypto_agent.cli import build_parser, config_from_args, stored_config
from crypto_agent.config import Config
from crypto_agent.core.types import Candle, Lesson
from tests.test_memory import make_trade


def candles(n=60, start=100.0):
    out = []
    price = start
    for i in range(n):
        open_price = price
        price *= 1.01 if i % 3 else 0.995
        out.append(Candle(i * 3_600_000, open_price, max(open_price, price) * 1.002,
                          min(open_price, price) * 0.998, price, 5.0))
    return out


class TestCharts(unittest.TestCase):
    def test_line_chart_emits_a_path_and_axis_labels(self):
        svg = dashboard.line_chart([100.0, 110.0, 105.0, 130.0], baseline=100.0)
        self.assertIn("<svg", svg)
        self.assertIn("<path", svg)
        self.assertIn("svg-baseline", svg)

    def test_charts_degrade_gracefully_when_empty(self):
        for svg in (dashboard.line_chart([]), dashboard.candle_chart([], []),
                    dashboard.fitness_chart([])):
            self.assertIn("<svg", svg)
            self.assertIn("svg-empty", svg)

    def test_flat_series_does_not_divide_by_zero(self):
        svg = dashboard.line_chart([100.0] * 20, baseline=100.0)
        self.assertIn("<path", svg)
        self.assertNotIn("nan", svg.lower())

    def test_candle_chart_marks_entries_and_exits(self):
        rows = candles(40)
        trade = make_trade(pnl_pct=0.05, ts=rows[5].ts)
        trade.entry_ts, trade.exit_ts = rows[5].ts, rows[20].ts
        trade.entry_price, trade.exit_price = rows[5].close, rows[20].close
        svg = dashboard.candle_chart(rows, [trade])
        self.assertIn("<polygon", svg)  # entry marker
        self.assertIn("<circle", svg)   # exit marker

    def test_fitness_chart_draws_both_series(self):
        gens = [{"best_fitness": i * 0.5, "mean_fitness": i * 0.2} for i in range(6)]
        svg = dashboard.fitness_chart(gens)
        self.assertEqual(svg.count("<path"), 2)


class TestDashboardPage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(data_dir=self.tmp.name, symbol="BTC/USDT", timeframe="1h")
        self.brain = DualBrain(self.cfg)

    def tearDown(self):
        self.brain.close()
        self.tmp.cleanup()

    def test_renders_on_a_completely_empty_brain(self):
        page = dashboard.render(self.brain, self.cfg)
        self.assertIn("<!doctype html>", page)
        self.assertIn("No open position", page)
        self.assertIn("Brain 2 is still empty", page)

    def test_renders_populated_state(self):
        self.brain.b1.save_candles("BTC/USDT", "1h", candles(80))
        for i in range(4):
            self.brain.remember_trade(make_trade(pnl_pct=0.02 if i % 2 else -0.01,
                                                 ts=1_000 + i * 10_000))
        self.brain.b1.record_equity(1_000, 10_100.0, 5_000.0, 5_100.0)
        self.brain.b1.record_equity(2_000, 10_250.0, 10_250.0, 0.0)
        self.brain.b1.record_generation(1, "abc123", 2.0, 1.0, ["abc123"])
        self.brain.b1.record_generation(2, "def456", 2.5, 1.4, ["def456"])
        self.brain.b2.remember(Lesson("regime 'uptrend_low_vol' long entries worked"))

        page = dashboard.render(self.brain, self.cfg)
        self.assertIn("BTC/USDT", page)
        self.assertIn("uptrend_low_vol", page)
        self.assertIn("Closed trades", page)
        self.assertGreaterEqual(page.count("<svg"), 3)

    def test_untrusted_text_is_escaped(self):
        evil = "<script>alert('xss')</script>"
        self.brain.b2.remember(Lesson(evil))
        self.brain.b1.log_event("test", evil)
        page = dashboard.render(self.brain, self.cfg)
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)

    def test_refresh_tag_is_opt_in(self):
        self.assertNotIn("http-equiv", dashboard.render(self.brain, self.cfg, 0))
        self.assertIn('content="15"', dashboard.render(self.brain, self.cfg, 15))

    def test_write_creates_the_file(self):
        target = Path(self.tmp.name) / "out" / "dash.html"
        written = dashboard.write(self.brain, self.cfg, str(target))
        self.assertTrue(Path(written).exists())
        self.assertIn("<!doctype html>", Path(written).read_text(encoding="utf-8"))

    def test_page_is_self_contained(self):
        page = dashboard.render(self.brain, self.cfg)
        for external in ("http://", "https://", "<script"):
            self.assertNotIn(external, page)


class TestStoredConfigAdoption(unittest.TestCase):
    """Inspection commands must describe the agent that actually ran."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        booted = Config(data_dir=self.tmp.name, symbol="ETH/USDT", timeframe="5m",
                        provider="binance", mode="paper")
        brain = DualBrain(booted)
        brain.b1.set_state("agent.config", booted.to_dict())
        brain.close()

    def tearDown(self):
        self.tmp.cleanup()

    def _args(self, argv):
        return build_parser().parse_args(["--data-dir", self.tmp.name] + argv)

    def test_stored_config_is_read_back(self):
        stored = stored_config(self.tmp.name)
        self.assertEqual(stored["symbol"], "ETH/USDT")
        self.assertEqual(stored["timeframe"], "5m")

    def test_status_adopts_the_stored_settings(self):
        cfg = config_from_args(self._args(["status"]), adopt_stored=True)
        self.assertEqual(cfg.symbol, "ETH/USDT")
        self.assertEqual(cfg.timeframe, "5m")
        self.assertEqual(cfg.provider, "binance")

    def test_explicit_flags_still_win(self):
        cfg = config_from_args(
            self._args(["--symbol", "SOL/USDT", "status"]), adopt_stored=True)
        self.assertEqual(cfg.symbol, "SOL/USDT")
        self.assertEqual(cfg.timeframe, "5m")  # unspecified, so adopted

    def test_stored_mode_is_never_adopted(self):
        """A stored live mode must not arm a read-only command."""
        path = Path(self.tmp.name) / "brain1_episodic.sqlite3"
        cfg = Config(data_dir=self.tmp.name, mode="live")
        brain = DualBrain(cfg)
        brain.b1.set_state("agent.config", {**cfg.to_dict(), "mode": "live"})
        brain.close()
        self.assertTrue(path.exists())
        self.assertNotIn("mode", stored_config(self.tmp.name))
        resolved = config_from_args(self._args(["status"]), adopt_stored=True)
        self.assertEqual(resolved.mode, "paper")

    def test_missing_or_corrupt_store_is_not_fatal(self):
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(stored_config(empty), {})
            broken = Path(empty) / "brain1_episodic.sqlite3"
            broken.write_text("not a database")
            self.assertEqual(stored_config(empty), {})

    def test_unknown_stored_keys_are_ignored(self):
        brain = DualBrain(Config(data_dir=self.tmp.name))
        brain.b1.set_state("agent.config", {"symbol": "ETH/USDT", "from_the_future": 1})
        brain.close()
        self.assertEqual(stored_config(self.tmp.name), {"symbol": "ETH/USDT"})
        self.assertIsInstance(json.dumps(stored_config(self.tmp.name)), str)


if __name__ == "__main__":
    unittest.main()
