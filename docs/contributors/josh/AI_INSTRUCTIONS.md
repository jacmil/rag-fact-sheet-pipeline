# AI instructions — Josh

**Repo:** JSON Derulo Comeback Tour — TPI scheduled **document discovery** (discover → filter → hand-off, GitHub Actions).

## Responsibilities

- Coordinate with teammates on **scope lock** (sector, 2–4 companies, hand-off contract) — see [`PROJECT_BOARD.md`](../../../PROJECT_BOARD.md).
- Likely focus areas: **architecture**, **config layout**, **DECISIONS.md**, **CI/workflow** review — adjust checkboxes as the team splits work.

## Global rules for the AI

- This project **allows** Scrapy/Selenium and search APIs; ignore any “no crawlers” note from PS2-only docs unless the team explicitly adopts it here.
- Tunable behaviour → **`config/<tool>.config.yaml`**; secrets → **GitHub Secrets** / env only.
- **Dedup** changes require **pytest** coverage.
- Link contributors to [`docs/README.md`](../../README.md) and [`docs/ai/README.md`](../../ai/README.md).

## Role references

Merge in as work is assigned:

- Discover: [`docs/ai/role-discover.md`](../../ai/role-discover.md)
- Filter / hand-off / dedup: [`docs/ai/role-filter-dedup-handoff.md`](../../ai/role-filter-dedup-handoff.md)
- CI / testing: [`docs/ai/role-ci-testing.md`](../../ai/role-ci-testing.md)
- Docs / report: [`docs/ai/role-documentation-report.md`](../../ai/role-documentation-report.md)

## Additional context

- Personal coding preferences: see [`RULES.md`](RULES.md) for general DS205 style (type hints, clarity, incremental commits) — **override** where it conflicts with discovery (e.g. crawlers allowed here).
