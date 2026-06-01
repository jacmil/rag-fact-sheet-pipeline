# Evaluation Documentation

This folder holds human-readable notes for the ChromaDB vs pgvector evaluation.
Runnable benchmark code stays at the repository root; notebooks and evaluation
data live in dedicated folders.

| File | Purpose |
|------|---------|
| [`benchmark_results.md`](benchmark_results.md) | Main benchmark summary: speed, retrieval quality, ingestion, document-size tests, recommendation |
| [`evaluation_notebook_doc.md`](evaluation_notebook_doc.md) | Detailed run notes from the latest pipeline smoke test and benchmark |
| [`reference_answers_review.md`](reference_answers_review.md) | Manual labelling rules and reference set summary |

Evaluation assets:

| File | Purpose |
|------|---------|
| `benchmark_metrics.py` | Reusable benchmark functions and terminal report (repo root) |
| `notebooks/benchmark_exploration.ipynb` | Notebook workflow for pandas tables and optional JSON export |
| `notebooks/reference_answer_builder.ipynb` | Notebook for inspecting chunks and building labels |
| `evaluation/reference_answers.json` | Manual Recall@5 reference set |
| `evaluation/document_metadata.json` | Company/year/sector metadata overrides for embedding |
| `evaluation/evaluation_results.json` | Optional export target, intentionally empty until regenerated |
| `evaluation/paths.py` | Repo-root-relative paths used by benchmark code and notebooks |
