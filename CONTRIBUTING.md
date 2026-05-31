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

`factory.py` uses lazy imports so the chroma path doesn't require pgvector packages installed, and vice versa. Key design decisions are documented in DECISIONS.md.

## Known bugs and areas for improvement

- `bitsandbytes` does not work on macOS Apple Silicon. Generation runs without quantisation on Mac.
- The current local cross-encoder can return non-finite scores. `retrieve.py` falls back to the bi-encoder order in that case. Backend benchmarking uses bi-encoder retrieval only, so this does not affect the ChromaDB vs pgvector comparison.

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
| `PG_CONNECTION_STRING` | Postgres URL when `VECTOR_STORE=pgvector` (use `postgresql+psycopg://...`) |
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

The pytest suite checks the shared vector-store contract against ChromaDB and
pgvector. It uses a tiny synthetic 384-dimensional dataset, so it does not embed
PDFs or touch the production `tpi_vectors` collection.

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

### Reference set and benchmark metrics

Keyword extraction was tested against natural-language queries on the AGL
reference set. It produced the same mean precision@5 as natural-language
retrieval, so the keyword rewriting path was removed and production retrieval
uses the original query text.

`reference_answers.json` contains 20 manually labelled queries. The current local
set covers 15 companies, 17 PDFs, 3 sectors, and publication years from 2016 to
2024. The chunk corpus currently has 5,913 chunks under `data/interim/chunks/`.
See [docs/evaluation/reference_answers_review.md](docs/evaluation/reference_answers_review.md)
for the labelling rules and current reference set summary.

Reference coverage by sector:

| Sector | Reference queries |
|--------|------------------:|
| Energy Utilities | 8 |
| Diversified Mining | 8 |
| Food | 4 |

The reference labels are used for backend comparison, not generation quality.
They measure bi-encoder top-k retrieval before cross-encoder reranking.

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -c "
import json
from sentence_transformers import SentenceTransformer
from vector_store import get_vector_store
from utils import resolve_pipeline_config, evaluate_retrieval

config = resolve_pipeline_config()
store = get_vector_store(config.collection_name)
model = SentenceTransformer(config.embedding_model)

with open('reference_answers.json') as f:
    ground_truth = json.load(f)

df = evaluate_retrieval(ground_truth, store, model, k=5)
print(df.to_string(index=False))
"
```

The benchmark notebook and script add timing, filter, ranking, and code
legibility tables on top of this basic retrieval evaluation.

Latest full local benchmark run:

| Metric | ChromaDB | pgvector |
|--------|---------:|---------:|
| Mean recall@5 | 0.4267 | 0.4267 |
| Mean precision@5 | 0.18 | 0.18 |
| Mean MRR | 0.4125 | 0.4125 |
| Same top-5 order | 20 / 20 | 20 / 20 |

Timing is machine-dependent. Use the notebook or `benchmark_metrics.py` for
fresh numbers before writing the final report.

To extend the reference set when adding new companies:
1. Read the PDF for a new query
2. Manually identify which chunks contain the correct answer
3. Note the chunk IDs
4. Add entry to `reference_answers.json`:
   ```json
   {
     "query": "Your question here",
     "relevant_ids": ["chunk_id_1", "chunk_id_2", ...]
   }
   ```
5. Re-run `evaluate_retrieval()` to measure impact of any pipeline changes

### Backend benchmark notebook

The benchmarker workflow is notebook-first. Use `benchmark_exploration.ipynb`
to test ideas and inspect pandas DataFrames. Stable helper functions live in
`benchmark_metrics.py`, and the notebook imports them.
Current benchmark notes are summarized in
[docs/evaluation/evaluation_notebook.md](docs/evaluation/evaluation_notebook.md).

Current notebook parameters:

| Parameter | Value |
|-----------|-------|
| Backends | `("chroma", "pgvector")` |
| Batch size | 256 |
| Query repeats | 3 |
| k | 5 |
| Max chunks | `None` |
| Max queries | `None` |

The notebook covers these comparison tables:

| Metric | How it is measured |
|--------|--------------------|
| Ingestion throughput | Time to embed chunks plus store them, with `store.add()` time also separated |
| Query latency | Time spent inside `store.query()` for each query/repeat |
| Filter overhead | Same query timing with company, year, and sector filters when metadata exists |
| Recall@5 | Top-k results scored against `reference_answers.json` |
| MRR | First relevant result rank from the top-k table |
| Score/ranking parity | Top-k cosine scores and chunk ID order across backends |
| Deployment complexity | Extra services, Docker Compose line count, and clean-machine setup steps |
| Code legibility | Line count, import count, and radon complexity for each backend implementation |

Run it after chunks already exist under `data/interim/chunks/`. If they do not,
run `python pipeline.py extract` first.

```bash
docker compose up -d
alembic upgrade head
python scripts/check_pgvector.py
python benchmark_metrics.py
```

Or open `benchmark_exploration.ipynb` and run the cells. The notebook uses
temporary benchmark collections and cleans them up after each run.
`evaluation_results.json` is intentionally empty by default; only write it after
the notebook output looks right by running:

```python
write_results_json(results, "evaluation_results.json")
```

`benchmark_metrics.py` can also be run directly. It prints a compact console
report and does not write JSON by default.

### Data directories

`data/` is in `.gitignore`. The pipeline creates:

- `data/interim/raw/` - pickle caches of extracted PDF elements
- `data/interim/chunks/` - JSONL chunk files
- `data/chromadb/` - ChromaDB persistent storage
- Postgres data lives in the Docker volume `pgvector_data` when using pgvector

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

See `docs/` and `PROJECT_BOARD.md` for project-specific notes and AI assistant setup.
