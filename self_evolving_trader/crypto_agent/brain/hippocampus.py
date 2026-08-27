"""Brain 1 - episodic / structured memory (SQLite).

This is the agent's ledger and its sense of "what literally happened": every
candle it has seen, every decision it made, every fill, every closed trade,
every genome it has ever evaluated, and the equity curve that resulted.

It is exact, queryable and transactional. Brain 2 (``cortex.py``) is the
opposite: fuzzy, associative, and searched by meaning rather than by key.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from ..core.types import Candle, Position, Signal, Trade

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS candles (
    symbol    TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    ts        INTEGER NOT NULL,
    open      REAL NOT NULL,
    high      REAL NOT NULL,
    low       REAL NOT NULL,
    close     REAL NOT NULL,
    volume    REAL NOT NULL,
    PRIMARY KEY (symbol, timeframe, ts)
);
CREATE TABLE IF NOT EXISTS decisions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        INTEGER NOT NULL,
    symbol    TEXT NOT NULL,
    action    TEXT NOT NULL,
    score     REAL NOT NULL,
    reason    TEXT NOT NULL,
    regime    TEXT NOT NULL,
    features  TEXT NOT NULL,
    genome_id TEXT NOT NULL,
    executed  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_decisions_ts ON decisions(ts);
CREATE TABLE IF NOT EXISTS trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL,
    qty         REAL NOT NULL,
    entry_ts    INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    exit_ts     INTEGER NOT NULL,
    exit_price  REAL NOT NULL,
    pnl         REAL NOT NULL,
    pnl_pct     REAL NOT NULL,
    fees        REAL NOT NULL,
    reason_open  TEXT NOT NULL,
    reason_close TEXT NOT NULL,
    genome_id   TEXT NOT NULL,
    regime      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trades_exit ON trades(exit_ts);
CREATE TABLE IF NOT EXISTS equity (
    ts       INTEGER PRIMARY KEY,
    equity   REAL NOT NULL,
    cash     REAL NOT NULL,
    exposure REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS genomes (
    id           TEXT PRIMARY KEY,
    generation   INTEGER NOT NULL,
    genes        TEXT NOT NULL,
    fitness      REAL NOT NULL,
    oos_fitness  REAL NOT NULL,
    metrics      TEXT NOT NULL,
    status       TEXT NOT NULL,
    created_at   INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS generations (
    id           INTEGER PRIMARY KEY,
    ts           INTEGER NOT NULL,
    best_id      TEXT NOT NULL,
    best_fitness REAL NOT NULL,
    mean_fitness REAL NOT NULL,
    population   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      INTEGER NOT NULL,
    level   TEXT NOT NULL,
    kind    TEXT NOT NULL,
    message TEXT NOT NULL,
    data    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
"""


def _now_ms() -> int:
    return int(time.time() * 1000)


class Hippocampus:
    """Durable, exact memory. Safe to share across threads."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "Hippocampus":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- key/value state ------------------------------------------------
    def set_state(self, key: str, value: Any) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO kv(key, value, updated_at) VALUES (?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (key, json.dumps(value), _now_ms()),
            )
            self._conn.commit()

    def get_state(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    # -- candles --------------------------------------------------------
    def save_candles(self, symbol: str, timeframe: str, candles: Iterable[Candle]) -> int:
        rows = [
            (symbol, timeframe, c.ts, c.open, c.high, c.low, c.close, c.volume)
            for c in candles
        ]
        if not rows:
            return 0
        with self._lock:
            self._conn.executemany(
                "INSERT INTO candles(symbol,timeframe,ts,open,high,low,close,volume) "
                "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(symbol,timeframe,ts) DO UPDATE SET "
                "open=excluded.open, high=excluded.high, low=excluded.low, "
                "close=excluded.close, volume=excluded.volume",
                rows,
            )
            self._conn.commit()
        return len(rows)

    def load_candles(self, symbol: str, timeframe: str, limit: int) -> List[Candle]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts,open,high,low,close,volume FROM candles "
                "WHERE symbol=? AND timeframe=? ORDER BY ts DESC LIMIT ?",
                (symbol, timeframe, limit),
            ).fetchall()
        return [
            Candle(r["ts"], r["open"], r["high"], r["low"], r["close"], r["volume"])
            for r in reversed(rows)
        ]

    # -- decisions ------------------------------------------------------
    def record_decision(
        self, ts: int, symbol: str, action: str, signal: Signal, genome_id: str, executed: bool
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO decisions(ts,symbol,action,score,reason,regime,features,genome_id,executed) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    ts,
                    symbol,
                    action,
                    signal.score,
                    signal.reason,
                    signal.regime,
                    json.dumps({k: round(v, 6) for k, v in signal.features.items()}),
                    genome_id,
                    int(executed),
                ),
            )
            self._conn.commit()

    def decision_reasons(self, limit: int = 2000) -> List[Dict[str, Any]]:
        """Why the recent decisions went the way they did, most common first.

        Every decision already stores its reason and whether it executed, so
        "the agent is not opening anything and I cannot see why" is a question
        the ledger can already answer - it just needed asking. Reasons carry
        live numbers ("volatility 0.041 above genome ceiling 0.038"), so they
        are bucketed by their leading words rather than counted verbatim.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT action, reason, executed FROM decisions ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
        buckets: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            key = _decision_bucket(row["action"] or "", row["reason"] or "")
            entry = buckets.setdefault(key, {"reason": key, "count": 0, "executed": 0,
                                             "example": row["reason"] or ""})
            entry["count"] += 1
            entry["executed"] += int(row["executed"] or 0)
        return sorted(buckets.values(), key=lambda b: -b["count"])

    def recent_decisions(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM decisions ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # -- trades ---------------------------------------------------------
    def record_trade(self, trade: Trade) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO trades(symbol,side,qty,entry_ts,entry_price,exit_ts,exit_price,"
                "pnl,pnl_pct,fees,reason_open,reason_close,genome_id,regime) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    trade.symbol,
                    trade.side,
                    trade.qty,
                    trade.entry_ts,
                    trade.entry_price,
                    trade.exit_ts,
                    trade.exit_price,
                    trade.pnl,
                    trade.pnl_pct,
                    trade.fees,
                    trade.reason_open,
                    trade.reason_close,
                    trade.genome_id,
                    trade.regime,
                ),
            )
            self._conn.commit()
            trade.id = int(cur.lastrowid)
        return trade.id

    def recent_trades(self, limit: int = 50) -> List[Trade]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM trades ORDER BY exit_ts DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_row_to_trade(r) for r in rows]

    def trades_since(self, ts: int) -> List[Trade]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM trades WHERE exit_ts >= ? ORDER BY exit_ts", (ts,)
            ).fetchall()
        return [_row_to_trade(r) for r in rows]

    def trade_stats(self) -> Dict[str, float]:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) n, "
                "COALESCE(SUM(pnl),0) pnl, "
                "COALESCE(AVG(pnl_pct),0) avg_pct, "
                "COALESCE(SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END),0) wins, "
                "COALESCE(SUM(fees),0) fees FROM trades"
            ).fetchone()
        n = int(row["n"])
        return {
            "trades": n,
            "net_pnl": float(row["pnl"]),
            "avg_pct": float(row["avg_pct"]),
            "win_rate": (float(row["wins"]) / n) if n else 0.0,
            "fees": float(row["fees"]),
        }

    # -- equity ---------------------------------------------------------
    def record_equity(self, ts: int, equity: float, cash: float, exposure: float) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO equity(ts,equity,cash,exposure) VALUES (?,?,?,?) "
                "ON CONFLICT(ts) DO UPDATE SET equity=excluded.equity, cash=excluded.cash, "
                "exposure=excluded.exposure",
                (ts, equity, cash, exposure),
            )
            self._conn.commit()

    def equity_curve(self, limit: int = 1000) -> List[Dict[str, float]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts,equity,cash,exposure FROM equity ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def peak_equity(self) -> Optional[float]:
        with self._lock:
            row = self._conn.execute("SELECT MAX(equity) peak FROM equity").fetchone()
        return float(row["peak"]) if row and row["peak"] is not None else None

    # -- genomes / generations -----------------------------------------
    def save_genome(
        self,
        genome_id: str,
        generation: int,
        genes: Dict[str, Any],
        fitness: float,
        oos_fitness: float,
        metrics: Dict[str, Any],
        status: str = "candidate",
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO genomes(id,generation,genes,fitness,oos_fitness,metrics,status,created_at) "
                "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                "generation=excluded.generation, fitness=excluded.fitness, "
                "oos_fitness=excluded.oos_fitness, metrics=excluded.metrics, "
                # Re-evaluating the reigning champion must not silently demote it;
                # only set_genome_status() changes who is champion.
                "status=CASE WHEN genomes.status='champion' THEN 'champion' "
                "ELSE excluded.status END",
                (
                    genome_id,
                    generation,
                    json.dumps(genes, sort_keys=True),
                    fitness,
                    oos_fitness,
                    json.dumps(metrics, sort_keys=True),
                    status,
                    _now_ms(),
                ),
            )
            self._conn.commit()

    def set_genome_status(self, genome_id: str, status: str) -> None:
        with self._lock:
            if status == "champion":
                self._conn.execute(
                    "UPDATE genomes SET status='retired' WHERE status='champion'"
                )
            self._conn.execute("UPDATE genomes SET status=? WHERE id=?", (status, genome_id))
            self._conn.commit()

    def get_genome(self, genome_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM genomes WHERE id=?", (genome_id,)).fetchone()
        return _row_to_genome(row) if row else None

    def champion(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM genomes WHERE status='champion' ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        return _row_to_genome(row) if row else None

    def top_genomes(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM genomes ORDER BY oos_fitness DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_row_to_genome(r) for r in rows]

    def record_generation(
        self,
        generation: int,
        best_id: str,
        best_fitness: float,
        mean_fitness: float,
        population: Sequence[str],
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO generations(id,ts,best_id,best_fitness,mean_fitness,population) "
                "VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET ts=excluded.ts, "
                "best_id=excluded.best_id, best_fitness=excluded.best_fitness, "
                "mean_fitness=excluded.mean_fitness, population=excluded.population",
                (
                    generation,
                    _now_ms(),
                    best_id,
                    best_fitness,
                    mean_fitness,
                    json.dumps(list(population)),
                ),
            )
            self._conn.commit()

    def last_generation(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT MAX(id) g FROM generations").fetchone()
        return int(row["g"]) if row and row["g"] is not None else 0

    def generation_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id,ts,best_id,best_fitness,mean_fitness FROM generations "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    # -- audit log ------------------------------------------------------
    def log_event(
        self, kind: str, message: str, data: Optional[Dict[str, Any]] = None, level: str = "INFO"
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO events(ts,level,kind,message,data) VALUES (?,?,?,?,?)",
                (_now_ms(), level, kind, message, json.dumps(data or {}, default=str)),
            )
            self._conn.commit()

    def recent_events(self, limit: int = 25) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts,level,kind,message,data FROM events ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # -- open positions (one per symbol) --------------------------------
    POSITIONS_KEY = "open_positions"
    LEGACY_POSITION_KEY = "open_position"

    def save_position(self, symbol: str, position: Optional[Position]) -> None:
        book = self.load_positions()
        if position is None:
            book.pop(symbol, None)
        else:
            book[symbol] = position
        self.set_state(
            self.POSITIONS_KEY,
            {name: _position_to_dict(p) for name, p in book.items()},
        )

    def load_position(self, symbol: str) -> Optional[Position]:
        return self.load_positions().get(symbol)

    def load_positions(self) -> Dict[str, Position]:
        raw = self.get_state(self.POSITIONS_KEY)
        if raw is None:
            # Brains written before the agent traded a universe kept a single
            # unkeyed position; adopt it rather than stranding an open trade.
            legacy = self.get_state(self.LEGACY_POSITION_KEY)
            if not legacy:
                return {}
            position = Position(**legacy)
            self.set_state(self.POSITIONS_KEY, {position.symbol: legacy})
            self.set_state(self.LEGACY_POSITION_KEY, None)
            return {position.symbol: position}
        return {name: Position(**data) for name, data in raw.items()}


_REASON_PREFIXES = (
    ("warming up", "warming up"),
    ("volatility", "volatility above the genome's ceiling"),
    ("genome stands aside", "genome stands aside in a ranging market"),
    ("target", "target below the cost floor"),
    ("memory vetoed", "memory vetoed the entry"),
    ("stand aside score", "score below the entry threshold"),
)


def _decision_bucket(action: str, reason: str) -> str:
    """Collapse one decision into a stable category.

    The action says what happened; only when nothing happened ("flat") does the
    signal's own reason say why, and that text carries live numbers, so it is
    matched by its leading words rather than counted verbatim.
    """
    act = action.strip().lower()
    if act.startswith("open:"):
        return "opened a position"
    if act.startswith("close:"):
        return f"closed a position ({act.split(':', 1)[1]})"
    if act == "hold":
        return "already in a position, holding"
    if act == "veto:memory":
        return "memory vetoed the entry"
    if act == "veto:risk":
        return "risk limits blocked the entry (see `report` for which)"
    if act and act != "flat":
        return act

    low = reason.strip().lower()
    for prefix, label in _REASON_PREFIXES:
        if low.startswith(prefix):
            return label
    return " ".join(reason.split()[:4]) or "no signal"


def _position_to_dict(p: Position) -> Dict[str, Any]:
    return {
        "symbol": p.symbol,
        "qty": p.qty,
        "entry_price": p.entry_price,
        "entry_ts": p.entry_ts,
        "stop": p.stop,
        "take_profit": p.take_profit,
        "genome_id": p.genome_id,
        "regime": p.regime,
        "bars_held": p.bars_held,
    }


def _row_to_trade(r: sqlite3.Row) -> Trade:
    return Trade(
        id=r["id"],
        symbol=r["symbol"],
        side=r["side"],
        qty=r["qty"],
        entry_ts=r["entry_ts"],
        entry_price=r["entry_price"],
        exit_ts=r["exit_ts"],
        exit_price=r["exit_price"],
        pnl=r["pnl"],
        pnl_pct=r["pnl_pct"],
        fees=r["fees"],
        reason_open=r["reason_open"],
        reason_close=r["reason_close"],
        genome_id=r["genome_id"],
        regime=r["regime"],
    )


def _row_to_genome(r: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": r["id"],
        "generation": r["generation"],
        "genes": json.loads(r["genes"]),
        "fitness": r["fitness"],
        "oos_fitness": r["oos_fitness"],
        "metrics": json.loads(r["metrics"]),
        "status": r["status"],
        "created_at": r["created_at"],
    }
