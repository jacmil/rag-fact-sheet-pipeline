# AI instructions — [YOUR NAME]

**Repo:** `lse-ds205/group-project-json-derulo-comeback-tour` (JSON Derulo Comeback Tour)  
**Project type:** TPI **document discovery** pipeline (scheduled discover → filter → hand-off). **Not** the PS2 RAG pipeline; crawlers and search APIs are in scope.

## My responsibilities on this team

- [ ] Discover (search API / Scrapy)
- [ ] Filter, dedup, hand-off
- [ ] GitHub Actions + pytest
- [ ] Docs + written report

*(Check the boxes that apply to you.)*

## Global rules for the AI

- Follow **[`PROJECT_BOARD.md`](../../PROJECT_BOARD.md)** for tasks and open questions.
- Record strategy and scope in **`DECISIONS.md`** (repo root); do not invent company lists without team agreement.
- Use **`config/*.yaml`** for tunable URLs, queries, allowlists, thresholds.
- **Never** commit API keys or paste secrets into chat logs; use GitHub Secrets / env vars only.
- Prefer **small, focused PRs**; keep Python files roughly under **300 lines**; add **pytest** when touching dedup logic.
- When suggesting a pattern **not taught in DS205**, flag it explicitly so a human can approve.

## Role-specific snippets

_Paste below the contents of the role file(s) you own from [`docs/ai/`](../ai/):_

```markdown
<!-- e.g. paste from docs/ai/role-discover.md -->
```

## Personal notes

_Add preferences: editor, OS, branch naming, time zone for standups, etc._
