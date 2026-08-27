"""The strategy genome - the thing that actually evolves.

A genome is a flat, bounded, typed parameter vector: indicator lengths, module
weights, entry/exit thresholds, and risk shape. Every gene has hard bounds, so
mutation can never produce a strategy that is invalid, only one that is bad -
and bad is what selection is for.

Keeping the genome flat (rather than, say, an evolvable expression tree) is a
deliberate trade: a smaller search space, but every candidate is interpretable
and every mutation is explainable in a sentence, which is what makes the lessons
in Brain 2 worth writing.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional


@dataclass(frozen=True)
class Gene:
    kind: str  # "int" | "float" | "bool"
    low: float
    high: float
    note: str = ""

    def span(self) -> float:
        return max(1e-9, self.high - self.low)

    def clamp(self, value: float) -> Any:
        if self.kind == "bool":
            return bool(value)
        value = max(self.low, min(self.high, float(value)))
        return int(round(value)) if self.kind == "int" else float(value)

    def sample(self, rng: random.Random) -> Any:
        if self.kind == "bool":
            return rng.random() < 0.5
        if self.kind == "int":
            return rng.randint(int(self.low), int(self.high))
        return rng.uniform(self.low, self.high)


GENE_SPECS: Dict[str, Gene] = {
    # --- indicator lengths ---
    "ema_fast": Gene("int", 3, 60, "fast trend EMA"),
    "ema_slow": Gene("int", 10, 220, "slow trend EMA"),
    "rsi_len": Gene("int", 5, 40, "RSI lookback"),
    "atr_len": Gene("int", 5, 40, "ATR lookback, drives stops and sizing"),
    "breakout_len": Gene("int", 5, 120, "Donchian channel length"),
    "bb_len": Gene("int", 10, 80, "mean-reversion band length"),
    "vol_len": Gene("int", 10, 80, "realised volatility window"),
    "slope_len": Gene("int", 5, 60, "trend slope window used for regime"),
    # --- module weights (blended into one conviction score) ---
    "w_trend": Gene("float", 0.0, 1.0, "EMA spread"),
    "w_macd": Gene("float", 0.0, 1.0, "MACD histogram"),
    "w_breakout": Gene("float", 0.0, 1.0, "position in the N-bar range"),
    "w_meanrev": Gene("float", 0.0, 1.0, "distance from the band mean"),
    "w_rsi": Gene("float", 0.0, 1.0, "RSI threshold crossings"),
    # --- decision thresholds ---
    "entry_threshold": Gene("float", 0.08, 0.85, "|score| needed to open"),
    "exit_threshold": Gene("float", 0.0, 0.6, "score decay that closes a winner"),
    "rsi_buy": Gene("float", 10.0, 48.0, "oversold line"),
    "rsi_sell": Gene("float", 52.0, 92.0, "overbought line"),
    "bb_entry_z": Gene("float", 0.5, 3.5, "sigma from mean for mean reversion"),
    # --- risk shape ---
    "stop_atr_mult": Gene("float", 0.5, 6.0, "initial stop distance in ATRs"),
    "tp_atr_mult": Gene("float", 0.8, 14.0, "take-profit distance in ATRs"),
    "trail_atr_mult": Gene("float", 0.0, 6.0, "0 disables trailing"),
    "max_bars_held": Gene("int", 4, 400, "time stop"),
    "max_vol": Gene("float", 0.004, 0.15, "stand aside above this per-bar vol"),
    "risk_scale": Gene("float", 0.25, 2.0, "multiplier on the configured risk"),
    # --- direction ---
    "allow_short": Gene("bool", 0, 1, "may open shorts"),
}


@dataclass
class Genome:
    genes: Dict[str, Any]
    generation: int = 0
    parents: List[str] = field(default_factory=list)
    origin: str = "random"

    def __post_init__(self) -> None:
        self.genes = self.repair(self.genes)

    # ------------------------------------------------------------------
    @property
    def id(self) -> str:
        payload = json.dumps(self.genes, sort_keys=True, default=str)
        return hashlib.blake2b(payload.encode(), digest_size=6).hexdigest()

    def __getitem__(self, key: str) -> Any:
        return self.genes[key]

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.genes)

    def to_json(self) -> str:
        return json.dumps(self.genes, sort_keys=True, default=str)

    @classmethod
    def from_dict(cls, genes: Mapping[str, Any], generation: int = 0, origin: str = "loaded") -> "Genome":
        return cls(genes=dict(genes), generation=generation, origin=origin)

    # ------------------------------------------------------------------
    @staticmethod
    def repair(genes: Mapping[str, Any]) -> Dict[str, Any]:
        """Fill gaps, clamp everything into range, enforce cross-gene sanity."""
        out: Dict[str, Any] = {}
        for name, spec in GENE_SPECS.items():
            value = genes.get(name, (spec.low + spec.high) / 2 if spec.kind != "bool" else False)
            out[name] = spec.clamp(value)
        if out["ema_slow"] <= out["ema_fast"]:
            out["ema_slow"] = GENE_SPECS["ema_slow"].clamp(out["ema_fast"] + 5)
        if out["rsi_sell"] <= out["rsi_buy"] + 4:
            out["rsi_sell"] = GENE_SPECS["rsi_sell"].clamp(out["rsi_buy"] + 10)
        if out["tp_atr_mult"] <= out["stop_atr_mult"] * 0.5:
            # A take-profit tighter than half the stop is a losing lottery ticket.
            out["tp_atr_mult"] = GENE_SPECS["tp_atr_mult"].clamp(out["stop_atr_mult"] * 1.5)
        if sum(out[w] for w in ("w_trend", "w_macd", "w_breakout", "w_meanrev", "w_rsi")) < 0.05:
            out["w_trend"] = 0.5  # a genome with no opinion at all never trades
        return out

    # ------------------------------------------------------------------
    @classmethod
    def random(cls, rng: random.Random, generation: int = 0) -> "Genome":
        return cls(
            genes={name: spec.sample(rng) for name, spec in GENE_SPECS.items()},
            generation=generation,
            origin="random",
        )

    def mutate(
        self,
        rng: random.Random,
        rate: float = 0.25,
        scale: float = 0.25,
        nudges: Optional[Mapping[str, float]] = None,
        generation: Optional[int] = None,
    ) -> "Genome":
        """Gaussian creep on a random subset of genes.

        ``nudges`` is how Brain 2 reaches into evolution: a lesson that says
        "stops under 1 ATR kept getting hit" becomes a directional bias on the
        ``stop_atr_mult`` gene rather than a blind coin flip.
        """
        nudges = nudges or {}
        child: Dict[str, Any] = dict(self.genes)
        touched: List[str] = []
        for name, spec in GENE_SPECS.items():
            if rng.random() > rate:
                continue
            touched.append(name)
            if spec.kind == "bool":
                child[name] = not child[name]
                continue
            drift = rng.gauss(0.0, scale) * spec.span()
            bias = float(nudges.get(name, 0.0)) * 0.15 * spec.span()
            child[name] = spec.clamp(float(child[name]) + drift + bias)
        if not touched:  # always change something, or the child is a duplicate
            name = rng.choice(list(GENE_SPECS))
            spec = GENE_SPECS[name]
            child[name] = spec.sample(rng)
            touched.append(name)
        return Genome(
            genes=child,
            generation=self.generation + 1 if generation is None else generation,
            parents=[self.id],
            origin=f"mutation({','.join(sorted(touched)[:4])})",
        )

    def crossover(self, other: "Genome", rng: random.Random,
                  generation: Optional[int] = None) -> "Genome":
        """Uniform crossover; numeric genes may also blend.

        Which parent a gene picks (``pick_roll``) and whether the gene picks
        discretely at all versus blends (``mode_roll``) must be independent
        rolls. Reusing one roll for both (as in ``a if roll < 0.5 else b``
        gated by ``roll < 0.4``) silently makes the discrete branch always
        resolve to ``a``, since ``roll < 0.4`` already implies ``roll < 0.5`` -
        parent B then never contributes a numeric gene on its own, only ever
        diluted into a blend.
        """
        child: Dict[str, Any] = {}
        for name, spec in GENE_SPECS.items():
            a, b = self.genes[name], other.genes[name]
            pick_roll = rng.random()
            if spec.kind == "bool":
                child[name] = a if pick_roll < 0.5 else b
                continue
            mode_roll = rng.random()
            if mode_roll < 0.4:
                child[name] = a if pick_roll < 0.5 else b
            else:
                mix = rng.uniform(0.2, 0.8)
                child[name] = spec.clamp(float(a) * mix + float(b) * (1.0 - mix))
        gen = max(self.generation, other.generation) + 1 if generation is None else generation
        return Genome(genes=child, generation=gen, parents=[self.id, other.id], origin="crossover")

    # ------------------------------------------------------------------
    def distance(self, other: "Genome") -> float:
        """Normalised gene-space distance, used to keep the population diverse."""
        total = 0.0
        for name, spec in GENE_SPECS.items():
            a, b = self.genes[name], other.genes[name]
            if spec.kind == "bool":
                total += 0.0 if a == b else 1.0
            else:
                total += abs(float(a) - float(b)) / spec.span()
        return total / len(GENE_SPECS)

    def describe(self) -> str:
        g = self.genes
        modules = sorted(
            (("trend", g["w_trend"]), ("macd", g["w_macd"]), ("breakout", g["w_breakout"]),
             ("meanrev", g["w_meanrev"]), ("rsi", g["w_rsi"])),
            key=lambda kv: kv[1],
            reverse=True,
        )
        lead = ", ".join(f"{name} {weight:.2f}" for name, weight in modules[:3])
        return (
            f"genome {self.id} (gen {self.generation}, {self.origin}): leans on {lead}; "
            f"EMA {g['ema_fast']}/{g['ema_slow']}, entry>{g['entry_threshold']:.2f}, "
            f"stop {g['stop_atr_mult']:.1f}ATR, tp {g['tp_atr_mult']:.1f}ATR, "
            f"{'long+short' if g['allow_short'] else 'long only'}"
        )


def seed_population(rng: random.Random, size: int, allow_short: bool) -> List[Genome]:
    """Start from a few hand-written archetypes, then fill with randoms.

    Pure random initialisation wastes generations rediscovering that trend
    following and mean reversion exist. These four are the classic families;
    evolution's job is to tune and recombine them, not to reinvent them.
    """
    archetypes: List[Dict[str, Any]] = [
        {  # trend follower
            "ema_fast": 12, "ema_slow": 48, "w_trend": 0.9, "w_macd": 0.5, "w_breakout": 0.4,
            "w_meanrev": 0.0, "w_rsi": 0.1, "entry_threshold": 0.25, "exit_threshold": 0.08,
            "stop_atr_mult": 2.5, "tp_atr_mult": 6.0, "trail_atr_mult": 3.0, "max_bars_held": 200,
            "atr_len": 14, "max_vol": 0.05, "risk_scale": 1.0,
        },
        {  # breakout
            "ema_fast": 8, "ema_slow": 30, "breakout_len": 55, "w_trend": 0.3, "w_macd": 0.2,
            "w_breakout": 1.0, "w_meanrev": 0.0, "w_rsi": 0.0, "entry_threshold": 0.45,
            "exit_threshold": 0.15, "stop_atr_mult": 2.0, "tp_atr_mult": 8.0,
            "trail_atr_mult": 2.5, "max_bars_held": 120, "atr_len": 20, "max_vol": 0.07,
        },
        {  # mean reversion
            "ema_fast": 5, "ema_slow": 60, "bb_len": 24, "bb_entry_z": 1.8, "w_trend": 0.1,
            "w_macd": 0.0, "w_breakout": 0.0, "w_meanrev": 1.0, "w_rsi": 0.7,
            "rsi_len": 9, "rsi_buy": 28, "rsi_sell": 72, "entry_threshold": 0.35,
            "exit_threshold": 0.05, "stop_atr_mult": 2.2, "tp_atr_mult": 3.0,
            "trail_atr_mult": 0.0, "max_bars_held": 40, "atr_len": 10, "max_vol": 0.04,
        },
        {  # slow, low-turnover carry of the dominant trend
            "ema_fast": 30, "ema_slow": 150, "w_trend": 1.0, "w_macd": 0.3, "w_breakout": 0.2,
            "w_meanrev": 0.0, "w_rsi": 0.0, "entry_threshold": 0.2, "exit_threshold": 0.02,
            "stop_atr_mult": 4.0, "tp_atr_mult": 12.0, "trail_atr_mult": 4.5,
            "max_bars_held": 400, "atr_len": 21, "max_vol": 0.09, "risk_scale": 0.8,
        },
    ]
    population: List[Genome] = []
    for genes in archetypes[:size]:
        genes = dict(genes)
        genes["allow_short"] = allow_short and genes.get("allow_short", True)
        population.append(Genome(genes=genes, generation=0, origin="archetype"))
    while len(population) < size:
        candidate = Genome.random(rng)
        if not allow_short:
            candidate.genes["allow_short"] = False
        population.append(candidate)
    return population
