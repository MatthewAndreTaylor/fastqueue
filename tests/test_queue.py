import pytest
from mqueue.prototype_mqueue import *
from mqueue.mqueue import *

queue_size = 1000000

@pytest.mark.parametrize("queue_type", [Queue(), QueueC(), LLQueue(), ContQueue()])
def test_newQueue(queue_type):
    queue = queue_type
    assert queue.is_empty() == True
    assert len(queue) == 0
    queue.enqueue(1)
    assert queue.is_empty() == False
    assert len(queue) == 1
    queue.enqueue('🙂')
    assert queue.is_empty() == False
    assert len(queue) == 2
    item = queue.dequeue()
    assert queue.is_empty() == False
    assert len(queue) == 1
    assert item == 1
    item = queue.dequeue()
    assert queue.is_empty() == True
    assert len(queue) == 0
    assert item == '🙂'
    with pytest.raises(IndexError):
        queue.dequeue()

@pytest.mark.parametrize("queue_type", [Queue(), QueueC(), LLQueue(), ContQueue()])
def test_largeQueue(queue_type):
    queue = queue_type
    for i in range(queue_size):
        queue.enqueue(i)
    assert queue.is_empty() == False
    assert len(queue) == queue_size
    for i in range(queue_size):
        assert queue.dequeue() == i

@pytest.mark.parametrize("queue_type", [Queue(), QueueC()])
def test_extendQueue(queue_type):
    queue = queue_type
    queue.extend(range(queue_size))
    assert queue.is_empty() == False
    assert len(queue) == queue_size
    assert ([queue.dequeue() for _ in range(queue_size)] == list(
        range(queue_size)))
    assert queue.is_empty() == True
    assert len(queue) == 0

@pytest.mark.parametrize("queue_type", [Queue(), QueueC()])
def test_getitemQueue(queue_type):
    queue = queue_type
    queue.extend(range(1000))
    item = queue[0]
    assert item == 0
    item = queue[1]
    assert item == 1
    item = queue[len(queue)-1]
    assert item == len(queue)-1


@pytest.mark.parametrize("queue_type", [Queue(), QueueC()])
def test_containsQueue(queue_type):
    queue = queue_type
    queue.extend(range(queue_size))
    assert (queue_size in queue) == False
    for i in range(258):
        assert (i in queue) == True

    assert (queue_size-1 in queue) == True
