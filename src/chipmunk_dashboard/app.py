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
    # Default layout settings
    config = dict(
        margin=_MARGIN,
        legend=_LEGEND,
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
            font=dict(family="Space Grotesk, sans-serif", size=14, color=_THEME["text"]),
        )

    # Update defaults with provided kwargs
    config.update(kw)
    fig.update_layout(**config)


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
                    id="subjects", options=subjects, value=[],
                    style={"display": "flex", "flexDirection": "column", "gap": "2px"},
                    inputStyle={"marginRight": "6px", "transform": "scale(1.2)"},
                    labelStyle={"fontSize": "16px", "cursor": "pointer"},
                ),
                style={
                    "height": "40vh",
                    "overflowY": "auto",
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
            "display": "flex",
            "flexDirection": "column",
        },
    )

    # -- content sections -----------------------------------------------------
    single_section = html.Div([
        html.H3("Single Session", style={"margin": "24px 0 12px", "borderBottom": "1px solid #ddd"}),
        
        # Row 1: Performance / Outcomes
        _row("frac-correct", "p-right", "chrono", "session-perf"),
        
        # Row 2: Initiation
        _row("init-line", "init-hist"),
        
        # Row 3: Wait (Delta)
        _row("wait-delta-line", "wait-delta-hist"),
        
        # Row 4: Reaction
        _row("react-line", "react-hist"),
    ])

    multi_section = html.Div([
        html.H3("Multi Session", style={"margin": "24px 0 12px", "borderBottom": "1px solid #ddd"}),
        _row("performance", "ew-rate", "side-bias", "trial-counts"),
        _row("init-times", "median-wait", "median-rt", "water"),
    ])

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
                style={"display": "flex", "height": "calc(100vh - 56px)", "overflow": "hidden"},
            ),
        ],
        style={
            "fontFamily": "IBM Plex Sans, sans-serif",
            "padding": "12px",
            "background": _THEME["bg"],
            "color": _THEME["text"],
            "height": "100vh",
            "overflow": "hidden"
        },
    )

    # -- callbacks ------------------------------------------------------------
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
        Output("session-perf", "figure"),
        Output("init-line", "figure"),
        Output("init-hist", "figure"),
        Output("wait-delta-line", "figure"),
        Output("wait-delta-hist", "figure"),
        Output("react-line", "figure"),
        Output("react-hist", "figure"),
        Input("subjects", "value"),
        Input("session", "value"),
    )
    def _update_single(subjects, session):
        n = 10
        if isinstance(subjects, str):
            subjects = [subjects]
        if not subjects:
            e = _empty_fig()
            return tuple(e for _ in range(n))

        multi = len(subjects) > 1
        
        # Initialize figures
        fig_fc, fig_pr, fig_ch, fig_sp = go.Figure(), go.Figure(), go.Figure(), go.Figure()
        fig_il, fig_ih = go.Figure(), go.Figure()
        fig_wdl, fig_wdh = go.Figure(), go.Figure()
        fig_rl, fig_rh = go.Figure(), go.Figure()

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
            
            ht_subj = "<extra>" + subj + "</extra>"

            # --- Row 1: Outcomes & Performance ---
            
            # Trial Outcomes (Grouped Bars)
            # Create unique legend groups per subject so we can toggle them
            # We use different colors/opacities or slight tint shifts if possible,
            # but standard plotly grouped bars work by x-axis (category).
            # Here X is intensity. We want grouped by Subject within Intensity.
            # To do this cleanly, we add traces for each outcome type.
            
            outcome_types = [
                ("correct", sm["n_correct"], "mediumseagreen"),
                ("incorrect", sm["n_incorrect"], "tomato"),
                ("ew", sm["n_ew"], "silver"), # Gray
                ("no choice", sm["n_no_choice"], "#333333"), # Dark gray/black
            ]
            
            for outcome_name, yvals, base_color in outcome_types:
                # To distinguish subjects in the stack/group, we rely on the legend.
                # But grouped bars with stacks is complex. 
                # Request: "grouped bar chart where you have different shades of green"
                # Since 'stims' is X, and we have multiple outcomes AND multiple subjects.
                # Simple approach: Standard Grouped Bar.
                # We will just append traces. Plotly handles grouping by X automatically.
                # To differentiate subjects, we can use slightly different opacity or patterns,
                # OR just rely on hover/legend. 
                # Let's keep it simple: One trace per outcome per subject.
                
                # We need to make sure colors are distinct enough if we want "shades".
                # For now, let's use the base color but maybe vary opacity or just repeat
                # since the user asked for "different shades".
                # A simple way to get a "shade" is to mix the base color with the subject color, 
                # but that might be messy.
                # Let's try standard colors for outcomes, but add subject name to trace name.
                
                fig_fc.add_trace(go.Bar(
                    x=sm["stims"], y=yvals, 
                    name=f"{subj} - {outcome_name}",
                    legendgroup=subj, # Group toggle by subject
                    marker_color=base_color, 
                    opacity=1.0 if i==0 else 0.6, # Make secondary subjects lighter
                    hovertemplate="%{y} " + outcome_name + ht_subj,
                ))

            # P(Right)
            fig_pr.add_trace(go.Scatter(
                x=sm["stims"], y=sm["p_right"], mode="lines+markers",
                name=subj, showlegend=multi, legendgroup=grp,
                marker=dict(color=c, size=7),
                hovertemplate="%{y:.2f}" + ht_subj,
            ))

            # Chronometric
            fig_ch.add_trace(go.Scatter(
                x=sm["stims"], y=sm["median_rt"], mode="lines+markers",
                name=subj, showlegend=False, legendgroup=grp,
                marker=dict(color=c, size=7), line=dict(color=c, width=2),
                hovertemplate="%{y:.3f}s" + ht_subj,
            ))

            # Within-session performance
            if sm["slide_x"]:
                fig_sp.add_trace(go.Scatter(
                    x=sm["slide_x"], y=sm["slide_y"], mode="lines",
                    name=subj, showlegend=False, legendgroup=grp,
                    line=dict(color=c, width=2),
                    hovertemplate="%{y:.2f}" + ht_subj,
                ))

            # --- Row 2: Initiation ---
            
            if sm["init_trial_nums"]:
                # Line
                fig_il.add_trace(go.Scatter(
                    x=sm["init_trial_nums"], y=sm["init_times"],
                    mode="markers", name=subj, showlegend=False, legendgroup=grp,
                    marker=dict(color=c, size=3, opacity=0.4),
                    hovertemplate="%{y:.3f}s" + ht_subj,
                ))
                 # Rolling
                if sm["init_roll_x"]:
                    fig_il.add_trace(go.Scatter(
                        x=sm["init_roll_x"], y=sm["init_roll_y"],
                        mode="lines", name=subj + " roll", showlegend=False, legendgroup=grp,
                        line=dict(color=c, width=2),
                        hovertemplate="%{y:.3f}s (roll)" + ht_subj,
                    ))

                # Hist (Box if multi, Hist if single)
                if multi:
                    fig_ih.add_trace(go.Box(
                        y=sm["init_times"], name=subj, marker_color=c,
                        legendgroup=grp, showlegend=False, boxmean=True,
                    ))
                else:
                    fig_ih.add_trace(go.Histogram(
                        x=sm["init_times"], nbinsx=30, name=subj,
                        marker_color=c, showlegend=False, opacity=0.8,
                    ))

            # --- Row 3: Wait Delta ---

            if sm["wait_delta_times"]:
                 # Line (Delta vs trial num)
                fig_wdl.add_trace(go.Scatter(
                     x=sm["wait_trial_nums"], y=sm["wait_delta_times"],
                     mode="markers", name=subj, showlegend=False, legendgroup=grp,
                     marker=dict(color=c, size=3, opacity=0.4),
                     hovertemplate="%{y:.3f}s<extra>raw</extra>"
                ))
                # Rolling median line
                if sm["wait_delta_x"]:
                    fig_wdl.add_trace(go.Scatter(
                        x=sm["wait_delta_x"], y=sm["wait_delta_y"],
                        mode="lines", name=subj + " roll", showlegend=False, legendgroup=grp,
                        line=dict(color=c, width=2), 
                        hovertemplate="%{y:.3f}s<extra>rolling</extra>",
                    ))
                
                # Hist (Box if multi)
                if multi:
                    fig_wdh.add_trace(go.Box(
                        y=sm["wait_delta_times"], name=subj, marker_color=c,
                        legendgroup=grp, showlegend=False, boxmean=True
                    ))
                else:
                    fig_wdh.add_trace(go.Histogram(
                        x=sm["wait_delta_times"], nbinsx=30, name=subj,
                        marker_color=c, showlegend=False, opacity=0.8,
                    ))

            # --- Row 4: Reaction Time ---
            
            # Line (RT vs trial)
            if sm["rt_trial_nums"]:
                fig_rl.add_trace(go.Scatter(
                    x=sm["rt_trial_nums"], y=sm["rt_vals"],
                    mode="markers", name=subj, showlegend=False, legendgroup=grp,
                    marker=dict(color=c, size=3, opacity=0.4),
                    hovertemplate="%{y:.3f}s" + ht_subj,
                ))
                # Rolling
                if sm["rt_roll_x"]:
                    fig_rl.add_trace(go.Scatter(
                        x=sm["rt_roll_x"], y=sm["rt_roll_y"],
                        mode="lines", name=subj + " roll", showlegend=False, legendgroup=grp,
                        line=dict(color=c, width=2),
                        hovertemplate="%{y:.3f}s (roll)" + ht_subj,
                    ))

            # Histogram / Box
            if multi:
                fig_rh.add_trace(go.Box(
                    y=sm["rts"], name=subj, marker_color=c,
                    legendgroup=grp, showlegend=False, boxmean=True,
                ))
            else:
                 fig_rh.add_trace(go.Histogram(
                    x=sm["rts"], nbinsx=30, name=subj, marker_color=c,
                    legendgroup=grp, showlegend=False, opacity=0.8,
                ))

        # --- Layouts ---
        
        # Consistent Reference Lines
        _ref_line = dict(line_dash="dash", line_color="grey", line_width=1)
        
        # Row 1
        _layout(fig_fc, title="Trial Outcomes", xaxis_title="stim intensity",
                yaxis_title="count", barmode="group") # Was stack
        
        _layout(fig_pr, title="P(Right)", xaxis_title="stim intensity",
                yaxis_title="p(right)", yaxis_range=[0, 1])
        fig_pr.add_hline(y=0.5, **_ref_line) # Ref Line
        
        _layout(fig_ch, title="Chronometric Curve", xaxis_title="stim intensity",
                yaxis_title="median RT (s)")
        
        _layout(fig_sp, title="Performance (Rolling 20)", xaxis_title="trial number",
                yaxis_title="accuracy", yaxis_range=[0, 1])
        fig_sp.add_hline(y=0.5, **_ref_line) # Ref Line (Updated style)

        # Row 2
        _layout(fig_il, title="Initiation Times", xaxis_title="trial number", 
                yaxis_title="time (s)")
        if multi:
             _layout(fig_ih, title="Initiation Dist.", yaxis_title="time (s)")
        else:
            _layout(fig_ih, title="Initiation Dist.", xaxis_title="time (s)", yaxis_title="count")

        # Row 3
        _layout(fig_wdl, title="Wait Delta (Actual - Min)", xaxis_title="trial number",
            yaxis_title="delta (s)")
        if multi:
             _layout(fig_wdh, title="Wait Delta Dist.", yaxis_title="delta (s)")
        else:
            _layout(fig_wdh, title="Wait Delta Dist.", xaxis_title="delta (s)", yaxis_title="count")

        # Row 4
        _layout(fig_rl, title="Reaction Times", xaxis_title="trial number", yaxis_title="time (s)")
        if multi:
            _layout(fig_rh, title="Reaction Time Dist.", yaxis_title="RT (s)")
        else:
            _layout(fig_rh, title="Reaction Time Dist.", xaxis_title="RT (s)", yaxis_title="count")

        return fig_fc, fig_pr, fig_ch, fig_sp, fig_il, fig_ih, fig_wdl, fig_wdh, fig_rl, fig_rh

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
        Input("session", "value"),
    )
    def _update_multi(subjects, sessions_back, session_val):
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
            
            # Determine logic for anchor session.
            # If a single subject is selected, the 'session_val' dropdown is valid for them.
            # If multiple subjects are selected, 'session_val' only corresponds to the first subject (as per UI label).
            # For simplicity:
            # - If i==0 (first subject), use session_val.
            # - If i>0, we default to None (latest), because we don't have a UI to select sessions for other subjects.
            # Exception: if all subjects share session names (e.g. dates), we could try applying it, but safer to default to latest.
            anchor = session_val if i == 0 else None
            
            ms = multisession_metrics(subj, sessions_back, anchor_session_name=anchor)
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

        _ref_line = dict(line_dash="dash", line_color="grey", line_width=1)
        
        _ms = dict(dtick=1, showgrid=False, zeroline=False)
        _layout(fig_perf, title="Performance (easy)", xaxis_title="sessions back",
                yaxis_title="performance", yaxis_range=[0.3, 1], xaxis=_ms)
        fig_perf.add_hline(y=0.5, **_ref_line)
        
        _layout(fig_ew, title="E.W. Rate", xaxis_title="sessions back",
                yaxis_title="e.w. rate", yaxis_range=[0, 1], xaxis=_ms)
        fig_ew.add_hline(y=0.5, line_dash="dash", line_color="black") # Keep black for EW? Spec said "make these new lines ... also make existing lines follow this style". Let's standardize ALL to grey dash.
        # Overriding EW line to match new style
        fig_ew.update_yaxes(range=[0,1]) # Reset if needed, but fig var is ok.
        # Actually, let's just add the grey line and remove the black one if it was added before.
        # Since I'm rebuilding the figure, I just add the new one.
        fig_ew.layout.shapes = [] # Clear existing
        fig_ew.add_hline(y=0.5, **_ref_line)

        _layout(fig_sb, title="Side Bias", xaxis_title="sessions back",
                yaxis_title="p(right choice)", yaxis_range=[0, 1], xaxis=_ms)
        fig_sb.add_hline(y=0.5, **_ref_line)
        
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
