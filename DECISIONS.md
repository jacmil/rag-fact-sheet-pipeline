# Decisions

Architectural choices and alternatives considered. Entries are grouped by area, not chronological.

## Vector store interface

### Protocol over ABC

Used `typing.Protocol` (structural subtyping) rather than `abc.ABC` (nominal subtyping). Protocol doesn't couple backends to a shared base class. ChromaStore and PgVectorStore just need to implement the right method signatures; they don't inherit from anything. This keeps the backends independent and makes adding a third backend trivial.

### Metadata constrained to `dict[str, str]`

Both ChromaDB and pgvector handle string metadata reliably. Mixed types (lists, ints) behave differently across backends. Constraining to strings-only in the interface means `embed.py` casts non-string fields (e.g. `pages` list) at the boundary, and both backends can trust what they receive. Trade-off: slightly less expressive metadata queries.

### Score as similarity, not distance

ChromaDB returns distances (lower = more similar). The interface returns similarity scores (higher = more similar), computed as `1 - distance` inside each backend implementation. `chroma.py` converts Chroma distances; `pgvector.py` converts pgvector cosine distances from SQL. This keeps the consumer code (retrieve, benchmark) consistent regardless of backend. Validated on the AGL reference set: both backends return identical recall@5 and top-5 rankings.

### Lazy imports in factory

`factory.py` imports `ChromaStore` and `PgVectorStore` inside their respective `if` branches, not at module level. This means running with `VECTOR_STORE=chroma` doesn't require `sqlalchemy` or `pgvector` installed, and vice versa. Matters for the benchmarker if they want to test one backend at a time.

## pgvector backend

### Single `chunk_records` table

Postgres stores chunks in one table rather than mirroring ChromaDB's collection abstraction at the schema level. Logical collections are represented by a `collection_name` column (default `tpi_vectors`). Trade-off: simpler schema and straightforward SQL inspection; collection isolation is application-level, not separate tables per collection.

### Fixed `vector(384)` column

The embedding model (`multi-qa-MiniLM-L6-cos-v1`) produces 384-dimensional vectors. The Alembic migration declares `embedding vector(384)` so Postgres rejects wrong-sized vectors at insert time rather than silently corrupting similarity search.

### JSONB metadata with GIN index

Metadata is stored as `jsonb`, mapped in SQLAlchemy as `metadata_` (the ORM reserves the name `metadata`). A GIN index on the column supports filtered queries. Values remain string-only at the boundary, matching the ChromaDB contract.

### Metadata filtering via SQL WHERE

`PgVectorStore.query()` applies `where={"company": "AGL"}` as JSONB equality filters (`metadata->>'key' = value`) before ordering by cosine distance. `ChromaStore.query()` passes the same `where` contract to ChromaDB. The benchmark measures both filtered and unfiltered query latency through the shared `VectorStore.query()` interface.

### Bulk upsert via table insert, not ORM `session.add()`

Re-running `python pipeline.py embed` must not crash on duplicate chunk IDs. pgvector uses PostgreSQL `INSERT … ON CONFLICT (chunk_id) DO UPDATE`, matching ChromaDB's `upsert()` semantics. Bulk writes go through `ChunkRecord.__table__` with `pg_insert().on_conflict_do_update()` rather than ORM `session.add()`, because the `metadata` column name collides with SQLAlchemy's reserved `metadata` attribute on declarative models.

### Docker Compose for local Postgres only

ChromaDB persists to files under `data/chromadb/` with no server process. Postgres requires a running database, so `docker-compose.yml` provides `pgvector/pgvector:0.7.1-pg16` (same image family as the CLEAR reference repo). Docker is only needed when `VECTOR_STORE=pgvector`; Chroma-only workflows do not require it.

### Alembic for reproducible schema

Table creation is managed by Alembic (`alembic upgrade head`), not implicit ORM `create_all()`. Fresh-machine setup is: start Docker, run migrations, smoke test, embed. Schema changes get versioned revision files rather than ad-hoc SQL.

### psycopg v3 connection strings

SQLAlchemy connects via psycopg v3 (`postgresql+psycopg://…`). Bare `postgresql://` URLs can fail with a missing `psycopg2` driver. `pgvector.py` normalises common URL forms, but `.env.example` documents the explicit driver prefix to avoid setup confusion.

### Backend equivalence validated before merge

pgvector recall@5 was checked against the ChromaDB baseline on `reference_answers.json` (bi-encoder only, k=5): emissions targets 0.25, power stations 1.00, renewables investment 1.00. Top-5 chunk IDs and order matched on all three queries. If numbers diverge after changes, check upsert logic and cosine score conversion in `pgvector.py` first; `retrieve.py` is backend-agnostic and should not need changes.

## Pipeline integration

### Upsert over client-side idempotency

The original PS2 pipeline checked existing IDs before adding. We removed that check. ChromaDB's `collection.upsert()` and pgvector's `ON CONFLICT` handle duplicates natively. `chroma.py` uses `upsert()` not `add()` specifically because `add()` throws `DuplicateIDError` on re-runs, which breaks pipeline idempotency.

### `_get_store()` per-command, not at group level

The Click CLI creates the VectorStore instance inside each command that needs it, not at the `@click.group()` level. `extract` doesn't use a vector store at all, so it shouldn't pay the setup cost or require store-related env vars to be set.

### `run-all` calls functions directly

The `run-all` command calls `run_extract()`, `run_embed()`, `run_retrieve()`, and `run_generate()` as Python functions rather than using `ctx.invoke()` on Click commands. The retrieve-to-generate handoff needs the intermediate `list[QueryResult]`, which can't pass through Click's command dispatch.

### Batch size 256 for embedding

`embed.py` encodes and stores 256 chunks per batch. Balances memory usage (encoding thousands of chunks at once would spike RAM) against the overhead of repeated `store.add()` calls. Not tuned empirically; 256 is a reasonable default.

## Evaluation

### Measurement-driven evaluation approach

The benchmark work isolates backend behaviour from unrelated pipeline costs.
Retrieval metrics use the bi-encoder only, and backend timing wraps direct
`store.add()` and `store.query()` calls rather than full CLI commands.

Keyword extraction was tested separately by comparing stripped-down query strings
against the original natural-language questions on the AGL reference set. It did
not improve mean precision@5, so the keyword rewriting path was removed.

### Notebook-first benchmark implementation

The benchmarker workflow is notebook-first. `benchmark_exploration.ipynb` is the
scratch surface for running experiments and inspecting pandas DataFrames.
`benchmark_metrics.py` contains reusable helper functions once a notebook cell
is stable enough to extract.

The harness creates each backend directly, using a temporary ChromaDB directory
and a temporary pgvector collection. Benchmark chunk IDs are prefixed with
`tpi_vectors_benchmark__` so pgvector upserts cannot overwrite production chunk
IDs. Cleanup deletes the benchmark collections after each run.

The notebook does not write result artifacts automatically. `evaluation_results.json`
starts as `{}` and should only be written after the notebook output looks right.
This keeps failed exploratory runs from becoming report evidence by accident.

### Reference set evaluates bi-encoder only

`reference_answers.json` and `evaluate_retrieval()` measure retrieval without cross-encoder reranking. The cross-encoder is identical code regardless of backend, so including it would add noise without helping isolate backend differences. When comparing ChromaDB vs pgvector, measure bi-encoder performance. For end-to-end retrieval quality (bi-encoder + cross-encoder), run the full `run_retrieve()` pipeline from `retrieve.py` instead.

**Current baseline (AGL document, bi-encoder, k=5, validated 24 May 2026):**

| Query | recall@5 | precision@5 | MRR |
|-------|----------|-------------|-----|
| Emissions targets | 0.25 | 0.2 | 0.5 |
| Power stations | 1.00 | 0.4 | 0.5 |
| Renewables investment | 1.00 | 0.4 | 1.0 |

Both ChromaDB and pgvector produce identical results. If changes to retrieval
strategy, chunking, or embedding model affect these numbers, run the tests again
to measure impact.

### Retrieval uses natural-language queries

`run_retrieve()` embeds the original user query directly for both the bi-encoder
retrieval pass and cross-encoder reranking. The keyword extraction experiment did
not improve precision@5 on the AGL reference set, so the extra query rewriting
step was removed.

### Qwen2.5-1.5B-Instruct for generation

Chose Qwen2.5-1.5B-Instruct as the generation model. TinyLlama-1.1B was too slow on Nuvolos (20+ minutes with no response). Qwen2.5-0.5B is lighter but noticeably worse output. 1.5B fits in 16GB RAM on an M2 without quantisation. On Nuvolos or Linux, 8-bit quantisation via `bitsandbytes` halves memory usage. `bitsandbytes` does not support macOS Apple Silicon, so `generate.py` detects the platform and skips quantisation on Mac.

## Base pipeline

### Adapted from a classmate's PS2

The pipeline is built on top of a classmate's PS2 submission (Hershey Company and Nomad Foods, food producers sector). We refactored the pipeline files to decouple them from ChromaDB and route through the `VectorStore` interface instead. `extract.py` was left largely untouched since it doesn't interact with the vector store.

### Pickle for elements, JSONL for chunks

`extract.py` caches raw `unstructured` elements as `.pkl` files (complex objects that don't serialise cleanly to JSON) and saves chunks as `.jsonl` (flat dicts, human-readable, inspectable in a text editor). Pickle files are reproducible from source PDFs if they break across library versions.

## Benchmark priorities (from Sylvan meeting, 19 May)

### Weight ingestion throughput over query latency

Sylvan told us TPI does batch uploads of 2-3k documents about 5-6 times a year. Day-to-day queries are short and come from roughly 25 users. A backend that's 50ms faster per query but 3x slower on bulk ingestion would be the wrong recommendation.

### Benchmark filtered and unfiltered queries separately

TPI filters by metadata (doctype, sector, company) to narrow from potentially 50k chunks to a manageable set. The two backends may handle metadata filtering differently internally, even though the pipeline exposes the same `where` interface. Measuring both filtered and unfiltered latency gives a more complete picture.

## Repository and code structure

### Flat file layout over pipeline package

Considered moving pipeline files into a `pipeline/` subdirectory. Kept them at root because there are only six files, the brief rewards code that is "smaller than you would expect for what it achieves", and a subdirectory would add import refactoring for no functional gain.

### Logging config at CLI level, not module level

`coloredlogs.install()` runs inside `cli()`, not at the top of `pipeline.py`. Module-level setup would fire on import, silently reconfiguring logging for anyone importing the module for testing or from another script.

### Cross-encoder loaded once per retrieve call

`rerank_chunks()` accepts a pre-loaded `CrossEncoder` instance rather than creating one internally from config. The benchmarker calling `run_retrieve()` 20 times for latency measurement loads the model once, not 20 times.

### Inlined thin wrapper functions

Removed `store_batch()` from `embed.py` and `get_embedding_model()` from `retrieve.py`. Both were single-line wrappers that added indirection without adding logic. The call sites are clearer without them.

### Shared default query constant

The fallback query string `"What are the emissions targets for this company?"` was duplicated in `retrieve.py` and `generate.py`. Moved to `DEFAULT_QUERY` in `utils.py` and imported in both files.

### Data ingestion responsibility

Pipeline infrastructure owner builds the machinery and documents how to add new companies. The benchmarker decides which documents to feed and handles data selection for measurement. Config is parameterised via `.env` so adding documents is a config change, not an infra change.

### Directory-based company discovery over per-company env vars

Originally had `HERSHEY_PDF_DIR` and `NOMAD_PDF_DIR` as separate env vars. Replaced with a single `PDF_SOURCE_DIR` that the pipeline scans for subdirectories. Folder names become company labels (underscores replaced by spaces). To add a company the benchmarker creates a folder and drops PDFs in it. No code or `.env` change needed. Considered a `COMPANY_N_NAME`/`COMPANY_N_DIR` pattern but it scales worse and clutters `.env` as companies increase.

### Warning not error for empty company folders

If a company subdirectory exists but contains no PDFs matching the glob, the pipeline logs a warning and continues rather than crashing. The benchmarker may have 10 company folders with only 8 populated. Crashing the whole pipeline for one empty folder wastes time.

### Pruned dead chunking code

`chunk_by_char_limit()` (Strategy A, fixed character limit) and `get_raw_texts()` were carried over from the base PS2 code but never called by the pipeline. Only `chunk_by_element_type()` (Strategy B) is used. Removed both to keep the codebase to what is actually exercised. The benchmarker can reintroduce Strategy A if they want to compare chunking strategies.

### Ray/multithreading deferred

A teammate proposed using the Ray library for parallel ingestion. Deferred because the core benchmark needs clean serial measurements first. If ingestion is parallelised, it becomes harder to isolate whether a timing difference comes from the backend or the parallelism. Once the six benchmark dimensions are measured serially, Ray could be layered on as an extension to test whether either backend benefits more from concurrent writes.

### PipelineConfig dataclass over plain dict

`resolve_pipeline_config()` originally returned a `dict[str, Any]`. Refactored to return a `@dataclass` (`PipelineConfig` in `utils.py`). Every call site now uses `config.embedding_model` instead of `config["embedding_model"]`. Trade-off: a mechanical find-and-replace across six files for type safety, autocomplete, and catching typos at import time rather than runtime. Done before the pgvector implementation started so the pgvector person builds against the dataclass from day one.

### requirements.txt and requirements-lock.txt

Kept the hand-written requirements.txt with comments and logical grouping. Added requirements-lock.txt (pip freeze output) for exact version pinning. The hand-written file is what humans read; the lock file is what reproduces the environment exactly.

## Known limitations

### `get_or_create_collection` ambiguity

ChromaDB's `get_or_create_collection` can't distinguish "created a new collection" from "loaded an existing one" without checking count before and after. Flagged in `chroma.py` but not resolved. If strict create-vs-load semantics are ever needed, the factory would need two paths.

### Company filter reads from config

`get_company_filter()` in `retrieve.py` originally had hardcoded company names (Hershey, Nomad). Refactored to read company names from `config["company_dirs"]` and match against the query. Adding a company folder to `PDF_SOURCE_DIR` automatically makes it filterable in retrieval. No code change needed.

### Evaluation function refactored to use VectorStore

`evaluate_retrieval()` in `utils.py` originally called `collection.query()` directly on a raw ChromaDB collection object, bypassing the abstraction. Refactored to accept a `VectorStore` and `SentenceTransformer` instead. The benchmarker will likely extend or replace this function for their harness, but the current version runs against either backend.
