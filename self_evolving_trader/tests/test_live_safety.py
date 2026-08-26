"""Safety tests for CcxtBroker: order-quantity rounding, the live-mode gates,
and reconciliation against the real exchange state.

ccxt is an optional dependency and is not installed in this environment, so
these tests never import it for real. Instead a fake ``ccxt`` module carrying
a small stub exchange is injected into ``sys.modules`` before construction,
matching the shape ``CcxtBroker`` actually calls: ``markets``,
``load_markets``, ``amount_to_precision``, ``create_order`` and
``fetch_balance``.
"""

import os
import sys
import tempfile
import types
import unittest

from crypto_agent.brain.hippocampus import Hippocampus
from crypto_agent.config import Config
from crypto_agent.execution.broker import (
    BrokerOrderError,
    CcxtBroker,
    LIVE_CONFIRMATION_ENV,
    LIVE_CONFIRMATION_VALUE,
    PaperBroker,
    ReconcileReport,
)


class FakeExchange:
    """Just enough of ccxt's unified exchange interface for CcxtBroker."""

    def __init__(self, config=None):
        self.config = config or {}
        self.password = None
        self.markets = {
            "BTC/USDT": {
                # step size of 0.001 BTC, minimum order value of 10 USDT
                "limits": {"amount": {"min": 0.001}, "cost": {"min": 10.0}},
                "precision": {"amount": 3},
            }
        }
        self.balance = {"free": {"USDT": 1_000.0, "BTC": 0.5}, "used": {}, "total": {}}
        self.load_markets_calls = 0
        self.orders = []  # (symbol, type, side, amount) for every create_order call
        self.next_order = None  # override the canned "closed, fully filled" response
        self.next_order_error = None
        self.open_orders = []

    def load_markets(self):
        self.load_markets_calls += 1
        return self.markets

    def amount_to_precision(self, symbol, amount):
        decimals = self.markets[symbol]["precision"]["amount"]
        return f"{amount:.{decimals}f}"

    def create_order(self, symbol, type_, side, amount, price=None, params=None):
        self.orders.append((symbol, type_, side, amount))
        if self.next_order_error is not None:
            raise self.next_order_error
        if self.next_order is not None:
            return self.next_order
        return {
            "id": "order-1",
            "status": "closed",
            "filled": amount,
            "average": 100.0,
            "fee": {"cost": amount * 100.0 * 0.001},
        }

    def fetch_balance(self):
        return self.balance

    def fetch_open_orders(self, symbol=None):
        return self.open_orders


class CcxtBrokerTestCase(unittest.TestCase):
    """Base class that arms the live-mode gates and injects a fake ccxt."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.brain = Hippocampus(f"{self.tmp.name}/brain1.sqlite3")
        self.addCleanup(self.brain.close)

        self._env_patches = {
            LIVE_CONFIRMATION_ENV: LIVE_CONFIRMATION_VALUE,
            "CRYPTO_AGENT_API_KEY": "key",
            "CRYPTO_AGENT_API_SECRET": "secret",
        }
        self._saved_env = {k: os.environ.get(k) for k in self._env_patches}
        os.environ.update(self._env_patches)
        self.addCleanup(self._restore_env)

        self._old_ccxt = sys.modules.get("ccxt")
        self.exchange = FakeExchange()
        fake_ccxt = types.ModuleType("ccxt")
        fake_ccxt.binance = lambda config=None, _exchange=self.exchange: _exchange
        sys.modules["ccxt"] = fake_ccxt
        self.addCleanup(self._restore_ccxt)

        self.cfg = Config(data_dir=self.tmp.name, mode="live", symbol="BTC/USDT",
                          exchange="binance", min_notional=10.0)

    def _restore_env(self):
        for key, old in self._saved_env.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

    def _restore_ccxt(self):
        if self._old_ccxt is None:
            sys.modules.pop("ccxt", None)
        else:
            sys.modules["ccxt"] = self._old_ccxt

    def make_broker(self) -> CcxtBroker:
        return CcxtBroker(self.cfg, self.brain)


class TestLiveModeGates(CcxtBrokerTestCase):
    def test_refuses_without_live_mode(self):
        cfg = Config(data_dir=self.tmp.name, mode="paper", symbol="BTC/USDT", exchange="binance")
        with self.assertRaises(RuntimeError):
            CcxtBroker(cfg, self.brain)

    def test_refuses_without_confirmation_env(self):
        os.environ.pop(LIVE_CONFIRMATION_ENV, None)
        with self.assertRaises(RuntimeError):
            self.make_broker()

    def test_refuses_with_wrong_confirmation_value(self):
        os.environ[LIVE_CONFIRMATION_ENV] = "yes please"
        with self.assertRaises(RuntimeError):
            self.make_broker()

    def test_refuses_without_api_credentials(self):
        os.environ.pop("CRYPTO_AGENT_API_KEY", None)
        with self.assertRaises(RuntimeError):
            self.make_broker()

    def test_constructs_when_everything_is_armed(self):
        broker = self.make_broker()
        self.assertEqual(broker.name, "ccxt")
        # the live-armed event is what an operator would grep the log for
        events = self.brain.recent_events(50)
        self.assertTrue(any(e["kind"] == "broker" for e in events))


class TestQuantityRounding(CcxtBrokerTestCase):
    def test_loads_markets_on_construction(self):
        self.make_broker()
        self.assertEqual(self.exchange.load_markets_calls, 1)

    def test_quantity_rounds_down_to_step_size(self):
        broker = self.make_broker()
        # 0.046713 BTC at a 0.001 step must floor to 0.046, never round to 0.047
        rounded = broker._round_amount_down("BTC/USDT", 0.046713)
        self.assertAlmostEqual(rounded, 0.046, places=9)

    def test_exact_multiple_of_step_is_not_knocked_down(self):
        broker = self.make_broker()
        rounded = broker._round_amount_down("BTC/USDT", 0.045)
        self.assertAlmostEqual(rounded, 0.045, places=9)

    def test_market_order_sends_the_rounded_quantity_to_the_exchange(self):
        broker = self.make_broker()
        broker.market_order("buy", 0.146713, 100.0, 0)
        self.assertEqual(len(self.exchange.orders), 1)
        _, _, _, sent_amount = self.exchange.orders[0]
        self.assertAlmostEqual(sent_amount, 0.146, places=9)

    def test_sub_minimum_notional_is_refused(self):
        broker = self.make_broker()
        # 0.001 BTC (one step) at $100 is $0.10, far under the $10 minimum
        with self.assertRaises(BrokerOrderError):
            broker.market_order("buy", 0.0015, 100.0, 0)
        # and refusing it must not have sent anything to the exchange
        self.assertEqual(self.exchange.orders, [])

    def test_quantity_that_floors_to_zero_is_refused_before_reaching_the_exchange(self):
        broker = self.make_broker()
        with self.assertRaises(BrokerOrderError):
            broker.market_order("buy", 0.0004, 100.0, 0)  # under one 0.001 step
        self.assertEqual(self.exchange.orders, [])


class TestOrderFailureHandling(CcxtBrokerTestCase):
    def test_exchange_rejection_raises_and_does_not_report_a_fill(self):
        broker = self.make_broker()
        self.exchange.next_order_error = RuntimeError("insufficient balance")
        with self.assertRaises(BrokerOrderError):
            broker.market_order("buy", 0.01, 100.0, 0)
        # local cache must be untouched by an order that never filled
        self.assertAlmostEqual(broker.cash, 1_000.0)

    def test_zero_fill_status_raises_instead_of_a_phantom_fill(self):
        broker = self.make_broker()
        self.exchange.next_order = {"id": "x", "status": "open", "filled": 0.0}
        with self.assertRaises(BrokerOrderError):
            broker.market_order("buy", 0.01, 100.0, 0)
        self.assertAlmostEqual(broker.cash, 1_000.0)

    def test_full_fill_updates_the_local_cache(self):
        broker = self.make_broker()
        cash_before = broker.cash
        fill = broker.market_order("buy", 0.2, 100.0, 0)
        self.assertGreater(fill.qty, 0)
        self.assertLess(broker.cash, cash_before)


class TestReconcile(CcxtBrokerTestCase):
    def test_reconcile_corrects_a_drifted_local_book_and_logs_it(self):
        broker = self.make_broker()
        # simulate a crash-mid-order: local cache still shows the pre-order
        # balance, but the exchange has already moved.
        broker._cash = 999.0
        broker._holdings = {"BTC/USDT": 0.4}
        self.exchange.balance = {"free": {"USDT": 700.0, "BTC": 0.55}, "used": {}, "total": {}}

        report = broker.reconcile()

        self.assertIsInstance(report, ReconcileReport)
        self.assertEqual(report.broker, "ccxt")
        self.assertFalse(report.clean)
        self.assertIn("cash", report.corrected)
        self.assertIn("holdings:BTC/USDT", report.corrected)
        self.assertAlmostEqual(broker.cash, 700.0)
        self.assertAlmostEqual(broker.qty, 0.55)

        events = self.brain.recent_events(50)
        self.assertTrue(any(e["kind"] == "reconcile" and e["level"] == "WARNING" for e in events))

    def test_reconcile_on_an_already_correct_book_reports_clean(self):
        broker = self.make_broker()
        report = broker.reconcile()
        self.assertTrue(report.clean)
        self.assertEqual(report.corrected, {})

    def test_reconcile_counts_open_orders(self):
        broker = self.make_broker()
        self.exchange.open_orders = [{"id": "a"}, {"id": "b"}]
        report = broker.reconcile()
        self.assertEqual(report.open_orders, 2)


class TestPaperBrokerReconcile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.brain = Hippocampus(f"{self.tmp.name}/brain1.sqlite3")
        self.addCleanup(self.brain.close)
        self.cfg = Config(data_dir=self.tmp.name, symbol="BTC/USDT", start_cash=5_000.0)
        self.broker = PaperBroker(self.cfg, self.brain)

    def test_reconcile_returns_the_same_report_shape_and_touches_nothing(self):
        self.broker.market_order("buy", 0.2, 100.0, 0)
        cash_before, holdings_before = self.broker.cash, self.broker.holdings

        report = self.broker.reconcile()

        self.assertIsInstance(report, ReconcileReport)
        self.assertEqual(report.broker, "paper")
        self.assertTrue(report.clean)
        self.assertEqual(report.corrected, {})
        self.assertEqual(report.open_orders, 0)
        self.assertEqual(self.broker.cash, cash_before)
        self.assertEqual(self.broker.holdings, holdings_before)


if __name__ == "__main__":
    unittest.main()
