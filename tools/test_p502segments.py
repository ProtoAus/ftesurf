#!/usr/bin/env python3
"""Counterfactual grader controls using a retained PRIVATE p502segments rig.

python tools/test_p502segments.py --rig <retained rig>
Copies only generated fixture logs/save snapshots into a new temporary root;
never edits original logs, follows content junctions, or touches player data.
"""
import argparse
import contextlib
import io
import pathlib
import re
import shutil
import tempfile
import p502segments as harness


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rig", required=True, type=pathlib.Path)
    args = ap.parse_args()
    source = args.rig / "ftesurf"
    faults = 0

    def check(name, ok):
        nonlocal faults
        print(("PASS" if ok else "FAIL"), name)
        faults += not ok

    with tempfile.TemporaryDirectory(prefix="p502-grade-") as tmp:
        gd = pathlib.Path(tmp)
        (gd / "logs").mkdir()
        for name in ("p502segments", "p502cold", "p502edges"):
            shutil.copyfile(source / f"logs/{name}.log", gd / f"logs/{name}.log")
        shutil.copytree(source / "data/p502-control", gd / "data/p502-control")
        shutil.copytree(source / "data/saves/surf_dune", gd / "data/saves/surf_dune")
        shutil.copyfile(source / "data/p502-stale-picture-control.json", gd / "data/p502-stale-picture-control.json")
        with contextlib.redirect_stdout(io.StringIO()):
            control = not harness.grade(gd) and not harness.grade_edges(gd)
        check("unmodified ACTED rig passes both graders", control)

        path = gd / "logs/p502segments.log"
        original = path.read_text()
        for name, mutation in (
            ("post-countdown recording loss", lambda s: s.replace("recording 1", "recording 0")),
            ("post-countdown stalled clock", lambda s: re.sub(r"tick: counted \d+", "tick: counted 1", s)),
        ):
            before, after = original.split("==== P502 C RELEASE ====", 1)
            path.write_text(before + "==== P502 C RELEASE ====" + mutation(after))
            with contextlib.redirect_stdout(io.StringIO()):
                rejected = harness.grade(gd)
            check(name, rejected)
        for name, mutation in (
            ("board release stays held", lambda s: s.replace("scores: closed", "scores: held")),
            ("server load refused after viewer closes", lambda s: re.sub(r"(saveloc: event \d+ op )2", r"\g<1>1", s)),
            ("loaded body differs from saved replay pose", lambda s: re.sub(r"setpos [\d.+-]+ [\d.+-]+ [\d.+-]+", "setpos 0 0 0", s)),
        ):
            path.write_text(mutation(original))
            with contextlib.redirect_stdout(io.StringIO()):
                rejected = harness.grade(gd)
            check(name, rejected)
        path.write_text(original)

        path = gd / "logs/p502edges.log"
        original = path.read_text()
        for name, mutation in (
            ("timed countdown clock advances", lambda s: re.sub(r"tick: counted \d+", "tick: counted 1", s)),
            ("timed countdown recorder stops", lambda s: s.replace("recording 1", "recording 0")),
            ("second board release stays held", lambda s: s.replace("scores: closed", "scores: held")),
        ):
            path.write_text(mutation(original))
            with contextlib.redirect_stdout(io.StringIO()):
                rejected = harness.grade_edges(gd)
            check(name, rejected)
        path.write_text(original)
    print(f"{faults} failed")
    return bool(faults)


if __name__ == "__main__":
    raise SystemExit(main())
