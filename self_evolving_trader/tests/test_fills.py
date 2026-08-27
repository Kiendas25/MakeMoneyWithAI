"""The local book must follow the fill, never the request.

A live exchange rounds an order down to its lot size, or fills only part of it
against a thin book. If the agent records what it *asked for* instead of what it
*got*, the position is larger than the real balance: every stop and risk check
is computed against inventory that does not exist, and the eventual exit order
is rejected for insufficient funds. The same asymmetry on the way out is worse —
clearing a position after a partial exit orphans real exposure that nothing is
managing any more.
"""

import tempfile
import unittest

from crypto_agent.agent import TradingAgent
from crypto_agent.config import Config
from crypto_agent.core.types import Fill, timeframe_ms
from crypto_agent.data.providers import SyntheticProvider
from crypto_agent.execution.broker import PaperBroker

STEP_MS = timeframe_ms("1h")


class PartialFillBroker(PaperBroker):
    """A paper broker that fills only a fraction of what it is asked for."""

    def __init__(self, cfg, brain, fraction=0.5):
        super().__init__(cfg, brain)
        self.fraction = fraction
        self.requested = []

    def market_order(self, side, qty, price, ts, symbol=None):
        self.requested.append(qty)
        fill = super().market_order(side, qty * self.fraction, price, ts, symbol)
        return fill


class EmptyFillBroker(PaperBroker):
    """A broker whose order returns without filling anything at all."""

    def market_order(self, side, qty, price, ts, symbol=None):
        return Fill(ts=ts, side=side, qty=0.0, price=price, fee=0.0)


def make_agent(tmp, broker_cls=None, **over):
    cfg = Config(
        data_dir=tmp, provider="synthetic", timeframe="1h", symbol="BTC/USDT",
        history_bars=900, oos_bars=300, population_size=6, elite_count=2,
        evolve_every_steps=0, consolidate_every_steps=0, max_trades_per_day=999,
        seed=11, **over)
    agent = TradingAgent(cfg)
    if broker_cls is not None:
        agent.broker = broker_cls(cfg, agent.brain.b1)
    return agent


def first_ts(seed=11):
    return SyntheticProvider(seed=seed).fetch_ohlcv("BTC/USDT", "1h", 900)[0].ts


class TestEntryFollowsTheFill(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.start = first_ts()

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_partial_entry_records_only_what_filled(self):
        agent = make_agent(self.tmp.name, PartialFillBroker)
        try:
            for n in range(250):
                agent.cycle(now_ms=self.start + (400 + n) * STEP_MS)
                book = agent.brain.b1.load_positions()
                if book:
                    position = book["BTC/USDT"]
                    held = agent.broker.qty_of("BTC/USDT")
                    self.assertAlmostEqual(
                        abs(position.qty), abs(held), places=9,
                        msg="position records more than the broker actually holds")
                    self.assertLess(abs(position.qty), agent.broker.requested[-1],
                                    "a half fill was recorded as a full one")
                    return
            self.skipTest("no position opened in the replay window")
        finally:
            agent.close()

    def test_an_unfilled_order_opens_no_position(self):
        agent = make_agent(self.tmp.name, EmptyFillBroker)
        try:
            actions = []
            for n in range(120):
                cycle = agent.cycle(now_ms=self.start + (400 + n) * STEP_MS)
                actions += [r.action for r in cycle.results]
                self.assertEqual(
                    agent.brain.b1.load_positions(), {},
                    "an order that filled nothing still created a position")
            self.assertIn("open:unfilled", actions,
                          "the empty fill was never surfaced as its own outcome")
        finally:
            agent.close()


class TestExitFollowsTheFill(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.start = first_ts()

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_partial_exit_keeps_managing_the_remainder(self):
        """The half that did not sell is still real exposure."""
        agent = make_agent(self.tmp.name)
        try:
            opened_at = None
            for n in range(250):
                agent.cycle(now_ms=self.start + (400 + n) * STEP_MS)
                if agent.brain.b1.load_positions():
                    opened_at = n
                    break
            if opened_at is None:
                self.skipTest("no position opened in the replay window")

            before = abs(agent.brain.b1.load_positions()["BTC/USDT"].qty)
            # From here every exit fills only half of what is asked.
            agent.broker.__class__ = PartialFillBroker
            agent.broker.fraction = 0.5
            agent.broker.requested = []

            for k in range(250):
                agent.cycle(now_ms=self.start + (400 + opened_at + 1 + k) * STEP_MS)
                book = agent.brain.b1.load_positions()
                if not book:
                    continue
                remaining = abs(book["BTC/USDT"].qty)
                if remaining < before * 0.99:  # an exit has partially filled
                    self.assertAlmostEqual(
                        remaining, abs(agent.broker.qty_of("BTC/USDT")), places=9,
                        msg="the ledger lost track of the unsold remainder")
                    self.assertGreater(remaining, 0.0)
                    return
            self.skipTest("no exit occurred in the replay window")
        finally:
            agent.close()

    def test_a_full_exit_still_clears_the_position(self):
        """The partial-exit handling must not leave dust behind on a clean exit."""
        agent = make_agent(self.tmp.name)
        try:
            opened_at = None
            for n in range(250):
                agent.cycle(now_ms=self.start + (400 + n) * STEP_MS)
                if agent.brain.b1.load_positions():
                    opened_at = n
                    break
            if opened_at is None:
                self.skipTest("no position opened in the replay window")
            for k in range(250):
                agent.cycle(now_ms=self.start + (400 + opened_at + 1 + k) * STEP_MS)
                if not agent.brain.b1.load_positions():
                    self.assertEqual(agent.broker.qty_of("BTC/USDT"), 0.0)
                    return
            self.skipTest("no exit occurred in the replay window")
        finally:
            agent.close()


if __name__ == "__main__":
    unittest.main()
