# Contributing to chipmunk-dashboard

This repo is small. The main thing is to keep the boundaries clean and run the
same checks CI runs.

## Setup

Prerequisites:

- `uv`
- VPN / lab network access for live database use
- the `chipmunk` labdata plugin in your `labdata` plugins folder

Install:

```bash
git clone https://github.com/rojasgabriel/chipmunk-dashboard.git
cd chipmunk-dashboard
uv sync --all-groups
uv run pre-commit install
```

## Repo shape

```text
src/chipmunk_dashboard/
  cli.py
  app.py
  data.py
tests/
```

- `data.py` does database access and metric computation.
- `app.py` does layout, callbacks, and figures.
- `cli.py` starts the app.

Keep the dependency direction one-way:

```text
cli.py -> app.py -> data.py
```

`app.py` should not query the database directly.

## Checks

Run these before you open a PR:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=src/chipmunk_dashboard --cov-fail-under=90
```

If you changed UI layout or interaction flow, also run:

```bash
RUN_PLAYWRIGHT=1 uv run pytest tests/test_playwright_ui.py
uv run chipmunk-dashboard run --debug
```

CI runs the same lint, format, and test checks on pushes and PRs.

## Common changes

### Adding a plot

Use `.agents/skills/add-plot/SKILL.md`.

That skill walks the full change:

- metric in `data.py` if needed
- layout row in `app.py`
- callback `Output(...)` and return tuple
- tests in `tests/test_app.py` and `tests/test_integration.py`

### Adding Dash imports

If you add new imports from `dash` in `app.py`, update the fake Dash shims in:

- `tests/test_app.py`
- `tests/test_integration.py`

### Dependencies

Do not loosen `setuptools < 80` without a real reason and validation.
`labdata` still depends on the older `pkg_resources` path.

## AI agents

Repo-specific agent rules live in `AI_AGENTS.md`.

If you use an agent, point it there first, keep the task narrow, and review the
diff yourself before opening a PR.

## Submitting changes

Work from `dev`:

```bash
git checkout dev
git pull --ff-only
git checkout -b my-feature
```

Then make the change, run the checks above, test the affected view in the app
if needed, and open a PR against `dev`.
