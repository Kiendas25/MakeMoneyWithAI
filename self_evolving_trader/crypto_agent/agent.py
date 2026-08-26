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
from typing import Any, Dict, List, Optional, Sequence

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
    ts: int
    price: float
    equity: float
    action: str
    reason: str
    signal: Optional[Signal] = None
    trade: Optional[Trade] = None
    bias: Optional[MemoryBias] = None
    generation: Optional[GenerationReport] = None
    lessons: List[str] = field(default_factory=list)

    def line(self) -> str:
        head = f"[{_fmt_ts(self.ts)}] {self.action:<14} px={self.price:,.2f} eq={self.equity:,.2f}"
        return f"{head}  {self.reason}"


class TradingAgent:
    def __init__(
        self,
        cfg: Config,
        brain: Optional[DualBrain] = None,
        provider=None,
        broker=None,
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
    def closed_candles(self, now_ms: Optional[int] = None) -> List[Candle]:
        """Only fully closed bars. Acting on a forming candle is how a backtest
        that looks profitable turns into a live system that buys wicks."""
        now = now_ms if now_ms is not None else int(time.time() * 1000)
        step = timeframe_ms(self.cfg.timeframe)
        raw = self.provider.fetch_ohlcv(self.cfg.symbol, self.cfg.timeframe, self.cfg.history_bars)
        return [c for c in raw if c.ts + step <= now]

    # ------------------------------------------------------------------
    def step(self, now_ms: Optional[int] = None) -> StepResult:
        now = now_ms if now_ms is not None else int(time.time() * 1000)
        candles = self.closed_candles(now)
        if len(candles) < 80:
            return StepResult(now, 0.0, self.broker.cash, "no_data",
                              f"only {len(candles)} closed candles available")

        last = candles[-1]
        price = last.close
        equity = self.broker.equity(price)
        self.risk.observe_equity(equity, last.ts)
        position = self.brain.b1.load_position()
        self.brain.b1.record_equity(
            last.ts, equity, self.broker.cash, abs(position.qty * price) if position else 0.0
        )

        if self.brain.b1.get_state(LAST_BAR_KEY) == last.ts:
            return StepResult(last.ts, price, equity, "waiting", "no new closed bar yet")
        self.brain.b1.set_state(LAST_BAR_KEY, last.ts)

        steps = int(self.brain.b1.get_state(STEP_COUNT_KEY, 0)) + 1
        self.brain.b1.set_state(STEP_COUNT_KEY, steps)

        genome = self._genome_for_position(position) if position else self.champion
        frame = rules.compute_frame(genome, candles)
        i = len(candles) - 1
        signal = rules.signal_at(genome, frame, i)

        result: StepResult
        if position is not None:
            result = self._manage_position(position, genome, frame, i, signal, equity)
        else:
            result = self._consider_entry(genome, frame, i, signal, equity)

        result.lessons = self._maybe_maintenance(steps, candles, result)
        return result

    # ------------------------------------------------------------------
    def _manage_position(
        self, position: Position, genome: Genome, frame: rules.Frame, i: int,
        signal: Signal, equity: float
    ) -> StepResult:
        candle = frame.candles[i]
        position.bars_held += 1
        position.stop = rules.update_trailing_stop(genome, frame, i, position)
        reason = rules.exit_reason(genome, frame, i, position, signal)

        if not reason:
            self.brain.b1.save_position(position)
            self.brain.b1.record_decision(
                candle.ts, self.cfg.symbol, "hold", signal, genome.id, executed=False
            )
            return StepResult(
                candle.ts, candle.close, equity, "hold",
                f"holding {position.side} from {position.entry_price:,.2f} "
                f"({position.unrealized_pct(candle.close) * 100:+.2f}%), stop {position.stop or 0:,.2f}",
                signal=signal,
            )

        exit_price = rules.exit_price_for(reason, position, candle)
        side = "sell" if position.qty > 0 else "buy"
        fill = self.broker.market_order(side, abs(position.qty), exit_price, candle.ts)
        entry_notional = abs(position.entry_price * position.qty)
        entry_fee = entry_notional * (self.cfg.fee_bps / 10_000.0)
        pnl = (fill.price - position.entry_price) * position.qty - fill.fee - entry_fee
        trade = Trade(
            symbol=self.cfg.symbol,
            side=position.side,
            qty=abs(position.qty),
            entry_ts=position.entry_ts,
            entry_price=position.entry_price,
            exit_ts=candle.ts,
            exit_price=fill.price,
            pnl=pnl,
            pnl_pct=pnl / entry_notional if entry_notional else 0.0,
            fees=fill.fee + entry_fee,
            reason_open=self.brain.b1.get_state("agent.open_reason", "") or "",
            reason_close=reason,
            genome_id=position.genome_id or genome.id,
            regime=position.regime,
        )
        self.brain.remember_trade(trade)
        self.brain.b1.save_position(None)
        equity_after = self.broker.equity(candle.close)
        self.risk.on_trade_closed(trade, equity_after)
        self.brain.b1.record_decision(
            candle.ts, self.cfg.symbol, f"close:{reason}", signal, genome.id, executed=True
        )
        return StepResult(
            candle.ts, candle.close, equity_after, f"close:{reason}",
            f"closed {trade.side} at {fill.price:,.2f} for {trade.pnl_pct * 100:+.2f}% "
            f"({trade.pnl:+,.2f})",
            signal=signal,
            trade=trade,
        )

    # ------------------------------------------------------------------
    def _consider_entry(
        self, genome: Genome, frame: rules.Frame, i: int, signal: Signal, equity: float
    ) -> StepResult:
        candle = frame.candles[i]
        if signal.direction == 0:
            self.brain.b1.record_decision(
                candle.ts, self.cfg.symbol, "flat", signal, genome.id, executed=False
            )
            return StepResult(candle.ts, candle.close, equity, "flat", signal.reason, signal=signal)

        bias = self.brain.advice(self.cfg.symbol, signal)
        if bias.vetoes(signal.direction):
            self.brain.b1.record_decision(
                candle.ts, self.cfg.symbol, "veto:memory", signal, genome.id, executed=False
            )
            note = bias.notes[0] if bias.notes else "similar setups lost money"
            return StepResult(
                candle.ts, candle.close, equity, "veto:memory",
                f"memory vetoed the entry - {note}", signal=signal, bias=bias,
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
        )
        if not decision.approved:
            self.brain.b1.record_decision(
                candle.ts, self.cfg.symbol, "veto:risk", signal, genome.id, executed=False
            )
            return StepResult(
                candle.ts, candle.close, equity, "veto:risk", decision.reason,
                signal=signal, bias=bias,
            )

        side = "buy" if signal.direction > 0 else "sell"
        fill = self.broker.market_order(side, decision.qty, entry_hint, candle.ts)
        stop, take_profit = rules.initial_stops(genome, frame, i, fill.price, signal.direction)
        position = Position(
            symbol=self.cfg.symbol,
            qty=decision.qty * signal.direction,
            entry_price=fill.price,
            entry_ts=candle.ts,
            stop=stop,
            take_profit=take_profit,
            genome_id=genome.id,
            regime=signal.regime,
        )
        self.brain.b1.save_position(position)
        self.brain.b1.set_state("agent.open_reason", f"{signal.reason} | memory {bias.describe()}")
        self.brain.b1.record_decision(
            candle.ts, self.cfg.symbol, f"open:{position.side}", signal, genome.id, executed=True
        )
        return StepResult(
            candle.ts, candle.close, self.broker.equity(candle.close), f"open:{position.side}",
            f"opened {position.side} {decision.qty:.6f} at {fill.price:,.2f} "
            f"(stop {stop or 0:,.2f}, target {take_profit or 0:,.2f}; {bias.describe()})",
            signal=signal, bias=bias,
        )

    # ------------------------------------------------------------------
    def _maybe_maintenance(
        self, steps: int, candles: Sequence[Candle], result: StepResult
    ) -> List[str]:
        """Sleep and dream: consolidate memories, then evolve."""
        lessons: List[str] = []
        if self.cfg.consolidate_every_steps and steps % self.cfg.consolidate_every_steps == 0:
            written = self.brain.consolidate(self.reflector)
            lessons = [l.text for l in written]
        if self.cfg.evolve_every_steps and steps % self.cfg.evolve_every_steps == 0:
            reports = self.engine.evolve(candles)
            if reports:
                result.generation = reports[-1]
                if any(r.promoted for r in reports):
                    self.refresh_champion()
        return lessons

    # ------------------------------------------------------------------
    def run(self, max_steps: Optional[int] = None, on_step=None) -> List[StepResult]:
        """Run autonomously until stopped (or ``max_steps`` iterations)."""
        self._install_signal_handlers()
        lock = _acquire_lock(self.cfg)
        self.brain.b1.log_event(
            "start",
            f"agent started in {self.cfg.mode} mode on {self.cfg.symbol} {self.cfg.timeframe} "
            f"via {getattr(self.provider, 'name', 'provider')}",
            {"config": self.cfg.to_dict()},
        )
        results: List[StepResult] = []
        failures = 0
        try:
            while not self._stop and (max_steps is None or len(results) < max_steps):
                started = time.time()
                try:
                    result = self.step()
                    failures = 0
                    results.append(result)
                    log.info(result.line())
                    if on_step:
                        on_step(result)
                except Exception as exc:  # keep the loop alive; record everything
                    failures += 1
                    log.exception("step failed: %s", exc)
                    self.brain.b1.log_event("step_error", str(exc), level="ERROR")
                    if failures >= 10:
                        self.brain.b1.log_event(
                            "stop", "10 consecutive step failures, stopping", level="ERROR"
                        )
                        break
                    time.sleep(min(300.0, 2.0**failures))
                if max_steps is not None and len(results) >= max_steps:
                    break
                elapsed = time.time() - started
                self._sleep(max(0.0, self.cfg.poll_seconds - elapsed))
        finally:
            self.brain.b1.log_event("stop", f"agent stopped after {len(results)} steps")
            _release_lock(lock)
        return results

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
        candles = self.brain.b1.load_candles(self.cfg.symbol, self.cfg.timeframe, 1)
        price = candles[-1].close if candles else 0.0
        position = self.brain.b1.load_position()
        champion = self.engine.champion_record()
        return {
            "mode": self.cfg.mode,
            "symbol": self.cfg.symbol,
            "timeframe": self.cfg.timeframe,
            "provider": getattr(self.provider, "name", "unknown"),
            "broker": getattr(self.broker, "name", "unknown"),
            "price": price,
            "cash": self.broker.cash,
            "equity": self.broker.equity(price) if price else self.broker.cash,
            "steps": self.brain.b1.get_state(STEP_COUNT_KEY, 0),
            "position": (
                {
                    "side": position.side,
                    "qty": position.qty,
                    "entry": position.entry_price,
                    "stop": position.stop,
                    "take_profit": position.take_profit,
                    "unrealized_pct": position.unrealized_pct(price) if price else 0.0,
                }
                if position
                else None
            ),
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
