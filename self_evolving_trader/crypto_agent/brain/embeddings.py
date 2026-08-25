"""Embeddings for Brain 2.

The default embedder is a deterministic hashing vectoriser (the "hashing trick"
over word unigrams and bigrams, sublinear term frequency, L2 normalised). It has
no dependencies, no network, no model download, and — critically for a process
that must reload its memories months later — it is stable across restarts and
machines, which Python's builtin ``hash`` is not.

``Embedder`` is a protocol, so swapping in a real embedding API later means
writing one class; vectors already stored keep their own dimension recorded.
"""

from __future__ import annotations

import hashlib
import math
import re
from array import array
from typing import List, Protocol, Sequence

_TOKEN = re.compile(r"[a-z0-9_.%\-]+")


class Embedder(Protocol):
    dim: int
    name: str

    def embed(self, text: str) -> List[float]:
        ...


def tokenize(text: str) -> List[str]:
    words = _TOKEN.findall(text.lower())
    bigrams = [f"{a}_{b}" for a, b in zip(words, words[1:])]
    return words + bigrams


class HashingEmbedder:
    """Stable bag-of-ngrams vectoriser using blake2b for bucket assignment."""

    name = "hashing-v1"

    def __init__(self, dim: int = 256) -> None:
        if dim < 16:
            raise ValueError("dim must be >= 16")
        self.dim = dim

    def _bucket(self, token: str) -> tuple[int, float]:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        # Low bit picks the sign, which keeps unrelated collisions from always
        # reinforcing each other.
        return value % self.dim, 1.0 if (value >> 63) & 1 else -1.0

    def embed(self, text: str) -> List[float]:
        counts: dict[int, float] = {}
        for token in tokenize(text):
            idx, sign = self._bucket(token)
            counts[idx] = counts.get(idx, 0.0) + sign
        vec = [0.0] * self.dim
        for idx, raw in counts.items():
            # Sublinear scaling: the tenth mention of "loss" is not ten times
            # more informative than the first.
            vec[idx] = math.copysign(1.0 + math.log(abs(raw)), raw) if raw else 0.0
        return l2_normalize(vec)


def l2_normalize(vec: Sequence[float]) -> List[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return list(vec)
    return [v / norm for v in vec]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity; inputs are expected to be L2-normalised already."""
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    dot = sum(a[i] * b[i] for i in range(n))
    return max(-1.0, min(1.0, dot))


def pack(vec: Sequence[float]) -> bytes:
    return array("f", vec).tobytes()


def unpack(blob: bytes) -> List[float]:
    arr = array("f")
    arr.frombytes(blob)
    return list(arr)
