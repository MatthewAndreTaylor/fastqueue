"""Benchmark the current build and save every queue and iteration figure.

Includes the six-panel matrix and separate construction, indexed-increment
and iterator-local-increment charts.
"""

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import random
from statistics import mean
import subprocess
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

import _fastqueue

if __package__:
    from . import iteration_profiles, queue_profiles as example
else:
    import iteration_profiles
    import queue_profiles as example

DEFAULT_SIZES = example.DEFAULT_SIZES


COLORS = {"Queue": "#0072B2", "QueueC": "#009E73", "deque": "#D55E00"}
OPERATIONS = {
    "enqueue": "Enqueue / appendleft",
    "dequeue": "Dequeue / pop",
    "mixed": "Mixed (enqueue + dequeue)",
    "iterator": "Iterator traversal (no-op loop)",
    "getitem": "Random access (__getitem__)",
    "extend": "Extend (one bulk call)",
}
BUILDERS = {
    "enqueue": example.enqueue_profiles,
    "dequeue": example.dequeue_profiles,
    "extend": example.extend_profiles,
    "iterator": example.iterator_profiles,
    "getitem": example.getter_profiles,
    "mixed": example.mixed_profiles,
}

ROOT = Path(__file__).resolve().parents[1]


def collect(sizes, trials, warmups):
    random.seed(1)
    groups = {operation: builder(sizes) for operation, builder in BUILDERS.items()}
    profiles = [profile for group in groups.values() for profile in group]
    print("Warming up all operations, queue types and sizes...", flush=True)
    example.run_profiles(profiles, warmups)
    for profile in profiles:
        profile.execution_times.clear()
    profiles.sort(key=lambda p: (p.structure.__name__, p.op.__name__, p.size))
    random.seed(1)
    print("Collecting measured trials...", flush=True)
    example.run_profiles(profiles, trials)
    return [
        {
            "queue": profile.structure.__name__,
            "operation": operation,
            "size": profile.size,
            "samples_ns": profile.execution_times,
        }
        for operation, group in groups.items()
        for profile in group
    ]


def build_metadata():
    files = {
        "extension": Path(_fastqueue.__file__),
        "workloads": Path(example.__file__),
        "iteration_workloads": Path(iteration_profiles.__file__),
        "runner": Path(__file__),
    }
    return {
        "revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "fastqueue_version": version("fastqueue-lib"),
        "extension": str(files["extension"].resolve()),
        **{
            name + "_sha256": hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in files.items()
        },
    }


def environment():
    system = platform.system()
    is_wsl = system == "Linux" and "microsoft" in platform.release().lower()
    return {
        "slug": "wsl" if is_wsl else system.lower(),
        "label": "WSL2 / Ubuntu" if is_wsl else system,
        "platform": platform.platform(),
        "python": sys.version,
        "python_version": platform.python_version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }


def plot(result, output):
    """Plot all six workloads using linear axes and arithmetic means."""
    expected = {(operation, queue) for operation in OPERATIONS for queue in COLORS}
    measured = {(row["operation"], row["queue"]) for row in result["results"]}
    if not expected <= measured:
        raise ValueError(
            "Measurements lack required workloads; rerun without --plot-only"
        )
    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none"})
    figure, axes = plt.subplots(2, 3, figsize=(18, 10))
    for axis, (operation, title) in zip(axes.flat, OPERATIONS.items()):
        for queue, color in COLORS.items():
            rows = sorted(
                (
                    row
                    for row in result["results"]
                    if row["operation"] == operation and row["queue"] == queue
                ),
                key=lambda row: row["size"],
            )
            axis.plot(
                [row["size"] for row in rows],
                [mean(row["samples_ns"]) / 1000 for row in rows],
                color=color,
                linestyle="-",
                linewidth=1.7,
            )
        axis.set_title(title, pad=12)
        axis.set_xlabel("Initial items / pairs" if operation == "mixed" else "Items")
        axis.set_ylabel("Mean elapsed time (microseconds)")
        axis.set_xlim(left=0)
        axis.set_ylim(bottom=0)
        axis.grid(alpha=0.18)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
    env = result["environment"]
    figure.suptitle(
        "fastqueue: {} | CPython {}".format(env["label"], env["python_version"]),
        fontsize=21,
        y=0.98,
    )
    figure.legend(
        handles=[
            Line2D([], [], color=color, linewidth=2, label=queue)
            for queue, color in COLORS.items()
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.94),
        ncol=3,
        frameon=False,
    )
    figure.text(
        0.5,
        0.025,
        "{} measured trials per size and type; {} warmups. "
        "Arithmetic means; construction and destruction are outside timers.\n"
        "Mixed workload: N enqueue/dequeue pairs (2N operations) at N initial items.\n"
        "Iterator traversal: for item in o: pass (one full pass; no updates).".format(
            result["trials"], result["warmups"]
        ),
        ha="center",
        fontsize=9,
        color="#555555",
    )
    figure.subplots_adjust(
        left=0.065, right=0.98, bottom=0.12, top=0.84, wspace=0.30, hspace=0.38
    )
    save_figure(figure, output, env["slug"])


def save_figure(figure, output, name):
    for suffix in ("svg", "png"):
        target = output / (name + "." + suffix)
        figure.savefig(target, dpi=160, metadata={"Date": None})
        print("Saved {}".format(target), flush=True)
    plt.close(figure)


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profiles",
        nargs="+",
        choices=("queue", "iteration"),
        default=["queue", "iteration"],
        help="Profile suites to run (default: queue iteration)",
    )
    parser.add_argument("--sizes", type=positive_int, nargs="+", default=DEFAULT_SIZES)
    parser.add_argument(
        "--trials",
        type=positive_int,
        default=20,
        help="Measured queue trials (default: 20)",
    )
    parser.add_argument(
        "--iteration-trials",
        type=positive_int,
        default=5,
        help="Measured iteration trials (default: 5)",
    )
    parser.add_argument("--warmups", type=positive_int, default=2)
    parser.add_argument("--output", type=Path, default=Path("docs/benchmarks"))
    parser.add_argument(
        "--plot-only",
        action="store_true",
        help="Regenerate selected figures from this platform's saved JSON",
    )
    args = parser.parse_args()
    profiles = list(dict.fromkeys(args.profiles))
    env = environment()
    args.output.mkdir(parents=True, exist_ok=True)
    suffix = "" if len(profiles) == 2 else "-" + profiles[0]
    data_path = args.output / (env["slug"] + suffix + ".json")
    if args.plot_only:
        result = json.loads(data_path.read_text(encoding="utf-8"))
    else:
        build = build_metadata()
        sizes = sorted(set(args.sizes))
        result = {
            "profiles": profiles,
            "sizes": sizes,
            "trials": args.trials,
            "warmups": args.warmups,
            "seed": 1,
            "clock": "perf_counter_ns",
            "statistic": "arithmetic mean",
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "build": build,
            "command": [sys.executable] + sys.argv,
            "environment": env,
            "results": (
                collect(sizes, args.trials, args.warmups) if "queue" in profiles else []
            ),
        }
        if "iteration" in profiles:
            result["iteration"] = iteration_profiles.collect(
                500_000, args.iteration_trials, args.warmups
            )
        if build_metadata() != build:
            raise RuntimeError("Build or workload files changed during measurement")
        data_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print("Saved {}".format(data_path), flush=True)
    if "iteration" in profiles and "iteration" not in result:
        raise ValueError(
            "Measurements lack iteration workloads; rerun without --plot-only"
        )
    if "queue" in profiles:
        plot(result, args.output)
    if "iteration" in profiles:
        iteration_profiles.plot(result["iteration"], args.output)


if __name__ == "__main__":
    main()
