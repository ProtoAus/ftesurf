"""Read-only, per-file copy checksums for evidence-backup.ps1, not verdicts.

The caller supplies REQUEST through standard input before this source. No source
writes, database access, collection or repair. Metadata stability is cooperative;
this is not a coherent global snapshot or proof against a dishonest source host.
"""
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import time


def _open_relative(root, relative):
    parts = PurePosixPath(relative).parts
    if len(parts) < 2 or parts[0] not in ('runs', 'evidence'):
        raise ValueError('outside declared copy scope')
    if any(part in ('', '.', '..') for part in parts):
        raise ValueError('unsafe relative path')
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=directory)
            os.close(directory)
            directory = child
        return os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                       dir_fd=directory)
    finally:
        os.close(directory)


def _identity(value):
    return (value.st_dev, value.st_ino, value.st_nlink, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns)


def snapshot(root, max_files, max_bytes, max_seconds):
    root = Path(root)
    if not root.is_absolute() or root.resolve(strict=True) != root:
        raise ValueError('source root must be canonical, not a symlink alias')
    if type(max_files) is not int or type(max_bytes) is not int:
        raise ValueError('integer copy budgets required')
    if (max_files <= 0 or max_bytes <= 0 or isinstance(max_seconds, bool)
            or not isinstance(max_seconds, (int, float))
            or not math.isfinite(max_seconds) or max_seconds <= 0):
        raise ValueError('finite positive copy budgets required')
    deadline = time.monotonic() + max_seconds
    files, deferred = [], []
    read_bytes = visited = 0

    def check():
        if visited > max_files or read_bytes > max_bytes:
            raise RuntimeError('copy-index allowance exhausted; no complete index')
        if time.monotonic() > deadline:
            raise RuntimeError('copy-index deadline; no complete index')

    def walk_error(error):
        raise error  # Never silently classify an unreadable subtree as complete.

    for name in ('runs', 'evidence'):
        base = root / name
        if base.is_symlink() or not base.is_dir():
            raise ValueError('declared evidence directory missing or aliased')
        for parent, directories, names in os.walk(base, followlinks=False, onerror=walk_error):
            visited += 1
            check()
            for directory in list(directories):
                path = Path(parent) / directory
                if path.is_symlink():
                    directories.remove(directory)
                    deferred.append(dict(rel=path.relative_to(root).as_posix(),
                                         reason='symlink-directory'))
                    visited += 1
                    check()
            for filename in names:
                visited += 1
                check()
                path = Path(parent) / filename
                relative = path.relative_to(root).as_posix()
                fd = None
                try:
                    fd = _open_relative(root, relative)
                    before = os.fstat(fd)
                    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                        deferred.append(dict(rel=relative, reason='not-single-regular-file'))
                        continue
                    digest = hashlib.sha256()
                    length = 0
                    while True:
                        check()
                        block = os.read(fd, min(1 << 20, max_bytes - read_bytes + 1))
                        if not block:
                            break
                        length += len(block)
                        read_bytes += len(block)
                        check()
                        digest.update(block)
                    after = os.fstat(fd)
                    if _identity(before) != _identity(after) or length != before.st_size:
                        deferred.append(dict(rel=relative, reason='changed-during-read'))
                        continue
                    files.append(dict(rel=relative, bytes=length,
                                      sha256=digest.hexdigest(), mtime_ns=before.st_mtime_ns))
                except OSError as error:
                    deferred.append(dict(rel=relative, reason=type(error).__name__))
                finally:
                    if fd is not None:
                        os.close(fd)
    return dict(version=1, per_file_observations_not_global_instant=True,
                files=sorted(files, key=lambda row: row['rel']), deferred=deferred,
                read_bytes=read_bytes, visited=visited)


if __name__ == '__main__':
    request = globals().get('REQUEST')
    if not isinstance(request, dict):
        raise SystemExit('Use evidence-backup.ps1; REQUEST is supplied through stdin')
    result = snapshot(request['root'], request['max_files'], request['max_bytes'],
                      request['max_seconds'])
    print(json.dumps(result, ensure_ascii=True, separators=(',', ':')))
