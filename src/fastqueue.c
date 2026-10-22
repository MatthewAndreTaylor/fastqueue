/**
 * Copyright (c) 2023 Matthew Andre Taylor
 */
#include <Python.h>
#include <string.h>

#define CHUNKLEN 256
#define CHUNKEND (CHUNKLEN - 1)
#define CONTIGUOUS_BASE_LENGTH 1024

#ifdef Py_TRASHCAN_BEGIN
#define QUEUE_TRASHCAN_BEGIN(op, dealloc) Py_TRASHCAN_BEGIN(op, dealloc)
#define QUEUE_TRASHCAN_END(op) Py_TRASHCAN_END
#else
#define QUEUE_TRASHCAN_BEGIN(op, dealloc) Py_TRASHCAN_SAFE_BEGIN(op)
#define QUEUE_TRASHCAN_END(op) Py_TRASHCAN_SAFE_END(op)
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
    PyObject_HEAD size_t length;
    size_t capacity;
    size_t front;
    size_t back;
    PyObject** objects;
} QueueC;

static PyObject* QueueC_new(PyTypeObject* type, PyObject* args,
                            PyObject* kwargs) {
    QueueC* self = (QueueC*)type->tp_alloc(type, 0);
    if (self == NULL) {
        return PyErr_NoMemory();
    }

    self->objects = (PyObject**)malloc(CONTIGUOUS_BASE_LENGTH * sizeof(PyObject*));
    if (self->objects == NULL) {
        Py_DECREF(self);
        return PyErr_NoMemory();
    }

    self->length = 0;
    self->back = 0;
    self->capacity = CONTIGUOUS_BASE_LENGTH;
    self->front = self->capacity - 1;
    return (PyObject*)self;
}

static PyObject* QueueC_copy(QueueC* self, PyObject* args) {
    QueueC* copy = (QueueC*)Py_TYPE(self)->tp_alloc(Py_TYPE(self), 0);
    if (copy == NULL) {
        return PyErr_NoMemory();
    }

    size_t capacity = self->capacity;
    copy->objects = (PyObject**)malloc(capacity * sizeof(PyObject*));
    if (copy->objects == NULL) {
        Py_DECREF(copy);
        return PyErr_NoMemory();
    }
    for (size_t i = 0; i < self->length; ++i) {
        size_t index = (self->back + i) % self->capacity;
        copy->objects[index] = self->objects[index];
        Py_INCREF(copy->objects[index]);
    }
    copy->length = self->length;
    copy->capacity = capacity;
    copy->front = self->front;
    copy->back = self->back;
    return (PyObject*)copy;
}

static int QueueC_clear(QueueC* self) {
    while (self->length > 0) {
        PyObject* object = self->objects[self->back];
        self->back = (self->back + 1) % self->capacity;
        self->length--;
        // Remove the item before its finalizer can modify the queue.
        Py_DECREF(object);
    }
    self->front = self->capacity - 1;
    self->back = 0;
    return 0;
}

static void QueueC_dealloc(QueueC* self) {
    PyObject_GC_UnTrack(self);
    QUEUE_TRASHCAN_BEGIN(self, QueueC_dealloc)
    for (size_t i = 0; i < self->length; ++i) {
        Py_DECREF(self->objects[(self->back + i) % self->capacity]);
    }
    free(self->objects);
    Py_TYPE(self)->tp_free(self);
    QUEUE_TRASHCAN_END(self)
}

static int QueueC_traverse(QueueC* self, visitproc visit, void* arg) {
    for (size_t i = 0; i < self->length; ++i) {
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
    PyObject** newObjects =
        realloc(self->objects, newCapacity * sizeof(*newObjects));
    if (newObjects == NULL) {
        PyErr_NoMemory();
        return -1;
    }
    size_t tail = self->capacity - self->back;
    if (self->length > tail) {
        size_t head = self->length - tail;
        // Leave the larger segment in place when the added space permits.
        if (head <= tail && head <= newCapacity - self->capacity) {
            memcpy(newObjects + self->capacity, newObjects,
                   head * sizeof(*newObjects));
        } else {
            size_t back = newCapacity - tail;
            memmove(newObjects + back, newObjects + self->back,
                    tail * sizeof(*newObjects));
            self->back = back;
        }
    }
    self->front = (self->back + self->length + newCapacity - 1) % newCapacity;
    self->objects = newObjects;
    self->capacity = newCapacity;
    return 0;
}

static PyObject* QueueC_enqueue(QueueC* self, PyObject* object) {
    if (self->length == self->capacity) {
        if (QueueC_resize(self, self->capacity * 2) < 0) {
            return NULL;
        }
    }

    Py_INCREF(object);
    self->front = (self->front + 1) % self->capacity;
    self->objects[self->front] = object;
    self->length++;
    Py_RETURN_NONE;
}

static PyObject* QueueC_dequeue(QueueC* self) {
    if (self->length == 0) {
        PyErr_SetString(PyExc_IndexError, "dequeue from an empty Queue");
        return NULL;
    }

    PyObject* object = self->objects[self->back];
    self->back = (self->back + 1) % self->capacity;
    self->length--;
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
    size_t capacity = self->length + (size_t)len;
    if (capacity > self->capacity &&
        QueueC_resize(self, capacity + self->capacity) < 0) {
        Py_DECREF(iterable);
        return NULL;
    }

    PyObject* (*next)(PyObject*) = Py_TYPE(iterable)->tp_iternext;
    PyObject* object;
    while ((object = next(iterable)) != NULL) {
        if (self->length == self->capacity &&
            QueueC_resize(self, self->capacity * 2) < 0) {
            Py_DECREF(object);
            Py_DECREF(iterable);
            return NULL;
        }
        // back + length is below twice capacity, so one subtraction wraps.
        size_t front = self->back + self->length;
        if (front >= self->capacity) front -= self->capacity;
        self->objects[front] = object;
        self->front = front;
        self->length++;
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

static Py_ssize_t QueueC_len(QueueC* self) { return (Py_ssize_t)self->length; }

static PyObject* QueueC_item(QueueC* self, Py_ssize_t index) {
    // CPython already adds the length to negative indices before calling sq_item.
    if (index < 0 || index >= (Py_ssize_t)self->length) {
        PyErr_SetString(PyExc_IndexError, "Queue index out of range");
        return NULL;
    }
    PyObject* object = self->objects[(self->back + index) % self->capacity];
    Py_INCREF(object);
    return object;
}

static int QueueC_setitem(QueueC* self, Py_ssize_t index, PyObject* object) {
    if (index < 0 || index >= (Py_ssize_t)self->length) {
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
    for (size_t i = 0; i < self->length; ++i) {
        size_t index = (self->back + i) % self->capacity;
        if (PyObject_RichCompareBool(object, self->objects[index], Py_EQ)) {
            return 1;
        }
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
    Py_ssize_t numEntries; // Number of entries into the current node
    Py_ssize_t front;
    Py_ssize_t back;
    struct QueueNode* next;
    PyObject* py_objects[CHUNKLEN];
} QueueNode_t;

typedef struct Queue {
    PyObject_HEAD QueueNode_t* head;
    QueueNode_t* tail;
    Py_ssize_t length;
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
    node->numEntries = 0;
    node->front = CHUNKEND;
    node->back = 0;
    node->next = NULL;
    return node;
}

static inline void QueueNode_recycle(Queue_t* self, QueueNode_t* node) {
    node->numEntries = 0;
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

    QueueNode_t* current = self->head;
    while (current != NULL) {
        QueueNode_t* newNode = QueueNode_new(newQueue);
        if (newNode == NULL) {
            Py_DECREF(newQueue);
            return NULL;
        }

        for (Py_ssize_t i = 0; i < current->numEntries; ++i) {
            Py_ssize_t index = (current->back + i) & CHUNKEND;
            newNode->py_objects[index] = current->py_objects[index];
            Py_INCREF(current->py_objects[index]);
        }

        newNode->numEntries = current->numEntries;
        newNode->front = current->front;
        newNode->back = current->back;

        if (newQueue->head == NULL) {
            newQueue->head = newNode;
        } else {
            newQueue->tail->next = newNode;
        }
        newQueue->tail = newNode;
        newQueue->length += newNode->numEntries;
        current = current->next;
    }
    return (PyObject*)newQueue;
}

// Add a py_object to the front of the QueueNode
static inline void QueueNode_put(QueueNode_t* queue_node, PyObject* py_object) {
    queue_node->front = (queue_node->front + 1) & CHUNKEND;
    queue_node->py_objects[queue_node->front] = py_object;
    queue_node->numEntries++;
}

// Add a py_object to the last QueueNode in the Queue
static PyObject* Queue_enqueue(Queue_t* self, PyObject* py_object) {
    if (self->tail->numEntries == CHUNKLEN) {
        QueueNode_t* node = QueueNode_new(self);
        if (node == NULL) {
            return NULL;
        }
        self->tail->next = node;
        self->tail = node;
    }

    Py_INCREF(py_object);
    QueueNode_put(self->tail, py_object);
    self->length++;
    Py_RETURN_NONE;
}

// Remove a py_object from the first QueueNode in the Queue
static PyObject* Queue_dequeue(Queue_t* self) {
    if (self->length == 0) {
        PyErr_SetString(PyExc_IndexError, "dequeue from an empty Queue");
        return NULL;
    }

    QueueNode_t* head = self->head;
    PyObject* py_object = head->py_objects[head->back];
    head->back = (head->back + 1) & CHUNKEND;
    head->numEntries--;
    self->length--;

    if (head->numEntries <= 0 && head->next != NULL) {
        self->head = head->next;
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
        for (Py_ssize_t i = 0; i < current->numEntries; ++i) {
            Py_ssize_t index = (current->back + i) & CHUNKEND;
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
        QueueNode_t* tail = self->tail;
        if (tail->numEntries == CHUNKLEN) {
            tail = QueueNode_new(self);
            if (tail == NULL) {
                Py_DECREF(object);
                Py_DECREF(iterable);
                return NULL;
            }
            self->tail->next = tail;
            self->tail = tail;
        }
        QueueNode_put(tail, object);
        self->length++;
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
    // Only the head can be partially consumed; subsequent skipped chunks are full.
    if (index >= current->numEntries) {
        index -= current->numEntries;
        current = current->next;
        for (Py_ssize_t i = 0; i < index / CHUNKLEN; ++i) {
            current = current->next;
        }
    }
    index &= CHUNKEND;
    PyObject* object = current->py_objects[(current->back + index) & CHUNKEND];
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
    if (index >= current->numEntries) {
        index -= current->numEntries;
        current = current->next;
        for (Py_ssize_t i = 0; i < index / CHUNKLEN; ++i) {
            current = current->next;
        }
    }
    index &= CHUNKEND;
    PyObject* oldObject =
        current->py_objects[(current->back + index) & CHUNKEND];
    Py_INCREF(object);
    current->py_objects[(current->back + index) & CHUNKEND] = object;
    Py_DECREF(oldObject);
    return 0;
}

static int Queue_contains(Queue_t* self, PyObject* object) {
    QueueNode_t* current = self->head;
    while (current != NULL) {
        for (Py_ssize_t i = 0; i < current->numEntries; ++i) {
            if (PyObject_RichCompareBool(
                    object, current->py_objects[(current->back + i) & CHUNKEND],
                    Py_EQ)) {
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
    PyObject_GenericGetAttr,                 /* tp_getattro */
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
                                     "fastqueue",
                                     fastqueue_doc,
                                     -1,
                                     NULL,
                                     NULL,
                                     NULL,
                                     NULL,
                                     NULL};

PyMODINIT_FUNC PyInit_fastqueue(void) {
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
