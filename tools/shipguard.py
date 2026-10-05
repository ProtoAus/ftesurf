#!/usr/bin/env python3
"""shipguard.py -- does the release archive contain what the QuakeC asks for?

WHY THIS EXISTS.  Three separate "the feature is broken" reports in one session
(2026-09-28) were ONE cause: content named by a string literal in QC that
release.ps1's allowlist never carried.  The zone library (587 maps drew "this map
has no zone file"), the voice icons (an error texture beside every player's name,
permanently) and the map-shot backdrop (a full-screen error texture).  0.1.15 had
to be CUT because 0.1.14 shipped the map-download code and no data/mapdl.txt for
it to read.  See AGENTS.md's table.

Nothing checked the allowlist against the code.  release.ps1 proves the archive
matches the stage and the stage matches the allowlist -- but the allowlist is
hand-maintained and was wrong three times, and the build box has all the content,
so NO AMOUNT OF LOCAL TESTING REPRODUCES ANY OF THEM.  This is that check.

WHAT IT DOES.  Reads $ShipRootFiles, $ShipGameFiles and $ShipGlobs straight out of
release.ps1 (it must not carry a copy of them, or the two drift and the gate grades
a ship set nobody ships), resolves them over the filesystem exactly as release.ps1
does -- NON-RECURSIVELY, with each entry's Filter and Deny -- then sweeps
src/**/*.qc for string literals under an asset root and asks whether each one is in
the result.

THE TWO THINGS BACKLOG SAID WOULD BE HARD, and how each is handled:

1. "Most of those strings are built, not literal."  True of the FILE and not of the
   DIRECTORY, and a ship glob is per-directory.  `sprintf("gfx/mapshots/%s-%s.jpg",
   uuid, size)` is not greppable as a path, but `gfx/mapshots` is, and that is the
   unit the allowlist expresses.  So a built path is reduced (`%s` -> `*`) and
   judged on its directory; a concrete path is judged on the file.  That is what
   lets one rule catch all three historical faults rather than one of them.

2. "Some misses are correct."  gfx/mapshots is 1.1 GB and must never ship;
   maps/zones/online resolves into the Momentum install; data/saves is the player's
   own tree.  DENY below carries each with a stated reason, and an entry with no
   reason is a bug in this file.  A gate that cries wolf on a correct absence gets
   turned off, which is worse than no gate.

AND A THIRD: AN EXTENSIONLESS LITERAL IS A PREFIX, NOT A FILE NAME.  17 of the 18
misses this tool reported on its first run were one false positive -- the engine
resolves `precache_pic("gfx/thumbnails/speaking_off")` by trying extensions, and a
`strcat("gfx/mapthumbs/atlas", ftos(page))` prefix is completed by the page number.
So a literal with no extension is judged by whether ANY shipped file starts with it,
which is directory-anchored because the literal carries its directory.  That is
deliberately looser than an exact match: `gfx/mapthumbs/at` would be satisfied by
`atlas0.png`.  The looseness is the price of not reporting 17 correct paths, and it
only applies where the mod itself wrote no extension.

AND A FOURTH, found while writing it: THE BUILTIN DECIDES WHETHER A PATH IS A LOAD.
`ui_file_exists("gfx/env/xray1.png")` is a QUESTION and the caller has a
$blackimage fallback for the answer (m_milk.qc); `drawpic` of the same string is a
DEMAND and substitutes a visible error texture on a miss (pr_menu.c:622-632).
AGENTS.md already records that drawpic, drawsubpic and precache_pic behave three
different ways on a miss.  So a literal reached through a probe is RUNTIME, not a
miss -- without that split the gate's first finding would be art that is absent on
the build box too and guarded at its only call site.

    python tools/shipguard.py            report; exit 1 on any unexplained MISS
    python tools/shipguard.py --verbose  list every literal and its verdict
    python tools/shipguard.py --mutate N falsifier: hide the Nth covering glob from
                                         a COPY of the ship set and assert that a
                                         MISS appears.  The gate must be seen to
                                         fire, or "0 misses" is unfalsifiable.

NOT COVERED, MEASURED RATHER THAN ASSUMED.  Paths assembled from a variable with no
literal prefix at all (`strcat(root, name)` where root is itself computed) are
invisible here, as is anything the ENGINE names rather than the mod.  `--mutate`
over all 13 ship globs says exactly how wide that is: 9 have a QC literal depending
on them and 4 do not --

    #0  ftesurf/cfg        the engine execs cfg/default.cfg itself (sv_main.c:6714);
                           no shipping cfg execs another (measured, 0 hits)
    #3  ftesurf/glsl       a shader names `prog milk_scene` and the engine resolves
                           it to glsl/milk_scene.glsl by convention; exactly ONE
                           glsl path is written literally anywhere
    #6  ftesurf/scripts    as #3 -- material names, not paths
    #10 ftesurf/gfx/env    `r_skybox milk` makes R_SetSky load gfx/env/milk.png
                           (gl_warp.c:133); the name is a skybox, never a path

Those four are engine-convention and no literal sweep of anything we author can
reach them.  A clean run therefore means "no literal asset path in src/ is missing
from the ship set", NOT "the archive is complete" -- which is still the whole of the
fault class that cost three reports and a re-cut release, since all three were
literal paths in QC.

MEASURED, on the tree as of this writing (801 shipped files, 143 asset literals:
56 shipped, 53 denied, 33 runtime, 1 pattern; 0 misses):

  * EVERY HISTORICAL FAULT IS CAUGHT.  Hiding a ship entry flips its literal to
    MISS for all five data files the menu reads -- data/mapdl.txt (the omission
    that forced the 0.1.15 re-cut), mapmeta.txt, mapdeps.txt, mapwr.txt and
    mapparticles.txt -- and `--mutate` over the 13 globs catches 9, including #11
    gfx/thumbnails (the error-texture fault) and #12 maps/zones/local (the 587-map
    zone-library fault).
  * ALL 20 DENY ENTRIES FIRE.  A deny rule that cannot fire claims to explain
    something nothing asks about, so the table is audited rather than assumed: two
    entries were removed for exactly that (`sound/milk/` and `music/`, both
    correctly RUNTIME through a probe and a search root).
  * csprogs.dat IS BLIND AND STAYS BLIND: no QC names its own file, the engine
    loads it.  Same class as the four globs above.

TWO DEFECTS THIS GATE HAD, both found by running its own falsifier rather than by
reading it, and both recorded here because each looked like a clean pass:
  1. A PREFIX deny key swallowed its own subtree.  `maps/` is a real search-root
     literal, and as a prefix it excused `maps/zones/local/` -- the zone library --
     with a search root's reason.  `--mutate 12` reported NOT CAUGHT for the largest
     of the three historical faults.  Hence DENY_EXACT vs DENY_PREFIX.
  2. `fopen` was treated as a probe.  It is a LOAD when the mode is FILE_READ, and
     excusing it hid data/mapdl.txt entirely -- the gate's own founding fault read
     as a pass.  The mode decides now, and this is the single most important line in
     the file: a silent-failure read is the worst thing to classify as optional.
"""
import argparse
import fnmatch
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASE = os.path.join(ROOT, "src", "release", "release.ps1")
SRCDIR = os.path.join(ROOT, "src")
GAMEDIR = os.path.join(ROOT, "ftesurf")

# Directories a QC path can start with and mean a file the engine will load.
# `hull/` is NOT here despite 31 hits: every one is prose in a sh_zones.qc test
# label ("hull/box: 15 units clear of +x -- hull").  The list was derived by
# tools/_survey_literals.py over all 11,842 literals in src/, not guessed.
ASSET_ROOTS = ("gfx/", "maps/", "models/", "sound/", "sprites/", "materials/",
               "particles/", "data/", "cfg/", "glsl/", "scripts/", "music/",
               "fonts/", "textures/")

# Builtins that ASK whether a path exists rather than load it.  A literal reached
# through one of these is not a demand on the ship set.
#
# `fopen` IS NOT IN THIS LIST AND MUST NOT BE ADDED BACK.  It was, and it hid the
# single most expensive fault this gate exists to catch: hiding data/mapdl.txt from
# the ship set -- the omission that forced the 0.1.15 re-cut -- produced NO miss,
# because ui_dl_load reaches it through fopen and every such literal was excused as
# "a probe".  `fopen(p, FILE_READ)` is a LOAD whose failure is silent (the feature
# reads nothing and draws no button, which is precisely how 0.1.14 presented), while
# `fopen(p, FILE_WRITE|FILE_APPEND)` is a runtime output that must never ship.  So
# the MODE decides, not the builtin -- see classify().
PROBES = {"ui_file_exists", "search_begin", "mapfilekb", "filelen",
          "search_getfilename", "search_getfilesize", "precache_pic2"}

# fopen modes that make the path an OUTPUT rather than a demand.
WRITE_MODES = ("FILE_WRITE", "FILE_APPEND")

# Literals that are a search pattern or a placeholder rather than a path.
PATTERNISH = re.compile(r"[*?<>]|\.\.\.|\s")

# Known-absent ON PURPOSE, in two tables because the difference is load-bearing.
# A PREFIX key was the first cut's defect: `maps/` and `sound/` are both real
# search-root literals, and as prefix keys they swallowed their own subtrees -- so
# `maps/zones/local/` (THE ZONE LIBRARY, the largest of the three historical faults)
# was excused with a search root's reason, and mutant #12 proved the gate could not
# see its own worst case.  Every entry needs a reason; --mutate is what keeps the
# table honest about the ones that stopped being reachable.

# The literal must EQUAL the key.
DENY_EXACT = {
    "maps/": "A search root, not a file (m_main.qc's map enumeration).",
    "sound/": "A search root, not a file (cl_banner.qc's Bn_SndPath).",
    "maps/surf_666.bsp": "Harness literal (cl_board.qc test path), not content.",
    "maps/surf_kitsune.bsp": "Harness literal (cl_hud.qc test path), not content.",
    "gfx/env/xray1.png": "The vessel's x-ray film. Absent on the BUILD BOX too, "
                         "and its only call site guards on ui_file_exists and "
                         "falls back to $blackimage (m_milk.qc).",
    "gfx/env/xray2.png": "As xray1.png.",
    "data/chatsilence.txt": "Written at runtime by the client (cl_chat.qc).",
    "data/consent.txt": "Written at runtime; in $DenyPatterns precisely so it can "
                        "never ship, because shipping it pre-accepts the terms.",
    "data/b316_buffered.txt": "Build-316 test scaffolding in m_main.qc.",
    "data/b316_stream.txt": "Build-316 test scaffolding in m_main.qc.",
}

# The literal must START WITH the key.  Covers a strcat prefix (`scripts/
# soundscapes_` + map + `.txt`) as well as a whole subtree.
DENY_PREFIX = {
    "gfx/mapshots/": "1.1 GB of generated map photography. Must never ship; "
                     "ui_bgprobe falls back to the mapthumb atlas.",
    "maps/zones/online": "Resolves into the Momentum install, not our tree "
                         "(tools/zoneinstall.py). Not ours to ship.",
    "maps/zones/dl": "cl_zonedl.qc's HTTP fetch sandbox. Written at runtime into "
                     "data/, and tried LAST of the three sources by design.",
    "sound/ftesurf/": "The mod's own banner sounds. cl_banner.qc's comment beside "
                      "the registercvar says it plainly: \"none ship yet; a "
                      "missing one is skipped silently\". ftesurf/sound/ does not "
                      "exist on the build box and is gitignored.",
    "sprites/": "Source-engine sprites. Come from the player's own Steam mount, "
                "never from our archive.",
    "materials/": "As sprites/ -- mounted Source content.",
    "scripts/soundscapes_": "Read from INSIDE the map's BSP or a mounted Source "
                            "VPK, not from our gamedir; a loose copy here would "
                            "only be an override (cl_soundscape.qc's own header: "
                            "935 uses from maps' packed scripts, 474 from the "
                            "HL2/CS:S packs). Normal absence, and it is reported "
                            "per-map rather than averaged away.",
    "data/runs/": "Player recordings. data/** is gitignored player data.",
    "data/probe/": "Test scaffolding in m_main.qc.",
    "data/online/": "Runtime board cache (cl_online.qc).",
}


# TWO ENTRIES THAT WERE HERE AND ARE NOT, because a rule that cannot fire should not
# claim to explain anything: `sound/milk/` (mkmusic.py's local effects, never
# shipped) and `music/` (the track picker's search root).  Both are classified
# RUNTIME first and more accurately -- `ui_file_exists("sound/milk/click.wav")` and
# `search_begin("music/")` are questions with documented graceful absence, not loads
# (AGENTS.md: "the menu plays effects only if click.wav exists").  If either call
# site ever becomes a load, the gate will then report a MISS, which is the correct
# answer to a newly real question.


def strip_comments(line):
    """Drop a PowerShell `#` comment, but not one inside a quoted string."""
    out = []
    q = None
    for ch in line:
        if q:
            out.append(ch)
            if ch == q:
                q = None
            continue
        if ch in "'\"":
            q = ch
            out.append(ch)
            continue
        if ch == "#":
            break
        out.append(ch)
    return "".join(out)


def ps_array(text, name):
    """The raw body of `$name = @( ... )`, comments stripped."""
    m = re.search(r"\$" + re.escape(name) + r"\s*=\s*@\(", text)
    if not m:
        raise SystemExit("release.ps1: cannot find $%s" % name)
    i = m.end()
    depth = 1
    body = []
    while i < len(text) and depth:
        ch = text[i]
        if ch in "(@":
            depth += 1 if ch == "(" else 0
        elif ch == ")":
            depth -= 1
            if not depth:
                break
        body.append(ch)
        i += 1
    return "\n".join(strip_comments(l) for l in "".join(body).splitlines())


def ps_strings(body):
    return re.findall(r"'([^']*)'", body)


def ps_globs(body):
    """@{ Path = '..'; Filter = '..'; Deny = @('..', '..') } -> dicts."""
    out = []
    for blk in re.findall(r"@\{(.*?)\}", body, re.S):
        d = {}
        for key in ("Path", "Filter"):
            m = re.search(key + r"\s*=\s*'([^']*)'", blk)
            if m:
                d[key.lower()] = m.group(1)
        m = re.search(r"Deny\s*=\s*@\(([^)]*)\)", blk)
        d["deny"] = ps_strings(m.group(1)) if m else []
        if "path" in d:
            out.append(d)
    return out


def win_filter(name, filt):
    """PowerShell's -Filter is a case-insensitive Win32 wildcard."""
    if not filt or filt == "*":
        return True
    return fnmatch.fnmatch(name.lower(), filt.lower())


def resolve_shipset(hidden=None):
    """(files, dirs) exactly as release.ps1 does: non-recursive, Filter, Deny.

    `hidden` is an index into the glob list, for --mutate.
    """
    text = open(RELEASE, encoding="utf-8-sig", errors="replace").read()
    files = set()
    # $ShipRootFiles are install-root names ('ftesurf64.exe'); $ShipGameFiles are
    # gamedir-relative with a 'ftesurf/' prefix ('ftesurf/data/mapdl.txt').  QC
    # literals are gamedir-relative, so the prefix comes off here or EVERY
    # ShipGameFiles comparison fails -- measured: 'data/mapmeta.txt' read as a miss
    # while 'ftesurf/data/mapmeta.txt' sat in the set beside it.
    for arr in ("ShipRootFiles", "ShipGameFiles"):
        for f in ps_strings(ps_array(text, arr)):
            f = f.replace("\\", "/")
            files.add(f.lower())
            if f.startswith("ftesurf/"):
                files.add(f[len("ftesurf/"):].lower())
    dirs = set()
    for n, g in enumerate(ps_globs(ps_array(text, "ShipGlobs"))):
        if hidden is not None and n == hidden:
            continue
        rel = g["path"].replace("\\", "/").rstrip("/")
        # release.ps1 strips no prefix: its Paths are 'ftesurf/...'.  The QC
        # literals are gamedir-relative, so judge both spellings.
        d = os.path.join(ROOT, *rel.split("/"))
        if not os.path.isdir(d):
            raise SystemExit("ship set names a directory that does not exist: %s" % rel)
        short = rel.split("/", 1)[1] if rel.startswith("ftesurf/") else rel
        dirs.add(short.lower())
        for entry in sorted(os.listdir(d)):
            p = os.path.join(d, entry)
            if not os.path.isfile(p) or not win_filter(entry, g.get("filter", "*")):
                continue
            if any(fnmatch.fnmatch(entry.lower(), dn.lower()) for dn in g["deny"]):
                continue
            files.add((short + "/" + entry).lower())
    return files, dirs, ps_globs(ps_array(text, "ShipGlobs"))


def qc_literals(path):
    """(line, literal, prefix, suffix) for every double-quoted string.  A linear
    scan, NOT a regex: `(?:[^"\\\\]|\\\\.)*` backtracks catastrophically over 6.4 MB
    of QC.  `suffix` is the source after the literal, which is where an fopen's mode
    argument lives."""
    text = open(path, encoding="utf-8", errors="replace").read()
    bs = chr(92)
    out = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == '"':
            j = i + 1
            buf = []
            while j < n:
                c = text[j]
                if c == bs and j + 1 < n:
                    buf.append(c + text[j + 1])
                    j += 2
                    continue
                if c == '"' or c == "\n":
                    break
                buf.append(c)
                j += 1
            if j < n and text[j] == '"':
                out.append((text.count("\n", 0, i) + 1, "".join(buf),
                            text[:i], text[j + 1:j + 64]))
                i = j + 1
                continue
            i = j
            continue
        i += 1
    return out


# `%` is a path character here because a built path IS the thing being judged:
# `data/parts/p%s-%g.rec` cut at the `%` reported the fragment `data/parts/p` as a
# miss, which is a defect in the cutter wearing a finding's clothes.
PATHCH = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_./-%")
TRIM = ".,;:!?"


def candidates(lit):
    """Every asset path inside a literal, not just one that starts it.

    `startswith(ASSET_ROOTS)` was the first cut and it is blind to a path embedded
    in a longer string -- which is how the mod execs its particle config:
    localcmd("exec particles/ftesurf.cfg\n") in cl_emit.qc, a REAL shipping file
    that runs on every map load and that release.ps1's own deny-tripwire comment
    warns an unanchored rule would kill.  Mutant #5 (ftesurf/particles) reported
    NOT CAUGHT for exactly that reason.

    BUT A ROOT MUST START AT A PATH BOUNDARY.  The unbounded version found
    `maps/render_default.cfg` INSIDE `cfg/maps/render_default.cfg` and reported the
    per-map render layer missing when it ships fine under glob #1 -- a false
    positive invented by substring matching, and the kind that gets a gate turned
    off.  So an occurrence counts only at offset 0 or after a character that cannot
    be part of a path, and the token is cut at the first character that cannot be
    either (which is also what strips the full stop off a path quoted at the end of
    a prose sentence).
    """
    out = []
    for r in ASSET_ROOTS:
        i = lit.find(r)
        while i >= 0:
            if i == 0 or lit[i - 1] not in PATHCH:
                j = i + len(r)
                while j < len(lit) and lit[j] in PATHCH:
                    j += 1
                tok = lit[i:j].rstrip(TRIM)
                if tok and tok not in out:
                    out.append(tok)
            i = lit.find(r, i + 1)
    return out


def enclosing_call(prefix):
    """The nearest `ident(` before this literal -- which decides load vs probe."""
    for m in reversed(list(re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(", prefix))):
        tail = prefix[m.end():]
        # only if nothing but arguments separates it from the literal
        if tail.count("(") == tail.count(")"):
            return m.group(1)
    return None


def classify(lit, call, files, dirs, suffix=""):
    """-> (verdict, detail).  verdict in SHIPPED/DENIED/RUNTIME/MISS/PATTERN."""
    s = lit.replace("\\", "/")
    if PATTERNISH.search(s):
        return "PATTERN", "a search pattern or placeholder, not a path"
    if call in PROBES:
        return "RUNTIME", "reached through %s(), an existence probe" % call
    if call == "fopen" and any(m in suffix for m in WRITE_MODES):
        return "RUNTIME", "fopen for writing -- a runtime output, never shipped"
    # fopen for READING falls through deliberately: it is a load whose absence is
    # silent, so it is a demand on the ship set like any other.
    for key, why in DENY_EXACT.items():
        if s == key:
            return "DENIED", why
    for key, why in DENY_PREFIX.items():
        if s.startswith(key):
            return "DENIED", why
    # a runtime WRITE path: data/ with a format spec or a trailing slash
    if s.startswith("data/") and ("%" in s or s.endswith("/")):
        return "RUNTIME", "a data/ sandbox path the mod writes at runtime"
    if "%" in s:
        d = os.path.dirname(s).lower()
        if d in dirs:
            return "SHIPPED", "built path; its directory %s is a ship glob" % d
        return "MISS", "built path; NO ship glob covers the directory %s" % d
    low = s.lower()
    if low in files:
        return "SHIPPED", "in the ship set"
    base = os.path.basename(low)
    if "." not in base:
        # Extensionless: the engine resolves it by trying extensions, and a
        # strcat-built name is a prefix of the real file.  Match as a prefix.
        hits = sorted(f for f in files if f.startswith(low))
        if hits:
            return "SHIPPED", ("extensionless; resolves to %s%s"
                               % (hits[0], " (+%d more)" % (len(hits) - 1)
                                  if len(hits) > 1 else ""))
    d = os.path.dirname(low)
    if d in dirs:
        return "MISS", ("directory %s ships, but its filter does not match %s"
                        % (d, os.path.basename(s)))
    return "MISS", "no ship entry covers %s" % (d or s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--mutate", type=int, default=None,
                    help="hide the Nth ship glob and assert a MISS appears")
    a = ap.parse_args()

    if a.mutate is not None:
        return mutate(a.mutate)

    files, dirs, globs = resolve_shipset()
    print("ship set: %d files over %d globbed directories" % (len(files), len(globs)))

    rows = []
    for path in sorted(glob.glob(os.path.join(SRCDIR, "**", "*.qc"), recursive=True)):
        for line, lit, prefix, suffix in qc_literals(path):
            for cand in candidates(lit):
                call = enclosing_call(prefix)
                v, why = classify(cand, call, files, dirs, suffix)
                rows.append((v, cand, call,
                             os.path.relpath(path, ROOT).replace(os.sep, "/"),
                             line, why))

    order = ("MISS", "SHIPPED", "DENIED", "RUNTIME", "PATTERN")
    tally = {k: sum(1 for r in rows if r[0] == k) for k in order}
    print("asset literals in src/: %d -- %s" % (len(rows), ", ".join(
        "%d %s" % (tally[k], k.lower()) for k in order if tally[k])))

    # Which ship globs does a QC literal actually depend on?  Cheap to answer here
    # and expensive to answer any other way (--mutate re-resolves per glob), and
    # without it "0 misses" does not say how much of the ship set was ever asked
    # about.  The four that read uncovered are engine-convention; see NOT COVERED.
    reached = set()
    for v, lit, call, f, line, why in rows:
        if v == "SHIPPED":
            m = re.search(r"resolves to (\S+)", why)
            reached.add(os.path.dirname((m.group(1) if m else lit).lower()))
    gdirs = [g["path"].split("ftesurf/", 1)[-1].lower() for g in globs]
    print("ship globs a QC literal depends on: %d of %d%s"
          % (len([d for d in gdirs if d in reached]), len(gdirs),
             "" if all(d in reached for d in gdirs) else
             "  (unreached: %s -- engine-convention, see NOT COVERED)"
             % ", ".join(d for d in gdirs if d not in reached)))
    print()
    for v, lit, call, f, line, why in rows:
        if v == "MISS":
            print("  MISS     %-40s %s:%d" % (lit, f, line))
            print("           %s" % why)
            if call:
                print("           reached through %s()" % call)
    if a.verbose:
        print()
        for v, lit, call, f, line, why in rows:
            if v != "MISS":
                print("  %-8s %-42s %-22s %s" % (v, lit, (call or "") + "()", why[:60]))
    print()
    if tally["MISS"]:
        print("FAILED: %d literal asset path(s) the archive would not contain." % tally["MISS"])
        print("Either add them to $ShipGlobs/$ShipGameFiles in src/release/release.ps1,")
        print("or give tools/shipguard.py a DENY entry WITH A STATED REASON.")
        return 1
    print("OK: every literal asset path in src/ is shipped, denied with a reason,")
    print("    a runtime path, or a search pattern.")
    return 0


def mutate(n):
    """The falsifier.  A gate nobody has watched fire is not a gate."""
    base, dirs, globs = resolve_shipset()
    if n >= len(globs):
        print("only %d ship globs; --mutate %d is out of range" % (len(globs), n))
        return 2
    g = globs[n]
    # dirs MUST be the mutant's own: passing the unmuted set is how the first cut
    # reported NOT CAUGHT for maps/zones/local, the mutant that mattered most.
    hid, hdirs, _ = resolve_shipset(hidden=n)
    print("mutant: hiding ship glob #%d  %s (filter %s)"
          % (n, g["path"], g.get("filter", "*")))
    print("        ship set %d -> %d files" % (len(base), len(hid)))
    if not (base - hid):
        print("NOT-REACHED: that glob contributes no file on this box, so hiding")
        print("it changes nothing and this mutant proves nothing. Pick another.")
        return 2
    found = []
    for path in sorted(glob.glob(os.path.join(SRCDIR, "**", "*.qc"), recursive=True)):
        for line, lit, prefix, suffix in qc_literals(path):
            for cand in candidates(lit):
                call = enclosing_call(prefix)
                for fset, dset, tag in ((base, dirs, "base"), (hid, hdirs, "mutant")):
                    v, why = classify(cand, call, fset, dset, suffix)
                    if tag == "mutant" and v == "MISS":
                        found.append((cand, line, why))
    if not found:
        print("NOT CAUGHT: hiding %s produced no MISS -- no QC literal depends on"
              % g["path"])
        print("it, so this mutant is uninformative rather than a gate failure.")
        return 2
    print("CAUGHT %d literal(s) that flipped to MISS:" % len(found))
    for lit, line, why in found[:6]:
        print("  %-40s line %d  %s" % (lit, line, why))
    return 0


if __name__ == "__main__":
    sys.exit(main())
