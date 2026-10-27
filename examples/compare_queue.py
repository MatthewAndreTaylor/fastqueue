"""Compare two built checkouts using fastqueue_example.py's workloads.

Build both checkouts with the same Python and compiler settings, then run:
    python examples/compare_queue.py --before ../fastqueue-before --after .
    python examples/compare_queue.py --plot-only

Results, build metadata, and PNG/SVG figures are saved in queue-comparison/.
The default runs 50 measured trials per size and version across five serial
paired blocks. Construction and destruction remain outside the timers.
Memory figures report fresh container storage, excluding payloads and allocator
bookkeeping. Sampling runs once per version, after all timing blocks finish.
"""

import argparse
import csv
import ctypes
import hashlib
import json
from pathlib import Path
import platform
import random
import re
import subprocess
import sys

from native_source import source_bytes


COLORS = {"Queue": "#0072B2", "QueueC": "#009E73", "deque": "#D55E00"}
STYLES = (("before", "--"), ("after", "-"))
OPERATIONS = {
    "enqueue": "Enqueue / appendleft",
    "dequeue": "Dequeue / pop",
    "extend": "Extend (one bulk call)",
    "getitem": "Random indexing",
}


def memory_layout(source):
    """Read only the simple native field declarations used by these checkouts."""
    source = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)
    chunk = re.search(r"^\s*#define\s+CHUNKLEN\s+(\d+)\s*$", source, re.M)
    if chunk is None or int(chunk[1]) < 1:
        raise ValueError("Memory measurement requires a positive numeric CHUNKLEN")
    chunklen = int(chunk[1])
    bodies = dict((name, body) for body, name in re.findall(
        r"typedef\s+struct(?:\s+\w+)?\s*\{([^{}]*)\}\s*(QueueNode_t|QueueC)\s*;", source))
    layouts = {}
    for name in ("QueueNode_t", "QueueC"):
        if name not in bodies:
            raise ValueError("Missing native layout: " + name)
        fields = []
        for declaration in bodies[name].replace("PyObject_HEAD", "PyObject_HEAD;").split(";"):
            declaration = declaration.strip()
            if not declaration:
                continue
            if declaration == "PyObject_HEAD":
                fields.append(("_object_head", ctypes.c_byte * object.__basicsize__))
                continue
            field = re.fullmatch(
                r"(struct\s+\w+|\w+)(?:\s*(\*+)\s*|\s+)(\w+)(?:\s*\[\s*(CHUNKLEN)\s*\])?",
                declaration)
            if field is None:
                raise ValueError("Unsupported native field: " + declaration)
            native_type, pointer, field_name, array = field.groups()
            scalar = {"Py_ssize_t": ctypes.c_ssize_t, "size_t": ctypes.c_size_t}.get(native_type)
            if array and not pointer or not pointer and scalar is None:
                raise ValueError("Unsupported native field: " + declaration)
            field_type = ctypes.c_void_p if pointer else scalar
            if array:
                field_type = field_type * chunklen
            fields.append((field_name, field_type))
        layouts[name] = type(name, (ctypes.Structure,), {"_fields_": fields})
    if not hasattr(layouts["QueueC"], "capacity"):
        raise ValueError("QueueC layout has no capacity field")
    return chunklen, layouts["QueueNode_t"], layouts["QueueC"]


def memory_samples(queue_types, sizes, source):
    chunklen, node_type, queuec_type = memory_layout(source)
    if ctypes.sizeof(queuec_type) != queue_types["QueueC"].__basicsize__:
        raise ValueError("QueueC source layout does not match the loaded extension")
    rows = []
    for operation in ("enqueue", "extend"):
        for name, queue_type in queue_types.items():
            for size in sizes:
                queue = queue_type()
                items = [None] * size
                if operation == "extend":
                    queue.extend(items)
                else:
                    enqueue = queue_type.appendleft if name == "deque" else queue_type.enqueue
                    for item in items:
                        enqueue(queue, item)
                if len(queue) != size:
                    raise ValueError("Unexpected queue length during memory measurement")
                native_bytes = 0
                if name == "Queue":
                    native_bytes = max(1, (size + chunklen - 1) // chunklen) * ctypes.sizeof(node_type)
                elif name == "QueueC":
                    capacity = queuec_type.from_address(id(queue)).capacity
                    if capacity < size or capacity < 1:
                        raise ValueError("Invalid QueueC capacity")
                    native_bytes = capacity * ctypes.sizeof(ctypes.c_void_p)
                rows.append({"queue_type": name, "operation": operation, "size": size,
                             "bytes": sys.getsizeof(queue) + native_bytes})
    return rows, {"chunk_length": chunklen, "node_bytes": ctypes.sizeof(node_type),
                  "queuec_basicsize": ctypes.sizeof(queuec_type),
                  "pointer_bytes": ctypes.sizeof(ctypes.c_void_p)}


def memory_build(manifest, version):
    if len(manifest["runs"]) != manifest["blocks"] * 2:
        raise ValueError("Finish all timing blocks before measuring memory")
    runs = [run for run in manifest["runs"] if run["version"] == version]
    keys = ("root", "extension", "source_sha256", "extension_sha256", "python", "platform")
    if len(runs) != manifest["blocks"] or any(len({run[key] for run in runs}) != 1 for key in keys):
        raise ValueError("Mismatched timing build: " + version)
    return {key: runs[0][key] for key in keys}


def measure_memory(output, version):
    from collections import deque

    manifest = json.loads((output / "run.json").read_text())
    build = memory_build(manifest, version)
    root = Path(build["root"]).resolve()
    sys.path.insert(0, str(root))
    import _fastqueue
    import fastqueue

    if (Path(_fastqueue.__file__).resolve() != Path(build["extension"]).resolve()
            or Path(fastqueue.__file__).resolve().parent != root / "fastqueue"):
        raise ValueError("Memory worker imported a different checkout")
    if sys.version != build["python"] or platform.platform() != build["platform"]:
        raise ValueError("Memory worker must use the timing run's Python and platform")
    files = {"extension_sha256": Path(build["extension"])}

    def verify_build():
        if hashlib.sha256(source_bytes(root)).hexdigest() != build["source_sha256"]:
            raise ValueError("Memory sources no longer match timings: " + str(root))
        for key, path in files.items():
            if hashlib.sha256(path.read_bytes()).hexdigest() != build[key]:
                raise ValueError("Memory build no longer matches timings: " + str(path))

    verify_build()
    sizes = [0] + manifest["sizes"]
    rows, layout = memory_samples(
        {"Queue": fastqueue.Queue, "QueueC": fastqueue.QueueC, "deque": deque},
        sizes, source_bytes(root).decode("utf-8"))
    verify_build()
    stem = version + "-memory"
    with (output / (stem + ".csv")).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("version", "queue_type", "operation", "size", "bytes"))
        writer.writeheader()
        writer.writerows(dict(version=version, **row) for row in rows)
    metadata = dict(build, version=version, csv=stem + ".csv", sizes=sizes, layout=layout,
                    samples=len(rows), method="Fresh containers filled with shared None; excludes payloads and allocator bookkeeping",
                    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (output / (stem + ".json")).write_text(json.dumps(metadata, indent=2) + "\n")
    print("Saved {} memory samples for {}".format(len(rows), version), flush=True)


def collect_memory(output):
    """Also callable to add memory results to a completed timing-only run."""
    output = Path(output).resolve()
    manifest = json.loads((output / "run.json").read_text())
    metadata = []
    for version, _ in STYLES:
        memory_build(manifest, version)
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--output", str(output),
                        "--memory-worker", version], check=True)
        metadata.append(json.loads((output / (version + "-memory.json")).read_text()))
    manifest["memory"] = metadata
    (output / "run.json").write_text(json.dumps(manifest, indent=2) + "\n")


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
    files = {"extension_sha256": extension,
             "example_sha256": Path(example.__file__)}
    hashes = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in files.items()}
    hashes["source_sha256"] = hashlib.sha256(source_bytes(root)).hexdigest()
    random.seed(args.seed)
    sizes = args.sizes or list(range(args.step, args.max_size + 1, args.step))
    builders = {
        "dequeue": example.dequeue_profiles, "enqueue": example.enqueue_profiles,
        "extend": example.extend_profiles, "getitem": example.getter_profiles,
    }
    profiles = []
    for operation, builder in builders.items():
        if operation in args.operations:
            profiles.extend(builder(sizes))
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
    current_hashes = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in files.items()}
    current_hashes["source_sha256"] = hashlib.sha256(source_bytes(root)).hexdigest()
    if hashes != current_hashes:
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
        "sizes": args.sizes or list(range(args.step, args.max_size + 1, args.step)),
        "operations": args.operations,
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
                "--seed", str(args.seed), "--operations", *args.operations,
                "--sizes", *(str(size) for size in manifest["sizes"]),
            ], check=True)
            metadata = json.loads((args.output / "{}-{}.json".format(version, block)).read_text())
            manifest["runs"].append(metadata)
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    collect_memory(args.output)


def legend_handles(labels):
    from matplotlib.lines import Line2D

    return ([Line2D([], [], color=color, linewidth=2, label=queue) for queue, color in COLORS.items()]
            + [Line2D([], [], color="#444444", linestyle=style, linewidth=2, label=labels[version])
               for version, style in STYLES])


def plot_memory(output, manifest):
    import matplotlib.pyplot as plt
    import pandas as pd

    metadata = manifest.get("memory")
    if metadata is None:
        return
    if len(metadata) != 2 or {item["version"] for item in metadata} != {"before", "after"}:
        raise ValueError("Incomplete memory comparison")
    sizes = [0] + manifest["sizes"]
    frames = []
    for item in metadata:
        build = memory_build(manifest, item["version"])
        if any(item[key] != value for key, value in build.items()) or item["sizes"] != sizes:
            raise ValueError("Memory results do not match the timing run")
        frame = pd.read_csv(output / item["csv"])
        if len(frame) != item["samples"] or not frame["version"].eq(item["version"]).all():
            raise ValueError("Mismatched memory samples")
        frames.append(frame)
    frame = pd.concat(frames, ignore_index=True)
    keys = ["version", "queue_type", "operation", "size"]
    expected = pd.MultiIndex.from_product([("before", "after"), COLORS, ("enqueue", "extend"), sizes], names=keys)
    counts = frame.groupby(keys).size()
    if (len(counts) != len(expected) or not counts.reindex(expected).eq(1).all()
            or not (frame["bytes"].gt(0) & frame["bytes"].lt(float("inf"))).all()):
        raise ValueError("Invalid memory samples")
    values = frame.set_index(keys)["bytes"].sort_index() / 1024
    figure, axes = plt.subplots(1, 2, figsize=(15, 5.4))
    for axis, operation in zip(axes, ("enqueue", "extend")):
        for queue, color in COLORS.items():
            for version, style in STYLES:
                series = values.loc[(version, queue, operation)].sort_index()
                axis.plot(series.index, series.values, color=color, linestyle=style, linewidth=1.7)
        axis.set_title("After " + OPERATIONS[operation].lower(), pad=12)
        axis.set_xlabel("Items")
        axis.set_ylabel("Container storage (KiB)")
        axis.set_xlim(left=0)
        axis.set_ylim(bottom=0)
        axis.grid(alpha=0.18)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
    figure.suptitle("fastqueue: memory footprint", fontsize=21, y=0.98)
    figure.legend(handles=legend_handles(manifest["labels"]), loc="upper center",
                  bbox_to_anchor=(0.5, 0.94), ncol=5, frameon=False)
    figure.text(0.5, 0.025, "Fresh containers; includes native nodes/buffers and reserved capacity. "
                "Excludes payloads and allocator bookkeeping.", ha="center", fontsize=9, color="#555555")
    figure.subplots_adjust(left=0.075, right=0.98, bottom=0.16, top=0.81, wspace=0.21)
    for suffix in ("png", "svg"):
        target = output / ("memory." + suffix)
        figure.savefig(target, dpi=160)
        print("Saved {}".format(target.resolve()))
    plt.close(figure)


def plot(output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd

    manifest = json.loads((output / "run.json").read_text())
    runs = manifest["runs"]
    operations = {name: OPERATIONS[name] for name in manifest.get("operations", OPERATIONS)}
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
    if len(frame) != 2 * len(COLORS) * len(operations) * len(manifest["sizes"]) * manifest["trials"]:
        raise ValueError("Unexpected number of benchmark samples")
    frame["operation"] = frame["queue_op"].replace({
        "appendleft": "enqueue", "pop": "dequeue", "__getitem__": "getitem",
    })
    keys = ["version", "queue_type", "operation", "size"]
    counts = frame.groupby(keys).size()
    expected = pd.MultiIndex.from_product(
        [("before", "after"), COLORS, operations, manifest["sizes"]], names=keys)
    if not counts.reindex(expected).eq(manifest["trials"]).all() or len(counts) != len(expected):
        raise ValueError("Missing or mismatched benchmark samples")
    valid_time = frame["time"].gt(0) & frame["time"].lt(float("inf"))
    if frame.duplicated(keys + ["block", "trial"]).any() or not valid_time.all():
        raise ValueError("Invalid benchmark samples")
    frame.to_csv(output / "timings.csv", index=False)
    means = frame.groupby(keys)["time"].mean()
    means.rename("mean_microseconds").to_csv(output / "means.csv")

    columns = min(2, len(operations))
    rows = (len(operations) + columns - 1) // columns
    figure, axes = plt.subplots(rows, columns, squeeze=False,
                               figsize=(15 if columns == 2 else 10, 9 if rows == 2 else 5.4))
    for axis in list(axes.flat)[len(operations):]:
        axis.set_visible(False)
    for axis, (operation, title) in zip(axes.flat, operations.items()):
        for queue, color in COLORS.items():
            for version, style in STYLES:
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
    figure.suptitle("fastqueue_example.py: current changes", fontsize=21, y=0.98)
    figure.legend(handles=legend_handles(manifest["labels"]), loc="upper center", bbox_to_anchor=(0.5, 0.94),
                  ncol=5 if columns == 2 else 3, frameon=False)
    figure.text(0.5, 0.025,
                "{} measured trials per size and version; {} serial paired blocks. "
                "Means match the original example; construction and destruction are outside timers."
                .format(manifest["trials"], manifest["blocks"]), ha="center", fontsize=9, color="#555555")
    figure.subplots_adjust(left=0.075, right=0.98, bottom=0.16 if rows == 1 else 0.11, top=0.81,
                           wspace=0.21, hspace=0.36)
    for suffix in ("png", "svg"):
        target = output / ("comparison." + suffix)
        figure.savefig(target, dpi=160)
        print("Saved {}".format(target.resolve()))
    plt.close(figure)
    plot_memory(output, manifest)


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
    parser.add_argument("--operations", nargs="+", choices=OPERATIONS, default=list(OPERATIONS),
                        help="Operations to benchmark (default: all four)")
    parser.add_argument("--sizes", nargs="+", type=int,
                        help="Explicit increasing sizes; overrides --step and --max-size")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--plot-only", action="store_true", help="Regenerate figures from saved timings")
    parser.add_argument("--worker", choices=("before", "after"), help=argparse.SUPPRESS)
    parser.add_argument("--memory-worker", choices=("before", "after"), help=argparse.SUPPRESS)
    parser.add_argument("--block", type=int, default=1, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.memory_worker:
        measure_memory(args.output, args.memory_worker)
        return
    if args.plot_only:
        plot(args.output)
        return
    if args.before is None:
        parser.error("--before is required unless --plot-only is used")
    if not args.before.is_dir() or not args.after.is_dir():
        parser.error("--before and --after must be built checkout directories")
    if args.sizes is not None and (any(size < 1 for size in args.sizes)
                                  or args.sizes != sorted(set(args.sizes))):
        parser.error("--sizes must contain unique increasing positive values")
    if len(set(args.operations)) != len(args.operations):
        parser.error("--operations must not contain duplicates")
    if (args.sizes is None and (args.step < 1 or args.max_size < args.step)) or not 1 <= args.blocks <= args.trials:
        parser.error("Require valid sizes and 1 <= blocks <= trials")
    if args.worker:
        measure(args)
    else:
        compare(args)
        plot(args.output)


if __name__ == "__main__":
    main()
