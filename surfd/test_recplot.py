"""
test_recplot.py -- the falsifier for recplot.parse (Patch 359).

    python3 test_recplot.py

Stdlib only; runs on Windows and the Pi.  Synthetic files follow the grammar
block over SV_RecOpen (sv_timer.qc); the last case smoke-parses every .rec under
ftesurf/data/runs (or $RECPLOT_CORPUS) when that tree is present.
"""

import collections
import json
import os
import random
import shutil
import sys
import tempfile
import time

import recplot

FAILED = []
TMP = tempfile.mkdtemp(prefix="recplot-")


def check(label, got, want):
    ok = got == want
    shown = ascii(got)      # ascii: a cp1252 console cannot print U+FFFD
    print("%-4s %-60s %s" % ("ok" if ok else "FAIL", label, shown if len(shown) < 120 else shown[:117] + "..."))
    if not ok:
        FAILED.append("%s: got %r, want %r" % (label, got, want))


def write(name, data):
    path = os.path.join(TMP, name)
    with open(path, "wb") as fh:
        fh.write(data if isinstance(data, bytes) else data.encode("utf-8"))
    return path


def S(t, x=0.0, y=0.0, z=0.0, vx=0.0, vy=0.0, vz=0.0, cols=17):
    # t ox oy oz vx vy vz pit yaw fl keys fwd side up [nx ny nz v4]
    row = "%.4f %.2f %.2f %.2f %.2f %.2f %.2f 0.0 90.0 1 0 0 0 0" % (t, x, y, z, vx, vy, vz)
    if cols >= 17:
        row += " 0.0000 0.0000 1.0000"
    return row


HEAD = ["map surf_test", "track 0", "startseg 0", "leg 0", "tickrate 0.015",
        "owner Some One", "runid 20260918-000000-0", "flags 0"]


def rec(name, ver, body, head=HEAD, begin=True):
    return write(name, "\n".join(["FTESURF-REC %d" % ver] + list(head)
                                 + (["begin"] if begin else []) + list(body)) + "\n")


def first(r, k):
    return next((m for m in r["marks"] if m["k"] == k), dict.fromkeys(("k", "n", "t", "x", "y", "kind")))


def notes_with(r, prefix):
    return [n for n in r["notes"] if n.startswith(prefix)]


def case_v3_v4():
    body = [S(0.0, 0, 0, 0, 300, 400, 0, cols=14), "cp 1 10", S(0.015, 4.5, 6, 0, 300, 400, 0, cols=14),
            "end 1 2 0 1"]
    r = recplot.parse(rec("v3.rec", 3, body))
    check("v3: ok, 14-column samples", (r["ok"], r["v"], r["n"]), (True, 3, 2))
    check("v3: speed is hypot(vx, vy)", r["spd"], [500.0, 500.0])
    check("v3: cp mark at ticks*rate, at the last sample", r["marks"],
          [{"k": "cp", "n": 1, "t": 0.15, "x": 0.0, "y": 0.0}])
    check("v3: 4-field trailer kept as ints", r["end"], [1, 2, 0, 1])
    check("v3: no notes", r["notes"], [])
    body = [S(0.0, 1, 2, 3, 3, 4, 0), "board 0.0100 1 0.0 0.7 0.7 1.0 2.0 3.0", S(0.015, 2, 3, 4, 3, 4, 0),
            "end 1 2 0 0"]
    r = recplot.parse(rec("v4.rec", 4, body))
    check("v4: 17-column samples, board counted", (r["n"], r["x"], r["z"], r["counts"]["board"]),
          (2, [1.0, 2.0], [3.0, 4.0], 1))
    check("v4: header allowlist", sorted(r["head"]),
          ["flags", "leg", "map", "owner", "runid", "startseg", "tickrate", "track"])
    check("v4: owner keeps its spaces", r["head"]["owner"], "Some One")


def case_v5_stage():
    head = HEAD + ["clock counted", "lobby FTESurf", "samples 0"]
    body = [S(-0.03), S(-0.015), "stagestart 1 0", S(0.0, 10, 0), S(0.015, 20, 0), "restart 1 1",
            S(0.03, 30, 0), "stage 2 2", S(0.045, 40, 0), "end 3 6 2 0", "split 1 2", "split 2 3"]
    r = recplot.parse(rec("v5.rec", 5, body, head=head))
    check("v5: unknown header keys are not kept", ("lobby" in r["head"], r["head"]["clock"]), (False, "counted"))
    check("v5: splits as [seg, ticks]", r["splits"], [[1, 2], [2, 3]])
    kinds = [(m["k"], m["n"], m["t"], m["x"]) for m in r["marks"]]
    check("v5: tick marks, then splits by nearest sample", kinds,
          [("stagestart", 1, 0.0, 0.0), ("restart", 1, 0.015, 20.0), ("stage", 2, 0.03, 30.0),
           ("split", 1, 0.03, 30.0), ("split", 2, 0.045, 40.0)])
    check("v5: 4-field trailer, no notes", (r["end"], r["notes"]), ([3, 6, 2, 0], []))


V7_HEAD = HEAD + ["movetickrate 0.015", "clock counted", "instart 1000 1000"]


def case_v7_warp():
    body = ["in 1 1000 0 0 0 0 0 0 0 0", S(0.0, 0, 0), "in 2 1001 0 0 0 0 0 0 0 0",
            "warp 2 1002 tele 512.00 -128.00 64.00 10.00 0.00 0.00", S(0.015, 512, -128, 64, 10),
            "warp 2 1002 zap 1 2 3 4 5 6", "end 2 2 0 0 2 2"]
    r = recplot.parse(rec("v7.rec", 7, body, head=V7_HEAD))
    w = first(r, "warp")
    check("v7: kind after pk mt; unknown kind kept", r["counts"]["warp"], {"tele": 1, "zap": 1})
    check("v7: warp t = (mt - start) * rate, xy from the record", (w["t"], w["x"], w["y"]),
          (0.03, 512.0, -128.0))
    check("v7: counts in", r["counts"]["in"], 2)
    check("v7: 6-field trailer agrees: no notes", r["notes"], [])


def case_v9():
    head = HEAD[:4] + ["tickrate 0.01", "movetickrate 0.01", "clock counted", "owner Kap",
                       "instart 500 500", "flags 1285      ",
                       "pmpin pmsrcver=1 trisoup=1 rotboxes=1 portalcsg=1 gravity=800"]
    body = ["seed 0 0 0 0 0 0 1 duck=0", "zseed evzone=0 azone=0 track=0 startseg=0 stagerun=0 twarp=1",
            "ride 0 500 arm 0 0 0", S(-0.01), "in 1 500 0 0 0 0 0 0 0 0 1", "pe 1 0 123",
            "in 1 501 0 0 0 0 0 0 0 0 1", "portal 1 1 1 100 200 300 1 2 3", "portal 1 0 2 7 8 9 0 0 0",
            "warp 1 502 1 lift 5 6 7 8 9 10 1", "pm 1 1 gravity=400", S(0.01, 100, 200, 300, 1, 2),
            "inend 502 0", "end 2 2 1 0 2 1 1 1 1 2"]
    r = recplot.parse(rec("v9.rec", 9, body, head=head))
    check("v9: ok", (r["ok"], r["v"], r["n"], r["rate"]), (True, 9, 2, 0.01))
    check("v9: pmpin kept; flags stripped", (r["head"]["pmpin"][:9], r["head"]["flags"]), ("pmsrcver=", "1285"))
    c = r["counts"]
    check("v9: counted records", (c["in"], c["pe"], c["pm"], c["seed"], c["zseed"], c["ride"], c["inend"],
                                  c["portal"], c["unknown"]), (2, 1, 1, 1, 1, 1, 1, 2, 0))
    check("v9: warp kind after the row field", c["warp"], {"lift": 1})
    w = first(r, "warp")
    check("v9: warp mark", (w["t"], w["x"], w["y"], w["kind"]), (0.02, 5.0, 6.0, "lift"))
    p = first(r, "portal")
    check("v9: portal mark, t from its `in` row", p, {"k": "portal", "n": 1, "t": 0.01, "x": 100.0, "y": 200.0})
    p = [m for m in r["marks"] if m["k"] == "portal"][1:] or [{}]
    check("v9: a portal not on the last `in` row: map only", p[0], {"k": "portal", "n": 2, "t": None, "x": 7.0, "y": 8.0})
    check("v9: 10-field trailer agrees: no notes", r["notes"], [])


def case_padding():
    body = [S(-0.03 + 0.015 * i) for i in range(2)] + [S(0.015 * i, i, 0, 0, 300) for i in range(4)]
    r = recplot.parse(rec("pad.rec", 9, body))
    check("padding: negative t kept first", r["t"][:3], [-0.03, -0.015, 0.0])
    check("padding: stats are over t >= 0", (r["stats"]["avg_speed"], r["stats"]["max_speed"]), (300.0, 300.0))
    check("padding: duration is the last t", r["stats"]["duration"], 0.045)
    r = recplot.parse(rec("padonly.rec", 9, [S(-0.03, vx=100), S(-0.015, vx=200)]))
    check("padding only: stats fall back to all samples", r["stats"]["avg_speed"], 150.0)
    check("padding only: duration 0", r["stats"]["duration"], 0)


def case_nonfinite():
    body = [S(0.0, 1), "0.015 nan 0 0 0 0 0", "0.03 0 inf 0 0 0 0", "0.045 0 0 0 1e999 0 0",
            "0.06 0 0 0 1e308 1e308 0", "0.075 0 0", S(0.09, 2) + " nan", "-", "-x 1 2 3"]
    r = recplot.parse(rec("nan.rec", 9, body))
    check("non-finite: only the two good samples", (r["n"], r["x"]), (2, [1.0, 2.0]))
    check("non-finite: dropped and noted", notes_with(r, "5 malformed"),
          ["5 malformed or non-finite sample(s) dropped"])
    check("non-finite: '-' and '-x' are records, not samples", r["counts"]["unknown"], 2)
    r = recplot.parse(rec("hugeticks.rec", 9, [S(0.0), "cp 1 1e300", "warp 1 5 tele 1e300 0 0 0 0 0"]))
    check("absurd ticks: mark untimed; absurd warp origin dropped",
          ([m["t"] for m in r["marks"]], r["counts"]["warp"]), ([None], {"tele": 1}))
    json.dumps(r, allow_nan=False)
    check("non-finite: output is strict JSON", True, True)


def case_long_lines():
    big = "9" * 20000
    head = HEAD + ["pmpin " + "a=1 " * 5000, "owner " + "x" * 20000]
    body = [S(0.0, 1), "0.015 " + big, S(0.03, 3), "cp " + big, S(0.045, 4)]
    r = recplot.parse(rec("long.rec", 9, body, head=head))
    check("20 KB lines: header values capped", (len(r["head"]["pmpin"]), len(r["head"]["owner"])),
          (recplot.PMPIN_MAX - 1, recplot.VALUE_MAX))
    check("20 KB lines: body lines skipped, the rest parses", (r["n"], r["x"]), (3, [1.0, 3.0, 4.0]))
    check("20 KB lines: noted", notes_with(r, "2 line(s) over"), ["2 line(s) over 4096 bytes skipped"])


def case_missing_begin():
    r = recplot.parse(rec("nobegin.rec", 9, [S(0.0, 1), S(0.015, 2), "end 1 2 0 0 0 0 0 0 0 0"], begin=False))
    check("no begin: samples still parse", (r["ok"], r["n"]), (True, 2))
    check("no begin: noted", r["notes"], ["no 'begin' before the first sample"])
    r = recplot.parse(rec("lobby.rec", 5, [], head=HEAD + ["samples 0"], begin=False))
    check("header only (lobby time): ok, empty", (r["ok"], r["n"], r["t"], r["end"]), (True, 0, [], None))
    check("header only: noted, no trailer complaint", r["notes"], ["no 'begin': header only"])
    r = recplot.parse(rec("hdr250.rec", 9, [], head=["junk %d" % i for i in range(250)], begin=False))
    check("250 header lines, no begin: refused", r, {"ok": False, "error": "no 'begin' in the first 200 header lines"})
    r = recplot.parse(rec("begin.rec", 9, [S(0.0)]))
    check("CONTROL: with begin, only the missing trailer is noted", r["notes"], ["no 'end' trailer"])


def case_non_utf8():
    data = (b"FTESURF-REC 9\nmap surf_x\nowner \xff\xfeBad\xc3\ntickrate 0.015\nbegin\n"
            + S(0.0, 1).encode() + b"\n\xff\xfe\x00junk\n0.015 \xff 0 0 0 0 0\n" + S(0.03, 3).encode() + b"\n")
    r = recplot.parse(write("utf.rec", data))
    check("non-UTF-8: ok, replaced in the header", (r["ok"], r["head"]["owner"]), (True, "\ufffd\ufffdBad\ufffd"))
    check("non-UTF-8: body garbage counted, bad sample dropped", (r["n"], r["counts"]["unknown"]), (2, 1))
    json.dumps(r, allow_nan=False)
    r = recplot.parse(write("bom.rec", b"\xef\xbb\xbfFTESURF-REC 4\r\ntickrate 0.015\r\nbegin\r\n"
                            + S(0.0).encode() + b"\r\n"))
    check("BOM and CRLF accepted", (r["ok"], r["v"], r["n"]), (True, 4, 1))


def case_rates():
    def rate_of(*keys):
        r = recplot.parse(rec("rate.rec", 9, [S(0.0), "cp 1 100"], head=["map m"] + list(keys)))
        return r["rate"], r["marks"][0]["t"]
    check("tickrate 0.01 (seconds per tick)", rate_of("tickrate 0.01"), (0.01, 1.0))
    check("tickrate 100 (Hz) -> 0.01", rate_of("tickrate 100"), (0.01, 1.0))
    check("movetickrate wins over tickrate", rate_of("tickrate 0.01", "movetickrate 0.015"), (0.015, 1.5))
    check("movetickrate 0 falls back to tickrate", rate_of("tickrate 0.015", "movetickrate 0"), (0.015, 1.5))
    check("movetickrate in Hz", rate_of("movetickrate 66.6666667")[1], 1.5)
    r = recplot.parse(rec("norate.rec", 9, [S(0.0), "cp 1 100", "split 1 100"], head=["map m", "tickrate x"]))
    check("no rate: marks untimed, no split mark, noted",
          (r["rate"], [m["t"] for m in r["marks"]], notes_with(r, "no usable")),
          (None, [None], ["no usable tickrate: markers are not timed"]))


def case_downsample():
    N, spike = 100000, 77777     # 7-column rows keep the file under max_bytes
    lines = ["%.3f %d %d 0 %s 0" % (i * 0.015, i, -i, "250 0" if i != spike else "3000 4000") for i in range(N)]
    path = rec("big.rec", 9, lines + ["end %d %d 0 0 0 0 0 0 0 0" % (N, N)])
    check("CONTROL: the 100k file fits max_bytes", os.path.getsize(path) < recplot.MAX_BYTES, True)
    r = recplot.parse(path)
    k = len(r["t"])
    check("100k: n counts every sample", r["n"], N)
    check("100k: kept <= 2 * max_points", k <= 2 * recplot.MAX_POINTS, True)
    check("100k: parallel arrays", {len(r[a]) for a in ("t", "x", "y", "z", "spd")}, {k})
    check("100k: first and last kept", (r["x"][0], r["x"][-1], r["t"][-1]), (0.0, float(N - 1), 1499.985))
    check("100k: kept are the stride multiples, then the last",
          r["x"][:-1] == [float(i) for i in range(0, N, r["stride"])], True)
    check("100k: max speed exact over all samples", r["stats"]["max_speed"], 5000.0)
    check("CONTROL: the spike is not on the kept path", 5000.0 in r["spd"], False)
    check("100k: no trailer note", r["notes"], [])
    r = recplot.parse(rec("small.rec", 9, [S(i * 0.015, i) for i in range(1001)]), max_points=10)
    check("max_points=10: kept <= 20, last kept", (len(r["t"]) <= 20, r["x"][-1]), (True, 1000.0))
    over = []
    for n in range(1, 120):
        r = recplot.parse(rec("n.rec", 9, ["%d %d 0 0 0 0 0" % (i, i) for i in range(n)]), max_points=5)
        if len(r["t"]) > 10 or r["x"][0] != 0 or r["x"][-1] != n - 1:
            over.append((n, len(r["t"])))
    check("every length 1..119 at max_points=5: <= 10, ends kept", over, [])


def case_trailer_notes():
    body = [S(0.0), "in 1 1000 0 0 0 0 0 0 0 0 1", S(0.015), "ride 1 1000 arm 1 0 0",
            "warp 1 1001 0 tele 1 2 3 4 5 6 0", "end 1 5 0 0 3 2 0 0 0 1"]
    r = recplot.parse(rec("mismatch.rec", 9, body, head=V7_HEAD))
    check("trailer mismatches noted", sorted(notes_with(r, "trailer")),
          ["trailer says 0 ride, the file has 1", "trailer says 1 portal, the file has 0",
           "trailer says 2 warp, the file has 1", "trailer says 3 in, the file has 1",
           "trailer says 5 samples, the file has 2"])
    r = recplot.parse(rec("match.rec", 9, body[:-1] + ["end 1 2 0 0 1 1 1 0 0 0"], head=V7_HEAD))
    check("CONTROL: an agreeing trailer: no notes", r["notes"], [])
    r = recplot.parse(rec("v5count.rec", 5, [S(0.0), "warp 1 1 tele 1 2 3 4 5 6", "end 1 1 0 0"]))
    check("v5: no in/warp fields to compare", r["notes"], [])
    r = recplot.parse(rec("cut.rec", 9, [S(0.015 * i) for i in range(400)] + ["end 1 400 0 0 0 0 0 0 0 0"]),
                      max_bytes=4000)
    check("max_bytes: truncated, no trailer compare", (r["truncated"], r["end"], r["notes"]),
          (True, None, ["stopped at 4000 bytes: the rest of the file was not read"]))
    check("max_bytes: kept only whole lines", r["n"] > 0 and r["n"] < 400, True)


def case_unknown_records():
    body = [S(0.0), "stagepost 1 234 5", S(0.015), "abandon 7", "abandon", "cp one 2", "end 1 2 0 0"]
    r = recplot.parse(rec("unk.rec", 9, body))
    check("unknown records counted, not errors", (r["ok"], r["n"], r["counts"]["unknown"]), (True, 2, 3))
    check("unknown records named in a note", notes_with(r, "unknown"), ["unknown records: abandon x2, stagepost x1"])
    check("a malformed known record is noted", notes_with(r, "1 malformed record"), ["1 malformed record(s) skipped"])
    body = [S(0.0)] + ["rec%d 1" % i for i in range(100)] + ["cp %d %d" % (i, i) for i in range(3000)]
    r = recplot.parse(rec("many.rec", 9, body))
    check("bounded: marks capped, names capped", (len(r["marks"]), r["counts"]["unknown"],
                                                  notes_with(r, "unknown")[0].count(" x")),
          (recplot.MAX_MARKS, 100, recplot.MAX_UNKNOWN_NAMES))


def case_resume_rebase():
    body = ["in 1 1000 0 0 0 0 0 0 0 0", S(0.0), "resume 3 50", "in 2 2000 0 0 0 0 0 0 0 0",
            "warp 2 2010 tele 1 2 3 4 5 6", S(0.75)]
    r = recplot.parse(rec("resume.rec", 7, body, head=V7_HEAD))
    w = first(r, "warp")
    check("resume: start rebased to next in row mt - ticks", w["t"], 0.9)
    r = recplot.parse(rec("noresume.rec", 7, [b for b in body if not b.startswith("resume")], head=V7_HEAD))
    w = first(r, "warp")
    check("CONTROL: without resume, t from instart", w["t"], 15.15)
    r = recplot.parse(rec("hugeresume.rec", 7, ["resume 1 1e300", "in 1 5 0 0 0 0 0 0 0 0",
                                                "warp 1 6 tele 1 2 3 4 5 6"], head=V7_HEAD))
    check("resume with absurd ticks: still ok, warp timed from instart", (r["ok"], first(r, "warp")["t"]),
          (True, round((6 - 1000) * 0.015, 3)))
    r = recplot.parse(rec("split.rec", 7,["warp 2 1010 tele 1 2 3 4 5 6"], head=HEAD + ["instart 900 1000"]))
    check("instart <mt> <start>: t counts from the start tick", first(r, "warp")["t"], 0.15)
    r = recplot.parse(rec("nostart.rec", 7, body[3:], head=HEAD))
    w = first(r, "warp")
    check("no instart: warp untimed, still on the map", (w["t"], w["x"]), (None, 1.0))


def case_spec():
    body = ["in 1 1000 0 0 0 0 0 0 0 0 0", S(0.0, 5, 6),
            "spec 1 1 1001 0.004 5 6 64 300 0 0 0 100.000",
            "spec 0 1 1001 0.004 5 6 64 300 0 0 0 112.250 leave",
            "in 2 1001 0.004 0 0 0 0 0 0 0 0", S(0.015, 10, 6),
            "spec 1 2 1002 0 10 6 64 300 0 0 0 130.000"]
    r = recplot.parse(rec("spec.rec", 9, body, head=V7_HEAD))
    got = [(m["t"], m["x"], m["y"], m["held"], m["why"]) for m in r["marks"] if m["k"] == "spec"]
    check("spec: one mark per window at its point; an open one last", got,
          [(0.015, 5.0, 6.0, 12.25, "leave"), (0.03, 10.0, 6.0, None, "open")])
    check("spec: windows counted, not unknown", (r["counts"].get("spec"), r["counts"]["unknown"]), (2, 0))
    check("spec: no note but the missing trailer", r["notes"], ["no 'end' trailer"])
    r = recplot.parse(rec("specbad.rec", 9, [S(0.0), "spec 1 1 1001", "spec 2 1 1 0 1 2 3 4 5 6 0 1.0",
                                            "spec 0 1 1 0 1 2 3 4 5 6 0 1e400 leave"]))
    check("spec: malformed edges skipped and noted, no mark",
          (notes_with(r, "3 malformed"), r["marks"], r["counts"].get("spec")),
          (["3 malformed record(s) skipped"], [], 0))
    r = recplot.parse(rec("specold.rec", 9, [S(0.0), "spek 1 1 1001"]))
    check("spec: a near-miss word is still an unknown record", r["counts"]["unknown"], 1)
    json.dumps(r, allow_nan=False)


def case_never_raises():
    rnd = random.Random(359)
    cases = [("missing", os.path.join(TMP, "nope.rec")), ("None", None), ("directory", TMP),
             ("empty", write("empty.rec", b"")), ("not a rec", write("x.rec", "hello\nbegin\n")),
             ("version only", write("vonly.rec", "FTESURF-REC 9"))]
    for i in range(20):
        cases.append(("random %d" % i, write("r%d.rec" % i, bytes(rnd.randrange(256) for _ in range(5000)))))
        junk = "\n".join(rnd.choice(["cp", "warp", "portal", "end", "split", "in", "-1", "1e5", "x", "nan",
                                     "resume", "retry", "ghost", "spec", "0"]) + " " + " ".join(
            rnd.choice(["1", "-2", "nan", "inf", "tele", "", "3.5", "1e400", "x"]) for _ in range(rnd.randrange(12)))
            for _ in range(200))
        cases.append(("fuzz %d" % i, write("f%d.rec" % i, "FTESURF-REC 9\ntickrate 0.015\ninstart 5\nbegin\n" + junk)))
    raised, oks = [], collections.Counter()
    for label, path in cases:
        try:
            r = recplot.parse(path)
            json.dumps(r, allow_nan=False)
            oks[r["ok"]] += 1
        except Exception as e:  # noqa: BLE001
            raised.append("%s: %r" % (label, e))
    check("never raises (%d inputs), strict JSON" % len(cases), raised, [])
    check("bad inputs are ok:false", [recplot.parse(p)["ok"] for _, p in cases[:5]], [False] * 5)
    check("CONTROL: 'version only' is an empty ok file", recplot.parse(cases[5][1])["ok"], True)
    check("error text carries no path", "nope" in recplot.parse(cases[0][1])["error"], False)


def case_corpus():
    root = os.environ.get("RECPLOT_CORPUS") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "ftesurf", "data", "runs")
    files = [os.path.join(d, f) for d, _, fs in os.walk(root) for f in fs if f.endswith(".rec")]
    if not files:
        print("     (no corpus at %s -- skipped)" % root)
        return
    per_v, notes, errs, over, slowest = collections.Counter(), collections.Counter(), [], [], (0, "")
    for p in sorted(files):
        t0 = time.perf_counter()
        try:
            r = recplot.parse(p)
            json.dumps(r, allow_nan=False)
        except Exception as e:  # noqa: BLE001
            errs.append("%s raised %r" % (p, e))
            continue
        slowest = max(slowest, (time.perf_counter() - t0, p))
        if not r["ok"]:
            errs.append("%s: %s" % (p, r["error"]))
            continue
        per_v[r["v"]] += 1
        if len(r["t"]) > 2 * recplot.MAX_POINTS:
            over.append(p)
        for n in r["notes"]:
            notes[n] += 1
    print("     corpus %s: %d files, by version %s" % (root, len(files), dict(sorted(per_v.items()))))
    for n, c in notes.most_common():
        print("     note x%d: %s" % (c, n))
    print("     slowest %.3f s: %s" % slowest)
    check("corpus: every file parses ok, strict JSON", errs, [])
    check("corpus: every path within 2*max_points", over, [])


def main():
    for case in (case_v3_v4, case_v5_stage, case_v7_warp, case_v9, case_padding, case_nonfinite,
                 case_long_lines, case_missing_begin, case_non_utf8, case_rates, case_downsample,
                 case_trailer_notes, case_unknown_records, case_resume_rebase, case_spec,
                 case_never_raises,
                 case_corpus):
        print("%s:" % case.__name__)
        case()
    shutil.rmtree(TMP, ignore_errors=True)
    print("\n%d failed" % len(FAILED))
    for f in FAILED:
        print("  " + f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
