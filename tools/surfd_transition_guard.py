#!/usr/bin/env python3
"""Cooperative POSIX pre-import admission fence; never imports surfd."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time
import uuid


FILES = {"surfd.py", "ksfimport.py", "ksfgrab.py", "ksfprofile.py",
         "tools/ksfconvert.py", "tools/ksfreplay_info.py"}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def plain_path(value):
    p = Path(value)
    require(p.is_absolute() and str(p) == value and ".." not in p.parts,
            "path must be absolute/canonical")
    for part in [*reversed(p.parents), p]:
        require(not part.is_symlink(), "symlink path refused")
    return p


def secure_stat(st, directory=False):
    require(st.st_uid == os.geteuid(), "wrong owner")
    require(stat.S_IMODE(st.st_mode) == (0o700 if directory else 0o600),
            "requires owner-only modes")
    require(stat.S_ISDIR(st.st_mode) if directory else
            stat.S_ISREG(st.st_mode) and st.st_nlink == 1, "unsafe file type/link")


def read_json(path, private=False):
    path = plain_path(str(path))
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd) as f:
        if private:
            secure_stat(os.fstat(f.fileno()))
        return json.load(f)


def manifest_check(m):
    require(type(m) is dict and set(m) == {"generation", "source_home", "hashes", "routes"},
            "malformed manifest")
    require(type(m["generation"]) is str and
            re.fullmatch("[0-9a-f]{40}", m["generation"]), "full generation SHA required")
    require(plain_path(m["source_home"]).is_dir(), "missing source home")
    require(type(m["hashes"]) is dict and set(m["hashes"]) == FILES,
            "exact six-file raw hash set required")
    for digest in m["hashes"].values():
        require(type(digest) is str and re.fullmatch("[0-9a-f]{64}", digest), "bad hash")
    require(type(m["routes"]) is dict and bool(m["routes"]), "routes required")
    for name, argv in m["routes"].items():
        require(re.fullmatch("[a-z][a-z0-9_-]*", name), "bad route name")
        require(type(argv) is list and len(argv) >= 2 and
                all(type(a) is str and a and "\0" not in a for a in argv), "bad fixed argv")
        require(plain_path(argv[0]).is_file() and os.access(argv[0], os.X_OK),
                "missing fixed interpreter/executable")
    return m


def verify_hashes(m):
    for name, digest in m["hashes"].items():
        p = plain_path(str(Path(m["source_home"]) / name))
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as source:
            require(stat.S_ISREG(os.fstat(source.fileno()).st_mode),
                    "target source must be regular: " + name)
            hashed = hashlib.sha256()
            for block in iter(lambda: source.read(1 << 20), b""):
                hashed.update(block)
        require(hashed.hexdigest() == digest,
                "target source raw hash mismatch: " + name)


def write_new(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def state_write(root, state):
    temp = root / ("state-" + uuid.uuid4().hex)
    write_new(temp, state)
    os.replace(temp, root / "state.json")
    sync_dir(root)


def state_read(root, m):
    s = read_json(root / "state.json", True)
    require(type(s) is dict and set(s) == {"admission", "generation", "closure"} and
            s["admission"] in ("CLOSED", "OPEN") and s["generation"] == m["generation"] and
            type(s["closure"]) is str and re.fullmatch("[0-9a-f]{32}", s["closure"]),
            "malformed state; admission refused")
    return s


def lock_file(root, name):
    fd = os.open(root / name, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
    secure_stat(os.fstat(fd))
    return fd


def acquire(fd, operation, timeout):
    import fcntl
    end = time.monotonic() + timeout
    while True:
        try:
            fcntl.flock(fd, operation | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            require(time.monotonic() < end, "bounded drain/lock timeout; remains CLOSED if closed")
            time.sleep(0.02)


def main():
    require(os.name == "posix", "UNSUPPORTED: POSIX flock/fsync required; Windows refused")
    import fcntl
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--timeout", type=float, default=5)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--manifest", required=True)
    sub.add_parser("close")
    sub.add_parser("status")
    reopen = sub.add_parser("reopen")
    reopen.add_argument("--generation", required=True)
    reopen.add_argument("--receipt", required=True)
    launch = sub.add_parser("launch")
    launch.add_argument("--generation", required=True)
    launch.add_argument("--route", required=True)
    sub.add_parser("candidate", help="intentionally blocked; requires separate reviewed protocol")
    a = parser.parse_args()
    require(math.isfinite(a.timeout) and 0 <= a.timeout <= 300, "invalid timeout")
    root = plain_path(a.state_dir)
    if a.command == "init":
        m = manifest_check(read_json(a.manifest))
        root.mkdir(mode=0o700)  # Exclusive: never overwrite/reinitialize existing state.
        secure_stat(root.stat(), True)
        write_new(root / "manifest.json", m)
        for name in ("admission.lock", "controller.lock"):
            write_new(root / name, {})
        state_write(root, {"admission": "CLOSED", "generation": m["generation"],
                           "closure": uuid.uuid4().hex})
        sync_dir(root.parent)
        print("INITIALIZED CLOSED")
        return
    secure_stat(root.stat(), True)
    m = manifest_check(read_json(root / "manifest.json", True))
    if a.command == "candidate":
        raise ValueError("candidate start BLOCKED: no quiescent-start acceptance protocol implemented")
    if a.command == "status":
        print(json.dumps(state_read(root, m), sort_keys=True))
        return
    admission = lock_file(root, "admission.lock")
    try:
        if a.command == "launch":
            acquire(admission, fcntl.LOCK_SH, a.timeout)
            s = state_read(root, m)
            require(s["admission"] == "OPEN", "CLOSED: application interpreter not started")
            require(a.generation == m["generation"], "wrong generation")
            require(a.route in m["routes"], "route not allowlisted")
            verify_hashes(m)
            os.chdir(m["source_home"])
            os.set_inheritable(admission, True)
            # exec preserves PID and shared lock for the cooperative foreground lifetime.
            os.execve(m["routes"][a.route][0], m["routes"][a.route],
                      {"PATH": "/usr/bin:/bin", "HOME": m["source_home"],
                       "PYTHONNOUSERSITE": "1"})
        controller = lock_file(root, "controller.lock")
        try:
            acquire(controller, fcntl.LOCK_EX, a.timeout)
            s = state_read(root, m)
            if a.command == "close":
                s.update(admission="CLOSED", closure=uuid.uuid4().hex)
                state_write(root, s)
                print("CLOSED DURABLE; draining", flush=True)
                acquire(admission, fcntl.LOCK_EX, a.timeout)
                print("DRAINED cooperative foreground launches only", flush=True)
            else:
                require(a.generation == m["generation"], "wrong generation")
                require(s["admission"] == "CLOSED", "already open; close explicitly first")
                acquire(admission, fcntl.LOCK_EX, a.timeout)
                verify_hashes(m)
                receipt = read_json(a.receipt, True)
                expected = {"generation": m["generation"], "closure": s["closure"],
                            "source_home": m["source_home"], "hashes": m["hashes"],
                            "schema": 19, "accepted": True}
                require(type(receipt) is dict and set(receipt) == set(expected) | {"process"},
                        "malformed external acceptance receipt")
                require(all(type(receipt[k]) is type(v) and receipt[k] == v
                            for k, v in expected.items()), "acceptance receipt mismatch")
                p = receipt["process"]
                require(type(p) is dict and set(p) == {"pid", "start", "cwd"} and
                        type(p["pid"]) is int and p["pid"] > 0 and
                        type(p["start"]) is str and bool(p["start"]) and
                        p["cwd"] == m["source_home"], "missing process acceptance")
                s["admission"] = "OPEN"
                state_write(root, s)
                print("OPEN: external receipt consumed; not independently attested")
        finally:
            os.close(controller)
    finally:
        os.close(admission)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print("REFUSED: " + str(exc), file=sys.stderr)
        sys.exit(2)
