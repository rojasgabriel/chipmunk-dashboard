# AI Agent Guide

Repo-specific rules only. Use Notion for project planning and live Git/GitHub
state for current work.

## Rules

- Preserve the dependency direction: `cli.py -> app.py -> data.py`.
- `app.py` must not query the database directly.
- If you add new Dash imports in `app.py`, update the fake Dash shims in
  `tests/test_app.py` and `tests/test_integration.py`.
- Keep callback `Output(...)` order aligned with callback return tuples.
- Do not loosen `setuptools < 80` without concrete validation.
- If a change adds a plot, use `.agents/skills/add-plot/SKILL.md`.
- Treat incorrect trials as `with_choice == 1` and `rewarded == 0`; do not
  derive them from `punished`.
- Keep the trial-count pacing x-axis in elapsed session minutes. Preserve trial
  number in hover data, and use `water_cum_time_x` for its water overlay.
- Keep debug and fixture UI paths usable without a live database.

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
