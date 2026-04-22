# Contributing to chipmunk-dashboard

This guide explains how the project is organized, how to set it up locally,
which checks gate changes, and how to add or modify dashboard features.

---

## Table of Contents

1. [Project structure](#project-structure)
2. [Development setup](#development-setup)
3. [Dependency management](#dependency-management)
4. [Code quality gates](#code-quality-gates)
5. [Running the dashboard locally](#running-the-dashboard-locally)
6. [Environment variables](#environment-variables)
7. [What is hardcoded vs. configurable](#what-is-hardcoded-vs-configurable)
8. [Example: adding a new plot](#example-adding-a-new-plot)
9. [Contributing with AI agents](#contributing-with-ai-agents)
10. [Submitting changes](#submitting-changes)

---

## Project structure

```
chipmunk-dashboard/
├── src/chipmunk_dashboard/
│   ├── __init__.py      # Empty marker file (version is declared in pyproject.toml)
│   ├── cli.py           # CLI entry-point (`chipmunk-dashboard run`)
│   ├── app.py           # Dash layout, callbacks, and figure helpers
│   └── data.py          # Database queries, caching, and metric computation
├── tests/
│   ├── test_app.py          # Unit tests for app.py callbacks
│   ├── test_cli.py          # Unit tests for the CLI
│   ├── test_data.py         # Unit tests for data.py
│   ├── test_integration.py  # Integration tests using real third-party libraries
│   └── test_playwright_ui.py # Browser smoke + screenshot regression tests
├── .github/workflows/ci.yml    # GitHub Actions CI pipeline
├── .pre-commit-config.yaml     # Linting / formatting hooks
├── pyproject.toml       # Build metadata and dependency declarations
├── uv.lock              # Exact pinned dependency snapshot (committed to repo)
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

# Create a virtual environment and install all dependencies (including dev tools)
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

## Dependency management

### How it works

Dependencies are declared in **`pyproject.toml`** in two groups:

- **`dependencies`** — runtime packages (`dash`, `plotly`, `pandas`, `numpy`,
  `labdata`, `setuptools`). Installed whenever anyone runs `uv sync` or installs
  the package.
- **`[dependency-groups] dev`** — dev-only tools (`ruff`, `pre-commit`, `pytest`,
  `pytest-cov`). Only installed when you pass `--all-groups`.

**`uv.lock`** is a complete, exact snapshot — every package pinned to a specific
version with a hash. It's committed to the repo so every developer and every CI
run installs identical versions. You should never edit it by hand; uv manages it.

### Common commands

```bash
# Install everything (runtime + dev tools) from the lock file
uv sync --all-groups

# Add a new runtime dependency (updates pyproject.toml and uv.lock)
uv add some-package

# Add a new dev dependency
uv add --dev some-package

# Upgrade a specific package to its latest allowed version
uv lock --upgrade-package some-package && uv sync --all-groups
```

### Why CI uses `uv sync --frozen`

Plain `uv sync` reads `uv.lock` and installs from it — it won't silently upgrade
packages on its own. What `--frozen` adds is that it also **fails if `pyproject.toml`
and `uv.lock` have drifted out of sync** — for example, if someone added a dep to
`pyproject.toml` but forgot to run `uv sync` to regenerate the lock file. Without
`--frozen`, uv would silently re-resolve and update the lock file in the CI runner,
masking the inconsistency. With `--frozen`, CI fails loudly and the repo stays in a
consistent state.

### Dependabot

Dependabot watches `uv.lock` and opens PRs automatically when new versions of
dependencies are released. Because CI runs on every PR, those upgrades are tested
before they can be merged. If a dep upgrade breaks the test suite, CI fails and
you see it before review/merge.

---

## Code quality gates

There are three layers, each catching different problems at different points.

### 1. Pre-commit hooks (local, on every `git commit`)

Defined in `.pre-commit-config.yaml`. These run on your machine before a commit
is accepted and block it if anything fails:

| Hook | What it does |
|------|-------------|
| `ruff check` | Lints for errors and style issues (unused imports, etc.) |
| `ruff format` | Enforces consistent code formatting |
| `pre-commit-hooks` | Trims trailing whitespace, ensures files end with a newline, checks for case conflicts |

If a hook fails, it fixes the file in place where possible — re-stage and commit
again. You can also run them manually at any time:

```bash
uv run ruff format .
uv run ruff check --fix .
```

Match the docstring style (Google-style `Args` / `Returns` / `Side Effects`) used
in the existing modules.

### 2. GitHub Actions CI (on every push and PR)

Defined in `.github/workflows/ci.yml`. Runs on every push to `main` or `dev`, and
on every pull request targeting those branches. One job with eight sequential steps:

| Step | Command | Purpose |
|------|---------|---------|
| Set up Python | `actions/setup-python` | Installs the exact version from `.python-version` |
| Install uv | `astral-sh/setup-uv` | Gets the uv binary |
| Install dependencies | `uv sync --frozen --all-groups` | Installs everything from the lock file; fails if lock is out of sync with `pyproject.toml` |
| Lint | `uv run ruff check .` | Same check as pre-commit, catches anything that slipped through |
| Format | `uv run ruff format --check .` | Verifies formatting without modifying files |
| Tests | `uv run pytest --cov=src/chipmunk_dashboard --cov-fail-under=90` | Runs the full test suite with coverage; CI fails if coverage drops below 90% |
| Install Playwright browser | `uv run playwright install --with-deps chromium` | Installs Chromium + OS dependencies for browser tests |
| Playwright UI tests | `RUN_PLAYWRIGHT=1 uv run pytest tests/test_playwright_ui.py` | Runs browser-level smoke and screenshot-regression checks |

### 3. The test suite

Five test files plus browser E2E checks. Coverage is still enforced by CI.

### Recommended local command sets

Use one of these two command sets depending on where you are in the edit cycle:

```bash
# Quick loop while iterating
uv run ruff check .
uv run pytest -q tests/test_cli.py
```

```bash
# Pre-PR/full checks (mirrors CI quality gates)
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=src/chipmunk_dashboard --cov-fail-under=90

# Optional locally; required in CI
RUN_PLAYWRIGHT=1 uv run pytest tests/test_playwright_ui.py
```

#### `tests/test_data.py` — unit tests for `data.py`

All of `pandas`, `numpy`, `labdata`, and `chipmunk` are replaced with lightweight
stubs, so these tests never touch a real database and run in milliseconds.

Covers:
- The TTL/LRU cache — time-bucketing logic, `cache_clear`, TTL expiry
- `clear_data_cache()` — every cached function is cleared
- `prewarm_multisession_cache()` — background thread is started, in-flight
  deduplication works, disabled when `CHIPMUNK_PREWARM=0`
- `get_subjects_with_recent_sessions()` — cutoff date is constructed correctly
  and pushed into the DB query restriction
- All query functions — acquire `_DB_LOCK`, call `fetch()` with the right
  arguments, return the right shape

#### `tests/test_app.py` — unit tests for `app.py`

Uses a fake `_Dash` class that stores callbacks in a dict
(`app.callbacks["_update_single"]`), a fake plotly `_Figure`, and a mocked data
layer. This gives direct access to every callback function without starting a
real server.

Covers:
- `_empty_fig()`, `_layout()`, `_perf_log()` helpers
- `_update_date_options` — all guard returns and the success path including
  prewarm call
- `_update_time_options` — no date/no-subjects guard, no sessions on the
  selected date, sessions without underscores, the normal filtering path
- `_clear_subjects` — returns empty list
- `_update_subject_options` — recent subjects get ★ prefix and sort first
- `_update_single`, `_update_multi` — empty-figure fallbacks when no data

#### `tests/test_integration.py` — integration tests with real libraries

Unlike the unit tests above, these import the **actual installed** `dash`,
`plotly`, `pandas`, and `numpy`. Only `labdata` and `chipmunk` are mocked
(they require VPN/database access). The purpose is to catch runtime breakage
that mocked tests miss: if a library renames a class, removes a kwarg, or
changes a return type, unit tests won't notice but these tests will immediately
fail.

Organized in five layers:

**Layer A — API surface**: Directly instantiates every plotly/dash/pandas/numpy
class the app uses and calls every method with the exact kwargs the app passes.
Acts as a canary for library upgrades — covers `go.Scatter`, `go.Scattergl`,
`go.Bar`, `go.Box`, `go.Histogram`, `add_hline`, `add_vline`, `px.colors`,
`Dash`, all `dcc.*` and `html.*` components, `Input`/`Output`, DataFrame
operations, datetime handling, rolling windows, and numpy stats/filtering.

**Layer B — App creation smoke test**: Calls `create_app()` with real Dash and
verifies it returns an actual `Dash` instance with a non-null layout.

**Layer C — Data processing end-to-end**: Runs `session_metrics()` and
`multisession_metrics()` with real pandas/numpy and synthetic DataFrames.
Verifies all output keys are present, all values are Python lists, and edge
cases (empty trials, smoothing) work correctly.

**Layer D — Callback bodies with real plotly**: Uses a fake `_Dash` (for
callback access) combined with real plotly/numpy, so the entire figure-building
logic in `_update_single` and `_update_multi` runs against real `go.Figure`
objects. Covers single-subject path (vertical bars + histograms),
multi-subject path (horizontal bars + box plots), loop skips when session or
metrics are missing, and the smoothing toggle.

**Layer E — data.py non-empty DB paths**: Uses a `_QueryChain` stub that
supports DataJoint's `Table * Table.Part & restriction` chaining syntax,
letting synthetic rows be injected into functions that would otherwise require
a real database. Covers `get_trials_for_sessions` groupby logic,
`get_wait_medians_for_sessions` filtering, `multisession_metrics` date
filtering, zero-choice side bias producing NaN, and `None` reaction times.

#### `tests/test_cli.py` — unit tests for `cli.py`

Tests argument parsing, default values, that `create_app().run()` is called
with the right host/port/debug, and that `--no-open` suppresses the browser.

#### `tests/test_playwright_ui.py` — browser smoke + screenshot regression

Runs real Chromium against a mocked-data dashboard server to verify end-user
interaction flows and coarse layout regressions:

- Subject selection and callback-driven figure rendering
- Single-session tab navigation
- Split-toggle visibility/interaction paths
- Screenshot hash regression checks for Overview and Timing tab states

This module is intentionally gated:

```bash
# Browser tests are opt-in locally
RUN_PLAYWRIGHT=1 uv run pytest tests/test_playwright_ui.py

# Regenerate screenshot hash baselines when UI changes are intentional
RUN_PLAYWRIGHT=1 UPDATE_PLAYWRIGHT_HASHES=1 uv run pytest tests/test_playwright_ui.py
```

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
runtime behavior without modifying source code.

| Variable | Default | Description |
|----------|---------|-------------|
| `CHIPMUNK_CACHE_TTL_SECONDS` | `1800` | Lifetime (seconds) for each TTL time bucket in `data.py`. Reduce for faster data refresh during development. |
| `CHIPMUNK_PROFILE` | `0` | Set to `1` to emit per-call timing logs (milliseconds) for functions that call `_perf_log(...)`. |
| `CHIPMUNK_PREWARM` | `1` | Set to `0` to disable background cache prewarming of multi-session metrics. Prewarming is triggered when subjects are selected, not at server startup. |

Example:

```bash
CHIPMUNK_CACHE_TTL_SECONDS=60 CHIPMUNK_PROFILE=1 uv run chipmunk-dashboard run --debug
```

---

## What is hardcoded vs. configurable

### Configurable at runtime (env vars or CLI flags)

- Server host, port, and debug mode — CLI flags on `chipmunk-dashboard run`
- Cache TTL — `CHIPMUNK_CACHE_TTL_SECONDS`
- Performance profiling — `CHIPMUNK_PROFILE`
- Background prewarming — `CHIPMUNK_PREWARM`

### Configurable by editing `app.py`

- **Theme colors** — the `_THEME` dict at the top of `app.py` controls every
  background, border, accent, and text color used in the UI.
- **Plot dimensions** — `_PLOT_H` (plot height in pixels).
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

## Example: adding a new plot

This walkthrough adds a **cumulative rewards** line plot to the Single Session
section. It demonstrates every file you need to touch and why. The same pattern
applies to the Multi Session section — differences are noted inline.

The four implementation steps are always the same, followed by verification:
1. Compute the metric in `data.py`
2. Register a new graph component in the layout (`app.py`)
3. Add the matching `Output` to the callback decorator (`app.py`)
4. Build and return the figure in the callback body (`app.py`)

A fifth step (verify) confirms everything works with a live reload.

---

### Step 1 — Compute the metric in `data.py`

`session_metrics()` crunches single-session numbers and returns them as a plain
dict. Add your new series to that dict so `app.py` can read it without touching
the database.

Find the `out = dict(...)` block near the bottom of `session_metrics()` and add
your key(s):

```python
# data.py — inside session_metrics(), in the `out = dict(...)` block

out = dict(
    # … existing keys …
    cum_reward_x=trial_nums.tolist(),               # trial numbers (x-axis)
    cum_reward_y=np.cumsum(rewarded).tolist(),       # cumulative correct (y-axis)
)
```

`trial_nums` and `rewarded` are already computed earlier in `session_metrics()`:

```python
# These lines already exist — no need to add them
rewarded = trials.rewarded.to_numpy()
trial_nums = trials.trial_num.to_numpy()
```

> **Multi-session equivalent:** add a new list to the `res = dict(...)` block
> inside `multisession_metrics()` instead. Each entry corresponds to one session
> in the time-series window. Put it inside `res` so the existing smoothing loop
> processes it automatically.

---

### Step 2 — Register the graph component in the layout

Every plot needs a unique string component ID. Add it to one of the `_row(...)`
calls in `create_app()` so the layout knows where to render it.

```python
# app.py — single-session rows (inside create_app())
single_section = html.Div([
    …
    _row("frac-correct", "p-right", "chrono", "session-perf"),  # Row 1
    _row("init-line", "init-hist"),                              # Row 2
    _row("wait-delta-line", "wait-delta-hist"),                  # Row 3
    _row("react-line", "react-hist"),                            # Row 4
    _row("cum-reward"),                                          # ← add Row 5
])
```

`_row("cum-reward")` creates a full-width `dcc.Graph` with id `"cum-reward"`.
Pass multiple IDs (e.g. `_row("cum-reward", "another-plot")`) to get a
side-by-side grid.

> **Multi-session equivalent:** add the ID to one of the `_row(...)` calls in
> `multi_section` instead.

---

### Step 3 — Add the `Output` to the callback decorator

Dash connects layout components to callbacks through `Output` / `Input`
declarations. Each plot must have a matching `Output` in exactly one callback.

Single-session plots belong to `_update_single`; multi-session plots belong to
`_update_multi`. Add the new output **and** increment the `n` counter so the
empty-figure fallback produces the right number of figures:

```python
# app.py — _update_single callback decorator
@app.callback(
    Output("frac-correct",      "figure"),
    Output("p-right",           "figure"),
    Output("chrono",            "figure"),
    Output("session-perf",      "figure"),
    Output("init-line",         "figure"),
    Output("init-hist",         "figure"),
    Output("wait-delta-line",   "figure"),
    Output("wait-delta-hist",   "figure"),
    Output("react-line",        "figure"),
    Output("react-hist",        "figure"),
    Output("cum-reward",        "figure"),   # ← add this line
    Input("subjects",           "value"),
    Input("session-time",       "value"),
    Input("auto-refresh",       "n_intervals"),
)
def _update_single(subjects, session_name, n_intervals):
    n = 11   # ← was 10, increment by 1
    …
```

The order of `Output` declarations must exactly match the order of values in
the `return` tuple at the end of the function.

---

### Step 4 — Build and return the figure

**Before the loop** (alongside the other `fig_*` initialisations):

```python
fig_cr = go.Figure()
```

**Inside the `for i, subj in enumerate(valid_subjects):` loop**, after `sm` is
fetched, add your trace using the already-computed `sm` dict — don't call
`session_metrics()` again:

```python
if sm and sm["cum_reward_x"]:
    fig_cr.add_trace(
        go.Scatter(
            x=sm["cum_reward_x"],
            y=sm["cum_reward_y"],
            mode="lines",
            name=subj,
            showlegend=len(valid_subjects) > 1,
            line=dict(color=c, width=2),
            hovertemplate="%{y} rewards" + "<extra>" + subj + "</extra>",
        )
    )
```

**After the loop** (alongside the other `_layout()` calls):

```python
_layout(
    fig_cr,
    title="Cumulative Rewards",
    xaxis_title="trial number",
    yaxis_title="rewards",
)
```

**In the `return` statement** — append `fig_cr` in the same position as the
`Output` you added in Step 3:

```python
return (
    fig_fc, fig_pr, fig_ch, fig_sp,
    fig_il, fig_ih,
    fig_wdl, fig_wdh,
    fig_rl, fig_rh,
    fig_cr,   # ← new
)
```

---

### Step 5 — Verify

```bash
uv run chipmunk-dashboard run --debug
```

Select a subject and confirm the new plot appears in the Single Session section.
Hot-reload will pick up any further edits automatically.

---

## Contributing with AI agents

AI coding agents can be useful here, but they work best when you give them the
same repo-specific constraints a human contributor would need.

### Recommended workflow

1. Start from a clean branch based on `dev`.
2. Point the agent at this repo's source-of-truth docs first:
   `CONTRIBUTING.md`, `AGENTS.md`, and the relevant files it will edit.
3. Give the agent a narrow task with explicit scope, for example:
   "Add a new multi-session plot", "Update the contributing guide", or
   "Fix the failing Plotly integration test without changing app behavior."
4. Require the agent to preserve the module boundary:
   `cli.py -> app.py -> data.py`.
   `app.py` should not query the database directly, and `data.py` should not
   import from `app.py`.
5. Have the agent run the same checks required of any contributor before you
   accept its output.
6. Review the diff yourself before opening a PR.

### Repo-specific guidance for agent-driven changes

- Ask the agent to inspect existing patterns before editing. Most regressions in
  this repo come from skipping the established callback, layout, or test shape.
- If the change adds a plot, tell the agent to use the repo's `add-plot` skill
  at `.agents/skills/add-plot/SKILL.md`. That skill walks the required wiring:
  metric, layout entry, callback `Output`, return tuple, and matching tests.
- If the agent adds new Dash imports in `app.py`, make sure it also updates the
  fake Dash shims in `tests/test_app.py` and `tests/test_integration.py`.
- Do not accept dependency upgrades that loosen the intentional
  `setuptools < 80` constraint without a concrete compatibility reason and test
  evidence.
- Treat agent output as a draft until it passes lint, tests, and a human review.

### Minimum prompt checklist

When prompting an agent, include:

- the target branch base (`dev`)
- the files or module area it may edit
- whether behavior should change or stay identical
- the required verification commands
- any repo rules that matter for the task (`setuptools < 80`, fake Dash test
  updates, and "use `.agents/skills/add-plot/SKILL.md` if this adds a plot",
  etc.)

### Verification commands

At minimum, ask the agent to run:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=src/chipmunk_dashboard --cov-fail-under=90
```

Include Playwright when the UI layout or interaction flow changed:

```bash
RUN_PLAYWRIGHT=1 uv run pytest tests/test_playwright_ui.py
```

---

## Submitting changes

1. **Branch from `dev`** and create a focused feature branch:

   ```bash
   git checkout dev
   git pull --ff-only
   git checkout -b my-feature
   ```

2. **Make your changes**, keeping `data.py` and `app.py` concerns separate.

3. **Confirm your branch is based on `dev`**:

   ```bash
   git merge-base --is-ancestor dev HEAD && echo "branch is based on dev"
   ```

4. **Run all quality checks locally** before pushing:

   ```bash
   uv run ruff check .
   uv run ruff format --check .
   uv run pytest --cov=src/chipmunk_dashboard --cov-fail-under=90
   RUN_PLAYWRIGHT=1 uv run pytest tests/test_playwright_ui.py
   ```

5. **Test manually** by running the dashboard with `--debug` and verifying the
   affected views.

6. **Open a pull request** against `dev` with a clear description of what
   changed and why.

For questions or to discuss larger changes before writing code, open a GitHub
Issue first.
