"""
rectrack.py -- one recording as the board's 3D viewer plays it (Patch 825).

    track(path, head_keys, max_bytes=32 MiB, max_samples=120000) -> dict

The output is itself an FTESURF-REC file, so src/viewer/src/rec.ts reads it
and a .rec from disk with one parser. What it keeps is an ALLOWLIST, the same
discipline as the run page's (surfd.WEB_HEAD_KEYS, recplot.HEAD_KEYS):

  header  only `head_keys`, plus `eye <stand> <duck>` taken from pmpin's two
          view heights. pmpin itself, mapcrc, zonecrc, zonerule, nonce,
          instart and startjit stay in the file.
  samples the first 11 columns (t, origin, velocity, pitch, yaw, flags, keys),
          each re-formatted from a parsed number, so no text of the file's own
          is echoed. The move columns and the ramp normal stay in the file.
  records only those the viewer acts on, re-written from parsed fields: the
          timer's (stage, stagestart, cp, restart, retry, resume, ghost,
          abandon, end, split), warp and portal as snap points (`warp 0 0
          <kind>`: the input-row indices mean nothing without the `in` rows),
          and ride's arm/disarm with its base velocity. `in`, `pm`, `pe`, `mc`,
          seed and zseed never leave.

Bounded like recplot: at most max_bytes are read, and a file with more than
max_samples samples keeps every k-th one (`thin <k>` in the header) -- the
sample beside a snap record is always kept, so a teleport still snaps.
Stdlib only, never raises.
"""

import math
import re

MAX_BYTES = 32 << 20
MAX_SAMPLES = 120000
LINE_MAX = 4096
VALUE_MAX = 256
VALUE_LIMIT = 1e9

_VERSION = re.compile(r"FTESURF-REC\s+(\d{1,4})$")
_CTRL = re.compile(r"[\x00-\x1f\x7f]")
_KIND = re.compile(r"[a-z]{1,16}$")
_VIEWH = re.compile(r"(?:^| )viewheight=([-+0-9.eE]{1,24})(?: |$)")
_DUCKH = re.compile(r" duckviewheight=([-+0-9.eE]{1,24})(?: |$)")
# Timer records: name -> how many integer fields follow it.
_TIMER = {"stage": 2, "stagestart": 2, "cp": 2, "restart": 2, "resume": 2,
          "ghost": 2, "split": 2, "retry": 1, "abandon": 1, "end": 1}
_SNAP = ("warp", "portal")


def _num(s):
    try:
        x = float(s)
    except ValueError:
        return None
    if not math.isfinite(x) or abs(x) > VALUE_LIMIT:
        return None
    return x


def _int(s):
    x = _num(s)
    return None if x is None or x != int(x) else int(x)


def _sample(tok):
    if len(tok) < 11:
        return None
    v = [_num(t) for t in tok[:11]]
    if any(x is None for x in v):
        return None
    fl, keys = _int(tok[9]), _int(tok[10])
    if fl is None or keys is None or not (0 <= fl < 1 << 16) or not (0 <= keys < 1 << 16):
        return None
    return ("%.4f %.2f %.2f %.2f %.2f %.2f %.2f %.1f %.1f %d %d"
            % (v[0], v[1], v[2], v[3], v[4], v[5], v[6], v[7], v[8], fl, keys))


def _record(tok):
    k = tok[0]
    if k in _TIMER:
        n = _TIMER[k]
        f = [_int(t) for t in tok[1:1 + n]]
        if len(f) < n or any(x is None for x in f):
            return None
        return " ".join([k] + [str(x) for x in f])
    if k in _SNAP:
        # v9 warp: <pk> <mt> <row> <kind> ...; older: <pk> <mt> <kind> ...
        kind = tok[3] if len(tok) > 3 else ""
        if _num(kind) is not None and len(tok) > 4:
            kind = tok[4]
        if k == "portal":
            kind = "portal"
        return "warp 0 0 %s" % kind if _KIND.match(kind) else None
    if k == "ride" and len(tok) >= 7 and _KIND.match(tok[3]):
        b = [_num(t) for t in tok[4:7]]
        if any(x is None for x in b):
            return None
        return "ride 0 0 %s %.3f %.3f %.3f" % (tok[3], b[0], b[1], b[2])
    return None


def _is_sample(s):
    c = s[:1]
    return c == "-" or "0" <= c <= "9"


def track(path, head_keys, max_bytes=MAX_BYTES, max_samples=MAX_SAMPLES):
    try:
        return _track(path, frozenset(head_keys), max_bytes, max_samples)
    except (OSError, ValueError, MemoryError) as exc:
        return {"ok": False, "error": type(exc).__name__}


def _track(path, head_keys, max_bytes, max_samples):
    with open(path, "rb") as fh:
        data = fh.read(max_bytes + 1)
    truncated = len(data) > max_bytes
    data = data[:max_bytes]
    lines = data.decode("utf-8", "replace").split("\n")
    if truncated:
        lines.pop()                       # the cut line is not interpreted

    ver, head, eye, i = None, [], None, 0
    vh = dvh = None
    for i, raw in enumerate(lines):
        s = raw.rstrip("\r")[:LINE_MAX].strip()
        if s == "begin":
            break
        m = _VERSION.match(s)
        if m:
            ver = int(m.group(1))
            continue
        key, _, val = s.partition(" ")
        if key == "pmpin":
            a, b = _VIEWH.search(" " + val), _DUCKH.search(val)
            vh = _num(a.group(1)) if a else None
            dvh = _num(b.group(1)) if b else None
        elif key in head_keys:
            head.append("%s %s" % (key, _CTRL.sub("", val.strip())[:VALUE_MAX]))
    else:
        return {"ok": False, "error": "no begin"}
    if ver is None:
        return {"ok": False, "error": "not a recording"}
    if vh is not None and dvh is not None and 0 < vh < 512 and 0 < dvh < 512:
        eye = "eye %g %g" % (vh, dvh)

    body = lines[i + 1:]
    total = sum(1 for s in body if _is_sample(s))
    thin = max(1, math.ceil(total / max_samples)) if max_samples > 0 else 1

    out, n, kept, pending = [], 0, 0, False
    for raw in body:
        if len(raw) > LINE_MAX:
            continue
        s = raw.strip()
        if not s:
            continue
        if _is_sample(s):
            # Keep every thin-th sample, and always the one after a snap record.
            keep = pending or n % thin == 0
            n += 1
            if not keep:
                continue
            line = _sample(s.split())
            if line is not None:
                out.append(line)
                kept += 1
                pending = False
            continue
        line = _record(s.split())
        if line is not None:
            out.append(line)
            if line.startswith("warp"):
                pending = True

    text = "\n".join(["FTESURF-REC %d" % ver] + head + ([eye] if eye else [])
                     + (["thin %d" % thin] if thin > 1 else []) + ["begin"] + out) + "\n"
    return {"ok": True, "rec": text, "samples": kept, "thin": thin,
            "truncated": truncated}
