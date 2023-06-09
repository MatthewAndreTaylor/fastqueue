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
llqueue_lib = CDLL(str(__libfile))

llqueue_lib.new_node_queue.argtypes = []
llqueue_lib.new_node_queue.restype = POINTER(LLNodeQueue)

llqueue_lib.is_empty.argtypes = [POINTER(LLNodeQueue)]
llqueue_lib.is_empty.restype = c_bool

llqueue_lib.enqueue.argtypes = [POINTER(LLNodeQueue), py_object]
llqueue_lib.enqueue.restype = None

llqueue_lib.dequeue.argtypes = [POINTER(LLNodeQueue)]
llqueue_lib.dequeue.restype = py_object

llqueue_lib.free_q.argtypes = [POINTER(LLNodeQueue)]
llqueue_lib.free_q.restype = None


class LLQueue:
    __slots__ = "queue"
    queue: POINTER(LLNodeQueue)

    def __init__(self):
        self.queue = llqueue_lib.new_node_queue()

    def is_empty(self) -> bool:
        return llqueue_lib.is_empty(self.queue)

    def __len__(self) -> int:
        return self.queue.contents.length

    def enqueue(self, item: Any) -> None:
        llqueue_lib.enqueue(self.queue, item)

    def dequeue(self) -> Any:
        if self.is_empty():
            raise IndexError
        return llqueue_lib.dequeue(self.queue)

    def clear(self):
        llqueue_lib.free_q(self.queue)
        self.queue = llqueue_lib.new__queue()

    def __del__(self):
        llqueue_lib.free_q(self.queue)


# Matt's Contiguous Queue
class ContiguousQueue(Structure):
    _fields_ = [
        ("objects", POINTER(py_object)),
        ("length", c_int),
        ("capacity", c_int),
        ("front", c_int),
        ("back", c_int),
    ]


__libfile = Path(__file__).parent / "ccqueue.so"
cqueue_lib = CDLL(str(__libfile))

cqueue_lib.new__queue.argtypes = []
cqueue_lib.new__queue.restype = POINTER(ContiguousQueue)

cqueue_lib.is_empty.argtypes = [POINTER(ContiguousQueue)]
cqueue_lib.is_empty.restype = c_bool

cqueue_lib.enqueue.argtypes = [POINTER(ContiguousQueue), py_object]
cqueue_lib.enqueue.restype = None

cqueue_lib.dequeue.argtypes = [POINTER(ContiguousQueue)]
cqueue_lib.dequeue.restype = py_object

cqueue_lib.free_q.argtypes = [POINTER(ContiguousQueue)]
cqueue_lib.free_q.restype = None


class ContQueue:
    __slots__ = "queue"
    queue: POINTER(ContiguousQueue)

    def __init__(self):
        self.queue = cqueue_lib.new__queue()

    def is_empty(self) -> bool:
        return cqueue_lib.is_empty(self.queue)

    def __len__(self) -> int:
        return self.queue.contents.length

    def enqueue(self, item: Any) -> None:
        cqueue_lib.enqueue(self.queue, item)

    def dequeue(self) -> Any:
        if self.is_empty():
            raise IndexError
        return cqueue_lib.dequeue(self.queue)

    def clear(self):
        cqueue_lib.free_q(self.queue)
        self.queue = cqueue_lib.new__queue()

    def __del__(self):
        cqueue_lib.free_q(self.queue)
