# Contributing

This document is for developers who want to understand the pipeline internals, fix bugs, or extend the codebase. **README.md** is the entry point: clone, install, add PDFs, and run. This file is for people who will change or extend the code.

## Project layout

See [README.md#project-layout](README.md#project-layout) for the full repository tree. Key areas for contributors: root stage modules, `vector_store/`, `evaluation/`, `notebooks/`, `tests/`, `docs/`, and `alembic/` (pgvector only).

## How the pipeline works

The pipeline has four stages, orchestrated by `pipeline.py` (a Click CLI):

```
extract.py    PDF extraction with unstructured, chunking to JSONL
embed.py      Sentence-transformer encoding, stores via VectorStore interface
retrieve.py   Two-stage retrieval: bi-encoder broad pass, cross-encoder rerank
generate.py   Prompt construction and text generation with HuggingFace
```

Data flows linearly: PDFs -> `.pkl` element caches -> `.jsonl` chunks -> vector store -> `list[QueryResult]` -> cited answer string.

`embed.py` and `retrieve.py` depend on the `vector_store/` package. `extract.py` and `generate.py` do not touch the vector store directly. Shared configuration and chunking logic live in `utils.py`.

The `vector_store/` package provides a backend-agnostic interface:

```
vector_store/
  types.py       VectorStore Protocol, QueryResult and CollectionInfo dataclasses
  factory.py     Reads VECTOR_STORE from .env, returns the matching backend
  chroma.py      ChromaDB implementation
  pgvector.py    Postgres + pgvector implementation
  db.py          SQLAlchemy schema for chunk_records (pgvector backend)
```

`factory.py` uses lazy imports so the chroma path doesn't require pgvector packages installed, and vice versa. Key design decisions are documented in [DECISIONS.md](DECISIONS.md).

## Known bugs and areas for improvement

- **Low retrieval precision (~0.18 @ k=5).** Mean precision@5 on the 20-query reference set is about **0.18** (recall@5 ~0.43). Both backends score the same — this is a pipeline/model/chunking limitation, not a Chroma vs pgvector issue. See [docs/evaluation/benchmark_results.md#retrieval-accuracy-limitations](docs/evaluation/benchmark_results.md#retrieval-accuracy-limitations) for interpretation and improvement directions.
- `bitsandbytes` does not work on macOS Apple Silicon. Generation runs without quantisation on Mac.
- The current local cross-encoder can return non-finite scores. `retrieve.py` falls back to the bi-encoder order in that case. Backend benchmarking uses bi-encoder retrieval only, so this does not affect the ChromaDB vs pgvector comparison.

## Development setup

Follow [README.md#quick-start](README.md#quick-start) for clone, conda environment creation, and `.env` setup.

Prerequisites beyond the README:

- Git with SSH access to the `lse-ds205` GitHub org
- TPI Carbon Performance PDFs (from the team SharePoint folder linked in the project brief)

Tested on macOS Apple Silicon (M2, 16GB RAM). System dependencies (`poppler`, `tesseract`, `pandoc`) are handled by conda.

Optional variables with defaults are documented in `utils.py` inside `resolve_pipeline_config()`.

## Configuration

All runtime settings come from `.env`. Copy `.env.example` to get started.

| Variable | Required | What it does |
|----------|----------|--------------|
| `PDF_SOURCE_DIR` | Yes | Parent directory with one subfolder per company |
| `VECTOR_STORE` | Yes | `chroma` or `pgvector` |
| `CHROMA_DIR` | When using chroma | Path to ChromaDB storage (default `data/chromadb`) |
| `PG_CONNECTION_STRING` | When using pgvector | SQLAlchemy URL, e.g. `postgresql+psycopg://...` |
| `DATABASE_URL` | When using pgvector | Same Postgres URL for Alembic migrations |
| `COLLECTION_NAME` | No | Vector store collection name (default `tpi_vectors`) |
| `OUTPUT_DIR` | No | Interim extract/chunk output (default `data/interim`) |
| `PDF_GLOB` | No | PDF filename pattern (default `*.pdf`) |
| `EMBEDDING_MODEL` | No | HuggingFace embedding model |
| `RERANKING_MODEL` | No | Cross-encoder for retrieve stage |
| `GENERATION_MODEL` | No | HuggingFace generation model |
| `HF_HOME` | No | HuggingFace cache directory |
| `HF_TOKEN` | No | HuggingFace token (optional; speeds downloads) |
| `POSTGRES_*` | When using pgvector | Must match `docker-compose.yml` |

Evaluation data paths (defaults via `evaluation/paths.py`):

| File | Purpose |
|------|---------|
| `evaluation/reference_answers.json` | Manual Recall@5 reference queries |
| `evaluation/document_metadata.json` | Company/year/sector overrides for embedding |
| `evaluation/evaluation_results.json` | Optional notebook export (empty `{}` until regenerated) |

Pipeline output directories (`data/` is gitignored) are listed in [README.md#project-layout](README.md#project-layout).

## CLI reference

Entry point: `python pipeline.py <command>`

| Command | Description |
|---------|-------------|
| `extract` | Extract PDFs and write chunks to `data/interim/` |
| `embed` | Embed chunks and upsert into the configured vector store |
| `retrieve` | Print top retrieved chunks for a query |
| `generate` | Retrieve chunks and print a cited generated answer |
| `run-all` | Run extract → embed → retrieve → generate in sequence |

Options:

| Option | Commands | Description |
|--------|----------|-------------|
| `--query`, `-q` | `retrieve`, `generate`, `run-all` | Question text (defaults to a built-in example query) |

Examples:

```bash
python pipeline.py run-all -q "What are Hershey Company's emissions targets?"
python pipeline.py extract
python pipeline.py embed
python pipeline.py retrieve -q "What are the emissions targets?"
python pipeline.py generate -q "What are the emissions targets?"
```

## Running tests

The pytest suite checks the shared vector-store contract against ChromaDB and pgvector. It uses a tiny synthetic 384-dimensional dataset, so it does not embed PDFs or touch the production `tpi_vectors` collection.

```bash
python -m pytest
```

pgvector tests require Docker/Postgres and the Alembic schema:

```bash
docker compose up -d
alembic upgrade head
python -m pytest
```

If Postgres is not available, pgvector tests skip and ChromaDB tests still run.

## Evaluation and benchmarks

The submitted evaluation compares ChromaDB and pgvector on the same corpus and reference set. Detailed tables, interpretation, and the Chroma recommendation are in [docs/evaluation/benchmark_results.md](docs/evaluation/benchmark_results.md). Labelling rules and reference-set summary: [docs/evaluation/reference_answers_review.md](docs/evaluation/reference_answers_review.md). Run notes: [docs/evaluation/evaluation_notebook_doc.md](docs/evaluation/evaluation_notebook_doc.md).

Reference set at submission: 20 manually labelled queries, 15 companies, 17 PDFs, 5,913 chunks (see `evaluation/reference_answers.json`). Benchmarks use bi-encoder top-k retrieval before cross-encoder reranking.

**Correctness check** (vector-store contract):

```bash
python -m pytest
```

**Full backend benchmark** (timing, retrieval quality, deployment, code legibility):

```bash
docker compose up -d
alembic upgrade head
python scripts/check_pgvector.py
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python benchmark_metrics.py
```

**Notebook workflow** (pandas tables, optional JSON export):

Open [notebooks/benchmark_exploration.ipynb](notebooks/benchmark_exploration.ipynb) from the repo root (or use the notebook's `REPO_ROOT` setup cell). The notebook uses temporary benchmark collections and cleans them up after each run. To export results after reviewing tables:

```python
write_results_json(results)
```

To inspect chunks or extend labels, use [notebooks/reference_answer_builder.ipynb](notebooks/reference_answer_builder.ipynb) and follow [reference_answers_review.md](docs/evaluation/reference_answers_review.md).

Timing is machine-dependent. Re-run the benchmark commands above to reproduce numbers on your hardware.

## Adding new documents

Create a subfolder in `PDF_SOURCE_DIR` named after the company, using underscores for spaces:

```
data/pdfs/
  Hershey_Company/
    report_2023.pdf
  Your_New_Company/
    report_2024.pdf
```

The pipeline discovers companies from folder names at runtime. Underscores are replaced by spaces in company labels. No code or `.env` change needed. Run `python pipeline.py extract` to process the new documents.

## Code style

- Typed Python: all function signatures have type hints
- Ruff for linting
- `logging` module, not `print()`, for pipeline output
- Configuration via `.env`, never hardcoded paths
- British spelling in documentation

Commit messages should be short, imperative summaries such as
`Add pgvector contract tests` or `Update evaluation benchmark notes`. Use a
separate branch for larger changes when coordinating with teammates, and keep
generated data out of commits unless the team explicitly decides otherwise.

## pgvector backend (Docker + Postgres)

Use this when `VECTOR_STORE=pgvector`. ChromaDB (`VECTOR_STORE=chroma`) does not require Docker.

### Prerequisites

- [Docker Desktop](https://docs.docker.com/desktop/) installed and running
- conda env `project-d` (includes `sqlalchemy`, `pgvector`, `psycopg`, `alembic`)

### Step 1 - Configure `.env`

```bash
cp .env.example .env
```

Set at minimum:

```bash
VECTOR_STORE=pgvector
PG_CONNECTION_STRING=postgresql+psycopg://tpi:change-me-local-only@localhost:5432/tpi_vectors
DATABASE_URL=postgresql+psycopg://tpi:change-me-local-only@localhost:5432/tpi_vectors
PDF_SOURCE_DIR=data/pdfs
```

`POSTGRES_*` variables must match `docker-compose.yml` credentials.

### Step 2 - Start Postgres

```bash
docker compose up -d
docker compose ps    # wait until STATUS is "healthy"
```

Image: `pgvector/pgvector:0.7.1-pg16` (same family as the CLEAR reference repo).

### Step 3 - Run migrations

From the repo root with `project-d` active:

```bash
alembic upgrade head
```

Creates `chunk_records` with `embedding vector(384)`, `collection_name`, and `metadata jsonb`.

### Step 4 - Smoke test

```bash
python scripts/check_pgvector.py
```

Expected final line: `Smoke test passed.`

### Step 5 - Run the pipeline on pgvector

```bash
python pipeline.py extract
VECTOR_STORE=pgvector python pipeline.py embed
VECTOR_STORE=pgvector python pipeline.py retrieve -q "What are AGL's emissions targets?"
```

Or set `VECTOR_STORE=pgvector` in `.env` so you do not need the prefix on each command.

Re-running `embed` is safe: `pgvector.py` uses upsert (`ON CONFLICT DO UPDATE`).

### Troubleshooting

| Problem | Fix |
|---------|-----|
| `port is already allocated` | Change `POSTGRES_PORT` in `.env` and both connection strings |
| `PG_CONNECTION_STRING must be set` | Add it to `.env` when using pgvector |
| `ModuleNotFoundError: psycopg2` | Use `postgresql+psycopg://...` (psycopg v3), not bare `postgresql://` |
| Container not healthy | `docker compose logs postgres`; wait 10–20s on first start |
| Reset database completely | `docker compose down -v` then repeat Steps 2–4 |

### Schema reference

```
chunk_records
  chunk_id        varchar(128) UNIQUE
  content         text
  embedding       vector(384)
  collection_name varchar(128)
  metadata        jsonb   - keys: company, source_file, strategy, pages, year, sector
```

See [docs/README.md](docs/README.md) for the documentation index, [docs/handoff/HANDOFF.md](docs/handoff/HANDOFF.md) for team handoff notes, and [docs/agent/RULES.md](docs/agent/RULES.md) for coding conventions.
