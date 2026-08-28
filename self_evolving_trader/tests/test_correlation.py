"""Correlation measurement, clustering, and the risk manager's cluster cap."""

import math
import random
import tempfile
import unittest

from crypto_agent.brain.memory import DualBrain
from crypto_agent.config import Config
from crypto_agent.core.types import Candle, Signal
from crypto_agent.data.correlation import cluster_symbols, correlation
from crypto_agent.execution.risk import RiskManager

STEP_MS = 3_600_000  # 1h bars - arbitrary but realistic


def _returns(seed: int, n: int, vol: float = 0.02):
    rng = random.Random(seed)
    return [rng.gauss(0.0, vol) for _ in range(n)]


def _candles_from_returns(returns, start_ts=0, start_price=100.0, step_ms=STEP_MS, skip_every=None):
    """Build a candle series whose closes follow the given log returns.

    ``skip_every`` drops every Nth bar to simulate a gap, while every bar that
    does survive keeps its original timestamp - so two series built this way
    from the same returns are only ever comparable at the timestamps they
    both happen to have.
    """
    price = start_price
    out = []
    ts = start_ts
    for i, r in enumerate(returns):
        price *= math.exp(r)
        if skip_every is None or (i % skip_every != 0):
            out.append(Candle(ts, price, price, price, price, 0.0))
        ts += step_ms
    return out


class TestPairwiseCorrelation(unittest.TestCase):
    def test_perfectly_correlated_series_score_near_one(self):
        rets = _returns(1, 200)
        a = _candles_from_returns(rets, start_price=100.0)
        b = _candles_from_returns(rets, start_price=50.0)  # different scale, same path
        result = correlation(a, b)
        self.assertTrue(result.known)
        self.assertAlmostEqual(result.value, 1.0, places=6)

    def test_anti_correlated_series_score_near_negative_one(self):
        rets = _returns(2, 200)
        a = _candles_from_returns(rets, start_price=100.0)
        b = _candles_from_returns([-r for r in rets], start_price=100.0)
        result = correlation(a, b)
        self.assertTrue(result.known)
        self.assertAlmostEqual(result.value, -1.0, places=6)

    def test_unrelated_series_score_near_zero(self):
        a = _candles_from_returns(_returns(3, 300), start_price=100.0)
        b = _candles_from_returns(_returns(4, 300), start_price=100.0)
        result = correlation(a, b)
        self.assertTrue(result.known)
        self.assertLess(abs(result.value), 0.3)

    def test_misaligned_and_gapped_timestamps_still_align_correctly(self):
        rets = _returns(5, 250)
        # `a` keeps every bar and runs on longer than `b`; `b` is missing
        # every fourth bar entirely. The values that survive in both are
        # still the same scaled path, so alignment on ts (not position)
        # should recover the same correlation as the ungapped case.
        a = _candles_from_returns(rets, start_price=100.0)
        b = _candles_from_returns(rets, start_price=25.0, skip_every=4)
        self.assertNotEqual(len(a), len(b))
        result = correlation(a, b)
        self.assertTrue(result.known)
        self.assertGreater(result.value, 0.999)
        # every 4th of 250 points is dropped from b; overlap is a bit under 250
        self.assertLess(result.n, 250)
        self.assertGreater(result.n, 150)

    def test_too_few_overlapping_points_is_unknown_not_zero(self):
        rets = _returns(6, 10)
        a = _candles_from_returns(rets, start_price=100.0)
        b = _candles_from_returns(rets, start_price=100.0)
        result = correlation(a, b)
        self.assertFalse(result.known)
        self.assertIsNone(result.value)
        self.assertIn("overlapping", result.reason)

    def test_zero_variance_series_is_unknown_not_zero(self):
        flat = [Candle(i * STEP_MS, 100.0, 100.0, 100.0, 100.0, 0.0) for i in range(50)]
        moving = _candles_from_returns(_returns(7, 50), start_price=100.0)
        result = correlation(flat, moving)
        self.assertFalse(result.known)
        self.assertIsNone(result.value)
        self.assertIn("zero-variance", result.reason)

    def test_unknown_and_a_real_number_are_distinguishable(self):
        """A caller must never mistake "unknown" for a genuine zero correlation."""
        rets = _returns(8, 200)
        a = _candles_from_returns(rets, start_price=100.0)
        b = _candles_from_returns([-r for r in rets], start_price=100.0)
        known_zero_ish = correlation(a, b)  # anti-correlated, not zero, but exercises .known
        too_short = correlation(a[:5], b[:5])
        self.assertTrue(known_zero_ish.known)
        self.assertFalse(too_short.known)
        self.assertNotEqual(known_zero_ish.value, too_short.value)


class TestClustering(unittest.TestCase):
    def test_a_correlated_pair_clusters_and_an_independent_series_stays_alone(self):
        rets = _returns(9, 200)
        histories = {
            "BTC/USDT": _candles_from_returns(rets, start_price=30_000.0),
            "ETH/USDT": _candles_from_returns(rets, start_price=2_000.0),
            "XRP/USDT": _candles_from_returns(_returns(10, 200), start_price=0.5),
        }
        clusters, pairs = cluster_symbols(histories, threshold=0.7)
        by_symbol = {s: sorted(c) for c in clusters for s in c}
        self.assertEqual(by_symbol["BTC/USDT"], ["BTC/USDT", "ETH/USDT"])
        self.assertEqual(by_symbol["ETH/USDT"], ["BTC/USDT", "ETH/USDT"])
        self.assertEqual(by_symbol["XRP/USDT"], ["XRP/USDT"])
        self.assertAlmostEqual(pairs[("BTC/USDT", "ETH/USDT")].value, 1.0, places=6)


class TestCheckEntryCorrelationCap(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(
            data_dir=self.tmp.name, symbols="ETH/USDT,XRP/USDT", start_cash=10_000.0,
            max_trades_per_day=99, max_open_positions=5,
        )
        self.brain = DualBrain(self.cfg)
        self.risk = RiskManager(self.cfg, self.brain.b1)
        self.signal = Signal(1, 0.5, "long", {}, "uptrend_low_vol")
        self.ts = 1_700_000_000_000
        self.risk.observe_equity(10_000, self.ts)

        rets = _returns(11, 60)
        self.price_history = {
            "BTC/USDT": _candles_from_returns(rets, start_ts=0, start_price=30_000.0),
            "ETH/USDT": _candles_from_returns(rets, start_ts=0, start_price=2_000.0),
            "XRP/USDT": _candles_from_returns(_returns(12, 60), start_ts=0, start_price=0.5),
        }
        # Already holding 35% of equity in BTC; BTC and ETH are ~1.0 correlated
        # by construction, above the default 0.7 threshold.
        self.holdings = {"BTC/USDT": 3_500.0}

    def tearDown(self):
        self.brain.close()
        self.tmp.cleanup()

    def test_a_correlated_third_entry_is_refused(self):
        decision = self.risk.check_entry(
            10_000, 10_000, 100.0, 95.0, self.signal, 1.0, now_ms=self.ts,
            symbol="ETH/USDT", price_history=self.price_history, holdings=self.holdings,
        )
        self.assertFalse(decision.approved)
        self.assertIn("cluster", decision.reason)
        self.assertIn("BTC/USDT", decision.reason)
        self.assertIn("ETH/USDT", decision.reason)
        self.assertIn("cap 50%", decision.reason)

    def test_an_uncorrelated_entry_is_allowed(self):
        decision = self.risk.check_entry(
            10_000, 10_000, 100.0, 95.0, self.signal, 1.0, now_ms=self.ts,
            symbol="XRP/USDT", price_history=self.price_history, holdings=self.holdings,
        )
        self.assertTrue(decision.approved)
        self.assertGreater(decision.qty, 0)

    def test_the_correlation_matrix_is_cached_and_does_not_accumulate_rows(self):
        """Cached per bar, but under one key - a key per bar would leak a kv
        row on every single bar, forever."""
        key = "risk.correlation.BTC/USDT|ETH/USDT|XRP/USDT"
        self.assertIsNone(self.risk.brain.get_state(key))

        def decide(now_ms):
            return self.risk.check_entry(
                10_000, 10_000, 100.0, 95.0, self.signal, 1.0, now_ms=now_ms,
                symbol="ETH/USDT", price_history=self.price_history,
                holdings=self.holdings,
            )

        decide(self.ts)
        cached = self.risk.brain.get_state(key)
        self.assertIsNotNone(cached)
        self.assertIn("clusters", cached)
        self.assertIn("bar_ts", cached)

        decide(self.ts + 60_000)
        rows = [k for k in self._cache_keys() if k.startswith("risk.correlation")]
        self.assertEqual(len(rows), 1, f"cache should hold one row, found {rows}")

    def _cache_keys(self):
        conn = self.risk.brain._conn  # noqa: SLF001 - inspecting storage is the point
        return [r[0] for r in conn.execute("SELECT key FROM kv").fetchall()]


class TestBackwardCompatibility(unittest.TestCase):
    """Every existing check_entry call signature must keep working unchanged."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(data_dir=self.tmp.name, start_cash=10_000.0, max_trades_per_day=99)
        self.brain = DualBrain(self.cfg)
        self.risk = RiskManager(self.cfg, self.brain.b1)
        self.signal = Signal(1, 0.5, "long", {}, "uptrend_low_vol")
        self.ts = 1_700_000_000_000
        self.risk.observe_equity(10_000, self.ts)

    def tearDown(self):
        self.brain.close()
        self.tmp.cleanup()

    def test_no_correlation_data_skips_the_check_entirely(self):
        decision = self.risk.check_entry(
            10_000, 10_000, 100.0, 95.0, self.signal, 1.0, now_ms=self.ts,
        )
        self.assertTrue(decision.approved)

    def test_positional_and_keyword_call_shapes_from_before_this_change_still_work(self):
        approved = self.risk.check_entry(10_000, 10_000, 100.0, 95.0, self.signal, 1.0,
                                         now_ms=self.ts)
        self.assertTrue(approved.approved)
        approved2 = self.risk.check_entry(10_000, 10_000, 100.0, 95.0, self.signal, 1.0,
                                          size_mult=0.5, now_ms=self.ts, symbol="ETH/USDT",
                                          open_positions=0)
        self.assertTrue(approved2.approved)


if __name__ == "__main__":
    unittest.main()


class TestCashIsNeverOverdrawn(unittest.TestCase):
    """A spot book cannot spend money it does not have.

    position_size() fits the order to available cash, but the memory size
    multiplier and the equity-based notional cap both rescale after it — and
    equity exceeds cash whenever another position is open. A real exchange
    rejects such an order; on paper it silently books negative cash.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(data_dir=self.tmp.name, start_cash=10_000.0,
                          risk_per_trade=0.25, max_position_pct=1.0,
                          min_notional=10.0, fee_bps=10.0)
        self.brain = DualBrain(self.cfg)
        self.risk = RiskManager(self.cfg, self.brain.b1)
        self.signal = Signal(1, 0.5, "long", {}, "uptrend_low_vol")
        self.ts = 1_700_000_000_000
        self.risk.observe_equity(10_000, self.ts)

    def tearDown(self):
        self.brain.close()
        self.tmp.cleanup()

    def _cost(self, decision, price):
        """What the broker will actually take out of cash: the slipped fill
        price plus the fee charged on it."""
        return (decision.qty * price
                * (1.0 + self.cfg.slippage_bps / 10_000.0)
                * (1.0 + self.cfg.fee_bps / 10_000.0))

    def test_a_memory_upsize_cannot_outspend_the_cash_on_hand(self):
        cash = 1_000.0  # the rest of equity is tied up in another position
        decision = self.risk.check_entry(10_000, cash, 100.0, 95.0, self.signal, 1.0,
                                         size_mult=1.5, now_ms=self.ts)
        self.assertTrue(decision.approved)
        self.assertLessEqual(self._cost(decision, 100.0), cash + 1e-9)

    def test_the_notional_cap_cannot_outspend_the_cash_on_hand(self):
        cash = 500.0
        decision = self.risk.check_entry(10_000, cash, 100.0, 99.9, self.signal, 1.0,
                                         now_ms=self.ts)
        if decision.approved:
            self.assertLessEqual(self._cost(decision, 100.0), cash + 1e-9)

    def test_an_unaffordable_order_is_refused_rather_than_shrunk_to_dust(self):
        decision = self.risk.check_entry(10_000, 5.0, 100.0, 95.0, self.signal, 1.0,
                                         now_ms=self.ts)
        self.assertFalse(decision.approved)
        self.assertIn("minimum notional", decision.reason)

    def test_shorts_are_not_clamped_by_cash(self):
        """Selling short raises cash rather than spending it."""
        cfg = Config(**{**self.cfg.to_dict(), "allow_short": True})
        risk = RiskManager(cfg, self.brain.b1)
        risk.observe_equity(10_000, self.ts)
        short = Signal(-1, -0.5, "short", {}, "downtrend_high_vol")
        decision = risk.check_entry(10_000, 1.0, 100.0, 105.0, short, 1.0, now_ms=self.ts)
        self.assertTrue(decision.approved)
        self.assertGreater(decision.qty, 0.0)
