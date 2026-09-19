#!/usr/bin/env python3
"""rigcompare.py -- diff two logs of cfg/test/p386case.cfg (or p386maps.cfg), map by map.

  python tools/linux/rigcompare.py <a.log> <b.log> [--show 20] [--quiet]

Sections are cut at the cfg's "======== P386CASE map <label>" echoes.  Per map it compares:
mapname, hl2_unresolved and _visible, the hl2_missing list (lowercased, sorted), the unparsed
list, images r_imagelist reports failed that were not failed before this map, "Couldn't load" /
"Unable to load" / "Can't find" lines, exec lines (execing / couldn't exec / not execing), zstd
error lines, "did not resolve from any wad" texture lines printed during the load, and the fs:
line (hash valid|STALE; only a note when the two logs ran different fs_cache values).  The
missed-lookup count is a note unless --strict-fs; searchpath and index counts and load times are
printed, never compared: the rig's library is a subset of Windows'.
Exit 0 = every compared field equal, 1 = a difference, 2 = unusable input.
"""

import argparse
import re
import sys

TS = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ")
LINK = re.compile(r"\^\[([^\\\]]*?)(?:\\[^\]]*?)?\^\]")
COLOR = re.compile(r"\^(?:x[0-9a-fA-F]{3}|&[0-9a-fA-F]{2}|[0-9a-zA-Z])")
MARK = re.compile(r"^======== P386CASE (map|report|end|done|setup)\s*(\S*)")
CVAR = re.compile(r'^"(mapname|hl2_unresolved|hl2_unresolved_visible|fs_cache)" is "([^"]*)"')
FSLINE = re.compile(r"^fs: (\S+) in (\d+)ms \| (\d+) lookups missed the hash \| (\d+) searchpaths, "
                    r"(\d+) files indexed \| hash (valid|STALE)")
MISSROW = re.compile(r"^    (.+?)\s+-- ")
NORES = re.compile(r'^texture "(.+)" did not resolve from any wad')
LOADFAIL = re.compile(r"(Couldn't load|Unable to load|Can't find) (.+)$")
EXEC = re.compile(r"^(execing|couldn't exec|not execing) (\S+)")
ZSTD = re.compile(r"auxiliary compression|needs a build with zstd")
IMG = re.compile(r"^(?:\([^)]*\))?(\S.*?): .*?(failed|not loaded|loading|loaded \()")


def plain(line):
    line = TS.sub("", line.rstrip("\r\n"))
    line = LINK.sub(lambda m: m.group(1), line)
    return COLOR.sub("", line)


def parse(path):
    try:
        text = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError as e:
        sys.exit("rigcompare: %s" % e)
    maps, order, cur, phase = {}, [], None, None
    failed_seen = set()
    head = {"fs_cache": None, "done": False}
    for raw in text:
        ln = plain(raw)
        m = MARK.match(ln)
        if m:
            kind, label = m.groups()
            if kind == "map":
                cur = maps.setdefault(label, new_section())
                order.append(label)
                phase = "load"
            elif kind == "report" and cur is not None:
                phase = "report"
                cur["img_failed_before"] = set(failed_seen)
                cur["img_failed_now"] = set()
            elif kind == "end" and cur is not None:
                if cur.get("img_failed_now") is not None and cur["imagelist"]:
                    failed_seen |= cur["img_failed_now"]
                phase = "end"
            elif kind == "done":
                head["done"] = True
                cur = None
            continue
        c = CVAR.match(ln)
        if c:
            if c.group(1) == "fs_cache" and cur is None:
                head["fs_cache"] = c.group(2)
            elif cur is not None and phase == "report":
                cur[c.group(1)] = c.group(2)
            continue
        if cur is None:
            continue
        f = FSLINE.match(ln)
        if f:
            cur["fs"].append({"name": f.group(1), "ms": int(f.group(2)), "missed": int(f.group(3)),
                              "paths": int(f.group(4)), "indexed": int(f.group(5)), "hash": f.group(6)})
            continue
        e = EXEC.match(ln)
        if e:
            cur["execs"].append("%s %s" % (e.group(1), e.group(2).lower()))
            continue
        lf = LOADFAIL.search(ln)
        if lf and not ln.startswith("    "):
            cur["loadfail"].append("%s %s" % (lf.group(1), lf.group(2).strip().lower()))
        if ZSTD.search(ln):
            cur["zstd"] += 1
        n = NORES.match(ln)
        if n:
            if phase == "load":     # r_imagelist re-locates images and repeats these lines
                cur["nores"].add(n.group(1).replace("\\", "/").lower())
            continue
        if phase == "report":
            if "did not resolve" in ln:
                cur["listing"] = "missing"
            elif "did not parse" in ln:
                cur["listing"] = "unparsed"
            elif ln.startswith("r_imagelist") or ln.endswith("images total"):
                pass
            r = MISSROW.match(ln)
            if r and cur.get("listing") in ("missing", "unparsed"):
                cur[cur["listing"]].add(r.group(1).lower())
            elif ln.startswith("    ") and cur.get("listing") == "unparsed":
                cur["unparsed"].add(ln.strip().lower())
            im = IMG.match(ln)
            if im and not ln.startswith(" "):
                cur["imagelist"] = True
                st = im.group(2)
                cur["img_status"][st] = cur["img_status"].get(st, 0) + 1
                if st == "failed":
                    cur["img_failed_now"].add(im.group(1).strip().lower())
    for s in maps.values():
        if s.get("img_failed_now") is not None:
            s["img_newfail"] = s["img_failed_now"] - s["img_failed_before"]
    return head, order, maps


def new_section():
    return {"fs": [], "execs": [], "loadfail": [], "zstd": 0, "missing": set(), "unparsed": set(), "nores": set(),
            "img_status": {}, "imagelist": False, "img_newfail": set()}


def setdiff(a, b, show):
    x, y = sorted(a - b), sorted(b - a)
    out = []
    if x:
        out.append("only A (%d): %s%s" % (len(x), ", ".join(x[:show]), " ..." if len(x) > show else ""))
    if y:
        out.append("only B (%d): %s%s" % (len(y), ", ".join(y[:show]), " ..." if len(y) > show else ""))
    return out


def compare(a, b, show, strict_fs=False, hash_note=False):
    diffs = []

    def fld(name, va, vb):
        if va != vb:
            diffs.append("%s: A %s | B %s" % (name, va, vb))
    fld("mapname", a.get("mapname"), b.get("mapname"))
    fld("hl2_unresolved", a.get("hl2_unresolved"), b.get("hl2_unresolved"))
    fld("hl2_unresolved_visible", a.get("hl2_unresolved_visible"), b.get("hl2_unresolved_visible"))
    for key, label in (("missing", "hl2_missing"), ("unparsed", "unparsed"), ("img_newfail", "images newly failed"),
                       ("nores", "textures that did not resolve")):
        if key == "img_newfail" and not (a["imagelist"] and b["imagelist"]):
            continue    # one log ran without r_imagelist (p386caseq.cfg)
        d = setdiff(a[key], b[key], show)
        if d:
            diffs.append("%s: %s" % (label, "; ".join(d)))
    for key, label in (("loadfail", "load failures"), ("execs", "execs")):
        d = setdiff(set(a[key]), set(b[key]), show)
        if d:
            diffs.append("%s: %s" % (label, "; ".join(d)))
        elif sorted(a[key]) != sorted(b[key]):
            diffs.append("%s: same names, different counts (A %d, B %d)" % (label, len(a[key]), len(b[key])))
    fld("zstd lines", a["zstd"], b["zstd"])
    notes = []
    ha, hb = [(f["name"].lower(), f["hash"]) for f in a["fs"]], [(f["name"].lower(), f["hash"]) for f in b["fs"]]
    if hash_note and ha != hb:
        # fs_cache 0 never rehashes, so its loads say STALE by construction
        notes.append("fs (name, hash): A %s | B %s" % (ha, hb))
    else:
        fld("fs (name, hash)", ha, hb)
    ma, mb = [f["missed"] for f in a["fs"]], [f["missed"] for f in b["fs"]]
    if ma != mb:
        # a subset library changes how many lookups find nothing; content fields say whether it mattered
        (diffs if strict_fs else notes).append("fs lookups missed the hash: A %s | B %s" % (ma, mb))
    return diffs, notes


def summary(s):
    fs = s["fs"][-1] if s["fs"] else None
    return "unres %s vis %s miss %d unparsed %d nores %d newfail %d imgs %s load-fail %d execs %d zstd %d fs %s" % (
        s.get("hl2_unresolved"), s.get("hl2_unresolved_visible"), len(s["missing"]), len(s["unparsed"]), len(s["nores"]),
        len(s["img_newfail"]), sum(s["img_status"].values()) if s["imagelist"] else "-",
        len(s["loadfail"]), len(s["execs"]), s["zstd"],
        ("%s %dms missed %d paths %d idx %d %s" % (fs["name"], fs["ms"], fs["missed"], fs["paths"],
                                                   fs["indexed"], fs["hash"]) if fs else "none"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--show", type=int, default=20)
    ap.add_argument("--quiet", action="store_true", help="verdict lines only")
    ap.add_argument("--strict-fs", action="store_true", help="count a missed-lookup difference as a DIFF")
    a = ap.parse_args()
    ha, oa, ma = parse(a.a)
    hb, ob, mb = parse(a.b)
    if not oa or not ob:
        print("rigcompare: no P386CASE sections in %s" % (a.a if not oa else a.b))
        return 2
    print("A %s  fs_cache %s  %s" % (a.a, ha["fs_cache"], "complete" if ha["done"] else "INCOMPLETE"))
    print("B %s  fs_cache %s  %s" % (a.b, hb["fs_cache"], "complete" if hb["done"] else "INCOMPLETE"))
    bad = 0
    labels = oa + [x for x in ob if x not in oa]
    for label in labels:
        if label not in ma or label not in mb:
            print("%-30s MISSING in %s" % (label, "A" if label not in ma else "B"))
            bad += 1
            continue
        d, notes = compare(ma[label], mb[label], a.show, a.strict_fs, ha["fs_cache"] != hb["fs_cache"])
        print("%-30s %s" % (label, "SAME" if not d else "DIFF (%d)" % len(d)))
        if not a.quiet:
            print("    A: " + summary(ma[label]))
            print("    B: " + summary(mb[label]))
            for x in d:
                print("    * " + x)
            for x in notes:
                print("    ~ " + x)
        bad += bool(d)
    print("verdict: %s (%d of %d maps differ)" % ("SAME" if not bad else "DIFF", bad, len(labels)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
