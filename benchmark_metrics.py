from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

from embed import BATCH_SIZE, build_chunk_records, load_all_chunks
from utils import PipelineConfig, resolve_pipeline_config
from vector_store import VectorStore


logging.getLogger("pypdf").setLevel(logging.ERROR)

DEFAULT_BENCHMARK_COLLECTION = "tpi_vectors_benchmark"
DEFAULT_PAGE_TARGETS = (20, 60)
BACKEND_FILES = {
    "chroma": Path("vector_store/chroma.py"),
    "pgvector": Path("vector_store/pgvector.py"),
}


def load_reference_answers(path: str | Path = "reference_answers.json") -> list[dict]:
    """Load the manually labelled Recall@5 reference set."""
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def make_store(
    backend: str,
    config: PipelineConfig,
    collection_name: str,
    chroma_dir: str | Path | None = None,
) -> VectorStore:
    """Create a backend directly so notebooks do not depend on VECTOR_STORE."""
    if backend == "chroma":
        from vector_store.chroma import ChromaStore

        return ChromaStore(
            collection_name=collection_name,
            chroma_dir=str(chroma_dir or config.chroma_dir),
        )

    if backend == "pgvector":
        from vector_store.pgvector import PgVectorStore

        if not config.pg_connection_string:
            raise ValueError("PG_CONNECTION_STRING is required for pgvector.")
        return PgVectorStore(
            collection_name=collection_name,
            connection_string=config.pg_connection_string,
        )

    raise ValueError(f"Unknown backend: {backend}")


def load_benchmark_inputs(
    config: PipelineConfig,
    reference_path: str | Path = "reference_answers.json",
    max_chunks: int | None = None,
    max_queries: int | None = None,
) -> dict[str, Any]:
    """Load chunks and reference queries, but do not embed anything yet."""
    chunks = load_all_chunks(config.output_dir)
    if max_chunks is not None:
        chunks = chunks[:max_chunks]

    reference_answers = load_reference_answers(reference_path)
    if max_queries is not None:
        reference_answers = reference_answers[:max_queries]

    ids, texts, metadatas = build_chunk_records(chunks)
    return {
        "ids": ids,
        "texts": texts,
        "metadatas": metadatas,
        "reference_answers": reference_answers,
    }


def prefix_chunk_ids(ids: list[str], prefix: str) -> list[str]:
    """Avoid collisions with normal collection IDs during benchmark upserts."""
    return [f"{prefix}{chunk_id}" for chunk_id in ids]


def prefix_reference_ids(reference_answers: list[dict], prefix: str) -> list[dict]:
    """Keep relevance labels aligned with prefixed benchmark chunk IDs."""
    return [
        {
            **entry,
            "relevant_ids": [
                f"{prefix}{chunk_id}" for chunk_id in entry["relevant_ids"]
            ],
        }
        for entry in reference_answers
    ]


def build_filter_cases(
    metadatas: list[dict[str, str]],
    keys: tuple[str, ...] = ("company", "year", "sector"),
) -> dict[str, dict[str, str] | None]:
    """Build simple filter cases from metadata that exists in the chunk set."""
    filter_cases: dict[str, dict[str, str] | None] = {"unfiltered": None}
    if not metadatas:
        return filter_cases

    first = metadatas[0]
    for key in keys:
        value = first.get(key)
        if value:
            filter_cases[f"{key}_filter"] = {key: value}

    return filter_cases


def describe_filter_cases(metadatas: list[dict[str, str]]) -> pd.DataFrame:
    """Show which metadata filters are available for this benchmark run."""
    rows = []
    for name, where in build_filter_cases(metadatas).items():
        rows.append(
            {
                "filter_name": name,
                "where": where,
                "available": where is not None or name == "unfiltered",
            }
        )
    return pd.DataFrame(rows)


def count_pdf_pages(pdf_path: Path) -> int:
    """Return the number of pages in a PDF."""
    return len(PdfReader(str(pdf_path)).pages)


def closest_page_target(pages: int, targets: tuple[int, ...] = DEFAULT_PAGE_TARGETS) -> int:
    """Return the target page count closest to the document page count."""
    return min(targets, key=lambda target: (abs(pages - target), target))


def document_page_inventory(
    config: PipelineConfig | None = None,
    chunks: list[dict] | None = None,
    page_threshold: int = 60,
    page_targets: tuple[int, ...] = DEFAULT_PAGE_TARGETS,
) -> pd.DataFrame:
    """List PDFs with page counts, chunk counts, and size group labels."""
    resolved_config = config or resolve_pipeline_config()
    loaded_chunks = chunks if chunks is not None else load_all_chunks(resolved_config.output_dir)

    chunk_counts: dict[tuple[str, str], int] = {}
    for chunk in loaded_chunks:
        key = (chunk["company"], chunk["source_file"])
        chunk_counts[key] = chunk_counts.get(key, 0) + 1

    rows: list[dict[str, Any]] = []
    for company, company_dir in sorted(resolved_config.company_dirs.items()):
        for pdf_path in sorted(company_dir.glob(resolved_config.pdf_glob)):
            pages = count_pdf_pages(pdf_path)
            source_file = pdf_path.stem
            page_group = (
                f"below_{page_threshold}_pages"
                if pages < page_threshold
                else f"{page_threshold}_pages_or_more"
            )
            page_target = closest_page_target(pages, page_targets)
            rows.append(
                {
                    "company": company,
                    "source_file": source_file,
                    "pdf_path": str(pdf_path),
                    "pages": pages,
                    "page_group": page_group,
                    "closest_page_target": page_target,
                    "page_target_distance": abs(pages - page_target),
                    "page_target_group": f"closest_to_{page_target}_pages",
                    "chunks": chunk_counts.get((company, source_file), 0),
                }
            )

    return pd.DataFrame(rows).sort_values(["page_group", "pages", "company"])


def split_chunks_by_inventory_group(
    chunks: list[dict],
    inventory: pd.DataFrame,
    group_column: str,
) -> dict[str, list[dict]]:
    """Group chunk records using a document-level group column."""
    group_by_doc = {
        (row.company, row.source_file): getattr(row, group_column)
        for row in inventory.itertuples(index=False)
    }
    grouped: dict[str, list[dict]] = {}

    for chunk in chunks:
        group = group_by_doc.get((chunk["company"], chunk["source_file"]))
        if group is None:
            continue
        grouped.setdefault(group, []).append(chunk)

    return grouped


def split_chunks_by_page_group(
    chunks: list[dict],
    inventory: pd.DataFrame,
) -> dict[str, list[dict]]:
    """Group chunk records using the page_group assigned to each source PDF."""
    return split_chunks_by_inventory_group(chunks, inventory, "page_group")


def deployment_complexity_metrics(
    compose_path: str | Path = "docker-compose.yml",
) -> pd.DataFrame:
    """Return concrete deployment-complexity counts requested by the brief."""
    compose = Path(compose_path)
    compose_lines = compose.read_text(encoding="utf-8").splitlines()
    nonblank_lines = [line for line in compose_lines if line.strip()]
    noncomment_lines = [
        line for line in nonblank_lines if not line.lstrip().startswith("#")
    ]
    services = count_compose_services(compose_lines)

    return pd.DataFrame(
        [
            {
                "backend": "chroma",
                "extra_services_required": 0,
                "docker_compose_total_lines": 0,
                "docker_compose_noncomment_lines": 0,
                "clean_machine_backend_steps": 2,
                "setup_notes": "Install Python env; set VECTOR_STORE=chroma.",
            },
            {
                "backend": "pgvector",
                "extra_services_required": services,
                "docker_compose_total_lines": len(compose_lines),
                "docker_compose_noncomment_lines": len(noncomment_lines),
                "clean_machine_backend_steps": 5,
                "setup_notes": (
                    "Install Docker; set Postgres env vars; docker compose up; "
                    "run Alembic; run pgvector smoke test."
                ),
            },
        ]
    )


def count_compose_services(lines: list[str]) -> int:
    """Count top-level services in a simple docker-compose.yml file."""
    in_services = False
    service_count = 0

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        if indent == 0:
            in_services = stripped == "services:"
            continue

        if in_services and indent == 2 and stripped.endswith(":"):
            service_count += 1

    return service_count


def code_legibility_metrics(
    backend_files: dict[str, Path] | None = None,
) -> pd.DataFrame:
    """Count backend code size/imports and include radon complexity if available."""
    files = backend_files or BACKEND_FILES
    radon_scores = run_radon_complexity(files)
    rows: list[dict[str, Any]] = []

    for backend, path in files.items():
        lines = path.read_text(encoding="utf-8").splitlines()
        imports = [
            line
            for line in lines
            if line.startswith("import ") or line.startswith("from ")
        ]
        radon = radon_scores.get(str(path), {})

        rows.append(
            {
                "backend": backend,
                "path": str(path),
                "line_count": len(lines),
                "import_count": len(imports),
                "radon_functions_classes": radon.get("items"),
                "radon_max_complexity": radon.get("max_complexity"),
                "radon_mean_complexity": radon.get("mean_complexity"),
                "radon_note": radon.get("note", ""),
            }
        )

    return pd.DataFrame(rows)


def run_radon_complexity(files: dict[str, Path]) -> dict[str, dict[str, Any]]:
    """Run radon if installed; otherwise return a clear note for the notebook."""
    if shutil.which("radon") is None:
        return {
            str(path): {"note": "radon not installed in this environment"}
            for path in files.values()
        }

    completed = subprocess.run(
        ["radon", "cc", "-s", "-j", *[str(path) for path in files.values()]],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return {
            str(path): {"note": completed.stderr.strip() or "radon failed"}
            for path in files.values()
        }

    raw = json.loads(completed.stdout)
    scores: dict[str, dict[str, Any]] = {}
    for path, items in raw.items():
        complexities = [
            item["complexity"]
            for item in items
            if isinstance(item.get("complexity"), (int, float))
        ]
        scores[path] = {
            "items": len(items),
            "max_complexity": max(complexities) if complexities else 0,
            "mean_complexity": float(np.mean(complexities)) if complexities else 0.0,
        }

    return scores


def encode_queries(
    model: SentenceTransformer,
    reference_answers: list[dict],
) -> dict[str, np.ndarray]:
    """Precompute query embeddings so timed query rows isolate store.query()."""
    queries = [entry["query"] for entry in reference_answers]
    vectors = model.encode(queries, normalize_embeddings=True)
    return dict(zip(queries, vectors))


def benchmark_ingestion(
    store: VectorStore,
    backend: str,
    model: SentenceTransformer,
    ids: list[str],
    texts: list[str],
    metadatas: list[dict[str, str]],
    batch_size: int = BATCH_SIZE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Time embedding plus storage, while also separating store.add() time."""
    embed_start = time.perf_counter()
    embeddings = model.encode(texts, normalize_embeddings=True)
    embed_seconds = time.perf_counter() - embed_start

    batch_rows: list[dict[str, Any]] = []
    total_add_seconds = 0.0

    for start_idx in range(0, len(ids), batch_size):
        end_idx = start_idx + batch_size
        batch_number = start_idx // batch_size + 1
        batch_ids = ids[start_idx:end_idx]

        add_start = time.perf_counter()
        store.add(
            ids=batch_ids,
            embeddings=embeddings[start_idx:end_idx],
            texts=texts[start_idx:end_idx],
            metadatas=metadatas[start_idx:end_idx],
        )
        add_seconds = time.perf_counter() - add_start
        total_add_seconds += add_seconds

        batch_rows.append(
            {
                "backend": backend,
                "batch_number": batch_number,
                "batch_size": len(batch_ids),
                "store_add_seconds": add_seconds,
                "store_chunks_per_second": (
                    len(batch_ids) / add_seconds if add_seconds else None
                ),
            }
        )

    total_seconds = embed_seconds + total_add_seconds
    chunks = len(ids)
    ingestion = pd.DataFrame(
        [
            {
                "backend": backend,
                "chunks": chunks,
                "batches": len(batch_rows),
                "embed_seconds": embed_seconds,
                "store_add_seconds": total_add_seconds,
                "total_embed_and_store_seconds": total_seconds,
                "chunks_per_second_total": chunks / total_seconds
                if total_seconds
                else None,
                "chunks_per_second_store_only": chunks / total_add_seconds
                if total_add_seconds
                else None,
            }
        ]
    )

    return ingestion, pd.DataFrame(batch_rows)


def run_page_group_ingestion_benchmark(
    backends: tuple[str, ...] = ("chroma", "pgvector"),
    page_threshold: int = 60,
    batch_size: int = BATCH_SIZE,
    collection_prefix: str = "tpi_vectors_page_group_benchmark",
    cleanup: bool = True,
) -> dict[str, Any]:
    """Compare ingestion throughput for PDFs below/above a page threshold."""
    config = resolve_pipeline_config()
    chunks = load_all_chunks(config.output_dir)
    inventory = document_page_inventory(
        config=config,
        chunks=chunks,
        page_threshold=page_threshold,
    )
    benchmark = run_inventory_group_ingestion_benchmark(
        config=config,
        chunks=chunks,
        inventory=inventory,
        group_column="page_group",
        backends=backends,
        batch_size=batch_size,
        collection_prefix=collection_prefix,
        id_prefix_root="pgsize",
        cleanup=cleanup,
    )
    benchmark["parameters"]["page_threshold"] = page_threshold
    benchmark["page_group_summary"] = benchmark.pop("group_summary")
    return benchmark


def run_page_target_ingestion_benchmark(
    backends: tuple[str, ...] = ("chroma", "pgvector"),
    page_targets: tuple[int, ...] = DEFAULT_PAGE_TARGETS,
    batch_size: int = BATCH_SIZE,
    collection_prefix: str = "tpi_vectors_page_target_benchmark",
    cleanup: bool = True,
) -> dict[str, Any]:
    """Compare ingestion by assigning each PDF to its nearest page target."""
    config = resolve_pipeline_config()
    chunks = load_all_chunks(config.output_dir)
    inventory = document_page_inventory(
        config=config,
        chunks=chunks,
        page_targets=page_targets,
    )
    benchmark = run_inventory_group_ingestion_benchmark(
        config=config,
        chunks=chunks,
        inventory=inventory,
        group_column="page_target_group",
        backends=backends,
        batch_size=batch_size,
        collection_prefix=collection_prefix,
        id_prefix_root="target",
        cleanup=cleanup,
    )
    benchmark["parameters"]["page_targets"] = list(page_targets)
    benchmark["page_target_summary"] = benchmark.pop("group_summary")
    return benchmark


def run_inventory_group_ingestion_benchmark(
    config: PipelineConfig,
    chunks: list[dict],
    inventory: pd.DataFrame,
    group_column: str,
    backends: tuple[str, ...],
    batch_size: int,
    collection_prefix: str,
    id_prefix_root: str,
    cleanup: bool,
) -> dict[str, Any]:
    """Compare ingestion throughput for any document-level grouping column."""
    chunks_by_group = split_chunks_by_inventory_group(chunks, inventory, group_column)
    model = SentenceTransformer(config.embedding_model)

    ingestion_frames: list[pd.DataFrame] = []
    batch_frames: list[pd.DataFrame] = []
    errors: list[dict[str, str]] = []

    group_stats = (
        inventory.groupby(group_column, as_index=False)
        .agg(
            pdf_count=("source_file", "count"),
            total_pages=("pages", "sum"),
            mean_pages=("pages", "mean"),
            mean_target_distance=("page_target_distance", "mean"),
            chunks=("chunks", "sum"),
        )
        .sort_values(group_column)
    )
    stats_by_group = {
        getattr(row, group_column): row._asdict()
        for row in group_stats.itertuples(index=False)
    }

    for group_name, group_chunks in chunks_by_group.items():
        ids, texts, metadatas = build_chunk_records(group_chunks)
        ids = prefix_chunk_ids(ids, f"{id_prefix_root}__{group_name}__")
        group_info = stats_by_group[group_name]

        for backend in backends:
            temp_dir = tempfile.TemporaryDirectory() if backend == "chroma" else None
            chroma_dir = temp_dir.name if temp_dir else None
            collection_name = f"{collection_prefix}_{group_name}_{backend}"
            store: VectorStore | None = None
            try:
                store = make_store(
                    backend=backend,
                    config=config,
                    collection_name=collection_name,
                    chroma_dir=chroma_dir,
                )
                store.delete_collection()
                store = make_store(
                    backend=backend,
                    config=config,
                    collection_name=collection_name,
                    chroma_dir=chroma_dir,
                )

                ingestion, batches = benchmark_ingestion(
                    store=store,
                    backend=backend,
                    model=model,
                    ids=ids,
                    texts=texts,
                    metadatas=metadatas,
                    batch_size=batch_size,
                )
                for frame in (ingestion, batches):
                    frame.insert(0, group_column, group_name)
                    frame.insert(1, "pdf_count", group_info["pdf_count"])
                    frame.insert(2, "total_pages", group_info["total_pages"])
                    frame.insert(3, "mean_pages", group_info["mean_pages"])
                    frame.insert(
                        4,
                        "mean_target_distance",
                        group_info["mean_target_distance"],
                    )

                ingestion_frames.append(ingestion)
                batch_frames.append(batches)
            except Exception as exc:
                errors.append(
                    {
                        group_column: group_name,
                        "backend": backend,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
            finally:
                if store is not None:
                    try:
                        store.delete_collection()
                    except Exception:
                        pass
                if temp_dir is not None:
                    temp_dir.cleanup()

    return {
        "parameters": {
            "backends": list(backends),
            "batch_size": batch_size,
            "collection_prefix": collection_prefix,
            "cleanup": cleanup,
        },
        "errors": errors,
        "document_inventory": inventory,
        "group_summary": group_stats,
        "ingestion": pd.concat(ingestion_frames, ignore_index=True)
        if ingestion_frames
        else pd.DataFrame(),
        "ingestion_batches": pd.concat(batch_frames, ignore_index=True)
        if batch_frames
        else pd.DataFrame(),
    }


def time_query_latency(
    store: VectorStore,
    backend: str,
    reference_answers: list[dict],
    query_embeddings: dict[str, np.ndarray],
    filter_cases: dict[str, dict[str, str] | None],
    k: int = 5,
    repeats: int = 3,
) -> pd.DataFrame:
    """Time top-k retrieval for each query/filter/repeat."""
    rows: list[dict[str, Any]] = []

    for filter_name, where in filter_cases.items():
        for repeat in range(1, repeats + 1):
            for entry in reference_answers:
                query = entry["query"]

                start = time.perf_counter()
                results = store.query(
                    embedding=query_embeddings[query],
                    k=k,
                    where=where,
                )
                seconds = time.perf_counter() - start

                rows.append(
                    {
                        "backend": backend,
                        "filter_name": filter_name,
                        "repeat": repeat,
                        "query": query,
                        "k": k,
                        "seconds": seconds,
                        "returned": len(results),
                        "top_chunk_id": results[0].chunk_id if results else None,
                        "top_score": results[0].score if results else None,
                    }
                )

    return pd.DataFrame(rows)


def collect_topk_results(
    store: VectorStore,
    backend: str,
    reference_answers: list[dict],
    query_embeddings: dict[str, np.ndarray],
    k: int = 5,
) -> pd.DataFrame:
    """Collect top-k IDs and scores for Recall@5 and ranking parity tables."""
    rows: list[dict[str, Any]] = []

    for entry in reference_answers:
        query = entry["query"]
        relevant_ids = set(entry["relevant_ids"])
        results = store.query(embedding=query_embeddings[query], k=k)

        for rank, result in enumerate(results, start=1):
            rows.append(
                {
                    "backend": backend,
                    "query": query,
                    "rank": rank,
                    "chunk_id": result.chunk_id,
                    "score": result.score,
                    "is_relevant": result.chunk_id in relevant_ids,
                    "text_preview": result.text[:160],
                }
            )

    return pd.DataFrame(rows)


def score_retrieval_quality(
    topk_results: pd.DataFrame,
    reference_answers: list[dict],
    k: int = 5,
) -> pd.DataFrame:
    """Compute Recall@k, Precision@k, and MRR from collected top-k rows."""
    if topk_results.empty:
        return pd.DataFrame()

    relevant_by_query = {
        entry["query"]: set(entry["relevant_ids"]) for entry in reference_answers
    }
    rows: list[dict[str, Any]] = []

    for (backend, query), group in topk_results.groupby(["backend", "query"]):
        group = group.sort_values("rank")
        relevant = relevant_by_query[query]
        retrieved = list(group["chunk_id"])
        hits = len(set(retrieved) & relevant)

        mrr = 0.0
        for rank, chunk_id in enumerate(retrieved, start=1):
            if chunk_id in relevant:
                mrr = 1.0 / rank
                break

        rows.append(
            {
                "backend": backend,
                "query": query,
                f"recall@{k}": hits / len(relevant) if relevant else 0.0,
                f"precision@{k}": hits / k,
                "mrr": mrr,
                "relevant_available": len(relevant),
                "relevant_returned": hits,
            }
        )

    return pd.DataFrame(rows)


def compare_rankings(topk_results: pd.DataFrame) -> pd.DataFrame:
    """Compare whether backends returned the same top-k IDs and order."""
    if topk_results.empty:
        return pd.DataFrame()

    grouped = topk_results.sort_values("rank").groupby(["backend", "query"])
    rankings = {
        (backend, query): list(group["chunk_id"])
        for (backend, query), group in grouped
    }
    backends = sorted(topk_results["backend"].unique())
    if len(backends) < 2:
        return pd.DataFrame()

    baseline = backends[0]
    rows: list[dict[str, Any]] = []
    for backend in backends[1:]:
        for query in sorted(topk_results["query"].unique()):
            baseline_ids = rankings.get((baseline, query), [])
            comparison_ids = rankings.get((backend, query), [])
            rows.append(
                {
                    "baseline_backend": baseline,
                    "comparison_backend": backend,
                    "query": query,
                    "same_order": baseline_ids == comparison_ids,
                    "same_set": set(baseline_ids) == set(comparison_ids),
                    "baseline_ids": baseline_ids,
                    "comparison_ids": comparison_ids,
                }
            )

    return pd.DataFrame(rows)


def run_backend_once(
    backend: str,
    config: PipelineConfig,
    model: SentenceTransformer,
    ids: list[str],
    texts: list[str],
    metadatas: list[dict[str, str]],
    reference_answers: list[dict],
    query_embeddings: dict[str, np.ndarray],
    batch_size: int,
    query_repeats: int,
    k: int,
    collection_prefix: str,
    cleanup: bool,
) -> dict[str, pd.DataFrame]:
    """Run one backend and return raw DataFrames for notebook display."""
    temp_dir = tempfile.TemporaryDirectory() if backend == "chroma" else None
    chroma_dir = temp_dir.name if temp_dir else None
    collection_name = f"{collection_prefix}_{backend}"

    store = make_store(backend, config, collection_name, chroma_dir=chroma_dir)
    store.delete_collection()
    store = make_store(backend, config, collection_name, chroma_dir=chroma_dir)

    try:
        ingestion, ingestion_batches = benchmark_ingestion(
            store=store,
            backend=backend,
            model=model,
            ids=ids,
            texts=texts,
            metadatas=metadatas,
            batch_size=batch_size,
        )
        filter_cases = build_filter_cases(metadatas)
        query_latency = time_query_latency(
            store=store,
            backend=backend,
            reference_answers=reference_answers,
            query_embeddings=query_embeddings,
            filter_cases=filter_cases,
            k=k,
            repeats=query_repeats,
        )
        topk_results = collect_topk_results(
            store=store,
            backend=backend,
            reference_answers=reference_answers,
            query_embeddings=query_embeddings,
            k=k,
        )
    finally:
        if cleanup:
            store.delete_collection()
        if temp_dir is not None:
            temp_dir.cleanup()

    return {
        "ingestion": ingestion,
        "ingestion_batches": ingestion_batches,
        "query_latency": query_latency,
        "topk_results": topk_results,
    }


def run_backend_benchmark(
    backends: tuple[str, ...] = ("chroma", "pgvector"),
    reference_path: str | Path = "reference_answers.json",
    batch_size: int = BATCH_SIZE,
    query_repeats: int = 3,
    k: int = 5,
    max_chunks: int | None = None,
    max_queries: int | None = None,
    collection_prefix: str = DEFAULT_BENCHMARK_COLLECTION,
    cleanup: bool = True,
) -> dict[str, Any]:
    """Run the notebook-first benchmark and return DataFrames, not files."""
    config = resolve_pipeline_config()
    inputs = load_benchmark_inputs(
        config=config,
        reference_path=reference_path,
        max_chunks=max_chunks,
        max_queries=max_queries,
    )

    id_prefix = f"{collection_prefix}__"
    ids = prefix_chunk_ids(inputs["ids"], id_prefix)
    reference_answers = prefix_reference_ids(inputs["reference_answers"], id_prefix)
    model = SentenceTransformer(config.embedding_model)
    query_embeddings = encode_queries(model, reference_answers)

    frames: dict[str, list[pd.DataFrame]] = {
        "ingestion": [],
        "ingestion_batches": [],
        "query_latency": [],
        "topk_results": [],
    }
    errors: list[dict[str, str]] = []

    for backend in backends:
        try:
            backend_frames = run_backend_once(
                backend=backend,
                config=config,
                model=model,
                ids=ids,
                texts=inputs["texts"],
                metadatas=inputs["metadatas"],
                reference_answers=reference_answers,
                query_embeddings=query_embeddings,
                batch_size=batch_size,
                query_repeats=query_repeats,
                k=k,
                collection_prefix=collection_prefix,
                cleanup=cleanup,
            )
        except Exception as exc:
            errors.append(
                {
                    "backend": backend,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
            continue

        for key, frame in backend_frames.items():
            frames[key].append(frame)

    results = {
        key: pd.concat(value, ignore_index=True) if value else pd.DataFrame()
        for key, value in frames.items()
    }
    retrieval_quality = score_retrieval_quality(
        results["topk_results"],
        reference_answers,
        k=k,
    )
    ranking_parity = compare_rankings(results["topk_results"])

    return {
        "parameters": {
            "backends": list(backends),
            "batch_size": batch_size,
            "query_repeats": query_repeats,
            "k": k,
            "max_chunks": max_chunks,
            "max_queries": max_queries,
            "chunks_benchmarked": len(ids),
            "reference_queries": len(reference_answers),
            "collection_prefix": collection_prefix,
            "benchmark_id_prefix": id_prefix,
            "cleanup": cleanup,
        },
        "errors": errors,
        **results,
        "retrieval_quality": retrieval_quality,
        "ranking_parity": ranking_parity,
        "metadata_filters": describe_filter_cases(inputs["metadatas"]),
        "deployment_complexity": deployment_complexity_metrics(),
        "code_legibility": code_legibility_metrics(),
    }


def summarise_results(results: dict[str, Any]) -> dict[str, pd.DataFrame]:
    """Return compact summary tables for notebook display."""
    summaries: dict[str, pd.DataFrame] = {}

    ingestion = results["ingestion"]
    if not ingestion.empty:
        summaries["ingestion_summary"] = ingestion.sort_values("backend")

    latency = results["query_latency"]
    if not latency.empty:
        summaries["query_latency_summary"] = (
            latency.groupby(["backend", "filter_name"], as_index=False)
            .agg(
                runs=("seconds", "count"),
                median_seconds=("seconds", "median"),
                mean_seconds=("seconds", "mean"),
                p95_seconds=("seconds", lambda values: values.quantile(0.95)),
                min_seconds=("seconds", "min"),
                max_seconds=("seconds", "max"),
            )
            .sort_values(["filter_name", "backend"])
        )

    quality = results["retrieval_quality"]
    if not quality.empty:
        recall_cols = [col for col in quality.columns if col.startswith("recall@")]
        precision_cols = [
            col for col in quality.columns if col.startswith("precision@")
        ]
        agg_spec: dict[str, tuple[str, str]] = {"mean_mrr": ("mrr", "mean")}
        if recall_cols:
            agg_spec[f"mean_{recall_cols[0]}"] = (recall_cols[0], "mean")
        if precision_cols:
            agg_spec[f"mean_{precision_cols[0]}"] = (precision_cols[0], "mean")
        summaries["retrieval_quality_summary"] = (
            quality.groupby("backend", as_index=False).agg(**agg_spec)
        )

    topk = results["topk_results"]
    if not topk.empty:
        summaries["score_summary"] = (
            topk.groupby("backend", as_index=False)
            .agg(
                returned_scores=("score", "count"),
                mean_score=("score", "mean"),
                median_score=("score", "median"),
                min_score=("score", "min"),
                max_score=("score", "max"),
            )
            .sort_values("backend")
        )

    parity = results["ranking_parity"]
    if not parity.empty:
        summaries["ranking_parity_summary"] = (
            parity.groupby(["baseline_backend", "comparison_backend"], as_index=False)
            .agg(
                queries_compared=("query", "count"),
                same_order_queries=("same_order", "sum"),
                same_set_queries=("same_set", "sum"),
            )
        )

    deployment = results["deployment_complexity"]
    if not deployment.empty:
        summaries["deployment_complexity_summary"] = deployment

    legibility = results["code_legibility"]
    if not legibility.empty:
        summaries["code_legibility_summary"] = legibility

    return summaries


def dataframe_to_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame to JSON-safe records."""
    if frame.empty:
        return []
    return json.loads(frame.to_json(orient="records"))


def write_results_json(
    results: dict[str, Any],
    path: str | Path = "evaluation_results.json",
) -> None:
    """Optional export after the notebook results look right."""
    summaries = summarise_results(results)
    payload = {
        "parameters": results["parameters"],
        "errors": results["errors"],
        "summaries": {
            name: dataframe_to_records(frame) for name, frame in summaries.items()
        },
        "ingestion": dataframe_to_records(results["ingestion"]),
        "ingestion_batches": dataframe_to_records(results["ingestion_batches"]),
        "query_latency": dataframe_to_records(results["query_latency"]),
        "retrieval_quality": dataframe_to_records(results["retrieval_quality"]),
        "topk_results": dataframe_to_records(results["topk_results"]),
        "ranking_parity": dataframe_to_records(results["ranking_parity"]),
        "metadata_filters": dataframe_to_records(results["metadata_filters"]),
        "deployment_complexity": dataframe_to_records(
            results["deployment_complexity"]
        ),
        "code_legibility": dataframe_to_records(results["code_legibility"]),
    }

    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def round_numeric_columns(frame: pd.DataFrame, decimals: int = 3) -> pd.DataFrame:
    """Return a display copy with numeric columns rounded."""
    display = frame.copy()
    numeric_cols = display.select_dtypes(include=["number"]).columns
    display[numeric_cols] = display[numeric_cols].round(decimals)
    return display


def latency_summary_for_console(summary: pd.DataFrame) -> pd.DataFrame:
    """Convert query latency seconds to a smaller, report-friendly table."""
    if summary.empty:
        return summary

    display = summary[
        ["backend", "filter_name", "runs", "median_seconds", "p95_seconds"]
    ].copy()
    display = display.rename(
        columns={
            "median_seconds": "median_ms",
            "p95_seconds": "p95_ms",
        }
    )
    display["median_ms"] = display["median_ms"] * 1000
    display["p95_ms"] = display["p95_ms"] * 1000
    return round_numeric_columns(display, decimals=2)


def ingestion_summary_for_console(summary: pd.DataFrame) -> pd.DataFrame:
    """Keep the ingestion table focused on the headline timing numbers."""
    if summary.empty:
        return summary

    display = summary[
        [
            "backend",
            "chunks",
            "total_embed_and_store_seconds",
            "embed_seconds",
            "store_add_seconds",
            "chunks_per_second_total",
            "chunks_per_second_store_only",
        ]
    ].copy()
    return round_numeric_columns(display, decimals=2)


def print_frame(title: str, frame: pd.DataFrame) -> None:
    """Print a DataFrame only when it has rows."""
    if frame.empty:
        return
    print(f"\n{title}")
    print(frame.to_string(index=False))


def print_console_report(results: dict[str, Any]) -> None:
    """Print a decision-oriented benchmark report for terminal runs."""
    summaries = summarise_results(results)
    parameters = results["parameters"]

    print("\nBenchmark Overview")
    print(f"chunks benchmarked: {parameters['chunks_benchmarked']}")
    print(f"reference queries: {parameters['reference_queries']}")
    print(f"top-k: {parameters['k']}")
    print(f"query repeats: {parameters['query_repeats']}")

    if results["errors"]:
        print_frame("Errors", pd.DataFrame(results["errors"]))

    parity = summaries.get("ranking_parity_summary", pd.DataFrame())
    quality = summaries.get("retrieval_quality_summary", pd.DataFrame())
    latency = summaries.get("query_latency_summary", pd.DataFrame())
    ingestion = summaries.get("ingestion_summary", pd.DataFrame())

    print("\nInterpretation")
    if not parity.empty:
        same_order = int(parity["same_order_queries"].sum())
        compared = int(parity["queries_compared"].sum())
        print(f"- Ranking parity: {same_order}/{compared} queries returned the same top-k order.")

    if not quality.empty:
        metric_cols = [col for col in quality.columns if col != "backend"]
        rounded_quality = round_numeric_columns(quality, decimals=3)
        quality_line = "; ".join(
            f"{row['backend']}: "
            + ", ".join(f"{col}={row[col]:.3f}" for col in metric_cols)
            for _, row in rounded_quality.iterrows()
        )
        print(f"- Retrieval quality: {quality_line}.")

    if not latency.empty:
        unfiltered = latency[latency["filter_name"] == "unfiltered"]
        if not unfiltered.empty:
            winner = unfiltered.loc[unfiltered["median_seconds"].idxmin()]
            print(
                "- Fastest unfiltered query median: "
                f"{winner['backend']} at {winner['median_seconds'] * 1000:.2f} ms."
            )

    if not ingestion.empty:
        winner = ingestion.loc[ingestion["total_embed_and_store_seconds"].idxmin()]
        print(
            "- Fastest total embed+store run: "
            f"{winner['backend']} at {winner['total_embed_and_store_seconds']:.2f} seconds."
        )

    print_frame(
        "Retrieval Quality",
        round_numeric_columns(quality, decimals=3),
    )
    print_frame(
        "Query Latency",
        latency_summary_for_console(latency),
    )
    print_frame(
        "Ingestion Throughput",
        ingestion_summary_for_console(ingestion),
    )
    print_frame(
        "Ranking Parity",
        parity,
    )
    print_frame(
        "Deployment Complexity",
        summaries.get("deployment_complexity_summary", pd.DataFrame()),
    )
    print_frame(
        "Code Legibility",
        round_numeric_columns(
            summaries.get("code_legibility_summary", pd.DataFrame()),
            decimals=2,
        ),
    )


if __name__ == "__main__":
    benchmark_results = run_backend_benchmark()
    print_console_report(benchmark_results)
