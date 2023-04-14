# mqueue

![Tests](https://github.com/MatthewAndreTaylor/mqueue/actions/workflows/tests.yml/badge.svg)
[![PyPI Versions](https://img.shields.io/badge/python-3.8%2B-blue)]()
[![PyPI license](https://img.shields.io/badge/license-MIT-%23373737)]()

Single ended fast queue's built in C for python.

## Requirements

- `python 3.8+`

## Installation

To install mqueue, using pip:

```bash
pip install mqueue
```

## Quickstart

```py
>>> from mqueue.mqueue import *
>>> queue = Queue()
>>> queue.extend(['🚒', '🛴'])
>>> queue.enqueue('🚅')
>>> queue.enqueue('🚗')
>>> [queue.dequeue() for _ in range(len(queue)) ]
['🚒', '🛴', '🚅', '🚗']
```
