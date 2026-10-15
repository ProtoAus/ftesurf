#!/usr/bin/env python3
"""Pinned legacy-entrypoint pre-import gate (POSIX, trusted same-UID code).

This gates application effects, not interpreter creation or Python startup hooks.
Installers must drain *all* old processes and pin dependencies first. source_home
must contain the entire immutable runtime, not merely the six hashed files.
This is cooperative admission, not a sandbox against the owner or application.
"""
import hashlib
import importlib.machinery
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import types


FILES = frozenset({"surfd.py", "ksfimport.py", "ksfgrab.py", "ksfprofile.py",
                   "tools/ksfconvert.py", "tools/ksfreplay_info.py"})


def _source(path, digest):
    p = Path(path)
    if not p.is_absolute() or str(p) != path or os.path.realpath(path) != path:
        raise ValueError("noncanonical helper/source path")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        st = os.fstat(stream.fileno())
        if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or
                st.st_uid != os.geteuid() or st.st_mode & 0o022):
            raise ValueError("unsafe helper/source")
        data = stream.read()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("raw helper/source hash mismatch")
    return data


def render_wrapper(*, dispatch_path, dispatch_sha256, guard_path, guard_sha256,
                   state_dir, generation, source_relative):
    """Return exact UTF-8 stub bytes with fixed bindings; no deployed CLI knobs."""
    for value in (dispatch_path, guard_path, state_dir):
        if (not isinstance(value, str) or "\0" in value or
                not PurePosixPath(value).is_absolute() or
                str(PurePosixPath(value)) != value or ".." in PurePosixPath(value).parts):
            raise ValueError("canonical absolute fixed POSIX paths required")
    for value, length in ((dispatch_sha256, 64), (guard_sha256, 64), (generation, 40)):
        if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{%d}" % length, value):
            raise ValueError("invalid fixed digest/generation")
    if source_relative not in FILES:
        raise ValueError("not one of the six entrypoints")
    # Keep imports and bootstrap scratch out of the application's original globals.
    stub = '''# Generated pre-import gate: application effects only, not interpreter startup.
def _surfd_bootstrap(namespace):
    import hashlib
    import os
    import stat
    import types
    path = {dispatch_path!r}
    if not os.path.isabs(path) or os.path.realpath(path) != path:
        raise ValueError("noncanonical dispatch path")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        st = os.fstat(stream.fileno())
        if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or
                st.st_uid != os.geteuid() or st.st_mode & 0o022):
            raise ValueError("unsafe dispatch source")
        data = stream.read()
    if hashlib.sha256(data).hexdigest() != {dispatch_sha256!r}:
        raise ValueError("raw dispatch hash mismatch")
    helper = types.ModuleType("_surfd_pinned_dispatch")
    helper.__file__ = path
    exec(compile(data, path, "exec"), helper.__dict__)
    helper.dispatch(namespace, guard_path={guard_path!r}, guard_sha256={guard_sha256!r},
                    state_dir={state_dir!r}, generation={generation!r},
                    source_relative={source_relative!r})
_surfd_bootstrap(globals())
'''
    return stub.format(dispatch_path=dispatch_path, dispatch_sha256=dispatch_sha256,
                       guard_path=guard_path, guard_sha256=guard_sha256,
                       state_dir=state_dir, generation=generation,
                       source_relative=source_relative).encode("utf-8")


def _reject_stale_modules(home, namespace):
    # Include unchanged local runtime modules: a preloaded legacy dependency is
    # just as dangerous as a stale one of the six entrypoints. Do not evict it.
    local_names = {p.stem for p in home.glob("*.py")}
    local_names.update(p.stem for p in (home / "tools").glob("*.py"))
    for name, module in tuple(sys.modules.items()):
        if name.rsplit(".", 1)[-1] not in local_names or module is None:
            continue
        if getattr(module, "__dict__", None) is namespace:
            continue
        origin = getattr(module, "__file__", None)
        if not origin or not Path(origin).resolve().is_relative_to(home):
            raise ValueError("preloaded runtime module outside source_home: " + name)


def dispatch(namespace, *, guard_path, guard_sha256, state_dir, generation,
             source_relative):
    """Gate then execute in the importer's existing module object and namespace."""
    if os.name != "posix":
        raise ValueError("POSIX admission required")
    import fcntl
    if source_relative not in FILES:
        raise ValueError("not one of the six entrypoints")
    guard = types.ModuleType("_surfd_pinned_guard")
    guard.__file__ = guard_path
    exec(compile(_source(guard_path, guard_sha256), guard_path, "exec"), guard.__dict__)
    root = guard.plain_path(state_dir)
    guard.secure_stat(root.stat(), True)
    fd = os.open(root / "admission.lock", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        guard.secure_stat(os.fstat(fd))
        guard.acquire(fd, fcntl.LOCK_SH, 5)
        manifest = guard.manifest_check(guard.read_json(root / "manifest.json", True))
        guard.require(manifest["generation"] == generation, "wrong fixed generation")
        state = guard.read_json(root / "state.json", True)
        guard.require(type(state) is dict and
                      set(state) == {"admission", "generation", "closure"} and
                      state["admission"] == "OPEN" and state["generation"] == generation and
                      type(state["closure"]) is str and
                      re.fullmatch("[0-9a-f]{32}", state["closure"]),
                      "admission not OPEN for fixed generation")
        guard.require(set(manifest["hashes"]) == FILES, "six-file manifest required")
        home = guard.plain_path(manifest["source_home"])
        for directory in (home, home / "tools"):
            st = guard.plain_path(str(directory)).stat()
            guard.require(stat.S_ISDIR(st.st_mode) and st.st_uid == os.geteuid() and
                          not st.st_mode & 0o022, "unsafe source directory")
        target_data = None
        for relative, digest in manifest["hashes"].items():
            data = _source(str(home / relative), digest)
            if relative == source_relative:
                target_data = data
        _reject_stale_modules(home, namespace)
        target = str(home / source_relative)
        code = compile(target_data, target, "exec")
        os.chdir(home)
        sys.path.insert(0, str(home))
        if source_relative.startswith("tools/"):
            sys.path.insert(1, str(home / "tools"))
        name = namespace["__name__"]
        loader = importlib.machinery.SourceFileLoader(name, target)
        namespace["__file__"] = target
        namespace["__loader__"] = loader
        namespace["__spec__"] = (None if name == "__main__" else
                                 importlib.machinery.ModuleSpec(name, loader, origin=target))
        namespace["__cached__"] = None
        namespace.pop("_surfd_bootstrap", None)
        os.set_inheritable(fd, True)
    except BaseException:
        os.close(fd)
        raise
    try:
        exec(code, namespace)
    except BaseException:
        os.close(fd)
        raise
    # Raw inheritable fd intentionally remains open for process/worker lifetime.
