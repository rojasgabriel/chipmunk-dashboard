"""Fixture-backed data provider for database-free UI debugging."""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache


_SUBJECTS = ["GRB050", "GRB058", "GRB059", "GRB061", "GRB062", "GRB063"]
_RECENT = {"GRB050", "GRB058", "GRB059"}
_BASE_DATE = date(2026, 5, 22)


def _subject_offset(subject: str) -> int:
    return sum(ord(ch) for ch in subject) % 7


@lru_cache(maxsize=1)
def get_all_subjects() -> list[str]:
    """Return fixture subject names without touching the database."""
    return list(_SUBJECTS)


@lru_cache(maxsize=1)
def get_subjects_with_recent_sessions(days: int = 7) -> set[str]:
    """Return fixture subjects marked as recent."""
    return set(_RECENT)


@lru_cache(maxsize=64)
def get_sessions(subject: str) -> list[str]:
    """Return deterministic fixture sessions for a subject."""
    offset = _subject_offset(subject)
    sessions = []
    for day_back in range(12, -1, -1):
        session_date = _BASE_DATE - timedelta(days=day_back)
        hour = 9 + ((offset + day_back) % 6)
        minute = (offset * 7 + day_back * 3) % 60
        sessions.append(f"{session_date:%Y%m%d}_{hour:02d}{minute:02d}17")
    return sessions


@lru_cache(maxsize=32)
def get_subjects_for_date(raw_date: str) -> list[str]:
    """Return fixture subjects with a session on ``YYYYMMDD``."""
    return [
        subject
        for subject in _SUBJECTS
        if any(s.startswith(raw_date) for s in get_sessions(subject))
    ]


@lru_cache(maxsize=128)
def session_metrics(subject: str, session_name: str) -> dict:
    """Return synthetic single-session metrics that exercise the UI."""
    offset = _subject_offset(subject)
    trial_nums = list(range(1, 81))
    roll_x = list(range(10, 76, 5))
    iti_roll_x = list(range(13, 74, 5))

    init_times = [0.35 + ((idx + offset) % 10) * 0.02 for idx in range(80)]
    wait_times = [0.85 + ((idx + offset) % 8) * 0.04 for idx in range(80)]
    wait_delta = [0.18 + ((idx + offset) % 7) * 0.015 for idx in range(80)]
    response_times = [0.18 + ((idx + offset) % 9) * 0.018 for idx in range(80)]
    iti_times = [0.7 + ((idx + offset) % 11) * 0.08 for idx in range(79)]
    left_trials = trial_nums[::2]
    right_trials = trial_nums[1::2]

    return {
        "stims": [-8.0, -4.0, 0.0, 4.0, 8.0],
        "n_correct": [5 + offset, 10, 13, 17, 22],
        "n_incorrect": [18, 11, 7, 5, 3 + offset],
        "n_ew": [2, 2, 3, 2, 2],
        "n_no_choice": [1, 1, 1, 1, 1],
        "p_right": [0.08, 0.22, 0.5, 0.78, 0.92],
        "median_rt": [0.38, 0.34, 0.3, 0.27, 0.25],
        "slide_x": roll_x,
        "slide_y": [0.55 + idx * 0.015 for idx, _ in enumerate(roll_x)],
        "ew_roll_x": roll_x,
        "ew_roll_y": [0.18 - min(idx * 0.007, 0.09) for idx, _ in enumerate(roll_x)],
        "init_trial_nums": trial_nums,
        "init_times": init_times,
        "init_roll_x": roll_x,
        "init_roll_y": [0.5 + idx * 0.01 for idx, _ in enumerate(roll_x)],
        "wait_delta_times": wait_delta,
        "wait_trial_nums": trial_nums,
        "wait_delta_x": roll_x,
        "wait_delta_y": [
            0.2 + ((idx + offset) % 5) * 0.01 for idx, _ in enumerate(roll_x)
        ],
        "wait_delta_left_times": wait_delta[::2],
        "wait_delta_right_times": wait_delta[1::2],
        "wait_trial_nums_left": left_trials,
        "wait_trial_nums_right": right_trials,
        "wait_delta_left_x": roll_x,
        "wait_delta_left_y": [0.18 + idx * 0.003 for idx, _ in enumerate(roll_x)],
        "wait_delta_right_x": roll_x,
        "wait_delta_right_y": [0.22 + idx * 0.003 for idx, _ in enumerate(roll_x)],
        "wait_times": wait_times,
        "wait_roll_x": roll_x,
        "wait_roll_y": [0.95 + idx * 0.01 for idx, _ in enumerate(roll_x)],
        "wait_times_left": wait_times[::2],
        "wait_times_right": wait_times[1::2],
        "wait_left_x": roll_x,
        "wait_left_y": [0.92 + idx * 0.008 for idx, _ in enumerate(roll_x)],
        "wait_right_x": roll_x,
        "wait_right_y": [0.98 + idx * 0.008 for idx, _ in enumerate(roll_x)],
        "rts": response_times,
        "rt_trial_nums": trial_nums,
        "rt_vals": response_times,
        "rt_roll_x": roll_x,
        "rt_roll_y": [0.24 + idx * 0.004 for idx, _ in enumerate(roll_x)],
        "response_trial_nums": trial_nums,
        "response_trial_nums_left": left_trials,
        "response_trial_nums_right": right_trials,
        "response_roll_x": roll_x,
        "response_roll_y": [0.2 + idx * 0.006 for idx, _ in enumerate(roll_x)],
        "response_roll_left_x": roll_x,
        "response_roll_left_y": [0.18 + idx * 0.006 for idx, _ in enumerate(roll_x)],
        "response_roll_right_x": roll_x,
        "response_roll_right_y": [0.22 + idx * 0.006 for idx, _ in enumerate(roll_x)],
        "response_times": response_times,
        "response_times_left": response_times[::2],
        "response_times_right": response_times[1::2],
        "session_settings_lines": [
            "debug fixture data",
            f"session: {session_name}",
            "rewarded modality: audio",
            "audio stim range: 5.00 to 15.00",
            "visual stim range: 5.00 to 15.00",
        ],
        "water_side_totals": [22.0, 24.0, 46.0],
        "water_side_totals_ul": [22.0, 24.0, 46.0],
        "water_cum_x": trial_nums,
        "water_cum_time_x": [float(v - 1) * 0.45 for v in trial_nums],
        "water_cum_total_ul": [float(v) * 5.5 for v in trial_nums],
        "water_cum_left_ul": [float(v) * 2.7 for v in trial_nums],
        "water_cum_right_ul": [float(v) * 2.8 for v in trial_nums],
        "iti_times": iti_times,
        "iti_times_after_correct": iti_times[:22],
        "iti_times_after_incorrect": iti_times[22:44],
        "iti_times_after_ew": iti_times[44:61],
        "iti_times_after_no_choice": iti_times[61:79],
        "iti_roll_x": iti_roll_x,
        "iti_roll_y": [
            0.95 + ((idx + offset) % 4) * 0.02 for idx, _ in enumerate(iti_roll_x)
        ],
        "iti_roll_correct_x": iti_roll_x,
        "iti_roll_correct_y": [0.88 + idx * 0.01 for idx, _ in enumerate(iti_roll_x)],
        "iti_roll_incorrect_x": iti_roll_x,
        "iti_roll_incorrect_y": [
            1.05 + idx * 0.008 for idx, _ in enumerate(iti_roll_x)
        ],
        "iti_roll_ew_x": iti_roll_x,
        "iti_roll_ew_y": [0.99 + idx * 0.004 for idx, _ in enumerate(iti_roll_x)],
        "iti_roll_no_choice_x": iti_roll_x,
        "iti_roll_no_choice_y": [0.9 + idx * 0.004 for idx, _ in enumerate(iti_roll_x)],
        "trial_count_x": [float(v) for v in range(0, 41, 5)],
        "trial_count_trial_nums": list(range(1, 82, 10)),
        "trial_count_y": [6.0, 14.0, 22.0, 28.0, 30.0, 26.0, 18.0, 10.0, 7.0],
    }


@lru_cache(maxsize=128)
def multisession_metrics(
    subject: str,
    sessions_back: int = 10,
    start_date: str | None = None,
    smooth: bool = False,
    smooth_window: int = 3,
) -> dict:
    """Return synthetic multi-session trend metrics for UI debugging."""
    offset = _subject_offset(subject)
    count = max(1, int(sessions_back or 10))
    session_dates = [
        (_BASE_DATE - timedelta(days=count - idx - 1)).isoformat()
        for idx in range(count)
    ]
    x_vals = [
        f"{day}T{9 + ((idx + offset) % 6):02d}:30:00"
        for idx, day in enumerate(session_dates)
    ]
    idx_vals = list(range(count))
    return {
        "x": x_vals,
        "session_dates": session_dates,
        "perf_easy": [0.52 + min(idx * 0.025, 0.35) for idx in idx_vals],
        "ew_rate": [max(0.05, 0.22 - idx * 0.01) for idx in idx_vals],
        "n_with_choice": [55 + idx * 4 + offset for idx in idx_vals],
        "side_bias": [((idx + offset) % 5 - 2) * 0.035 for idx in idx_vals],
        "median_init": [0.82 - min(idx * 0.012, 0.18) for idx in idx_vals],
        "median_rt": [0.34 - min(idx * 0.006, 0.08) for idx in idx_vals],
        "median_wait": [1.1 - min(idx * 0.012, 0.18) for idx in idx_vals],
        "water": [1.1 + idx * 0.08 + offset * 0.02 for idx in idx_vals],
        "training_time_hours": [9.5 + ((idx + offset) % 7) * 0.35 for idx in idx_vals],
    }


def prewarm_multisession_cache(*_args, **_kwargs) -> None:
    """No-op for fixture-backed UI debugging."""
    return None
