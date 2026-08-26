"""How correlated two markets are, measured from their candle closes.

The portfolio risk limits (``max_open_positions``, ``max_position_pct``) treat
each symbol as an independent bet. Across a basket of large-cap coins that is
false: BTC/ETH/XRP/BNB/SOL move together far more often than not, so three
"independent" positions can really be one leveraged bet on crypto beta. This
module gives the risk manager an honest number for how entangled a set of
symbols currently is, so it can cap exposure to one cluster rather than one
symbol.

Everything here is pure stdlib. Pearson correlation of log returns is the
standard, cheap proxy for "do these two markets move together" - it is not
causal and it is not stable over time, but it is enough to notice that a third
concurrent long in this basket is not diversification.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from ..core.types import Candle

# Fewer aligned bars than this and a correlation coefficient is a guess, not a
# measurement - short windows are dominated by noise, and the number would be
# more misleading than an honest "unknown". This applies to the log-return
# series, which is one shorter than the number of aligned closes.
MIN_OVERLAP = 30


@dataclass(frozen=True)
class Correlation:
    """The result of measuring correlation between two return series.

    ``value`` is ``None`` whenever the measurement is not trustworthy - too
    few overlapping bars, or a series with no variance to correlate against -
    rather than a fabricated 0.0. Callers must check ``known`` (or
    ``value is None``) before treating the number as meaningful; ``reason``
    explains why when it is not.
    """

    value: Optional[float]
    n: int  # overlapping bars the measurement (or attempt) used
    reason: str = ""

    @property
    def known(self) -> bool:
        return self.value is not None


def align_closes(a: Sequence[Candle], b: Sequence[Candle]) -> Tuple[List[float], List[float]]:
    """Pair up closes from two candle series by timestamp.

    The two series are not assumed to share a length or be gap-free - one
    symbol can be missing bars the other has - so this joins on ``ts`` rather
    than on position, keeping only the timestamps present in both, in order.
    """
    by_ts_b: Dict[int, float] = {c.ts: c.close for c in b}
    xs: List[float] = []
    ys: List[float] = []
    for c in a:
        close_b = by_ts_b.get(c.ts)
        if close_b is not None:
            xs.append(c.close)
            ys.append(close_b)
    return xs, ys


def log_returns(closes: Sequence[float]) -> List[float]:
    """Bar-over-bar log returns; a non-positive close yields a 0.0 return
    rather than raising, since a synthetic or bad tick should not crash a
    risk check."""
    out: List[float] = []
    for prev, cur in zip(closes, closes[1:]):
        out.append(math.log(cur / prev) if prev > 0 and cur > 0 else 0.0)
    return out


def pearson(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    """Pearson correlation coefficient of two equal-length series.

    Returns ``None`` if either series has zero variance - a constant series
    has no relationship to correlate, and dividing by a zero standard
    deviation would otherwise produce a fabricated number (or a NaN).
    """
    n = len(xs)
    if n == 0 or len(ys) != n:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x <= 0.0 or var_y <= 0.0:
        return None
    value = cov / math.sqrt(var_x * var_y)
    return max(-1.0, min(1.0, value))  # guard against float drift past +-1


def correlation(
    a: Sequence[Candle], b: Sequence[Candle], min_overlap: int = MIN_OVERLAP
) -> Correlation:
    """Pearson correlation of log returns between two candle series, aligned on timestamp."""
    closes_a, closes_b = align_closes(a, b)
    # min_overlap is a floor on the number of *returns*, which needs one more
    # aligned close than that.
    if len(closes_a) < min_overlap + 1:
        return Correlation(
            None, len(closes_a),
            f"only {len(closes_a)} overlapping bars (need at least {min_overlap + 1})",
        )
    rets_a = log_returns(closes_a)
    rets_b = log_returns(closes_b)
    value = pearson(rets_a, rets_b)
    if value is None:
        return Correlation(None, len(rets_a), "zero-variance return series")
    return Correlation(value, len(rets_a))


def cluster_symbols(
    histories: Dict[str, Sequence[Candle]],
    threshold: float,
    min_overlap: int = MIN_OVERLAP,
) -> Tuple[List[List[str]], Dict[Tuple[str, str], Correlation]]:
    """Group symbols into clusters where any pair above ``threshold`` is linked.

    This is connected components over the "correlated" graph, not mutual
    correlation within a cluster: if A-B and B-C both clear the threshold, A
    ends up grouped with C even when A-C alone would not clear it, because
    that is still one leveraged bet running through B. A pair whose
    correlation is unknown (too little overlap, zero variance) is treated as
    not linked - absence of evidence is not evidence of independence, but it
    is not grounds to lump two symbols into one cluster either.

    Returns the clusters (each symbol appears in exactly one, including
    clusters of one) and the full pairwise correlation table, so callers can
    explain *why* two symbols were grouped.
    """
    names = sorted(histories)
    pairs: Dict[Tuple[str, str], Correlation] = {}
    parent = {name: name for name in names}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            result = correlation(histories[a], histories[b], min_overlap)
            pairs[(a, b)] = result
            if result.known and result.value >= threshold:
                union(a, b)

    groups: Dict[str, List[str]] = {}
    for name in names:
        groups.setdefault(find(name), []).append(name)
    return list(groups.values()), pairs
