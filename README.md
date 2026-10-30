# fastqueue

[![Tests](https://github.com/MatthewAndreTaylor/fastqueue/actions/workflows/tests.yml/badge.svg)](https://github.com/MatthewAndreTaylor/fastqueue/actions)
[![PyPI versions](https://img.shields.io/badge/python-3.7%2B-blue)](https://github.com/MatthewAndreTaylor/fastqueue/)
[![PyPI license](https://img.shields.io/badge/license-MIT-%23373737)](https://github.com/MatthewAndreTaylor/fastqueue/blob/master/LICENSE)\
[![PyPI](https://img.shields.io/pypi/v/fastqueue-lib.svg)](https://pypi.org/project/fastqueue-lib/)


Single-ended Fast Queue Python C-extension.

## Installation

Install with [uv](https://docs.astral.sh/uv/):

```bash
uv pip install fastqueue-lib
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

## Benchmarks

Run every benchmark and save all five figures as PNG and SVG, along with the
measurements and build metadata in JSON:

```bash
uv pip install ".[benchmark]"

uv run python benchmark/main.py --profiles queue
uv run python benchmark/main.py --profiles iteration
```
<img width="2880" height="1600" alt="windows" src="https://github.com/user-attachments/assets/124de899-3864-4d7c-a5c9-f17037e1e02c" />
<img width="2880" height="1600" alt="wsl" src="https://github.com/user-attachments/assets/3317e697-c57a-4a2e-89c3-d676ab5a0d2a" />


<img width="1920" height="1120" alt="Indexed_Increment" src="https://github.com/user-attachments/assets/2dcd61ea-ef3d-422a-b037-f32fef566f23" />

<img width="1920" height="1120" alt="Iterator_Local_Increment" src="https://github.com/user-attachments/assets/43a2f81d-48a3-4d33-a97f-3eb37a926088" />

<img width="1920" height="1120" alt="Iterable_Instantiation" src="https://github.com/user-attachments/assets/e8437e42-7d76-449d-bff8-fb37c20a44ef" />
