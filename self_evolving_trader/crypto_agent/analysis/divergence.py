"""Live-vs-backtest divergence for the champion genome.

Nothing else in the agent compares what the backtester *predicted* a genome
would do against what that genome *actually* did once it was trading. That
comparison is arguably the highest-value diagnostic a paper-trading system
can produce short of real money: it is how a slippage model that is quietly
too generous gets caught before an operator flips ``mode`` to ``live`` and
pays for the difference themselves.

Two, quite different, things can make the live record disagree with a fresh
backtest of the same genome over the same candles, and this module is built
to keep them apart rather than reporting one number that conflates them:

1. **The fill model was wrong.** ``PaperBroker.market_order`` and
   ``backtest.simulate`` price a fill with the exact same formula
   (``price * (1 +/- slippage_bps / 10_000)``), so under paper trading a
   fill divergence almost always means the assumptions moved underneath the
   trade - ``slippage_bps``/``fee_bps`` changed in config after the trade
   was booked, or a candle was re-fetched and revised - rather than a
   general truth about the model. Under live trading (a real exchange fill)
   this is the comparison that actually matters: it is the live cost of
   trading versus what the model assumed it would be.
2. **The agent chose differently.** Brain 2's memory bias can veto an
   entry or resize it, and the risk manager can refuse one outright, both
   *after* the same deterministic rule engine produced the same signal a
   fresh backtest would replay bar-for-bar. A missed entry explained by a
   logged ``veto:memory`` or ``veto:risk`` decision is the system working
   exactly as designed, not a modelling failure.

Because of (2), every comparison here is scoped to trades and decisions
attributed to the *current* champion genome. A position still being managed
by a retired genome (see ``TradingAgent._genome_for_position``), or an entry
considered under a genome that has since been replaced, is not a fair test
of today's champion - mixing it in would blame the model for what was
actually a different strategy trading. That scoping, and its consequences,
are the caveats carried on every :class:`DivergenceReport`.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ..brain.memory import DualBrain
from ..config import Config
from ..core.types import Trade
from ..strategy.backtest import simulate
from ..strategy.genome import Genome

# How far back into Brain 1 to look. A divergence report is about the
# champion's recent live record, not a full-history replay, so these bound
# the cost of computing one against a long-running agent's ledger.
DEFAULT_TRADE_LIMIT = 5000
DEFAULT_DECISION_LIMIT = 20000
# Candles handed to the backtester per symbol - generous enough to cover a
# long trading window plus every genome's indicator warmup.
DEFAULT_CANDLE_LIMIT = 4000

# Paper fills use the identical formula the backtester does, so anything
# above this on a paper-traded window is a real discrepancy worth naming as
# the headline finding rather than noise from float rounding.
FILL_DIVERGENCE_THRESHOLD_BPS = 3.0


@dataclass
class FillComparison:
    """One matched entry or exit: what actually got booked against what a
    fresh backtest of the same genome and candle would have booked at that
    same bar."""

    ts: int
    realised_price: float
    modelled_price: float

    @property
    def error_bps(self) -> float:
        """Signed difference, in basis points of the modelled price.

        Positive means the live fill was higher than the model predicted -
        worse on a buy, better on a sell - so a caller that cares about
        direction should read this alongside the trade's side rather than
        assume "positive is bad".
        """
        if self.modelled_price == 0:
            return 0.0
        return (self.realised_price - self.modelled_price) / self.modelled_price * 10_000.0


def _mean_bps(fills: Sequence[FillComparison]) -> Optional[float]:
    return statistics.fmean(f.error_bps for f in fills) if fills else None


@dataclass
class SymbolDivergence:
    """Divergence numbers for one market, or the pooled total across all of
    them (``symbol == "pooled"``)."""

    symbol: str
    realised_trades: int = 0
    modelled_trades: int = 0
    realised_wins: int = 0
    modelled_wins: int = 0
    matched_entries: int = 0
    # The backtest would have entered here; the live agent's memory bias
    # (or the risk manager) explicitly said no - a choice, not an error.
    memory_declined: int = 0
    risk_declined: int = 0
    # The backtest entered and nothing in the decision log explains why the
    # live agent did not: worth investigating, but not yet attributable to
    # either a modelling problem or a deliberate veto.
    unexplained_backtest_only: int = 0
    # The live agent booked a champion-genome trade a fresh backtest of the
    # same genome and candles does not reproduce at that bar - most often a
    # candle that was later revised, or an incomplete cache.
    unexplained_live_only: int = 0
    realised_total_pnl: float = 0.0
    modelled_total_pnl: float = 0.0
    entry_fills: List[FillComparison] = field(default_factory=list)
    exit_fills: List[FillComparison] = field(default_factory=list)
    #: Why this symbol was skipped (or partially skipped) - empty when it
    #: was fully compared.
    note: str = ""

    @property
    def realised_win_rate(self) -> float:
        return self.realised_wins / self.realised_trades if self.realised_trades else 0.0

    @property
    def modelled_win_rate(self) -> float:
        return self.modelled_wins / self.modelled_trades if self.modelled_trades else 0.0

    @property
    def mean_entry_slippage_bps(self) -> Optional[float]:
        return _mean_bps(self.entry_fills)

    @property
    def mean_exit_slippage_bps(self) -> Optional[float]:
        return _mean_bps(self.exit_fills)


@dataclass
class DivergenceReport:
    """The full comparison: one :class:`SymbolDivergence` per market, the
    pooled total across all of them, and a plain-English verdict naming the
    largest discrepancy.

    ``verdict`` always distinguishes a fill-model problem from the agent
    having chosen differently (see the module docstring), so it should never
    be read as a blanket "the backtester was wrong" without checking which
    of the two it actually names. ``caveats`` spells out what this report
    cannot tell you, on purpose, every time.
    """

    champion_id: Optional[str]
    window: Optional[Tuple[int, int]]
    per_symbol: Dict[str, SymbolDivergence]
    pooled: SymbolDivergence
    verdict: str
    caveats: List[str] = field(default_factory=list)


def measure_divergence(
    brain: DualBrain,
    cfg: Config,
    symbols: Optional[Sequence[str]] = None,
    candle_limit: int = DEFAULT_CANDLE_LIMIT,
    trade_limit: int = DEFAULT_TRADE_LIMIT,
    decision_limit: int = DEFAULT_DECISION_LIMIT,
) -> DivergenceReport:
    """Re-simulate the current champion over the window it actually traded
    and compare the result against what really happened.

    ``symbols`` defaults to ``cfg.symbol_list``. Degrades gracefully: a brain
    with no champion yet, or a champion with no candles or trades cached,
    returns a report that says so rather than raising.
    """
    champion = brain.b1.champion()
    if champion is None:
        return DivergenceReport(
            champion_id=None,
            window=None,
            per_symbol={},
            pooled=SymbolDivergence("pooled"),
            verdict="no champion has been promoted yet - nothing to compare.",
            caveats=["Evolution has not produced a champion genome in this brain."],
        )

    genome = Genome.from_dict(champion["genes"], champion["generation"], "champion")
    champion_id = str(champion["id"])
    universe = list(symbols) if symbols is not None else cfg.symbol_list

    trades_by_symbol: Dict[str, List[Trade]] = {}
    for trade in brain.b1.recent_trades(limit=trade_limit):
        if trade.genome_id == champion_id and trade.symbol in universe:
            trades_by_symbol.setdefault(trade.symbol, []).append(trade)

    # Only decisions considered under the champion genome are a fair replay
    # target - a veto logged for a different genome says nothing about today's.
    decisions_by_key: Dict[Tuple[str, int], str] = {}
    for row in brain.b1.recent_decisions(limit=decision_limit):
        if str(row.get("genome_id", "")) != champion_id:
            continue
        decisions_by_key[(str(row["symbol"]), int(row["ts"]))] = str(row["action"])

    per_symbol: Dict[str, SymbolDivergence] = {}
    caveats: List[str] = []
    window_start: Optional[int] = None
    window_end: Optional[int] = None

    for symbol in universe:
        realised = sorted(trades_by_symbol.get(symbol, []), key=lambda t: t.entry_ts)
        candles = brain.b1.load_candles(symbol, cfg.timeframe, candle_limit)
        if len(candles) < 60:
            note = (
                f"only {len(candles)} candle(s) cached for {symbol} - too little "
                "history for the backtester to run (needs at least 60)."
            )
            per_symbol[symbol] = SymbolDivergence(symbol, realised_trades=len(realised), note=note)
            if realised:
                # There is a live record but nothing to check it against - that
                # is itself worth surfacing, not silently dropping.
                caveats.append(f"{symbol}: {note}")
            continue

        if realised:
            sym_start = min(t.entry_ts for t in realised)
            sym_end = max(t.exit_ts for t in realised)
        else:
            # No champion trades yet for this market: still simulate it, so a
            # market that should be trading and isn't shows up as such, but
            # there is no live window to bound the comparison to.
            sym_start, sym_end = candles[0].ts, candles[-1].ts

        result = simulate(genome, candles, cfg, start_cash=cfg.start_cash)
        modelled = [t for t in result.trades if sym_start <= t.entry_ts <= sym_end]

        per_symbol[symbol] = _compare_symbol(symbol, realised, modelled, decisions_by_key)
        if realised or modelled:
            window_start = sym_start if window_start is None else min(window_start, sym_start)
            window_end = sym_end if window_end is None else max(window_end, sym_end)

    pooled = _pool(per_symbol.values())
    window = (window_start, window_end) if window_start is not None else None
    caveats.extend([
        "Only trades and decisions logged under the current champion genome are compared; a "
        "position still being managed by a retired genome is excluded on purpose, since "
        "comparing two different strategies would not isolate a modelling error.",
        "A fill comparison only exists where a live entry landed on the same bar a fresh "
        "backtest also entered on; memory- or risk-vetoed bars have no live fill by "
        "construction, so they cannot and do not count toward the slippage numbers.",
    ])
    verdict = _verdict(pooled, per_symbol)
    return DivergenceReport(champion_id, window, per_symbol, pooled, verdict, caveats)


def _compare_symbol(
    symbol: str,
    realised: Sequence[Trade],
    modelled: Sequence[Trade],
    decisions_by_key: Dict[Tuple[str, int], str],
) -> SymbolDivergence:
    """Match realised and modelled trades bar-for-bar by entry timestamp.

    The rule engine is deterministic given the genome and the candles, so an
    entry the backtest takes and the live agent does not is explained by a
    logged veto or it isn't - there is no third, silent possibility once the
    genome and the data are held fixed.
    """
    div = SymbolDivergence(symbol, realised_trades=len(realised), modelled_trades=len(modelled))
    realised_by_ts = {t.entry_ts: t for t in realised}
    modelled_by_ts = {t.entry_ts: t for t in modelled}

    for ts, live in realised_by_ts.items():
        sim = modelled_by_ts.get(ts)
        if sim is None:
            div.unexplained_live_only += 1
            continue
        div.matched_entries += 1
        div.entry_fills.append(FillComparison(ts, live.entry_price, sim.entry_price))
        div.exit_fills.append(FillComparison(live.exit_ts, live.exit_price, sim.exit_price))

    for ts, sim in modelled_by_ts.items():
        if ts in realised_by_ts:
            continue
        action = decisions_by_key.get((symbol, ts))
        if action == "veto:memory":
            div.memory_declined += 1
        elif action == "veto:risk":
            div.risk_declined += 1
        else:
            div.unexplained_backtest_only += 1

    if realised:
        div.realised_wins = sum(1 for t in realised if t.pnl > 0)
        div.realised_total_pnl = sum(t.pnl for t in realised)
    if modelled:
        div.modelled_wins = sum(1 for t in modelled if t.pnl > 0)
        div.modelled_total_pnl = sum(t.pnl for t in modelled)
    return div


def _pool(divs: Iterable[SymbolDivergence]) -> SymbolDivergence:
    pooled = SymbolDivergence("pooled")
    for d in divs:
        pooled.realised_trades += d.realised_trades
        pooled.modelled_trades += d.modelled_trades
        pooled.realised_wins += d.realised_wins
        pooled.modelled_wins += d.modelled_wins
        pooled.matched_entries += d.matched_entries
        pooled.memory_declined += d.memory_declined
        pooled.risk_declined += d.risk_declined
        pooled.unexplained_backtest_only += d.unexplained_backtest_only
        pooled.unexplained_live_only += d.unexplained_live_only
        pooled.realised_total_pnl += d.realised_total_pnl
        pooled.modelled_total_pnl += d.modelled_total_pnl
        pooled.entry_fills.extend(d.entry_fills)
        pooled.exit_fills.extend(d.exit_fills)
    return pooled


def _verdict(pooled: SymbolDivergence, per_symbol: Dict[str, SymbolDivergence]) -> str:
    """Name the single largest pooled discrepancy.

    Priority order, deliberately: a real fill-model divergence outranks the
    agent having chosen differently, which outranks an unexplained gap. Paper
    fills should track the model almost exactly by construction, so anything
    material there is treated as the more urgent finding; a veto is the
    system working as designed and is reported as such, not as an error.
    """
    if not per_symbol:
        return "no markets with cached candles to compare against."
    if pooled.realised_trades == 0 and pooled.modelled_trades == 0:
        return "the champion has no trades yet in this window, live or modelled - nothing to compare."

    entry_bps = pooled.mean_entry_slippage_bps
    exit_bps = pooled.mean_exit_slippage_bps
    worst_bps = max((abs(b) for b in (entry_bps, exit_bps) if b is not None), default=0.0)

    if worst_bps >= FILL_DIVERGENCE_THRESHOLD_BPS:
        use_entry = abs(entry_bps or 0.0) >= abs(exit_bps or 0.0)
        tag, bps = ("entry", entry_bps) if use_entry else ("exit", exit_bps)
        cost_more = pooled.realised_total_pnl < pooled.modelled_total_pnl
        read = "cost the live book more than the model assumed" if cost_more else \
            "cost the live book less than the model assumed"
        return (
            f"largest discrepancy is the {tag} fill price: live trades {read}, averaging "
            f"{bps:+.1f} bps versus the backtested model across {len(pooled.entry_fills)} "
            "matched trade(s) - the slippage/fee assumptions look mis-calibrated for this "
            "window, which is a modelling problem, not the agent choosing differently."
        )

    veto_total = pooled.memory_declined + pooled.risk_declined
    unexplained_total = pooled.unexplained_backtest_only + pooled.unexplained_live_only

    if veto_total and veto_total >= unexplained_total:
        risk_led = pooled.risk_declined > pooled.memory_declined
        lead = "the risk manager" if risk_led else "memory bias"
        count = pooled.risk_declined if risk_led else pooled.memory_declined
        plural = "y" if count == 1 else "ies"
        return (
            f"largest discrepancy is behavioural: {lead} vetoed {count} entr{plural} the "
            "backtested model would have taken. That is the agent choosing differently from a "
            "pure replay of the genome, on purpose - not evidence the model's assumptions are wrong."
        )

    if unexplained_total:
        return (
            f"{unexplained_total} bar(s) where the live trade log and a fresh backtest of the "
            "champion disagree with no logged veto to explain the gap - worth checking for a "
            "revised candle or a stale cache before trusting either side."
        )

    return "backtested model and live trading agree closely over this window; no material divergence found."
