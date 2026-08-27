"""Regression tests for the risk-manager resume() kill switch and the
correlation_window knob (see crypto_agent/execution/risk.py, config.py).
"""

import tempfile
import unittest

from crypto_agent.brain.memory import DualBrain
from crypto_agent.config import Config
from crypto_agent.core.types import Candle, Signal, timeframe_ms
from crypto_agent.execution.risk import RiskManager


class TestResumeRebaselinesWatermarks(unittest.TestCase):
    """resume() must be a real restart, not just a flag flip.

    Before the fix, resume() cleared ``halted`` but left ``peak_equity`` at
    the pre-crash high and set ``day_start_equity`` to that same peak. The
    very next observe_equity() at the (much lower) current equity then
    recomputed the identical drawdown and daily loss and re-halted
    immediately - the operator's only manual recovery lever did nothing.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(data_dir=self.tmp.name, start_cash=10_000.0,
                          max_drawdown_pct=0.2, max_daily_loss_pct=0.9)
        self.brain = DualBrain(self.cfg)
        self.risk = RiskManager(self.cfg, self.brain.b1)
        self.ts = 1_700_000_000_000

    def tearDown(self):
        self.brain.close()
        self.tmp.cleanup()

    def test_resume_after_drawdown_halt_does_not_instantly_re_halt(self):
        # Peak at 10,000, then a crash to 7,000 (-30%) trips the 20% drawdown
        # kill switch.
        self.risk.observe_equity(10_000, self.ts)
        self.risk.observe_equity(7_000, self.ts)
        self.assertTrue(self.risk.halted)
        self.assertEqual(self.risk.state["peak_equity"], 10_000)

        # The agent records an equity snapshot every cycle, including the one
        # that caused the halt - this is what resume() re-baselines from.
        self.brain.b1.record_equity(self.ts, 7_000, 7_000, 0.0)

        self.risk.resume()
        self.assertFalse(self.risk.halted)
        self.assertEqual(self.risk.state["peak_equity"], 7_000)
        self.assertEqual(self.risk.state["day_start_equity"], 7_000)

        # Reproduce the bug: observing the *same* current equity right after
        # resume must not immediately re-trip the kill switch or the daily
        # loss limit.
        self.risk.observe_equity(7_000, self.ts)
        self.assertFalse(self.risk.halted)
        self.assertEqual(self.risk.daily_loss_pct(7_000), 0.0)

        signal = Signal(1, 0.5, "long", {}, "uptrend_low_vol")
        decision = self.risk.check_entry(7_000, 7_000, 100.0, 95.0, signal, 1.0,
                                         now_ms=self.ts)
        self.assertTrue(decision.approved, decision.reason)

    def test_resume_without_recorded_equity_falls_back_to_peak(self):
        # No record_equity() has been called - equity_curve() is empty - so
        # resume() has nothing fresher than the stored peak to fall back to.
        self.risk.observe_equity(10_000, self.ts)
        self.risk.halt("manual test halt")
        self.risk.resume()
        self.assertEqual(self.risk.state["peak_equity"], 10_000)
        self.assertEqual(self.risk.state["day_start_equity"], 10_000)

    def test_resume_persists_across_reload(self):
        self.risk.observe_equity(10_000, self.ts)
        self.risk.observe_equity(7_000, self.ts)
        self.brain.b1.record_equity(self.ts, 7_000, 7_000, 0.0)
        self.risk.resume()
        reloaded = RiskManager(self.cfg, self.brain.b1)
        self.assertFalse(reloaded.halted)
        self.assertEqual(reloaded.state["peak_equity"], 7_000)


class TestCorrelationWindow(unittest.TestCase):
    """correlation_window must actually bound how much history is measured.

    The series below is constructed so the two halves disagree: symbol B
    mirrors -A for the first 250 bars (strong negative correlation) and then
    mirrors +A exactly for the last 49 bars (perfect positive correlation).
    A narrow window sees only the second half; a wide one sees the whole
    contradictory series.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _make_series(returns, start=100.0, start_ts=0):
        tf = timeframe_ms("1h")
        closes = [start]
        for r in returns:
            closes.append(closes[-1] * (1 + r))
        out = []
        ts = start_ts
        for close in closes:
            out.append(Candle(ts, close, close, close, close, 1.0))
            ts += tf
        return out

    def _price_history(self):
        seq = [0.02, -0.01, 0.015, -0.008, 0.005, -0.017, 0.009, -0.003]
        anti_len, mirror_len = 250, 49
        a_returns = [seq[i % len(seq)] for i in range(anti_len + mirror_len)]
        b_returns = [-r for r in a_returns[:anti_len]] + list(a_returns[anti_len:])
        return {"A": self._make_series(a_returns), "B": self._make_series(b_returns)}

    def _risk(self, correlation_window):
        cfg = Config(data_dir=self.tmp.name + str(correlation_window), start_cash=10_000.0,
                    correlation_window=correlation_window, correlation_threshold=0.7)
        brain = DualBrain(cfg)
        self.addCleanup(brain.close)
        return RiskManager(cfg, brain.b1)

    def test_narrow_window_sees_only_the_recent_positive_correlation(self):
        risk = self._risk(correlation_window=50)  # last 50 closes -> 49 returns, all mirrored
        clusters, pairs = risk._correlation_clusters(self._price_history())
        self.assertAlmostEqual(pairs[("A", "B")].value, 1.0, places=6)
        self.assertIn(sorted(["A", "B"]), [sorted(c) for c in clusters])

    def test_wide_window_sees_the_full_contradictory_history(self):
        risk = self._risk(correlation_window=1000)  # exceeds the series length -> full history
        clusters, pairs = risk._correlation_clusters(self._price_history())
        self.assertLess(pairs[("A", "B")].value, 0.0)
        self.assertNotIn(sorted(["A", "B"]), [sorted(c) for c in clusters])

    def test_window_changes_a_real_entry_decision(self):
        # Same data, same equity/holdings - only correlation_window differs -
        # yet the two risk managers disagree about whether B is "the same
        # bet" as an existing A position.
        history = self._price_history()
        holdings = {"A": 4_000.0}
        signal = Signal(1, 0.5, "long", {}, "uptrend_low_vol")

        narrow = self._risk(correlation_window=50)
        narrow.observe_equity(10_000, 0)
        narrow_decision = narrow.check_entry(
            10_000, 6_000, 100.0, 95.0, signal, 1.0, now_ms=0, symbol="B",
            price_history=history, holdings=holdings,
        )
        self.assertFalse(narrow_decision.approved)
        self.assertIn("correlated", narrow_decision.reason)

        wide = self._risk(correlation_window=1000)
        wide.observe_equity(10_000, 0)
        wide_decision = wide.check_entry(
            10_000, 6_000, 100.0, 95.0, signal, 1.0, now_ms=0, symbol="B",
            price_history=history, holdings=holdings,
        )
        self.assertTrue(wide_decision.approved, wide_decision.reason)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
