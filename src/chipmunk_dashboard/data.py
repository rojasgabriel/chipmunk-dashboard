"""Data fetching and metric computation."""

from labdata.schema import DecisionTask, Watering  # type: ignore
from labdata import chipmunk  # type: ignore
from chipmunk import Chipmunk  # type: ignore
import pandas as pd
import numpy as np
from functools import lru_cache
import threading

_DB_LOCK = threading.RLock()


def get_all_subjects() -> list[str]:
    """Return sorted unique subject names from the database."""
    with _DB_LOCK:
        subjects = DecisionTask.TrialSet().fetch("subject_name")
    return sorted(set(subjects))


@lru_cache(maxsize=64)
def get_subject_data(subject: str) -> pd.DataFrame:
    """Fetch all trial-set rows for a subject (cached in memory)."""
    with _DB_LOCK:
        return pd.DataFrame(DecisionTask.TrialSet() & f"subject_name = '{subject}'")


@lru_cache(maxsize=64)
def get_session_trials(subject: str, session_name: str) -> pd.DataFrame:
    """Fetch per-trial Chipmunk data for a single session (cached)."""
    restriction = f"subject_name = '{subject}' AND session_name = '{session_name}'"
    with _DB_LOCK:
        return pd.DataFrame(
            (Chipmunk * Chipmunk.Trial * Chipmunk.TrialParameters & restriction).fetch(
                order_by="trial_num"
            )
        )


def get_sessions(subject: str) -> list[str]:
    """Return session names for a subject (chronological order)."""
    df = get_subject_data(subject)
    return df["session_name"].tolist() if not df.empty else []


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


def session_metrics(subject: str, session_name: str) -> dict | None:
    """Per-stimulus metrics for a single session, using Chipmunk.Trial directly."""
    trials = get_session_trials(subject, session_name)
    if trials.empty:
        return None

    intensity = _compute_intensity(trials)

    # Reaction times: t_response - t_gocue (Chipmunk.Trial fields)
    rts = trials["t_response"].to_numpy() - trials["t_gocue"].to_numpy()
    rts[trials.response.to_numpy() == 0] = np.nan
    valid_rts = rts[np.isfinite(rts)]
    valid_rts = valid_rts[valid_rts < 2]

    # Per-stimulus outcome counts (4 categories) + chronometric + p(right)
    ustims = np.unique(intensity[np.isfinite(intensity)])
    n_correct, n_incorrect, n_ew, n_no_choice, p_right, median_rt = [], [], [], [], [], []
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
        pr = (with_choice.response == 1).sum() / len(with_choice) if len(with_choice) else 0
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

    # Initiation times: t_stim - t_start
    init_mask = (trials["t_stim"] > trials["t_start"]) & np.isfinite(trials["t_stim"])
    init_raw = trials.loc[init_mask, "t_stim"] - trials.loc[init_mask, "t_start"]
    # Filter insane values
    init_mask_2 = (init_raw > 0) & (init_raw < 30)
    init_vals = init_raw[init_mask_2].to_numpy()
    init_trial_nums = trials.loc[init_mask, "trial_num"][init_mask_2].to_numpy()

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

    # Rolling median of wait delta (20-trial window)
    wait_delta_x, wait_delta_y = [], []
    for start in range(0, len(wait_delta) - win + 1, 5):
        block = slice(start, start + win)
        wait_delta_x.append(int(np.mean(wait_trial_nums[block])))
        wait_delta_y.append(float(np.median(wait_delta[block])))

    return dict(
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
        init_times=init_vals.tolist(),
        init_trial_nums=init_trial_nums.tolist(),
        wait_times=wait_actual.tolist(),
        wait_min_times=wait_min.tolist(),
        wait_delta_times=wait_delta.tolist(),
        wait_trial_nums=wait_trial_nums.tolist(),
        wait_delta_x=wait_delta_x,
        wait_delta_y=wait_delta_y,
        slide_x=slide_x,
        slide_y=slide_y,
    )


def multisession_metrics(subject: str, sessions_back: int) -> dict | None:
    """Cross-session metrics (performance, EW rate, trial counts, etc.)."""
    df = get_subject_data(subject)
    if df.empty:
        return None

    n = min(sessions_back, len(df))
    d = df.tail(n)

    ew_rate, side_bias, median_init, median_rt_list, median_wait_list = [], [], [], [], []
    for row in d.itertuples(index=False):
        resp = np.array(row.response_values)
        choice = np.isin(resp, [-1, 1])
        ew_rate.append((~choice).sum() / resp.shape[0])
        # Side bias: fraction rightward among choice trials
        if choice.sum() > 0:
            side_bias.append(float((resp[choice] == 1).sum() / choice.sum()))
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
            median_rt_list.append(float(np.median(rt_valid)) if len(rt_valid) else np.nan)
        else:
            median_rt_list.append(np.nan)
        # Median wait time (t_react - t_stim per trial)
        try:
            trials = get_session_trials(row.subject_name, row.session_name)
            if not trials.empty:
                wt = trials["t_react"].to_numpy() - trials["t_stim"].to_numpy()
                wt = wt[np.isfinite(wt) & (wt > 0) & (wt < 30)]
                median_wait_list.append(float(np.median(wt)) if len(wt) else np.nan)
            else:
                median_wait_list.append(np.nan)
        except Exception:
            median_wait_list.append(np.nan)

    # Water earned per session (from Watering table via DecisionTask)
    water = []
    for row in d.itertuples(index=False):
        try:
            key = dict(subject_name=row.subject_name, session_name=row.session_name)
            with _DB_LOCK:
                w = (DecisionTask * Watering & key).fetch1("water_volume")
            water.append(float(w))
        except Exception:
            water.append(np.nan)

    # Chronological X-axis: -n+1 ... 0
    # Data is already chronological (tail(n)), do NOT reverse lists
    x_axis = list(range(-len(d) + 1, 1))

    return dict(
        x=x_axis,
        perf_easy=d["performance_easy"].values.tolist(),
        ew_rate=ew_rate,
        n_with_choice=d["n_with_choice"].values.tolist(),
        side_bias=side_bias,
        median_init=median_init,
        median_rt=median_rt_list,
        median_wait=median_wait_list,
        water=water,
    )
