"""Reflection: turning outcomes into hypotheses.

Consolidation (in ``brain/memory.py``) summarises *what* happened. Reflection
asks *what to change about it*, and emits lessons carrying ``gene_hints`` -
directional pressure on specific genes that the evolution engine applies as a
mutation bias. That is the loop that makes this agent self-improving rather than
merely self-describing: outcome -> lesson -> mutation bias -> next generation.

Two implementations:

* ``HeuristicReflector`` (default) - explicit, auditable rules over trade
  statistics. No network, no API key, deterministic.
* ``LLMReflector`` - asks Claude for hypotheses, validated against the same
  gene whitelist before anything is trusted. Falls back to the heuristic on any
  error, because reflection must never be able to stall the trading loop.
"""

from __future__ import annotations

import json
import logging
import os
import statistics
import urllib.error
import urllib.request
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence

from ..core.types import Lesson, Trade
from ..strategy.genome import GENE_SPECS

log = logging.getLogger(__name__)


class HeuristicReflector:
    """Rule-based post-mortem over recent trades."""

    name = "heuristic"

    def __init__(self, min_trades: int = 5) -> None:
        self.min_trades = min_trades

    def reflect(self, trades: Sequence[Trade], stats: Dict[str, Any]) -> List[Lesson]:
        if len(trades) < self.min_trades:
            return []
        lessons: List[Lesson] = []
        pcts = [t.pnl_pct for t in trades]
        avg = statistics.fmean(pcts)
        closes = Counter(t.reason_close for t in trades)
        n = len(trades)
        wins = [p for p in pcts if p > 0]
        losses = [p for p in pcts if p <= 0]

        stop_share = closes.get("stop_loss", 0) / n
        if stop_share > 0.5:
            lessons.append(
                self._lesson(
                    f"{stop_share * 100:.0f}% of the last {n} trades ended on the stop: "
                    "stops are sitting inside normal noise, widen them and cut size to compensate",
                    {"stop_atr_mult": +1.0, "risk_scale": -0.5},
                    weight=1.6,
                )
            )
        time_share = closes.get("time_stop", 0) / n
        if time_share > 0.35:
            lessons.append(
                self._lesson(
                    f"{time_share * 100:.0f}% of trades hit the time stop rather than a target: "
                    "either the hold window is too short or entries are too early",
                    {"max_bars_held": +1.0, "entry_threshold": +0.5},
                    weight=1.3,
                )
            )
        flip_share = closes.get("signal_flip", 0) / n
        if flip_share > 0.5 and avg < 0:
            lessons.append(
                self._lesson(
                    "most exits come from the signal flipping and the average trade is negative: "
                    "the entry threshold is too loose, the strategy is trading noise",
                    {"entry_threshold": +1.0, "exit_threshold": +0.3},
                    weight=1.4,
                )
            )
        if wins and losses:
            payoff = statistics.fmean(wins) / abs(statistics.fmean(losses))
            if payoff < 0.8:
                lessons.append(
                    self._lesson(
                        f"payoff ratio is {payoff:.2f}: winners are smaller than losers, "
                        "let profits run further before taking them",
                        {"tp_atr_mult": +1.0, "trail_atr_mult": +0.5},
                        weight=1.5,
                    )
                )
            elif payoff > 2.5 and len(wins) / n < 0.3:
                lessons.append(
                    self._lesson(
                        f"payoff is high ({payoff:.2f}) but only {len(wins) / n * 100:.0f}% of "
                        "trades win: targets are too ambitious for the hit rate",
                        {"tp_atr_mult": -0.7},
                        weight=1.1,
                    )
                )
        if stats.get("fees", 0) and abs(stats["fees"]) > abs(stats.get("net_pnl", 0.0)):
            lessons.append(
                self._lesson(
                    "fees exceed net PnL: the strategy is trading too often to survive costs",
                    {"entry_threshold": +0.8, "max_bars_held": +0.5},
                    weight=1.7,
                )
            )
        worst_regime = _worst_regime(trades)
        if worst_regime:
            regime, regime_avg, count = worst_regime
            lessons.append(
                self._lesson(
                    f"regime '{regime}' is the worst performer: {count} trades averaging "
                    f"{regime_avg * 100:+.2f}% - tighten the volatility gate there",
                    {"max_vol": -0.6},
                    weight=1.2,
                )
            )
        return lessons

    @staticmethod
    def _lesson(text: str, hints: Dict[str, float], weight: float = 1.0) -> Lesson:
        return Lesson(
            text=text,
            kind="reflection",
            weight=weight,
            meta={"gene_hints": validate_hints(hints), "source": "heuristic"},
        )


def _worst_regime(trades: Sequence[Trade]) -> Optional[tuple[str, float, int]]:
    by_regime: Dict[str, List[float]] = {}
    for t in trades:
        by_regime.setdefault(t.regime, []).append(t.pnl_pct)
    eligible = [(r, statistics.fmean(v), len(v)) for r, v in by_regime.items() if len(v) >= 3]
    if not eligible:
        return None
    worst = min(eligible, key=lambda item: item[1])
    return worst if worst[1] < 0 else None


def validate_hints(hints: Dict[str, Any]) -> Dict[str, float]:
    """Only real genes, only sane magnitudes. Applies to LLM output too."""
    clean: Dict[str, float] = {}
    for gene, value in (hints or {}).items():
        if gene not in GENE_SPECS:
            continue
        try:
            nudge = float(value)
        except (TypeError, ValueError):
            continue
        clean[gene] = max(-2.0, min(2.0, nudge))
    return clean


class LLMReflector:
    """Optional Claude-powered reflection over the recent trade log."""

    name = "llm"
    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, model: str = "claude-sonnet-5", max_trades: int = 40,
                 timeout: float = 45.0) -> None:
        self.model = model
        self.max_trades = max_trades
        self.timeout = timeout
        self.fallback = HeuristicReflector()

    def reflect(self, trades: Sequence[Trade], stats: Dict[str, Any]) -> List[Lesson]:
        lessons = self.fallback.reflect(trades, stats)  # always keep the auditable baseline
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key or not trades:
            return lessons
        try:
            lessons.extend(self._ask_claude(api_key, trades, stats))
        except Exception as exc:
            log.warning("LLM reflection unavailable (%s); using heuristics only", exc)
        return lessons

    def _ask_claude(self, api_key: str, trades: Sequence[Trade],
                    stats: Dict[str, Any]) -> List[Lesson]:
        sample = [
            {
                "side": t.side,
                "regime": t.regime,
                "pnl_pct": round(t.pnl_pct, 4),
                "opened_because": t.reason_open,
                "closed_because": t.reason_close,
            }
            for t in list(trades)[-self.max_trades:]
        ]
        prompt = (
            "You are reviewing an automated crypto trading agent's recent closed trades.\n"
            f"Aggregate stats: {json.dumps(stats)}\n"
            f"Trades: {json.dumps(sample)}\n\n"
            "Tunable genes and their meaning:\n"
            + "\n".join(f"- {name}: {spec.note} (range {spec.low}..{spec.high})"
                        for name, spec in GENE_SPECS.items())
            + "\n\nReturn STRICT JSON: {\"lessons\": [{\"text\": str, "
            "\"gene_hints\": {gene: number between -2 and 2}}]}. "
            "Give at most 4 lessons. A positive hint means increase the gene. "
            "Base every claim on the trades shown; if the sample is too small to "
            "conclude anything, return an empty list."
        )
        body = json.dumps(
            {
                "model": self.model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode()
        req = urllib.request.Request(
            self.API_URL,
            data=body,
            headers={
                "content-type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            payload = json.loads(resp.read().decode())
        text = "".join(block.get("text", "") for block in payload.get("content", []))
        return self._parse(text)

    @staticmethod
    def _parse(text: str) -> List[Lesson]:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return []
        try:
            data = json.loads(text[start: end + 1])
        except json.JSONDecodeError:
            return []
        out: List[Lesson] = []
        for item in (data.get("lessons") or [])[:4]:
            body = str(item.get("text", "")).strip()
            if not body:
                continue
            out.append(
                Lesson(
                    text=body,
                    kind="reflection",
                    weight=1.0,
                    meta={"gene_hints": validate_hints(item.get("gene_hints")), "source": "llm"},
                )
            )
        return out


def make_reflector(cfg) -> HeuristicReflector | LLMReflector:
    if cfg.reflector == "llm":
        return LLMReflector(model=cfg.llm_model)
    return HeuristicReflector()
