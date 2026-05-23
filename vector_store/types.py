"""Shared types consumed by both vector store backends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class QueryResult:
    """A single retrieval result with its similarity score."""

    chunk_id: str
    text: str
    score: float  # cosine similarity, range [0, 1], higher = more similar
    metadata: dict[str, str]


@dataclass(frozen=True)
class CollectionInfo:
    """Summary of a stored collection."""

    name: str
    count: int
    metadata: dict[str, str]


class VectorStore(Protocol):
    """Structural protocol for vector store backends."""

    def add(
        self,
        ids: list[str],
        embeddings: np.ndarray,
        texts: list[str],
        metadatas: list[dict[str, str]],
    ) -> None:
        """Store chunks with their embeddings and metadata."""
        ...

    def query(
        self,
        embedding: np.ndarray,
        k: int = 5,
        where: dict[str, str] | None = None,
    ) -> list[QueryResult]:
        """Return the k most similar chunks, optionally filtered by metadata."""
        ...

    def delete_collection(self) -> None:
        """Delete the collection and all stored data."""
        ...

    def count(self) -> int:
        """Return the number of chunks in the collection."""
        ...

    def info(self) -> CollectionInfo:
        """Return collection name, count, and metadata."""
        ...
