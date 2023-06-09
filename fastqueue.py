class Queue:
    def __init__(self, iterable) -> None:
        """Initialize the Queue object.

        :param iterable (Optional[Iterable], optional): An iterable to
        initialize the Queue with. Defaults to None
        :param self:
        """
        pass

    def enqueue(self, item) -> None:
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

    def extend(self, items) -> None:
        """Enqueue a sequence of elements from an iterator.

        :param items: (Iterable[Any]): An iterable containing the
        elements to be enqueued.
        :param self:
        """
        pass

    def __len__(self) -> int:
        pass

    def is_empty(self) -> bool:
        """Returns whether the Queue is empty.

        :return: True if the Queue is empty, False otherwise.
        """
        pass

    def __getitem__(self, index: int):
        pass

    def __setitem__(self, index: int, item) -> None:
        pass

    def __contains__(self, item) -> bool:
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


class Queue:
    def __init__(self, iterable) -> None:
        """Initialize the Queue object.

        :param iterable (Optional[Iterable], optional): An iterable to
        initialize the Queue with. Defaults to None
        :param self:
        """
        pass

    def enqueue(self, item) -> None:
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

    def extend(self, items) -> None:
        """Enqueue a sequence of elements from an iterator.

        :param items: (Iterable[Any]): An iterable containing the
        elements to be enqueued.
        :param self:
        """
        pass

    def __len__(self) -> int:
        pass

    def is_empty(self) -> bool:
        """Returns whether the Queue is empty.

        :return: True if the Queue is empty, False otherwise.
        """
        pass

    def __getitem__(self, index: int):
        pass

    def __setitem__(self, index: int, item) -> None:
        pass

    def __contains__(self, item) -> bool:
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


class LockQueue(Queue):
    def get(self):
        """Return the first element of the LockQueue, None if no element exists.

        :return: The first element of the LockQueue, or None if the LockQueue
        is empty.
        """
        pass
