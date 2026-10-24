#!/usr/bin/env python3
"""Actual subprocess controls. Synthetic only; --out must not already exist."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import time
import uuid

GUARD = Path(__file__).with_name("surfd_transition_guard.py").resolve()
GEN = "1" * 40
FILES = ("surfd.py", "ksfimport.py", "ksfgrab.py", "ksfprofile.py",
         "tools/ksfconvert.py", "tools/ksfreplay_info.py")
PROCESSES = []
COMMANDS = []


def check(ok, message):
    if not ok:
        raise RuntimeError(message)


def save(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)


def wait_for(predicate, message, timeout=5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.02)
    raise RuntimeError("timeout: " + message)


def spawn(argv, log):
    f = log.open("w")
    try:
        p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=f, stderr=subprocess.STDOUT,
                             env={"PATH": "/usr/bin:/bin"})
    finally:
        f.close()
    PROCESSES.append(p)
    return p


def stop(p):
    if p.poll() is None:
        p.kill()  # Only a handle returned by this harness's Popen; never a process group.
    p.wait(timeout=5)
    if p.stdin and not p.stdin.closed:
        p.stdin.close()


class Fixture:
    def __init__(self, root, target_schema=None, runtime_profile=None):
        self.root = root
        root.mkdir(mode=0o700)
        self.token = uuid.uuid4().hex
        self.identity = root / ".transition-guard-test.json"
        save(self.identity, {"token": self.token, "root": str(root),
                             "home": str(root / "home"), "guard": str(root / "guard")})
        self.home = root / "home"
        self.home.mkdir()
        (self.home / "tools").mkdir()
        (self.home / "surfd.py").write_text(
            "from pathlib import Path\n"
            "with Path('imports').open('a') as f: f.write('IMPORT ACTED\\n')\n")
        (self.home / "ksfimport.py").write_text(
            "import surfd\nimport time\nfrom pathlib import Path\n"
            "deadline = time.monotonic() + 20\n"
            "while not Path('release').exists():\n"
            "    if time.monotonic() > deadline: raise RuntimeError('fixture release timeout')\n"
            "    time.sleep(.02)\n"
            "Path('writer-done').write_text('OLD WRITE ACTED')\n")
        (self.home / "candidate-server.py").write_text(
            "import time\nfrom pathlib import Path\n"
            "Path('candidate-acted').write_text('SERVER ACTED')\n"
            "while True: time.sleep(.02)\n")
        files = FILES + (("accounts.py", "social.py") if target_schema in (20, 22, 23) else ())
        if target_schema == 23:
            files += ("viewmodel.py",)
        if runtime_profile == "hid-v1":
            files += ("hidupload.py",)
        for name in files[2:]:
            (self.home / name).write_text("# synthetic source sentinel\n")
        self.hashes = {name: hashlib.sha256((self.home / name).read_bytes()).hexdigest()
                       for name in files}
        self.manifest = {"generation": GEN, "source_home": str(self.home),
                         "hashes": self.hashes,
                         "routes": {r: [str(Path(sys.executable).resolve()), "ksfimport.py"]
                                    for r in ("scheduled", "manual", "worker")}}
        self.manifest["routes"]["server"] = [str(Path(sys.executable).resolve()),
                                             "candidate-server.py"]
        if target_schema is not None:
            self.manifest["target_schema"] = target_schema
        if runtime_profile is not None:
            self.manifest["runtime_profile"] = runtime_profile
        self.state = root / "guard"
        self.manifest_path = root / "manifest.json"
        save(self.manifest_path, self.manifest)
        self.run("init", "--manifest", str(self.manifest_path))
        self.db = self.home / "fixture.sqlite"
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE TABLE native(value TEXT)")
            db.execute("INSERT INTO native VALUES ('original-native')")
            db.execute("PRAGMA user_version=18")
        (self.home / "demos.json").write_text('{"sentinel":"cache18"}')

    def argv(self, *args, timeout=2):
        return [sys.executable, str(GUARD), "--state-dir", str(self.state),
                "--timeout", str(timeout), *args]

    def run(self, *args, ok=True, timeout=2):
        result = subprocess.run(self.argv(*args, timeout=timeout), capture_output=True,
                                text=True, timeout=timeout + 5,
                                env={"PATH": "/usr/bin:/bin"})
        COMMANDS.append({"args": list(args), "returncode": result.returncode,
                         "stdout": result.stdout, "stderr": result.stderr})
        check((result.returncode == 0) == ok, "unexpected verdict: " + str(COMMANDS[-1]))
        return result

    def receipt(self, **overrides):
        state = json.loads((self.state / "state.json").read_text())
        receipt = {"generation": GEN, "closure": state["closure"],
                   "source_home": str(self.home), "hashes": self.hashes,
                   "schema": self.manifest.get("target_schema", 19), "accepted": True,
                   "process": {"pid": os.getpid(), "start": "SYNTHETIC-not-attestation",
                               "cwd": str(self.home)}}
        record = self.state / "candidate.json"
        if record.exists():
            receipt["process"] = json.loads(record.read_text())["process"]
        receipt.update(overrides)
        path = self.root / "receipt.json"
        save(path, receipt)
        return path

    def candidate(self):
        state = json.loads((self.state / "state.json").read_text())
        grant = self.root / "authorization.json"
        save(grant, {"generation": GEN, "closure": state["closure"],
                     "route": "server", "authorized": True})
        marker = self.home / "candidate-acted"
        if marker.exists():
            marker.unlink()
        p = spawn(self.argv("candidate", "--generation", GEN, "--route", "server",
                            "--authorization", str(grant)), self.root / "candidate.log")
        wait_for(lambda: marker.exists(), "authorized candidate acted")
        check(p.poll() is None, "candidate not live")
        return p

    def reopen(self):
        # Existing admission suite needs a real measured candidate at acceptance.
        p = self.candidate()
        self.run("reopen", "--generation", GEN, "--receipt", str(self.receipt()))
        stop(p)  # The suite then tests independent ordinary admission lifetimes.

    def refused_launches(self):
        witness = self.home / "imports"
        before = witness.read_bytes() if witness.exists() else None
        for route in ("scheduled", "manual", "worker", "alternate-cache"):
            self.run("launch", "--generation", GEN, "--route", route, ok=False)
        self.run("launch", "--generation", "0" * 40, "--route", "manual", ok=False)
        self.run("launch", "--generation", GEN, "--route", "manual",
                 "--cache", str(self.root / "alternate"), ok=False)
        check((witness.read_bytes() if witness.exists() else None) == before,
              "pre-import refusal oracle failed")


def phase_controller(root_value, phase, token):
    # Test-only fake installer, NOT a guard command or a product migration.
    # Authenticate our exact newly authored fixture BEFORE closing or writing.
    root = Path(root_value)
    check(root.is_absolute() and str(root) == root_value and ".." not in root.parts,
          "controller requires canonical synthetic fixture root")
    for path in (root, *root.parents, root / "home", root / "guard"):
        check(not path.is_symlink(), "controller symlink path refused")
    check(type(token) is str and len(token) == 32 and
          all(c in "0123456789abcdef" for c in token), "fixture token required")
    identity = root / ".transition-guard-test.json"
    st = identity.lstat()
    check(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and
          st.st_uid == os.geteuid() and stat.S_IMODE(st.st_mode) == 0o600,
          "unsafe fixture identity")
    expected = {"token": token, "root": str(root), "home": str(root / "home"),
                "guard": str(root / "guard")}
    check(json.loads(identity.read_text()) == expected, "foreign fixture identity")
    home = root / "home"
    manifest = json.loads((root / "guard" / "manifest.json").read_text())
    check(manifest["source_home"] == str(home), "foreign source home binding")
    for name in FILES:
        path = home / name
        check(not path.is_symlink() and not path.parent.is_symlink() and path.is_file(),
              "unsafe synthetic source")
    subprocess.run([sys.executable, str(GUARD), "--state-dir", str(root / "guard"),
                    "close"], check=True, timeout=5)
    if phase != "pre-install":
        count = 3 if phase == "mid-six-file" else 6
        for name in FILES[:count]:
            (home / name).write_text("# simulated new source\n")
    if phase in ("post-migration", "pre-receipt"):
        with sqlite3.connect(home / "fixture.sqlite") as db:
            db.execute("PRAGMA user_version=19")
        (home / "demos.json").write_text('{"sentinel":"cache19"}')
    print("PHASE ACTED " + phase, flush=True)
    sys.stdin.read()  # EOF is deliberately not a reopen/restore operation.


def suite(out):
    import fcntl
    f = Fixture(out / "admission")
    f.refused_launches()
    f.run("candidate", ok=False)
    f.run("init", "--manifest", str(f.manifest_path), ok=False)
    f.run("reopen", "--generation", GEN, "--receipt", str(out / "absent"), ok=False)
    for override in ({"schema": 18}, {"generation": "0" * 40}, {"process": {}},
                     {"hashes": {}}, {"closure": "0" * 32}, {"accepted": False}):
        f.run("reopen", "--generation", GEN, "--receipt", str(f.receipt(**override)), ok=False)
    receipt = f.receipt()
    f.run("reopen", "--generation", "0" * 40, "--receipt", str(receipt), ok=False)
    receipt.write_text("{")
    f.run("reopen", "--generation", GEN, "--receipt", str(receipt), ok=False)
    original = (f.home / "ksfgrab.py").read_bytes()
    (f.home / "ksfgrab.py").write_text("# wrong hash\n")
    f.run("reopen", "--generation", GEN, "--receipt", str(f.receipt()), ok=False)
    (f.home / "ksfgrab.py").write_bytes(original)
    f.reopen()
    # These refusals must also hold while OPEN, not merely hit CLOSED first.
    f.run("launch", "--generation", "0" * 40, "--route", "manual", ok=False)
    f.run("launch", "--generation", GEN, "--route", "alternate-cache", ok=False)
    check(not (f.home / "imports").exists(), "bad OPEN launch imported")
    old = spawn(f.argv("launch", "--generation", GEN, "--route", "manual"),
                out / "old-writer.log")
    wait_for(lambda: (f.home / "imports").exists(), "positive application import witness")
    with (f.state / "admission.lock").open("r+") as lock:
        contended = False
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            contended = True
        check(contended, "shared lifetime lock did not actually contend")
    closer_log = out / "close-death.log"
    closer = spawn(f.argv("close", timeout=10), closer_log)
    wait_for(lambda: "CLOSED DURABLE" in closer_log.read_text(), "durable closure")
    check(closer.poll() is None, "drain did not wait for old writer")
    closer.stdin.close()  # Transport EOF cannot undo durable closure.
    f.refused_launches()
    stop(closer)
    f.refused_launches()  # Fresh guard process after controller death.
    f.run("close", timeout=.1, ok=False)
    (f.home / "release").touch()
    check(old.wait(timeout=5) == 0, "old writer failed")
    check((f.home / "writer-done").read_text() == "OLD WRITE ACTED", "old write missing")
    f.run("close")
    # Negative control: bypassing the guard really imports, so missing witnesses discriminate.
    before = (f.home / "imports").read_text().count("IMPORT ACTED")
    raw = subprocess.run([sys.executable, str(f.home / "ksfimport.py")], cwd=f.home,
                         capture_output=True, timeout=5, env={"PATH": "/usr/bin:/bin"})
    check(raw.returncode == 0 and
          (f.home / "imports").read_text().count("IMPORT ACTED") == before + 1,
          "unguarded negative control did not violate the refusal oracle")
    # Positive witnesses for every allowlisted route, using fresh admission receipts.
    for route in ("scheduled", "manual", "worker"):
        f.reopen()
        before = (f.home / "imports").read_text().count("IMPORT ACTED")
        f.run("launch", "--generation", GEN, "--route", route)
        check((f.home / "imports").read_text().count("IMPORT ACTED") == before + 1,
              "positive route import missing: " + route)
        f.run("close")
    print("PASS pre-import/drain/EOF/death/lock-contention and bypass-negative-control")

    for phase in ("pre-install", "mid-six-file", "post-migration", "pre-receipt"):
        for cut in ("death", "eof"):
            g = Fixture(out / (phase + "-" + cut))
            backup = g.root / "recovery"
            backup.mkdir()
            for name in FILES:
                dest = backup / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes((g.home / name).read_bytes())
            with sqlite3.connect(g.db) as src, sqlite3.connect(backup / "fixture.sqlite") as dst:
                src.backup(dst)
            (backup / "demos.json").write_bytes((g.home / "demos.json").read_bytes())
            log = g.root / "controller.log"
            controller = spawn([sys.executable, str(Path(__file__).resolve()),
                                "--controller", str(g.root), "--phase", phase,
                                "--fixture-token", g.token], log)
            wait_for(lambda: "PHASE ACTED" in log.read_text(), phase)
            observed = {name: (g.home / name).read_bytes() for name in FILES}
            cache = (g.home / "demos.json").read_bytes()
            if cut == "death":
                stop(controller)
            else:
                controller.stdin.close()
                check(controller.wait(timeout=5) == 0, "EOF fixture failed")
            g.refused_launches()
            # Later native write must survive errors; guard has no restore operation.
            with sqlite3.connect(g.db) as db:
                db.execute("INSERT INTO native VALUES ('later-native')")
            g.run("candidate", ok=False)
            g.run("reopen", "--generation", GEN, "--receipt", str(g.root / "missing"), ok=False)
            check(all((g.home / n).read_bytes() == b for n, b in observed.items()),
                  "automatic source restore occurred")
            check((g.home / "demos.json").read_bytes() == cache, "cache restored")
            with sqlite3.connect(g.db) as db:
                check(db.execute("SELECT value FROM native ORDER BY rowid").fetchall() ==
                      [("original-native",), ("later-native",)], "native data lost")
                check(db.execute("PRAGMA integrity_check").fetchone() == ("ok",), "SQLite integrity")
                check(db.execute("PRAGMA user_version").fetchone()[0] ==
                      (19 if phase in ("post-migration", "pre-receipt") else 18), "schema sentinel")
            with sqlite3.connect(backup / "fixture.sqlite") as db:
                check(db.execute("SELECT value FROM native").fetchall() ==
                      [("original-native",)] and
                      db.execute("PRAGMA user_version").fetchone()[0] == 18,
                      "recovery SQLite sentinel changed")
            check(all(hashlib.sha256((backup / n).read_bytes()).hexdigest() == g.hashes[n]
                      for n in FILES), "recovery source bytes changed")
            check((backup / "demos.json").read_text() == '{"sentinel":"cache18"}',
                  "recovery cache changed")
            check(all((backup / n).read_bytes() ==
                      (g.home / n).read_bytes() for n in FILES) if phase == "pre-install" else
                  (backup / "surfd.py").read_bytes() != (g.home / "surfd.py").read_bytes(),
                  "phase source/recovery control did not act")
    print("PASS eight simulated phase death/EOF cuts; recovery/native/cache sentinels")
    j = Fixture(out / "unsafe-source")
    bad_source = j.home / "surfd.py"
    source_bytes = bad_source.read_bytes()
    for kind in ("fifo", "directory", "symlink"):
        j.reopen()
        bad_source.unlink()
        if kind == "fifo":
            os.mkfifo(bad_source, 0o600)
        elif kind == "directory":
            bad_source.mkdir()
        else:
            bad_source.symlink_to(j.home / "ksfgrab.py")
        j.run("launch", "--generation", GEN, "--route", "manual", ok=False, timeout=.1)
        check(not (j.home / "imports").exists(), "unsafe source imported")
        j.run("close")
        j.run("reopen", "--generation", GEN, "--receipt", str(j.receipt()),
              ok=False, timeout=.1)
        if kind == "directory":
            bad_source.rmdir()
        else:
            bad_source.unlink()
        bad_source.write_bytes(source_bytes)
    alias = str(j.state.parent) + "/../" + j.root.name + "/guard"
    alias_result = subprocess.run([sys.executable, str(GUARD), "--state-dir", alias, "status"],
                                  capture_output=True, text=True, timeout=5)
    check(alias_result.returncode == 2 and "canonical" in alias_result.stderr,
          "noncanonical state path accepted")
    # Prove test-only controller rejection happens BEFORE closing or mutating.
    foreign = Fixture(out / "foreign-existing")
    foreign.reopen()
    foreign.identity.unlink()
    for label, fixture, extra in (("missing-token", j, []),
                                  ("wrong-token", j, ["--fixture-token", "0" * 32]),
                                  ("foreign-root", foreign, ["--fixture-token", foreign.token])):
        before_state = (fixture.state / "state.json").read_bytes()
        before_source = {name: (fixture.home / name).read_bytes() for name in FILES}
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                 "--controller", str(fixture.root), "--phase", "mid-six-file",
                                 *extra], input="", capture_output=True, text=True, timeout=5)
        (out / (label + ".log")).write_text(result.stdout + result.stderr)
        check(result.returncode != 0 and "PHASE ACTED" not in result.stdout,
              "foreign/missing-token controller accepted")
        check((fixture.state / "state.json").read_bytes() == before_state and
              all((fixture.home / name).read_bytes() == data
                  for name, data in before_source.items()), "controller mutated foreign fixture")
    print("PASS FIFO/directory/symlink source and canonical-path/controller-identity refusals")
    h = Fixture(out / "unsafe-state")
    (h.state / "state.json").unlink()
    h.refused_launches()
    (h.state / "state.json").write_text("{}")
    (h.state / "state.json").chmod(0o600)
    h.refused_launches()
    (h.state / "state.json").unlink()
    (h.state / "state.json").symlink_to(h.manifest_path)
    h.refused_launches()
    link = out / "linked-state"
    link.symlink_to(h.state, target_is_directory=True)
    result = subprocess.run([sys.executable, str(GUARD), "--state-dir", str(link), "status"],
                            capture_output=True, text=True, timeout=5)
    check(result.returncode == 2 and "symlink" in result.stderr, "state symlink accepted")
    h.state.chmod(0o755)
    h.run("status", ok=False)
    print("PASS missing/malformed/symlink/loose-mode state refusal")


def main():
    if os.name != "posix":
        print("UNSUPPORTED: local Linux/POSIX required; Windows refused", file=sys.stderr)
        return 2
    if not __debug__:
        print("REFUSED: -O unsupported; no output created", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out")
    parser.add_argument("--controller")
    parser.add_argument("--fixture-token", help=argparse.SUPPRESS)
    parser.add_argument("--phase", choices=("pre-install", "mid-six-file", "post-migration", "pre-receipt"))
    args = parser.parse_args()
    if args.controller:
        check(args.phase is not None, "phase required")
        phase_controller(args.controller, args.phase, args.fixture_token)
        return 0
    check(args.out is not None, "--out required, exclusively new synthetic path")
    out = Path(args.out)
    check(out.is_absolute() and not out.exists() and not out.is_symlink(), "--out must be NEW absolute path")
    for parent in out.parents:
        check(not parent.is_symlink(), "symlink output ancestor refused")
    out.mkdir(mode=0o700)
    try:
        suite(out)
        for schema in (20, 22, 23):
            hid = Fixture(out / ("hid-profile-%d" % schema), target_schema=schema, runtime_profile="hid-v1")
            hid.reopen()  # A real fixed candidate must act with the exact schema/profile hashes.
            body = (hid.home / "hidupload.py").read_bytes()
            (hid.home / "hidupload.py").write_bytes(body + b"# changed collector\n")
            refused = hid.run("launch", "--generation", GEN, "--route", "manual", ok=False)
            check("raw hash mismatch: hidupload.py" in refused.stderr, "collector was not sealed")
            check(not (hid.home / "imports").exists(), "changed collector allowed application import")
            (hid.home / "hidupload.py").write_bytes(body)
            if schema == 23:
                vm = hid.home / "viewmodel.py"
                original = vm.read_bytes()
                vm.write_bytes(original + b"# changed viewmodel dependency\n")
                refused = hid.run("launch", "--generation", GEN, "--route", "manual", ok=False)
                check("raw hash mismatch: viewmodel.py" in refused.stderr and
                      not (hid.home / "imports").exists(), "viewmodel dependency was not sealed")
                vm.write_bytes(original)
            (hid.home / "release").touch()
            hid.run("launch", "--generation", GEN, "--route", "manual")
            check((hid.home / "imports").read_text() == "IMPORT ACTED\n", "restored collector did not act")
            variants = [("missing-hid", {"hashes": {k: v for k, v in hid.hashes.items() if k != "hidupload.py"}}),
                        ("untagged-hid", {"runtime_profile": None}),
                        ("unknown-profile", {"runtime_profile": "unapproved"}),
                        ("unsupported-schema21", {"target_schema": 21}),
                        ("unsupported-schema24", {"target_schema": 24})]
            if schema == 23:
                variants += [("missing-viewmodel", {"hashes": {k: v for k, v in hid.hashes.items() if k != "viewmodel.py"}}),
                             ("schema22-extra-viewmodel", {"target_schema": 22})]
            else:
                variants += [("schema23-missing-viewmodel", {"target_schema": 23})]
            for label, changes in variants:
                manifest = dict(hid.manifest, **changes)
                if label == "untagged-hid":
                    del manifest["runtime_profile"]
                path = hid.root / (label + ".json")
                save(path, manifest)
                state_dir = hid.root / (label + "-state")
                r = subprocess.run([sys.executable, str(GUARD), "--state-dir", str(state_dir),
                                    "init", "--manifest", str(path)], capture_output=True, text=True, timeout=5)
                check(r.returncode == 2 and not state_dir.exists(), "profile admitted malformed hash set/schema")
            hid.run("close")
            print("PASS explicit schema%d HID profile: candidate, altered-byte refusal, restored import and exact sets" % schema)
        save(out / "result.json", {"verdict": "PASS", "limits": "synthetic cooperative POSIX only"})
        return 0
    except Exception as exc:
        save(out / "result.json", {"verdict": "FAIL", "error": str(exc)})
        raise
    finally:
        for p in PROCESSES:
            stop(p)
        save(out / "commands.json", COMMANDS)


if __name__ == "__main__":
    sys.exit(main())
