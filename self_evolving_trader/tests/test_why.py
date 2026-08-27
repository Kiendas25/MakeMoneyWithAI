"""Tallying why the agent did or did not open anything.

Twice in one session the answer to "it is running but nothing is happening"
was guessed at instead of looked up - once wrongly. Every decision already
carried its action and reason; the ledger could answer the question all along.
"""

import tempfile
import unittest
from pathlib import Path

from crypto_agent.brain.hippocampus import Hippocampus, _decision_bucket
from crypto_agent.config import Config
from crypto_agent.core.types import Signal


def signal(reason, score=0.1):
    return Signal(direction=0, score=score, reason=reason,
                  features={"trend": 0.5}, regime="range_low_vol")


class TestDecisionBucket(unittest.TestCase):
    def test_the_action_decides_the_category_not_the_signal_text(self):
        # A held position and an opened one both carry a "long score ..."
        # reason; only the action separates them.
        text = "long score +0.30 vs 0.18, led by trend (+0.82)"
        self.assertEqual(_decision_bucket("open:long", text), "opened a position")
        self.assertEqual(_decision_bucket("hold", text), "already in a position, holding")

    def test_vetoes_are_named(self):
        self.assertIn("memory", _decision_bucket("veto:memory", "long score +0.4"))
        self.assertIn("risk", _decision_bucket("veto:risk", "long score +0.4"))

    def test_closes_keep_their_cause(self):
        self.assertEqual(_decision_bucket("close:stop_loss", "x"),
                         "closed a position (stop_loss)")

    def test_a_flat_decision_falls_through_to_its_reason(self):
        cases = {
            "stand aside score +0.16 vs 0.18, led by trend (+0.87)":
                "score below the entry threshold",
            "volatility 0.041 above genome ceiling 0.038":
                "volatility above the genome's ceiling",
            "genome stands aside in range_low_vol":
                "genome stands aside in a ranging market",
            "target 0.21% below the 0.45% cost floor":
                "target below the cost floor",
            "warming up": "warming up",
        }
        for reason, expected in cases.items():
            with self.subTest(reason=reason):
                self.assertEqual(_decision_bucket("flat", reason), expected)

    def test_live_numbers_do_not_split_a_bucket(self):
        a = _decision_bucket("flat", "volatility 0.041 above genome ceiling 0.038")
        b = _decision_bucket("flat", "volatility 0.099 above genome ceiling 0.038")
        self.assertEqual(a, b)

    def test_an_empty_reason_does_not_produce_an_empty_label(self):
        self.assertTrue(_decision_bucket("flat", "").strip())


class TestDecisionReasons(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.b1 = Hippocampus(Path(self.tmp.name) / "b1.sqlite3")

    def tearDown(self):
        self.b1.close()
        self.tmp.cleanup()

    def _record(self, action, reason, executed, n=1, ts=0):
        for i in range(n):
            self.b1.record_decision(ts + i, "BTC/USDT", action, signal(reason),
                                    "g1", executed)

    def test_counts_are_ordered_by_frequency(self):
        self._record("flat", "stand aside score +0.1 vs 0.3", False, n=5)
        self._record("open:long", "long score +0.4 vs 0.3", True, n=2, ts=100)
        buckets = self.b1.decision_reasons()
        self.assertEqual(buckets[0]["reason"], "score below the entry threshold")
        self.assertEqual(buckets[0]["count"], 5)
        self.assertEqual(buckets[1]["count"], 2)

    def test_executed_is_tallied_separately_from_count(self):
        self._record("open:long", "long score +0.4 vs 0.3", True, n=3)
        opened = next(b for b in self.b1.decision_reasons()
                      if b["reason"] == "opened a position")
        self.assertEqual(opened["executed"], 3)

    def test_an_example_of_the_real_text_is_kept(self):
        self._record("flat", "volatility 0.041 above genome ceiling 0.038", False)
        bucket = self.b1.decision_reasons()[0]
        self.assertIn("0.041", bucket["example"])

    def test_empty_ledger_returns_nothing_rather_than_failing(self):
        self.assertEqual(self.b1.decision_reasons(), [])

    def test_the_limit_looks_at_recent_decisions_only(self):
        self._record("flat", "stand aside score +0.1 vs 0.3", False, n=10)
        self._record("open:long", "long score +0.4 vs 0.3", True, n=2, ts=100)
        buckets = self.b1.decision_reasons(limit=2)
        self.assertEqual(sum(b["count"] for b in buckets), 2)
        self.assertEqual(buckets[0]["reason"], "opened a position")


class TestCostHurdle(unittest.TestCase):
    """Costs are fixed per trade; the move on offer scales with the bar. On a
    fast enough timeframe the round trip is the whole range and nothing in the
    gene space can win - which is a fact about the market, worth stating
    plainly rather than leaving the agent to discover it one loss at a time.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.b1 = Hippocampus(Path(self.tmp.name) / "b1.sqlite3")

    def tearDown(self):
        self.b1.close()
        self.tmp.cleanup()

    def _store(self, bar_pct):
        from crypto_agent.core.types import Candle
        candles = []
        price = 100.0
        for i in range(300):
            half = price * bar_pct / 2
            candles.append(Candle(ts=i * 300_000, open=price, high=price + half,
                                  low=price - half, close=price, volume=1.0))
        self.b1.save_candles("BTC/USDT", "5m", candles)

    def _hurdle(self, bar_pct, trip=0.003):
        from crypto_agent.cli import _print_hurdle
        import io
        import contextlib
        self._store(bar_pct)
        cfg = Config(data_dir=self.tmp.name, symbol="BTC/USDT", timeframe="5m")

        class Brain:
            b1 = self.b1

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            _print_hurdle(Brain(), cfg, trip)
        return out.getvalue()

    def test_a_fast_market_is_called_unwinnable(self):
        # 0.1% bars against a 0.3% round trip: costs are 3x the whole range.
        text = self._hurdle(0.001)
        self.assertIn("more than a whole typical bar", text)
        self.assertIn("1h", text)

    def test_a_slow_market_gets_no_warning(self):
        # 3% bars: the round trip is a tenth of the move on offer.
        text = self._hurdle(0.03)
        self.assertNotIn("more than a whole typical bar", text)
        self.assertNotIn("Costs eat a large share", text)

    def test_the_middle_case_is_flagged_as_tight_not_hopeless(self):
        text = self._hurdle(0.005)
        self.assertIn("Costs eat a large share", text)

    def test_a_market_without_history_says_so_rather_than_failing(self):
        from crypto_agent.cli import _print_hurdle
        import io
        import contextlib
        cfg = Config(data_dir=self.tmp.name, symbol="BTC/USDT", timeframe="5m")

        class Brain:
            b1 = self.b1

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            _print_hurdle(Brain(), cfg, 0.003)
        self.assertIn("not enough cached history", out.getvalue())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
