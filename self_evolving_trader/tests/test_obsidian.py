import tempfile
import unittest
from pathlib import Path

from crypto_agent.brain.memory import DualBrain
from crypto_agent.brain.obsidian import BEGIN, END, export_vault, safe_name, unique_name
from crypto_agent.config import Config
from crypto_agent.core.types import Lesson, Trade


def make_trade(symbol="BTC/USDT", pnl=25.0, ts=1_700_000_000_000):
    return Trade(
        symbol=symbol, side="long", qty=0.1, entry_ts=ts, entry_price=100.0,
        exit_ts=ts + 3_600_000, exit_price=100.0 + pnl / 0.1 / 100, pnl=pnl,
        pnl_pct=pnl / 1000.0, fees=1.0, reason_open="long score +0.40 led by trend",
        reason_close="take_profit", genome_id="abc123", regime="uptrend_low_vol",
    )


class TestSafeName(unittest.TestCase):
    def test_symbols_lose_the_slash(self):
        self.assertEqual(safe_name("BTC/USDT"), "BTC-USDT")

    def test_windows_forbidden_characters_are_stripped(self):
        for raw in ('a<b', 'a>b', 'a:b', 'a"b', "a\\b", "a|b", "a?b", "a*b"):
            with self.subTest(raw=raw):
                name = safe_name(raw)
                self.assertNotRegex(name, r'[<>:"/\\|?*]')
                self.assertTrue(name)

    def test_obsidian_link_syntax_is_stripped(self):
        self.assertNotRegex(safe_name("lesson [1] #tag ^ref"), r"[\[\]#^]")

    def test_dos_device_names_get_a_suffix(self):
        self.assertEqual(safe_name("CON"), "CON-note")
        self.assertEqual(safe_name("com1"), "com1-note")

    def test_trailing_dots_and_spaces_go(self):
        self.assertEqual(safe_name("  report.  "), "report")

    def test_empty_and_control_characters_fall_back(self):
        self.assertEqual(safe_name(""), "unnamed")
        self.assertEqual(safe_name("\x00\x01"), "unnamed")

    def test_long_names_are_capped(self):
        self.assertLessEqual(len(safe_name("x" * 500)), 64)

    def test_collisions_are_deterministically_suffixed(self):
        taken = {}
        self.assertEqual(unique_name("BTC/USDT", taken), "BTC-USDT")
        self.assertEqual(unique_name("BTC:USDT", taken), "BTC-USDT-2")
        self.assertEqual(unique_name("BTC|USDT", taken), "BTC-USDT-3")


class TestExportVault(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(data_dir=self.tmp.name, symbol="BTC/USDT", symbols="ETH/USDT")
        self.cfg.ensure_dirs()
        self.vault = Path(self.tmp.name) / "vault"

    def tearDown(self):
        self.tmp.cleanup()

    def _seed(self, brain):
        brain.b1.record_trade(make_trade())
        brain.b1.record_trade(make_trade(symbol="ETH/USDT", pnl=-12.0))
        brain.b2.remember(Lesson(
            text="Longs in uptrend_low_vol on BTC/USDT paid; keep full size.",
            kind="reflection", weight=1.0, meta={"symbol": "BTC/USDT", "samples": 4},
        ))
        brain.b2.remember(Lesson(
            text="Shorts into a volatility spike lost money twice.",
            kind="regime", weight=0.8, meta={"symbol": "ETH/USDT"},
        ))

    def test_export_creates_the_expected_layout(self):
        with DualBrain(self.cfg) as brain:
            self._seed(brain)
            report = export_vault(brain, self.cfg, self.vault)

        self.assertTrue((self.vault / "index.md").exists())
        self.assertTrue((self.vault / "markets" / "BTC-USDT.md").exists())
        self.assertTrue((self.vault / "markets" / "ETH-USDT.md").exists())
        self.assertEqual(len(list((self.vault / "lessons").glob("*.md"))), 2)
        self.assertEqual(len(list((self.vault / "trades").glob("*.md"))), 1)
        self.assertGreater(report.written, 0)
        self.assertEqual(report.skipped, 0)

    def test_slash_symbols_never_create_directories(self):
        with DualBrain(self.cfg) as brain:
            self._seed(brain)
            export_vault(brain, self.cfg, self.vault)
        self.assertFalse((self.vault / "markets" / "BTC").exists())

    def test_market_note_links_its_lessons(self):
        with DualBrain(self.cfg) as brain:
            self._seed(brain)
            export_vault(brain, self.cfg, self.vault)
        text = (self.vault / "markets" / "BTC-USDT.md").read_text(encoding="utf-8")
        self.assertIn("[[lessons/", text)
        self.assertNotIn("Nothing in Brain 2", text)

    def test_second_export_writes_nothing(self):
        with DualBrain(self.cfg) as brain:
            self._seed(brain)
            export_vault(brain, self.cfg, self.vault)
            again = export_vault(brain, self.cfg, self.vault)
        self.assertEqual(again.written, 0)
        self.assertGreater(again.skipped, 0)

    def test_human_text_outside_the_markers_survives(self):
        note = self.vault / "markets" / "BTC-USDT.md"
        with DualBrain(self.cfg) as brain:
            self._seed(brain)
            export_vault(brain, self.cfg, self.vault)

            note.write_text(
                note.read_text(encoding="utf-8") + "\n## My notes\n\nI disagree: too big.\n",
                encoding="utf-8",
            )
            brain.b1.record_trade(make_trade(pnl=9.0, ts=1_700_100_000_000))
            report = export_vault(brain, self.cfg, self.vault)

        text = note.read_text(encoding="utf-8")
        self.assertIn("I disagree: too big.", text)
        self.assertEqual(text.count(BEGIN), 1)
        self.assertEqual(text.count(END), 1)
        self.assertGreaterEqual(report.preserved, 1)

    def test_a_file_without_markers_is_appended_to_not_clobbered(self):
        (self.vault / "markets").mkdir(parents=True)
        note = self.vault / "markets" / "BTC-USDT.md"
        note.write_text("# My own BTC page\n\nHand written, do not delete.\n", encoding="utf-8")

        with DualBrain(self.cfg) as brain:
            self._seed(brain)
            report = export_vault(brain, self.cfg, self.vault)

        text = note.read_text(encoding="utf-8")
        self.assertIn("Hand written, do not delete.", text)
        self.assertIn(BEGIN, text)
        self.assertEqual(report.appended, 1)

    def test_empty_brains_still_produce_a_valid_vault(self):
        with DualBrain(self.cfg) as brain:
            report = export_vault(brain, self.cfg, self.vault)
        index = (self.vault / "index.md").read_text(encoding="utf-8")
        self.assertIn("Brain 2 is empty.", index)
        self.assertIn("No trades closed yet.", index)
        self.assertGreater(report.written, 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
