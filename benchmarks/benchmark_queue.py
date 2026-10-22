"""Reproducible, single-threaded queue microbenchmarks using only the stdlib.

Run identical commands with --root pointing to each separately built version.
Results include raw samples, import paths, and nanoseconds per roundtrip/item
(or per copy). GC is disabled during timing; cycle collection is not benchmarked.
"""

import argparse
import gc
import json
from pathlib import Path
import platform
import statistics
import sys
import time


def workloads(queue_type, iterations, keepalive):
    payloads = tuple(range(512))
    queue = queue_type()
    keepalive.append(queue)
    for item in payloads:
        queue.enqueue(item)
    assert tuple(queue.dequeue() for _ in payloads) == payloads
    assert queue.__len__() == 0
    enqueue, dequeue = queue.enqueue, queue.dequeue

    def roundtrip():
        for _ in range(iterations):
            enqueue(payloads[0])
            dequeue()

    batches = max(1, iterations // len(payloads))

    def batch():
        for _ in range(batches):
            for item in payloads:
                enqueue(item)
            for _ in payloads:
                dequeue()

    yield "roundtrip", roundtrip, iterations
    yield "batch512", batch, batches * len(payloads)
    if hasattr(queue, "clear"):
        for size in (0, 8, 512):
            clear_items = payloads[:size]
            clear_rounds = max(1, iterations // max(1, size))

            def fill_clear():
                for _ in range(clear_rounds):
                    for item in clear_items:
                        enqueue(item)
                    queue.clear()

            yield "clear%d" % size, fill_clear, clear_rounds
            assert not queue
    if not hasattr(queue, "extend"):
        return

    for size in (8, 512):
        queue.extend(payloads)
        items = payloads[:size]
        rounds = max(1, iterations // size)

        def extend():
            for _ in range(rounds):
                queue.extend(items)
                for _ in items:
                    dequeue()

        yield "extend%d" % size, extend, rounds * size
        for _ in payloads:
            dequeue()
        assert not queue

    growth_items = payloads[:8]
    growth_size = 8192
    growth_rounds = max(1, iterations // growth_size)

    def extend_growth():
        for _ in range(growth_rounds):
            growing = queue_type()
            # Keep destruction outside this workload's timing.
            keepalive.append(growing)
            growing_dequeue = growing.dequeue
            for _ in range(growth_size // len(growth_items)):
                growing.extend(growth_items)
            for _ in range(growth_size):
                growing_dequeue()

    yield "extend_growth8", extend_growth, growth_rounds * growth_size
    assert not queue

    queue.extend(payloads)
    copy_queue = queue.copy
    copied = copy_queue()
    assert tuple(copied.dequeue() for _ in payloads) == payloads

    def copy_drain():
        for _ in range(batches):
            copied = copy_queue()
            for _ in payloads:
                copied.dequeue()

    def copy_release():
        for _ in range(batches):
            copied = copy_queue()
            del copied

    yield "copy_drain512", copy_drain, batches
    yield "copy_release512", copy_release, batches
    for _ in payloads:
        dequeue()
    assert not queue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--iterations", type=int, default=2_000_000)
    parser.add_argument("--filter", default="", help="run matching Queue.workload names")
    args = parser.parse_args()
    if args.samples < 3 or args.iterations < 512:
        parser.error("use at least 3 samples and 512 iterations")
    root = args.root.resolve()
    sys.path.insert(0, str(root))
    import _fastqueue
    import fastqueue
    from fastqueue.prototypes import ContQueue, LLQueue

    assert Path(fastqueue.__file__).resolve().parent == root / "fastqueue"
    assert Path(_fastqueue.__file__).resolve().parent == root
    gc.disable()
    keepalive = []
    results = []
    print("Imported %s" % _fastqueue.__file__, flush=True)
    for queue_type in (fastqueue.Queue, fastqueue.QueueC, LLQueue, ContQueue):
        iterations = args.iterations
        if queue_type in (LLQueue, ContQueue):
            iterations = max(512, iterations // 4)
        for name, run, units in workloads(queue_type, iterations, keepalive):
            if args.filter not in "%s.%s" % (queue_type.__name__, name):
                continue
            run()
            run()
            samples = []
            for _ in range(args.samples):
                start = time.perf_counter_ns()
                run()
                samples.append((time.perf_counter_ns() - start) / units)
            result = {"queue": queue_type.__name__, "workload": name,
                      "median_ns": statistics.median(samples),
                      "min_ns": min(samples), "max_ns": max(samples),
                      "samples_ns": samples, "units_per_sample": units}
            results.append(result)
            print("%-10s %-16s %10.1f ns [%10.1f, %10.1f]" %
                  (result["queue"], name, result["median_ns"],
                   result["min_ns"], result["max_ns"]), flush=True)
    report = {"python": sys.version, "platform": platform.platform(),
              "root": str(root), "extension": _fastqueue.__file__,
              "iterations": args.iterations, "warmups": 2,
              "filter": args.filter,
              "gc_enabled": False, "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
