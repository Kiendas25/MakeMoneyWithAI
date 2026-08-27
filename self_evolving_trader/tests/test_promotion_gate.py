"""The gate that stops a genome being crowned for fitting the fit window.

From a real run: generation 14 produced a best genome scoring +2.305
in-sample and -2.158 out-of-sample, and generation 16 +0.501 against -1.828.
In-sample and out-of-sample were not merely uncorrelated, they were pulling in
opposite directions - the search was rewarding memorisation - and a champion
was promoted anyway.
"""

import random
import tempfile
import unittest

from crypto_agent.brain.memory import DualBrain
from crypto_agent.config import Config
from crypto_agent.core.types import BacktestMetrics, BacktestResult
from crypto_agent.evolution.engine import Evaluation, EvolutionEngine
from crypto_agent.strategy.genome import Genome


def evaluation(genome, fitness, oos_fitness, trades=20, drawdown=0.05):
    dummy = BacktestResult(BacktestMetrics())
    return Evaluation(
        genome=genome, fitness=fitness, oos_fitness=oos_fitness,
        in_sample=dummy, out_sample=dummy,
        pooled_oos_trades=trades, worst_oos_drawdown=drawdown,
        trials=1, deflation_penalty=0.0,
    )


class TestGeneralisationGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(
            data_dir=self.tmp.name, population_size=4, elite_count=1,
            trials_penalty=False, min_trades_for_promotion=8,
            min_generalisation=0.25, max_drawdown_pct=0.20,
        )
        self.brain = DualBrain(self.cfg)
        self.engine = EvolutionEngine(self.cfg, self.brain, rng=random.Random(0))
        self.rng = random.Random(1)

    def tearDown(self):
        self.brain.close()
        self.tmp.cleanup()

    def _genome(self):
        return Genome.random(self.rng)

    def test_the_observed_overfit_is_refused(self):
        # gen 14: +2.305 in-sample, -2.158 out-of-sample.
        promoted, _ = self.engine.maybe_promote(
            [evaluation(self._genome(), fitness=2.305, oos_fitness=-2.158)])
        self.assertFalse(promoted)

    def test_a_milder_collapse_is_also_refused(self):
        # +2.0 in-sample must hold at least +0.5 out; +0.3 is fitting noise.
        promoted, _ = self.engine.maybe_promote(
            [evaluation(self._genome(), fitness=2.0, oos_fitness=0.3)])
        self.assertFalse(promoted)

    def test_a_genome_that_generalises_is_still_promoted(self):
        # The gate must not deadlock promotion, or the agent stops evolving.
        promoted, _ = self.engine.maybe_promote(
            [evaluation(self._genome(), fitness=2.0, oos_fitness=1.2)])
        self.assertTrue(promoted)

    def test_doing_better_out_of_sample_than_in_is_not_penalised(self):
        # Only the collapse direction is the failure mode being caught.
        promoted, _ = self.engine.maybe_promote(
            [evaluation(self._genome(), fitness=0.2, oos_fitness=1.4)])
        self.assertTrue(promoted)

    def test_a_negative_in_sample_score_is_exempt_from_the_ratio(self):
        # 0.25 * a negative number is a *lower* bar, which would invert the
        # test; such a genome still has to beat the incumbent out-of-sample.
        promoted, _ = self.engine.maybe_promote(
            [evaluation(self._genome(), fitness=-1.0, oos_fitness=0.9)])
        self.assertTrue(promoted)

    def test_too_few_hold_out_trades_is_not_evidence(self):
        promoted, _ = self.engine.maybe_promote(
            [evaluation(self._genome(), fitness=1.0, oos_fitness=0.9, trades=3)])
        self.assertFalse(promoted)

    def test_the_generalising_candidate_wins_over_the_higher_overfit_one(self):
        # The overfit genome scores higher out-of-sample here too, so only the
        # gate can keep it from being crowned.
        overfit = evaluation(self._genome(), fitness=9.0, oos_fitness=1.5)
        honest = evaluation(self._genome(), fitness=1.2, oos_fitness=1.0)
        promoted, champion_id = self.engine.maybe_promote([overfit, honest])
        self.assertTrue(promoted)
        self.assertEqual(champion_id, honest.genome.id)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
