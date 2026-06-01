# Evaluation Handoff

This handoff summarizes the ChromaDB vs pgvector evaluation work and where to
look when writing the final report.

## What Was Added

- Added a shared pytest suite for both vector stores.
  - Files: `tests/`, `pytest.ini`
  - Purpose: checks that ChromaDB and pgvector both support the same basic
    operations before we compare speed.

- Expanded `benchmark_metrics.py`.
  - Main benchmark: retrieval quality, query latency, ingestion throughput,
    metadata filters, deployment complexity, and code complexity.
  - Added document-size ingestion helpers:
    - below 60 pages vs 60+ pages
    - closest to 20 pages vs closest to 60 pages

- Organized the evaluation documentation.
  - Main summary: `docs/evaluation/benchmark_results.md`
  - Manual reference-label notes: `docs/evaluation/reference_answers_review.md`
  - Detailed run notes: `docs/evaluation/evaluation_notebook_doc.md`

- Documented that the reference chunks were manually selected.
  - I inspected PDFs and full chunk text, then manually added the correct
    `chunk_id` values to `reference_answers.json`.

## Where To Look First

Start here:

```text
docs/evaluation/benchmark_results.md
```

That file has the cleanest summary of:

- retrieval quality
- query speed
- ingestion speed
- document-size benchmarks
- deployment/code complexity
- recommendation
- commands to reproduce the results

It also has a **Numerical Summary** section near the top. Use that section for
the report's main analysis: it states the winner for each dimension and gives
the key numbers Sylvan asked for.

For how the labelled reference set was created, read:

```text
docs/evaluation/reference_answers_review.md
```

For extra notes from the local notebook-style run, read:

```text
docs/evaluation/evaluation_notebook_doc.md
```

## Current Findings

- Retrieval quality is tied.
  - ChromaDB and pgvector returned the same top-5 order for all 20 reference
    queries.
  - Mean recall@5, precision@5, and MRR were identical.

- ChromaDB is faster for the measured query-latency modes in the latest run,
  especially unfiltered retrieval.
  - This supports ChromaDB as the easier laptop default.

- pgvector is faster for ingestion.
  - This showed up in the full-corpus benchmark and the document-size ingestion
    benchmarks.

- ChromaDB is simpler to deploy.
  - It does not require Docker/Postgres.
  - pgvector requires Docker Compose, Postgres, and Alembic migrations.

For the numerical version of these findings, use:

```text
docs/evaluation/benchmark_results.md
```

The most report-ready numbers are in the sections titled `Numerical Summary`,
`Query Speed`, `Full-Corpus Ingestion Speed`, and the two document-size
benchmark sections.

## Suggested Report Recommendation

Recommend ChromaDB as the default for social science researchers running
TPI-style retrieval on a university laptop.

Reason: retrieval quality is identical, ChromaDB is much simpler to set up, and
query latency is lower in the current benchmark.

Say pgvector should be reconsidered if the team needs:

- relational joins with structured metadata
- stronger Postgres-native filtering
- an existing production Postgres deployment
- bulk ingestion speed as the main priority

## Commands To Reproduce

Start pgvector:

```bash
docker compose up -d
alembic upgrade head
```

Run correctness tests:

```bash
python -m pytest
```

Run the main benchmark:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python benchmark_metrics.py
```

Run the document-size benchmark helpers in Python or the notebook:

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

## What Is Left

- Write the final recommendation report to Sylvan.
- Decide whether to run one extra exact single-document benchmark for one
  near-20-page PDF and one exact 60-page PDF. Current results use document
  cohorts, which are useful, but not exactly the single-document wording.
- Make sure the final report cites `docs/evaluation/benchmark_results.md`.
- If submitting the repo, commit and push the current changes.
