from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.helpers import make_test_store
from utils import bootstrap_runtime_env
from vector_store.types import VectorStore

CONTRACT_COVERAGE = (
    "Both backends can add records, report count/info, and query top-k results.",
    "Company, year, and sector metadata filters use the same where={...} contract.",
    "Duplicate chunk IDs upsert instead of crashing or creating duplicate rows.",
    "ChromaDB and pgvector return the same top-k order on a fixed synthetic dataset.",
)


@pytest.fixture(scope="session", autouse=True)
def load_test_env() -> None:
    bootstrap_runtime_env()


@pytest.fixture
def collection_name() -> str:
    return f"pytest_vectors_{uuid.uuid4().hex[:12]}"


@pytest.fixture(params=("chroma", "pgvector"), ids=("chroma", "pgvector"))
def vector_store(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    collection_name: str,
) -> Iterator[VectorStore]:
    store = make_test_store(request.param, collection_name, tmp_path)
    try:
        yield store
    finally:
        store.delete_collection()


def pytest_terminal_summary(terminalreporter, exitstatus: int, config) -> None:
    terminalreporter.section("Vector Store Contract Coverage")
    terminalreporter.write_line(
        "These tests validate correctness before running benchmark_metrics.py."
    )
    for item in CONTRACT_COVERAGE:
        terminalreporter.write_line(f"- {item}")
