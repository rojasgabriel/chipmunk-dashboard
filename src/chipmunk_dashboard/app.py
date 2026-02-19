"""Dash application — layout and callbacks."""

import numpy as np
from typing import Any
from dash import Dash, dcc, html, Input, Output
import plotly.graph_objects as go
import plotly.express as px
from .data import (
    get_all_subjects,
    get_sessions,
    session_metrics,
    multisession_metrics,
)

COLORS = px.colors.qualitative.Plotly
_MARGIN: dict[str, int] = dict(l=50, r=20, t=42, b=80)
_CLEAN: dict[str, Any] = dict(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)"
)
_AXIS_CLEAN = dict(showgrid=False, zeroline=False, tickfont=dict(color="#56606b"))
_LEGEND: dict[str, Any] = dict(visible=False)
_PLOT_H = "280px"
_MAX_W = "560px"  # max width per plot
_THEME = dict(
    bg="#f6f7fb",
    panel="#eef1f6",
    card="#ffffff",
    border="#e3e7ef",
    text="#1f2630",
    muted="#56606b",
    accent="#1f77b4",
)


def _empty_fig(msg: str = "Select subject(s)") -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        annotations=[dict(text=msg, showarrow=False, font=dict(size=14))],
        margin=_MARGIN,
        **_CLEAN,
    )
    return fig


def _layout(fig: go.Figure, **kw) -> None:
    # Default layout settings
    config = dict(
        margin=_MARGIN,
        legend=_LEGEND,
        hoverlabel=dict(
            bgcolor="rgba(255, 255, 255, 0.9)",
            font_size=12,
            font_family="IBM Plex Sans, sans-serif",
        ),
        hovermode="x unified",
        font=dict(family="IBM Plex Sans, sans-serif", color=_THEME["text"], size=12),
        xaxis=_AXIS_CLEAN,
        yaxis=_AXIS_CLEAN,
        **_CLEAN,
    )

    # Handle title if provided (wrap in dict)
    if "title" in kw:
        kw["title"] = dict(
            text=kw["title"],
            font=dict(
                family="Space Grotesk, sans-serif", size=14, color=_THEME["text"]
            ),
        )

    # Update defaults with provided kwargs
    config.update(kw)
    fig.update_layout(**config)


def create_app() -> Dash:
    subjects = get_all_subjects()
    app = Dash(
        __name__,
        title="chipmunk dashboard",
        suppress_callback_exceptions=True,
        external_stylesheets=[
            "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap"
        ],
    )

    # Auto-refresh interval (60 minutes)
    auto_refresh = dcc.Interval(id="auto-refresh", interval=60 * 60 * 1000)

    # -- helpers --------------------------------------------------------------
    def _graph(gid: str) -> dcc.Graph:
        return dcc.Graph(
            id=gid,
            style={"height": _PLOT_H, "width": "100%"},
            config={"displayModeBar": False},
        )

    def _row(*ids: str) -> html.Div:
        return html.Div(
            [_graph(i) for i in ids],
            style={
                "display": "grid",
                "gridTemplateColumns": f"repeat({len(ids)}, 1fr)",
                "gap": "12px",
                "marginBottom": "12px",
            },
        )

    # -- sidebar --------------------------------------------------------------
    sidebar = html.Div(
        [
            html.Label("Subjects", style={"fontWeight": "bold"}),
            html.Div(
                dcc.Checklist(
                    id="subjects",
                    options=subjects,
                    value=[],
                    style={"display": "flex", "flexDirection": "column", "gap": "2px"},
                    inputStyle={"marginRight": "6px", "transform": "scale(1.2)"},
                    labelStyle={"fontSize": "16px", "cursor": "pointer"},
                ),
                style={
                    "height": "40vh",
                    "overflowY": "auto",
                    "border": "1px solid #ccc",
                    "borderRadius": "4px",
                    "padding": "6px",
                    "marginTop": "4px",
                },
            ),
            html.Button(
                "Clear Selection",
                id="clear-subjects",
                n_clicks=0,
                style={"marginTop": "8px", "width": "100%", "cursor": "pointer"},
            ),
            html.Br(),
            html.Label("Session Date", style={"fontWeight": "bold"}),
            dcc.DatePickerSingle(
                id="session-date",
                display_format="YYYY-MM-DD",
                style={"width": "100%", "marginBottom": "8px"},
            ),
            dcc.Dropdown(
                id="session-time",
                placeholder="Time (if multiple)",
                style={"marginBottom": "8px"},
            ),
            html.Br(),
            html.Label("Smooth (Multi)", style={"fontWeight": "bold"}),
            dcc.Checklist(
                id="smooth-metrics",
                options=[{"label": "Enable Smoothing", "value": "smooth"}],
                value=[],
                style={"fontSize": "14px"},
            ),
            dcc.Slider(
                id="smooth-window",
                min=1,
                max=10,
                step=1,
                value=3,
                marks={1: "1", 3: "3", 5: "5", 10: "10"},
            ),
            html.Br(),
            html.Label("Sessions back", style={"fontWeight": "bold"}),
            dcc.Slider(
                id="sessions-back",
                min=1,
                max=30,
                step=1,
                value=10,
                marks={i: str(i) for i in [1, 5, 10, 15, 20, 25, 30]},
            ),
        ],
        style={
            "width": "240px",
            "padding": "16px",
            "borderRight": f"1px solid {_THEME['border']}",
            "background": _THEME["panel"],
            "flexShrink": 0,
            "display": "flex",
            "flexDirection": "column",
        },
    )

    # -- content sections -----------------------------------------------------
    single_section = html.Div(
        [
            html.H3(
                "Single Session",
                style={"margin": "24px 0 12px", "borderBottom": "1px solid #ddd"},
            ),
            # Row 1: Performance / Outcomes
            _row("frac-correct", "p-right", "chrono", "session-perf"),
            # Row 2: Initiation
            _row("init-line", "init-hist"),
            # Row 3: Wait (Delta)
            _row("wait-delta-line", "wait-delta-hist"),
            # Row 4: Reaction
            _row("react-line", "react-hist"),
        ]
    )

    multi_section = html.Div(
        [
            html.H3(
                "Multi Session",
                style={"margin": "24px 0 12px", "borderBottom": "1px solid #ddd"},
            ),
            _row("performance", "ew-rate", "side-bias", "trial-counts"),
            _row("init-times", "median-wait", "median-rt", "water"),
        ]
    )

    main_area = html.Div(
        [single_section, multi_section],
        style={
            "flex": 1,
            "display": "flex",
            "flexDirection": "column",
            "overflowY": "auto",
            "padding": "0 20px 40px",
            "background": _THEME["bg"],
        },
    )

    app.layout = html.Div(
        [
            auto_refresh,
            html.H2(
                "Chipmunk Dashboard",
                style={
                    "margin": "0 0 8px",
                    "fontFamily": "Space Grotesk, sans-serif",
                    "letterSpacing": "0.2px",
                },
            ),
            html.Div(
                [sidebar, main_area],
                style={
                    "display": "flex",
                    "height": "calc(100vh - 56px)",
                    "overflow": "hidden",
                },
            ),
        ],
        style={
            "fontFamily": "IBM Plex Sans, sans-serif",
            "padding": "12px",
            "background": _THEME["bg"],
            "color": _THEME["text"],
            "height": "100vh",
            "overflow": "hidden",
        },
    )

    # -- callbacks ------------------------------------------------------------
    # Session Date & Time Logic
    @app.callback(
        Output("session-date", "date"),
        Output("session-date", "min_date_allowed"),
        Output("session-date", "max_date_allowed"),
        Output("session-date", "initial_visible_month"),
        Input("subjects", "value"),
        Input("auto-refresh", "n_intervals"),
    )
    def _update_date_options(subjects, n_intervals):
        if not subjects:
            return None, None, None, None

        sessions = get_sessions(subjects[0])
        if not sessions:
            return None, None, None, None

        # Parse dates from session names (YYYYMMDD_HHMMSS)
        dates = []
        for s in sessions:
            if len(s) >= 8:
                d_str = f"{s[:4]}-{s[4:6]}-{s[6:8]}"
                dates.append(d_str)

        if not dates:
            return None, None, None, None

        min_d = min(dates)
        max_d = max(dates)
        return max_d, min_d, max_d, max_d  # Default to latest

    @app.callback(
        Output("session-time", "options"),
        Output("session-time", "value"),
        Input("session-date", "date"),
        Input("subjects", "value"),
    )
    def _update_time_options(date_val, subjects):
        if not date_val or not subjects:
            return [], None

        sessions = get_sessions(subjects[0])
        raw_date = date_val.replace("-", "")  # YYYY-MM-DD -> YYYYMMDD

        # Filter sessions for this date
        day_sessions = [s for s in sessions if s.startswith(raw_date)]

        if not day_sessions:
            return [], None

        # Create time options (HH:MM:SS) from YYYYMMDD_HHMMSS
        opts = []
        for s in day_sessions:
            if "_" in s:
                t_str = s.split("_")[1]
                if len(t_str) == 6:
                    fmt = f"{t_str[:2]}:{t_str[2:4]}:{t_str[4:]}"
                    opts.append({"label": fmt, "value": s})
                else:
                    opts.append({"label": s, "value": s})
            else:
                opts.append({"label": s, "value": s})

        # Select the latest session of the day by default
        return opts, opts[-1]["value"] if opts else None

    @app.callback(
        Output("subjects", "value"),
        Input("clear-subjects", "n_clicks"),
        prevent_initial_call=True,
    )
    def _clear_subjects(n_clicks):
        return []

    # ── Single-session plots ─────────────────────────────────────────────────
    @app.callback(
        Output("frac-correct", "figure"),
        Output("p-right", "figure"),
        Output("chrono", "figure"),
        Output("session-perf", "figure"),
        Output("init-line", "figure"),
        Output("init-hist", "figure"),
        Output("wait-delta-line", "figure"),
        Output("wait-delta-hist", "figure"),
        Output("react-line", "figure"),
        Output("react-hist", "figure"),
        Input("subjects", "value"),
        Input("session-time", "value"),
        Input("auto-refresh", "n_intervals"),
    )
    def _update_single(subjects, session_name, n_intervals):
        n = 10
        if isinstance(subjects, str):
            subjects = [subjects]

        sessions_by_subject = {s: get_sessions(s) for s in subjects}
        valid_subjects = [s for s in subjects if sessions_by_subject.get(s)]

        if not valid_subjects:
            e = _empty_fig()
            return tuple(e for _ in range(n))

        multi = len(subjects) > 1
        multi_col = len(valid_subjects) > 1

        # Initialize figures
        fig_fc = go.Figure()

        fig_pr, fig_ch, fig_sp = go.Figure(), go.Figure(), go.Figure()
        fig_il, fig_ih = go.Figure(), go.Figure()
        fig_wdl, fig_wdh = go.Figure(), go.Figure()
        fig_rl, fig_rh = go.Figure(), go.Figure()

        # Collect outcome totals for multi-subject horizontal bars
        multi_outcome_data = []

        for i, subj in enumerate(valid_subjects):
            c = COLORS[i % len(COLORS)]
            grp = subj
            sessions_list = sessions_by_subject[subj]
            ses = (
                session_name
                if i == 0 and session_name
                else (sessions_list[-1] if sessions_list else None)
            )
            if not ses:
                continue
            sm = session_metrics(subj, ses)
            if not sm:
                continue

            ht_subj = "<extra>" + subj + "</extra>"

            # --- Row 1: Outcomes & Performance ---

            if multi_col:
                # Collect totals for horizontal stacked bars
                multi_outcome_data.append(
                    dict(
                        subject=subj,
                        correct=sum(sm["n_correct"]),
                        incorrect=sum(sm["n_incorrect"]),
                        ew=sum(sm["n_ew"]),
                        no_choice=sum(sm["n_no_choice"]),
                    )
                )
            else:
                # Single subject: per-stimulus vertical stacked bars
                outcome_types = [
                    ("correct", sm["n_correct"], "mediumseagreen"),
                    ("incorrect", sm["n_incorrect"], "tomato"),
                    ("ew", sm["n_ew"], "silver"),
                    ("no choice", sm["n_no_choice"], "#333333"),
                ]
                for outcome_name, yvals, base_color in outcome_types:
                    fig_fc.add_trace(
                        go.Bar(
                            x=sm["stims"],
                            y=yvals,
                            name=outcome_name,
                            legendgroup=outcome_name,
                            showlegend=True,
                            marker_color=base_color,
                            hovertemplate="%{y} " + outcome_name + ht_subj,
                        )
                    )

            # P(Right)
            fig_pr.add_trace(
                go.Scatter(
                    x=sm["stims"],
                    y=sm["p_right"],
                    mode="lines+markers",
                    name=subj,
                    showlegend=multi,
                    legendgroup=grp,
                    marker=dict(color=c, size=7),
                    hovertemplate="%{y:.2f}" + ht_subj,
                )
            )

            # Chronometric
            fig_ch.add_trace(
                go.Scatter(
                    x=sm["stims"],
                    y=sm["median_rt"],
                    mode="lines+markers",
                    name=subj,
                    showlegend=False,
                    legendgroup=grp,
                    marker=dict(color=c, size=7),
                    line=dict(color=c, width=2),
                    hovertemplate="%{y:.3f}s" + ht_subj,
                )
            )

            # Within-session performance
            if sm["slide_x"]:
                fig_sp.add_trace(
                    go.Scatter(
                        x=sm["slide_x"],
                        y=sm["slide_y"],
                        mode="lines",
                        name=subj,
                        showlegend=False,
                        legendgroup=grp,
                        line=dict(color=c, width=2),
                        hovertemplate="%{y:.2f}" + ht_subj,
                    )
                )

            # Within-session EW Rate (Secondary Axis)
            if "ew_roll_x" in sm and sm["ew_roll_x"]:
                fig_sp.add_trace(
                    go.Scatter(
                        x=sm["ew_roll_x"],
                        y=sm["ew_roll_y"],
                        mode="lines",
                        line=dict(color=c, width=1.5, dash="dot"),
                        name=(subj + " ew") if multi else "ew rate",
                        showlegend=multi,
                        yaxis="y2",
                        hovertemplate="ew: %{y:.2f}" + ht_subj,
                        opacity=0.7,
                    )
                )

            # --- Row 2: Initiation ---

            if sm["init_trial_nums"] and sm["init_times"]:
                # Line
                fig_il.add_trace(
                    go.Scattergl(
                        x=sm["init_trial_nums"],
                        y=sm["init_times"],
                        mode="markers",
                        name=subj,
                        showlegend=False,
                        legendgroup=grp,
                        marker=dict(color=c, size=3, opacity=0.4),
                        hovertemplate="%{y:.3f}s" + ht_subj,
                    )
                )
                # Rolling
                if sm["init_roll_x"]:
                    fig_il.add_trace(
                        go.Scatter(
                            x=sm["init_roll_x"],
                            y=sm["init_roll_y"],
                            mode="lines",
                            name=subj + " roll",
                            showlegend=False,
                            legendgroup=grp,
                            line=dict(color=c, width=2),
                            hovertemplate="%{y:.3f}s (roll)" + ht_subj,
                        )
                    )

                # Hist (Box if multi, Hist if single)
                if multi:
                    fig_ih.add_trace(
                        go.Box(
                            y=sm["init_times"],
                            name=subj,
                            marker_color=c,
                            legendgroup=grp,
                            showlegend=False,
                            boxmean=True,
                        )
                    )
                else:
                    fig_ih.add_trace(
                        go.Histogram(
                            x=sm["init_times"],
                            nbinsx=30,
                            name=subj,
                            marker_color=c,
                            showlegend=False,
                            opacity=0.8,
                        )
                    )
                    # Add Median Line
                    if sm["init_times"]:
                        med_val = np.median(sm["init_times"])
                        fig_ih.add_vline(
                            x=med_val,
                            line_dash="dash",
                            line_color="black",
                            line_width=1.5,
                        )

            # --- Row 3: Wait Delta ---

            if sm["wait_delta_times"]:
                # Line (Delta vs trial num)
                fig_wdl.add_trace(
                    go.Scattergl(
                        x=sm["wait_trial_nums"],
                        y=sm["wait_delta_times"],
                        mode="markers",
                        name=subj,
                        showlegend=False,
                        legendgroup=grp,
                        marker=dict(color=c, size=3, opacity=0.4),
                        hovertemplate="%{y:.3f}s<extra>raw</extra>",
                    )
                )
                # Rolling median line - ensure rolling data exists
                if sm["wait_delta_x"] and sm["wait_delta_y"]:
                    fig_wdl.add_trace(
                        go.Scatter(
                            x=sm["wait_delta_x"],
                            y=sm["wait_delta_y"],
                            mode="lines",
                            name=subj + " roll",
                            showlegend=False,
                            legendgroup=grp,
                            line=dict(color=c, width=2),
                            hovertemplate="%{y:.3f}s<extra>rolling</extra>",
                        )
                    )

                # Hist (Box if multi)
                if multi:
                    fig_wdh.add_trace(
                        go.Box(
                            y=sm["wait_delta_times"],
                            name=subj,
                            marker_color=c,
                            legendgroup=grp,
                            showlegend=False,
                            boxmean=True,
                        )
                    )
                else:
                    fig_wdh.add_trace(
                        go.Histogram(
                            x=sm["wait_delta_times"],
                            nbinsx=30,
                            name=subj,
                            marker_color=c,
                            showlegend=False,
                            opacity=0.8,
                        )
                    )
                    # Add Median Line
                    if sm["wait_delta_times"]:
                        med_val = np.median(sm["wait_delta_times"])
                        fig_wdh.add_vline(
                            x=med_val,
                            line_dash="dash",
                            line_color="black",
                            line_width=1.5,
                        )

            # --- Row 4: Reaction Time ---

            # Line (RT vs trial)
            if sm["rt_trial_nums"]:
                fig_rl.add_trace(
                    go.Scattergl(
                        x=sm["rt_trial_nums"],
                        y=sm["rt_vals"],
                        mode="markers",
                        name=subj,
                        showlegend=False,
                        legendgroup=grp,
                        marker=dict(color=c, size=3, opacity=0.4),
                        hovertemplate="%{y:.3f}s" + ht_subj,
                    )
                )
                # Rolling
                if sm["rt_roll_x"]:
                    fig_rl.add_trace(
                        go.Scatter(
                            x=sm["rt_roll_x"],
                            y=sm["rt_roll_y"],
                            mode="lines",
                            name=subj + " roll",
                            showlegend=False,
                            legendgroup=grp,
                            line=dict(color=c, width=2),
                            hovertemplate="%{y:.3f}s (roll)" + ht_subj,
                        )
                    )

            # Histogram / Box
            if multi:
                fig_rh.add_trace(
                    go.Box(
                        y=sm["rts"],
                        name=subj,
                        marker_color=c,
                        legendgroup=grp,
                        showlegend=False,
                        boxmean=True,
                    )
                )
            else:
                fig_rh.add_trace(
                    go.Histogram(
                        x=sm["rts"],
                        nbinsx=30,
                        name=subj,
                        marker_color=c,
                        legendgroup=grp,
                        showlegend=False,
                        opacity=0.8,
                    )
                )
                # Add Median Line
                if sm["rts"]:
                    med_val = np.median(sm["rts"])
                    fig_rh.add_vline(
                        x=med_val, line_dash="dash", line_color="black", line_width=1.5
                    )

        # --- Layouts ---

        # Build horizontal stacked bars for multi-subject outcome view
        if multi_col and multi_outcome_data:
            subjects_list = [d["subject"] for d in multi_outcome_data]
            for outcome_name, key, base_color in [
                ("correct", "correct", "mediumseagreen"),
                ("incorrect", "incorrect", "tomato"),
                ("ew", "ew", "silver"),
                ("no choice", "no_choice", "#333333"),
            ]:
                vals = [d[key] for d in multi_outcome_data]
                fig_fc.add_trace(
                    go.Bar(
                        y=subjects_list,
                        x=vals,
                        name=outcome_name,
                        orientation="h",
                        marker_color=base_color,
                        hovertemplate="%{x} " + outcome_name + "<extra>%{y}</extra>",
                    )
                )

        # Consistent Reference Lines
        _ref_line = dict(line_dash="dash", line_color="grey", line_width=1)

        # Row 1
        _fc_legend = dict(
            visible=True,
            orientation="h",
            y=-0.35,
            x=0.5,
            xanchor="center",
            font=dict(size=10),
        )
        if multi_col:
            _layout(
                fig_fc,
                title="Trial Outcomes",
                xaxis_title="count",
                yaxis_title="",
                barmode="stack",
                legend=_fc_legend,
            )
        else:
            _layout(
                fig_fc,
                title="Trial Outcomes",
                xaxis_title="stim intensity",
                yaxis_title="count",
                barmode="stack",
                legend=_fc_legend,
            )

        _layout(
            fig_pr,
            title="Psychometric Curve",
            xaxis_title="stim intensity",
            yaxis_title="p(right)",
            yaxis_range=[0, 1],
        )
        fig_pr.add_hline(y=0.5, **_ref_line)  # Ref Line

        _layout(
            fig_ch,
            title="Chronometric Curve",
            xaxis_title="stim intensity",
            yaxis_title="median response time (s)",
        )

        _layout(
            fig_sp,
            title="Performance (easy)<br><sup>20 trial rolling mean</sup>",
            xaxis_title="trial number",
            yaxis_title="correct rate",
            yaxis_range=[0, 1],
            yaxis2=dict(
                title="ew rate",
                overlaying="y",
                side="right",
                range=[0, 1],
                showgrid=False,
                zeroline=False,
                tickfont=dict(color="silver"),
                titlefont=dict(color="silver"),
            ),
        )
        fig_sp.add_hline(y=0.5, **_ref_line)  # Ref Line (Updated style)

        # Row 2

        # Auto-scale Initiation Y-axis based on 98th percentiles (REVERTED LOGIC)
        # Recalculate basic 98th percentile logic here if we want *some* filtering,
        # otherwise, just leave it mostly open but maybe max(10s) floor?
        # User asked for "normal box plots", "showing outlier points".
        # If we show outliers, Plotly will scale to them.
        # But if outliers are HUGE (200s), the box is tiny.
        # User said "let's back to... showing outlier points".
        # So we remove manual scaling logic that hides them.

        _layout(
            fig_il,
            title="Initiation Times",
            xaxis_title="trial number",
            yaxis_title="time (s)",
        )

        if multi:
            _layout(fig_ih, title="Initiation Dist.", yaxis_title="time (s)")
        else:
            _layout(
                fig_ih,
                title="Initiation Dist.",
                xaxis_title="time (s)",
                yaxis_title="count",
            )

        # Row 3
        _layout(
            fig_wdl,
            title="Wait Delta (Actual - Min)",
            xaxis_title="trial number",
            yaxis_title="time (s)",
        )
        if multi:
            _layout(fig_wdh, title="Wait Delta Dist.", yaxis_title="time (s)")
        else:
            _layout(
                fig_wdh,
                title="Wait Delta Dist.",
                xaxis_title="time (s)",
                yaxis_title="count",
            )

        # Row 4
        _layout(
            fig_rl,
            title="Response Times",
            xaxis_title="trial number",
            yaxis_title="time (s)",
        )
        if multi:
            _layout(fig_rh, title="Response Time Dist.", yaxis_title="time (s)")
        else:
            _layout(
                fig_rh,
                title="Response Time Dist.",
                xaxis_title="time (s)",
                yaxis_title="count",
            )

        return (
            fig_fc,
            fig_pr,
            fig_ch,
            fig_sp,
            fig_il,
            fig_ih,
            fig_wdl,
            fig_wdh,
            fig_rl,
            fig_rh,
        )

    # ── Multi-session plots ──────────────────────────────────────────────────
    @app.callback(
        Output("performance", "figure"),
        Output("ew-rate", "figure"),
        Output("side-bias", "figure"),
        Output("init-times", "figure"),
        Output("median-rt", "figure"),
        Output("median-wait", "figure"),
        Output("trial-counts", "figure"),
        Output("water", "figure"),
        Input("subjects", "value"),
        Input("sessions-back", "value"),
        Input("session-date", "date"),  # Replaces session-time for alignment anchor
        Input("smooth-metrics", "value"),
        Input("smooth-window", "value"),
        Input("auto-refresh", "n_intervals"),
    )
    def _update_multi(
        subjects, sessions_back, session_date, smooth_vals, smooth_window, n_intervals
    ):
        n = 8
        if isinstance(subjects, str):
            subjects = [subjects]
        if not subjects:
            e = _empty_fig()
            return tuple(e for _ in range(n))

        do_smooth = "smooth" in (smooth_vals or [])
        win = smooth_window or 3

        fig_perf, fig_ew, fig_sb = go.Figure(), go.Figure(), go.Figure()
        fig_it, fig_mrt, fig_mwt = go.Figure(), go.Figure(), go.Figure()
        fig_tc, fig_wa = go.Figure(), go.Figure()

        for i, subj in enumerate(subjects):
            c = COLORS[i % len(COLORS)]
            grp = subj

            # Anchor Handling:
            # - We use 'session_date' (YYYY-MM-DD string) as the anchor for EVERY subject.
            # - This aligns "0" to that date for all subjects.
            # - If date is None (startup), session_date usually defaults to latest, but we handle None.

            ms = multisession_metrics(
                subj,
                sessions_back,
                start_date=session_date,  # Passing date string directly
                smooth=do_smooth,
                smooth_window=win,
            )
            if not ms:
                continue
            ht = "%{y:.2f}<extra>" + subj + "</extra>"
            mk = dict(color=c, size=7)
            ln = dict(color=c, width=2)

            fig_perf.add_trace(
                go.Scatter(
                    x=ms["x"],
                    y=ms["perf_easy"],
                    mode="lines+markers",
                    name=subj,
                    legendgroup=grp,
                    showlegend=True,
                    line=ln,
                    marker=mk,
                    hovertemplate=ht,
                )
            )
            fig_ew.add_trace(
                go.Scatter(
                    x=ms["x"],
                    y=ms["ew_rate"],
                    mode="lines+markers",
                    name=subj,
                    legendgroup=grp,
                    showlegend=False,
                    marker=mk,
                    line=dict(color=c),
                    hovertemplate=ht,
                )
            )
            fig_sb.add_trace(
                go.Scatter(
                    x=ms["x"],
                    y=ms["side_bias"],
                    mode="lines+markers",
                    name=subj,
                    legendgroup=grp,
                    showlegend=False,
                    marker=mk,
                    line=dict(color=c),
                    hovertemplate=ht,
                )
            )
            fig_it.add_trace(
                go.Scatter(
                    x=ms["x"],
                    y=ms["median_init"],
                    mode="lines+markers",
                    name=subj,
                    legendgroup=grp,
                    showlegend=False,
                    marker=mk,
                    line=dict(color=c),
                    hovertemplate="%{y:.3f}s<extra>" + subj + "</extra>",
                )
            )
            fig_mrt.add_trace(
                go.Scatter(
                    x=ms["x"],
                    y=ms["median_rt"],
                    mode="lines+markers",
                    name=subj,
                    legendgroup=grp,
                    showlegend=False,
                    marker=mk,
                    line=dict(color=c),
                    hovertemplate="%{y:.3f}s<extra>" + subj + "</extra>",
                )
            )
            fig_mwt.add_trace(
                go.Scatter(
                    x=ms["x"],
                    y=ms["median_wait"],
                    mode="lines+markers",
                    name=subj,
                    legendgroup=grp,
                    showlegend=False,
                    marker=mk,
                    line=dict(color=c),
                    hovertemplate="%{y:.3f}s<extra>" + subj + "</extra>",
                )
            )
            fig_tc.add_trace(
                go.Scatter(
                    x=ms["x"],
                    y=ms["n_with_choice"],
                    mode="lines+markers",
                    name=subj,
                    legendgroup=grp,
                    showlegend=False,
                    line=dict(color=c),
                    marker=mk,
                    hovertemplate="%{y}<extra>" + subj + "</extra>",
                )
            )
            fig_wa.add_trace(
                go.Scatter(
                    x=ms["x"],
                    y=ms["water"],
                    mode="lines+markers",
                    name=subj,
                    legendgroup=grp,
                    showlegend=False,
                    marker=mk,
                    line=dict(color=c),
                    hovertemplate="%{y:.2f} mL<extra>" + subj + "</extra>",
                )
            )

        _ref_line = dict(line_dash="dash", line_color="grey", line_width=1)

        _ms = dict(dtick=5, showgrid=False, zeroline=False)
        _layout(
            fig_perf,
            title="Performance (easy)",
            xaxis_title="sessions back",
            yaxis_title="performance",
            yaxis_range=[0.3, 1],
            xaxis=_ms,
        )
        fig_perf.add_hline(y=0.5, **_ref_line)

        _layout(
            fig_ew,
            title="E.W. Rate",
            xaxis_title="sessions back",
            yaxis_title="e.w. rate",
            yaxis_range=[0, 1],
            xaxis=_ms,
        )
        fig_ew.add_hline(
            y=0.5, line_dash="dash", line_color="black"
        )  # Keep black for EW? Spec said "make these new lines ... also make existing lines follow this style". Let's standardize ALL to grey dash.
        # Overriding EW line to match new style
        fig_ew.update_yaxes(range=[0, 1])  # Reset if needed, but fig var is ok.
        # Actually, let's just add the grey line and remove the black one if it was added before.
        # Since I'm rebuilding the figure, I just add the new one.
        fig_ew.layout.shapes = []  # Clear existing
        fig_ew.add_hline(y=0.5, **_ref_line)

        _layout(
            fig_sb,
            title="Bias Index",
            xaxis_title="sessions back",
            yaxis_title="bias (R - L)",
            yaxis_range=[-0.6, 0.6],
            xaxis=_ms,
        )
        fig_sb.add_hline(y=0.0, **_ref_line)

        _layout(
            fig_it,
            title="Median Initiation Time",
            xaxis_title="sessions back",
            yaxis_title="time (s)",
            xaxis=_ms,
        )
        _layout(
            fig_mrt,
            title="Median Response Time",
            xaxis_title="sessions back",
            yaxis_title="time (s)",
            xaxis=_ms,
        )
        _layout(
            fig_mwt,
            title="Median Wait Time",
            xaxis_title="sessions back",
            yaxis_title="time (s)",
            xaxis=_ms,
        )
        _layout(
            fig_tc,
            title="Trials with Choice",
            xaxis_title="sessions back",
            yaxis_title="trials",
            xaxis=_ms,
        )
        _layout(
            fig_wa,
            title="Water Earned",
            xaxis_title="sessions back",
            yaxis_title="volume (mL)",
            xaxis=_ms,
        )

        return fig_perf, fig_ew, fig_sb, fig_it, fig_mrt, fig_mwt, fig_tc, fig_wa

    return app
