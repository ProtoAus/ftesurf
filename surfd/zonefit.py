#!/usr/bin/env python3
"""Can one map's zone file be used on another build of that map?

The watcher's copy of tools/census/zonefit.py's verdict; tools/ is not deployed
to the Pi.  That tool's docstring has the story and the finding that shaped the
rule (a moved entity is not a moved world).  test_zonefit.py runs both on the
same pairs and fails where they disagree.

A zone is an absolute world polygon and its restart point is usually a
targetname resolved in the BSP, so a donor's file means the same thing on the
target only if the two builds share a coordinate frame AND the target's entity
lump carries those names.  fit() -> (verdict, why):

  FIT         copy it
  SHIFTED     a start, end or stage region outside the target's world, or the
              two worlds' mins more than FRAME units apart
  NO-DESTS    a teleDestTargetname the target does not have
  EMPTY       the file names no region: nothing to copy
  OWN-TIMER   the target carries Momentum's own timer triggers in its BSP: it
              is timed already, and a file would be a second rule on top
  UNREADABLE  a file that is not a VBSP this can read, or zones that are not
              the shape Momentum publishes

Only FIT is a yes.  Everything read here is bounded: these are files a
stranger compiled.
"""
import functools
import json
import lzma
import os
import re
import struct

HDRSZ = 8 + 64 * 16 + 4
MAX_LUMP = 16 << 20         # the largest entity lump in the library is under 4 MB
MAX_DICT = 64 << 20         # an LZMA lump's dictionary: the decoder allocates it whole
FRAME = 64.0                # units the two worlds' mins may differ by
SLACK = 64.0                # units a region may sit outside the target's world
_TARGETNAME = re.compile(rb'"targetname"\s*"([^"]*)"', re.I)
_OWN_TIMER = re.compile(rb'"classname"\s*"trigger_momentum_timer_', re.I)


def _lump(fh, idx, strict=False):
    """One lump's bytes, LZMA undone, or None when it cannot be had whole.
    `strict` lets a MemoryError through: on the swapless Pi it is the moment's,
    not the file's (timer_read)."""
    fh.seek(0)
    hdr = fh.read(HDRSZ)
    if len(hdr) < HDRSZ or hdr[:4] != b"VBSP":
        return None
    off, size = struct.unpack("<ii", hdr[8 + idx * 16:8 + idx * 16 + 8])
    if size <= 0:
        return b""
    if off < 0 or size > MAX_LUMP:
        return None
    fh.seek(off)
    raw = fh.read(size)
    if len(raw) != size:
        return None
    if raw[:4] != b"LZMA":
        return raw
    if len(raw) < 17:
        return None
    actual, lsize = struct.unpack("<II", raw[4:12])
    if actual > MAX_LUMP:
        return None
    props = raw[12:17]
    if struct.unpack("<I", props[1:5])[0] > MAX_DICT:
        return None
    flt = [{"id": lzma.FILTER_LZMA1, "lc": props[0] % 9, "lp": (props[0] // 9) % 5,
            "pb": props[0] // 45, "dict_size": struct.unpack("<I", props[1:5])[0]}]
    try:
        dec = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=flt)
        return dec.decompress(raw[17:17 + lsize], max_length=actual)
    except MemoryError:
        if strict:
            raise
        return None
    except (lzma.LZMAError, ValueError):
        return None


def has_timer(path):
    """The legacy loader can time a BSP without JSON. Cache by file identity,
    not just name: mapwatch replaces builds atomically under the same name.
    """
    try:
        st = os.stat(path)
        return _has_timer(path, st.st_mtime_ns, st.st_ctime_ns, st.st_size)
    except OSError:
        return False


@functools.lru_cache(maxsize=8192)
def _has_timer(path, mtime, ctime, size):
    try:
        with open(path, "rb") as fh:
            ents, models = _lump(fh, 0), _lump(fh, 14)
    except OSError:
        return False
    return _timer_in(ents, models)


def timer_read(path):
    """has_timer's answer, or None when the file could not be read just now (an
    OSError, a MemoryError): an answer surfd may keep across restarts, and a
    failure it must not (Patch 829)."""
    try:
        with open(path, "rb") as fh:
            ents, models = _lump(fh, 0, True), _lump(fh, 14, True)
    except (OSError, MemoryError):
        return None
    return _timer_in(ents, models)


def _timer_in(ents, models):
    if ents is None or models is None or len(models) % 48:
        return False
    found = set()
    for entity in re.findall(rb'\{([^{}]*)\}', ents):
        pairs = dict(re.findall(rb'"([^"\r\n]+)"\s*"([^"\r\n]*)"', entity))
        cn = pairs.get(b"classname", b"")
        if cn not in (b"trigger_momentum_timer_start", b"trigger_momentum_timer_stop"):
            continue
        model = pairs.get(b"model", b"")
        if not re.fullmatch(rb"\*[1-9][0-9]{0,5}", model):
            continue
        idx = int(model[1:])
        if idx >= len(models) // 48:
            continue
        box = struct.unpack_from("<6f", models, idx * 48)
        if not all(v == v and abs(v) < 1e7 for v in box):
            continue
        if any(box[a] > box[a + 3] for a in range(3)):
            continue
        found.add(cn)
    return len(found) == 2


def world(path):
    """-> (worldspawn mins, maxs, {targetname}, has its own timer triggers) of
    a VBSP, or None."""
    try:
        with open(path, "rb") as fh:
            ents, models = _lump(fh, 0), _lump(fh, 14)
    except OSError:
        return None
    if ents is None or models is None or len(models) < 48:
        return None
    mins = struct.unpack("<3f", models[0:12])
    maxs = struct.unpack("<3f", models[12:24])
    if not all(v == v and abs(v) < 1e7 for v in mins + maxs):   # NaN, or no world at all
        return None
    names = {m.decode("latin1") for m in _TARGETNAME.findall(ents)} - {""}
    return mins, maxs, names, _OWN_TIMER.search(ents) is not None


def regions(z):
    """-> [(tag, region)] for every region of a zone file; raises on another shape."""
    out = []

    def seg(zones, who):
        for i, s in enumerate(zones.get("segments") or []):
            for j, cp in enumerate(s.get("checkpoints") or []):
                tag = "start" if (i == 0 and j == 0) else "stage" if j == 0 else "checkpoint"
                for r in cp.get("regions") or []:
                    out.append(("%s:%s" % (who, tag), r))
        for r in (zones.get("end") or {}).get("regions") or []:
            out.append(("%s:end" % who, r))

    tracks = z.get("tracks") or {}
    seg((tracks.get("main") or {}).get("zones") or {}, "main")
    for k, b in enumerate(tracks.get("bonuses") or []):
        seg(b.get("zones") or {}, "b%d" % (k + 1))
    return out


def _box(r):
    pts = r.get("points") or []
    if not pts:
        return None
    xs, ys = [float(p[0]) for p in pts], [float(p[1]) for p in pts]
    b = float(r.get("bottom", 0))
    return (min(xs), min(ys), b), (max(xs), max(ys), b + float(r.get("height", 0)))


def fit(zone_bytes, donor_bsp, target_bsp):
    """Whether `zone_bytes`, made for `donor_bsp`, mean the same on `target_bsp`."""
    try:
        z = json.loads(zone_bytes.decode("utf-8-sig"))
        regs = regions(z)
        boxes = [(tag, _box(r)) for tag, r in regs]
        want = {r.get("teleDestTargetname") for _t, r in regs} - {None, ""}
    except (ValueError, AttributeError, TypeError, IndexError, KeyError, RecursionError,
            OverflowError):         # float() of a 400-digit integer (the review ran it)
        return "UNREADABLE", "the zones are not the shape Momentum publishes"
    if not all(isinstance(n, str) for n in want):
        return "UNREADABLE", "a destination name that is not text"
    if not regs:
        return "EMPTY", "the file names no region"
    src, tgt = world(donor_bsp), world(target_bsp)
    if src is None or tgt is None:
        return "UNREADABLE", "%s is not a VBSP this reads" % ("the donor" if src is None
                                                             else "the target")
    if tgt[3]:
        return "OWN-TIMER", "the target has Momentum's timer triggers in its BSP"
    out = [tag for tag, box in boxes
           if box and tag.endswith(("start", "end", "stage"))
           and any(box[1][a] < tgt[0][a] - SLACK or box[0][a] > tgt[1][a] + SLACK
                   for a in range(3))]
    if out:
        return "SHIFTED", "%d start/end/stage region(s) outside the target's world" % len(out)
    shift = max(abs(src[0][a] - tgt[0][a]) for a in range(3))
    if shift > FRAME:
        return "SHIFTED", "world mins differ by up to %.0f units" % shift
    missing = sorted(want - tgt[2])
    if missing:
        return "NO-DESTS", "%d of %d teleDestTargetname absent from the target (%s)" % (
            len(missing), len(want), missing[0][:40])
    return "FIT", "%d regions, %d destinations all present" % (len(regs), len(want))
