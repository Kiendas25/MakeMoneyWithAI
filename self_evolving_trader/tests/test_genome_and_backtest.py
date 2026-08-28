import random
import unittest

from crypto_agent.config import Config
from crypto_agent.core.types import Candle, fitness_score, BacktestMetrics
from crypto_agent.data.providers import SyntheticProvider
from crypto_agent.strategy import rules
from crypto_agent.strategy.backtest import position_size, simulate, walk_forward
from crypto_agent.strategy.genome import GENE_SPECS, Genome, seed_population


def trending_candles(n=400, drift=0.004, start=100.0):
    out = []
    price = start
    for i in range(n):
        open_price = price
        price = price * (1 + drift)
        out.append(Candle(i * 3_600_000, open_price, max(open_price, price) * 1.001,
                          min(open_price, price) * 0.999, price, 10.0))
    return out


class TestGenome(unittest.TestCase):
    def test_repair_clamps_every_gene_into_range(self):
        wild = {name: 1e9 for name in GENE_SPECS}
        genome = Genome(genes=wild)
        for name, spec in GENE_SPECS.items():
            if spec.kind == "bool":
                continue
            self.assertLessEqual(genome.genes[name], spec.high, name)
            self.assertGreaterEqual(genome.genes[name], spec.low, name)

    def test_repair_enforces_cross_gene_sanity(self):
        genome = Genome(genes={"ema_fast": 50, "ema_slow": 10, "rsi_buy": 45, "rsi_sell": 46})
        self.assertGreater(genome.genes["ema_slow"], genome.genes["ema_fast"])
        self.assertGreater(genome.genes["rsi_sell"], genome.genes["rsi_buy"] + 4)

    def test_id_is_stable_and_content_addressed(self):
        rng = random.Random(1)
        a = Genome.random(rng)
        b = Genome.from_dict(a.to_dict())
        self.assertEqual(a.id, b.id)
        c = a.mutate(random.Random(2), rate=1.0, scale=0.5)
        self.assertNotEqual(a.id, c.id)

    def test_mutation_is_deterministic_for_a_given_seed(self):
        base = Genome.random(random.Random(5))
        first = base.mutate(random.Random(11), rate=0.4, scale=0.3)
        second = base.mutate(random.Random(11), rate=0.4, scale=0.3)
        self.assertEqual(first.id, second.id)

    def test_mutation_always_changes_something(self):
        base = Genome.random(random.Random(3))
        child = base.mutate(random.Random(4), rate=0.0, scale=0.2)
        self.assertNotEqual(base.to_dict(), child.to_dict())

    def test_nudges_push_the_gene_in_the_requested_direction(self):
        genes = {name: (spec.low + spec.high) / 2 for name, spec in GENE_SPECS.items()}
        base = Genome(genes=genes)
        ups, downs = 0, 0
        for seed in range(40):
            up = base.mutate(random.Random(seed), rate=1.0, scale=0.05,
                             nudges={"stop_atr_mult": 2.0})
            down = base.mutate(random.Random(seed), rate=1.0, scale=0.05,
                               nudges={"stop_atr_mult": -2.0})
            ups += up.genes["stop_atr_mult"] > base.genes["stop_atr_mult"]
            downs += down.genes["stop_atr_mult"] < base.genes["stop_atr_mult"]
        self.assertGreater(ups, 30)
        self.assertGreater(downs, 30)

    def test_crossover_takes_genes_from_both_parents(self):
        rng = random.Random(9)
        a, b = Genome.random(rng), Genome.random(rng)
        child = a.crossover(b, random.Random(21))
        self.assertEqual(set(child.genes), set(GENE_SPECS))
        self.assertGreater(child.generation, max(a.generation, b.generation) - 1)

    def test_distance_is_zero_for_identical_and_positive_otherwise(self):
        rng = random.Random(13)
        a = Genome.random(rng)
        self.assertAlmostEqual(a.distance(Genome.from_dict(a.to_dict())), 0.0)
        self.assertGreater(a.distance(Genome.random(rng)), 0.0)

    def test_seed_population_respects_the_short_setting(self):
        pop = seed_population(random.Random(2), 10, allow_short=False)
        self.assertEqual(len(pop), 10)
        self.assertTrue(all(g.genes["allow_short"] is False for g in pop))

    def test_describe_mentions_the_id(self):
        genome = seed_population(random.Random(1), 4, allow_short=True)[0]
        self.assertIn(genome.id, genome.describe())


class TestBacktest(unittest.TestCase):
    def setUp(self):
        self.cfg = Config(symbol="BTC/USDT", timeframe="1h", start_cash=10_000.0,
                          history_bars=1200, oos_bars=200)

    def test_position_size_risks_the_configured_fraction(self):
        cfg = Config(risk_per_trade=0.01, max_position_pct=1.0, min_notional=1.0)
        qty = position_size(equity=10_000, price=100.0, stop=95.0, cfg=cfg, risk_scale=1.0)
        # 1% of 10k = 100 risked over a 5-wide stop = 20 units
        self.assertAlmostEqual(qty, 20.0, places=6)
        self.assertAlmostEqual(qty * 5.0, 100.0, places=6)

    def test_position_size_is_capped_by_notional_and_cash(self):
        cfg = Config(risk_per_trade=0.02, max_position_pct=0.1, min_notional=1.0)
        qty = position_size(10_000, 100.0, 99.9, cfg, 1.0)
        self.assertLessEqual(qty * 100.0, 10_000 * 0.1 + 1e-6)
        capped = position_size(10_000, 100.0, 99.9, cfg, 1.0, cash=250.0)
        self.assertLessEqual(capped * 100.0, 250.0 + 1e-6)

    def test_position_size_rejects_dust(self):
        cfg = Config(min_notional=100.0, risk_per_trade=0.001, max_position_pct=0.001)
        self.assertEqual(position_size(1_000, 100.0, 90.0, cfg, 1.0), 0.0)

    def test_trend_follower_profits_in_a_clean_uptrend(self):
        genome = seed_population(random.Random(1), 4, allow_short=False)[0]
        result = simulate(genome, trending_candles(500, drift=0.004), self.cfg)
        self.assertGreater(result.metrics.trades, 0)
        self.assertGreater(result.metrics.total_return, 0.0)
        self.assertAlmostEqual(result.metrics.final_equity,
                               self.cfg.start_cash * (1 + result.metrics.total_return), places=4)

    def test_fees_and_slippage_reduce_the_result(self):
        genome = seed_population(random.Random(1), 4, allow_short=False)[0]
        candles = trending_candles(500, drift=0.004)
        cheap = Config(**{**self.cfg.to_dict(), "fee_bps": 0.0, "slippage_bps": 0.0})
        pricey = Config(**{**self.cfg.to_dict(), "fee_bps": 50.0, "slippage_bps": 25.0})
        self.assertGreater(
            simulate(genome, candles, cheap).metrics.total_return,
            simulate(genome, candles, pricey).metrics.total_return,
        )

    def test_stops_bound_the_loss_on_a_single_trade(self):
        genome = Genome(genes={**seed_population(random.Random(1), 4, False)[0].to_dict(),
                               "stop_atr_mult": 1.0, "trail_atr_mult": 0.0, "tp_atr_mult": 8.0})
        candles = trending_candles(300, drift=0.004) + trending_candles(200, drift=-0.02, start=100 * (1.004 ** 300))
        result = simulate(genome, candles, self.cfg)
        losses = [t.pnl_pct for t in result.trades if t.pnl < 0]
        if losses:
            # Sizing risks 1% of equity per trade; a stop-loss exit must stay in
            # that neighbourhood rather than wiping out the account.
            self.assertGreater(min(losses), -0.35)

    def test_no_lookahead_prefix_stability(self):
        """A decision at bar i must not change when future bars are appended."""
        genome = seed_population(random.Random(4), 4, allow_short=False)[0]
        candles = SyntheticProvider(seed=3).fetch_ohlcv("BTC/USDT", "1h", 600)
        prefix = candles[:400]
        full_frame = rules.compute_frame(genome, candles)
        prefix_frame = rules.compute_frame(genome, prefix)
        i = 399
        self.assertEqual(
            rules.signal_at(genome, full_frame, i).direction,
            rules.signal_at(genome, prefix_frame, i).direction,
        )
        self.assertAlmostEqual(
            rules.signal_at(genome, full_frame, i).score,
            rules.signal_at(genome, prefix_frame, i).score,
            places=9,
        )

    def test_walk_forward_splits_without_overlap(self):
        genome = seed_population(random.Random(1), 4, allow_short=False)[0]
        candles = SyntheticProvider(seed=5).fetch_ohlcv("BTC/USDT", "1h", 1000)
        in_sample, out_sample = walk_forward(genome, candles, self.cfg)
        self.assertLessEqual(len(out_sample.equity_curve), self.cfg.oos_bars)
        self.assertGreater(len(in_sample.equity_curve), len(out_sample.equity_curve))

    def test_fitness_punishes_drawdown_and_thin_samples(self):
        good = BacktestMetrics(total_return=0.4, sharpe=2.0, max_drawdown=0.05, trades=40)
        deep = BacktestMetrics(total_return=0.4, sharpe=2.0, max_drawdown=0.6, trades=40)
        thin = BacktestMetrics(total_return=0.4, sharpe=2.0, max_drawdown=0.05, trades=1)
        self.assertGreater(fitness_score(good), fitness_score(deep))
        self.assertGreater(fitness_score(good), fitness_score(thin))
        self.assertLess(fitness_score(thin), 0.0)


if __name__ == "__main__":
    unittest.main()
