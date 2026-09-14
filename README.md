# RAG Pipeline for Carbon Performance Disclosures, with a ChromaDB vs pgvector Benchmark

Retrieval-augmented generation pipeline over TPI Centre Carbon Performance PDFs. Extracts and
chunks corporate sustainability disclosures, embeds them, retrieves relevant passages, and
generates cited answers. The same pipeline runs against either ChromaDB or pgvector behind one
interface, which is what makes the benchmark possible.

**[Full report (PDF)](Report/DS205%20TPI%20Final%20Report.pdf)** |
**[Benchmark results](docs/evaluation/benchmark_results.md)** |
**[Design decisions](DECISIONS.md)**

## What it does

The pipeline is a five-stage CLI: extract, chunk, embed, retrieve, generate. The vector store sits
behind a Protocol-typed interface with a factory that lazily imports whichever backend is
configured, so switching stores is an environment variable rather than a code change.

Corpus as benchmarked: 15 companies, 17 PDFs, 5,913 chunks, 20 reference queries with hand-built
expected-chunk sets.

## Benchmark result

Both backends were loaded with the identical corpus and compared across five dimensions.

| Dimension | Winner | Evidence |
|---|---|---|
| Retrieval quality | Tie | Identical recall@5, precision@5, MRR, and identical top-5 ordering on 20/20 queries |
| Query latency | ChromaDB | 3.93 ms vs 8.97 ms average median across filter modes |
| Ingestion throughput | pgvector | 32.86 s vs 37.47 s full corpus; 179.9 vs 157.8 chunks/sec |
| Deployment complexity | ChromaDB | 0 extra services vs 1; 2 setup steps vs 5 |
| Code legibility | ChromaDB | 110 lines / 5 imports vs 174 lines / 11 imports |

The conclusion is that backend choice is not an accuracy question in this pipeline, because
accuracy tied exactly. ChromaDB is the recommended default for laptop-scale retrieval. pgvector is
worth the setup cost when ingestion throughput matters or when the vectors need to live alongside
relational data.

**Honest limitation:** absolute retrieval precision is modest, around 0.18 at k=5 on the reference
set. Improving that requires changes to chunking, the embedding model, or a reranking stage. It is
not a vector store problem, and switching stores will not move it. Detail in
[benchmark_results.md](docs/evaluation/benchmark_results.md#retrieval-accuracy-limitations).

## Engineering notes

Worth reading [DECISIONS.md](DECISIONS.md) if you care about the implementation. It records the
reasoning behind the Protocol-over-ABC interface, the fixed `vector(384)` column, JSONB metadata
with a GIN index, metadata filtering pushed into SQL WHERE clauses, bulk upsert instead of ORM
session adds, and Alembic migrations for reproducible schema.

Backend equivalence is enforced by a shared contract test suite (`tests/test_vector_store_contract.py`)
that both stores must pass before merge. That suite is a trust check, not the performance
evaluation; the benchmark is separate.

## Running it

```bash
conda env create -f environment.yml
conda activate <env>
cp .env.example .env   # set PDF_SOURCE_DIR, CHROMA_DIR, and store selection
python pipeline.py --help
```

For the pgvector path, `docker-compose up` brings up local Postgres and `alembic upgrade head`
applies the schema.

Source PDFs are not included in the repository. They are public TPI Centre Carbon Performance
disclosures; see [CONTRIBUTING.md](CONTRIBUTING.md) for document selection rationale.

```bash
python -m pytest              # backend contract suite
python benchmark_metrics.py   # benchmark suite
```

## Contributors

Four-person project, LSE DS205, spring 2026.

<!-- FILL THIS IN before treating the repo as resume-facing. Name each contributor and what
     they owned. Commit counts were Jackson Miller 17, Josh de Buhr 14, 1chaos0 10,
     Braydenc121 7, but commit count is not a description of ownership. -->

- Jackson Miller: TODO
- Josh de Buhr: TODO
- 1chaos0: TODO
- Braydenc121: TODO
