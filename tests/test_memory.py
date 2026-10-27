"""Memory regressions run in subprocesses to contain native crashes and leaks.

tracemalloc covers Python allocations, not the queues' raw malloc buffers.
The Queue node-cache check inspects native pointers separately to verify reuse.
"""

import gc
import os
import subprocess
import sys
import tracemalloc
import weakref
from ctypes import (
    cast, c_int, c_size_t, c_ssize_t, c_void_p, py_object,
    pythonapi, sizeof,
)
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


def _queuec_storage(queue):
    assert type(queue).__basicsize__ == (
        object.__basicsize__ + 3 * sizeof(c_size_t) + sizeof(c_void_p)
    )
    address = id(queue) + object.__basicsize__
    fields = (c_size_t * 3).from_address(address)
    buffer = c_void_p.from_address(address + 3 * sizeof(c_size_t)).value
    return fields[1], buffer


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

    queue = queue_type([1, 2, 3])
    queue.extend(queue)
    assert list(queue) == [1, 2, 3, 1, 2, 3]
    queue.__init__([4])
    assert list(queue) == [1, 2, 3, 1, 2, 3, 4]


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
        with pytest.raises(IndexError):
            queue[index] = Payload()
    with pytest.raises(TypeError):
        del queue[0]
    assert list(queue) == list(range(100, 600))


def _check_reentrant_extend(queue_type):
    queue = queue_type([10])

    def values():
        yield len(queue)
        queue.enqueue(20)
        yield queue.dequeue()

    queue.extend(values())
    assert list(queue) == [1, 20, 10]


def _check_contiguous_extend_resize(queue_type):
    for reported in (None, 0, 1, "exact", 20_000):
        queue = queue_type(["existing"])
        initial_capacity = _queuec_storage(queue)[0]
        capacities = [initial_capacity]
        count = initial_capacity * 4 + 1
        if reported == "exact":
            reported = count

        def values():
            for value in range(count):
                capacities.append(_queuec_storage(queue)[0])
                yield value

        class SizedIterable:
            def __len__(self):
                return reported

            def __iter__(self):
                return values()

        queue.extend(values() if reported is None else SizedIterable())
        capacities.append(_queuec_storage(queue)[0])
        if reported is not None and reported >= count:
            assert sum(a != b for a, b in zip(capacities, capacities[1:])) == 1
            assert capacities[1:] == [capacities[-1]] * (count + 1)
        assert all(a <= b for a, b in zip(capacities, capacities[1:]))
        assert capacities[-1] >= len(queue)
        assert list(queue) == ["existing"] + list(range(count))


def _check_native_contiguous_clear(queue_type):
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
    storage = _queuec_storage(queue)
    queue.clear()
    gc.collect()
    assert not queue
    assert all(reference() is None for reference in references)
    assert _queuec_storage(queue) == storage
    queue.clear()
    queue.extend(range(storage[0]))
    assert _queuec_storage(queue) == storage
    assert [queue.dequeue() for _ in range(storage[0])] == list(range(storage[0]))


def _check_native_clear_reentry(queue_type):
    queue = queue_type()
    observations = []
    references = []

    class ReentrantPayload:
        def __del__(self):
            observations.append(len(queue))
            if queue_type is QueueC:
                observations.append(_queuec_storage(queue) == storage)
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
    storage = _queuec_storage(queue) if queue_type is QueueC else None
    queue.clear()
    gc.collect()
    assert observations == ([1500, True, 0] if queue_type is QueueC else [1500, 0])
    assert all(reference() is None for reference in references)
    assert not queue
    if queue_type is QueueC:
        assert _queuec_storage(queue)[0] > storage[0]
    queue.clear()
    assert not queue
    queue.enqueue(42)
    assert queue.dequeue() == 42

    observations.clear()
    references.clear()
    capacity = _queuec_storage(queue)[0] if queue_type is QueueC else None
    added = capacity + 1 if queue_type is QueueC else 4097
    if queue_type is Queue:
        # The finalizer runs as the first node empties and becomes reusable.
        queue = queue_type(range(255))

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
    if queue_type is QueueC:
        assert _queuec_storage(queue)[0] > capacity


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


def _check_clear_reuses_queue(queue_type):
    queue = queue_type()
    native_queue = queue.queue
    observations = []

    class ReentrantPayload:
        def __del__(self):
            observations.append(
                (len(queue), not queue, queue.queue is native_queue)
            )
            queue.enqueue("temporary")
            queue.clear()
            for value in range(600):
                queue.enqueue(value)

    queue.clear()
    assert queue.queue is native_queue
    queue.enqueue(ReentrantPayload())
    payload = Payload()
    reference = weakref.ref(payload)
    queue.enqueue(payload)
    del payload
    queue.clear()
    gc.collect()
    assert observations == [(0, True, True)]
    assert reference() is None
    assert queue.queue is native_queue
    assert [queue.dequeue() for _ in range(600)] == list(range(600))
    assert not queue
    queue.clear()
    assert queue.queue is native_queue


def _check_contiguous_buffer_reuse(queue_type):
    queue = queue_type()
    references = []
    for _ in range(600):
        payload = Payload()
        references.append(weakref.ref(payload))
        queue.enqueue(payload)
    del payload
    for _ in range(257):
        queue.dequeue()
    for _ in range(400):
        payload = Payload()
        references.append(weakref.ref(payload))
        queue.enqueue(payload)
    del payload
    buffer = cast(queue.queue.contents.objects, c_void_p).value
    capacity = queue.queue.contents.capacity
    queue.clear()
    gc.collect()
    assert all(ref() is None for ref in references)
    assert cast(queue.queue.contents.objects, c_void_p).value == buffer
    assert queue.queue.contents.capacity == capacity
    queue.clear()
    queue.enqueue(42)
    assert queue.dequeue() == 42


def _check_prototype_destructor(queue_type):
    uninitialized = queue_type.__new__(queue_type)
    uninitialized.__del__()
    uninitialized.__del__()

    queue = queue_type()
    observations = []

    class ReentrantPayload:
        def __del__(self):
            observations.append(queue.queue is None)
            queue.__del__()

    payload = ReentrantPayload()
    reference = weakref.ref(payload)
    queue.enqueue(payload)
    del payload
    queue.__del__()
    assert observations == [True]
    assert reference() is None
    assert queue.queue is None
    queue.__del__()


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


def _queue_chunk_length(queue_type):
    probe = queue_type()
    pointers = (c_void_p * 2).from_address(id(probe) + object.__basicsize__)
    count = 0
    while pointers[0] == pointers[1]:
        probe.enqueue(None)
        count += 1
    return count - 1


def test_queue_head_and_tail_entry_counts():
    chunklen = _queue_chunk_length(Queue)
    queue = Queue()

    def entry_counts(value):
        address = (
            id(value) + object.__basicsize__
            + 2 * sizeof(c_void_p) + sizeof(c_ssize_t)
        )
        tail, head = (c_ssize_t * 2).from_address(address)
        return head, tail

    assert entry_counts(queue) == (0, 0)
    assert entry_counts(queue.copy()) == (0, 0)
    queue.extend(range(2 * chunklen + 7))
    assert entry_counts(queue) == (chunklen, 7)
    for remaining in range(chunklen - 1, 0, -1):
        queue.dequeue()
        assert entry_counts(queue) == (remaining, 7)
    copied = queue.copy()
    assert entry_counts(copied) == (1, 7)
    assert list(copied) == list(queue)
    queue.dequeue()
    assert entry_counts(queue) == (chunklen, 7)
    for _ in range(chunklen):
        queue.dequeue()
    assert entry_counts(queue) == (7, 7)
    queue.dequeue()
    assert entry_counts(queue) == (6, 6)
    copied = queue.copy()
    assert entry_counts(copied) == (6, 6)
    assert list(copied) == list(queue)
    queue.enqueue(None)
    assert entry_counts(queue) == (7, 7)
    while queue:
        queue.dequeue()
    assert entry_counts(queue) == (0, 0)

    # Refilling the retained node starts at a nonzero index and wraps.
    queue.extend(range(chunklen))
    assert entry_counts(queue) == (chunklen, chunklen)
    copied = queue.copy()
    assert entry_counts(copied) == (chunklen, chunklen)
    assert list(copied) == list(queue)
    queue.enqueue(chunklen)
    assert entry_counts(queue) == (chunklen, 1)
    assert list(queue) == list(range(chunklen + 1))
    queue.clear()
    assert entry_counts(queue) == (0, 0)


def _check_chunk_indices_wrap(queue_type):
    chunklen = _queue_chunk_length(queue_type)
    for bulk in (False, True):
        queue = queue_type([0])
        address = (
            id(queue) + object.__basicsize__
            + 2 * sizeof(c_void_p) + 3 * sizeof(c_ssize_t)
        )
        indices = (c_ssize_t * 2).from_address(address)
        for value in range(1, 5 * chunklen):
            if bulk:
                queue.extend(iter((value,)))
            else:
                queue.enqueue(value)
            assert queue.dequeue() == value - 1
            assert all(0 <= index < chunklen for index in indices)
        values = list(range(5 * chunklen, 7 * chunklen + 3))
        if bulk:
            queue.extend(iter(values))
        else:
            for value in values:
                queue.enqueue(value)
        expected = list(range(5 * chunklen - 1, 7 * chunklen + 3))
        assert list(queue) == expected
        assert list(queue.copy()) == expected
        gc.collect()
        for value in expected:
            assert queue.dequeue() == value
            assert all(0 <= index < chunklen for index in indices)
        assert not queue


def _check_cached_nodes_reused(queue_type):
    # Queue owns head, tail, length, both entry counts, indices, and free_nodes.
    assert queue_type.__basicsize__ == (
        object.__basicsize__ + 3 * sizeof(c_void_p)
        + 5 * sizeof(c_ssize_t)
    )
    chunklen = _queue_chunk_length(queue_type)
    queue = queue_type()
    address = id(queue) + object.__basicsize__
    head = c_void_p.from_address(address)
    free_nodes = c_void_p.from_address(
        address + 2 * sizeof(c_void_p) + 5 * sizeof(c_ssize_t)
    )

    def nodes(active):
        pointer = head.value if active else free_nodes.value
        addresses = set()
        while pointer:
            assert pointer not in addresses, "Cycle in native node chain"
            addresses.add(pointer)
            pointer = c_void_p.from_address(pointer).value
        return addresses

    values = (None,) * (4 * chunklen + 1)
    queue.extend(values)
    original = nodes(True)
    assert len(original) > 1
    assert not nodes(False)
    for _ in range(2 * chunklen + 1):
        queue.dequeue()
    active, cached = nodes(True), nodes(False)
    assert cached
    assert active.isdisjoint(cached)
    assert active | cached == original
    queue.extend(values[:2 * chunklen + 1])
    assert nodes(True) == original
    assert not nodes(False)
    for _ in values:
        queue.dequeue()
    active, cached = nodes(True), nodes(False)
    assert len(active) == 1
    assert active.isdisjoint(cached)
    assert active | cached == original
    for _ in values:
        queue.enqueue(None)
    assert nodes(True) == original
    assert not nodes(False)

    queue.clear()
    payloads = [Payload() for _ in values]
    references = [weakref.ref(payload) for payload in payloads]
    queue.extend(payloads)
    del payloads
    for _ in range(2 * chunklen + 1):
        queue.dequeue()
    assert nodes(False)
    queue.clear()
    gc.collect()
    active, cached = nodes(True), nodes(False)
    assert not queue
    assert all(reference() is None for reference in references)
    assert len(active) == 1
    assert active.isdisjoint(cached)
    assert active | cached == original
    queue.clear()
    queue.extend(values)
    assert nodes(True) == original
    assert not nodes(False)
    assert [queue.dequeue() for _ in values] == list(values)


def _check_cached_nodes_release_payloads(queue_type):
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


def _check_cached_nodes_cycle(queue_type):
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


def _check_cached_nodes_iterators(queue_type):
    class SizedIterable:
        def __init__(self, reported, count):
            self.reported = reported
            self.count = count

        def __len__(self):
            return self.reported

        def __iter__(self):
            return iter(range(self.count))

    queue = queue_type()
    for reported, count in (
        (0, 1025), (1, 1025), (4096, 300), (4096, 0),
        (-1, 300), (sys.maxsize + 1, 300),
    ):
        queue.extend(SizedIterable(reported, count))
        assert [queue.dequeue() for _ in range(count)] == list(range(count))
        assert not queue

    class UnsizedIterable:
        def __length_hint__(self):
            raise AssertionError("Queue must not query length hints")

        def __iter__(self):
            return iter(range(1025))

    queue.extend(UnsizedIterable())
    assert [queue.dequeue() for _ in range(1025)] == list(range(1025))

    class InvalidLength(SizedIterable):
        def __len__(self):
            raise self.reported("length failed")

    for error in (RuntimeError, TypeError):
        queue.extend(InvalidLength(error, 300))
        assert [queue.dequeue() for _ in range(300)] == list(range(300))
    assert not queue

    class BrokenIterable(SizedIterable):
        def __iter__(self):
            raise RuntimeError("iter failed")

    with pytest.raises(RuntimeError, match="iter failed"):
        queue.extend(BrokenIterable(4096, 300))
    assert not queue

    class BrokenIterator(SizedIterable):
        def __iter__(self):
            yield from range(300)
            raise RuntimeError("iteration failed")

    with pytest.raises(RuntimeError, match="iteration failed"):
        queue.extend(BrokenIterator(4096, 300))
    assert [queue.dequeue() for _ in range(300)] == list(range(300))
    queue.extend(value for value in range(4097))
    assert [queue.dequeue() for _ in range(4097)] == list(range(4097))


def _check_cached_nodes_reentry(queue_type):
    queue = queue_type(range(600))
    expected = list(range(600))
    calls = set()

    def mutate(name, removed, values):
        calls.add(name)
        assert [queue.dequeue() for _ in range(removed)] == expected[:removed]
        del expected[:removed]
        queue.extend(values)
        expected.extend(values)

    class ReentrantIterable:
        def __init__(self):
            self.position = 0

        def __iter__(self):
            mutate("iter", 300, range(2300, 2900))
            return self

        def __next__(self):
            if self.position == 0:
                mutate("next", 400, range(2900, 3600))
            if self.position == 700:
                raise StopIteration
            value = 4000 + self.position
            self.position += 1
            expected.append(value)
            return value

    queue.extend(ReentrantIterable())
    assert calls == {"iter", "next"}
    assert list(queue) == expected
    copied = queue.copy()
    assert [queue.dequeue() for _ in expected] == expected
    assert [copied.dequeue() for _ in expected] == expected


def _check_large_contiguous_storage(queue_type):
    from collections import deque

    queue = queue_type(range(40000))
    capacity, _ = _queuec_storage(queue)
    expected = deque(range(40000))
    for value in range(40000, capacity):
        queue.enqueue(value)
        expected.append(value)
    for _ in range(capacity // 2):
        assert queue.dequeue() == expected.popleft()
    for value in range(capacity, capacity + capacity // 2 + 1):
        queue.enqueue(value)
        expected.append(value)
    assert list(queue) == list(expected)
    copied = queue.copy()
    assert list(copied) == list(expected)
    del copied

    class LargeHint:
        def __len__(self):
            return 9_000_000

        def __iter__(self):
            return iter(())

    # Exercise large growth without creating millions of payloads.
    queue.extend(LargeHint())
    assert list(queue) == list(expected)
    payload = Payload()
    payload.queue = queue
    reference = weakref.ref(payload)
    queue.enqueue(payload)
    del payload, queue
    gc.collect()
    assert reference() is None


CHECKS = {
    "large_contiguous_storage": _check_large_contiguous_storage,
    "release_payload": _check_releases_payload,
    "release_wrapped_payloads": _check_releases_wrapped_payloads,
    "copy_ownership": _check_copy_ownership,
    "extend_iterators": _check_extend_iterators,
    "indexing_ownership": _check_indexing_ownership,
    "reentrant_extend": _check_reentrant_extend,
    "contiguous_extend_resize": _check_contiguous_extend_resize,
    "native_contiguous_clear": _check_native_contiguous_clear,
    "native_clear_reentry": _check_native_clear_reentry,
    "prototype_clear": _check_prototype_clear,
    "reentrant_clear": _check_reentrant_clear,
    "clear_reuses_queue": _check_clear_reuses_queue,
    "contiguous_buffer_reuse": _check_contiguous_buffer_reuse,
    "prototype_destructor": _check_prototype_destructor,
    "reentrant_setitem": _check_reentrant_setitem,
    "deeply_nested": _check_deeply_nested_queues,
    "chunk_indices_wrap": _check_chunk_indices_wrap,
    "cached_nodes_reused": _check_cached_nodes_reused,
    "cached_nodes_release_payloads": _check_cached_nodes_release_payloads,
    "cached_nodes_cycle": _check_cached_nodes_cycle,
    "cached_nodes_iterators": _check_cached_nodes_iterators,
    "cached_nodes_reentry": _check_cached_nodes_reentry,
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
    ["copy_ownership", "extend_iterators", "indexing_ownership", "reentrant_extend"],
)
def test_sequence_operations_release_payloads(queue_type, scenario):
    _run_in_subprocess(queue_type, scenario)


@pytest.mark.parametrize(
    "scenario", ["contiguous_extend_resize", "native_contiguous_clear"]
)
def test_contiguous_storage_reuse(scenario):
    _run_in_subprocess(QueueC, scenario)


@pytest.mark.parametrize(
    "initial, removed, added", [(0, 0, 2048), (0, 0, 4097), (1000, 800, 4097)]
)
def test_contiguous_extend_leaves_room_for_enqueue(initial, removed, added):
    queue = QueueC(range(initial))
    assert [queue.dequeue() for _ in range(removed)] == list(range(removed))
    queue.extend(range(initial, initial + added))
    storage = _queuec_storage(queue)
    assert storage[0] > len(queue)

    queue.enqueue(initial + added)
    assert _queuec_storage(queue) == storage
    assert [queue.dequeue() for _ in range(len(queue))] == list(
        range(removed, initial + added + 1)
    )
    assert not queue


def test_contiguous_capacity_does_not_round_to_power_of_two():
    queue = QueueC()
    capacity = _queuec_storage(queue)[0]
    assert capacity == 384
    queue.extend(range(1001))
    assert _queuec_storage(queue)[0] == capacity + 1001
    assert list(queue) == list(range(1001))


@pytest.mark.parametrize(
    "queue_type", PUBLIC_QUEUE_TYPES, ids=lambda cls: cls.__name__
)
def test_native_clear_allows_reentry(queue_type):
    _run_in_subprocess(queue_type, "native_clear_reentry")


@pytest.mark.parametrize("queue_type", [LLQueue, ContQueue], ids=lambda cls: cls.__name__)
@pytest.mark.parametrize(
    "scenario", ["prototype_clear", "reentrant_clear", "clear_reuses_queue"]
)
def test_clear_releases_payloads(queue_type, scenario):
    _run_in_subprocess(queue_type, scenario)


def test_contiguous_clear_reuses_buffer():
    _run_in_subprocess(ContQueue, "contiguous_buffer_reuse")


@pytest.mark.parametrize("queue_type", [LLQueue, ContQueue], ids=lambda cls: cls.__name__)
def test_prototype_destructor_is_safe(queue_type):
    _run_in_subprocess(queue_type, "prototype_destructor")


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
    "scenario",
    [
        "chunk_indices_wrap", "cached_nodes_reused", "cached_nodes_release_payloads", "cached_nodes_cycle",
        "cached_nodes_iterators", "cached_nodes_reentry",
    ],
)
def test_queue_cached_nodes(scenario):
    _run_in_subprocess(Queue, scenario)


def test_large_contiguous_storage():
    _run_in_subprocess(QueueC, "large_contiguous_storage")


if __name__ == "__main__":
    queue_type = next(cls for cls in QUEUE_TYPES if cls.__name__ == sys.argv[1])
    scenario = sys.argv[2]
    if scenario in WORKLOADS:
        _check_no_memory_growth(queue_type, WORKLOADS[scenario])
    else:
        CHECKS[scenario](queue_type)
