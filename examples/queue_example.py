import queue
import sys
import time
import matplotlib.pyplot as plt
from mqueue.prototype_mqueue import *
from mqueue.mqueue import *

queue_size = 1000000
queue_structures = {
    "Python queue": (queue.Queue(), queue.Queue.put, queue.Queue.get),
    "Python Simple queue": (queue.SimpleQueue(), queue.SimpleQueue.put, queue.SimpleQueue.get),
    "Matt's Linked List queue": (LLQueue(), LLQueue.enqueue, LLQueue.dequeue),
    "Matt's Contiguous queue": (ContQueue(), ContQueue.enqueue, ContQueue.dequeue),
    "Matt's C queue": (Queue(), Queue.enqueue, Queue.dequeue),
    "Matt's C Contiguous queue": (QueueC(), QueueC.enqueue, QueueC.dequeue),
}
queue_types = queue_structures.keys()
queue_times = []

for q in queue_types:
    enqueue = queue_structures[q][1]
    dequeue = queue_structures[q][2]
    start = time.time()
    for j in range(queue_size):
        enqueue(queue_structures[q][0], j)
    assert([dequeue(queue_structures[q][0]) for _ in range(queue_size)] == list(range(queue_size)))
    queue_times.append(time.time()-start)

queue_types, queue_times = zip(*sorted(zip(queue_types, queue_times), key = lambda x: x[1], reverse=True))
fig = plt.figure(figsize = (15, 7))
plt.bar(queue_types, queue_times, color=['y', 'r', 'g', 'c', 'm', 'b'], width = 0.5)
for i, v in enumerate(queue_times):
    plt.text(i, v, str(round(v, 5)), ha='center', family='sans-serif')
plt.xlabel("Queue Type")
plt.ylabel("Time")
plt.title(f"Queue Analysis : {sys.platform}")
plt.savefig("examples/Queue_types.png")
print("Queue times Graphed")
