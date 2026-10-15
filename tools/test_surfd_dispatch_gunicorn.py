#!/usr/bin/env python3
"""Synthetic actual-gunicorn legacy surfd:app import/lifetime gate.

Predict: a legacy master without admission FDs can serve only after its worker
imports the exact pinned wrapper while OPEN. CLOSED replacement imports refuse
before real source execution. An admitted held request retains SH until drain;
a deliberately FD-dropping WSGI falsifies that oracle while still serving.
No live application/schema/no-loss/sandbox acceptance is claimed.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess
import sys
import time

GUARD = Path(__file__).with_name("surfd_transition_guard.py").resolve()
DISPATCH = Path(__file__).with_name("surfd_import_dispatch.py").resolve()
GENERATION = "1" * 40
FILES = ("surfd.py", "ksfimport.py", "ksfgrab.py", "ksfprofile.py",
         "tools/ksfconvert.py", "tools/ksfreplay_info.py")
ENV = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}
sys.dont_write_bytecode = True


def check(ok, message):
    if not ok:
        raise RuntimeError(message)


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def wait_for(predicate, message, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.02)
    raise RuntimeError("timeout: " + message)


def canonical(value):
    path = Path(value)
    check(path.is_absolute() and str(path) == value and str(path.resolve()) == value,
          "path must be canonical absolute and link-free: " + value)
    for part in (path, *path.parents):
        check(not part.is_symlink(), "linked path refused: " + str(part))
    return path


def identity(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": pid, "start": fields[19], "ppid": int(fields[1])}
    except FileNotFoundError:
        return None


def same_process(record):
    current = identity(record["pid"])
    return current is not None and current["start"] == record["start"]


def matching_fds(pid, lock):
    target = lock.stat()
    found = []
    for entry in Path(f"/proc/{pid}/fd").iterdir():
        try:
            st = entry.stat()
        except FileNotFoundError:
            continue
        if (st.st_dev, st.st_ino) == (target.st_dev, target.st_ino):
            found.append(int(entry.name))
    return sorted(found)


def contended(lock):
    import fcntl
    with lock.open("r+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(handle, fcntl.LOCK_UN)
        return False


def bounded_command(argv, timeout, env=None):
    process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, env=env)
    record = identity(process.pid)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        # subprocess.run(timeout=...) would silently escalate to SIGKILL.
        if process.poll() is None:
            check(record is not None and same_process(record), "refuse stale command identity signal")
            process.send_signal(signal.SIGTERM)
        process.communicate(timeout=5)
        raise RuntimeError("bounded command timed out (TERM only): " + str(argv))
    check(len(stdout) + len(stderr) <= 65536, "command output exceeded bound")
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)


def preflight(args):
    check(sys.platform.startswith("linux") and os.name == "posix", "UNSUPPORTED: native local Linux only")
    check(__debug__, "REFUSED: -O unsupported; no output created")
    dependencies = canonical(args.gunicorn_path)
    check(dependencies.is_dir(), "missing explicit dependency directory")
    versions = {d.metadata["Name"].lower(): d.version
                for d in importlib.metadata.distributions(path=[str(dependencies)])}
    if args.host_distro:
        check(str(dependencies) == "/usr/lib/python3/dist-packages",
              "host distro mode requires the explicit Debian system package path")
        check(str(Path(sys.executable).resolve()).startswith("/usr/bin/python3"),
              "host distro mode requires the actual system interpreter")
        import gunicorn
        check(Path(gunicorn.__file__).resolve().is_relative_to(dependencies),
              "host gunicorn did not resolve from the declared distro path")
        check(gunicorn.__version__ == args.gunicorn_version,
              "declared host gunicorn version does not match imported distro bytes")
        hashes = {}
        for package in ("gunicorn", "packaging", "pkg_resources"):
            for path in sorted((dependencies / package).rglob("*.py")):
                st = path.lstat()
                check(stat.S_ISREG(st.st_mode) and st.st_uid == 0 and
                      not (st.st_mode & 0o022) and not path.is_symlink(),
                      "unsafe distro dependency source")
                hashes[str(path.relative_to(dependencies))] = hashlib.sha256(path.read_bytes()).hexdigest()
        check("gunicorn/app/wsgiapp.py" in hashes, "missing host gunicorn source")
        for directory in (dependencies, dependencies / "gunicorn",
                          *[p for p in (dependencies / "gunicorn").rglob("*") if p.is_dir()]):
            st = directory.lstat()
            check(not directory.is_symlink() and st.st_uid == 0 and not st.st_mode & 0o022,
                  "unsafe distro package directory")
        out = canonical(args.out)
        check(not out.exists() and out.parent.is_dir(), "--out must be NEW with existing parent")
        owners = [p / "OWNER.md" for p in out.parents if (p / "OWNER.md").is_file()]
        check(owners and not owners[0].is_symlink() and
              owners[0].stat().st_uid == os.geteuid(), "unsafe/missing OWNER.md")
        for part in (out.parent, *out.parent.parents):
            check(part.stat().st_uid == os.geteuid() or not (part.stat().st_mode & 0o022),
                  "foreign writable output ancestor refused")
        check(len(os.fsencode(str(out / "c/g.sock"))) < 108, "Unix socket path too long")
        distro = bounded_command(["dpkg-query", "-W", "-f=${Version}", "gunicorn"], timeout=10)
        check(distro.returncode == 0, "installed gunicorn dpkg-query failed")
        return out, dependencies, {"mode": "actual-installed-distro-not-upstream-pin",
            "distro_package_version": distro.stdout, "versions": versions,
            "dependency_sha256": hashes, "dependency_path": str(dependencies),
            "python": sys.version, "executable": str(Path(sys.executable).resolve()),
            "launcher_sha256": hashlib.sha256(Path("/usr/bin/gunicorn").read_bytes()).hexdigest(),
            "guard_sha256": hashlib.sha256(GUARD.read_bytes()).hexdigest(),
            "test_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "owner_file": str(owners[0])}
    expected = {"gunicorn": args.gunicorn_version, "packaging": "24.2"}
    if args.gunicorn_version == "20.1.0":
        expected["setuptools"] = "65.5.1"  # Supplies this version's pkg_resources import.
    check(all(versions.get(name) == version for name, version in expected.items()),
          "explicit pinned dependencies required: " + str(expected))
    hashes = {}
    packages = ["gunicorn", "packaging", "gunicorn-" + args.gunicorn_version + ".dist-info",
                "packaging-24.2.dist-info"]
    if args.gunicorn_version == "20.1.0":
        packages.extend(("setuptools", "pkg_resources", "_distutils_hack", "setuptools-65.5.1.dist-info"))
    for package in packages:
        for path in sorted((dependencies / package).rglob("*")):
            check(not path.is_symlink(), "linked dependency refused")
            if path.is_file() and "__pycache__" not in path.parts:
                check(stat.S_ISREG(path.lstat().st_mode), "nonregular dependency refused")
                hashes[str(path.relative_to(dependencies))] = hashlib.sha256(path.read_bytes()).hexdigest()
    check("gunicorn/app/wsgiapp.py" in hashes and "packaging/version.py" in hashes,
          "missing dependency source")
    # Fail missing/broken imports before creating output; never use global packages.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(dependencies))
    try:
        import gunicorn.app.wsgiapp
        import packaging.version
        modules = [gunicorn, packaging]
        if args.gunicorn_version == "20.1.0":
            import pkg_resources
            modules.append(pkg_resources)
            check("pkg_resources/__init__.py" in hashes, "missing local pkg_resources source")
        for module in modules:
            check(Path(module.__file__).resolve().is_relative_to(dependencies),
                  "dependency resolved outside explicit root")
    finally:
        sys.path.remove(str(dependencies))
    out = canonical(args.out)
    check(not out.exists() and out.parent.is_dir(), "--out must be NEW with existing parent")
    owners = [p / "OWNER.md" for p in out.parents if (p / "OWNER.md").exists()]
    check(owners, "--out requires existing OWNER.md ancestor")
    owner = owners[0]
    check(not owner.is_symlink() and stat.S_ISREG(owner.lstat().st_mode) and
          owner.stat().st_uid == os.geteuid(), "unsafe OWNER.md")
    for part in (out.parent, *out.parent.parents):
        check(part.stat().st_uid == os.geteuid() or not (part.stat().st_mode & 0o022),
              "foreign writable output ancestor refused")
    check(len(os.fsencode(str(out / "c/g.sock"))) < 108, "Unix socket path too long")
    return out, dependencies, {"versions": versions, "dependency_sha256": hashes,
                              "dependency_path": str(dependencies), "python": sys.version,
                              "executable": str(Path(sys.executable).resolve()),
                              "guard_sha256": hashlib.sha256(GUARD.read_bytes()).hexdigest(),
                              "test_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                              "owner_file": str(owner)}


# Candidate is a fixed, single-process stdlib WSGI server, never the real surfd.
CANDIDATE = r'''import os, signal, socket
from pathlib import Path
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler
root = Path(__file__).resolve().parent.parent
class UnixServer(WSGIServer):
    address_family = socket.AF_UNIX
    def server_bind(self):
        self.socket.bind(self.server_address)
        self.server_name = "synthetic"
        self.server_port = 0
        self.setup_environ()
class Handler(WSGIRequestHandler):
    def get_environ(self):
        self.client_address = ("local", 0)
        return super().get_environ()
def app(environ, start_response):
    body = b"SYNTHETIC CANDIDATE READY\n"
    start_response("200 OK", [("Content-Length", str(len(body)))])
    return [body]
running = True
def stop(signum, frame):
    global running
    running = False
signal.signal(signal.SIGTERM, stop)
server = UnixServer(str(root / "b.sock"), Handler)
server.set_app(app)
server.timeout = .05
try:
    while running:
        server.handle_request()
finally:
    server.server_close()
    (root / "b.sock").unlink()
'''

WITNESS = r'''import json, os
from pathlib import Path
root = Path(__file__).resolve().parent
original = None

def admission_fds():
    lock = (root / "guard/admission.lock").stat()
    found = []
    for entry in Path("/proc/self/fd").iterdir():
        try:
            st = entry.stat()
        except FileNotFoundError:
            continue
        if (st.st_dev, st.st_ino) == (lock.st_dev, lock.st_ino):
            found.append(int(entry.name))
    return sorted(found)

def emit(event, **extra):
    start = Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19]
    record = dict(event=event, pid=os.getpid(), ppid=os.getppid(), start=start,
                  fds=admission_fds(), monotonic_ns=__import__('time').monotonic_ns(), **extra)
    fd = os.open(root / "events.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, (json.dumps(record) + "\n").encode())
    finally:
        os.close(fd)
'''

LAUNCHER = r'''import importlib.machinery, importlib.util
import json, os, sys
from pathlib import Path
sys.dont_write_bytecode = True
root = Path(__file__).resolve().parent
settings = json.loads((root / "settings.json").read_text())
sys.path.insert(0, settings["dependencies"])
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "legacy"))
import witness
class WrapperLoader(importlib.machinery.SourceFileLoader):
    def exec_module(self, module):
        witness.original = module
        witness.emit("import_attempt", wrapper=self.path)
        try:
            super().exec_module(module)
        except BaseException as exc:
            witness.emit("import_refused", error=str(exc))
            raise
class WrapperFinder:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "surfd":
            source = str(root / "legacy/surfd.py")
            return importlib.util.spec_from_file_location(fullname, source,
                        loader=WrapperLoader(fullname, source))
sys.meta_path.insert(0, WrapperFinder())
witness.emit("master")
from gunicorn.app.wsgiapp import run
sys.argv = ["synthetic-legacy-gunicorn", "--config", str(root / "config.py"),
            "--bind", "unix:" + str(root / "g.sock"), "--worker-class", "gthread",
            "--threads", "2", "--workers", "1", "--max-requests", "4",
            "--max-requests-jitter", "0", "--timeout", "30",
            "--graceful-timeout", "20", "--umask", "0077",
            "--worker-tmp-dir", str(root), "--access-logfile", "-",
            "--error-logfile", "-", "surfd:app"]
run()
'''

WSGI = r'''import os, sys, time
from pathlib import Path
import witness
root = Path(__file__).resolve().parent.parent
assert witness.original is sys.modules[__name__]
assert witness.original.__dict__ is globals()
assert __name__ == "surfd" and __spec__.origin == __file__
assert Path(__file__) == root / "immutable/surfd.py"
assert "_surfd_bootstrap" not in globals()
before = witness.admission_fds()
assert len(before) == 1 and os.get_inheritable(before[0])
if DROP_FD:
    for fd in before:
        os.close(fd)
witness.emit("import", origin=__file__, spec_origin=__spec__.origin,
             original_module=True, original_globals=True, before=before, dropped=DROP_FD)

def app(environ, start_response):
    path = environ["PATH_INFO"]
    witness.emit("request", path=path, origin=__file__)
    if path == "/held":
        witness.emit("held")
        deadline = time.monotonic() + 15
        while not (root / "release").exists():
            if time.monotonic() >= deadline:
                raise RuntimeError("synthetic held release timeout")
            time.sleep(.02)
    body = ("SYNTHETIC LEGACY " + path + " " + __file__ + "\n").encode()
    start_response("200 OK", [("Content-Type", "text/plain"),
                              ("Content-Length", str(len(body)))])
    yield body
    witness.emit("complete", path=path)
'''


class Fixture:
    def __init__(self, root, dependencies, drop_fd, commands):
        self.root, self.commands = root, commands
        self.master = self.bootstrap = None
        self.master_identity = self.bootstrap_identity = None
        self.held_socket = None
        self.finished = False
        root.mkdir(mode=0o700)
        self.home = root / "immutable"
        self.home.mkdir(mode=0o700)
        (self.home / "tools").mkdir(mode=0o700)
        (root / "legacy").mkdir(mode=0o700)
        for name in FILES:
            (self.home / name).write_text("raise AssertionError('sentinel imported')\n")
        (self.home / "surfd.py").write_text("DROP_FD = %r\n" % drop_fd + WSGI)
        (self.home / "candidate.py").write_text(CANDIDATE)
        (root / "launcher.py").write_text(LAUNCHER)
        (root / "witness.py").write_text(WITNESS)
        (root / "config.py").write_text("# Fixed empty synthetic config.\n")
        save(root / "settings.json", {"dependencies": str(dependencies)})
        self.hashes = {name: digest(self.home / name) for name in FILES}
        save(root / "manifest.json", {"generation": GENERATION,
             "source_home": str(self.home), "hashes": self.hashes,
             "routes": {"server": [str(Path(sys.executable).resolve()), "-I",
                                    str(self.home / "candidate.py")]}})
        self.run("init", "--manifest", str(root / "manifest.json"))
        closure = json.loads((root / "guard/state.json").read_text())["closure"]
        save(root / "candidate-grant.json", {"generation": GENERATION,
             "closure": closure, "route": "server", "authorized": True})
        import types
        dispatch = types.ModuleType("synthetic_dispatch_renderer")
        exec(compile(DISPATCH.read_bytes(), str(DISPATCH), "exec"), dispatch.__dict__)
        wrapper = dispatch.render_wrapper(dispatch_path=str(DISPATCH),
            dispatch_sha256=digest(DISPATCH), guard_path=str(GUARD),
            guard_sha256=digest(GUARD), state_dir=str(root / "guard"),
            generation=GENERATION, source_relative="surfd.py")
        (root / "legacy/surfd.py").write_bytes(wrapper)
        check((root / "legacy/surfd.py").read_bytes() == wrapper, "wrapper bytes changed")
        save(root / "bindings.json", {"wrapper_sha256": digest(root / "legacy/surfd.py"),
             "dispatch_sha256": digest(DISPATCH), "guard_sha256": digest(GUARD),
             "hashes": self.hashes})

    def argv(self, *args, timeout=2):
        return [str(Path(sys.executable).resolve()), "-I", str(GUARD), "--state-dir",
                str(self.root / "guard"), "--timeout", str(timeout), *args]

    def run(self, *args, ok=True, timeout=2):
        argv = self.argv(*args, timeout=timeout)
        result = bounded_command(argv, timeout=timeout + 4, env=ENV)
        check(len(result.stdout) + len(result.stderr) <= 65536, "guard output exceeded bound")
        self.commands.append({"argv": argv, "returncode": result.returncode,
                              "stdout": result.stdout, "stderr": result.stderr,
                              "expected_failure_control": not ok})
        check(result.returncode == (0 if ok else 2), "unexpected guard result: " + str(result))
        return result

    def events(self, event=None):
        path = self.root / "events.jsonl"
        data = path.read_text() if path.exists() else ""
        check(len(data) <= 262144, "witness log exceeded bound")
        records = [json.loads(line) for line in data.splitlines(keepends=True)
                   if line.endswith("\n")]
        return [r for r in records if event is None or r["event"] == event]

    def spawn(self, argv, logname, cwd):
        with (self.root / logname).open("w") as log:
            process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=log,
                                       stderr=subprocess.STDOUT, cwd=cwd, env=ENV)
        record = identity(process.pid)
        check(record is not None, "process vanished before identity capture")
        self.commands.append({"argv": argv, "cwd": str(cwd), "process": record})
        return process, record

    def bootstrap_open(self):
        self.bootstrap, self.bootstrap_identity = self.spawn(
            self.argv("candidate", "--generation", GENERATION, "--route", "server",
                      "--authorization", str(self.root / "candidate-grant.json")),
            "candidate.log", self.home)
        wait_for(lambda: (self.root / "b.sock").exists(), "bootstrap socket")
        raw = self.read_response(self.connect("/ready", "b.sock"))
        check(raw.split(b"\r\n\r\n", 1)[1] == b"SYNTHETIC CANDIDATE READY\n",
              "candidate readiness did not act")
        record = json.loads((self.root / "guard/candidate.json").read_text())
        state = json.loads((self.root / "guard/state.json").read_text())
        check(record["process"]["pid"] == self.bootstrap.pid and
              record["process"]["start"] == self.bootstrap_identity["start"] and
              record["process"]["cwd"] == str(self.home) and
              os.readlink(f"/proc/{self.bootstrap.pid}/cwd") == str(self.home) and
              record["closure"] == state["closure"] and
              matching_fds(self.bootstrap.pid, self.root / "guard/candidate.lock") and
              contended(self.root / "guard/candidate.lock"), "bootstrap binding mismatch")
        save(self.root / "SYNTHETIC-NOT-ATTESTATION.json", {"generation": GENERATION,
             "closure": record["closure"], "source_home": str(self.home),
             "hashes": self.hashes, "schema": 19, "accepted": True,
             "process": record["process"]})
        self.run("reopen", "--generation", GENERATION, "--receipt",
                 str(self.root / "SYNTHETIC-NOT-ATTESTATION.json"))
        self.stop_bootstrap()
        check(json.loads((self.root / "guard/state.json").read_text())["admission"] == "OPEN",
              "bootstrap did not stop while OPEN")
        check(not contended(self.root / "guard/candidate.lock"), "bootstrap leaked lock")

    def stop_bootstrap(self):
        if self.bootstrap is not None:
            if self.bootstrap.poll() is None:
                self.signal_exact(self.bootstrap, self.bootstrap_identity, signal.SIGTERM)
            check(self.bootstrap.wait(timeout=5) == 0, "bootstrap unsuccessful exit")
            check(not (self.root / "b.sock").exists(), "bootstrap socket leaked")

    def start(self):
        self.master, self.master_identity = self.spawn(
            [str(Path(sys.executable).resolve()), "-I", str(self.root / "launcher.py")],
            "gunicorn.log", self.root / "legacy")
        worker = wait_for(lambda: self.events("import"), "actual real WSGI import")[0]
        check(worker["ppid"] == self.master.pid and same_process(worker), "wrong worker author")
        check(not matching_fds(self.master.pid, self.root / "guard/admission.lock"),
              "legacy master unexpectedly owns admission lock")
        check(not matching_fds(self.master.pid, self.root / "guard/candidate.lock"),
              "legacy master inherited candidate lock")
        wait_for(lambda: (self.root / "g.sock").exists(), "legacy Unix bind")
        return worker

    def connect(self, path, name="g.sock"):
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(5)
        try:
            connection.connect(str(self.root / name))
            connection.sendall(("GET " + path + " HTTP/1.0\r\nHost: synthetic\r\n\r\n").encode())
            return connection
        except BaseException:
            connection.close()
            raise

    def read_response(self, connection):
        chunks, size = [], 0
        deadline = time.monotonic() + 5
        try:
            while True:
                remaining = deadline - time.monotonic()
                check(remaining > 0, "bounded response timeout")
                connection.settimeout(remaining)
                chunk = connection.recv(8192)
                if not chunk:
                    break
                size += len(chunk)
                check(size <= 65536, "response exceeded bound")
                chunks.append(chunk)
        finally:
            connection.close()
        return b"".join(chunks)

    def response(self, connection, path):
        raw = self.read_response(connection)
        expected = ("SYNTHETIC LEGACY " + path + " " + str(self.home / "surfd.py") + "\n").encode()
        check(raw.startswith(b"HTTP/1.0 200 OK\r\n") and
              raw.split(b"\r\n\r\n", 1)[1] == expected, "real served origin response missing")
        wait_for(lambda: any(r.get("path") == path for r in self.events("complete")),
                 "real request completed " + path)
        (self.root / (path.strip("/") + ".response")).write_bytes(raw)

    def request(self, path):
        self.response(self.connect(path), path)

    def oracle(self, worker):
        check(same_process(worker) and same_process(self.master_identity), "lifetime unmeasurable")
        lock = self.root / "guard/admission.lock"
        fds = matching_fds(worker["pid"], lock)
        flags = []
        for fd in fds:
            info = Path(f"/proc/{worker['pid']}/fdinfo/{fd}").read_text()
            flags.append(int(next(line.split()[1] for line in info.splitlines()
                                  if line.startswith("flags:")), 8))
        observation = {"master": self.master_identity, "worker": worker,
                       "worker_fds": fds, "flags": flags,
                       "master_fds": matching_fds(self.master.pid, lock),
                       "exclusive_contended": contended(lock),
                       "lock_device": lock.stat().st_dev, "lock_inode": lock.stat().st_ino}
        observation["cooperative_lifetime"] = bool(len(fds) == 1 and
            all(flag & os.O_ACCMODE == os.O_RDONLY and not flag & os.O_CLOEXEC for flag in flags)
            and observation["exclusive_contended"])
        return observation

    def close_busy(self):
        result = self.run("close", timeout=.2, ok=False)
        check("CLOSED DURABLE" in result.stdout and "timeout" in result.stderr,
              "close did not durably act and time out")
        check(json.loads((self.root / "guard/state.json").read_text())["admission"] == "CLOSED",
              "state not CLOSED")

    @staticmethod
    def signal_exact(process, record, sig):
        check(process.poll() is None and same_process(record), "refuse stale identity signal")
        process.send_signal(sig)

    def finish(self):
        if self.finished:
            return
        (self.root / "release").touch(mode=0o600)
        self.stop_bootstrap()
        if self.master is not None:
            if self.master.poll() is None:
                self.signal_exact(self.master, self.master_identity, signal.SIGTERM)
            self.master.wait(timeout=12)
        if self.held_socket is not None:
            self.held_socket.close()
            self.held_socket = None
        check(self.master_identity is None or not same_process(self.master_identity),
              "exact master identity survived wait")
        check(self.bootstrap_identity is None or not same_process(self.bootstrap_identity),
              "exact bootstrap identity survived wait")
        bindings = json.loads((self.root / "bindings.json").read_text())
        check(digest(self.root / "legacy/surfd.py") == bindings["wrapper_sha256"] and
              digest(DISPATCH) == bindings["dispatch_sha256"] and
              digest(GUARD) == bindings["guard_sha256"] and
              {name: digest(self.home / name) for name in FILES} == bindings["hashes"],
              "raw wrapper/helper/runtime changed during arm")
        workers = self.events("import_attempt")
        wait_for(lambda: not any(same_process(r) for r in workers), "owned worker identities reaped")
        check(not (self.root / "g.sock").exists(), "legacy socket leaked")
        check(not contended(self.root / "guard/admission.lock") and
              not contended(self.root / "guard/candidate.lock"), "lock leaked after exit")
        for name in ("candidate.log", "gunicorn.log"):
            path = self.root / name
            if path.exists():
                check(path.stat().st_size <= 262144, "gunicorn log exceeded bound")
        save(self.root / "cleanup.json", {"master": self.master_identity,
             "master_returncode": self.master.returncode if self.master else None,
             "bootstrap": self.bootstrap_identity, "workers": workers,
             "remaining_exact_identities": [], "sockets_absent": True,
             "exclusive_locks_available": True, "raw_bindings_unchanged": True,
             "no_signal_escalation": True})
        self.finished = True


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def suite(out, dependencies, commands, fixtures):
    for name, replacement in (("h", "hup"), ("a", "maxrequests")):
        good = Fixture(out / name, dependencies, False, commands)
        fixtures.append(good)
        good.bootstrap_open()
        worker = good.start()
        good.request("/initial")
        initial = good.oracle(worker)
        check(initial["cooperative_lifetime"], "worker read-only inheritable lock missing")
        save(good.root / "initial-oracle.json", initial)
        if replacement == "maxrequests":
            # Three completed requests; /held is the fourth and triggers recycle.
            good.request("/two")
            good.request("/three")
        good.held_socket = good.connect("/held")
        held = wait_for(lambda: good.events("held"), "held request ACTED")[0]
        check(held["pid"] == worker["pid"], "wrong held request worker")
        good.close_busy()
        before = good.events()
        refused = good.run("launch", "--generation", GENERATION, "--route", "server", ok=False)
        check("CLOSED: application interpreter not started" in refused.stderr and
              good.events() == before, "fresh root launch did not refuse before effects")
        if replacement == "hup":
            good.signal_exact(good.master, good.master_identity, signal.SIGHUP)
            failure = wait_for(lambda: good.events("import_refused"), "CLOSED HUP import refusal")[0]
            check(failure["ppid"] == good.master.pid and failure["pid"] != worker["pid"] and
                  "admission not OPEN" in failure["error"], "HUP wrong refusal")
        check(len(good.events("import")) == 1, "CLOSED replacement reached real module")
        check(good.master.poll() is None and same_process(worker), "held worker prematurely exited")
        check(not any(r.get("path") == "/held" for r in good.events("complete")),
              "held request completed without release")
        held_oracle = good.oracle(worker)
        check(held_oracle["cooperative_lifetime"], "held worker lost lock")
        save(good.root / "held-oracle.json", held_oracle)
        good.close_busy()
        (good.root / "release").touch(mode=0o600)
        good.response(good.held_socket, "/held")
        good.held_socket = None
        if replacement == "maxrequests":
            failure = wait_for(lambda: good.events("import_refused"),
                               "CLOSED automatic replacement refusal", timeout=10)[0]
            check(failure["ppid"] == good.master.pid and failure["pid"] != worker["pid"] and
                  "admission not OPEN" in failure["error"], "maxrequests wrong refusal")
        check(len(good.events("import")) == 1, "replacement executed real module")
        good.master.wait(timeout=10)
        check(good.master.returncode != 0, "expected worker boot refusal not reflected in exit")
        good.finish()
        good.run("close")
        save(good.root / "expected-failures.json", {
            "controls": ["close durably CLOSED but drain timeout while held",
                         "fresh ordinary root launch refused before interpreter",
                         replacement + " worker attempted wrapper but refused before real module"],
            "real_imports": len(good.events("import")),
            "refused_workers": good.events("import_refused")})

    fresh = Fixture(out / "f", dependencies, False, commands)
    fixtures.append(fresh)
    fresh.bootstrap_open()
    fresh.run("close")
    fresh.master, fresh.master_identity = fresh.spawn(
        [str(Path(sys.executable).resolve()), "-I", str(fresh.root / "launcher.py")],
        "gunicorn.log", fresh.root / "legacy")
    refused = wait_for(lambda: fresh.events("import_refused"), "fresh CLOSED legacy worker refusal")[0]
    check(refused["ppid"] == fresh.master.pid and "admission not OPEN" in refused["error"] and
          not fresh.events("import"), "fresh legacy worker reached real source while CLOSED")
    fresh.master.wait(timeout=10)
    check(fresh.master.returncode != 0, "fresh CLOSED master did not report boot refusal")
    fresh.finish()
    save(fresh.root / "expected-failures.json", {"controls": [
        "fresh unguarded legacy master started; actual worker wrapper refused before real import"],
        "refused_workers": fresh.events("import_refused")})

    bad = Fixture(out / "d", dependencies, True, commands)
    fixtures.append(bad)
    bad.bootstrap_open()
    worker = bad.start()
    bad.request("/intentional-drop")
    check(worker["before"] and worker["dropped"] and not worker["fds"], "FD drop did not act")
    negative = bad.oracle(worker)
    check(not negative["cooperative_lifetime"] and not negative["exclusive_contended"] and
          not negative["worker_fds"] and not negative["master_fds"], "drop oracle not discriminating")
    save(bad.root / "expected-negative-oracle.json", negative)
    drained = bad.run("close")
    check("DRAINED" in drained.stdout and bad.master.poll() is None, "negative drain did not act")
    bad.request("/bypass-still-serving")
    save(bad.root / "expected-failures.json", {"controls": [
        "EXPECTED lifetime oracle FAIL: authored real WSGI dropped its admission FD",
        "exclusive drain succeeds although the same worker still serves after CLOSED"]})
    bad.finish()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--gunicorn-path", required=True)
    parser.add_argument("--host-distro", action="store_true",
                        help="actual installed Debian bytes, not same-version upstream equivalence")
    parser.add_argument("--gunicorn-version", required=True, choices=("20.1.0", "23.0.0"))
    args = parser.parse_args()
    try:
        out, dependencies, provenance = preflight(args)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2
    os.umask(0o077)
    out.mkdir(mode=0o700)
    owner = out / "OWNER.md"
    owner.write_text("# Synthetic legacy gunicorn dispatch gate\n"
        "Owner: invoking test operator/dispatch test worker; UTC " + time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + "\n"
        "Parent ownership: " + provenance["owner_file"] + "\n"
        "Base: a9dce85f27f94b6c89672b6b63fc5659801ebe4c; provenance pins exact helper/test bytes.\n"
        "Owned: this root, authored fixtures, exact Popen identities and their workers.\n"
        "Status active. No real surfd/home/config/DB imports, TCP, installs or live actions.\n"
        "Retain logs/source for review; gracefully stop only exact owned children, no SIGKILL.\n")
    global GUARD, DISPATCH
    for name in ("GUARD", "DISPATCH"):
        original = globals()[name]
        target = out / original.name
        target.write_bytes(original.read_bytes())
        target.chmod(0o600)
        check(target.read_bytes() == original.read_bytes() and
              stat.S_IMODE(target.stat().st_mode) == 0o600, "helper copy mismatch")
        globals()[name] = target
    provenance["dispatch_sha256"] = digest(DISPATCH)
    commands, fixtures, errors = [], [], []
    save(out / "provenance.json", provenance)
    try:
        suite(out, dependencies, commands, fixtures)
    except Exception as exc:
        errors.append(str(exc))
    finally:
        for fixture in fixtures:
            try:
                fixture.finish()
            except Exception as exc:
                errors.append("CLEANUP FAILED " + str(fixture.root) + ": " + str(exc))
                save(fixture.root / "cleanup-failure.json", {"master": fixture.master_identity,
                     "bootstrap": fixture.bootstrap_identity, "error": str(exc),
                     "no_escalation": "No SIGKILL or discovered-PID signals"})
        save(out / "commands.json", commands)
    check(not list(out.rglob("*.pyc")), "unexpected fixture bytecode")
    result = {"verdict": "FAIL" if errors else "PASS", "errors": errors,
              "limits": "Synthetic actual-gunicorn gthread2 legacy module/candidate/lifetime only. "
              "Installed distro and upstream-pin provenance are distinct, not equivalent. "
              "Not live app/schema acceptance, no-loss, installer coverage or a sandbox. "
              "Shared trusted same-UID cooperation is required; FD-drop control proves this limit."}
    save(out / "result.json", result)
    with owner.open("a") as stream:
        stream.write("Status retained: " + result["verdict"] + "; see cleanup evidence for exact children.\n")
    print(json.dumps(result))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
