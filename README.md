# fastqueue

[![Tests](https://github.com/MatthewAndreTaylor/fastqueue/actions/workflows/tests.yml/badge.svg)](https://github.com/MatthewAndreTaylor/fastqueue/actions)
[![PyPI versions](https://img.shields.io/badge/python-3.9%2B-blue)](https://github.com/MatthewAndreTaylor/fastqueue/)
[![PyPI license](https://img.shields.io/badge/license-MIT-%23373737)](https://github.com/MatthewAndreTaylor/fastqueue/blob/master/LICENSE)\
[![PyPI](https://img.shields.io/pypi/v/fastqueue-lib.svg)](https://pypi.org/project/fastqueue-lib/)


Single ended fast queue's built in C tuned for python.

## Requirements

- `python 3.9+`

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

![Iterable_Instantiation](https://github.com/MatthewAndreTaylor/fastqueue/assets/100451342/c1028e20-d47c-4ec1-a602-263deefb4e05)
![Iterable_Iteration](https://github.com/MatthewAndreTaylor/fastqueue/assets/100451342/792e21b2-08b9-4e76-b75c-473caa90cdde)

Windows

![Iterable_Instantiation](https://github.com/MatthewAndreTaylor/fastqueue/assets/100451342/7cc9866f-869e-466d-ac50-28a370f73cf7)
![Iterable_Iteration](https://github.com/MatthewAndreTaylor/fastqueue/assets/100451342/b5f53f09-a02a-472d-9ac7-f8cd9ceb3355)
