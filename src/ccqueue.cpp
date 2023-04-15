/**
 * Copyright (c) 2023 Matthew Andre Taylor
 */
#ifdef _WIN32
#define QUEUE_LIBRARY_API extern "C" __declspec(dllexport)
#else
#define QUEUE_LIBRARY_API extern "C"
#endif

#include <Python.h>
#include <stdlib.h>
#include <stdio.h>

// Matt's C Contiguous Queue
QUEUE_LIBRARY_API typedef struct queue {
    PyObject** objects;
    int length;
    int capacity;
    int front;
    int back;
} queue_t;

QUEUE_LIBRARY_API int is_empty(queue_t* queue) {
    if (queue == NULL) {
        perror("Queue not allocated");
        return 1;
    }
    return queue->length == 0;
}

QUEUE_LIBRARY_API queue_t* new__queue() {
    queue_t* queue = (queue_t*) malloc(sizeof(queue_t));
    queue->length = 0;
    queue->capacity = 256;
    queue->front = 0;
    queue->back = queue->capacity -1;
    queue->objects = (PyObject**) malloc(256 * sizeof(PyObject*));
    return queue;
}

void resize(queue_t* queue, int newCapacity) {
    PyObject** newObjects = (PyObject**) malloc(newCapacity * sizeof(PyObject*));
    for (int i = 0; i < queue->length; ++i) {
        newObjects[i] = queue->objects[(queue->front + i) % queue->capacity];
    }

    free(queue->objects);
    queue->objects = newObjects;
    queue->front = 0;
    queue->back = queue->length - 1;
    queue->capacity = newCapacity;
}

QUEUE_LIBRARY_API void enqueue(queue_t* queue, PyObject* object) {
    if (object == Py_None)
        return;

    if (queue->length == queue->capacity)
        resize(queue, queue->capacity * 2);

    Py_INCREF(object);
    queue->front = (queue->front + queue->capacity - 1) % queue->capacity;
    queue->objects[queue->front] = object;
    queue->length++;
}

QUEUE_LIBRARY_API PyObject* dequeue(queue_t* queue) {
    if (is_empty(queue))
        return NULL;

    PyObject* object = queue->objects[queue->back];
    queue->back = (queue->back + queue->capacity - 1) % queue->capacity;
    queue->length--;
    return object;
}

QUEUE_LIBRARY_API void free_q(queue_t* queue) {
    if (queue == NULL) {
        perror("Queue not allocated");
        return;
    }

    for (int i = 0; i < queue->length; i++) {
        int index = (queue->front + i) % queue->capacity;
        Py_DECREF(queue->objects[index]);
    }
    free(queue->objects);
    free(queue);
}
