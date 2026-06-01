# Benchmark Results

This is the main place to read the ChromaDB vs pgvector evaluation results.
The benchmark code lives in `benchmark_metrics.py`; this file explains the
outputs in one place.

## What Counts As A Test

There are two different kinds of checks in this project:

| Check | Command | Purpose |
|-------|---------|---------|
| Correctness suite | `python -m pytest` | Confirms both backends obey the same vector-store contract |
| Benchmark suite | `python benchmark_metrics.py` and notebook helpers | Measures speed, retrieval quality, filtering, deployment, and code complexity |

The pytest output is not the performance evaluation. It is the trust check before
benchmarking.

## Current Corpus

| Item | Count |
|------|------:|
| Companies | 15 |
| PDFs | 17 |
| Chunks | 5,913 |
| Reference queries | 20 |
| Missing reference chunk IDs | 0 |

Both stores were populated with the full corpus:

| Store | Chunks |
|-------|------:|
| ChromaDB | 5,913 |
| pgvector | 5,913 |

## Numerical Summary

| Dimension | Winner | Numerical evidence |
|-----------|--------|--------------------|
| Retrieval quality | Tie | Same recall@5, precision@5, MRR, and same top-5 order on 20 / 20 queries |
| Query latency | ChromaDB | Average median across filter modes: 3.93 ms for ChromaDB vs 8.97 ms for pgvector |
| Full-corpus ingestion | pgvector | 32.86 sec vs 37.47 sec; 179.93 vs 157.79 chunks/sec |
| Document-size ingestion | pgvector | Faster in below-60, 60+, closest-to-20, and closest-to-60 page groups |
| Deployment complexity | ChromaDB | 0 extra services vs 1; 2 setup steps vs 5 |
| Code legibility | ChromaDB | 110 lines / 5 imports vs 174 lines / 11 imports |

This means the backend choice is not about accuracy in the current pipeline.
Accuracy tied exactly. The trade-off is speed and setup: ChromaDB is easier and
faster for common query use, while pgvector is stronger for ingestion and future
relational database integration.

## Retrieval Quality

Full benchmark command:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python benchmark_metrics.py
```

Benchmark settings:

| Setting | Value |
|---------|------:|
| Chunks benchmarked | 5,913 |
| Reference queries | 20 |
| Top-k | 5 |
| Query repeats | 3 |

Retrieval quality:

| Metric | ChromaDB | pgvector |
|--------|---------:|---------:|
| Mean MRR | 0.412 | 0.412 |
| Mean recall@5 | 0.427 | 0.427 |
| Mean precision@5 | 0.180 | 0.180 |
| Same top-5 order | 20 / 20 | 20 / 20 |

Interpretation: retrieval quality is identical in this benchmark. The two
backends store the same vectors and return the same ranked chunks.

The reference set behind these scores was manually labelled. Questions were
written from source PDF passages, candidate chunks were searched and inspected in
`notebooks/reference_answer_builder.ipynb`, and the selected `chunk_id` values were added
to `evaluation/reference_answers.json` by hand. See
[`reference_answers_review.md`](reference_answers_review.md) for the labelling
workflow.

Numerical takeaway: backend choice changed none of the retrieval-quality metrics.
The difference was `0.000` for mean recall@5, precision@5, and MRR.

## Retrieval accuracy limitations

**Important:** The benchmark shows **identical** retrieval between ChromaDB and pgvector, but **absolute accuracy is modest**. On the 20-query reference set at `k=5`:

| Metric | Value | Plain-language meaning |
|--------|------:|------------------------|
| Mean precision@5 | **~0.18** | On average, only about **1–2 of the top 5** retrieved chunks are labelled relevant |
| Mean recall@5 | **~0.43** | On average, the top 5 retrieve roughly **43%** of all chunks marked relevant for a query |
| Mean MRR | **~0.41** | The first relevant hit often appears around **rank 2–3**, not rank 1 |

These numbers reflect the **current end-to-end pipeline** (PDF extraction, chunking, `multi-qa-MiniLM-L6-cos-v1` bi-encoder, manual reference labels) — **not** a difference between vector stores. Do not interpret low precision as evidence that one backend is worse than the other.

**Possible improvements** (not implemented in this submission):

- Stronger **embedding** or **reranking** models (e.g. larger sentence-transformers or domain-tuned encoders)
- **Chunking** changes (size, overlap, table-aware splitting, section boundaries)
- **Hybrid retrieval** (dense + keyword/BM25) or metadata-first filtering before vector search
- **Query rewriting** or multi-query expansion (tested briefly; did not beat natural-language queries on the AGL subset — see DECISIONS.md)
- Richer **reference labels** or higher `k` if users need more complete recall

Re-run `python benchmark_metrics.py` or `notebooks/benchmark_exploration.ipynb` after any pipeline change to measure impact on these metrics.

## Query Speed

Median and p95 query latency:

| Backend | Filter | Runs | Median ms | p95 ms |
|---------|--------|-----:|----------:|-------:|
| ChromaDB | company | 60 | 5.14 | 5.71 |
| pgvector | company | 60 | 6.67 | 9.32 |
| ChromaDB | sector | 60 | 4.28 | 5.65 |
| pgvector | sector | 60 | 7.35 | 11.15 |
| ChromaDB | unfiltered | 60 | 1.01 | 1.32 |
| pgvector | unfiltered | 60 | 15.58 | 21.23 |
| ChromaDB | year | 60 | 5.30 | 5.71 |
| pgvector | year | 60 | 6.26 | 9.42 |

Interpretation: ChromaDB is faster across the measured query modes in this run,
with the largest gap on unfiltered retrieval.

Numerical takeaway:

- Unfiltered query median: ChromaDB was about 15.4x faster.
- Company filter median: ChromaDB was about 23% lower latency.
- Sector filter median: ChromaDB was about 42% lower latency.
- Year filter median: ChromaDB was about 15% lower latency.
- Average median across all four filter modes: ChromaDB was about 56% lower
  latency.

## Full-Corpus Ingestion Speed

| Backend | Chunks | Total embed+store sec | Embed sec | Store sec | Total chunks/sec | Store-only chunks/sec |
|---------|------:|----------------------:|----------:|----------:|-----------------:|----------------------:|
| ChromaDB | 5,913 | 37.47 | 33.01 | 4.47 | 157.79 | 1,323.96 |
| pgvector | 5,913 | 32.86 | 30.05 | 2.82 | 179.93 | 2,099.87 |

Interpretation: pgvector was faster for full-corpus ingestion, especially for
the store-only portion.

Numerical takeaway:

- pgvector was about 12.3% faster by total ingestion seconds.
- pgvector had about 14.0% higher total chunks/sec.
- pgvector had about 58.6% higher store-only chunks/sec.

## Document Size Benchmark 1: Below 60 vs 60+ Pages

This groups PDFs by a 60-page threshold.

Run:

```python
from benchmark_metrics import run_page_group_ingestion_benchmark

results = run_page_group_ingestion_benchmark(page_threshold=60)
```

Group summary:

| Page group | PDFs | Total pages | Mean pages | Chunks |
|------------|----:|------------:|-----------:|------:|
| Below 60 pages | 8 | 133 | 16.625 | 916 |
| 60 pages or more | 9 | 1,068 | 118.667 | 4,997 |

Ingestion by page group:

| Page group | Backend | PDFs | Pages | Chunks | Total sec | Embed sec | Store sec | Total chunks/sec | Store-only chunks/sec |
|------------|---------|----:|------:|------:|----------:|----------:|----------:|-----------------:|----------------------:|
| Below 60 pages | ChromaDB | 8 | 133 | 916 | 6.006 | 5.380 | 0.626 | 152.516 | 1,464.376 |
| Below 60 pages | pgvector | 8 | 133 | 916 | 4.114 | 3.635 | 0.478 | 222.662 | 1,914.705 |
| 60 pages or more | ChromaDB | 9 | 1,068 | 4,997 | 31.861 | 27.964 | 3.896 | 156.840 | 1,282.558 |
| 60 pages or more | pgvector | 9 | 1,068 | 4,997 | 28.938 | 26.188 | 2.750 | 172.677 | 1,817.117 |

Interpretation: pgvector was faster for ingestion in both page-size groups.
Because the groups contain different numbers of chunks, chunks/sec is more useful
than total seconds alone.

## Document Size Benchmark 2: Closest To 20 Pages vs Closest To 60 Pages

This assigns each PDF to whichever target page count it is closer to: 20 pages or
60 pages.

Run:

```python
from benchmark_metrics import run_page_target_ingestion_benchmark

results = run_page_target_ingestion_benchmark(page_targets=(20, 60))
```

Group summary:

| Target group | PDFs | Total pages | Mean pages | Mean distance from target | Chunks |
|--------------|----:|------------:|-----------:|--------------------------:|------:|
| Closest to 20 pages | 7 | 85 | 12.143 | 7.857 | 636 |
| Closest to 60 pages | 10 | 1,116 | 111.600 | 54.000 | 5,277 |

Ingestion by closest page target:

| Target group | Backend | PDFs | Pages | Chunks | Total sec | Embed sec | Store sec | Total chunks/sec | Store-only chunks/sec |
|--------------|---------|----:|------:|------:|----------:|----------:|----------:|-----------------:|----------------------:|
| Closest to 20 pages | ChromaDB | 7 | 85 | 636 | 4.227 | 3.827 | 0.400 | 150.445 | 1,588.303 |
| Closest to 20 pages | pgvector | 7 | 85 | 636 | 2.888 | 2.594 | 0.293 | 220.254 | 2,167.856 |
| Closest to 60 pages | ChromaDB | 10 | 1,116 | 5,277 | 33.696 | 29.793 | 3.902 | 156.606 | 1,352.224 |
| Closest to 60 pages | pgvector | 10 | 1,116 | 5,277 | 29.604 | 27.227 | 2.377 | 178.253 | 2,219.571 |

Interpretation: pgvector was faster for ingestion in both closest-target groups.
The closest-to-60 group includes much longer reports, including one 336-page
annual report, so describe this as a cohort benchmark rather than a pure
60-page-only condition.

Numerical takeaway:

- Closest-to-20 group: pgvector had about 46% higher chunks/sec.
- Closest-to-60 group: pgvector had about 14% higher chunks/sec.

## Deployment And Code Complexity

Deployment complexity:

| Backend | Extra services | Compose lines | Clean-machine backend steps |
|---------|---------------:|--------------:|----------------------------:|
| ChromaDB | 0 | 0 | 2 |
| pgvector | 1 | 26 | 5 |

Backend implementation size:

| Backend | File | Lines | Imports | Max radon complexity | Mean radon complexity |
|---------|------|------:|--------:|---------------------:|----------------------:|
| ChromaDB | `vector_store/chroma.py` | 110 | 5 | 4 | 2.14 |
| pgvector | `vector_store/pgvector.py` | 174 | 11 | 6 | 2.50 |

Interpretation: pgvector adds Docker/Postgres setup and a larger implementation.
ChromaDB is simpler to run on a laptop.

Numerical takeaway:

- pgvector has 2.5x as many clean-machine setup steps.
- pgvector has about 58% more backend implementation lines.
- pgvector has about 120% more imports.
- pgvector's max radon complexity is 50% higher.

## Recommendation

For a team of social science researchers running TPI-style retrieval on a
university laptop, ChromaDB is the better default. Retrieval quality is identical
to pgvector, query latency is lower in the current benchmark, and setup is
simpler.

pgvector becomes more attractive if the project needs relational joins, stronger
metadata querying inside Postgres, an existing production Postgres deployment, or
bulk ingestion speed as the dominant constraint.

## How To Reproduce

Start pgvector:

```bash
docker compose up -d
alembic upgrade head
```

Run correctness tests:

```bash
python -m pytest
```

Run the full backend benchmark:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python benchmark_metrics.py
```

Run the two document-size benchmarks from a notebook or Python shell:

```python
from benchmark_metrics import (
    document_page_inventory,
    run_page_group_ingestion_benchmark,
    run_page_target_ingestion_benchmark,
)

page_inventory = document_page_inventory()
threshold_results = run_page_group_ingestion_benchmark(page_threshold=60)
target_results = run_page_target_ingestion_benchmark(page_targets=(20, 60))
```
