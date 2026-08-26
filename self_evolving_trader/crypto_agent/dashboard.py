"""A visual dashboard rendered straight out of the two brains.

Produces one self-contained HTML file - no server required, no CDN, no
JavaScript libraries, no dependencies. Charts are inline SVG generated here in
plain Python, so the file opens in any browser and keeps working offline, on a
plane, five years from now.

Everything shown is read from Brain 1 and Brain 2; the dashboard has no state of
its own and never touches the exchange, which means it is safe to render while
the agent is running.
"""

from __future__ import annotations

import html
import json
import time
from dataclasses import dataclass
from string import Template
from typing import Any, Dict, Optional, Sequence

from .brain.memory import DualBrain
from .config import Config
from .core.types import Candle
from .strategy.genome import Genome

PALETTE = {
    "up": "#12a150",
    "down": "#e5484d",
    "accent": "#4c7fff",
    "muted": "#8b93a7",
}


# ----------------------------------------------------------------------
# Chart primitives
# ----------------------------------------------------------------------
@dataclass
class Box:
    width: float = 900.0
    height: float = 240.0
    pad_left: float = 56.0
    pad_right: float = 12.0
    pad_top: float = 12.0
    pad_bottom: float = 22.0

    @property
    def inner_w(self) -> float:
        return self.width - self.pad_left - self.pad_right

    @property
    def inner_h(self) -> float:
        return self.height - self.pad_top - self.pad_bottom


def _scale(value: float, lo: float, hi: float, out_lo: float, out_hi: float) -> float:
    if hi <= lo:
        return (out_lo + out_hi) / 2.0
    return out_lo + (value - lo) / (hi - lo) * (out_hi - out_lo)


def _fmt(value: float) -> str:
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    if abs(value) >= 1:
        return f"{value:,.2f}"
    return f"{value:.4f}"


def _empty_chart(box: Box, message: str) -> str:
    return (
        f'<svg viewBox="0 0 {box.width:.0f} {box.height:.0f}" class="chart" '
        f'preserveAspectRatio="xMidYMid meet" role="img">'
        f'<text x="{box.width / 2:.0f}" y="{box.height / 2:.0f}" class="svg-empty" '
        f'text-anchor="middle">{html.escape(message)}</text></svg>'
    )


def line_chart(values: Sequence[float], box: Optional[Box] = None,
               baseline: Optional[float] = None, label: str = "") -> str:
    """Equity-curve style area chart with a reference line."""
    box = box or Box()
    if len(values) < 2:
        return _empty_chart(box, "not enough history yet")

    lo, hi = min(values), max(values)
    if baseline is not None:
        lo, hi = min(lo, baseline), max(hi, baseline)
    span = (hi - lo) or max(1e-9, abs(hi) * 0.01)
    lo, hi = lo - span * 0.08, hi + span * 0.08

    step = box.inner_w / (len(values) - 1)
    points = [
        (box.pad_left + i * step,
         box.pad_top + box.inner_h - _scale(v, lo, hi, 0.0, box.inner_h))
        for i, v in enumerate(values)
    ]
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(points))
    area = (
        f"M{points[0][0]:.1f},{box.pad_top + box.inner_h:.1f} "
        + " ".join(f"L{x:.1f},{y:.1f}" for x, y in points)
        + f" L{points[-1][0]:.1f},{box.pad_top + box.inner_h:.1f} Z"
    )
    rising = values[-1] >= values[0]
    color = PALETTE["up"] if rising else PALETTE["down"]

    parts = [
        f'<svg viewBox="0 0 {box.width:.0f} {box.height:.0f}" class="chart" '
        f'preserveAspectRatio="none" role="img" aria-label="{html.escape(label or "chart")}">',
        f'<path d="{area}" fill="{color}" opacity="0.12"/>',
        f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linejoin="round" stroke-linecap="round"/>',
    ]
    if baseline is not None:
        y = box.pad_top + box.inner_h - _scale(baseline, lo, hi, 0.0, box.inner_h)
        parts.append(
            f'<line x1="{box.pad_left:.1f}" y1="{y:.1f}" '
            f'x2="{box.width - box.pad_right:.1f}" y2="{y:.1f}" '
            f'class="svg-baseline" stroke-dasharray="4 4"/>'
        )
    for value, y in ((hi, box.pad_top + 4), (lo, box.pad_top + box.inner_h)):
        parts.append(f'<text x="4" y="{y:.1f}" class="svg-axis">{_fmt(value)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def candle_chart(candles: Sequence[Candle], trades: Sequence[Any],
                 box: Optional[Box] = None) -> str:
    """Price candles with entry/exit markers for the trades that fit the window."""
    box = box or Box(height=300.0)
    if len(candles) < 2:
        return _empty_chart(box, "waiting for candles")

    lo = min(c.low for c in candles)
    hi = max(c.high for c in candles)
    pad = (hi - lo) * 0.05 or 1.0
    lo, hi = lo - pad, hi + pad
    slot = box.inner_w / len(candles)
    body = max(1.0, min(9.0, slot * 0.62))

    def y_of(price: float) -> float:
        return box.pad_top + box.inner_h - _scale(price, lo, hi, 0.0, box.inner_h)

    def x_of(index: int) -> float:
        return box.pad_left + slot * (index + 0.5)

    parts = [
        f'<svg viewBox="0 0 {box.width:.0f} {box.height:.0f}" class="chart" '
        f'preserveAspectRatio="none" role="img" aria-label="price with trades">'
    ]
    for i, c in enumerate(candles):
        x = x_of(i)
        color = PALETTE["up"] if c.close >= c.open else PALETTE["down"]
        top, bottom = y_of(max(c.open, c.close)), y_of(min(c.open, c.close))
        parts.append(
            f'<line x1="{x:.1f}" y1="{y_of(c.high):.1f}" x2="{x:.1f}" '
            f'y2="{y_of(c.low):.1f}" stroke="{color}" stroke-width="1" opacity="0.75"/>'
            f'<rect x="{x - body / 2:.1f}" y="{top:.1f}" width="{body:.1f}" '
            f'height="{max(1.0, bottom - top):.1f}" fill="{color}" opacity="0.9"/>'
        )

    index_of_ts = {c.ts: i for i, c in enumerate(candles)}
    for trade in trades:
        for ts, price, marker in (
            (trade.entry_ts, trade.entry_price, "entry"),
            (trade.exit_ts, trade.exit_price, "exit"),
        ):
            i = index_of_ts.get(ts)
            if i is None:
                continue
            x, y = x_of(i), y_of(price)
            if marker == "entry":
                colour = PALETTE["accent"]
                parts.append(
                    f'<polygon points="{x:.1f},{y - 7:.1f} {x - 5:.1f},{y + 3:.1f} '
                    f'{x + 5:.1f},{y + 3:.1f}" fill="{colour}"/>'
                )
            else:
                colour = PALETTE["up"] if trade.pnl > 0 else PALETTE["down"]
                parts.append(
                    f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="none" '
                    f'stroke="{colour}" stroke-width="2"/>'
                )
    for value, y in ((hi, box.pad_top + 4), (lo, box.pad_top + box.inner_h)):
        parts.append(f'<text x="4" y="{y:.1f}" class="svg-axis">{_fmt(value)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def fitness_chart(generations: Sequence[Dict[str, Any]], box: Optional[Box] = None) -> str:
    """Best and mean fitness per generation - the shape of the search itself."""
    box = box or Box(height=200.0)
    if len(generations) < 2:
        return _empty_chart(box, "evolution has not run enough generations yet")

    best = [float(g["best_fitness"]) for g in generations]
    mean = [float(g["mean_fitness"]) for g in generations]
    lo, hi = min(min(best), min(mean)), max(max(best), max(mean))
    pad = (hi - lo) * 0.1 or 0.5
    lo, hi = lo - pad, hi + pad
    step = box.inner_w / (len(generations) - 1)

    def series(values: Sequence[float]) -> str:
        return " ".join(
            f"{'M' if i == 0 else 'L'}{box.pad_left + i * step:.1f},"
            f"{box.pad_top + box.inner_h - _scale(v, lo, hi, 0.0, box.inner_h):.1f}"
            for i, v in enumerate(values)
        )

    return (
        f'<svg viewBox="0 0 {box.width:.0f} {box.height:.0f}" class="chart" '
        f'preserveAspectRatio="none" role="img" aria-label="fitness per generation">'
        f'<path d="{series(mean)}" fill="none" stroke="{PALETTE["muted"]}" '
        f'stroke-width="1.5" stroke-dasharray="5 4"/>'
        f'<path d="{series(best)}" fill="none" stroke="{PALETTE["accent"]}" stroke-width="2"/>'
        f'<text x="4" y="{box.pad_top + 4:.0f}" class="svg-axis">{_fmt(hi)}</text>'
        f'<text x="4" y="{box.pad_top + box.inner_h:.0f}" class="svg-axis">{_fmt(lo)}</text>'
        f"</svg>"
    )


# ----------------------------------------------------------------------
# Page
# ----------------------------------------------------------------------
def _stat(label: str, value: str, tone: str = "") -> str:
    cls = f"stat {tone}".strip()
    return (
        f'<div class="{cls}"><span class="stat-label">{html.escape(label)}</span>'
        f'<span class="stat-value">{html.escape(value)}</span></div>'
    )


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]], empty: str) -> str:
    if not rows:
        return f'<p class="empty">{html.escape(empty)}</p>'
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows
    )
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _market_charts(by_symbol, prices, trades) -> str:
    """One price card per market, each showing only its own trades."""
    if not by_symbol:
        return ('<section class="card full"><h2>Price and trades</h2>'
                f'{_empty_chart(Box(height=300.0), "waiting for candles")}</section>')
    cards = []
    for symbol, rows in by_symbol.items():
        own = [t for t in trades if t.symbol == symbol]
        last = prices.get(symbol, 0.0)
        cards.append(
            '<section class="card full">'
            f"<h2>{html.escape(symbol)} &middot; {last:,.2f}</h2>"
            f"{candle_chart(rows, own)}"
            '<div class="legend"><span>&#9650; entry</span>'
            "<span>&#9675; exit (green = win, red = loss)</span>"
            f"<span>{len(own)} closed trade(s) in view</span></div></section>"
        )
    return "".join(cards)


def _pct(value: float) -> str:
    tone = "pos" if value > 0 else "neg" if value < 0 else ""
    return f'<span class="{tone}">{value * 100:+.2f}%</span>'


def _ts(ms: int) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(ms / 1000)) if ms else "-"


def render(brain: DualBrain, cfg: Config, refresh_seconds: int = 0,
           candle_limit: int = 220) -> str:
    b1 = brain.b1
    universe = cfg.symbol_list
    by_symbol = {
        symbol: b1.load_candles(symbol, cfg.timeframe, candle_limit) for symbol in universe
    }
    by_symbol = {symbol: rows for symbol, rows in by_symbol.items() if rows}
    prices = {symbol: rows[-1].close for symbol, rows in by_symbol.items()}
    equity_rows = b1.equity_curve(limit=1500)
    equity = [float(r["equity"]) for r in equity_rows]
    trades = b1.recent_trades(60)
    decisions = b1.recent_decisions(25)
    generations = b1.generation_history(60)
    champion = b1.champion()
    positions = b1.load_positions()
    stats = b1.trade_stats()
    risk = b1.get_state("risk.state") or {}
    memories = brain.b2.latest(limit=25)
    b2_stats = brain.b2.stats()

    current_equity = equity[-1] if equity else cfg.start_cash
    pnl_pct = current_equity / cfg.start_cash - 1.0 if cfg.start_cash else 0.0
    peak = float(risk.get("peak_equity") or current_equity)
    drawdown = (peak - current_equity) / peak if peak > 0 else 0.0

    halted = bool(risk.get("halted"))
    cached = sum(len(rows) for rows in by_symbol.values())
    status_line = (
        f"HALTED - {risk.get('halt_reason', '')}" if halted
        else f"{cfg.mode} mode - {cfg.provider} - {len(by_symbol)}/{len(universe)} markets, "
             f"{cached} candles cached"
    )

    stats_html = "".join([
        _stat("Equity", f"{current_equity:,.2f}"),
        _stat("Return", f"{pnl_pct * 100:+.2f}%", "pos" if pnl_pct > 0 else "neg" if pnl_pct else ""),
        _stat("Markets", f"{len(by_symbol)}/{len(universe)}"),
        _stat("Open positions", f"{len(positions)}"),
        _stat("Drawdown", f"{drawdown * 100:.2f}%", "neg" if drawdown > 0.05 else ""),
        _stat("Closed trades", f"{stats['trades']:.0f}"),
        _stat("Win rate", f"{stats['win_rate'] * 100:.0f}%"),
        _stat("Fees paid", f"{stats['fees']:,.2f}"),
        _stat("Generations", f"{b1.last_generation()}"),
        _stat("Memories", f"{b2_stats['total']}"),
        _stat("Steps", f"{b1.get_state('agent.steps', 0)}"),
    ])

    if positions:
        pos_html = "".join(
            f'<div class="position {"long" if p.qty > 0 else "short"}">'
            f"<strong>{html.escape(p.side.upper())} {abs(p.qty):.6f} "
            f"{html.escape(symbol)}</strong> from {p.entry_price:,.2f} "
            f"&middot; now "
            f"{_pct(p.unrealized_pct(prices[symbol])) if symbol in prices else '-'} "
            f"&middot; stop {p.stop or 0:,.2f} &middot; target "
            f"{p.take_profit or 0:,.2f} &middot; {p.bars_held} bars held</div>"
            for symbol, p in sorted(positions.items())
        )
    else:
        pos_html = '<div class="position flat">No open position</div>'

    champion_html = (
        f'<p class="genome">{html.escape(Genome.from_dict(champion["genes"]).describe())}</p>'
        f'<p class="muted">out-of-sample fitness {champion["oos_fitness"]:+.3f} '
        f'&middot; in-sample {champion["fitness"]:+.3f} &middot; generation {champion["generation"]}</p>'
        if champion else '<p class="empty">no champion yet</p>'
    )

    trade_rows = [
        [
            _ts(t.exit_ts),
            html.escape(t.side),
            _pct(t.pnl_pct),
            f"{t.pnl:+,.2f}",
            html.escape(t.regime),
            html.escape(t.reason_close),
            f'<span class="muted">{html.escape(t.reason_open[:70])}</span>',
        ]
        for t in trades[:25]
    ]
    decision_rows = [
        [
            _ts(int(d["ts"])),
            html.escape(str(d["action"])),
            f'{float(d["score"]):+.2f}',
            html.escape(str(d["regime"])),
            f'<span class="muted">{html.escape(str(d["reason"])[:90])}</span>',
        ]
        for d in decisions
    ]
    memory_rows = [
        [
            f'<span class="tag {html.escape(m.kind)}">{html.escape(m.kind)}</span>',
            f"{m.weight:.1f}",
            html.escape(m.text),
        ]
        for m in memories
    ]
    event_rows = [
        [
            _ts(int(e["ts"])),
            html.escape(str(e["level"])),
            html.escape(str(e["kind"])),
            html.escape(str(e["message"])[:160]),
        ]
        for e in b1.recent_events(15)
    ]

    refresh_tag = (
        f'<meta http-equiv="refresh" content="{int(refresh_seconds)}">'
        if refresh_seconds > 0 else ""
    )

    heading = universe[0] if len(universe) == 1 else f"{len(universe)} markets"
    return _TEMPLATE.substitute(
        title=html.escape(f"{heading} {cfg.timeframe} - trading agent"),
        refresh=refresh_tag,
        symbol=html.escape(", ".join(universe)),
        timeframe=html.escape(cfg.timeframe),
        status_class="halted" if halted else "live",
        status=html.escape(status_line),
        generated=_ts(int(time.time() * 1000)),
        stats=stats_html,
        position=pos_html,
        equity_chart=line_chart(equity, Box(height=220.0), baseline=cfg.start_cash, label="equity"),
        price_charts=_market_charts(by_symbol, prices, trades),
        fitness_chart=fitness_chart(generations),
        champion=champion_html,
        trades=_table(
            ["closed", "side", "pnl %", "pnl", "regime", "exit", "entry reason"],
            trade_rows, "no closed trades yet"),
        decisions=_table(
            ["bar", "action", "score", "regime", "reason"],
            decision_rows, "no decisions recorded yet"),
        memories=_table(["kind", "weight", "lesson"], memory_rows,
                        "Brain 2 is still empty - lessons appear after the first trades"),
        events=_table(["time", "level", "kind", "message"], event_rows, "no events"),
        memory_summary=html.escape(json.dumps(b2_stats.get("by_kind", {}), sort_keys=True)),
    )


_TEMPLATE = Template("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
$refresh
<title>$title</title>
<style>
  :root {
    --bg: #f6f7f9; --panel: #ffffff; --ink: #16181d; --muted: #6b7280;
    --line: #e3e6ec; --accent: #4c7fff; --pos: #12a150; --neg: #e5484d;
    --shadow: 0 1px 2px rgba(16,24,40,.06), 0 8px 24px rgba(16,24,40,.05);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0e1014; --panel: #161a21; --ink: #e8eaee; --muted: #9aa3b2;
      --line: #262c36; --shadow: none;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 24px; background: var(--bg); color: var(--ink);
    font: 14px/1.5 ui-sans-serif, -apple-system, "Segoe UI", Roboto, sans-serif;
  }
  .wrap { max-width: 1180px; margin: 0 auto; }
  header { display: flex; flex-wrap: wrap; gap: 12px; align-items: baseline;
           justify-content: space-between; margin-bottom: 18px; }
  h1 { font-size: 20px; margin: 0; letter-spacing: -.01em; }
  h2 { font-size: 14px; margin: 0 0 12px; text-transform: uppercase;
       letter-spacing: .08em; color: var(--muted); }
  .badge { padding: 3px 10px; border-radius: 999px; font-size: 12px;
           border: 1px solid var(--line); }
  .badge.live { color: var(--pos); border-color: color-mix(in srgb, var(--pos) 40%, transparent); }
  .badge.halted { color: var(--neg); border-color: color-mix(in srgb, var(--neg) 40%, transparent); }
  .grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
  .card { background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
          padding: 16px; box-shadow: var(--shadow); }
  .card.full { grid-column: 1 / -1; }
  .stats { display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); }
  .stat { border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; }
  .stat-label { display: block; font-size: 11px; text-transform: uppercase;
                letter-spacing: .06em; color: var(--muted); }
  .stat-value { display: block; font-size: 18px; font-variant-numeric: tabular-nums;
                margin-top: 2px; }
  .stat.pos .stat-value { color: var(--pos); } .stat.neg .stat-value { color: var(--neg); }
  .position { margin-top: 12px; padding: 10px 12px; border-radius: 10px;
              border: 1px dashed var(--line); font-variant-numeric: tabular-nums; }
  .position.long { border-color: color-mix(in srgb, var(--pos) 45%, transparent); }
  .position.short { border-color: color-mix(in srgb, var(--neg) 45%, transparent); }
  .chart { width: 100%; height: auto; display: block; }
  .svg-axis { fill: var(--muted); font-size: 10px; }
  .svg-empty { fill: var(--muted); font-size: 12px; }
  .svg-baseline { stroke: var(--muted); opacity: .5; }
  .scroll { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; font-weight: 600; color: var(--muted); font-size: 11px;
       text-transform: uppercase; letter-spacing: .05em; padding: 6px 10px 6px 0;
       border-bottom: 1px solid var(--line); white-space: nowrap; }
  td { padding: 7px 10px 7px 0; border-bottom: 1px solid var(--line);
       vertical-align: top; font-variant-numeric: tabular-nums; }
  tr:last-child td { border-bottom: none; }
  .muted, .empty { color: var(--muted); }
  .empty { margin: 0; font-style: italic; }
  .pos { color: var(--pos); } .neg { color: var(--neg); }
  .genome { margin: 0 0 6px; font-family: ui-monospace, "Cascadia Code", Menlo, monospace;
            font-size: 12.5px; }
  .tag { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 11px;
         border: 1px solid var(--line); color: var(--muted); white-space: nowrap; }
  .legend { display: flex; gap: 16px; flex-wrap: wrap; font-size: 12px;
            color: var(--muted); margin-top: 10px; }
  footer { margin-top: 20px; color: var(--muted); font-size: 12px; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>$symbol &middot; $timeframe</h1>
    <span class="badge $status_class">$status</span>
  </header>

  <div class="grid">
    <section class="card full">
      <h2>Position &amp; performance</h2>
      <div class="stats">$stats</div>
      $position
    </section>

    <section class="card full">
      <h2>Equity curve</h2>
      $equity_chart
      <div class="legend"><span>dashed line = starting capital</span></div>
    </section>

    $price_charts

    <section class="card">
      <h2>Evolution</h2>
      $fitness_chart
      <div class="legend"><span>solid = best fitness</span><span>dashed = population mean</span></div>
      <h2 style="margin-top:16px">Current champion</h2>
      $champion
    </section>

    <section class="card">
      <h2>Brain 2 &middot; lessons</h2>
      <p class="muted">$memory_summary</p>
      $memories
    </section>

    <section class="card full">
      <h2>Closed trades</h2>
      $trades
    </section>

    <section class="card full">
      <h2>Recent decisions</h2>
      $decisions
    </section>

    <section class="card full">
      <h2>Event log</h2>
      $events
    </section>
  </div>

  <footer>Rendered $generated UTC from Brain 1 and Brain 2. Paper results are
  simulated; nothing here is financial advice.</footer>
</div>
</body>
</html>
""")


def write(brain: DualBrain, cfg: Config, path: str, refresh_seconds: int = 0) -> str:
    from pathlib import Path

    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(brain, cfg, refresh_seconds), encoding="utf-8")
    return str(target)


def serve(cfg: Config, host: str, port: int, refresh_seconds: int,
          open_browser: bool = False) -> None:
    """Serve a freshly rendered dashboard on every request.

    Re-reading the brains per request means the page always reflects the running
    agent, and the two processes never share anything but SQLite.
    """
    import threading
    import webbrowser
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib naming
            if self.path not in ("/", "/index.html"):
                self.send_error(404)
                return
            with DualBrain(cfg) as brain:
                page = render(brain, cfg, refresh_seconds).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(page)

        def log_message(self, *args):  # keep the console for the agent's own output
            pass

    server = _bind(ThreadingHTTPServer, host, port, Handler)
    actual_port = server.server_address[1]
    url = f"http://{host}:{actual_port}/"
    print(f"dashboard on {url}  (Ctrl-C to stop)")
    if open_browser:
        # The server has to be accepting connections before the browser asks.
        threading.Timer(0.4, webbrowser.open, [url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()


def _bind(server_cls, host: str, port: int, handler):
    """Bind the requested port, or fall back to any free one.

    Windows reserves whole TCP port ranges for Hyper-V, WSL and Docker, and
    binding inside one fails with WinError 10013 (a PermissionError) even though
    nothing is listening there. Refusing to start over that would be unhelpful
    when the OS is perfectly willing to hand out a different port.
    """
    try:
        return server_cls((host, port), handler)
    except (PermissionError, OSError) as exc:
        if port == 0:
            raise
        print(f"port {port} is not available ({exc.__class__.__name__}: {exc}); "
              "asking the OS for a free port instead")
        return server_cls((host, 0), handler)
