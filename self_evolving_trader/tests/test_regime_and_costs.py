"""The two gates that stop a genome trading a setup it cannot win.

Both exist because of a real paper run: 12 trades, 12 losses, every one a
breakout-led long in `range_low_vol` closed by its stop. The regime was being
labelled and stored but never acted on, and nothing required a target to clear
the round-trip cost.
"""

import unittest

from crypto_agent.config import Config
from crypto_agent.core.types import Candle
from crypto_agent.strategy import rules
from crypto_agent.strategy.genome import GENE_SPECS, Genome


def flat_candles(n=400, price=100.0, wobble=0.15):
    """A range: no drift, small alternating moves, so slope stays near zero."""
    out = []
    for i in range(n):
        mid = price + (wobble if i % 2 else -wobble)
        out.append(Candle(ts=i * 60_000, open=mid, high=mid + wobble,
                          low=mid - wobble, close=mid, volume=10.0))
    return out


def trending_candles(n=400, price=100.0, growth=0.005):
    """An uptrend. Growth is compounded, not linear: `slope` normalises by the
    window mean, so a fixed step would drift back under the trend threshold as
    the price climbed and the series would stop counting as a trend."""
    out = []
    mid = price
    for i in range(n):
        out.append(Candle(ts=i * 60_000, open=mid, high=mid * 1.002,
                          low=mid * 0.998, close=mid, volume=10.0))
        mid *= 1.0 + growth
    return out


def genome_with(**overrides):
    genes = {name: (spec.default if spec.default is not None
                    else (spec.low + spec.high) / 2 if spec.kind != "bool" else True)
             for name, spec in GENE_SPECS.items()}
    genes.update(overrides)
    return Genome(genes=Genome.repair(genes))


class TestRegimeGate(unittest.TestCase):
    def test_flat_series_is_classified_as_a_range(self):
        frame = rules.compute_frame(genome_with(), flat_candles())
        self.assertTrue(rules.regime_at(frame, len(frame) - 1).startswith("range"))

    def test_standing_aside_in_a_range_blocks_the_entry(self):
        candles = flat_candles()
        opted_out = genome_with(trade_range=False, entry_threshold=0.08)
        frame = rules.compute_frame(opted_out, candles)
        signal = rules.signal_at(opted_out, frame, len(candles) - 1)
        self.assertEqual(signal.direction, 0)
        self.assertIn("stands aside", signal.reason)

    def test_standing_aside_in_a_range_does_not_block_a_trend(self):
        candles = trending_candles()
        opted_out = genome_with(trade_range=False, entry_threshold=0.08)
        frame = rules.compute_frame(opted_out, candles)
        signal = rules.signal_at(opted_out, frame, len(candles) - 1)
        self.assertNotIn("stands aside", signal.reason)

    def test_the_gene_defaults_to_participating_so_old_genomes_are_unchanged(self):
        # A champion saved before the gene existed must behave exactly as it did.
        stored = {name: (spec.low + spec.high) / 2 if spec.kind != "bool" else True
                  for name, spec in GENE_SPECS.items()}
        del stored["trade_range"]
        del stored["range_meanrev_bias"]
        repaired = Genome.repair(stored)
        self.assertTrue(repaired["trade_range"])
        self.assertEqual(repaired["range_meanrev_bias"], 0.0)


class TestMeanReversionBias(unittest.TestCase):
    def _scores(self):
        # Breakout says "buy, we are at the top of the range"; mean reversion
        # says "sell, we are stretched". They disagree, which is the point.
        return {"trend": 0.8, "macd": 0.6, "breakout": 1.0, "meanrev": -1.0, "rsi": 0.0}

    def test_zero_bias_leaves_the_score_alone(self):
        g = genome_with(range_meanrev_bias=0.0, w_trend=0.5, w_macd=0.5,
                        w_breakout=0.5, w_meanrev=0.5, w_rsi=0.5)
        self.assertEqual(rules.blended_score(g, self._scores(), "range_low_vol"),
                         rules.blended_score(g, self._scores(), "uptrend_low_vol"))

    def test_full_bias_flips_a_range_buy_into_a_range_sell(self):
        g = genome_with(range_meanrev_bias=1.0, w_trend=0.5, w_macd=0.5,
                        w_breakout=0.5, w_meanrev=0.5, w_rsi=0.5)
        in_trend = rules.blended_score(g, self._scores(), "uptrend_low_vol")
        in_range = rules.blended_score(g, self._scores(), "range_low_vol")
        self.assertGreater(in_trend, 0.0)
        self.assertLess(in_range, 0.0)

    def test_weight_is_moved_not_created(self):
        # Rotating weight must not change the total, or the score silently
        # rescales and every threshold means something different in a range.
        g = genome_with(range_meanrev_bias=0.6, w_trend=0.4, w_macd=0.3,
                        w_breakout=0.9, w_meanrev=0.2, w_rsi=0.1)
        flat = {m: 0.5 for m in rules.MODULES}
        self.assertAlmostEqual(rules.blended_score(g, flat, "range_low_vol"),
                               rules.blended_score(g, flat, "uptrend_low_vol"),
                               places=9)


class TestCostFloor(unittest.TestCase):
    def test_round_trip_charges_both_sides(self):
        self.assertAlmostEqual(rules.round_trip_cost(10.0, 5.0), 0.003)

    def test_min_edge_reads_the_config(self):
        cfg = Config(fee_bps=10.0, slippage_bps=5.0, min_edge_multiple=1.5)
        self.assertAlmostEqual(rules.min_edge_for(cfg), 0.0045)

    def test_a_target_inside_the_cost_band_is_refused(self):
        candles = trending_candles()
        tiny = genome_with(tp_atr_mult=0.8, stop_atr_mult=0.5, entry_threshold=0.08)
        frame = rules.compute_frame(tiny, candles, min_edge=0.05)  # 5%, unmeetable
        signal = rules.signal_at(tiny, frame, len(candles) - 1)
        self.assertEqual(signal.direction, 0)
        self.assertIn("cost floor", signal.reason)

    def test_a_target_clearing_the_band_is_allowed_through(self):
        candles = trending_candles()
        roomy = genome_with(tp_atr_mult=14.0, stop_atr_mult=2.0, entry_threshold=0.08)
        frame = rules.compute_frame(roomy, candles, min_edge=0.0001)
        signal = rules.signal_at(roomy, frame, len(candles) - 1)
        self.assertNotIn("cost floor", signal.reason)

    def test_a_zero_floor_disables_the_check_entirely(self):
        candles = trending_candles()
        tiny = genome_with(tp_atr_mult=0.8, stop_atr_mult=0.5, entry_threshold=0.08)
        frame = rules.compute_frame(tiny, candles, min_edge=0.0)
        self.assertNotIn("cost floor", rules.signal_at(tiny, frame, len(candles) - 1).reason)

    def test_the_backtester_and_the_agent_use_the_same_floor(self):
        # Both build their Frame from the same helper; if one stopped passing
        # it, paper results would stop matching what evolution was scored on.
        cfg = Config(fee_bps=10.0, slippage_bps=5.0, min_edge_multiple=1.5)
        frame = rules.compute_frame(genome_with(), trending_candles(),
                                    min_edge=rules.min_edge_for(cfg))
        self.assertAlmostEqual(frame.min_edge, 0.0045)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
