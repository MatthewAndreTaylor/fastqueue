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
`fastqueue.Queue()` starts with 254 pointer slots and doubles the capacity of
newly allocated nodes as it grows. Each node stores its header and pointer slots
in one allocation; existing nodes never move. Retired nodes are cached and reused
at their original capacities. This reduces allocation overhead for large queues
but can retain more spare memory after draining.

Both queue types provide native iterators for `for item in queue`, visiting
items in FIFO order without removing them. `Queue` walks each chunk once;
`QueueC` walks its ring buffer directly. Adding or removing items during iteration
raises `RuntimeError` on the next step of an active iterator. Replacing an item
with `queue[index] = value` is allowed.

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
`fastqueue.QueueC()` starts with 512 pointer slots and doubles its contiguous
buffer when full. Bulk extension reserves its requested length plus the current
capacity. Ring indexing uses modulo to support arbitrary allocation sizes.
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

One command produces a **2 x 3 image matrix** for enqueue, dequeue, extend,
iteration, random access, and mixed enqueue/dequeue workloads, comparing `Queue`,
`QueueC`, and `collections.deque`. The colors and arithmetic means match
[`compare_queue.py`](examples/compare_queue.py), with one solid line per queue type.
Both axes are linear and start at zero; lower elapsed time is better.
The top row shows enqueue, dequeue, and mixed workloads; the bottom row shows
iteration, random access, and extend.

Each line connects the measured mean at **100 queue sizes, from 500 to 99,500
items in steps of 1,000**, below the 100,000-item limit. Each point averages
**25 measured trials**, following **2 warmups**.
All operation/type/size combinations are shuffled each trial using a fixed seed.
The graphs use the measured points directly, without smoothing or curve fitting.

| Operation | Timed workload |
| --- | --- |
| Enqueue | Add N items individually to an empty queue (`appendleft` for deque). |
| Dequeue | Remove N items from a prefilled queue (`pop` for deque). |
| Extend | One `extend` call with a prebuilt list of N items. |
| Iteration | One full pass with `for item in queue: pass`. |
| Random access (`__getitem__`) | N lookups using prebuilt random indices into a prefilled queue of N items (`getter_profiles`). |
| Mixed enqueue/dequeue | N enqueue-then-dequeue pairs on a queue prefilled with N items; 2N operations total (`appendleft`/`pop` for deque). |

Enqueue, dequeue, extend, and random access reuse the exact profiles used by `compare_queue.py`,
including its unbound method calls and Python loop overhead. Input generation,
queue construction/prefilling, and destruction are outside the timers. The mixed
workload maintains N live items between pairs and briefly reaches N+1 after each
enqueue; its panel shows total time for all 2N operations. Both queues use native
iterators: `Queue` walks linked chunks, and `QueueC` walks its ring buffer directly.
All workloads are single-threaded.

Collected on **2026-10-27** from the current working tree based on **`eae1c22`**,
with fresh native builds, **CPython 3.11.15**, **Matplotlib 3.11.2**, and
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

Each benchmark command collects all six workloads and writes the platform's
SVG, PNG, and JSON to `docs/benchmarks`. Use `--plot-only` to regenerate the matrix
from saved measurements containing all six workloads, `--output` to save elsewhere, or `--sizes` and
`--trials` to change the workload. Rebuild the package after changing native code
before collecting new measurements.

### Enqueue optimization comparison

This compares `Queue.enqueue` from published **0.0.17**, unmodified
**master `a9e21de`** (labelled `latest`), and the current working tree (labelled
`optimized`) with `collections.deque.appendleft`. All extensions match the same
Python ABI within each platform. Each trial shuffles all builds and sizes in one process,
using identical input lists. There are **150 measured trials**, **2 warmups**, and
99 sizes from 500 to 49,500 in steps of 500. The right panel shows deque time divided by Queue
time: values above 1 favor Queue. Points are arithmetic means without smoothing.

The current Queue starts with 254 pointer slots and doubles newly allocated
node capacities. Node headers and pointer slots share one allocation, and
retired nodes are cached for reuse. The matrices above also include the current
QueueC with its 512-slot base and modulo indexing.

| CPython 3.11.15 | 0.0.17 | Master | Optimized | deque | Optimized speedup over deque |
| --- | ---: | ---: | ---: | ---: | ---: |
| Windows | 18.43 ns/item | 18.09 ns/item | 17.94 ns/item | 18.45 ns/item | 1.028x |
| WSL2 | 15.70 ns/item | 15.39 ns/item | 14.75 ns/item | 15.63 ns/item | 1.060x |

These aggregate rates divide the sum of mean elapsed times by the sum of queue
sizes. In this run, the current Queue has about 2.8% higher enqueue throughput
than deque on Windows and 6.0% higher on WSL2. Relative to master, its
aggregate throughput is about 0.8% higher on Windows and 4.4% higher on WSL2.
Individual points vary; these are point estimates for 500 to 49,500 items.
The matrices and comparison runs use different trial schedules, so compare
implementations within each run rather than mixing their absolute timings.

[`compare_enqueue.py`](examples/compare_enqueue.py) takes `--build LABEL=PATH`
arguments pointing to separately compiled `_fastqueue` extensions. Build every
version with the interpreter used for the comparison. The exact paths below
refer to the isolated baseline builds used for this run; the optimized Windows
extension was built in the repository root with `python setup.py build_ext --inplace`.
The WSL `wsl-linear` directory was refreshed with the current native sources and
rebuilt before this run; its directory name is retained by the command below.

![Windows enqueue comparison](docs/benchmarks/enqueue-windows.svg)

```powershell
.tox/bench-windows/Scripts/python.exe -u examples/compare_enqueue.py --build 0.0.17=.tox/enqueue-opt/release311/_fastqueue.cp311-win_amd64.pyd --build latest=.tox/enqueue-opt/latest/_fastqueue.cp311-win_amd64.pyd --build optimized=_fastqueue.cp311-win_amd64.pyd --trials 25 --seed 20261027 --output docs/benchmarks/enqueue-windows
```

[Raw Windows comparison](docs/benchmarks/enqueue-windows.json)

![WSL2 enqueue comparison](docs/benchmarks/enqueue-wsl.svg)

```bash
.tox/bench-wsl/bin/python -u examples/compare_enqueue.py --build 0.0.17=.tox/enqueue-opt/wsl-release311/_fastqueue.cpython-311-x86_64-linux-gnu.so --build latest=.tox/enqueue-opt/wsl-latest/_fastqueue.cpython-311-x86_64-linux-gnu.so --build optimized=.tox/enqueue-opt/wsl-linear/_fastqueue.cpython-311-x86_64-linux-gnu.so --trials 25 --seed 20261027 --output docs/benchmarks/enqueue-wsl
```

[Raw WSL comparison](docs/benchmarks/enqueue-wsl.json)
