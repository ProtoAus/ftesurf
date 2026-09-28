"""Convert Momentum Mod runs into .rec files this game can draw and watch.

  python tools/momimport.py --paths <wrlines_data/paths> --demos <dir> [...] \
                            --out <gamedir>/data/momentum [--go]

WHAT THIS READS, AND WHAT IT DELIBERATELY DOES NOT.  A Momentum .mtv is a
container around a Source entity-delta netstream, and that netstream has no
public spec -- wrlines does not decode it either, it scans for float32
coordinate triples and picks the longest physically-smooth chain with a dynamic
program.  So this reads `.wrpath`, the extractor's OUTPUT, which is a documented
fixed-layout file with a CRC32 over the whole thing.

That split also decides where each half runs.  The extractor's float arithmetic
is bit-pinned to CPython 3.13.9 -- math.dist and a Neumaier-compensated sum()
are load-bearing, and a last-digit disagreement does not nudge a coordinate, it
selects a DIFFERENT CHAIN through the demo.  This file does no such arithmetic:
it copies numbers and formats them.  So extraction stays on the machine where it
is proven and this runs anywhere, including the Pi's 3.11.

THE HONESTY RULE.  A .rec header states what the machine that ran the physics
loaded: mapcrc, zonecrc, zonerule, nonce, pmpin, seed.  That machine was Source,
so NONE of them can be honestly filled and all are OMITTED -- which the grammar
already defines as the answer for an unknown value (sv_timer.qc's header block).
The precedent is not invented here: cl_lobbytime.qc:652-681 writes a client-side
.rec and omits exactly this set, arguing that filling them from something other
than the fact would be "a second copy of a fact, derived from something that is
not the fact".  reccheck then reports the file as `zones not stated`, `nonce not
stated`, `ruleset unknown` in its own words, with nothing added here.

NO WARP RECORDS ARE WRITTEN, and that is a rule rather than an omission.  37% of
these paths teleport, and it is tempting to emit `warp` at each jump.  The
grammar forbids it in terms: "A record synthesised by watching for a
discontinuity would see the jump and still not know what caused it, which is the
entire question."  The reader's own kinematic snap test finds them from the
samples (`rec_wt_snkin`, cl_watch.qc:782) and reports them as `kin` rather than
`rec`, which is the truth about where the knowledge came from.

WHAT A MOMENTUM DEMO DOES NOT CONTAIN -- proven negatives, from a grep of the
whole reference for the field names, not from a failed search here:
  * view angles.  So pitch/yaw are DERIVED from the direction of travel, and no
    .view sidecar is ever written: that file is mouse evidence, and a derived
    angle filed there is a measurement that never happened.
  * buttons.  keys/fwd/side/up are 0.
  * ground contact.  `fl` is 0, so the plane must be 0 0 0 -- which is also what
    reccheck requires, since a plane without a contact bit is a "stray plane".
  * a per-tick velocity.  What the .wrpath carries is a central difference of
    positions, which is exact in the middle and wrong at a coverage gap: see
    --flag-only below.

VELOCITY IS IMPORTED UNTOUCHED, AND FLAGGED.  Measured over 2977 pairs, the
stored velocity's peak matches the demo's own maxHorizontalSpeed exactly at the
median -- but 7.6% exceed it by >5% and 44 by over 2x, because the point array's
index is a fiction wherever a tick went missing and a central difference across
a gap divides a longer distance by the same two ticks.  81% of those carry no
LOW_CONFIDENCE flag, because that flag measures coverage rather than velocity.
Nothing here rewrites a number: the ratio goes in the header as `momquality` so
a reader can show it, and the run is imported as it is.
"""
import argparse
import bisect
import io
import hashlib
import json
import math
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

REC_VER = 5      # 17-column samples, and the lowest version whose allowed-key
                 # set covers what can honestly be stated.  v4+ is also what
                 # cl_watch.qc:1237 needs for the strafe/board/segment panels.

HDR, PT, MK = 0x100, 28, 36
F_MARKERS, F_LOWCONF = 0x08, 0x40
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"

# wrlines truncates every 40-char hash into a 40-BYTE field that reserves a NUL,
# so what is stored is 39 characters.  Match as a prefix with a floor, never ==.
SHA_FLOOR = 20

# A run whose peak exceeds the demo's own ceiling by more than this is flagged.
# 1.05 and not 1.0: the oracle is compared against a chain the extractor already
# fitted to it, so the two agree to a rounding error by construction and a
# tighter bound would flag arithmetic rather than gaps.
VRATIO_FLAG = 1.05

SLUG_RE = re.compile(r"[^a-zA-Z0-9]+")

# A Momentum alias is free text and arrives as real Unicode -- the first
# whole-corpus run died on cp1252 after a single ASCII test file passed.  Files
# are written UTF-8, and the name itself is stripped of anything that could end
# a line or a token, because `owner` runs to end of line and a newline inside it
# would silently split the header.  64 matches surfd's MAX_FIELD_LEN.
NAME_MAX = 64


def clean_name(s):
    s = "".join(" " if ord(c) < 0x20 or ord(c) == 0x7F else c for c in (s or ""))
    return s.strip()[:NAME_MAX] or "?"


# --------------------------------------------------------------------------
# .wrpath

class WrPath(object):
    __slots__ = ("map", "player", "steamid64", "run_time", "tick_interval",
                 "date_ms", "gamemode", "track_type", "track_num", "flags",
                 "src_sha1", "start_index", "start_found", "points", "crc_ok")


def wr_parse(blob):
    if len(blob) < HDR + 4 or blob[:8] != b"WRPATH\0\0":
        raise ValueError("not a wrpath")
    ver, flags, npts, nmks = struct.unpack_from("<IIII", blob, 0x08)
    if ver != 1:
        raise ValueError("wrpath version %d" % ver)
    if len(blob) != HDR + npts * PT + nmks * MK + 4:
        raise ValueError("length does not fit %d points / %d markers" % (npts, nmks))
    if struct.unpack_from("<I", blob, len(blob) - 4)[0] != (
            __import__("zlib").crc32(blob[:-4]) & 0xFFFFFFFF):
        raise ValueError("crc32 mismatch")

    p = WrPath()
    p.flags = flags
    p.tick_interval, = struct.unpack_from("<f", blob, 0x18)
    # runTime is an f64 at 0x1C and OCCUPIES 0x1C..0x23.  wr_path.h:575 claims a
    # zero gap at 0x20..0x23; there is none, and a parser written from that
    # comment writes four zero bytes there and breaks every CRC.
    p.run_time, = struct.unpack_from("<d", blob, 0x1C)
    p.steamid64, = struct.unpack_from("<Q", blob, 0x24)
    p.date_ms, = struct.unpack_from("<q", blob, 0x2C)
    p.map = blob[0x34:0x74].split(b"\0")[0].decode("utf-8", "replace")
    p.src_sha1 = blob[0x9C:0xC4].split(b"\0")[0].decode("utf-8", "replace")
    p.player = blob[0xC4:0xE4].split(b"\0")[0].decode("utf-8", "replace")
    p.start_index, = struct.unpack_from("<I", blob, 0xE8)
    p.start_found = bool(struct.unpack_from("<I", blob, 0xEC)[0] & 1)
    p.gamemode, p.track_type, p.track_num = blob[0xF8], blob[0xF9], blob[0xFA]
    p.crc_ok = True
    p.points = [struct.unpack_from("<7f", blob, HDR + i * PT) for i in range(npts)]
    return p


# --------------------------------------------------------------------------
# the .mtv's own speed ceiling

def mtv_oracle(path):
    """trackStats.maxHorizontalSpeed -- the figure the extractor fitted to.

    The JSON blob is NOT at a fixed offset (0xC6 on v1, 0xC7 on v2, with no
    field saying which) and every '{' in the window must be tried: the padding
    around the player name is arbitrary bytes, and taking the first on faith is
    what produced `implausible JSON length 1076353433` upstream.  A candidate is
    accepted only if the u32 before it is a plausible length AND the bytes at
    that length are a codec magic.
    """
    try:
        with open(path, "rb") as fh:
            b = fh.read(0x4000)
    except OSError:
        return None
    if b[:4] != b"MMTV":
        return None
    for probe in range(0xB0, min(0x200, len(b))):
        if b[probe] != 0x7B:
            continue
        n = struct.unpack_from("<I", b, probe - 4)[0]
        if not n or n >= (1 << 20) or probe + n + 4 > len(b):
            continue
        if b[probe + n:probe + n + 4] not in (b"LZMA", ZSTD_MAGIC):
            continue
        try:
            j = json.loads(b[probe:probe + n].rstrip(b"\0").decode("utf-8", "replace"))
        except Exception:
            continue
        v = (j.get("trackStats") or {}).get("maxHorizontalSpeed")
        return v if isinstance(v, (int, float)) and v > 0 else None
    return None


# --------------------------------------------------------------------------
# naming

def leg_dir(track, leg):
    """FS_LegDir, sh_defs.qc:2212-2226 -- transcribed, not reinvented."""
    if track <= 0:
        return "main" if leg <= 0 else "stage_%d" % leg
    if leg <= 0:
        return "bonus_%d" % track
    return "bonus_%d_stage_%d" % (track, leg)


def track_leg(track_type, track_num):
    """Momentum's (trackType, trackNum) -> our (track, leg).

    trackNum is 1-based and is 1 on a main track, never 0.
    """
    if track_type == 0:
        return 0, 0                      # main
    if track_type == 1:
        return 0, int(track_num)         # stage N
    return int(track_num), 0             # bonus N


def who(player, steamid64):
    """FS_PlayerSeg: <nameslug<=12>-<sha256(id)[:8]>, the id alone if no slug."""
    slug = SLUG_RE.sub("", player or "").lower()[:12]
    dig = hashlib.sha256(str(steamid64).encode("utf-8")).hexdigest()[:8]
    return ("%s-%s" % (slug, dig)) if slug else dig


def angles_from_velocity(vx, vy, vz):
    """A camera has to point somewhere; travel direction is the honest source."""
    h = math.hypot(vx, vy)
    if h < 1.0:
        return 0.0, 0.0
    return (max(-89.0, min(89.0, -math.degrees(math.atan2(vz, h)))),
            math.degrees(math.atan2(vy, vx)))


# --------------------------------------------------------------------------
# conversion

def convert(w, oracle):
    """Return (text, info).  Writes no file."""
    if len(w.points) < 2:
        raise ValueError("fewer than 2 points")
    ti = w.tick_interval if 0.001 <= w.tick_interval <= 0.1 else 0.015
    track, leg = track_leg(w.track_type, w.track_num)

    # The timer does not start at point 0: every .mtv holds a pre-roll, median
    # 2.07 s and up to 4.11 s.  startIndex is honoured only when the extractor
    # actually found the start; otherwise the whole path is pre-start padding,
    # which is what a negative t means to every reader.
    s0 = w.start_index if (w.start_found and 0 < w.start_index < len(w.points)) else 0
    t0 = w.points[s0][6]

    peak = 0.0
    for q in w.points:
        h = math.hypot(q[3], q[4])
        if h > peak:
            peak = h
    ratio = (peak / oracle) if oracle else 0.0

    out = []
    a = out.append
    a("FTESURF-REC %d" % REC_VER)
    a("map %s" % w.map)
    a("track %d" % track)
    a("startseg %d" % leg)
    a("leg %d" % leg)
    a("tickrate %.6g" % ti)
    a("movetickrate %.6g" % ti)
    a("clock sampled")
    a("owner %s" % clean_name(w.player))
    a("runid mom-%s" % (w.src_sha1[:24] or "unknown"))
    # Provenance and quality.  An unknown header key is SKIPPED by every reader
    # and is a note (not a fault) in reccheck.py:624, so these cost nothing to
    # a reader that does not know them and are the hook for the ones that do.
    a("foreign momentum %s %d %d %d %d" % (w.src_sha1, w.gamemode,
                                           w.track_type, w.track_num, w.steamid64))
    a("momquality %.4f %.1f %d" % (ratio, oracle or 0.0,
                                   1 if (w.flags & F_LOWCONF) else 0))
    a("flags 0")
    a("begin")

    for q in w.points:
        x, y, z, vx, vy, vz, t = q
        pitch, yaw = angles_from_velocity(vx, vy, vz)
        # 17 columns: t o[3] v[3] pitch yaw fl keys fwd side up n[3].
        # No exponent form anywhere in the body -- reccheck faults on it.
        a("%.4f %.2f %.2f %.2f %.2f %.2f %.2f %.1f %.1f 0 0 0 0 0 0 0 0"
          % (t - t0, x, y, z, vx, vy, vz, pitch, yaw))

    ticks = int(round(w.run_time / ti)) if w.run_time > 0 else len(w.points)
    a("end %d %d %d 0" % (ticks, len(w.points), s0))
    return "\n".join(out) + "\n", {
        "map": w.map, "track": track, "leg": leg, "ticks": ticks,
        "samples": len(w.points), "padding": s0, "ratio": ratio,
        "oracle": oracle or 0.0, "lowconf": bool(w.flags & F_LOWCONF),
        "player": clean_name(w.player), "steamid64": w.steamid64, "sha": w.src_sha1,
        "seconds": w.run_time, "tick": ti, "date_ms": w.date_ms,
    }


# --------------------------------------------------------------------------

def index_demos(dirs):
    """stem -> path, for prefix-matching a 39-char srcSha1 back to its .mtv."""
    stems = {}
    for d in dirs:
        for dp, _, fns in os.walk(d):
            for f in fns:
                if f.endswith(".mtv"):
                    stems.setdefault(os.path.splitext(f)[0], os.path.join(dp, f))
    return stems


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--paths", required=True, help="wrlines_data/paths root")
    ap.add_argument("--demos", action="append", default=[],
                    help="a .mtv root (repeatable); used only for the speed oracle")
    ap.add_argument("--out", required=True, help="destination data/momentum root")
    ap.add_argument("--map", action="append", default=[], help="limit to these maps")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--go", action="store_true", help="actually write files")
    args = ap.parse_args()

    stems = index_demos(args.demos)
    keys = sorted(stems)

    srcs = []
    for dp, _, fns in os.walk(args.paths):
        for f in fns:
            if f.endswith(".wrpath"):
                srcs.append(os.path.join(dp, f))
    srcs.sort()
    if args.map:
        want = {m.lower() for m in args.map}
        srcs = [p for p in srcs if os.path.basename(os.path.dirname(p)).lower() in want]
    if args.limit:
        srcs = srcs[:args.limit]

    rows, bad, noor, flagged = [], [], 0, 0
    for p in srcs:
        try:
            w = wr_parse(open(p, "rb").read())
        except Exception as e:
            bad.append((p, str(e)))
            continue
        oracle = None
        if len(w.src_sha1) >= SHA_FLOOR:
            i = bisect.bisect_left(keys, w.src_sha1)
            if i < len(keys) and keys[i].startswith(w.src_sha1):
                oracle = mtv_oracle(stems[keys[i]])
        if oracle is None:
            noor += 1
        try:
            text, info = convert(w, oracle)
        except Exception as e:
            bad.append((p, str(e)))
            continue
        if info["ratio"] > VRATIO_FLAG:
            flagged += 1

        d = os.path.join(args.out, info["map"], leg_dir(info["track"], info["leg"]))
        leaf = "%07d_%s_run.rec" % (info["ticks"], who(w.player, w.steamid64))
        rows.append((os.path.join(d, leaf), info, text, p))

    # DEDUPE, deliberately rather than by last-writer-wins.  The destination leaf
    # IS the run's identity -- same map, leg, player and tick count -- so two
    # sources landing on one leaf are two copies of one run, which is exactly
    # what this library holds: the game's own recording of a run
    # (`104455274-surf_4am-...`) and the same run downloaded from the
    # leaderboard under its hash.  Measured on the first whole-corpus write: 39
    # of 3000, and they overwrote each other without a word.
    #
    # The leaderboard copy wins, because it is the one the board's replayHash
    # names and so the one anybody else can obtain.  Ties break on the longer
    # point stream and then on the source path, so a re-run picks the same file.
    def rank(row):
        _, info, _, src = row
        stem = os.path.splitext(os.path.basename(src))[0]
        canonical = 1 if re.fullmatch(r"[0-9a-fA-F]{39,40}", stem) else 0
        return (-canonical, -info["samples"], src)

    byleaf = {}
    for row in rows:
        byleaf.setdefault(row[0], []).append(row)
    deduped, dropped = [], 0
    for dst, group in byleaf.items():
        group.sort(key=rank)
        deduped.append(group[0])
        dropped += len(group) - 1
    deduped.sort(key=lambda r: r[0])

    written = []
    for dst, info, text, _src in deduped:
        if args.go:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with io.open(dst, "w", newline="\n", encoding="utf-8") as fh:
                fh.write(text)
        written.append((dst, info))
    rows = written

    print("wrpath found    %d" % len(srcs))
    print("converted       %d" % len(rows))
    print("deduped away    %d  (same run held twice: the game's own copy and the leaderboard download)" % dropped)
    print("unreadable      %d" % len(bad))
    print("no speed oracle %d  (imported, momquality ratio 0)" % noor)
    print("flagged >%.2fx   %d  (imported untouched)" % (VRATIO_FLAG, flagged))
    for p, e in bad[:8]:
        print("   ! %-50s %s" % (os.path.basename(p)[:50], e))

    if args.go:
        man = os.path.join(args.out, "manifest.tsv")
        os.makedirs(args.out, exist_ok=True)
        with open(man, "w", newline="\n", encoding="utf-8") as fh:
            fh.write("# map\ttrack\tleg\tticks\tseconds\tsamples\tratio\toracle\t"
                     "lowconf\tsteamid64\tplayer\tsha\tleaf\n")
            for dst, i in rows:
                fh.write("%s\t%d\t%d\t%d\t%.3f\t%d\t%.4f\t%.1f\t%d\t%d\t%s\t%s\t%s\n"
                         % (i["map"], i["track"], i["leg"], i["ticks"], i["seconds"],
                            i["samples"], i["ratio"], i["oracle"], int(i["lowconf"]),
                            i["steamid64"], i["player"].replace("\t", " "),
                            i["sha"], os.path.basename(dst)))
        print("wrote %d file(s) under %s" % (len(rows), args.out))
        print("manifest: %s" % man)
    else:
        print("\nDRY RUN -- nothing written.  Pass --go.")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
