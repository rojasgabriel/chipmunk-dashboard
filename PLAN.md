# Implementation Plan: Dashboard Improvements

This document outlines the technical steps to address the user's requested improvements for the `chipmunk-dashboard`.

## 1. Multi-Session Anchoring

**Goal**: Multi-session plots should look backwards from the *selected* session, not just the latest available session.

*   **Update `data.py`**:
    *   Modify `multisession_metrics` to accept an optional `anchor_session_name`.
    *   Logic: Find the index of `anchor_session_name` in the subject's full session list. Slice the DataFrame to include that session and the `N-1` preceding sessions.
*   **Update `app.py`**:
    *   Update `_update_multi` callback to accept the `session` dropdown value as an input.
    *   Pass this value to `multisession_metrics`.

## 2. Multi-Subject Support (Single Session)

**Goal**: When multiple subjects are selected, overlay their data on *all* single-session plots.

*   **Update `app.py` (`_update_single` callback)**:
    *   **Scatter Plots (Init, Wait, React, Perf)**: Remove `if i == 0` guards. Iterate through all subjects and add traces.
        *   *Note*: Ensure unique colors/markers distinguish subjects.
    *   **Distribution Plots (Init, Wait, React)**:
        *   **Single Subject**: Keep as Histogram.
        *   **Multiple Subjects**: Switch to Box Plots (similar to current Reaction Time behavior).
    *   **Trial Outcomes (Bar Chart)**:
        *   Change `barmode` from `stack` to `group`.
        *   **Color Logic**:
            *   Correct: Shades of Green per subject.
            *   Incorrect: Shades of Red per subject.
            *   Early Withdrawal: Shades of Grey.
            *   No Choice: Shades of Black/Dark.

## 3. Rolling Medians

**Goal**: Add rolling median lines to Initiation and Reaction time scatter plots (consistent with Wait Delta).

*   **Update `data.py`**:
    *   In `session_metrics`, compute rolling medians (window=20) for:
        *   `init_times` (vs trial num)
        *   `rts` (vs trial num)
    *   Export `init_rolling_x`, `init_rolling_y` etc. in the return dict.
*   **Update `app.py`**:
    *   Plot these rolling lines on top of the raw scatter points in `_update_single`.

## 4. Reference Lines & Styling

**Goal**: Add/Standardize reference lines at `y=0.5`.

*   **Style**: `line_dash="dash"`, `line_color="grey"`, `line_width=1` (matching existing Side Bias plot).

## 5. Refinements (Current)

- [x] **Fix Trial Outcomes**: Grouped bar chart per subject, colored by outcome type. Use distinct colors for correct/incorrect/ew/no-choice.
- [ ] **Fix Wait Time Rolling Median**: Ensure the rolling median lines appear on the Wait Time Scatter plot.
- [ ] **Refine Initiation Plot**: Scale Y-axis to 80th percentile to hide outliers.
*   **Locations**:
    *   **Single Session**: `P(Right)` plot.
    *   **Multi Session**: `Performance (Easy)` plot.
    *   Ensure existing lines (e.g., Side Bias, Within-session performance) match this style.

## 5. Execution Steps

1.  **Modify `data.py`**:
    *   Updates to `session_metrics` (Rolling calculations).
    *   Updates to `multisession_metrics` (Anchoring logic).
2.  **Modify `app.py`**:
    *   Updates to `_update_single`:
        *   Loop logic for all plots.
        *   Rolling median traces.
        *   Outcome bar chart styling.
        *   Histogram vs Box switch.
    *   Updates to `_update_multi`:
        *   Input `session`.
    *   Apply consistent `add_hline` styling across all relevant plots.
