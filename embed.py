from __future__ import annotations

import json
import logging
import re
from functools import lru_cache

import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer

from vector_store import VectorStore
from utils import resolve_pipeline_config, PipelineConfig


logger = logging.getLogger(__name__)

# Encode and store this many chunks per batch. 256 balances memory
# usage against the overhead of repeated store.add() calls.
BATCH_SIZE: int = 256
METADATA_OVERRIDES_PATH = Path("document_metadata.json")
NUL_BYTE = "\x00"


def remove_nul_bytes(value: str) -> str:
    """Remove NUL bytes, which PostgreSQL text fields reject."""
    return value.replace(NUL_BYTE, "")


def clean_metadata(metadata: dict[str, str]) -> dict[str, str]:
    """Sanitize string metadata before handing it to a vector backend."""
    return {key: remove_nul_bytes(value) for key, value in metadata.items()}


def run_embed(store: VectorStore) -> None:
    """Load chunks, generate embeddings, and store via the vector store backend."""
    config: PipelineConfig = resolve_pipeline_config()
    chunks: list[dict] = load_all_chunks(config.output_dir)
    logger.info(f"Total chunks loaded: {len(chunks)}")

    model: SentenceTransformer = SentenceTransformer(config.embedding_model)
    logger.info("Embedding model loaded")

    add_chunks_to_store(chunks, store, model)
    logger.info("Embedding stage complete")


def load_all_chunks(output_dir: Path) -> list[dict]:
    """Load all chunk records from JSONL files in the chunks subdirectory."""
    chunks: list[dict] = []
    chunk_files: list[Path] = sorted((output_dir / "chunks").glob("*_chunks.jsonl"))
    logger.info(f"Found {len(chunk_files)} chunk file(s)")

    for jsonl_path in chunk_files:
        logger.info(f"Loading chunks from {jsonl_path.name}")
        with jsonl_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                chunks.append(json.loads(line))

    logger.info(f"Loaded {len(chunks)} total chunk(s)")
    return chunks


def build_chunk_id(chunk: dict) -> str:
    """Build a unique ID for a chunk.

    Format: {company}_{source_file}_{chunk_id}, with spaces replaced
    by underscores so the ID is safe for both backends.
    """
    source: str = chunk.get("source_file", "unknown").replace(" ", "_")
    company: str = chunk["company"].replace(" ", "_")
    return f"{company}_{source}_{chunk['id']}"


@lru_cache(maxsize=1)
def load_document_metadata(path: str = str(METADATA_OVERRIDES_PATH)) -> dict[str, dict[str, str]]:
    """Load optional per-company/per-document metadata for filters."""
    metadata_path = Path(path)
    if not metadata_path.exists():
        return {}

    with metadata_path.open("r", encoding="utf-8") as f:
        raw_metadata = json.load(f)

    return {
        str(key): {str(k): str(v) for k, v in value.items() if v is not None}
        for key, value in raw_metadata.items()
    }


def lookup_document_metadata(company: str, source_file: str) -> dict[str, str]:
    """Merge company-level and document-level metadata overrides."""
    metadata = load_document_metadata()
    resolved: dict[str, str] = {}

    for key in (company, source_file, f"{company}|{source_file}"):
        resolved.update(metadata.get(key, {}))

    return resolved


def infer_year_from_source(source_file: str) -> str:
    """Infer year only from the source filename, not from arbitrary body text."""
    match = re.search(r"\b(19|20)\d{2}\b", source_file)
    return match.group(0) if match else ""


def build_chunk_metadata(chunk: dict) -> dict[str, str]:
    """Extract metadata from a chunk.

    All values must be strings to satisfy the VectorStore interface
    contract. Non-string fields (e.g. pages list) are cast with str().
    """
    company = chunk["company"]
    source_file = chunk["source_file"]
    metadata = lookup_document_metadata(company, source_file)
    year = str(chunk.get("year") or metadata.get("year") or infer_year_from_source(source_file))
    sector = str(chunk.get("sector") or metadata.get("sector", ""))

    chunk_metadata = {
        "company": chunk["company"],
        "source_file": chunk["source_file"],
        "strategy": chunk["strategy"],
        "pages": str(chunk.get("pages", [])),  # list → string
    }

    if year:
        chunk_metadata["year"] = year
    if sector:
        chunk_metadata["sector"] = sector

    return chunk_metadata


def build_chunk_records(
    chunks: list[dict],
) -> tuple[list[str], list[str], list[dict[str, str]]]:
    """Build parallel lists of ids, documents, and metadatas from raw chunks.

    The three returned lists are aligned by index and match the
    positional arguments of VectorStore.add().
    """
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, str]] = []

    for chunk in chunks:
        ids.append(build_chunk_id(chunk))
        documents.append(remove_nul_bytes(chunk["text"]))
        metadatas.append(clean_metadata(build_chunk_metadata(chunk)))

    return ids, documents, metadatas


def add_chunks_to_store(
    chunks: list[dict],
    store: VectorStore,
    model: SentenceTransformer,
) -> None:
    """Embed chunks in batches and store via the vector store backend.

    Both backends handle duplicate IDs via upsert, so no client-side
    idempotency check is needed. See DECISIONS.md.
    """
    ids, documents, metadatas = build_chunk_records(chunks)

    logger.info(f"Chunks to store: {len(ids)}")
    if not ids:
        return

    total_batches: int = (len(ids) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(ids), BATCH_SIZE):
        batch_num: int = i // BATCH_SIZE + 1
        batch_docs: list[str] = documents[i : i + BATCH_SIZE]

        # normalize_embeddings=True produces unit vectors so dot product = cosine similarity
        batch_embeddings: np.ndarray = model.encode(
            batch_docs, normalize_embeddings=True
        )

        store.add(
            ids=ids[i : i + BATCH_SIZE],
            embeddings=batch_embeddings,
            texts=batch_docs,
            metadatas=metadatas[i : i + BATCH_SIZE],
        )
        logger.info(f"Batch [{batch_num}/{total_batches}] stored")

    logger.info(f"Stored {len(ids)} chunk(s)")


if __name__ == "__main__":
    log_format = "%(asctime)s %(levelname)-8s %(message)s"
    try:
        import coloredlogs

        coloredlogs.install(level="INFO", fmt=log_format, datefmt="%H:%M:%S")
    except ImportError:
        logging.basicConfig(level=logging.INFO, format=log_format, datefmt="%H:%M:%S")

    # Standalone run for testing: create store from config
    from vector_store import get_vector_store

    config: PipelineConfig = resolve_pipeline_config()
    store: VectorStore = get_vector_store(config.collection_name)
    run_embed(store)
