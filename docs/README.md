# Project documentation

## Tracking and planning

- **[PROJECT_BOARD.md](../PROJECT_BOARD.md)** (repo root) — task checklist, deliverables, and design questions for the TPI **document discovery** pipeline (discover → filter → hand-off, GitHub Actions cron).
- **`DECISIONS.md`** (repo root, create when you start) — sector, companies, search vs crawl vs hybrid, relevance definition, tradeoffs.

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

That file was carried from **Problem Set 2** (RAG) conventions. For **this** project, web discovery (Scrapy/Selenium) and scheduled GitHub Actions are **in scope**. Prefer the discovery-specific instructions in [`docs/ai/`](ai/) and your personal [`docs/contributors/`](contributors/) file.
