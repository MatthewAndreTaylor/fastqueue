from typing import Any, Iterable, Optional


class Queue:
    """
    A Queue class that implements a FIFO data structure.
    This queue is made up of a linked list of nodes, each containing a queue.
    """

    def __init__(self, iterable: Optional[Iterable] = None) -> None:
        """Initialize the Queue object.

        :param iterable (Optional[Iterable], optional): An iterable to
        initialize the Queue with. Defaults to None
        :param self:
        """
        pass

    def enqueue(self, item: Any) -> None:
        """Add an item to the front of the Queue.

        :param item: (Any): The item to be added to the Queue.
        :param self:
        """
        pass

    def dequeue(self):
        """Remove and return an item from the end of the Queue.

        :return: The item removed from the Queue.
        """
        pass

    def extend(self, items: Iterable[Any]) -> None:
        """Enqueue a sequence of elements from an iterator.

        :param items: (Iterable[Any]): An iterable containing the
        elements to be enqueued.
        :param self:
        """
        pass

    def __len__(self) -> int:
        pass

    def __getitem__(self, index: int):
        pass

    def __setitem__(self, index: int, item: Any) -> None:
        pass

    def __contains__(self, item: Any) -> bool:
        pass

    def copy(self):
        """Return a shallow copy of the Queue.

        :return: A shallow copy of the Queue object.
        """
        pass

    def __copy__(self):
        """Return a shallow copy of the Queue.

        :return: A shallow copy of the Queue object.
        """
        pass


class QueueC:
    """
    A Queue class that implements a FIFO data structure.
    This queue is made up a single contiguous container.
    """

    def __init__(self, iterable: Optional[Iterable] = None) -> None:
        """Initialize the Queue object.

        :param iterable (Optional[Iterable], optional): An iterable to
        initialize the Queue with. Defaults to None
        :param self:
        """
        pass

    def enqueue(self, item: Any) -> None:
        """Add an item to the front of the Queue.

        :param item: (Any): The item to be added to the Queue.
        :param self:
        """
        pass

    def dequeue(self):
        """Remove and return an item from the end of the Queue.

        :return: The item removed from the Queue.
        """
        pass

    def extend(self, items: Iterable[Any]) -> None:
        """Enqueue a sequence of elements from an iterator.

        :param items: (Iterable[Any]): An iterable containing the
        elements to be enqueued.
        :param self:
        """
        pass

    def __len__(self) -> int:
        pass

    def __getitem__(self, index: int):
        pass

    def __setitem__(self, index: int, item: Any) -> None:
        pass

    def __contains__(self, item: Any) -> bool:
        pass

    def copy(self):
        """Return a shallow copy of the Queue.

        :return: A shallow copy of the Queue object.
        """
        pass

    def __copy__(self):
        """Return a shallow copy of the Queue.

        :return: A shallow copy of the Queue object.
        """
        pass
