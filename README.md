[Review Assignment Due Date](https://classroom.github.com/a/Ho0VU-Re)

# JSON Derulo Comeback Tour

RAG pipeline for TPI Centre Carbon Performance PDFs. Extracts and chunks sustainability reports, embeds them, retrieves relevant passages, and generates cited answers — with the same pipeline runnable on **ChromaDB** or **pgvector**.

**Recommendation:** For TPI-style retrieval on a laptop, **ChromaDB is the default** (identical retrieval quality, lower query latency, simpler setup). See [docs/evaluation/benchmark_results.md](docs/evaluation/benchmark_results.md) for numbers and when pgvector is worth it.

**Limitation:** Absolute retrieval precision is modest (**~0.18 @ k=5** on our reference set); improving it would require pipeline or model changes, not switching vector stores. Details in [benchmark_results.md § Retrieval accuracy limitations](docs/evaluation/benchmark_results.md#retrieval-accuracy-limitations).

## Quick start

```bash
git clone git@github.com:lse-ds205/group-project-json-derulo-comeback-tour.git
cd group-project-json-derulo-comeback-tour

conda env create -f environment.yml   # 25–30 min on first run
conda activate project-d

cp .env.example .env
# Set PDF_SOURCE_DIR (see below)
```

### 1. Add your PDFs

PDFs are not in Git. Obtain TPI assessment PDFs from the team SharePoint folder (see course brief), then place them like this:

```
data/pdfs/
  AGL/
    *.pdf
```

One subfolder per company; underscores in folder names become spaces in metadata. Set `PDF_SOURCE_DIR=data/pdfs` in `.env` (default in `.env.example`).

The team benchmark used **17 PDFs** (5,913 chunks, 20 reference queries). 

### 2. Run the pipeline

```bash
python pipeline.py run-all --query "What are the emissions targets for AGL?"
```

Stages can also be run separately: `extract`, `embed`, `retrieve`, `generate`. Output goes under `data/` (gitignored). Use **`VECTOR_STORE=chroma`** in `.env` for the simplest path; pgvector requires Docker — see [CONTRIBUTING.md](CONTRIBUTING.md#pgvector-backend-docker--postgres).

### 3. Optional checks

```bash
python -m pytest                  # vector-store contract (both backends)
python pipeline.py --help         # CLI commands
```

For backend benchmarks and notebooks, see [CONTRIBUTING.md](CONTRIBUTING.md#evaluation-and-benchmarks).

## Project layout

```
group-project-json-derulo-comeback-tour/
│
├── README.md                   # Quick start (this file)
├── CONTRIBUTING.md             # Configuration, CLI, internals, pgvector setup
├── DECISIONS.md                # Design rationale and tradeoffs
├── .env.example                # Environment variable template
├── environment.yml             # Conda environment
├── requirements.txt            # Pip dependencies
├── requirements-lock.txt       # Locked pip versions
├── pytest.ini                  # pytest configuration
├── docker-compose.yml          # Postgres + pgvector (when VECTOR_STORE=pgvector)
├── alembic.ini                 # Database migration config
│
├── pipeline.py                 # Click CLI — run stages from here
├── extract.py                  # PDF extraction and chunking
├── embed.py                    # Embeddings → vector store
├── retrieve.py                 # Bi-encoder + cross-encoder retrieval
├── generate.py                 # Cited answer generation
├── utils.py                    # Config and shared helpers
├── benchmark_metrics.py        # Terminal backend benchmark
│
├── vector_store/               # Chroma + pgvector backends
│   ├── __init__.py
│   ├── types.py                # VectorStore protocol, QueryResult
│   ├── factory.py              # Reads VECTOR_STORE from .env
│   ├── chroma.py
│   ├── pgvector.py
│   └── db.py                   # SQLAlchemy schema (pgvector)
│
├── alembic/                    # pgvector schema migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_create_chunk_records.py
│
├── evaluation/                 # Benchmark data (JSON)
│   ├── __init__.py
│   ├── paths.py                # Repo-root-relative path constants
│   ├── reference_answers.json  # Manual Recall@5 reference set
│   ├── document_metadata.json  # Company / year / sector overrides
│   └── evaluation_results.json # Optional notebook export (empty by default)
│
├── notebooks/
│   ├── benchmark_exploration.ipynb      # Pandas benchmark workflow
│   └── reference_answer_builder.ipynb   # Inspect chunks, build labels
│
├── scripts/
│   └── check_pgvector.py       # pgvector smoke test
│
├── tests/
│   ├── conftest.py
│   ├── helpers.py
│   └── test_vector_store_contract.py
│
├── docs/                       # Documentation
│   ├── README.md               # Documentation index
│   ├── handoff/
│   │   └── HANDOFF.md          # Team / AI handoff notes
│   ├── agent/
│   │   └── RULES.md            # AI agent rules & conventions
│   ├── transcripts/
│   │   └── Meeting Sylvan.docx # TPI scoping call notes
│   └── evaluation/             # Benchmark write-ups (markdown)
│       ├── README.md
│       ├── benchmark_results.md
│       ├── evaluation_notebook_doc.md
│       └── reference_answers_review.md
│
├── Report/
│   └── DS205 TPI Final Report.pdf
│
└── data/                       # Gitignored — created when you run the pipeline
    ├── pdfs/                   # Your PDFs (one subfolder per company)
    ├── interim/
    │   ├── raw/                # Cached PDF extraction (pickle)
    │   └── chunks/             # Chunked text (JSONL)
    └── chromadb/               # ChromaDB storage (when using chroma)
```

**Note:** `evaluation/` at the repo root holds benchmark **data** (JSON + `paths.py`). `docs/evaluation/` holds benchmark **documentation** (markdown). They are different folders.

## Further reading


| Document                                                                                                     | Purpose                                                           |
| ------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------- |
| [CONTRIBUTING.md](CONTRIBUTING.md)                                                                           | Configuration, CLI options, internals, pgvector setup, benchmarks |
| [DECISIONS.md](DECISIONS.md)                                                                                 | Design rationale                                                  |
| [docs/README.md](docs/README.md)                                                                             | Documentation index                                               |
| [docs/evaluation/benchmark_results.md](docs/evaluation/benchmark_results.md)                                 | Benchmark tables and recommendation                               |
| [Report/DS205 TPI Final Report.pdf](Report/DS205%20TPI%20Final%20Report.pdf) | Final submission report                                           |


