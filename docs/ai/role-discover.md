# AI instructions — Discover stage

**Project:** DS205 group project — TPI corporate climate disclosure **discovery** (not PS2 ingestion). Scrapy/Selenium and search APIs are **allowed** and often required.

## Context to give the AI

- We implement **discover**: find **candidate PDF URLs** for 2–4 companies in one TPI sector.
- Approach is chosen in `DECISIONS.md`: **search API**, **sitemap/IR crawl**, or **hybrid**.
- Output of discover is a **list of candidate URLs** (plus source metadata) for the filter stage — not final downloads.

## Rules

- Respect **robots.txt**, crawl-delay, and reasonable **rate limits**; use an identifiable **User-Agent**.
- **Normalize URLs** (scheme, host, tracking query params policy) before passing downstream.
- Restrict candidates to **agreed domains** (allowlist per company) where the brief requires it.
- Log **counts per source** (queries, pages, URLs found) for observability.
- Put tunable lists (domains, seed URLs, query strings) in **`config/*.yaml`**, not hardcoded in Python.
- **Never** commit API keys; use env vars / GitHub Secrets only.

## Checklist alignment

See **Discover** section in [`PROJECT_BOARD.md`](../../PROJECT_BOARD.md).
