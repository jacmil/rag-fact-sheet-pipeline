# AI instructions — CI (GitHub Actions) and testing

**Project:** Discovery pipeline must run on a **schedule** in a **clean** environment with **inspectable logs**.

## Context to give the AI

- Workflow under **`.github/workflows/`** with `schedule` (cron) and **`workflow_dispatch`**.
- Cron runs in **UTC**; document chosen schedule in README or DECISIONS.
- Search API keys (if any) only as **GitHub Secrets**; document secret **names** in `CONTRIBUTING.md` (W07 pattern).
- Upload **logs / run summary** as **workflow artifacts** so markers can inspect each run.
- **pytest** is mandatory for **deduplication** edge cases (redirects, URL variants, replay, empty runs).

## Rules

- Fail the job on **fatal** errors; define what “success with zero new docs” means (exit 0 + clear log).
- Pin dependencies (`requirements.txt` / `environment.yml`) for reproducible Actions runs.
- Do not print secrets or echo env vars that contain keys in logs.

## Checklist alignment

See **Scheduling and CI** and **Dedup and tests** in [`PROJECT_BOARD.md`](../../PROJECT_BOARD.md).
