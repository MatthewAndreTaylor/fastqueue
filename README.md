# fastqueue

[![Tests](https://github.com/MatthewAndreTaylor/fastqueue/actions/workflows/tests.yml/badge.svg)](https://github.com/MatthewAndreTaylor/fastqueue/actions)
[![PyPI versions](https://img.shields.io/badge/python-3.7%2B-blue)](https://github.com/MatthewAndreTaylor/fastqueue/)
[![PyPI license](https://img.shields.io/badge/license-MIT-%23373737)](https://github.com/MatthewAndreTaylor/fastqueue/blob/master/LICENSE)\
[![PyPI](https://img.shields.io/pypi/v/fastqueue-lib.svg)](https://pypi.org/project/fastqueue-lib/)


Single-ended fast queues built in C tuned for Python.

## Requirements

- `python 3.7+`

## Installation

To install fastqueue, using pip:

```bash
pip install fastqueue-lib
```

## Quickstart

For general use cases `fastqueue.Queue()` objects are tuned to perform well.
The enqueue and dequeue methods perform well over a large sequence of arbitrary operations.
`fastqueue.Queue()` supports many standard sequence methods similar to lists.
`fastqueue.Queue()` minimizes memory usage but maintains the fast queue speeds.

```py
>>> from fastqueue import Queue
>>> queue = Queue()
>>> queue.extend(['🚒', '🛴'])
>>> queue[0]
'🚒'
>>> '🛴' in queue
True
>>> queue.enqueue('🚅')
>>> queue.enqueue('🚗')
>>> queue[-1]
'🚗'
>>> [queue.dequeue() for _ in range(len(queue)) ]
['🚒', '🛴', '🚅', '🚗']
```


For more specialized cases `fastqueue.QueueC()` objects are tuned to perform well.
The interface for `fastqueue.QueueC()` is identical to `fastqueue.Queue()`.
The enqueue and dequeue methods perform similarly well over a large sequence of arbitrary operations.
`fastqueue.QueueC()` handles memory differently by doubling the capacity when full.
This increases the complexity but maintains fast amortized cost.
The benefit of this approach is even faster `__getitem__` and `__setitem__` speeds

```py
>>> from fastqueue import QueueC

>>> queue_c = QueueC()
>>> queue_c.extend(['🚒', '🛴'])
>>> queue_c[0]
'🚒'
>>> '🛴' in queue_c
True
>>> queue_c.enqueue('🚅')
>>> queue_c.enqueue('🚗')
>>> queue_c[-1]
'🚗'
>>> [queue_c.dequeue() for _ in range(len(queue_c)) ]
['🚒', '🛴', '🚅', '🚗']
```

Another alternative is `fastqueue.LockQueue()` which supports all queue operations.
`fastqueue.LockQueue()` is built as a thread-safe alternative to the other queue types.

## Example Benchmarks

### Queue operations

Ubuntu

![Queue_times](https://github.com/MatthewAndreTaylor/fastqueue/assets/100451342/1c47cdc5-e7cc-4c89-8902-91359f660002)
![Queue_types_linux](https://github.com/MatthewAndreTaylor/fastqueue/assets/100451342/59a6d2c6-51c6-45e1-aa4e-eb6679616a75)

Windows

![Queue_times](https://user-images.githubusercontent.com/100451342/232172485-c17b6b33-986f-461b-b0bf-b26b3f6e8304.png)
![Queue_types](https://user-images.githubusercontent.com/100451342/232172490-bd90b021-7aeb-47b8-99e0-2481ccbc1f8f.png)

### Iteration


Ubuntu

![Iterable_Instantiation](https://github.com/MatthewAndreTaylor/fastqueue/assets/100451342/85939d12-73ed-42a5-a8bd-b2bea4ee599c)
![Iterable_Iteration](https://github.com/MatthewAndreTaylor/fastqueue/assets/100451342/b17f5f66-26b5-4e21-b5e5-c8fcbe5433a9)

Windows

![Iterable_Instantiation](https://github.com/MatthewAndreTaylor/fastqueue/assets/100451342/a7f89750-3b3b-475a-ac93-849c62d0c4a6)
![Iterable_Iteration](https://github.com/MatthewAndreTaylor/fastqueue/assets/100451342/9ee2feed-28a5-44a1-b72d-eff17804ebdd)

