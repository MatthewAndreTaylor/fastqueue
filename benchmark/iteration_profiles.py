"""Compare indexed updates with iterator traversal over integer values.

Indexed increments write back to the container. Increments of values yielded by
an iterator only rebind the local variable, leaving these containers unchanged.
"""

import argparse
from collections import deque
from pathlib import Path
import random
from statistics import mean, stdev
import time

import matplotlib.pyplot as plt
import numpy

from fastqueue import Queue, QueueC

STRUCTURES = {
    "QueueC (contiguous)": QueueC,
    "Queue (non-contiguous)": Queue,
    "collections.deque": deque,
    "NumPy array": numpy.array,
}


def indexed_increment(o):
    start = time.perf_counter()
    for i in range(len(o)):
        o[i] += 1
    return time.perf_counter() - start


def iterator_local_increment(o):
    start = time.perf_counter()
    for item in o:
        item += 1
    return time.perf_counter() - start


WORKLOADS = {
    "construction": (
        None,
        "Container construction",
        "o = container_type(values)",
        "Build a container from a prebuilt list of integers.",
        "Iterable_Instantiation",
    ),
    "indexed_increment": (
        indexed_increment,
        "Indexed in-place increment",
        "for i in range(len(o)):\n    o[i] += 1",
        "Read, increment and write back every stored value. The container changes.\n"
        "Indexed_Increment",
    ),
    "iterator_local_increment": (
        iterator_local_increment,
        "Iterator traversal + local increment",
        "for item in o:\n    item += 1",
        "Visit every value and increment the local variable. The integer container is unchanged.\n"
        "Iterator_Local_Increment",
    ),
}


def collect(size, trials, warmups):
    if size < 1 or trials < 1 or warmups < 0:
        raise ValueError(
            "size and trials must be positive; warmups must be nonnegative"
        )
    values = list(range(size))
    rows = [
        {"operation": operation, "structure": structure, "samples_seconds": []}
        for operation in WORKLOADS
        for structure in STRUCTURES
    ]
    profiles = rows[:]
    rng = random.Random(1)
    for trial in range(warmups + trials):
        if trial < warmups:
            print(f"Iteration warmup: {trial + 1}/{warmups}", flush=True)
        else:
            print(f"Iteration trial: {trial - warmups + 1}/{trials}", flush=True)
        rng.shuffle(profiles)
        for row in profiles:
            structure = STRUCTURES[row["structure"]]
            operation = WORKLOADS[row["operation"]][0]
            if operation is None:
                start = time.perf_counter()
                o = structure(values)
                elapsed = time.perf_counter() - start
            else:
                o = structure(values)
                elapsed = operation(o)
            del o
            if trial >= warmups:
                row["samples_seconds"].append(elapsed)
    return {
        "size": size,
        "trials": trials,
        "warmups": warmups,
        "seed": 1,
        "clock": "perf_counter",
        "statistic": "arithmetic mean",
        "results": rows,
    }


def plot_times(
    title, snippet, explanation, times, deviations, size, trials, warmups, filename
):
    figure, axis = plt.subplots(figsize=(12, 7))
    figure.suptitle(title, fontsize=17, y=0.96)
    figure.text(
        0.5,
        0.89,
        snippet,
        ha="center",
        va="top",
        multialignment="left",
        family="monospace",
        fontsize=12,
    )
    figure.text(0.5, 0.76, explanation, ha="center", fontsize=10)
    axis.bar(
        list(STRUCTURES),
        times,
        color=["#009E73", "#0072B2", "#D55E00", "#CC79A7"],
        width=0.5,
        yerr=deviations,
        capsize=5,
        error_kw={"ecolor": "black", "elinewidth": 1.2},
    )
    errors = deviations if deviations is not None else [0] * len(times)
    upper = [elapsed + error for elapsed, error in zip(times, errors)]
    lower = [elapsed - error for elapsed, error in zip(times, errors)]
    for i, (elapsed, top) in enumerate(zip(times, upper)):
        axis.annotate(
            f"{elapsed:.6f}",
            (i, top),
            xytext=(0, 5),
            textcoords="offset points",
            ha="center",
        )
    axis.set_ylabel("Mean elapsed time (seconds)")
    axis.set_xlabel("Container type")
    axis.set_ylim(min(0, min(lower)), max(upper) * 1.2 if max(upper) else 1)
    uncertainty = (
        "Error bars: +/-1 sample standard deviation."
        if deviations is not None
        else "Standard deviation unavailable with fewer than two samples."
    )
    figure.text(
        0.5,
        0.03,
        f"{size:,} integer items; {trials} measured trials per type; "
        f"{warmups} warmups. Arithmetic means.",
        ha="center",
        fontsize=9,
    )
    figure.subplots_adjust(top=0.69, bottom=0.15)
    for suffix in ("png", "svg"):
        target = filename.with_suffix("." + suffix)
        figure.savefig(target, dpi=160, metadata={"Date": None})
        print(f"Saved {target}", flush=True)
    plt.close(figure)


def plot(result, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    samples = {
        (row["operation"], row["structure"]): row["samples_seconds"]
        for row in result["results"]
    }
    expected = {
        (operation, structure) for operation in WORKLOADS for structure in STRUCTURES
    }
    if not expected <= samples.keys() or any(not samples[key] for key in expected):
        raise ValueError(
            "Measurements lack required iteration workloads; rerun without --plot-only"
        )
    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none"})
    for operation, (_, title, snippet, explanation, filename) in WORKLOADS.items():
        measured = [samples[operation, structure] for structure in STRUCTURES]
        times = [mean(values) for values in measured]
        deviations = (
            [stdev(values) for values in measured]
            if all(len(values) >= 2 for values in measured)
            else None
        )
        plot_times(
            title,
            snippet,
            explanation,
            times,
            deviations,
            result["size"],
            result["trials"],
            result["warmups"],
            output / filename,
        )


def main(size=500_000, trials=5, warmups=2, output=Path("docs/benchmarks")):
    plot(collect(size, trials, warmups), output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path("docs/benchmarks"))
    args = parser.parse_args()
    if args.trials < 1 or args.warmups < 0:
        parser.error("--trials must be positive; --warmups must be nonnegative")
    main(trials=args.trials, warmups=args.warmups, output=args.output)
