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
import sys
import types
import unittest
from unittest import mock

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, html


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
    fake_data.session_metrics = mock.Mock(return_value=None)
    fake_data.multisession_metrics = mock.Mock(return_value=None)
    fake_data.prewarm_multisession_cache = mock.Mock()

    patches = {**_fake_db_modules(), "chipmunk_dashboard.data": fake_data}
    with mock.patch.dict(sys.modules, patches):
        module = importlib.import_module("chipmunk_dashboard.app")
    return module


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
        with mock.patch.object(self.data, "get_session_trials", return_value=trials):
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
            "init_times",
            "init_trial_nums",
            "init_roll_x",
            "init_roll_y",
            "wait_times",
            "wait_min_times",
            "wait_delta_times",
            "wait_trial_nums",
            "wait_delta_x",
            "wait_delta_y",
            "slide_x",
            "slide_y",
            "ew_roll_x",
            "ew_roll_y",
        }
        self.assertEqual(set(result.keys()), expected_keys)

    def test_session_metrics_all_values_are_plain_lists(self):
        trials = _make_trial_dataframe()
        with mock.patch.object(self.data, "get_session_trials", return_value=trials):
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
