/**
 * Copyright (c) 2023 Matthew Andre Taylor
 */
#include <Python.h>
#include <string.h>

#define CHUNKLEN 384
#define CHUNKEND (CHUNKLEN - 1)

#ifdef Py_TRASHCAN_BEGIN
#define QUEUE_TRASHCAN_BEGIN(op, dealloc) Py_TRASHCAN_BEGIN(op, dealloc)
#define QUEUE_TRASHCAN_END(op) Py_TRASHCAN_END
#else
#define QUEUE_TRASHCAN_BEGIN(op, dealloc) Py_TRASHCAN_SAFE_BEGIN(op)
#define QUEUE_TRASHCAN_END(op) Py_TRASHCAN_SAFE_END(op)
#endif

// Keep rare allocation/error calls from adding stack frames to the hot paths.
#ifdef _MSC_VER
#define QUEUE_NOINLINE __declspec(noinline)
#elif defined(__GNUC__)
#define QUEUE_NOINLINE __attribute__((noinline))
#else
#define QUEUE_NOINLINE
#endif

PyDoc_STRVAR(copy_doc, "Return a shallow copy of the Queue.");
PyDoc_STRVAR(enqueue_doc, "Add an item to the front of the Queue.");
PyDoc_STRVAR(dequeue_doc,
             "Remove and return an item from the end of the Queue.");
PyDoc_STRVAR(extend_doc, "Enqueue a sequence of elements from an iterator.");

/**
 * Single ended Contiguous Python Queue
 * --- fastqueue.QueueC ---
 */
typedef struct {
    PyObject_HEAD size_t front;
    size_t capacity;
    size_t back;
    PyObject** objects;
} QueueC;

static PyObject* QueueC_new(PyTypeObject* type, PyObject* args,
                            PyObject* kwargs) {
    QueueC* self = (QueueC*)type->tp_alloc(type, 0);
    if (self == NULL) {
        return PyErr_NoMemory();
    }

    size_t capacity = CHUNKLEN;
    self->objects = malloc(capacity * sizeof(PyObject*));
    if (self->objects == NULL) {
        Py_DECREF(self);
        return PyErr_NoMemory();
    }

    self->front = 0;
    self->back = 0;
    self->capacity = capacity;
    return (PyObject*)self;
}

static PyObject* QueueC_copy(QueueC* self, PyObject* args) {
    QueueC* copy = (QueueC*)Py_TYPE(self)->tp_alloc(Py_TYPE(self), 0);
    if (copy == NULL) {
        return PyErr_NoMemory();
    }

    size_t capacity = self->capacity;
    copy->objects = malloc(capacity * sizeof(PyObject*));
    if (copy->objects == NULL) {
        Py_DECREF(copy);
        return PyErr_NoMemory();
    }
    for (size_t i = 0; i < (self->front - self->back); ++i) {
        size_t index = (self->back + i) % self->capacity;
        copy->objects[index] = self->objects[index];
        Py_INCREF(copy->objects[index]);
    }
    copy->front = self->front;
    copy->capacity = capacity;
    copy->back = self->back;
    return (PyObject*)copy;
}

static int QueueC_clear(QueueC* self) {
    while (self->back != self->front) {
        PyObject* object = self->objects[self->back % self->capacity];
        self->back++;
        if (self->back >= self->capacity) {
            self->back -= self->capacity;
            self->front -= self->capacity;
        }
        Py_DECREF(object);
    }
    return 0;
}

static void QueueC_dealloc(QueueC* self) {
    PyObject_GC_UnTrack(self);
    QUEUE_TRASHCAN_BEGIN(self, QueueC_dealloc)
    for (size_t i = 0; i < (self->front - self->back); ++i) {
        Py_DECREF(self->objects[(self->back + i) % self->capacity]);
    }
    free(self->objects);
    Py_TYPE(self)->tp_free(self);
    QUEUE_TRASHCAN_END(self)
}

static int QueueC_traverse(QueueC* self, visitproc visit, void* arg) {
    for (size_t i = 0; i < (self->front - self->back); ++i) {
        size_t index = (self->back + i) % self->capacity;
        Py_VISIT(self->objects[index]);
    }
    return 0;
}

static int QueueC_resize(QueueC* self, size_t newCapacity) {
    if (newCapacity > PY_SSIZE_T_MAX / sizeof(PyObject*)) {
        PyErr_NoMemory();
        return -1;
    }
    PyObject** newObjects = realloc(self->objects, newCapacity * sizeof(PyObject*));
    if (newObjects == NULL) {
        PyErr_NoMemory();
        return -1;
    }
    size_t length = self->front - self->back;
    size_t index = self->back % self->capacity;
    size_t tail = self->capacity - index;
    if (length > tail) {
        size_t head = length - tail;
        if (head <= tail && head <= newCapacity - self->capacity) {
            memcpy(newObjects + self->capacity, newObjects, head * sizeof(*newObjects));
        } else {
            size_t moved = newCapacity - tail;
            memmove(newObjects + moved, newObjects + index, tail * sizeof(*newObjects));
            index = moved;
        }
    }
    self->objects = newObjects;
    self->capacity = newCapacity;
    self->back = index;
    self->front = index + length;
    return 0;
}

static QUEUE_NOINLINE PyObject* QueueC_enqueue_grow(QueueC* self, PyObject* object);

static PyObject* QueueC_enqueue(QueueC* self, PyObject* object) {
    if (self->front - self->back >= self->capacity)
        return QueueC_enqueue_grow(self, object);
    size_t front = self->front;
    size_t capacity = self->capacity;
    PyObject** objects = self->objects;
    Py_INCREF(object);
    objects[front % capacity] = object;
    self->front = front + 1;
    Py_RETURN_NONE;
}

static QUEUE_NOINLINE PyObject* QueueC_enqueue_grow(QueueC* self, PyObject* object) {
    if (QueueC_resize(self, self->capacity * 2) < 0) return NULL;
    return QueueC_enqueue(self, object);
}

// Keep error-reporting calls out of the successful dequeue path.
static QUEUE_NOINLINE PyObject* Queue_dequeue_empty(void) {
    PyErr_SetString(PyExc_IndexError, "dequeue from an empty Queue");
    return NULL;
}

static PyObject* QueueC_dequeue(QueueC* self) {
    size_t back = self->back;
    if (back == self->front) return Queue_dequeue_empty();
    PyObject* object = self->objects[back % self->capacity];
    self->back = back + 1;
    if (self->back >= self->capacity) {
        self->back -= self->capacity;
        self->front -= self->capacity;
    }
    return object;
}

static PyObject* QueueC_extend(QueueC* self, PyObject* iterator) {
    if (iterator == (PyObject*)self) {
        PyObject* copy = QueueC_copy(self, NULL);
        if (copy == NULL) return NULL;
        PyObject* result = QueueC_extend(self, copy);
        Py_DECREF(copy);
        return result;
    }

    PyObject* iterable = PyObject_GetIter(iterator);
    if (iterable == NULL) return NULL;
    Py_ssize_t len = PyObject_LengthHint(iterator, 0);
    if (len < 0) {
        Py_DECREF(iterable);
        return NULL;
    }
    size_t capacity = (self->front - self->back) + (size_t)len;
    if (capacity > self->capacity) {
        if (capacity > (size_t)PY_SSIZE_T_MAX / sizeof(PyObject*) - self->capacity) {
            Py_DECREF(iterable);
            return PyErr_NoMemory();
        }
        capacity += self->capacity;
        if (QueueC_resize(self, capacity) < 0) {
            Py_DECREF(iterable);
            return NULL;
        }
    }

    PyObject* (*next)(PyObject*) = Py_TYPE(iterable)->tp_iternext;
    PyObject* object;
    while ((object = next(iterable)) != NULL) {
        if ((self->front - self->back) >= self->capacity &&
            QueueC_resize(self, self->capacity * 2) < 0) {
            Py_DECREF(object);
            Py_DECREF(iterable);
            return NULL;
        }
        size_t front = self->front % self->capacity;
        self->objects[front] = object;
        self->front++;
    }

    if (PyErr_ExceptionMatches(PyExc_StopIteration)) PyErr_Clear();
    Py_DECREF(iterable);
    if (PyErr_Occurred()) return NULL;
    Py_RETURN_NONE;
}

static int QueueC_init(QueueC* self, PyObject* args, PyObject* kwargs) {
    Py_ssize_t arglen = PyTuple_GET_SIZE(args);
    if (arglen == 1) {
        PyObject* iterable = PyTuple_GET_ITEM(args, 0);
        PyObject* res = QueueC_extend(self, iterable);
        if (res == NULL) {
            return -1;
        }
        Py_DECREF(res);
    } else if (arglen > 1) {
        PyErr_Format(PyExc_TypeError,
                     "QueueC() requires at most 1 argument (%d given)", arglen);
        return -1;
    }
    return 0;
}

static Py_ssize_t QueueC_len(QueueC* self) {
    return (Py_ssize_t)(self->front - self->back);
}

static PyObject* QueueC_item(QueueC* self, Py_ssize_t index) {
    // CPython already adds the length to negative indices before calling sq_item.
    if (index < 0 || index >= (Py_ssize_t)(self->front - self->back)) {
        PyErr_SetString(PyExc_IndexError, "Queue index out of range");
        return NULL;
    }
    PyObject* object = self->objects[(self->back + index) % self->capacity];
    Py_INCREF(object);
    return object;
}

static int QueueC_setitem(QueueC* self, Py_ssize_t index, PyObject* object) {
    if (index < 0 || index >= (Py_ssize_t)(self->front - self->back)) {
        PyErr_SetString(PyExc_IndexError, "Queue index out of range");
        return -1;
    }
    if (object == NULL) {
        PyErr_SetString(PyExc_TypeError, "Queue does not support item deletion");
        return -1;
    }

    PyObject* oldObject = self->objects[(self->back + index) % self->capacity];
    Py_INCREF(object);
    self->objects[(self->back + index) % self->capacity] = object;
    Py_DECREF(oldObject);
    return 0;
}

static int QueueC_contains(QueueC* self, PyObject* object) {
    size_t back = self->back;
    size_t front = self->front;
    for (size_t i = 0; i < front - back; ++i) {
        PyObject* item = self->objects[(back + i) % self->capacity];
        if (PyObject_RichCompareBool(object, item, Py_EQ)) return 1;
    }
    return 0;
}

static PySequenceMethods QueueC_sequence_methods = {
    (lenfunc)QueueC_len,             /* sq_length */
    NULL,                            /* sq_concat */
    NULL,                            /* sq_repeat */
    (ssizeargfunc)QueueC_item,       /* sq_item */
    NULL,                            /* sq_slice */
    (ssizeobjargproc)QueueC_setitem, /* sq_as_item */
    NULL,                            /* sq_as_slice */
    (objobjproc)QueueC_contains,     /* sq_contains */
    0                                /* sq_inplace_concat */
};

static PyMethodDef QueueC_methods[] = {
    {"enqueue", (PyCFunction)QueueC_enqueue, METH_O, enqueue_doc},
    {"dequeue", (PyCFunction)QueueC_dequeue, METH_NOARGS, dequeue_doc},
    {"extend", (PyCFunction)QueueC_extend, METH_O, extend_doc},
    {"__copy__", (PyCFunction)QueueC_copy, METH_NOARGS, copy_doc},
    {"copy", (PyCFunction)QueueC_copy, METH_NOARGS, copy_doc},
    {NULL, NULL, 0, NULL}};

PyDoc_STRVAR(queuec_doc, "QueueC() -> Contiguous Single ended Queue object.");
static PyTypeObject QueueCType = {
    PyVarObject_HEAD_INIT(NULL, 0) "QueueC", /* tp_name */
    sizeof(QueueC),                          /* tp_basicsize */
    0,                                       /* tp_itemsize */
    (destructor)QueueC_dealloc,              /* tp_dealloc */
    0,                                       /* tp_print */
    0,                                       /* tp_getattr */
    0,                                       /* tp_setattr */
    0,                                       /* tp_reserved */
    0,                                       /* tp_repr */
    0,                                       /* tp_as_number */
    &QueueC_sequence_methods,                /* tp_as_sequence */
    0,                                       /* tp_as_mapping */
    PyObject_HashNotImplemented,             /* tp_hash */
    0,                                       /* tp_call */
    0,                                       /* tp_str */
    0,                                       /* tp_getattro */
    0,                                       /* tp_setattro */
    0,                                       /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC, /* tp_flags */
    queuec_doc,                              /* tp_doc */
    (traverseproc)QueueC_traverse,           /* tp_traverse */
    (inquiry)QueueC_clear,                   /* tp_clear */
    0,                                       /* tp_richcompare */
    0,                                       /* tp_weaklistoffset */
    0,                                       /* tp_iter */
    0,                                       /* tp_iternext */
    QueueC_methods,                          /* tp_methods */
    0,                                       /* tp_members */
    0,                                       /* tp_getset */
    0,                                       /* tp_base */
    0,                                       /* tp_dict */
    0,                                       /* tp_descr_get */
    0,                                       /* tp_descr_set */
    0,                                       /* tp_dictoffset */
    (initproc)QueueC_init,                   /* tp_init */
    PyType_GenericAlloc,                     /* tp_alloc */
    QueueC_new,                              /* tp_new */
    PyObject_GC_Del,                         /* tp_free */
};

/**
 * Single ended Python Queue with subqueue chunks
 * --- fastqueue.Queue ---
 */
typedef struct QueueNode {
    struct QueueNode* next;
    PyObject* py_objects[CHUNKLEN];
} QueueNode_t;

typedef struct Queue {
    PyObject_HEAD QueueNode_t* head;
    QueueNode_t* tail;
    Py_ssize_t length;
    Py_ssize_t tailEntries; // Number of entries in the tail node.
    Py_ssize_t headEntries; // Number of entries in the head node.
    Py_ssize_t front; // Last occupied index in the tail.
    Py_ssize_t back; // Next occupied index in the head.
    QueueNode_t* free_nodes;
} Queue_t;

static inline QueueNode_t* QueueNode_new(Queue_t* self) {
    QueueNode_t* node = self->free_nodes;
    if (node != NULL) {
        self->free_nodes = node->next;
    } else {
        node = (QueueNode_t*)malloc(sizeof(QueueNode_t));
        if (node == NULL) {
            PyErr_NoMemory();
            return NULL;
        }
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

    self->head = QueueNode_new(self);
    if (self->head == NULL) {
        Py_DECREF(self);
        return NULL;
    }
    self->tail = self->head;
    self->length = 0;
    self->front = CHUNKEND;
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
        QueueNode_t* newNode = QueueNode_new(newQueue);
        if (newNode == NULL) {
            Py_DECREF(newQueue);
            return NULL;
        }

        Py_ssize_t back = current == self->head ? self->back : 0;
        Py_ssize_t entries = current == self->head ? self->headEntries :
                            current == self->tail ? self->tailEntries : CHUNKLEN;
        for (Py_ssize_t i = 0; i < entries; ++i) {
            Py_ssize_t index = (back + i) % CHUNKLEN;
            newNode->py_objects[index] = current->py_objects[index];
            Py_INCREF(current->py_objects[index]);
        }

        if (newQueue->head == NULL) {
            newQueue->head = newNode;
            newQueue->headEntries = entries;
        } else {
            newQueue->tail->next = newNode;
        }
        newQueue->tail = newNode;
        newQueue->tailEntries = entries;
        newQueue->front = (back + entries + CHUNKEND) % CHUNKLEN;
        newQueue->length += entries;
        current = current->next;
    }
    return (PyObject*)newQueue;
}

// Transfer an owned reference into the tail node.
static inline void QueueNode_put(Queue_t* self, PyObject* py_object) {
    Py_ssize_t front = self->front + 1;
    if (front == CHUNKLEN) front = 0;
    self->front = front;
    self->tail->py_objects[front] = py_object;
    self->tailEntries++;
    if (self->head == self->tail) self->headEntries++;
    self->length++;
}

// Add a py_object to the last QueueNode in the Queue
static PyObject* Queue_enqueue(Queue_t* self, PyObject* py_object) {
    if (self->tailEntries == CHUNKLEN) {
        QueueNode_t* node = QueueNode_new(self);
        if (node == NULL) {
            return NULL;
        }
        self->tail->next = node;
        self->tail = node;
        self->tailEntries = 0;
        self->front = CHUNKEND;
    }

    Py_INCREF(py_object);
    QueueNode_put(self, py_object);
    Py_RETURN_NONE;
}

// Remove a py_object from the first QueueNode in the Queue
static PyObject* Queue_dequeue(Queue_t* self) {
    if (self->length == 0) {
        PyErr_SetString(PyExc_IndexError, "dequeue from an empty Queue");
        return NULL;
    }

    QueueNode_t* head = self->head;
    PyObject* py_object = head->py_objects[self->back];
    self->back = (self->back + 1) % CHUNKLEN;
    self->headEntries--;
    self->length--;

    if (head == self->tail) {
        self->tailEntries--;
    } else if (self->headEntries == 0) {
        self->head = head->next;
        self->headEntries = self->head == self->tail ? self->tailEntries : CHUNKLEN;
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
        Py_ssize_t entries = current == self->head ? self->headEntries :
                            current == self->tail ? self->tailEntries : CHUNKLEN;
        for (Py_ssize_t i = 0; i < entries; ++i) {
            Py_ssize_t index = (back + i) % CHUNKLEN;
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
        if (self->tailEntries == CHUNKLEN) {
            QueueNode_t* tail = QueueNode_new(self);
            if (tail == NULL) {
                Py_DECREF(object);
                Py_DECREF(iterable);
                return NULL;
            }
            self->tail->next = tail;
            self->tail = tail;
            self->tailEntries = 0;
            self->front = CHUNKEND;
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

static PyObject* Queue_item(Queue_t* self, Py_ssize_t index) {
    // CPython already adds the length to negative indices before calling sq_item.
    if (index < 0 || index >= self->length) {
        PyErr_SetString(PyExc_IndexError, "Queue index out of range");
        return NULL;
    }

    QueueNode_t* current = self->head;
    Py_ssize_t entries = self->headEntries;
    Py_ssize_t back = self->back;
    // Only the head can be partially consumed; subsequent skipped chunks are full.
    if (index >= entries) {
        index -= entries;
        current = current->next;
        back = 0;
        for (Py_ssize_t i = 0; i < index / CHUNKLEN; ++i) {
            current = current->next;
        }
    }
    index %= CHUNKLEN;
    PyObject* object = current->py_objects[(back + index) % CHUNKLEN];
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

    QueueNode_t* current = self->head;
    Py_ssize_t entries = self->headEntries;
    Py_ssize_t back = self->back;
    if (index >= entries) {
        index -= entries;
        current = current->next;
        back = 0;
        for (Py_ssize_t i = 0; i < index / CHUNKLEN; ++i) {
            current = current->next;
        }
    }
    index = (back + index % CHUNKLEN) % CHUNKLEN;
    PyObject* oldObject = current->py_objects[index];
    Py_INCREF(object);
    current->py_objects[index] = object;
    Py_DECREF(oldObject);
    return 0;
}

static int Queue_contains(Queue_t* self, PyObject* object) {
    QueueNode_t* current = self->head;
    while (current != NULL) {
        Py_ssize_t back = current == self->head ? self->back : 0;
        Py_ssize_t entries = current == self->head ? self->headEntries :
                            current == self->tail ? self->tailEntries : CHUNKLEN;
        for (Py_ssize_t i = 0; i < entries; ++i) {
            PyObject* item =
                current->py_objects[(back + i) % CHUNKLEN];
            int result = PyObject_RichCompareBool(item, object, Py_EQ);
            if (result < 0) {
                return -1;
            }
            if (result) {
                return 1;
            }
        }
        current = current->next;
    }
    return 0;
}

static PySequenceMethods Queue_sequence_methods = {
    (lenfunc)Queue_len,             /* sq_length */
    0,                              /* sq_concat */
    NULL,                           /* sq_repeat */
    (ssizeargfunc)Queue_item,       /* sq_item */
    NULL,                           /* sq_slice */
    (ssizeobjargproc)Queue_setitem, /* sq_as_item */
    NULL,                           /* sq_as_slice */
    (objobjproc)Queue_contains,     /* sq_contains */
    0                               /* sq_inplace_concat */
};

static PyMethodDef Queue_methods[] = {
    {"enqueue", (PyCFunction)Queue_enqueue, METH_O, enqueue_doc},
    {"dequeue", (PyCFunction)Queue_dequeue, METH_NOARGS, dequeue_doc},
    {"extend", (PyCFunction)Queue_extend, METH_O, extend_doc},
    {"__copy__", (PyCFunction)Queue_copy, METH_NOARGS, copy_doc},
    {"copy", (PyCFunction)Queue_copy, METH_NOARGS, copy_doc},
    {NULL, NULL, 0, NULL}};

PyDoc_STRVAR(queue_doc, "Queue() -> Single ended Queue object.");
static PyTypeObject QueueType = {
    PyVarObject_HEAD_INIT(NULL, 0) "Queue",  /* tp_name */
    sizeof(Queue_t),                         /* tp_basicsize */
    0,                                       /* tp_itemsize */
    (destructor)Queue_dealloc,               /* tp_dealloc */
    0,                                       /* tp_print */
    0,                                       /* tp_getattr */
    0,                                       /* tp_setattr */
    0,                                       /* tp_reserved */
    0,                                       /* tp_repr */
    0,                                       /* tp_as_number */
    &Queue_sequence_methods,                 /* tp_as_sequence */
    0,                                       /* tp_as_mapping */
    PyObject_HashNotImplemented,             /* tp_hash */
    0,                                       /* tp_call */
    0,                                       /* tp_str */
    0,                                       /* tp_getattro */
    0,                                       /* tp_setattro */
    0,                                       /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC, /* tp_flags */
    queue_doc,                               /* tp_doc */
    (traverseproc)Queue_traverse,            /* tp_traverse */
    (inquiry)Queue_clear,                    /* tp_clear */
    0,                                       /* tp_richcompare */
    0,                                       /* tp_weaklistoffset */
    0,                                       /* tp_iter */
    0,                                       /* tp_iternext */
    Queue_methods,                           /* tp_methods */
    0,                                       /* tp_members */
    0,                                       /* tp_getset */
    0,                                       /* tp_base */
    0,                                       /* tp_dict */
    0,                                       /* tp_descr_get */
    0,                                       /* tp_descr_set */
    0,                                       /* tp_dictoffset */
    (initproc)Queue_init,                    /* tp_init */
    PyType_GenericAlloc,                     /* tp_alloc */
    (newfunc)Queue_new,                      /* tp_new */
    PyObject_GC_Del,                         /* tp_free */
};

PyDoc_STRVAR(fastqueue_doc,
             "Single ended fast queue's built in C tuned for Python.");
static PyModuleDef QueueModuleDef = {PyModuleDef_HEAD_INIT,
                                     "_fastqueue",
                                     fastqueue_doc,
                                     -1,
                                     NULL,
                                     NULL,
                                     NULL,
                                     NULL,
                                     NULL};

PyMODINIT_FUNC PyInit__fastqueue(void) {
    PyObject* module;
    if (PyType_Ready(&QueueType) < 0 || PyType_Ready(&QueueCType) < 0) {
        return NULL;
    }

    module = PyModule_Create(&QueueModuleDef);
    if (module == NULL) {
        return NULL;
    }
    PyModule_AddObject(module, "QueueC", (PyObject*)&QueueCType);
    PyModule_AddObject(module, "Queue", (PyObject*)&QueueType);
    return module;
}
