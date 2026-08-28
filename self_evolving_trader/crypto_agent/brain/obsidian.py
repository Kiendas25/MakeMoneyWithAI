"""Export both brains into an Obsidian vault a human can read and annotate.

The two SQLite files stay the single source of truth. This module only ever
*writes* markdown mirrors of them, so a corrupted or hand-edited vault can never
feed bad state back into the agent - the worst case is a stale note.

The point is asymmetric: the agent thinks in vectors and rows, a person thinks
in linked prose. Brain 2 already stores lessons in English; put them in a vault
and the graph view shows which markets a lesson touches, search finds the note
about the regime that keeps losing money, and a trader can write their own
disagreement *next to* the agent's conclusion.

Two properties make that annotation safe:

* **Idempotent.** Everything from the start of the file down to
  ``<!-- agent:end generated -->`` is ours; everything after it is yours.
  Re-exporting unchanged data produces a byte-identical region and the file is
  then left untouched rather than rewritten, so mtimes - and Obsidian's own
  sync - stay quiet when nothing happened.
* **Human text survives.** Whatever follows the marker is copied through
  verbatim. A file with no marker at all was written by a person, not by us,
  so the generated block is *prepended* and their text kept below it: silently
  overwriting someone's note is the one unrecoverable mistake an exporter can
  make.

The region starts at byte zero rather than at an opening marker because
Obsidian only parses YAML frontmatter when the ``---`` is the very first line
of the file. A leading ``<!-- ... -->`` would cost every note its properties.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from ..config import Config
from ..core.types import Trade

END = "<!-- agent:end generated -->"
SCAFFOLD = "\n## My notes\n\n"  # the empty invitation a fresh note ends with

# Windows forbids these outright; the rest are reserved by Obsidian's own
# link syntax or make shell quoting miserable.
_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f\[\]#^]')
_RESERVED_WIN = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}
_MAX_STEM = 64


@dataclass
class ExportReport:
    """What one export actually did to the vault."""

    vault: Path
    written: int = 0  # generated region created or changed
    skipped: int = 0  # already identical, left alone
    preserved: int = 0  # files carrying human text we copied through
    appended: int = 0  # human-authored files we appended a block to
    paths: List[Path] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"{self.written} written, {self.skipped} unchanged, "
            f"{self.preserved} with notes preserved, {self.appended} appended "
            f"-> {self.vault}"
        )


# ----------------------------------------------------------------------
def safe_name(raw: str, fallback: str = "unnamed") -> str:
    """Turn a symbol or lesson title into a filename safe everywhere.

    ``BTC/USDT`` becomes ``BTC-USDT``. Windows is the binding constraint: it
    rejects ``<>:"/\\|?*``, trailing dots and spaces, and the DOS device names
    (``CON``, ``NUL``, ``COM1``...) even with an extension. Obsidian adds
    ``[]#^`` to the list because they are link syntax.
    """
    text = _UNSAFE.sub("-", str(raw).strip())
    text = re.sub(r"\s+", " ", text).strip(" .")
    text = re.sub(r"-{2,}", "-", text).strip("-")
    if not text:
        return fallback
    if len(text) > _MAX_STEM:
        text = text[:_MAX_STEM].rstrip(" .-")
    if text.lower() in _RESERVED_WIN:
        text = f"{text}-note"
    return text or fallback


def unique_name(raw: str, taken: Dict[str, int], fallback: str = "unnamed") -> str:
    """``safe_name`` plus a deterministic suffix when two inputs collide.

    Slugging is lossy - ``BTC/USDT`` and ``BTC:USDT`` both land on ``BTC-USDT`` -
    so collisions get ``-2``, ``-3``, in the order they were first seen. Same
    input order, same names, which keeps the export idempotent.
    """
    base = safe_name(raw, fallback)
    key = base.lower()
    seen = taken.get(key, 0) + 1
    taken[key] = seen
    return base if seen == 1 else f"{base}-{seen}"


def _ts(ms: Optional[int]) -> str:
    if not ms:
        return ""
    return datetime.fromtimestamp(int(ms) / 1000.0, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M"
    )


def _month(ms: int) -> str:
    return datetime.fromtimestamp(int(ms) / 1000.0, tz=timezone.utc).strftime("%Y-%m")


def _yaml_scalar(value: Any) -> str:
    """Quote anything that YAML would otherwise misread."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return f"{value}"
    text = str(value)
    if text == "" or re.search(r"[:#\[\]{},&*!|>'\"%@`]", text) or text != text.strip():
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def _frontmatter(fields: Dict[str, Any]) -> List[str]:
    out = ["---"]
    for key, value in fields.items():
        if isinstance(value, (list, tuple)):
            rendered = ", ".join(_yaml_scalar(v) for v in value)
            out.append(f"{key}: [{rendered}]")
        else:
            out.append(f"{key}: {_yaml_scalar(value)}")
    out.append("---")
    return out


# ----------------------------------------------------------------------
def _write_note(path: Path, body: str, report: ExportReport) -> None:
    """Write ``body`` into ``path``'s generated region, keeping human text.

    Three cases, and the third is the one that matters: a file with no marker
    was authored by a person, so the generated block goes in above what they
    wrote instead of replacing it.
    """
    block = f"{body.rstrip()}\n{END}\n"
    existing = path.read_text(encoding="utf-8") if path.exists() else None

    if existing is None:
        new = block + SCAFFOLD
    else:
        cut = existing.find(END)
        if cut < 0:
            new = block + "\n" + existing.lstrip("\n")
            report.appended += 1
        else:
            tail = existing[cut + len(END):]
            new = block.rstrip("\n") + tail
            # The empty "## My notes" heading is ours, not theirs - counting it
            # would report preserved notes on a vault nobody has written in.
            if tail.strip() and tail.strip() != SCAFFOLD.strip():
                report.preserved += 1

    report.paths.append(path)
    if existing == new:
        report.skipped += 1
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(new, encoding="utf-8")
    os.replace(tmp, path)
    report.written += 1


# ----------------------------------------------------------------------
def _lesson_symbol(recall: Any, meta: Dict[str, Any], known: Sequence[str]) -> str:
    """Which market a lesson is about.

    Consolidation writes the symbol into the lesson's prose ("long BTC/USDT in
    regime ...") rather than into its metadata, so reading only ``meta`` would
    leave every market note claiming Brain 2 had never heard of it.
    """
    tagged = str(meta.get("symbol") or "").strip().upper()
    if tagged:
        return tagged
    text = recall.text.upper()
    for name in known:
        if name in text:
            return name
    return ""


def _lesson_notes(brain: Any, known: Sequence[str], vault: Path,
                  report: ExportReport,
                  by_symbol: Dict[str, List[str]]) -> List[str]:
    """One note per Brain 2 lesson; returns their vault-relative links."""
    links: List[str] = []
    taken: Dict[str, int] = {}
    for recall in brain.b2.latest(limit=500):
        meta = recall.meta if isinstance(recall.meta, dict) else {}
        symbol = _lesson_symbol(recall, meta, known)
        title = recall.text.strip().splitlines()[0] if recall.text.strip() else "lesson"
        stem = unique_name(f"{recall.id:05d} {title}", taken, fallback=f"lesson-{recall.id}")
        link = f"lessons/{stem}"
        links.append(link)
        if symbol:
            by_symbol.setdefault(symbol, []).append(link)

        tags = ["brain2", f"kind/{safe_name(recall.kind, 'unknown')}"]
        if symbol:
            tags.append(f"market/{safe_name(symbol)}")
        lines = _frontmatter({
            "id": recall.id,
            "kind": recall.kind,
            "symbol": symbol,
            "weight": round(float(recall.weight), 4),
            "recorded": _ts(recall.ts),
            "tags": tags,
        })
        lines += ["", f"# {title}", "", recall.text.strip(), ""]
        if symbol:
            lines += [f"Market: [[markets/{safe_name(symbol)}]]", ""]
        if meta:
            lines += ["## Evidence", ""]
            lines += [f"- **{k}**: {v}" for k, v in sorted(meta.items())]
            lines.append("")
        lines.append("Back to [[index]].")
        _write_note(vault / "lessons" / f"{stem}.md", "\n".join(lines), report)
    return links


def _symbol_universe(cfg: Config, trades: Sequence[Trade],
                     positions: Dict[str, Any]) -> List[str]:
    """Every market worth a note: configured, traded, or currently held."""
    symbols: List[str] = list(cfg.symbol_list)
    for source in (t.symbol for t in trades), positions.keys():
        for name in source:
            name = str(name).strip().upper()
            if name and name not in symbols:
                symbols.append(name)
    return symbols


def _market_notes(symbols: Sequence[str], trades: Sequence[Trade],
                  positions: Dict[str, Any], vault: Path, report: ExportReport,
                  by_symbol: Dict[str, List[str]]) -> List[str]:
    links: List[str] = []
    taken: Dict[str, int] = {}
    for symbol in symbols:
        stem = unique_name(symbol, taken, fallback="market")
        links.append(f"markets/{stem}")
        mine = [t for t in trades if t.symbol == symbol]
        wins = sum(1 for t in mine if t.pnl > 0)
        pnl = sum(t.pnl for t in mine)
        position = positions.get(symbol)

        lines = _frontmatter({
            "symbol": symbol,
            "trades": len(mine),
            "net_pnl": round(pnl, 2),
            "win_rate": round(wins / len(mine), 4) if mine else 0.0,
            "open": bool(position),
            "tags": ["brain1", "market", f"market/{safe_name(symbol)}"],
        })
        lines += ["", f"# {symbol}", ""]
        if position is not None:
            side = "long" if getattr(position, "qty", 0) > 0 else "short"
            stop = f"{position.stop:,.2f}" if position.stop else "none"
            lines += [
                f"Open {side} {abs(position.qty):.6f} from "
                f"{position.entry_price:,.2f} ({_ts(position.entry_ts)} UTC), "
                f"stop {stop}.",
                "",
            ]
        else:
            lines += ["No open position.", ""]
        lines += [
            f"- Closed trades: **{len(mine)}**",
            f"- Net P&L: **{pnl:+.2f}**",
            f"- Win rate: **{(wins / len(mine) * 100 if mine else 0):.0f}%**",
            "",
        ]
        related = by_symbol.get(symbol, [])
        lines += ["## What the agent learned here", ""]
        lines += ([f"- [[{link}]]" for link in related[:25]]
                  if related else ["Nothing in Brain 2 mentions this market yet.", ""])
        lines += ["", "Back to [[index]]."]
        _write_note(vault / "markets" / f"{stem}.md", "\n".join(lines), report)
    return links


def _trade_notes(trades: Sequence[Trade], vault: Path,
                 report: ExportReport) -> List[str]:
    months: Dict[str, List[Trade]] = {}
    for trade in trades:
        months.setdefault(_month(trade.exit_ts), []).append(trade)

    links: List[str] = []
    for month in sorted(months, reverse=True):
        rows = sorted(months[month], key=lambda t: t.exit_ts)
        links.append(f"trades/{month}")
        pnl = sum(t.pnl for t in rows)
        lines = _frontmatter({
            "month": month,
            "trades": len(rows),
            "net_pnl": round(pnl, 2),
            "tags": ["brain1", "ledger"],
        })
        lines += [
            "", f"# Trades - {month}", "",
            f"{len(rows)} closed, net **{pnl:+.2f}**.", "",
            "| Closed (UTC) | Market | Side | Entry | Exit | P&L | % | Why in | Why out |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for t in rows:
            lines.append(
                f"| {_ts(t.exit_ts)} | [[markets/{safe_name(t.symbol)}\\|{t.symbol}]] "
                f"| {t.side} | {t.entry_price:.2f} | {t.exit_price:.2f} "
                f"| {t.pnl:+.2f} | {t.pnl_pct * 100:+.2f}% "
                f"| {t.reason_open} | {t.reason_close} |"
            )
        lines += ["", "Back to [[index]]."]
        _write_note(vault / "trades" / f"{month}.md", "\n".join(lines), report)
    return links


def _index_note(cfg: Config, brain: Any, trades: Sequence[Trade],
                positions: Dict[str, Any], lesson_links: Sequence[str],
                market_links: Sequence[str], trade_links: Sequence[str],
                vault: Path, report: ExportReport) -> None:
    stats = brain.b1.trade_stats()
    curve = brain.b1.equity_curve(limit=1)
    equity = float(curve[-1]["equity"]) if curve else float(cfg.start_cash)
    champion = brain.b1.champion() or {}
    b2 = brain.b2.stats()

    lines = _frontmatter({
        "generated": _ts(int(datetime.now(tz=timezone.utc).timestamp() * 1000)),
        "mode": cfg.mode,
        "provider": cfg.provider,
        "timeframe": cfg.timeframe,
        "equity": round(equity, 2),
        "tags": ["dashboard"],
    })
    lines += [
        "", "# Agent vault", "",
        f"Equity **{equity:,.2f}** from a **{cfg.start_cash:,.2f}** start "
        f"({(equity / cfg.start_cash - 1) * 100:+.2f}%), "
        f"{cfg.mode} mode on {cfg.provider} {cfg.timeframe}.", "",
        f"- Closed trades: **{int(stats['trades'])}**, "
        f"win rate **{stats['win_rate'] * 100:.0f}%**, "
        f"net **{stats['net_pnl']:+.2f}**, fees **{stats['fees']:.2f}**",
        f"- Brain 2 holds **{b2['total']}** memories ({b2['embedder']})",
        f"- Champion: **{champion.get('id', 'none yet')}** "
        f"(generation {champion.get('generation', 0)})",
        f"- Open positions: **{len(positions)}**", "",
        "## Markets", "",
    ]
    lines += [f"- [[{link}]]" for link in market_links] or ["None yet."]
    lines += ["", "## Ledger", ""]
    lines += [f"- [[{link}]]" for link in trade_links] or ["No trades closed yet."]
    lines += ["", f"## Lessons ({len(lesson_links)})", ""]
    lines += [f"- [[{link}]]" for link in lesson_links[:50]] or ["Brain 2 is empty."]
    if len(lesson_links) > 50:
        lines.append(f"- ...and {len(lesson_links) - 50} more in `lessons/`.")
    _write_note(vault / "index.md", "\n".join(lines), report)


# ----------------------------------------------------------------------
def export_vault(brain: Any, cfg: Config, vault_dir: Path | str) -> ExportReport:
    """Mirror both brains into an Obsidian vault at ``vault_dir``.

    Read-only with respect to the agent: nothing here writes to SQLite. Safe to
    run while the agent trades, and safe to run twice - see the module docstring
    for the idempotence and human-text guarantees.
    """
    vault = Path(vault_dir).expanduser().resolve()
    vault.mkdir(parents=True, exist_ok=True)
    report = ExportReport(vault=vault)

    trades: List[Trade] = list(brain.b1.recent_trades(limit=2000))
    positions = brain.b1.load_positions()

    symbols = _symbol_universe(cfg, trades, positions)
    by_symbol: Dict[str, List[str]] = {}
    lesson_links = _lesson_notes(brain, symbols, vault, report, by_symbol)
    market_links = _market_notes(symbols, trades, positions, vault, report, by_symbol)
    trade_links = _trade_notes(trades, vault, report)
    _index_note(cfg, brain, trades, positions, lesson_links, market_links,
                trade_links, vault, report)
    return report


def iter_note_paths(vault_dir: Path | str) -> Iterable[Path]:
    """Every markdown note currently in the vault (for tests and tooling)."""
    return sorted(Path(vault_dir).rglob("*.md"))
