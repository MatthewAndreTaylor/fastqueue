# fastqueue

[![Tests](https://github.com/MatthewAndreTaylor/fastqueue/actions/workflows/tests.yml/badge.svg)](https://github.com/MatthewAndreTaylor/fastqueue/actions)
[![PyPI versions](https://img.shields.io/badge/python-3.7%2B-blue)](https://github.com/MatthewAndreTaylor/fastqueue/)
[![PyPI license](https://img.shields.io/badge/license-MIT-%23373737)](https://github.com/MatthewAndreTaylor/fastqueue/blob/master/LICENSE)\
[![PyPI](https://img.shields.io/pypi/v/fastqueue-lib.svg)](https://pypi.org/project/fastqueue-lib/)


Single-ended fast queues built in C tuned for Python.

## Requirements

- `python 3.7+`

## Installation

To install fastqueue, using [pip](https://pypi.org/project/fastqueue-lib): 

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

## Example Benchmarks

One command produces a **2 x 2 image matrix** for enqueue, dequeue, extend, and
iteration, comparing `Queue`, `QueueC`, and `collections.deque`.
The layout, colors, and arithmetic means match
[`compare_queue.py`](examples/compare_queue.py), with one solid line per queue type.
Both axes are linear and start at zero; lower elapsed time is better.

Each line connects the measured mean at **99 queue sizes, from 500 to 49,500
items in steps of 500**. Each point averages **50 trials**, following **2 warmups**.
All operation/type/size combinations are shuffled each trial using a fixed seed.
The graphs use the measured points directly, without smoothing or curve fitting.

| Operation | Timed workload |
| --- | --- |
| Enqueue | Add N items individually to an empty queue (`appendleft` for deque). |
| Dequeue | Remove N items from a prefilled queue (`pop` for deque). |
| Extend | One `extend` call with a prebuilt list of N items. |
| Iteration | One full pass with `for item in queue: pass`. |

Enqueue, dequeue, and extend reuse the exact profiles used by `compare_queue.py`,
including its unbound method calls and Python loop overhead. Input generation,
queue construction/prefilling, and destruction are outside the timers. The
iteration panel measures sequential traversal; the comparison script's fourth
panel measures random indexing. `Queue` currently iterates through indexed
lookups over linked chunks, so its traversal cost grows faster than its length.
All workloads are single-threaded.

Collected on **2026-10-27** from **master `a9e21de`**, with fresh native builds of
**fastqueue-lib 0.0.18**, **CPython 3.11.15**, **Matplotlib 3.11.2**, and
**pandas 3.1.0**, on an **Intel Core Ultra 7 265H**. Windows 11 Enterprise and
WSL2 Ubuntu 24.04 runs used the same machine and ran sequentially. Results depend
on the machine, Python build, and workload; WSL includes its virtualization environment.
Raw JSON includes every sample, source revision, source and extension hashes,
import path, and environment details.

### Windows (PowerShell)

From the repository root, prepare the environment with `uv` and rebuild the
current package. A C/C++ compiler is required.

```powershell
uv venv --python 3.11 .tox/bench-windows
uv pip install --python .tox/bench-windows/Scripts/python.exe --reinstall-package fastqueue-lib . matplotlib==3.11.2 pandas==3.1.0
```

![Windows queue benchmark matrix](docs/benchmarks/windows.svg)

```powershell
.tox/bench-windows/Scripts/python.exe -u examples/benchmark.py
```

[Raw Windows measurements](docs/benchmarks/windows.json)

### WSL2 (Ubuntu terminal)

From the repository root in WSL, prepare a separate Linux environment with `uv`
and a C/C++ compiler (for Ubuntu, `sudo apt install build-essential`).

```bash
uv venv --python 3.11 .tox/bench-wsl
uv pip install --python .tox/bench-wsl/bin/python --reinstall-package fastqueue-lib . matplotlib==3.11.2 pandas==3.1.0
```

![WSL2 Ubuntu queue benchmark matrix](docs/benchmarks/wsl.svg)

```bash
.tox/bench-wsl/bin/python -u examples/benchmark.py
```

[Raw WSL measurements](docs/benchmarks/wsl.json)

Each benchmark command collects all four operations and writes the platform's
SVG, PNG, and JSON to `docs/benchmarks`. Use `--plot-only` to regenerate the matrix
from its saved measurements, `--output` to save elsewhere, or `--sizes` and
`--trials` to change the workload. Rebuild the package after changing native code
before collecting new measurements.

### Enqueue optimization comparison

This compares `Queue.enqueue` from the published **0.0.17** source, unmodified
**master `a9e21de`**, and the optimized implementation in this working tree with
`collections.deque.appendleft`. All native builds use the same Python and compiler
within each platform. Each trial shuffles all builds and sizes in one process,
using identical input lists. There are **150 measured trials**, **2 warmups**, and
the same 99 sizes as above. The right panel shows deque time divided by Queue
time: values above 1 favor Queue. Points are arithmetic means without smoothing.

The optimized Queue uses linear positions within each block, removes redundant
entry counts, and moves allocation into a separate function. Its object is 16
bytes smaller on these 64-bit builds. A partially consumed live queue can need
one additional 384-item block compared with the previous layout.

| CPython 3.11.15 | 0.0.17 | Master | Optimized | deque | Optimized speedup over deque |
| --- | ---: | ---: | ---: | ---: | ---: |
| Windows | 18.48 ns/item | 18.17 ns/item | 17.93 ns/item | 18.70 ns/item | 1.043x |
| WSL2 | 14.70 ns/item | 14.36 ns/item | 13.68 ns/item | 14.60 ns/item | 1.068x |

These aggregate rates divide the sum of mean elapsed times by the sum of queue
sizes. Individual points vary; the Windows improvement over master is only
about 1.3%, while WSL improves about 5.0%. The four-operation matrices above
remain measurements of unmodified master `a9e21de`.

[`compare_enqueue.py`](examples/compare_enqueue.py) takes `--build LABEL=PATH`
arguments pointing to separately compiled `_fastqueue` extensions. Build every
version with the interpreter used for the comparison. The exact paths below
refer to the isolated baseline builds used for this run; the optimized Windows
extension was built in the repository root with `python setup.py build_ext --inplace`.

![Windows enqueue comparison](docs/benchmarks/enqueue-windows.svg)

```powershell
.tox/bench-windows/Scripts/python.exe -u examples/compare_enqueue.py --build 0.0.17=.tox/enqueue-opt/release311/_fastqueue.cp311-win_amd64.pyd --build latest=.tox/enqueue-opt/latest/_fastqueue.cp311-win_amd64.pyd --build optimized=_fastqueue.cp311-win_amd64.pyd --trials 150 --seed 20261027 --output docs/benchmarks/enqueue-windows
```

[Raw Windows comparison](docs/benchmarks/enqueue-windows.json)

![WSL2 enqueue comparison](docs/benchmarks/enqueue-wsl.svg)

```bash
.tox/bench-wsl/bin/python -u examples/compare_enqueue.py --build 0.0.17=.tox/enqueue-opt/wsl-release311/_fastqueue.cpython-311-x86_64-linux-gnu.so --build latest=.tox/enqueue-opt/wsl-latest/_fastqueue.cpython-311-x86_64-linux-gnu.so --build optimized=.tox/enqueue-opt/wsl-linear/_fastqueue.cpython-311-x86_64-linux-gnu.so --trials 150 --seed 20261027 --output docs/benchmarks/enqueue-wsl
```

[Raw WSL comparison](docs/benchmarks/enqueue-wsl.json)
