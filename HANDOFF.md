# Chipmunk Dashboard – Handoff Summary

## 1. Overview

**Project**: Plotly Dash dashboard ("Chipmunk Dashboard") for mouse behavioral decision-task data from a DataJoint database.

**Current Status**: **BROKEN** — neither tab renders plots. The app compiles and launches, subjects can be selected, but all plot cards show "Select subject(s)" even when subjects and sessions are selected.

**User's Last Words**: "the problem still persists after the latest edits. something broke along the way because now not even the single session tab renders data."

---

## 2. Technical Stack

| Component | Details |
|-----------|---------|
| Python | 3.10 (miniconda3 at `/Users/gabriel/miniconda3`) |
| Framework | Dash + Plotly |
| Database | DataJoint → remote MySQL on AWS RDS (`churchland-data.cmojfwfr0b9t.us-west-2.rds.amazonaws.com`). **Requires VPN/lab network.** |
| Build | hatchling via `pyproject.toml`, installed editable (`pip install -e .`) |
| CLI | `chipmunk-dashboard run` → `chipmunk_dashboard.cli:main` |
| Fonts | Google Fonts: Space Grotesk (titles), IBM Plex Sans (body) |

### Import Pattern (user-corrected)

```python
from labdata.schema import DecisionTask, Watering
from labdata import chipmunk
from chipmunk import Chipmunk
```

> **NOT** `from labdata_plugin.pluginschema import Chipmunk`

### Chipmunk.Trial Timing Columns

`t_start`, `t_initiate`, `t_stim`, `t_gocue`, `t_react`, `t_response`, `t_end`

### Timing Definitions

| Metric | Formula |
|--------|---------|
| Initiation time | `t_stim - t_start` |
| Wait time (actual) | `t_react - t_stim` |
| Wait time (minimum) | `t_gocue - t_stim` |
| Reaction time | `t_response - t_gocue` |

---

## 3. File Status

### `pyproject.toml` (22 lines) — ✅ Working

Package config. Dependencies: dash, plotly, pandas, numpy. labdata/chipmunk are system-installed.

### `src/chipmunk_dashboard/cli.py` (28 lines) — ✅ Working

CLI entry point (`chipmunk-dashboard run`).

### `src/chipmunk_dashboard/data.py` (217 lines) — ✅ Working

Data fetching from DataJoint + metric computation. Compiles clean, all functions tested live before layout broke.

**Key functions:**

- `get_all_subjects()` → sorted list of subject names from `DecisionTask.TrialSet`
- `get_subject_data(subject)` → cached DataFrame of `DecisionTask.TrialSet` rows
- `get_session_trials(subject, session_name)` → cached DataFrame of `Chipmunk * Trial * TrialParameters`
- `get_sessions(subject)` → list of session names
- `_compute_intensity(trials)` → stimulus intensity per trial (`stim_rate - category_boundary`)
- `session_metrics(subject, session_name)` → returns dict with: `stims`, `n_correct/incorrect/ew/no_choice`, `p_right`, `median_rt`, `rts`, `init_times`, `wait_times`, `wait_min_times`, `wait_delta_times`, `wait_trial_nums`, `wait_delta_x/y`, `slide_x/y`
- `multisession_metrics(subject, sessions_back)` → returns dict with: `x`, `perf_easy`, `ew_rate`, `n_with_choice`, `side_bias`, `median_init`, `median_rt`, `median_wait`, `water`

### `src/chipmunk_dashboard/app.py` (497 lines) — ❌ BROKEN

Dash layout (sidebar + tabs + plots) and callbacks. Compiles clean but **no plots render in either tab**.

**Layout structure:**
- Sidebar: subject checklist, session dropdown, sessions-back slider
- Main area: `dcc.Tabs` + two divs (`single-content`, `multi-content`) toggled via `display:none`

**Callbacks:**
- `_toggle_tabs` — show/hide tab content divs
- `_update_sessions` — populate session dropdown when subjects change
- `_update_single` — 9 graph outputs for single-session tab
- `_update_multi` — 8 graph outputs + tabs input for multi-session tab

**Key detail:** `_graph()` helper wraps `dcc.Graph` inside an `html.Div` for card styling (border, shadow, radius) — **this is the suspected cause of the rendering bug**.

---

## 4. The Rendering Bug

### Symptoms

- Both tabs compile and launch
- Subjects can be checked, sessions can be selected
- All plot cards show "Select subject(s)" — callbacks aren't populating figures
- Screenshot confirmed: subjects checked (GRB055, GRB056, GRB057), session selected (20260209_164530), but all 6 visible plot cards are empty

### Timeline

1. Dashboard worked with 6 plots in a flat layout
2. Expanded to 11 plots across 2 tabs — multi-session tab never worked
3. Added card wrappers for visual theming → **both tabs broke**
4. Added `isinstance(subjects, str)` guards → didn't fix it

### Suspected Root Cause

The `_graph()` helper was changed from:

```python
# BEFORE (working)
dcc.Graph(style={"flex": ...})
```

to:

```python
# AFTER (broken)
html.Div(
    dcc.Graph(style={"height": "100%"}),
    style={border, shadow, radius, ...}  # NO explicit height
)
```

The card wrapper `html.Div` has **no explicit height**. The `dcc.Graph` inside uses `height: 100%` which resolves to **0px** (100% of auto-height parent = 0). The `_row` wrapper sets `height: "280px"` but this doesn't propagate through the card div.

### Secondary Issue

`display: none` on the `multi-content` div may prevent Dash from firing callbacks for components inside it.

---

## 5. Fix Plan

### P0: Fix rendering bug

Add `"height": "100%"` to the card wrapper div's style dict so the height chain works:

```
_row (280px) → card div (100%) → dcc.Graph (100%)
```

**Alternatively**, temporarily revert `_graph()` to return bare `dcc.Graph` to confirm this is the cause.

### P1: Fix multi-session tab

If card fix doesn't resolve multi-tab, investigate whether `display: none` prevents Dash callbacks. Consider:
- Using `dcc.Tabs` with `children` directly (let Dash handle tab switching)
- Using `visibility: hidden; height: 0; overflow: hidden` instead of `display: none`

### P2: Align toggle_tabs padding

`_toggle_tabs` returns `padding: "4px 0"` but initial styles use `"12px 8px"` — cosmetic inconsistency.

### P3: Debug with live data

Add a debug `html.Pre(id="debug")` + callback that prints `str(subjects)` and whether metrics returned data, to diagnose without needing the agent connected.

---

## 6. Progress Checklist

- [x] `data.py` with all metrics (session + multisession)
- [x] CLI entry point
- [x] `pyproject.toml` package config
- [x] Visual theme code (fonts, colors, cards)
- [x] Tab structure (single-session + multi-session)
- [x] Wait time actual vs min visualization code
- [ ] **Fix card wrapper height bug** ← blocking
- [ ] **Fix multi-session tab rendering** ← blocked by above
- [ ] Align toggle_tabs padding
- [ ] End-to-end test with live data
