"""Memory regressions run in subprocesses to contain native crashes and leaks.

tracemalloc covers Python allocations, not the queues' raw malloc buffers.
Payload ownership and reference cycles are checked through weak references.
"""

import gc
import os
import subprocess
import sys
import tracemalloc
import weakref
from pathlib import Path

import pytest

from fastqueue import Queue, QueueC
from fastqueue.prototypes import ContQueue, LLQueue


QUEUE_TYPES = [Queue, QueueC, LLQueue, ContQueue]
PUBLIC_QUEUE_TYPES = [Queue, QueueC]
ITERATIONS = 20_000
MAX_GROWTH = 4 * 1024


class Payload:
    pass


def _create_empty(queue_type):
    queue_type()


def _enqueue_dequeue(queue_type):
    queue = queue_type()
    queue.enqueue(bytearray(128))
    queue.dequeue()


def _delete_populated(queue_type):
    queue = queue_type()
    # Containers exercise cleanup of GC-tracked objects as well as their data.
    queue.enqueue([bytearray(128)])


def _copy_populated(queue_type):
    queue = queue_type()
    queue.enqueue([bytearray(128)])
    copied = queue.copy()
    queue.dequeue()
    del copied


def _extend_nonempty(queue_type):
    queue = queue_type([None, None])
    # Exercise QueueC's branch for an extension shorter than the current queue.
    queue.extend([bytearray(128)])
    while queue:
        queue.dequeue()


def _create_cycle(queue_type):
    queue = queue_type()
    payload = Payload()
    payload.queue = queue
    queue.enqueue(payload)


WORKLOADS = {
    "create_empty": _create_empty,
    "enqueue_dequeue": _enqueue_dequeue,
    "delete_populated": _delete_populated,
    "copy_populated": _copy_populated,
    "extend_nonempty": _extend_nonempty,
    "collect_cycle": _create_cycle,
}


def _check_no_memory_growth(queue_type, workload):
    def run_many():
        for _ in range(ITERATIONS):
            workload(queue_type)

    tracemalloc.start()
    try:
        run_many()
        gc.collect()
        before = tracemalloc.take_snapshot()
        gc.collect()

        run_many()
        gc.collect()
        after = tracemalloc.take_snapshot()
        growth = sum(stat.size_diff for stat in after.compare_to(before, "lineno"))
    finally:
        tracemalloc.stop()

    assert growth < MAX_GROWTH, (
        f"{queue_type.__name__}: memory growth detected: {growth} bytes "
        f"(limit: {MAX_GROWTH} bytes)"
    )


def _check_releases_payload(queue_type):
    queue = queue_type()
    payload = Payload()
    reference = weakref.ref(payload)
    queue.enqueue(payload)
    del payload
    gc.collect()
    assert reference() is not None, "Queue released a payload it still owns"

    del queue
    gc.collect()
    assert reference() is None, "Queue retained its payload after collection"


def _check_releases_wrapped_payloads(queue_type):
    queue = queue_type()
    references = []
    for _ in range(512):
        payload = Payload()
        references.append(weakref.ref(payload))
        queue.enqueue(payload)
    del payload
    for _ in range(257):
        queue.dequeue()
    for _ in range(257):
        payload = Payload()
        references.append(weakref.ref(payload))
        queue.enqueue(payload)
    del payload
    gc.collect()
    assert all(ref() is None for ref in references[:257])
    assert all(ref() is not None for ref in references[257:])
    del queue
    gc.collect()
    assert all(ref() is None for ref in references)


def _check_copy_ownership(queue_type):
    queue = queue_type()
    references = []
    for _ in range(600):
        payload = Payload()
        references.append(weakref.ref(payload))
        queue.enqueue(payload)
    del payload
    for _ in range(257):
        queue.dequeue()
    copied = queue.copy()
    del queue
    gc.collect()
    assert all(ref() is not None for ref in references[257:])
    while copied:
        copied.dequeue()
    gc.collect()
    assert all(ref() is None for ref in references)


def _check_extend_iterators(queue_type):
    class SizedIterable:
        def __init__(self, size):
            self.size = size

        def __len__(self):
            return self.size

        def __iter__(self):
            yield Payload()
            yield Payload()

    for size in (0, 1, 10):
        queue = queue_type()
        queue.extend(SizedIterable(size))
        assert len(queue) == 2
        references = [weakref.ref(queue[0]), weakref.ref(queue[1])]
        del queue
        gc.collect()
        assert all(ref() is None for ref in references)

    references = []

    def broken_iterator():
        payload = Payload()
        references.append(weakref.ref(payload))
        yield payload
        raise RuntimeError("iterator failed")

    queue = queue_type()
    with pytest.raises(RuntimeError, match="iterator failed"):
        queue.extend(broken_iterator())
    assert len(queue) == 1
    del queue
    gc.collect()
    assert references[0]() is None

    payload = Payload()
    reference = weakref.ref(payload)
    queue = queue_type([payload])
    del payload
    queue.extend(queue)
    queue.dequeue()
    gc.collect()
    assert reference() is not None
    del queue
    gc.collect()
    assert reference() is None


def _check_indexing_ownership(queue_type):
    queue = queue_type(range(600))
    for _ in range(100):
        queue.dequeue()
    assert queue[300] == 400
    assert queue[-1] == 599
    payload = Payload()
    reference = weakref.ref(payload)
    queue[300] = payload
    del payload
    assert queue[300] is reference()
    queue[300] = 400
    gc.collect()
    assert reference() is None
    for index in (-len(queue) - 1, len(queue)):
        with pytest.raises(IndexError):
            queue[index]
        payload = Payload()
        reference = weakref.ref(payload)
        with pytest.raises(IndexError):
            queue[index] = payload
        del payload
        gc.collect()
        assert reference() is None
    with pytest.raises(TypeError):
        del queue[0]
    assert list(queue) == list(range(100, 600))


def _check_extend_hints_release_payloads(queue_type):
    count = 4097
    for reported in (None, 0, 1, count, 20_000):
        queue = queue_type()
        references = []

        def values():
            for _ in range(count):
                payload = Payload()
                references.append(weakref.ref(payload))
                yield payload

        class SizedIterable:
            def __len__(self):
                return reported

            def __iter__(self):
                return values()

        queue.extend(values() if reported is None else SizedIterable())
        assert len(queue) == count
        gc.collect()
        assert all(reference() is not None for reference in references)
        queue.clear()
        gc.collect()
        assert not queue
        assert all(reference() is None for reference in references)


def _check_clear_after_partial_drain(queue_type):
    queue = queue_type()
    references = []
    for _ in range(2050):
        payload = Payload()
        references.append(weakref.ref(payload))
        queue.enqueue(payload)
    del payload
    for _ in range(1500):
        queue.dequeue()
    for _ in range(2500):
        payload = Payload()
        references.append(weakref.ref(payload))
        queue.enqueue(payload)
    del payload
    queue.clear()
    gc.collect()
    assert not queue
    assert all(reference() is None for reference in references)
    queue.clear()
    payload = Payload()
    reference = weakref.ref(payload)
    queue.enqueue(payload)
    del payload, queue
    gc.collect()
    assert reference() is None


def _check_native_clear_reentry(queue_type):
    queue = queue_type()
    observations = []
    references = []

    class ReentrantPayload:
        def __del__(self):
            observations.append(len(queue))
            payload = Payload()
            references.append(weakref.ref(payload))
            queue.enqueue(payload)
            del payload
            queue.clear()
            observations.append(len(queue))
            queue.extend(range(4097))

    queue.enqueue(ReentrantPayload())
    for _ in range(1500):
        payload = Payload()
        references.append(weakref.ref(payload))
        queue.enqueue(payload)
    del payload
    queue.clear()
    gc.collect()
    assert observations == [1500, 0]
    assert all(reference() is None for reference in references)
    assert not queue
    queue.clear()
    assert not queue
    queue.enqueue(42)
    assert queue.dequeue() == 42

    observations.clear()
    references.clear()
    added = 4097
    queue = queue_type(range(1025))

    class GrowingPayload:
        def __del__(self):
            removed = queue.dequeue()
            observations.append(removed is references[0]())
            del removed
            values = [Payload() for _ in range(added)]
            references.extend(weakref.ref(value) for value in values)
            queue.extend(values)

    queue.enqueue(GrowingPayload())
    for _ in range(2):
        payload = Payload()
        references.append(weakref.ref(payload))
        queue.enqueue(payload)
    del payload
    queue.clear()
    gc.collect()
    assert observations == [True]
    assert len(references) == added + 2
    assert all(reference() is None for reference in references)
    assert not queue


def _check_prototype_clear(queue_type):
    queue = queue_type()
    payload = Payload()
    reference = weakref.ref(payload)
    queue.enqueue(payload)
    del payload
    queue.clear()
    gc.collect()
    assert reference() is None
    assert not queue
    queue.clear()
    queue.enqueue(42)
    assert queue.dequeue() == 42


def _check_reentrant_setitem(queue_type):
    queue = queue_type()
    removed = []

    class ReentrantPayload:
        def __del__(self):
            while queue:
                removed.append(queue.dequeue())
            queue.extend(("from finalizer",) * 600)

    queue.enqueue(ReentrantPayload())
    queue.extend(range(300))
    queue[0] = "replacement"
    assert removed == ["replacement"] + list(range(300))
    assert [queue.dequeue() for _ in range(600)] == ["from finalizer"] * 600
    assert not queue


def _check_reentrant_clear(queue_type):
    queue = queue_type()

    class ReentrantPayload:
        def __del__(self):
            queue.enqueue("from finalizer")

    queue.enqueue(ReentrantPayload())
    queue.clear()
    assert queue.dequeue() == "from finalizer"
    assert not queue


def _check_clear_finalizer_refill(queue_type):
    queue = queue_type()
    observations = []

    class ReentrantPayload:
        def __del__(self):
            observations.append((len(queue), not queue))
            queue.enqueue("temporary")
            queue.clear()
            for value in range(600):
                queue.enqueue(value)

    queue.clear()
    queue.enqueue(ReentrantPayload())
    payload = Payload()
    reference = weakref.ref(payload)
    queue.enqueue(payload)
    del payload
    queue.clear()
    gc.collect()
    assert observations == [(0, True)]
    assert reference() is None
    assert [queue.dequeue() for _ in range(600)] == list(range(600))
    assert not queue
    queue.clear()


def _check_deeply_nested_queues(queue_type):
    current = Payload()
    reference = weakref.ref(current)
    for _ in range(5000):
        queue = queue_type()
        queue.enqueue(current)
        current = queue
    del queue, current
    gc.collect()
    assert reference() is None


def _check_repeated_drain_releases_payloads(queue_type):
    queue = queue_type()
    for _ in range(3):
        values = [Payload() for _ in range(1025)]
        references = [weakref.ref(value) for value in values]
        queue.extend(values)
        del values
        while queue:
            queue.dequeue()
        gc.collect()
        assert all(reference() is None for reference in references)


def _check_cycle_after_drain(queue_type):
    values = (None,) * 4097
    queue = queue_type(values)
    for _ in values:
        queue.dequeue()
    payload = Payload()
    reference = weakref.ref(payload)
    payload.queue = queue
    queue.enqueue(payload)
    del payload, queue
    gc.collect()
    assert reference() is None


def _check_large_contiguous_cycle(queue_type):
    references = []

    def values(count):
        for _ in range(count):
            payload = Payload()
            references.append(weakref.ref(payload))
            yield payload

    queue = queue_type(values(40_000))
    for _ in range(20_000):
        queue.dequeue()
    queue.extend(values(40_000))
    gc.collect()
    assert all(reference() is None for reference in references[:20_000])
    assert all(reference() is not None for reference in references[20_000:])
    copied = queue.copy()

    class LargeHint:
        def __len__(self):
            return 9_000_000

        def __iter__(self):
            return iter(())

    # A large length hint must preserve ownership of the existing payloads.
    queue.extend(LargeHint())
    assert len(queue) == len(copied) == 60_000
    payload = Payload()
    payload.queue = queue
    reference = weakref.ref(payload)
    queue.enqueue(payload)
    del payload, queue
    gc.collect()
    assert reference() is None
    assert all(reference() is not None for reference in references[20_000:])
    del copied
    gc.collect()
    assert all(reference() is None for reference in references)


CHECKS = {
    "large_contiguous_cycle": _check_large_contiguous_cycle,
    "release_payload": _check_releases_payload,
    "release_wrapped_payloads": _check_releases_wrapped_payloads,
    "copy_ownership": _check_copy_ownership,
    "extend_iterators": _check_extend_iterators,
    "indexing_ownership": _check_indexing_ownership,
    "extend_hints_release_payloads": _check_extend_hints_release_payloads,
    "clear_after_partial_drain": _check_clear_after_partial_drain,
    "native_clear_reentry": _check_native_clear_reentry,
    "prototype_clear": _check_prototype_clear,
    "reentrant_clear": _check_reentrant_clear,
    "clear_finalizer_refill": _check_clear_finalizer_refill,
    "reentrant_setitem": _check_reentrant_setitem,
    "deeply_nested": _check_deeply_nested_queues,
    "repeated_drain": _check_repeated_drain_releases_payloads,
    "cycle_after_drain": _check_cycle_after_drain,
}


def _run_in_subprocess(queue_type, scenario):
    result = subprocess.run(
        [
            sys.executable, "-X", "faulthandler", str(Path(__file__).resolve()),
            queue_type.__name__, scenario,
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
        timeout=60,
    )
    assert result.returncode == 0, (
        f"{queue_type.__name__}/{scenario} exited with {result.returncode}\n"
        f"{result.stdout}{result.stderr}"
    )


@pytest.mark.parametrize("queue_type", QUEUE_TYPES, ids=lambda cls: cls.__name__)
@pytest.mark.parametrize(
    "workload", ["create_empty", "enqueue_dequeue", "delete_populated"]
)
def test_no_memory_growth(queue_type, workload):
    _run_in_subprocess(queue_type, workload)


@pytest.mark.parametrize(
    "queue_type", PUBLIC_QUEUE_TYPES, ids=lambda cls: cls.__name__
)
@pytest.mark.parametrize("workload", ["copy_populated", "extend_nonempty"])
def test_sequence_operations_no_memory_growth(queue_type, workload):
    _run_in_subprocess(queue_type, workload)


@pytest.mark.parametrize("queue_type", QUEUE_TYPES, ids=lambda cls: cls.__name__)
@pytest.mark.parametrize("scenario", ["release_payload", "release_wrapped_payloads"])
def test_deleting_queue_releases_payload(queue_type, scenario):
    _run_in_subprocess(queue_type, scenario)


@pytest.mark.parametrize(
    "queue_type", PUBLIC_QUEUE_TYPES, ids=lambda cls: cls.__name__
)
@pytest.mark.parametrize(
    "scenario",
    ["copy_ownership", "extend_iterators", "indexing_ownership"],
)
def test_sequence_operations_release_payloads(queue_type, scenario):
    _run_in_subprocess(queue_type, scenario)


@pytest.mark.parametrize("queue_type", QUEUE_TYPES, ids=lambda cls: cls.__name__)
def test_clear_after_partial_drain_releases_payloads(queue_type):
    _run_in_subprocess(queue_type, "clear_after_partial_drain")


@pytest.mark.parametrize(
    "queue_type", PUBLIC_QUEUE_TYPES, ids=lambda cls: cls.__name__
)
def test_extend_hints_release_payloads(queue_type):
    _run_in_subprocess(queue_type, "extend_hints_release_payloads")


@pytest.mark.parametrize(
    "queue_type", PUBLIC_QUEUE_TYPES, ids=lambda cls: cls.__name__
)
def test_native_clear_allows_reentry(queue_type):
    _run_in_subprocess(queue_type, "native_clear_reentry")


@pytest.mark.parametrize("queue_type", [LLQueue, ContQueue], ids=lambda cls: cls.__name__)
@pytest.mark.parametrize(
    "scenario", ["prototype_clear", "reentrant_clear", "clear_finalizer_refill"]
)
def test_clear_releases_payloads(queue_type, scenario):
    _run_in_subprocess(queue_type, scenario)


@pytest.mark.parametrize(
    "queue_type", PUBLIC_QUEUE_TYPES, ids=lambda cls: cls.__name__
)
def test_replacing_payload_allows_reentry(queue_type):
    _run_in_subprocess(queue_type, "reentrant_setitem")


@pytest.mark.parametrize(
    "queue_type", PUBLIC_QUEUE_TYPES, ids=lambda cls: cls.__name__
)
def test_deeply_nested_queues_are_released(queue_type):
    _run_in_subprocess(queue_type, "deeply_nested")


@pytest.mark.parametrize(
    "queue_type", PUBLIC_QUEUE_TYPES, ids=lambda cls: cls.__name__
)
def test_reference_cycles_are_collected(queue_type):
    _run_in_subprocess(queue_type, "collect_cycle")


@pytest.mark.parametrize(
    "queue_type", PUBLIC_QUEUE_TYPES, ids=lambda cls: cls.__name__
)
@pytest.mark.parametrize("scenario", ["repeated_drain", "cycle_after_drain"])
def test_reused_queue_releases_payloads(queue_type, scenario):
    _run_in_subprocess(queue_type, scenario)


def test_large_contiguous_cycle_is_collected():
    _run_in_subprocess(QueueC, "large_contiguous_cycle")


if __name__ == "__main__":
    queue_type = next(cls for cls in QUEUE_TYPES if cls.__name__ == sys.argv[1])
    scenario = sys.argv[2]
    if scenario in WORKLOADS:
        _check_no_memory_growth(queue_type, WORKLOADS[scenario])
    else:
        CHECKS[scenario](queue_type)
