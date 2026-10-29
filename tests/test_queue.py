import gc
import struct
import sys
import weakref
from collections import deque

import pytest

from fastqueue.prototypes import *
from fastqueue import *

queue_size = 350000


@pytest.mark.parametrize("queue", [Queue(), QueueC(), LLQueue(), ContQueue()])
def test_new(queue):
    assert not queue
    assert len(queue) == 0
    assert queue.enqueue(0) is None
    assert queue
    assert len(queue) == 1
    queue.enqueue("🙂")
    assert queue
    assert len(queue) == 2
    item = queue.dequeue()
    assert queue
    assert len(queue) == 1
    assert item == 0
    item = queue.dequeue()
    assert not queue
    assert len(queue) == 0
    assert item == "🙂"

    with pytest.raises(IndexError):
        queue.dequeue()


@pytest.mark.parametrize("queue", [Queue(), QueueC(), LLQueue(), ContQueue()])
def test_mutation(queue):
    queue.enqueue(1)
    item = queue.dequeue()
    assert item == 1
    item = 7
    queue.enqueue(item)
    assert item == 7
    queue.dequeue()
    assert item == 7

    queue.enqueue("👑")
    queue.enqueue("🎁")
    item = queue.dequeue()
    assert item == "👑"
    item = "🧶"
    queue.enqueue(item)
    assert item == "🧶"
    item = queue.dequeue()
    assert item == "🎁"


@pytest.mark.parametrize("queue", [Queue(), QueueC(), LLQueue(), ContQueue()])
def test_large(queue):
    for i in range(queue_size):
        queue.enqueue(i)
    assert queue
    assert len(queue) == queue_size
    for i in range(queue_size):
        assert queue.dequeue() == i
    assert not queue
    queue.enqueue(1)
    queue.enqueue(2)
    assert queue
    assert queue.dequeue() == 1
    assert queue.dequeue() == 2
    assert not queue


@pytest.mark.parametrize("queue_type", [Queue, QueueC])
@pytest.mark.parametrize("size", [0, 1, 255, 256, 257, 383, 384, 385, 1024, 3075])
def test_single_item_wraparound_matches_deque(queue_type, size):
    expected = deque(object() for _ in range(size))
    queue = queue_type()
    for value in expected:
        queue.enqueue(value)

    steps = 2 * (size + 1024)
    checkpoints = {0, 255, 256, 1023, 1024, 3074, 3075, steps - 1}
    for step in range(steps):
        value = object()
        queue.enqueue(value)
        expected.append(value)
        assert queue.dequeue() is expected.popleft()
        assert len(queue) == size

        if step in checkpoints:
            assert list(queue) == list(expected)
            copied = queue.copy()
            assert len(copied) == size
            assert list(copied) == list(expected)
            for index in (0, 255, 256, 1023, size - 1):
                if 0 <= index < size:
                    assert queue[index] is expected[index]
                    assert queue[index - size] is expected[index]
            if expected:
                assert copied.dequeue() is expected[0]
                assert len(queue) == size
                assert queue[0] is expected[0]

    while expected:
        assert queue.dequeue() is expected.popleft()
    assert len(queue) == 0
    with pytest.raises(IndexError):
        queue.dequeue()


@pytest.mark.parametrize("queue_type", [Queue, QueueC])
def test_extend_drain_and_reuse_matches_deque(queue_type):
    queue = queue_type()
    expected = deque()
    # Exercise reservations from non-power-of-two input lengths.
    phases = [(2051, 2000), (949, 900), (200, 300), (257, 256), (1024, 1025)]
    for cycle in range(3):
        for added, removed in phases:
            values = [object() for _ in range(added)]
            items = values if cycle == 0 else tuple(values)
            if cycle == 2:
                items = (value for value in values)
            queue.extend(items)
            expected.extend(values)
            assert len(queue) == len(expected)
            assert list(queue.copy()) == list(expected)

            for _ in range(removed):
                assert queue.dequeue() is expected.popleft()
            assert len(queue) == len(expected)
            assert list(queue) == list(expected)
            if expected:
                assert queue[0] is expected[0]
                assert queue[-1] is expected[-1]
        assert not queue
        queue.extend([])
        marker = object()
        queue.enqueue(marker)
        assert queue.dequeue() is marker
        assert not queue


@pytest.mark.parametrize("queue", [Queue(), QueueC()])
def test_extend(queue):
    queue.extend(range(queue_size))
    assert queue
    assert len(queue) == queue_size
    queue.extend([1, 2, 3])
    assert queue
    assert len(queue) == queue_size + 3
    assert [queue.dequeue() for _ in range(queue_size)] == list(range(queue_size))
    assert len(queue) == 3
    assert [queue.dequeue() for _ in range(len(queue))] == [1, 2, 3]
    assert not queue
    assert len(queue) == 0

    # Tests for mutation
    lst = [1, 2, 3]
    queue.extend(lst)
    assert len(queue) == 3
    assert lst == [1, 2, 3]
    assert lst[2] == 3
    assert queue[2] == 3
    queue.extend([])
    assert len(queue) == 3
    assert lst == [1, 2, 3]
    assert lst[2] == 3
    assert queue[2] == 3

    with pytest.raises(TypeError):
        queue.extend(0)

    with pytest.raises(TypeError):
        queue.extend([1, 2], [])


@pytest.mark.parametrize("queue", [Queue(), QueueC()])
def test_mixed_extend(queue):
    size = 50
    queue.enqueue(1)
    queue.enqueue(2)
    queue.enqueue(3)
    queue.extend(range(size))
    queue.enqueue(4)
    queue.enqueue(5)
    queue.enqueue(6)

    assert queue
    assert len(queue) == size + 6
    assert [queue.dequeue() for _ in range(size + 6)] == [1, 2, 3] + list(
        range(size)
    ) + [4, 5, 6]
    assert not queue
    assert len(queue) == 0

    size = 50
    for i in range(10):
        queue.enqueue(i)
    for _ in range(10):
        queue.dequeue()
    queue.extend(range(size))

    assert queue
    assert len(queue) == size
    assert [queue.dequeue() for _ in range(size)] == list(range(size))
    assert not queue
    assert len(queue) == 0

    queue.extend(range(10))
    assert len(queue) == 10
    assert queue[0] == 0
    assert queue[-1] == 9


@pytest.mark.parametrize("queue_type", [Queue, QueueC])
def test_extend_after_wraparound(queue_type):
    queue = queue_type(range(513))
    for value in range(400):
        assert queue.dequeue() == value
    queue.extend(list(range(513, 913)))
    assert list(queue) == list(range(400, 913))
    queue.extend(value for value in range(913, 1513))
    assert list(queue) == list(range(400, 1513))


@pytest.mark.parametrize(
    "initial, removed, added, input_type",
    [
        pytest.param(1024, 1024, 0, "tuple", id="empty-at-wrap-boundary"),
        pytest.param(1024, 800, 0, "generator", id="empty-with-retained-items"),
        pytest.param(1000, 800, 24, "list", id="ends-at-buffer-boundary"),
        pytest.param(1000, 800, 25, "tuple", id="wraps-one-item"),
        pytest.param(1000, 800, 824, "generator", id="fills-remaining-capacity"),
        pytest.param(1000, 800, 825, "list", id="grows-by-one-item"),
        pytest.param(1024, 800, 800, "tuple", id="starts-at-zero"),
        pytest.param(0, 0, 1024, "generator", id="fills-empty-buffer"),
    ],
)
def test_contiguous_extend_boundaries(initial, removed, added, input_type):
    queue = QueueC(range(initial))
    for value in range(removed):
        assert queue.dequeue() == value
    values = range(initial, initial + added)
    if input_type == "list":
        items = list(values)
    elif input_type == "tuple":
        items = tuple(values)
    else:
        items = (value for value in values)
    assert queue.extend(items) is None
    expected = list(range(removed, initial + added))
    assert len(queue) == len(expected)
    assert list(queue) == expected

    queue.enqueue("tail")
    assert [queue.dequeue() for _ in range(len(queue))] == expected + ["tail"]
    assert not queue


def test_contiguous_extend_grows_wrapped_buffer():
    # A 2051-item extension rounds its reservation up to 4096 slots.
    queue = QueueC(range(2051))
    for value in range(2000):
        assert queue.dequeue() == value
    queue.extend(tuple(range(2051, 3000)))
    for value in range(2000, 2900):
        assert queue.dequeue() == value

    # Wrap inside that buffer, then request more than its 4096-slot capacity.
    queue.extend(value for value in range(3000, 4200))
    assert list(queue) == list(range(2900, 4200))
    queue.extend(list(range(4200, 7000)))
    assert list(queue) == list(range(2900, 7000))
    queue.enqueue("tail")
    assert [queue.dequeue() for _ in range(len(queue))] == (
        list(range(2900, 7000)) + ["tail"]
    )
    assert not queue


def test_contiguous_extend_iterator_can_mutate_and_resize_queue():
    queue = QueueC(range(1024))
    for value in range(800):
        assert queue.dequeue() == value
    queue.extend(range(1024, 1824))

    def values():
        assert queue.dequeue() == 800
        queue.enqueue(1824)
        queue.enqueue(1825)
        yield 1826
        assert queue.dequeue() == 801
        queue.enqueue(1827)
        yield 1828

    queue.extend(values())
    assert list(queue) == list(range(802, 1829))
    queue.enqueue(1829)
    assert [queue.dequeue() for _ in range(len(queue))] == list(range(802, 1830))


@pytest.mark.parametrize("removed", [0, 1000], ids=["growth", "wraparound"])
def test_contiguous_extend_keeps_progress_after_iterator_error(removed):
    queue = QueueC(range(1024))
    for value in range(removed):
        assert queue.dequeue() == value

    def values():
        yield 1024
        yield 1025
        raise RuntimeError("iterator failed")

    with pytest.raises(RuntimeError, match="iterator failed"):
        queue.extend(values())
    assert list(queue) == list(range(removed, 1026))
    queue.enqueue(1026)
    assert [queue.dequeue() for _ in range(len(queue))] == list(range(removed, 1027))


@pytest.mark.parametrize(
    "hint, error",
    [
        (sys.maxsize, MemoryError),
        (sys.maxsize // struct.calcsize("P") - 514, MemoryError),
        (-1, ValueError),
        (sys.maxsize + 1, OverflowError),
    ],
)
def test_contiguous_extend_invalid_length_hint_preserves_queue(hint, error):
    class InvalidLengthHint:
        def __length_hint__(self):
            return hint

        def __iter__(self):
            return iter([99])

    queue = QueueC([1, 2])
    with pytest.raises(error):
        queue.extend(InvalidLengthHint())
    assert list(queue) == [1, 2]
    queue.enqueue(3)
    assert [queue.dequeue() for _ in range(len(queue))] == [1, 2, 3]


@pytest.mark.parametrize("sequence_type", [list, tuple])
def test_contiguous_extend_honors_sequence_subclass_iterator(sequence_type):
    class ReversedSequence(sequence_type):
        def __iter__(self):
            return reversed(self)

    queue = QueueC([0])
    queue.extend(ReversedSequence([1, 2, 3]))
    queue.enqueue(4)
    assert [queue.dequeue() for _ in range(len(queue))] == [0, 3, 2, 1, 4]


@pytest.mark.parametrize("sequence_type", [list, tuple])
def test_contiguous_extend_owns_wrapped_sequence_items(sequence_type):
    class Payload:
        pass

    queue = QueueC(range(1000))
    for value in range(800):
        assert queue.dequeue() == value
    items = sequence_type(Payload() for _ in range(32))
    references = [weakref.ref(item) for item in items]
    queue.extend(items)
    del items
    gc.collect()
    assert all(reference() is not None for reference in references)

    for value in range(800, 1000):
        assert queue.dequeue() == value
    for reference in references:
        value = queue.dequeue()
        assert value is reference()
        del value
    assert not queue
    gc.collect()
    assert all(reference() is None for reference in references)


@pytest.mark.parametrize("offset", [0, 1, 512, 1023])
@pytest.mark.parametrize("method", ["enqueue", "sized", "unsized"])
def test_contiguous_resize_preserves_wrapped_items(offset, method):
    values = [object() for _ in range(1025 + offset)]
    queue = QueueC(values[:1024])
    for value in values[:offset]:
        assert queue.dequeue() is value
    queue.extend(values[1024:-1])

    if method == "enqueue":
        queue.enqueue(values[-1])
    elif method == "sized":
        queue.extend(values[-1:])
    else:
        queue.extend(value for value in values[-1:])

    expected = values[offset:]
    assert len(queue) == len(expected)
    assert list(queue) == expected
    assert queue[0] is expected[0]
    assert queue[-1] is expected[-1]
    for value in expected:
        assert queue.dequeue() is value
    assert not queue

    queue.extend(values)
    queue.enqueue(values[0])
    for value in values + values[:1]:
        assert queue.dequeue() is value
    assert not queue


@pytest.mark.parametrize("initial, removed", [(512, 123), (1024, 123), (512, 512)])
def test_contiguous_resize_from_length_hint(initial, removed):
    class EmptyWithLengthHint:
        def __iter__(self):
            return iter(())

        def __length_hint__(self):
            return 2051

    values = [object() for _ in range(initial)]
    queue = QueueC(values)
    for value in values[:removed]:
        assert queue.dequeue() is value

    queue.extend(EmptyWithLengthHint())
    assert len(queue) == initial - removed
    assert list(queue) == values[removed:]
    queue.enqueue(values[0])
    for value in values[removed:] + values[:1]:
        assert queue.dequeue() is value
    assert not queue
    queue.enqueue(values[-1])
    assert queue.dequeue() is values[-1]


@pytest.mark.parametrize("queue", [Queue(), QueueC()])
def test_getitemQueue(queue):
    queue.extend(range(1000))
    assert queue[0] == queue[0]
    item = queue[0]
    assert item == 0
    item = queue[1]
    assert item == 1
    assert queue[256] == 256
    item = queue[len(queue) - 1]
    assert item == len(queue) - 1

    with pytest.raises(IndexError):
        queue[1000]
    assert queue[len(queue) - 1] == queue[-1]
    assert queue[len(queue) - 3] == queue[-3]

    queue.enqueue(1)
    assert queue[-1] == 1


@pytest.mark.parametrize("queue_type", [Queue, QueueC])
@pytest.mark.parametrize(
    "initial, removed, added",
    [(600, 100, 0), (256, 100, 100), (256, 100, 700)],
)
def test_indexing_after_dequeue(queue_type, initial, removed, added):
    queue = queue_type(range(initial))
    for _ in range(removed):
        queue.dequeue()
    queue.extend(range(initial, initial + added))
    expected = list(range(removed, initial + added))

    for index, value in enumerate(expected):
        assert queue[index] == value
        assert queue[index - len(expected)] == value
        queue[index] = -value - 1

    assert [queue.dequeue() for _ in expected] == [-value - 1 for value in expected]


@pytest.mark.parametrize(
    "initial, removed, added",
    [(1537, 1025, 768), (256, 100, 700), (257, 255, 0)],
)
def test_copy_after_node_reuse(initial, removed, added):
    queue = Queue(range(initial))
    for _ in range(removed):
        queue.dequeue()
    queue.extend(range(initial, initial + added))
    expected = list(range(removed, initial + added))
    copied = queue.copy()
    assert list(copied) == expected
    assert [queue.dequeue() for _ in expected] == expected

    queue.extend(value for value in range(1025))
    copied[-1] = "copied tail"
    expected[-1] = "copied tail"
    assert [copied.dequeue() for _ in expected] == expected
    assert [queue.dequeue() for _ in range(1025)] == list(range(1025))


def test_dynamic_nodes_copy_and_index_with_partial_head():
    items = [MembershipPayload() for _ in range(384 + 768 + 1536 + 17)]
    references = [weakref.ref(item) for item in items]
    queue = Queue(items)
    removed = 384 + 117
    for _ in range(removed):
        queue.dequeue()
    expected = items[removed:]
    tracked = expected[1]
    before_copy = sys.getrefcount(tracked)
    copied = queue.copy()
    assert sys.getrefcount(tracked) == before_copy + 1
    del tracked

    replacements = []
    # Both sides of the remaining 768- and 1536-slot node boundaries.
    for index in (0, 650, 651, 2186, 2187, len(expected) - 1):
        assert queue[index] is expected[index]
        assert queue[index - len(expected)] is expected[index]
        replacement = MembershipPayload()
        replacements.append(weakref.ref(replacement))
        queue[index - len(expected)] = replacement
        expected[index] = replacement
    assert list(queue) == expected
    assert list(copied) == items[removed:]
    del items, expected, replacement
    queue.clear()
    gc.collect()
    assert all(reference() is None for reference in references[:removed])
    assert all(reference() is not None for reference in references[removed:])
    assert all(reference() is None for reference in replacements)
    copied.clear()
    gc.collect()
    assert all(reference() is None for reference in references)

    queue.extend(None for _ in range(6000))
    payload = MembershipPayload()
    payload.queue = queue
    reference = weakref.ref(payload)
    queue.enqueue(payload)
    del payload, queue, copied
    gc.collect()
    assert reference() is None


@pytest.mark.parametrize("removed", [1, 191, 383])
@pytest.mark.parametrize("bulk", [False, True])
def test_wrapped_single_node_grows_into_multiple_nodes(removed, bulk):
    chunklen = 384
    queue = Queue(range(chunklen))
    for value in range(removed):
        assert queue.dequeue() == value
    queue.extend(range(chunklen, chunklen + removed))
    expected = list(range(removed, chunklen + removed))
    assert list(queue.copy()) == expected

    values = range(chunklen + removed, 2 * chunklen + removed + 1)
    if bulk:
        queue.extend(iter(values))
    else:
        for value in values:
            queue.enqueue(value)
    expected.extend(values)
    assert list(queue) == expected
    assert list(queue.copy()) == expected
    for index in (0, chunklen - removed, chunklen, len(expected) - 1):
        assert queue[index] == expected[index]
        assert queue[index - len(expected)] == expected[index]
        assert expected[index] in queue
        queue[index] = -expected[index] - 1
        expected[index] = -expected[index] - 1
    assert list(queue) == expected
    assert None not in queue

    payload = MembershipPayload()
    payload.queue = queue
    queue[0] = payload
    queue[-1] = payload
    reference = weakref.ref(payload)
    del payload, queue
    gc.collect()
    assert reference() is None


@pytest.mark.parametrize("queue_type", [Queue, QueueC])
@pytest.mark.parametrize(
    "initial, removed, added",
    [(0, 0, 0), (1, 0, 0), (600, 0, 0), (600, 100, 100), (600, 600, 1)],
)
def test_negative_indices(queue_type, initial, removed, added):
    queue = queue_type(range(initial))
    for _ in range(removed):
        queue.dequeue()
    for value in range(initial, initial + added):
        queue.enqueue(value)
    expected = list(range(removed, initial + added))

    for index in range(-len(expected), 0):
        assert queue[index] == expected[index]
        assert queue.__getitem__(index) == expected[index]
        queue[index] = -expected[index] - 1
        expected[index] = -expected[index] - 1
        assert queue[index] == expected[index]

    for index in (-len(queue) - 1, -2 * len(queue) - 1, len(queue)):
        with pytest.raises(IndexError):
            queue[index]
        with pytest.raises(IndexError):
            queue.__getitem__(index)
        with pytest.raises(IndexError):
            queue[index] = None
    assert list(queue) == expected


@pytest.mark.parametrize("queue", [Queue(), QueueC()])
def test_setitemQueue(queue):
    queue.extend(range(1000))
    queue[0] = "🙂"
    assert queue[0] == "🙂"
    queue[0] = 0
    assert queue[0] == 0

    queue[0] = None
    assert queue[0] is None
    queue[256] += 1
    assert queue[256] == 257

    queue[-1] = 10
    assert queue[len(queue) - 1] == 10

    with pytest.raises(IndexError):
        queue[1000] = 90


@pytest.mark.parametrize("queue", [Queue(), QueueC()])
def test_containsQueue(queue):
    queue.extend(range(queue_size))
    assert not (queue_size in queue)
    for i in range(258):
        assert i in queue
    assert (queue_size - 1) in queue
    queue.dequeue()
    assert not (0 in queue)

    assert not ("🐲" in queue)
    queue.enqueue("🐲")
    assert "🐲" in queue


@pytest.mark.parametrize("queue", [Queue, QueueC])
def test_initialize(queue):
    q = queue()
    assert len(q) == 0
    assert not q
    q = queue([i for i in range(10)])
    assert len(q) == 10
    assert q
    assert [q.dequeue() for _ in range(len(q))] == list(range(10))
    q = queue(range(10))
    assert len(q) == 10
    q.enqueue(10)
    assert list(q) == [i for i in range(11)]
    assert [q.dequeue() for _ in range(len(q))] == list(range(11))

    with pytest.raises(TypeError):
        q = queue(0)

    with pytest.raises(TypeError):
        q = queue([1, 2], [])


@pytest.mark.parametrize("queue", [Queue(), QueueC()])
def test_copy(queue):
    queue.extend(range(1, 5))
    copy = queue.copy()
    assert copy != queue
    queue[0] = 0
    assert copy[0] == 1
    assert [copy.dequeue() for _ in range(len(copy))] == [1, 2, 3, 4]
    assert len(copy) == 0
    assert len(queue) == 4
    assert [queue.dequeue() for _ in range(len(queue))] == [0, 2, 3, 4]
    queue.enqueue("🎈")
    copy = queue.copy()
    assert len(queue) == 1
    assert len(copy) == 1
    assert copy[0] == "🎈"
    assert queue[0] == "🎈"
    queue.extend(range(1000))
    copy = queue.copy()
    assert len(copy) == len(queue)
    assert copy.dequeue() == queue.dequeue()


class MembershipPayload:
    pass


@pytest.mark.parametrize("queue_type", [Queue, QueueC])
def test_contains_allows_item_replacement_without_cursor_mutation(queue_type):
    queue = queue_type([MembershipPayload(), MembershipPayload()])
    seen = []

    class Probe:
        def __eq__(self, other):
            seen.append(other)
            queue[0] = None
            return False

    assert Probe() not in queue
    assert len(seen) == 2
    assert queue[0] is None


@pytest.mark.parametrize("size", [2, 384 + 768 + 17])
@pytest.mark.parametrize("outcome", [False, True, "raise"])
@pytest.mark.parametrize("queue_type", [Queue, QueueC])
def test_contains_allows_same_length_clear_and_refill(size, outcome, queue_type):
    queue = queue_type()
    needle = object()
    replacement = [None] * (size - 1) + [needle]
    events = []

    class Compare:
        def __eq__(self, other):
            queue.clear()
            queue.extend(replacement)
            assert reference() is self
            # Nested membership has its own cursor and must not disturb the
            # outer scan, which resumes at logical index one after mutation.
            assert needle in queue
            events.append("compared")
            if outcome == "raise":
                raise RuntimeError("comparison failed after refilling")
            return outcome

        def __del__(self):
            events.append("released")

    item = Compare()
    reference = weakref.ref(item)
    queue.enqueue(item)
    queue.extend(None for _ in range(size - 1))
    del item
    if outcome == "raise":
        with pytest.raises(RuntimeError, match="comparison failed after refilling"):
            needle in queue
    else:
        assert needle in queue
    gc.collect()
    assert list(queue) == replacement
    assert events == ["compared", "released"]
    assert reference() is None


@pytest.mark.parametrize("queue_type", [Queue, QueueC])
def test_contains_rechecks_cursor_after_comparison_item_destructor(queue_type):
    queue = queue_type()
    needle = object()
    replacement = [None] * (384 + 768 + 17) + [needle]
    events = []

    class Compare:
        def __eq__(self, other):
            queue[0] = None
            return False

        def __del__(self):
            # The comparison's temporary owned reference delays this mutation
            # until after __eq__, when its saved node cursor may become stale.
            queue.clear()
            queue.extend(replacement)
            events.append("refilled")

    queue.enqueue(Compare())
    queue.enqueue(None)
    assert needle in queue
    assert events == ["refilled"]
    assert list(queue) == replacement


@pytest.mark.parametrize("queue_type", [Queue, QueueC])
def test_contains_stops_when_comparison_clears_queue(queue_type):
    class Compare:
        def __eq__(self, other):
            queue.clear()
            return False

    queue = queue_type([Compare(), None])
    assert object() not in queue
    assert not queue
