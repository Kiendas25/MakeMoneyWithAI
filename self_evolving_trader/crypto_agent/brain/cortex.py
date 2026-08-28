"""Brain 2 - semantic / associative memory.

Where Brain 1 answers "what happened at 14:00 on Tuesday", Brain 2 answers
"what does this situation remind me of". Lessons are stored as text plus an
embedding; recall is a cosine search with a recency-and-usefulness prior, so
memories that keep proving useful surface more often and stale ones fade.

Storage is a separate SQLite file: the two brains have different access
patterns, different lifetimes, and can be backed up or wiped independently.
"""

from __future__ import annotations

import json
import math
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ..core.types import Lesson
from .embeddings import Embedder, HashingEmbedder, cosine, pack, unpack

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        INTEGER NOT NULL,
    kind      TEXT NOT NULL,
    text      TEXT NOT NULL,
    vector    BLOB NOT NULL,
    dim       INTEGER NOT NULL,
    embedder  TEXT NOT NULL,
    meta      TEXT NOT NULL,
    weight    REAL NOT NULL,
    hits      INTEGER NOT NULL DEFAULT 0,
    last_used INTEGER NOT NULL,
    digest    TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_memories_kind ON memories(kind);
CREATE INDEX IF NOT EXISTS idx_memories_ts ON memories(ts);
"""

MS_PER_DAY = 86_400_000.0


def _now_ms() -> int:
    return int(time.time() * 1000)


class Recall:
    """One recalled memory plus the scores that surfaced it."""

    __slots__ = ("id", "text", "kind", "meta", "similarity", "score", "ts", "weight")

    def __init__(
        self,
        id: int,
        text: str,
        kind: str,
        meta: Dict[str, Any],
        similarity: float,
        score: float,
        ts: int,
        weight: float,
    ) -> None:
        self.id = id
        self.text = text
        self.kind = kind
        self.meta = meta
        self.similarity = similarity
        self.score = score
        self.ts = ts
        self.weight = weight

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Recall {self.kind} sim={self.similarity:.2f} {self.text[:60]!r}>"


class Cortex:
    """Vector memory with decay, reinforcement and pruning."""

    def __init__(
        self,
        path: Path | str,
        embedder: Optional[Embedder] = None,
        half_life_days: float = 30.0,
        max_items: int = 5000,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.embedder = embedder or HashingEmbedder()
        self.half_life_days = max(0.5, half_life_days)
        self.max_items = max_items
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "Cortex":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    def remember(self, lesson: Lesson) -> int:
        """Store a lesson. Re-learning the same text reinforces it instead of
        duplicating it - that is what makes repetition matter."""
        text = lesson.text.strip()
        if not text:
            raise ValueError("cannot remember empty text")
        digest = f"{lesson.kind}:{hash_text(text)}"
        vector = self.embedder.embed(text)
        now = _now_ms()
        with self._lock:
            row = self._conn.execute(
                "SELECT id, weight FROM memories WHERE digest=?", (digest,)
            ).fetchone()
            if row:
                new_weight = min(10.0, float(row["weight"]) + lesson.weight * 0.5)
                self._conn.execute(
                    "UPDATE memories SET weight=?, ts=?, meta=? WHERE id=?",
                    (new_weight, now, json.dumps(lesson.meta, default=str), row["id"]),
                )
                self._conn.commit()
                return int(row["id"])
            cur = self._conn.execute(
                "INSERT INTO memories(ts,kind,text,vector,dim,embedder,meta,weight,hits,last_used,digest) "
                "VALUES (?,?,?,?,?,?,?,?,0,?,?)",
                (
                    now,
                    lesson.kind,
                    text,
                    pack(vector),
                    self.embedder.dim,
                    self.embedder.name,
                    json.dumps(lesson.meta, default=str),
                    float(lesson.weight),
                    now,
                    digest,
                ),
            )
            self._conn.commit()
            new_id = int(cur.lastrowid)
        self.prune()
        return new_id

    def remember_many(self, lessons: Sequence[Lesson]) -> List[int]:
        return [self.remember(lesson) for lesson in lessons]

    # ------------------------------------------------------------------
    def recall(
        self,
        query: str,
        k: int = 5,
        kind: Optional[str | Sequence[str]] = None,
        min_similarity: float = 0.05,
        reinforce: bool = True,
    ) -> List[Recall]:
        """Retrieve the memories most relevant to ``query``.

        Ranking blends three things: semantic similarity, how much the memory
        has earned its keep (weight), and how recent it is. A three-year-old
        lesson about a market that no longer exists should not outrank last
        week's, however well it matches the words.
        """
        qvec = self.embedder.embed(query)
        now = _now_ms()
        sql = "SELECT * FROM memories"
        params: List[Any] = []
        kinds = [kind] if isinstance(kind, str) else list(kind) if kind else []
        if kinds:
            sql += " WHERE kind IN (" + ",".join("?" * len(kinds)) + ")"
            params.extend(kinds)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()

        scored: List[Recall] = []
        for row in rows:
            if row["embedder"] != self.embedder.name or row["dim"] != self.embedder.dim:
                continue  # vectors from another embedder are not comparable
            sim = cosine(qvec, unpack(row["vector"]))
            if sim < min_similarity:
                continue
            age_days = max(0.0, (now - int(row["ts"])) / MS_PER_DAY)
            recency = 0.5 ** (age_days / self.half_life_days)
            weight = float(row["weight"])
            score = sim * (1.0 + 0.25 * math.log1p(weight)) * (0.35 + 0.65 * recency)
            scored.append(
                Recall(
                    id=int(row["id"]),
                    text=row["text"],
                    kind=row["kind"],
                    meta=json.loads(row["meta"]),
                    similarity=sim,
                    score=score,
                    ts=int(row["ts"]),
                    weight=weight,
                )
            )
        scored.sort(key=lambda r: r.score, reverse=True)
        top = scored[:k]
        if reinforce and top:
            with self._lock:
                self._conn.executemany(
                    "UPDATE memories SET hits=hits+1, last_used=? WHERE id=?",
                    [(now, r.id) for r in top],
                )
                self._conn.commit()
        return top

    # ------------------------------------------------------------------
    def reinforce(self, memory_id: int, delta: float) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE memories SET weight=MAX(0.05, MIN(10.0, weight + ?)) WHERE id=?",
                (delta, memory_id),
            )
            self._conn.commit()

    def prune(self) -> int:
        """Forget the least useful memories once over capacity."""
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) n FROM memories").fetchone()
            total = int(row["n"])
            if total <= self.max_items:
                return 0
            excess = total - self.max_items
            now = _now_ms()
            candidates = self._conn.execute(
                "SELECT id, ts, weight, hits FROM memories"
            ).fetchall()
            ranked = sorted(
                candidates,
                key=lambda r: (
                    float(r["weight"]) * (1.0 + float(r["hits"]))
                    * 0.5 ** (max(0.0, (now - int(r["ts"])) / MS_PER_DAY) / self.half_life_days)
                ),
            )
            doomed = [(int(r["id"]),) for r in ranked[:excess]]
            self._conn.executemany("DELETE FROM memories WHERE id=?", doomed)
            self._conn.commit()
        return len(doomed)

    # ------------------------------------------------------------------
    def count(self, kind: Optional[str] = None) -> int:
        with self._lock:
            if kind:
                row = self._conn.execute(
                    "SELECT COUNT(*) n FROM memories WHERE kind=?", (kind,)
                ).fetchone()
            else:
                row = self._conn.execute("SELECT COUNT(*) n FROM memories").fetchone()
        return int(row["n"])

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT kind, COUNT(*) n, AVG(weight) w FROM memories GROUP BY kind"
            ).fetchall()
        return {
            "total": self.count(),
            "by_kind": {r["kind"]: {"count": int(r["n"]), "avg_weight": float(r["w"])} for r in rows},
            "embedder": f"{self.embedder.name}/{self.embedder.dim}",
        }

    def latest(self, limit: int = 10, kind: Optional[str] = None) -> List[Recall]:
        sql = "SELECT * FROM memories"
        params: List[Any] = []
        if kind:
            sql += " WHERE kind=?"
            params.append(kind)
        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [
            Recall(
                id=int(r["id"]),
                text=r["text"],
                kind=r["kind"],
                meta=json.loads(r["meta"]),
                similarity=1.0,
                score=1.0,
                ts=int(r["ts"]),
                weight=float(r["weight"]),
            )
            for r in rows
        ]


def hash_text(text: str) -> str:
    import hashlib

    return hashlib.blake2b(text.encode("utf-8"), digest_size=16).hexdigest()
