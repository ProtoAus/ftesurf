#!/usr/bin/env python3
"""test_qcframes.py -- the frame-overlap guard (Patch 1617) on synthetic progs.  python3 tools/test_qcframes.py

The compiler shape that put a global inside a frame did not reproduce in a small program (P1617's notes), so these
build the .dat bytes directly: a version 7 32-bit progs whose functions table says what each case needs.
"""
import os
import struct
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qcframes as Q  # noqa: E402

PASS = FAIL = 0


def check(what, ok):
    global PASS, FAIL
    if ok:
        PASS += 1
    else:
        FAIL += 1
        print("FAIL", what)


def progs(defs, funcs, wide=True, version=7, compressed=0):
    """defs = [(type, ofs, name)], funcs = [(name, first_statement, parm_start, locals)]."""
    strings = b"\0"
    index = {}

    def sid(s):
        nonlocal strings
        if s not in index:
            index[s] = len(strings)
            strings += s.encode() + b"\0"
        return index[s]

    size = 12 if wide else 8
    gd = b"".join(struct.pack("<IIi" if wide else "<HHi", t, o, sid(n)) for t, o, n in defs)
    fn = b"".join(struct.pack("<7i8B", first, ps, lc, 0, sid(n), 0, 0, *([0] * 8)) for n, first, ps, lc in funcs)
    hsize = 23 * 4
    ofs_gd = hsize
    ofs_fn = ofs_gd + len(gd)
    ofs_str = ofs_fn + len(fn)
    sec = Q.PROG_SECONDARYVERSION32 if wide else 0x12345678
    head = struct.pack("<15i", version, 0, 0, 0, ofs_gd, len(defs), 0, 0, ofs_fn, len(funcs), ofs_str, len(strings), 0, 0, 0)
    ext = struct.pack("<7I", 0, 0, 0, 0, 0, 0, compressed) + struct.pack("<I", sec & 0xffffffff)
    assert len(defs) * size == len(gd)
    return head + ext + gd + fn + strings


F, FN = 2, Q.TYPE_FUNCTION
SRC = {"flag_a", "flag_b", "shared_i"}
# The P1617 shape: three builtins at 839-841, the flag at 842, the function whose frame is 839..842.
BAD_DEFS = [(FN, 839, "B_One"), (FN, 840, "B_Two"), (FN, 841, "B_Three"), (F, 842, "flag_a"), (F, 843, "flag_b"),
            (FN, 844, "Probe")]
BAD_FUNCS = [("", 0, 0, 0), ("B_One", -1, 0, 0), ("Probe", 10, 839, 4)]


def case_detects():
    d, f = Q.read_progs(progs(BAD_DEFS, BAD_FUNCS))
    hits, amb = Q.inside_frames(d, f, SRC)
    check("the P1617 shape is caught", hits == [("Probe", 842, "flag_a")])
    check("a global just past the frame is not", all(h[2] != "flag_b" for h in hits))
    check("builtins in the frame are not globals", all(h[2].startswith("flag") for h in hits))
    check("nothing ambiguous", amb == [])


def case_clean():
    d, f = Q.read_progs(progs(BAD_DEFS, [("", 0, 0, 0), ("Probe", 10, 839, 3)]))
    check("frame over builtins only: clean", Q.inside_frames(d, f, SRC) == ([], []))
    d, f = Q.read_progs(progs(BAD_DEFS + [(F, 900, "tmp")], [("Probe", 10, 900, 1)]))
    check("a frame over its own local: clean", Q.inside_frames(d, f, SRC) == ([], []))


def case_builtin_and_empty():
    d, f = Q.read_progs(progs(BAD_DEFS, [("B_One", -5, 839, 4), ("Empty", 0, 839, 4)]))
    check("a builtin's or an empty function's range is no frame", Q.inside_frames(d, f, SRC) == ([], []))


def case_ambiguous():
    defs = BAD_DEFS + [(F, 950, "shared_i"), (F, 841, "shared_i")]
    d, f = Q.read_progs(progs(defs, BAD_FUNCS))
    hits, amb = Q.inside_frames(d, f, SRC)
    check("a name that is global and local is noted, not failed", ("Probe", 841, "shared_i") in amb)
    check("the unique global still fails", ("Probe", 842, "flag_a") in hits)


def case_formats():
    d, f = Q.read_progs(progs(BAD_DEFS, BAD_FUNCS, wide=False, version=6))
    check("version 6, 16-bit defs", Q.inside_frames(d, f, SRC)[0] == [("Probe", 842, "flag_a")])
    d, f = Q.read_progs(progs(BAD_DEFS, BAD_FUNCS, wide=False, version=7))
    check("version 7, 16-bit defs", Q.inside_frames(d, f, SRC)[0] == [("Probe", 842, "flag_a")])
    for what, blob in (("compressed", progs(BAD_DEFS, BAD_FUNCS, compressed=2)), ("truncated", progs(BAD_DEFS, BAD_FUNCS)[:200]),
                       ("version 5", progs(BAD_DEFS, BAD_FUNCS, version=5)), ("short", b"\0" * 10)):
        try:
            Q.read_progs(blob)
            check("%s refuses" % what, False)
        except Q.ProgsError:
            check("%s refuses" % what, True)


def case_source_and_exit():
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "src", "shared"))
        with open(os.path.join(td, "src", "shared", "a.qc"), "w") as fh:
            fh.write("float flag_a, flag_b;\nnoref string shared_i;\nfloat() Probe =\n{\n\tlocal float tmp;\n\treturn 0;\n};\n"
                     "float arr[4];\nvector  spaced;\n__int64 wide_one;\n")
        g = Q.source_globals(os.path.join(td, "src"))
        check("source globals", {"flag_a", "flag_b", "shared_i", "arr", "spaced", "wide_one"} <= g)
        check("a local is not a global", "tmp" not in g and "Probe" not in g)
        bad = os.path.join(td, "bad.dat")
        good = os.path.join(td, "good.dat")
        with open(bad, "wb") as fh:
            fh.write(progs(BAD_DEFS, BAD_FUNCS))
        with open(good, "wb") as fh:
            fh.write(progs(BAD_DEFS, [("Probe", 10, 839, 3)]))
        src = os.path.join(td, "src")
        check("exit 1 on the P1617 shape", Q.main([bad, "--src", src]) == 1)
        check("exit 0 when clean", Q.main([good, "--src", src]) == 0)
        check("exit 2 on a missing file", Q.main([os.path.join(td, "none.dat"), "--src", src]) == 2)


for case in (case_detects, case_clean, case_builtin_and_empty, case_ambiguous, case_formats, case_source_and_exit):
    case()
print("test_qcframes: %d/%d" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
