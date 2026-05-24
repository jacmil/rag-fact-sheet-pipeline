"""pgvector implementation of the VectorStore protocol."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

import numpy as np
from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .db import ChunkRecord
from .types import CollectionInfo, QueryResult

logger = logging.getLogger(__name__)


def _normalize_connection_string(url: str) -> str:
    """Use psycopg v3 driver when no driver is specified in the URL."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


class PgVectorStore:
    """Postgres + pgvector store using cosine distance."""

    def __init__(self, collection_name: str, connection_string: str) -> None:
        self._collection_name = collection_name
        self._engine: Engine = create_engine(_normalize_connection_string(connection_string))
        self._session_factory = sessionmaker(bind=self._engine)
        self._ensure_extension()
        existing = self.count()
        if existing > 0:
            logger.info(
                "Loaded collection '%s' (%d chunks)", collection_name, existing
            )
        else:
            logger.info("Created collection '%s'", collection_name)

    def _ensure_extension(self) -> None:
        with self._engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()

    @contextmanager
    def _session(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def add(
        self,
        ids: list[str],
        embeddings: np.ndarray,
        texts: list[str],
        metadatas: list[dict[str, str]],
    ) -> None:
        """Store chunks with their embeddings and metadata."""
        if not ids:
            return

        rows = [
            {
                "chunk_id": chunk_id,
                "content": content,
                "embedding": embedding.tolist(),
                "collection_name": self._collection_name,
                "metadata": metadata,
            }
            for chunk_id, embedding, content, metadata in zip(
                ids, embeddings, texts, metadatas
            )
        ]

        stmt = pg_insert(ChunkRecord.__table__).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["chunk_id"],
            set_={
                "content": stmt.excluded.content,
                "embedding": stmt.excluded.embedding,
                "collection_name": stmt.excluded.collection_name,
                "metadata": stmt.excluded.metadata,
            },
        )

        with self._session() as session:
            session.execute(stmt)

        logger.info("Added %d chunks to '%s'", len(ids), self._collection_name)

    def query(
        self,
        embedding: np.ndarray,
        k: int = 5,
        where: dict[str, str] | None = None,
    ) -> list[QueryResult]:
        """Return the k most similar chunks, optionally filtered by metadata."""
        query_vec = embedding.tolist()
        distance = ChunkRecord.embedding.cosine_distance(query_vec)

        stmt = (
            select(
                ChunkRecord.chunk_id,
                ChunkRecord.content,
                ChunkRecord.metadata_,
                distance.label("distance"),
            )
            .where(ChunkRecord.collection_name == self._collection_name)
            .order_by(distance)
            .limit(k)
        )

        if where is not None:
            for key, value in where.items():
                stmt = stmt.where(ChunkRecord.metadata_[key].as_string() == value)

        with self._session() as session:
            rows = session.execute(stmt).all()

        if not rows:
            return []

        query_results = [
            QueryResult(
                chunk_id=row.chunk_id,
                text=row.content,
                score=1.0 - float(row.distance),
                metadata=dict(row.metadata_ or {}),
            )
            for row in rows
        ]

        return sorted(query_results, key=lambda result: result.score, reverse=True)

    def delete_collection(self) -> None:
        """Delete the collection and all stored data."""
        with self._session() as session:
            result = session.execute(
                delete(ChunkRecord).where(
                    ChunkRecord.collection_name == self._collection_name
                )
            )
            deleted = result.rowcount or 0
        logger.info("Deleted collection '%s' (%d rows)", self._collection_name, deleted)

    def count(self) -> int:
        """Return the number of chunks in the collection."""
        stmt = (
            select(func.count())
            .select_from(ChunkRecord)
            .where(ChunkRecord.collection_name == self._collection_name)
        )
        with self._session() as session:
            return int(session.scalar(stmt) or 0)

    def info(self) -> CollectionInfo:
        """Return collection name, count, and metadata."""
        return CollectionInfo(
            name=self._collection_name,
            count=self.count(),
            metadata={"backend": "pgvector"},
        )
