#!/usr/bin/env python3
"""zonefit.py against built BSPs, and against tools/census/zonefit.py.

  python3 test_zonefit.py

Every BSP here is made in a temp folder; nothing is read from an install.  The
second half runs the tool the verdict was copied from on the same pairs: two
answers for one question, and they must be the same answer.
"""
import atexit
import json
import lzma
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zonefit as Z     # noqa: E402

FAILED, SKIPPED = [], []
HOME = tempfile.mkdtemp(prefix="surfd-zonefit-")
atexit.register(shutil.rmtree, HOME, True)


def check(label, got, want):
    ok = got == want
    print("%-4s %-66s %r" % ("ok" if ok else "FAIL", label, got))
    if not ok:
        FAILED.append("%s: got %r, want %r" % (label, got, want))


def lzma_lump(raw):
    """A lump the way Source packs one: 'LZMA', sizes, 5 property bytes, the stream."""
    flt = [{"id": lzma.FILTER_LZMA1, "lc": 3, "lp": 0, "pb": 2, "dict_size": 1 << 16}]
    body = lzma.compress(raw, format=lzma.FORMAT_RAW, filters=flt)
    return (b"LZMA" + struct.pack("<II", len(raw), len(body))
            + bytes([3 + 9 * (0 + 5 * 2)]) + struct.pack("<I", 1 << 16) + body)


def vbsp(mins, maxs, names=(), packed=False, extra=b""):
    ents = b'{\n"classname" "worldspawn"\n}\n' + b"".join(
        b'{\n"classname" "info_teleport_destination"\n"targetname" "%s"\n"origin" "0 0 0"\n}\n'
        % n.encode() for n in names) + extra
    models = struct.pack("<9f3i", *(tuple(mins) + tuple(maxs) + (0, 0, 0)), 0, 0, 0)
    if packed:
        ents = lzma_lump(ents)
    table = [(0, 0)] * 64
    off = Z.HDRSZ
    table[0] = (off, len(ents))
    table[14] = (off + len(ents), len(models))
    hdr = b"VBSP" + struct.pack("<i", 20) + b"".join(
        struct.pack("<iiii", o, n, 0, 0) for o, n in table) + struct.pack("<i", 1)
    return hdr + ents + models


def region(x, y, dest=None, bottom=0, height=128):
    r = {"points": [[x, y], [x + 64, y], [x + 64, y + 64], [x, y + 64]],
         "bottom": bottom, "height": height}
    if dest:
        r["teleDestTargetname"] = dest
    return r


def zones(start=(0, 0), end=(2000, 0), dest="start_dest", stage=None):
    segs = [{"checkpoints": [{"regions": [region(start[0], start[1], dest)]}]}]
    if stage:
        segs.append({"checkpoints": [{"regions": [region(stage[0], stage[1], "stage2")]}]})
    return json.dumps({"formatVersion": 1, "tracks": {
        "main": {"zones": {"segments": segs, "end": {"regions": [region(end[0], end[1])]}}},
        "bonuses": []}}, separators=(",", ":")).encode()


def patched(data, at, new):
    return data[:at] + new + data[at + len(new):]


def put(name, data):
    p = os.path.join(HOME, name)
    with open(p, "wb") as fh:
        fh.write(data)
    return p


def main():
    W1 = ((-4096, -4096, -512), (4096, 4096, 2048))
    donor = put("donor.bsp", vbsp(W1[0], W1[1], ["start_dest"]))
    cases = [
        ("the same world recompiled, its roof higher: fits",
         vbsp(W1[0], (4096, 4096, 4096), ["start_dest", "another"]), zones(), "FIT"),
        ("a packed (LZMA) entity lump is read: fits",
         vbsp(W1[0], W1[1], ["start_dest"], packed=True), zones(), "FIT"),
        ("the world's corner moved 512 units: shifted",
         vbsp((-3584, -4096, -512), W1[1], ["start_dest"]), zones(), "SHIFTED"),
        ("...and 64 is still the same frame",
         vbsp((-4032, -4096, -512), W1[1], ["start_dest"]), zones(), "FIT"),
        ("an end zone outside the target's world: shifted",
         vbsp(W1[0], (1000, 4096, 2048), ["start_dest"]), zones(), "SHIFTED"),
        ("a restart destination the target does not have: no dests",
         vbsp(W1[0], W1[1], ["start_dst"]), zones(), "NO-DESTS"),
        ("a stage whose destination is missing: no dests",
         vbsp(W1[0], W1[1], ["start_dest"]), zones(stage=(500, 0)), "NO-DESTS"),
        ("the name is matched whatever the key's case",
         vbsp(W1[0], W1[1], [], extra=b'{\n"TargetName" "start_dest"\n}\n'), zones(), "FIT"),
        ("zones with no destination names need none",
         vbsp(W1[0], W1[1]), zones(dest=None), "FIT"),
    ]
    pairs = []
    for i, (label, tbsp, zb, want) in enumerate(cases):
        t = put("t%d.bsp" % i, tbsp)
        got = Z.fit(zb, donor, t)
        check(label, got[0], want)
        pairs.append((i, zb, want))

    check("a target with Momentum's own timer triggers in its BSP is timed already",
          Z.fit(zones(), donor, put("own.bsp", vbsp(W1[0], W1[1], ["start_dest"], extra=(
              b'{\n"classname" "trigger_momentum_timer_start"\n"model" "*1"\n}\n'))))[0],
          "OWN-TIMER")
    check("a number no float holds is zones of another shape, not an error",
          Z.fit(zones().replace(b'"bottom":0', b'"bottom":' + b"9" * 400, 1), donor, donor)[0],
          "UNREADABLE")
    check("a zone file with no region is nothing to copy",
          Z.fit(b'{"tracks":{"main":{"zones":{}}}}', donor, donor)[0], "EMPTY")
    for label, zb in (("zones that are not JSON", b"<html>"),
                      ("zones that are a list", b"[1,2]"),
                      ("a region whose points are words",
                       zones().replace(b"[0,0]", b'["a","b"]')),
                      ("a destination name that is a number",
                       zones().replace(b'"start_dest"', b"7"))):
        check(label + ": unreadable", Z.fit(zb, donor, donor)[0], "UNREADABLE")
    bad = {
        "a file that is not a VBSP": b"IBSP" + vbsp(W1[0], W1[1])[4:],
        "a file cut inside its header": vbsp(W1[0], W1[1])[:200],
        "a file cut inside its models": vbsp(W1[0], W1[1])[:-20],
        "an entity lump longer than the cap": patched(vbsp(W1[0], W1[1], ["start_dest"]), 12,
                                                      struct.pack("<i", Z.MAX_LUMP + 1)),
        "a world of NaNs": vbsp((float("nan"), 0, 0), W1[1]),
        "a packed lump whose dictionary is over the cap":
            patched(vbsp(W1[0], W1[1], ["start_dest"], packed=True), Z.HDRSZ + 13,
                    struct.pack("<I", Z.MAX_DICT + 1)),
        "a packed lump that claims more than the cap":
            patched(vbsp(W1[0], W1[1], ["start_dest"], packed=True), Z.HDRSZ + 4,
                    struct.pack("<I", Z.MAX_LUMP + 1)),
    }
    for label, data in bad.items():
        check(label + ": unreadable, as target and as donor",
              (Z.fit(zones(), donor, put("bad.bsp", data))[0],
               Z.fit(zones(), put("bad.bsp", data), donor)[0]), ("UNREADABLE", "UNREADABLE"))
    keep, Z.MAX_LUMP = Z.MAX_LUMP, 64
    try:
        got = Z.fit(zones(), donor, donor)[0]
    finally:
        Z.MAX_LUMP = keep
    check("a lump over the cap is not read at all (the cap set to 64 bytes here)",
          got, "UNREADABLE")
    check("a file that is not there: unreadable",
          Z.fit(zones(), donor, os.path.join(HOME, "none.bsp"))[0], "UNREADABLE")
    # A packed lump whose stream is longer than it claims is cut at the claim.
    big = b'{\n"classname" "worldspawn"\n}\n' + b" " * 200000
    lump = lzma_lump(big).replace(struct.pack("<I", len(big)), struct.pack("<I", 64), 1)
    hdr = bytearray(vbsp(W1[0], W1[1]))
    models = bytes(hdr[-48:])
    table = b"VBSP" + struct.pack("<i", 20) + b"".join(
        struct.pack("<iiii", *e) for e in
        [(Z.HDRSZ, len(lump), 0, 0)] + [(0, 0, 0, 0)] * 13
        + [(Z.HDRSZ + len(lump), 48, 0, 0)] + [(0, 0, 0, 0)] * 49) + struct.pack("<i", 1)
    p = put("claim.bsp", table + lump + models)
    with open(p, "rb") as fh:
        check("a packed lump is not inflated past the size it claims",
              len(Z._lump(fh, 0) or b""), 64)

    # The tool the rule came from, on the same pairs.
    tools = os.path.join(os.path.dirname(HERE), "tools", "census")
    if not os.path.isfile(os.path.join(tools, "zonefit.py")):
        SKIPPED.append("the tool's own verdicts (no tools/census beside surfd/)")
    else:
        sys.path.insert(0, tools)
        os.environ["MOMENTUM_DIR"] = os.path.join(HOME, "no-momentum")
        import importlib.util
        spec = importlib.util.spec_from_file_location("census_zonefit",
                                                      os.path.join(tools, "zonefit.py"))
        T = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(T)
        d = os.path.join(HOME, "tool")
        os.makedirs(d)
        T.SEARCH, T.GAMEMAPS, T.MOMMAPS = [d], d, d
        shutil.copyfile(donor, os.path.join(d, "donor.bsp"))
        got, want = [], []
        for i, zb, verdict in pairs:
            shutil.copyfile(os.path.join(HOME, "t%d.bsp" % i), os.path.join(d, "t%d.bsp" % i))
            with open(os.path.join(d, "donor.json"), "wb") as fh:
                fh.write(zb)
            got.append(T.check("donor", "t%d" % i)[0])
            want.append(verdict)
        check("tools/census/zonefit.py gives the same verdict on every pair", got, want)

    print("\n%d failed%s" % (len(FAILED), (", skipped: " + "; ".join(SKIPPED)) if SKIPPED else ""))
    for f in FAILED:
        print("  " + f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
