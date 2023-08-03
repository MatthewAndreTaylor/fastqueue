import random
import time
import sys
from pandas import DataFrame
import matplotlib.pyplot as plt
from collections import deque
from fastqueue import *


class QueueOperationProfile:
    def __init__(self, structure, op, size, constructor_params=[]):
        self.structure = structure
        self.op = op
        self.size = size
        self.execution_times = []
        self.constructor_params = constructor_params

    def as_tuple(self) -> tuple:
        return (
            self.size,
            self.structure.__module__,
            self.structure.__name__,
            self.op.__name__,
            self.execution_times,
        )

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


def run_profiles(profiles: QueueOperationProfile, trials: int) -> None:
    for i in range(trials):
        print(f"Trial: {i + 1}/{trials}")
        random.shuffle(profiles)
        for profile in profiles:
            profile.run()


def to_dataframe(profiles: QueueOperationProfile):
    frame = DataFrame.from_records(
        data=map(lambda profile: profile.as_tuple(), profiles),
        columns=["size", "module", "queue_type", "queue_op", "time"],
    )
    frame = frame.explode("time")
    frame["time"] = frame["time"].astype(float)
    frame["time"] /= 10**3
    return frame


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


def execute_profiles(seed, profiles, num_trials):
    random.seed(seed)
    run_profiles(profiles, num_trials)
    df = to_dataframe(profiles)

    fig, ax = plt.subplots()
    plt.title(f"Queue Performance : {sys.platform}")
    ax.set_xlabel("Number of operations")
    ax.set_ylabel("Time (microseconds)")

    grouped = df.groupby(["queue_type", "queue_op"])
    for name, group in grouped:
        means = group.groupby("size")["time"].mean()
        ax.plot(means, label=name)
    ax.legend()
    plt.show()


if __name__ == "__main__":
    it = range(500, 50000, 500)
    execute_profiles(
        1,
        dequeue_profiles(it)
        + enqueue_profiles(it)
        + extend_profiles(it)
        + getter_profiles(it),
        50,
    )
