import importlib
import sys
import types
import unittest
from unittest import mock


class _ComponentNamespace:
    def __getattr__(self, name):
        def _factory(*args, **kwargs):
            return {"component": name, "args": args, "kwargs": kwargs}

        return _factory


class _IO:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class _Figure:
    def __init__(self) -> None:
        self.layout = {}
        self.traces = []
        self.hlines = []
        self.vlines = []

    def update_layout(self, **kw) -> None:
        self.layout.update(kw)

    def add_trace(self, trace) -> None:
        self.traces.append(trace)

    def add_hline(self, **kw) -> None:
        self.hlines.append(kw)

    def add_vline(self, **kw) -> None:
        self.vlines.append(kw)


class _Dash:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs
        self.layout = None
        self.callbacks = {}

    def callback(self, *cb_args, **cb_kwargs):
        def _decorator(func):
            self.callbacks[func.__name__] = func
            return func

        return _decorator


def _import_app_module():
    sys.modules.pop("chipmunk_dashboard.app", None)

    fake_numpy = types.ModuleType("numpy")
    fake_numpy.ndarray = object
    fake_numpy.median = lambda values: values[0] if values else 0

    fake_dash = types.ModuleType("dash")
    fake_dash.Dash = _Dash
    fake_dash.dcc = _ComponentNamespace()
    fake_dash.html = _ComponentNamespace()
    fake_dash.Input = _IO
    fake_dash.Output = _IO

    fake_plotly = types.ModuleType("plotly")
    fake_plotly.__path__ = []
    fake_go = types.ModuleType("plotly.graph_objects")
    fake_go.Figure = _Figure
    fake_px = types.ModuleType("plotly.express")
    fake_px.colors = types.SimpleNamespace(
        qualitative=types.SimpleNamespace(Plotly=["#1f77b4", "#ff7f0e", "#2ca02c"])
    )

    fake_data = types.ModuleType("chipmunk_dashboard.data")
    fake_data.get_all_subjects = mock.Mock(return_value=["subject-a", "subject-b"])
    fake_data.get_subjects_with_recent_sessions = mock.Mock(return_value=set())
    fake_data.get_sessions = mock.Mock(return_value=[])
    fake_data.session_metrics = mock.Mock(return_value=None)
    fake_data.multisession_metrics = mock.Mock(return_value=None)
    fake_data.prewarm_multisession_cache = mock.Mock()

    with mock.patch.dict(
        sys.modules,
        {
            "numpy": fake_numpy,
            "dash": fake_dash,
            "plotly": fake_plotly,
            "plotly.graph_objects": fake_go,
            "plotly.express": fake_px,
            "chipmunk_dashboard.data": fake_data,
        },
    ):
        module = importlib.import_module("chipmunk_dashboard.app")
    return module


class TestAppUtilities(unittest.TestCase):
    def setUp(self) -> None:
        self.addCleanup(lambda: sys.modules.pop("chipmunk_dashboard.app", None))
        self.appmod = _import_app_module()

    def test_empty_fig_builds_placeholder_annotation(self) -> None:
        fig = self.appmod._empty_fig("No data")
        self.assertEqual(fig.layout["annotations"][0]["text"], "No data")
        self.assertFalse(fig.layout["xaxis"]["visible"])
        self.assertFalse(fig.layout["yaxis"]["visible"])

    def test_layout_wraps_title_and_applies_overrides(self) -> None:
        fig = self.appmod.go.Figure()
        self.appmod._layout(fig, title="Title", xaxis_title="x-axis")
        self.assertEqual(fig.layout["title"]["text"], "Title")
        self.assertEqual(fig.layout["xaxis_title"], "x-axis")
        self.assertEqual(fig.layout["font"]["color"], self.appmod._THEME["text"])

    def test_perf_log_skips_when_disabled(self) -> None:
        with (
            mock.patch.object(self.appmod, "_PROFILE_PERF", False),
            mock.patch.object(self.appmod._LOGGER, "info") as log_info,
        ):
            self.appmod._perf_log("metric", 0.0, key="value")
        log_info.assert_not_called()

    def test_perf_log_emits_when_enabled(self) -> None:
        with (
            mock.patch.object(self.appmod, "_PROFILE_PERF", True),
            mock.patch.object(self.appmod.time, "perf_counter", return_value=2.5),
            mock.patch.object(self.appmod._LOGGER, "info") as log_info,
        ):
            self.appmod._perf_log("metric", 2.0, key="value")
        log_info.assert_called_once()
        msg = log_info.call_args[0][0]
        self.assertIn("perf metric", msg)
        self.assertIn("key=value", msg)

    def test_update_date_options_handles_empty_and_valid_sessions(self) -> None:
        app = self.appmod.create_app()
        update_date_options = app.callbacks["_update_date_options"]

        self.assertEqual(update_date_options([], 0), (None, None, None, None))

        with (
            mock.patch.object(
                self.appmod,
                "get_sessions",
                return_value=["20260101_010101", "20260103_010101", "bad"],
            ),
            mock.patch.object(self.appmod, "prewarm_multisession_cache") as prewarm,
        ):
            result = update_date_options(["subject-a"], 0)

        self.assertEqual(
            result, ("2026-01-03", "2026-01-01", "2026-01-03", "2026-01-03")
        )
        prewarm.assert_called_once_with(
            ["subject-a"], sessions_back=30, start_date="2026-01-03"
        )

    def test_update_time_options_filters_and_defaults_to_latest(self) -> None:
        app = self.appmod.create_app()
        update_time_options = app.callbacks["_update_time_options"]

        self.assertEqual(update_time_options(None, ["subject-a"]), ([], None))

        with mock.patch.object(
            self.appmod,
            "get_sessions",
            return_value=[
                "20260102_010101",
                "20260102_120000",
                "20260103_000000",
                "20260102_BAD",
            ],
        ):
            options, value = update_time_options("2026-01-02", ["subject-a"])

        self.assertEqual(len(options), 3)
        self.assertEqual(options[0]["label"], "01:01:01")
        self.assertEqual(options[1]["label"], "12:00:00")
        self.assertEqual(options[2]["label"], "20260102_BAD")
        self.assertEqual(value, "20260102_BAD")

    def test_clear_subjects_callback_returns_empty_list(self) -> None:
        app = self.appmod.create_app()
        clear_subjects = app.callbacks["_clear_subjects"]
        self.assertEqual(clear_subjects(1), [])

    def test_update_subject_options_prioritizes_recent_subjects(self) -> None:
        app = self.appmod.create_app()
        update_subject_options = app.callbacks["_update_subject_options"]

        with (
            mock.patch.object(
                self.appmod, "get_all_subjects", return_value=["subject-a", "subject-b"]
            ),
            mock.patch.object(
                self.appmod,
                "get_subjects_with_recent_sessions",
                return_value={"subject-b"},
            ),
        ):
            options = update_subject_options(1)

        self.assertEqual(
            options,
            [
                {"label": "★ subject-b", "value": "subject-b"},
                {"label": "subject-a", "value": "subject-a"},
            ],
        )

    def test_update_single_returns_empty_figures_when_no_valid_subjects(self) -> None:
        app = self.appmod.create_app()
        update_single = app.callbacks["_update_single"]

        with mock.patch.object(self.appmod, "get_sessions", return_value=[]):
            figures = update_single("subject-a", None, 0)

        self.assertEqual(len(figures), 10)
        self.assertEqual(
            figures[0].layout["annotations"][0]["text"], "Select subject(s)"
        )

    def test_update_multi_returns_empty_figures_when_no_subjects(self) -> None:
        app = self.appmod.create_app()
        update_multi = app.callbacks["_update_multi"]
        figures = update_multi([], 10, None, [], 3, 0)
        self.assertEqual(len(figures), 8)
        self.assertEqual(
            figures[0].layout["annotations"][0]["text"], "Select subject(s)"
        )

    def test_update_date_options_returns_none_when_sessions_empty(self) -> None:
        app = self.appmod.create_app()
        update_date_options = app.callbacks["_update_date_options"]
        with mock.patch.object(self.appmod, "get_sessions", return_value=[]):
            result = update_date_options(["subject-a"], 0)
        self.assertEqual(result, (None, None, None, None))

    def test_update_date_options_returns_none_when_all_sessions_too_short(self) -> None:
        app = self.appmod.create_app()
        update_date_options = app.callbacks["_update_date_options"]
        with mock.patch.object(self.appmod, "get_sessions", return_value=["short"]):
            result = update_date_options(["subject-a"], 0)
        self.assertEqual(result, (None, None, None, None))

    def test_update_time_options_returns_empty_when_no_sessions_on_date(self) -> None:
        app = self.appmod.create_app()
        update_time_options = app.callbacks["_update_time_options"]
        with mock.patch.object(
            self.appmod, "get_sessions", return_value=["20260103_010101"]
        ):
            result = update_time_options("2026-01-02", ["subject-a"])
        self.assertEqual(result, ([], None))

    def test_update_time_options_handles_session_without_underscore(self) -> None:
        app = self.appmod.create_app()
        update_time_options = app.callbacks["_update_time_options"]
        with mock.patch.object(self.appmod, "get_sessions", return_value=["20260102"]):
            options, value = update_time_options("2026-01-02", ["subject-a"])
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]["label"], "20260102")
        self.assertEqual(value, "20260102")
