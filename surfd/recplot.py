"""
recplot.py -- a .rec file as plot data for the owner's run page (Patch 359).

    parse(path, max_bytes=8 MiB, max_points=1500) -> dict
    track(path, head_keys, ...) -> dict    the 3D viewer's filtered copy (Patch 825)

Stdlib only, never raises, bounded: max_bytes is an exact nonnegative integer.
At most max_bytes are acquired; reaching the allowance conservatively reports
truncation without an EOF probe, and an incomplete line at that boundary is
not interpreted. A body line
over 4096 bytes is skipped (a header line keeps its first 4096), and the path
keeps at most 2*max_points samples; stats cover every sample.  Layouts
follow the FTESURF-REC grammar block over SV_RecOpen (src/server/sv_timer.qc);
a record this file does not know is counted, never an error.
"""

import bisect
import math
import re

MAX_BYTES = 8 << 20
MAX_POINTS = 1500
LINE_MAX = 4096
HEAD_LINES = 200
VALUE_MAX = 256
PMPIN_MAX = 2048
MAX_MARKS = 2000
MAX_SPLITS = 512
MAX_KINDS = 32
MAX_UNKNOWN_NAMES = 16
VALUE_LIMIT = 1e9       # |t|, origin or velocity beyond this is malformed; keeps sums finite

HEAD_KEYS = frozenset((
    "map track leg startseg tickrate movetickrate clock owner runid mapcrc "
    "zonesrc zonecrc zonerule instart startjit flags pmpin "
    # Patch 416: the run nonce.  Listed so it does not show on the owner's run
    # page as an unknown key -- it is a normal header key, not a finding.
    "nonce "
    # The Momentum demo an import was rewritten from (tools/momreimport.py), a
    # 40-hex SHA1.  Listed because a key absent here is dropped SILENTLY -- no
    # note, no unknown counter, which counts body records only -- so surfd's
    # WEB_HEAD_KEYS selecting it would find nothing and the run page could not
    # tell a demo-sourced import from one derived from positions.  Safe to
    # publish: it names a public demo, and surfd's own allowlist is still what
    # decides what leaves the process.
    "momdemo").split())
TICK_RECS = frozenset(("cp", "stage", "stagestart", "restart", "resume", "ghost"))  # <n> <ticks>
COUNTED = ("in", "pe", "pm", "seed", "zseed", "board", "inend", "ride", "portal",
           "spec")     # spec: windows, parsed before the counted fallback

_VERSION = re.compile(r"FTESURF-REC\s+(\d{1,4})$")
_NUMBER = re.compile(r"[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$")
_CTRL = re.compile(r"[\x00-\x1f\x7f]")
_WORD = re.compile(r"[^A-Za-z0-9_]")


def parse(path, max_bytes=MAX_BYTES, max_points=MAX_POINTS):
    try:
        if type(max_bytes) is not int or max_bytes < 0:
            raise ValueError("max_bytes must be a nonnegative integer")
        max_points = max(2, int(max_points))
        with open(path, "rb") as fh:
            return _parse(fh, max_bytes, max_points)
    except OSError as e:
        return {"ok": False, "error": "cannot read: %s" % (e.strerror or type(e).__name__)}
    except Exception as e:  # noqa: BLE001 -- the page shows the error instead
        return {"ok": False, "error": "parse failed: %s" % type(e).__name__}


def _num(s):
    try:
        f = float(s)
    except (ValueError, OverflowError):
        return None
    return f if math.isfinite(f) else None


def _vec(toks):
    v = [_num(x) for x in toks]
    return None if None in v or any(abs(x) > VALUE_LIMIT for x in v) else v


def _int(s):
    f = _num(s)
    if f is None or f != int(f) or abs(f) > 2 ** 53:
        return None
    return int(f)


def _is_sample(tok):
    # reccheck.is_sample: records start with a word; padding samples with '-'.
    return tok[:1].isdigit() or (tok[:1] == "-" and tok[1:2].isdigit())


def _clean(s, cap):
    return _CTRL.sub(" ", s)[:cap].strip()


def _lines(fh, max_bytes, st):
    """Yield (text, overlong).  An overlong line yields its first 4096 bytes."""
    used = 0
    while used < max_bytes:
        chunk = fh.readline(min(LINE_MAX, max_bytes - used))
        if not chunk:
            return
        used += len(chunk)
        if used == max_bytes and not chunk.endswith(b"\n"):
            st["truncated"] = True
            return  # never interpret a budget-cut line as a complete record
        overlong = len(chunk) == LINE_MAX and not chunk.endswith(b"\n")
        while overlong:
            if used == max_bytes:
                st["truncated"] = True
                return
            more = fh.readline(min(LINE_MAX, max_bytes - used))
            used += len(more)
            if used == max_bytes and not more.endswith(b"\n"):
                st["truncated"] = True
                return
            if not more or more.endswith(b"\n"):
                break
        yield chunk.decode("utf-8", "replace").strip(), overlong
    st["truncated"] = True  # no acquisition beyond the allowance to probe EOF


def _rate(head):
    """Seconds per tick.  The file writes seconds; runs.tickrate is Hz, so >1 is Hz."""
    for key in ("movetickrate", "tickrate"):
        v = head.get(key, "").split()
        r = _num(v[0]) if v else None
        if r is not None and r > 0:
            return 1.0 / r if r > 1 else r
    return None


def _parse(fh, max_bytes, max_points):
    st = {"truncated": False}
    notes = []
    it = _lines(fh, max_bytes, st)

    first = next(it, None)
    m = _VERSION.match(first[0].lstrip("\ufeff")) if first else None
    if not m:
        return {"ok": False, "error": "not an FTESURF-REC file"}
    ver = int(m.group(1))

    # ---- header: allowlisted keys, until `begin` --------------------------
    head = {}
    pending = None      # the first sample, when `begin` is missing
    began = False
    for _ in range(HEAD_LINES):
        ln = next(it, None)
        if ln is None:
            break
        text = ln[0]
        if text == "begin":
            began = True
            break
        if _is_sample(text):
            pending = ln
            notes.append("no 'begin' before the first sample")
            break
        kv = text.split(None, 1)
        if kv and kv[0] in HEAD_KEYS:
            head[kv[0]] = _clean(kv[1] if len(kv) > 1 else "",
                                 PMPIN_MAX if kv[0] == "pmpin" else VALUE_MAX)
    else:
        return {"ok": False, "error": "no 'begin' in the first %d header lines" % HEAD_LINES}
    if not began and pending is None and not st["truncated"]:
        notes.append("no 'begin': header only")

    rate = _rate(head)
    start = None        # the run's start tick: instart's second number (the first on old files)
    toks = head.get("instart", "").split()
    if toks:
        start = _int(toks[1] if len(toks) > 1 else toks[0])

    # ---- body ---------------------------------------------------------------
    n = 0               # samples kept for stats (all of them)
    sample_lines = 0    # sample-shaped lines, for the trailer compare
    bad_samples = bad_recs = overlong = 0
    stride = 1
    buf = []            # (t, x, y, z, spd) at indices i % stride == 0
    last = None
    last_i = -1
    run_n = 0
    run_sum = all_sum = 0.0
    run_max = all_max = 0.0
    tmax = None

    marks = []
    marks_dropped = 0
    splits = []
    end = None
    counts = dict.fromkeys(COUNTED, 0)
    warp_lines = 0
    warp_kinds = {}
    unknown = 0
    unknown_names = {}
    in_row = -1         # position of the last `in` row, and its <mt>
    in_mt = None
    rebase = None       # resume/retry: SV_TimerResume sets starttick = movetick - ticks
    spec_open = None    # the open spectate window's `spec 1`: (t, x, y, wall)

    def mark(k, num, t, x=None, y=None, **extra):
        nonlocal marks_dropped
        if len(marks) >= MAX_MARKS:
            marks_dropped += 1
            return
        if t is not None and abs(t) > VALUE_LIMIT:
            t = None
        if x is None and last is not None and k != "split":
            x, y = last[1], last[2]      # file order: where the player was, at full rate
        m = {"k": k, "n": num, "t": t, "x": x, "y": y}
        m.update(extra)
        marks.append(m)

    def ticks_t(ticks):
        return ticks * rate if rate is not None and ticks is not None else None

    def body():
        if pending is not None:
            yield pending
        for ln in it:
            yield ln

    for text, long_line in (body() if (began or pending is not None) else ()):
        if not text:
            continue
        if long_line:
            overlong += 1
            continue
        toks = text.split()
        kw = toks[0]
        a = toks[1:]

        if _is_sample(kw):
            sample_lines += 1
            vals = _vec(toks[:7]) if len(toks) >= 7 else None
            if vals is None:
                bad_samples += 1
                continue
            t, ox, oy, oz, vx, vy, _ = vals
            spd = math.hypot(vx, vy)
            last = (t, ox, oy, oz, spd)
            last_i = n
            if n % stride == 0:
                buf.append(last)
                if len(buf) >= 2 * max_points:
                    buf = buf[::2]
                    stride *= 2
            n += 1
            all_sum += spd
            all_max = max(all_max, spd)
            if t >= 0:
                run_n += 1
                run_sum += spd
                run_max = max(run_max, spd)
            tmax = t if tmax is None else max(tmax, t)
            continue

        if kw in TICK_RECS:
            num = _int(a[0]) if len(a) >= 2 else None
            ticks = _num(a[1]) if len(a) >= 2 else None
            if num is None or ticks is None:
                bad_recs += 1
                continue
            if kw == "resume":
                rebase = _int(a[1])
            mark(kw, num, ticks_t(ticks))
        elif kw == "retry":
            ticks = _num(a[0]) if a else None
            if ticks is None:
                bad_recs += 1
                continue
            rebase = _int(a[0])
            mark(kw, None, ticks_t(ticks))
        elif kw == "split":
            seg = _int(a[0]) if len(a) >= 2 else None
            ticks = _int(a[1]) if len(a) >= 2 else None
            if seg is None or ticks is None:
                bad_recs += 1
                continue
            if len(splits) < MAX_SPLITS:
                splits.append([seg, ticks])
                if rate is not None:
                    mark("split", seg, ticks * rate)
        elif kw == "warp":
            # v7/8: pk mt kind o v; v9: pk mt row kind o v fl -- kind is the first word after mt
            warp_lines += 1
            j = next((j for j in range(2, len(a)) if not _NUMBER.match(a[j])), None)
            kind = (_WORD.sub("", a[j])[:24] or "?") if j is not None else "?"
            if kind not in warp_kinds and len(warp_kinds) >= MAX_KINDS:
                kind = "?"
            warp_kinds[kind] = warp_kinds.get(kind, 0) + 1
            vec = _vec(a[j + 1:j + 7]) if j is not None else None
            mt = _int(a[1]) if len(a) > 1 else None
            if vec is None or len(vec) != 6 or mt is None:
                bad_recs += 1
                continue
            t = (mt - start) * rate if start is not None and rate is not None else None
            mark("warp", None, t, vec[0], vec[1], kind=kind)
        elif kw == "portal":
            counts["portal"] += 1
            row = _int(a[1]) if len(a) >= 9 else None
            num = _int(a[2]) if len(a) >= 9 else None
            vec = _vec(a[3:9])
            if row is None or num is None or vec is None:
                bad_recs += 1
                continue
            t = None
            if row == in_row and in_mt is not None and start is not None and rate is not None:
                t = (in_mt - start) * rate
            mark("portal", num, t, vec[0], vec[1])
        elif kw == "spec":
            # Patch 382: spec <0|1> <ticks> <mt> <carry> <o3> <v3> <fl> <wall> [<why>].
            # The body is held and the clock stopped, so a window is one point
            # and one instant: one mark per window, carrying its wall length.
            num = _int(a[0]) if len(a) >= 12 else None
            ticks = _num(a[1]) if len(a) >= 12 else None
            vec = _vec(a[4:7]) if len(a) >= 12 else None
            wall = _num(a[11]) if len(a) >= 12 else None
            if num not in (0, 1) or ticks is None or vec is None or wall is None \
                    or abs(wall) > VALUE_LIMIT:
                bad_recs += 1
                continue
            if num == 1:
                spec_open = (ticks_t(ticks), vec[0], vec[1], wall)
                continue
            counts["spec"] += 1
            held = round(wall - spec_open[3], 3) if spec_open is not None else None
            why = (_WORD.sub("", a[12])[:24] or "?") if len(a) > 12 else "?"
            mark("spec", None, ticks_t(ticks), vec[0], vec[1], held=held, why=why)
            spec_open = None
        elif kw == "end":
            end = [_int(x) for x in a[:16]]
        elif kw in counts:
            counts[kw] += 1
            if kw == "in":
                in_row += 1
                in_mt = _int(a[1]) if len(a) > 1 else None
                if rebase is not None and in_mt is not None:
                    start = in_mt - rebase
                    rebase = None
        else:
            unknown += 1
            name = _WORD.sub("", kw)[:24] or "?"
            if name in unknown_names or len(unknown_names) < MAX_UNKNOWN_NAMES:
                unknown_names[name] = unknown_names.get(name, 0) + 1

    # A window still open at the end of what was read (a live part file).
    if spec_open is not None:
        counts["spec"] += 1
        mark("spec", None, spec_open[0], spec_open[1], spec_open[2], held=None, why="open")

    # The last sample is always on the path.
    if last is not None and last_i % stride != 0:
        buf.append(last)

    # Marks with no earlier sample (and splits, which follow `end`) take the
    # nearest kept sample by time.
    kept_t = [s[0] for s in buf]
    for mk in marks:
        if mk["x"] is None and mk["t"] is not None and buf:
            i = bisect.bisect_left(kept_t, mk["t"])
            if i >= len(buf) or (i > 0 and mk["t"] - kept_t[i - 1] <= kept_t[i] - mk["t"]):
                i -= 1
            i = max(0, min(i, len(buf) - 1))
            mk["x"], mk["y"] = buf[i][1], buf[i][2]
        for key in ("t", "x", "y"):
            if mk[key] is not None:
                mk[key] = round(mk[key], 3 if key == "t" else 1)

    # ---- notes --------------------------------------------------------------
    if st["truncated"]:
        notes.append("stopped at %d bytes: the rest of the file was not read" % max_bytes)
    elif began and end is None:
        notes.append("no 'end' trailer")
    if end is not None and not st["truncated"]:
        # end <ticks> <samples> <padding> <cps> [<inputs> v6] [<warps> v7] [<rides> v8]
        #     [<pms> <pes> <portals> v9]
        for idx, since, what, got in ((1, 0, "samples", sample_lines),
                                      (4, 6, "in", counts["in"]),
                                      (5, 7, "warp", warp_lines),
                                      (6, 8, "ride", counts["ride"]),
                                      (9, 9, "portal", counts["portal"])):
            if ver >= since and idx < len(end) and end[idx] is not None and end[idx] != got:
                notes.append("trailer says %d %s, the file has %d" % (end[idx], what, got))
    if bad_samples:
        notes.append("%d malformed or non-finite sample(s) dropped" % bad_samples)
    if bad_recs:
        notes.append("%d malformed record(s) skipped" % bad_recs)
    if overlong:
        notes.append("%d line(s) over %d bytes skipped" % (overlong, LINE_MAX))
    if unknown:
        notes.append("unknown records: " + ", ".join(
            "%s x%d" % kv for kv in sorted(unknown_names.items())))
    if marks_dropped:
        notes.append("%d marker(s) beyond %d not shown" % (marks_dropped, MAX_MARKS))
    if rate is None:
        notes.append("no usable tickrate: markers are not timed")

    counts["warp"] = warp_kinds
    counts["unknown"] = unknown
    avg = run_sum / run_n if run_n else (all_sum / n if n else 0.0)
    top = run_max if run_n else all_max
    return {
        "ok": True, "v": ver, "head": head, "rate": rate, "n": n, "stride": stride,
        "t": [round(s[0], 3) for s in buf],
        "x": [round(s[1], 1) for s in buf],
        "y": [round(s[2], 1) for s in buf],
        "z": [round(s[3], 1) for s in buf],
        "spd": [round(s[4], 1) for s in buf],
        "marks": marks, "splits": splits, "end": end, "counts": counts,
        "stats": {"max_speed": round(top, 1), "avg_speed": round(avg, 1),
                  "duration": round(max(tmax or 0.0, 0.0), 3)},
        "notes": notes, "truncated": st["truncated"],
    }


# ---- the 3D viewer's copy (Patch 825) ---------------------------------------
#
# track() is a recording as surfd/web/watch.html plays it: an FTESURF-REC file
# itself, so src/viewer/src/rec.ts reads it and a .rec from disk with one parser.
# What it keeps is an ALLOWLIST, like the run page's head:
#   header  the caller's head_keys (printable ASCII, VALUE_MAX), plus `eye <stand>
#           <duck>` from pmpin's two view heights; pmpin, mapcrc, zonecrc, zonerule,
#           nonce, instart and startjit stay in the file
#   samples the first 11 columns (t, origin, velocity, pitch, yaw, flags, keys),
#           re-formatted from parsed numbers; the moves and the ramp normal stay
#   records the timer's, `warp 0 0 <kind>` for warp and portal (the input-row
#           indices mean nothing without the `in` rows), ride's arm/disarm; never
#           in, pm, pe, mc, seed or zseed
# Bounded: two passes of _lines over at most max_bytes and TRACK_MAX_LINES lines,
# at most max_samples samples and max_records records. A sample is kept when it
# is every k-th (`thin <k>`), the one after a snap, or the last; k leaves room for
# the snaps the first pass counted, so a run with many teleports keeps its finish.
# Version on line 1, as parse() requires.

TRACK_MAX_BYTES = 32 << 20
TRACK_MAX_LINES = 1000000      # the largest local recording has 238,452
TRACK_MAX_SAMPLES = 60000
TRACK_MAX_RECORDS = 4000
_TRACK_TIMER = {"stage": 2, "stagestart": 2, "cp": 2, "restart": 2, "resume": 2,
                "ghost": 2, "split": 2, "retry": 1, "abandon": 1, "end": 1}
_KIND = re.compile(r"[a-z]{1,16}$")
_NOT_ASCII = re.compile(r"[^\x20-\x7e]")
_VIEWH = re.compile(r"(?:^| )viewheight=(\S{1,24})")
_DUCKH = re.compile(r" duckviewheight=(\S{1,24})")


def track(path, head_keys, max_bytes=TRACK_MAX_BYTES, max_samples=TRACK_MAX_SAMPLES,
          max_records=TRACK_MAX_RECORDS):
    try:
        if type(max_bytes) is not int or max_bytes < 0:
            raise ValueError("max_bytes must be a nonnegative integer")
        with open(path, "rb") as fh:
            st = {"truncated": False}
            total = snaps = 0
            for text, _ in _track_lines(fh, max_bytes, st):
                if _is_sample(text):
                    total += 1
                elif text.startswith(("warp ", "portal ")):
                    snaps += 1
            fh.seek(0)
            return _track(fh, frozenset(head_keys), max_bytes, max(2, int(max_samples)),
                          max(0, int(max_records)), total, snaps)
    except OSError as e:
        return {"ok": False, "error": "cannot read: %s" % (e.strerror or type(e).__name__)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "parse failed: %s" % type(e).__name__}


def _track_lines(fh, max_bytes, st):
    for i, ln in enumerate(_lines(fh, max_bytes, st)):
        if i >= TRACK_MAX_LINES:
            st["truncated"] = True
            return
        yield ln


def _track_sample(tok):
    if len(tok) < 11:
        return None
    v = _vec(tok[:9])
    fl, keys = _int(tok[9]), _int(tok[10])
    if v is None or fl is None or keys is None or not (0 <= fl < 1 << 16 and 0 <= keys < 1 << 16):
        return None
    return "%.4f %.2f %.2f %.2f %.2f %.2f %.2f %.1f %.1f %d %d" % (tuple(v) + (fl, keys))


def _track_record(tok):
    k = tok[0]
    if k in _TRACK_TIMER:
        f = [_int(t) for t in tok[1:1 + _TRACK_TIMER[k]]]
        if len(f) < _TRACK_TIMER[k] or None in f:
            return None
        return " ".join([k] + [str(x) for x in f])
    if k in ("warp", "portal"):
        # v9 warp: <pk> <mt> <row> <kind> ...; older: <pk> <mt> <kind> ...
        kind = "portal" if k == "portal" else (tok[3] if len(tok) > 3 else "")
        if k == "warp" and _num(kind) is not None and len(tok) > 4:
            kind = tok[4]
        return "warp 0 0 %s" % kind if _KIND.match(kind) else None
    if k == "ride" and len(tok) >= 7 and _KIND.match(tok[3]):
        b = _vec(tok[4:7])
        return None if b is None else "ride 0 0 %s %.3f %.3f %.3f" % (tok[3], b[0], b[1], b[2])
    return None


def _track(fh, head_keys, max_bytes, max_samples, max_records, total, snaps):
    st = {"truncated": False}
    it = _track_lines(fh, max_bytes, st)
    first = next(it, None)
    m = _VERSION.match(first[0].lstrip("﻿")) if first else None
    if not m:
        return {"ok": False, "error": "not an FTESURF-REC file"}

    head, seen, vh, dvh = [], set(), None, None
    for _ in range(HEAD_LINES):
        ln = next(it, None)
        if ln is None:
            return {"ok": False, "error": "no 'begin'"}
        text, overlong = ln
        if text == "begin":
            break
        key, _, val = text.partition(" ")
        if overlong or key in seen:
            continue
        seen.add(key)
        if key == "pmpin":
            a, b = _VIEWH.search(val), _DUCKH.search(" " + val)
            vh, dvh = (_num(a.group(1)) if a else None), (_num(b.group(1)) if b else None)
        elif key in head_keys:
            head.append("%s %s" % (key, _NOT_ASCII.sub("", val).strip()[:VALUE_MAX]))
    else:
        return {"ok": False, "error": "no 'begin'"}
    if vh is not None and dvh is not None and 0 < vh < 512 and 0 < dvh < 512:
        head.append("eye %g %g" % (vh, dvh))
    # Regular samples get what the snaps and the last sample leave, but never
    # less than half: past that a file is mostly teleports and the cap decides.
    thin = -(-total // max(max_samples // 2, max_samples - 1 - snaps))
    if thin > 1:
        head.append("thin %d" % thin)

    out, n, kept, records, splits, pending, capped = [], 0, 0, 0, 0, False, False
    for text, overlong in it:
        if overlong or not text:
            continue
        if _is_sample(text):
            keep = pending or n % thin == 0 or n == total - 1
            n += 1
            if not keep:
                continue
            if kept >= max_samples:
                capped = True
                continue
            line = _track_sample(text.split())
            if line is not None:
                out.append(line)
                kept += 1
                pending = False
            continue
        if records >= max_records:
            capped = True
            continue
        line = _track_record(text.split())
        if line is None or (line.startswith("split ") and splits >= MAX_SPLITS):
            continue
        splits += line.startswith("split ")
        out.append(line)
        records += 1
        pending = pending or line.startswith("warp ")

    text = "\n".join(["FTESURF-REC %d" % int(m.group(1))] + head + ["begin"] + out) + "\n"
    return {"ok": True, "rec": text, "samples": kept, "thin": thin,
            "truncated": st["truncated"], "capped": capped}
