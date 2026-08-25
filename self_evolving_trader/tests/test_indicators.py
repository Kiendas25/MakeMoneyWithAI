import math
import unittest

from crypto_agent.core.types import Candle
from crypto_agent.data import indicators as ind


def candles_from(closes, spread=1.0):
    out = []
    for i, c in enumerate(closes):
        out.append(Candle(ts=i * 60_000, open=c, high=c + spread, low=c - spread, close=c, volume=1.0))
    return out


class TestIndicators(unittest.TestCase):
    def test_sma_alignment_and_value(self):
        values = [1, 2, 3, 4, 5]
        out = ind.sma(values, 3)
        self.assertEqual(out[:2], [None, None])
        self.assertAlmostEqual(out[2], 2.0)
        self.assertAlmostEqual(out[4], 4.0)
        self.assertEqual(len(out), len(values))

    def test_ema_seeds_with_sma_then_smooths(self):
        values = [10.0] * 20
        out = ind.ema(values, 5)
        self.assertIsNone(out[3])
        self.assertAlmostEqual(out[4], 10.0)
        self.assertAlmostEqual(out[-1], 10.0)  # flat input stays flat

    def test_ema_tracks_a_ramp_below_price(self):
        values = [float(i) for i in range(1, 40)]
        out = ind.ema(values, 10)
        self.assertLess(out[-1], values[-1])
        self.assertGreater(out[-1], values[-10])

    def test_rsi_saturates_on_a_monotonic_series(self):
        rising = [float(i) for i in range(1, 40)]
        falling = list(reversed(rising))
        self.assertAlmostEqual(ind.rsi(rising, 14)[-1], 100.0, places=6)
        self.assertAlmostEqual(ind.rsi(falling, 14)[-1], 0.0, places=6)

    def test_rsi_is_mid_range_on_alternating_moves(self):
        values = []
        price = 100.0
        for i in range(60):
            price += 1.0 if i % 2 == 0 else -1.0
            values.append(price)
        self.assertTrue(40 <= ind.rsi(values, 14)[-1] <= 60)

    def test_atr_matches_a_constant_true_range(self):
        closes = [100.0] * 30
        candles = candles_from(closes, spread=2.0)  # every bar has a 4-wide range
        out = ind.atr(candles, 14)
        self.assertIsNone(out[13])
        self.assertAlmostEqual(out[-1], 4.0, places=6)

    def test_donchian_position_is_bounded_and_signed(self):
        closes = [float(i) for i in range(1, 50)]
        out = ind.donchian_position(candles_from(closes), 20)
        self.assertTrue(all(-1.0001 <= v <= 1.0001 for v in out if v is not None))
        self.assertGreater(out[-1], 0.5)  # closing at the top of a rising range

    def test_bollinger_z_is_zero_for_flat_input_and_high_when_stretched(self):
        flat = [100.0] * 40
        self.assertIsNone(ind.bollinger_z(flat, 20)[-1])  # zero variance: undefined, not infinite
        stretched = [100.0] * 39 + [130.0]
        self.assertGreater(ind.bollinger_z(stretched, 20)[-1], 3.0)

    def test_realized_vol_grows_with_noise(self):
        calm = [100.0 + 0.01 * i for i in range(60)]
        wild = [100.0 * (1.1 if i % 2 else 0.9) for i in range(60)]
        self.assertLess(ind.realized_vol(calm, 20)[-1], ind.realized_vol(wild, 20)[-1])

    def test_slope_sign_follows_direction(self):
        up = [float(i) for i in range(1, 40)]
        down = list(reversed(up))
        self.assertGreater(ind.slope(up, 10)[-1], 0)
        self.assertLess(ind.slope(down, 10)[-1], 0)

    def test_macd_hist_is_finite_and_aligned(self):
        values = [100.0 + math.sin(i / 5.0) * 5 for i in range(120)]
        out = ind.macd_hist(values)
        self.assertEqual(len(out), len(values))
        self.assertTrue(all(math.isfinite(v) for v in out if v is not None))
        self.assertIsNotNone(out[-1])

    def test_short_series_never_raises(self):
        for fn in (lambda v: ind.ema(v, 20), lambda v: ind.rsi(v, 14), lambda v: ind.sma(v, 5)):
            self.assertTrue(all(x is None for x in fn([1.0, 2.0])))


if __name__ == "__main__":
    unittest.main()
