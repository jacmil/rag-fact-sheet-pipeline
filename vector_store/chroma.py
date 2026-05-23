"""ChromaDB implementation of the VectorStore protocol."""

from __future__ import annotations

import logging

import chromadb
import numpy as np

from .types import CollectionInfo, QueryResult

logger = logging.getLogger(__name__)


class ChromaStore:
    """Persistent ChromaDB vector store using cosine similarity."""

    def __init__(self, collection_name: str, chroma_dir: str) -> None:
        self.client = chromadb.PersistentClient(path=chroma_dir)
        self._collection_name = collection_name

        # See DECISIONS.md: get_or_create ambiguity
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        existing = self.collection.count()
        if existing > 0:
            logger.info("Loaded collection '%s' (%d chunks)", collection_name, existing)
        else:
            logger.info("Created collection '%s'", collection_name)

    def add(
        self,
        ids: list[str],
        embeddings: np.ndarray,
        texts: list[str],
        metadatas: list[dict[str, str]],
    ) -> None:
        """Store chunks with their embeddings and metadata."""
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings.tolist(),
            documents=texts,
            metadatas=metadatas,
        )
        logger.info("Added %d chunks to '%s'", len(ids), self._collection_name)

    def query(
        self,
        embedding: np.ndarray,
        k: int = 5,
        where: dict[str, str] | None = None,
    ) -> list[QueryResult]:
        """Return the k most similar chunks, optionally filtered by metadata."""
        kwargs: dict = {
            "query_embeddings": [embedding.tolist()],
            "n_results": k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where is not None:
            kwargs["where"] = where

        results = self.collection.query(**kwargs)

        # FLAG 2: ChromaDB nests everything in lists-of-lists because it
        # supports batched queries. We always query with one vector so we
        # unpack index [0]. If you ever want batch queries, this method
        # signature would need to change (accept 2D embeddings, return
        # list[list[QueryResult]]).
        result_ids = results["ids"][0]
        if not result_ids:
            return []

        query_results = [
            QueryResult(
                chunk_id=chunk_id,
                text=text,
                score=1.0 - distance,
                metadata=meta,
            )
            for chunk_id, text, distance, meta in zip(
                result_ids,
                results["documents"][0],
                results["distances"][0],
                results["metadatas"][0],
            )
        ]

        return sorted(query_results, key=lambda r: r.score, reverse=True)

    def delete_collection(self) -> None:
        """Delete the collection and all stored data."""
        try:
            self.client.delete_collection(name=self._collection_name)
            logger.info("Deleted collection '%s'", self._collection_name)
        except ValueError:
            logger.info("Collection '%s' already deleted, no-op", self._collection_name)

    def count(self) -> int:
        """Return the number of chunks in the collection."""
        return self.collection.count()

    def info(self) -> CollectionInfo:
        """Return collection name, count, and metadata."""
        return CollectionInfo(
            name=self.collection.name,
            count=self.collection.count(),
            metadata=dict(self.collection.metadata or {}),
        )
