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

// Matt's C Linked List Queue

QUEUE_LIBRARY_API typedef struct node {
    PyObject* object;
    struct node* next;
} node_t;

QUEUE_LIBRARY_API typedef struct queue {
    node_t* front;
    node_t* back;
    unsigned int length;
} queue_t;

node_t* new_node(PyObject* object) {
    node_t* node = (node_t*)malloc(sizeof(node_t));
    if (node == NULL) {
        PyErr_NoMemory();
        return NULL;
    }

    Py_INCREF(object);
    node->object = object;
    node->next = NULL;
    return node;
}

QUEUE_LIBRARY_API queue_t* new_node_queue() {
    queue_t* queue = (queue_t*)malloc(sizeof(queue_t));
    if (queue == NULL) {
        PyErr_NoMemory();
        return NULL;
    }
    queue->front = NULL;
    queue->back = NULL;
    queue->length = 0;
    return queue;
}

QUEUE_LIBRARY_API void enqueue(queue_t* queue, PyObject* object) {
    if (queue == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "Queue is not allocated");
        return;
    }
    if (object == Py_None)
        return;

    node_t* node = new_node(object);
    if (node == NULL)
        return;
    if (queue->back == NULL) {
        queue->front = node;
        queue->back = node;
    } else {
        queue->back->next = node;
        queue->back = node;
    }
    queue->length++;
}

QUEUE_LIBRARY_API PyObject* dequeue(queue_t* queue) {
    if (queue == NULL || queue->length == 0) {
        PyErr_SetString(PyExc_IndexError, "dequeue from an empty queue");
        return NULL;
    }

    node_t* temp = queue->front;
    PyObject* object = temp->object;
    queue->front = temp->next;
    free(temp);
    if (queue->front == NULL)
        queue->back = NULL;
    queue->length--;
    return object;
}

QUEUE_LIBRARY_API void clear_q(queue_t* queue) {
    if (queue == NULL) {
        return;
    }

    node_t* current = queue->front;
    // Detach before decrefs so finalizers can safely reuse this queue.
    queue->front = NULL;
    queue->back = NULL;
    queue->length = 0;
    node_t* next;
    while (current != NULL) {
        next = current->next;
        Py_DECREF(current->object);
        free(current);
        current = next;
    }
}

QUEUE_LIBRARY_API void free_q(queue_t* queue) {
    if (queue == NULL) {
        return;
    }

    clear_q(queue);
    free(queue);
}
