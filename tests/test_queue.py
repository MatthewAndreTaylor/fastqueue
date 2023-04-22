import pytest

from fastqueue.prototypes import *
from fastqueue import *

queue_size = 500000


@pytest.mark.parametrize(
    "queue_type", [LockQueue(), Queue(), QueueC(), LLQueue(), ContQueue()]
)
def test_newQueue(queue_type):
    queue = queue_type
    assert queue.is_empty()
    assert len(queue) == 0
    queue.enqueue(1)
    assert not queue.is_empty()
    assert len(queue) == 1
    queue.enqueue("🙂")
    assert not queue.is_empty()
    assert len(queue) == 2
    item = queue.dequeue()
    assert not queue.is_empty()
    assert len(queue) == 1
    assert item == 1
    item = queue.dequeue()
    assert queue.is_empty()
    assert len(queue) == 0
    assert item == "🙂"

    with pytest.raises(IndexError):
        queue.dequeue()


@pytest.mark.parametrize(
    "queue_type", [LockQueue(), Queue(), QueueC(), LLQueue(), ContQueue()]
)
def test_mutationQueue(queue_type):
    queue = queue_type
    queue.enqueue(1)
    item = queue.dequeue()
    assert item == 1
    item = 7
    queue.enqueue(item)
    assert item == 7
    queue.dequeue()
    assert item == 7


@pytest.mark.parametrize(
    "queue_type", [LockQueue(), Queue(), QueueC(), LLQueue(), ContQueue()]
)
def test_largeQueue(queue_type):
    queue = queue_type
    for i in range(queue_size):
        queue.enqueue(i)
    assert not queue.is_empty()
    assert len(queue) == queue_size
    for i in range(queue_size):
        assert queue.dequeue() == i


@pytest.mark.parametrize("queue_type", [LockQueue(), Queue(), QueueC()])
def test_extendQueue(queue_type):
    queue = queue_type
    queue.extend(range(queue_size))
    assert not queue.is_empty()
    assert len(queue) == queue_size
    assert [queue.dequeue() for _ in range(queue_size)] == list(range(queue_size))
    assert queue.is_empty()
    assert len(queue) == 0

    # Tests for mutation
    lst = [1, 2, 3]
    queue.extend(lst)
    assert len(queue) == 3
    assert lst == [1, 2, 3]
    assert lst[2] == 3


@pytest.mark.parametrize("queue_type", [LockQueue(), Queue(), QueueC()])
def test_getitemQueue(queue_type):
    queue = queue_type
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


@pytest.mark.parametrize("queue_type", [LockQueue(), Queue(), QueueC()])
def test_setitemQueue(queue_type):
    queue = queue_type
    queue.extend(range(1000))
    queue[0] = "🙂"
    assert queue[0] == "🙂"
    queue[0] = 0
    assert queue[0] == 0

    queue[0] = None
    assert queue[0] is None

    queue[-1] = 10
    assert queue[len(queue) - 1] == 10

    with pytest.raises(IndexError):
        queue[1000] = 90


@pytest.mark.parametrize("queue_type", [LockQueue(), Queue(), QueueC()])
def test_containsQueue(queue_type):
    queue = queue_type
    queue.extend(range(queue_size))
    assert not (queue_size in queue)
    for i in range(258):
        assert i in queue
    assert (queue_size - 1) in queue
    queue.dequeue()
    assert not (0 in queue)
