#!/usr/bin/env python3
"""cfgguard.py -- every test cfg must turn off the config auto-save before it can
reach a disconnect.

The engine writes ftesurf/ftesurf.cfg from CL_ClearState -- every disconnect and
map change, not only at quit (engine client/cl_main.c, `cfg_save_auto.ival &&
Cvar_UnsavedArchive()`) -- and default.cfg turns cfg_save_auto ON.  So a harness
that sets an archived cvar (cl_maxfps 100, vid_*, sv_dlURL ...) without
`cfg_save_auto 0` writes it into the config of whoever plays the install next.
That is how sv_dlURL came to be "" on the main rig (BACKLOG, 0.1.19).

A cfg passes when `cfg_save_auto 0` runs before its first map/connect/exec/
disconnect/quit-class command.  A cfg that another cfg execs is a helper and
inherits its caller's setting, so it is listed, not judged.  A cfg that SAVES
on purpose (`cfg_save`, `saveconfig`) is listed separately and never edited --
b33a is ABOUT the config being written, so the guard would change its subject --
and running one writes your config.

    python tools/cfgguard.py          report; exit 1 if any cfg is unguarded
    python tools/cfgguard.py --fix    insert `cfg_save_auto 0` before the first
                                      command of every cfg that has none at all
                                      (a cfg that sets it too LATE is reported,
                                      never edited)
"""
import argparse
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTDIR = os.path.join(ROOT, "ftesurf", "cfg", "test")
REACH = re.compile(r"^(map|connect|exec|disconnect|reconnect|quit|changelevel|"
                   r"map_restart|retry|cmd\s+retry)\b")
GUARD = re.compile(r"^(set\s+|seta\s+)?cfg_save_auto\s+\"?0\"?\s*$")
SAVES = re.compile(r"^(cfg_save|saveconfig|writeconfig|cfg_save_ifmodified)\b")


def commands(path):
    """(line number, command) for every command, comments and blanks dropped.
    A `;` splits a line into several, as the console does."""
    out = []
    for n, line in enumerate(open(path, "r", errors="replace"), 1):
        s = line.split("//", 1)[0]
        for c in s.split(";"):
            c = c.strip()
            if c:
                out.append((n, c))
    return out


def scan():
    cfgs = sorted(glob.glob(os.path.join(TESTDIR, "*.cfg")))
    names = {os.path.basename(c) for c in cfgs}
    nested = set()
    for c in cfgs:
        for _, cmd in commands(c):
            m = re.match(r'exec\s+"?([^\s"]+)', cmd)
            if m:
                t = os.path.basename(m.group(1))
                t = t if t.endswith(".cfg") else t + ".cfg"
                if t in names and t != os.path.basename(c):
                    nested.add(t)
    rows = []
    for c in cfgs:
        name = os.path.basename(c)
        cmds = commands(c)
        guard = next((n for n, x in cmds if GUARD.match(x)), None)
        reach = next((n for n, x in cmds if REACH.match(x)), None)
        saves = [n for n, x in cmds if SAVES.match(x)]
        if name in nested:
            verdict = "helper"
        elif saves:
            verdict = "saves"
        elif not cmds:
            verdict = "empty"                    # notes only: the driver runs it
        elif guard is None:
            verdict = "missing"
        elif reach is not None and reach < guard:
            verdict = "late"
        else:
            verdict = "ok"
        rows.append((name, verdict, guard, reach, saves, cmds))
    return rows


def fix(rows):
    done = 0
    for name, verdict, _, _, _, cmds in rows:
        if verdict != "missing" or not cmds:
            continue
        path = os.path.join(TESTDIR, name)
        with open(path, "rb") as f:
            raw = f.read()
        eol = b"\r\n" if b"\r\n" in raw else b"\n"
        lines = raw.split(eol)
        at = cmds[0][0] - 1                      # the first command's line
        lines.insert(at, b"cfg_save_auto 0")
        with open(path, "wb") as f:
            f.write(eol.join(lines))
        done += 1
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true")
    a = ap.parse_args()
    rows = scan()
    if a.fix:
        print("inserted `cfg_save_auto 0` into %d cfg(s)" % fix(rows))
        rows = scan()
    by = {}
    for r in rows:
        by.setdefault(r[1], []).append(r)
    print("%d test cfgs: %s" % (len(rows), ", ".join(
        "%d %s" % (len(by.get(k, [])), k)
        for k in ("ok", "missing", "late", "helper", "saves", "empty"))))
    for k in ("missing", "late"):
        for name, _, guard, reach, _, _ in by.get(k, []):
            print("  %-7s %s%s" % (k.upper(), name, "" if guard is None else
                  "  (guard at line %d, line %d reaches a disconnect first)"
                  % (guard, reach)))
    for name, _, _, _, _, _ in by.get("helper", []):
        print("  helper  %s  (exec'd by another cfg; inherits its caller's setting)" % name)
    for name, _, _, _, saves, _ in by.get("saves", []):
        print("  SAVES   %s  writes ftesurf.cfg on purpose (line %s) -- run it on a "
              "copy of the install" % (name, ", ".join(map(str, saves))))
    bad = len(by.get("missing", [])) + len(by.get("late", []))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
