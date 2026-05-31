from __future__ import annotations

import logging
import os

import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder

from vector_store import VectorStore, QueryResult
from utils import resolve_pipeline_config, PipelineConfig, DEFAULT_QUERY


logger = logging.getLogger(__name__)

# Two-stage retrieval: retrieve a broad candidate set, then rerank
# with a cross-encoder to get a precise top-k. These control the
# width of the first pass and the depth of the final output.
BROAD_K: int = 50
RERANK_TOP_K: int = 5


def get_company_filter(query_text: str, config: PipelineConfig) -> dict[str, str] | None:
    """Return a metadata company filter if the query names a tracked company.

    Reads company names from config rather than hardcoding them.
    """
    query_lower: str = query_text.lower()

    for company_name in config.company_dirs:
        if company_name.lower().split()[0] in query_lower:
            return {"company": company_name}

    return None


def retrieve_chunks(
    query_text: str,
    store: VectorStore,
    model: SentenceTransformer,
    config: PipelineConfig,
    k: int = 5,
) -> list[QueryResult]:
    """Embed a query and retrieve the top-k matching chunks.

    The embedding model produces a single query vector. model.encode()
    returns shape (1, embed_dim); we index [0] to get (embed_dim,)
    which is what the VectorStore.query() interface expects.
    """
    query_embedding: np.ndarray = model.encode([query_text], normalize_embeddings=True)[
        0
    ]  # (embed_dim,) — single query vector

    where_filter: dict[str, str] | None = get_company_filter(query_text, config)

    if where_filter:
        logger.info(f"Applying filter: {where_filter}")

    results: list[QueryResult] = store.query(
        embedding=query_embedding, k=k, where=where_filter
    )
    logger.info(f"Retrieved {len(results)} chunk(s)")
    return results


def rerank_chunks(
    query_text: str,
    results: list[QueryResult],
    reranker: CrossEncoder,
    top_k: int = RERANK_TOP_K,
) -> list[QueryResult]:
    """Rerank retrieved chunks using a cross-encoder model.

    The cross-encoder reads (query, chunk) pairs jointly with full
    attention, producing more accurate relevance scores than the
    bi-encoder retrieval. Scores replace the original cosine
    similarity scores from the first stage.
    """

    # Cross-encoder expects list of (query, document) pairs
    pairs: list[tuple[str, str]] = [(query_text, r.text) for r in results]
    scores: np.ndarray = reranker.predict(pairs)
    finite_scores = np.isfinite(scores)

    if not finite_scores.any():
        logger.warning(
            "Reranker returned no finite scores; using bi-encoder ranking instead"
        )
        return results[:top_k]

    scores = np.where(finite_scores, scores, -np.inf)

    # Sort by cross-encoder score descending, keep top_k
    ranked: list[tuple[float, QueryResult]] = sorted(
        zip(scores, results),
        key=lambda x: x[0],
        reverse=True,
    )[:top_k]

    # Rebuild QueryResult with cross-encoder scores replacing bi-encoder scores
    return [
        QueryResult(
            chunk_id=r.chunk_id,
            text=r.text,
            score=float(s),
            metadata=r.metadata,
        )
        for s, r in ranked
    ]


def run_retrieve(
    query: str | None = None,
    store: VectorStore | None = None,
) -> list[QueryResult]:
    """Two-stage retrieval: broad bi-encoder pass, then cross-encoder rerank."""
    config: PipelineConfig = resolve_pipeline_config()
    query_text: str = query or os.getenv("QUERY_TEXT", DEFAULT_QUERY)

    # Allow standalone use without a pre-created store
    if store is None:
        from vector_store import get_vector_store

        store = get_vector_store(config.collection_name)

    logger.info(f"Query: {query_text}")
    model: SentenceTransformer = SentenceTransformer(config.embedding_model)

    try:
        reranker: CrossEncoder = CrossEncoder(config.reranking_model)
    except Exception as exc:
        logger.warning(
            "Reranker unavailable (%s); using bi-encoder ranking instead",
            exc,
        )
        results = retrieve_chunks(
            query_text,
            store,
            model,
            config,
            k=RERANK_TOP_K,
        )
        for i, r in enumerate(results, start=1):
            logger.info(f"[{i}] {r.text[:200]}...")
        return results

    # Stage 1: broad retrieval with bi-encoder
    results: list[QueryResult] = retrieve_chunks(query_text, store, model, config, k=BROAD_K)
    # Stage 2: rerank candidates with cross-encoder
    results = rerank_chunks(query_text, results, reranker, top_k=RERANK_TOP_K)

    for i, r in enumerate(results, start=1):
        logger.info(f"[{i}] {r.text[:200]}...")

    return results


if __name__ == "__main__":
    log_format = "%(asctime)s %(levelname)-8s %(message)s"
    try:
        import coloredlogs

        coloredlogs.install(level="INFO", fmt=log_format, datefmt="%H:%M:%S")
    except ImportError:
        logging.basicConfig(level=logging.INFO, format=log_format, datefmt="%H:%M:%S")

    run_retrieve()
