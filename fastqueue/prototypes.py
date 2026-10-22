"""Prototype implementations of a Queue.

* LLQueue   Each element is stored as a Link List Node
* ContQueue   Each element is stored contiguous in memory

"""

from ctypes import *
from pathlib import *
from typing import Any


# Matt's Linked List Queue
class LLNode(Structure):
    pass


LLNode._fields_ = [("val", py_object), ("next", POINTER(LLNode))]


class LLNodeQueue(Structure):
    _fields_ = [
        ("front", POINTER(LLNode)),
        ("back", POINTER(LLNode)),
        ("length", c_uint),
    ]


__libfile = Path(__file__).parent / "cllqueue.so"
# Native calls own Python references and must keep the GIL.
llqueue_lib = PyDLL(str(__libfile))

llqueue_lib.new_node_queue.argtypes = []
llqueue_lib.new_node_queue.restype = POINTER(LLNodeQueue)

llqueue_lib.enqueue.argtypes = [POINTER(LLNodeQueue), py_object]
llqueue_lib.enqueue.restype = None

llqueue_lib.dequeue.argtypes = [POINTER(LLNodeQueue)]
llqueue_lib.dequeue.restype = py_object

llqueue_lib.clear_q.argtypes = [POINTER(LLNodeQueue)]
llqueue_lib.clear_q.restype = None

llqueue_lib.free_q.argtypes = [POINTER(LLNodeQueue)]
llqueue_lib.free_q.restype = None


class LLQueue:
    __slots__ = "queue"
    queue: POINTER(LLNodeQueue)

    def __init__(self):
        self.queue = llqueue_lib.new_node_queue()

    def __len__(self) -> int:
        return self.queue.contents.length

    def enqueue(self, item: Any) -> None:
        llqueue_lib.enqueue(self.queue, item)

    def dequeue(self) -> Any:
        return llqueue_lib.dequeue(self.queue)

    def clear(self):
        llqueue_lib.clear_q(self.queue)

    def __del__(self):
        queue = getattr(self, "queue", None)
        self.queue = None
        llqueue_lib.free_q(queue)


# Matt's Contiguous Queue
class ContiguousQueue(Structure):
    _fields_ = [
        ("objects", POINTER(py_object)),
        ("length", c_size_t),
        ("capacity", c_size_t),
        ("front", c_size_t),
        ("back", c_size_t),
    ]


__libfile = Path(__file__).parent / "ccqueue.so"
cqueue_lib = PyDLL(str(__libfile))

cqueue_lib.new__queue.argtypes = []
cqueue_lib.new__queue.restype = POINTER(ContiguousQueue)

cqueue_lib.enqueue.argtypes = [POINTER(ContiguousQueue), py_object]
cqueue_lib.enqueue.restype = None

cqueue_lib.dequeue.argtypes = [POINTER(ContiguousQueue)]
cqueue_lib.dequeue.restype = py_object

cqueue_lib.clear_q.argtypes = [POINTER(ContiguousQueue)]
cqueue_lib.clear_q.restype = None

cqueue_lib.free_q.argtypes = [POINTER(ContiguousQueue)]
cqueue_lib.free_q.restype = None


class ContQueue:
    __slots__ = "queue"
    queue: POINTER(ContiguousQueue)

    def __init__(self):
        self.queue = cqueue_lib.new__queue()

    def __len__(self) -> int:
        return self.queue.contents.length

    def enqueue(self, item: Any) -> None:
        cqueue_lib.enqueue(self.queue, item)

    def dequeue(self) -> Any:
        return cqueue_lib.dequeue(self.queue)

    def clear(self):
        cqueue_lib.clear_q(self.queue)

    def __del__(self):
        queue = getattr(self, "queue", None)
        self.queue = None
        cqueue_lib.free_q(queue)
