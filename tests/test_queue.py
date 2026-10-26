import pytest
import weakref

from fastqueue.prototypes import *
from fastqueue import *

queue_size = 350000


@pytest.mark.parametrize(
    "queue", [LockQueue(), Queue(), QueueC(), LLQueue(), ContQueue()]
)
def test_new(queue):
    assert queue.is_empty()
    assert len(queue) == 0
    assert queue.enqueue(1) is None
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
    "queue", [LockQueue(), Queue(), QueueC(), LLQueue(), ContQueue()]
)
def test_mutation(queue):
    queue.enqueue(1)
    item = queue.dequeue()
    assert item == 1
    item = 7
    queue.enqueue(item)
    assert item == 7
    queue.dequeue()
    assert item == 7

    queue.enqueue('👑')
    queue.enqueue('🎁')
    item = queue.dequeue()
    assert item == '👑'
    item = '🧶'
    queue.enqueue(item)
    assert item == '🧶'
    item = queue.dequeue()
    assert item == '🎁'


@pytest.mark.parametrize(
    "queue", [LockQueue(), Queue(), QueueC(), LLQueue(), ContQueue()]
)
def test_large(queue):
    for i in range(queue_size):
        queue.enqueue(i)
    assert not queue.is_empty()
    assert len(queue) == queue_size
    for i in range(queue_size):
        assert queue.dequeue() == i
    assert queue.is_empty()
    queue.enqueue(1)
    queue.enqueue(2)
    assert not queue.is_empty()
    assert queue.dequeue() == 1
    assert queue.dequeue() == 2
    assert queue.is_empty()


@pytest.mark.parametrize("queue", [LockQueue(), Queue(), QueueC()])
def test_extend(queue):
    queue.extend(range(queue_size))
    assert not queue.is_empty()
    assert len(queue) == queue_size
    queue.extend([1, 2, 3])
    assert not queue.is_empty()
    assert len(queue) == queue_size + 3
    assert [queue.dequeue() for _ in range(queue_size)] == list(
        range(queue_size))
    assert len(queue) == 3
    assert [queue.dequeue() for _ in range(len(queue))] == [1, 2, 3]
    assert queue.is_empty()
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


@pytest.mark.parametrize("queue", [LockQueue(), Queue(), QueueC()])
def test_mixed_extend(queue):
    size = 50
    queue.enqueue(1)
    queue.enqueue(2)
    queue.enqueue(3)
    queue.extend(range(size))
    queue.enqueue(4)
    queue.enqueue(5)
    queue.enqueue(6)

    assert not queue.is_empty()
    assert len(queue) == size + 6
    assert [queue.dequeue() for _ in range(size + 6)] == [1, 2, 3] + list(
        range(size)
    ) + [4, 5, 6]
    assert queue.is_empty()
    assert len(queue) == 0

    size = 50
    for i in range(10):
        queue.enqueue(i)
    for _ in range(10):
        queue.dequeue()
    queue.extend(range(size))

    assert not queue.is_empty()
    assert len(queue) == size
    assert [queue.dequeue() for _ in range(size)] == list(range(size))
    assert queue.is_empty()
    assert len(queue) == 0

    queue.extend(range(10))
    assert len(queue) == 10
    assert queue[0] == 0
    assert queue[-1] == 9


@pytest.mark.parametrize("queue", [LockQueue(), Queue(), QueueC()])
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


@pytest.mark.parametrize("queue", [LockQueue(), Queue(), QueueC()])
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


@pytest.mark.parametrize("queue", [LockQueue(), Queue(), QueueC()])
def test_containsQueue(queue):
    queue.extend(range(queue_size))
    assert not (queue_size in queue)
    for i in range(258):
        assert i in queue
    assert (queue_size - 1) in queue
    queue.dequeue()
    assert not (0 in queue)

    assert not ('🐲' in queue)
    queue.enqueue('🐲')
    assert '🐲' in queue


@pytest.mark.parametrize("queue", [LockQueue, Queue, QueueC])
def test_initialize(queue):
    q = queue()
    assert len(q) == 0
    assert q.is_empty()
    q = queue([i for i in range(10)])
    assert len(q) == 10
    assert not q.is_empty()
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


@pytest.mark.parametrize("queue", [LockQueue(), Queue(), QueueC()])
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


@pytest.mark.parametrize(
    'queue_type, size',
    [(QueueC, 256), (QueueC, 600)],
)
@pytest.mark.parametrize('consumed', [0, 255, 256, 513])
@pytest.mark.parametrize('refill', [False, True])
def test_contains_detects_drain_and_same_length_refill(queue_type, consumed, refill, size):
    queue = queue_type(MembershipPayload() for _ in range(consumed + size))
    for _ in range(consumed):
        queue.dequeue()
    references = tuple(weakref.ref(item) for item in queue)

    class Probe:
        def __eq__(self, other):
            while queue:
                queue.dequeue()
            if refill:
                queue.extend(MembershipPayload() for _ in range(size))
            return False

    with pytest.raises(RuntimeError, match='mutated'):
        Probe() in queue
    assert len(queue) == (size if refill else 0)
    assert all(reference() is None for reference in references)


@pytest.mark.parametrize('queue_type', [Queue, QueueC])
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
