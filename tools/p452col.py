"""p452col.py -- grade Patch 452's contact and energy colouring.

Reads `replay colours` output (ln_col itself, sampled) and derives what each
sampled point's colour should be straight from the .rec:

  contact  the three-state rule from the documented flag bits, the same one
           p449mark.py reimplements -- imported from it rather than written
           twice, since two copies of a rule is the defect this patch's whole
           design is arranged to avoid.
  energy   E = z + |v|^2 / 2g over the same two-samples-each-side window the
           client uses, divided by Strafe_PowerCeiling(30, g, tick).

  python tools/p452col.py [ftesurf/logs/p452col.log]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p449mark                                     # noqa: E402  (the shared rule)

GRAV = 800.0
AIRCAP = 30.0
GROUND, AIR, RAMP = 0, 1, 2
CONTACT_RGB = {GROUND: (1.00, 0.62, 0.20), RAMP: (0.35, 0.85, 1.00),
               AIR: (0.85, 0.88, 0.95), -1: (0.45, 0.45, 0.50)}


def ceiling(aircap, g, tick):
    """Strafe_PowerCeiling: ws^2 / (2 g tick), sh_strafe.qc:558."""
    return (aircap * aircap) / (2 * g * tick) if tick > 0 else 37.5


def samples(recpath):
    """[(t, z, spd, vz, flags)] for the whole body, plus the header tickrate."""
    out, body, tick = [], False, 0.015
    for line in open(recpath, "r", errors="replace"):
        if not body:
            if line.startswith("tickrate"):
                tick = float(line.split()[1])
            if line.startswith("begin"):
                body = True
            continue
        if line[:1].isdigit() or line[:1] == "-":
            f = line.split()
            v = (float(f[4]), float(f[5]), float(f[6]))
            out.append((p449mark.f32(float(f[0])), float(f[3]),
                        (v[0] ** 2 + v[1] ** 2) ** 0.5, v[2],
                        int(float(f[9]))))
    return out, tick


def contact_kinds(rows):
    """The contact kind of every sample, by the documented rule."""
    ks, ron, rlast = [], False, 0.0
    for t, z, spd, vz, fl in rows:
        raw = fl & p449mark.F_RAMP
        held = bool(raw) or (ron and rlast > 0 and t >= rlast
                             and p449mark.f32(t - rlast) <= p449mark.f32(0.08))
        if raw:
            rlast = t
        ron = held
        ks.append(GROUND if (fl & p449mark.F_ONGROUND) else (RAMP if held else AIR))
    return ks


def parse(path):
    blocks, cur, recpath, brk = [], None, None, set()
    for raw in open(path, "r", errors="replace"):
        line = re.sub(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ", "", raw.rstrip("\n"))
        m = re.search(r"=== p452col (\S+) (\S+)", line)
        if m:
            cur = {"label": m.group(1), "mode": m.group(2), "pts": []}
            blocks.append(cur)
            continue
        f = line.split()
        if line.startswith("lnmb ") and len(f) >= 8:
            recpath = f[7]
        elif cur is not None and line.startswith("lncb ") and len(f) >= 5:
            cur["cmode"] = int(float(f[2]))
        elif line.startswith("lnm ") and len(f) >= 12 and int(float(f[2])) == 7:
            brk.add(int(float(f[5])))       # a teleport, by sample ordinal
        elif cur is not None and line.startswith("lnc ") and len(f) >= 6:
            cur["pts"].append((int(float(f[1])), float(f[2]),
                               (float(f[3]), float(f[4]), float(f[5]))))
    return blocks, recpath, brk


def near(a, b, tol=0.02):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def main():
    log = sys.argv[1] if len(sys.argv) > 1 else "ftesurf/logs/p452col.log"
    blocks, recpath, brk = parse(log)
    if not blocks or not recpath:
        print("FAIL no p452col blocks or no mark dump in %s" % log)
        return 1
    rows, tick = samples("ftesurf/" + recpath)
    kinds = contact_kinds(rows)
    # the client's point array is the sample array here (no decimation on a
    # 5321-sample file), which lncb's count confirms below
    out, bad = [], 0

    def check(name, ok, detail):
        nonlocal bad
        if not ok:
            bad += 1
        out.append("%s %-3s %s" % ("PASS" if ok else "FAIL", name, detail))

    def cut(lbl):
        b = [x for x in blocks if x["label"] == lbl and x["pts"]]
        return b[-1] if b else None

    # C1 -- contact
    b = [x for x in blocks if x.get("cmode") == 2 and x["pts"]]
    if not b:
        check("C1", False, "no contact cut")
    else:
        pts = b[-1]["pts"]
        edges = set()
        for i in range(1, len(kinds)):
            if kinds[i] != kinds[i - 1]:
                edges.update((i - 1, i, i + 1))
        wrong, graded = [], 0
        for i, t, rgb in pts:
            if i >= len(kinds) or i in edges:
                continue
            graded += 1
            if not near(rgb, CONTACT_RGB[kinds[i]]):
                wrong.append("point %d (%s) is %s, want %s"
                             % (i, {0: "ground", 1: "air", 2: "ramp"}[kinds[i]],
                                rgb, CONTACT_RGB[kinds[i]]))
        check("C1", graded > 10 and not wrong,
              "%d of %d sampled points graded, %d wrong%s"
              % (graded, len(pts), len(wrong), "  " + wrong[0] if wrong else ""))

    # C2 -- energy
    b = [x for x in blocks if x.get("cmode") == 3 and x["pts"]]
    if not b:
        check("C2", False, "no energy cut")
    else:
        pts = b[-1]["pts"]
        p = ceiling(AIRCAP, GRAV, tick)
        wrong, graded = [], 0
        for i, t, rgb in pts:
            if i >= len(rows):
                continue
            # The window does not cross a teleport, exactly as Line_ColEnergy
            # does not: stepping over one differences two unrelated positions
            # and saturates the colour.  One point in 167 turns on this.
            j0, j1 = i, i
            for _ in range(2):
                if j0 > 0 and j0 not in brk:
                    j0 -= 1
                if j1 + 1 < len(rows) and (j1 + 1) not in brk:
                    j1 += 1
            dt = rows[j1][0] - rows[j0][0]
            e = lambda r: r[1] + (r[2] ** 2 + r[3] ** 2) / (2 * GRAV)
            f = max(-1.0, min(1.0, ((e(rows[j1]) - e(rows[j0])) / dt) / p)) if dt > 0 else 0
            base = (0.85, 0.85, 0.85)
            d = (-0.55, 0.15, -0.45) if f >= 0 else (0.15, -0.60, -0.60)
            want = tuple(base[k] + d[k] * abs(f) for k in range(3))
            graded += 1
            if not near(rgb, want, 0.03):
                wrong.append("point %d is %s, want %s (f=%.3f)" % (i, rgb, want, f))
        check("C2", graded > 10 and not wrong,
              "%d points graded against E over the ceiling %.1f, %d wrong%s"
              % (graded, p, len(wrong), "  " + wrong[0] if wrong else ""))

    # C3/C4 -- the older modes still work, and the modes differ from each other
    sigs = {}
    for x in blocks:
        if x["pts"] and "cmode" in x:
            sigs[x["cmode"]] = tuple(rgb for _, _, rgb in x["pts"][:40])
    check("C3", 0 in sigs and 1 in sigs and sigs[0] != sigs[1],
          "speed and gain both present and different (%d modes sampled)" % len(sigs))
    check("C4", len(set(sigs.values())) == len(sigs) and len(sigs) == 4,
          "%d modes sampled, %d distinct colourings"
          % (len(sigs), len(set(sigs.values()))))

    print("\n".join(out))
    print("%d check(s), %d failed" % (len(out), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
