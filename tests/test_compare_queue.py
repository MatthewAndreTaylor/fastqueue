from collections import deque
import ctypes
import hashlib
import json
from pathlib import Path
import platform
import sys

import pytest

import _fastqueue
from fastqueue import Queue, QueueC
from examples.compare_queue import memory_layout, memory_samples, measure_memory


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("old", [False, True])
def test_memory_layout_reads_both_native_headers(old):
    chunklen = 256 if old else 384
    source = """
        #define CHUNKLEN %d
        typedef struct QueueNode {
            %s
            struct QueueNode* next;
            PyObject *py_objects[CHUNKLEN];
        } QueueNode_t;
        typedef struct {
            PyObject_HEAD %s
            size_t front;
            size_t capacity;
            size_t back;
            PyObject** objects;
        } QueueC;
    """ % (chunklen, "Py_ssize_t numEntries; /* count */ Py_ssize_t front; Py_ssize_t back;" if old else "",
           "size_t length; // old header\n" if old else "")
    actual_chunklen, node_type, queuec_type = memory_layout(source)
    pointer_bytes = ctypes.sizeof(ctypes.c_void_p)
    assert actual_chunklen == chunklen
    assert ctypes.sizeof(node_type) == (chunklen + 1) * pointer_bytes + (3 * ctypes.sizeof(ctypes.c_ssize_t) if old else 0)
    assert ctypes.sizeof(queuec_type) == object.__basicsize__ + (4 if old else 3) * ctypes.sizeof(ctypes.c_size_t) + pointer_bytes
    assert queuec_type.capacity.offset == object.__basicsize__ + (2 if old else 1) * ctypes.sizeof(ctypes.c_size_t)


@pytest.mark.parametrize("replacement", ["double capacity;", "size_t capacity[CHUNKLEN];"])
def test_memory_layout_rejects_unsupported_fields(replacement):
    source = (ROOT / "src" / "fastqueue.c").read_text()
    with pytest.raises(ValueError, match="Unsupported native field"):
        memory_layout(source.replace("size_t capacity;", replacement, 1))


def test_memory_samples_count_native_storage_at_capacity_boundaries():
    source = (ROOT / "src" / "fastqueue.c").read_text()
    chunklen, node_type, queuec_type = memory_layout(source)
    sizes = [0, 1, chunklen, chunklen + 1]
    rows, layout = memory_samples({"Queue": Queue, "QueueC": QueueC, "deque": deque}, sizes, source)
    assert len(rows) == 2 * 3 * len(sizes)
    assert layout["node_bytes"] == ctypes.sizeof(node_type)
    values = {(row["queue_type"], row["operation"], row["size"]): row["bytes"] for row in rows}
    for operation in ("enqueue", "extend"):
        empty = values["Queue", operation, 0]
        assert empty == sys.getsizeof(Queue()) + ctypes.sizeof(node_type)
        assert values["Queue", operation, 1] == empty
        assert values["Queue", operation, chunklen] == empty
        assert values["Queue", operation, chunklen + 1] == empty + ctypes.sizeof(node_type)
        for size in sizes:
            contiguous = QueueC()
            standard = deque()
            if operation == "extend":
                contiguous.extend([None] * size)
                standard.extend([None] * size)
            else:
                for _ in range(size):
                    contiguous.enqueue(None)
                    standard.appendleft(None)
            capacity = queuec_type.from_address(id(contiguous)).capacity
            assert values["QueueC", operation, size] == sys.getsizeof(contiguous) + capacity * ctypes.sizeof(ctypes.c_void_p)
            assert values["deque", operation, size] == sys.getsizeof(standard)
    assert values["QueueC", "enqueue", chunklen + 1] != values["QueueC", "extend", chunklen + 1]


def test_memory_worker_rejects_changed_timing_build(tmp_path):
    build = {
        "root": str(ROOT), "extension": _fastqueue.__file__,
        "python": sys.version, "platform": platform.platform(),
        "source_sha256": "changed source",
        "extension_sha256": hashlib.sha256(Path(_fastqueue.__file__).read_bytes()).hexdigest(),
    }
    manifest = {"blocks": 1, "sizes": [1],
                "runs": [dict(build, version=version) for version in ("before", "after")]}
    (tmp_path / "run.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="no longer matches timings"):
        measure_memory(tmp_path, "before")
    assert not (tmp_path / "before-memory.csv").exists()
