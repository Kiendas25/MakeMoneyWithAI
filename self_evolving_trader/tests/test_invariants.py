"""Properties that must hold over a long run, not just on one call.

These are the checks that found the cash-overdraft bug: unit tests exercise a
decision, but a trading agent fails over *sequences* — a book that drifts from
its ledger, a kill switch that traps a position, storage that grows without
bound. Each test here drives a real multi-cycle replay and asserts an invariant
that should never be violated at any point along it.
"""

import tempfile
import unittest

from crypto_agent.agent import TradingAgent
from crypto_agent.config import Config
from crypto_agent.core.types import Candle, timeframe_ms
from crypto_agent.data.providers import SyntheticProvider

STEP_MS = timeframe_ms("1h")


def make_config(tmp, **over):
    base = dict(
        data_dir=tmp, provider="synthetic", timeframe="1h",
        symbols="ETH/USDT,XRP/USDT", history_bars=900, oos_bars=300,
        population_size=6, elite_count=2, evolve_every_steps=0,
        consolidate_every_steps=0, max_trades_per_day=999, seed=4,
    )
    base.update(over)
    return Config(**base)


def first_ts(seed):
    return SyntheticProvider(seed=seed).fetch_ohlcv("BTC/USDT", "1h", 900)[0].ts


class TestBookInvariants(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def _replay(self, agent, cycles, seed=4, warmup=400):
        start = first_ts(seed)
        for n in range(cycles):
            yield agent.cycle(now_ms=start + (warmup + n) * STEP_MS)

    def test_a_spot_book_never_goes_cash_negative(self):
        """The bug this suite was written for: sizing rescaled past the cash
        clamp, so the agent bought what it could not pay for."""
        for label, over in (
            ("max risk", {"risk_per_trade": 0.25, "max_position_pct": 1.0}),
            ("three positions", {"symbols": "ETH/USDT,XRP/USDT,BNB/USDT",
                                 "max_open_positions": 3}),
            ("tiny capital", {"start_cash": 200.0}),
        ):
            with self.subTest(label):
                with tempfile.TemporaryDirectory() as tmp:
                    agent = TradingAgent(make_config(tmp, **over))
                    try:
                        worst = min(
                            [agent.broker.cash for _ in self._replay(agent, 150)] or [0.0]
                        )
                        self.assertGreaterEqual(worst, -1e-6, f"{label}: overdrew to {worst}")
                    finally:
                        agent.close()

    def test_equity_always_equals_cash_plus_marked_holdings(self):
        agent = TradingAgent(make_config(self.tmp.name))
        try:
            for cycle in self._replay(agent, 150):
                prices = {r.symbol: r.price for r in cycle.results if r.price}
                if not prices:
                    continue
                expected = agent.broker.cash + sum(
                    qty * prices.get(sym, 0.0)
                    for sym, qty in agent.broker.holdings.items()
                )
                self.assertAlmostEqual(agent.broker.equity(prices), expected, places=6)
        finally:
            agent.close()

    def test_the_ledger_and_the_book_never_disagree(self):
        """Brain 1's positions and the broker's holdings are two records of the
        same fact; if they drift, every risk limit downstream is computed from
        a fiction."""
        agent = TradingAgent(make_config(self.tmp.name))
        try:
            for _ in self._replay(agent, 150):
                ledger = set(agent.brain.b1.load_positions())
                book = {s for s, q in agent.broker.holdings.items() if abs(q) > 1e-12}
                self.assertEqual(ledger, book)
        finally:
            agent.close()

    def test_the_position_cap_is_never_exceeded(self):
        agent = TradingAgent(make_config(
            self.tmp.name, symbols="ETH/USDT,XRP/USDT,BNB/USDT", max_open_positions=2))
        try:
            for _ in self._replay(agent, 150):
                self.assertLessEqual(len(agent.brain.b1.load_positions()), 2)
        finally:
            agent.close()


class TestKillSwitchDoesNotTrapPositions(unittest.TestCase):
    """A halt must stop new risk, not imprison existing risk.

    An agent that cannot close what it already holds has turned its own safety
    limit into the worst kind of exposure: a losing position nobody can exit.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.agent = TradingAgent(make_config(
            self.tmp.name, symbols="", symbol="BTC/USDT", seed=11))
        self.start = first_ts(11)

    def tearDown(self):
        self.agent.close()
        self.tmp.cleanup()

    def test_a_halted_agent_still_exits_but_never_enters(self):
        opened_at = None
        for n in range(250):
            self.agent.cycle(now_ms=self.start + (400 + n) * STEP_MS)
            if self.agent.brain.b1.load_positions():
                opened_at = n
                break
        self.assertIsNotNone(opened_at, "probe inconclusive: never opened a position")

        self.agent.risk.halt("test: kill switch tripped while holding")
        opened = closed = 0
        for k in range(250):
            cycle = self.agent.cycle(
                now_ms=self.start + (400 + opened_at + 1 + k) * STEP_MS)
            opened += sum(1 for r in cycle.results if r.action.startswith("open"))
            closed += sum(1 for r in cycle.results if r.action.startswith("close"))
            if not self.agent.brain.b1.load_positions():
                break
        self.assertEqual(opened, 0, "a halted agent opened a new position")
        self.assertGreater(closed, 0, "a halted agent could not exit what it held")
        self.assertEqual(self.agent.brain.b1.load_positions(), {})


class TestStateAndStorage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_restart_mid_flight_preserves_the_whole_book(self):
        cfg = make_config(self.tmp.name, symbols="ETH/USDT,XRP/USDT", seed=8)
        start = first_ts(8)

        agent = TradingAgent(cfg)
        for n in range(120):
            agent.cycle(now_ms=start + (400 + n) * STEP_MS)
        before = self._snapshot(agent)
        agent.close()

        restarted = TradingAgent(cfg)  # exactly what Ctrl-C and relaunch does
        try:
            self.assertEqual(self._snapshot(restarted), before)
        finally:
            restarted.close()

    @staticmethod
    def _snapshot(agent):
        return (
            round(agent.broker.cash, 9),
            {s: round(q, 9) for s, q in agent.broker.holdings.items()},
            {s: round(p.entry_price, 9) for s, p in agent.brain.b1.load_positions().items()},
            agent.brain.b1.trade_stats()["trades"],
            agent.brain.b1.get_state("agent.steps"),
        )

    def test_key_value_state_stays_bounded_over_a_long_run(self):
        """Caches keyed by bar timestamp would leave one dead row per bar."""
        agent = TradingAgent(make_config(
            self.tmp.name, symbols="ETH/USDT,XRP/USDT,BNB/USDT", seed=8))
        start = first_ts(8)
        try:
            def kv_rows():
                return agent.brain.b1._conn.execute(  # noqa: SLF001 - storage is the subject
                    "SELECT COUNT(*) FROM kv").fetchone()[0]

            for n in range(60):
                agent.cycle(now_ms=start + (400 + n) * STEP_MS)
            early = kv_rows()
            for n in range(60, 200):
                agent.cycle(now_ms=start + (400 + n) * STEP_MS)
            self.assertLessEqual(
                kv_rows(), early + 5,
                "key-value state is growing with the number of bars processed")
        finally:
            agent.close()


class CorrelatedProvider:
    """Markets that move together, the way real majors do.

    The synthetic provider seeds each symbol independently, so a correlation
    cap can never bind against it — which means a replay on synthetic data
    cannot prove the cap is wired correctly. This one drives every market from
    one shared factor: four names, one bet.
    """

    name = "correlated"

    def __init__(self, symbols, seed=1, bars=900, shared=0.95):
        import math
        import random

        rng = random.Random(seed)
        factor = [rng.gauss(0.0005, 0.02) for _ in range(bars)]
        self.series = {}
        for i, symbol in enumerate(symbols):
            idiosyncratic = random.Random(seed + i + 1)
            rows, price, ts = [], 100.0 * (i + 1), 0
            for r in factor:
                ret = shared * r + (1.0 - shared) * idiosyncratic.gauss(0.0, 0.02)
                open_price = price
                price *= math.exp(ret)
                rows.append(Candle(ts, open_price, max(open_price, price) * 1.001,
                                   min(open_price, price) * 0.999, price, 10.0))
                ts += STEP_MS
            self.series[symbol] = rows

    def fetch_ohlcv(self, symbol, timeframe, limit):
        return self.series.get(symbol, [])[-limit:]


class TestCorrelatedExposureCapBinds(unittest.TestCase):
    """The cluster cap must actually hold in the live loop, not just in a unit
    test of the risk manager. A units mismatch between what the agent passes
    and what the risk manager expects would disable it silently, and on
    independent synthetic markets nothing would ever reveal that."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cap = 0.4
        cfg = make_config(
            self.tmp.name, symbols="ETH/USDT,XRP/USDT,BNB/USDT",
            max_open_positions=5, max_correlated_exposure_pct=self.cap, seed=6)
        self.symbols = cfg.symbol_list
        self.agent = TradingAgent(cfg, provider=CorrelatedProvider(self.symbols))

    def tearDown(self):
        self.agent.close()
        self.tmp.cleanup()

    def test_exposure_to_one_cluster_stays_under_the_cap(self):
        refusals, peak = 0, 0.0
        for n in range(200):
            cycle = self.agent.cycle(now_ms=(400 + n) * STEP_MS)
            prices = {r.symbol: r.price for r in cycle.results if r.price}
            refusals += sum(1 for r in cycle.results if "cluster" in r.reason)
            if prices:
                equity = self.agent.broker.equity(prices)
                held = sum(self.agent._notional_held(prices).values())  # noqa: SLF001
                if equity > 0:
                    peak = max(peak, held / equity)
        self.assertGreater(refusals, 0, "the cluster cap never fired on correlated markets")
        self.assertLessEqual(peak, self.cap + 0.02, f"cluster exposure reached {peak:.0%}")


if __name__ == "__main__":
    unittest.main()
