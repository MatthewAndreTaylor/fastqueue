# mqueue

[![PyPI Versions](https://img.shields.io/badge/python-3.7%2B-blue)]()
[![PyPI license](https://img.shields.io/badge/license-MIT-%23373737)]()

Single ended fast queue's built in C for python.

## Requirements

- Python 3.7+

## Installation

To install mqueue, using pip:

```bash
pip install mqueue
```

## Quickstart

```py
>>> import mQueue
>>> queue = mQueue.Queue()
>>> queue.extend(['🚒', '🛴'])
>>> queue.enqueue('🚅')
>>> queue.enqueue('🚗')
>>> [queue.dequeue() for _ in range(len(queue)) ]
['🚒', '🛴', '🚅', '🚗']
```
