#!/usr/bin/env python3
"""Acted synthetic Linux candidate protocol controls; exclusively NEW --out."""
import argparse
import copy
import fcntl
import json
import os
from pathlib import Path
import sys

from test_surfd_transition_guard import (Fixture, GEN, PROCESSES, COMMANDS, check,
                                         save, stop, wait_for)


def closed(f):
    check(json.loads((f.state / "state.json").read_text())["admission"] == "CLOSED",
          "failed attempt opened admission")


def reopen(f, receipt, ok=False):
    f.run("reopen", "--generation", GEN, "--receipt", str(receipt), ok=ok)
    if not ok:
        closed(f)


def candidate_args(f, grant):
    return ("candidate", "--generation", GEN, "--route", "server",
            "--authorization", str(grant))


def schema_suite(out):
    for target in (None, 19, 20):
        f = Fixture(out / ("schema-legacy19" if target is None else "schema%d" % target),
                    target_schema=target)
        schema = 19 if target is None else target
        manifest_bytes = (f.state / "manifest.json").read_bytes()
        initial_state = (f.state / "state.json").read_bytes()
        if schema == 20:
            state = json.loads(initial_state)
            grant = f.root / "grant.json"
            save(grant, {"generation": GEN, "closure": state["closure"],
                         "route": "server", "authorized": True})
            for name in ("accounts.py", "social.py"):
                path = f.home / name
                original = path.read_bytes()
                for changed in (None, b"# mismatched schema20 dependency\n"):
                    path.unlink()
                    if changed is not None:
                        path.write_bytes(changed)
                    f.run(*candidate_args(f, grant), ok=False)
                    check(not (f.state / "candidate.json").exists() and
                          not (f.home / "candidate-acted").exists(),
                          "dependency hash refusal started candidate")
                    if path.exists():
                        path.unlink()
                    path.write_bytes(original)
        p = f.candidate()  # Acted server marker and same-PID record required by Fixture.
        for wrong in (20 if schema == 19 else 19, True, False, float(schema),
                      str(schema), None, 18, 21):
            reopen(f, f.receipt(schema=wrong))
            check((f.state / "state.json").read_bytes() == initial_state,
                  "rejected schema receipt changed closure/state")
        receipt = f.receipt()
        accepted_bytes = receipt.read_bytes()
        reopen(f, receipt, ok=True)
        check(p.poll() is None, "schema acceptance killed live candidate")
        stop(p)
        if schema == 20:
            for name in ("accounts.py", "social.py"):
                path = f.home / name
                original = path.read_bytes()
                for changed in (None, b"# mismatched launch dependency\n"):
                    path.unlink()
                    if changed is not None:
                        path.write_bytes(changed)
                    f.run("launch", "--generation", GEN, "--route", "manual", ok=False)
                    check(not (f.home / "imports").exists(), "bad dependency launch acted")
                    if path.exists():
                        path.unlink()
                    path.write_bytes(original)
        (f.home / "release").touch()
        f.run("launch", "--generation", GEN, "--route", "manual")
        check((f.home / "imports").read_text() == "IMPORT ACTED\n" and
              (f.home / "writer-done").read_text() == "OLD WRITE ACTED",
              "matching-schema launch did not act")
        f.run("close")
        f.refused_launches()
        p = f.candidate()
        stale = f.root / "stale-receipt.json"
        stale.write_bytes(accepted_bytes)
        stale.chmod(0o600)
        reopen(f, stale)
        if schema == 20:
            for name in ("accounts.py", "social.py"):
                path = f.home / name
                original = path.read_bytes()
                path.write_text("# mismatched reopen dependency\n")
                reopen(f, f.receipt())
                path.write_bytes(original)
        reopen(f, f.receipt(), ok=True)
        stop(p)
        f.run("close")
        check(not (f.state / "candidate.json").exists(), "close failed to retire candidate")
        check((f.state / "manifest.json").read_bytes() == manifest_bytes,
              "schema handling mutated immutable manifest")
    print("PASS legacy19/explicit19/explicit20 acted acceptance, cross-schema refusal, hash gates and closure replay")

    f = Fixture(out / "invalid-manifests", target_schema=20)
    valid_state = f.state
    variants = []
    for value in (True, False, 20.0, 19.0, "20", None, 18, 21, [], {}):
        variants.append(dict(f.manifest, target_schema=value))
    for target in (None, 19, 20):
        base = copy.deepcopy(f.manifest)
        if target is None:
            base.pop("target_schema")
        else:
            base["target_schema"] = target
        # Eight hashes cannot silently upgrade a keyless or explicit19 manifest.
        if target != 20:
            variants.append(copy.deepcopy(base))
        for name in ("accounts.py", "social.py"):
            missing = copy.deepcopy(base)
            missing["hashes"].pop(name)
            variants.append(missing)
        extra = copy.deepcopy(base)
        extra["hashes"]["extra.py"] = "0" * 64
        variants.append(extra)
    for index, manifest in enumerate(variants):
        f.state = f.root / ("invalid-guard-%d" % index)
        path = f.root / ("invalid-manifest-%d.json" % index)
        save(path, manifest)
        f.run("init", "--manifest", str(path), ok=False)
        check(not f.state.exists(), "invalid manifest initialized state")
    f.state = valid_state
    closed(f)
    print("PASS target types and insufficient/extra dependency sets refuse before initialization")


def suite(out):
    schema_suite(out)
    f = Fixture(out / "authorization")
    state = json.loads((f.state / "state.json").read_text())
    good = {"generation": GEN, "closure": state["closure"],
            "route": "server", "authorized": True}
    grant = f.root / "grant.json"
    for change in ({"generation": "0" * 40}, {"closure": "0" * 32},
                   {"route": "manual"}, {"authorized": False}, {"authorized": 1},
                   {"extra": True}):
        save(grant, dict(good, **change))
        f.run(*candidate_args(f, grant), ok=False)
    save(grant, good)
    grant.chmod(0o644)
    f.run(*candidate_args(f, grant), ok=False)
    grant.chmod(0o600)
    link = f.root / "link.json"
    link.symlink_to(grant)
    f.run(*candidate_args(f, link), ok=False)
    hard = f.root / "hard.json"
    os.link(grant, hard)
    f.run(*candidate_args(f, grant), ok=False)
    hard.unlink()
    f.run("candidate", "--generation", GEN, "--route", "manual",
          "--authorization", str(grant), ok=False)
    original = (f.home / "surfd.py").read_bytes()
    (f.home / "surfd.py").write_text("# mismatched candidate source\n")
    f.run(*candidate_args(f, grant), ok=False)
    (f.home / "surfd.py").write_bytes(original)
    check(not (f.state / "candidate.json").exists(), "hash refusal wrote candidate")
    check(not (f.home / "candidate-acted").exists() and
          not (f.home / "imports").exists(), "unauthorized application acted")
    f.refused_launches()
    # Missing/empty candidate cannot be replaced by a plausible external receipt.
    receipt = f.receipt()
    reopen(f, receipt)
    save(f.state / "candidate.json", {})
    reopen(f, receipt)
    # Malformed evidence is never silently deleted by close.
    f.run("close", ok=False)
    check(json.loads((f.state / "candidate.json").read_text()) == {},
          "close deleted malformed candidate evidence")
    (f.state / "candidate.json").unlink()  # Exact test-authored corrupt record only.
    state = json.loads((f.state / "state.json").read_text())
    save(grant, dict(good, closure=state["closure"]))
    p = f.candidate()
    closed(f)
    f.refused_launches()
    record_path = f.state / "candidate.json"
    record = json.loads(record_path.read_text())
    check(record["process"]["pid"] == p.pid, "exec did not preserve candidate PID")
    check(json.loads((f.root / "receipt.json").read_text())["process"] != record["process"],
          "candidate rewrote external receipt")
    # A second candidate cannot import, even with the current grant.
    f.run(*candidate_args(f, grant), ok=False, timeout=.1)
    record_path.unlink()
    reopen(f, f.receipt(process=record["process"]))
    save(record_path, record)
    for change in ({"pid": os.getpid()}, {"start": "0"}, {"cwd": str(out)}):
        forged = copy.deepcopy(record)
        forged["process"].update(change)
        save(record_path, forged)
        reopen(f, f.receipt())
    save(record_path, record)
    # Contention alone cannot substitute for matching live identity.
    stop(p)
    with (f.state / "candidate.lock").open("r+") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        reopen(f, f.receipt())
    reopen(f, f.receipt())
    f.run(*candidate_args(f, grant), ok=False)  # stale record requires full close
    f.run("close")
    check(not record_path.exists(), "full close failed to retire exact own record")
    f.run(*candidate_args(f, grant), ok=False)  # rotated closure
    reopen(f, receipt)
    p = f.candidate()
    accepted = f.receipt()
    # A real live PID without the lifetime FD is insufficient (oracle-negative).
    # Replace only the fixture record with the harness's own live process identity.
    raw = Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()
    fake = copy.deepcopy(json.loads(record_path.read_text()))
    fake["process"] = {"pid": os.getpid(), "start": raw[19], "cwd": str(f.home)}
    real = json.loads(record_path.read_text())
    stop(p)
    previous = Path.cwd()
    os.chdir(f.home)
    try:
        save(record_path, fake)
        reopen(f, f.receipt())
    finally:
        os.chdir(previous)
        save(record_path, real)
    f.run("close")
    p = f.candidate()
    accepted = f.receipt()
    reopen(f, accepted, ok=True)
    f.run(*candidate_args(f, grant), ok=False)
    check(p.poll() is None, "reopen drained/killed independent candidate")
    f.run("close", timeout=.1, ok=False)
    closed(f)
    check(record_path.exists() and p.poll() is None, "timeout removed candidate")
    reopen(f, accepted)  # closure rotated under the still-live candidate
    stop(p)
    f.run("close")
    print("PASS authorization/no-import, live identity+lock acceptance, rotation and full drain")

    g = Fixture(out / "fork")
    # Fixed manifest route forks, retaining the exec-inherited candidate FD in child.
    (g.home / "candidate-server.py").write_text(
        "import os,time\nfrom pathlib import Path\n"
        "pid=os.fork()\n"
        "if pid == 0:\n"
        "    Path('child-acted').write_text(str(os.getpid()))\n"
        "    deadline=time.monotonic()+20\n"
        "    while not Path('child-release').exists() and time.monotonic()<deadline: time.sleep(.02)\n"
        "    Path('child-done').write_text('CHILD EXIT ACTED')\n"
        "    os._exit(0)\n"
        "Path('candidate-acted').write_text('PARENT ACTED')\n"
        "while True: time.sleep(.02)\n")
    p = g.candidate()
    wait_for(lambda: (g.home / "child-acted").exists(), "fork child acted")
    receipt = g.receipt()
    stop(p)
    reopen(g, receipt)  # master dead even though child retains the lock
    g.run("close", timeout=.1, ok=False)
    closed(g)
    (g.home / "child-release").touch()
    wait_for(lambda: (g.home / "child-done").exists(), "child natural exit acted")
    g.run("close")
    print("PASS exec/fork inherited lifetime blocks drain after master death")

    h = Fixture(out / "failed-exec")
    # Executable passed init but kernel refuses its format at execve.
    bad = h.root / "bad-executable"
    bad.write_text("NOT AN EXECUTABLE FORMAT\n")
    bad.chmod(0o700)
    # Author a separate immutable manifest before init; never change initialized state.
    manifest = copy.deepcopy(h.manifest)
    manifest["routes"]["server"] = [str(bad), "fixed"]
    save(h.root / "bad-manifest.json", manifest)
    h.state = h.root / "bad-guard"
    h.run("init", "--manifest", str(h.root / "bad-manifest.json"))
    s = json.loads((h.state / "state.json").read_text())
    save(grant, dict(good, closure=s["closure"]))
    h.run(*candidate_args(h, grant), ok=False)
    closed(h)
    check((h.state / "candidate.json").exists(), "failed exec evidence removed")
    reopen(h, h.receipt())
    h.run("close")
    # Legacy init cannot silently run without the candidate lifetime protocol.
    (h.state / "candidate.lock").unlink()
    h.run("status", ok=False)
    h.refused_launches()
    print("PASS failed exec remains CLOSED, evidence retained; legacy missing lock refused")


def main():
    check(sys.platform == "linux" and __debug__, "UNSUPPORTED: nonoptimized Linux required")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    a = parser.parse_args()
    out = Path(a.out)
    check(out.is_absolute() and not out.exists() and not out.is_symlink(),
          "--out must be NEW absolute path")
    for parent in out.parents:
        check(not parent.is_symlink(), "symlink output ancestor")
    check(any((p / "OWNER.md").is_file() for p in out.parents), "owned ancestor required")
    out.mkdir(mode=0o700)
    (out / "OWNER.md").write_text("Candidate synthetic suite; exact Popen handles; retain evidence.\n")
    try:
        suite(out)
        save(out / "result.json", {"verdict": "PASS", "limits": "synthetic Linux, no gunicorn"})
    except Exception as exc:
        save(out / "result.json", {"verdict": "FAIL", "error": str(exc)})
        raise
    finally:
        for p in PROCESSES:
            stop(p)
        save(out / "commands.json", COMMANDS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
