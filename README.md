# mqueue

[![Tests](https://github.com/MatthewAndreTaylor/mqueue/actions/workflows/tests.yml/badge.svg)](https://github.com/MatthewAndreTaylor/mqueue/actions)
[![PyPI Versions](https://img.shields.io/badge/python-3.9%2B-blue)](https://github.com/MatthewAndreTaylor/mqueue/blob/master/pyproject.toml)
[![PyPI license](https://img.shields.io/badge/license-MIT-%23373737)](https://github.com/MatthewAndreTaylor/mqueue/blob/master/LICENSE)\
[![PyPI](https://img.shields.io/badge/pypi-v0.0.1-blue)](https://pypi.org/project/mqueue-lib/)


Single ended fast queue's built in C for python.

## Requirements

- `python 3.9+`

## Installation

To install mqueue, using pip:

```bash
pip install mqueue-lib
```

## Quickstart

```py
>>> from mqueue.mqueue import *
>>> queue = Queue()
>>> queue.extend(['🚒', '🛴'])
>>> queue[0]
'🚒'
>>> queue.enqueue('🚅')
>>> queue.enqueue('🚗')
>>> queue[-1]
'🚗'
>>> [queue.dequeue() for _ in range(len(queue)) ]
['🚒', '🛴', '🚅', '🚗']
```
