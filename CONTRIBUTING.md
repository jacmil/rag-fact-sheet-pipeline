# Contributing

This document is for developers who want to understand the pipeline internals, fix bugs, or extend the codebase. For usage instructions, see README.md.

## How the pipeline works

The pipeline has four stages, orchestrated by `pipeline.py` (a Click CLI):

```
extract.py    PDF extraction with unstructured, chunking to JSONL
embed.py      Sentence-transformer encoding, stores via VectorStore interface
retrieve.py   Two-stage retrieval: bi-encoder broad pass, cross-encoder rerank
generate.py   Prompt construction and text generation with HuggingFace
```

Data flows linearly: PDFs → `.pkl` element caches → `.jsonl` chunks → vector store → `list[QueryResult]` → cited answer string.

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

`factory.py` uses lazy imports so the chroma path doesn't require pgvector packages installed, and vice versa. Key design decisions are documented in DECISIONS.md.

## Known bugs and areas for improvement

- `bitsandbytes` does not work on macOS Apple Silicon. Generation runs without quantisation on Mac.

## Setting up the development environment

### Prerequisites

- conda (Miniconda or Anaconda)
- Git with SSH access to the `lse-ds205` GitHub org
- TPI Carbon Performance PDFs (from the SharePoint folder linked in the project brief)

Tested on macOS Apple Silicon (M2, 16GB RAM). System dependencies (`poppler`, `tesseract`, `pandoc`) are handled by conda.

### Installation

```bash
# 1. Clone the repository
git clone git@github.com:lse-ds205/group-project-json-derulo-comeback-tour.git
cd group-project-json-derulo-comeback-tour

# 2. Create and activate the conda environment
conda env create -f environment.yml
conda activate project-d
```

> **Note:** conda environment creation takes 25-30 minutes on the pip dependency resolution step. This is normal; don't kill it.

```bash
# 3. Set up environment variables
cp .env.example .env
# Edit .env to set PDF_SOURCE_DIR and any other config
```

Required `.env` variables:

| Variable | What it does |
|----------|-------------|
| `VECTOR_STORE` | `chroma` or `pgvector` |
| `CHROMA_DIR` | Path to ChromaDB storage directory |
| `PG_CONNECTION_STRING` | Postgres URL when `VECTOR_STORE=pgvector` (use `postgresql+psycopg://…`) |
| `DATABASE_URL` | Same Postgres URL for Alembic migrations |
| `PDF_SOURCE_DIR` | Parent directory containing one subfolder per company |
| `COLLECTION_NAME` | Collection name for the vector store |
| `HF_TOKEN` | HuggingFace access token (speeds up model downloads) |

Optional variables with defaults are documented in `utils.py` inside `resolve_pipeline_config()`.

### Running the pipeline

```bash
# Full pipeline
python pipeline.py run-all --query "What are the emissions targets for Hershey Company?"

# Individual stages
python pipeline.py extract
python pipeline.py embed
python pipeline.py retrieve --query "What are the emissions targets?"
python pipeline.py generate --query "What are the emissions targets?"
```

### Running tests

> **TODO**: Test suite not yet written. Will be added by the benchmarking teammate as a parametrised pytest suite that runs against both backends.

### Running the reference answer evaluation

`reference_answers.json` contains queries with manually verified chunk IDs from the AGL test document. To run bi-encoder retrieval evaluation against it:

```bash
python -c "
import json
from sentence_transformers import SentenceTransformer
from vector_store import get_vector_store
from utils import resolve_pipeline_config, PipelineConfig, evaluate_retrieval

config = resolve_pipeline_config()
store = get_vector_store(config.collection_name)
model = SentenceTransformer(config.embedding_model)

with open('reference_answers.json') as f:
    ground_truth = json.load(f)

df = evaluate_retrieval(ground_truth, store, model, k=5)
print(df.to_string(index=False))
"
```

This evaluates bi-encoder retrieval only (no cross-encoder reranking). The reference set is designed for backend equivalence testing: run the same script with `VECTOR_STORE=chroma` and `VECTOR_STORE=pgvector` and compare numbers.

**pgvector baseline (AGL document, bi-encoder, k=5):**

| Query | recall@5 |
|-------|----------|
| Emissions targets | 0.25 |
| Power stations | 1.00 |
| Renewables investment | 1.00 |

pgvector must match these ChromaDB numbers. If they diverge, check upsert logic and cosine score conversion in `vector_store/pgvector.py`.

### Data directories

`data/` is in `.gitignore`. The pipeline creates:

- `data/interim/raw/` — pickle caches of extracted PDF elements
- `data/interim/chunks/` — JSONL chunk files
- `data/chromadb/` — ChromaDB persistent storage

All reproducible from source PDFs by re-running the pipeline.

## Adding new documents

Create a subfolder in `PDF_SOURCE_DIR` named after the company, using underscores for spaces:

```
data/pdfs/
  Hershey_Company/
    report_2023.pdf
  Nomad_Foods/
    report_2023.pdf
  Your_New_Company/
    report_2024.pdf
```

The pipeline discovers companies from folder names at runtime. Underscores are replaced by spaces in company labels. No code or `.env` change needed. Run `python pipeline.py extract` to process the new documents.

## Adding a new vector store backend

1. Create `vector_store/your_backend.py` implementing all methods from `VectorStore` in `types.py`
2. Add a branch in `factory.py` for your backend name
3. Run the existing test suite against your implementation

The interface accepts numpy arrays for embeddings and returns `list[QueryResult]`. Scores should be cosine similarity (higher = more similar). If the underlying store returns distances, convert inside your implementation.

## Code style

- Typed Python: all function signatures have type hints
- Ruff for linting
- `logging` module, not `print()`, for pipeline output
- Configuration via `.env`, never hardcoded paths
- British spelling in documentation

> **TODO**: Commit message conventions and branch naming to be agreed with the team.

## pgvector backend (Docker + Postgres)

Use this when `VECTOR_STORE=pgvector`. ChromaDB (`VECTOR_STORE=chroma`) does not require Docker.

### Prerequisites

- [Docker Desktop](https://docs.docker.com/desktop/) installed and running
- conda env `project-d` (includes `sqlalchemy`, `pgvector`, `psycopg`, `alembic`)

### Step 1 — Configure `.env`

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

### Step 2 — Start Postgres

```bash
docker compose up -d
docker compose ps    # wait until STATUS is "healthy"
```

Image: `pgvector/pgvector:0.7.1-pg16` (same family as the CLEAR reference repo).

### Step 3 — Run migrations

From the repo root with `project-d` active:

```bash
alembic upgrade head
```

Creates `chunk_records` with `embedding vector(384)`, `collection_name`, and `metadata jsonb`.

### Step 4 — Smoke test

```bash
python scripts/check_pgvector.py
```

Expected final line: `Smoke test passed.`

### Step 5 — Run the pipeline on pgvector

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
| `ModuleNotFoundError: psycopg2` | Use `postgresql+psycopg://…` (psycopg v3), not bare `postgresql://` |
| Container not healthy | `docker compose logs postgres`; wait 10–20s on first start |
| Reset database completely | `docker compose down -v` then repeat Steps 2–4 |

### Schema reference

```
chunk_records
  chunk_id        varchar(128) UNIQUE
  content         text
  embedding       vector(384)
  collection_name varchar(128)
  metadata        jsonb   — keys: company, source_file, strategy, pages
```

See `docs/` and `PROJECT_BOARD.md` for project-specific notes and AI assistant setup.
