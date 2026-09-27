"""p451num.py -- grade Patch 451's numbers on the run line's marks.

The subject prints the string it handed to HUD_Text as the last field of each
lndm line.  This rebuilds that string from the MARK TABLE the same frame was
drawn from (`replay marks`, itself graded against the .rec by p449mark.py) and
compares it character for character.

Grading the DRAWN text matters: a label assembled from the wrong mark, or from
a stale unit, still prints plausible numbers.  N4 caught exactly that -- the
energy column would not change unit, because seq_units is cached by a function
that does not run while a replay is up.

  python tools/p451num.py [ftesurf/logs/p451num.log]
"""
import math
import re
import sys

E_LAND, E_LEAVE, E_JUMP, E_APEX, E_TROUGH, E_STITCH, E_BREAK = 1, 2, 3, 4, 5, 6, 7
GRAV = 800.0


def equiv(e, g):
    """Strafe_EquivSpeed: sign-carrying, sh_strafe.qc:52."""
    return -math.sqrt(-2 * g * e) if e < 0 else math.sqrt(2 * g * e)


def first_sample(recpath):
    """The run's own first sample, straight from the file: (z, |v|^2).

    Derived here rather than read from the client's lnmz line, so a reference
    taken from the wrong sample is catchable.  lnmz is compared against it.
    """
    body = False
    for line in open(recpath, "r", errors="replace"):
        if not body:
            if line.startswith("begin"):
                body = True
            continue
        if line[:1].isdigit() or line[:1] == "-":
            f = line.split()
            v = [float(f[4]), float(f[5]), float(f[6])]
            return float(f[3]), v[0] ** 2 + v[1] ** 2 + v[2] ** 2
    return None, None


def parse(path):
    blocks, cur, marks = [], None, []
    said = {}
    recpath = None
    for raw in open(path, "r", errors="replace"):
        line = re.sub(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ", "", raw.rstrip("\n"))
        m = re.search(r"=== p451num (\S+)", line)
        if m:
            cur = {"label": m.group(1), "marks": [], "frame": 0, "slots": {}}
            blocks.append(cur)
            continue
        f = line.split()
        if line.startswith("lnmb ") and len(f) >= 8:
            recpath = f[7]
        elif line.startswith("lnmz ") and len(f) >= 4:
            said[int(float(f[1]))] = (float(f[2]), float(f[3]))
        elif line.startswith("lnm ") and len(f) >= 12:
            # the mark table, dumped after the cuts: index by sample ordinal
            marks.append({"kind": int(float(f[2])), "t": float(f[4]),
                          "ord": int(float(f[5])),
                          "z": float(f[8]), "spd": float(f[9]),
                          "v2": float(f[10]), "vz": float(f[11])})
        if cur is None:
            continue
        if line.startswith("lnde"):
            cur["frame"] += 1
        elif line.startswith("lnd3 ") and len(f) >= 3:
            cur["slots"].setdefault(int(float(f[1])), {})["nlab"] = int(float(f[2]))
        elif line.startswith("lnd2 ") and len(f) >= 7:
            cur["slots"].setdefault(int(float(f[1])), {})["nmk"] = int(float(f[6]))
        elif line.startswith("lndm ") and len(f) >= 7:
            mm = re.search(r'"(.*)"\s*$', line)
            cur["marks"].append({"slot": int(float(f[1])), "kind": int(float(f[2])),
                                 "t": float(f[3]), "x": float(f[4]),
                                 "y": float(f[5]), "frame": cur["frame"],
                                 "lab": mm.group(1) if mm else None})
    return blocks, marks, said, recpath


def main():
    log = sys.argv[1] if len(sys.argv) > 1 else "ftesurf/logs/p451num.log"
    blocks, marks, said, recpath = parse(log)
    if not blocks or not marks:
        print("FAIL no p451num blocks or no mark table in %s" % log)
        return 1

    # hud_lines_ref 1's zero: the run's own first sample, from the FILE
    z0, v20 = first_sample("ftesurf/" + recpath)
    e0 = z0 + v20 / (2 * GRAV)
    by_t = {round(m["t"], 4): m for m in marks}
    out, bad = [], 0
    sz, sv = said.get(0, (None, None))

    def check(name, ok, detail):
        nonlocal bad
        if not ok:
            bad += 1
        out.append("%s %-3s %s" % ("PASS" if ok else "FAIL", name, detail))

    def cut(label):
        b = [x for x in blocks if x["label"] == label]
        return b[0] if b else None

    def labelled(b):
        return [m for m in b["marks"] if m["frame"] == 0 and m["slot"] == 0
                and m["lab"]]

    # N0 -- the zero the client says it used is the file's own first sample
    ok0 = (sz is not None and abs(sz - z0) < 0.01 and abs(sv - v20) < 1.0)
    out.append("%s N0  energy zero: client z %s v2 %s, file z %.2f v2 %.1f"
               % ("PASS" if ok0 else "FAIL",
                  "%.2f" % sz if sz is not None else "-",
                  "%.1f" % sv if sv is not None else "-", z0, v20))
    if not ok0:
        bad += 1

    # N1 -- numbers off, marks still drawn
    b = cut("N1")
    if not b:
        check("N1", False, "cut missing")
    else:
        mk = [m for m in b["marks"] if m["frame"] == 0 and m["slot"] == 0]
        check("N1", mk and not labelled(b),
              "%d marks drawn, %d labelled" % (len(mk), len(labelled(b))))

    # N2 -- the speed is the mark's own
    b = cut("N2")
    if not b:
        check("N2", False, "cut missing")
    else:
        wrong = []
        for m in labelled(b):
            src = by_t.get(round(m["t"], 4))
            if not src or abs(float(m["lab"]) - src["spd"]) > 0.51:
                wrong.append("%s at %.4f (file %s)"
                             % (m["lab"], m["t"],
                                "%.0f" % src["spd"] if src else "no mark"))
        check("N2", labelled(b) and not wrong,
              "%d labels, %d wrong%s" % (len(labelled(b)), len(wrong),
                                         "  " + wrong[0] if wrong else ""))

    # N3/N4 -- speed and energy, in the unit in force
    for name, units in (("N3", 1), ("N4", 0)):
        b = cut(name)
        if not b:
            check(name, False, "cut missing")
            continue
        wrong = []
        for m in labelled(b):
            src = by_t.get(round(m["t"], 4))
            if not src:
                wrong.append("no mark at %.4f" % m["t"])
                continue
            e = src["z"] + src["v2"] / (2 * GRAV) - e0
            # Compared as numbers with half a unit of slack, not as strings:
            # both sides round a float to 0 dp and C and Python disagree on
            # the exact half (973.4996 printed "973.50" in the first dump).
            got = re.findall(r"-?\d+(?:\.\d+)?", m["lab"])
            wante = e if units else equiv(e, GRAV)
            if (len(got) != 2 or abs(float(got[0]) - src["spd"]) > 0.51
                    or abs(float(got[1]) - wante) > 0.51
                    or ("u/s" in m["lab"]) != (units == 0)):
                wrong.append("%r want %.0f %.0f%s at %.4f"
                             % (m["lab"], src["spd"], wante,
                                "u/s" if units == 0 else "e", m["t"]))
        check(name, labelled(b) and not wrong,
              "units %d: %d labels, %d wrong%s"
              % (units, len(labelled(b)), len(wrong),
                 "  " + wrong[0] if wrong else ""))

    # N4 must actually differ from N3, or the unit switch did nothing
    b3, b4 = cut("N3"), cut("N4")
    if b3 and b4:
        l3 = [m["lab"] for m in labelled(b3)]
        l4 = [m["lab"] for m in labelled(b4)]
        check("N4b", l3 and l4 and l3 != l4,
              "the unit switch changed the text (%s -> %s)"
              % (l3[0] if l3 else "-", l4[0] if l4 else "-"))

    # N5 -- peaks carry numbers once nums 2 is on
    b = cut("N5")
    if not b:
        check("N5", False, "cut missing")
    else:
        pk = [m for m in labelled(b) if m["kind"] in (E_APEX, E_TROUGH)]
        n3 = cut("N3")
        was = [m for m in labelled(n3) if m["kind"] in (E_APEX, E_TROUGH)] if n3 else []
        check("N5", pk and not was,
              "%d peak labels at nums 2, %d at nums 1" % (len(pk), len(was)))

    # N6 -- labels declutter separately from glyphs
    b = cut("N6")
    if not b or 0 not in b["slots"]:
        check("N6", False, "cut missing")
    else:
        sl = b["slots"][0]
        gap = 24.0
        cells, dup = {}, 0
        for m in labelled(b):
            k = (int(m["x"] // gap), int(m["y"] // gap))
            if k in cells:
                dup += 1
            cells[k] = 1
        check("N6", sl.get("nlab", 0) < sl.get("nmk", 0) and dup == 0,
              "every field at size 24: %d marks, %d labels, %d sharing a cell"
              % (sl.get("nmk", -1), sl.get("nlab", -1), dup))

    # N7 -- the labels' grid is their own
    b = cut("N7")
    if not b or 0 not in b["slots"]:
        check("N7", False, "cut missing")
    else:
        sl = b["slots"][0]
        check("N7", sl.get("nmk", 0) > 0 and sl.get("nlab", -1) == sl.get("nmk"),
              "gap 240: %d marks, %d labels -- a label must not lose its cell "
              "to its own glyph" % (sl.get("nmk", -1), sl.get("nlab", -1)))

    print("\n".join(out))
    print("%d check(s), %d failed" % (len(out), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
