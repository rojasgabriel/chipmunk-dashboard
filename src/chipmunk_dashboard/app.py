"""Dash application — layout and callbacks."""

from typing import Any, cast
import os
import time
import logging
import math
from datetime import date as _date

from dash import Dash, ctx, dcc, html, Input, Output, State
import plotly.graph_objects as go
import plotly.express as px
from .data import (
    get_all_subjects,
    get_subjects_with_recent_sessions,
    get_sessions,
    get_subjects_for_date,
    session_metrics,
    multisession_metrics,
    prewarm_multisession_cache,
)

COLORS = px.colors.qualitative.Plotly
_MARGIN: dict[str, int] = dict(l=50, r=20, t=42, b=80)
_CLEAN: dict[str, Any] = dict(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)"
)
_AXIS_CLEAN = dict(showgrid=False, zeroline=False, tickfont=dict(color="#56606b"))
_LEGEND: dict[str, Any] = dict(visible=False)
_PLOT_H_DEFAULT = "280px"
_PLOT_H_BY_ID: dict[str, str] = {
    # line/scatter-heavy panels benefit from extra vertical space
    "session-perf": "300px",
    "init-line": "300px",
    "wait-delta-line": "300px",
    "wait-floor-line": "300px",
    "response-time-line": "300px",
    "iti-rolling": "320px",
    "water-cumulative": "300px",
    # distribution / count panels
    "init-hist": "300px",
    "wait-delta-hist": "300px",
    "wait-floor-hist": "300px",
    "response-time": "300px",
    "iti-dist": "300px",
    "trial-count-time": "300px",
    "training-time": "300px",
}
_MAX_W = "560px"  # max width per plot
_TIMING_Y_CLIP_PCT = 95.0
_PROFILE_PERF = os.getenv("CHIPMUNK_PROFILE", "0") == "1"
_LOGGER = logging.getLogger(__name__)
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
    """Build a placeholder figure shown when no data selection is available.

    Args:
        msg: Annotation text displayed in the middle of the empty figure.

    Returns:
        A Plotly figure with hidden axes and a centered message annotation.
    """
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
    """Apply shared dashboard layout defaults and optional per-figure overrides.

    Args:
        fig: Figure to style.
        **kw: Plotly layout keyword overrides merged onto default settings.

    Returns:
        None. The input figure is updated in place.
    """
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


def _percentile(values: list[float], pct: float) -> float:
    """Compute a percentile with linear interpolation."""
    if not values:
        return float("nan")
    if len(values) == 1:
        return float(values[0])
    p = min(100.0, max(0.0, float(pct)))
    sorted_vals = sorted(float(v) for v in values)
    pos = (len(sorted_vals) - 1) * (p / 100.0)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def _robust_y_range(
    values: list[float],
    pct: float = _TIMING_Y_CLIP_PCT,
    lower_bound: float | None = None,
    min_span: float = 0.05,
) -> list[float] | None:
    """Return a median-centered default y-range clipped by percentile radius."""
    finite = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if len(finite) < 2:
        return None
    med = _percentile(finite, 50.0)
    radius = _percentile([abs(v - med) for v in finite], pct)
    if not math.isfinite(radius) or radius <= 0:
        radius = min_span

    lo = med - radius
    hi = med + radius
    if lower_bound is not None:
        lo = max(lo, float(lower_bound))
    if hi <= lo:
        hi = lo + min_span
    return [float(lo), float(hi)]


def _perf_log(label: str, start_time: float, **fields) -> None:
    """Emit callback timing metrics when profiling is enabled.

    Args:
        label: Metric label used in the emitted log message.
        start_time: Timer start from ``time.perf_counter()``.
        **fields: Extra key-value metadata appended to the message.

    Returns:
        None. Logging is skipped unless ``CHIPMUNK_PROFILE=1``.
    """
    if not _PROFILE_PERF:
        return

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    details = " ".join(f"{k}={v}" for k, v in fields.items())
    msg = f"perf {label} elapsed_ms={elapsed_ms:.1f}"
    if details:
        msg = f"{msg} {details}"
    _LOGGER.info(msg)


def create_app() -> Dash:
    """Create and configure the Chipmunk Dash application.

    Returns:
        A fully configured Dash app with layout, callbacks, and styles.

    Side Effects:
        Reads subjects from the data layer during app construction.
    """
    subjects = get_all_subjects()
    recent_subjects = get_subjects_with_recent_sessions()
    assets_dir = os.path.join(os.path.dirname(__file__), "assets")
    app = Dash(
        __name__,
        title="chipmunk dashboard",
        suppress_callback_exceptions=True,
        assets_folder=assets_dir,
        external_stylesheets=[
            "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap"
        ],
    )

    # Auto-refresh interval (60 minutes)
    auto_refresh = dcc.Interval(id="auto-refresh", interval=60 * 60 * 1000)

    def _build_subject_options(
        all_subjects: list[str], recent: set[str]
    ) -> tuple[list[dict], list[dict]]:
        """Build separate checklist option lists for recent and older subjects.

        Subjects with a session in the last 14 days are shown in accent color
        and bold weight so they are immediately visible without scrolling.

        Args:
            all_subjects: Full sorted list of subject names.
            recent: Set of subject names with recent sessions.

        Returns:
            A ``(recent_opts, older_opts)`` tuple where recent subjects carry a
            styled ``html.Span`` label and older subjects use a plain string.
        """
        recent_opts = [
            {
                "label": html.Span(
                    s,
                    style={"color": _THEME["accent"], "fontWeight": "bold"},
                ),
                "value": s,
            }
            for s in all_subjects
            if s in recent
        ]
        older_opts = [{"label": s, "value": s} for s in all_subjects if s not in recent]
        return recent_opts, older_opts

    # -- helpers --------------------------------------------------------------
    def _plot_height(gid: str) -> str:
        """Return per-panel graph height with a sensible default."""
        return _PLOT_H_BY_ID.get(gid, _PLOT_H_DEFAULT)

    def _graph(gid: str) -> dcc.Graph:
        """Create a standardized graph component used in dashboard rows.

        Args:
            gid: Dash component id for the graph.

        Returns:
            A configured ``dcc.Graph`` with shared sizing and display settings.
        """
        return dcc.Graph(
            id=gid,
            className="dashboard-graph",
            style={"height": _plot_height(gid), "width": "100%"},
            config={"displayModeBar": False},
        )

    def _clock_label(hours_since_midnight: float) -> str:
        """Format decimal hours as a zero-padded clock string."""
        if not math.isfinite(hours_since_midnight):
            return "unknown"
        total_seconds = int(round(hours_since_midnight * 3600))
        total_seconds = max(0, min(total_seconds, 24 * 3600 - 1))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"

    def _row(*ids: str) -> html.Div:
        """Create a grid row of standardized graph components.

        Args:
            *ids: Graph component ids to render in the row.

        Returns:
            A ``html.Div`` containing one graph per id in a responsive grid.
        """
        return html.Div(
            [_graph(i) for i in ids],
            className="dashboard-row",
            style={
                "display": "grid",
                "gridTemplateColumns": f"repeat({len(ids)}, 1fr)",
                "gap": "12px",
                "marginBottom": "12px",
            },
        )

    def _apply_split_toggle(
        fig: go.Figure,
        combined_idx: list[int],
        split_idx: list[int],
        trace_count: int,
        label: str,
    ) -> None:
        """Apply a consistent single-button aggregate/split toggle."""
        if not combined_idx or not split_idx:
            return
        off_visible = [idx in combined_idx for idx in range(trace_count)]
        on_visible = [idx in split_idx for idx in range(trace_count)]
        fig.update_layout(
            updatemenus=[
                dict(
                    type="buttons",
                    active=-1,
                    direction="left",
                    x=1.0,
                    y=1.18,
                    xanchor="right",
                    yanchor="top",
                    showactive=True,
                    bgcolor=_THEME["card"],
                    bordercolor=_THEME["border"],
                    font=dict(size=11, color=_THEME["text"]),
                    buttons=[
                        dict(
                            label=label,
                            method="restyle",
                            args=[{"visible": on_visible}],
                            args2=[{"visible": off_visible}],
                        )
                    ],
                )
            ]
        )

    def _kde_line_xy(
        values: list[float], points: int = 128
    ) -> tuple[list[float], list[float]]:
        """Compute x/y points for a Gaussian KDE line."""
        finite_vals: list[float] = []
        for raw_val in values:
            try:
                val = float(raw_val)
            except (TypeError, ValueError):
                continue
            if math.isfinite(val):
                finite_vals.append(val)
        n_vals = len(finite_vals)
        if n_vals == 0:
            return [], []
        if n_vals == 1:
            center = finite_vals[0]
            span = max(abs(center) * 0.1, 0.05)
            x_min = center - span
            x_max = center + span
            bandwidth = max(span / 3.0, 1e-3)
            xs = [x_min + (x_max - x_min) * i / (points - 1) for i in range(points)]
            norm = 1.0 / (bandwidth * math.sqrt(2.0 * math.pi))
            ys = [
                norm * math.exp(-0.5 * ((x_val - center) / bandwidth) ** 2)
                for x_val in xs
            ]
            return xs, ys

        sorted_vals = sorted(finite_vals)
        x_min = sorted_vals[0]
        x_max = sorted_vals[-1]
        if math.isclose(x_min, x_max):
            span = max(abs(x_min) * 0.1, 0.05)
            x_min -= span
            x_max += span

        mean_val = sum(finite_vals) / n_vals
        variance = sum((v - mean_val) ** 2 for v in finite_vals) / max(n_vals - 1, 1)
        std_val = math.sqrt(max(variance, 1e-12))
        q1 = sorted_vals[int((n_vals - 1) * 0.25)]
        q3 = sorted_vals[int((n_vals - 1) * 0.75)]
        iqr_sigma = (q3 - q1) / 1.34 if q3 > q1 else std_val
        sigma = min(std_val, iqr_sigma) if iqr_sigma > 0 else std_val
        bandwidth = 0.9 * sigma * (n_vals ** (-1.0 / 5.0))
        if (not math.isfinite(bandwidth)) or bandwidth <= 0:
            bandwidth = max((x_max - x_min) / 25.0, 1e-3)

        xs = [x_min + (x_max - x_min) * i / (points - 1) for i in range(points)]
        norm = 1.0 / (n_vals * bandwidth * math.sqrt(2.0 * math.pi))
        ys = [
            norm
            * sum(
                math.exp(-0.5 * ((x_val - sample) / bandwidth) ** 2)
                for sample in finite_vals
            )
            for x_val in xs
        ]
        return xs, ys

    def _add_kde_line_trace(
        fig: go.Figure,
        values: list[float],
        *,
        name: str,
        color: str,
        legendgroup: str,
        showlegend: bool,
        visible: bool,
        hover_label: str,
    ) -> None:
        """Render a KDE distribution as a line trace."""
        xs, ys = _kde_line_xy(values)
        if not xs:
            return
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                name=name,
                line=dict(color=color, width=2),
                fill="tozeroy",
                opacity=0.4,
                legendgroup=legendgroup,
                showlegend=showlegend,
                hovertemplate="%{x:.3f}s · density %{y:.3f}<extra>"
                + hover_label
                + "</extra>",
                visible=visible,
            )
        )

    # -- sidebar --------------------------------------------------------------
    _init_recent_opts, _init_older_opts = _build_subject_options(
        subjects, recent_subjects
    )
    sidebar = html.Div(
        [
            html.Label("Subjects", style={"fontWeight": "bold"}),
            html.Div(
                "blue = subjects with recent sessions",
                style={
                    "fontSize": "11px",
                    "color": _THEME["muted"],
                    "marginBottom": "2px",
                },
            ),
            html.Div(
                [
                    dcc.Checklist(
                        id="subjects-recent",
                        options=_init_recent_opts,
                        value=[],
                        style={
                            "display": "flex",
                            "flexDirection": "column",
                            "gap": "2px",
                        },
                        inputStyle={"marginRight": "6px", "transform": "scale(1.2)"},
                        labelStyle={"fontSize": "16px", "cursor": "pointer"},
                    ),
                    html.Hr(
                        id="subjects-divider",
                        style={
                            "margin": "4px 0",
                            "border": "none",
                            "borderTop": f"1px solid {_THEME['border']}",
                            "display": (
                                "block"
                                if (_init_recent_opts and _init_older_opts)
                                else "none"
                            ),
                        },
                    ),
                    dcc.Checklist(
                        id="subjects-older",
                        options=_init_older_opts,
                        value=[],
                        style={
                            "display": "flex",
                            "flexDirection": "column",
                            "gap": "2px",
                        },
                        inputStyle={"marginRight": "6px", "transform": "scale(1.2)"},
                        labelStyle={"fontSize": "16px", "cursor": "pointer"},
                    ),
                ],
                className="subjects-list",
                style={
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
                style={"width": "100%", "marginBottom": "4px"},
            ),
            html.Button(
                "Today",
                id="today-button",
                n_clicks=0,
                style={
                    "width": "100%",
                    "marginBottom": "8px",
                    "cursor": "pointer",
                    "fontSize": "12px",
                },
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
                options=cast(Any, [{"label": "Enable Smoothing", "value": "smooth"}]),
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
        className="dashboard-sidebar",
        style={
            "padding": "16px",
            "background": _THEME["panel"],
            "display": "flex",
            "flexDirection": "column",
        },
    )

    # -- content sections -----------------------------------------------------
    single_overview = html.Div(
        [
            _row("frac-correct", "p-right", "chrono", "session-perf"),
            _row("trial-count-time", "water-cumulative"),
            html.Div(
                [
                    html.Details(
                        [
                            html.Summary("Session settings"),
                            html.Div(
                                [
                                    html.Pre(
                                        "Select subject(s) to show settings.",
                                        id="session-settings-box",
                                        style={"margin": 0, "whiteSpace": "pre-wrap"},
                                    )
                                ],
                                className="overview-summary-card",
                            ),
                        ],
                        id="session-settings-toggle",
                        className="overview-settings-toggle",
                    )
                ],
                className="overview-summary-stack",
            ),
        ],
        className="single-tab-pane",
    )
    single_timing = html.Div(
        [
            _row("init-line", "init-hist"),
            _row("wait-delta-line", "wait-delta-hist"),
            _row("wait-floor-line", "wait-floor-hist"),
            _row("response-time-line", "response-time"),
            _row("iti-rolling", "iti-dist"),
        ],
        className="single-tab-pane",
    )
    single_section = html.Div(
        [
            html.H3(
                "Single Session",
                style={"margin": "24px 0 12px", "borderBottom": "1px solid #ddd"},
            ),
            dcc.Tabs(
                id="single-session-tabs",
                value="single-overview",
                children=[
                    dcc.Tab(
                        label="Overview",
                        value="single-overview",
                        children=single_overview,
                    ),
                    dcc.Tab(
                        label="Timing", value="single-timing", children=single_timing
                    ),
                ],
            ),
        ]
    )

    multi_section = html.Div(
        [
            html.H3(
                "Multi Session",
                style={"margin": "24px 0 12px", "borderBottom": "1px solid #ddd"},
            ),
            _row("performance", "ew-rate", "side-bias", "trial-counts"),
            _row("init-times", "median-wait", "median-rt", "water", "training-time"),
        ]
    )

    main_area = html.Div(
        [single_section, multi_section],
        className="dashboard-main",
        style={
            "flex": 1,
            "display": "flex",
            "flexDirection": "column",
            "overflowY": "auto",
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
                className="dashboard-shell",
            ),
        ],
        className="dashboard-root",
        style={
            "fontFamily": "IBM Plex Sans, sans-serif",
            "padding": "12px",
            "background": _THEME["bg"],
            "color": _THEME["text"],
        },
    )

    # -- callbacks ------------------------------------------------------------

    def _sessions_on_date(sessions_list: list[str], date_val: str) -> str | None:
        """Return the latest session name for a subject on a given calendar date.

        Args:
            sessions_list: Pre-fetched list of session names for the subject,
                in ascending chronological order.
            date_val: Date in ``YYYY-MM-DD`` format.

        Returns:
            The latest ``session_name`` for that day, or ``None`` if no session
            exists on that date for the subject.
        """
        raw_date = date_val.replace("-", "")  # YYYYMMDD
        day_sessions = [s for s in sessions_list if s.startswith(raw_date)]
        return day_sessions[-1] if day_sessions else None

    # Session Date & Time Logic
    @app.callback(
        Output("session-date", "date"),
        Output("session-date", "min_date_allowed"),
        Output("session-date", "max_date_allowed"),
        Output("session-date", "initial_visible_month"),
        Input("subjects-recent", "value"),
        Input("subjects-older", "value"),
        Input("auto-refresh", "n_intervals"),
        Input("today-button", "n_clicks"),
    )
    def _update_date_options(
        subjects_recent, subjects_older, n_intervals, _today_clicks
    ):
        """Update date-picker bounds spanning all selected subjects.

        Callback Inputs:
            - ``subjects-recent.value``
            - ``subjects-older.value``
            - ``auto-refresh.n_intervals``
            - ``today-button.n_clicks``

        Callback Outputs:
            - ``session-date.date``
            - ``session-date.min_date_allowed``
            - ``session-date.max_date_allowed``
            - ``session-date.initial_visible_month``

        Args:
            subjects_recent: Selected recent subject names.
            subjects_older: Selected older subject names.
            n_intervals: Auto-refresh tick counter (unused except as trigger).
            _today_clicks: Today button click count (unused; presence in
                ``ctx.triggered_id`` is the signal).

        Returns:
            A tuple with selected date and allowed date bounds, or ``None`` values
            when no sessions are available.

        Side Effects:
            Triggers multi-session cache prewarming anchored to the latest date.
        """
        today = _date.today().isoformat()
        if ctx.triggered_id == "today-button":
            return today, None, today, today

        subjects = (subjects_recent or []) + (subjects_older or [])
        if not subjects:
            return None, None, today, today

        all_dates = [
            f"{s[:4]}-{s[4:6]}-{s[6:8]}"
            for subj in subjects
            for s in get_sessions(subj)
            if len(s) >= 8
        ]

        if not all_dates:
            return None, None, today, today

        min_d = min(all_dates)
        max_d = min(max(all_dates), today)
        prewarm_multisession_cache(subjects, sessions_back=30, start_date=max_d)
        return max_d, min_d, today, max_d

    @app.callback(
        Output("session-time", "options"),
        Output("session-time", "value"),
        Input("session-date", "date"),
        Input("subjects-recent", "value"),
        Input("subjects-older", "value"),
    )
    def _update_time_options(date_val, subjects_recent, subjects_older):
        """Update session-time dropdown options for the selected calendar day.

        Callback Inputs:
            - ``session-date.date``
            - ``subjects-recent.value``
            - ``subjects-older.value``

        Callback Outputs:
            - ``session-time.options``
            - ``session-time.value``

        Args:
            date_val: Selected date in ``YYYY-MM-DD`` format.
            subjects_recent: Selected recent subject names.
            subjects_older: Selected older subject names.

        Returns:
            Dropdown options for sessions on that day and the default selected
            value (latest session for the day), or empty outputs.
        """
        subjects = (subjects_recent or []) + (subjects_older or [])
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
        Output("subjects-recent", "value"),
        Output("subjects-older", "value"),
        Input("clear-subjects", "n_clicks"),
        prevent_initial_call=True,
    )
    def _clear_subjects(n_clicks):
        """Clear all subject selections when the reset button is clicked.

        Callback Inputs:
            - ``clear-subjects.n_clicks``

        Callback Outputs:
            - ``subjects-recent.value``
            - ``subjects-older.value``

        Args:
            n_clicks: Button click count provided by Dash.

        Returns:
            A pair of empty lists to clear both subject checklist values.
        """
        return [], []

    @app.callback(
        Output("subjects-recent", "options"),
        Output("subjects-older", "options"),
        Output("subjects-divider", "style"),
        Input("session-date", "date"),
        Input("auto-refresh", "n_intervals"),
    )
    def _update_subject_options(date_val, _n_intervals):
        """Refresh the subject checklist options, filtered to the selected date.

        Callback Inputs:
            - ``session-date.date``
            - ``auto-refresh.n_intervals``

        Callback Outputs:
            - ``subjects-recent.options``
            - ``subjects-older.options``
            - ``subjects-divider.style``

        Args:
            date_val: Selected date in ``YYYY-MM-DD`` format, or ``None``.
            _n_intervals: Auto-refresh tick counter (unused).

        Returns:
            A tuple of recent options, older options, and divider style dict.
            When a date is selected, only subjects with sessions on that date
            are included. Falls back to all subjects when no date is set.
            The divider is hidden when either group is empty.
        """
        all_subjs = get_all_subjects()
        if date_val:
            raw_date = date_val.replace("-", "")
            date_subjs = set(get_subjects_for_date(raw_date))
            all_subjs = [s for s in all_subjs if s in date_subjs]
        recent = get_subjects_with_recent_sessions()
        recent_opts, older_opts = _build_subject_options(all_subjs, recent)
        divider_style = {
            "margin": "4px 0",
            "border": "none",
            "borderTop": f"1px solid {_THEME['border']}",
            "display": "block" if (recent_opts and older_opts) else "none",
        }
        return recent_opts, older_opts, divider_style

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
        Output("wait-floor-line", "figure"),
        Output("wait-floor-hist", "figure"),
        Output("response-time-line", "figure"),
        Output("response-time", "figure"),
        Output("iti-dist", "figure"),
        Output("trial-count-time", "figure"),
        Output("water-cumulative", "figure"),
        Output("iti-rolling", "figure"),
        Input("subjects-recent", "value"),
        Input("subjects-older", "value"),
        Input("session-time", "value"),
        Input("auto-refresh", "n_intervals"),
        State("session-date", "date"),
    )
    def _update_single(
        subjects_recent, subjects_older, session_name, n_intervals, session_date
    ):
        """Render all single-session figures for the current selection.

        Callback Inputs:
            - ``subjects-recent.value``
            - ``subjects-older.value``
            - ``session-time.value``
            - ``auto-refresh.n_intervals``

        Callback State:
            - ``session-date.date``

        Callback Outputs:
            Sixteen figures for outcomes, psychometric/chronometric, performance,
            initiation, post-go center dwell, wait-floor, response-time, session
            pacing, and ITI rolling-trend views.

        Args:
            subjects_recent: Selected recent subject names.
            subjects_older: Selected older subject names.
            session_name: Selected session name for the first subject.
            n_intervals: Auto-refresh tick counter (unused except as trigger).
            session_date: Currently selected date in ``YYYY-MM-DD`` format, or
                ``None``. When set and multiple subjects are selected, each
                additional subject resolves its session from this date.
        Returns:
            A 16-item tuple of Plotly figures in callback output order.

        Side Effects:
            Reads cached session metrics and emits performance logs when enabled.
        """
        start = time.perf_counter()
        n = 16
        subjects = (subjects_recent or []) + (subjects_older or [])

        sessions_by_subject = {s: get_sessions(s) for s in subjects}
        valid_subjects = [s for s in subjects if sessions_by_subject.get(s)]

        if not valid_subjects:
            e = _empty_fig()
            _perf_log("_update_single", start, subjects=0)
            return tuple(e for _ in range(n))

        multi = len(subjects) > 1
        multi_col = len(valid_subjects) > 1

        # Initialize figures
        fig_fc = go.Figure()

        fig_pr, fig_ch, fig_sp = go.Figure(), go.Figure(), go.Figure()
        fig_il, fig_ih = go.Figure(), go.Figure()
        fig_wdl, fig_wdh = go.Figure(), go.Figure()
        fig_wfl, fig_wfh = go.Figure(), go.Figure()
        fig_rtl = go.Figure()
        fig_rt = go.Figure()
        fig_itid = go.Figure()
        fig_tct = go.Figure()
        fig_wc = go.Figure()
        fig_itir = go.Figure()
        init_y_vals: list[float] = []
        wait_delta_y_vals: list[float] = []
        wait_floor_y_vals: list[float] = []
        response_line_y_vals: list[float] = []
        wdl_combined_idx: list[int] = []
        wdl_split_idx: list[int] = []
        wdh_combined_idx: list[int] = []
        wdh_split_idx: list[int] = []
        wfl_combined_idx: list[int] = []
        wfl_split_idx: list[int] = []
        wfh_combined_idx: list[int] = []
        wfh_split_idx: list[int] = []
        itid_combined_idx: list[int] = []
        itid_split_idx: list[int] = []
        wdl_trace_count = 0
        wdh_trace_count = 0
        wfl_trace_count = 0
        wfh_trace_count = 0
        itid_trace_count = 0
        itir_combined_idx: list[int] = []
        itir_split_idx: list[int] = []
        itir_trace_count = 0
        rtl_combined_idx: list[int] = []
        rtl_split_idx: list[int] = []
        rtl_trace_count = 0
        rt_combined_idx: list[int] = []
        rt_split_idx: list[int] = []
        rt_trace_count = 0
        wc_combined_idx: list[int] = []
        wc_split_idx: list[int] = []
        wc_trace_count = 0

        # Collect outcome totals for multi-subject horizontal bars
        multi_outcome_data = []

        for i, subj in enumerate(valid_subjects):
            c = COLORS[i % len(COLORS)]
            grp = subj
            sessions_list = sessions_by_subject[subj]
            if i == 0 and session_name:
                # First subject: use the session selected in the time dropdown
                ses = session_name
            elif session_date:
                # Other subjects (or first with no time selected): resolve from date
                ses = _sessions_on_date(sessions_list, session_date)
            else:
                ses = sessions_list[-1] if sessions_list else None
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
                init_y_vals.extend(sm["init_times"])
                init_y_vals.extend(sm["init_roll_y"])

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
                    _add_kde_line_trace(
                        fig_ih,
                        sm["init_times"],
                        name=subj,
                        color=c,
                        legendgroup=grp,
                        showlegend=False,
                        visible=True,
                        hover_label=subj,
                    )

            # --- Row 3: Post-Go Center Dwell ---

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
                        visible=True,
                    )
                )
                wdl_combined_idx.append(wdl_trace_count)
                wdl_trace_count += 1
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
                            visible=True,
                        )
                    )
                    wdl_combined_idx.append(wdl_trace_count)
                    wdl_trace_count += 1
                left_delta_times = sm.get("wait_delta_left_times", [])
                right_delta_times = sm.get("wait_delta_right_times", [])
                if left_delta_times and sm.get("wait_trial_nums_left", []):
                    fig_wdl.add_trace(
                        go.Scattergl(
                            x=sm["wait_trial_nums_left"],
                            y=left_delta_times,
                            mode="markers",
                            name="Left",
                            showlegend=i == 0,
                            legendgroup="choice-left",
                            marker=dict(color="royalblue", size=3, opacity=0.4),
                            hovertemplate="%{y:.3f}s<extra>left</extra>",
                            visible=False,
                        )
                    )
                    wdl_split_idx.append(wdl_trace_count)
                    wdl_trace_count += 1
                if sm.get("wait_delta_left_x", []) and sm.get("wait_delta_left_y", []):
                    fig_wdl.add_trace(
                        go.Scatter(
                            x=sm["wait_delta_left_x"],
                            y=sm["wait_delta_left_y"],
                            mode="lines",
                            name="Left roll",
                            showlegend=i == 0,
                            legendgroup="choice-left",
                            line=dict(color="royalblue", width=2),
                            hovertemplate="%{y:.3f}s<extra>left rolling</extra>",
                            visible=False,
                        )
                    )
                    wdl_split_idx.append(wdl_trace_count)
                    wdl_trace_count += 1
                if right_delta_times and sm.get("wait_trial_nums_right", []):
                    fig_wdl.add_trace(
                        go.Scattergl(
                            x=sm["wait_trial_nums_right"],
                            y=right_delta_times,
                            mode="markers",
                            name="Right",
                            showlegend=i == 0,
                            legendgroup="choice-right",
                            marker=dict(color="darkorange", size=3, opacity=0.4),
                            hovertemplate="%{y:.3f}s<extra>right</extra>",
                            visible=False,
                        )
                    )
                    wdl_split_idx.append(wdl_trace_count)
                    wdl_trace_count += 1
                if sm.get("wait_delta_right_x", []) and sm.get(
                    "wait_delta_right_y", []
                ):
                    fig_wdl.add_trace(
                        go.Scatter(
                            x=sm["wait_delta_right_x"],
                            y=sm["wait_delta_right_y"],
                            mode="lines",
                            name="Right roll",
                            showlegend=i == 0,
                            legendgroup="choice-right",
                            line=dict(color="darkorange", width=2),
                            hovertemplate="%{y:.3f}s<extra>right rolling</extra>",
                            visible=False,
                        )
                    )
                    wdl_split_idx.append(wdl_trace_count)
                    wdl_trace_count += 1
                wait_delta_y_vals.extend(sm["wait_delta_times"])
                wait_delta_y_vals.extend(sm["wait_delta_y"])
                wait_delta_y_vals.extend(sm.get("wait_delta_left_y", []))
                wait_delta_y_vals.extend(sm.get("wait_delta_right_y", []))

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
                            visible=True,
                        )
                    )
                    wdh_combined_idx.append(wdh_trace_count)
                    wdh_trace_count += 1
                    if left_delta_times:
                        fig_wdh.add_trace(
                            go.Box(
                                x=[subj] * len(left_delta_times),
                                y=left_delta_times,
                                name="Left",
                                marker_color="royalblue",
                                legendgroup="choice-left",
                                showlegend=i == 0,
                                boxmean=True,
                                offsetgroup="left",
                                visible=False,
                            )
                        )
                        wdh_split_idx.append(wdh_trace_count)
                        wdh_trace_count += 1
                    if right_delta_times:
                        fig_wdh.add_trace(
                            go.Box(
                                x=[subj] * len(right_delta_times),
                                y=right_delta_times,
                                name="Right",
                                marker_color="darkorange",
                                legendgroup="choice-right",
                                showlegend=i == 0,
                                boxmean=True,
                                offsetgroup="right",
                                visible=False,
                            )
                        )
                        wdh_split_idx.append(wdh_trace_count)
                        wdh_trace_count += 1
                else:
                    _add_kde_line_trace(
                        fig_wdh,
                        sm["wait_delta_times"],
                        name=subj,
                        color=c,
                        legendgroup=grp,
                        showlegend=False,
                        visible=True,
                        hover_label=subj,
                    )
                    wdh_combined_idx.append(wdh_trace_count)
                    wdh_trace_count += 1
                    if left_delta_times:
                        _add_kde_line_trace(
                            fig_wdh,
                            left_delta_times,
                            name="Left",
                            color="royalblue",
                            legendgroup="choice-left",
                            showlegend=True,
                            visible=False,
                            hover_label="left",
                        )
                        wdh_split_idx.append(wdh_trace_count)
                        wdh_trace_count += 1
                    if right_delta_times:
                        _add_kde_line_trace(
                            fig_wdh,
                            right_delta_times,
                            name="Right",
                            color="darkorange",
                            legendgroup="choice-right",
                            showlegend=True,
                            visible=False,
                            hover_label="right",
                        )
                        wdh_split_idx.append(wdh_trace_count)
                        wdh_trace_count += 1

            # --- Row 3 (cont.): Wait Floor ---

            if sm["wait_times"] and sm["wait_trial_nums"]:
                fig_wfl.add_trace(
                    go.Scattergl(
                        x=sm["wait_trial_nums"],
                        y=sm["wait_times"],
                        mode="markers",
                        name=subj,
                        showlegend=False,
                        legendgroup=grp,
                        marker=dict(color=c, size=3, opacity=0.4),
                        hovertemplate="%{y:.3f}s" + ht_subj,
                        visible=True,
                    )
                )
                wfl_combined_idx.append(wfl_trace_count)
                wfl_trace_count += 1
                if sm["wait_roll_x"] and sm["wait_roll_y"]:
                    fig_wfl.add_trace(
                        go.Scatter(
                            x=sm["wait_roll_x"],
                            y=sm["wait_roll_y"],
                            mode="lines",
                            name=subj + " roll",
                            showlegend=False,
                            legendgroup=grp,
                            line=dict(color=c, width=2),
                            hovertemplate="%{y:.3f}s (roll)" + ht_subj,
                            visible=True,
                        )
                    )
                    wfl_combined_idx.append(wfl_trace_count)
                    wfl_trace_count += 1
                wait_left_times = sm.get("wait_times_left", [])
                wait_right_times = sm.get("wait_times_right", [])
                if wait_left_times and sm.get("wait_trial_nums_left", []):
                    fig_wfl.add_trace(
                        go.Scattergl(
                            x=sm["wait_trial_nums_left"],
                            y=wait_left_times,
                            mode="markers",
                            name="Left",
                            showlegend=i == 0,
                            legendgroup="choice-left",
                            marker=dict(color="royalblue", size=3, opacity=0.4),
                            hovertemplate="%{y:.3f}s<extra>left</extra>",
                            visible=False,
                        )
                    )
                    wfl_split_idx.append(wfl_trace_count)
                    wfl_trace_count += 1
                if sm.get("wait_left_x", []) and sm.get("wait_left_y", []):
                    fig_wfl.add_trace(
                        go.Scatter(
                            x=sm["wait_left_x"],
                            y=sm["wait_left_y"],
                            mode="lines",
                            name="Left roll",
                            showlegend=i == 0,
                            legendgroup="choice-left",
                            line=dict(color="royalblue", width=2),
                            hovertemplate="%{y:.3f}s<extra>left rolling</extra>",
                            visible=False,
                        )
                    )
                    wfl_split_idx.append(wfl_trace_count)
                    wfl_trace_count += 1
                if wait_right_times and sm.get("wait_trial_nums_right", []):
                    fig_wfl.add_trace(
                        go.Scattergl(
                            x=sm["wait_trial_nums_right"],
                            y=wait_right_times,
                            mode="markers",
                            name="Right",
                            showlegend=i == 0,
                            legendgroup="choice-right",
                            marker=dict(color="darkorange", size=3, opacity=0.4),
                            hovertemplate="%{y:.3f}s<extra>right</extra>",
                            visible=False,
                        )
                    )
                    wfl_split_idx.append(wfl_trace_count)
                    wfl_trace_count += 1
                if sm.get("wait_right_x", []) and sm.get("wait_right_y", []):
                    fig_wfl.add_trace(
                        go.Scatter(
                            x=sm["wait_right_x"],
                            y=sm["wait_right_y"],
                            mode="lines",
                            name="Right roll",
                            showlegend=i == 0,
                            legendgroup="choice-right",
                            line=dict(color="darkorange", width=2),
                            hovertemplate="%{y:.3f}s<extra>right rolling</extra>",
                            visible=False,
                        )
                    )
                    wfl_split_idx.append(wfl_trace_count)
                    wfl_trace_count += 1
                wait_floor_y_vals.extend(sm["wait_times"])
                wait_floor_y_vals.extend(sm["wait_roll_y"])
                wait_floor_y_vals.extend(sm.get("wait_left_y", []))
                wait_floor_y_vals.extend(sm.get("wait_right_y", []))

                if multi:
                    fig_wfh.add_trace(
                        go.Box(
                            y=sm["wait_times"],
                            name=subj,
                            marker_color=c,
                            legendgroup=grp,
                            showlegend=False,
                            boxmean=True,
                            visible=True,
                        )
                    )
                    wfh_combined_idx.append(wfh_trace_count)
                    wfh_trace_count += 1
                    if wait_left_times:
                        fig_wfh.add_trace(
                            go.Box(
                                x=[subj] * len(wait_left_times),
                                y=wait_left_times,
                                name="Left",
                                marker_color="royalblue",
                                legendgroup="choice-left",
                                showlegend=i == 0,
                                boxmean=True,
                                offsetgroup="left",
                                visible=False,
                            )
                        )
                        wfh_split_idx.append(wfh_trace_count)
                        wfh_trace_count += 1
                    if wait_right_times:
                        fig_wfh.add_trace(
                            go.Box(
                                x=[subj] * len(wait_right_times),
                                y=wait_right_times,
                                name="Right",
                                marker_color="darkorange",
                                legendgroup="choice-right",
                                showlegend=i == 0,
                                boxmean=True,
                                offsetgroup="right",
                                visible=False,
                            )
                        )
                        wfh_split_idx.append(wfh_trace_count)
                        wfh_trace_count += 1
                else:
                    _add_kde_line_trace(
                        fig_wfh,
                        sm["wait_times"],
                        name=subj,
                        color=c,
                        legendgroup=grp,
                        showlegend=False,
                        visible=True,
                        hover_label=subj,
                    )
                    wfh_combined_idx.append(wfh_trace_count)
                    wfh_trace_count += 1
                    if wait_left_times:
                        _add_kde_line_trace(
                            fig_wfh,
                            wait_left_times,
                            name="Left",
                            color="royalblue",
                            legendgroup="choice-left",
                            showlegend=True,
                            visible=False,
                            hover_label="left",
                        )
                        wfh_split_idx.append(wfh_trace_count)
                        wfh_trace_count += 1
                    if wait_right_times:
                        _add_kde_line_trace(
                            fig_wfh,
                            wait_right_times,
                            name="Right",
                            color="darkorange",
                            legendgroup="choice-right",
                            showlegend=True,
                            visible=False,
                            hover_label="right",
                        )
                        wfh_split_idx.append(wfh_trace_count)
                        wfh_trace_count += 1

            # --- Row 4: Response Time ---
            response_times = sm.get("response_times", [])
            response_left = sm.get("response_times_left", [])
            response_right = sm.get("response_times_right", [])
            response_trial_nums = sm.get("response_trial_nums", [])
            response_roll_x = sm.get("response_roll_x", [])
            response_roll_y = sm.get("response_roll_y", [])
            response_trial_nums_left = sm.get("response_trial_nums_left", [])
            response_trial_nums_right = sm.get("response_trial_nums_right", [])
            response_roll_left_x = sm.get("response_roll_left_x", [])
            response_roll_left_y = sm.get("response_roll_left_y", [])
            response_roll_right_x = sm.get("response_roll_right_x", [])
            response_roll_right_y = sm.get("response_roll_right_y", [])

            if response_trial_nums and response_times:
                fig_rtl.add_trace(
                    go.Scattergl(
                        x=response_trial_nums,
                        y=response_times,
                        mode="markers",
                        name=subj,
                        showlegend=False,
                        legendgroup=grp,
                        marker=dict(color=c, size=3, opacity=0.4),
                        hovertemplate="%{y:.3f}s" + ht_subj,
                        visible=True,
                    )
                )
                rtl_combined_idx.append(rtl_trace_count)
                rtl_trace_count += 1
                if response_roll_x and response_roll_y:
                    fig_rtl.add_trace(
                        go.Scatter(
                            x=response_roll_x,
                            y=response_roll_y,
                            mode="lines",
                            name=subj + " roll",
                            showlegend=False,
                            legendgroup=grp,
                            line=dict(color=c, width=2),
                            hovertemplate="%{y:.3f}s (roll)" + ht_subj,
                            visible=True,
                        )
                    )
                    rtl_combined_idx.append(rtl_trace_count)
                    rtl_trace_count += 1
                if response_left and response_trial_nums_left:
                    fig_rtl.add_trace(
                        go.Scattergl(
                            x=response_trial_nums_left,
                            y=response_left,
                            mode="markers",
                            name="Left",
                            showlegend=i == 0,
                            legendgroup="rt-left",
                            marker=dict(color="royalblue", size=3, opacity=0.4),
                            hovertemplate="%{y:.3f}s<extra>left</extra>",
                            visible=False,
                        )
                    )
                    rtl_split_idx.append(rtl_trace_count)
                    rtl_trace_count += 1
                if response_roll_left_x and response_roll_left_y:
                    fig_rtl.add_trace(
                        go.Scatter(
                            x=response_roll_left_x,
                            y=response_roll_left_y,
                            mode="lines",
                            name="Left roll",
                            showlegend=i == 0,
                            legendgroup="rt-left",
                            line=dict(color="royalblue", width=2),
                            hovertemplate="%{y:.3f}s<extra>left rolling</extra>",
                            visible=False,
                        )
                    )
                    rtl_split_idx.append(rtl_trace_count)
                    rtl_trace_count += 1
                if response_right and response_trial_nums_right:
                    fig_rtl.add_trace(
                        go.Scattergl(
                            x=response_trial_nums_right,
                            y=response_right,
                            mode="markers",
                            name="Right",
                            showlegend=i == 0,
                            legendgroup="rt-right",
                            marker=dict(color="darkorange", size=3, opacity=0.4),
                            hovertemplate="%{y:.3f}s<extra>right</extra>",
                            visible=False,
                        )
                    )
                    rtl_split_idx.append(rtl_trace_count)
                    rtl_trace_count += 1
                if response_roll_right_x and response_roll_right_y:
                    fig_rtl.add_trace(
                        go.Scatter(
                            x=response_roll_right_x,
                            y=response_roll_right_y,
                            mode="lines",
                            name="Right roll",
                            showlegend=i == 0,
                            legendgroup="rt-right",
                            line=dict(color="darkorange", width=2),
                            hovertemplate="%{y:.3f}s<extra>right rolling</extra>",
                            visible=False,
                        )
                    )
                    rtl_split_idx.append(rtl_trace_count)
                    rtl_trace_count += 1
                response_line_y_vals.extend(response_times)
                response_line_y_vals.extend(response_roll_y)
                response_line_y_vals.extend(response_roll_left_y)
                response_line_y_vals.extend(response_roll_right_y)

            if multi_col:
                if response_times:
                    fig_rt.add_trace(
                        go.Box(
                            x=[subj] * len(response_times),
                            y=response_times,
                            name=subj,
                            legendgroup=grp,
                            showlegend=False,
                            marker_color=c,
                            boxmean=True,
                            visible=True,
                        )
                    )
                    rt_combined_idx.append(rt_trace_count)
                    rt_trace_count += 1
                if response_left:
                    fig_rt.add_trace(
                        go.Box(
                            x=[subj] * len(response_left),
                            y=response_left,
                            name="Left",
                            legendgroup="rt-left",
                            showlegend=i == 0,
                            marker_color="royalblue",
                            boxmean=True,
                            offsetgroup="left",
                            visible=False,
                        )
                    )
                    rt_split_idx.append(rt_trace_count)
                    rt_trace_count += 1
                if response_right:
                    fig_rt.add_trace(
                        go.Box(
                            x=[subj] * len(response_right),
                            y=response_right,
                            name="Right",
                            legendgroup="rt-right",
                            showlegend=i == 0,
                            marker_color="darkorange",
                            boxmean=True,
                            offsetgroup="right",
                            visible=False,
                        )
                    )
                    rt_split_idx.append(rt_trace_count)
                    rt_trace_count += 1
            else:
                if response_times:
                    _add_kde_line_trace(
                        fig_rt,
                        response_times,
                        name="All choices",
                        color=c,
                        legendgroup=grp,
                        showlegend=False,
                        visible=True,
                        hover_label="all choices",
                    )
                    rt_combined_idx.append(rt_trace_count)
                    rt_trace_count += 1
                if response_left:
                    _add_kde_line_trace(
                        fig_rt,
                        response_left,
                        name="Left",
                        color="royalblue",
                        legendgroup="rt-left",
                        showlegend=True,
                        visible=False,
                        hover_label="left",
                    )
                    rt_split_idx.append(rt_trace_count)
                    rt_trace_count += 1
                if response_right:
                    _add_kde_line_trace(
                        fig_rt,
                        response_right,
                        name="Right",
                        color="darkorange",
                        legendgroup="rt-right",
                        showlegend=True,
                        visible=False,
                        hover_label="right",
                    )
                    rt_split_idx.append(rt_trace_count)
                    rt_trace_count += 1

            iti_vals = sm.get("iti_times", [])
            iti_after_correct = sm.get("iti_times_after_correct", [])
            iti_after_incorrect = sm.get("iti_times_after_incorrect", [])
            iti_after_ew = sm.get("iti_times_after_ew", [])
            iti_after_no_choice = sm.get("iti_times_after_no_choice", [])
            if iti_vals:
                if multi_col:
                    fig_itid.add_trace(
                        go.Box(
                            y=iti_vals,
                            name=subj,
                            marker_color=c,
                            legendgroup=grp,
                            showlegend=False,
                            boxmean=True,
                            visible=True,
                        )
                    )
                    itid_combined_idx.append(itid_trace_count)
                    itid_trace_count += 1
                    for label, vals, color, group in [
                        (
                            "After Correct",
                            iti_after_correct,
                            "mediumseagreen",
                            "iti-correct",
                        ),
                        (
                            "After Incorrect",
                            iti_after_incorrect,
                            "tomato",
                            "iti-incorrect",
                        ),
                        ("After EW", iti_after_ew, "slategray", "iti-ew"),
                        (
                            "After No Choice",
                            iti_after_no_choice,
                            "#6b7280",
                            "iti-no-choice",
                        ),
                    ]:
                        if vals:
                            fig_itid.add_trace(
                                go.Box(
                                    x=[subj] * len(vals),
                                    y=vals,
                                    name=label,
                                    marker_color=color,
                                    legendgroup=group,
                                    showlegend=i == 0,
                                    boxmean=True,
                                    offsetgroup=group,
                                    visible=False,
                                )
                            )
                            itid_split_idx.append(itid_trace_count)
                            itid_trace_count += 1
                else:
                    _add_kde_line_trace(
                        fig_itid,
                        iti_vals,
                        name=subj,
                        color=c,
                        legendgroup=grp,
                        showlegend=False,
                        visible=True,
                        hover_label=subj,
                    )
                    itid_combined_idx.append(itid_trace_count)
                    itid_trace_count += 1
                    for label, vals, color in [
                        ("After Correct", iti_after_correct, "mediumseagreen"),
                        ("After Incorrect", iti_after_incorrect, "tomato"),
                        ("After EW", iti_after_ew, "slategray"),
                        ("After No Choice", iti_after_no_choice, "#6b7280"),
                    ]:
                        if vals:
                            _add_kde_line_trace(
                                fig_itid,
                                vals,
                                name=label,
                                color=color,
                                legendgroup=label.lower().replace(" ", "-"),
                                showlegend=True,
                                visible=False,
                                hover_label=label.lower(),
                            )
                            itid_split_idx.append(itid_trace_count)
                            itid_trace_count += 1

            trial_count_x = sm.get("trial_count_x", [])
            trial_count_y = sm.get("trial_count_y", [])
            if trial_count_x and trial_count_y:
                fig_tct.add_trace(
                    go.Scatter(
                        x=trial_count_x,
                        y=trial_count_y,
                        mode="lines+markers",
                        name=subj,
                        showlegend=multi_col,
                        legendgroup=grp,
                        marker=dict(color=c, size=6),
                        line=dict(color=c, width=2),
                        hovertemplate="%{y:.0f}<extra>" + subj + "</extra>",
                    )
                )

            water_cum_x = sm.get("water_cum_x", [])
            water_cum_total = sm.get("water_cum_total_ul", [])
            water_cum_left = sm.get("water_cum_left_ul", [])
            water_cum_right = sm.get("water_cum_right_ul", [])
            if water_cum_x and water_cum_total:
                fig_wc.add_trace(
                    go.Scatter(
                        x=water_cum_x,
                        y=water_cum_total,
                        mode="lines",
                        name=subj if multi_col else "Total",
                        showlegend=multi_col,
                        legendgroup=grp,
                        line=dict(color=c, width=2),
                        hovertemplate="%{y:.1f} µL<extra>" + subj + "</extra>",
                        visible=True,
                    )
                )
                wc_combined_idx.append(wc_trace_count)
                wc_trace_count += 1
                if water_cum_left:
                    fig_wc.add_trace(
                        go.Scatter(
                            x=water_cum_x,
                            y=water_cum_left,
                            mode="lines",
                            name="Left",
                            showlegend=i == 0,
                            legendgroup="water-left",
                            line=dict(color="royalblue", width=2),
                            hovertemplate="%{y:.1f} µL<extra>left</extra>",
                            visible=False,
                        )
                    )
                    wc_split_idx.append(wc_trace_count)
                    wc_trace_count += 1
                if water_cum_right:
                    fig_wc.add_trace(
                        go.Scatter(
                            x=water_cum_x,
                            y=water_cum_right,
                            mode="lines",
                            name="Right",
                            showlegend=i == 0,
                            legendgroup="water-right",
                            line=dict(color="darkorange", width=2),
                            hovertemplate="%{y:.1f} µL<extra>right</extra>",
                            visible=False,
                        )
                    )
                    wc_split_idx.append(wc_trace_count)
                    wc_trace_count += 1

            # --- Row 5: ITI rolling trend (25-trial median) ---
            iti_roll_x = sm.get("iti_roll_x", [])
            iti_roll_y = sm.get("iti_roll_y", [])
            if iti_roll_x and iti_roll_y:
                fig_itir.add_trace(
                    go.Scatter(
                        x=iti_roll_x,
                        y=iti_roll_y,
                        mode="lines+markers",
                        name=subj,
                        showlegend=multi,
                        legendgroup=grp,
                        marker=dict(color=c, size=6),
                        line=dict(color=c, width=2),
                        hovertemplate="%{y:.3f}s" + ht_subj,
                        visible=True,
                    )
                )
                itir_combined_idx.append(itir_trace_count)
                itir_trace_count += 1

            for label, x_vals, y_vals, color, group, hover_label in [
                (
                    "After Correct",
                    sm.get("iti_roll_correct_x", []),
                    sm.get("iti_roll_correct_y", []),
                    "mediumseagreen",
                    "iti-roll-correct",
                    "after correct",
                ),
                (
                    "After Incorrect",
                    sm.get("iti_roll_incorrect_x", []),
                    sm.get("iti_roll_incorrect_y", []),
                    "tomato",
                    "iti-roll-incorrect",
                    "after incorrect",
                ),
                (
                    "After EW",
                    sm.get("iti_roll_ew_x", []),
                    sm.get("iti_roll_ew_y", []),
                    "slategray",
                    "iti-roll-ew",
                    "after ew",
                ),
                (
                    "After No Choice",
                    sm.get("iti_roll_no_choice_x", []),
                    sm.get("iti_roll_no_choice_y", []),
                    "#6b7280",
                    "iti-roll-no-choice",
                    "after no choice",
                ),
            ]:
                if x_vals and y_vals:
                    fig_itir.add_trace(
                        go.Scatter(
                            x=x_vals,
                            y=y_vals,
                            mode="lines+markers",
                            name=label,
                            showlegend=i == 0,
                            legendgroup=group,
                            marker=dict(color=color, size=6),
                            line=dict(color=color, width=2),
                            hovertemplate=(
                                "%{y:.3f}s<extra>"
                                + hover_label
                                + " · "
                                + subj
                                + "</extra>"
                            ),
                            visible=False,
                        )
                    )
                    itir_split_idx.append(itir_trace_count)
                    itir_trace_count += 1

        init_y_range = _robust_y_range(
            init_y_vals, pct=_TIMING_Y_CLIP_PCT, lower_bound=0
        )
        wait_delta_y_range = _robust_y_range(wait_delta_y_vals, pct=_TIMING_Y_CLIP_PCT)
        wait_floor_y_range = _robust_y_range(
            wait_floor_y_vals, pct=_TIMING_Y_CLIP_PCT, lower_bound=0
        )
        response_line_y_range = _robust_y_range(
            response_line_y_vals, pct=_TIMING_Y_CLIP_PCT, lower_bound=0
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
                title=dict(text="ew rate", font=dict(color="silver")),
                overlaying="y",
                side="right",
                range=[0, 1],
                showgrid=False,
                zeroline=False,
                tickfont=dict(color="silver"),
            ),
        )
        fig_sp.add_hline(y=0.5, **_ref_line)  # Ref Line (Updated style)

        # Row 2
        _layout(
            fig_il,
            title="Initiation Times",
            xaxis_title="trial number",
            yaxis_title="time (s)",
            yaxis_range=init_y_range,
        )

        if multi:
            _layout(fig_ih, title="Initiation Dist", yaxis_title="time (s)")
        else:
            _layout(
                fig_ih,
                title="Initiation Dist",
                xaxis_title="time (s)",
                yaxis_title="density",
            )

        # Row 3
        _layout(
            fig_wdl,
            title="Center Dwell (Post-Go)",
            xaxis_title="trial number",
            yaxis_title="time (s)",
            yaxis_range=wait_delta_y_range,
        )
        _apply_split_toggle(
            fig_wdl, wdl_combined_idx, wdl_split_idx, wdl_trace_count, "Choice"
        )
        if multi:
            _layout(
                fig_wdh,
                title="Center Dwell Dist",
                yaxis_title="time (s)",
                boxmode="group",
            )
        else:
            _layout(
                fig_wdh,
                title="Center Dwell Dist",
                xaxis_title="time (s)",
                yaxis_title="density",
            )
        _apply_split_toggle(
            fig_wdh, wdh_combined_idx, wdh_split_idx, wdh_trace_count, "Choice"
        )
        _layout(
            fig_wfl,
            title="Minimum Wait (Floor)",
            xaxis_title="trial number",
            yaxis_title="time (s)",
            yaxis_range=wait_floor_y_range,
        )
        _apply_split_toggle(
            fig_wfl, wfl_combined_idx, wfl_split_idx, wfl_trace_count, "Choice"
        )
        if multi:
            _layout(
                fig_wfh,
                title="Minimum Wait Dist",
                yaxis_title="time (s)",
                boxmode="group",
            )
        else:
            _layout(
                fig_wfh,
                title="Minimum Wait Dist",
                xaxis_title="time (s)",
                yaxis_title="density",
            )
        _apply_split_toggle(
            fig_wfh, wfh_combined_idx, wfh_split_idx, wfh_trace_count, "Choice"
        )

        # Row 4
        _layout(
            fig_rtl,
            title="Response Time Rolling",
            xaxis_title="trial number",
            yaxis_title="time (s)",
            yaxis_range=response_line_y_range,
        )
        _apply_split_toggle(
            fig_rtl, rtl_combined_idx, rtl_split_idx, rtl_trace_count, "Choice"
        )
        _apply_split_toggle(
            fig_rt, rt_combined_idx, rt_split_idx, rt_trace_count, "Choice"
        )
        if multi_col:
            _layout(
                fig_rt,
                title="Response Time Dist",
                xaxis_title="subject",
                yaxis_title="time (s)",
                boxmode="group",
            )
        else:
            _layout(
                fig_rt,
                title="Response Time Dist",
                xaxis_title="time (s)",
                yaxis_title="density",
            )
        if multi_col:
            _layout(
                fig_itid,
                title="ITI Dist",
                yaxis_title="time (s)",
                boxmode="group",
            )
        else:
            _layout(
                fig_itid,
                title="ITI Dist",
                xaxis_title="time (s)",
                yaxis_title="density",
            )
        _apply_split_toggle(
            fig_itid, itid_combined_idx, itid_split_idx, itid_trace_count, "Outcome"
        )
        _layout(
            fig_tct,
            title="Rolling Trial Counts",
            xaxis_title="trial number",
            yaxis_title="trials in last 5 min",
        )
        _layout(
            fig_wc,
            title="Cumulative Rewarded Water (µL)",
            xaxis_title="trial number",
            yaxis_title="water (µL)",
        )
        _apply_split_toggle(
            fig_wc, wc_combined_idx, wc_split_idx, wc_trace_count, "Side"
        )
        _layout(
            fig_itir,
            title="ITI Rolling Trend<br><sup>25-trial median</sup>",
            xaxis_title="trial number",
            yaxis_title="time (s)",
        )
        _apply_split_toggle(
            fig_itir, itir_combined_idx, itir_split_idx, itir_trace_count, "Outcome"
        )

        _perf_log("_update_single", start, subjects=len(valid_subjects), multi=multi)
        return (
            fig_fc,
            fig_pr,
            fig_ch,
            fig_sp,
            fig_il,
            fig_ih,
            fig_wdl,
            fig_wdh,
            fig_wfl,
            fig_wfh,
            fig_rtl,
            fig_rt,
            fig_itid,
            fig_tct,
            fig_wc,
            fig_itir,
        )

    @app.callback(
        Output("session-settings-box", "children"),
        Input("subjects-recent", "value"),
        Input("subjects-older", "value"),
        Input("session-time", "value"),
        Input("auto-refresh", "n_intervals"),
        State("session-date", "date"),
    )
    def _update_overview_boxes(
        subjects_recent, subjects_older, session_name, n_intervals, session_date
    ):
        """Populate overview settings box with compact session and water details."""
        subjects = (subjects_recent or []) + (subjects_older or [])
        sessions_by_subject = {s: get_sessions(s) for s in subjects}
        valid_subjects = [s for s in subjects if sessions_by_subject.get(s)]

        if not valid_subjects:
            return "Select subject(s) to show settings."

        settings_lines: list[str] = []
        for i, subj in enumerate(valid_subjects):
            sessions_list = sessions_by_subject[subj]
            if i == 0 and session_name:
                ses = session_name
            elif session_date:
                ses = _sessions_on_date(sessions_list, session_date)
            else:
                ses = sessions_list[-1] if sessions_list else None
            if not ses:
                continue

            sm = session_metrics(subj, ses)
            if not sm:
                continue

            subj_settings = sm.get("session_settings_lines", [])
            if subj_settings:
                settings_lines.append(f"{subj} ({ses})")
                settings_lines.extend(f"  {line}" for line in subj_settings)

            water_totals = sm.get("water_side_totals_ul", [])
            if len(water_totals) >= 2:
                left = float(water_totals[0])
                right = float(water_totals[1])
                total = (
                    float(water_totals[2]) if len(water_totals) > 2 else left + right
                )
                settings_lines.append(
                    f"  water (µL): total {total:.1f} | L {left:.1f} | R {right:.1f}"
                )

        if not settings_lines:
            return "Settings unavailable for current selection."
        return "\n".join(settings_lines)

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
        Output("training-time", "figure"),
        Input("subjects-recent", "value"),
        Input("subjects-older", "value"),
        Input("sessions-back", "value"),
        Input("session-date", "date"),  # Replaces session-time for alignment anchor
        Input("smooth-metrics", "value"),
        Input("smooth-window", "value"),
        Input("auto-refresh", "n_intervals"),
    )
    def _update_multi(
        subjects_recent,
        subjects_older,
        sessions_back,
        session_date,
        smooth_vals,
        smooth_window,
        n_intervals,
    ):
        """Render all multi-session trend figures for selected subjects.

        Callback Inputs:
            - ``subjects-recent.value``
            - ``subjects-older.value``
            - ``sessions-back.value``
            - ``session-date.date``
            - ``smooth-metrics.value``
            - ``smooth-window.value``
            - ``auto-refresh.n_intervals``

        Callback Outputs:
            Nine figures for performance, EW rate, bias, medians, trial counts,
            water earned, and training time.

        Args:
            subjects_recent: Selected recent subject names.
            subjects_older: Selected older subject names.
            sessions_back: Number of recent sessions to include.
            session_date: Shared anchor date used to align subject timelines.
            smooth_vals: Smoothing toggle values from checklist.
            smooth_window: Moving-average window size when smoothing is enabled.
            n_intervals: Auto-refresh tick counter (unused except as trigger).
        Returns:
            A 9-item tuple of Plotly figures in callback output order.

        Side Effects:
            Reads cached multi-session metrics and emits performance logs when
            profiling is enabled.
        """
        start = time.perf_counter()
        n = 9
        subjects = (subjects_recent or []) + (subjects_older or [])

        if not subjects:
            e = _empty_fig()
            _perf_log("_update_multi", start, subjects=0)
            return tuple(e for _ in range(n))

        do_smooth = "smooth" in (smooth_vals or [])
        win = smooth_window or 3

        fig_perf, fig_ew, fig_sb = go.Figure(), go.Figure(), go.Figure()
        fig_it, fig_mrt, fig_mwt = go.Figure(), go.Figure(), go.Figure()
        fig_tc, fig_wa, fig_tt = go.Figure(), go.Figure(), go.Figure()

        for i, subj in enumerate(subjects):
            c = COLORS[i % len(COLORS)]
            grp = subj

            # Anchor Handling:
            # - We use 'session_date' (YYYY-MM-DD string) as the upper-date filter
            #   for EVERY subject.
            # - Each series still plots the true session datetime on the x-axis so
            #   multiple sessions from one day remain visually distinct.
            # - If date is None (startup), session_date usually defaults to latest,
            #   but we handle None.

            ms = multisession_metrics(
                subj,
                sessions_back,
                start_date=session_date,  # Passing date string directly
                smooth=do_smooth,
                smooth_window=win,
            )
            if not ms:
                continue
            session_dates = ms.get("session_dates", [])
            ht = "%{y:.2f}<br>session date: %{customdata}<extra>" + subj + "</extra>"
            mk = dict(color=c, size=7)
            ln = dict(color=c, width=2)

            fig_perf.add_trace(
                go.Scatter(
                    x=ms["x"],
                    customdata=session_dates,
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
                    customdata=session_dates,
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
                    customdata=session_dates,
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
                    customdata=session_dates,
                    y=ms["median_init"],
                    mode="lines+markers",
                    name=subj,
                    legendgroup=grp,
                    showlegend=False,
                    marker=mk,
                    line=dict(color=c),
                    hovertemplate="%{y:.3f}s<br>session date: %{customdata}<extra>"
                    + subj
                    + "</extra>",
                )
            )
            fig_mrt.add_trace(
                go.Scatter(
                    x=ms["x"],
                    customdata=session_dates,
                    y=ms["median_rt"],
                    mode="lines+markers",
                    name=subj,
                    legendgroup=grp,
                    showlegend=False,
                    marker=mk,
                    line=dict(color=c),
                    hovertemplate="%{y:.3f}s<br>session date: %{customdata}<extra>"
                    + subj
                    + "</extra>",
                )
            )
            fig_mwt.add_trace(
                go.Scatter(
                    x=ms["x"],
                    customdata=session_dates,
                    y=ms["median_wait"],
                    mode="lines+markers",
                    name=subj,
                    legendgroup=grp,
                    showlegend=False,
                    marker=mk,
                    line=dict(color=c),
                    hovertemplate="%{y:.3f}s<br>session date: %{customdata}<extra>"
                    + subj
                    + "</extra>",
                )
            )
            fig_tc.add_trace(
                go.Scatter(
                    x=ms["x"],
                    customdata=session_dates,
                    y=ms["n_with_choice"],
                    mode="lines+markers",
                    name=subj,
                    legendgroup=grp,
                    showlegend=False,
                    line=dict(color=c),
                    marker=mk,
                    hovertemplate="%{y}<br>session date: %{customdata}<extra>"
                    + subj
                    + "</extra>",
                )
            )
            fig_wa.add_trace(
                go.Scatter(
                    x=ms["x"],
                    customdata=session_dates,
                    y=ms["water"],
                    mode="lines+markers",
                    name=subj,
                    legendgroup=grp,
                    showlegend=False,
                    marker=mk,
                    line=dict(color=c),
                    hovertemplate="%{y:.2f} mL<br>session date: %{customdata}<extra>"
                    + subj
                    + "</extra>",
                )
            )
            training_time_hours = ms.get("training_time_hours", [])
            training_time_labels = [
                _clock_label(float(val)) if val is not None else "unknown"
                for val in training_time_hours
            ]
            fig_tt.add_trace(
                go.Scatter(
                    x=ms["x"],
                    customdata=session_dates,
                    text=training_time_labels,
                    y=training_time_hours,
                    mode="lines+markers",
                    name=subj,
                    legendgroup=grp,
                    showlegend=False,
                    marker=mk,
                    line=dict(color=c),
                    hovertemplate="session date: %{customdata}<br>"
                    + "training time: %{text}<extra>"
                    + subj
                    + "</extra>",
                )
            )

        _ref_line = dict(line_dash="dash", line_color="grey", line_width=1)

        _ms = dict(type="date", showgrid=False, zeroline=False)
        _layout(
            fig_perf,
            title="Performance (easy)",
            xaxis_title="session datetime",
            yaxis_title="performance",
            yaxis_range=[0.3, 1],
            xaxis=_ms,
        )
        fig_perf.add_hline(y=0.5, **_ref_line)

        _layout(
            fig_ew,
            title="E.W. Rate",
            xaxis_title="session datetime",
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
            xaxis_title="session datetime",
            yaxis_title="bias (R - L)",
            yaxis_range=[-0.6, 0.6],
            xaxis=_ms,
        )
        fig_sb.add_hline(y=0.0, **_ref_line)

        _layout(
            fig_it,
            title="Median Initiation Time",
            xaxis_title="session datetime",
            yaxis_title="time (s)",
            xaxis=_ms,
        )
        _layout(
            fig_mrt,
            title="Median Response Time",
            xaxis_title="session datetime",
            yaxis_title="time (s)",
            xaxis=_ms,
        )
        _layout(
            fig_mwt,
            title="Median Wait Time",
            xaxis_title="session datetime",
            yaxis_title="time (s)",
            xaxis=_ms,
        )
        _layout(
            fig_tc,
            title="Trials with Choice",
            xaxis_title="session datetime",
            yaxis_title="trials",
            xaxis=_ms,
        )
        _layout(
            fig_wa,
            title="Water Earned",
            xaxis_title="session datetime",
            yaxis_title="volume (mL)",
            xaxis=_ms,
        )
        _layout(
            fig_tt,
            title="Training Time",
            xaxis_title="session datetime",
            yaxis_title="time of day",
            xaxis=_ms,
            yaxis=dict(
                range=[24, 0],
                tickmode="array",
                tickvals=list(range(0, 25, 3)),
                ticktext=[f"{hour:02d}:00" for hour in range(0, 25, 3)],
            ),
        )

        _perf_log(
            "_update_multi",
            start,
            subjects=len(subjects),
            sessions_back=sessions_back,
            smooth=do_smooth,
            smooth_window=win,
        )
        return (
            fig_perf,
            fig_ew,
            fig_sb,
            fig_it,
            fig_mrt,
            fig_mwt,
            fig_tc,
            fig_wa,
            fig_tt,
        )

    return app
