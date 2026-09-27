"""p449win.py -- grade Patch 449's run-time window and its marks' draw pass.

Reads ftesurf/logs/p449win.log: the lnd / lnd2 / lndm / lnde lines `replay
marktrace` prints from inside the pass, never a re-derivation of them.

  lnd   <slot> <tplay> <winon> <wa> <wb>
  lnd2  <slot> <ia> <ib> <points> <segments> <marks>
  lndm  <slot> <kind> <t> <x> <y> <alpha>        one per glyph DRAWN

  python tools/p449win.py [ftesurf/logs/p449win.log]
"""
import math
import os
import re
import sys

GUARD = 8192                         # cl_lines.qc LN_GUARD


def parse(path):
    """{label: {slot: {...}}} plus each block's glyphs, in the order they ran."""
    blocks, cur = [], None
    for raw in open(path, "r", errors="replace"):
        line = re.sub(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ", "", raw.rstrip("\n"))
        m = re.search(r"=== p449win (\S+)(.*?)===", line)
        if m:
            cur = {"label": m.group(1), "title": (m.group(1) + m.group(2)).strip(),
                   "slots": {}, "marks": [], "frame": 0}
            blocks.append(cur)
            continue
        if cur is None:
            continue
        f = line.split()
        if line.startswith("lnde"):
            cur["frame"] += 1           # marktrace traces n frames; grade one
        elif line.startswith("lnd ") and len(f) >= 6:
            cur["slots"].setdefault(int(float(f[1])), {}).update(
                tplay=float(f[2]), winon=int(float(f[3])),
                wa=float(f[4]), wb=float(f[5]))
        elif line.startswith("lnd2 ") and len(f) >= 7:
            cur["slots"].setdefault(int(float(f[1])), {}).update(
                ia=int(float(f[2])), ib=int(float(f[3])), npt=int(float(f[4])),
                nseg=int(float(f[5])), nmk=int(float(f[6])))
        elif line.startswith("lndm ") and len(f) >= 7:
            # The coordinates are graded, so a NaN must survive parsing as one
            # rather than crash the reader: that is the W3 failure mode.
            def num(x):
                try:
                    return float(x)
                except ValueError:
                    return float("nan")
            cur["marks"].append({"slot": int(float(f[1])), "kind": int(float(f[2])),
                                 "t": num(f[3]), "x": num(f[4]), "y": num(f[5]),
                                 "frame": cur["frame"], "raw": line})
    return blocks


def by_label(blocks, want):
    return [b for b in blocks if b["label"] == want]


def main():
    log = sys.argv[1] if len(sys.argv) > 1 else "ftesurf/logs/p449win.log"
    blocks = parse(log)
    if not blocks:
        print("FAIL no p449win blocks in %s -- the arm measured nothing" % log)
        return 1

    out, bad = [], 0

    def check(name, ok, detail):
        nonlocal bad
        if not ok:
            bad += 1
        out.append("%s %-4s %s" % ("PASS" if ok else "FAIL", name, detail))

    w1 = by_label(blocks, "W1")
    w2 = by_label(blocks, "W2")
    w4 = by_label(blocks, "W4")
    w6 = by_label(blocks, "W6")
    w5 = by_label(blocks, "W5")

    # W1 -- the window off, and marks actually drawn (or nothing below measures)
    if not w1 or 0 not in w1[0]["slots"]:
        check("W1", False, "no slot 0 trace")
        s1 = None
    else:
        s1 = w1[0]["slots"][0]
        check("W1", s1["winon"] == 0 and s1["nmk"] > 0,
              "winon %d, ia..ib %d..%d, %d points, %d marks drawn"
              % (s1["winon"], s1["ia"], s1["ib"], s1["npt"], s1["nmk"]))

    # W2 -- the window narrows the range and every mark is inside it
    if not w2 or 0 not in w2[0]["slots"]:
        check("W2", False, "no slot 0 trace")
    else:
        s2 = w2[0]["slots"][0]
        mk = [m for m in w2[0]["marks"] if m["slot"] == 0 and m["frame"] == 0]
        outside = [m for m in mk if not (s2["wa"] - 1e-3 <= m["t"] <= s2["wb"] + 1e-3)]
        # BOTH edges, separately.  "Narrower than the whole line" passes with the
        # back edge not enforced at all -- the stretch it would have added is
        # behind the camera at this frame and draws nothing, so the marks tell
        # you nothing about it.  ia must have MOVED.
        back = s1 is None or s2["ia"] > s1["ia"]
        fwd = s1 is None or s2["ib"] < s1["ib"]
        check("W2", s2["winon"] == 1 and not outside and back and fwd and mk,
              "window %.1f..%.1f at tplay %.1f: %d..%d against the whole line's "
              "%d..%d (back edge moved %s, front %s), %d marks, %d outside"
              % (s2["wa"], s2["wb"], s2["tplay"], s2["ia"], s2["ib"],
                 s1["ia"] if s1 else -1, s1["ib"] if s1 else -1,
                 "yes" if back else "NO", "yes" if fwd else "NO",
                 len(mk), len(outside)))

    # W3 -- every drawn coordinate finite and inside the guard
    allm = [m for b in blocks for m in b["marks"]]
    wild = [m for m in allm
            if not (math.isfinite(m["x"]) and math.isfinite(m["y"]))
            or abs(m["x"]) > GUARD or abs(m["y"]) > GUARD]
    check("W3", allm and not wild,
          "%d glyphs traced, %d non-finite or past the guard" % (len(allm), len(wild)))

    # W4 -- the declutter: fewer marks at a coarse gap, one per cell
    if not w4 or 0 not in w4[0]["slots"] or s1 is None:
        check("W4", False, "no slot 0 trace")
    else:
        s4 = w4[0]["slots"][0]
        gap = 240.0
        cells = {}
        dup = 0
        for m in w4[0]["marks"]:
            if m["slot"] != 0 or m["frame"] != 0:
                continue
            k = (m["slot"], int(m["x"] // gap), int(m["y"] // gap))
            if k in cells:
                dup += 1
            cells[k] = 1
        check("W4", s4["nmk"] < s1["nmk"] and dup == 0,
              "gap 240 drew %d marks against gap 24's %d, %d sharing a cell"
              % (s4["nmk"], s1["nmk"], dup))

    # W5 -- a board line has no playhead, so the window never touches it
    if len(w5) < 2:
        check("W5", False, "need the window-on and window-off cuts, got %d" % len(w5))
    else:
        on = w5[0]["slots"].get(4)
        off = w5[1]["slots"].get(4)
        r0on = w5[0]["slots"].get(0)
        if not on or not off:
            check("W5", False, "slot 4 never drew -- the board line did not build")
        else:
            same = (on["ia"], on["ib"], on["nmk"]) == (off["ia"], off["ib"], off["nmk"])
            check("W5", on["winon"] == 0 and off["winon"] == 0 and same,
                  "slot 4 winon %d/%d, %d..%d vs %d..%d, %d/%d marks "
                  "(slot 0 narrowed to %d..%d in the same frame)"
                  % (on["winon"], off["winon"], on["ia"], on["ib"],
                     off["ia"], off["ib"], on["nmk"], off["nmk"],
                     r0on["ia"] if r0on else -1, r0on["ib"] if r0on else -1))

    # W6 -- nothing past the playhead with ahead 0
    if not w6 or 0 not in w6[0]["slots"]:
        check("W6", False, "no slot 0 trace")
    else:
        s6 = w6[0]["slots"][0]
        mk = [m for m in w6[0]["marks"] if m["slot"] == 0 and m["frame"] == 0]
        past = [m for m in mk if m["t"] > s6["tplay"] + 1e-3]
        check("W6", mk and not past,
              "ahead 0 at %.1f: %d marks drawn, %d past the playhead "
              "(%d points -- 0 would mean the cut measured nothing)"
              % (s6["tplay"], len(mk), len(past), s6["npt"]))

    print("\n".join(out))
    print("%d check(s), %d failed" % (len(out), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
