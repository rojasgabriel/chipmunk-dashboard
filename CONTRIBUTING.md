# Contributing to chipmunk-dashboard

Thank you for your interest in contributing!
This guide explains how the project is structured, what is configurable vs. hardcoded,
and how to submit changes.

---

## Table of Contents

1. [Project structure](#project-structure)
2. [Development setup](#development-setup)
3. [Code style](#code-style)
4. [Running the dashboard locally](#running-the-dashboard-locally)
5. [Environment variables](#environment-variables)
6. [What is hardcoded vs. configurable](#what-is-hardcoded-vs-configurable)
7. [Submitting changes](#submitting-changes)

---

## Project structure

```
chipmunk-dashboard/
├── src/chipmunk_dashboard/
│   ├── __init__.py      # Package version / public surface
│   ├── cli.py           # CLI entry-point (`chipmunk-dashboard run`)
│   ├── app.py           # Dash layout, callbacks, and figure helpers
│   └── data.py          # Database queries, caching, and metric computation
├── notebooks/
│   └── ingest_subjects.ipynb   # One-off data exploration / ingestion helpers
├── pyproject.toml       # Build metadata and dependency declarations
├── .pre-commit-config.yaml     # Linting / formatting hooks
└── README.md
```

### Module responsibilities

| Module | Responsibility |
|--------|---------------|
| `cli.py` | Parses `chipmunk-dashboard run` arguments and starts the Dash server. |
| `app.py` | Defines the Dash layout (sidebar, plot grid) and all `@app.callback` functions that populate figures. Theme constants and shared plot helpers live here. |
| `data.py` | All database access (`labdata` / `chipmunk` schemas). Exposes cached query functions (`get_all_subjects`, `get_sessions`, `session_metrics`, `multisession_metrics`, …) used by `app.py`. |

The split is intentional: `data.py` should never import from `app.py`, and `app.py`
should never talk to the database directly. Keep this boundary clean when adding
features.

---

## Development setup

### Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) (package and environment manager)
- VPN / lab network access (required to reach the database at runtime)
- The [chipmunk labdata plugin](https://github.com/churchlandlab/chipmunk/tree/labdata) in your `labdata` plugins folder

### Install

```bash
git clone https://github.com/rojasgabriel/chipmunk-dashboard.git
cd chipmunk-dashboard

# Creates a virtual environment and installs all dependencies
uv sync --all-groups
```

### Install pre-commit hooks

```bash
uv run pre-commit install
```

Hooks run automatically on every `git commit`. You can also run them manually:

```bash
uv run pre-commit run --all-files
```

---

## Code style

The project uses [ruff](https://docs.astral.sh/ruff/) for both linting and
formatting, configured via the pre-commit hooks in `.pre-commit-config.yaml`.

Run the formatter and linter at any time with:

```bash
uv run ruff format .
uv run ruff check --fix .
```

There are no additional style rules beyond what ruff enforces. Match the docstring
style (Google-style Args / Returns / Side Effects) used in the existing modules.

---

## Running the dashboard locally

```bash
# Default: localhost:8050, auto-opens browser
uv run chipmunk-dashboard run

# Hot-reload during development (Werkzeug reloader)
uv run chipmunk-dashboard run --debug

# Custom host / port
uv run chipmunk-dashboard run --host 0.0.0.0 --port 9000

# Skip browser auto-open
uv run chipmunk-dashboard run --no-open
```

---

## Environment variables

These variables can be set in your shell before starting the server to change
runtime behaviour without modifying source code.

| Variable | Default | Description |
|----------|---------|-------------|
| `CHIPMUNK_CACHE_TTL_SECONDS` | `1800` | Lifetime (seconds) for each LRU cache bucket in `data.py`. Reduce for faster data refresh during development. |
| `CHIPMUNK_PROFILE` | `0` | Set to `1` to emit per-call timing logs (milliseconds) for every data-layer and callback function. |
| `CHIPMUNK_PREWARM` | `1` | Set to `0` to disable background cache prewarming of multi-session metrics on startup. |

Example:

```bash
CHIPMUNK_CACHE_TTL_SECONDS=60 CHIPMUNK_PROFILE=1 uv run chipmunk-dashboard run --debug
```

---

## What is hardcoded vs. configurable

Understanding what can be changed at runtime versus what requires a code edit
helps avoid confusion when extending the project.

### Configurable at runtime (env vars or CLI flags)

- Server host, port, and debug mode — CLI flags on `chipmunk-dashboard run`
- Cache TTL — `CHIPMUNK_CACHE_TTL_SECONDS`
- Performance profiling — `CHIPMUNK_PROFILE`
- Background prewarming — `CHIPMUNK_PREWARM`

### Configurable by editing `app.py`

- **Theme colours** — the `_THEME` dict at the top of `app.py` controls every
  background, border, accent, and text colour used in the UI.
- **Plot dimensions** — `_PLOT_H` (plot height) and `_MAX_W` (max plot width).
- **Layout margins / spacing** — `_MARGIN` and the shared `_layout()` helper.
- **Auto-refresh interval** — the `dcc.Interval` `interval` parameter (default
  60 minutes).
- **Sidebar controls** — the "Sessions back" slider range (`min`/`max`/`marks`)
  and smoothing window slider live directly in the `create_app()` function.
- **Dashboard sections** — the two `html.Div` blocks (`single_section`,
  `multi_section`) and the `_row(...)` calls that define which plot IDs appear
  in each row.

### Configurable by editing `data.py`

- **Rolling window size** — the `win = 20` value inside `session_metrics()`
  controls the trial window used for sliding-window performance, EW rate,
  initiation, wait-delta, and reaction-time rolling medians.
- **Reaction time cutoff** — `rts < 2` (seconds) filters outlier reaction times.
- **Wait time bounds** — `wait_actual < 30` and `wait_min < 30` (seconds).
- **LRU cache sizes** — the `maxsize` argument on each `@_ttl_lru_cache` call.
- **Fields fetched from the database** — the `fields` list in
  `get_subject_data()` and the `fetch()` calls in other functions.
- **Stimulus intensity mapping** — `_compute_intensity()` maps modality names
  (`audio`, `visual`, `visual+audio`) to their rate columns. Add a new entry
  there when a new modality is introduced.

### Truly hardcoded (requires coordinated changes)

- **Database schema tables** — `DecisionTask.TrialSet`, `Chipmunk`,
  `Chipmunk.Trial`, `Chipmunk.TrialParameters`, and `Watering` are imported
  from `labdata` / `chipmunk` and used by name throughout `data.py`. Changing
  them requires updating every query site.
- **Session name format** — `YYYYMMDD_HHMMSS` is assumed in the date-picker and
  time-dropdown parsing logic in `app.py` (`_update_date_options`,
  `_update_time_options`).
- **Dash component IDs** — string IDs like `"subjects"`, `"session-date"`, and
  `"performance"` are shared between the layout and the callback decorators.
  Renaming one requires updating both places.

---

## Submitting changes

1. **Fork** the repository and create a feature branch:

   ```bash
   git checkout -b my-feature
   ```

2. **Make your changes**, keeping `data.py` and `app.py` concerns separate.

3. **Lint and format**:

   ```bash
   uv run pre-commit run --all-files
   ```

4. **Test manually** by running the dashboard with `--debug` and verifying the
   affected views.

5. **Open a pull request** against `dev` with a clear description of what
   changed and why.

For questions or to discuss larger changes before writing code, open a GitHub
Issue first.
