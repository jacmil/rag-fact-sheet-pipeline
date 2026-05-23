[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/Ho0VU-Re)
# JSON Derulo Comeback Tour

RAG pipeline for TPI Centre Carbon Performance data, built to compare ChromaDB and pgvector as vector store backends.

**Project tracking:** see [PROJECT_BOARD.md](PROJECT_BOARD.md) for tasks, deliverables, and design questions.

**Per-person AI assistant setup:** see [docs/README.md](docs/README.md) (role briefs in `docs/ai/`, personal files under `docs/contributors/<name>/`).

## Overview

This pipeline extracts text from corporate sustainability PDFs, chunks it, embeds it with sentence-transformers, stores it in a vector database, and answers questions about company emissions targets using a small language model. The same pipeline runs against two vector store backends (ChromaDB and pgvector) so we can benchmark ingestion throughput, query latency, and retrieval quality for TPI's use case.

Data comes from TPI Centre Carbon Performance assessment PDFs (hosted on SharePoint, not committed to Git). The pipeline currently processes companies from the Food Producers sector.

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

For developer setup, internal architecture, and the reference answer evaluation, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Configuration

All configuration is via `.env`. Required and optional variables are documented in `.env.example` and in the `PipelineConfig` dataclass in `utils.py`. Key variables:

| Variable | Required | What it does |
|----------|----------|-------------|
| `PDF_SOURCE_DIR` | Yes | Parent directory with one subfolder per company |
| `VECTOR_STORE` | Yes | `chroma` or `pgvector` |
| `CHROMA_DIR` | When using chroma | Path to ChromaDB storage |
| `PG_CONNECTION_STRING` | When using pgvector | Postgres connection string |
| `COLLECTION_NAME` | No (default: `tpi_vectors`) | Vector store collection name |
| `EMBEDDING_MODEL` | No (default: `multi-qa-MiniLM-L6-cos-v1`) | HuggingFace embedding model |
| `GENERATION_MODEL` | No (default: `Qwen2.5-1.5B-Instruct`) | HuggingFace generation model |

## Output

The pipeline writes intermediate and final data to `data/` (gitignored, reproducible from source PDFs):

- `data/interim/raw/` — cached PDF extraction results (pickle)
- `data/interim/chunks/` — chunked text (JSONL, human-readable)
- `data/chromadb/` — ChromaDB persistent storage

The `generate` and `run-all` commands print a cited answer to stdout. Design decisions and architectural rationale are in [DECISIONS.md](DECISIONS.md).
