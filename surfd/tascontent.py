"""Managed canonical-content epochs; callers must fence the REAL mutation interval.

POSIX cooperative publishers, not a sandbox against root/the trusted owner.
Missing/dirty state never initializes or repairs itself. A crash during publication
leaves ODD, so neither an old cached witness nor a partial write becomes eligible.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import errno
import math
import os
from pathlib import Path
import re
import secrets
import stat
import threading
import time

try:
    import fcntl
except ImportError:
    fcntl = None

MAGIC = b'FTETASASSET1 '
MAX_EPOCH = (1 << 64) - 1
RECORD = re.compile(rb'FTETASASSET1 ([0-9a-f]{32}) ([0-9]{20})\n')
SIZE = len(MAGIC) + 32 + 1 + 20 + 1
_LOCAL = threading.local()


class Unavailable(ValueError):
    pass


@dataclass(frozen=True)
class Stamp:
    incarnation: str
    epoch: int


@dataclass(frozen=True)
class Lease:
    stamp: Stamp
    fd: int  # May be explicitly inherited by an owned actor; never LOCK_UN it.


def _path(value):
    if (os.name != 'posix' or fcntl is None or
            not all(hasattr(os, name) for name in ('O_NOFOLLOW', 'O_NONBLOCK', 'pread', 'pwrite', 'O_DIRECTORY'))):
        raise Unavailable('CONTENT_LEASE_UNSUPPORTED')
    raw = os.fspath(value)
    path = Path(raw)
    if (not path.is_absolute() or str(path) != raw or '..' in path.parts or
            os.path.realpath(path.parent) != str(path.parent)):
        raise Unavailable('CONTENT_LEASE_PATH')
    return path


def _identity(fd):
    s = os.fstat(fd)
    if (not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_uid != os.geteuid() or s.st_mode & 0o077):
        raise Unavailable('CONTENT_LEASE_IDENTITY')


def _read(fd):
    _identity(fd)
    if os.fstat(fd).st_size != SIZE:
        raise Unavailable('CONTENT_LEASE_RECORD')
    raw = os.pread(fd, SIZE + 1, 0)
    match = RECORD.fullmatch(raw)
    if match is None:
        raise Unavailable('CONTENT_LEASE_RECORD')
    epoch = int(match[2])
    if epoch > MAX_EPOCH:
        raise Unavailable('CONTENT_LEASE_RECORD')
    if epoch & 1:
        raise Unavailable('CONTENT_LEASE_DIRTY')
    return Stamp(match[1].decode('ascii'), epoch)


def _write(fd, stamp):
    raw = MAGIC + stamp.incarnation.encode('ascii') + b' ' + ('%020d\n' % stamp.epoch).encode('ascii')
    offset = 0
    while offset < len(raw):
        n = os.pwrite(fd, raw[offset:], offset)
        if n <= 0:
            raise Unavailable('CONTENT_LEASE_IO')
        offset += n
    os.ftruncate(fd, len(raw))
    os.fsync(fd)


def initialize(value):
    """Explicit bootstrap in an existing owned directory; NEVER overwrite/recover."""
    path = _path(value)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        _identity(fd)
        stamp = Stamp(secrets.token_hex(16), 0)
        _write(fd, stamp)
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
        return stamp
    finally:
        os.close(fd)


def _acquire(fd, write, timeout):
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 <= timeout <= 60:
        raise Unavailable('CONTENT_LEASE_TIMEOUT')
    deadline = time.monotonic() + timeout
    operation = (fcntl.LOCK_EX if write else fcntl.LOCK_SH) | fcntl.LOCK_NB
    while True:
        try:
            fcntl.flock(fd, operation)
            return
        except OSError as error:
            if error.errno not in (errno.EACCES, errno.EAGAIN, errno.EINTR):
                raise
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise Unavailable('CONTENT_LEASE_BUSY') from error
            time.sleep(min(.02, remaining))


@contextmanager
def _lease(value, write, timeout):
    path = _path(value)
    held = getattr(_LOCAL, 'held', None)
    if held is not None and held[1] != os.getpid():
        # A fork must not unlock its parent's open-description lock.
        os.close(held[3].fd)
        _LOCAL.held = held = None
    if held is not None:
        if held[0] != path or held[2] != write:
            raise Unavailable('CONTENT_LEASE_LOCK_ORDER')
        yield held[3]
        return
    fd = os.open(path, (os.O_RDWR if write else os.O_RDONLY) | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        _identity(fd)
        _acquire(fd, write, timeout)
        before = _read(fd)
        if write:
            if before.epoch > MAX_EPOCH - 2:
                raise Unavailable('CONTENT_LEASE_EXHAUSTED')
            odd = Stamp(before.incarnation, before.epoch + 1)
            _write(fd, odd)  # Durable invalidation BEFORE caller can mutate content.
            lease = Lease(odd, fd)
        else:
            lease = Lease(before, fd)
        _LOCAL.held = (path, os.getpid(), write, lease)
        try:
            yield lease
        finally:
            _LOCAL.held = None
            if write:
                _write(fd, Stamp(before.incarnation, before.epoch + 2))
    finally:
        # Closing ONLY this copy preserves any explicitly inherited actor lease.
        os.close(fd)


def snapshot(value, timeout=5):
    return _lease(value, False, timeout)


def publication(value, timeout=10):
    return _lease(value, True, timeout)
