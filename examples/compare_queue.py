"""Compare two built checkouts using fastqueue_example.py's workloads.

Build both checkouts with the same Python and compiler settings, then run:
    python examples/compare_queue.py --before ../fastqueue-before --after .
    python examples/compare_queue.py --plot-only

Results, build metadata, and PNG/SVG figures are saved in queue-comparison/.
The default runs 50 measured trials per size and version across five serial
paired blocks. Construction and destruction remain outside the timers.
"""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import subprocess
import sys


COLORS = {"Queue": "#0072B2", "QueueC": "#009E73", "deque": "#D55E00"}
OPERATIONS = {
    "enqueue": "Enqueue / appendleft",
    "dequeue": "Dequeue / pop",
    "extend": "Extend (one bulk call)",
    "getitem": "Random indexing",
}


def measure(args):
    import matplotlib
    matplotlib.use("Agg")

    root = getattr(args, args.worker).resolve()
    sys.path.insert(0, str(root))
    import _fastqueue
    import fastqueue
    import fastqueue_example as example

    extension = Path(_fastqueue.__file__).resolve()
    if extension.parent != root or Path(fastqueue.__file__).resolve().parent != root / "fastqueue":
        raise RuntimeError("Build fastqueue in {} with this Python before benchmarking".format(root))
    files = {"extension_sha256": extension, "source_sha256": root / "src" / "fastqueue.c",
             "example_sha256": Path(example.__file__)}
    hashes = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in files.items()}
    random.seed(args.seed)
    sizes = range(args.step, args.max_size + 1, args.step)
    profiles = (example.dequeue_profiles(sizes) + example.enqueue_profiles(sizes)
                + example.extend_profiles(sizes) + example.getter_profiles(sizes))
    print("{} block {}: {} profiles; {}".format(
        args.worker, args.block, len(profiles), extension), flush=True)
    random.seed(args.seed + args.block)
    example.run_profiles(profiles, 1)
    for profile in profiles:
        profile.execution_times.clear()
    profiles.sort(key=lambda p: (p.structure.__name__, p.op.__name__, p.size))
    random.seed(args.seed + args.block)
    example.run_profiles(profiles, args.trials)

    frame = example.to_dataframe(profiles)
    frame["trial"] = frame.groupby(["queue_type", "queue_op", "size"]).cumcount() + 1
    frame["version"] = args.worker
    frame["block"] = args.block
    stem = "{}-{}".format(args.worker, args.block)
    frame.to_csv(args.output / (stem + ".csv"), index=False)
    if hashes != {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in files.items()}:
        raise RuntimeError("Build or benchmark files changed during measurement")
    metadata = {
        "version": args.worker, "block": args.block, "trials": args.trials,
        "csv": stem + ".csv", "root": str(root), "extension": str(extension),
        **hashes,
        "python": sys.version, "platform": platform.platform(),
    }
    (args.output / (stem + ".json")).write_text(json.dumps(metadata, indent=2) + "\n")


def compare(args):
    if (args.output / "run.json").exists():
        raise ValueError("Output already contains a run; choose another --output or use --plot-only")
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "trials": args.trials, "blocks": args.blocks, "seed": args.seed,
        "sizes": list(range(args.step, args.max_size + 1, args.step)),
        "labels": {"before": args.before_label, "after": args.after_label},
        "runs": [],
    }
    manifest_path = args.output / "run.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    per_block, remainder = divmod(args.trials, args.blocks)
    for block in range(1, args.blocks + 1):
        trials = per_block + (block <= remainder)
        order = ("before", "after") if block % 2 else ("after", "before")
        for version in order:
            subprocess.run([
                sys.executable, str(Path(__file__).resolve()),
                "--before", str(args.before.resolve()), "--after", str(args.after.resolve()),
                "--output", str(args.output.resolve()), "--worker", version,
                "--block", str(block), "--trials", str(trials), "--blocks", "1",
                "--step", str(args.step), "--max-size", str(args.max_size),
                "--seed", str(args.seed),
            ], check=True)
            metadata = json.loads((args.output / "{}-{}.json".format(version, block)).read_text())
            manifest["runs"].append(metadata)
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


def plot(output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    import pandas as pd

    manifest = json.loads((output / "run.json").read_text())
    runs = manifest["runs"]
    if len(runs) != manifest["blocks"] * 2:
        raise ValueError("The comparison is incomplete; completed blocks remain saved in {}".format(output))
    for key in ("python", "platform", "example_sha256"):
        if len({run[key] for run in runs}) != 1:
            raise ValueError("Mismatched benchmark environment: " + key)
    for version in ("before", "after"):
        versions = [run for run in runs if run["version"] == version]
        for key in ("extension_sha256", "source_sha256"):
            if len({run[key] for run in versions}) != 1:
                raise ValueError("{} build changed during measurement".format(version))
    frame = pd.concat([pd.read_csv(output / run["csv"]) for run in runs], ignore_index=True)
    if len(frame) != 24 * len(manifest["sizes"]) * manifest["trials"]:
        raise ValueError("Unexpected number of benchmark samples")
    frame["operation"] = frame["queue_op"].replace({
        "appendleft": "enqueue", "pop": "dequeue", "__getitem__": "getitem",
    })
    keys = ["version", "queue_type", "operation", "size"]
    counts = frame.groupby(keys).size()
    expected = pd.MultiIndex.from_product(
        [("before", "after"), COLORS, OPERATIONS, manifest["sizes"]], names=keys)
    if not counts.reindex(expected).eq(manifest["trials"]).all() or len(counts) != len(expected):
        raise ValueError("Missing or mismatched benchmark samples")
    valid_time = frame["time"].gt(0) & frame["time"].lt(float("inf"))
    if frame.duplicated(keys + ["block", "trial"]).any() or not valid_time.all():
        raise ValueError("Invalid benchmark samples")
    frame.to_csv(output / "timings.csv", index=False)
    means = frame.groupby(keys)["time"].mean()
    means.rename("mean_microseconds").to_csv(output / "means.csv")

    figure, axes = plt.subplots(2, 2, figsize=(15, 9))
    for axis, (operation, title) in zip(axes.flat, OPERATIONS.items()):
        for queue, color in COLORS.items():
            for version, style in (("before", "--"), ("after", "-")):
                values = means.loc[(version, queue, operation)].sort_index()
                axis.plot(values.index, values.values, color=color, linestyle=style, linewidth=1.7)
        axis.set_title(title, pad=12)
        axis.set_xlabel("Items / random lookups" if operation == "getitem" else "Items")
        axis.set_ylabel("Mean elapsed time (microseconds)")
        axis.set_xlim(left=0)
        axis.set_ylim(bottom=0)
        axis.grid(alpha=0.18)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
    handles = [Line2D([], [], color=color, linewidth=2, label=queue)
               for queue, color in COLORS.items()]
    handles += [Line2D([], [], color="#444444", linestyle=style, linewidth=2,
                       label=manifest["labels"][version])
                for version, style in (("before", "--"), ("after", "-"))]
    figure.suptitle("fastqueue_example.py: current changes", fontsize=21, y=0.98)
    figure.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.94),
                  ncol=5, frameon=False)
    figure.text(0.5, 0.025,
                "{} measured trials per size and version; {} serial paired blocks. "
                "Means match the original example; construction and destruction are outside timers."
                .format(manifest["trials"], manifest["blocks"]), ha="center", fontsize=9, color="#555555")
    figure.subplots_adjust(left=0.075, right=0.98, bottom=0.11, top=0.81,
                           wspace=0.21, hspace=0.36)
    for suffix in ("png", "svg"):
        target = output / ("comparison." + suffix)
        figure.savefig(target, dpi=160)
        print("Saved {}".format(target.resolve()))
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--before", type=Path, help="Separately built baseline checkout")
    parser.add_argument("--after", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("queue-comparison"), help="Results directory")
    parser.add_argument("--before-label", default="Before (baseline)")
    parser.add_argument("--after-label", default="After (current)")
    parser.add_argument("--trials", type=int, default=50, help="Total measured trials per size and version")
    parser.add_argument("--blocks", type=int, default=5, help="Serial paired blocks with alternating version order")
    parser.add_argument("--max-size", type=int, default=49500, help="Inclusive maximum size")
    parser.add_argument("--step", type=int, default=500)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--plot-only", action="store_true", help="Regenerate figures from saved timings")
    parser.add_argument("--worker", choices=("before", "after"), help=argparse.SUPPRESS)
    parser.add_argument("--block", type=int, default=1, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.plot_only:
        plot(args.output)
        return
    if args.before is None:
        parser.error("--before is required unless --plot-only is used")
    if not args.before.is_dir() or not args.after.is_dir():
        parser.error("--before and --after must be built checkout directories")
    if args.step < 1 or args.max_size < args.step or not 1 <= args.blocks <= args.trials:
        parser.error("Require step > 0, max-size >= step, and 1 <= blocks <= trials")
    if args.worker:
        measure(args)
    else:
        compare(args)
        plot(args.output)


if __name__ == "__main__":
    main()
