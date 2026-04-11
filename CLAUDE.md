# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies (runtime + dev)
uv sync --all-groups

# Run tests (90% coverage minimum enforced)
uv run pytest --cov=src/chipmunk_dashboard --cov-fail-under=90

# Run a single test
uv run pytest tests/test_integration.py::TestCallbacksWithRealPlotly::test_update_single_multi_subject_uses_box_and_horizontal_bars -v

# Lint / format
uv run ruff check .
uv run ruff format .

# Run the app
uv run chipmunk-dashboard run --debug
```

CI runs `ruff check`, `ruff format --check`, and pytest on every push/PR to `main`. Pre-commit hooks enforce the same checks locally.

## Architecture

The app is a Plotly Dash dashboard for visualizing mouse behavioral data from the `chipmunk` task. Three modules, strict one-way dependency:

```
cli.py → app.py → data.py → labdata (external DB)
```

**`data.py`** — all database access and metric computation. Never imported by anything other than `app.py`. All query functions are wrapped with `@_ttl_lru_cache` (LRU + time-bucketing) and protected by `_DB_LOCK` (RLock) for thread safety. Key functions:
- `get_all_subjects()` — sorted list of all subject names
- `get_subjects_with_recent_sessions(days=14)` — set of subjects with a session in the last N days
- `get_subjects_for_date(date_str)` — sorted list of subjects with at least one session on a given date (YYYYMMDD format); used for date→subject filtering
- `get_sessions(subject)` — list of session IDs for a subject
- `session_metrics(subject, session)` — per-trial metrics for a single session (psychometric curve, rolling performance, RT, initiation time, etc.)
- `multisession_metrics(subject, ...)` — session-level aggregates over N sessions back (performance, EW rate, side bias, water earned)
- `prewarm_multisession_cache()` — spawns a daemon thread to precompute multi-session metrics when the date changes; deduplicates in-flight requests via `_PREWARM_INFLIGHT`

**`app.py`** — Dash layout and six callbacks. `app.py` never touches the database directly. A `_layout(fig, **kwargs)` helper applies consistent styling to every figure.

The subject sidebar uses **two separate `dcc.Checklist` components** (`subjects-recent` and `subjects-older`) separated by an `html.Hr` divider. Recent subjects (sessions in the last 14 days) are styled in accent blue + bold; older subjects use plain labels. All callbacks merge the two value lists with `(subjects_recent or []) + (subjects_older or [])`.

Key callbacks:
- `_update_date_options` — subject selection or Today button click → date picker bounds (spans all selected subjects) and default date
- `_update_time_options` — date + subject change → session time dropdown
- `_clear_subjects` — clear button → empties both subject checklists
- `_update_subject_options` — date selection → filters subject list to only those with sessions on that date; falls back to all subjects when no date is set
- `_update_single` — session selection → 10 single-session figures (outcome bars, psychometric/chronometric curves, rolling metrics); uses `State("session-date")` to resolve sessions for additional subjects when multiple are selected
- `_update_multi` — multi-session controls → 8 trend figures (performance, EW rate, bias, RT, initiation, water)

Single-session callbacks adapt based on subject count: vertical stacked bars + histograms for one subject, horizontal bars + box plots for multiple.

**`cli.py`** — thin wrapper that parses `--port/--host/--debug/--no-open`, starts the Dash server, and handles browser auto-open (with Werkzeug reloader awareness).

## Dependencies

`setuptools` is pinned to `<80` in `pyproject.toml`. This is intentional: `setuptools>=80` removes `pkg_resources` from its distribution, which breaks `datajoint 0.x` (a transitive dependency of `labdata`). Do not bump `setuptools` above 80.

## Tests

Four test files, 90 tests, ~98% coverage. No real database required — all `labdata` access is mocked.

| File | What it tests |
|------|--------------|
| `test_data.py` | Unit tests for metric computation with mocked pandas/numpy/labdata |
| `test_app.py` | Unit tests with a fake Dash and mocked data layer |
| `test_integration.py` | Full callbacks with real plotly/pandas/numpy — catches library breaking changes like the plotly 6.x `titlefont` removal |
| `test_cli.py` | Argument parsing and server startup |

The fake Dash module in `test_app.py` and `_import_app_fake_dash_real_plotly` in `test_integration.py` must expose `Dash`, `dcc`, `html`, `Input`, `Output`, `State`, and `ctx`. When adding new Dash imports to `app.py`, update both fake modules accordingly.

When adding a plot: add a trace in the relevant callback in `app.py`, add the corresponding `Output` to the callback decorator, wire it to the layout, then add coverage in both `test_app.py` and `test_integration.py`.

## Useful environment variables

| Variable | Default | Effect |
|----------|---------|--------|
| `CHIPMUNK_CACHE_TTL_SECONDS` | `1800` | Cache TTL bucket size in seconds |
| `CHIPMUNK_PROFILE` | `0` | Set to `1` to emit per-callback timing logs |
| `CHIPMUNK_PREWARM` | `1` | Set to `0` to disable background cache prewarming |
