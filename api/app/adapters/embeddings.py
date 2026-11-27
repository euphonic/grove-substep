"""Embedding adapter. Mock vectors are hash-seeded unit vectors of the real dimension."""

import hashlib
import math
import struct
from typing import Protocol

from app.config import Settings


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class MockEmbedder:
    def __init__(self, dim: int) -> None:
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        values: list[float] = []
        counter = 0
        while len(values) < self.dim:
            block = hashlib.sha256(f"{counter}:{text}".encode()).digest()
            for (n,) in struct.iter_unpack(">I", block):
                values.append(n / 0xFFFFFFFF * 2 - 1)
            counter += 1
        values = values[: self.dim]
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]


def get_embedder(settings: Settings) -> Embedder:
    if settings.embedding_provider == "mock":
        return MockEmbedder(settings.embedding_dim)
    raise NotImplementedError("Gemini embeddings are wired up in M4")
