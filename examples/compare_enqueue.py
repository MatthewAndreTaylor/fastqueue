"""Compare separately built Queue versions with deque.appendleft in one process.

Pass --build LABEL=PATH for each _fastqueue extension to compare. All builds
must match this Python's ABI. Timings use fastqueue_example.py's enqueue loop.
"""

import argparse
from collections import deque
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import random
from statistics import mean
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from fastqueue_example import SingleArgProfile
from native_source import source_bytes


def build_metadata(path):
    metadata = {"extension": str(path),
                "extension_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    source = path.parent / "src" / "fastqueue.c"
    if source.exists():
        metadata["source_sha256"] = hashlib.sha256(source_bytes(path.parent)).hexdigest()
    return metadata


def load_builds(builds):
    structures = {}
    metadata = {}
    for index, (label, path) in enumerate(builds):
        spec = importlib.util.spec_from_file_location("enqueue_build_{}._fastqueue".format(index), path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        structures[label] = module.Queue
        metadata[label] = build_metadata(path)
        queue = module.Queue()
        for item in range(1000):
            queue.enqueue(item)
        assert [queue.dequeue() for _ in range(1000)] == list(range(1000))
    assert len(set(structures.values())) == len(structures), "Builds must load distinct Queue types"
    structures["deque"] = deque
    return structures, metadata


def collect(structures, sizes, trials, warmups, seed):
    rng = random.Random(seed)
    profiles = []
    for size in sizes:
        items = [rng.randrange(1001) for _ in range(size)]
        for label, structure in structures.items():
            operation = structure.appendleft if structure is deque else structure.enqueue
            profiles.append((label, SingleArgProfile(structure, operation, items, size)))
    for trial in range(warmups + trials):
        rng.shuffle(profiles)
        for _, profile in profiles:
            profile.run()
        if trial == warmups - 1:
            for _, profile in profiles:
                profile.execution_times.clear()
        print("{} {}/{}".format("Warmup" if trial < warmups else "Trial",
              trial + 1 if trial < warmups else trial - warmups + 1,
              warmups if trial < warmups else trials), flush=True)
    rows = [{"build": label, "size": p.size, "samples_ns": p.execution_times}
            for label, p in profiles]
    assert all(len(r["samples_ns"]) == trials and min(r["samples_ns"]) > 0 for r in rows)
    return rows


def plot(result, output):
    plt.rcParams["svg.fonttype"] = "none"
    figure, axes = plt.subplots(1, 2, figsize=(14, 5.6))
    colors = ["#7e22ce", "#0072B2", "#009E73", "#D55E00", "#444444", "#cc79a7"]
    sizes = result["sizes"]
    means = {(row["build"], row["size"]): mean(row["samples_ns"])
             for row in result["results"]}
    for label, color in zip(result["builds"], colors):
        values = [means[label, size] for size in sizes]
        axes[0].plot(sizes, [v / 1000 for v in values], label=label, color=color, linewidth=1.7)
        if label != "deque":
            axes[1].plot(sizes, [means["deque", size] / value for size, value in zip(sizes, values)],
                         label=label, color=color, linewidth=1.7)
    axes[1].axhline(1, color="#777777", linewidth=1)
    axes[0].set_title("Enqueue / appendleft (lower is better)", pad=12)
    axes[0].set_ylabel("Mean elapsed time (microseconds)")
    axes[0].set_ylim(bottom=0)
    axes[1].set_title("Speed relative to deque (higher is better)", pad=12)
    axes[1].set_ylabel("deque time / Queue time")
    for axis in axes:
        axis.set_xlabel("Items")
        axis.set_xlim(left=0)
        axis.grid(alpha=0.18)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
    figure.suptitle("Queue enqueue | {} | CPython {}".format(
        result["platform_label"], result["python_version"]), fontsize=19, y=0.98)
    figure.legend(*axes[0].get_legend_handles_labels(), loc="upper center",
                  bbox_to_anchor=(0.5, 0.925), ncol=min(4, len(result["builds"])), frameon=False)
    figure.text(0.5, 0.025,
                "{} trials per point; {} warmups. All builds shuffled in one process.\n"
                "Identical prebuilt inputs; construction and cleanup outside timers; arithmetic means."
                .format(result["trials"], result["warmups"]), ha="center", fontsize=9, color="#555555")
    figure.subplots_adjust(left=0.075, right=0.98, bottom=0.17, top=0.77, wspace=0.23)
    for suffix in ("svg", "png"):
        figure.savefig(output.with_suffix("." + suffix), dpi=160)
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="append", required=True, metavar="LABEL=EXTENSION")
    parser.add_argument("--sizes", nargs="+", type=int, default=list(range(500, 50000, 500)))
    parser.add_argument("--trials", type=int, default=50)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True, help="Output file stem")
    args = parser.parse_args()
    if args.trials < 1 or args.warmups < 0 or any(size < 1 for size in args.sizes):
        parser.error("Require positive sizes/trials and nonnegative warmups")
    builds = []
    labels = {"deque"}
    for value in args.build:
        label, separator, filename = value.partition("=")
        if not separator or not label or label in labels or not Path(filename).is_file():
            parser.error("Each --build needs a unique label and existing extension path")
        labels.add(label)
        builds.append((label, Path(filename).resolve()))
    if len(builds) > 5:
        parser.error("At most five Queue builds can be plotted")
    structures, metadata = load_builds(builds)
    sizes = sorted(set(args.sizes))
    profile_path = Path(sys.modules[SingleArgProfile.__module__].__file__)
    result = {
        "python": sys.version, "python_version": platform.python_version(),
        "platform": platform.platform(),
        "platform_label": "WSL2" if "microsoft" in platform.release().lower() else platform.system(),
        "builds": list(structures), "build_metadata": metadata,
        "profile_sha256": hashlib.sha256(profile_path.read_bytes()).hexdigest(),
        "sizes": sizes, "trials": args.trials, "warmups": args.warmups, "seed": args.seed,
        "command": [sys.executable] + sys.argv,
        "results": collect(structures, sizes, args.trials, args.warmups, args.seed),
    }
    if {label: build_metadata(path) for label, path in builds} != metadata:
        raise RuntimeError("An extension or source file changed during measurement")
    if hashlib.sha256(profile_path.read_bytes()).hexdigest() != result["profile_sha256"]:
        raise RuntimeError("The benchmark workload changed during measurement")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix(".json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    plot(result, args.output)
    for label in structures:
        times = [mean(r["samples_ns"]) for r in result["results"] if r["build"] == label]
        print("{}: {:.3f} ns/item".format(label, sum(times) / sum(sizes)), flush=True)


if __name__ == "__main__":
    main()
