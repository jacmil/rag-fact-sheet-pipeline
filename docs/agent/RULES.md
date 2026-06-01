# DS205 Project Coding Rules and Best Practices

**Advanced Data Manipulation - Winter Term 2025/2026**  
*Project Guidelines for RAG Pipeline (Problem Set 2)*

---

## Core Principles

### 1. Follow DS205 Best Practices

- **Use DS205 coding patterns** from W07–W10 lecture notebooks and lab exercises
- **Pipeline design:** Apply atomicity, idempotency, modularity from W07 Lecture
- **CLI:** Use Click for the pipeline entry point (as practised in W07 Lab)
- **Implement proper error handling** for extraction, embedding, and generation failures

### 2. Code Simplicity and Readability

- **Keep code simple** — Prefer straightforward solutions over complex abstractions
- **Remain practical** — Code should solve real problems, not demonstrate cleverness
- **Easy to read** — Self-documenting with clear variable names
- **Avoid duplication** — Check for existing similar code before creating new functions
- **File length limit** — Keep files under 200–300 lines; refactor when needed
- **Clean and organized** — Clear project structure, consistent formatting
- **Document** — Minimal documentation that earns its place; no over-engineering

### 3. Required Tools and Constraints

| Requirement | Details |
|-------------|---------|
| **PDF extraction** | MUST use the `unstructured` library. Additional tools allowed if justified in CONTRIBUTING. |
| **Models** | MUST use HuggingFace (open-source). Commercial APIs (OpenAI, Anthropic, Google) optional for comparison only. |
| **No web crawlers** | PDFs are provided. Do not write scrapers for this assignment. |

---

## Pipeline Architecture (W07)

Apply these design principles to pipeline stages:

- **Atomicity** — Each stage does one thing and can run independently
- **Idempotency** — Re-running a stage with the same inputs produces the same outputs
- **Modularity** — Stages are separate; data flows via files or clear interfaces

Document your stages in README.md or CONTRIBUTING.md: what each stage does, how they connect, and why you chose this structure.

---

## Project Structure

Conventions for where things live:

- **PDFs** — `data/pdfs/{company}/` (gitignored; obtain from team SharePoint). Document layout in README.
- **Extracted / chunked data** — `data/interim/raw/` (pickle cache), `data/interim/chunks/` (JSONL).
- **Vector stores** — `data/chromadb/` (Chroma) or Docker volume for pgvector; see `vector_store/`.
- **Pipeline code** — `pipeline.py` (Click CLI) plus stage modules: `extract.py`, `embed.py`, `retrieve.py`, `generate.py`, `utils.py`.
- **Environment** — `environment.yml` or `requirements.txt`. Document Python version.
- **Per-tool configuration** — `config/<tool>.config.yaml` (see **Configuration files** below)

---

## Configuration files

Use YAML files under **`config/`** whenever a pipeline stage or feature has **settings that users, experiments, or environments might change**. Hardcoding those values in Python makes runs harder to reproduce, compare, and tune.

### Naming and placement

- **Filename:** `<tool>.config.yaml`, where `<tool>` is the **feature or stage** the settings belong to (e.g. `chunking.config.yaml`, `embedding.config.yaml`). One primary config file per logical tool or stage—not a single giant `settings.yaml` unless the project explicitly standardises on that.
- **Location:** `config/` at the project root, committed with **safe defaults** so clones reproduce behaviour without editing code.

### What belongs in config (vs code)

| Prefer `config/<tool>.config.yaml` | Keep in code |
|-----------------------------------|----------------|
| Model names, dimensions, device hints | Pure algorithms with no sensible “knob” |
| Chunk sizes, overlaps, batch sizes | Internal loop indices, obvious constants |
| Paths that are project conventions but might vary (e.g. output roots) | Hard-coded structure that is truly fixed by the assignment |
| Thresholds, top-*k*, temperature-style generation params | Type definitions, small enums |

**Secrets and keys** must **not** live in committed YAML. Use environment variables (and document them in README); the config file can reference *which* env vars to set, or stay free of secrets entirely.

### Implementation expectations

- **Load explicitly** — Stage code should read the YAML (e.g. via a small loader or Click default path) and fail clearly if required keys are missing.
- **Defaults** — Optional: code may supply fallbacks only for minor, stable values; prefer documenting keys in the YAML (short comments) or in README so experiments stay transparent.
- **New features** — When adding a feature that introduces tunable behaviour, **add or extend** the matching `config/<tool>.config.yaml` rather than scattering literals across modules.

---

## Documentation

- **README.md** — What the pipeline does, how to run it, where output goes
- **CONTRIBUTING.md** — Internals, known bugs, dev setup, how to extend
- **Decisions** — Document all major choices (extraction strategy, chunking, embeddings, retrieval, prompts) in README or CONTRIBUTING with reasoning

---

## Git Workflow

- **Incremental commits** — Small, logical commits. Bulk commits are marked down.
- **Clear commit messages** — Describe what changed and why
- **Regular pushes** — Keep remote up to date for collaboration

---

## Evaluation and Failure Documentation

- **Document what works and what fails** — Clear documentation of pipeline behaviour
- **Explain failures** — Connect failures to specific pipeline decisions (e.g. chunking too coarse, table data lost in extraction)
- **Compare approaches** — At least two approaches (e.g. different embedding models or chunking strategies) with rationale

---

## Reproducibility

- Someone cloning the repo must be able to reproduce results by following README.md
- **Document clearly:** API keys, large model downloads, data not in the repo
- **Run tests locally** — `python -m pytest` (see `tests/`). Contract tests cover both Chroma and pgvector backends.

---

## Code Quality

- **Type hints** — Use where they add clarity (per course engineering principles)
- **No over-engineering** — Unnecessary abstractions and verbose documentation are marked down
- **Every file earns its place** — Remove dead code and unused modules

---

## AI Collaboration (Optional but Encouraged)

- **Flag new strategies** — The agent MUST always flag when using a new coding strategy, pattern, or technique not from DS205 materials, so you can verify it before accepting.
- **Configuration files** — AI assistants should follow the **Configuration files** section above: add `config/<tool>.config.yaml` for any new feature with tunable settings instead of hardcoding them (see **AGENTS.md** for the concise rule).
- Document how you configure AI assistants (AGENTS.md, .github/copilot-instructions.md, CLAUDE.md, or equivalent)
- Share your AI collaboration rules with classmates
- When using AI for techniques not in course materials, verify against official documentation
