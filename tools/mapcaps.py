#!/usr/bin/env python3
"""
mapcaps.py -- per-map speed caps: the `set sv_maxvelocity` line of cfg/maps/map_<map>.cfg.

The engine reads that file at every map load (SV_LoadMapRuleset, sv_phys.c); a zone file's own
nonzero maxVelocity beats it (P841) and cfg/default.cfg's 3500 is what is left without either.
80 such files came from the maps' own entity lumps.  This adds the caps Momentum and KSF run, so
a raised cap does not have to be set by hand in zone_edit (Lex, 20 Nov 2026: surf_affliction).

Per map, the first that applies:
  1. a Momentum build: its Momentum zone file's maxVelocity
  2. a second build (the list's `of` column: _css, _ksf, _fix, _njv): the plain map's Momentum
     zone maxVelocity, else the plain map's entity lump (owner, 20 Oct)
  3. a map Momentum does not list, or whose zone file is missing: KSF's maxvelocity
  4. the map's own entity-lump value (the file's existing line)
  5. nothing: 3500
Zero or absent is "no override" in both catalogues, and Momentum honours a map's lump
(point_servercommand whitelist), so a zero falls straight to 4.

Inputs, cached (no network here):
  --list       data/mapdl.txt or mapdl.net.txt: `dl <name> ...`, column 11 the `of` map
  --catalogue  Momentum's map list: JSON keyed by name or a list of {"name"} (scratch momcache.py
               output), or a Momentum game dir (_cache/*.dat)
  --zones      <name>.json bodies of https://api.momentum-mod.org/v1/maps/<id>/zones
  --ksf        name<TAB>maxvelocity[<TAB>tier], from https://ksf.surf/maps' embedded page data
A line this tool writes has `// mapcaps src=<src> lump=<N|->` above it, so a rerun still knows
the lump's own value.  Other lines of a file are kept; a file whose sv_maxvelocity lines cannot
be read is skipped and reported.  --shadow DIRs (in SV_FindZoneFile order) report zone files
whose own maxVelocity would override the file.

usage: python3 -I tools/mapcaps.py --list L --catalogue C --zones Z --ksf K [--cfgdir DIR]
                                   [--shadow DIR ...] [--show MAP ...] [--tsv OUT] [--write]
"""
import argparse
import collections
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mapmeta  # noqa: E402  (read_msml)

DEFAULT = 3500.0            # cfg/default.cfg
MAX = 100000.0              # SV_LoadZoneRuleset's range
CFGDIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ftesurf", "cfg", "maps")
SETLINE = re.compile(r"^\s*(?:(?:set|seta|sets|setr)\s+)?sv_maxvelocity\s+(\S+)\s*$", re.I)
MARKER = re.compile(r"^\s*//\s*mapcaps\s+src=(\S+)\s+lump=(\S+)\s*$")
MAPNAME = re.compile(r"^[A-Za-z0-9_+-][A-Za-z0-9_.+-]*$")   # also the file name: no paths


def slurp(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def num(s):
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    return v if v == v and abs(v) != float("inf") else None


def fmt(v):
    return "%d" % v if v == int(v) else "%g" % v


def read_list(path):
    """[(name, of or None)] in file order."""
    out = []
    for ln in slurp(path).splitlines():
        t = ln.split()
        if len(t) >= 2 and t[0] == "dl":
            of = t[10] if len(t) > 10 and t[10] != "-" else None
            if MAPNAME.match(t[1]) and (of is None or MAPNAME.match(of)):
                out.append((t[1], of))
            else:
                print("  ! %s: map name %r not used" % (path, ln.strip()[:80]), file=sys.stderr)
    return out


def read_catalogue(path):
    if os.path.isdir(path):
        names = set()
        for p in glob.glob(os.path.join(path, "_cache", "*.dat")):
            names.update(m["name"].lower() for m in mapmeta.read_msml(p))
        if not names:
            raise SystemExit("%s: no _cache/*.dat" % path)
        return names
    j = json.loads(slurp(path))
    if isinstance(j, dict):
        return {k.lower() for k in j}
    return {m["name"].lower() for m in j}


def zone_cap(zones, name):
    """Momentum's cap for this map: None unknown (no zone file), 0 none, else the value."""
    p = os.path.join(zones, name.lower() + ".json")
    if not os.path.isfile(p):
        return None
    try:
        j = json.loads(slurp(p))
    except (OSError, ValueError):
        return None
    if not isinstance(j, dict) or "tracks" not in j:
        return None
    v = j.get("maxVelocity", 0)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return 0.0
    return float(v) if 1 <= v <= MAX else 0.0


def read_ksf(path):
    out = {}
    for ln in slurp(path).splitlines():
        t = ln.split("\t")
        if len(t) >= 2 and num(t[1]) is not None:
            v = num(t[1])
            out[t[0].lower()] = v if 1 <= v <= MAX else 0.0
    return out


def parse_cfg(text):
    """-> (lines, [set line indices], [values], marker index or None, marker lump or None, ok)."""
    lines = text.splitlines()
    sets, vals, mk, lump = [], [], None, None
    for i, ln in enumerate(lines):
        m = SETLINE.match(ln)
        if m:
            sets.append(i)
            vals.append(num(m.group(1)))
            continue
        m = MARKER.match(ln)
        if m:
            mk, lump = i, num(m.group(2))
    ok = len(set(vals)) <= 1 and None not in vals and (mk is None or len(sets) == 1)
    return lines, sets, vals, mk, lump, ok


def decide(name, of, cat, zone, ksf, lump, baselump):
    """-> (cap or None, source).  lump/baselump: the entity-lump values, or None."""
    low, base = name.lower(), (of or name).lower()
    if of is None and low in cat:
        z = zone(low)
        if z:
            return z, "mom"
        if z is not None:
            return lump, "lump" if lump else "-"
    if of is not None and base in cat:
        z = zone(base)
        if z:
            return z, "mom:" + base
        if z is not None:
            if lump:
                return lump, "lump"
            return baselump, ("lump:" + base) if baselump else "-"
    k = ksf.get(low, ksf.get(base))
    if k:
        return k, "ksf"
    return lump, "lump" if lump else "-"


def shadow_cap(dirs, name):
    """The first zone file's own maxVelocity across dirs, as (path, value), or None."""
    for d in dirs:
        p = os.path.join(d, name + ".json")
        if os.path.isfile(p):
            try:
                j = json.loads(slurp(p))
            except (OSError, ValueError):
                return None
            v = j.get("maxVelocity") if isinstance(j, dict) else None
            if isinstance(v, (int, float)) and not isinstance(v, bool) and 1 <= v <= MAX:
                return p, float(v)
            return None
    return None


def plan(name, of, cat, zone, ksf, cfgdir, baselumps):
    """One map -> dict(action, text, ...).  action: none same new merge restore remove skip."""
    path = os.path.join(cfgdir, "map_%s.cfg" % name)
    text = slurp(path) if os.path.isfile(path) else None
    r = dict(name=name, of=of or "-", path=path, cur=None, lump=None, want=None, src="-", text=None)
    lines, sets, vals, mk, mlump, ok = parse_cfg(text or "")
    if text is not None and not ok:
        r["action"] = "skip"
        return r
    cur = vals[0] if vals else None
    lump = mlump if mk is not None else cur
    r.update(cur=cur, lump=lump)
    base = (of or "").lower()
    want, src = decide(name, of, cat, zone, ksf, lump, baselumps.get(base))
    r.update(want=want, src=src)
    if want is not None and want == DEFAULT and not lump:
        want = None                     # the default already: no line needed
    marker = "// mapcaps src=%s lump=%s" % (src, fmt(lump) if lump else "-")
    if want is None:
        if not sets:
            r["action"] = "none"
            return r
        keep = [ln for i, ln in enumerate(lines) if i not in sets and i != mk]
        r["action"] = "remove"
        r["text"] = "" if all(not ln.strip() or ln.lstrip().startswith("//") for ln in keep) \
            and lines and lines[0].startswith("// %s -- speed cap" % name) else "\n".join(keep) + "\n"
        return r
    if cur == want:
        if src == "lump" and mk is not None:    # a lump value back on its own line: drop the marker
            r["action"] = "restore"
            r["text"] = "\n".join(ln for i, ln in enumerate(lines) if i != mk) + "\n"
        elif mk is not None and lines[mk].strip() != marker:
            r["action"] = "merge"               # same cap, another source
            r["text"] = "\n".join(marker if i == mk else ln for i, ln in enumerate(lines)) + "\n"
        else:
            r["action"] = "same"
        return r
    setln = "set sv_maxvelocity %s" % fmt(want)
    if text is None:
        r["action"] = "new"
        r["text"] = "// %s -- speed cap, written by tools/mapcaps.py (its docstring has the rules).\n%s\n%s\n" % (
            name, marker, setln)
        return r
    out = list(lines)
    if sets:
        out[sets[0]] = setln
        if src == "lump" and mk is not None:
            del out[mk]
            r["action"] = "restore"
        elif mk is not None:
            out[mk] = marker
            r["action"] = "merge"
        else:
            out.insert(sets[0], marker)
            r["action"] = "merge"
    else:
        out += ["", marker, setln]
        r["action"] = "merge"
    r["text"] = "\n".join(out) + "\n"
    return r


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--list", required=True)
    ap.add_argument("--catalogue", required=True)
    ap.add_argument("--zones", required=True)
    ap.add_argument("--ksf", required=True)
    ap.add_argument("--cfgdir", default=CFGDIR)
    ap.add_argument("--shadow", action="append", default=[], help="zone dir, in SV_FindZoneFile order")
    ap.add_argument("--show", action="append", default=[], help="print this map's decision")
    ap.add_argument("--tsv", help="write every map's decision here")
    ap.add_argument("--write", action="store_true", help="write the files (default: report only)")
    a = ap.parse_args(argv)

    cat = read_catalogue(a.catalogue)
    ksf = read_ksf(a.ksf)
    zcache = {}

    def zone(n):
        if n not in zcache:
            zcache[n] = zone_cap(a.zones, n)
        return zcache[n]

    rows = read_list(a.list)
    nlist = len(rows)
    seen = {n.lower() for n, _ in rows}
    for p in sorted(glob.glob(os.path.join(a.cfgdir, "map_*.cfg"))):
        n = os.path.basename(p)[4:-4]
        if n.lower() not in seen:
            rows.append((n, None))
            seen.add(n.lower())
    baselumps = {}
    for n, of in rows:
        if of:
            p = os.path.join(a.cfgdir, "map_%s.cfg" % of)
            if os.path.isfile(p):
                lines, sets, vals, mk, mlump, ok = parse_cfg(slurp(p))
                if ok and vals:
                    baselumps[of.lower()] = mlump if mk is not None else vals[0]

    plans = [plan(n, of, cat, zone, ksf, a.cfgdir, baselumps) for n, of in rows]
    act = collections.Counter(r["action"] for r in plans)
    ch = [r for r in plans if r["action"] in ("new", "merge", "restore", "remove")]
    print("maps %d (list %d): %s" % (len(plans), nlist, dict(sorted(act.items()))))
    print("caps by source (every map with one):",
          dict(collections.Counter(r["src"].split(":")[0] for r in plans if r["want"]).most_common()))
    print("changes by source:", dict(collections.Counter(r["src"].split(":")[0] for r in ch).most_common()))
    sfx = collections.Counter(r["name"].rsplit("_", 1)[-1] for r in ch if r["of"] != "-")
    print("  second builds among them, by suffix:", dict(sfx.most_common()))
    eff = lambda v: v if v else DEFAULT     # noqa: E731
    lower = [r for r in ch if eff(r["want"]) < eff(r["cur"])]
    print("  raise %d, lower %d:%s" % (len(ch) - len(lower), len(lower),
                                       "".join("\n    %s %s -> %s (%s)" % (r["name"], fmt(eff(r["cur"])),
                                               fmt(eff(r["want"])), r["src"]) for r in lower)))
    for r in plans:
        if r["action"] == "skip":
            print("SKIP %s: its sv_maxvelocity lines do not read as one value; not touched" % r["path"])
    if a.shadow:
        for r in plans:
            s = shadow_cap(a.shadow, r["name"])
            if s and s[1] != eff(r["want"] if r["action"] != "skip" else r["cur"]):
                print("SHADOW %s: %s says %s, so %s's %s never applies" % (
                    r["name"], s[0], fmt(s[1]), "this file" if r["want"] else "the default", fmt(eff(r["want"]))))
    for n in a.show:
        r = next((x for x in plans if x["name"].lower() == n.lower()), None)
        print("SHOW", n, r and {k: r[k] for k in ("of", "src", "want", "cur", "lump", "action")})
    if a.tsv:
        with open(a.tsv, "w", encoding="utf-8") as f:
            f.write("name\tof\tsrc\twant\tcur\tlump\taction\n")
            for r in plans:
                f.write("\t".join(str(fmt(v) if isinstance(v, float) else v) for v in (
                    r["name"], r["of"], r["src"], r["want"] or "-", r["cur"] or "-", r["lump"] or "-",
                    r["action"])) + "\n")
    if not a.write:
        print("report only: --write to apply %d change(s) under %s" % (len(ch), a.cfgdir))
        return 0
    for r in ch:
        if r["text"] == "":
            os.remove(r["path"])
        else:
            with open(r["path"], "w", encoding="utf-8", newline="\n") as f:
                f.write(r["text"])
    print("wrote %d file(s) under %s" % (len(ch), a.cfgdir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
