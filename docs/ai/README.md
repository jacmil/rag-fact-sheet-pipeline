# AI role briefs (JSON Derulo Comeback Tour)

These files are **snippets to merge** into each contributor’s own `docs/contributors/<name>/AI_INSTRUCTIONS.md`. They are not global project rules by themselves.

## Roles

| File | Typical ownership |
|------|-------------------|
| [`role-discover.md`](role-discover.md) | Search API client and/or Scrapy spiders, URL normalization, robots.txt, rate limits |
| [`role-filter-dedup-handoff.md`](role-filter-dedup-handoff.md) | Manifest, relevance rules, reject reasons, downloads to staging, checksums |
| [`role-ci-testing.md`](role-ci-testing.md) | GitHub Actions workflow, secrets, pytest (especially dedup), artifacts |
| [`role-documentation-report.md`](role-documentation-report.md) | README, CONTRIBUTING, DECISIONS, written report, precision/coverage evidence |

One person may own multiple roles; split as your team agrees. Always keep [`PROJECT_BOARD.md`](../../PROJECT_BOARD.md) updated as tasks complete.
