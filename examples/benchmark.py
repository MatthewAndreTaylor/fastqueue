"""Benchmark the current build and create a 2x2 README image matrix.

Uses the same enqueue, dequeue and extend workloads as compare_queue.py.
The fourth panel measures sequential iteration rather than random indexing.
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
import fastqueue_example as example
from native_source import source_bytes


COLORS = {"Queue": "#0072B2", "QueueC": "#009E73", "deque": "#D55E00"}
OPERATIONS = {
    "enqueue": "Enqueue / appendleft",
    "dequeue": "Dequeue / pop",
    "extend": "Extend (one bulk call)",
    "iteration": "Iteration (one full pass)",
}
BUILDERS = {
    "enqueue": example.enqueue_profiles,
    "dequeue": example.dequeue_profiles,
    "extend": example.extend_profiles,
    "iteration": example.iteration_profiles,
}
DEFAULT_SIZES = list(range(500, 50000, 500))
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
        {"queue": profile.structure.__name__, "operation": operation,
         "size": profile.size, "samples_ns": profile.execution_times}
        for operation, group in groups.items() for profile in group
    ]


def build_metadata():
    files = {"extension": Path(_fastqueue.__file__),
             "workloads": Path(example.__file__)}
    return {
        "revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "fastqueue_version": version("fastqueue-lib"),
        "extension": str(files["extension"].resolve()),
        "source_sha256": hashlib.sha256(source_bytes(ROOT)).hexdigest(),
        **{name + "_sha256": hashlib.sha256(path.read_bytes()).hexdigest()
           for name, path in files.items()},
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
        "matplotlib": matplotlib.__version__,
    }


def plot(result, output):
    """Match compare_queue.py's linear axes, means, colors and matrix layout."""
    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none"})
    figure, axes = plt.subplots(2, 2, figsize=(15, 9))
    for axis, (operation, title) in zip(axes.flat, OPERATIONS.items()):
        for queue, color in COLORS.items():
            rows = sorted(
                (row for row in result["results"]
                 if row["operation"] == operation and row["queue"] == queue),
                key=lambda row: row["size"])
            axis.plot([row["size"] for row in rows],
                      [mean(row["samples_ns"]) / 1000 for row in rows],
                      color=color, linestyle="-", linewidth=1.7)
        axis.set_title(title, pad=12)
        axis.set_xlabel("Items")
        axis.set_ylabel("Mean elapsed time (microseconds)")
        axis.set_xlim(left=0)
        axis.set_ylim(bottom=0)
        axis.grid(alpha=0.18)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
    env = result["environment"]
    figure.suptitle("fastqueue: {} | CPython {}".format(
        env["label"], env["python_version"]), fontsize=21, y=0.98)
    figure.legend(
        handles=[Line2D([], [], color=color, linewidth=2, label=queue)
                 for queue, color in COLORS.items()],
        loc="upper center", bbox_to_anchor=(0.5, 0.94), ncol=3, frameon=False)
    figure.text(0.5, 0.025,
                "{} measured trials per size and type; {} warmups. "
                "Arithmetic means; construction and destruction are outside timers."
                .format(result["trials"], result["warmups"]),
                ha="center", fontsize=9, color="#555555")
    figure.subplots_adjust(left=0.075, right=0.98, bottom=0.11, top=0.81,
                           wspace=0.21, hspace=0.36)
    for suffix in ("svg", "png"):
        target = output / (env["slug"] + "." + suffix)
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
    parser.add_argument("--sizes", type=positive_int, nargs="+", default=DEFAULT_SIZES)
    parser.add_argument("--trials", type=positive_int, default=50)
    parser.add_argument("--warmups", type=positive_int, default=2)
    parser.add_argument("--output", type=Path, default=Path("docs/benchmarks"))
    parser.add_argument("--plot-only", action="store_true",
                        help="Regenerate the matrix from this platform's saved JSON")
    args = parser.parse_args()
    env = environment()
    args.output.mkdir(parents=True, exist_ok=True)
    data_path = args.output / (env["slug"] + ".json")
    if args.plot_only:
        result = json.loads(data_path.read_text(encoding="utf-8"))
    else:
        build = build_metadata()
        sizes = sorted(set(args.sizes))
        result = {
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
            "results": collect(sizes, args.trials, args.warmups),
        }
        if build_metadata() != build:
            raise RuntimeError("Build or workload files changed during measurement")
        data_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print("Saved {}".format(data_path), flush=True)
    plot(result, args.output)


if __name__ == "__main__":
    main()
