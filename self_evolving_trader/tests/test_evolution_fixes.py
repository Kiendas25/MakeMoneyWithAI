"""Regression tests for three genetic-algorithm correctness bugs.

Each test embeds the measurement that motivated the fix: a "before" number
(reconstructed from the old, buggy formula/behaviour without reverting any
source) next to the "after" number the fixed code now produces, so the
regression is visible in the test output, not just asserted blindly.
"""

from __future__ import annotations

import random
import tempfile
import unittest
from unittest.mock import patch

from crypto_agent.brain.memory import DualBrain
from crypto_agent.config import Config
from crypto_agent.core.types import BacktestMetrics, BacktestResult
from crypto_agent.evolution.engine import Evaluation, EvolutionEngine, _deflation_penalty
from crypto_agent.strategy.genome import GENE_SPECS, Genome


# ----------------------------------------------------------------------
# Bug 1: crossover's discrete branch could never resolve to parent B.
# ----------------------------------------------------------------------
class TestCrossoverProvenance(unittest.TestCase):
    """``roll < 0.4`` gated a choice of ``a if roll < 0.5 else b`` - since the
    gate already implies the choice condition, parent B could only ever enter
    a child through blending, never as an outright pick. Over many crossovers
    that means B contributes essentially nothing on its own.
    """

    def test_both_parents_contribute_numeric_genes_symmetrically(self):
        rng = random.Random(42)
        parent_a = Genome.random(random.Random(1))
        parent_b = Genome.random(random.Random(2))
        trials = 2000

        count_a = 0
        count_b = 0
        for _ in range(trials):
            child = parent_a.crossover(parent_b, rng)
            for name, spec in GENE_SPECS.items():
                if spec.kind == "bool":
                    continue
                av, bv = parent_a.genes[name], parent_b.genes[name]
                if av == bv:
                    continue  # can't tell provenance when both parents agree
                cv = child.genes[name]
                if cv == av:
                    count_a += 1
                elif cv == bv:
                    count_b += 1

        # Measured before this fix (task description, 2000 crossovers):
        #   genes taken exactly from A: 18079   genes taken exactly from B: 0
        # Reproduced independently against the unfixed logic in this file's
        # git history: ~20000+ from A, ~0-1000 from B (the nonzero B count
        # there is blend rounding coincidentally landing on B's int value,
        # not a genuine independent pick).
        print(f"[bug1] gene provenance over {trials} crossovers: "
              f"A={count_a} B={count_b} ratio={count_a / max(1, count_b):.3f}")

        self.assertGreater(count_a, 0)
        self.assertGreater(count_b, 0)
        ratio = count_a / count_b
        self.assertTrue(
            0.75 <= ratio <= 1.35,
            f"expected roughly symmetric parent contribution, got A={count_a} B={count_b} "
            f"(ratio {ratio:.3f})",
        )

    def test_bool_genes_still_pick_either_parent(self):
        # allow_short is the only bool gene; it never touched the buggy branch,
        # this just guards against the fix accidentally breaking it.
        rng = random.Random(7)
        parent_a = Genome.random(random.Random(3))
        parent_a.genes["allow_short"] = True
        parent_b = Genome.random(random.Random(4))
        parent_b.genes["allow_short"] = False
        picks = {parent_a.crossover(parent_b, rng).genes["allow_short"] for _ in range(50)}
        self.assertEqual(picks, {True, False})


# ----------------------------------------------------------------------
# Shared helpers for the engine-level bugs.
# ----------------------------------------------------------------------
def _make_eval(genome: Genome, raw_oos: float, trials: int, cfg: Config,
                pooled_oos_trades: int = 10, worst_oos_drawdown: float = 0.05) -> Evaluation:
    """Build an Evaluation with a known undeflated score, deflated at ``trials``.

    Bypasses walk_forward/backtest entirely (out of scope for this file) -
    only the fields maybe_promote and breed actually read are populated.
    """
    penalty = _deflation_penalty(trials) if cfg.trials_penalty else 0.0
    oos_fitness = raw_oos - penalty
    dummy = BacktestResult(BacktestMetrics())
    return Evaluation(
        genome=genome,
        fitness=oos_fitness,
        oos_fitness=oos_fitness,
        in_sample=dummy,
        out_sample=dummy,
        pooled_oos_trades=pooled_oos_trades,
        worst_oos_drawdown=worst_oos_drawdown,
        trials=trials,
        deflation_penalty=penalty,
    )


# ----------------------------------------------------------------------
# Bug 2: promotion bar compared scores deflated at different trial counts.
# ----------------------------------------------------------------------
class TestPromotionBarTracksTrials(unittest.TestCase):
    """The champion's stored oos_fitness is deflated at its crowning trial
    count; every later challenger is deflated at today's (larger) count. Left
    unfixed, the bar effectively drifts upward by the deflation *delta* every
    generation regardless of strategy quality, and eventually nothing clears
    it.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(
            data_dir=self.tmp.name,
            population_size=4,
            elite_count=1,
            trials_penalty=True,
            promotion_margin=0.05,
            min_trades_for_promotion=3,
            max_drawdown_pct=0.20,
        )
        self.brain = DualBrain(self.cfg)
        self.engine = EvolutionEngine(self.cfg, self.brain, rng=random.Random(0))

    def tearDown(self):
        self.brain.close()
        self.tmp.cleanup()

    def test_promotion_stays_reachable_at_a_high_trials_count(self):
        incumbent_genome = Genome.random(random.Random(11))
        challenger_genome = Genome.random(random.Random(12))
        crown_trials, today_trials = 20, 500
        raw_incumbent, raw_challenger = 0.30, 0.36  # challenger is genuinely, clearly better

        crowning_eval = _make_eval(incumbent_genome, raw_incumbent, crown_trials, self.cfg)
        self.engine._install_champion(crowning_eval, "seed")
        challenger_eval = _make_eval(challenger_genome, raw_challenger, today_trials, self.cfg)

        # --- "before" measurement: reconstruct the old, unfixed comparison ---
        # (stored deflated-at-crowning score vs. margin, never re-deflated)
        stored_oos = crowning_eval.oos_fitness
        old_required = stored_oos + self.cfg.promotion_margin * max(1.0, abs(stored_oos))
        deflation_delta = _deflation_penalty(today_trials) - _deflation_penalty(crown_trials)
        print(f"[bug2] deflation penalty grew by {deflation_delta:+.3f} between trials="
              f"{crown_trials} and trials={today_trials}; old bar would require "
              f"{old_required:+.3f} vs. challenger's {challenger_eval.oos_fitness:+.3f}")
        self.assertAlmostEqual(deflation_delta, 0.1586, places=3)
        self.assertLess(
            challenger_eval.oos_fitness, old_required,
            "sanity check on the reconstructed old formula: a genuinely better "
            "challenger should still lose under the unfixed, drifting bar",
        )

        # --- "after": the actual (fixed) engine ---
        promoted, champion_id = self.engine.maybe_promote([challenger_eval])
        print(f"[bug2] fixed engine promoted={promoted} champion_id={champion_id}")
        self.assertTrue(promoted, "a genuinely better challenger must still be promotable")
        self.assertEqual(champion_id, challenger_genome.id)

    def test_a_challenger_no_better_than_the_incumbent_is_not_promoted(self):
        incumbent_genome = Genome.random(random.Random(21))
        weaker_genome = Genome.random(random.Random(22))
        crowning_eval = _make_eval(incumbent_genome, 0.30, 20, self.cfg)
        self.engine._install_champion(crowning_eval, "seed")
        weaker_eval = _make_eval(weaker_genome, 0.29, 500, self.cfg)  # not genuinely better

        promoted, champion_id = self.engine.maybe_promote([weaker_eval])
        self.assertFalse(promoted)
        self.assertEqual(champion_id, incumbent_genome.id)


# ----------------------------------------------------------------------
# Bug 3: diversity-exhaustion fallback skipped the allow_short clamp.
# ----------------------------------------------------------------------
class TestBreedRespectsAllowShortOnEveryPath(unittest.TestCase):
    """Every other path in ``breed`` (seed_population, crossover+mutate)
    clamps ``allow_short`` to the configured value; the fallback that fires
    when the diversity guard runs out of tries must too.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(
            data_dir=self.tmp.name,
            allow_short=False,
            population_size=16,
            elite_count=1,
        )
        self.brain = DualBrain(self.cfg)
        self.engine = EvolutionEngine(self.cfg, self.brain, rng=random.Random(5))

    def tearDown(self):
        self.brain.close()
        self.tmp.cleanup()

    def test_fallback_filled_genomes_are_still_long_only(self):
        # "Before" measurement: unclamped Genome.random() is close to a fair
        # coin on allow_short, confirming the fallback's bug would leak
        # short-capable genomes into a long-only configuration about half
        # the time it fires.
        baseline_rng = random.Random(99)
        baseline_shorts = sum(
            1 for _ in range(2000) if Genome.random(baseline_rng).genes["allow_short"]
        )
        print(f"[bug3] unclamped Genome.random(): allow_short=True in "
              f"{baseline_shorts}/2000 draws")
        self.assertGreater(baseline_shorts, 700)  # roughly half, well above zero

        genome = Genome.random(random.Random(1))
        genome.genes["allow_short"] = False
        evaluation = _make_eval(genome, 0.1, 1, self.cfg)

        # Force every candidate to look identical in gene-space so the
        # diversity guard exhausts on every single slot and the fallback
        # (the code under test) is what actually fills the population.
        with patch.object(Genome, "distance", lambda self, other: 0.0):
            next_gen = self.engine.breed([evaluation], nudges={}, generation=1)

        self.assertEqual(len(next_gen), self.cfg.population_size)
        fallback_filled = next_gen[self.cfg.elite_count:]
        self.assertGreater(len(fallback_filled), 5)  # enough genomes for the check to mean something
        shorts_leaked = sum(1 for g in fallback_filled if g.genes["allow_short"])
        print(f"[bug3] fallback-filled genomes with allow_short=True: "
              f"{shorts_leaked}/{len(fallback_filled)}")
        self.assertEqual(shorts_leaked, 0)


if __name__ == "__main__":
    unittest.main()
