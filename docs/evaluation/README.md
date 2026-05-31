# Evaluation Documentation

This folder holds human-readable notes for the ChromaDB vs pgvector evaluation.
The runnable benchmark files stay at the repository root because the code and
notebooks currently import them from there.

| File | Purpose |
|------|---------|
| [`evaluation_notebook.md`](evaluation_notebook.md) | Latest pipeline smoke test and benchmark findings |
| [`reference_answers_review.md`](reference_answers_review.md) | Manual labelling rules and reference set summary |

Root-level evaluation files:

| File | Why it stays at root |
|------|----------------------|
| `benchmark_metrics.py` | Reusable benchmark functions and terminal report |
| `benchmark_exploration.ipynb` | Notebook workflow for pandas tables and optional JSON export |
| `reference_answer_builder.ipynb` | Notebook for inspecting chunks and building labels |
| `reference_answers.json` | Default path used by benchmark code and notebooks |
| `document_metadata.json` | Default path used by embedding metadata code |
| `evaluation_results.json` | Optional export target, intentionally empty until regenerated |
