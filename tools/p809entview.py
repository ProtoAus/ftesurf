#!/usr/bin/env python3
"""Patch 809: ent_view's MOUSE3 is a bind, not a key the input chain keeps.

python tools/p809entview.py --progs <dir> --out <root> [--control]

A local game in an owned basedir (default.cfg from the tree under test). MOUSE3 is
fed through the input chain (`vote key`, CL_InputEvent): the subject passes it on
(took 0, no overlay) and default.cfg binds it to ent_cursor; the control takes it
and opens the overlay itself. Rebound to `noclip` by `bind`, the key's bind is
what runs, and config_menu lists the Entity view row.
"""
import argparse
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from p808rewind import prepare, unjunction  # noqa: E402
from p811savesync import client  # noqa: E402

CFG = """waitms 3000
map surf_dune
waitmap 60
waitms 6000
menu_restart
ui_close
waitms 500
echo ==== P809 CHAIN ====
vote key 514 1
waitms 300
vote key 514 0
waitms 300
echo ==== P809 BIND ====
bind MOUSE3
config_menu status
config_menu
waitms 800
screenshot p809keys
waitms 800
config_menu
waitms 300
ent_cursor 0
waitms 300
echo ==== P809 TYPED ====
ent_cursor
waitms 300
ent_cursor 0
waitms 300
quit
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--progs", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--exe", default="C:/FTESurf/ftesurf64.exe")
    ap.add_argument("--control", action="store_true")
    args = ap.parse_args()
    rig = args.out / time.strftime("rig-%Y%m%dT%H%M%S")
    made = []
    try:
        cl, made = prepare(rig, args.progs, [], 0)
        log = client(args, rig, "p809", CFG)
    finally:
        unjunction(made)
    faults = 0

    def check(name, ok, detail):
        nonlocal faults
        faults += not ok
        print(("PASS" if ok else "FAIL"), name, "--", detail)

    chain = log.split("==== P809 CHAIN ====")[-1].split("==== P809 BIND ====")[0]
    took = re.findall(r"vote key: scan 514 down 1 took (\d)", chain)
    opened = "ent_cursor^7: on" in chain or "ent_cursor: on" in chain
    if args.control:
        check("chain-takes (control)", took == ["1"] and opened, f"took {took}, overlay opened {opened}")
    else:
        check("chain-passes", took == ["0"] and not opened, f"took {took}, overlay opened {opened}")
        bind = log.split("==== P809 BIND ====")[-1].split("==== P809 TYPED ====")[0]
        check("default-bind", re.search(r'"MOUSE3" = "ent_cursor"', bind) is not None,
              re.findall(r'MOUSE3.*', bind)[:2])
        check("panel-row", re.search(r"entview.*ent_cursor.*MOUSE3", bind, re.I) is not None,
              re.findall(r".*entview.*", bind)[:1])
    typed = log.split("==== P809 TYPED ====")[-1]
    check("typed", "on --" in typed, "ent_cursor typed still opens the overlay")
    print("rig:", rig)
    print(f"{faults} failed")
    return faults


if __name__ == "__main__":
    raise SystemExit(main())
