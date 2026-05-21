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
  (pgvector.py)  pgvector implementation (in progress)
```

`factory.py` uses lazy imports so the chroma path doesn't require pgvector packages installed, and vice versa. Key design decisions are documented in DECISIONS.md.

## Known bugs and areas for improvement

- `resolve_pipeline_config()` returns a plain `dict` with string keys. A `@dataclass` would give type safety and autocomplete across all files that use it.
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
from utils import resolve_pipeline_config, evaluate_retrieval

config = resolve_pipeline_config()
store = get_vector_store(config['collection_name'])
model = SentenceTransformer(config['embedding_model'])

with open('reference_answers.json') as f:
    ground_truth = json.load(f)

df = evaluate_retrieval(ground_truth, store, model, k=5)
print(df.to_string(index=False))
"
```

This evaluates bi-encoder retrieval only (no cross-encoder reranking). The reference set is designed for backend equivalence testing: run the same script with `VECTOR_STORE=chroma` and `VECTOR_STORE=pgvector` and compare numbers.

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
