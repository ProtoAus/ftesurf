#!/usr/bin/env python3
"""Local synthetic gunicorn lifetime falsifier, not an installation/acceptance driver.

Predictions: inherited candidate-lifetime FDs block exclusive drain through HUP and automatic
worker recycling, even while CLOSED. Graceful shutdown retains an in-flight request
until release. An intentional FD-drop control serves while drain succeeds and must
FAIL the same lifetime oracle. No real application modules or TCP sockets are used.
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
GENERATION = "1" * 40
FILES = ("surfd.py", "ksfimport.py", "ksfgrab.py", "ksfprofile.py",
         "tools/ksfconvert.py", "tools/ksfreplay_info.py")
ENV = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}

# Authored once per NEW fixture; only fixed argv below can run it.
LAUNCHER = '''import json
import os
from pathlib import Path
import sys
sys.dont_write_bytecode = True
root = Path(__file__).resolve().parent
settings = json.loads((root / "settings.json").read_text())
sys.path.insert(0, settings["dependencies"])
sys.path.insert(0, str(root))
from witness import emit, admission_fds
before = admission_fds()
if settings["drop_fd"]:
    for fd in before:
        os.close(fd)
emit("master", before=before, dropped=settings["drop_fd"])
from gunicorn.app.wsgiapp import run
sys.argv = ["synthetic-gunicorn", "--config", str(root / "synthetic_config.py"),
            "--bind", "unix:" + str(root / "g.sock"),
            "--worker-class", "gthread", "--threads", "2", "--workers", "1",
            "--max-requests", "4", "--max-requests-jitter", "0",
            "--timeout", "30", "--graceful-timeout", "20", "--umask", "0077",
            "--worker-tmp-dir", str(root), "--access-logfile", "-",
            "--error-logfile", "-", "synthetic_wsgi:app"]
run()
'''

WITNESS = '''import json
import os
from pathlib import Path
root = Path(__file__).resolve().parent

def admission_fds():
    lock = (root / "guard" / "candidate.lock").stat()
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
    data = dict(event=event, pid=os.getpid(), ppid=os.getppid(), start=start,
                fds=admission_fds(), **extra)
    fd = os.open(root / "events.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, (json.dumps(data) + "\\n").encode())
    finally:
        os.close(fd)
'''

WSGI = '''from pathlib import Path
import time
from witness import emit
root = Path(__file__).resolve().parent
emit("import")

def app(environ, start_response):
    path = environ["PATH_INFO"]
    emit("request", path=path)
    if path == "/held":
        emit("held")
        deadline = time.monotonic() + 12
        while not (root / "release").exists():
            if time.monotonic() >= deadline:
                raise RuntimeError("synthetic held request release timeout")
            time.sleep(.02)
    body = ("SYNTHETIC RESPONSE " + path + "\\n").encode()
    start_response("200 OK", [("Content-Type", "text/plain"),
                              ("Content-Length", str(len(body)))])
    yield body
    emit("complete", path=path)
'''


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


class Fixture:
    def __init__(self, root, dependencies, drop_fd, commands):
        self.root = root
        self.commands = commands
        self.master = None
        self.master_identity = None
        self.held_socket = None
        root.mkdir(mode=0o700)
        (root / "tools").mkdir(mode=0o700)
        for name in FILES:
            (root / name).write_text("# Synthetic sentinel; never imported.\n")
        (root / "launcher.py").write_text(LAUNCHER)
        (root / "witness.py").write_text(WITNESS)
        (root / "synthetic_wsgi.py").write_text(WSGI)
        (root / "synthetic_config.py").write_text("# Fixed empty synthetic configuration.\n")
        save(root / "settings.json", {"dependencies": str(dependencies), "drop_fd": drop_fd})
        self.hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                       for name in FILES}
        manifest = {"generation": GENERATION, "source_home": str(root),
                    "hashes": self.hashes,
                    "routes": {"server": [str(Path(sys.executable).resolve()),
                                             "-I", str(root / "launcher.py")]}}
        save(root / "manifest.json", manifest)
        self.run("init", "--manifest", str(root / "manifest.json"))
        closure = json.loads((root / "guard/state.json").read_text())["closure"]
        save(root / "candidate-grant.json",
             {"generation": GENERATION, "closure": closure,
              "route": "server", "authorized": True})

    def argv(self, *args, timeout=2):
        return [sys.executable, "-I", str(GUARD), "--state-dir", str(self.root / "guard"),
                "--timeout", str(timeout), *args]

    def run(self, *args, ok=True, timeout=2):
        argv = self.argv(*args, timeout=timeout)
        result = subprocess.run(argv, capture_output=True, text=True, env=ENV,
                                timeout=timeout + 4)
        self.commands.append({"argv": argv, "returncode": result.returncode,
                              "stdout": result.stdout, "stderr": result.stderr})
        check(result.returncode == (0 if ok else 2), "unexpected guard result: " + str(result))
        return result

    def events(self, event=None):
        path = self.root / "events.jsonl"
        # A single append is authored per line. Ignore only a currently partial final line.
        data = path.read_text() if path.exists() else ""
        records = [json.loads(line) for line in data.splitlines(keepends=True)
                   if line.endswith("\n")]
        return [r for r in records if event is None or r["event"] == event]

    def start(self):
        with (self.root / "gunicorn.log").open("w") as log:
            self.master = subprocess.Popen(self.argv("candidate", "--generation", GENERATION,
                                                    "--route", "server", "--authorization",
                                                    str(self.root / "candidate-grant.json")),
                                           stdin=subprocess.DEVNULL, stdout=log,
                                           stderr=subprocess.STDOUT, env=ENV)
        self.master_identity = identity(self.master.pid)
        check(self.master_identity is not None, "master vanished before identity capture")
        worker = wait_for(lambda: self.events("import"), "actual WSGI import")[0]
        check(worker["ppid"] == self.master.pid and same_process(worker),
              "import is not from the owned master's worker")
        wait_for(lambda: (self.root / "g.sock").exists(), "Unix socket bind")
        return worker

    def accept(self, ok=True):
        record = json.loads((self.root / "guard/candidate.json").read_text())
        save(self.root / "SYNTHETIC-NOT-ATTESTATION.json",
             {"generation": GENERATION, "closure": record["closure"],
              "source_home": str(self.root), "hashes": self.hashes,
              "schema": 19, "accepted": True, "process": record["process"]})
        return self.run("reopen", "--generation", GENERATION, "--receipt",
                        str(self.root / "SYNTHETIC-NOT-ATTESTATION.json"), ok=ok)

    def request_start(self, path):
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(5)
        try:
            connection.connect(str(self.root / "g.sock"))
            connection.sendall(("GET " + path + " HTTP/1.0\r\nHost: synthetic\r\n\r\n").encode())
            return connection
        except Exception:
            connection.close()
            raise

    def response(self, connection, path):
        try:
            chunks = []
            size = 0
            deadline = time.monotonic() + 5
            while True:
                remaining = deadline - time.monotonic()
                check(remaining > 0, "bounded response timeout")
                connection.settimeout(remaining)
                chunk = connection.recv(8192)
                if not chunk:
                    break
                size += len(chunk)
                check(size <= 65536, "synthetic response exceeded bound")
                chunks.append(chunk)
        finally:
            connection.close()
        raw = b"".join(chunks)
        check(raw.startswith(b"HTTP/1.0 200 OK\r\n") and
              raw.split(b"\r\n\r\n", 1)[1] == ("SYNTHETIC RESPONSE " + path + "\n").encode(),
              "authored WSGI response missing: " + repr(raw))
        wait_for(lambda: any(r.get("path") == path for r in self.events("complete")),
                 "request completion witness " + path)
        (self.root / (path.strip("/") + ".response")).write_bytes(raw)

    def request(self, path):
        self.response(self.request_start(path), path)

    def oracle(self, worker):
        check(same_process(self.master_identity) and same_process(worker),
              "cannot measure lifetime on vanished identities")
        lock = self.root / "guard/candidate.lock"
        observation = {"master": self.master_identity, "worker": worker,
                       "master_fds": matching_fds(self.master.pid, lock),
                       "worker_fds": matching_fds(worker["pid"], lock),
                       "exclusive_contended": contended(lock),
                       "lock_device": lock.stat().st_dev, "lock_inode": lock.stat().st_ino}
        observation["cooperative_lifetime"] = bool(observation["master_fds"] and
                                                   observation["worker_fds"] and
                                                   observation["exclusive_contended"])
        return observation

    def closed(self):
        check(json.loads((self.root / "guard/state.json").read_text())["admission"] == "CLOSED",
              "closure was not persisted")

    def signal_master(self, sig):
        check(self.master.poll() is None and same_process(self.master_identity),
              "refuse signal to vanished/reused master identity")
        self.master.send_signal(sig)

    def finish(self):
        (self.root / "release").touch(mode=0o600)
        if self.master is not None:
            if self.master.poll() is None:
                self.signal_master(signal.SIGTERM)
            check(self.master.wait(timeout=10) == 0, "gunicorn master exited unsuccessfully")
        if self.held_socket is not None:
            self.held_socket.close()
            self.held_socket = None
        workers = self.events("import")
        wait_for(lambda: not any(same_process(r) for r in workers), "exact worker identities reaped")
        check(not (self.root / "g.sock").exists(), "gunicorn socket survived shutdown")
        check(not contended(self.root / "guard/candidate.lock"), "candidate FD leaked after exit")
        save(self.root / "cleanup.json", {"master": self.master_identity,
             "master_returncode": self.master.returncode if self.master else None,
             "workers": workers, "remaining_exact_identities": [r for r in workers if same_process(r)],
             "socket_absent": True, "exclusive_lock_available": True})


def suite(out, dependencies, commands, fixtures):
    good = Fixture(out / "c", dependencies, False, commands)
    fixtures.append(good)
    worker = good.start()
    good.request("/initial")
    good.accept()
    first = good.oracle(worker)
    check(first["cooperative_lifetime"], "foreground master/worker did not retain admission FD")
    save(good.root / "initial-oracle.json", first)
    result = good.run("close", timeout=.2, ok=False)
    check("CLOSED DURABLE" in result.stdout and "timeout" in result.stderr,
          "close did not act and time out")
    good.closed()
    check(good.master.poll() is None, "master exited during bounded close")
    before = good.events()
    refusal = good.run("launch", "--generation", GENERATION, "--route", "server", ok=False)
    check("CLOSED: application interpreter not started" in refusal.stderr and good.events() == before,
          "fresh guarded launch failed pre-import refusal oracle")

    good.signal_master(signal.SIGHUP)
    imports = wait_for(lambda: good.events("import") if len(good.events("import")) >= 2 else None,
                       "HUP replacement imported WHILE CLOSED")
    hup_worker = imports[-1]
    check(hup_worker["pid"] != worker["pid"] and hup_worker["ppid"] == good.master.pid,
          "HUP did not create a new owned worker")
    wait_for(lambda: not same_process(worker), "HUP old worker reaped")
    good.closed()
    good.request("/hup-closed")
    hup_oracle = good.oracle(hup_worker)
    check(hup_oracle["cooperative_lifetime"], "HUP replacement lost FD while CLOSED")
    save(good.root / "hup-oracle.json", hup_oracle)
    # Four total requests in this generation force pinned gunicorn's automatic recycle.
    for number in range(3):
        good.request("/automatic-" + str(number))
    imports = wait_for(lambda: good.events("import") if len(good.events("import")) >= 3 else None,
                       "max-requests replacement import", timeout=10)
    auto_worker = imports[-1]
    check(auto_worker["pid"] != hup_worker["pid"] and auto_worker["ppid"] == good.master.pid,
          "automatic recycle did not create an owned worker")
    wait_for(lambda: not same_process(hup_worker), "automatic old worker reaped")
    good.closed()
    good.request("/automatic-closed")
    auto_oracle = good.oracle(auto_worker)
    check(auto_oracle["cooperative_lifetime"], "automatic replacement lost admission FD")
    save(good.root / "automatic-oracle.json", auto_oracle)

    good.held_socket = good.request_start("/held")
    held = wait_for(lambda: good.events("held"), "actual in-flight held request")[0]
    check(held["pid"] == auto_worker["pid"], "held request has unexpected author")
    good.signal_master(signal.SIGTERM)
    wait_for(lambda: "Handling signal: term" in (good.root / "gunicorn.log").read_text(),
             "master graceful shutdown acted")
    try:
        good.master.wait(timeout=.3)
    except subprocess.TimeoutExpired:
        pass
    else:
        raise RuntimeError("master exited before synthetic request release")
    check(not any(r.get("path") == "/held" for r in good.events("complete")),
          "held request completed before release")
    shutdown_oracle = good.oracle(auto_worker)
    check(shutdown_oracle["cooperative_lifetime"], "shutdown released FD before request")
    save(good.root / "shutdown-held-oracle.json", shutdown_oracle)
    result = good.run("close", timeout=.2, ok=False)
    check("timeout" in result.stderr, "drain succeeded before held request release")
    (good.root / "release").touch(mode=0o600)
    good.response(good.held_socket, "/held")
    good.held_socket = None
    good.finish()
    good.run("close")
    good.closed()

    bad = Fixture(out / "d", dependencies, True, commands)
    fixtures.append(bad)
    bad_worker = bad.start()
    bad.request("/intentional-drop")
    rejection = bad.accept(ok=False)
    check("candidate lifetime lock is not held" in rejection.stderr,
          "FD-dropping candidate was not rejected at acceptance")
    master_witness = bad.events("master")[0]
    check(master_witness["before"] and master_witness["dropped"] and not master_witness["fds"],
          "intentional inherited FD drop did not act")
    negative = bad.oracle(bad_worker)
    check(not negative["cooperative_lifetime"] and not negative["master_fds"] and
          not negative["worker_fds"] and not negative["exclusive_contended"],
          "lifetime oracle failed to discriminate intentional FD drop")
    save(bad.root / "negative-oracle.json", negative)
    drained = bad.run("close")
    check("DRAINED" in drained.stdout and bad.master.poll() is None, "negative drain did not act")
    bad.closed()
    bad.request("/bypass-still-serving")
    bad.finish()


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
        out = canonical(args.out)
        check(not out.exists() and out.parent.is_dir(), "--out must be NEW with existing parent")
        owners = [p / "OWNER.md" for p in out.parents if (p / "OWNER.md").is_file()]
        check(owners and not owners[0].is_symlink() and
              owners[0].stat().st_uid == os.geteuid(), "unsafe/missing OWNER.md")
        for part in (out.parent, *out.parent.parents):
            check(part.stat().st_uid == os.geteuid() or not (part.stat().st_mode & 0o022),
                  "foreign writable output ancestor refused")
        check(len(os.fsencode(str(out / "c/g.sock"))) < 108, "Unix socket path too long")
        distro = subprocess.run(["dpkg-query", "-W", "-f=${Version}", "gunicorn"],
                                capture_output=True, text=True, timeout=10, check=True)
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--gunicorn-path", required=True)
    parser.add_argument("--host-distro", action="store_true",
                        help="test actual installed Debian bytes, explicitly not an upstream pin")
    parser.add_argument("--gunicorn-version", choices=("20.1.0", "23.0.0"), default="23.0.0",
                        help="explicit upstream pin; never identifies host distro-patched bytes")
    args = parser.parse_args()
    try:
        out, dependencies, provenance = preflight(args)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2
    os.umask(0o077)
    out.mkdir(mode=0o700)
    (out / "OWNER.md").write_text(
        "# Synthetic guarded gunicorn candidate lifetime test\n\n"
        "Owner: invoking agent/operator; parent ownership: " + provenance["owner_file"] +
        "\nOwn fixture sources, exact Popen master/worker identities and logs here. "
        "No application imports/production data or TCP sockets. Retain provenance and "
        "failure evidence; finally gracefully stops only owned masters and checks workers.\n")
    commands = []
    fixtures = []
    errors = []
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
                save(fixture.root / "cleanup-failure.json",
                     {"master": fixture.master_identity, "workers": fixture.events("import"),
                      "error": str(exc), "no_escalation": "No SIGKILL or discovered-PID signals"})
        save(out / "commands.json", commands)
    result = {"verdict": "FAIL" if errors else "PASS", "errors": errors,
              "limits": "Synthetic local gunicorn gthread2 candidate only; dependency provenance records "
                        "upstream pin versus actual installed distro. Not live launch coverage, "
                        "installation permission, pre-drain worker exclusion, or attestation. "
                        "CLOSED permits existing-generation HUP/max-requests imports; drain first."}
    save(out / "result.json", result)
    print(json.dumps(result))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
