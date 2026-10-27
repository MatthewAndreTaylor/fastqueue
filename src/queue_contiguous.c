/**
 * Copyright (c) 2023 Matthew Andre Taylor
 */
/**
 * Single ended Contiguous Python Queue
 * --- fastqueue.QueueC ---
 */

#define QUEUE_CONTIGUOUS_CHUNKLEN 512

typedef struct {
    PyObject_HEAD size_t front;
    size_t capacity;
    size_t back;
    PyObject** objects;
    size_t state;
} QueueC;

static PyObject* QueueC_new(PyTypeObject* type, PyObject* args,
                            PyObject* kwargs) {
    QueueC* self = (QueueC*)type->tp_alloc(type, 0);
    if (self == NULL) {
        return PyErr_NoMemory();
    }

    size_t capacity = QUEUE_CONTIGUOUS_CHUNKLEN;
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
        self->state++;
        Py_DECREF(object);
    }
    return 0;
}

static PyObject* QueueC_clear_method(QueueC* self, PyObject* args) {
    QueueC_clear(self);
    Py_RETURN_NONE;
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
    self->state++;
    Py_RETURN_NONE;
}

static QUEUE_NOINLINE PyObject* QueueC_enqueue_grow(QueueC* self, PyObject* object) {
    if (QueueC_resize(self, self->capacity * 2) < 0) return NULL;
    return QueueC_enqueue(self, object);
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
    self->state++;
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
        self->state++;
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
        // __eq__ may drop the queue's reference to item.
        Py_INCREF(item);
        int result = PyObject_RichCompareBool(item, object, Py_EQ);
        Py_DECREF(item);
        if (result < 0) {
            return -1;
        }
        if (result) {
            return 1;
        }
    }
    return 0;
}

typedef struct {
    PyObject_HEAD
    QueueC* queue;
    size_t index;
    size_t state;
    Py_ssize_t remaining;
} QueueCIter;

static int QueueCIter_traverse(QueueCIter* self, visitproc visit, void* arg) {
    Py_VISIT(self->queue);
    return 0;
}

static int QueueCIter_clear(QueueCIter* self) {
    self->remaining = 0;
    Py_CLEAR(self->queue);
    return 0;
}

static void QueueCIter_dealloc(QueueCIter* self) {
    PyObject_GC_UnTrack(self);
    QueueCIter_clear(self);
    PyObject_GC_Del(self);
}

static PyObject* QueueCIter_next(QueueCIter* self) {
    if (self->remaining == 0) {
        QueueCIter_clear(self);
        return NULL;
    }
    QueueC* queue = self->queue;
    if (self->state != queue->state) {
        QueueCIter_clear(self);
        PyErr_SetString(PyExc_RuntimeError, "QueueC mutated during iteration");
        return NULL;
    }
    // A length hint may relocate live items without changing their order.
    size_t index = queue->back + self->index;
    if (index >= queue->capacity) index -= queue->capacity;
    PyObject* object = queue->objects[index];
    self->index++;
    self->remaining--;
    Py_INCREF(object);
    return object;
}

static PyObject* QueueCIter_length_hint(QueueCIter* self, PyObject* args) {
    return PyLong_FromSsize_t(self->remaining);
}

static PyMethodDef QueueCIter_methods[] = {
    {"__length_hint__", (PyCFunction)QueueCIter_length_hint, METH_NOARGS,
     "Return the number of items remaining."},
    {NULL, NULL, 0, NULL}
};

static PyTypeObject QueueCIterType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "_fastqueue.QueueCIterator",
    .tp_basicsize = sizeof(QueueCIter),
    .tp_dealloc = (destructor)QueueCIter_dealloc,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
    .tp_traverse = (traverseproc)QueueCIter_traverse,
    .tp_clear = (inquiry)QueueCIter_clear,
    .tp_iter = PyObject_SelfIter,
    .tp_iternext = (iternextfunc)QueueCIter_next,
    .tp_methods = QueueCIter_methods,
};

static PyObject* QueueC_iter(QueueC* self) {
    QueueCIter* iterator = PyObject_GC_New(QueueCIter, &QueueCIterType);
    if (iterator == NULL) return NULL;
    Py_INCREF(self);
    iterator->queue = self;
    iterator->index = 0;
    iterator->state = self->state;
    iterator->remaining = QueueC_len(self);
    PyObject_GC_Track(iterator);
    return (PyObject*)iterator;
}
