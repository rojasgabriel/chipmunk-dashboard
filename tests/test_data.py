import importlib
import sys
import types
import unittest
from unittest import mock


def _import_data_module():
    sys.modules.pop("chipmunk_dashboard.data", None)

    fake_labdata = types.ModuleType("labdata")
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

    fake_numpy = types.ModuleType("numpy")
    fake_numpy.ndarray = object
    fake_numpy.nan = float("nan")

    fake_pandas = types.ModuleType("pandas")

    class _DataFrame:
        pass

    fake_pandas.DataFrame = _DataFrame

    with mock.patch.dict(
        sys.modules,
        {
            "labdata": fake_labdata,
            "labdata.schema": fake_schema,
            "chipmunk": fake_chipmunk,
            "numpy": fake_numpy,
            "pandas": fake_pandas,
        },
    ):
        module = importlib.import_module("chipmunk_dashboard.data")
    return module


class _Cacheable:
    def __init__(self) -> None:
        self.cache_clear = mock.Mock()


class _ImmediateThread:
    created = []

    def __init__(self, target, daemon):
        self.target = target
        self.daemon = daemon
        self.started = False
        _ImmediateThread.created.append(self)

    def start(self):
        self.started = True
        self.target()


class _DeferredThread:
    created = []

    def __init__(self, target, daemon):
        self.target = target
        self.daemon = daemon
        self.started = False
        _DeferredThread.created.append(self)

    def start(self):
        self.started = True


class TestDataUtilities(unittest.TestCase):
    def setUp(self) -> None:
        self.data = _import_data_module()

    def test_ttl_lru_cache_reuses_value_within_bucket_and_expires(self) -> None:
        calls = {"count": 0}

        @self.data._ttl_lru_cache(maxsize=8, ttl_seconds=10)
        def cached(x):
            calls["count"] += 1
            return x * 2

        with mock.patch.object(self.data.time, "time", return_value=5):
            self.assertEqual(cached(3), 6)
            self.assertEqual(cached(3), 6)
        self.assertEqual(calls["count"], 1)

        with mock.patch.object(self.data.time, "time", return_value=25):
            self.assertEqual(cached(3), 6)
        self.assertEqual(calls["count"], 2)

        cached.cache_clear()
        with mock.patch.object(self.data.time, "time", return_value=25):
            self.assertEqual(cached(3), 6)
        self.assertEqual(calls["count"], 3)

    def test_clear_data_cache_clears_all_registered_caches(self) -> None:
        attrs = [
            "get_all_subjects",
            "get_subject_data",
            "get_session_trials",
            "get_subject_water",
            "get_trials_for_sessions",
            "get_wait_medians_for_sessions",
            "get_sessions",
            "session_metrics",
            "multisession_metrics",
        ]
        fakes = {name: _Cacheable() for name in attrs}

        with (
            mock.patch.multiple(self.data, **fakes),
        ):
            self.data.clear_data_cache()

        for fake in fakes.values():
            fake.cache_clear.assert_called_once()

    def test_prewarm_multisession_cache_deduplicates_inflight_requests(self) -> None:
        _DeferredThread.created = []
        self.data._PREWARM_INFLIGHT.clear()

        with mock.patch.object(self.data, "_PREWARM_ENABLED", True), mock.patch.object(
            self.data.threading, "Thread", _DeferredThread
        ):
            self.data.prewarm_multisession_cache(["b", "a"], sessions_back=7, start_date="2026-01-01")
            self.data.prewarm_multisession_cache(["a", "b"], sessions_back=7, start_date="2026-01-01")

        self.assertEqual(len(_DeferredThread.created), 1)
        key = (("a", "b"), 7, "2026-01-01")
        self.assertIn(key, self.data._PREWARM_INFLIGHT)

    def test_prewarm_multisession_cache_worker_runs_and_clears_inflight(self) -> None:
        _ImmediateThread.created = []
        self.data._PREWARM_INFLIGHT.clear()

        with (
            mock.patch.object(self.data, "_PREWARM_ENABLED", True),
            mock.patch.object(self.data.threading, "Thread", _ImmediateThread),
            mock.patch.object(self.data, "multisession_metrics") as multisession_metrics,
        ):
            self.data.prewarm_multisession_cache(
                ["s2", "s1", "s1"], sessions_back=4, start_date="2026-03-05"
            )

        multisession_metrics.assert_has_calls(
            [
                mock.call("s1", 4, "2026-03-05", False, 3),
                mock.call("s2", 4, "2026-03-05", False, 3),
            ]
        )
        self.assertEqual(multisession_metrics.call_count, 2)
        self.assertEqual(self.data._PREWARM_INFLIGHT, set())

    def test_prewarm_multisession_cache_noops_when_disabled_or_empty(self) -> None:
        _ImmediateThread.created = []
        self.data._PREWARM_INFLIGHT.clear()

        with mock.patch.object(self.data.threading, "Thread", _ImmediateThread):
            with mock.patch.object(self.data, "_PREWARM_ENABLED", False):
                self.data.prewarm_multisession_cache(["x"])
            self.data.prewarm_multisession_cache([])

        self.assertEqual(len(_ImmediateThread.created), 0)
        self.assertEqual(self.data._PREWARM_INFLIGHT, set())
