# AI instructions — Filter, dedup, and hand-off

**Project:** Scheduled discovery pipeline — **filter** (new + relevant), **deduplicate**, **download** to staging for **decoupled** PS2-style ingestion.

## Context to give the AI

- **Filter:** compare candidates to a **manifest** of seen documents; apply the team’s **relevance** definition from `DECISIONS.md`; log a **reject reason** for every dropped URL.
- **Dedup:** canonical URL and/or **content hash** after download; this logic **must be covered by pytest** (course requirement).
- **Hand-off:** write PDFs under an agreed **staging layout** (e.g. sector/company) plus **manifest rows** (URL, path, sha256, retrieved_at, company, source). Ingestion must consume this **without code changes** on the PS2 side.

## Rules

- Staging writes should be **atomic** (temp file → rename) where possible.
- Emit a **structured run summary** (JSON) suitable for GitHub Actions artifacts.
- Keep modules **small** (<300 lines per file); split discover vs filter vs download if needed.
- Document the **hand-off contract** in README once stable.

## Checklist alignment

See **Filter**, **Hand-off**, and **Dedup and tests** in [`PROJECT_BOARD.md`](../../PROJECT_BOARD.md).
