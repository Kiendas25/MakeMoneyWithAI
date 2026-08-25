"""The evolution engine.

A steady-state genetic algorithm over strategy genomes, with three properties
that matter more than the GA itself:

1. **Walk-forward selection.** Fitness for breeding comes from the in-sample
   window; promotion to champion requires beating the incumbent out-of-sample.
2. **Diversity pressure.** Children too close in gene space to an existing
   member are re-mutated, so the population does not collapse onto one
   over-tuned lineage.
3. **Memory-guided mutation.** Lessons in Brain 2 carry ``gene_hints`` which
   bias the mutation of specific genes. The search is not blind; it is informed
   by what already went wrong.

Everything (population, fitness, generation history, champion) is persisted in
Brain 1, so evolution resumes exactly where it left off after a restart.
"""

from __future__ import annotations

import logging
import random
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from ..brain.memory import DualBrain
from ..config import Config
from ..core.types import BacktestResult, Candle, Lesson, fitness_score
from ..strategy.backtest import walk_forward
from ..strategy.genome import Genome, seed_population

log = logging.getLogger(__name__)

POPULATION_KEY = "evolution.population"
BEST_FITNESS_KEY = "evolution.best_fitness"


@dataclass
class Evaluation:
    genome: Genome
    fitness: float
    oos_fitness: float
    in_sample: BacktestResult
    out_sample: BacktestResult

    @property
    def metrics(self) -> Dict[str, Any]:
        return {
            "in_sample": self.in_sample.metrics.to_dict(),
            "out_sample": self.out_sample.metrics.to_dict(),
        }


@dataclass
class GenerationReport:
    generation: int
    best_id: str
    best_fitness: float
    best_oos_fitness: float
    mean_fitness: float
    evaluated: int
    promoted: bool
    champion_id: str
    notes: List[str] = field(default_factory=list)

    def summary(self) -> str:
        verdict = "PROMOTED new champion" if self.promoted else "champion unchanged"
        return (
            f"gen {self.generation}: best {self.best_id} fitness {self.best_fitness:+.3f} "
            f"(oos {self.best_oos_fitness:+.3f}), mean {self.mean_fitness:+.3f} "
            f"over {self.evaluated} genomes - {verdict} ({self.champion_id})"
        )


class EvolutionEngine:
    def __init__(self, cfg: Config, brain: DualBrain, rng: Optional[random.Random] = None) -> None:
        self.cfg = cfg
        self.brain = brain
        self.rng = rng or random.Random(cfg.seed)

    # ------------------------------------------------------------------
    # Population persistence
    # ------------------------------------------------------------------
    def load_population(self) -> List[Genome]:
        stored = self.brain.b1.get_state(POPULATION_KEY)
        if stored:
            population = [
                Genome.from_dict(item["genes"], item.get("generation", 0), item.get("origin", "loaded"))
                for item in stored
            ]
            if len(population) >= 4:
                return population[: self.cfg.population_size]
        population = seed_population(self.rng, self.cfg.population_size, self.cfg.allow_short)
        self.save_population(population)
        return population

    def save_population(self, population: Sequence[Genome]) -> None:
        self.brain.b1.set_state(
            POPULATION_KEY,
            [
                {"genes": g.to_dict(), "generation": g.generation, "origin": g.origin}
                for g in population
            ],
        )

    # ------------------------------------------------------------------
    # Champion
    # ------------------------------------------------------------------
    def champion(self) -> Genome:
        record = self.brain.b1.champion()
        if record:
            return Genome.from_dict(record["genes"], record["generation"], "champion")
        # Bootstrap: the first archetype is a reasonable prior until evolution runs.
        genome = seed_population(self.rng, self.cfg.population_size, self.cfg.allow_short)[0]
        self.brain.b1.save_genome(genome.id, 0, genome.to_dict(), 0.0, 0.0, {}, status="champion")
        self.brain.b1.log_event("champion", f"bootstrapped {genome.describe()}")
        return genome

    def champion_record(self) -> Optional[Dict[str, Any]]:
        return self.brain.b1.champion()

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------
    def evaluate(self, genome: Genome, candles: Sequence[Candle]) -> Evaluation:
        in_sample, out_sample = walk_forward(genome, candles, self.cfg)
        return Evaluation(
            genome=genome,
            fitness=fitness_score(in_sample.metrics),
            oos_fitness=fitness_score(out_sample.metrics),
            in_sample=in_sample,
            out_sample=out_sample,
        )

    def gene_nudges(self) -> Dict[str, float]:
        """Pull mutation bias out of Brain 2's reflections."""
        recalls = self.brain.b2.recall(
            "which genes should change stop take profit entry threshold hold time volatility",
            k=self.cfg.recall_k,
            kind="reflection",
            reinforce=False,
        )
        nudges: Dict[str, float] = {}
        for r in recalls:
            for gene, value in (r.meta.get("gene_hints") or {}).items():
                nudges[gene] = nudges.get(gene, 0.0) + float(value) * r.similarity
        return {gene: max(-2.0, min(2.0, v)) for gene, v in nudges.items()}

    # ------------------------------------------------------------------
    # One generation
    # ------------------------------------------------------------------
    def run_generation(self, candles: Sequence[Candle]) -> GenerationReport:
        population = self.load_population()
        generation = self.brain.b1.last_generation() + 1
        nudges = self.gene_nudges()

        evaluations = sorted(
            (self.evaluate(g, candles) for g in population),
            key=lambda e: e.fitness,
            reverse=True,
        )
        for ev in evaluations:
            self.brain.b1.save_genome(
                ev.genome.id,
                generation,
                ev.genome.to_dict(),
                ev.fitness,
                ev.oos_fitness,
                ev.metrics,
            )

        best = evaluations[0]
        mean_fitness = statistics.fmean(e.fitness for e in evaluations)
        self.brain.b1.record_generation(
            generation,
            best.genome.id,
            best.fitness,
            mean_fitness,
            [e.genome.id for e in evaluations],
        )

        promoted, champion_id = self.maybe_promote(evaluations)
        next_population = self.breed(evaluations, nudges, generation)
        self.save_population(next_population)

        notes = [
            f"generation {generation}: best in-sample fitness {best.fitness:+.3f} from "
            f"{best.genome.describe()}",
            f"population mean fitness {mean_fitness:+.3f}; "
            f"best out-of-sample {best.oos_fitness:+.3f} over "
            f"{best.out_sample.metrics.trades} hold-out trades",
        ]
        # Only a generation that changed something is worth remembering. Writing
        # a note every time would bury the trade lessons that actually inform
        # decisions under a pile of "nothing happened".
        previous_best = self.brain.b1.get_state(BEST_FITNESS_KEY)
        improved = previous_best is None or best.fitness > float(previous_best) + 1e-9
        if improved:
            self.brain.b1.set_state(BEST_FITNESS_KEY, best.fitness)
        if promoted or improved:
            self.brain.b2.remember_many(
                [
                    Lesson(
                        text=note,
                        kind="evolution",
                        weight=1.0,
                        meta={"generation": generation, "genome_id": best.genome.id},
                    )
                    for note in notes
                ]
            )
        report = GenerationReport(
            generation=generation,
            best_id=best.genome.id,
            best_fitness=best.fitness,
            best_oos_fitness=best.oos_fitness,
            mean_fitness=mean_fitness,
            evaluated=len(evaluations),
            promoted=promoted,
            champion_id=champion_id,
            notes=notes,
        )
        self.brain.b1.log_event("generation", report.summary(), {"nudges": nudges})
        log.info(report.summary())
        return report

    def evolve(self, candles: Sequence[Candle], generations: Optional[int] = None) -> List[GenerationReport]:
        return [
            self.run_generation(candles)
            for _ in range(generations or self.cfg.generations_per_cycle)
        ]

    # ------------------------------------------------------------------
    # Promotion and breeding
    # ------------------------------------------------------------------
    def maybe_promote(self, evaluations: Sequence[Evaluation]) -> tuple[bool, str]:
        """Promote on out-of-sample evidence only, and only by a clear margin.

        Churning the champion on noise is its own failure mode: every swap
        resets the live track record, and a strategy that is 1% better on a
        hold-out is not measurably better at all.
        """
        current = self.brain.b1.champion()
        candidates = [
            e for e in evaluations
            if e.out_sample.metrics.trades >= self.cfg.min_trades_for_promotion
            and e.out_sample.metrics.max_drawdown <= self.cfg.max_drawdown_pct
        ]
        if not candidates:
            return False, (current or {}).get("id", "none")
        best = max(candidates, key=lambda e: e.oos_fitness)

        if current is None:
            self._install_champion(best, "no incumbent")
            return True, best.genome.id
        if current["id"] == best.genome.id:
            return False, current["id"]

        incumbent = float(current.get("oos_fitness", 0.0))
        required = incumbent + self.cfg.promotion_margin * max(1.0, abs(incumbent))
        if best.oos_fitness > required and best.oos_fitness > 0:
            self._install_champion(
                best,
                f"out-of-sample fitness {best.oos_fitness:+.3f} beats incumbent "
                f"{incumbent:+.3f} by more than the {self.cfg.promotion_margin:.0%} margin",
            )
            return True, best.genome.id
        return False, current["id"]

    def _install_champion(self, ev: Evaluation, why: str) -> None:
        self.brain.b1.save_genome(
            ev.genome.id,
            ev.genome.generation,
            ev.genome.to_dict(),
            ev.fitness,
            ev.oos_fitness,
            ev.metrics,
            status="candidate",
        )
        self.brain.b1.set_genome_status(ev.genome.id, "champion")
        message = f"new champion {ev.genome.id}: {why}"
        self.brain.b1.log_event("champion", message, {"genome": ev.genome.to_dict()})
        self.brain.b2.remember(
            Lesson(
                text=f"{message}. {ev.genome.describe()}",
                kind="evolution",
                weight=2.0,
                meta={"genome_id": ev.genome.id, "oos_fitness": ev.oos_fitness},
            )
        )
        log.info(message)

    def breed(
        self, evaluations: Sequence[Evaluation], nudges: Dict[str, float], generation: int
    ) -> List[Genome]:
        elites = [e.genome for e in evaluations[: self.cfg.elite_count]]
        next_gen: List[Genome] = list(elites)
        guard = 0
        while len(next_gen) < self.cfg.population_size and guard < self.cfg.population_size * 12:
            guard += 1
            parent_a = self._tournament(evaluations)
            parent_b = self._tournament(evaluations)
            child = (
                parent_a.crossover(parent_b, self.rng, generation)
                if parent_a.id != parent_b.id and self.rng.random() < 0.65
                else parent_a
            )
            child = child.mutate(
                self.rng,
                rate=self.cfg.mutation_rate,
                scale=self.cfg.mutation_scale,
                nudges=nudges,
                generation=generation,
            )
            if not self.cfg.allow_short:
                child.genes["allow_short"] = False
            if any(child.distance(existing) < 0.02 for existing in next_gen):
                continue  # too close to something we already have; try again
            next_gen.append(child)
        while len(next_gen) < self.cfg.population_size:  # diversity guard exhausted
            next_gen.append(Genome.random(self.rng, generation))
        return next_gen[: self.cfg.population_size]

    def _tournament(self, evaluations: Sequence[Evaluation]) -> Genome:
        size = min(self.cfg.tournament_size, len(evaluations))
        contenders = self.rng.sample(list(evaluations), size)
        return max(contenders, key=lambda e: e.fitness).genome
