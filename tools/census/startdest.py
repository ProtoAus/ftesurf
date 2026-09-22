#!/usr/bin/env python3
"""
startdest.py -- which shipped start regions put a placed body BELOW its own zone.

Patch 415 measured that a save loaded into a start box often lands a hair outside
the zone, so Build 47's gate (which forces the zone edge and lets the next scan
arm the attempt clean) never fires there.  The mechanism is state.txt's
`origin %.4f` against a zone `bottom` that has more decimals than four: the placed
origin rounds to 64.0312 where the slab starts at 64.03125.

Patch 435 answers the velocity instead of the rounding, and only where the gate
can fire -- so the population that stays exposed is exactly this census's second
column, and only on a non-bhop mode (p435hop/p435mode measure both).

    python tools/census/startdest.py [--zones <dir>]

Default --zones is the local Momentum install's shipped library.  Counts REGIONS
with an authored teleDestPos, per track and per segment, and names the maps.

Patch 415's essay quotes "37 of 48 sampled regions"; this counts 6 of 35 over the
whole shipped library.  The two are not the same sample and this one is the one a
reader can re-run.
"""
import argparse
import collections
import glob
import json
import os
import sys

DEFAULT = (r"C:\Program Files (x86)\Steam\steamapps\common"
           r"\Momentum Mod Playtest\momentum\maps\zones\online")


def walk(zones_dir):
    for path in sorted(glob.glob(os.path.join(zones_dir, "*.json"))):
        name = os.path.basename(path)[:-5]
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as exc:
            print("  ! %s: %s" % (name, exc), file=sys.stderr)
            continue
        tracks = data.get("tracks")
        if not isinstance(tracks, dict):
            continue
        for tname, track in tracks.items():
            if not isinstance(track, dict):
                continue
            zt = track.get("zones")
            if not isinstance(zt, dict):
                continue
            for si, seg in enumerate(zt.get("segments") or []):
                if not isinstance(seg, dict):
                    continue
                for cp in seg.get("checkpoints", []):
                    if not isinstance(cp, dict):
                        continue
                    for reg in cp.get("regions", []):
                        if not isinstance(reg, dict):
                            continue
                        yield name, tname, si, reg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zones", default=DEFAULT)
    a = ap.parse_args()
    if not os.path.isdir(a.zones):
        raise SystemExit("no such zones dir: %s" % a.zones)

    fires, bites = [], []
    for name, tname, si, reg in walk(a.zones):
        dest, bot = reg.get("teleDestPos"), reg.get("bottom")
        if not isinstance(dest, list) or not isinstance(bot, (int, float)):
            continue
        # What SV_SaveWriteState writes and SV_SaveReadLight reads back.
        placed = float("%.4f" % dest[2])
        row = (name, tname, si, bot, placed)
        (fires if placed >= bot else bites).append(row)

    total = len(fires) + len(bites)
    print("regions with an authored teleDestPos: %d" % total)
    print("  gate FIRES  (placed origin at or above the slab bottom): %d" % len(fires))
    print("  rounding BITES (placed origin below it, gate cannot fire):  %d" % len(bites))
    bymap = collections.defaultdict(list)
    for row in bites:
        bymap[row[0]].append(row)
    print("\nthe exposed maps:")
    for name in sorted(bymap):
        rows = bymap[name]
        print("  %-28s %s" % (name, ", ".join(
            "%s seg%d bottom %.7f -> placed %.4f" % (r[1], r[2], r[3], r[4])
            for r in rows)))
    print("\nmode matters: on bhop/bhop-hl1 SV_TimerTryArm refuses to arm an")
    print("attempt that is already RUNNING, so a hop starts the run instead of")
    print("arming it (cfg/test/p435hop.cfg).  Any other mode arms outright")
    print("(cfg/test/p435mode.cfg, sv_gamemode surf).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
