# Project documentation

## Tracking and planning

- **[PROJECT_BOARD.md](../PROJECT_BOARD.md)** (repo root) — task checklist and remaining deliverables.
- **[DECISIONS.md](../DECISIONS.md)** (repo root) — vector store, pipeline, evaluation, and deployment tradeoffs.
- **[docs/evaluation/](evaluation/)** — benchmark notes, reference set documentation, and labelling rules.

## AI assistant instructions (per person)

Each teammate should keep a short **AI_INSTRUCTIONS** file so Cursor / Copilot / other tools stay aligned with this repo and DS205 expectations.

| Location | Purpose |
|----------|---------|
| [`docs/ai/README.md`](ai/README.md) | How to use the role briefs below |
| [`docs/ai/`](ai/) | **Role briefs** — copy relevant bullets into your personal file |
| [`docs/contributors/`](contributors/) | **Per-person folders** — `docs/contributors/<name>/AI_INSTRUCTIONS.md` |

### Quick start

1. Create `docs/contributors/<your-github-username>/AI_INSTRUCTIONS.md` (see [`contributors/_TEMPLATE_AI_INSTRUCTIONS.md`](contributors/_TEMPLATE_AI_INSTRUCTIONS.md)).
2. Copy sections from the **role** file(s) you own from [`docs/ai/`](ai/).
3. In Cursor: **Settings → Rules** for this project, or add `@docs/contributors/<you>/AI_INSTRUCTIONS.md` when prompting.

## Note on `docs/josh/RULES.md`

That file was carried from **Problem Set 2** conventions. For this project, the
active deliverable is the ChromaDB vs pgvector RAG backend comparison. Prefer the
project README, CONTRIBUTING guide, DECISIONS file, and evaluation notes for the
current workflow.
