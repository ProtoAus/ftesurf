#!/usr/bin/env python3
"""qcframes.py -- fail a QC build where a file-scope global sits inside a function's frame (Patch 1617).

    python3 tools/qcframes.py ftesurf/qwprogs.dat [ftesurf/csprogs.dat ...] [--src src]

WHY.  The VM saves a function's frame -- globals[parm_start .. parm_start+locals) -- when the function is entered
and puts it back when it returns (qclib PR_EnterFunction / PR_LeaveFunction).  fteqcc writes that range from the
offset of the function's first local and the total size of its locals (qccmain.c, the funcs[i].parm_start loop),
and in the full FTESurf build a function whose only locals were compiler temporaries got a frame that began at
the globals declared just above it.  P1617's first build declared a cache flag there: set to 1 inside
FS_StreamFiles, back to 0 the moment it returned (watchpoint_ssqc fs_streamfiles_asked: "changed from 1065353216
to 0" in Archive_StreamFrame), with 0 warnings.  Nothing in the language says a global can do that, and nothing
at compile time said so -- this does.  The live 19 Nov builds (qwprogs 14f1aa82, csprogs 9f0ea093) have none.

WHAT COUNTS AS A GLOBAL.  The .dat names locals and globals alike.  A def is a file-scope global when its name is
declared at column 0 of a .qc under --src (float/string/vector/entity/int/__int64/bool, plain or `noref`/`nosave`/
`var`) and the .dat holds exactly one def of that name.  A name that is both a global and somebody's local is
counted as ambiguous and printed, not failed: the .dat cannot say which of the two defs is the global.

Exit 0 clean, 1 if any global is inside a frame, 2 if a file cannot be read as progs.
"""
import collections
import glob
import os
import re
import struct
import sys

PROG_SECONDARYVERSION32 = (ord("1") | ord("F") << 8 | ord("T") << 16 | ord("E") << 24) ^ \
                          (ord("3") | ord("2") << 8 | ord("B") << 16 | ord(" ") << 24)
TYPE_FUNCTION = 6
DEF_SAVEGLOBAL = 1 << 15
FUNC_SIZE = 36                  # dfunction_t: 7 ints + 8 parm sizes

GLOBAL_DECL = re.compile(r"^(?:(?:noref|nosave|var|shared)\s+)*"
                         r"(?:float|string|vector|entity|int|integer|__int64|bool)\s*\**\s+"
                         r"([^(=;{]+?)\s*(?:=[^;]*)?;")


class ProgsError(Exception):
    pass


def read_progs(data):
    """(defs, functions): defs = [(type, ofs, name)], functions = [(name, first_statement, parm_start, locals)]."""
    if len(data) < 60:
        raise ProgsError("too short for a progs header")
    head = struct.unpack_from("<15i", data, 0)
    version = head[0]
    ofs_gd, n_gd, ofs_fn, n_fn, ofs_str, n_str = head[4], head[5], head[8], head[9], head[10], head[11]
    wide = False
    if version == 7:
        if len(data) < 23 * 4:
            raise ProgsError("version 7 header truncated")
        ext = struct.unpack_from("<8i", data, 15 * 4)
        if ext[6]:
            raise ProgsError("compressed blocks (blockscompressed %#x) are not read" % ext[6])
        wide = (ext[7] & 0xffffffff) == PROG_SECONDARYVERSION32
    elif version != 6:
        raise ProgsError("progs version %d" % version)
    size = 12 if wide else 8
    if ofs_gd + n_gd * size > len(data) or ofs_fn + n_fn * FUNC_SIZE > len(data) or ofs_str + n_str > len(data):
        raise ProgsError("a table runs past the end of the file")
    strings = data[ofs_str:ofs_str + n_str]

    def name(i):
        if i < 0 or i >= len(strings):
            return "?"
        end = strings.find(b"\0", i)
        return strings[i:end if end >= 0 else len(strings)].decode("latin-1")

    fmt = "<IIi" if wide else "<HHi"
    defs = []
    for k in range(n_gd):
        t, o, n = struct.unpack_from(fmt, data, ofs_gd + size * k)
        defs.append((t & ~DEF_SAVEGLOBAL & 0xffff, o, name(n)))
    funcs = []
    for k in range(n_fn):
        first, parm_start, locs, _prof, s_name, _s_file, _nparms = struct.unpack_from("<7i", data, ofs_fn + FUNC_SIZE * k)
        funcs.append((name(s_name), first, parm_start, locs))
    return defs, funcs


def source_globals(src):
    names = set()
    for path in glob.glob(os.path.join(src, "**", "*.qc"), recursive=True):
        with open(path, encoding="latin-1") as fh:
            for line in fh:
                m = GLOBAL_DECL.match(line)
                if not m:
                    continue
                for part in m.group(1).split(","):
                    nm = part.split("[")[0].strip().lstrip("*").strip()
                    if re.fullmatch(r"[A-Za-z_]\w*", nm):
                        names.add(nm)
    return names


def inside_frames(defs, funcs, globals_):
    """(hits, ambiguous): hits = [(function, ofs, global)] for a unique-named source global inside a frame."""
    count = collections.Counter(n for _, _, n in defs)
    byofs = collections.defaultdict(list)
    for t, o, n in defs:
        if t != TYPE_FUNCTION and n in globals_:
            byofs[o].append(n)
    hits, ambiguous = [], []
    for fname, first, parm_start, locs in funcs:
        if first <= 0 or locs <= 0:         # builtins and empty functions have no frame
            continue
        for o in range(parm_start, parm_start + locs):
            for n in byofs.get(o, ()):
                (hits if count[n] == 1 else ambiguous).append((fname, o, n))
    return hits, ambiguous


def main(argv):
    src = "src"
    files = []
    it = iter(argv)
    for a in it:
        if a == "--src":
            src = next(it, src)
        else:
            files.append(a)
    if not files:
        print(__doc__.split("\n\n")[0])
        return 2
    globals_ = source_globals(src)
    if not globals_:
        print("qcframes: no file-scope globals found under %s" % src)
        return 2
    worst = 0
    for path in files:
        try:
            with open(path, "rb") as fh:
                defs, funcs = read_progs(fh.read())
        except (OSError, ProgsError) as e:
            print("qcframes: %s: %s" % (path, e))
            worst = 2
            continue
        hits, ambiguous = inside_frames(defs, funcs, globals_)
        print("qcframes: %s: %d functions, %d globals inside a frame, %d ambiguous"
              % (path, len(funcs), len(hits), len(ambiguous)))
        for fname, o, n in hits:
            print("  FRAME  %s holds global %s (@%d): it is put back on every return from %s" % (fname, n, o, fname))
        for fname, o, n in ambiguous[:20]:
            print("  note   %s's frame holds @%d, and %s is both a global and a local name" % (fname, o, n))
        if hits:
            worst = max(worst, 1)
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
