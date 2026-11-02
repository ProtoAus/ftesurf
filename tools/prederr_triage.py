#!/usr/bin/env python3
"""prederr_triage.py -- read prederror reports (Patch 1195) and say where each one started.

A report is what a lobby stores in data/prederr/<map>/<utc>_<slot>.txt: the lobby's header, the
client's context (== context) and the engine's comparison ring (== ring), or the client's own
pair data/prederr/<stem>.txt + <stem>_ctx.txt.  For each report this prints the worst prederr,
the first ring row before it where the client and server disagree by more than --eps units, the
rows around that, and the context lines (server prints, mirror triggers, gates, warp ops) from
--window seconds before it to after the worst.

Usage:
    python tools/prederr_triage.py REPORT [REPORT ...]
    python tools/prederr_triage.py --fetch DIR      # copy the lobbies' data/prederr/ here, then read it
"""
import argparse
import math
import re
import subprocess
import sys
from pathlib import Path

PI = "proto@192.168.1.102"
PI_DIR = "/srv/nvme/ftesurf-server/game/ftesurf/data/prederr/"
RING_COLS = ("t seq px py pz sx sy sz pvx pvy pvz svx svy svz pground sground pmtype msec "
             "pitch yaw roll fwd side up buttons").split()


def clean(s):
    """A report is client-written: no terminal control bytes reach the screen."""
    return "".join(c if c == "\t" or 32 <= ord(c) < 127 or ord(c) > 159 else "?" for c in s)


def parse(text):
    head, ctx, ring = [], [], []
    part = "head"
    for line in text.splitlines():
        if line.startswith("== context"):
            part = "ctx"
            continue
        if line.startswith("== ring"):
            part = "ring"
            continue
        if line.startswith("== "):
            part = "tail"
            continue
        if part == "head":
            head.append(line)
        elif part == "ctx":
            ctx.append(line)
        elif part == "ring":
            ring.append(line)
    rows = []
    for line in ring:
        f = line.split()
        if len(f) != len(RING_COLS) or line.startswith("#"):
            continue
        try:
            row = dict(zip(RING_COLS, map(float, f)))
            if all(math.isfinite(v) for v in row.values()):
                rows.append(row)
        except ValueError:
            continue
    return head, ctx, rows


def load(path):
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    if text.startswith("FTESURF-PREDRING"):
        ctx = p.with_name(p.stem + "_ctx.txt")
        ctx_text = ctx.read_text(encoding="utf-8", errors="replace") if ctx.exists() else ""
        text = "== context\n" + ctx_text + "\n== ring\n" + text
    elif text.startswith("FTESURF-PREDCTX"):
        ring = p.with_name(p.stem[:-4] + ".txt")
        text = "== context\n" + text + "\n== ring\n" + (ring.read_text(errors="replace") if ring.exists() else "")
    return parse(text)


def err(r):
    return math.dist((r["px"], r["py"], r["pz"]), (r["sx"], r["sy"], r["sz"]))


def triage(path, eps, window, around):
    head, ctx, rows = load(path)
    print("=" * 78)
    print(path)
    for line in head[:7]:
        print("  " + clean(line))
    if not rows:
        print("  no ring rows")
        return
    worst = max(rows, key=err)
    wi = rows.index(worst)
    first = wi
    while first > 0 and err(rows[first - 1]) > eps:
        first -= 1
    print("  ring: %d rows, seq %d..%d, %.1f s" % (len(rows), rows[0]["seq"], rows[-1]["seq"],
                                                   rows[-1]["t"] - rows[0]["t"]))
    print("  worst: seq %d off by %.1f (predicted %.1f %.1f %.1f, server %.1f %.1f %.1f)" % (
        worst["seq"], err(worst), worst["px"], worst["py"], worst["pz"], worst["sx"], worst["sy"], worst["sz"]))
    print("  disagreement starts at seq %d (%d commands before the worst, eps %.1f)" % (
        rows[first]["seq"], wi - first, eps))
    print("  rows around the start:")
    for r in rows[max(0, first - around):min(len(rows), wi + around + 1)]:
        mark = "*" if r is worst else (">" if r is rows[first] else " ")
        print("   %s seq %5d err %8.2f  pred %9.1f %9.1f %9.1f  srv %9.1f %9.1f %9.1f  pvz %7.1f "
              "gnd %d/%d pm %d  move %d %d %d btn %d" % (
                  mark, r["seq"], err(r), r["px"], r["py"], r["pz"], r["sx"], r["sy"], r["sz"], r["pvz"],
                  r["pground"], r["sground"], r["pmtype"], r["fwd"], r["side"], r["up"], r["buttons"]))
    lo, hi = rows[first]["seq"] - window * 70, worst["seq"] + 20
    print("  context (seq %d..%d):" % (lo, hi))
    for line in ctx:
        m = re.match(r"([\d.]+) (\d+) (.*)", line)
        if m and lo <= int(m.group(2)) <= hi:
            print("    " + clean(line))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("reports", nargs="*")
    ap.add_argument("--fetch", metavar="DIR", help="scp the lobbies' data/prederr/ into DIR first")
    ap.add_argument("--eps", type=float, default=1.0, help="units of disagreement that count (default 1)")
    ap.add_argument("--window", type=float, default=2.0, help="context seconds before the start")
    ap.add_argument("--around", type=int, default=4, help="ring rows shown around the start")
    a = ap.parse_args()
    paths = list(a.reports)
    if a.fetch:
        out = Path(a.fetch)
        out.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["scp", "-o", "BatchMode=yes", "-r", PI + ":" + PI_DIR, str(out)],
                           capture_output=True, text=True)
        if r.returncode:
            print(r.stderr.strip() or "scp failed", file=sys.stderr)
        paths += sorted(str(p) for p in out.rglob("*.txt") if not p.name.endswith("_ctx.txt"))
    if not paths:
        ap.error("no reports")
    for p in paths:
        try:
            triage(p, a.eps, a.window, a.around)
        except (OSError, ValueError) as e:
            print("%s: not read (%s)" % (p, e))
    return 0


if __name__ == "__main__":
    sys.exit(main())
