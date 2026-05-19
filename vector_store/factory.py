"""Factory that returns the correct vector store backend from .env config."""

from __future__ import annotations

import logging
import os

from .types import VectorStore

logger = logging.getLogger(__name__)


def get_vector_store(collection_name: str) -> VectorStore:
    """Read VECTOR_STORE from environment and return the matching backend."""
    backend = os.getenv("VECTOR_STORE", "chroma").lower().strip()

    if backend == "chroma":
        from .chroma import ChromaStore

        chroma_dir = os.getenv("CHROMA_DIR", "data/chromadb")
        logger.info("Using ChromaDB backend (dir=%s)", chroma_dir)
        return ChromaStore(collection_name=collection_name, chroma_dir=chroma_dir)

    if backend == "pgvector":
        from .pgvector import PgVectorStore

        connection_string = os.getenv("PG_CONNECTION_STRING")
        if not connection_string:
            raise ValueError(
                "PG_CONNECTION_STRING must be set when VECTOR_STORE=pgvector"
            )
        logger.info("Using pgvector backend")
        return PgVectorStore(
            collection_name=collection_name,
            connection_string=connection_string,
        )

    raise ValueError(
        f"Unknown VECTOR_STORE backend: '{backend}'. Use 'chroma' or 'pgvector'."
    )
