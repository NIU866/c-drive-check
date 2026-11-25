"""Read file sizes and roll them up into directory totals."""

import heapq
import os
import stat
from dataclasses import dataclass, field


@dataclass
class Scan:
    size: int = 0
    files: int = 0
    skipped: int = 0
    folders: list[tuple[int, str]] = field(default_factory=list)
    largest: list[tuple[int, str]] = field(default_factory=list)


def is_link(info):
    attributes = getattr(info, "st_file_attributes", 0)
    return stat.S_ISLNK(info.st_mode) or bool(
        attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def scan(root, cancelled, report=lambda count: None, limit=200):
    """Return None if cancelled. Paths that cannot be read are counted as skipped."""
    info = os.lstat(root)
    if is_link(info) or not stat.S_ISDIR(info.st_mode):
        raise ValueError("请选择实际磁盘或文件夹。")
    result = Scan()

    def keep(heap, size, path):
        item = (size, path)
        if len(heap) < limit:
            heapq.heappush(heap, item)
        elif item > heap[0]:
            heapq.heapreplace(heap, item)

    def read_folder(path):
        subtotal = 0
        children = []
        try:
            with os.scandir(path) as directory:
                for entry in directory:
                    if cancelled.is_set():
                        break
                    try:
                        info = entry.stat(follow_symlinks=False)
                        if is_link(info):
                            result.skipped += 1
                        elif stat.S_ISDIR(info.st_mode):
                            children.append(entry.path)
                        elif stat.S_ISREG(info.st_mode):
                            subtotal += info.st_size
                            result.files += 1
                            keep(result.largest, info.st_size, entry.path)
                            if result.files % 2048 == 0:
                                report(result.files)
                    except OSError:
                        result.skipped += 1
        except OSError:
            if path == root:
                raise
            result.skipped += 1
        return subtotal, iter(children)

    size, children = read_folder(root)
    stack = [(root, size, children)]
    while stack:
        if cancelled.is_set():
            return None
        path, size, children = stack[-1]
        child = next(children, None)
        if child is not None:
            child_size, child_iter = read_folder(child)
            stack.append((child, child_size, child_iter))
            continue
        stack.pop()
        if stack:
            keep(result.folders, size, path)
            parent, parent_size, remaining = stack[-1]
            stack[-1] = (parent, parent_size + size, remaining)
        else:
            result.size = size
    result.folders.sort(reverse=True)
    result.largest.sort(reverse=True)
    return result
