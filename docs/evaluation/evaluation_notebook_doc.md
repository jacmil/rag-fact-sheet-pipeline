# Evaluation Notebook Notes

This note records the full local pipeline and benchmark check run on 31 May 2026.
It summarizes what should be reflected in `notebooks/benchmark_exploration.ipynb` and in the
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

## Ingestion Throughput

| Backend | Chunks | Total embed+store sec | Embed sec | Store sec | Total chunks/sec | Store-only chunks/sec |
|---------|------:|----------------------:|----------:|----------:|-----------------:|----------------------:|
| ChromaDB | 5,913 | 37.47 | 33.01 | 4.47 | 157.79 | 1,323.96 |
| pgvector | 5,913 | 32.86 | 30.05 | 2.82 | 179.93 | 2,099.87 |

Interpretation: pgvector was faster for ingestion in this run, especially for
the store-only portion.

## Document Size Threshold

The corpus was also split at a 60-page threshold to compare short-document and
long-document ingestion. This is a cohort comparison, not the exact single
20-page vs single 60-page benchmark from the brief.

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
Because the long group contains many more chunks, normalized rates such as
chunks/sec are more meaningful than total seconds alone.

## Closest 20-Page Or 60-Page Target

The corpus was also grouped by whichever target page count each PDF is closest
to: 20 pages or 60 pages. This gives a closer match to the assignment language,
while still using all available documents rather than picking only two examples.

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

Interpretation: pgvector was faster for ingestion in both target groups. The
closest-to-60 group contains several much longer reports, including a 336-page
annual report, so the group is not a pure 60-page-only condition.

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
to pgvector, query latency is lower in the current benchmark, and setup is
simpler.

The answer could change if the project needs stronger relational metadata
queries, joins with existing structured data, or a production Postgres deployment
that already exists. pgvector also looks stronger for ingestion throughput in the
current benchmark, so it is worth revisiting if bulk upload speed becomes the
main bottleneck.

## File Notes

`benchmark_metrics.py` prints the benchmark results but does not automatically
write `evaluation/evaluation_results.json`. Only export JSON from the notebook after the
pandas tables look correct. `evaluation/evaluation_results.json` is tracked as an empty
placeholder by default; treat populated benchmark exports as local run artifacts
unless regenerated from the latest run and intentionally reviewed.
