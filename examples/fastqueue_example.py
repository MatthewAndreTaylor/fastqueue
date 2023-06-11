import random
import time
import sys
from pandas import DataFrame
import matplotlib.pyplot as plt
from collections import deque
from fastqueue import *


class QueueOperationProfile:
    def __init__(self, structure, op, size):
        self.structure = structure
        self.op = op
        self.size = size
        self.execution_times = []

    def as_tuple(self) -> tuple:
        return (
            self.size,
            self.structure.__class__.__module__,
            self.structure.__class__.__name__,
            self.op.__name__,
            self.execution_times,
        )

    def run(self) -> None:
        pass


class NoArgProfile(QueueOperationProfile):
    def run(self) -> None:
        copy = self.structure.copy()
        start = time.perf_counter_ns()
        for _ in range(self.size):
            self.op(copy)
        end = time.perf_counter_ns()
        self.execution_times.append(end - start)


class SingleArgProfile(QueueOperationProfile):
    def __init__(self, structure, op, data, size):
        super().__init__(structure, op, size)
        self.data = data

    def run(self) -> None:
        copy = self.structure.copy()
        start = time.perf_counter_ns()
        for item in self.data:
            self.op(copy, item)
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


def enqueue_profiles(it):
    res = []
    for i in it:
        items = [random.randint(0, 1000) for _ in range(i)]
        res.append(SingleArgProfile(deque(), deque.appendleft, items, i))
        res.append(SingleArgProfile(Queue(), Queue.enqueue, items, i))
        res.append(SingleArgProfile(QueueC(), QueueC.enqueue, items, i))
    return res


def dequeue_profiles(it):
    res = []
    for i in it:
        items = [random.randint(0, 1000) for _ in range(i)]
        res.append(NoArgProfile(deque(items), deque.pop, i))
        res.append(NoArgProfile(Queue(items), Queue.dequeue, i))
        res.append(NoArgProfile(QueueC(items), QueueC.dequeue, i))
    return res


def extend_profiles(it):
    res = []
    for i in it:
        items = [random.randint(0, 1000) for _ in range(i)]
        res.append(SingleArgProfile(deque(), deque.extend, [items], i))
        res.append(SingleArgProfile(Queue(), Queue.extend, [items], i))
        res.append(SingleArgProfile(QueueC(), QueueC.extend, [items], i))
    return res


if __name__ == "__main__":
    seed = 10
    random.seed(seed)
    it = range(500, 50000, 500)
    trials = 50

    tests = dequeue_profiles(it) + enqueue_profiles(it) + extend_profiles(it)
    run_profiles(tests, trials)
    df = to_dataframe(tests)

    fig, ax = plt.subplots()
    plt.title(f"Queue Performance : {sys.platform}")
    ax.set_xlabel("Number of operations")
    ax.set_ylabel("Time (microseconds)")

    grouped = df.groupby(["module", "queue_type", "queue_op"])
    for name, group in grouped:
        means = group.groupby("size")["time"].mean()
        ax.plot(means, label=name)
    ax.legend()
    plt.show()
