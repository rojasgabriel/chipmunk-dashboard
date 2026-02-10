from labdata.schema import DecisionTask  # type: ignore
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path


# %%
def run_perf_summary(mouse: str, out_dir: Path, sessions_back: int) -> Path | None:
    data = pd.DataFrame(DecisionTask.TrialSet() & f"subject_name = '{mouse}'")
    if data.empty:
        return None

    ses_back = sessions_back if len(data) >= sessions_back else len(data)
    data = data.tail(ses_back)
    sesdata = data[data.session_name == data.session_name.iloc[-1]]
    session_name = sesdata.session_name.values[0]

    ew_rate = []
    for ses in data.itertuples(index=False):
        ew_trials = ~(np.isin(np.array(ses.response_values), [-1, 1]))
        ew_rate.append((ew_trials).sum() / ew_trials.shape[0])

    valid_trials = sesdata.response_values.apply(lambda x: np.isin(x, [-1, 1])).values[
        0
    ]

    stims = sesdata.intensity_values.values[0][valid_trials]
    responses = np.array(sesdata.response_values.values[0])[valid_trials]
    correct = sesdata.correct_values.values[0][valid_trials]
    react_times = sesdata.reaction_times.values[0][valid_trials]
    react_times = react_times[react_times < 2]

    unique_stims = np.unique(sesdata.intensity_values.values[0])
    frac_correct = []
    p_right = []
    for ustim in unique_stims:
        mask = stims == ustim
        right_mask = responses[mask] == 1
        frac_correct.append(correct[mask].sum() / correct[mask].shape[0])
        p_right.append(right_mask.sum() / right_mask.shape[0])

    fig, ax = plt.subplots(3, 2, figsize=(6, 7))

    ### fraction correct per stim ###
    ax[0, 0].plot(unique_stims, frac_correct, "o-", color="dodgerblue")
    ax[0, 0].set_xlabel("stim intensities")
    ax[0, 0].set_ylabel("fraction correct")
    ax[0, 0].set_ylim((0.3, 1))

    ### p(right) per stim ###
    ax[1, 0].plot(unique_stims, p_right, "o-", color="dodgerblue")
    ax[1, 0].set_xlabel("stim intensities")
    ax[1, 0].set_ylabel("p(right)")
    ax[1, 0].set_ylim((0, 1))

    ### performance on easy trials ###
    xvalues = np.arange(0, ses_back, 1)
    ax[0, 1].plot(
        xvalues,
        data["performance_easy"][::-1],
        color="violet",
        marker="o",
        linestyle="-",
        label="easy",
        alpha=0.8,
    )
    ax[0, 1].plot(
        xvalues,
        data["performance"][::-1],
        color="grey",
        marker="o",
        linestyle="-",
        label="all",
        alpha=0.8,
    )
    ax[0, 1].set_ylabel("performance")
    ax[0, 1].set_xlabel("sessions back")
    ax[0, 1].legend()
    ax[0, 1].set_ylim((0.3, 1))

    ### early withdrawal rate ###
    ax[1, 1].hlines(0.5, xvalues[0], xvalues[-1], color="k", linestyle="--")
    ax[1, 1].plot(xvalues, ew_rate, color="crimson", marker="o", alpha=0.8)
    ax[1, 1].set_xlabel("sessions back")
    ax[1, 1].set_ylabel("e.w. rate")
    ax[1, 1].set_ylim([0, 1])

    ### reaction times ###
    ax[2, 0].hist(react_times, bins=20, color="dodgerblue", alpha=0.8)
    ax[2, 0].set_xlabel("reaction times")
    ax[2, 0].set_ylabel("count")

    ### trial counts ###
    ax[2, 1].bar(
        xvalues, data["n_trials"][::-1], color="grey", label="total", alpha=0.8
    )
    ax[2, 1].bar(
        xvalues,
        data["n_with_choice"][::-1],
        color="dodgerblue",
        label="with choice",
        alpha=0.8,
    )
    ax[2, 1].bar(
        xvalues,
        data["n_correct"][::-1],
        color="deeppink",
        label="correct",
        alpha=0.8,
    )
    ax[2, 1].set_ylabel("trials")
    ax[2, 1].set_xlabel("sessions back")
    ax[2, 1].set_xticks(xvalues[::2])
    ax[2, 1].legend()

    fig.suptitle(
        f"{sesdata.subject_name.values[0]}\n{sesdata.session_name.values[0]}",
        x=0.1,
        ha="left",
    )
    plt.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{mouse}_{session_name}_perf_summary.png"
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate performance summary plots for one or more mice."
    )
    parser.add_argument(
        "mice",
        nargs="+",
        help="One or more mouse names, e.g. GRB050 GRB051",
    )
    parser.add_argument(
        "--out-dir",
        default=str(Path.home() / "Downloads"),
        help="Directory to save output PNGs (default: ~/Downloads)",
    )
    parser.add_argument(
        "--sessions-back",
        type=int,
        default=10,
        help="Number of most recent sessions to include (default: 10)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    for mouse in args.mice:
        out_path = run_perf_summary(mouse, out_dir, args.sessions_back)
        if out_path is None:
            print(f"No data found for mouse {mouse}")
        else:
            print(f"Saved {out_path}")


if __name__ == "__main__":
    main()

# %%
