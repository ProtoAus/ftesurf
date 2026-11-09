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


FILES = frozenset({"surfd.py", "ksfimport.py", "ksfgrab.py", "ksfprofile.py",
                   "tools/ksfconvert.py", "tools/ksfreplay_info.py"})
# Explicit schema23 also seals the bounded account-viewmodel module.
# Older generations keep their exact original dependency sets and defaults.
SCHEMA_FILES = {19: FILES, 20: FILES | {"accounts.py", "social.py"},
                22: FILES | {"accounts.py", "social.py"},
                23: FILES | {"accounts.py", "social.py", "viewmodel.py"},
                24: FILES | {"accounts.py", "social.py", "viewmodel.py"},
                25: FILES | {"accounts.py", "social.py", "viewmodel.py", "inventory.py"},
                26: FILES | {"accounts.py", "social.py", "viewmodel.py", "inventory.py", "playstats.py"}}


CURRENT_FAMILY_FILES = frozenset(['accounts.py', 'admin.py', 'b65stub.py', 'b66stub.py', 'hidupload.py', 'ksfgrab.py', 'ksfimport.py', 'ksfprofile.py', 'ksftopup.py', 'mapmanifest.py', 'mapwatch.py', 'mkadminpw.py', 'momboards.py', 'momdates.py', 'momfetch.py', 'momgrab.py', 'momindex.py', 'momrequest.py', 'momwatch.py', 'msml.py', 'p357board.py', 'p371stub.py', 'rcon.py', 'recplot.py', 'simcheck.py', 'social.py', 'steam.py', 'steamsync.py', 'surfd.py', 'sweep.py', 'templates/_admin_style.html', 'templates/admin.html', 'templates/admin_accounts.html', 'templates/admin_login.html', 'templates/admin_maps.html', 'templates/admin_run.html', 'templates/admin_runs.html', 'test_accounts.py', 'test_admin.py', 'test_admin_association_bounds.py', 'test_admin_log_bounds.py', 'test_admin_metrics.py', 'test_admin_similarity.py', 'test_board.py', 'test_evidence.py', 'test_join.py', 'test_ksfimport.py', 'test_mappool.py', 'test_momboards.py', 'test_momgrab.py', 'test_momindex.py', 'test_momrequest.py', 'test_ranked.py', 'test_receipt_angle_reasons.py', 'test_receipt_identity.py', 'test_receipt_late_hid.py', 'test_receipt_late_rec.py', 'test_receipt_late_view.py', 'test_recplot.py', 'test_recplot_budget.py', 'test_recsim_observations.py', 'test_replays.py', 'test_simcheck.py', 'test_surfd.py', 'test_sweep.py', 'test_verifier_counts.py', 'test_verifier_finish.py', 'test_verifier_sources.py', 'test_web.py', 'tools/ksfconvert.py', 'tools/ksfreplay_info.py', 'viewmodel.py', 'web/board.css', 'web/board.html', 'web/board.js', 'web/link.css', 'web/runview.js', 'web/watch.css', 'web/watch.html', 'web/watch.js', 'zonefit.py'])

def target_schema(m):
    # Keyless manifests retain their original schema19 meaning; never infer from receipts.
    schema = m.get("target_schema", 19)
    require(type(schema) is int and schema in SCHEMA_FILES, "unsupported target_schema")
    return schema


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
    keys = {"generation", "source_home", "hashes", "routes"}
    optional = {"target_schema", "runtime_profile", "external_python"}
    require(type(m) is dict and keys <= set(m) <= keys | optional, "malformed manifest")
    schema = target_schema(m)
    files = SCHEMA_FILES[schema]
    if "runtime_profile" in m:
        if m["runtime_profile"] == "current81-v1":
            require(schema == 24, "current81-v1 requires explicit schema24")
            files = CURRENT_FAMILY_FILES
        elif m["runtime_profile"] == "inventory82-v1":
            require(schema == 25, "inventory82-v1 requires explicit schema25")
            files = CURRENT_FAMILY_FILES | {"inventory.py"}
        elif m["runtime_profile"] == "activity83-v1":
            require(schema == 26, "activity83-v1 requires explicit schema26")
            files = CURRENT_FAMILY_FILES | {"inventory.py", "playstats.py"}
        elif m["runtime_profile"] == "collectors84-v1":
            # P1234: P1117's momprofile.py (surfd.py, accounts.py, momwatch.py, steamsync.py).
            require(schema == 26, "collectors84-v1 requires explicit schema26")
            files = CURRENT_FAMILY_FILES | {"inventory.py", "playstats.py", "momprofile.py"}
        elif m["runtime_profile"] == "fetch85-v1":
            require(schema == 26, "fetch85-v1 requires explicit schema26")
            files = CURRENT_FAMILY_FILES | {"inventory.py", "playstats.py", "momprofile.py", "fetchq.py"}
        else:
            require(schema in (20, 22, 23, 24, 25, 26) and m["runtime_profile"] == "hid-v1", "unsupported runtime_profile")
            files = files | {"hidupload.py"}
    require(type(m["generation"]) is str and
            re.fullmatch("[0-9a-f]{40}", m["generation"]), "full generation SHA required")
    require(plain_path(m["source_home"]).is_dir(), "missing source home")
    require(type(m["hashes"]) is dict and set(m["hashes"]) == files,
            "exact schema%d/profile raw hash set required" % schema)
    if m.get("runtime_profile") in ("current81-v1", "inventory82-v1", "activity83-v1", "collectors84-v1", "fetch85-v1"):
        external = m.get("external_python")
        require(type(external) is dict and set(external) == {"momimport", "momreimport", "momreplay"},
                "exact three-converter external source closure required")
        for name, item in external.items():
            require(type(item) is dict and set(item) == {"origin", "sha256"}, "external source shape")
            require(type(item["origin"]) is str and plain_path(item["origin"]).is_file() and
                    Path(item["origin"]).name == name + ".py", "external source origin")
            require(type(item["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", item["sha256"]), "external source hash")
        require(len({str(Path(item["origin"]).parent) for item in external.values()}) == 1,
                "converter closure must share selected tools directory")
    else:
        require("external_python" not in m, "external closure requires explicit current81/schema24, inventory82/schema25, activity83/schema26 or collectors84/schema26 or fetch85/schema26")
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

    for name, item in m.get("external_python", {}).items():
        p = plain_path(item["origin"])
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as source:
            meta = os.fstat(source.fileno())
            require(stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1 and
                    meta.st_uid == os.geteuid() and not meta.st_mode & 0o022, "unsafe external source")
            actual = hashlib.sha256(source.read()).hexdigest()
        require(actual == item["sha256"], "external source raw hash mismatch: " + name)


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


def state_write(root, state, not_after_ns=None):
    temp = root / ("state-" + uuid.uuid4().hex)
    write_new(temp, state)
    try:
        if not_after_ns is not None:
            require(time.monotonic_ns() < not_after_ns, "OPEN deadline expired; remains CLOSED")
        os.replace(temp, root / "state.json")
    finally:
        if temp.exists(): temp.unlink()
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


def linux_process(pid):
    require(sys.platform == "linux", "UNSUPPORTED: candidate identity requires Linux /proc")
    raw = Path("/proc/%d/stat" % pid).read_text()
    fields = raw[raw.rfind(")") + 2:].split()
    require(fields[0] not in ("Z", "X"), "candidate is not live")
    return {"pid": pid, "start": fields[19],
            "cwd": os.readlink("/proc/%d/cwd" % pid)}


def candidate_read(root, m, s=None):
    record = read_json(root / "candidate.json", True)
    require(type(record) is dict and
            set(record) == {"generation", "closure", "route", "process"} and
            record["generation"] == m["generation"] and record["route"] == "server" and
            type(record["closure"]) is str and
            re.fullmatch("[0-9a-f]{32}", record["closure"]), "malformed candidate record")
    if s is not None:
        require(record["closure"] == s["closure"], "stale candidate closure")
    p = record["process"]
    require(type(p) is dict and set(p) == {"pid", "start", "cwd"} and
            type(p["pid"]) is int and p["pid"] > 0 and
            type(p["start"]) is str and re.fullmatch("[0-9]+", p["start"]) and
            p["cwd"] == m["source_home"], "malformed candidate process")
    return record


def fixed_exec(m, route, lifetime):
    os.chdir(m["source_home"])
    os.set_inheritable(lifetime, True)
    os.execve(m["routes"][route][0], m["routes"][route],
              {"PATH": "/usr/bin:/bin", "HOME": m["source_home"],
               "PYTHONNOUSERSITE": "1"})


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
    candidate = sub.add_parser("candidate", help="Linux externally authorized CLOSED server start")
    candidate.add_argument("--generation", required=True)
    candidate.add_argument("--route", required=True)
    candidate.add_argument("--authorization", required=True)
    parser.add_argument("--open-deadline-ns", type=int)
    a = parser.parse_args()
    require(math.isfinite(a.timeout) and 0 <= a.timeout <= 300, "invalid timeout")
    root = plain_path(a.state_dir)
    if a.command == "init":
        m = manifest_check(read_json(a.manifest))
        root.mkdir(mode=0o700)  # Exclusive: never overwrite/reinitialize existing state.
        secure_stat(root.stat(), True)
        write_new(root / "manifest.json", m)
        for name in ("admission.lock", "controller.lock", "candidate.lock"):
            write_new(root / name, {})
        state_write(root, {"admission": "CLOSED", "generation": m["generation"],
                           "closure": uuid.uuid4().hex})
        sync_dir(root.parent)
        print("INITIALIZED CLOSED")
        return
    secure_stat(root.stat(), True)
    m = manifest_check(read_json(root / "manifest.json", True))
    # Legacy directories without the third lock fail safely, including ordinary launches.
    candidate_fd = lock_file(root, "candidate.lock")
    os.close(candidate_fd)
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
            fixed_exec(m, a.route, admission)
        controller = lock_file(root, "controller.lock")
        try:
            acquire(controller, fcntl.LOCK_EX, a.timeout)
            s = state_read(root, m)
            if a.command == "close":
                s.update(admission="CLOSED", closure=uuid.uuid4().hex)
                state_write(root, s)
                print("CLOSED DURABLE; draining", flush=True)
                acquire(admission, fcntl.LOCK_EX, a.timeout)
                lifetime = lock_file(root, "candidate.lock")
                try:
                    acquire(lifetime, fcntl.LOCK_EX, a.timeout)
                    record_path = root / "candidate.json"
                    if os.path.lexists(record_path):
                        # Only our exact record type may be retired after BOTH drains.
                        candidate_read(root, m)
                        record_path.unlink()
                        sync_dir(root)
                finally:
                    os.close(lifetime)
                print("DRAINED cooperative foreground launches and candidate", flush=True)
            elif a.command == "candidate":
                require(sys.platform == "linux", "UNSUPPORTED: candidate requires Linux")
                require(a.generation == m["generation"], "wrong generation")
                require(s["admission"] == "CLOSED", "candidate requires CLOSED")
                require(a.route == "server" and a.route in m["routes"],
                        "candidate requires fixed server route")
                grant = read_json(a.authorization, True)
                expected = {"generation": m["generation"], "closure": s["closure"],
                            "route": "server", "authorized": True}
                require(type(grant) is dict and set(grant) == set(expected) and
                        all(type(grant[k]) is type(v) and grant[k] == v
                            for k, v in expected.items()), "candidate authorization mismatch")
                lifetime = lock_file(root, "candidate.lock")
                try:
                    acquire(lifetime, fcntl.LOCK_EX, a.timeout)
                    require(not os.path.lexists(root / "candidate.json"),
                            "prior candidate record; full close required")
                    # A CLOSED state alone does not prove old admitted work drained.
                    acquire(admission, fcntl.LOCK_EX, a.timeout)
                    verify_hashes(m)
                    os.chdir(m["source_home"])
                    write_new(root / "candidate.json",
                              {"generation": m["generation"], "closure": s["closure"],
                               "route": "server", "process": linux_process(os.getpid())})
                    sync_dir(root)
                    # Release controller before exec; close can publish CLOSED and then wait
                    # for lifetime without preventing this startup from finishing.
                    os.close(controller)
                    controller = None
                    os.close(admission)
                    admission = None
                    fixed_exec(m, a.route, lifetime)
                finally:
                    os.close(lifetime)
            else:
                require(a.generation == m["generation"], "wrong generation")
                require(s["admission"] == "CLOSED", "already open; close explicitly first")
                acquire(admission, fcntl.LOCK_EX, a.timeout)
                verify_hashes(m)
                receipt = read_json(a.receipt, True)
                expected = {"generation": m["generation"], "closure": s["closure"],
                            "source_home": m["source_home"], "hashes": m["hashes"],
                            "schema": target_schema(m), "accepted": True}
                require(type(receipt) is dict and set(receipt) == set(expected) | {"process"},
                        "malformed external acceptance receipt")
                require(all(type(receipt[k]) is type(v) and receipt[k] == v
                            for k, v in expected.items()), "acceptance receipt mismatch")
                p = receipt["process"]
                require(type(p) is dict and set(p) == {"pid", "start", "cwd"} and
                        type(p["pid"]) is int and p["pid"] > 0 and
                        type(p["start"]) is str and bool(p["start"]) and
                        p["cwd"] == m["source_home"], "missing process acceptance")
                record = candidate_read(root, m, s)
                require(p == record["process"] and linux_process(p["pid"]) == p,
                        "candidate process acceptance mismatch")
                lifetime = lock_file(root, "candidate.lock")
                try:
                    try:
                        fcntl.flock(lifetime, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        pass
                    else:
                        raise ValueError("candidate lifetime lock is not held")
                    # Recheck identity after contention; a dead master with live children
                    # is drainable but cannot be accepted as the measured master.
                    require(linux_process(p["pid"]) == p, "candidate no longer live")
                finally:
                    os.close(lifetime)
                s["admission"] = "OPEN"
                state_write(root, s, not_after_ns=a.open_deadline_ns)
                print("OPEN: external receipt consumed; not independently attested")
        finally:
            if controller is not None:
                os.close(controller)
    finally:
        if admission is not None:
            os.close(admission)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print("REFUSED: " + str(exc), file=sys.stderr)
        sys.exit(2)
