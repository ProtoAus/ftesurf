#!/usr/bin/env python3
"""prederr_triage.py -- read prederror reports (Patch 1195) and say where each one started.

A report is what a lobby stores in data/prederr/<map>/<utc>_<slot>.txt: the lobby's header, the
client's context (== context) and the engine's comparison ring (== ring), or the client's own
pair data/prederr/<stem>.txt + <stem>_ctx.txt.  For each report this prints the worst prederr,
the first ring row before it where the client and server disagree by more than --eps units, the
rows around that, and the context lines (server prints, mirror triggers, gates, warp ops) from
--window seconds before it to after the worst.

P1238: it also flags a stretch with no server packets before the worst row (ring rows are made
only when a server frame arrives), and, from a lobby report's == server section (the server's own
row for every command it ran, frozen when the client marked the error), lists the commands the
server ran across that stretch: which sequences it never ran, which were loss fills (kind 0), and
how many milliseconds it simulated against the client's.

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
SV_COLS = "t rt kind seq msec piece off ox oy oz vx vy vz movetype onground impulse".split()


def clean(s):
    """A report is client-written: no terminal control bytes reach the screen."""
    return "".join(c if c == "\t" or 32 <= ord(c) < 127 or ord(c) > 159 else "?" for c in s)


def numrows(lines, cols):
    rows = []
    for line in lines:
        f = line.split()
        if len(f) != len(cols) or line.startswith("#"):
            continue
        try:
            row = dict(zip(cols, map(float, f)))
            if all(math.isfinite(v) for v in row.values()):
                rows.append(row)
        except ValueError:
            continue
    return rows


def parse(text):
    head, ctx, ring, sv = [], [], [], []
    part = "head"
    for line in text.splitlines():
        if line.startswith("== context"):
            part = "ctx"
            continue
        if line.startswith("== ring"):
            part = "ring"
            continue
        if line.startswith("== server"):
            part = "sv"
            sv.append(line)
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
        elif part == "sv":
            sv.append(line)
    return head, ctx, numrows(ring, RING_COLS), sv


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


def gap_report(rows, wi):
    """No server frame arrived between the worst row and the one before it for longer than usual."""
    if wi == 0:
        print("  first row of the ring: no row before it to compare")
        return None
    dts = sorted(rows[i]["t"] - rows[i - 1]["t"] for i in range(1, len(rows)))
    med = dts[len(dts) // 2] if dts else 0
    prev, w = rows[wi - 1], rows[wi]
    gap = w["t"] - prev["t"]
    if gap < max(0.08, 3 * med):
        return None
    dp = math.dist((prev["sx"], prev["sy"], prev["sz"]), (w["px"], w["py"], w["pz"]))
    ds = math.dist((prev["sx"], prev["sy"], prev["sz"]), (w["sx"], w["sy"], w["sz"]))
    print("  GAP: no server packet for %.3f s before it (usual %.3f s); seq %d..%d were never acked on their own" % (
        gap, med, prev["seq"] + 1, w["seq"] - 1))
    print("       over it the prediction moved %.0f units and the server %.0f" % (dp, ds))
    return prev


def server_report(sv, rows, worst, prev):
    """The lobby's own rows: what it ran for the commands up to and just after the worst."""
    if not sv:
        print("  server rows: none (a report from before P1238)")
        return
    if sv[0].startswith("== server none"):
        print("  server rows: " + clean(sv[0][len("== server "):]))
        return
    for line in sv[1:]:
        if line.startswith(("mark ", "packet stalls")):
            print("  server: " + clean(line))
    srows = numrows(sv, SV_COLS)
    if not srows:
        print("  server rows: none in the section")
        return
    lo = (prev["seq"] if prev else worst["seq"] - 4)
    hi = worst["seq"] + 2
    span = [r for r in srows if (r["kind"] and lo <= r["seq"] <= hi)]
    fills = [r for r in srows if not r["kind"]]
    wt = next((r["t"] for r in srows if r["kind"] and r["seq"] == worst["seq"]), None)
    if wt is not None:
        near_fill = [r for r in fills if abs(r["t"] - wt) < 1.0]
        for line in sv[1:]:
            if line.startswith("stall ") and abs(float(line.split()[1]) - wt) < 2.0:
                print("  SERVER STALL near it: " + clean(line))
        if near_fill:
            print("  LOSS FILLS: the server ran %d command(s) of its own within 1 s of it (kind 0: a replayed "
                  "last command for lost packets)" % len(near_fill))
    ran = sorted({r["seq"] for r in span})
    missing = [s for s in range(int(lo) + 1, int(worst["seq"]) + 1) if s not in ran]
    msec = sum(r["piece"] for r in span if lo < r["seq"] <= worst["seq"])
    cms = sorted(r["msec"] for r in rows)
    nominal = cms[len(cms) // 2] if cms else 0
    n = int(worst["seq"] - lo)
    print("  server ran %d of the %d commands %d..%d: %.0f ms simulated against ~%.0f ms predicted" % (
        len([s for s in ran if s > lo and s <= worst["seq"]]), n, lo + 1, worst["seq"], msec, n * nominal))
    if missing:
        show = missing if len(missing) <= 12 else missing[:6] + ["..."] + missing[-4:]
        print("  NEVER RAN on the server: " + " ".join(str(s) for s in show))
    print("  server rows (t realtime kind seq msec piece offset origin velocity movetype ground impulse):")
    for r in span:
        print("    %9.3f %9.3f k%d %6d %5.1f %5.1f %5.1f  %9.1f %9.1f %9.1f  %7.1f %7.1f %7.1f  mt%d g%d i%d" % (
            r["t"], r["rt"], r["kind"], r["seq"], r["msec"], r["piece"], r["off"], r["ox"], r["oy"], r["oz"],
            r["vx"], r["vy"], r["vz"], r["movetype"], r["onground"], r["impulse"]))


def err(r):
    return math.dist((r["px"], r["py"], r["pz"]), (r["sx"], r["sy"], r["sz"]))


def triage(path, eps, window, around):
    head, ctx, rows, sv = load(path)
    print("=" * 78)
    print(path)
    for line in head[:7]:
        print("  " + clean(line))
    if not rows:
        print("  no ring rows")
        return
    worst = max(rows, key=err)
    # The line the report was made for (header "client <stem> worst N seq S"), not an excused one
    # elsewhere in the ring (P1238).
    m = next((re.search(r"worst [\d.]+ (?:at )?seq (\d+)", l) for l in head + ctx
              if re.search(r"worst [\d.]+ (?:at )?seq \d+", l)), None)
    if m:
        named = [r for r in rows if r["seq"] == int(m.group(1))]
        if named and err(named[0]) > eps:
            worst = named[0]
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
    prev = gap_report(rows, wi)
    server_report(sv, rows, worst, prev if prev is not None else (rows[wi - 1] if wi else None))
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
        got = out / Path(PI_DIR.rstrip("/")).name    # scp -r puts the folder itself under DIR
        paths += sorted(str(p) for p in got.rglob("*.txt") if not p.name.endswith("_ctx.txt"))
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
