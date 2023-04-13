#include <Python.h>

typedef struct QueueNode {
    PyObject* py_objects[256];
    int numEntries; // Number of entries into this node
    int front;
    int back;
    struct QueueNode* next;
} QueueNode_t;

typedef struct Queue {
    PyObject_HEAD
    QueueNode_t* head;
    QueueNode_t* tail;
    int length; // Total number of py_objects stored in the queue
} Queue_t;

PyDoc_STRVAR(is_empty_doc, "Returns whether the queue is empty.");
static PyObject* Queue_is_empty(Queue_t* self, PyObject* args) {
    if (self->length == 0)
        Py_RETURN_TRUE;
    else
        Py_RETURN_FALSE;
}

// Initialize a new QueueNode
static QueueNode_t* QueueNode_new() {
    QueueNode_t* node = (QueueNode_t*) malloc(sizeof(QueueNode_t));
    node->numEntries = 0;
    node->front = 255;
    node->back = 0;
    node->next = NULL;
    return node;
}

static PyObject* Queue_new(PyTypeObject* type, PyObject* args, PyObject* kwargs) {
    Queue_t* self = (Queue_t*)type->tp_alloc(type, 0);
    if (self == NULL)
        return PyErr_NoMemory();

    self->head = NULL;
    self->tail = NULL;
    self->length = 0;
    return (PyObject*)self;
}

// Add a py_object to the front of the QueueNode
static inline void QueueNode_put(QueueNode_t* queue_node, PyObject* py_object) {
    Py_INCREF(py_object);
    queue_node->front = (queue_node->front + 1) & 255;
    queue_node->py_objects[queue_node->front] = py_object;
    queue_node->numEntries++;
}

// Add a py_object to the last QueueNode in the Queue
PyDoc_STRVAR(enqueue_doc, "Add an item to the front of the queue.");
static PyObject* Queue_enqueue(Queue_t* self, PyObject* object) {
    if (object == Py_None)
        Py_RETURN_NONE;

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
PyDoc_STRVAR(dequeue_doc, "Remove and return an item from the end of the queue.");
static PyObject* Queue_dequeue(Queue_t* self, PyObject* args) {
    if (self->length == 0) {
        PyErr_SetString(PyExc_IndexError, "dequeue from an empty Queue");
        return NULL;
    }

    PyObject* py_object = self->head->py_objects[self->head->back];
    self->head->back = (self->head->back + 1) & 255;
    self->head->numEntries--;
    self->length--;

    if (self->head->numEntries <= 0) {
        QueueNode_t* oldHead = self->head;
        self->head = self->head->next;
        free(oldHead);
    }

    if (self->head == NULL)
        self->tail = NULL;

    return py_object;
}

// Deallocate the Queue
static void Queue_dealloc(Queue_t* self) {
    PyObject_GC_UnTrack(self);
    free(self->head);
    Py_TYPE(self)->tp_free((PyObject*)self);
}

static int Queue_clear(Queue_t *self) {
    if (self->length == 0)
        return 0;

    QueueNode_t* current = self->head;
    QueueNode_t* next;
    while (current != NULL) {
        for (int i = 0; i < current->numEntries; ++i) {
            int index = (current->front + i) & 255;
            if (current->py_objects[index] != NULL && !PyObject_IS_GC(current->py_objects[index])) {
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

static int Queue_traverse(Queue_t* self, visitproc visit, void* arg) {
    QueueNode_t* current = self->head;
    while (current != NULL) {
        for (int i = 0; i < current->numEntries; ++i) {
            int index = (current->front + i) & 255;
            Py_VISIT(current->py_objects[index]);
        }
        current = current->next;
    }
    return 0;
}

PyDoc_STRVAR(extend_doc, "Enqueue a sequence of elements from an iterator.");
static PyObject* Queue_extend(Queue_t* self, PyObject* iterator) {
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

static Py_ssize_t Queue_len(Queue_t* self) {   
    return (Py_ssize_t)self->length;
}

static PySequenceMethods Queue_sequence_methods = {
    (lenfunc)Queue_len,                  /* sq_length */
};

static PyMethodDef Queue_methods[] = {
    {"enqueue", (PyCFunction)Queue_enqueue, METH_O, enqueue_doc},
    {"dequeue", (PyCFunction)Queue_dequeue, METH_NOARGS, dequeue_doc},
    {"is_empty", (PyCFunction)Queue_is_empty, METH_NOARGS, is_empty_doc},
    {"extend", (PyCFunction)Queue_extend, METH_O, extend_doc},
    {NULL, NULL, 0, NULL}
};

PyDoc_STRVAR(queue_doc,"Queue() -> Queue object\nQueue is optimized for a sequence of enqueue and dequeue operations at the head and tail.");
static PyTypeObject QueueType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "Queue",                                    /* tp_name */
    sizeof(Queue_t),                            /* tp_basicsize */
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
    PyObject_GenericGetAttr,                    /* tp_getattro */
    0,                                          /* tp_setattro */
    0,                                          /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,    /* tp_flags */
    queue_doc,                                  /* tp_doc */
    (traverseproc)Queue_traverse,               /* tp_traverse */
    (inquiry)Queue_clear,                       /* tp_clear */
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
    (newfunc)Queue_new,                         /* tp_new */
    PyObject_GC_Del,                            /* tp_free */
};

static PyModuleDef QueueModuleDef = {
    PyModuleDef_HEAD_INIT,
    "mQueue",
    "Singly linked, small overhead imlementation of the Queue data structure.",
    -1,
    NULL, NULL, NULL, NULL, NULL
};

PyMODINIT_FUNC PyInit_mQueue(void) {
    PyObject* module;
    if (PyType_Ready(&QueueType) < 0)
        return NULL;

    module = PyModule_Create(&QueueModuleDef);
    if (module == NULL)
        return NULL;
    PyModule_AddType(module, &QueueType);
    return module;
}