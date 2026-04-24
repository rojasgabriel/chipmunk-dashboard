# AI Agent Guide

Repo-specific rules only. Broader project context and handoffs belong in the
wiki, not here.

## Rules

- Preserve the dependency direction: `cli.py -> app.py -> data.py`.
- `app.py` must not query the database directly.
- If you add new Dash imports in `app.py`, update the fake Dash shims in
  `tests/test_app.py` and `tests/test_integration.py`.
- Keep callback `Output(...)` order aligned with callback return tuples.
- Do not loosen `setuptools < 80` without concrete validation.
- If a change adds a plot, use `.agents/skills/add-plot/SKILL.md`.

## Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=src/chipmunk_dashboard --cov-fail-under=90
```

For UI changes, also run:

```bash
uv run chipmunk-dashboard run --debug
```
