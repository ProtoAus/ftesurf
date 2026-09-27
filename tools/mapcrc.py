#!/usr/bin/env python3
"""
mapcrc.py -- what `infokey(world, "*mapcrc")` says on THIS install, for a given map.

WHY THIS EXISTS.  Patch 450 made the Build 47 arm gate require a save to prove which
bsp it came from, and hand-authored save fixtures (cfg/test/p435rest.txt and friends)
carry no `mapcrc` -- so on a 450 build they cannot prove anything and the gate refuses
them.  That is correct behaviour and it is also a problem for the arms: several sections
exist to measure what the FORCED ARM does, and a gate that never fires makes them
measure nothing.  cfg/test/p445hop.cfg's L section is the sharpest case, since it is
Patch 445's own core reading.

So fixtures are STAMPED with the live crc at stage time rather than carrying a literal.
A literal would be wrong on every other machine: the value is `%08x` of the engine's
worldmodel checksum (server/pr_cmds.c), which depends on the installed .bsp.

HOW IT IS OBTAINED, and it is deliberately not a reimplementation.  Reproducing the
engine's checksum in Python would be a second spelling of a rule that lives in C, and
version-dependent -- exactly the drift this repo keeps finding.  Instead the GAME is
asked: a ten-second headless run loads the map, takes one `sl_save`, and quits, and the
crc is read out of the `mapcrc` line that Patch 450's own writer emitted.  The value
therefore comes from the same code path the readers compare against, which is the
strongest source available short of asking the engine directly.

Cached in the scratchpad per (map, exe) so the cost is paid once per session.  Delete the
cache if the installed map changes -- and note that a STALE cache is silent, which is why
the file records the bsp's size and mtime beside the value and refuses a cache whose bsp
has moved.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMEDIR = os.path.join(ROOT, "ftesurf")
CFGDIR = os.path.join(GAMEDIR, "cfg", "test")

MOM = os.environ.get("MOMENTUM_DIR",
                     r"C:\Program Files (x86)\Steam\steamapps\common"
                     r"\Momentum Mod Playtest\momentum")


def _cachepath():
    d = os.environ.get("CLAUDE_SCRATCH") or os.path.join(ROOT, "ftesurf", "logs")
    return os.path.join(d, "mapcrc.cache.json")


def _bspstat(mapname):
    """(size, mtime) of the installed bsp, so a stale cache is caught rather than used."""
    for base in (os.path.join(GAMEDIR, "maps"), os.path.join(MOM, "maps")):
        p = os.path.join(base, mapname + ".bsp")
        if os.path.exists(p):
            st = os.stat(p)
            return [st.st_size, int(st.st_mtime)]
    return None


def probe(mapname, exe="ftesurf64.exe", timeout=90):
    """Run the game once and read the crc out of a save it writes.  -> str or ''."""
    saves = os.path.join(GAMEDIR, "data", "saves", mapname)
    park = saves + ".crcpark"
    log = os.path.join(GAMEDIR, "logs", "mapcrc.log")
    cfg = os.path.join(CFGDIR, "mapcrc.cfg")

    with open(cfg, "w", newline="\n") as fh:
        fh.write("cfg_save_auto 0\n"
                 "// Written by tools/mapcrc.py.  One save, one map, then quit -- the crc\n"
                 "// is read out of the state.txt this produces.  Not hand-maintained.\n"
                 "log_enable 1\nlog_dir logs\nlog_name mapcrc\n"
                 "developer 1\nlog_developer 1\ncl_idlefps 0\ncl_maxfps 100\n"
                 "fs_missingwarn 0\ncon_notifylines 0\nsv_port 27709\nsv_cheats 0\n"
                 "set run_resume 0\nvid_fullscreen 0\n"
                 "waitms 4000\nmap %s\nwaitmap 2400\nwaitms 2500\n"
                 "menu_restart\nui_close\nwaitms 1000\n"
                 "cmd sl_save\nwaitms 1200\nquit\n" % mapname)

    if os.path.isdir(park):
        raise SystemExit("refusing: %s exists (a previous probe did not restore)" % park)
    if os.path.isdir(saves):
        os.rename(saves, park)
    try:
        flags = 0x08000000 if os.name == "nt" else 0
        p = subprocess.Popen([os.path.join(ROOT, exe), "-WindowStyle", "Minimized",
                              "+exec", "cfg/test/mapcrc.cfg"], cwd=ROOT,
                             creationflags=flags,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t0 = time.time()
        while p.poll() is None and time.time() - t0 < timeout:
            time.sleep(1)
        if p.poll() is None:
            p.kill()
            raise SystemExit("the crc probe did not exit in %g s" % timeout)
        crc = ""
        for dirpath, _, files in os.walk(saves):
            for f in files:
                if f != "state.txt":
                    continue
                with open(os.path.join(dirpath, f), errors="replace") as sf:
                    m = re.search(r"^mapcrc\s*(\S*)\s*$", sf.read(), re.M)
                if m and m.group(1):
                    crc = m.group(1)
        return crc
    finally:
        # No `except: pass` -- a probe that leaves the shared saves dir parked would
        # break every later arm silently.
        if os.path.isdir(saves):
            shutil.rmtree(saves)
        if os.path.isdir(park):
            os.rename(park, saves)
        if os.path.exists(cfg):
            os.remove(cfg)


def get(mapname, exe="ftesurf64.exe", refresh=False):
    """Cached crc for `mapname`, or '' if this build cannot produce one."""
    cp = _cachepath()
    stat = _bspstat(mapname)
    if not refresh and os.path.exists(cp):
        try:
            with open(cp) as fh:
                c = json.load(fh)
        except (OSError, ValueError):
            c = {}
        row = c.get(mapname)
        # A stale cache is SILENT, so the bsp's identity is checked rather than trusted.
        if row and row.get("bsp") == stat and row.get("crc"):
            return row["crc"]
    crc = probe(mapname, exe)
    try:
        with open(cp) as fh:
            c = json.load(fh)
    except (OSError, ValueError):
        c = {}
    c[mapname] = {"crc": crc, "bsp": stat}
    os.makedirs(os.path.dirname(cp), exist_ok=True)
    with open(cp, "w") as fh:
        json.dump(c, fh, indent=1)
    return crc


def stamp(path, crc):
    """Insert or replace a `mapcrc` line in a save fixture, in place.

    Idempotent, and it inserts after `map` so the file keeps the shape the writer
    produces -- a reader is a key-match loop and does not care, but a human diffing a
    fixture against a real save does.
    """
    with open(path, encoding="utf-8", newline="") as fh:
        lines = fh.read().split("\n")
    out, done = [], False
    for l in lines:
        if l.startswith("mapcrc "):
            continue                      # drop any existing one; re-added below
        out.append(l)
        if l.startswith("map ") and not done:
            out.append("mapcrc %s" % crc)
            done = True
    if not done:
        raise SystemExit("%s has no `map` line to stamp after" % path)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out))


if __name__ == "__main__":
    m = sys.argv[1] if len(sys.argv) > 1 else "bhop_eazy"
    r = "--refresh" in sys.argv
    v = get(m, refresh=r)
    print("%s *mapcrc = %r%s" % (m, v, "" if v else "   (empty: this build/map cannot hash)"))
