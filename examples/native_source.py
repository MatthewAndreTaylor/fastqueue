"""Read native sources from either a legacy or split checkout."""


def source_bytes(root):
    source = root / "src"
    data = (source / "fastqueue.c").read_bytes()
    for name in ("queue.c", "queue_contiguous.c"):
        path = source / name
        if path.exists():
            data += path.read_bytes()
    return data
