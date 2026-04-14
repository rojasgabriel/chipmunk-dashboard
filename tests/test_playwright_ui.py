"""Playwright-based browser smoke and screenshot regression tests."""

from __future__ import annotations

import json
import importlib
import os
import sys
import threading
import time
import types
import urllib.request
from contextlib import ExitStack
from io import BytesIO
from pathlib import Path
from unittest import mock

import pytest
import numpy as np
from PIL import Image
from werkzeug.serving import make_server

if os.getenv("RUN_PLAYWRIGHT") != "1":
    pytest.skip(
        "Playwright tests are disabled. Set RUN_PLAYWRIGHT=1 to enable.",
        allow_module_level=True,
    )


HASH_FILE = Path(__file__).with_name("playwright_layout_hashes.json")
HASH_BITS = 16  # 16x16 = 256-bit dHash
MAX_HASH_DISTANCE = 42


def _load_hashes() -> dict[str, str]:
    if not HASH_FILE.exists():
        return {}
    return json.loads(HASH_FILE.read_text())


def _save_hashes(hashes: dict[str, str]) -> None:
    HASH_FILE.write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")


def _dhash(png_bytes: bytes, hash_bits: int = HASH_BITS) -> int:
    img = Image.open(BytesIO(png_bytes)).convert("L")
    img = img.resize((hash_bits + 1, hash_bits), Image.Resampling.LANCZOS)
    pixels = np.asarray(img, dtype=np.uint8)

    value = 0
    for row in range(hash_bits):
        for col in range(hash_bits):
            left = int(pixels[row, col])
            right = int(pixels[row, col + 1])
            value = (value << 1) | int(right > left)
    return value


def _hamming_distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def _assert_layout_hash(name: str, png_bytes: bytes) -> None:
    current = _dhash(png_bytes)
    hashes = _load_hashes()

    if os.getenv("UPDATE_PLAYWRIGHT_HASHES") == "1":
        hashes[name] = f"{current:064x}"
        _save_hashes(hashes)
        pytest.skip(f"Updated screenshot hash baseline for {name}.")

    if name not in hashes:
        pytest.fail(
            f"Missing screenshot hash baseline for '{name}'. "
            "Run with UPDATE_PLAYWRIGHT_HASHES=1 to generate baselines."
        )

    expected = int(hashes[name], 16)
    distance = _hamming_distance(current, expected)
    assert distance <= MAX_HASH_DISTANCE, (
        f"Screenshot regression for '{name}': hamming distance {distance} "
        f"(allowed <= {MAX_HASH_DISTANCE})"
    )


def _session_metrics_payload() -> dict:
    trial_nums = list(range(1, 61))
    roll_x = list(range(10, 51, 5))
    iti_roll_x = list(range(13, 49, 5))

    init_times = [0.35 + (i % 10) * 0.02 for i in range(60)]
    wait_times = [0.85 + (i % 8) * 0.04 for i in range(60)]
    wait_delta = [0.18 + (i % 7) * 0.015 for i in range(60)]
    response_times = [0.18 + (i % 9) * 0.018 for i in range(60)]
    iti_times = [0.7 + (i % 11) * 0.08 for i in range(59)]

    left_trials = trial_nums[::2]
    right_trials = trial_nums[1::2]

    return {
        "stims": [-2.0, -1.0, 0.0, 1.0, 2.0],
        "n_correct": [4, 8, 12, 14, 18],
        "n_incorrect": [12, 8, 6, 4, 2],
        "n_ew": [2, 2, 2, 2, 2],
        "n_no_choice": [1, 1, 1, 1, 1],
        "p_right": [0.1, 0.28, 0.5, 0.72, 0.9],
        "median_rt": [0.36, 0.33, 0.29, 0.26, 0.24],
        "slide_x": roll_x,
        "slide_y": [0.55, 0.58, 0.6, 0.63, 0.66, 0.68, 0.7, 0.71, 0.73],
        "ew_roll_x": roll_x,
        "ew_roll_y": [0.18, 0.16, 0.14, 0.15, 0.12, 0.11, 0.1, 0.09, 0.08],
        "init_trial_nums": trial_nums,
        "init_times": init_times,
        "init_roll_x": roll_x,
        "init_roll_y": [0.5, 0.52, 0.54, 0.55, 0.57, 0.58, 0.6, 0.61, 0.63],
        "wait_delta_times": wait_delta,
        "wait_trial_nums": trial_nums,
        "wait_delta_x": roll_x,
        "wait_delta_y": [0.2, 0.22, 0.23, 0.24, 0.23, 0.22, 0.21, 0.2, 0.19],
        "wait_delta_left_times": wait_delta[::2],
        "wait_delta_right_times": wait_delta[1::2],
        "wait_trial_nums_left": left_trials,
        "wait_trial_nums_right": right_trials,
        "wait_delta_left_x": roll_x,
        "wait_delta_left_y": [0.19, 0.2, 0.21, 0.22, 0.21, 0.2, 0.2, 0.19, 0.18],
        "wait_delta_right_x": roll_x,
        "wait_delta_right_y": [0.21, 0.23, 0.24, 0.25, 0.24, 0.23, 0.22, 0.21, 0.2],
        "wait_times": wait_times,
        "wait_roll_x": roll_x,
        "wait_roll_y": [0.95, 0.96, 0.98, 1.0, 1.01, 1.03, 1.04, 1.05, 1.06],
        "wait_times_left": wait_times[::2],
        "wait_times_right": wait_times[1::2],
        "wait_left_x": roll_x,
        "wait_left_y": [0.92, 0.94, 0.95, 0.97, 0.99, 1.0, 1.01, 1.02, 1.03],
        "wait_right_x": roll_x,
        "wait_right_y": [0.98, 0.99, 1.0, 1.02, 1.03, 1.05, 1.06, 1.07, 1.08],
        "rts": [0.2 + (i % 8) * 0.02 for i in range(60)],
        "rt_trial_nums": trial_nums,
        "rt_vals": [0.2 + (i % 7) * 0.018 for i in range(60)],
        "rt_roll_x": roll_x,
        "rt_roll_y": [0.24, 0.25, 0.25, 0.26, 0.26, 0.27, 0.27, 0.28, 0.28],
        "response_times": response_times,
        "response_times_left": response_times[::2],
        "response_times_right": response_times[1::2],
        "session_settings_lines": [
            "trials: 60",
            "rewarded modality: audio",
            "audio stim range: 5.00 to 15.00",
            "visual stim range: 5.00 to 15.00",
        ],
        "water_side_totals": [18, 20, 38],
        "iti_times": iti_times,
        "iti_times_after_correct": iti_times[:16],
        "iti_times_after_incorrect": iti_times[16:32],
        "iti_times_after_ew": iti_times[32:45],
        "iti_times_after_no_choice": iti_times[45:59],
        "iti_roll_x": iti_roll_x,
        "iti_roll_y": [0.95, 0.98, 1.0, 1.03, 1.01, 0.99, 1.02, 1.04],
        "iti_roll_correct_x": iti_roll_x,
        "iti_roll_correct_y": [0.88, 0.9, 0.92, 0.94, 0.95, 0.96, 0.98, 1.0],
        "iti_roll_incorrect_x": iti_roll_x,
        "iti_roll_incorrect_y": [1.05, 1.08, 1.1, 1.09, 1.07, 1.06, 1.08, 1.1],
        "iti_roll_ew_x": iti_roll_x,
        "iti_roll_ew_y": [0.99, 1.0, 1.01, 1.02, 1.03, 1.02, 1.01, 1.0],
        "iti_roll_no_choice_x": iti_roll_x,
        "iti_roll_no_choice_y": [0.9, 0.92, 0.94, 0.95, 0.96, 0.95, 0.94, 0.93],
        "trial_count_x": [2.5, 7.5, 12.5, 17.5],
        "trial_count_y": [24.0, 19.0, 15.0, 10.0],
    }


def _multisession_metrics_payload() -> dict:
    x = [float(v) for v in range(-9, 1)]
    return {
        "x": x,
        "perf_easy": [0.55, 0.57, 0.6, 0.62, 0.61, 0.63, 0.65, 0.66, 0.68, 0.7],
        "ew_rate": [0.2, 0.19, 0.17, 0.16, 0.15, 0.14, 0.14, 0.13, 0.12, 0.11],
        "n_with_choice": [60, 64, 67, 70, 72, 74, 78, 81, 84, 88],
        "side_bias": [0.0, 0.03, 0.01, -0.01, -0.03, -0.02, 0.0, 0.01, 0.02, 0.01],
        "median_init": [0.8, 0.79, 0.78, 0.77, 0.78, 0.77, 0.76, 0.75, 0.75, 0.74],
        "median_rt": [0.32, 0.31, 0.3, 0.3, 0.29, 0.29, 0.28, 0.28, 0.27, 0.27],
        "median_wait": [1.1, 1.09, 1.08, 1.06, 1.07, 1.05, 1.04, 1.03, 1.02, 1.0],
        "water": [1.2, 1.4, 1.3, 1.5, 1.6, 1.4, 1.7, 1.8, 1.9, 2.0],
    }


def _wait_for_server(url: str, timeout_s: float = 8.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5):
                return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError(f"Timed out waiting for test server at {url}")


@pytest.fixture(scope="session")
def dashboard_url():
    sys.modules.pop("chipmunk_dashboard.app", None)

    fake_data = types.ModuleType("chipmunk_dashboard.data")
    fake_data.get_all_subjects = lambda: ["subject-a", "subject-b"]
    fake_data.get_subjects_with_recent_sessions = lambda: {"subject-a"}
    fake_data.get_sessions = lambda _subject: ["20260101_090000", "20260101_120000"]
    fake_data.get_subjects_for_date = lambda _raw_date: ["subject-a", "subject-b"]
    fake_data.session_metrics = lambda _subj, _ses: _session_metrics_payload()
    fake_data.multisession_metrics = lambda *_args, **_kwargs: (
        _multisession_metrics_payload()
    )
    fake_data.prewarm_multisession_cache = lambda *_args, **_kwargs: None

    with ExitStack() as stack:
        stack.enter_context(
            mock.patch.dict(sys.modules, {"chipmunk_dashboard.data": fake_data})
        )
        appmod = importlib.import_module("chipmunk_dashboard.app")
        app = appmod.create_app()
        server = make_server("127.0.0.1", 8051, app.server)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            _wait_for_server("http://127.0.0.1:8051")
            yield "http://127.0.0.1:8051"
        finally:
            server.shutdown()
            thread.join(timeout=5)
            sys.modules.pop("chipmunk_dashboard.app", None)


def _open_dashboard_with_subject(page, dashboard_url: str) -> None:
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(dashboard_url, wait_until="networkidle")
    page.wait_for_selector("#subjects-recent input[type='checkbox']", timeout=10000)
    page.locator("#subjects-recent input[type='checkbox']").first.check(force=True)
    page.wait_for_selector("#frac-correct .main-svg", timeout=10000)


def _open_single_session_tab(page, label: str) -> None:
    page.locator("#single-session-tabs").locator(f"text={label}").first.click()


def test_dashboard_functional_smoke(page, dashboard_url):
    _open_dashboard_with_subject(page, dashboard_url)

    _open_single_session_tab(page, "Timing")
    page.wait_for_selector("#iti-rolling .main-svg", timeout=10000)
    assert page.locator("#iti-rolling").is_visible()

    older_checkbox = page.locator("#subjects-older input[type='checkbox']").first
    older_checkbox.check(force=True)
    page.wait_for_selector("#iti-rolling .main-svg", timeout=10000)
    assert older_checkbox.is_checked()


def test_overview_layout_hash_regression(page, dashboard_url):
    _open_dashboard_with_subject(page, dashboard_url)
    _open_single_session_tab(page, "Overview")
    page.wait_for_timeout(300)
    screenshot = page.locator(".dashboard-main").screenshot(type="png")
    _assert_layout_hash("single_overview", screenshot)


def test_timing_layout_hash_regression(page, dashboard_url):
    _open_dashboard_with_subject(page, dashboard_url)
    _open_single_session_tab(page, "Timing")
    page.wait_for_selector("#iti-rolling .main-svg", timeout=10000)
    page.wait_for_timeout(300)
    screenshot = page.locator(".dashboard-main").screenshot(type="png")
    _assert_layout_hash("single_timing", screenshot)
