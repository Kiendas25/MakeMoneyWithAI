"""The two brains, wired together.

``DualBrain`` is the only object the rest of the agent talks to. It owns:

* **Brain 1** (:class:`Hippocampus`) - exact episodic ledger.
* **Brain 2** (:class:`Cortex`) - semantic lessons, searched by meaning.

and the two flows between them:

* **consolidation** ("sleep"): periodically re-read the raw episodes in Brain 1,
  aggregate them into statements worth generalising, and write those into
  Brain 2. Raw trades are data; distilled lessons are memory.
* **advice** (recall at decision time): before acting, the agent describes its
  current situation, recalls what similar situations produced, and turns that
  into a concrete bias - size up, size down, or refuse the trade outright.

The second flow is the point. Memory that cannot change behaviour is decoration.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from ..config import Config
from ..core.types import Lesson, Signal, Trade
from .cortex import Cortex, Recall
from .embeddings import HashingEmbedder
from .hippocampus import Hippocampus

log = logging.getLogger(__name__)

LAST_CONSOLIDATION_KEY = "memory.last_consolidated_ts"


@dataclass
class MemoryBias:
    """What Brain 2 wants to change about the decision Brain 1's strategy made."""

    size_mult: float = 1.0
    veto_long: bool = False
    veto_short: bool = False
    confidence: float = 0.0
    notes: List[str] = field(default_factory=list)
    gene_nudges: Dict[str, float] = field(default_factory=dict)

    def vetoes(self, direction: int) -> bool:
        return (direction > 0 and self.veto_long) or (direction < 0 and self.veto_short)

    def describe(self) -> str:
        if not self.notes:
            return "no relevant memories"
        head = f"x{self.size_mult:.2f} size"
        if self.veto_long or self.veto_short:
            head += " + veto(" + ("long" if self.veto_long else "") + ("short" if self.veto_short else "") + ")"
        return f"{head} from {len(self.notes)} memories"


class DualBrain:
    def __init__(self, cfg: Config, hippocampus: Optional[Hippocampus] = None,
                 cortex: Optional[Cortex] = None) -> None:
        cfg.ensure_dirs()
        self.cfg = cfg
        self.b1 = hippocampus or Hippocampus(cfg.hippocampus_path)
        self.b2 = cortex or Cortex(
            cfg.cortex_path,
            embedder=HashingEmbedder(cfg.memory_dim),
            half_life_days=cfg.memory_half_life_days,
            max_items=cfg.max_memories,
        )

    def close(self) -> None:
        self.b1.close()
        self.b2.close()

    def __enter__(self) -> "DualBrain":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------
    def remember_trade(self, trade: Trade) -> None:
        """A closed trade lands in both brains: the row in Brain 1, the story in Brain 2."""
        self.b1.record_trade(trade)
        self.b2.remember(
            Lesson(
                text=trade.summary(),
                kind="trade",
                weight=1.0 + min(2.0, abs(trade.pnl_pct) * 20.0),
                meta={
                    "side": trade.side,
                    "regime": trade.regime,
                    "pnl_pct": trade.pnl_pct,
                    "genome_id": trade.genome_id,
                    "reason_open": trade.reason_open,
                    "reason_close": trade.reason_close,
                },
            )
        )

    def remember(self, lesson: Lesson) -> int:
        return self.b2.remember(lesson)

    # ------------------------------------------------------------------
    # Recall
    # ------------------------------------------------------------------
    @staticmethod
    def context_text(symbol: str, signal: Signal, extra: str = "") -> str:
        """The query Brain 2 is searched with - deliberately written in the same
        vocabulary the lessons are, so the embedding actually matches."""
        side = "long" if signal.direction > 0 else "short" if signal.direction < 0 else "flat"
        feats = " ".join(f"{k}={v:.2f}" for k, v in sorted(signal.features.items()))
        return (
            f"{side} {symbol} in regime '{signal.regime}' on '{signal.reason}' "
            f"score={signal.score:.2f} {feats} {extra}".strip()
        )

    #: Kinds that carry a measurable outcome. Evolution bookkeeping is excluded:
    #: it would otherwise crowd genuine lessons out of the top-k.
    EVIDENCE_KINDS = ("trade", "regime", "reflection")

    def advice(self, symbol: str, signal: Signal, k: Optional[int] = None) -> MemoryBias:
        query = self.context_text(symbol, signal)
        recalls = self.b2.recall(query, k=k or self.cfg.recall_k, kind=self.EVIDENCE_KINDS)
        return self.bias_from_recalls(recalls, signal.direction)

    def bias_from_recalls(self, recalls: Sequence[Recall], direction: int) -> MemoryBias:
        bias = MemoryBias()
        if not recalls:
            return bias
        side = "long" if direction > 0 else "short" if direction < 0 else None
        evidence: List[float] = []
        weights: List[float] = []
        samples_total = 0
        losing_samples = 0
        for r in recalls:
            outcome = r.meta.get("pnl_pct", r.meta.get("avg_pct"))
            if outcome is None:
                for gene, nudge in (r.meta.get("gene_hints") or {}).items():
                    bias.gene_nudges[gene] = bias.gene_nudges.get(gene, 0.0) + float(nudge)
                continue
            if side and r.meta.get("side") not in (None, side):
                continue  # a lesson about shorts says little about this long
            samples = max(1, int(r.meta.get("samples", 1)))
            sample_weight = r.similarity * (1.0 + 0.3 * r.weight) * samples**0.5
            evidence.append(float(outcome))
            weights.append(sample_weight)
            samples_total += samples
            if float(outcome) < 0:
                losing_samples += samples
            bias.notes.append(r.text)
            for gene, nudge in (r.meta.get("gene_hints") or {}).items():
                bias.gene_nudges[gene] = bias.gene_nudges.get(gene, 0.0) + float(nudge)

        if not evidence:
            return bias
        total_w = sum(weights) or 1.0
        weighted = sum(e * w for e, w in zip(evidence, weights)) / total_w
        # Confidence counts *episodes*, not memories: one vivid loss recalled
        # three times is still one loss.
        bias.confidence = min(1.0, samples_total / 8.0)
        # A 1% average historical edge in similar situations moves size by ~20%.
        bias.size_mult = _clamp(1.0 + 20.0 * weighted * bias.confidence, 0.4, 1.5)
        # A veto blocks the strategy outright, so it demands real evidence:
        # a materially negative average over at least six similar episodes, most
        # of which lost. Anything weaker only trims size.
        if (
            weighted < -0.02
            and samples_total >= 6
            and losing_samples >= 0.6 * samples_total
        ):
            if direction > 0:
                bias.veto_long = True
            elif direction < 0:
                bias.veto_short = True
        return bias

    # ------------------------------------------------------------------
    # Consolidation ("sleep")
    # ------------------------------------------------------------------
    def consolidate(self, reflector=None, min_trades: int = 3, window: int = 60) -> List[Lesson]:
        """Turn recent raw episodes into generalisations.

        Triggered by new trades, but distilled over a rolling window of the last
        ``window`` round trips: grouping only the two or three trades booked
        since the last pass would never reach a sample size worth generalising
        from. Re-distilling overlapping windows is deliberate - Brain 2
        deduplicates identical text and reinforces it instead, so a pattern that
        keeps holding gets heavier every time it is re-derived.
        """
        since = int(self.b1.get_state(LAST_CONSOLIDATION_KEY, 0) or 0)
        fresh = self.b1.trades_since(since)
        if not fresh:
            return []
        trades = sorted(self.b1.recent_trades(limit=window), key=lambda t: t.exit_ts)

        lessons: List[Lesson] = []
        lessons.extend(_group_lessons(trades, key=lambda t: (t.regime, t.side),
                                      label=lambda k: f"regime '{k[0]}' {k[1]} entries",
                                      kind="regime", min_trades=min_trades))
        lessons.extend(_group_lessons(trades, key=lambda t: (t.genome_id,),
                                      label=lambda k: f"genome {k[0]}",
                                      kind="evolution", min_trades=min_trades))
        lessons.extend(_group_lessons(trades, key=lambda t: (t.reason_close,),
                                      label=lambda k: f"exits via '{k[0]}'",
                                      kind="reflection", min_trades=min_trades))

        if reflector is not None:
            try:
                lessons.extend(reflector.reflect(trades, self.b1.trade_stats()))
            except Exception as exc:  # reflection is a bonus, never a blocker
                log.warning("reflector failed: %s", exc)
                self.b1.log_event("reflect_error", str(exc), level="WARNING")

        for lesson in lessons:
            self.b2.remember(lesson)
        # The watermark advances past the newly booked trades only, so the next
        # pass fires on genuinely new activity rather than on the window's tail.
        self.b1.set_state(LAST_CONSOLIDATION_KEY, max(t.exit_ts for t in fresh) + 1)
        self.b1.log_event(
            "consolidate",
            f"distilled {len(trades)} trades into {len(lessons)} lessons",
            {"lessons": [l.text for l in lessons[:5]]},
        )
        return lessons

    # ------------------------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        return {
            "brain1": {
                "trades": self.b1.trade_stats(),
                "generations": self.b1.last_generation(),
                "champion": (self.b1.champion() or {}).get("id"),
            },
            "brain2": self.b2.stats(),
        }


def _group_lessons(trades: Sequence[Trade], key, label, kind: str, min_trades: int) -> List[Lesson]:
    groups: Dict[Any, List[Trade]] = {}
    for t in trades:
        groups.setdefault(key(t), []).append(t)
    out: List[Lesson] = []
    for group_key, group in groups.items():
        if len(group) < min_trades:
            continue
        pcts = [t.pnl_pct for t in group]
        avg = statistics.fmean(pcts)
        wins = sum(1 for p in pcts if p > 0)
        verdict = "worked" if avg > 0 else "lost money"
        sides = {t.side for t in group}
        out.append(
            Lesson(
                text=(
                    f"{label(group_key)} {verdict}: {len(group)} trades, "
                    f"avg {avg * 100:+.2f}%, win rate {wins / len(group) * 100:.0f}%, "
                    f"worst {min(pcts) * 100:+.2f}%, best {max(pcts) * 100:+.2f}%"
                ),
                kind=kind,
                weight=1.0 + min(2.0, len(group) / 10.0),
                meta={
                    "avg_pct": avg,
                    "samples": len(group),
                    "win_rate": wins / len(group),
                    "side": next(iter(sides)) if len(sides) == 1 else None,
                    "group": [str(part) for part in group_key],
                    "kind": kind,
                },
            )
        )
    return out


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
