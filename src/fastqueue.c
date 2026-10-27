/**
 * Copyright (c) 2023 Matthew Andre Taylor
 */
#include <Python.h>
#include <string.h>

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

// Keep error-reporting calls out of the successful dequeue path.
static QUEUE_NOINLINE PyObject* Queue_dequeue_empty(void) {
    PyErr_SetString(PyExc_IndexError, "dequeue from an empty Queue");
    return NULL;
}

#include "queue.c"
#include "queue_contiguous.c"

PyDoc_STRVAR(copy_doc, "Return a shallow copy of the Queue.");
PyDoc_STRVAR(enqueue_doc, "Add an item to the front of the Queue.");
PyDoc_STRVAR(dequeue_doc,
             "Remove and return an item from the end of the Queue.");
PyDoc_STRVAR(extend_doc, "Enqueue a sequence of elements from an iterator.");
PyDoc_STRVAR(clear_doc, "Remove all items from the Queue.");


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
    {"clear", (PyCFunction)Queue_clear_method, METH_NOARGS, clear_doc},
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
    {"clear", (PyCFunction)QueueC_clear_method, METH_NOARGS, clear_doc},
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
    (newfunc)QueueC_new,                     /* tp_new */
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
