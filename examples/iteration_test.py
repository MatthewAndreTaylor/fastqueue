from fastqueue import *
import numpy
import time

size = 20000000

start = time.time()
q = QueueC()
q.extend([i for i in range(size)])
QUE = time.time() - start


start = time.time()
arr = numpy.array([i for i in range(size)])
ARR = time.time() - start

print("Instantiation:")
print("Array: ", ARR, "Queue: ", QUE)

start = time.time()
for i in range(len(q)):
    q[i] += 1
QUE = time.time() - start

start = time.time()
for i in range(len(arr)):
    arr[i] += 1
ARR = time.time() - start

print("Iteration:")
print("Array: ", ARR, "Queue: ", QUE)

