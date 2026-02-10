"""Dash application — layout and callbacks."""

from dash import Dash, dcc, html, Input, Output
import plotly.graph_objects as go
import plotly.express as px
from .data import get_all_subjects, get_sessions, session_metrics, multisession_metrics

COLORS = px.colors.qualitative.Plotly
_MARGIN = dict(l=50, r=20, t=42, b=40)
_CLEAN = dict(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
_AXIS_CLEAN = dict(showgrid=False, zeroline=False, tickfont=dict(color="#56606b"))
_LEGEND = dict(
    orientation="h",
    yanchor="top",
    y=-0.22,
    xanchor="center",
    x=0.5,
    font=dict(size=10, color="#56606b"),
    tracegroupgap=5,
)
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
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        annotations=[dict(text=msg, showarrow=False, font=dict(size=14))],
        margin=_MARGIN, **_CLEAN,
    )
    return fig


def _layout(fig: go.Figure, **kw) -> None:
    fig.update_layout(
        margin=_MARGIN, legend=_LEGEND, hovermode="x unified",
        font=dict(family="IBM Plex Sans, sans-serif", color=_THEME["text"], size=12),
        title=dict(
            font=dict(family="Space Grotesk, sans-serif", size=14, color=_THEME["text"])
        ),
        xaxis=_AXIS_CLEAN, yaxis=_AXIS_CLEAN, **_CLEAN, **kw,
    )


def create_app() -> Dash:
    subjects = get_all_subjects()
    app = Dash(
        __name__,
        suppress_callback_exceptions=True,
        external_stylesheets=[
            "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap"
        ],
    )

    # -- helpers --------------------------------------------------------------
    def _graph(gid: str) -> dcc.Graph:
        return html.Div(
            dcc.Graph(
                id=gid,
                style={"height": "100%"},
                config={"displayModeBar": False},
            ),
            style={
                "flex": "1 1 0",
                "minWidth": "0",
                "maxWidth": _MAX_W,
                "background": _THEME["card"],
                "border": f"1px solid {_THEME['border']}",
                "borderRadius": "10px",
                "boxShadow": "0 6px 18px rgba(16, 24, 40, 0.06)",
                "padding": "6px",
            },
        )

    def _row(*ids: str) -> html.Div:
        return html.Div(
            [_graph(i) for i in ids],
            style={
                "display": "flex",
                "gap": "12px",
                "height": _PLOT_H,
                "justifyContent": "center",
            },
        )

    # -- sidebar --------------------------------------------------------------
    sidebar = html.Div(
        [
            html.Label("Subjects", style={"fontWeight": "bold"}),
            html.Div(
                dcc.Checklist(
                    id="subjects", options=subjects, value=[],
                    style={"display": "flex", "flexDirection": "column", "gap": "2px"},
                    inputStyle={"marginRight": "6px"},
                    labelStyle={"fontSize": "13px", "cursor": "pointer"},
                ),
                style={
                    "maxHeight": "180px", "overflowY": "auto",
                    "border": "1px solid #ccc", "borderRadius": "4px",
                    "padding": "6px", "marginTop": "4px",
                },
            ),
            html.Br(),
            html.Label("Session (first subject)", style={"fontWeight": "bold"}),
            dcc.Dropdown(id="session", placeholder="(latest)"),
            html.Br(),
            html.Label("Sessions back", style={"fontWeight": "bold"}),
            dcc.Slider(
                id="sessions-back", min=1, max=30, step=1, value=10,
                marks={i: str(i) for i in [1, 5, 10, 15, 20, 25, 30]},
            ),
        ],
        style={
            "width": "240px",
            "padding": "16px",
            "borderRight": f"1px solid {_THEME['border']}",
            "background": _THEME["panel"],
            "flexShrink": 0,
        },
    )

    # -- tab contents (both always in DOM) ------------------------------------
    single_content = html.Div(
        id="single-content",
        children=[
            _row("frac-correct", "p-right"),
            _row("chrono", "react-times"),
            _row("init-hist", "wait-hist"),
            _row("wait-line", "wait-delta-hist"),
            _row("session-perf"),
        ],
        style={"overflowY": "auto", "flex": 1, "padding": "12px 8px"},
    )
    multi_content = html.Div(
        id="multi-content",
        children=[
            _row("performance", "ew-rate"),
            _row("side-bias", "init-times"),
            _row("median-rt", "median-wait"),
            _row("trial-counts", "water"),
        ],
        style={"overflowY": "auto", "flex": 1, "padding": "12px 8px", "display": "none"},
    )

    _tab_base = {
        "padding": "12px 26px",
        "fontSize": "14px",
        "fontWeight": "bold",
        "cursor": "pointer",
        "borderBottom": "3px solid transparent",
        "background": _THEME["panel"],
        "color": _THEME["muted"],
    }
    _tab_sel = {
        **_tab_base,
        "borderBottom": f"3px solid {_THEME['accent']}",
        "background": _THEME["card"],
        "color": _THEME["accent"],
    }

    tabs = dcc.Tabs(
        id="tabs", value="single",
        children=[
            dcc.Tab(label="Single Session", value="single",
                    style=_tab_base, selected_style=_tab_sel),
            dcc.Tab(label="Multi Session", value="multi",
                    style=_tab_base, selected_style=_tab_sel),
        ],
        style={"borderBottom": f"2px solid {_THEME['border']}", "marginBottom": "6px"},
    )

    main_area = html.Div(
        [tabs, single_content, multi_content],
        style={
            "flex": 1,
            "display": "flex",
            "flexDirection": "column",
            "overflow": "hidden",
            "background": _THEME["bg"],
        },
    )

    app.layout = html.Div(
        [
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
                style={"display": "flex", "height": "calc(100vh - 56px)"},
            ),
        ],
        style={
            "fontFamily": "IBM Plex Sans, sans-serif",
            "padding": "12px",
            "background": _THEME["bg"],
            "color": _THEME["text"],
        },
    )

    # -- callbacks ------------------------------------------------------------
    # Tab visibility toggle
    @app.callback(
        Output("single-content", "style"),
        Output("multi-content", "style"),
        Input("tabs", "value"),
    )
    def _toggle_tabs(tab):
        show = {"overflowY": "auto", "flex": 1, "padding": "4px 0"}
        hide = {**show, "display": "none"}
        if tab == "single":
            return show, hide
        return hide, show

    # Session dropdown
    @app.callback(
        Output("session", "options"),
        Output("session", "value"),
        Input("subjects", "value"),
    )
    def _update_sessions(subjects):
        if not subjects:
            return [], None
        sessions = get_sessions(subjects[0])
        opts = [{"label": s, "value": s} for s in sessions]
        return opts, sessions[-1] if sessions else None

    # ── Single-session plots ─────────────────────────────────────────────────
    @app.callback(
        Output("frac-correct", "figure"),
        Output("p-right", "figure"),
        Output("chrono", "figure"),
        Output("react-times", "figure"),
        Output("init-hist", "figure"),
        Output("wait-hist", "figure"),
        Output("wait-line", "figure"),
        Output("wait-delta-hist", "figure"),
        Output("session-perf", "figure"),
        Input("subjects", "value"),
        Input("session", "value"),
    )
    def _update_single(subjects, session):
        n = 9
        if isinstance(subjects, str):
            subjects = [subjects]
        if not subjects:
            e = _empty_fig()
            return tuple(e for _ in range(n))

        multi = len(subjects) > 1
        fig_fc, fig_pr, fig_ch = go.Figure(), go.Figure(), go.Figure()
        fig_rt, fig_ih, fig_wh = go.Figure(), go.Figure(), go.Figure()
        fig_wl, fig_wdh = go.Figure(), go.Figure()
        fig_sp = go.Figure()

        for i, subj in enumerate(subjects):
            c = COLORS[i % len(COLORS)]
            grp = subj
            sessions_list = get_sessions(subj)
            ses = session if i == 0 and session else (sessions_list[-1] if sessions_list else None)
            if not ses:
                continue
            sm = session_metrics(subj, ses)
            if not sm:
                continue

            # Trial Outcomes — first subject only
            if i == 0:
                for yvals, name, color, lg in [
                    (sm["n_correct"], "correct", "mediumseagreen", "correct"),
                    (sm["n_incorrect"], "incorrect", "tomato", "incorrect"),
                    (sm["n_ew"], "early withdrawal", "darkgrey", "ew"),
                    (sm["n_no_choice"], "no choice", "black", "nochoice"),
                ]:
                    fig_fc.add_trace(go.Bar(
                        x=sm["stims"], y=yvals, name=name,
                        marker_color=color, legendgroup=lg,
                        hovertemplate="%{y}<extra>" + name + "</extra>",
                    ))

            # P(Right)
            fig_pr.add_trace(go.Scatter(
                x=sm["stims"], y=sm["p_right"], mode="lines+markers",
                name=subj, showlegend=multi, legendgroup=grp,
                marker=dict(color=c, size=7),
                hovertemplate="%{y:.2f}<extra>" + subj + "</extra>",
            ))

            # Chronometric — first subject only
            if i == 0:
                fig_ch.add_trace(go.Scatter(
                    x=sm["stims"], y=sm["median_rt"], mode="lines+markers",
                    name=subj, legendgroup=grp, showlegend=False,
                    marker=dict(color=c, size=7), line=dict(color=c, width=2),
                    hovertemplate="%{y:.3f}s<extra>" + subj + "</extra>",
                ))

            # Reaction Times
            if multi:
                fig_rt.add_trace(go.Box(
                    y=sm["rts"], name=subj, marker_color=c,
                    legendgroup=grp, showlegend=False, boxmean=True,
                ))
            else:
                fig_rt.add_trace(go.Histogram(
                    x=sm["rts"], nbinsx=20, name=subj, marker_color=c,
                    legendgroup=grp, showlegend=False, opacity=0.8,
                ))

            # Initiation Time histogram — first subject only
            if i == 0 and sm["init_times"]:
                fig_ih.add_trace(go.Histogram(
                    x=sm["init_times"], nbinsx=25, name=subj,
                    marker_color=c, showlegend=False, opacity=0.8,
                ))

            # Wait Time histogram — first subject only
            if i == 0 and sm["wait_times"]:
                fig_wh.add_trace(go.Histogram(
                    x=sm["wait_times"], nbinsx=25, name=subj,
                    marker_color=c, showlegend=False, opacity=0.8,
                ))

            # Wait time: actual vs min, with rolling delta — first subject only
            if i == 0 and sm["wait_trial_nums"]:
                fig_wl.add_trace(go.Scatter(
                    x=sm["wait_trial_nums"], y=sm["wait_times"],
                    mode="lines", name="actual wait",
                    line=dict(color=c, width=2), showlegend=True,
                    hovertemplate="%{y:.3f}s<extra>actual wait</extra>",
                ))
                fig_wl.add_trace(go.Scatter(
                    x=sm["wait_trial_nums"], y=sm["wait_min_times"],
                    mode="lines", name="min wait",
                    line=dict(color="black", width=1, dash="dash"),
                    showlegend=True,
                    hovertemplate="%{y:.3f}s<extra>min wait</extra>",
                ))
                if sm["wait_delta_x"]:
                    fig_wl.add_trace(go.Scatter(
                        x=sm["wait_delta_x"], y=sm["wait_delta_y"],
                        mode="lines", name="delta (rolling median)",
                        line=dict(color="gray", width=2), showlegend=True,
                        hovertemplate="%{y:.3f}s<extra>delta</extra>",
                    ))

            # Wait delta histogram — first subject only
            if i == 0 and sm["wait_delta_times"]:
                fig_wdh.add_trace(go.Histogram(
                    x=sm["wait_delta_times"], nbinsx=25, name=subj,
                    marker_color=c, showlegend=False, opacity=0.8,
                ))

            # Within-session performance — first subject only
            if i == 0 and sm["slide_x"]:
                fig_sp.add_trace(go.Scatter(
                    x=sm["slide_x"], y=sm["slide_y"], mode="lines",
                    name=subj, legendgroup=grp, showlegend=False,
                    line=dict(color=c, width=2),
                    hovertemplate="%{y:.2f}<extra>" + subj + "</extra>",
                ))

        _layout(fig_fc, title="Trial Outcomes", xaxis_title="stim intensity",
                yaxis_title="count", barmode="stack")
        _layout(fig_pr, title="P(Right)", xaxis_title="stim intensity",
                yaxis_title="p(right)", yaxis_range=[0, 1])
        _layout(fig_ch, title="Chronometric Curve", xaxis_title="stim intensity",
                yaxis_title="median RT (s)")
        if multi:
            _layout(fig_rt, title="Reaction Times", yaxis_title="RT (s)")
        else:
            _layout(fig_rt, title="Reaction Times", xaxis_title="RT (s)", yaxis_title="count")
        _layout(fig_ih, title="Initiation Times", xaxis_title="time (s)", yaxis_title="count")
        _layout(fig_wh, title="Wait Times", xaxis_title="time (s)", yaxis_title="count")
        _layout(fig_wl, title="Wait Time vs Min (Session)", xaxis_title="trial number",
            yaxis_title="time (s)")
        _layout(fig_wdh, title="Wait Delta (Actual - Min)", xaxis_title="time (s)",
            yaxis_title="count")
        _layout(fig_sp, title="Within-Session Performance", xaxis_title="trial number",
                yaxis_title="accuracy (20-trial window)", yaxis_range=[0, 1])
        fig_sp.add_hline(y=0.5, line_dash="dash", line_color="grey", line_width=1)

        return fig_fc, fig_pr, fig_ch, fig_rt, fig_ih, fig_wh, fig_wl, fig_wdh, fig_sp

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
        Input("tabs", "value"),
    )
    def _update_multi(subjects, sessions_back, _tab):
        n = 8
        if isinstance(subjects, str):
            subjects = [subjects]
        if not subjects:
            e = _empty_fig()
            return tuple(e for _ in range(n))

        fig_perf, fig_ew, fig_sb = go.Figure(), go.Figure(), go.Figure()
        fig_it, fig_mrt, fig_mwt = go.Figure(), go.Figure(), go.Figure()
        fig_tc, fig_wa = go.Figure(), go.Figure()

        for i, subj in enumerate(subjects):
            c = COLORS[i % len(COLORS)]
            grp = subj
            ms = multisession_metrics(subj, sessions_back)
            if not ms:
                continue
            ht = "%{y:.2f}<extra>" + subj + "</extra>"
            mk = dict(color=c, size=7)
            ln = dict(color=c, width=2)

            fig_perf.add_trace(go.Scatter(
                x=ms["x"], y=ms["perf_easy"], mode="lines+markers",
                name=subj, legendgroup=grp, showlegend=True,
                line=ln, marker=mk, hovertemplate=ht))
            fig_ew.add_trace(go.Scatter(
                x=ms["x"], y=ms["ew_rate"], mode="lines+markers",
                name=subj, legendgroup=grp, showlegend=False,
                marker=mk, line=dict(color=c), hovertemplate=ht))
            fig_sb.add_trace(go.Scatter(
                x=ms["x"], y=ms["side_bias"], mode="lines+markers",
                name=subj, legendgroup=grp, showlegend=False,
                marker=mk, line=dict(color=c), hovertemplate=ht))
            fig_it.add_trace(go.Scatter(
                x=ms["x"], y=ms["median_init"], mode="lines+markers",
                name=subj, legendgroup=grp, showlegend=False,
                marker=mk, line=dict(color=c),
                hovertemplate="%{y:.3f}s<extra>" + subj + "</extra>"))
            fig_mrt.add_trace(go.Scatter(
                x=ms["x"], y=ms["median_rt"], mode="lines+markers",
                name=subj, legendgroup=grp, showlegend=False,
                marker=mk, line=dict(color=c),
                hovertemplate="%{y:.3f}s<extra>" + subj + "</extra>"))
            fig_mwt.add_trace(go.Scatter(
                x=ms["x"], y=ms["median_wait"], mode="lines+markers",
                name=subj, legendgroup=grp, showlegend=False,
                marker=mk, line=dict(color=c),
                hovertemplate="%{y:.3f}s<extra>" + subj + "</extra>"))
            fig_tc.add_trace(go.Scatter(
                x=ms["x"], y=ms["n_with_choice"], mode="lines+markers",
                name=subj, legendgroup=grp, showlegend=False,
                line=dict(color=c), marker=mk,
                hovertemplate="%{y}<extra>" + subj + "</extra>"))
            fig_wa.add_trace(go.Scatter(
                x=ms["x"], y=ms["water"], mode="lines+markers",
                name=subj, legendgroup=grp, showlegend=False,
                marker=mk, line=dict(color=c),
                hovertemplate="%{y:.2f} mL<extra>" + subj + "</extra>"))

        _ms = dict(dtick=1, showgrid=False, zeroline=False)
        _layout(fig_perf, title="Performance (easy)", xaxis_title="sessions back",
                yaxis_title="performance", yaxis_range=[0.3, 1], xaxis=_ms)
        _layout(fig_ew, title="E.W. Rate", xaxis_title="sessions back",
                yaxis_title="e.w. rate", yaxis_range=[0, 1], xaxis=_ms)
        fig_ew.add_hline(y=0.5, line_dash="dash", line_color="black")
        _layout(fig_sb, title="Side Bias", xaxis_title="sessions back",
                yaxis_title="p(right choice)", yaxis_range=[0, 1], xaxis=_ms)
        fig_sb.add_hline(y=0.5, line_dash="dash", line_color="grey", line_width=1)
        _layout(fig_it, title="Median Initiation Time", xaxis_title="sessions back",
                yaxis_title="time (s)", xaxis=_ms)
        _layout(fig_mrt, title="Median Reaction Time", xaxis_title="sessions back",
                yaxis_title="time (s)", xaxis=_ms)
        _layout(fig_mwt, title="Median Wait Time", xaxis_title="sessions back",
                yaxis_title="time (s)", xaxis=_ms)
        _layout(fig_tc, title="Trials with Choice", xaxis_title="sessions back",
                yaxis_title="trials", xaxis=_ms)
        _layout(fig_wa, title="Water Earned", xaxis_title="sessions back",
                yaxis_title="volume (mL)", xaxis=_ms)

        return fig_perf, fig_ew, fig_sb, fig_it, fig_mrt, fig_mwt, fig_tc, fig_wa

    return app
