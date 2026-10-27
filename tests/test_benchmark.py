from collections import deque
import importlib.util
from pathlib import Path
import sys

import pytest

pytest.importorskip("matplotlib")
pytest.importorskip("pandas")
spec = importlib.util.spec_from_file_location(
    "fastqueue_example",
    Path(__file__).resolve().parents[1] / "examples" / "fastqueue_example.py",
)
example = importlib.util.module_from_spec(spec)
spec.loader.exec_module(example)

BUILDERS = {
    "enqueue": example.enqueue_profiles,
    "dequeue": example.dequeue_profiles,
    "extend": example.extend_profiles,
    "iteration": example.iteration_profiles,
}


@pytest.mark.parametrize("structure", [deque, example.Queue, example.QueueC])
@pytest.mark.parametrize("operation", BUILDERS)
def test_profile_workload_and_inputs(structure, operation):
    profile = next(p for p in BUILDERS[operation]([500]) if p.structure is structure)
    if operation == "enqueue":
        items = profile.data
    elif operation == "extend":
        items = profile.data[0]
    else:
        items = profile.constructor_params
    original = items[:]
    instances = []
    removed = []

    def construct(values):
        instance = structure(values)
        instances.append(instance)
        return instance

    profile.structure = construct
    if operation == "dequeue":
        dequeue = profile.op

        def record_dequeue(instance):
            item = dequeue(instance)
            removed.append(item)
            return item

        profile.op = record_dequeue
    profile.run()

    assert len(profile.execution_times) == 1
    assert profile.execution_times[0] > 0
    assert len(instances) == 1
    expected = original[::-1] if structure is deque and operation in ("enqueue", "dequeue") else original
    assert list(instances[0]) == ([] if operation == "dequeue" else expected)
    if operation == "dequeue":
        assert removed == expected
    assert items == original


def test_iteration_visits_every_item_inside_timer(monkeypatch):
    events = []

    class RecordingQueue:
        def __init__(self, items):
            events.append("construct")
            self.items = items

        def __iter__(self):
            for item in self.items:
                events.append(item)
                yield item

    def clock():
        events.append("clock")
        return len(events) * 10

    monkeypatch.setattr(example.time, "perf_counter_ns", clock)
    items = [7, 2, 9, 1]
    profile = example.IterationProfile(RecordingQueue, iter, len(items), items)
    profile.run()

    assert events == ["construct", "clock", 7, 2, 9, 1, "clock"]
    assert profile.execution_times == [50]
    assert items == [7, 2, 9, 1]


@pytest.mark.skipif(sys.version_info < (3, 8), reason="Benchmark CLI uses importlib.metadata")
def test_matrix_uses_solid_lines_and_arithmetic_means(monkeypatch):
    monkeypatch.setitem(sys.modules, "fastqueue_example", example)
    plot_spec = importlib.util.spec_from_file_location(
        "benchmark", Path(example.__file__).with_name("benchmark.py")
    )
    benchmark = importlib.util.module_from_spec(plot_spec)
    plot_spec.loader.exec_module(benchmark)
    figures = []
    monkeypatch.setattr(
        benchmark.plt.Figure, "savefig",
        lambda figure, *args, **kwargs: figures.append(figure),
    )
    result = {
        "environment": {"slug": "test", "label": "Test", "python_version": "3.11"},
        "trials": 3,
        "warmups": 1,
        "results": [
            {"operation": operation, "queue": queue, "size": size,
             "samples_ns": [1000, 1000, 7000]}
            for operation in benchmark.OPERATIONS
            for queue in benchmark.COLORS
            for size in (20, 10)
        ],
    }
    benchmark.plot(result, Path("."))

    assert len(figures[0].axes) == 4
    for axis in figures[0].axes:
        assert len(axis.lines) == 3
        assert axis.get_xscale() == axis.get_yscale() == "linear"
        assert axis.get_xlim()[0] == axis.get_ylim()[0] == 0
        for line in axis.lines:
            assert line.get_linestyle() == "-"
            assert list(line.get_xdata()) == [10, 20]
            assert list(line.get_ydata()) == [3, 3]
