from typing import Any
from collections.abc import Iterable


class Queue:
    def __init__(self):
        ...

    def enqueue(self, item: Any) -> None:
        ...

    def dequeue(self) -> Any:
        ...

    def extend(self, items: Iterable[Any]) -> None:
        ...

    def __len__(self) -> int:
        ...

    def is_empty(self) -> bool:
        ...

    def __getitem__(self, index: int) -> Any:
        ...

    def __setitem__(self, index: int, item: Any) -> None:
        ...

    def __contains__(self, item: Any) -> bool:
        ...


class QueueC:
    def __init__(self):
        ...

    def enqueue(self, item: Any) -> None:
        ...

    def dequeue(self) -> Any:
        ...

    def extend(self, items: Iterable[Any]) -> None:
        ...

    def __len__(self) -> int:
        ...

    def is_empty(self) -> bool:
        ...

    def __getitem__(self, index: int) -> Any:
        ...

    def __setitem__(self, index: int, item: Any) -> None:
        ...

    def __contains__(self, item: Any) -> bool:
        ...


class LockQueue(Queue):
    pass
