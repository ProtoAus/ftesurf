#!/usr/bin/env python3
"""runcompare -- where does a run lose time to a reference run, and on what?

    python3 tools/runcompare.py REF.rec RUN.rec [RUN.rec ...] [--json out.json]

Runs are lined up by POSITION along the reference path (nearest point, monotone), so
"behind" means behind at the same place. Splits are cut at the reference's ramp boards,
where lines converge, so the best splits of several runs can be added up. Works on any
FTESURF-REC with samples: our recordings, KSF/Momentum imports, a fork's or a bot's.
Contact is read from physics (free flight drops vz by exactly g dt), so imports without
surface normals work. First use: surf_sandtrap2 bonus 4, 117 replays (20 Nov 2026).
"""

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tasplaus  # noqa: E402  one sample reader

G = 800.0


def load(path):
    run = tasplaus.read(path)
    rate = float(run.hdr.get("movetickrate") or run.hdr.get("tickrate") or 0.015)
    rows = []
    for i, (t, o, v) in enumerate(run.samples):
        rows.append({"t": t, "o": o, "v": v, "yaw": run.yaw[i] if i < len(run.yaw) else 0.0})
    for a, b in zip(rows, rows[1:]):
        dt = b["t"] - a["t"]
        dvz = b["v"][2] - a["v"][2]
        if dt > 0 and abs(dvz + G * dt) < 0.6:
            a["c"] = "air"
        elif abs(a["v"][2]) < 0.01 and abs(b["v"][2]) < 0.01:
            a["c"] = "ground"
        else:
            a["c"] = "ramp"
    if rows:
        rows[-1]["c"] = rows[-2]["c"] if len(rows) > 1 else "air"
    kt = run.hdr.get("ksftime")
    fin = run.end * rate if run.end else None
    return {"path": path, "owner": run.hdr.get("owner", os.path.basename(path)), "rows": rows,
            "rate": rate, "clock_finish": fin, "time": float(kt) if kt else fin,
            "source": (run.hdr.get("foreign") or "ftesurf").split()[0]}


def hs(r):
    return math.hypot(r["v"][0], r["v"][1])


def ref_path(ref):
    pts = [r for r in ref["rows"] if 0 <= r["t"] <= (ref["clock_finish"] or 1e9)]
    s = [0.0]
    for a, b in zip(pts, pts[1:]):
        s.append(s[-1] + math.dist(a["o"], b["o"]))
    return pts, s


def project(pts, s, run):
    out, j, n = [], 0, len(pts)
    for r in run["rows"]:
        if r["t"] < 0:
            continue
        best, bj, bu = 1e18, j, 0.0
        for k in range(max(0, j - 3), min(n - 1, j + 40)):
            a, b = pts[k]["o"], pts[k + 1]["o"]
            ab = [b[i] - a[i] for i in range(3)]
            L2 = sum(x * x for x in ab) or 1e-9
            u = max(0.0, min(1.0, sum((r["o"][i] - a[i]) * ab[i] for i in range(3)) / L2))
            d = math.dist([a[i] + u * ab[i] for i in range(3)], r["o"])
            if d < best:
                best, bj, bu = d, k, u
        j = bj
        sp = s[bj] + bu * (s[bj + 1] - s[bj])
        if out and sp < out[-1][0]:
            sp = out[-1][0]
        out.append((sp, r["t"], best, r))
    return out


def t_at(curve, sq):
    for (s0, t0, _, _), (s1, t1, _, _) in zip(curve, curve[1:]):
        if s1 >= sq:
            return t1 if s1 == s0 else t0 + (t1 - t0) * (sq - s0) / (s1 - s0)
    return None


def ramps(rows, t_from=0.0, t_to=1e9, gap=2):
    """Contiguous ramp-contact rides as (first, last) row indices."""
    out = []
    for i, r in enumerate(rows):
        if not (t_from <= r["t"] <= t_to) or r["c"] != "ramp":
            continue
        if out and i - out[-1][1] <= gap:
            out[-1][1] = i
        else:
            out.append([i, i])
    return [(a, b) for a, b in out if rows[b]["t"] - rows[a]["t"] >= 0.06]


def metrics(run):
    rows = run["rows"]
    fin = run["clock_finish"] or rows[-1]["t"]
    t0 = min(rows, key=lambda r: abs(r["t"]))
    jump = None
    for a, b in zip(rows, rows[1:]):
        if -1.5 <= b["t"] <= 0.5 and a["c"] != "air" and b["c"] == "air" and b["v"][2] > 100:
            jump = b["t"]
    rides = []
    for a, b in ramps(rows, 0.0, fin):
        ride = rows[a:b + 1]
        rides.append({"board_t": rows[a]["t"], "board_speed": hs(rows[a]), "leave_t": rows[b]["t"],
                      "leave_speed": hs(rows[b]), "leave_z": rows[b]["o"][2], "leave_vz": rows[b]["v"][2],
                      "low_z": min(r["o"][2] for r in ride), "top_speed": max(hs(r) for r in ride)})
    last = rides[-1]["leave_t"] if rides else 0.0
    tail = [r for r in rows if last <= r["t"] <= fin]
    turn = sum(abs(((b["yaw"] - a["yaw"] + 180) % 360) - 180) for a, b in zip(tail, tail[1:]))
    path = sum(math.dist(a["o"], b["o"]) for a, b in zip(tail, tail[1:]))
    return {"start_speed": hs(t0), "jump_t": jump, "rides": rides,
            "final_air": {"time": fin - last, "path": path, "turn_deg": turn}}


def compare(ref, runs):
    pts, s = ref_path(ref)
    rr = ramps(pts)
    cuts = [("start", 0.0)] + [(f"ramp {i + 2} board", s[a]) for i, (a, b) in enumerate(rr[1:])]
    res = []
    for run in [ref] + runs:
        c = project(pts, s, run)
        marks = [0.0] + [t_at(c, sq) for _, sq in cuts[1:]] + [run["clock_finish"]]
        splits = [None if a is None or b is None else b - a for a, b in zip(marks, marks[1:])]
        res.append({"owner": run["owner"], "time": run["time"], "source": run["source"],
                    "marks": marks, "splits": splits, "max_off_line": max(p[2] for p in c) if c else None,
                    "metrics": metrics(run)})
    names = [f"{a} -> {b}" for (a, _), (b, _) in zip(cuts, cuts[1:] + [("finish", 0)])]
    return names, res


def report(names, res):
    ref = res[0]
    print(f"reference {ref['owner']} {ref['time']:.3f}s; splits cut at its ramp boards")
    w = max(len(n) for n in names)
    print(f"{'':{w}}  " + "  ".join(f"{r['owner'][:10]:>10}" for r in res))
    for i, n in enumerate(names):
        cells = []
        for r in res:
            v = r["splits"][i]
            if v is None:
                cells.append(f"{'off line':>10}")
            elif r is ref:
                cells.append(f"{v:10.3f}")
            else:
                cells.append(f"{v - ref['splits'][i]:+10.3f}")
        print(f"{n:{w}}  " + "  ".join(cells))
    if len(res) >= 3:
        best = []
        for i in range(len(names)):
            ok = [r for r in res if r["splits"][i] is not None]
            b = min(ok, key=lambda r: r["splits"][i])
            best.append((names[i], b["splits"][i], b["owner"]))
        tot = sum(x[1] for x in best)
        print(f"\nsum of best splits {tot:.3f}s (reference on the same clock {ref['marks'][-1]:.3f}s)")
        for n, v, o in best:
            print(f"  {n:{w}}  {v:.3f}  {o}")
    print()
    for r in res:
        m = r["metrics"]
        j = f"{m['jump_t']:+.3f}s" if m["jump_t"] is not None else "-"
        print(f"{r['owner'][:16]:16} start {m['start_speed']:5.0f} u/s  jump {j}  final air {m['final_air']['time']:.3f}s"
              f" path {m['final_air']['path']:.0f}u turn {m['final_air']['turn_deg']:.0f} deg")
        for k, d in enumerate(m["rides"]):
            print(f"   ramp {k + 1}: board {d['board_t']:6.3f}s @{d['board_speed']:5.0f}  leave {d['leave_t']:6.3f}s"
                  f" @{d['leave_speed']:5.0f} z {d['leave_z']:8.1f} vz {d['leave_vz']:+5.0f}  low z {d['low_z']:8.1f}"
                  f"  top {d['top_speed']:5.0f}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("ref")
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    names, res = compare(load(a.ref), [load(p) for p in a.runs])
    report(names, res)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"splits": names, "runs": res}, f, indent=1)


if __name__ == "__main__":
    main()
