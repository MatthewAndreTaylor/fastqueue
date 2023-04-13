#include <Python.h>

typedef struct {
    PyObject_VAR_HEAD
    PyObject** objects;
    int length;
    int capacity;
    int front;
    int back;
} QueueObject;

static int is_empty(QueueObject* self) {
    if (self == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "Queue not allocated");
        return -1;
    }
    return self->length == 0;
}

static PyObject* Queue_is_empty(QueueObject* self, PyObject* args) {
    if (is_empty(self))
        Py_RETURN_TRUE;
    else
        Py_RETURN_FALSE;
}

static PyObject* Queue_new(PyTypeObject* type, PyObject* args, PyObject* kwargs) {
    QueueObject* self = (QueueObject*)type->tp_alloc(type, 0);
    if (self == NULL)
        return PyErr_NoMemory();

    self->objects = (PyObject**) malloc(1024 * sizeof(PyObject*));
    if (self->objects == NULL) {
        Py_DECREF(self);
        return PyErr_NoMemory();
    }

    self->length = 0;
    self->capacity = 1024;
    self->front = 0;
    self->back = self->capacity - 1;
    return (PyObject*)self;
}

static void Queue_dealloc(QueueObject* self) {
    if (self == NULL)
        return;
    PyObject_GC_UnTrack(self);
    free(self->objects);
    self->objects = NULL;
    Py_TYPE(self)->tp_free(self);
}

static int Queue_clear(QueueObject* self) {
    if (self->length == 0)
        return 0;

    for (int i = 0; i < self->length; ++i) {
        int index = (self->front + i) % self->capacity;
        if (self->objects[index] != NULL && !PyObject_IS_GC(self->objects[index])) {
            Py_DECREF(self->objects[index]);
            self->objects[index] = NULL;
        }
    }
    self->length = 0;
    self->front = 0;
    self->back = self->capacity - 1;
    return 0;
}

static int Queue_traverse(QueueObject* self, visitproc visit, void* arg) {
    for (int i = 0; i < self->length; ++i) {
        int index = (self->front + i) % self->capacity;
        Py_VISIT(self->objects[index]);
    }
    return 0;
}

static void resize(QueueObject* self, int newCapacity) {
    PyObject** newObjects = (PyObject**) malloc(newCapacity * sizeof(PyObject*));
    if (newObjects == NULL) {
        PyErr_NoMemory();
        return;
    }
    for (int i = 0; i < self->length; ++i) {
        newObjects[i] = self->objects[(self->front + i) % self->capacity];
    }

    free(self->objects);
    self->objects = newObjects;
    self->front = 0;
    self->back = self->length - 1;
    self->capacity = newCapacity;
}

static PyObject* Queue_enqueue(QueueObject* self, PyObject* object) {
    if (object == Py_None)
        Py_RETURN_NONE;
    if (self->length == self->capacity)
        resize(self, self->capacity * 2);

    Py_INCREF(object);
    self->front = (self->front + self->capacity - 1) % self->capacity;
    self->objects[self->front] = object;
    self->length++;
    Py_RETURN_NONE;
}

static PyObject* Queue_dequeue(QueueObject* self, PyObject* args) {
    if (is_empty(self))
        return NULL;

    PyObject* object = self->objects[self->back];
    self->back = (self->back + self->capacity - 1) % self->capacity;
    self->length--;
    return object;
}

static PyObject* Queue_extend(QueueObject* self, PyObject* iterator) {
    PyObject* iterable = PyObject_GetIter(iterator);
    if (iterable == NULL)
        return NULL;
    
    PyObject* py_object;
    PyObject* (*next)(PyObject*);
    next = *Py_TYPE(iterable)->tp_iternext;
    while ((py_object = next(iterable)) != NULL) {
        Queue_enqueue(self, py_object);
    }
    Py_DECREF(iterable);
    Py_RETURN_NONE;
}

static Py_ssize_t Queue_len(QueueObject* self) {   
    return (Py_ssize_t)self->length;
}

static PySequenceMethods Queue_sequence_methods = {
    (lenfunc)Queue_len,                  /* sq_length */
};

static PyMethodDef Queue_methods[] = {
    {"enqueue", (PyCFunction)Queue_enqueue, METH_O, "Add an object to the front of the queue."},
    {"dequeue", (PyCFunction)Queue_dequeue, METH_NOARGS, "Remove and return an object from the back of the queue."},
    {"is_empty", (PyCFunction)Queue_is_empty, METH_NOARGS, "Check if the queue is empty."},
    {"extend", (PyCFunction)Queue_extend, METH_O, "Add an objects from an iterator front of the queue."},
    {NULL, NULL, 0, NULL}
};


static PyTypeObject QueueType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "Queue",                                    /* tp_name */
    sizeof(QueueObject),                        /* tp_basicsize */
    0,                                          /* tp_itemsize */
    (destructor)Queue_dealloc,                  /* tp_dealloc */
    0,                                          /* tp_print */
    0,                                          /* tp_getattr */
    0,                                          /* tp_setattr */
    0,                                          /* tp_reserved */
    0,                                          /* tp_repr */
    0,                                          /* tp_as_number */
    &Queue_sequence_methods,                    /* tp_as_sequence */
    0,                                          /* tp_as_mapping */
    PyObject_HashNotImplemented,                /* tp_hash */
    0,                                          /* tp_call */
    0,                                          /* tp_str */
    0,                                          /* tp_getattro */
    0,                                          /* tp_setattro */
    0,                                          /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,    /* tp_flags */
    "Python Queue Extension",                   /* tp_doc */
    (traverseproc)Queue_traverse,               /* tp_traverse */
    (inquiry)Queue_clear,                        /* tp_clear */
    0,                                          /* tp_richcompare */
    0,                                          /* tp_weaklistoffset */
    0,                                          /* tp_iter */
    0,                                          /* tp_iternext */
    Queue_methods,                              /* tp_methods */
    0,                                          /* tp_members */
    0,                                          /* tp_getset */
    0,                                          /* tp_base */
    0,                                          /* tp_dict */
    0,                                          /* tp_descr_get */
    0,                                          /* tp_descr_set */
    0,                                          /* tp_dictoffset */
    0,                                          /* tp_init */
    PyType_GenericAlloc,                        /* tp_alloc */
    Queue_new,                                  /* tp_new */
    PyObject_GC_Del,                            /* tp_free */
};

static PyModuleDef QueueModuleDef = {
    PyModuleDef_HEAD_INIT,
    "mQueueContiguous",
    "A simple implementation of a Queue data structure",
    -1,
    NULL, NULL, NULL, NULL, NULL
};

PyMODINIT_FUNC PyInit_mQueueContiguous(void) {
    PyObject* module;

    if (PyType_Ready(&QueueType) < 0)
        return NULL;

    module = PyModule_Create(&QueueModuleDef);
    if (module == NULL)
        return NULL;
    PyModule_AddType(module, &QueueType);
    return module;
}