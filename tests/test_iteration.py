import gc
from operator import length_hint
import weakref

import pytest

from fastqueue import Queue, QueueC


@pytest.fixture(params=[Queue, QueueC])
def queue_type(request):
    return request.param


@pytest.mark.parametrize("size", [0, 1, 253, 254, 255, 256, 257, 762, 763, 4097])
def test_iteration_preserves_fifo_items_and_length_hint(queue_type, size):
    values = [object() for _ in range(size)]
    queue = queue_type(values)
    iterator = iter(queue)
    assert iter(iterator) is iterator
    for index, value in enumerate(values):
        assert length_hint(iterator) == size - index
        assert next(iterator) is value
    assert length_hint(iterator) == 0
    with pytest.raises(StopIteration):
        next(iterator)
    assert len(queue) == size
    assert list(queue) == values


def test_iterators_are_independent_and_support_nested_loops(queue_type):
    queue = queue_type([1, 2, 3])
    first, second = iter(queue), iter(queue)
    assert next(first) == 1
    assert list(second) == [1, 2, 3]
    assert list(first) == [2, 3]
    assert [(left, right) for left in queue for right in queue] == [
        (left, right) for left in [1, 2, 3] for right in [1, 2, 3]
    ]


def test_iteration_after_partial_drain_and_storage_reuse(queue_type):
    queue = queue_type(range(4097))
    for value in range(3500):
        assert queue.dequeue() == value
    queue.extend(range(4097, 10000))
    assert list(queue) == list(range(3500, 10000))
    queue.clear()
    queue.extend(range(10000, 15000))
    for value in range(10000, 10123):
        assert queue.dequeue() == value
    assert list(queue) == list(range(10123, 15000))


@pytest.mark.parametrize(
    "mutation",
    [
        "enqueue",
        "dequeue",
        "clear",
        "extend",
        "extend_generator",
        "same_length",
    ],
)
@pytest.mark.parametrize("consumed", [0, 253])
def test_structural_mutation_invalidates_native_iterator(
    queue_type, mutation, consumed
):
    queue = queue_type(range(1024))
    iterator = iter(queue)
    for value in range(consumed):
        assert next(iterator) == value
    if mutation == "enqueue":
        queue.enqueue(1024)
    elif mutation == "dequeue":
        queue.dequeue()
    elif mutation == "clear":
        queue.clear()
    elif mutation == "extend":
        queue.extend([1024, 1025])
    elif mutation == "extend_generator":
        queue.extend(value for value in [1024, 1025])
    else:
        queue.dequeue()
        queue.enqueue(1024)
    with pytest.raises(RuntimeError, match="mutated during iteration"):
        next(iterator)
    assert length_hint(iterator) == 0
    with pytest.raises(StopIteration):
        next(iterator)


def test_large_extend_invalidates_native_iterator(queue_type):
    queue = queue_type(range(4097))
    iterator = iter(queue)
    assert next(iterator) == 0
    queue.extend(range(4097, 16385))
    with pytest.raises(RuntimeError, match="mutated during iteration"):
        next(iterator)
    assert list(queue) == list(range(16385))


def test_contiguous_hint_only_resize_preserves_iterator():
    class EmptyWithLengthHint:
        def __iter__(self):
            return iter(())

        def __length_hint__(self):
            return 16384

    queue = QueueC(range(4097))
    for value in range(3500):
        assert queue.dequeue() == value
    queue.extend(range(4097, 7597))
    iterator = iter(queue)
    for value in range(3500, 4003):
        assert next(iterator) == value
    queue.extend(EmptyWithLengthHint())
    assert length_hint(iterator) == 7597 - 4003
    assert list(iterator) == list(range(4003, 7597))


def test_item_replacement_and_empty_extend_preserve_iterator(queue_type):
    queue = queue_type([1, 2, 3])
    iterator = iter(queue)
    assert next(iterator) == 1
    queue[1] = 20
    queue.extend([])
    with pytest.raises(IndexError):
        queue[10] = 30
    with pytest.raises(TypeError):
        del queue[1]
    assert list(iterator) == [20, 3]


@pytest.mark.parametrize("size", [0, 1])
@pytest.mark.parametrize("observe_stop", [False, True])
def test_iterator_exhaustion_after_mutation(queue_type, size, observe_stop):
    queue = queue_type(range(size))
    iterator = iter(queue)
    for value in range(size):
        assert next(iterator) == value
    if observe_stop:
        with pytest.raises(StopIteration):
            next(iterator)
    queue.enqueue("new")
    assert length_hint(iterator) == 0
    with pytest.raises(StopIteration):
        next(iterator)


@pytest.mark.parametrize("size", [3, 256])
def test_extend_from_own_native_iterator_is_invalidated(queue_type, size):
    values = list(range(size))
    queue = queue_type()
    for value in values:
        queue.enqueue(value)
    iterator = iter(queue)
    with pytest.raises(RuntimeError, match="mutated during iteration"):
        queue.extend(iterator)
    assert list(queue) == values + values[:1]
    assert list(iterator) == []


@pytest.mark.parametrize("size", [3, 256])
def test_self_extend(queue_type, size):
    values = list(range(size))
    queue = queue_type(values)
    queue.extend(queue)
    assert list(queue) == values * 2


class Payload:
    pass


def test_iterator_keeps_owner_alive_and_returns_owned_items(queue_type):
    value = Payload()
    reference = weakref.ref(value)
    queue = queue_type([value])
    iterator = iter(queue)
    del value, queue
    gc.collect()
    assert reference() is not None
    yielded = next(iterator)
    assert yielded is reference()
    del iterator
    gc.collect()
    assert reference() is yielded
    del yielded
    gc.collect()
    assert reference() is None


def test_iterator_owner_cycle_is_collectible(queue_type):
    value = Payload()
    reference = weakref.ref(value)
    queue = queue_type([value])
    value.iterator = iter(queue)
    assert gc.is_tracked(value.iterator)
    del value, queue
    gc.collect()
    assert reference() is None


def test_exhausted_iterator_releases_owner(queue_type):
    value = Payload()
    reference = weakref.ref(value)
    iterator = iter(queue_type([value]))
    assert next(iterator) is value
    del value
    with pytest.raises(StopIteration):
        next(iterator)
    assert reference() is None
    assert length_hint(iterator) == 0


def test_invalidated_iterator_releases_owner(queue_type):
    value = Payload()
    reference = weakref.ref(value)
    queue = queue_type([value])
    iterator = iter(queue)
    queue.enqueue(None)
    del value, queue
    assert reference() is not None
    with pytest.raises(RuntimeError, match="mutated during iteration"):
        next(iterator)
    gc.collect()
    assert reference() is None
    assert length_hint(iterator) == 0
    with pytest.raises(StopIteration):
        next(iterator)


def test_native_clear_invalidates_before_running_item_finalizers(queue_type):
    errors = []

    class InspectIteratorOnDelete:
        def __del__(self):
            try:
                next(iterator)
            except RuntimeError as error:
                errors.append(str(error))

    queue = queue_type([InspectIteratorOnDelete(), 2])
    iterator = iter(queue)
    queue.clear()
    assert len(errors) == 1
    assert "mutated during iteration" in errors[0]
