"""The autonomous agent loop.

One iteration is:

    perceive -> recall -> decide -> risk-check -> act -> record -> (evolve)

Perception is closed candles only. Recall asks Brain 2 what situations like this
one produced. Decision comes from the champion genome. The risk manager holds a
veto. Everything that happens is written to Brain 1, and on a cadence the agent
consolidates its episodes into lessons and runs a generation of evolution
against its own recent history.

The loop is designed to be interruptible at any point: all state lives in the
two brains, so ``Ctrl-C`` and a restart resume mid-position without confusion.
"""

from __future__ import annotations

import logging
import os
import signal
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .brain.memory import DualBrain, MemoryBias
from .config import Config
from .core.types import Candle, Position, Signal, Trade, timeframe_ms
from .data.providers import make_provider
from .evolution.engine import EvolutionEngine, GenerationReport
from .evolution.reflect import make_reflector
from .execution.broker import make_broker
from .execution.risk import RiskManager
from .strategy import rules
from .strategy.genome import Genome

log = logging.getLogger(__name__)

STEP_COUNT_KEY = "agent.steps"
LAST_BAR_KEY = "agent.last_bar_ts"


@dataclass
class StepResult:
    """What the agent decided about one symbol on one bar."""

    ts: int
    price: float
    equity: float
    action: str
    reason: str
    symbol: str = ""
    signal: Optional[Signal] = None
    trade: Optional[Trade] = None
    bias: Optional[MemoryBias] = None
    generation: Optional[GenerationReport] = None
    lessons: List[str] = field(default_factory=list)

    def line(self) -> str:
        market = f"{self.symbol:<9} " if self.symbol else ""
        head = (f"[{_fmt_ts(self.ts)}] {market}{self.action:<14} "
                f"px={self.price:,.2f} eq={self.equity:,.2f}")
        return f"{head}  {self.reason}"


@dataclass
class CycleResult:
    """One pass over the whole universe."""

    ts: int
    equity: float
    results: List[StepResult] = field(default_factory=list)
    generation: Optional[GenerationReport] = None
    lessons: List[str] = field(default_factory=list)

    @property
    def notable(self) -> List[StepResult]:
        return [r for r in self.results if r.action not in ("flat", "hold", "waiting", "no_data")]


class TradingAgent:
    def __init__(
        self,
        cfg: Config,
        brain: Optional[DualBrain] = None,
        provider=None,
        broker=None,
        record_config: bool = True,
    ) -> None:
        cfg.ensure_dirs()
        self.cfg = cfg
        self.brain = brain or DualBrain(cfg)
        self.provider = provider or make_provider(cfg, self.brain.b1)
        self.broker = broker or make_broker(cfg, self.brain.b1)
        self.risk = RiskManager(cfg, self.brain.b1)
        self.engine = EvolutionEngine(cfg, self.brain)
        self.reflector = make_reflector(cfg)
        self._stop = False
        self._champion: Optional[Genome] = None
        # Only a trading agent records what it booted with. An inspection
        # command constructing one must not overwrite the running agent's
        # config with its own defaults - that is how `status` ended up
        # reporting synthetic 1h while a 5m Binance agent was live.
        if record_config:
            self.brain.b1.set_state("agent.config", cfg.to_dict())

    # ------------------------------------------------------------------
    def close(self) -> None:
        self.brain.close()

    def __enter__(self) -> "TradingAgent":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    @property
    def champion(self) -> Genome:
        if self._champion is None:
            self._champion = self.engine.champion()
        return self._champion

    def refresh_champion(self) -> Genome:
        self._champion = self.engine.champion()
        return self._champion

    def _genome_for_position(self, position: Position) -> Genome:
        """Manage an open position with the genome that opened it.

        A promotion mid-trade must not silently change the stop and target of a
        position that was sized under different rules.
        """
        if position.genome_id and position.genome_id != self.champion.id:
            record = self.brain.b1.get_genome(position.genome_id)
            if record:
                return Genome.from_dict(record["genes"], record["generation"], "position_owner")
        return self.champion

    # ------------------------------------------------------------------
    def closed_candles(self, now_ms: Optional[int] = None,
                       symbol: Optional[str] = None) -> List[Candle]:
        """Only fully closed bars. Acting on a forming candle is how a backtest
        that looks profitable turns into a live system that buys wicks."""
        now = now_ms if now_ms is not None else int(time.time() * 1000)
        step = timeframe_ms(self.cfg.timeframe)
        raw = self.provider.fetch_ohlcv(
            symbol or self.cfg.symbol, self.cfg.timeframe, self.cfg.history_bars
        )
        return [c for c in raw if c.ts + step <= now]

    def perceive(self, now_ms: int) -> Dict[str, List[Candle]]:
        """Fetch every symbol before deciding anything.

        Marking the book to market needs all the prices, and a risk check that
        saw only one of them would size the second entry against a stale
        equity figure.
        """
        history: Dict[str, List[Candle]] = {}
        for symbol in self.cfg.symbol_list:
            try:
                candles = self.closed_candles(now_ms, symbol)
            except Exception as exc:  # one bad market must not stop the rest
                log.warning("could not fetch %s: %s", symbol, exc)
                self.brain.b1.log_event("fetch_error", f"{symbol}: {exc}", level="WARNING")
                continue
            if candles:
                history[symbol] = candles
        return history

    # ------------------------------------------------------------------
    def step(self, now_ms: Optional[int] = None) -> StepResult:
        """One decision on the primary symbol - the single-market view."""
        cycle = self.cycle(now_ms)
        for result in cycle.results:
            if result.symbol == self.cfg.symbol:
                return result
        return StepResult(cycle.ts, 0.0, cycle.equity, "no_data",
                          "no closed candles for the primary symbol",
                          symbol=self.cfg.symbol)

    def cycle(self, now_ms: Optional[int] = None) -> CycleResult:
        """Walk the whole universe once: perceive, then decide per symbol."""
        now = now_ms if now_ms is not None else int(time.time() * 1000)
        history = self.perceive(now)
        prices = {sym: candles[-1].close for sym, candles in history.items()}
        equity = self.broker.equity(prices) if prices else self.broker.cash

        if not history:
            return CycleResult(now, equity, [StepResult(
                now, 0.0, equity, "no_data", "no market data available", symbol=self.cfg.symbol)])

        newest_ts = max(candles[-1].ts for candles in history.values())
        self.risk.observe_equity(equity, newest_ts)
        positions = self.brain.b1.load_positions()
        exposure = sum(abs(p.qty) * prices.get(sym, p.entry_price)
                       for sym, p in positions.items())
        self.brain.b1.record_equity(newest_ts, equity, self.broker.cash, exposure)

        if self.brain.b1.get_state(LAST_BAR_KEY) == newest_ts:
            return CycleResult(newest_ts, equity, [StepResult(
                newest_ts, prices.get(self.cfg.symbol, 0.0), equity, "waiting",
                "no new closed bar yet", symbol=self.cfg.symbol)])
        self.brain.b1.set_state(LAST_BAR_KEY, newest_ts)

        steps = int(self.brain.b1.get_state(STEP_COUNT_KEY, 0)) + 1
        self.brain.b1.set_state(STEP_COUNT_KEY, steps)

        results: List[StepResult] = []
        for symbol, candles in history.items():
            if len(candles) < 80:
                results.append(StepResult(
                    candles[-1].ts, candles[-1].close, equity, "no_data",
                    f"only {len(candles)} closed candles available", symbol=symbol))
                continue
            position = positions.get(symbol)
            genome = self._genome_for_position(position) if position else self.champion
            frame = rules.compute_frame(genome, candles)
            i = len(candles) - 1
            signal = rules.signal_at(genome, frame, i)
            if position is not None:
                results.append(self._manage_position(
                    symbol, position, genome, frame, i, signal, equity, prices))
            else:
                open_count = len(self.brain.b1.load_positions())
                results.append(self._consider_entry(
                    symbol, genome, frame, i, signal, equity, open_count,
                    history=history, prices=prices))

        cycle = CycleResult(newest_ts, self.broker.equity(prices), results)
        cycle.lessons = self._maybe_maintenance(steps, history, cycle)
        return cycle

    # ------------------------------------------------------------------
    def _manage_position(
        self, symbol: str, position: Position, genome: Genome, frame: rules.Frame,
        i: int, signal: Signal, equity: float, prices: Optional[Dict[str, float]] = None
    ) -> StepResult:
        candle = frame.candles[i]
        position.bars_held += 1
        position.stop = rules.update_trailing_stop(genome, frame, i, position)
        reason = rules.exit_reason(genome, frame, i, position, signal)

        if not reason:
            self.brain.b1.save_position(symbol, position)
            self.brain.b1.record_decision(
                candle.ts, symbol, "hold", signal, genome.id, executed=False
            )
            return StepResult(
                candle.ts, candle.close, equity, "hold",
                f"holding {position.side} from {position.entry_price:,.2f} "
                f"({position.unrealized_pct(candle.close) * 100:+.2f}%), stop {position.stop or 0:,.2f}",
                symbol=symbol,
                signal=signal,
            )

        exit_price = rules.exit_price_for(reason, position, candle)
        side = "sell" if position.qty > 0 else "buy"
        fill = self.broker.market_order(side, abs(position.qty), exit_price, candle.ts, symbol)
        entry_notional = abs(position.entry_price * position.qty)
        entry_fee = entry_notional * (self.cfg.fee_bps / 10_000.0)
        pnl = (fill.price - position.entry_price) * position.qty - fill.fee - entry_fee
        trade = Trade(
            symbol=symbol,
            side=position.side,
            qty=abs(position.qty),
            entry_ts=position.entry_ts,
            entry_price=position.entry_price,
            exit_ts=candle.ts,
            exit_price=fill.price,
            pnl=pnl,
            pnl_pct=pnl / entry_notional if entry_notional else 0.0,
            fees=fill.fee + entry_fee,
            reason_open=self.brain.b1.get_state(f"agent.open_reason:{symbol}", "") or "",
            reason_close=reason,
            genome_id=position.genome_id or genome.id,
            regime=position.regime,
        )
        self.brain.remember_trade(trade)
        self.brain.b1.save_position(symbol, None)
        marks = dict(prices or {})
        marks[symbol] = candle.close
        equity_after = self.broker.equity(marks)
        self.risk.on_trade_closed(trade, equity_after)
        self.brain.b1.record_decision(
            candle.ts, symbol, f"close:{reason}", signal, genome.id, executed=True
        )
        return StepResult(
            candle.ts, candle.close, equity_after, f"close:{reason}",
            f"closed {trade.side} at {fill.price:,.2f} for {trade.pnl_pct * 100:+.2f}% "
            f"({trade.pnl:+,.2f})",
            symbol=symbol,
            signal=signal,
            trade=trade,
        )

    # ------------------------------------------------------------------
    def _consider_entry(
        self, symbol: str, genome: Genome, frame: rules.Frame, i: int,
        signal: Signal, equity: float, open_positions: int = 0,
        history: Optional[Dict[str, List[Candle]]] = None,
        prices: Optional[Dict[str, float]] = None,
    ) -> StepResult:
        candle = frame.candles[i]
        if signal.direction == 0:
            self.brain.b1.record_decision(
                candle.ts, symbol, "flat", signal, genome.id, executed=False
            )
            return StepResult(candle.ts, candle.close, equity, "flat", signal.reason,
                              symbol=symbol, signal=signal)

        bias = self.brain.advice(symbol, signal)
        if bias.vetoes(signal.direction):
            self.brain.b1.record_decision(
                candle.ts, symbol, "veto:memory", signal, genome.id, executed=False
            )
            note = bias.notes[0] if bias.notes else "similar setups lost money"
            return StepResult(
                candle.ts, candle.close, equity, "veto:memory",
                f"memory vetoed the entry - {note}",
                symbol=symbol, signal=signal, bias=bias,
            )

        entry_hint = candle.close
        stop, take_profit = rules.initial_stops(genome, frame, i, entry_hint, signal.direction)
        decision = self.risk.check_entry(
            equity=equity,
            cash=self.broker.cash,
            price=entry_hint,
            stop=stop,
            signal=signal,
            risk_scale=float(genome.genes["risk_scale"]),
            size_mult=bias.size_mult,
            now_ms=candle.ts,
            symbol=symbol,
            open_positions=open_positions,
            # Five majors move together, so three "diversified" positions can be
            # one leveraged bet on crypto beta. The risk manager needs the price
            # history to see that, and the notional held to know how far in it
            # already is.
            price_history=history,
            holdings=self._notional_held(prices or {}),
        )
        if not decision.approved:
            self.brain.b1.record_decision(
                candle.ts, symbol, "veto:risk", signal, genome.id, executed=False
            )
            return StepResult(
                candle.ts, candle.close, equity, "veto:risk", decision.reason,
                symbol=symbol, signal=signal, bias=bias,
            )

        side = "buy" if signal.direction > 0 else "sell"
        fill = self.broker.market_order(side, decision.qty, entry_hint, candle.ts, symbol)
        stop, take_profit = rules.initial_stops(genome, frame, i, fill.price, signal.direction)
        position = Position(
            symbol=symbol,
            qty=decision.qty * signal.direction,
            entry_price=fill.price,
            entry_ts=candle.ts,
            stop=stop,
            take_profit=take_profit,
            genome_id=genome.id,
            regime=signal.regime,
        )
        self.brain.b1.save_position(symbol, position)
        self.brain.b1.set_state(f"agent.open_reason:{symbol}",
                                f"{signal.reason} | memory {bias.describe()}")
        self.brain.b1.record_decision(
            candle.ts, symbol, f"open:{position.side}", signal, genome.id, executed=True
        )
        return StepResult(
            candle.ts, candle.close, equity, f"open:{position.side}",
            f"opened {position.side} {decision.qty:.6f} at {fill.price:,.2f} "
            f"(stop {stop or 0:,.2f}, target {take_profit or 0:,.2f}; {bias.describe()})",
            symbol=symbol, signal=signal, bias=bias,
        )

    # ------------------------------------------------------------------
    def _maybe_maintenance(
        self, steps: int, history: Dict[str, List[Candle]], cycle: "CycleResult"
    ) -> List[str]:
        """Sleep and dream: consolidate memories, then evolve."""
        lessons: List[str] = []
        if self.cfg.consolidate_every_steps and steps % self.cfg.consolidate_every_steps == 0:
            written = self.brain.consolidate(self.reflector)
            lessons = [l.text for l in written]
        if self.cfg.evolve_every_steps and steps % self.cfg.evolve_every_steps == 0:
            reports = self.engine.evolve(history)
            if reports:
                cycle.generation = reports[-1]
                if any(r.promoted for r in reports):
                    self.refresh_champion()
        return lessons

    # ------------------------------------------------------------------
    def run(self, max_steps: Optional[int] = None, on_step=None) -> List[CycleResult]:
        """Run autonomously until stopped (or ``max_steps`` cycles).

        A cycle is one pass over the whole universe, so ``max_steps`` counts
        polls, not symbols.
        """
        self._install_signal_handlers()
        lock = _acquire_lock(self.cfg)
        self.brain.b1.log_event(
            "start",
            f"agent started in {self.cfg.mode} mode on "
            f"{', '.join(self.cfg.symbol_list)} {self.cfg.timeframe} "
            f"via {getattr(self.provider, 'name', 'provider')}",
            {"config": self.cfg.to_dict()},
        )
        self._reconcile_book()
        cycles: List[CycleResult] = []
        failures = 0
        try:
            while not self._stop and (max_steps is None or len(cycles) < max_steps):
                started = time.time()
                try:
                    cycle = self.cycle()
                    failures = 0
                    cycles.append(cycle)
                    for result in cycle.results:
                        log.info(result.line())
                    if on_step:
                        on_step(cycle)
                except Exception as exc:  # keep the loop alive; record everything
                    failures += 1
                    log.exception("cycle failed: %s", exc)
                    self.brain.b1.log_event("step_error", str(exc), level="ERROR")
                    if failures >= 10:
                        self.brain.b1.log_event(
                            "stop", "10 consecutive failures, stopping", level="ERROR"
                        )
                        break
                    time.sleep(min(300.0, 2.0**failures))
                if max_steps is not None and len(cycles) >= max_steps:
                    break
                elapsed = time.time() - started
                self._sleep(max(0.0, self.cfg.poll_seconds - elapsed))
        finally:
            self.brain.b1.log_event("stop", f"agent stopped after {len(cycles)} cycles")
            _release_lock(lock)
        return cycles

    def _notional_held(self, prices: Dict[str, float]) -> Dict[str, float]:
        """Current exposure per market, in quote currency."""
        return {
            symbol: abs(position.qty) * prices.get(symbol, position.entry_price)
            for symbol, position in self.brain.b1.load_positions().items()
        }

    def _reconcile_book(self) -> None:
        """Trust the exchange over our own records before trading anything.

        A process that died mid-order, or a partial fill, leaves the local book
        disagreeing with reality - and every risk limit downstream is computed
        from that book. Checking once at startup is cheap; discovering the drift
        through a rejected order is not.
        """
        try:
            report = self.broker.reconcile()
        except Exception as exc:  # never let a bookkeeping check stop the agent
            log.warning("could not reconcile the book: %s", exc)
            self.brain.b1.log_event("reconcile_error", str(exc), level="WARNING")
            return
        if getattr(report, "corrected", None):
            log.warning("book corrected against the exchange: %s", report.corrected)

    def _sleep(self, seconds: float) -> None:
        deadline = time.time() + seconds
        while not self._stop and time.time() < deadline:
            time.sleep(min(0.5, max(0.0, deadline - time.time())))

    def _install_signal_handlers(self) -> None:
        def handler(signum, _frame):
            log.info("received signal %s, finishing the current step and stopping", signum)
            self._stop = True

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):  # not the main thread
                pass

    # ------------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        prices: Dict[str, float] = {}
        for symbol in self.cfg.symbol_list:
            rows = self.brain.b1.load_candles(symbol, self.cfg.timeframe, 1)
            if rows:
                prices[symbol] = rows[-1].close
        positions = self.brain.b1.load_positions()
        champion = self.engine.champion_record()
        return {
            "mode": self.cfg.mode,
            "symbols": self.cfg.symbol_list,
            "timeframe": self.cfg.timeframe,
            "provider": getattr(self.provider, "name", "unknown"),
            "broker": getattr(self.broker, "name", "unknown"),
            "prices": prices,
            "cash": self.broker.cash,
            "equity": self.broker.equity(prices) if prices else self.broker.cash,
            "steps": self.brain.b1.get_state(STEP_COUNT_KEY, 0),
            "positions": {
                symbol: {
                    "side": position.side,
                    "qty": position.qty,
                    "entry": position.entry_price,
                    "stop": position.stop,
                    "take_profit": position.take_profit,
                    "unrealized_pct": (
                        position.unrealized_pct(prices[symbol]) if symbol in prices else 0.0
                    ),
                }
                for symbol, position in positions.items()
            },
            "risk": self.risk.snapshot(),
            "champion": (
                {
                    "id": champion["id"],
                    "generation": champion["generation"],
                    "oos_fitness": champion["oos_fitness"],
                    "description": Genome.from_dict(champion["genes"]).describe(),
                }
                if champion
                else None
            ),
            "memory": self.brain.snapshot(),
        }


# ----------------------------------------------------------------------
def _fmt_ts(ts: int) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(ts / 1000)) if ts else "----"


def _acquire_lock(cfg: Config):
    """Refuse to run two agents against one set of brains."""
    path = cfg.lock_path
    if path.exists():
        try:
            pid = int(path.read_text().strip() or 0)
        except ValueError:
            pid = 0
        if pid and _pid_alive(pid):
            raise RuntimeError(f"another agent is already running (pid {pid}); lock at {path}")
    path.write_text(str(os.getpid()))
    return path


def _release_lock(path) -> None:
    try:
        if path and path.exists():
            path.unlink()
    except OSError:  # pragma: no cover - best effort
        pass


def _pid_alive(pid: int) -> bool:
    """Is this PID still running?

    ``os.kill(pid, 0)`` is the POSIX idiom, but on Windows ``os.kill`` calls
    TerminateProcess for any signal other than the console-control ones - it
    would kill whatever process now holds a stale PID from the lockfile rather
    than merely asking about it. Windows gets an OpenProcess probe instead.
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        return _pid_alive_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by someone else
    except OSError:
        return False
    return True


def _pid_alive_windows(pid: int) -> bool:  # pragma: no cover - platform specific
    import ctypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        exit_code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return True  # can't tell; assume alive rather than stomp a live agent
        return exit_code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)
