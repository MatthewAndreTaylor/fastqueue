from typing import Any, Optional
from collections.abc import Iterable
from typing_extensions import Self

class Queue:
    def __init__(self, iterable: Optional[Iterable] = None) -> None: ...
    def enqueue(self, item: Any) -> None: ...
    def dequeue(self) -> Any: ...
    def extend(self, items: Iterable[Any]) -> None: ...
    def __len__(self) -> int: ...
    def is_empty(self) -> bool: ...
    def __getitem__(self, index: int) -> Any: ...
    def __setitem__(self, index: int, item: Any) -> None: ...
    def __contains__(self, item: Any) -> bool: ...
    def copy(self) -> Self: ...
    def __copy__(self) -> Self: ...

class QueueC:
    def __init__(self, iterable: Optional[Iterable] = None) -> None: ...
    def enqueue(self, item: Any) -> None: ...
    def dequeue(self) -> Any: ...
    def extend(self, items: Iterable[Any]) -> None: ...
    def __len__(self) -> int: ...
    def is_empty(self) -> bool: ...
    def __getitem__(self, index: int) -> Any: ...
    def __setitem__(self, index: int, item: Any) -> None: ...
    def __contains__(self, item: Any) -> bool: ...
    def copy(self) -> Self: ...
    def __copy__(self) -> Self: ...

class LockQueue(Queue):
    def get(self) -> Any: ...
