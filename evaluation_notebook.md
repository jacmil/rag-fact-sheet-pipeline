# Evaluation Notebook Notes

This note records the full local pipeline and benchmark check run on 31 May 2026.
It summarizes what should be reflected in `benchmark_exploration.ipynb` and in the
written recommendation.

## Pipeline Status

The active `.env` points the pipeline at the company PDF folders:

```text
PDF_SOURCE_DIR=data/pdfs
VECTOR_STORE=chroma
COLLECTION_NAME=tpi_vectors
```

Current local corpus:

| Item | Count |
|------|------:|
| Companies | 15 |
| PDFs | 17 |
| Chunks | 5,913 |
| Reference queries | 20 |
| Missing reference chunk IDs | 0 |

Both stores currently contain the full corpus:

| Store | Chunks |
|-------|------:|
| ChromaDB | 5,913 |
| pgvector | 5,913 |

`python pipeline.py extract` completed successfully. All 17 PDFs were already
extracted and chunked, so the command verified the folder structure and skip
logic without regenerating files.

Retrieval smoke tests succeeded for both backends on the Kraft Heinz query:

```bash
VECTOR_STORE=chroma python pipeline.py retrieve -q "What are Kraft Heinz's environmental sustainability goals?"
VECTOR_STORE=pgvector python pipeline.py retrieve -q "What are Kraft Heinz's environmental sustainability goals?"
```

Generation also ran end to end with ChromaDB. The local generation model repeated
part of the final answer, so generation output should not be used as the backend
comparison metric. The backend evaluation should stay focused on retrieval.

## Benchmark Run

Command:

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

## Retrieval Quality

ChromaDB and pgvector returned the same top-5 chunk order for every reference
query.

| Metric | ChromaDB | pgvector |
|--------|---------:|---------:|
| Mean MRR | 0.412 | 0.412 |
| Mean recall@5 | 0.427 | 0.427 |
| Mean precision@5 | 0.180 | 0.180 |
| Same top-5 order | 20 / 20 | 20 / 20 |

Interpretation: retrieval quality is identical in this benchmark. The two
backends store the same vectors and return the same ranked chunks.

## Query Latency

Median and p95 timings from the benchmark:

| Backend | Filter | Runs | Median ms | p95 ms |
|---------|--------|-----:|----------:|-------:|
| ChromaDB | company | 60 | 5.68 | 6.19 |
| pgvector | company | 60 | 4.07 | 7.51 |
| ChromaDB | sector | 60 | 4.99 | 6.35 |
| pgvector | sector | 60 | 7.20 | 10.14 |
| ChromaDB | unfiltered | 60 | 1.04 | 1.28 |
| pgvector | unfiltered | 60 | 14.73 | 18.89 |
| ChromaDB | year | 60 | 5.83 | 6.14 |
| pgvector | year | 60 | 6.84 | 12.12 |

Interpretation: ChromaDB is much faster for unfiltered queries and slightly
faster for sector and year filters. pgvector is slightly faster for the company
filter in this run.

## Ingestion Throughput

| Backend | Chunks | Total embed+store sec | Embed sec | Store sec | Total chunks/sec | Store-only chunks/sec |
|---------|------:|----------------------:|----------:|----------:|-----------------:|----------------------:|
| ChromaDB | 5,913 | 38.33 | 33.63 | 4.70 | 154.26 | 1,258.68 |
| pgvector | 5,913 | 31.94 | 29.35 | 2.59 | 185.12 | 2,281.71 |

Interpretation: pgvector was faster for ingestion in this run, especially for
the store-only portion.

## Deployment And Code Complexity

| Backend | Extra services | Compose lines | Clean-machine backend steps |
|---------|---------------:|--------------:|----------------------------:|
| ChromaDB | 0 | 0 | 2 |
| pgvector | 1 | 26 | 5 |

| Backend | File | Lines | Imports | Max radon complexity | Mean radon complexity |
|---------|------|------:|--------:|---------------------:|----------------------:|
| ChromaDB | `vector_store/chroma.py` | 110 | 5 | 4 | 2.14 |
| pgvector | `vector_store/pgvector.py` | 174 | 11 | 6 | 2.50 |

Interpretation: pgvector adds Docker/Postgres setup and a larger implementation.
ChromaDB is simpler to run on a laptop.

## Current Recommendation

For a team of social science researchers running TPI-style retrieval on a
university laptop, ChromaDB is the better default right now. Accuracy is identical
to pgvector, unfiltered retrieval is faster, and setup is simpler.

The answer could change if the project needs stronger relational metadata
queries, joins with existing structured data, or a production Postgres deployment
that already exists. pgvector also looks stronger for ingestion throughput in the
current benchmark, so it is worth revisiting if bulk upload speed becomes the
main bottleneck.

## File Notes

`benchmark_metrics.py` prints the benchmark results but does not automatically
write `evaluation_results.json`. Only export JSON from the notebook after the
pandas tables look correct. The current untracked `evaluation_results.json`
should be treated as a local artifact unless regenerated from the latest run.
