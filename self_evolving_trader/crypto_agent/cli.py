"""Command line interface.

    python -m crypto_agent demo                 # 250 offline steps, end to end
    python -m crypto_agent run --steps 100      # autonomous loop (paper by default)
    python -m crypto_agent backtest             # champion vs. history
    python -m crypto_agent evolve -g 5          # run generations on demand
    python -m crypto_agent status               # what the agent thinks right now
    python -m crypto_agent memory -q "downtrend high vol long"
    python -m crypto_agent report                # trades, equity, generations
    python -m crypto_agent resume-risk           # clear a drawdown halt
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import os
import sqlite3
import sys
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional

from .agent import TradingAgent
from . import dashboard as dashboard_module
from .config import Config, ENV_PREFIX
from .core.types import fitness_score
from .strategy.backtest import simulate, walk_forward
from .strategy.genome import Genome


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crypto_agent",
        description="Self-evolving autonomous crypto trading agent (paper by default).",
    )
    parser.add_argument("--config", help="path to a JSON config file")
    parser.add_argument("--data-dir", help="where the two brains live")
    parser.add_argument("--symbol", help="e.g. BTC/USDT")
    parser.add_argument("--timeframe", help="1m 5m 15m 1h 4h 1d ...")
    parser.add_argument("--provider", choices=["synthetic", "binance", "ccxt"])
    parser.add_argument("--exchange", help="ccxt exchange id (with --provider ccxt)")
    parser.add_argument("--mode", choices=["paper", "live"])
    parser.add_argument("--seed", type=int)
    parser.add_argument("--log-level", default="INFO")

    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run the autonomous loop")
    run.add_argument("--steps", type=int, help="stop after N iterations (default: forever)")
    run.add_argument("--poll-seconds", type=float)

    demo = sub.add_parser("demo", help="offline end-to-end demonstration on synthetic data")
    demo.add_argument("--steps", type=int, default=250)
    demo.add_argument("--fresh", action="store_true", help="wipe the data dir first")

    bt = sub.add_parser("backtest", help="backtest a genome over stored/fetched history")
    bt.add_argument("--genome-id", help="defaults to the current champion")
    bt.add_argument("--bars", type=int)

    ev = sub.add_parser("evolve", help="run evolution generations now")
    ev.add_argument("-g", "--generations", type=int, default=2)

    sub.add_parser("status", help="print the agent's current state as JSON")

    mem = sub.add_parser("memory", help="search or list Brain 2")
    mem.add_argument("-q", "--query", help="semantic query")
    mem.add_argument("-k", type=int, default=8)
    mem.add_argument("--kind", help="trade | reflection | regime | evolution")

    rep = sub.add_parser("report", help="trades, equity and evolution history")
    rep.add_argument("--limit", type=int, default=15)

    dash = sub.add_parser("dashboard", help="render a visual HTML dashboard of both brains")
    dash.add_argument("-o", "--output", default="dashboard.html",
                      help="file to write (ignored with --serve)")
    dash.add_argument("--serve", action="store_true",
                      help="serve it instead, re-rendering on every request")
    dash.add_argument("--port", type=int, default=8787)
    dash.add_argument("--host", default="127.0.0.1")
    dash.add_argument("--refresh", type=int, default=30,
                      help="browser auto-refresh in seconds (0 disables)")
    dash.add_argument("--open", dest="open_browser", action="store_true",
                      help="open the result in your browser")

    sub.add_parser("resume-risk", help="clear a drawdown halt (operator action)")
    return parser


def config_from_args(args: argparse.Namespace, adopt_stored: bool = False, **extra: Any) -> Config:
    """Resolve the config for this invocation.

    ``adopt_stored`` is for the read-only commands. The agent writes its resolved
    config into Brain 1 on every boot, so ``status`` should describe the agent
    that actually ran rather than silently falling back to defaults and then
    reporting, say, 1h synthetic when a 5m Binance agent is running in the next
    window. Explicit flags and environment variables still win.
    """
    overrides: Dict[str, Any] = {
        "data_dir": args.data_dir,
        "symbol": args.symbol,
        "timeframe": args.timeframe,
        "provider": args.provider,
        "exchange": args.exchange,
        "mode": args.mode,
        "seed": args.seed,
        "log_level": args.log_level,
        **extra,
    }
    explicit = {k: v for k, v in overrides.items() if v is not None}
    if adopt_stored:
        stored = stored_config(explicit.get("data_dir") or Config().data_dir)
        for key, value in stored.items():
            if key not in explicit and f"{ENV_PREFIX}{key.upper()}" not in os.environ:
                explicit[key] = value
    return Config.load(args.config, **explicit)


def stored_config(data_dir: str) -> Dict[str, Any]:
    """The config the agent last booted with, straight out of Brain 1."""
    path = Path(data_dir).expanduser().resolve() / "brain1_episodic.sqlite3"
    if not path.exists():
        return {}
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            row = conn.execute("SELECT value FROM kv WHERE key='agent.config'").fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return {}
    if not row:
        return {}
    try:
        stored = json.loads(row[0])
    except (TypeError, ValueError):
        return {}
    known = {f.name for f in dataclasses.fields(Config)}
    # Never adopt a stored mode: an inspection command must not arm live trading.
    return {k: v for k, v in stored.items() if k in known and k not in ("mode", "log_level")}


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    handler = {
        "run": cmd_run,
        "demo": cmd_demo,
        "backtest": cmd_backtest,
        "evolve": cmd_evolve,
        "status": cmd_status,
        "memory": cmd_memory,
        "report": cmd_report,
        "dashboard": cmd_dashboard,
        "resume-risk": cmd_resume_risk,
    }[args.command]
    return handler(args)


# ----------------------------------------------------------------------
def cmd_run(args: argparse.Namespace) -> int:
    extra: Dict[str, Any] = {}
    if getattr(args, "poll_seconds", None):
        extra["poll_seconds"] = args.poll_seconds
    cfg = config_from_args(args, **extra)
    if cfg.mode == "live":
        print("!! LIVE MODE: real orders will be placed. Ctrl-C now if that is not intended.")
    with TradingAgent(cfg) as agent:
        results = agent.run(max_steps=args.steps, on_step=lambda r: print(r.line()))
    print(f"\n{len(results)} steps completed.")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    import shutil

    cfg = config_from_args(
        args,
        provider="synthetic",
        mode="paper",
        data_dir=args.data_dir or "./agent_data_demo",
        poll_seconds=0.0,
    )
    if args.fresh and cfg.root.exists():
        shutil.rmtree(cfg.root)
    cfg.ensure_dirs()

    print(f"Two brains at {cfg.root}")
    print(f"Market: {cfg.symbol} {cfg.timeframe} (synthetic, seed {cfg.seed})\n")
    with TradingAgent(cfg) as agent:
        clock = _replay_clock(agent, args.steps)
        opened = closed = vetoed = 0
        for now_ms in clock:
            result = agent.step(now_ms=now_ms)
            if result.action.startswith("open"):
                opened += 1
            elif result.action.startswith("close"):
                closed += 1
            elif result.action.startswith("veto"):
                vetoed += 1
            if result.action not in ("flat", "hold", "waiting"):
                print(result.line())
            if result.generation:
                print(f"    evolution: {result.generation.summary()}")
            for lesson in result.lessons[:2]:
                print(f"    learned: {lesson}")
        status = agent.status()

    print("\n--- after the run ---")
    print(f"opened {opened}, closed {closed}, vetoed {vetoed}")
    print(json.dumps(status, indent=2, default=str))
    return 0


def _replay_clock(agent: TradingAgent, steps: int) -> List[int]:
    """Simulated wall-clock timestamps, one closed bar per step.

    The agent is fed the history one bar at a time exactly as it would arrive
    live, which is what makes the offline demo a real test of the loop rather
    than a batch backtest wearing a costume.
    """
    from .core.types import timeframe_ms

    step_ms = timeframe_ms(agent.cfg.timeframe)
    series = agent.provider.fetch_ohlcv(
        agent.cfg.symbol, agent.cfg.timeframe, agent.cfg.history_bars
    )
    if not series:
        return []
    warmup = min(len(series) - 1, 200)
    start = max(warmup, len(series) - steps)
    return [series[min(len(series) - 1, start + n)].ts + step_ms for n in range(steps)]


def cmd_backtest(args: argparse.Namespace) -> int:
    cfg = config_from_args(args, adopt_stored=True)
    with TradingAgent(cfg) as agent:
        if args.genome_id:
            record = agent.brain.b1.get_genome(args.genome_id)
            if not record:
                print(f"no genome {args.genome_id}", file=sys.stderr)
                return 1
            genome = Genome.from_dict(record["genes"], record["generation"])
        else:
            genome = agent.champion
        candles = agent.closed_candles()
        if args.bars:
            candles = candles[-args.bars:]
        print(genome.describe())
        print(f"{len(candles)} candles\n")
        in_sample, out_sample = walk_forward(genome, candles, cfg)
        for label, result in (("in-sample", in_sample), ("out-of-sample", out_sample)):
            m = result.metrics
            print(
                f"{label:>14}: return {m.total_return * 100:+7.2f}%  sharpe {m.sharpe:+6.2f}  "
                f"maxDD {m.max_drawdown * 100:5.2f}%  trades {m.trades:4d}  "
                f"win {m.win_rate * 100:5.1f}%  fitness {fitness_score(m):+.3f}"
            )
        full = simulate(genome, candles, cfg)
        print(f"\nfull history final equity: {full.metrics.final_equity:,.2f} "
              f"from {cfg.start_cash:,.2f}")
    return 0


def cmd_evolve(args: argparse.Namespace) -> int:
    cfg = config_from_args(args)
    with TradingAgent(cfg) as agent:
        candles = agent.closed_candles()
        if len(candles) < 200:
            print(f"need at least 200 candles, have {len(candles)}", file=sys.stderr)
            return 1
        for report in agent.engine.evolve(candles, args.generations):
            print(report.summary())
        agent.refresh_champion()
        print(f"\nchampion: {agent.champion.describe()}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    cfg = config_from_args(args, adopt_stored=True)
    with TradingAgent(cfg) as agent:
        print(json.dumps(agent.status(), indent=2, default=str))
    return 0


def cmd_memory(args: argparse.Namespace) -> int:
    cfg = config_from_args(args, adopt_stored=True)
    with TradingAgent(cfg) as agent:
        cortex = agent.brain.b2
        if args.query:
            recalls = cortex.recall(args.query, k=args.k, kind=args.kind, reinforce=False)
            if not recalls:
                print("nothing relevant remembered yet")
            for r in recalls:
                print(f"[{r.kind:10}] sim {r.similarity:.2f} w {r.weight:.1f} :: {r.text}")
        else:
            print(json.dumps(cortex.stats(), indent=2))
            for r in cortex.latest(limit=args.k, kind=args.kind):
                print(f"[{r.kind:10}] {r.text}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    cfg = config_from_args(args, adopt_stored=True)
    with TradingAgent(cfg) as agent:
        b1 = agent.brain.b1
        stats = b1.trade_stats()
        print(f"trades {stats['trades']:.0f}  net PnL {stats['net_pnl']:+,.2f}  "
              f"win rate {stats['win_rate'] * 100:.1f}%  fees {stats['fees']:,.2f}\n")
        print("recent trades")
        for t in b1.recent_trades(args.limit):
            print(f"  {t.side:<5} {t.pnl_pct * 100:+7.2f}%  {t.regime:<18} "
                  f"open:{t.reason_open[:38]:<38} close:{t.reason_close}")
        print("\nevolution history")
        for g in b1.generation_history(args.limit):
            print(f"  gen {g['id']:>3}  best {g['best_id']}  fitness {g['best_fitness']:+.3f}  "
                  f"mean {g['mean_fitness']:+.3f}")
        curve = b1.equity_curve(limit=5)
        if curve:
            print(f"\nlatest equity {curve[-1]['equity']:,.2f} (cash {curve[-1]['cash']:,.2f})")
        print("\nrecent events")
        for e in b1.recent_events(8):
            print(f"  [{e['level']}] {e['kind']}: {e['message']}")
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    from .brain.memory import DualBrain

    cfg = config_from_args(args, adopt_stored=True)
    if args.serve:
        dashboard_module.serve(cfg, args.host, args.port, args.refresh)
        return 0
    with DualBrain(cfg) as brain:
        path = dashboard_module.write(brain, cfg, args.output, args.refresh)
    print(f"dashboard written to {path}")
    if args.open_browser:
        webbrowser.open(Path(path).as_uri())
    return 0


def cmd_resume_risk(args: argparse.Namespace) -> int:
    cfg = config_from_args(args)
    with TradingAgent(cfg) as agent:
        agent.risk.resume()
        print("risk halt cleared; the agent may open positions again")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
