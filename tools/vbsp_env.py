#!/usr/bin/env python3
"""
vbsp_env.py -- what a Source BSP says about its OWN reflections and its 3D sky,
read with no engine code in the path.

WHY THIS EXISTS.  Build 12 fixed the ambient cube and some brush models still
came back wrong -- one set of them "bright saturated blue" on a warm map.  A
lighting bug cannot invent a hue that is not in the lightmap, so before touching
the lighting again the question is whether the blue is *lighting* at all.  The
suspect is reflection: `$envmap env_cubemap` is the standard Source idiom and
means "use the baked cubemap from the nearest env_cubemap entity".  If those
cubemaps are never loaded, whatever the renderer substitutes IS the colour.

This prints, per map:

  * LUMP_CUBEMAPS (42)      -- the env_cubemap positions VRAD/VBSP recorded
  * the pakfile (lump 40)   -- where the BAKED cubemap VTFs actually live
  * sky_camera / worldspawn -- the 3D skybox origin+scale, and skyname
  * every entity classname  -- a census, so nothing is assumed absent

Usage:
    python vbsp_env.py <map.bsp>
    python vbsp_env.py <map.bsp> --pak            # full pakfile listing
    python vbsp_env.py <map.bsp> --extract <name> # one file out of the pakfile
"""

import io
import lzma
import os
import struct
import sys
import zipfile
from collections import Counter

LUMP_ENTITIES  = 0
LUMP_CUBEMAPS  = 42
LUMP_PAKFILE   = 40


class Bsp:
    def __init__(self, path):
        self.data = open(path, "rb").read()
        ident, self.version = struct.unpack_from("<ii", self.data, 0)
        if ident != 0x50534256:
            raise SystemExit("not a VBSP file (ident %08x)" % ident)
        self.lumps = []
        for i in range(64):
            ofs, ln, ver, fourcc = struct.unpack_from("<iii4s", self.data, 8 + i * 16)
            self.lumps.append((ofs, ln, ver, fourcc))

    def lump(self, n):
        """Raw lump bytes, LZMA-decompressed if Valve compressed it.

        A compressed lump carries a big-endian uncompressed size in the fourCC
        field and begins with Valve's 17-byte 'LZMA' header, which is NOT the
        .xz/.lzma container any stdlib decoder expects -- hence FORMAT_RAW with
        the properties unpacked by hand.
        """
        ofs, ln, ver, fourcc = self.lumps[n]
        if ln == 0:
            return b""
        raw = self.data[ofs:ofs + ln]
        if raw[:4] == b"LZMA":
            actual, lzma_size = struct.unpack_from("<II", raw, 4)
            props = raw[12:17]
            lc = props[0] % 9
            rem = props[0] // 9
            lp, pb = rem % 5, rem // 5
            dictsize = struct.unpack_from("<I", props, 1)[0]
            filt = [{"id": lzma.FILTER_LZMA1, "lc": lc, "lp": lp, "pb": pb,
                     "dict_size": max(dictsize, 4096)}]
            d = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filt)
            return d.decompress(raw[17:17 + lzma_size])[:actual]
        return raw


def parse_entities(text):
    """Split the entity lump into a list of dicts. Tolerates the odd stray byte."""
    ents, cur, key = [], None, None
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "{":
            cur, key = {}, None
            i += 1
        elif c == "}":
            if cur is not None:
                ents.append(cur)
            cur = None
            i += 1
        elif c == '"':
            j = text.find('"', i + 1)
            if j < 0:
                break
            tok = text[i + 1:j]
            i = j + 1
            if cur is None:
                continue
            if key is None:
                key = tok
            else:
                # duplicate keys happen (multiple outputs); keep them all
                if key in cur:
                    cur[key] = cur[key] + "\n" + tok
                else:
                    cur[key] = tok
                key = None
        else:
            i += 1
    return ents


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    path = sys.argv[1]
    want_pak = "--pak" in sys.argv
    extract = None
    if "--extract" in sys.argv:
        extract = sys.argv[sys.argv.index("--extract") + 1]

    b = Bsp(path)
    print("%s  VBSP v%d  %d bytes" % (os.path.basename(path), b.version, len(b.data)))
    print()

    # --- LUMP_CUBEMAPS -----------------------------------------------------
    cm = b.lump(LUMP_CUBEMAPS)
    ncm = len(cm) // 16                      # int origin[3]; int size;
    print("LUMP_CUBEMAPS (42): %d bytes, %d cubemaps" % (len(cm), ncm))
    for i in range(min(ncm, 12)):
        x, y, z, size = struct.unpack_from("<iiii", cm, i * 16)
        print("    [%3d] %7d %7d %7d   size %d" % (i, x, y, z, size))
    if ncm > 12:
        print("    ... %d more" % (ncm - 12))
    print()

    # --- entities ----------------------------------------------------------
    ents = parse_entities(b.lump(LUMP_ENTITIES).decode("latin-1"))
    print("LUMP_ENTITIES: %d entities" % len(ents))
    classes = Counter(e.get("classname", "?") for e in ents)

    ws = next((e for e in ents if e.get("classname") == "worldspawn"), {})
    print("    worldspawn skyname     = %r" % ws.get("skyname"))
    print("    worldspawn maxpropscreenwidth = %r" % ws.get("maxpropscreenwidth"))
    print()

    for cn in ("env_cubemap", "sky_camera", "func_brush", "func_detail",
               "func_illusionary", "trigger_teleport",
               "info_teleport_destination", "prop_static", "func_wall"):
        if classes.get(cn):
            print("    %-28s %d" % (cn, classes[cn]))
    print()

    for e in ents:
        if e.get("classname") == "sky_camera":
            print("    sky_camera: origin=%s scale=%s fogenable=%s fogcolor=%s "
                  "fogstart=%s fogend=%s"
                  % (e.get("origin"), e.get("scale"), e.get("fogenable"),
                     e.get("fogcolor"), e.get("fogstart"), e.get("fogend")))

    # teleports: does the destination carry angles?
    dests = {e.get("targetname"): e for e in ents
             if e.get("classname") in ("info_teleport_destination", "info_target")}
    tps = [e for e in ents if e.get("classname") == "trigger_teleport"]
    if tps:
        print()
        print("    trigger_teleport: %d" % len(tps))
        withang = 0
        for t in tps[:8]:
            d = dests.get(t.get("target"))
            print("        -> %-24s spawnflags=%-6s dest angles=%s"
                  % (t.get("target"), t.get("spawnflags"),
                     d.get("angles") if d else "(no dest ent)"))
        for t in tps:
            d = dests.get(t.get("target"))
            if d and d.get("angles") and d.get("angles").split()[1] != "0":
                withang += 1
        print("        %d of %d destinations carry a non-zero yaw"
              % (withang, len(tps)))

    print()
    print("    top classnames:")
    for cn, n in classes.most_common(15):
        print("        %-34s %d" % (cn, n))
    print()

    # --- pakfile -----------------------------------------------------------
    pak = b.lump(LUMP_PAKFILE)
    print("LUMP_PAKFILE (40): %d bytes" % len(pak))
    if pak:
        z = zipfile.ZipFile(io.BytesIO(pak))
        names = z.namelist()
        print("    %d entries" % len(names))
        cubes = [n for n in names if "/c" in n.lower() and n.lower().endswith(".vtf")
                 and "maps/" in n.lower()]
        print("    baked cubemap VTFs (materials/maps/<map>/c*.vtf): %d" % len(cubes))
        for n in cubes[:10]:
            print("        %s" % n)
        if len(cubes) > 10:
            print("        ... %d more" % (len(cubes) - 10))
        if want_pak:
            print("    --- full listing ---")
            for n in sorted(names):
                print("        %s" % n)
        if extract:
            match = [n for n in names if extract.lower() in n.lower()]
            for n in match[:5]:
                out = os.path.basename(n)
                open(out, "wb").write(z.read(n))
                print("    extracted %s -> %s (%d bytes)" % (n, out, len(z.read(n))))


if __name__ == "__main__":
    main()
