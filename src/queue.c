/**
 * Copyright (c) 2023 Matthew Andre Taylor
 */
/**
 * Single ended Python Queue with subqueue chunks
 * --- fastqueue.Queue ---
 */

#define QUEUE_NODE_INITIAL_CAPACITY 254
// Header + pointer storage is 2048 bytes -> 4096 bytes -> ...

typedef struct QueueNode {
    struct QueueNode* next;
    Py_ssize_t capacity;
    PyObject* py_objects[];
} QueueNode_t;


// #define QUEUE_NODE_MAX_CAPACITY \
//     (((size_t)PY_SSIZE_T_MAX - sizeof(QueueNode_t)) / sizeof(PyObject*))

typedef struct Queue {
    PyObject_HEAD QueueNode_t* head;
    QueueNode_t* tail;
    Py_ssize_t length;
    Py_ssize_t front; // Next free index in the tail, including its capacity.
    Py_ssize_t back; // Next occupied index in the head.
    QueueNode_t* free_nodes;
    size_t state;
} Queue_t;

static inline QueueNode_t* QueueNode_new(Queue_t* self, size_t capacity) {
    QueueNode_t* node = self->free_nodes;
    if (node != NULL) {
        // Reuse any cached capacity without searching or resizing.
        self->free_nodes = node->next;
    } else {
        node = (QueueNode_t*)malloc(sizeof(QueueNode_t) + capacity * sizeof(PyObject*));
        if (node == NULL) {
            PyErr_NoMemory();
            return NULL;
        }
        node->capacity = capacity;
    }
    node->next = NULL;
    return node;
}

static inline void QueueNode_recycle(Queue_t* self, QueueNode_t* node) {
    node->next = self->free_nodes;
    self->free_nodes = node;
}

static PyObject* Queue_new(PyTypeObject* type, PyObject* args,
                           PyObject* kwargs) {
    Queue_t* self = (Queue_t*)type->tp_alloc(type, 0);
    if (self == NULL) {
        return PyErr_NoMemory();
    }

    self->head = QueueNode_new(self, QUEUE_NODE_INITIAL_CAPACITY);
    if (self->head == NULL) {
        Py_DECREF(self);
        return NULL;
    }
    self->tail = self->head;
    self->length = 0;
    self->front = 0;
    return (PyObject*)self;
}

static PyObject* Queue_copy(Queue_t* self, PyObject* args) {
    Queue_t* newQueue = (Queue_t*)Py_TYPE(self)->tp_alloc(Py_TYPE(self), 0);
    if (newQueue == NULL) {
        return PyErr_NoMemory();
    }

    newQueue->head = NULL;
    newQueue->tail = NULL;
    newQueue->length = 0;
    newQueue->back = self->back;

    QueueNode_t* current = self->head;
    while (current != NULL) {
        QueueNode_t* newNode = QueueNode_new(newQueue, current->capacity);
        if (newNode == NULL) {
            Py_DECREF(newQueue);
            return NULL;
        }

        Py_ssize_t back = current == self->head ? self->back : 0;
        Py_ssize_t end = current == self->tail ? self->front : current->capacity;
        for (Py_ssize_t index = back; index < end; ++index) {
            newNode->py_objects[index] = current->py_objects[index];
            Py_INCREF(current->py_objects[index]);
        }

        if (newQueue->head == NULL) {
            newQueue->head = newNode;
        } else {
            newQueue->tail->next = newNode;
        }
        newQueue->tail = newNode;
        newQueue->front = end;
        newQueue->length += end - back;
        current = current->next;
    }
    return (PyObject*)newQueue;
}

// Transfer an owned reference into the tail node.
static inline void QueueNode_put(Queue_t* self, PyObject* py_object) {
    Py_ssize_t front = self->front;
    self->tail->py_objects[front] = py_object;
    self->front = front + 1;
    self->length++;
    self->state++;
}

static QUEUE_NOINLINE QueueNode_t* Queue_enqueue_grow(Queue_t* self) {
    size_t capacity = self->tail->capacity * 2;

    // Allocation would fail vastly earlier than this
    // capacity = capacity > QUEUE_NODE_MAX_CAPACITY / 2
    //     ? QUEUE_NODE_MAX_CAPACITY : capacity * 2;
    QueueNode_t* node = QueueNode_new(self, capacity);
    if (node == NULL) return NULL;
    self->tail->next = node;
    self->tail = node;
    self->front = 0;
    return node;
}


static QUEUE_NOINLINE PyObject* Queue_enqueue_slow(Queue_t* self, PyObject* object) {
    if (Queue_enqueue_grow(self) == NULL)
        return NULL;

    Py_INCREF(object);
    QueueNode_put(self, object);
    Py_RETURN_NONE;
}

static PyObject* Queue_enqueue(Queue_t* self, PyObject* object) {
    if (self->front == self->tail->capacity)
        return Queue_enqueue_slow(self, object);

    Py_INCREF(object);
    QueueNode_put(self, object);
    Py_RETURN_NONE;
}

// Remove a py_object from the first QueueNode in the Queue
static PyObject* Queue_dequeue(Queue_t* self) {
    if (self->length == 0) return Queue_dequeue_empty();

    QueueNode_t* head = self->head;
    PyObject* py_object = head->py_objects[self->back];
    self->back++;
    self->length--;
    self->state++;

    if (self->length == 0) {
        self->front = self->back = 0;
    } else if (self->back == head->capacity) {
        self->head = head->next;
        self->back = 0;
        QueueNode_recycle(self, head);
    }

    return py_object;
}

static int Queue_clear(Queue_t* self) {
    while (self->length > 0) {
        PyObject* object = Queue_dequeue(self);
        Py_DECREF(object);
    }
    return 0;
}

static PyObject* Queue_clear_method(Queue_t* self, PyObject* args) {
    Queue_clear(self);
    Py_RETURN_NONE;
}

// Deallocate the Queue
static void Queue_dealloc(Queue_t* self) {
    if (self == NULL) {
        return;
    }
    PyObject_GC_UnTrack(self);
    QUEUE_TRASHCAN_BEGIN(self, Queue_dealloc)
    Queue_clear(self);
    free(self->head);
    QueueNode_t* node = self->free_nodes;
    while (node != NULL) {
        QueueNode_t* next = node->next;
        free(node);
        node = next;
    }
    Py_TYPE(self)->tp_free((PyObject*)self);
    QUEUE_TRASHCAN_END(self)
}

static int Queue_traverse(Queue_t* self, visitproc visit, void* arg) {
    QueueNode_t* current = self->head;
    while (current != NULL) {
        Py_ssize_t back = current == self->head ? self->back : 0;
        Py_ssize_t end = current == self->tail ? self->front : current->capacity;
        for (Py_ssize_t index = back; index < end; ++index) {
            Py_VISIT(current->py_objects[index]);
        }
        current = current->next;
    }
    return 0;
}

static PyObject* Queue_extend(Queue_t* self, PyObject* iterator) {
    if (iterator == (PyObject*)self) {
        PyObject* copy = Queue_copy(self, NULL);
        if (copy == NULL) return NULL;
        PyObject* result = Queue_extend(self, copy);
        Py_DECREF(copy);
        return result;
    }

    PyObject* iterable = PyObject_GetIter(iterator);
    if (iterable == NULL) return NULL;
    PyObject* (*next)(PyObject*) = Py_TYPE(iterable)->tp_iternext;

    PyObject* object;
    while ((object = next(iterable)) != NULL) {
        if (self->front == self->tail->capacity && Queue_enqueue_grow(self) == NULL) {
            Py_DECREF(object);
            Py_DECREF(iterable);
            return NULL;
        }
        QueueNode_put(self, object);
    }

    if (PyErr_ExceptionMatches(PyExc_StopIteration)) PyErr_Clear();
    Py_DECREF(iterable);
    if (PyErr_Occurred()) return NULL;
    Py_RETURN_NONE;
}

static int Queue_init(Queue_t* self, PyObject* args, PyObject* kwargs) {
    Py_ssize_t arglen = PyTuple_GET_SIZE(args);
    if (arglen == 1) {
        PyObject* iterable = PyTuple_GET_ITEM(args, 0);
        PyObject* res = Queue_extend(self, iterable);
        if (res == NULL) {
            return -1;
        }
        Py_DECREF(res);
    } else if (arglen > 1) {
        PyErr_Format(PyExc_TypeError,
                     "Queue() requires at most 1 argument (%d given)", arglen);
        return -1;
    }

    return 0;
}

static Py_ssize_t Queue_len(Queue_t* self) { return self->length; }

// Callers validate the logical index before walking variable-sized nodes.
static inline QueueNode_t* Queue_locate(Queue_t* self, Py_ssize_t index, size_t* position) {
    QueueNode_t* current = self->head;
    *position = (size_t)self->back + (size_t)index;
    while (*position >= current->capacity) {
        *position -= current->capacity;
        current = current->next;
    }
    return current;
}

static PyObject* Queue_item(Queue_t* self, Py_ssize_t index) {
    // CPython already adds the length to negative indices before calling sq_item.
    if (index < 0 || index >= self->length) {
        PyErr_SetString(PyExc_IndexError, "Queue index out of range");
        return NULL;
    }

    size_t position;
    QueueNode_t* current = Queue_locate(self, index, &position);
    PyObject* object = current->py_objects[position];
    Py_INCREF(object);
    return object;
}

static int Queue_setitem(Queue_t* self, Py_ssize_t index, PyObject* object) {
    if (index < 0 || index >= self->length) {
        PyErr_SetString(PyExc_IndexError, "Queue index out of range");
        return -1;
    }
    if (object == NULL) {
        PyErr_SetString(PyExc_TypeError, "Queue does not support item deletion");
        return -1;
    }

    size_t position;
    QueueNode_t* current = Queue_locate(self, index, &position);
    PyObject* oldObject = current->py_objects[position];
    Py_INCREF(object);
    current->py_objects[position] = object;
    Py_DECREF(oldObject);
    return 0;
}

static int Queue_contains(Queue_t* self, PyObject* object) {
    for (Py_ssize_t index = 0; index < self->length; ++index) {
        // Comparisons/finalizers may recycle nodes; reacquire each owned item.
        PyObject* item = Queue_item(self, index);
        if (item == NULL) return -1;
        int result = PyObject_RichCompareBool(item, object, Py_EQ);
        Py_DECREF(item);
        if (result != 0) return result;
    }
    return 0;
}

typedef struct {
    PyObject_HEAD
    QueueNode_t* node;
    Py_ssize_t index;
    Queue_t* queue;
    size_t state;
    Py_ssize_t remaining;
} QueueIter;

static int QueueIter_traverse(QueueIter* self, visitproc visit, void* arg) {
    Py_VISIT(self->queue);
    return 0;
}

static int QueueIter_clear(QueueIter* self) {
    self->remaining = 0;
    self->node = NULL;
    Py_CLEAR(self->queue);
    return 0;
}

static void QueueIter_dealloc(QueueIter* self) {
    PyObject_GC_UnTrack(self);
    QueueIter_clear(self);
    PyObject_GC_Del(self);
}

static PyObject* QueueIter_next(QueueIter* self) {
    if (self->remaining == 0) {
        QueueIter_clear(self);
        return NULL;
    }
    // Check before dereferencing a node that a mutation may have recycled.
    if (self->state != self->queue->state) {
        QueueIter_clear(self);
        PyErr_SetString(PyExc_RuntimeError, "Queue mutated during iteration");
        return NULL;
    }

    PyObject* object = self->node->py_objects[self->index++];
    self->remaining--;
    if (self->index == self->node->capacity && self->remaining > 0) {
        self->node = self->node->next;
        self->index = 0;
    }
    Py_INCREF(object);
    return object;
}

static PyObject* QueueIter_length_hint(QueueIter* self, PyObject* args) {
    return PyLong_FromSsize_t(self->remaining);
}

static PyMethodDef QueueIter_methods[] = {
    {"__length_hint__", (PyCFunction)QueueIter_length_hint, METH_NOARGS,
     "Return the number of items remaining."},
    {NULL, NULL, 0, NULL}
};

static PyTypeObject QueueIterType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "_fastqueue.QueueIterator",
    .tp_basicsize = sizeof(QueueIter),
    .tp_dealloc = (destructor)QueueIter_dealloc,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
    .tp_traverse = (traverseproc)QueueIter_traverse,
    .tp_clear = (inquiry)QueueIter_clear,
    .tp_iter = PyObject_SelfIter,
    .tp_iternext = (iternextfunc)QueueIter_next,
    .tp_methods = QueueIter_methods,
};

static PyObject* Queue_iter(Queue_t* self) {
    QueueIter* iterator = PyObject_GC_New(QueueIter, &QueueIterType);
    if (iterator == NULL) return NULL;
    iterator->node = self->head;
    iterator->index = self->back;
    Py_INCREF(self);
    iterator->queue = self;
    iterator->state = self->state;
    iterator->remaining = self->length;
    PyObject_GC_Track(iterator);
    return (PyObject*)iterator;
}
