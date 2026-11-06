#!/usr/bin/env python3
"""prederr_triage.py -- read prederror reports (Patch 1195) and say where each one started.

A report is what a lobby stores in data/prederr/<map>/<utc>_<slot>.txt: the lobby's header, the
client's context (== context) and the engine's comparison ring (== ring), or the client's own
pair data/prederr/<stem>.txt + <stem>_ctx.txt.  For each report this prints the worst prederr,
the first ring row before it where the client and server disagree by more than --eps units, the
rows around that, and the context lines (server prints, mirror triggers, gates, warp ops) from
--window seconds before it to after the worst.

Comparison rows are selective, not a packet/ACK journal. The bounded == server section records
command-part observations, sampled at the next PlayerPreThink. Missing rows do not prove lost
packets or commands that never executed. Piece durations are input time, not measured simulation
time. Native v1 command fields may also have the pre-P1326 identity defect; provenance is shown
before interpreting them. Native v2 adds event-time prediction provenance without regrading v1.

Usage:
    python tools/prederr_triage.py REPORT [REPORT ...]
    python tools/prederr_triage.py --fetch DIR      # copy the lobbies' data/prederr/ here, then read it

For a local snapshot without an error popup, run `prederr_dump boomer_check.txt`
in the game console, then read ftesurf/data/prederr/boomer_check.txt with this tool.
That captures retained comparisons locally; it does not upload a report.
No above-epsilon difference describes only those rows, not earlier/future errors.
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
RING_V2_COLS = RING_COLS + "cmdvalid predvalid predpm seedseq seedcarry phasehit parts ticks".split()
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
    ring_version = 1
    for line in text.splitlines():
        if line.startswith("== context"):
            part = "ctx"
            continue
        if line.startswith("== ring"):
            part = "ring"
            continue
        if line.startswith("== server"):
            if sv:
                part = "tail"           # only the lobby's own section; a client chunk can spell it too
                continue
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
            if line.startswith("FTESURF-PREDRING"):
                head.append(line)
                try:
                    ring_version = int(line.split()[1])
                except (ValueError, IndexError):
                    ring_version = 0
            elif line.startswith(("# engine ", "# command_identity ")):
                head.append(line)
            ring.append(line)
        elif part == "sv":
            sv.append(line)
    cols = {1: RING_COLS, 2: RING_V2_COLS}.get(ring_version)
    if cols is None:
        head.append("unsupported ring schema %d" % ring_version)
    return head, ctx, numrows(ring, cols) if cols is not None else [], sv


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


def provenance(head, ctx):
    """Allowlist diagnostics, never echo the lobby's account/address headers."""
    for prefix in ("FTESURF-PREDRING", "# engine ", "# command_identity ", "unsupported ring schema"):
        line = next((s for s in head if s.startswith(prefix)), None)
        if line:
            print("  " + clean(line))
    reporter = next((s for s in ctx if s.startswith("reporter ")), None)
    if reporter:
        print("  " + clean(reporter))
    binding = any(s == "# command_identity ack-seat-tag-v1" for s in head)
    if binding:
        print("  command identity: declared acknowledged move/local seat, sequence-tag checked (not attestation)")
    else:
        engine = next((s for s in head if s.startswith("# engine ")), "")
        patch = re.search(r"patch-(\d+)", engine)
        label = "pre-P1326 command identity not qualified" if patch and int(patch.group(1)) < 1326 else "command identity not qualified by this dump"
        print("  WARNING: " + label + "; timing/angles/movement/buttons may belong to another command")
    return binding


def gap_report(rows, wi):
    """Describe gaps between retained comparisons, not unobserved packet history."""
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
    print("  COMPARISON GAP: %.3f s between retained samples (usual %.3f s); no comparisons for seq %d..%d" % (
        gap, med, prev["seq"] + 1, w["seq"] - 1))
    print("       packet receipt/ACK history unknown; sampled endpoint displacements: predicted %.0f, authoritative %.0f units" % (dp, ds))
    return prev


def server_report(sv, rows, worst, prev):
    """Observed command identities and delayed body samples in a frozen window."""
    if not sv:
        print("  server section absent; command receipt/execution unknown")
        return
    if sv[0].startswith("== server none"):
        print("  server rows: " + clean(sv[0][len("== server "):]))
        return
    for line in sv[1:]:
        if line.startswith("packet stalls"):
            print("  server counters (not window-local): " + clean(line))
        elif line.startswith("mark "):
            print("  server: " + clean(line))
    srows = numrows(sv, SV_COLS)
    if not srows:
        print("  server rows: none in the section")
        return
    tagged = [r for r in srows if r["kind"]]
    if tagged:
        print("  captured SV tagged bounds: %d..%d; %d total rows" % (
            min(r["seq"] for r in tagged), max(r["seq"] for r in tagged), len(srows)))
    print("  SV body/mode sampled at next PreThink; inter-command transitions can change them")
    lo = max(prev["seq"] if prev else worst["seq"] - 4, worst["seq"] - 2000)
    hi = worst["seq"] + 2
    span = [r for r in srows if (r["kind"] and lo <= r["seq"] <= hi)]
    fills = [r for r in srows if not r["kind"]]
    wt = next((r["t"] for r in srows if r["kind"] and r["seq"] == worst["seq"]), None)
    if wt is not None:
        near_fill = [r for r in fills if abs(r["t"] - wt) < 1.0]
        for line in sv[1:]:
            f = line.split()
            try:
                near = line.startswith("stall ") and len(f) >= 3 and abs(float(f[1]) - wt) < 2.0
            except ValueError:
                near = False
            if near:
                print("  SERVER STALL near it: " + clean(line))
        if near_fill:
            print("  KIND 0: %d untagged observations within 1 s; loss-fill/special input cannot be distinguished here" % len(near_fill))
    ran = {r["seq"] for r in span}
    missing = [s for s in range(int(lo) + 1, int(worst["seq"]) + 1) if s not in ran]
    msec = sum(r["piece"] for r in span if lo < r["seq"] <= worst["seq"])   # one row per piece
    n = int(worst["seq"] - lo)
    print("  observed tagged identities %d/%d in seq %d..%d: %.1f ms logged input-piece duration" % (
        len([s for s in ran if lo < s <= worst["seq"]]), n, lo + 1, worst["seq"], msec))
    print("  predicted/authoritative simulated duration unknown without event-time tick/carry evidence")
    if missing:
        show = missing if len(missing) <= 12 else missing[:6] + ["..."] + missing[-4:]
        print("  no matching tagged SV row captured: " + " ".join(str(s) for s in show))
        print("  absence is not proof of nonexecution: bounded capture/untagged paths may omit identities")
    print("  server rows (t realtime kind seq msec piece offset origin velocity movetype ground impulse):")
    for r in span:
        print("    %9.3f %9.3f k%d %6d %5.1f %5.1f %5.1f  %9.1f %9.1f %9.1f  %7.1f %7.1f %7.1f  mt%d g%d i%d" % (
            r["t"], r["rt"], r["kind"], r["seq"], r["msec"], r["piece"], r["off"], r["ox"], r["oy"], r["oz"],
            r["vx"], r["vy"], r["vz"], r["movetype"], r["onground"], r["impulse"]))


def err(r):
    return math.dist((r["px"], r["py"], r["pz"]), (r["sx"], r["sy"], r["sz"]))


def print_comparison(r, mark, binding):
    inputs = "inputs" if binding and r.get("cmdvalid") == 1 else "inputs(unqualified)"
    print("   %s seq %5d err %8.2f  pred %9.1f %9.1f %9.1f  srv %9.1f %9.1f %9.1f  pvz %7.1f "
          "gnd %d/%d pm %d  %s move %d %d %d btn %d" % (
              mark, r["seq"], err(r), r["px"], r["py"], r["pz"], r["sx"], r["sy"], r["sz"], r["pvz"],
              r["pground"], r["sground"], r["pmtype"], inputs, r["fwd"], r["side"], r["up"], r["buttons"]))
    if r.get("predvalid") == 1:
        print("       saved prediction: pm %d, seed seq %d carry %.6f ms, phase hit %d, parts %d ticks %d" % (
            r["predpm"], r["seedseq"], r["seedcarry"] * 1000, r["phasehit"], r["parts"], r["ticks"]))
        if r["predpm"] != r["pmtype"]:
            print("       movement-mode boundary observed; not automatically expected or excused")


def triage(path, eps, window, around):
    head, ctx, rows, sv = load(path)
    print("=" * 78)
    print(path)
    for line in head:
        if line.startswith(("utc ", "map ", "client ")):
            print("  " + clean(line))
    binding = provenance(head, ctx)
    if not rows:
        print("  no valid ring rows for the declared schema; report not graded")
        return False
    print("  ring: %d rows, seq %d..%d, %.1f s" % (len(rows), rows[0]["seq"], rows[-1]["seq"],
                                                   rows[-1]["t"] - rows[0]["t"]))
    worst = max(rows, key=err)
    if err(worst) <= eps:
        print("  no disagreement above eps %.3g in retained ring (largest %.3f units)" % (eps, err(worst)))
        print("  diagnostic snapshot only; errors outside these retained position comparisons are unknown")
        print("  last retained comparisons:")
        for r in (rows[-around:] if around > 0 else []):
            print_comparison(r, " ", binding)
        return True
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
    print("  worst: seq %d off by %.1f (predicted %.1f %.1f %.1f, server %.1f %.1f %.1f)" % (
        worst["seq"], err(worst), worst["px"], worst["py"], worst["pz"], worst["sx"], worst["sy"], worst["sz"]))
    print("  disagreement starts at seq %d (%d retained comparisons before the worst, eps %.1f)" % (
        rows[first]["seq"], wi - first, eps))
    prev = gap_report(rows, wi)
    server_report(sv, rows, worst, prev if prev is not None else (rows[wi - 1] if wi else None))
    print("  rows around the start:")
    for r in rows[max(0, first - around):min(len(rows), wi + around + 1)]:
        mark = "*" if r is worst else (">" if r is rows[first] else " ")
        print_comparison(r, mark, binding)
    lo, hi = rows[first]["seq"] - window * 70, worst["seq"] + 20
    print("  context (seq %d..%d):" % (lo, hi))
    for line in ctx:
        m = re.match(r"([\d.]+) (\d+) (.*)", line)
        if m and lo <= int(m.group(2)) <= hi:
            print("    " + clean(line))
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("reports", nargs="*")
    ap.add_argument("--fetch", metavar="DIR", help="scp the lobbies' data/prederr/ into DIR first")
    ap.add_argument("--eps", type=float, default=1.0, help="units of disagreement that count (default 1)")
    ap.add_argument("--window", type=float, default=2.0, help="context seconds before the start")
    ap.add_argument("--around", type=int, default=4, help="ring rows shown around the start")
    a = ap.parse_args()
    paths = list(a.reports)
    failed = False
    if a.fetch:
        out = Path(a.fetch)
        out.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["scp", "-o", "BatchMode=yes", "-r", PI + ":" + PI_DIR, str(out)],
                           capture_output=True, text=True)
        if r.returncode:
            failed = True
            print(r.stderr.strip() or "scp failed", file=sys.stderr)
        got = out / Path(PI_DIR.rstrip("/")).name    # scp -r puts the folder itself under DIR
        paths += sorted(str(p) for p in got.rglob("*.txt") if not p.name.endswith("_ctx.txt"))
    if not paths:
        ap.error("no reports")
    for p in paths:
        try:
            if triage(p, a.eps, a.window, a.around) is False:
                failed = True
        except (OSError, ValueError) as e:
            failed = True
            print("%s: not read (%s)" % (p, e))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
