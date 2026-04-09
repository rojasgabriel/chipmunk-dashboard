import os
import sys
import types
import unittest
from unittest import mock

from chipmunk_dashboard import cli


class _FakeApp:
    def __init__(self) -> None:
        self.run = mock.Mock()


class TestCli(unittest.TestCase):
    def _install_fake_app_module(self, app: _FakeApp) -> None:
        fake_mod = types.ModuleType("chipmunk_dashboard.app")
        fake_mod.create_app = mock.Mock(return_value=app)
        self._patcher = mock.patch.dict(sys.modules, {"chipmunk_dashboard.app": fake_mod})
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

    def test_main_without_command_prints_help(self) -> None:
        with mock.patch.object(sys, "argv", ["chipmunk-dashboard"]), mock.patch(
            "argparse.ArgumentParser.print_help"
        ) as print_help:
            cli.main()
        print_help.assert_called_once()

    def test_run_command_starts_server_without_opening_browser_when_no_open(self) -> None:
        app = _FakeApp()
        self._install_fake_app_module(app)

        with (
            mock.patch.object(
                sys, "argv", ["chipmunk-dashboard", "run", "--no-open", "--port", "9000"]
            ),
            mock.patch("chipmunk_dashboard.cli.webbrowser.open") as open_browser,
            mock.patch("chipmunk_dashboard.cli.threading.Timer") as timer_cls,
        ):
            cli.main()

        open_browser.assert_not_called()
        timer_cls.assert_not_called()
        app.run.assert_called_once_with(host="localhost", port=9000, debug=False)

    def test_run_command_opens_browser_in_debug_reloader_child(self) -> None:
        app = _FakeApp()
        self._install_fake_app_module(app)
        timer_instance = mock.Mock()

        with (
            mock.patch.dict(os.environ, {"WERKZEUG_RUN_MAIN": "true"}, clear=False),
            mock.patch.object(
                sys, "argv", ["chipmunk-dashboard", "run", "--debug", "--host", "0.0.0.0"]
            ),
            mock.patch("chipmunk_dashboard.cli.threading.Timer", return_value=timer_instance) as timer_cls,
        ):
            cli.main()

        timer_cls.assert_called_once()
        timer_instance.start.assert_called_once()
        app.run.assert_called_once_with(host="0.0.0.0", port=8050, debug=True)

