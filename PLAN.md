# Implementation Plan: Dashboard Improvements

This document outlines the technical steps to address the user's requested improvements for the `chipmunk-dashboard`.

## 1. Layout & Responsive Design

**Goal**: Create a flexible, responsive layout that utilizes screen real estate better and allows larger viewing areas for controls.

### A. Flexible Grid System
*   **Current State**: Fixed `grid-template-columns` based on the number of plots passed to `_row`.
*   **Change**: Refactor `_row` or specific section layouts to use CSS Flexbox (`display: flex; flex-wrap: wrap`) or a responsive Grid (`grid-template-columns: repeat(auto-fit, minmax(400px, 1fr))`).
    *   This ensures plots stack on smaller screens and expand on larger ones.
    *   `dcc.Graph` will keep `responsive=True` (default) to handle window resizing.

### B. Sidebar Improvements
*   **Current State**: Subject checklist restricted to `maxHeight: 180px`.
*   **Change**: 
    *   Convert Sidebar to a Flex column.
    *   Set Subject Checklist container to `flex: 1` or `min-height: 50vh` to consume available vertical space.

---

## 2. Visualization Logic: Temporal Sequence

**Goal**:  Reorder single-session plots to follow the logical trial sequence: **Initiation → Wait → Reaction**, with consistent "Line vs Histogram" comparisons.

### A. Data Updates (`src/chipmunk_dashboard/data.py`)
To support the "Line vs Histogram" view for all three metrics, we need to export per-trial time series data for everything.

*   **Initiation**:
    *   Add `init_trial_nums` (X-axis) and `init_raw` (Y-axis, preserving order) to `session_metrics`.
*   **Wait**:
    *   Use existing `wait_delta_x/y` for the Line plot.
    *   Use existing `wait_delta_times` for the Histogram.
    *   **Action**: Conform to "only wait delta plots" request by dropping the raw wait time vs min comparison if strictly implied, or keeping the Delta Line + Delta Hist.
*   **Reaction**:
    *   Add `rt_trial_nums` (X-axis) and `rts` (Y-axis, preserving order, not just valid ones for histogram) to `session_metrics`.
    *   *Note*: Chronometric curve is performance-based, not temporal. We will keep it but move it to a "Trial Outcomes" row or keep it with Reaction Times if space permits.

### B. New Plot pairings (`src/chipmunk_dashboard/app.py`)

Layout will be organized into logical rows (or 3-4 column grids):

1.  **Row 1: Performance / Outcomes**
    *   Psychometric / Chronometric curves
    *   Bar charts / Performance over time
2.  **Row 2: Initiation**
    *   Plot A: Initiation Time Line (Trial vs Time)
    *   Plot B: Initiation Time Histogram
3.  **Row 3: Wait (Delta)**
    *   Plot A: Wait Time Delta Line (Trial vs [Actual - Min])
    *   Plot B: Wait Time Delta Histogram
4.  **Row 4: Reaction**
    *   Plot A: Reaction Time Line (Trial vs RT)
    *   Plot B: Reaction Time Histogram

---

## 3. Multi-Session Axis Logic

**Goal**: Chronological order (Old → New) with "Sessions Back" negative indexing.

### A. Data Processing (`src/chipmunk_dashboard/data.py`)
*   **Current**: `df.tail(n)` (Chronological), but metrics returned as `[::-1]` (Reverse Chronological: New → Old).
*   **Change**: 
    *   Remove `[::-1]` reversal for all lists (`perf_easy`, `ew_rate`, etc.).
    *   Data will flow: Oldest Session → Newest Session.

### B. Axis Labeling (`src/chipmunk_dashboard/app.py`)
*   **Current**: `x = range(n)` (0..Positive).
*   **Change**: 
    *   Construct X-axis as `range(-n + 1, 1)`.
    *   Example for `n=5`: `[-4, -3, -2, -1, 0]`.
    *   0 represents the most recent session (right-most).

---

## 4. Execution Steps

1.  **Modify `data.py`**:
    *   Remove list reversals in `multisession_metrics`.
    *   Add trial-number arrays for Initiation and Reaction times in `session_metrics`.
2.  **Modify `app.py`**:
    *   Update `sidebar` styles.
    *   Update `_update_single` callback to generate the new Line plots.
    *   Reorganize `single_section` layout into the Init -> Wait -> React flow.
    *   Update `_update_multi` to use negative integers for X-axis.
