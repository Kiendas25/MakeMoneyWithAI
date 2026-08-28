import tempfile
import unittest
from pathlib import Path

from crypto_agent.brain.cortex import Cortex
from crypto_agent.brain.embeddings import HashingEmbedder, cosine
from crypto_agent.brain.memory import DualBrain
from crypto_agent.config import Config
from crypto_agent.core.types import Candle, Lesson, Signal, Trade


def make_trade(pnl_pct=0.02, regime="uptrend_low_vol", side="long", ts=1_000, genome="abc123",
               reason_close="take_profit"):
    pnl = pnl_pct * 1000.0
    return Trade(
        symbol="BTC/USDT", side=side, qty=0.1, entry_ts=ts, entry_price=100.0,
        exit_ts=ts + 3_600_000, exit_price=100.0 * (1 + pnl_pct), pnl=pnl, pnl_pct=pnl_pct,
        fees=1.0, reason_open="long score +0.40 led by trend", reason_close=reason_close,
        genome_id=genome, regime=regime,
    )


class TestEmbeddings(unittest.TestCase):
    def test_same_text_same_vector_across_instances(self):
        a = HashingEmbedder(128).embed("stop loss in a downtrend")
        b = HashingEmbedder(128).embed("stop loss in a downtrend")
        self.assertEqual(a, b)

    def test_vectors_are_unit_length(self):
        vec = HashingEmbedder(64).embed("volatility spike liquidation cascade")
        self.assertAlmostEqual(sum(v * v for v in vec) ** 0.5, 1.0, places=6)

    def test_related_text_scores_higher_than_unrelated(self):
        emb = HashingEmbedder(512)
        query = emb.embed("long BTC in regime uptrend_low_vol led by trend")
        near = emb.embed("long BTC in regime uptrend_low_vol opened on trend breakout")
        far = emb.embed("short ETH in regime downtrend_high_vol led by meanrev")
        self.assertGreater(cosine(query, near), cosine(query, far))

    def test_empty_text_is_handled(self):
        self.assertEqual(len(HashingEmbedder(32).embed("")), 32)


class TestCortex(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cortex = Cortex(Path(self.tmp.name) / "b2.sqlite3", embedder=HashingEmbedder(256))

    def tearDown(self):
        self.cortex.close()
        self.tmp.cleanup()

    def test_recall_ranks_the_relevant_memory_first(self):
        self.cortex.remember(Lesson("long BTC in regime uptrend_low_vol worked, avg +1.4%"))
        self.cortex.remember(Lesson("short BTC in regime downtrend_high_vol lost money, avg -2.2%"))
        self.cortex.remember(Lesson("fees exceed net PnL, trading too often"))
        top = self.cortex.recall("long BTC uptrend_low_vol", k=1)
        self.assertEqual(len(top), 1)
        self.assertIn("uptrend_low_vol worked", top[0].text)

    def test_repeating_a_lesson_reinforces_instead_of_duplicating(self):
        first = self.cortex.remember(Lesson("stops keep getting hit in high vol"))
        second = self.cortex.remember(Lesson("stops keep getting hit in high vol"))
        self.assertEqual(first, second)
        self.assertEqual(self.cortex.count(), 1)
        self.assertGreater(self.cortex.latest(1)[0].weight, 1.0)

    def test_memories_survive_reopening_the_store(self):
        self.cortex.remember(Lesson("time stops fire too early in trends"))
        path = self.cortex.path
        self.cortex.close()
        reopened = Cortex(path, embedder=HashingEmbedder(256))
        try:
            self.assertEqual(reopened.count(), 1)
            self.assertTrue(reopened.recall("time stop trend", k=1))
        finally:
            reopened.close()

    def test_pruning_keeps_the_store_bounded(self):
        small = Cortex(Path(self.tmp.name) / "small.sqlite3", max_items=10)
        try:
            for i in range(40):
                small.remember(Lesson(f"lesson number {i} about regime {i % 5}"))
            self.assertLessEqual(small.count(), 10)
        finally:
            small.close()

    def test_kind_filter(self):
        self.cortex.remember(Lesson("a trade note", kind="trade"))
        self.cortex.remember(Lesson("an evolution note", kind="evolution"))
        self.assertEqual(len(self.cortex.recall("note", k=5, kind="trade")), 1)


class TestDualBrain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(data_dir=self.tmp.name, memory_dim=256)
        self.brain = DualBrain(self.cfg)

    def tearDown(self):
        self.brain.close()
        self.tmp.cleanup()

    def test_a_trade_lands_in_both_brains(self):
        self.brain.remember_trade(make_trade())
        self.assertEqual(self.brain.b1.trade_stats()["trades"], 1)
        self.assertEqual(self.brain.b2.count(kind="trade"), 1)

    def test_consolidation_distils_repeated_episodes_into_a_lesson(self):
        for i in range(6):
            self.brain.remember_trade(make_trade(pnl_pct=-0.03, ts=1_000 + i * 10_000))
        lessons = self.brain.consolidate()
        self.assertTrue(lessons)
        self.assertTrue(any("lost money" in l.text for l in lessons))
        # Consolidation is incremental: the same trades are not re-distilled.
        self.assertEqual(self.brain.consolidate(), [])

    def test_recalled_losses_shrink_size_and_can_veto(self):
        for i in range(8):
            self.brain.remember_trade(
                make_trade(pnl_pct=-0.04, ts=1_000 + i * 10_000, reason_close="stop_loss")
            )
        self.brain.consolidate()
        signal = Signal(direction=1, score=0.5, reason="long score +0.50 led by trend",
                        features={"trend": 0.5}, regime="uptrend_low_vol")
        bias = self.brain.advice("BTC/USDT", signal)
        self.assertLess(bias.size_mult, 1.0)
        self.assertTrue(bias.veto_long)
        self.assertFalse(bias.veto_short)

    def test_recalled_wins_increase_size(self):
        for i in range(8):
            self.brain.remember_trade(make_trade(pnl_pct=0.05, ts=1_000 + i * 10_000))
        self.brain.consolidate()
        signal = Signal(1, 0.5, "long score +0.50 led by trend", {"trend": 0.5}, "uptrend_low_vol")
        bias = self.brain.advice("BTC/USDT", signal)
        self.assertGreater(bias.size_mult, 1.0)
        self.assertFalse(bias.veto_long)

    def test_no_memories_means_no_bias(self):
        signal = Signal(1, 0.4, "long score +0.40 led by macd", {}, "range_mid_vol")
        bias = self.brain.advice("BTC/USDT", signal)
        self.assertEqual(bias.size_mult, 1.0)
        self.assertFalse(bias.veto_long)

    def test_lessons_about_the_other_side_do_not_veto_this_one(self):
        for i in range(8):
            self.brain.remember_trade(make_trade(pnl_pct=-0.05, side="short", ts=1_000 + i * 10_000))
        self.brain.consolidate()
        long_signal = Signal(1, 0.6, "long score +0.60 led by trend", {}, "uptrend_low_vol")
        self.assertFalse(self.brain.advice("BTC/USDT", long_signal).veto_long)

    def test_brain1_persists_candles_and_state_across_reopen(self):
        candles = [Candle(i * 60_000, 1, 2, 0.5, 1.5, 10) for i in range(50)]
        self.brain.b1.save_candles("BTC/USDT", "1m", candles)
        self.brain.b1.set_state("probe", {"value": 42})
        self.brain.close()
        reopened = DualBrain(self.cfg)
        try:
            self.assertEqual(len(reopened.b1.load_candles("BTC/USDT", "1m", 100)), 50)
            self.assertEqual(reopened.b1.get_state("probe"), {"value": 42})
        finally:
            reopened.close()
            self.brain = DualBrain(self.cfg)  # for tearDown

    def test_saving_the_same_candle_twice_updates_rather_than_duplicates(self):
        first = [Candle(0, 1, 2, 0.5, 1.5, 10)]
        second = [Candle(0, 1, 2, 0.5, 9.9, 10)]
        self.brain.b1.save_candles("BTC/USDT", "1m", first)
        self.brain.b1.save_candles("BTC/USDT", "1m", second)
        stored = self.brain.b1.load_candles("BTC/USDT", "1m", 10)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].close, 9.9)


if __name__ == "__main__":
    unittest.main()
