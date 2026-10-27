from collections import deque
import hashlib
import importlib.util
from pathlib import Path
import shutil

import pytest

pytest.importorskip("matplotlib")
pytest.importorskip("pandas")
import _fastqueue


@pytest.fixture
def comparison(monkeypatch):
    examples = Path(__file__).resolve().parents[1] / "examples"
    monkeypatch.syspath_prepend(str(examples))
    spec = importlib.util.spec_from_file_location("compare_enqueue", examples / "compare_enqueue.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_loads_distinct_extensions_and_records_hashes(comparison, tmp_path):
    extension = Path(_fastqueue.__file__)
    builds = []
    for label in ("first", "second"):
        directory = tmp_path / label
        directory.mkdir()
        path = directory / extension.name
        shutil.copy2(extension, path)
        builds.append((label, path))

    structures, metadata = comparison.load_builds(builds)

    assert structures["first"] is not structures["second"]
    assert structures["deque"] is deque
    for label, path in builds:
        assert metadata[label]["extension"] == str(path)
        assert metadata[label]["extension_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_rejects_same_extension_loaded_twice(comparison):
    extension = Path(_fastqueue.__file__)
    with pytest.raises(AssertionError, match="distinct Queue types"):
        comparison.load_builds([("first", extension), ("second", extension)])


def test_legacy_source_hash_is_unchanged(comparison, tmp_path):
    (tmp_path / "src").mkdir()
    source = b"legacy native implementation\r\n"
    (tmp_path / "src" / "fastqueue.c").write_bytes(source)
    extension = tmp_path / "extension"
    extension.write_bytes(b"native binary")
    assert comparison.build_metadata(extension)["source_sha256"] == hashlib.sha256(source).hexdigest()


@pytest.mark.parametrize("filename", ["fastqueue.c", "queue.c", "queue_contiguous.c"])
def test_split_source_hash_tracks_each_file(comparison, tmp_path, filename):
    source = tmp_path / "src"
    source.mkdir()
    for name in ("fastqueue.c", "queue.c", "queue_contiguous.c"):
        (source / name).write_text(name + "\n")
    extension = tmp_path / "extension"
    extension.write_bytes(b"native binary")
    before = comparison.build_metadata(extension)["source_sha256"]
    (source / filename).write_text("changed\n")
    assert comparison.build_metadata(extension)["source_sha256"] != before


def test_plot_uses_raw_arithmetic_means_and_correct_speed_ratio(comparison, monkeypatch):
    figures = []
    monkeypatch.setattr(
        comparison.plt.Figure, "savefig",
        lambda figure, *args, **kwargs: figures.append(figure),
    )
    result = {
        "builds": ["candidate", "deque"],
        "sizes": [10, 20],
        "platform_label": "Test",
        "python_version": "3.9.6",
        "trials": 3,
        "warmups": 0,
        "results": [
            {"build": build, "size": size, "samples_ns": samples}
            for build, samples in (("candidate", [1000, 1000, 7000]),
                                   ("deque", [2000, 2000, 14000]))
            for size in (20, 10)
        ],
    }
    comparison.plot(result, Path("comparison"))

    elapsed, relative = figures[0].axes
    assert [list(line.get_ydata()) for line in elapsed.lines] == [[3, 3], [6, 6]]
    assert list(relative.lines[0].get_ydata()) == [2, 2]
    assert list(relative.lines[1].get_ydata()) == [1, 1]
    for line in elapsed.lines:
        assert list(line.get_xdata()) == [10, 20]
