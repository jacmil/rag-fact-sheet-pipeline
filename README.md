[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/Ho0VU-Re)
# JSON Derulo Comeback Tour

RAG pipeline for TPI Centre Carbon Performance PDFs. Extracts and chunks sustainability reports, embeds them, retrieves relevant passages, and generates cited answers — with the same pipeline runnable on **ChromaDB** or **pgvector**.

**Recommendation:** For TPI-style retrieval on a laptop, **ChromaDB is the default** (identical retrieval quality, lower query latency, simpler setup). See [docs/evaluation/benchmark_results.md](docs/evaluation/benchmark_results.md) for numbers and when pgvector is worth it.

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
  Hershey_Company/
    *.pdf
  Your_Company_Name/
    *.pdf
```

One subfolder per company; underscores in folder names become spaces in metadata. Set `PDF_SOURCE_DIR=data/pdfs` in `.env` (default in `.env.example`).

The team benchmark used **17 PDFs** (5,913 chunks, 20 reference queries). A local run may use **16 PDFs** if one document is omitted (e.g. Vedanta, which can hang on hi-res OCR).

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

For backend benchmarks and notebooks, see [CONTRIBUTING.md](CONTRIBUTING.md#reference-set-and-benchmark-metrics).

## Project layout

```
pipeline.py, extract.py, embed.py, retrieve.py, generate.py, utils.py
benchmark_metrics.py              # terminal benchmark
vector_store/                     # Chroma + pgvector backends
evaluation/                       # reference_answers.json, document_metadata.json
notebooks/                        # benchmark_exploration.ipynb, reference_answer_builder.ipynb
scripts/check_pgvector.py         # pgvector smoke test
tests/                            # pytest contract suite
docs/                             # handoff, agent rules; benchmark write-ups in docs/evaluation/
Report/                           # final team PDF
data/                             # PDFs and pipeline output (gitignored)
```

**Note:** `evaluation/` at the repo root holds benchmark **data** (JSON + `paths.py`). **`docs/evaluation/`** holds benchmark **documentation** (markdown). They are different folders.

## Further reading

| Document | Purpose |
|----------|---------|
| [CONTRIBUTING.md](CONTRIBUTING.md) | Configuration, CLI options, internals, pgvector setup, benchmarks |
| [DECISIONS.md](DECISIONS.md) | Design rationale |
| [docs/README.md](docs/README.md) | Documentation index |
| [docs/evaluation/benchmark_results.md](docs/evaluation/benchmark_results.md) | Benchmark tables and recommendation |
| [Report/DS205 Final TPI Recommendation Report.pdf](Report/DS205%20Final%20TPI%20Recommendation%20Report.pdf) | Final submission report |
