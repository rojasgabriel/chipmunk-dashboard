---
name: add-plot
description: Add a new Plotly plot to the chipmunk dashboard. Walks the full wiring — optional data-layer extension, layout row, callback Output + return tuple, single/multi-subject adaptive rendering, and test coverage in both test_app.py and test_integration.py — in the correct order. Use when the user asks to add a plot, chart, figure, or visualization to the dashboard.
---

# Add a plot to the chipmunk dashboard

This skill walks the full wiring for a new Plotly plot. The dashboard has a strict one-way module dependency (`cli.py → app.py → data.py`) and a 90% coverage floor enforced in CI (`--cov-fail-under=90`), so skipping steps fails the build. Follow this checklist in order.

## Step 1 — Gather requirements upfront

Before writing any code, ask the user (batch the questions):

1. **Plot ID and title.** Kebab-case ID (e.g. `water-heatmap`) used as the Dash component id. A human title shown on the figure.
2. **Section.** Single-session (`_update_single`) or multi-session (`_update_multi`)?
   - Single-session = metrics from one session, e.g. psychometric curve, per-trial RT, rolling performance within a session.
   - Multi-session = trends across sessions, e.g. daily water earned, side bias over time.
3. **Data source.** An existing key returned from `session_metrics` / `multisession_metrics` in `data.py`, OR a new metric that needs computing. If new, is the metric trial-level (extend `session_metrics`) or session-aggregate (extend `multisession_metrics`)?
4. **Figure type.** `go.Bar`, `go.Scatter`, `go.Box`, `go.Histogram`, `go.Heatmap`, etc.
5. **Row placement.** Append to an existing `_row(...)` in the target section, or add a new row? If new, where in the section?
6. **Single-session only:** does the plot need adaptive single- vs. multi-subject rendering? Most existing single-session plots do (vertical bars/histograms for 1 subject; horizontal bars / box plots for many). Check existing plots like `frac-correct`, `p-right`, `rt-hist` for the pattern.

Do not begin writing code until these are answered.

## Step 2 — (Optional) Extend the data layer

Only if the user selected "new metric." Path: `src/chipmunk_dashboard/data.py`.

**Preferred path — extend an existing function.** Compute the new metric inside `session_metrics` (trial-level) or `multisession_metrics` (session-aggregate) and add it as a new key in the dict these functions return. No new top-level query function is needed. Update `tests/test_data.py` with a test that covers the new key — follow the mock pattern used by other tests in the file.

**Only if the query shape is genuinely new:** add a new top-level function. Requirements:
- Decorate with `@_ttl_lru_cache(maxsize=...)` (see existing decorators in the file for sizing).
- Read the DB under `with _DB_LOCK:`.
- Register `<new_func>.cache_clear()` inside `clear_data_cache()` — grep the file for `cache_clear()` to find the block and add it there. Forgetting this leaks stale data across date rollovers.
- Add a mock-based unit test in `tests/test_data.py`. `test_get_subjects_for_date_filters_at_query` is a recent reference.

Remember: `data.py` is never imported by anything other than `app.py`. Don't leak DB calls into `app.py`.

## Step 3 — Wire the layout

Path: `src/chipmunk_dashboard/app.py`. Grep for `single_section =` and `multi_section =` to find the two sections (line numbers drift — always grep, don't hard-code).

- **Append to an existing row:** add the new plot ID as a string to the `_row(...)` call. Existing rows group related metrics (e.g. psychometric curve + chronometric curve live together).
- **New row:** create a new `_row("id1", "id2", ...)` call in the list of row arguments for the section's `html.Div(...)`. Rows render left-to-right in a CSS grid of `repeat(N, 1fr)` where N is the number of ids.

## Step 4 — Wire the callback

Same file: `src/chipmunk_dashboard/app.py`. Two big callbacks:
- `_update_single` — decorated with `@app.callback(...)`, driven by subject + session selection, returns a tuple of 10 figures today.
- `_update_multi` — driven by subject + sessions-back + smoothing controls, returns a tuple of 8 figures today.

**Both the decorator Output list and the return tuple must change in lockstep.** The Nth `Output(...)` must correspond to the Nth item in the return tuple — they are matched positionally by Dash. Get this wrong and Dash silently puts figures in the wrong components.

### Adding the Output and return position

1. Add `Output("<plot-id>", "figure")` to the decorator in a sensible position (usually adjacent to conceptually related Outputs).
2. Add the figure variable at the matching position in the return tuple at the end of the callback.

### Building the figure

Inside the callback body:
- Construct traces using the chosen `go.*` class.
- Call `_layout(fig, title="…")` to apply shared styling (margins, fonts, hover settings, theme colors). Do **not** set colors/fonts/margins inline — `_layout` and the `_THEME` dict already own that. Inline styling creates inconsistency across plots.

### Adaptive single/multi-subject rendering (single-session plots only)

Most single-session plots render differently depending on subject count:
- 1 subject: vertical stacked bars, histograms, single-trace scatters.
- >1 subject: horizontal stacked bars, box plots, faceted or color-grouped scatters.

The branching flag is `multi_col = len(valid_subjects) > 1` (grep `multi_col` in `_update_single` to find usage sites). Follow the pattern: compute both trace shapes and switch inside `if multi_col:` / `else:`. Look at how `frac-correct` (outcome bars) handles this — it's the clearest reference.

If the user said "no adaptive rendering needed," just build a single shape. Note in a code comment that the plot is subject-count-agnostic by design.

## Step 5 — Tests

Both test files must be updated. Coverage below 90% fails CI.

### `tests/test_app.py`

Add a unit test inside `TestAppUtilities` (or a relevant class) that:
- Calls `create_app()` and looks up the callback via `app.callbacks["_update_single"]` or `["_update_multi"]`.
- Invokes the callback with mocked `get_sessions` / `session_metrics` / `multisession_metrics` returning shaped data.
- Asserts the returned figure at the new plot's index has expected properties (trace count, layout title text, axis titles, data length).

Fake-Dash stubs (`_ComponentNamespace`, `_IO`, `_Figure`, `_Dash`) accept any component and trace type, so **no stub updates are needed for a plain plot addition**. Only touch them if the plot introduces a new Dash import (see Gotcha A below).

### `tests/test_integration.py`

Add a test inside `TestCallbacksWithRealPlotly` that:
- Uses `_make_session_metrics()` / `_make_multisession_metrics()` (grep for these helpers — they build realistic dicts).
- Calls the real callback and confirms the figure is a `go.Figure` with the expected trace types — this catches plotly library breakage (see the CLAUDE.md note about plotly 6.x `titlefont` removal).

### Gotcha A: new Dash imports

If the plot needs a new import from `dash` (e.g. `State`, `Patch`, `clientside_callback`), update **both**:
- `_import_app_module` in `tests/test_app.py` — add the attribute to `fake_dash`.
- `_import_app_fake_dash_real_plotly` in `tests/test_integration.py` — add the attribute to `fake_dash_mod`.

Skipping either causes `AttributeError` at test collection time in a way that's easy to mis-diagnose.

### Gotcha B: tuple/Output ordering drift

After editing, re-count Outputs in the decorator vs. return values in the tuple. They must match exactly. A mismatch silently renders figures in the wrong components.

## Step 6 — Verify

Run, in order:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=src/chipmunk_dashboard --cov-fail-under=90
```

Then — non-negotiable for UI changes — start the app and look at the plot:

```bash
uv run chipmunk-dashboard run --debug
```

Select a subject, pick a date. Confirm:
- The plot renders in the expected row position.
- It shows sensible data for a real subject.
- If it has adaptive rendering: select a second subject and confirm the multi-subject shape renders correctly.
- No layout regressions on other plots (watch for misaligned Outputs/returns).

Tests verify code, not pixels. Skipping browser verification on a UI change is how regressions ship.

## Conventions

- Terse code. No emojis in source or comments.
- Reference helpers by name, not by line number — line numbers drift.
- Single-session plots go in `_update_single`; multi-session plots go in `_update_multi`. Do not cross-wire.
- Every figure goes through `_layout(fig, title=...)`. No inline theming.
- Match existing naming: kebab-case component ids, snake_case variable names.
