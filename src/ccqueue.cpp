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

// Matt's C Contiguous Queue
QUEUE_LIBRARY_API typedef struct queue {
    PyObject** objects;
    size_t length;
    size_t capacity;
    size_t front;
    size_t back;
} queue_t;

QUEUE_LIBRARY_API queue_t* new__queue() {
    queue_t* queue = (queue_t*)malloc(sizeof(queue_t));
    if (queue == NULL) {
        PyErr_NoMemory();
        return NULL;
    }
    queue->length = 0;
    queue->capacity = 256;
    queue->front = 0;
    queue->back = queue->capacity - 1;
    queue->objects = (PyObject**)malloc(256 * sizeof(PyObject*));
    if (queue->objects == NULL) {
        free(queue);
        PyErr_NoMemory();
        return NULL;
    }
    return queue;
}

int resize(queue_t* queue, size_t newCapacity) {
    if (newCapacity > PY_SSIZE_T_MAX / sizeof(PyObject*)) {
        PyErr_NoMemory();
        return -1;
    }
    PyObject** newObjects = (PyObject**)malloc(newCapacity * sizeof(PyObject*));
    if (newObjects == NULL) {
        PyErr_NoMemory();
        return -1;
    }
    for (size_t i = 0; i < queue->length; ++i) {
        newObjects[i] = queue->objects[(queue->front + i) % queue->capacity];
    }

    free(queue->objects);
    queue->objects = newObjects;
    queue->front = 0;
    queue->back = (queue->length + newCapacity - 1) % newCapacity;
    queue->capacity = newCapacity;
    return 0;
}

QUEUE_LIBRARY_API void enqueue(queue_t* queue, PyObject* object) {
    if (queue == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "Queue is not allocated");
        return;
    }
    if (object == Py_None)
        return;

    if (queue->length == queue->capacity) {
        if (queue->capacity > PY_SSIZE_T_MAX / sizeof(PyObject*) / 2) {
            PyErr_NoMemory();
            return;
        }
        if (resize(queue, queue->capacity ? queue->capacity * 2 : 256) < 0)
            return;
    }

    Py_INCREF(object);
    queue->front = (queue->front + queue->capacity - 1) % queue->capacity;
    queue->objects[queue->front] = object;
    queue->length++;
}

QUEUE_LIBRARY_API PyObject* dequeue(queue_t* queue) {
    if (queue == NULL || queue->length == 0) {
        PyErr_SetString(PyExc_IndexError, "dequeue from an empty queue");
        return NULL;
    }

    PyObject* object = queue->objects[queue->back];
    queue->back = (queue->back + queue->capacity - 1) % queue->capacity;
    queue->length--;
    return object;
}

QUEUE_LIBRARY_API void clear_q(queue_t* queue) {
    if (queue == NULL || queue->length == 0) {
        return;
    }

    PyObject** objects = queue->objects;
    size_t length = queue->length;
    size_t capacity = queue->capacity;
    size_t front = queue->front;
    // Detach before decrefs so callbacks cannot overwrite the old payloads.
    queue->objects = NULL;
    queue->length = queue->capacity = queue->front = queue->back = 0;
    for (size_t i = 0; i < length; ++i) {
        Py_DECREF(objects[(front + i) % capacity]);
    }
    if (queue->objects == NULL) {
        queue->objects = objects;
        queue->capacity = capacity;
        queue->front = 0;
        queue->back = capacity - 1;
    } else {
        free(objects);
    }
}

QUEUE_LIBRARY_API void free_q(queue_t* queue) {
    if (queue == NULL) {
        return;
    }

    clear_q(queue);
    free(queue->objects);
    free(queue);
}
