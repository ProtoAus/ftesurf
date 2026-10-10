#!/usr/bin/env python3
"""Patch 545 graph falsifier: synthetic sample clocks, independent E formula.

python tools/p545graph.py --prepare
Run only in a private content overlay via tools/runlines_smoke.py, then:
python tools/p545graph.py --check ftesurf/logs/<fresh log>.log

Writes only named synthetic fixtures under cfg/test, never data/runs or saves.
Two labels/palettes, recorded/assumed gravity, stage-start alignment, exact and
interpolated samples, no clamping past the run, no interpolation across a retry,
and selectable comparisons are asserted. The screenshots must ALSO be read.
"""
import argparse
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLOTS = 11     # LG_SLOTS: where a finished build's slot cursor rests (9 before Patch 622's two live slots)


def prepare():
    base = ROOT / "ftesurf/cfg/test"
    base.mkdir(parents=True, exist_ok=True)
    for name, gravity, vz, z, duration, gap in (
        ("A", 800, 80, 100, .1, False),
        ("B", 400, 160, 200, .1, False),
        ("stage", 800, 80, 100, .2, False),
        ("gap", None, 80, 100, .1, True),
    ):
        head = ["FTESURF-REC 4", "map surf_dune", "track 0", "leg 0", "startseg 0",
                "tickrate 0.01", "movetickrate 0.01", "owner Test" + name, "flags 0"]
        if gravity is not None:
            head += ["pmpin gravity=%d" % gravity]
        head += ["begin"]
        for i in range(round(duration * 100) + 1):
            t = i / 100
            if gap and i == 5:
                head += ["retry 5 1"]
            if name == "stage" and i in (10, 20):
                head += ["stage %d %d" % (i // 10, i)]
            vx, vy = (0, 0) if name == "B" else (300, 400)
            head += ["%.4f %.3f %.3f %.3f %d %d %d 0 0 0 0 0 0 0 0 0 0" %
                     (t, vx * t, vy * t, z + vz * t, vx, vy, vz)]
        head += ["end %d %d 0 0" % (round(duration * 100), round(duration * 100) + 1)]
        (base / ("p545graph%s.rec" % name)).write_text("\n".join(head) + "\n")
    cfg = """cfg_save_auto 0
log_enable 1
log_dir logs
log_name runlines_smoke
developer 0
cl_idlefps 0
cl_maxfps 100
vid_fullscreen 0
set fs_missingwarn 0
sv_public 0
sv_port 27639
set lobby_dir ""
set run_resume 0
set hud_lines_board 1
set hud_linegraph 1
set hud_linegraph_labels 1
set hud_watch_path 1
set hud_watch_path_ahead 1
set hud_watch_path_far 20000
set hud_watch_skipidle 0
set hud_scale 1
waitms 2000
map surf_dune
waitmap 60
waitms 2500
menu_restart
waitms 500
ui_close
waitms 500
scores lineat 1 cfg/test/p545graphA.rec
scores lineat 2 cfg/test/p545graphB.rec
scores lineat 3 cfg/test/p545graphstage.rec 2
scores lineat 4 cfg/test/p545graphgap.rec
waitms 2500
scores lines
linegraph sample 1 0.05
linegraph sample 2 0.05
linegraph sample 3 0.05
linegraph sample 4 0.045
linegraph sample 4 0.05
linegraph sample 1 -1
linegraph sample 1 1
linegraph sample 1 0.035
screenshot screenshots/p545graph_passive.png
linegraph
waitms 1000
linegraph cursorat 0.05
waitms 300
linegraph status
linegraph toggle 2
linegraph sample 2 0.05
linegraph toggle 2
linegraph sample 2 0.05
waitms 500
screenshot screenshots/p545graph_compare.png
waitms 500
linegraph close
scores lines clear
linegraph sample 1 0.05
waitms 500
echo p545graph DONE
echo RUNLINES COMPLETE
quit
"""
    (base / "p545graph.cfg").write_text(cfg)
    print("Prepared four synthetic fixtures and cfg/test/p545graph.cfg")


def check(path):
    text = Path(path).read_text(errors="replace")
    rows = re.findall(r"linegraph: slot (\d+) t ([\d.-]+) valid (\d+) speed ([\d.-]+) selected (\d+) bins (\d+)(?:[^\n]*\n(?:.*?linegraph: energy ([\d.-]+) relative ([+\d.-]+) gravity ([\d.-]+) start ([\d.-]+)))?", text)
    wanted = [(1,.05,1,500,264.25,4,800,0), (2,.05,1,0,240,8,400,0),
              (3,.05,1,500,272.25,4,800,.1), (4,.045,0,0,None,None,None,None),
              (4,.05,1,500,264.25,4,800,0), (1,-1,0,0,None,None,None,None),
              (1,1,0,0,None,None,None,None), (1,.035,1,500,263.05,2.8,800,0),
              (2,.05,1,0,240,8,400,0), (2,.05,1,0,240,8,400,0),
              (1,.05,0,0,None,None,None,None)]
    errors = []
    if len(rows) != len(wanted):
        errors.append("%d sample replies, wanted %d (subject must ACT)" % (len(rows),len(wanted)))
    for i, (got, want) in enumerate(zip(rows, wanted)):
        values = [int(got[0]), float(got[1]), int(got[2]), float(got[3])]
        if any(abs(a-b) > .003 for a,b in zip(values, want[:4])):
            errors.append("reply %d sample %s != %s" % (i,values,want[:4]))
        if int(got[5]) != SLOTS:
            errors.append("reply %d cache not finished" % i)
        if want[4] is not None:
            if not all(got[6:]):
                errors.append("reply %d missing energy" % i)
            elif any(abs(float(a)-b) > .02 for a,b in zip(got[6:],want[4:])):
                errors.append("reply %d energy %s != %s" % (i,got[6:],want[4:]))
        if i in (8,9) and int(got[4]) != i-8:
            errors.append("comparison selection did not change on reply %d" % i)
    for word in ("p545graph DONE", "line 1 drawn", "line 2 drawn", "line 3 drawn", "line 4 drawn"):
        if word not in text:
            errors.append("missing control: " + word)
    cursor = re.search(r"linegraph: open 1 cursor ([\d.]+) duration ([\d.]+) build %d" % SLOTS, text)
    if not cursor or not 0 < float(cursor[1]) < float(cursor[2]):
        errors.append("shared mouse cursor did not act")
    if re.search(r"(QC ERROR|runaway|VM error|failed|could not)", text, re.I):
        errors.append("runtime error in log (inspect)")
    print("\n".join("FAIL " + x for x in errors) if errors else "PASS clocks, full velocity energy, two gravities, gaps, interpolation, selection and clearing")
    return bool(errors)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepare", action="store_true")
    p.add_argument("--check")
    a = p.parse_args()
    if a.prepare:
        prepare()
    if a.check:
        raise SystemExit(check(a.check))
