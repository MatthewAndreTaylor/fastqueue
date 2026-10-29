import random
import time
from collections import deque
from fastqueue import *

DEFAULT_SIZES = range(500, 401000, 20000)


class QueueOperationProfile:
    def __init__(self, structure, op, size, constructor_params=[]):
        self.structure = structure
        self.op = op
        self.size = size
        self.execution_times = []
        self.constructor_params = constructor_params

    def run(self) -> None:
        pass


class NoArgProfile(QueueOperationProfile):
    def run(self) -> None:
        test_instance = self.structure(self.constructor_params)
        start = time.perf_counter_ns()
        for _ in range(self.size):
            self.op(test_instance)
        end = time.perf_counter_ns()
        self.execution_times.append(end - start)


class SingleArgProfile(QueueOperationProfile):
    def __init__(self, structure, op, data, size, constructor_params=[]):
        super().__init__(structure, op, size, constructor_params)
        self.data = data

    def run(self) -> None:
        test_instance = self.structure(self.constructor_params)
        start = time.perf_counter_ns()
        for item in self.data:
            self.op(test_instance, item)
        end = time.perf_counter_ns()
        self.execution_times.append(end - start)


class MixedProfile(SingleArgProfile):
    def __init__(self, structure, enqueue, dequeue, data, size, constructor_params):
        super().__init__(structure, enqueue, data, size, constructor_params)
        self.dequeue = dequeue

    def run(self) -> None:
        test_instance = self.structure(self.constructor_params)
        start = time.perf_counter_ns()
        for item in self.data:
            self.op(test_instance, item)
            self.dequeue(test_instance)
        end = time.perf_counter_ns()
        self.execution_times.append(end - start)


class IteratorTraversalProfile(QueueOperationProfile):
    def run(self) -> None:
        test_instance = self.structure(self.constructor_params)
        start = time.perf_counter_ns()
        for item in test_instance:
            pass
        end = time.perf_counter_ns()
        self.execution_times.append(end - start)


def run_profiles(profiles: QueueOperationProfile, trials: int) -> None:
    for i in range(trials):
        print(f"Trial: {i + 1}/{trials}")
        random.shuffle(profiles)
        for profile in profiles:
            profile.run()


def getter_profiles(it):
    res = []
    for i in it:
        items = [random.randint(0, 1000) for _ in range(i)]
        indices = [random.randint(0, len(items) - 1) for _ in range(i)]
        res.append(SingleArgProfile(deque, deque.__getitem__, indices, i, items))
        res.append(SingleArgProfile(Queue, Queue.__getitem__, indices, i, items))
        res.append(SingleArgProfile(QueueC, QueueC.__getitem__, indices, i, items))
    return res


def enqueue_profiles(it):
    res = []
    for i in it:
        items = [random.randint(0, 1000) for _ in range(i)]
        res.append(SingleArgProfile(deque, deque.appendleft, items, i))
        res.append(SingleArgProfile(Queue, Queue.enqueue, items, i))
        res.append(SingleArgProfile(QueueC, QueueC.enqueue, items, i))
    return res


def dequeue_profiles(it):
    res = []
    for i in it:
        items = [random.randint(0, 1000) for _ in range(i)]
        res.append(NoArgProfile(deque, deque.pop, i, items))
        res.append(NoArgProfile(Queue, Queue.dequeue, i, items))
        res.append(NoArgProfile(QueueC, QueueC.dequeue, i, items))
    return res


def extend_profiles(it):
    res = []
    for i in it:
        items = [random.randint(0, 1000) for _ in range(i)]
        res.append(SingleArgProfile(deque, deque.extend, [items], i))
        res.append(SingleArgProfile(Queue, Queue.extend, [items], i))
        res.append(SingleArgProfile(QueueC, QueueC.extend, [items], i))
    return res


def iterator_profiles(it):
    res = []
    for i in it:
        items = [random.randint(0, 1000) for _ in range(i)]
        for structure in (deque, Queue, QueueC):
            res.append(IteratorTraversalProfile(structure, iter, i, items))
    return res


def mixed_profiles(it):
    res = []
    for i in it:
        initial = [random.randint(0, 1000) for _ in range(i)]
        items = [random.randint(0, 1000) for _ in range(i)]
        # appendleft/pop needs reversed storage to remove the same FIFO inputs.
        res.append(
            MixedProfile(deque, deque.appendleft, deque.pop, items, i, initial[::-1])
        )
        res.append(MixedProfile(Queue, Queue.enqueue, Queue.dequeue, items, i, initial))
        res.append(
            MixedProfile(QueueC, QueueC.enqueue, QueueC.dequeue, items, i, initial)
        )
    return res
