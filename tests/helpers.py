from __future__ import annotations

import os
from pathlib import Path

import pytest

from vector_store.chroma import ChromaStore
from vector_store.pgvector import PgVectorStore
from vector_store.types import VectorStore


def make_test_store(backend: str, collection_name: str, tmp_path: Path) -> VectorStore:
    if backend == "chroma":
        return ChromaStore(
            collection_name=collection_name,
            chroma_dir=str(tmp_path / "chroma"),
        )

    if backend == "pgvector":
        connection_string = os.getenv("PG_CONNECTION_STRING", "").strip()
        if not connection_string:
            pytest.skip("PG_CONNECTION_STRING is not set; skipping pgvector tests")

        try:
            return PgVectorStore(
                collection_name=collection_name,
                connection_string=connection_string,
            )
        except Exception as exc:
            pytest.skip(f"pgvector is unavailable; skipping pgvector tests: {exc}")

    raise ValueError(f"Unknown backend: {backend}")
