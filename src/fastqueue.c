/**
 * Copyright (c) 2023 Matthew Andre Taylor
 */
#include <Python.h>
#include <pythread.h>

PyDoc_STRVAR(is_empty_doc, "Returns whether the Queue is empty.");
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
    PyObject_HEAD PyObject** objects;
    size_t length;
    size_t capacity;
    size_t front;
    size_t back;
} QueueC;

static PyObject* QueueC_is_empty(QueueC* self, PyObject* args) {
    if (self->length == 0) {
        Py_RETURN_TRUE;
    }
    Py_RETURN_FALSE;
}

static PyObject* QueueC_new(PyTypeObject* type, PyObject* args,
                            PyObject* kwargs) {
    QueueC* self = (QueueC*)type->tp_alloc(type, 0);
    if (self == NULL) {
        return PyErr_NoMemory();
    }

    self->objects = (PyObject**)malloc(1024 * sizeof(PyObject*));
    if (self->objects == NULL) {
        Py_DECREF(self);
        return PyErr_NoMemory();
    }

    self->length = 0;
    self->back = 0;
    self->capacity = 1024;
    self->front = 1023;
    return (PyObject*)self;
}

static PyObject* QueueC_copy(QueueC* self, PyObject* args) {
    QueueC* copy = (QueueC*)Py_TYPE(self)->tp_alloc(Py_TYPE(self), 0);
    if (copy == NULL) {
        return PyErr_NoMemory();
    }

    copy->objects = (PyObject**)malloc(self->capacity * sizeof(PyObject*));
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
    copy->capacity = self->capacity;
    copy->front = self->front;
    copy->back = self->back;
    return (PyObject*)copy;
}

static void QueueC_dealloc(QueueC* self) {
    if (self == NULL) {
        return;
    }
    PyObject_GC_UnTrack(self);
    free(self->objects);
    Py_TYPE(self)->tp_free(self);
}

static int QueueC_clear(QueueC* self) {
    if (self->length == 0) {
        return 0;
    }

    for (size_t i = 0; i < self->length; ++i) {
        size_t index = (self->back + i) % self->capacity;
        if (self->objects[index] != NULL &&
            !PyObject_IS_GC(self->objects[index])) {
            Py_DECREF(self->objects[index]);
            self->objects[index] = NULL;
        }
    }
    self->length = 0;
    self->front = self->capacity - 1;
    self->back = 0;
    return 0;
}

static int QueueC_traverse(QueueC* self, visitproc visit, void* arg) {
    for (size_t i = 0; i < self->length; ++i) {
        size_t index = (self->back + i) % self->capacity;
        Py_VISIT(self->objects[index]);
    }
    return 0;
}

static void QueueC_resize(QueueC* self, size_t newCapacity) {
    PyObject** newObjects = (PyObject**)malloc(newCapacity * sizeof(PyObject*));
    if (newObjects == NULL) {
        PyErr_NoMemory();
        return;
    }
    for (size_t i = 0; i < self->length; ++i) {
        newObjects[i] = self->objects[(self->back + i) % self->capacity];
    }
    self->front = self->length - 1;
    self->back = 0;
    free(self->objects);
    self->objects = newObjects;
    self->capacity = newCapacity;
}

static PyObject* QueueC_enqueue(QueueC* self, PyObject* object) {
    if (self->length == self->capacity) {
        QueueC_resize(self, self->capacity * 2);
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
    PyObject* iterable = PyObject_GetIter(iterator);
    if (iterable == NULL) {
        PyErr_Format(PyExc_TypeError, "Expected 'Iterable', got '%s'",
                     Py_TYPE(iterator)->tp_name);
        return NULL;
    }

    PyObject* py_object;
    PyObject* (*next)(PyObject*);
    next = *Py_TYPE(iterable)->tp_iternext;

    // Small optimization sizing, amortized approach is still very good
    size_t len = (size_t)PyObject_Size(iterator);
    if (len > self->length) {
        if (self->length + len > self->capacity) {
            QueueC_resize(self, (self->capacity + len) * 2);
        }

        while ((py_object = next(iterable)) != NULL) {
            Py_INCREF(py_object);
            self->front = (self->front + 1) % self->capacity;
            self->objects[self->front] = py_object;
            self->length++;
        }
    } else {
        while ((py_object = next(iterable)) != NULL) {
            QueueC_enqueue(self, py_object);
        }
    }

    Py_DECREF(iterable);
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
    if (index < 0) {
        index = index + self->length;
    }
    if (index >= (Py_ssize_t)self->length) {
        PyErr_SetString(PyExc_IndexError, "Queue index out of range");
        return NULL;
    }
    PyObject* object = self->objects[(self->back + index) % self->capacity];
    Py_INCREF(object);
    return object;
}

static int QueueC_setitem(QueueC* self, Py_ssize_t index, PyObject* object) {
    if (index < 0) {
        index = index + self->length;
    }
    if (index >= (Py_ssize_t)self->length) {
        PyErr_SetString(PyExc_IndexError, "Queue index out of range");
        return -1;
    }

    PyObject* oldObject = self->objects[(self->back + index) % self->capacity];
    Py_DECREF(oldObject);
    Py_INCREF(object);
    self->objects[(self->back + index) % self->capacity] = object;
    return 0;
}

static int QueueC_contains(QueueC* self, PyObject* object) {
    for (size_t i = 0; i < self->length; ++i) {
        size_t index = (self->back + i) % self->capacity;
        if (self->objects[index] != NULL &&
            PyObject_RichCompareBool(object, self->objects[index], Py_EQ)) {
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
    {"is_empty", (PyCFunction)QueueC_is_empty, METH_NOARGS, is_empty_doc},
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
 * --- fastqueue.QueueC ---
 */
typedef struct QueueNode {
    PyObject* py_objects[256];
    short numEntries; // Number of entries into this node
    short front;
    short back;
    struct QueueNode* next;
} QueueNode_t;

typedef struct Queue {
    PyObject_HEAD QueueNode_t* head;
    QueueNode_t* tail;
    Py_ssize_t length; // Total number of py_objects stored in the queue
} Queue_t;

static PyObject* Queue_is_empty(Queue_t* self, PyObject* args) {
    if (self->length == 0) {
        Py_RETURN_TRUE;
    }
    Py_RETURN_FALSE;
}

// Initialize a new QueueNode
static inline QueueNode_t* QueueNode_new() {
    QueueNode_t* node = (QueueNode_t*)malloc(sizeof(QueueNode_t));
    node->numEntries = 0;
    node->front = 255;
    node->back = 0;
    node->next = NULL;
    return node;
}

static PyObject* Queue_new(PyTypeObject* type, PyObject* args,
                           PyObject* kwargs) {
    Queue_t* self = (Queue_t*)type->tp_alloc(type, 0);
    if (self == NULL) {
        return PyErr_NoMemory();
    }

    self->head = NULL;
    self->tail = NULL;
    self->length = 0;
    return (PyObject*)self;
}

static PyObject* Queue_copy(Queue_t* self, PyObject* args) {
    Queue_t* newQueue = (Queue_t*)Queue_new(Py_TYPE(self), args, NULL);
    if (newQueue == NULL) {
        return PyErr_NoMemory();
    }

    newQueue->head = NULL;
    newQueue->tail = NULL;
    newQueue->length = self->length;

    QueueNode_t* current = self->head;
    while (current != NULL) {
        QueueNode_t* newNode = QueueNode_new();
        if (newNode == NULL) {
            PyErr_NoMemory();
            return NULL;
        }

        for (short i = 0; i < current->numEntries; ++i) {
            short index = (current->back + i) & 255;
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
        current = current->next;
    }
    return (PyObject*)newQueue;
}

// Add a py_object to the front of the QueueNode
static inline void QueueNode_put(QueueNode_t* queue_node, PyObject* py_object) {
    Py_INCREF(py_object);
    queue_node->front = (queue_node->front + 1) & 255;
    queue_node->py_objects[queue_node->front] = py_object;
    queue_node->numEntries++;
}

// Add a py_object to the last QueueNode in the Queue
static PyObject* Queue_enqueue(Queue_t* self, PyObject* object) {
    if (self->tail == NULL) {
        self->head = QueueNode_new();
        self->tail = self->head;
    } else {
        if (self->tail->numEntries >= 256) {
            if (self->tail->next == NULL) {
                QueueNode_t* node = QueueNode_new();
                self->tail->next = node;
                self->tail = node;
            }
        }
    }

    QueueNode_put(self->tail, object);
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
    head->back = (head->back + 1) & 255;
    head->numEntries--;
    self->length--;

    if (head->numEntries <= 0) {
        self->head = head->next;
        free(head);
    }

    if (self->head == NULL) {
        self->tail = NULL;
    }

    return py_object;
}

static int Queue_clear(Queue_t* self) {
    if (self->length == 0) {
        return 0;
    }

    QueueNode_t* current = self->head;
    QueueNode_t* next;
    while (current != NULL) {
        for (short i = 0; i < current->numEntries; ++i) {
            short index = (current->back + i) & 255;
            if (current->py_objects[index] != NULL &&
                !PyObject_IS_GC(current->py_objects[index])) {
                Py_DECREF(current->py_objects[index]);
                current->py_objects[index] = NULL;
            }
        }
        next = current->next;
        free(current);
        current = next;
    }
    self->length = 0;
    self->head = NULL;
    self->tail = NULL;
    return 0;
}

// Deallocate the Queue
static void Queue_dealloc(Queue_t* self) {
    if (self == NULL) {
        return;
    }
    PyObject_GC_UnTrack(self);
    if (self->head != NULL) {
        Queue_clear(self);
    }
    Py_TYPE(self)->tp_free((PyObject*)self);
}

static int Queue_traverse(Queue_t* self, visitproc visit, void* arg) {
    QueueNode_t* current = self->head;
    while (current != NULL) {
        for (short i = 0; i < current->numEntries; ++i) {
            short index = (current->back + i) & 255;
            Py_VISIT(current->py_objects[index]);
        }
        current = current->next;
    }
    return 0;
}

static PyObject* Queue_extend(Queue_t* self, PyObject* iterator) {
    PyObject* iterable = PyObject_GetIter(iterator);
    if (iterable == NULL) {
        PyErr_Format(PyExc_TypeError, "Expected 'Iterable', got '%s'",
                     Py_TYPE(iterator)->tp_name);
        return NULL;
    }

    PyObject* py_object;
    PyObject* (*next)(PyObject*);
    next = *Py_TYPE(iterable)->tp_iternext;
    while ((py_object = next(iterable)) != NULL) {
        Queue_enqueue(self, py_object);
    }
    Py_DECREF(iterable);
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
    if (index < 0) {
        index = index + self->length;
    }

    if (index >= self->length) {
        PyErr_SetString(PyExc_IndexError, "Queue index out of range");
        return NULL;
    }

    QueueNode_t* current = self->head;
    for (size_t i = 0; i < (size_t)(index / 256); ++i) {
        current = current->next;
    }
    PyObject* object = current->py_objects[(current->back + index) & 255];
    Py_INCREF(object);
    return object;
}

static int Queue_setitem(Queue_t* self, Py_ssize_t index, PyObject* object) {
    if (index < 0) {
        index = index + Queue_len(self);
    }

    if (index >= self->length) {
        PyErr_SetString(PyExc_IndexError, "Queue index out of range");
        return -1;
    }

    QueueNode_t* current = self->head;
    for (size_t i = 0; i < (size_t)(index / 256); ++i) {
        current = current->next;
    }
    PyObject* oldObject = current->py_objects[(current->back + index) & 255];
    Py_DECREF(oldObject);
    Py_INCREF(object);
    current->py_objects[(current->back + index) & 255] = object;
    return 0;
}

static int Queue_contains(Queue_t* self, PyObject* object) {
    QueueNode_t* current = self->head;
    while (current != NULL) {
        for (short i = 0; i < current->numEntries; ++i) {
            if (PyObject_RichCompareBool(
                    object, current->py_objects[(current->back + i) & 255],
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
    {"is_empty", (PyCFunction)Queue_is_empty, METH_NOARGS, is_empty_doc},
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

typedef struct LockQueue {
    PyObject_HEAD Queue_t* queue;
    PyThread_type_lock lock;
} LockQueue_t;

static PyObject* LockQueue_new(PyTypeObject* type, PyObject* args,
                               PyObject* kwargs) {
    LockQueue_t* self = (LockQueue_t*)type->tp_alloc(type, 0);
    if (self == NULL) {
        return PyErr_NoMemory();
    }

    self->queue = (Queue_t*)Queue_new(&QueueType, args, kwargs);
    self->lock = NULL;
    return (PyObject*)self;
}

static int LockQueue_init(LockQueue_t* self, PyObject* args, PyObject* kwargs) {
    self->lock = PyThread_allocate_lock();
    if (self == NULL) {
        PyErr_SetString(PyExc_MemoryError, "Could not allocate thread lock.");
        return -1;
    }
    return Queue_init(self->queue, args, kwargs);
}

static void LockQueue_dealloc(LockQueue_t* self) {
    PyThread_free_lock(self->lock);
    Py_TYPE(self)->tp_free((PyObject*)self);
}

static int LockQueue_traverse(LockQueue_t* self, visitproc visit, void* arg) {
    return Queue_traverse(self->queue, visit, arg);
}

static int LockQueue_clear(LockQueue_t* self) {
    PyThread_acquire_lock(self->lock, 1);
    int res = Queue_clear(self->queue);
    PyThread_release_lock(self->lock);
    return res;
}

static PyObject* LockQueue_call_with_lock(LockQueue_t* self, PyObject* args,
                                          PyObject* (*func)(Queue_t*,
                                                            PyObject*)) {
    PyThread_acquire_lock(self->lock, 1);
    PyObject* result = func(self->queue, args);
    PyThread_release_lock(self->lock);
    return result;
}

static PyObject* LockQueue_is_empty(LockQueue_t* self, PyObject* args) {
    return LockQueue_call_with_lock(self, args, &Queue_is_empty);
}

static PyObject* LockQueue_copy(LockQueue_t* self, PyObject* args) {
    return LockQueue_call_with_lock(self, args, &Queue_copy);
}

static PyObject* LockQueue_enqueue(LockQueue_t* self, PyObject* args) {
    return LockQueue_call_with_lock(self, args, &Queue_enqueue);
}

static PyObject* LockQueue_dequeue(LockQueue_t* self) {
    PyThread_acquire_lock(self->lock, 1);
    PyObject* result = Queue_dequeue(self->queue);
    PyThread_release_lock(self->lock);
    return result;
}

static PyObject* LockQueue_extend(LockQueue_t* self, PyObject* args) {
    return LockQueue_call_with_lock(self, args, &Queue_extend);
}

static PyObject* LockQueue_item(LockQueue_t* self, Py_ssize_t index) {
    PyThread_acquire_lock(self->lock, 1);
    PyObject* result = Queue_item(self->queue, index);
    PyThread_release_lock(self->lock);
    return result;
}

static Py_ssize_t LockQueue_len(LockQueue_t* self) {
    PyThread_acquire_lock(self->lock, 1);
    Py_ssize_t res = (Py_ssize_t)self->queue->length;
    PyThread_release_lock(self->lock);
    return res;
}

static int LockQueue_setitem(LockQueue_t* self, Py_ssize_t index,
                             PyObject* args) {
    PyThread_acquire_lock(self->lock, 1);
    int res = Queue_setitem(self->queue, index, args);
    PyThread_release_lock(self->lock);
    return res;
}

static int LockQueue_contains(LockQueue_t* self, PyObject* args) {
    PyThread_acquire_lock(self->lock, 1);
    int res = Queue_contains(self->queue, args);
    PyThread_release_lock(self->lock);
    return res;
}

PyDoc_STRVAR(
    get_doc,
    "Return the first element of the LockQueue, None if no element exists.");
static PyObject* LockQueue_get(LockQueue_t* self, PyObject* args) {
    if (LockQueue_len(self) > 0) {
        return LockQueue_dequeue(self);
    }
    Py_RETURN_NONE;
}

static PyMethodDef LockQueue_methods[] = {
    {"is_empty", (PyCFunction)LockQueue_is_empty, METH_NOARGS, is_empty_doc},
    {"enqueue", (PyCFunction)LockQueue_enqueue, METH_O, enqueue_doc},
    {"dequeue", (PyCFunction)LockQueue_dequeue, METH_NOARGS, dequeue_doc},
    {"extend", (PyCFunction)LockQueue_extend, METH_O, extend_doc},
    {"__copy__", (PyCFunction)LockQueue_copy, METH_NOARGS, copy_doc},
    {"copy", (PyCFunction)LockQueue_copy, METH_NOARGS, copy_doc},
    {"get", (PyCFunction)LockQueue_get, METH_NOARGS, get_doc},
    {NULL, NULL, 0, NULL}};

static PySequenceMethods LockQueue_sequence_methods = {
    (lenfunc)LockQueue_len,             /* sq_length */
    0,                                  /* sq_concat */
    NULL,                               /* sq_repeat */
    (ssizeargfunc)LockQueue_item,       /* sq_item */
    NULL,                               /* sq_slice */
    (ssizeobjargproc)LockQueue_setitem, /* sq_as_item */
    NULL,                               /* sq_as_slice */
    (objobjproc)LockQueue_contains,     /* sq_contains */
    0                                   /* sq_inplace_concat */
};

PyDoc_STRVAR(lockqueue_doc,
             "LockQueue() -> Single ended synchronous Queue object.");
static PyTypeObject LockQueueType = {
    PyVarObject_HEAD_INIT(NULL, 0) "LockQueue", /* tp_name */
    sizeof(LockQueue_t),                        /* tp_basicsize */
    0,                                          /* tp_itemsize */
    (destructor)LockQueue_dealloc,              /* tp_dealloc */
    0,                                          /* tp_print */
    0,                                          /* tp_getattr */
    0,                                          /* tp_setattr */
    0,                                          /* tp_reserved */
    0,                                          /* tp_repr */
    0,                                          /* tp_as_number */
    &LockQueue_sequence_methods,                /* tp_as_sequence */
    0,                                          /* tp_as_mapping */
    PyObject_HashNotImplemented,                /* tp_hash */
    0,                                          /* tp_call */
    0,                                          /* tp_str */
    PyObject_GenericGetAttr,                    /* tp_getattro */
    0,                                          /* tp_setattro */
    0,                                          /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,    /* tp_flags */
    lockqueue_doc,                              /* tp_doc */
    (traverseproc)LockQueue_traverse,           /* tp_traverse */
    (inquiry)LockQueue_clear,                   /* tp_clear */
    0,                                          /* tp_richcompare */
    0,                                          /* tp_weaklistoffset */
    0,                                          /* tp_iter */
    0,                                          /* tp_iternext */
    LockQueue_methods,                          /* tp_methods */
    0,                                          /* tp_members */
    0,                                          /* tp_getset */
    0,                                          /* tp_base */
    0,                                          /* tp_dict */
    0,                                          /* tp_descr_get */
    0,                                          /* tp_descr_set */
    0,                                          /* tp_dictoffset */
    (initproc)LockQueue_init,                   /* tp_init */
    PyType_GenericAlloc,                        /* tp_alloc */
    (newfunc)LockQueue_new,                     /* tp_new */
    PyObject_GC_Del,                            /* tp_free */
};

static PyModuleDef QueueModuleDef = {
    PyModuleDef_HEAD_INIT,
    "_fastqueue",
    "Singly linked, small overhead implementations of the Queue data "
    "structure.",
    -1,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL};

PyMODINIT_FUNC PyInit__fastqueue(void) {
    PyObject* module;
    if (PyType_Ready(&QueueType) < 0 || PyType_Ready(&QueueCType) < 0 ||
        PyType_Ready(&LockQueueType) < 0) {
        return NULL;
    }

    module = PyModule_Create(&QueueModuleDef);
    if (module == NULL) {
        return NULL;
    }
    PyModule_AddObject(module, "QueueC", (PyObject*)&QueueCType);
    PyModule_AddObject(module, "Queue", (PyObject*)&QueueType);
    PyModule_AddObject(module, "LockQueue", (PyObject*)&LockQueueType);
    return module;
}
