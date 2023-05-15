from fastqueue import *
from collections import deque
import numpy
import time
import matplotlib.pyplot as plt

size = 500000


def iterate(o):
    start_time = time.time()
    for i in range(len(o)):
        o[i] += 1
    return time.time() - start_time


iterable_structures = [
    "Matt's C Contiguous queue",
    "Collections dequeue",
    "Numpy Array",
]
iterables = []
times = []
for iterable_type in [QueueC, deque, numpy.array]:
    start_time = time.time()
    iterables.append(iterable_type([i for i in range(size)]))
    times.append(time.time() - start_time)

fig = plt.figure(figsize=(15, 7))
plt.bar(iterable_structures, times, color=["r", "g", "b"], width=0.5)
for i, v in enumerate(times):
    plt.text(i, v, str(round(v, 5)), ha="center", family="sans-serif")
plt.xlabel("Type")
plt.ylabel("Time")
plt.title("Instantiation")
plt.savefig("Iterable_Instantiation.png")
print("Iterables Instantiation times Graphed")

times = [iterate(it) for it in iterables]
for i in range(size):
    for it in iterables:
        assert it[i] == i + 1

fig = plt.figure(figsize=(15, 7))
plt.bar(iterable_structures, times, color=["r", "g", "b"], width=0.5)
for i, v in enumerate(times):
    plt.text(i, v, str(round(v, 5)), ha="center", family="sans-serif")
plt.xlabel("Type")
plt.ylabel("Time")
plt.title("Iteration")
plt.savefig("Iterable_Iteration.png")
print("Iterables Iteration times Graphed")
