import sys, time
import matplotlib.pyplot as plt
import collections
import mQueue
import mQueueContiguous

fig, ax = plt.subplots()
queue_sizes = [100, 1000, 10000, 100000, 1000000, 4000000]

queue_structures = {
    "Collections dequeue": (
        collections.deque(), collections.deque.appendleft,
        collections.deque.pop,
        collections.deque.extendleft),
    "Matt's C queue": (
        mQueue.Queue(), mQueue.Queue.enqueue, mQueue.Queue.dequeue,
        mQueue.Queue.extend),
    "Matt's C Contiguous queue": (
        mQueueContiguous.Queue(), mQueueContiguous.Queue.enqueue,
        mQueueContiguous.Queue.dequeue, mQueueContiguous.Queue.extend),
}
queue_types = queue_structures.keys()

for q in queue_types:
    queue_times = []
    enqueue = queue_structures[q][1]
    dequeue = queue_structures[q][2]
    for size in queue_sizes:
        start = time.time()
        for i in range(size):
            enqueue(queue_structures[q][0], i)

        assert ([dequeue(queue_structures[q][0]) for _ in range(size)] == list(
            range(size)))
        queue_times.append(time.time() - start)

    ax.plot(queue_sizes, queue_times, label=q)

for q in queue_types:
    queue_times = []
    extend = queue_structures[q][3]
    dequeue = queue_structures[q][2]
    for size in queue_sizes:
        start = time.time()
        extend(queue_structures[q][0], range(size))
        assert ([dequeue(queue_structures[q][0]) for _ in range(size)] == list(
            range(size)))
        queue_times.append(time.time() - start)

    ax.plot(queue_sizes, queue_times, label=q + " extend")

ax.legend()
plt.title(f"Queue Timing : {sys.platform}")
plt.xlabel("Number of operations")
plt.ylabel("Time (seconds)")
plt.savefig("examples/Queue_times.png")
print("Queue times Graphed")
