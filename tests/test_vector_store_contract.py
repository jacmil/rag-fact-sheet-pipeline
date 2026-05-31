from __future__ import annotations

import math
import uuid

import numpy as np
import pytest

from tests.helpers import make_test_store
from vector_store.types import VectorStore

EMBEDDING_DIM = 384


def unit_vector(*components: tuple[int, float]) -> np.ndarray:
    vector = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    for index, value in components:
        vector[index] = value

    norm = np.linalg.norm(vector)
    if norm == 0:
        raise ValueError("Test vectors must be non-zero")
    return vector / norm


QUERY_VECTOR = unit_vector((0, 1.0))


def sample_records(
    prefix: str,
) -> tuple[list[str], np.ndarray, list[str], list[dict[str, str]]]:
    ids = [
        f"{prefix}_agl_targets",
        f"{prefix}_bhp_scope3",
        f"{prefix}_kraft_goals",
        f"{prefix}_vale_targets",
    ]
    embeddings = np.vstack(
        [
            unit_vector((0, 1.0)),
            unit_vector((0, 0.8), (1, 0.6)),
            unit_vector((0, 0.5), (1, 0.866)),
            unit_vector((1, 1.0)),
        ]
    )
    texts = [
        "AGL emissions targets and renewable electricity goals.",
        "BHP scope 3 goals for steelmaking and shipping.",
        "Kraft Heinz environmental sustainability goals.",
        "Vale long-term scope 1, scope 2, and scope 3 targets.",
    ]
    metadatas = [
        {"company": "AGL", "year": "2024", "sector": "Energy Utilities"},
        {"company": "BHP", "year": "2020", "sector": "Diversified Mining"},
        {"company": "Kraft Heinz", "year": "2024", "sector": "Food"},
        {"company": "Vale", "year": "2024", "sector": "Diversified Mining"},
    ]
    return ids, embeddings, texts, metadatas


def add_sample_records(store: VectorStore, prefix: str) -> list[str]:
    ids, embeddings, texts, metadatas = sample_records(prefix)
    store.add(ids=ids, embeddings=embeddings, texts=texts, metadatas=metadatas)
    return ids


def test_add_count_info_and_query(vector_store: VectorStore) -> None:
    prefix = uuid.uuid4().hex[:8]
    ids = add_sample_records(vector_store, prefix)

    assert vector_store.count() == 4

    info = vector_store.info()
    assert info.count == 4
    assert info.name

    results = vector_store.query(embedding=QUERY_VECTOR, k=3)

    assert [result.chunk_id for result in results] == ids[:3]
    assert all(math.isfinite(result.score) for result in results)
    assert results[0].metadata["company"] == "AGL"
    assert results[0].text.startswith("AGL emissions targets")


@pytest.mark.parametrize(
    ("where", "expected_company"),
    [
        ({"company": "Kraft Heinz"}, "Kraft Heinz"),
        ({"year": "2020"}, "BHP"),
        ({"sector": "Energy Utilities"}, "AGL"),
    ],
)
def test_metadata_filters(
    vector_store: VectorStore,
    where: dict[str, str],
    expected_company: str,
) -> None:
    prefix = uuid.uuid4().hex[:8]
    add_sample_records(vector_store, prefix)

    results = vector_store.query(embedding=QUERY_VECTOR, k=5, where=where)

    assert results
    assert all(
        result.metadata.get(key) == value
        for result in results
        for key, value in where.items()
    )
    assert results[0].metadata["company"] == expected_company


def test_metadata_filter_without_matches_returns_empty(vector_store: VectorStore) -> None:
    prefix = uuid.uuid4().hex[:8]
    add_sample_records(vector_store, prefix)

    results = vector_store.query(
        embedding=QUERY_VECTOR,
        k=5,
        where={"company": "Not A Real Company"},
    )

    assert results == []


def test_duplicate_ids_upsert(vector_store: VectorStore) -> None:
    chunk_id = f"{uuid.uuid4().hex[:8]}_upsert"
    vector_store.add(
        ids=[chunk_id],
        embeddings=np.vstack([unit_vector((1, 1.0))]),
        texts=["Old text"],
        metadatas=[{"company": "OldCo", "year": "2020", "sector": "Food"}],
    )
    vector_store.add(
        ids=[chunk_id],
        embeddings=np.vstack([unit_vector((0, 1.0))]),
        texts=["Updated emissions target text"],
        metadatas=[
            {"company": "UpdatedCo", "year": "2024", "sector": "Energy Utilities"}
        ],
    )

    assert vector_store.count() == 1

    results = vector_store.query(
        embedding=QUERY_VECTOR,
        k=1,
        where={"company": "UpdatedCo"},
    )

    assert len(results) == 1
    assert results[0].chunk_id == chunk_id
    assert results[0].text == "Updated emissions target text"
    assert results[0].metadata["year"] == "2024"


def test_chroma_and_pgvector_return_same_topk_order(tmp_path) -> None:
    collection_name = f"pytest_parity_{uuid.uuid4().hex[:12]}"
    chroma = make_test_store("chroma", collection_name, tmp_path)
    pgvector = make_test_store("pgvector", collection_name, tmp_path)

    try:
        prefix = uuid.uuid4().hex[:8]
        add_sample_records(chroma, prefix)
        add_sample_records(pgvector, prefix)

        chroma_ids = [
            result.chunk_id for result in chroma.query(embedding=QUERY_VECTOR, k=4)
        ]
        pgvector_ids = [
            result.chunk_id for result in pgvector.query(embedding=QUERY_VECTOR, k=4)
        ]

        assert chroma_ids == pgvector_ids
    finally:
        chroma.delete_collection()
        pgvector.delete_collection()
