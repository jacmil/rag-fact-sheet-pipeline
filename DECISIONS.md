# Decisions

Architectural choices and alternatives considered. Entries are grouped by area, not chronological.

## Vector store interface

### Protocol over ABC

Used `typing.Protocol` (structural subtyping) rather than `abc.ABC` (nominal subtyping). Protocol doesn't couple backends to a shared base class. ChromaStore and PgVectorStore just need to implement the right method signatures; they don't inherit from anything. This keeps the backends independent and makes adding a third backend trivial.

### Metadata constrained to `dict[str, str]`

Both ChromaDB and pgvector handle string metadata reliably. Mixed types (lists, ints) behave differently across backends. Constraining to strings-only in the interface means `embed.py` casts non-string fields (e.g. `pages` list) at the boundary, and both backends can trust what they receive. Trade-off: slightly less expressive metadata queries.

### Score as similarity, not distance

ChromaDB returns distances (lower = more similar). The interface returns similarity scores (higher = more similar), computed as `1 - distance` inside `chroma.py`. This keeps the consumer code (retrieve, benchmark) consistent regardless of backend. The pgvector implementation will need to do its own conversion.

### Lazy imports in factory

`factory.py` imports `ChromaStore` and `PgVectorStore` inside their respective `if` branches, not at module level. This means running with `VECTOR_STORE=chroma` doesn't require `sqlalchemy` or `pgvector` installed, and vice versa. Matters for the benchmarker if they want to test one backend at a time.

## Pipeline integration

### Upsert over client-side idempotency

The original PS2 pipeline checked existing IDs before adding. We removed that check. Both ChromaDB (`add` with existing IDs) and pgvector (`ON CONFLICT`) handle duplicates natively. Simpler code, same behaviour.

### `_get_store()` per-command, not at group level

The Click CLI creates the VectorStore instance inside each command that needs it, not at the `@click.group()` level. `extract` doesn't use a vector store at all, so it shouldn't pay the setup cost or require store-related env vars to be set.

### `run-all` calls functions directly

The `run-all` command calls `run_extract()`, `run_embed()`, `run_retrieve()`, and `run_generate()` as Python functions rather than using `ctx.invoke()` on Click commands. The retrieve-to-generate handoff needs the intermediate `list[QueryResult]`, which can't pass through Click's command dispatch.

### Batch size 256 for embedding

`embed.py` encodes and stores 256 chunks per batch. Balances memory usage (encoding thousands of chunks at once would spike RAM) against the overhead of repeated `store.add()` calls. Not tuned empirically; 256 is a reasonable default.

## Base pipeline

### Adapted from a classmate's PS2

The pipeline is built on top of a classmate's PS2 submission (Hershey Company and Nomad Foods, food producers sector). We refactored the pipeline files to decouple them from ChromaDB and route through the `VectorStore` interface instead. `extract.py` was left largely untouched since it doesn't interact with the vector store.

### Pickle for elements, JSONL for chunks

`extract.py` caches raw `unstructured` elements as `.pkl` files (complex objects that don't serialise cleanly to JSON) and saves chunks as `.jsonl` (flat dicts, human-readable, inspectable in a text editor). Pickle files are reproducible from source PDFs if they break across library versions.

## Benchmark priorities (from Sylvan meeting, 19 May)

### Weight ingestion throughput over query latency

Sylvan told us TPI does batch uploads of 2-3k documents about 5-6 times a year. Day-to-day queries are short and come from roughly 25 users. A backend that's 50ms faster per query but 3x slower on bulk ingestion would be the wrong recommendation.

### Benchmark filtered and unfiltered queries separately

TPI filters by metadata (doctype, sector, company) to narrow from potentially 50k chunks to a manageable set. The two backends may handle metadata filtering very differently (ChromaDB's HNSW with post-filter vs pgvector's SQL WHERE with pre-filter via joins). Measuring both gives a more complete picture.

## Known limitations

### `get_or_create_collection` ambiguity

ChromaDB's `get_or_create_collection` can't distinguish "created a new collection" from "loaded an existing one" without checking count before and after. Flagged in `chroma.py` but not resolved. If strict create-vs-load semantics are ever needed, the factory would need two paths.

### Hardcoded company filter in retrieve

`get_company_filter()` in `retrieve.py` maps query keywords to company names. Currently hardcoded to Hershey and Nomad. Needs parameterising from config or collection metadata before the benchmarker adds more companies.

### Evaluation function bypasses abstraction

`evaluate_retrieval()` in `utils.py` calls `collection.query()` directly on a ChromaDB collection object. This needs refactoring to go through `VectorStore.query()` so the same evaluation runs against both backends.
