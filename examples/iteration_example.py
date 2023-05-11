from fastqueue import *
from collections import deque
import numpy
import time
import matplotlib.pyplot as plt

size = 500000

iterable_structures = [
    "Numpy Array",
    "Collections dequeue",
    "Matt's C Contiguous queue",
]
times = []

start = time.time()
q = QueueC()
q.extend([i for i in range(size)])
times.append(time.time() - start)

start = time.time()
deq = deque([i for i in range(size)])
times.append(time.time() - start)

start = time.time()
arr = numpy.array([i for i in range(size)])
times.append(time.time() - start)

fig = plt.figure(figsize=(15, 7))
plt.bar(iterable_structures, times, color=["r", "g", "b"], width=0.5)
for i, v in enumerate(times):
    plt.text(i, v, str(round(v, 5)), ha="center", family="sans-serif")
plt.xlabel("Type")
plt.ylabel("Time")
plt.title("Instantiation")
plt.savefig("Iterable_Instantiation.png")
print("Iterables Instantiation times Graphed")

times = []

start = time.time()
for i in range(len(q)):
    q[i] += 1
times.append(time.time() - start)

start = time.time()
for i in range(len(arr)):
    deq[i] += 1
times.append(time.time() - start)

start = time.time()
for i in range(len(arr)):
    arr[i] += 1
times.append(time.time() - start)

for i in range(size):
    assert arr[i] == i + 1
    assert deq[i] == i + 1
    assert q[i] == i + 1

fig = plt.figure(figsize=(15, 7))
plt.bar(iterable_structures, times, color=["r", "g", "b"], width=0.5)
for i, v in enumerate(times):
    plt.text(i, v, str(round(v, 5)), ha="center", family="sans-serif")
plt.xlabel("Type")
plt.ylabel("Time")
plt.title("Iteration")
plt.savefig("Iterable_Iteration.png")
print("Iterables Iteration times Graphed")
