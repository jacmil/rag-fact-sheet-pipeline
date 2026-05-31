[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/Ho0VU-Re)
# JSON Derulo Comeback Tour

RAG pipeline for TPI Centre Carbon Performance data, built to compare ChromaDB and pgvector as vector store backends.

**Project tracking:** see [PROJECT_BOARD.md](PROJECT_BOARD.md) for tasks, deliverables, and design questions.

**Per-person AI assistant setup:** see [docs/README.md](docs/README.md) (role briefs in `docs/ai/`, personal files under `docs/contributors/<name>/`).

## Overview

This pipeline extracts text from corporate sustainability PDFs, chunks it, embeds it with sentence-transformers, stores it in a vector database, and answers questions about company emissions targets using a small language model. The same pipeline runs against two vector store backends (ChromaDB and pgvector) so we can benchmark ingestion throughput, query latency, and retrieval quality for TPI's use case.

Data comes from TPI Centre Carbon Performance assessment PDFs and related corporate climate disclosures. PDFs and generated data are not committed to Git. The current local evaluation set contains 17 PDFs, 5,913 chunks, and a manually labelled 20-query reference set across Energy Utilities, Diversified Mining, and Food. Company, year, and sector metadata live in `document_metadata.json`.

## Current benchmark status

Use `benchmark_exploration.ipynb` for the notebook workflow. It imports helper functions from `benchmark_metrics.py` and shows pandas DataFrames for ingestion speed, query latency, retrieval quality, metadata filters, deployment complexity, and code legibility. The notebook only writes `evaluation_results.json` if you run the optional save cell.

The latest full local run used 20 reference queries, `k=5`, and 3 query repeats. ChromaDB and pgvector returned the same top-5 chunk order for all 20 queries. Mean retrieval quality was identical: recall@5 `0.4267`, precision@5 `0.18`, and MRR `0.4125`. On that run, ChromaDB was faster for unfiltered queries, while pgvector had faster store-only ingestion. Re-run the benchmark before reporting final numbers, since timing depends on the machine and current Docker state.

Evaluation notes live in [docs/evaluation/](docs/evaluation/). Start with
[docs/evaluation/benchmark_results.md](docs/evaluation/benchmark_results.md)
for the consolidated benchmark tables and recommendation.

## How to run

1. Create and activate the conda environment (takes 25-30 minutes, this is normal):

   ```bash
   conda env create -f environment.yml
   conda activate project-d
   ```

2. Copy `.env.example` to `.env` and fill in the required variables:

   ```bash
   cp .env.example .env
   ```

   At minimum you need `PDF_SOURCE_DIR` pointing at a directory with one subfolder per company containing PDFs.

3. Run the full pipeline:

   ```bash
   python pipeline.py run-all --query "What are the emissions targets for AGL?"
   ```

   Or run individual stages:

   ```bash
   python pipeline.py extract
   python pipeline.py embed
   python pipeline.py retrieve --query "What are the emissions targets?"
   python pipeline.py generate --query "What are the emissions targets?"
   ```

For developer setup, internal architecture, pgvector Docker setup, and the reference answer evaluation, see [CONTRIBUTING.md](CONTRIBUTING.md).

To run the backend benchmark from the terminal:

```bash
docker compose up -d
alembic upgrade head
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python benchmark_metrics.py
```

## Configuration

All configuration is via `.env`. Required and optional variables are documented in `.env.example` and in the `PipelineConfig` dataclass in `utils.py`. Key variables:

| Variable | Required | What it does |
|----------|----------|-------------|
| `PDF_SOURCE_DIR` | Yes | Parent directory with one subfolder per company |
| `VECTOR_STORE` | Yes | `chroma` or `pgvector` |
| `CHROMA_DIR` | When using chroma | Path to ChromaDB storage |
| `PG_CONNECTION_STRING` | When using pgvector | Postgres connection string, for example `postgresql+psycopg://...` |
| `DATABASE_URL` | When using pgvector | Same URL for Alembic migrations |
| `COLLECTION_NAME` | No (default: `tpi_vectors`) | Vector store collection name |
| `EMBEDDING_MODEL` | No (default: `multi-qa-MiniLM-L6-cos-v1`) | HuggingFace embedding model |
| `GENERATION_MODEL` | No (default: `Qwen2.5-1.5B-Instruct`) | HuggingFace generation model |

## Output

The pipeline writes intermediate and final data to `data/` (gitignored, reproducible from source PDFs):

- `data/interim/raw/` - cached PDF extraction results as pickle files
- `data/interim/chunks/` - chunked text as JSONL
- `data/chromadb/` - ChromaDB persistent storage
- Docker volume `pgvector_data` - Postgres data for pgvector

The `generate` and `run-all` commands print a cited answer to stdout. Design decisions and architectural rationale are in [DECISIONS.md](DECISIONS.md).
