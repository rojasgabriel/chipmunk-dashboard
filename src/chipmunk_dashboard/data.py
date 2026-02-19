"""Data fetching and metric computation."""

from labdata.schema import DecisionTask, Watering  # type: ignore
from chipmunk import Chipmunk  # type: ignore
import pandas as pd
import numpy as np
from functools import lru_cache
from functools import wraps
import threading
import time
import os
import logging

_DB_LOCK = threading.RLock()
_CACHE_TTL_SECONDS = int(os.getenv("CHIPMUNK_CACHE_TTL_SECONDS", "1800"))
_PROFILE_PERF = os.getenv("CHIPMUNK_PROFILE", "0") == "1"
_LOGGER = logging.getLogger(__name__)


def _perf_log(label: str, start_time: float, **fields) -> None:
    if not _PROFILE_PERF:
        return

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    details = " ".join(f"{k}={v}" for k, v in fields.items())
    msg = f"perf {label} elapsed_ms={elapsed_ms:.1f}"
    if details:
        msg = f"{msg} {details}"
    _LOGGER.info(msg)


def _ttl_lru_cache(maxsize: int = 128, ttl_seconds: int = _CACHE_TTL_SECONDS):
    """lru_cache with time-bucketed invalidation."""

    def decorator(func):
        @lru_cache(maxsize=maxsize)
        def _cached(*args, __ttl_bucket: int, **kwargs):
            return func(*args, **kwargs)

        @wraps(func)
        def wrapper(*args, **kwargs):
            ttl_bucket = int(time.time() // ttl_seconds)
            return _cached(*args, __ttl_bucket=ttl_bucket, **kwargs)

        wrapper.cache_clear = _cached.cache_clear
        return wrapper

    return decorator


@_ttl_lru_cache(maxsize=1)
def get_all_subjects() -> list[str]:
    """Return sorted unique subject names from the database."""
    with _DB_LOCK:
        subjects = DecisionTask.TrialSet().fetch("subject_name")
    return sorted(set(subjects))


@_ttl_lru_cache(maxsize=64)
def get_subject_data(subject: str) -> pd.DataFrame:
    """Fetch all trial-set rows for a subject (cached in memory)."""
    start = time.perf_counter()
    fields = [
        "subject_name",
        "session_name",
        "performance_easy",
        "n_with_choice",
        "response_values",
        "initiation_times",
        "reaction_times",
    ]
    with _DB_LOCK:
        rel = DecisionTask.TrialSet() & f"subject_name = '{subject}'"
        try:
            rows = rel.fetch(*fields, order_by="session_name", as_dict=True)
            df = pd.DataFrame(rows)
            _perf_log("get_subject_data", start, subject=subject, rows=len(df))
            return df
        except Exception:
            df = pd.DataFrame(rel)
            _perf_log("get_subject_data_fallback", start, subject=subject, rows=len(df))
            return df


@_ttl_lru_cache(maxsize=64)
def get_session_trials(subject: str, session_name: str) -> pd.DataFrame:
    """Fetch per-trial Chipmunk data for a single session (cached)."""
    restriction = f"subject_name = '{subject}' AND session_name = '{session_name}'"
    with _DB_LOCK:
        return pd.DataFrame(
            (Chipmunk * Chipmunk.Trial * Chipmunk.TrialParameters & restriction).fetch(
                order_by="trial_num"
            )
        )


@_ttl_lru_cache(maxsize=64)
def get_subject_water(subject: str) -> dict[str, float]:
    """Fetch water volumes for all sessions of a subject (cached)."""
    with _DB_LOCK:
        rows = (DecisionTask * Watering & f"subject_name = '{subject}'").fetch(
            "session_name", "water_volume", as_dict=True
        )
    return {row["session_name"]: float(row["water_volume"]) for row in rows}


@_ttl_lru_cache(maxsize=64)
def get_trials_for_sessions(
    subject: str, session_names: tuple[str, ...]
) -> dict[str, pd.DataFrame]:
    """Fetch per-trial data for many sessions with a single DB query (cached)."""
    start = time.perf_counter()
    if not session_names:
        return {}

    quoted = ", ".join(f"'{s}'" for s in session_names)
    restriction = f"subject_name = '{subject}' AND session_name in ({quoted})"

    with _DB_LOCK:
        df = pd.DataFrame(
            (Chipmunk * Chipmunk.Trial * Chipmunk.TrialParameters & restriction).fetch(
                order_by="session_name, trial_num"
            )
        )

    if df.empty:
        return {}

    grouped: dict[str, pd.DataFrame] = {}
    for session, session_df in df.groupby("session_name", sort=False):
        grouped[str(session)] = session_df.reset_index(drop=True)
    _perf_log(
        "get_trials_for_sessions",
        start,
        subject=subject,
        sessions=len(session_names),
        rows=len(df),
    )
    return grouped


def clear_data_cache() -> None:
    """Clear lru_caches to force DB refetch."""
    get_all_subjects.cache_clear()
    get_subject_data.cache_clear()
    get_session_trials.cache_clear()
    get_subject_water.cache_clear()
    get_trials_for_sessions.cache_clear()
    get_sessions.cache_clear()
    session_metrics.cache_clear()
    multisession_metrics.cache_clear()


@_ttl_lru_cache(maxsize=64)
def get_sessions(subject: str) -> list[str]:
    """Return session names for a subject (chronological order)."""
    with _DB_LOCK:
        sessions = (DecisionTask.TrialSet() & f"subject_name = '{subject}'").fetch(
            "session_name", order_by="session_name"
        )
    return list(sessions)


def _compute_intensity(trials: pd.DataFrame) -> np.ndarray:
    """Compute stimulus intensity per trial (stim_rate - category_boundary)."""
    intensity = np.full(len(trials), np.nan)
    for mod, rate_col in [
        ("audio", "stim_rate_audio"),
        ("visual", "stim_rate_vision"),
        ("visual+audio", "stim_rate_vision"),
    ]:
        mask = trials.rewarded_modality == mod
        if mask.any():
            intensity[mask] = (
                trials.loc[mask, rate_col].to_numpy()
                - trials.loc[mask, "category_boundary"].to_numpy()
            )
    return intensity


@_ttl_lru_cache(maxsize=256)
def session_metrics(subject: str, session_name: str) -> dict | None:
    """Per-stimulus metrics for a single session, using Chipmunk.Trial directly."""
    start = time.perf_counter()
    trials = get_session_trials(subject, session_name)
    if trials.empty:
        _perf_log(
            "session_metrics", start, subject=subject, session=session_name, rows=0
        )
        return None

    intensity = _compute_intensity(trials)

    # Reaction times: t_response - t_gocue (Chipmunk.Trial fields)
    rts = trials["t_response"].to_numpy() - trials["t_gocue"].to_numpy()
    rts[trials.response.to_numpy() == 0] = np.nan
    valid_rts = rts[np.isfinite(rts)]
    valid_rts = valid_rts[valid_rts < 2]

    # Per-stimulus outcome counts (4 categories) + chronometric + p(right)
    ustims = np.unique(intensity[np.isfinite(intensity)])
    n_correct, n_incorrect, n_ew, n_no_choice, p_right, median_rt = (
        [],
        [],
        [],
        [],
        [],
        [],
    )
    for s in ustims:
        m = intensity == s
        t = trials[m]
        nc = int((t.rewarded == 1).sum())
        ni = int((t.punished == 1).sum())
        ne = int((t.early_withdrawal == 1).sum())
        nn = int(m.sum() - nc - ni - ne)
        n_correct.append(nc)
        n_incorrect.append(ni)
        n_ew.append(ne)
        n_no_choice.append(nn)
        with_choice = t[t.with_choice == 1]
        pr = (
            (with_choice.response == 1).sum() / len(with_choice)
            if len(with_choice)
            else 0
        )
        p_right.append(pr)
        # Median RT for chronometric curve
        trial_rts = rts[m]
        trial_rts = trial_rts[np.isfinite(trial_rts) & (trial_rts < 2)]
        median_rt.append(float(np.median(trial_rts)) if len(trial_rts) else np.nan)

    # Within-session sliding-window performance (20-trial window)
    choice_mask = trials.with_choice.to_numpy() == 1
    rewarded = trials.rewarded.to_numpy()
    trial_nums = trials.trial_num.to_numpy()
    win = 20
    slide_x, slide_y = [], []
    choice_idx = np.where(choice_mask)[0]
    for start in range(0, len(choice_idx) - win + 1, 5):  # step 5
        block = choice_idx[start : start + win]
        slide_x.append(int(np.mean(trial_nums[block])))
        slide_y.append(float(rewarded[block].sum() / win))

    # Calculate initiation times (t_stim - t_start)
    # Filter for valid (finite) initiation times
    init_raw = trials["t_stim"].to_numpy() - trials["t_start"].to_numpy()
    init_mask = np.isfinite(init_raw) & (init_raw > 0)
    init_vals = init_raw[init_mask]
    init_trial_nums = trials["trial_num"].to_numpy()[init_mask]

    # Sort by trial number for rolling calcs
    # (Note: init_trial_nums and init_vals might not be sorted if fetch order wasn't strict, but fetch(order_by="trial_num") should handle it. Being safe:)
    init_sorted_idx = np.argsort(init_trial_nums)
    init_trial_nums = init_trial_nums[init_sorted_idx]
    init_vals = init_vals[init_sorted_idx]

    # Rolling median of initiation time (20-trial window)
    init_roll_x, init_roll_y = [], []
    for start in range(0, len(init_vals) - win + 1, 5):
        init_roll_x.append(int(np.mean(init_trial_nums[start : start + win])))
        init_roll_y.append(float(np.median(init_vals[start : start + win])))

    # Wait times: actual vs minimum
    wait_actual = trials["t_react"].to_numpy() - trials["t_stim"].to_numpy()
    wait_min = trials["t_gocue"].to_numpy() - trials["t_stim"].to_numpy()
    wait_mask = (
        np.isfinite(wait_actual)
        & np.isfinite(wait_min)
        & (wait_actual > 0)
        & (wait_actual < 30)
        & (wait_min > 0)
        & (wait_min < 30)
    )
    wait_actual = wait_actual[wait_mask]
    wait_min = wait_min[wait_mask]
    wait_delta = wait_actual - wait_min

    # Wait delta filtered for histogram/lines
    wait_trial_nums = trials["trial_num"].to_numpy()[wait_mask]

    # Reaction times (Trial vs RT)
    rt_full_mask = np.isfinite(rts) & (rts < 2) & (trials.response != 0)
    rt_trial_nums = trials["trial_num"].to_numpy()[rt_full_mask]
    rt_vals = rts[rt_full_mask]

    # Sort for rolling
    rt_sorted_idx = np.argsort(rt_trial_nums)
    rt_trial_nums = rt_trial_nums[rt_sorted_idx]
    rt_vals = rt_vals[rt_sorted_idx]

    # Rolling median of RT (20-trial window)
    rt_roll_x, rt_roll_y = [], []
    for start in range(0, len(rt_vals) - win + 1, 5):
        rt_roll_x.append(int(np.mean(rt_trial_nums[start : start + win])))
        rt_roll_y.append(float(np.median(rt_vals[start : start + win])))

    # Rolling median of wait delta (20-trial window)
    wait_delta_x, wait_delta_y = [], []
    for start in range(0, len(wait_delta) - win + 1, 5):
        wait_delta_x.append(int(np.mean(wait_trial_nums[start : start + win])))
        wait_delta_y.append(float(np.median(wait_delta[start : start + win])))

    # Rolling EW Rate (20-trial window)
    ew_roll_x, ew_roll_y = [], []
    ew_raw = trials.early_withdrawal.to_numpy()  # 0 or 1
    # We want rolling mean of this binary vector vs trial number
    # Assuming trials are sorted by trial_num, which they are from fetch(order_by="trial_num")
    trial_nums_all = trials.trial_num.to_numpy()

    for start in range(0, len(ew_raw) - win + 1, 5):
        ew_roll_x.append(int(np.mean(trial_nums_all[start : start + win])))
        ew_roll_y.append(float(np.mean(ew_raw[start : start + win])))

    out = dict(
        stims=ustims.tolist(),
        n_correct=n_correct,
        n_incorrect=n_incorrect,
        n_ew=n_ew,
        n_no_choice=n_no_choice,
        p_right=p_right,
        median_rt=median_rt,
        rts=valid_rts.tolist(),
        rt_trial_nums=rt_trial_nums.tolist(),
        rt_vals=rt_vals.tolist(),
        rt_roll_x=rt_roll_x,
        rt_roll_y=rt_roll_y,
        init_times=init_vals.tolist(),
        init_trial_nums=init_trial_nums.tolist(),
        init_roll_x=init_roll_x,
        init_roll_y=init_roll_y,
        wait_times=wait_actual.tolist(),
        wait_min_times=wait_min.tolist(),
        wait_delta_times=wait_delta.tolist(),
        wait_trial_nums=wait_trial_nums.tolist(),
        wait_delta_x=wait_delta_x,
        wait_delta_y=wait_delta_y,
        slide_x=slide_x,  # rolling performance x
        slide_y=slide_y,  # rolling performance y
        ew_roll_x=ew_roll_x,  # rolling EW x
        ew_roll_y=ew_roll_y,  # rolling EW y
    )
    _perf_log(
        "session_metrics",
        start,
        subject=subject,
        session=session_name,
        rows=len(trials),
    )
    return out


@_ttl_lru_cache(maxsize=256)
def multisession_metrics(
    subject: str,
    sessions_back: int,
    start_date: str | None = None,
    smooth: bool = False,
    smooth_window: int = 3,
) -> dict | None:
    """Cross-session metrics. Dates are relative to `start_date` (default: latest)."""
    start = time.perf_counter()
    df = get_subject_data(subject).copy()
    if df.empty:
        _perf_log("multisession_metrics", start, subject=subject, sessions=0)
        return None

    df = df.sort_values("session_name")

    # Parse session dates for filtering
    df["date"] = pd.to_datetime(
        df["session_name"].str.slice(0, 8), format="%Y%m%d", errors="coerce"
    )

    # Filter by date if provided
    if start_date:
        anchor_dt = pd.to_datetime(start_date)
        # Keep sessions <= start_date
        df = df[df["date"] <= anchor_dt]
    else:
        # If no date provided, use the latest session date of this subject as anchor
        if not df.empty:
            anchor_dt = df["date"].iloc[-1]
        else:
            _perf_log("multisession_metrics", start, subject=subject, sessions=0)
            return None

    # Take the last N sessions
    n = min(sessions_back, len(df))
    d = df.tail(n).copy()
    d_session_names = tuple(d["session_name"].tolist())

    trials_by_session = get_trials_for_sessions(subject, d_session_names)
    water_by_session = get_subject_water(subject)

    # Calculate X-axis (Days relative to anchor_dt)
    # This aligns 0 to the shared anchor date (or this subject's latest date if none shared)
    try:
        days_diff = (d["date"] - anchor_dt).dt.days
        x_axis = days_diff.tolist()
    except Exception:
        x_axis = list(range(-len(d) + 1, 1))

    ew_rate, side_bias, median_init, median_rt_list, median_wait_list = (
        [],
        [],
        [],
        [],
        [],
    )
    for row in d.itertuples(index=False):
        resp = np.array(row.response_values)
        choice = np.isin(resp, [-1, 1])
        ew_rate.append((~choice).sum() / resp.shape[0])
        # Side bias: Bias Index (fraction right - 0.5)
        if choice.sum() > 0:
            frac = float((resp[choice] == 1).sum() / choice.sum())
            side_bias.append(frac - 0.5)
        else:
            side_bias.append(np.nan)
        # Median initiation time
        init = np.array(row.initiation_times)
        finite = init[np.isfinite(init)]
        median_init.append(float(np.median(finite)) if len(finite) else np.nan)
        # Median reaction time
        if row.reaction_times is not None:
            rt_arr = np.asarray(row.reaction_times).flatten()
            rt_valid = rt_arr[np.isfinite(rt_arr) & (rt_arr > 0) & (rt_arr < 2)]
            median_rt_list.append(
                float(np.median(rt_valid)) if len(rt_valid) else np.nan
            )
        else:
            median_rt_list.append(np.nan)
        # Median wait time (t_react - t_stim per trial)
        try:
            trials = trials_by_session.get(row.session_name)
            if trials is not None and not trials.empty:
                wt = trials["t_react"].to_numpy() - trials["t_stim"].to_numpy()
                wt = wt[np.isfinite(wt) & (wt > 0) & (wt < 30)]
                median_wait_list.append(float(np.median(wt)) if len(wt) else np.nan)
            else:
                median_wait_list.append(np.nan)
        except Exception:
            median_wait_list.append(np.nan)

    # Water earned per session (from Watering table via DecisionTask)
    water = [
        water_by_session.get(row.session_name, np.nan)
        for row in d.itertuples(index=False)
    ]

    # --- Smoothing Logic ---
    res = dict(
        perf_easy=np.array(d["performance_easy"]),
        ew_rate=np.array(ew_rate),
        n_with_choice=np.array(d["n_with_choice"]),
        side_bias=np.array(side_bias),
        median_init=np.array(median_init),
        median_rt=np.array(median_rt_list),
        median_wait=np.array(median_wait_list),
        water=np.array(water),
    )

    out: dict[str, list[float]] = {}
    if smooth and smooth_window > 1:
        # Simple moving average, handling NaNs
        # We can use pandas rolling on a temporary series for each metric
        for k, v in res.items():
            s = pd.Series(v)
            # Center=True, min_periods=1 to keep tails
            out[k] = (
                s.rolling(window=smooth_window, center=True, min_periods=1)
                .mean()
                .tolist()
            )
    else:
        # Convert back to list
        for k, v in res.items():
            out[k] = np.asarray(v).tolist()

    out["x"] = x_axis
    _perf_log(
        "multisession_metrics",
        start,
        subject=subject,
        sessions=len(d),
        smooth=smooth,
        smooth_window=smooth_window,
    )
    return out
