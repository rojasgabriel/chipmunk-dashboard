"""Integration tests using real third-party libraries.

Unlike test_app.py and test_data.py — which mock all third-party libs — these
tests import the actual installed versions of dash, plotly, pandas, and numpy.
They catch runtime breakage that mocked tests miss: removed trace types,
renamed kwargs, changed function signatures, and so on.

Only ``labdata`` and ``chipmunk`` are mocked (database access requires VPN).

Three layers:
  A. API surface  — verify every class, function, and kwarg the app uses exists.
  B. App creation — create_app() builds a real Dash layout with real components.
  C. Data processing — session_metrics / multisession_metrics run end-to-end
                       with real pandas/numpy and synthetic DataFrames.
"""

import importlib
import math
import sys
import types
import unittest
from unittest import mock

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dcc, html


# ---------------------------------------------------------------------------
# Module import helpers
# ---------------------------------------------------------------------------


def _fake_db_modules():
    """Return sys.modules patches for labdata and chipmunk (DB-only deps)."""
    fake_labdata = types.ModuleType("labdata")
    fake_labdata.__path__ = []
    fake_schema = types.ModuleType("labdata.schema")

    class _DecisionTask:
        class TrialSet:
            pass

    class _Watering:
        pass

    fake_schema.DecisionTask = _DecisionTask
    fake_schema.Watering = _Watering
    fake_labdata.schema = fake_schema

    fake_chipmunk = types.ModuleType("chipmunk")

    class _Chipmunk:
        class Trial:
            pass

        class TrialParameters:
            pass

    fake_chipmunk.Chipmunk = _Chipmunk

    return {
        "labdata": fake_labdata,
        "labdata.schema": fake_schema,
        "chipmunk": fake_chipmunk,
    }


def _import_data_with_real_libs():
    """Import chipmunk_dashboard.data with real pandas/numpy; only DB deps mocked."""
    sys.modules.pop("chipmunk_dashboard.data", None)
    with mock.patch.dict(sys.modules, _fake_db_modules()):
        module = importlib.import_module("chipmunk_dashboard.data")
    return module


def _import_app_with_real_libs():
    """Import chipmunk_dashboard.app with real dash/plotly/numpy; only DB deps mocked."""
    sys.modules.pop("chipmunk_dashboard.app", None)

    fake_data = types.ModuleType("chipmunk_dashboard.data")
    fake_data.get_all_subjects = mock.Mock(return_value=["subject-a"])
    fake_data.get_subjects_with_recent_sessions = mock.Mock(return_value=set())
    fake_data.get_sessions = mock.Mock(return_value=["20260101_010101"])
    fake_data.get_subjects_for_date = mock.Mock(return_value=[])
    fake_data.session_metrics = mock.Mock(return_value=None)
    fake_data.multisession_metrics = mock.Mock(return_value=None)
    fake_data.prewarm_multisession_cache = mock.Mock()

    patches = {**_fake_db_modules(), "chipmunk_dashboard.data": fake_data}
    with mock.patch.dict(sys.modules, patches):
        module = importlib.import_module("chipmunk_dashboard.app")
    return module


class _FakeDash:
    """Minimal Dash stub that captures callbacks by function name."""

    def __init__(self, *args, **kwargs):
        self.layout = None
        self.callbacks: dict = {}

    def callback(self, *cb_args, **cb_kwargs):
        def _deco(func):
            self.callbacks[func.__name__] = func
            return func

        return _deco


def _import_app_fake_dash_real_plotly():
    """Import app.py with fake Dash (callback access) + real plotly/numpy."""
    sys.modules.pop("chipmunk_dashboard.app", None)

    fake_dash_mod = types.ModuleType("dash")
    fake_dash_mod.Dash = _FakeDash
    fake_dash_mod.dcc = dcc
    fake_dash_mod.html = html
    fake_dash_mod.Input = Input
    fake_dash_mod.Output = Output
    fake_dash_mod.State = State
    fake_dash_mod.ctx = types.SimpleNamespace(triggered_id=None)

    fake_data = types.ModuleType("chipmunk_dashboard.data")
    fake_data.get_all_subjects = mock.Mock(return_value=["subject-a", "subject-b"])
    fake_data.get_subjects_with_recent_sessions = mock.Mock(return_value=set())
    fake_data.get_sessions = mock.Mock(return_value=["20260101_010101"])
    fake_data.get_subjects_for_date = mock.Mock(return_value=[])
    fake_data.session_metrics = mock.Mock(return_value=None)
    fake_data.multisession_metrics = mock.Mock(return_value=None)
    fake_data.prewarm_multisession_cache = mock.Mock()

    patches = {
        **_fake_db_modules(),
        "dash": fake_dash_mod,
        "chipmunk_dashboard.data": fake_data,
    }
    with mock.patch.dict(sys.modules, patches):
        module = importlib.import_module("chipmunk_dashboard.app")
    return module


def _walk_components(node):
    if node is None:
        return
    yield node
    children = getattr(node, "children", None)
    if children is None:
        return
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk_components(child)
        return
    yield from _walk_components(children)


def _find_component_by_id(root, component_id: str):
    for node in _walk_components(root):
        if getattr(node, "id", None) == component_id:
            return node
    return None


# ---------------------------------------------------------------------------
# Synthetic data fixtures
# ---------------------------------------------------------------------------


def _make_trial_dataframe() -> pd.DataFrame:
    """Realistic trial DataFrame matching the columns expected by session_metrics."""
    n = 100
    rng = np.random.default_rng(42)
    t_stim = rng.uniform(1.0, 2.0, n)
    return pd.DataFrame(
        {
            "trial_num": list(range(1, n + 1)),
            "rewarded_modality": ["audio"] * n,
            "stim_rate_audio": rng.uniform(5.0, 15.0, n).tolist(),
            "stim_rate_vision": rng.uniform(5.0, 15.0, n).tolist(),
            "category_boundary": [10.0] * n,
            "t_start": rng.uniform(0.0, 0.5, n).tolist(),
            "t_stim": t_stim.tolist(),
            "t_gocue": (t_stim + rng.uniform(0.5, 1.5, n)).tolist(),
            "t_react": (t_stim + rng.uniform(0.5, 2.0, n)).tolist(),
            "t_response": (t_stim + rng.uniform(0.6, 2.1, n)).tolist(),
            "response": rng.choice([0, 1, -1], n).tolist(),
            "rewarded": rng.choice([0, 1], n, p=[0.3, 0.7]).tolist(),
            "punished": rng.choice([0, 1], n, p=[0.7, 0.3]).tolist(),
            "early_withdrawal": rng.choice([0, 1], n, p=[0.9, 0.1]).tolist(),
            "with_choice": rng.choice([0, 1], n, p=[0.2, 0.8]).tolist(),
        }
    )


def _make_subject_dataframe() -> pd.DataFrame:
    """Realistic subject DataFrame matching the columns expected by multisession_metrics."""
    n = 10
    rng = np.random.default_rng(42)
    session_names = [f"202601{i:02d}_120000" for i in range(1, n + 1)]
    return pd.DataFrame(
        {
            "session_name": session_names,
            "performance_easy": rng.uniform(0.5, 0.9, n).tolist(),
            "n_with_choice": rng.integers(50, 120, n).tolist(),
            "response_values": [rng.choice([-1, 0, 1], 80).tolist() for _ in range(n)],
            "initiation_times": [rng.uniform(0.3, 2.0, 80).tolist() for _ in range(n)],
            "reaction_times": [rng.uniform(0.1, 0.5, 50).tolist() for _ in range(n)],
        }
    )


def _make_session_metrics() -> dict:
    """Full session_metrics dict that exercises every figure-building branch."""
    n = 100
    rng = np.random.default_rng(42)
    trial_nums = list(range(1, n + 1))
    roll_x = list(range(10, n - 9, 5))
    nroll = len(roll_x)
    iti_roll_x = list(range(13, n - 12, 5))
    n_iti_roll = len(iti_roll_x)
    return dict(
        stims=[-2.0, -1.0, 0.0, 1.0, 2.0],
        n_correct=[4, 6, 8, 12, 15],
        n_incorrect=[10, 8, 6, 4, 2],
        n_ew=[2, 2, 2, 2, 2],
        n_no_choice=[1, 1, 1, 1, 1],
        p_right=[0.1, 0.25, 0.5, 0.75, 0.9],
        median_rt=[0.3, 0.28, 0.25, 0.24, 0.23],
        rts=rng.uniform(0.1, 0.5, n).tolist(),
        rt_trial_nums=trial_nums,
        rt_vals=rng.uniform(0.1, 0.5, n).tolist(),
        rt_roll_x=roll_x,
        rt_roll_y=rng.uniform(0.2, 0.4, nroll).tolist(),
        response_trial_nums=trial_nums,
        response_trial_nums_left=trial_nums[::2],
        response_trial_nums_right=trial_nums[1::2],
        response_roll_x=roll_x,
        response_roll_y=rng.uniform(0.1, 0.6, nroll).tolist(),
        response_roll_left_x=roll_x,
        response_roll_left_y=rng.uniform(0.1, 0.5, nroll).tolist(),
        response_roll_right_x=roll_x,
        response_roll_right_y=rng.uniform(0.2, 0.7, nroll).tolist(),
        init_times=rng.uniform(0.3, 2.0, n).tolist(),
        init_trial_nums=trial_nums,
        init_roll_x=roll_x,
        init_roll_y=rng.uniform(0.5, 1.5, nroll).tolist(),
        wait_times=rng.uniform(0.5, 3.0, n).tolist(),
        wait_min_times=rng.uniform(0.2, 1.0, n).tolist(),
        wait_delta_times=rng.uniform(0.0, 2.0, n).tolist(),
        wait_trial_nums=trial_nums,
        wait_delta_x=roll_x,
        wait_delta_y=rng.uniform(0.0, 1.0, nroll).tolist(),
        wait_delta_left_times=rng.uniform(0.0, 1.0, n // 2).tolist(),
        wait_delta_right_times=rng.uniform(0.0, 1.0, n // 2).tolist(),
        wait_trial_nums_left=trial_nums[::2],
        wait_trial_nums_right=trial_nums[1::2],
        wait_delta_left_x=roll_x,
        wait_delta_left_y=rng.uniform(0.0, 1.0, nroll).tolist(),
        wait_delta_right_x=roll_x,
        wait_delta_right_y=rng.uniform(0.0, 1.0, nroll).tolist(),
        wait_roll_x=roll_x,
        wait_roll_y=rng.uniform(0.5, 2.0, nroll).tolist(),
        wait_times_left=rng.uniform(0.5, 3.0, n // 2).tolist(),
        wait_times_right=rng.uniform(0.5, 3.0, n // 2).tolist(),
        wait_left_x=roll_x,
        wait_left_y=rng.uniform(0.5, 2.0, nroll).tolist(),
        wait_right_x=roll_x,
        wait_right_y=rng.uniform(0.5, 2.0, nroll).tolist(),
        response_times=rng.uniform(0.05, 0.8, n).tolist(),
        response_times_left=rng.uniform(0.05, 0.5, n // 2).tolist(),
        response_times_right=rng.uniform(0.2, 0.9, n // 2).tolist(),
        session_settings_lines=[
            "trials: 100",
            "rewarded modality: audio",
            "audio stim range: 5.00 to 15.00",
        ],
        water_side_totals=[120.0, 150.0, 270.0],
        water_side_totals_ul=[120.0, 150.0, 270.0],
        water_cum_x=trial_nums,
        water_cum_total_ul=np.cumsum(rng.uniform(1.0, 2.0, n)).tolist(),
        water_cum_left_ul=np.cumsum(rng.uniform(0.4, 1.0, n)).tolist(),
        water_cum_right_ul=np.cumsum(rng.uniform(0.4, 1.0, n)).tolist(),
        iti_times=rng.uniform(0.5, 3.0, n).tolist(),
        iti_times_after_correct=rng.uniform(0.5, 3.0, n // 4).tolist(),
        iti_times_after_incorrect=rng.uniform(0.5, 3.0, n // 4).tolist(),
        iti_times_after_ew=rng.uniform(0.5, 3.0, n // 4).tolist(),
        iti_times_after_no_choice=rng.uniform(0.5, 3.0, n // 4).tolist(),
        iti_roll_x=iti_roll_x,
        iti_roll_y=rng.uniform(0.5, 2.0, n_iti_roll).tolist(),
        iti_roll_correct_x=iti_roll_x,
        iti_roll_correct_y=rng.uniform(0.5, 2.0, n_iti_roll).tolist(),
        iti_roll_incorrect_x=iti_roll_x,
        iti_roll_incorrect_y=rng.uniform(0.5, 2.0, n_iti_roll).tolist(),
        iti_roll_ew_x=iti_roll_x,
        iti_roll_ew_y=rng.uniform(0.5, 2.0, n_iti_roll).tolist(),
        iti_roll_no_choice_x=iti_roll_x,
        iti_roll_no_choice_y=rng.uniform(0.5, 2.0, n_iti_roll).tolist(),
        trial_count_x=[5, 10, 15, 20],
        trial_count_y=[6.0, 8.0, 9.0, 10.0],
        slide_x=roll_x,
        slide_y=rng.uniform(0.5, 0.9, nroll).tolist(),
        ew_roll_x=roll_x,
        ew_roll_y=rng.uniform(0.0, 0.2, nroll).tolist(),
    )


def _make_multisession_metrics() -> dict:
    """Full multisession_metrics dict for multi-session figure building."""
    n = 10
    rng = np.random.default_rng(42)
    return dict(
        x=[f"2026-01-{i + 1:02d} 12:00:00" for i in range(n)],
        session_dates=[f"2026-01-{i + 1:02d} 12:00:00" for i in range(n)],
        training_time_hours=[9.5 + (i * 0.25) for i in range(n)],
        perf_easy=rng.uniform(0.5, 0.9, n).tolist(),
        ew_rate=rng.uniform(0.0, 0.3, n).tolist(),
        n_with_choice=[int(v) for v in rng.integers(50, 120, n)],
        side_bias=rng.uniform(-0.2, 0.2, n).tolist(),
        median_init=rng.uniform(0.3, 1.0, n).tolist(),
        median_rt=rng.uniform(0.2, 0.5, n).tolist(),
        median_wait=rng.uniform(0.5, 2.0, n).tolist(),
        water=rng.uniform(1.0, 3.0, n).tolist(),
    )


# ---------------------------------------------------------------------------
# Layer A: Third-party API surface
# ---------------------------------------------------------------------------


class TestPlotlyApiSurface(unittest.TestCase):
    """Verify the plotly API surface the app relies on still exists."""

    def test_figure_core_methods_exist(self):
        fig = go.Figure()
        fig.update_layout(
            margin=dict(l=50, r=20, t=42, b=80), legend=dict(visible=False)
        )
        fig.update_yaxes(range=[0, 1])
        fig.layout.shapes = []

    def test_scatter_trace_accepts_app_kwargs(self):
        go.Figure().add_trace(
            go.Scatter(
                x=[1, 2, 3],
                y=[0.1, 0.5, 0.9],
                mode="lines+markers",
                name="test",
                showlegend=True,
                legendgroup="grp",
                marker=dict(color="#1f77b4", size=7),
                line=dict(color="#1f77b4", width=2, dash="dash"),
                hovertemplate="%{y:.2f}<extra>subj</extra>",
                yaxis="y2",
                opacity=0.7,
            )
        )

    def test_scattergl_trace_accepts_app_kwargs(self):
        go.Figure().add_trace(
            go.Scattergl(
                x=[1, 2, 3],
                y=[0.1, 0.2, 0.3],
                mode="markers",
                name="test",
                showlegend=False,
                legendgroup="grp",
                marker=dict(color="#1f77b4", size=3, opacity=0.4),
            )
        )

    def test_bar_trace_accepts_app_kwargs(self):
        # Vertical stacked bars (single-subject mode)
        go.Figure().add_trace(
            go.Bar(
                x=[-2.0, -1.0, 0.0, 1.0, 2.0],
                y=[5, 8, 12, 18, 20],
                name="correct",
                legendgroup="grp",
                showlegend=True,
                marker_color="mediumseagreen",
                hovertemplate="%{y} correct<extra>subj</extra>",
            )
        )
        # Horizontal stacked bars (multi-subject mode)
        go.Figure().add_trace(
            go.Bar(
                y=["subject-a", "subject-b"],
                x=[10, 20],
                name="correct",
                orientation="h",
                marker_color="mediumseagreen",
                hovertemplate="%{x} correct<extra>%{y}</extra>",
            )
        )

    def test_box_trace_accepts_app_kwargs(self):
        go.Figure().add_trace(
            go.Box(
                y=[0.5, 0.6, 0.7, 0.55, 0.65],
                name="subject-a",
                marker_color="#1f77b4",
                legendgroup="grp",
                showlegend=False,
                boxmean=True,
            )
        )

    def test_histogram_trace_accepts_app_kwargs(self):
        go.Figure().add_trace(
            go.Histogram(
                x=[0.2, 0.3, 0.4, 0.25, 0.35],
                nbinsx=30,
                name="subject-a",
                marker_color="#1f77b4",
                showlegend=False,
                opacity=0.8,
            )
        )

    def test_violin_trace_accepts_app_kwargs(self):
        go.Figure().add_trace(
            go.Violin(
                x=["subject-a", "subject-a", "subject-a"],
                y=[0.2, 0.25, 0.3],
                name="Correct",
                legendgroup="gap-correct",
                showlegend=True,
                line_color="mediumseagreen",
                side="negative",
                meanline_visible=True,
                points=False,
                scalegroup="subject-a",
            )
        )

    def test_reference_lines_accept_app_kwargs(self):
        fig = go.Figure()
        fig.add_hline(y=0.5, line_dash="dash", line_color="grey", line_width=1)
        fig.add_vline(x=1.0, line_dash="dash", line_color="black", line_width=1.5)

    def test_express_color_palette_is_available(self):
        colors = px.colors.qualitative.Plotly
        self.assertIsInstance(colors, list)
        self.assertGreater(len(colors), 0)


class TestDashApiSurface(unittest.TestCase):
    """Verify the dash component API surface the app relies on still exists."""

    def test_dash_constructor_accepts_app_kwargs(self):
        Dash(
            __name__,
            title="test",
            suppress_callback_exceptions=True,
            external_stylesheets=[],
        )

    def test_dcc_graph_accepts_app_kwargs(self):
        dcc.Graph(
            id="graph-id",
            style={"height": "280px", "width": "100%"},
            config={"displayModeBar": False},
        )

    def test_dcc_checklist_accepts_app_kwargs(self):
        dcc.Checklist(
            id="subjects",
            options=[{"label": "Subject A", "value": "a"}],
            value=[],
            style={"display": "flex"},
            inputStyle={"marginRight": "6px"},
            labelStyle={"fontSize": "16px"},
        )

    def test_dcc_datepickersingle_accepts_app_kwargs(self):
        dcc.DatePickerSingle(
            id="session-date",
            display_format="YYYY-MM-DD",
            style={"width": "100%"},
        )

    def test_dcc_dropdown_accepts_app_kwargs(self):
        dcc.Dropdown(
            id="session-time",
            placeholder="Time (if multiple)",
            style={"marginBottom": "8px"},
        )

    def test_dcc_slider_accepts_app_kwargs(self):
        dcc.Slider(
            id="smooth-window",
            min=1,
            max=10,
            step=1,
            value=3,
            marks={1: "1", 3: "3", 5: "5", 10: "10"},
        )

    def test_dcc_interval_accepts_app_kwargs(self):
        dcc.Interval(id="auto-refresh", interval=60 * 60 * 1000)

    def test_html_components_construct(self):
        html.Div([], style={"display": "flex"})
        html.Label("Subjects", style={"fontWeight": "bold"})
        html.Button("Clear", id="clear-btn", n_clicks=0, style={})
        html.Br()
        html.H2("Title", style={})
        html.H3("Section", style={})

    def test_input_output_accept_component_property_pairs(self):
        Input("subjects", "value")
        Input("session-date", "date")
        Input("auto-refresh", "n_intervals")
        Output("session-date", "date")
        Output("session-date", "min_date_allowed")
        Output("session-date", "max_date_allowed")
        Output("session-date", "initial_visible_month")
        Output("session-time", "options")
        Output("session-time", "value")
        Output("subjects", "value")
        Output("subjects", "options")
        Output("frac-correct", "figure")


class TestPandasApiSurface(unittest.TestCase):
    """Verify the pandas API surface the data layer relies on still exists."""

    def test_dataframe_construction_and_core_operations(self):
        rows = [
            {"session": "20260101_120000", "val": 0.7},
            {"session": "20260102_120000", "val": 0.8},
        ]
        df = pd.DataFrame(rows)
        df2 = df.copy()
        df2.sort_values("session")
        df2["session"].str.slice(0, 8)
        df2.tail(1)
        df2["val"].tolist()
        _ = df2.empty
        df2.loc[df2["val"] > 0.7]
        df2.iloc[0]
        df2.groupby("session").size().reset_index()

    def test_datetime_and_timestamp_operations(self):
        ts1 = pd.to_datetime("20260101", format="%Y%m%d", errors="coerce")
        ts2 = pd.to_datetime("2026-01-05")
        delta = pd.Timestamp(ts2) - pd.Timestamp(ts1)
        _ = delta.days
        self.assertTrue(pd.notna(1.0))
        self.assertFalse(pd.notna(None))

    def test_series_rolling_window(self):
        s = pd.Series([0.6, 0.65, float("nan"), 0.7, 0.75])
        result = s.rolling(window=3, center=True, min_periods=1).mean().tolist()
        self.assertEqual(len(result), 5)


class TestNumpyApiSurface(unittest.TestCase):
    """Verify the numpy API surface the data layer relies on still exists."""

    def test_constants_and_array_creation(self):
        _ = np.nan
        np.full(3, np.nan)
        np.array([1.0, 2.0, 3.0])
        np.asarray([1, 2, 3])

    def test_filtering_functions(self):
        arr = np.array([1.0, np.nan, 3.0, np.inf])
        finite = np.isfinite(arr)
        self.assertEqual(finite.sum(), 2)
        np.unique(np.array([1, 2, 1, 3]))
        mask = np.isin(np.array([1, 2, 3]), [1, 3])
        self.assertTrue(mask[0])
        self.assertFalse(mask[1])

    def test_statistical_functions(self):
        arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertAlmostEqual(np.mean(arr), 3.0)
        self.assertAlmostEqual(np.median(arr), 3.0)

    def test_indexing_functions(self):
        arr = np.array([3.0, 1.0, 2.0])
        idx = np.argsort(arr)
        self.assertEqual(idx[0], 1)
        out = np.where(arr > 2.0, arr, 0.0)
        self.assertEqual(out[0], 3.0)
        self.assertEqual(out[1], 0.0)

    def test_array_properties_and_methods(self):
        arr = np.array([[1.0, 2.0], [3.0, 4.0]])
        self.assertEqual(arr.size, 4)
        self.assertEqual(arr.shape, (2, 2))
        self.assertEqual(arr.ravel().shape, (4,))


# ---------------------------------------------------------------------------
# Layer B: App creation smoke test with real libraries
# ---------------------------------------------------------------------------


class TestAppCreationWithRealLibs(unittest.TestCase):
    def setUp(self):
        self.addCleanup(lambda: sys.modules.pop("chipmunk_dashboard.app", None))
        self.appmod = _import_app_with_real_libs()

    def test_create_app_returns_real_dash_instance(self):
        app = self.appmod.create_app()
        self.assertIsInstance(app, Dash)

    def test_create_app_sets_non_null_layout(self):
        app = self.appmod.create_app()
        self.assertIsNotNone(app.layout)

    def test_create_app_includes_single_session_tabs(self):
        app = self.appmod.create_app()
        tabs = _find_component_by_id(app.layout, "single-session-tabs")
        self.assertIsNotNone(tabs)
        self.assertEqual(tabs.value, "single-overview")
        self.assertEqual(len(tabs.children), 2)
        labels = [child.label for child in tabs.children]
        values = [child.value for child in tabs.children]
        self.assertEqual(labels, ["Overview", "Timing"])
        self.assertEqual(values, ["single-overview", "single-timing"])

    def test_create_app_includes_overview_summary_boxes(self):
        app = self.appmod.create_app()
        self.assertIsNotNone(_find_component_by_id(app.layout, "session-settings-box"))
        self.assertIsNotNone(
            _find_component_by_id(app.layout, "session-settings-toggle")
        )
        self.assertIsNotNone(_find_component_by_id(app.layout, "water-cumulative"))
        self.assertIsNotNone(_find_component_by_id(app.layout, "training-time"))

    def test_create_app_places_iti_row_after_response_time_row(self):
        app = self.appmod.create_app()
        tabs = _find_component_by_id(app.layout, "single-session-tabs")
        self.assertIsNotNone(tabs)
        timing_tab = next(
            child for child in tabs.children if child.value == "single-timing"
        )
        rows = list(timing_tab.children.children)
        row_ids = []
        for row in rows:
            children = (
                row.children
                if isinstance(row.children, (list, tuple))
                else [row.children]
            )
            row_ids.append(tuple(getattr(child, "id", None) for child in children))

        response_row = ("response-time-line", "response-time")
        iti_row = ("iti-rolling", "iti-dist")
        self.assertIn(response_row, row_ids)
        self.assertIn(iti_row, row_ids)
        self.assertLess(row_ids.index(response_row), row_ids.index(iti_row))

    def test_empty_fig_returns_real_plotly_figure(self):
        fig = self.appmod._empty_fig("No data")
        self.assertIsInstance(fig, go.Figure)
        self.assertFalse(fig.layout.xaxis.visible)
        self.assertFalse(fig.layout.yaxis.visible)
        self.assertEqual(fig.layout.annotations[0].text, "No data")

    def test_layout_helper_applies_title_to_real_figure(self):
        fig = go.Figure()
        self.appmod._layout(fig, title="Test Title", xaxis_title="x")
        self.assertEqual(fig.layout.title.text, "Test Title")


# ---------------------------------------------------------------------------
# Layer C: Data processing with real pandas/numpy
# ---------------------------------------------------------------------------


class TestSessionMetricsWithRealLibs(unittest.TestCase):
    def setUp(self):
        self.addCleanup(lambda: sys.modules.pop("chipmunk_dashboard.data", None))
        self.data = _import_data_with_real_libs()
        self.data.session_metrics.cache_clear()

    def test_session_metrics_returns_all_expected_keys(self):
        trials = _make_trial_dataframe()
        with (
            mock.patch.object(self.data, "get_session_trials", return_value=trials),
            mock.patch.object(
                self.data, "get_subject_water", return_value={"20260101_010101": 1.5}
            ),
        ):
            result = self.data.session_metrics("subject-a", "20260101_010101")

        self.assertIsNotNone(result)
        expected_keys = {
            "stims",
            "n_correct",
            "n_incorrect",
            "n_ew",
            "n_no_choice",
            "p_right",
            "median_rt",
            "rts",
            "rt_trial_nums",
            "rt_vals",
            "rt_roll_x",
            "rt_roll_y",
            "response_trial_nums",
            "response_trial_nums_left",
            "response_trial_nums_right",
            "response_roll_x",
            "response_roll_y",
            "response_roll_left_x",
            "response_roll_left_y",
            "response_roll_right_x",
            "response_roll_right_y",
            "response_times",
            "response_times_left",
            "response_times_right",
            "session_settings_lines",
            "water_side_totals",
            "water_side_totals_ul",
            "water_cum_x",
            "water_cum_total_ul",
            "water_cum_left_ul",
            "water_cum_right_ul",
            "iti_times",
            "trial_count_x",
            "trial_count_y",
            "init_times",
            "init_trial_nums",
            "init_roll_x",
            "init_roll_y",
            "wait_times",
            "wait_min_times",
            "wait_delta_times",
            "wait_delta_left_times",
            "wait_delta_right_times",
            "wait_trial_nums",
            "wait_trial_nums_left",
            "wait_trial_nums_right",
            "wait_delta_x",
            "wait_delta_y",
            "wait_delta_left_x",
            "wait_delta_left_y",
            "wait_delta_right_x",
            "wait_delta_right_y",
            "wait_roll_x",
            "wait_roll_y",
            "wait_times_left",
            "wait_times_right",
            "wait_left_x",
            "wait_left_y",
            "wait_right_x",
            "wait_right_y",
            "slide_x",
            "slide_y",
            "ew_roll_x",
            "ew_roll_y",
            "iti_times_after_correct",
            "iti_times_after_incorrect",
            "iti_times_after_ew",
            "iti_times_after_no_choice",
            "iti_roll_x",
            "iti_roll_y",
            "iti_roll_correct_x",
            "iti_roll_correct_y",
            "iti_roll_incorrect_x",
            "iti_roll_incorrect_y",
            "iti_roll_ew_x",
            "iti_roll_ew_y",
            "iti_roll_no_choice_x",
            "iti_roll_no_choice_y",
        }
        self.assertEqual(set(result.keys()), expected_keys)

    def test_session_metrics_all_values_are_plain_lists(self):
        trials = _make_trial_dataframe()
        with (
            mock.patch.object(self.data, "get_session_trials", return_value=trials),
            mock.patch.object(
                self.data, "get_subject_water", return_value={"20260101_010101": 1.5}
            ),
        ):
            result = self.data.session_metrics("subject-a", "20260101_010101")

        self.assertIsNotNone(result)
        for key, val in result.items():
            self.assertIsInstance(
                val, list, f"key '{key}' should be a list, got {type(val)}"
            )

    def test_session_metrics_returns_none_for_empty_trials(self):
        with mock.patch.object(
            self.data, "get_session_trials", return_value=pd.DataFrame()
        ):
            result = self.data.session_metrics("subject-a", "20260101_010101")
        self.assertIsNone(result)

    def test_session_metrics_iti_incorrect_falls_back_to_unrewarded_choices(self):
        trials = _make_trial_dataframe().head(6).copy()
        trials["trial_num"] = [1, 2, 3, 4, 5, 6]
        trials["t_start"] = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0]
        trials["t_stim"] = [0.5, 2.5, 4.5, 6.5, 8.5, 10.5]
        trials["t_gocue"] = [1.0, 3.0, 5.0, 7.0, 9.0, 11.0]
        trials["t_react"] = [1.2, 3.2, 5.2, 7.2, 9.2, 11.2]
        trials["t_response"] = [1.5, 3.5, 5.5, 7.5, 9.5, 11.5]
        trials["response"] = [1, 1, -1, -1, 1, 1]
        trials["with_choice"] = [1, 1, 1, 1, 1, 1]
        # Trial 1 is incorrect even though punished=0, which is a valid data shape.
        trials["rewarded"] = [0, 1, 1, 1, 1, 1]
        trials["punished"] = [0, 0, 0, 0, 0, 0]
        trials["early_withdrawal"] = [0, 0, 0, 0, 0, 0]

        with (
            mock.patch.object(self.data, "get_session_trials", return_value=trials),
            mock.patch.object(self.data, "get_subject_water", return_value={}),
        ):
            result = self.data.session_metrics("subject-a", "20260101_010101")

        self.assertIsNotNone(result)
        self.assertEqual(result["iti_times_after_incorrect"], [2.0])
        self.assertEqual(result["iti_roll_incorrect_x"], [1])
        self.assertEqual(result["iti_roll_incorrect_y"], [2.0])

    def test_session_metrics_incorrect_count_uses_with_choice_and_rewarded(self):
        trials = _make_trial_dataframe().head(6).copy()
        trials["trial_num"] = [1, 2, 3, 4, 5, 6]
        trials["stim_rate_audio"] = [10.0] * 6
        trials["stim_rate_vision"] = [10.0] * 6
        trials["rewarded"] = [1, 0, 0, 0, 1, 0]
        trials["with_choice"] = [1, 1, 1, 0, 0, 1]
        trials["early_withdrawal"] = [0, 0, 1, 1, 0, 0]
        # punished is intentionally unused for incorrect classification.
        trials["punished"] = [0, 0, 0, 0, 0, 0]

        with (
            mock.patch.object(self.data, "get_session_trials", return_value=trials),
            mock.patch.object(self.data, "get_subject_water", return_value={}),
        ):
            result = self.data.session_metrics("subject-a", "20260101_010101")

        self.assertIsNotNone(result)
        self.assertEqual(result["n_correct"], [2])
        self.assertEqual(result["n_incorrect"], [3])
        self.assertEqual(result["n_ew"], [1])
        self.assertEqual(result["n_no_choice"], [0])


class TestMultisessionMetricsWithRealLibs(unittest.TestCase):
    def setUp(self):
        self.addCleanup(lambda: sys.modules.pop("chipmunk_dashboard.data", None))
        self.data = _import_data_with_real_libs()
        self.data.multisession_metrics.cache_clear()
        self.data.get_subject_data.cache_clear()

    def _patched(self, df):
        return (
            mock.patch.object(self.data, "get_subject_data", return_value=df),
            mock.patch.object(
                self.data, "get_wait_medians_for_sessions", return_value={}
            ),
            mock.patch.object(self.data, "get_subject_water", return_value={}),
        )

    def test_multisession_metrics_returns_all_expected_keys(self):
        df = _make_subject_dataframe()
        with self._patched(df)[0], self._patched(df)[1], self._patched(df)[2]:
            result = self.data.multisession_metrics("subject-a", sessions_back=5)

        self.assertIsNotNone(result)
        expected_keys = {
            "x",
            "session_dates",
            "training_time_hours",
            "perf_easy",
            "ew_rate",
            "n_with_choice",
            "side_bias",
            "median_init",
            "median_rt",
            "median_wait",
            "water",
        }
        self.assertEqual(set(result.keys()), expected_keys)

    def test_multisession_metrics_smoothed_has_same_length_as_unsmoothed(self):
        df = _make_subject_dataframe()
        patches = self._patched(df)
        with patches[0], patches[1], patches[2]:
            raw = self.data.multisession_metrics(
                "subject-a", sessions_back=5, smooth=False, smooth_window=3
            )
        self.data.multisession_metrics.cache_clear()
        patches = self._patched(df)
        with patches[0], patches[1], patches[2]:
            smoothed = self.data.multisession_metrics(
                "subject-a", sessions_back=5, smooth=True, smooth_window=3
            )

        self.assertEqual(len(raw["x"]), len(smoothed["x"]))
        self.assertEqual(len(raw["perf_easy"]), len(smoothed["perf_easy"]))

    def test_multisession_metrics_returns_none_for_empty_subject_data(self):
        with mock.patch.object(
            self.data, "get_subject_data", return_value=pd.DataFrame()
        ):
            result = self.data.multisession_metrics("subject-a", sessions_back=5)
        self.assertIsNone(result)

    def test_multisession_metrics_returns_nan_training_time_when_session_name_lacks_time(
        self,
    ):
        df = pd.DataFrame(
            {
                "session_name": ["20260105", "bad-session"],
                "performance_easy": [0.6, 0.7],
                "n_with_choice": [60, 65],
                "response_values": [[-1, 1], [-1, 1]],
                "initiation_times": [[0.5, 0.6], [0.7, 0.8]],
                "reaction_times": [[0.2, 0.3], [0.4, 0.5]],
            }
        )
        with self._patched(df)[0], self._patched(df)[1], self._patched(df)[2]:
            result = self.data.multisession_metrics("subject-a", sessions_back=10)

        self.assertIsNotNone(result)
        self.assertTrue(math.isnan(result["training_time_hours"][0]))
        self.assertTrue(math.isnan(result["training_time_hours"][1]))


# ---------------------------------------------------------------------------
# Layer D: Callback bodies with real plotly figures
# ---------------------------------------------------------------------------


class TestCallbacksWithRealPlotly(unittest.TestCase):
    """Run _update_single and _update_multi with real plotly and synthetic data.

    Uses _FakeDash so callbacks are accessible via app.callbacks[name], while
    plotly.graph_objects and numpy are the real installed libraries.  Only the
    data layer is mocked.
    """

    def setUp(self):
        self.addCleanup(lambda: sys.modules.pop("chipmunk_dashboard.app", None))
        self.appmod = _import_app_fake_dash_real_plotly()

    def test_update_single_single_subject_returns_sixteen_figures(self):
        app = self.appmod.create_app()
        update_single = app.callbacks["_update_single"]
        sm = _make_session_metrics()
        with (
            mock.patch.object(
                self.appmod, "get_sessions", return_value=["20260101_010101"]
            ),
            mock.patch.object(self.appmod, "session_metrics", return_value=sm),
        ):
            figures = update_single(["subject-a"], [], "20260101_010101", 0, None)

        self.assertEqual(len(figures), 16)
        for fig in figures:
            self.assertIsInstance(fig, go.Figure)
        # Single-subject outcome chart: 4 vertical bar traces (one per outcome type)
        self.assertEqual(len(figures[0].data), 4)
        # P(right) and chronometric charts have one trace each
        self.assertEqual(len(figures[1].data), 1)
        self.assertEqual(len(figures[2].data), 1)
        # Wait-floor plot includes aggregate + split traces with aggregate visible by default.
        self.assertGreaterEqual(len(figures[8].data), 2)
        # Timing scatter panels apply robust default y-axis clipping.
        self.assertIsNotNone(figures[4].layout.yaxis.range)
        self.assertIsNotNone(figures[6].layout.yaxis.range)
        self.assertIsNotNone(figures[8].layout.yaxis.range)
        # Wait-floor dist panel includes aggregate + split traces.
        self.assertGreaterEqual(len(figures[9].data), 1)
        self.assertIsInstance(figures[9].data[0], go.Scatter)
        # Response-time rolling plot (index 10): raw + rolling (+ split hidden traces)
        self.assertGreaterEqual(len(figures[10].data), 3)
        self.assertIsInstance(figures[10].data[0], go.Scattergl)
        self.assertEqual(figures[10].layout.updatemenus[0].buttons[0].label, "Choice")
        self.assertEqual(figures[10].layout.updatemenus[0].active, -1)
        # Response-time dist (index 11): combined KDE + split hidden traces
        self.assertGreaterEqual(len(figures[11].data), 3)
        self.assertIsInstance(figures[11].data[0], go.Scatter)
        self.assertEqual(figures[11].layout.updatemenus[0].buttons[0].label, "Choice")
        self.assertEqual(figures[6].layout.updatemenus[0].buttons[0].label, "Choice")
        self.assertEqual(figures[8].layout.updatemenus[0].buttons[0].label, "Choice")
        self.assertEqual(figures[12].layout.updatemenus[0].buttons[0].label, "Outcome")
        # ITI dist panel (index 12) includes aggregate + split traces.
        self.assertGreaterEqual(len(figures[12].data), 1)
        self.assertIsInstance(figures[12].data[0], go.Scatter)
        # Trial-count-time (index 13) is a rolling scatter in single-subject mode
        self.assertEqual(len(figures[13].data), 1)
        self.assertIsInstance(figures[13].data[0], go.Scatter)
        # Water cumulative plot (index 14) has line traces + side toggle
        self.assertGreaterEqual(len(figures[14].data), 1)
        self.assertIsInstance(figures[14].data[0], go.Scatter)
        self.assertEqual(figures[14].layout.updatemenus[0].buttons[0].label, "Side")
        # ITI rolling trend (index 15) includes aggregate + split traces.
        self.assertGreaterEqual(len(figures[15].data), 1)
        self.assertIsInstance(figures[15].data[0], go.Scatter)
        self.assertEqual(figures[15].layout.updatemenus[0].buttons[0].label, "Outcome")

    def test_update_single_multi_subject_uses_box_and_horizontal_bars(self):
        app = self.appmod.create_app()
        update_single = app.callbacks["_update_single"]
        sm = _make_session_metrics()
        with (
            mock.patch.object(
                self.appmod, "get_sessions", return_value=["20260101_010101"]
            ),
            mock.patch.object(self.appmod, "session_metrics", return_value=sm),
        ):
            figures = update_single(
                ["subject-a"], ["subject-b"], "20260101_010101", 0, "2026-01-01"
            )

        self.assertEqual(len(figures), 16)
        for fig in figures:
            self.assertIsInstance(fig, go.Figure)
        # Multi-col outcome chart: 4 horizontal bar traces
        self.assertEqual(len(figures[0].data), 4)
        self.assertIsInstance(figures[0].data[0], go.Bar)
        self.assertEqual(figures[0].data[0].orientation, "h")
        # Initiation dist uses Box in multi mode
        self.assertIsInstance(figures[5].data[0], go.Box)
        # Wait floor includes aggregate + split traces in multi-subject mode.
        self.assertGreaterEqual(len(figures[8].data), 4)
        # Wait-floor dist (index 9) uses Box in multi mode
        self.assertIsInstance(figures[9].data[0], go.Box)
        # Response-time rolling (index 10) uses scatter markers/lines in multi mode
        self.assertIsInstance(figures[10].data[0], go.Scattergl)
        # Response-time dist (index 11) uses per-subject box plots in multi mode
        self.assertIsInstance(figures[11].data[0], go.Box)
        # ITI dist (index 12) uses Box in multi mode
        self.assertIsInstance(figures[12].data[0], go.Box)
        # Trial-count-time (index 13) uses scatter in multi mode
        self.assertIsInstance(figures[13].data[0], go.Scatter)
        # Water cumulative (index 14) uses scatter in multi mode
        self.assertIsInstance(figures[14].data[0], go.Scatter)
        # ITI rolling trend (index 15) uses scatter lines in multi mode
        self.assertIsInstance(figures[15].data[0], go.Scatter)

    def test_update_overview_boxes_renders_subject_summaries(self):
        app = self.appmod.create_app()
        update_overview_boxes = app.callbacks["_update_overview_boxes"]
        sm = _make_session_metrics()
        with (
            mock.patch.object(
                self.appmod, "get_sessions", return_value=["20260101_010101"]
            ),
            mock.patch.object(self.appmod, "session_metrics", return_value=sm),
        ):
            settings = update_overview_boxes(
                ["subject-a"], [], "20260101_010101", 0, None
            )

        self.assertIn("subject-a (20260101_010101)", settings)
        self.assertIn("rewarded modality", settings)
        self.assertIn("water (µL):", settings)

    def test_update_multi_with_data_returns_eight_figures(self):
        app = self.appmod.create_app()
        update_multi = app.callbacks["_update_multi"]
        ms = _make_multisession_metrics()
        with mock.patch.object(self.appmod, "multisession_metrics", return_value=ms):
            figures = update_multi(["subject-a"], [], 10, "2026-01-10", [], 3, 0)

        self.assertEqual(len(figures), 9)
        for fig in figures:
            self.assertIsInstance(fig, go.Figure)
        # Performance figure should have one Scatter trace
        self.assertEqual(len(figures[0].data), 1)
        self.assertIsInstance(figures[0].data[0], go.Scatter)

    def test_update_multi_hover_shows_session_date(self):
        app = self.appmod.create_app()
        update_multi = app.callbacks["_update_multi"]
        ms = _make_multisession_metrics()
        with mock.patch.object(self.appmod, "multisession_metrics", return_value=ms):
            figures = update_multi(["subject-a"], [], 10, "2026-01-10", [], 3, 0)

        perf_trace = figures[0].data[0]
        self.assertEqual(list(perf_trace.customdata), ms["session_dates"])
        self.assertIn("session date: %{customdata}", perf_trace.hovertemplate)
        self.assertEqual(list(perf_trace.x), ms["x"])
        self.assertEqual(figures[0].layout.xaxis.type, "date")
        self.assertEqual(figures[0].layout.xaxis.title.text, "session datetime")

    def test_update_multi_smooth_enabled_still_returns_eight_figures(self):
        app = self.appmod.create_app()
        update_multi = app.callbacks["_update_multi"]
        ms = _make_multisession_metrics()
        with mock.patch.object(self.appmod, "multisession_metrics", return_value=ms):
            figures = update_multi(
                ["subject-a"], [], 10, "2026-01-10", ["smooth"], 5, 0
            )

        self.assertEqual(len(figures), 9)
        for fig in figures:
            self.assertIsInstance(fig, go.Figure)

    def test_update_single_recent_and_older_subjects_are_merged(self):
        """Subjects from both checklists are combined and processed together."""
        app = self.appmod.create_app()
        update_single = app.callbacks["_update_single"]
        sm = _make_session_metrics()
        with (
            mock.patch.object(
                self.appmod, "get_sessions", return_value=["20260101_010101"]
            ),
            mock.patch.object(self.appmod, "session_metrics", return_value=sm),
        ):
            figures = update_single(
                ["subject-a"], ["subject-b"], "20260101_010101", 0, "2026-01-01"
            )

        self.assertEqual(len(figures), 16)

    def test_update_multi_recent_and_older_subjects_are_merged(self):
        """Subjects from both checklists are combined and processed together."""
        app = self.appmod.create_app()
        update_multi = app.callbacks["_update_multi"]
        ms = _make_multisession_metrics()
        with mock.patch.object(self.appmod, "multisession_metrics", return_value=ms):
            figures = update_multi(["subject-a"], ["subject-b"], 10, None, [], 3, 0)

        self.assertEqual(len(figures), 9)

    def test_update_single_skips_subjects_with_falsy_session_name(self):
        """Line 590: `if not ses: continue` — session name resolves to empty string."""
        app = self.appmod.create_app()
        update_single = app.callbacks["_update_single"]
        # get_sessions returns [""] — non-empty list so subject is "valid", but
        # ses = "" which is falsy → the loop body is skipped via continue.
        with mock.patch.object(self.appmod, "get_sessions", return_value=[""]):
            figures = update_single(["subject-a"], [], None, 0, None)
        self.assertEqual(len(figures), 16)
        for fig in figures:
            self.assertIsInstance(fig, go.Figure)

    def test_update_single_skips_subject_when_session_metrics_none(self):
        """Line 593: `if not sm: continue` — session_metrics returns None."""
        app = self.appmod.create_app()
        update_single = app.callbacks["_update_single"]
        with (
            mock.patch.object(
                self.appmod, "get_sessions", return_value=["20260101_010101"]
            ),
            mock.patch.object(self.appmod, "session_metrics", return_value=None),
        ):
            figures = update_single(["subject-a"], [], "20260101_010101", 0, None)
        self.assertEqual(len(figures), 16)

    def test_update_multi_skips_subject_when_multisession_metrics_none(self):
        """Line 1128: `if not ms: continue` — multisession_metrics returns None."""
        app = self.appmod.create_app()
        update_multi = app.callbacks["_update_multi"]
        with mock.patch.object(self.appmod, "multisession_metrics", return_value=None):
            figures = update_multi(["subject-a"], [], 10, "2026-01-10", [], 3, 0)
        self.assertEqual(len(figures), 9)

    def test_update_multi_training_time_plot_uses_clock_axis(self):
        app = self.appmod.create_app()
        update_multi = app.callbacks["_update_multi"]
        ms = _make_multisession_metrics()
        with mock.patch.object(self.appmod, "multisession_metrics", return_value=ms):
            figures = update_multi(["subject-a"], [], 10, "2026-01-10", [], 3, 0)

        training_trace = figures[8].data[0]
        self.assertEqual(training_trace.type, "scatter")
        self.assertEqual(list(training_trace.x), ms["x"])
        self.assertEqual(list(training_trace.y), ms["training_time_hours"])
        self.assertEqual(figures[8].layout.title.text, "Training Time")
        self.assertEqual(figures[8].layout.yaxis.ticktext[3], "09:00")


# ---------------------------------------------------------------------------
# Layer E: data.py non-empty code paths
# ---------------------------------------------------------------------------


class _QueryChain:
    """Chainable fake for DataJoint table expressions used in data.py queries.

    Supports ``Table * Table.Part * Table.Params & restriction`` chaining and
    a ``.fetch()`` call that returns the rows passed at construction time.
    Attribute access (for nested table names like ``Chipmunk.Trial``) returns
    ``self`` so the full expression evaluates to a single ``_QueryChain``.
    """

    def __init__(self, rows):
        self._rows = rows

    def __mul__(self, other):
        return self

    def __rmul__(self, other):
        return self

    def __and__(self, _):
        return self

    def fetch(self, *args, **kwargs):
        if kwargs.get("as_dict"):
            return self._rows
        return self._rows

    def __getattr__(self, name):
        return self


class TestDataNonEmptyPaths(unittest.TestCase):
    """Cover data.py branches that are only reached with non-empty DB results."""

    def setUp(self):
        self.addCleanup(lambda: sys.modules.pop("chipmunk_dashboard.data", None))
        self.data = _import_data_with_real_libs()
        self.data.get_trials_for_sessions.cache_clear()
        self.data.get_wait_medians_for_sessions.cache_clear()
        self.data.multisession_metrics.cache_clear()
        self.data.get_subject_data.cache_clear()

    # -- get_trials_for_sessions (lines 257-280) ------------------------------

    def test_get_trials_for_sessions_non_empty_returns_grouped_dict(self):
        rows = [
            {"session_name": "20260101", "trial_num": 1, "x": 10},
            {"session_name": "20260101", "trial_num": 2, "x": 20},
            {"session_name": "20260102", "trial_num": 1, "x": 30},
        ]
        with mock.patch.object(self.data, "Chipmunk", _QueryChain(rows)):
            result = self.data.get_trials_for_sessions(
                "subject-a", ("20260101", "20260102")
            )

        self.assertEqual(set(result.keys()), {"20260101", "20260102"})
        self.assertEqual(len(result["20260101"]), 2)
        self.assertEqual(len(result["20260102"]), 1)

    def test_get_trials_for_sessions_empty_db_result_returns_empty_dict(self):
        with mock.patch.object(self.data, "Chipmunk", _QueryChain([])):
            result = self.data.get_trials_for_sessions("subject-a", ("20260101",))

        self.assertEqual(result, {})

    # -- get_wait_medians_for_sessions (lines 305-334) ------------------------

    def test_get_wait_medians_for_sessions_non_empty_returns_float_per_session(self):
        rows = [
            {"session_name": "20260101", "t_react": 1.5, "t_stim": 1.0},
            {"session_name": "20260101", "t_react": 2.0, "t_stim": 1.2},
            {"session_name": "20260102", "t_react": 1.8, "t_stim": 1.3},
        ]
        with mock.patch.object(self.data, "Chipmunk", _QueryChain(rows)):
            result = self.data.get_wait_medians_for_sessions(
                "subject-a", ("20260101", "20260102")
            )

        self.assertIn("20260101", result)
        self.assertIn("20260102", result)
        self.assertIsInstance(result["20260101"], float)
        self.assertAlmostEqual(result["20260101"], 0.65)

    def test_get_wait_medians_for_sessions_empty_rows_returns_empty_dict(self):
        """Line 314: `if not rows: return {}` — DB query returns no rows."""
        with mock.patch.object(self.data, "Chipmunk", _QueryChain([])):
            result = self.data.get_wait_medians_for_sessions("subject-a", ("20260101",))
        self.assertEqual(result, {})

    def test_get_wait_medians_for_sessions_all_invalid_wait_returns_empty(self):
        # wait = t_react - t_stim; all negative -> mask filters everything out
        rows = [
            {"session_name": "20260101", "t_react": 0.5, "t_stim": 1.5},
        ]
        with mock.patch.object(self.data, "Chipmunk", _QueryChain(rows)):
            result = self.data.get_wait_medians_for_sessions("subject-a", ("20260101",))

        self.assertEqual(result, {})

    # -- multisession_metrics: start_date branch (lines 684-686) --------------

    def test_multisession_metrics_with_start_date_filters_to_that_date(self):
        # Sessions span Jan 1-10; start_date=Jan 5 should keep only Jan 1-5.
        df = _make_subject_dataframe()
        with (
            mock.patch.object(self.data, "get_subject_data", return_value=df),
            mock.patch.object(
                self.data, "get_wait_medians_for_sessions", return_value={}
            ),
            mock.patch.object(self.data, "get_subject_water", return_value={}),
        ):
            result = self.data.multisession_metrics(
                "subject-a", sessions_back=10, start_date="2026-01-05"
            )

        self.assertIsNotNone(result)
        # Only Jan 1-5 pass the <= filter; sessions_back=10 keeps all 5.
        self.assertEqual(len(result["x"]), 5)

    def test_multisession_metrics_keeps_same_day_sessions_distinct_on_x_axis(self):
        df = pd.DataFrame(
            {
                "session_name": [
                    "20260105_090000",
                    "20260105_150000",
                    "20260106_120000",
                ],
                "performance_easy": [0.6, 0.7, 0.8],
                "n_with_choice": [60, 65, 70],
                "response_values": [[-1, 1]] * 3,
                "initiation_times": [[0.5, 0.6]] * 3,
                "reaction_times": [[0.2, 0.3]] * 3,
            }
        )
        with (
            mock.patch.object(self.data, "get_subject_data", return_value=df),
            mock.patch.object(
                self.data, "get_wait_medians_for_sessions", return_value={}
            ),
            mock.patch.object(self.data, "get_subject_water", return_value={}),
        ):
            result = self.data.multisession_metrics("subject-a", sessions_back=10)

        self.assertIsNotNone(result)
        self.assertEqual(
            result["x"],
            [
                "2026-01-05 09:00:00",
                "2026-01-05 15:00:00",
                "2026-01-06 12:00:00",
            ],
        )
        self.assertEqual(
            result["session_dates"],
            [
                "2026-01-05 09:00:00",
                "2026-01-05 15:00:00",
                "2026-01-06 12:00:00",
            ],
        )

    # -- multisession_metrics: side_bias no-choice path (line 730) ------------

    def test_multisession_metrics_side_bias_is_nan_when_no_choices(self):
        df = _make_subject_dataframe().copy()
        # All response values are 0 → not in [-1, 1] → n_choice = 0 → nan bias
        df["response_values"] = [[0, 0, 0, 0]] * len(df)
        with (
            mock.patch.object(self.data, "get_subject_data", return_value=df),
            mock.patch.object(
                self.data, "get_wait_medians_for_sessions", return_value={}
            ),
            mock.patch.object(self.data, "get_subject_water", return_value={}),
        ):
            result = self.data.multisession_metrics("subject-a", sessions_back=5)

        self.assertIsNotNone(result)
        for v in result["side_bias"]:
            self.assertTrue(math.isnan(v), f"expected NaN but got {v}")

    # -- multisession_metrics: None reaction_times path (lines 741-742) -------

    def test_multisession_metrics_median_rt_is_nan_when_reaction_times_is_none(self):
        df = _make_subject_dataframe().copy()
        df["reaction_times"] = [None] * len(df)
        with (
            mock.patch.object(self.data, "get_subject_data", return_value=df),
            mock.patch.object(
                self.data, "get_wait_medians_for_sessions", return_value={}
            ),
            mock.patch.object(self.data, "get_subject_water", return_value={}),
        ):
            result = self.data.multisession_metrics("subject-a", sessions_back=5)

        self.assertIsNotNone(result)
        for v in result["median_rt"]:
            self.assertTrue(math.isnan(v), f"expected NaN but got {v}")
