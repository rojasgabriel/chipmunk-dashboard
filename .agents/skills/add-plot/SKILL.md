---
name: add-plot
description: Add a Plotly plot to the chipmunk dashboard, including data, callback wiring, and visual checks.
---

# Add a plot to the chipmunk dashboard

Preserve the one-way dependency `cli.py → app.py → data.py` and the CI coverage floor of 90%.

## Determine the plot requirements

Inspect the closest existing plot and the relevant data and callback code. Infer the component ID, Plotly type, row placement, and existing data keys from those patterns. Preserve the user's stated metric and comparison.

Ask a focused question only when a missing choice would change scientific meaning or the useful display: for example, the metric definition, session scope, aggregation, or comparison. Continue with routine implementation choices when the request and current code establish the intended outcome.

## Step 2 — (Optional) Extend the data layer

Only if the requested metric is not already available. Path: `src/chipmunk_dashboard/data.py`.

**Preferred path — extend an existing function.** Compute the new metric inside `session_metrics` (trial-level) or `multisession_metrics` (session-aggregate) and add it as a new key in the dict these functions return. No new top-level query function is needed. Update `tests/test_data.py` with a test that covers the new key — follow the mock pattern used by other tests in the file.

**Only if the query shape is genuinely new:** add a new top-level function. Requirements:
- Decorate with `@_ttl_lru_cache(maxsize=...)` (see existing decorators in the file for sizing).
- Read the DB under `with _DB_LOCK:`.
- Register `<new_func>.cache_clear()` inside `clear_data_cache()` — grep the file for `cache_clear()` to find the block and add it there. Forgetting this leaks stale data across date rollovers.
- Add a mock-based unit test in `tests/test_data.py`. `test_get_subjects_for_date_filters_at_query` is a recent reference.

Keep database access in `data.py`; `app.py` must not query the database directly.

## Step 3 — Wire the layout

Path: `src/chipmunk_dashboard/app.py`. Grep for `single_section =` and `multi_section =` to find the two sections (line numbers drift — always grep, don't hard-code).

- **Append to an existing row:** add the new plot ID to `OVERVIEW_ROWS`, `TIMING_ROWS`, or `MULTI_ROWS`.
- **New row:** add a new id tuple in those constants. Layout is `[_row(*ids) for ids in ...]`.

## Step 4 — Wire the callback

Same file: `src/chipmunk_dashboard/app.py`. Two big callbacks:
- `_update_single` — driven by subject + session selection.
- `_update_multi` — driven by subject + sessions-back + smoothing controls.

Add the plot id to `SINGLE_FIGURE_IDS` or `MULTI_FIGURE_IDS` in the same position as the new figure in the return tuple. Those tuples build the `Output(...)` list.

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

Coverage below 90% fails CI. Update `tests/test_integration.py`.

Add a test inside `TestCallbacksWithRealPlotly` that:
- Uses `make_session_metrics()` / `make_multisession_metrics()`.
- Calls `_update_single` or `_update_multi` and confirms the figure is a `go.Figure` with the expected trace types.

Also add the plot id to `SINGLE_FIGURE_IDS` / `MULTI_FIGURE_IDS` and the matching row tuple in `app.py`. Streamlit imports those constants.

### Gotcha A: new Dash imports

If the plot needs a new import from `dash`, add it to `_import_app_fake_dash_real_plotly` in `tests/test_integration.py`.

### Gotcha B: tuple/Output ordering drift

`SINGLE_FIGURE_IDS` / `MULTI_FIGURE_IDS` drive the callback `Output` list. Keep the return tuple in that same order.

## Step 6 — Verify

Run affected tests during development, then complete these required code checks once the plot is ready:

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
- It shows sensible data for the selected fixture or real subject. Use the debug fixtures when live access is unavailable, and report that limit.
- If it has adaptive rendering: select a second subject and confirm the multi-subject shape renders correctly.
- No layout regressions on other plots (watch for misaligned Outputs/returns).

Tests verify code, not pixels. Skipping browser verification on a UI change is how regressions ship.

## Conventions

- Terse code. No emojis in source or comments.
- Reference helpers by name, not by line number — line numbers drift.
- Single-session plots go in `_update_single`; multi-session plots go in `_update_multi`. Do not cross-wire.
- Every figure goes through `_layout(fig, title=...)`. No inline theming.
- Match existing naming: kebab-case component ids, snake_case variable names.
