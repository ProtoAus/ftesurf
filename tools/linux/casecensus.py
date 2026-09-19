#!/usr/bin/env python3
"""casecensus.py -- which of a map's file references only a case-insensitive lookup can find.

On a case-sensitive filesystem FTE finds a loose file whose on-disk spelling differs from the
name it asks for only through the fs_cache hash (fs.c FS_FLocateFile, Hash_GetInsensitiveBucket).
Archives (the BSP pakfile, VPKs) match case-insensitively on every path (fs_vpk.c lowercases).
So a reference is CASE-DEPENDENT when it resolves case-insensitively, but no archive holds it
and no loose copy is spelled exactly as asked.  Two spellings of "as asked":
  lc    the lowercased reference (texdata names are lowercased, mod_vbsp.c:2371-2372)
  asis  the string as the engine issues it: VMT values, .mdl $cdmaterials and entity keys
        keep their case (mod_hl2.c:634-640 builds materials\\<path><name>.vmt verbatim)
Resolution follows tools/mapdeps.py (texdata -> VMT -> textures/includes, props -> .mdl/.vvd/.vtx
and their materials, sky faces) plus entity sounds.  Runs on Windows against the Steam library.

  python tools/linux/casecensus.py --maps bhop_eazy surf_demise      # per-map detail
  python tools/linux/casecensus.py --all --maxmb 150 --top 10         # rank the library
  add --json <file> to keep the result
"""

import argparse
import json
import os
import re
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import mapdeps                                              # noqa: E402
from vbsp_env import Bsp                                    # noqa: E402

STEAM = mapdeps.STEAM
LIVE = [("momentum", os.path.join(STEAM, "Momentum Mod Playtest", "momentum")),
        ("cstrike", os.path.join(STEAM, "Counter-Strike Source", "cstrike")),
        ("hl2", os.path.join(STEAM, "Half-Life 2", "hl2"))]
MOUNT = ("mount", os.path.join(STEAM, "Momentum Mod Playtest", "mount"))
MAPDEPS = os.path.join(mapdeps.FTESURF, "data", "mapdeps.txt")
LOOSE_DIRS = ("materials", "models", "sound")
SNDKEY = re.compile(r'"([^"]+)"\s*"([^"]*\.(?:wav|mp3|ogg))"', re.I)
SNDSTRIP = "*#@<>^)(}$!?"


class LazyBsp(Bsp):
    """vbsp_env.Bsp without reading the whole file: lumps are read by seek."""

    class _Data:
        def __init__(self, f, size):
            self.f, self.size = f, size

        def __len__(self):
            return self.size

        def __getitem__(self, s):
            self.f.seek(s.start)
            return self.f.read(s.stop - s.start)

    def __init__(self, path):
        self.f = open(path, "rb")
        head = self.f.read(8 + 64 * 16)
        ident, self.version = struct.unpack_from("<ii", head, 0)
        if ident != 0x50534256:
            raise ValueError("not VBSP")
        self.lumps = [struct.unpack_from("<iii4s", head, 8 + i * 16) for i in range(64)]
        self.data = LazyBsp._Data(self.f, os.path.getsize(path))

    def lump(self, n):
        ofs, ln, _v, _cc = self.lumps[n]
        if ln == 0:
            return b""
        self.f.seek(ofs)
        raw = self.f.read(ln)
        if raw[:4] == b"LZMA":
            import lzma
            actual, lsize = struct.unpack_from("<II", raw, 4)
            p = raw[12:17]
            filt = [{"id": lzma.FILTER_LZMA1, "lc": p[0] % 9, "lp": (p[0] // 9) % 5,
                     "pb": (p[0] // 9) // 5,
                     "dict_size": max(struct.unpack_from("<I", p, 1)[0], 4096)}]
            d = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filt)
            return d.decompress(raw[17:17 + lsize])[:actual]
        return raw

    def close(self):
        self.f.close()


class Game:
    """One mounted game dir: loose files keyed lowercase -> on-disk relative spelling, plus VPKs."""

    def __init__(self, name, root):
        self.name, self.root, self.loose, self.vpks = name, root, {}, []
        for sub in LOOSE_DIRS:
            base = os.path.join(root, sub)
            if not os.path.isdir(base):
                continue
            for dp, _d, files in os.walk(base):
                rel = os.path.relpath(dp, root).replace("\\", "/")
                for fn in files:
                    r = rel + "/" + fn
                    self.loose.setdefault(r.lower(), r)
        if os.path.isdir(root):
            for fn in sorted(os.listdir(root)):
                if fn.lower().endswith("_dir.vpk"):
                    self.vpks.append(mapdeps.Vpk(os.path.join(root, fn)))

    def in_vpk(self, key):
        return next((v for v in self.vpks if key in v), None)


class World:
    def __init__(self, with_mount):
        t = time.time()
        self.games = [Game(n, r) for n, r in LIVE if os.path.isdir(r)]
        self.mount = Game(*MOUNT) if with_mount and os.path.isdir(MOUNT[1]) else None
        print("indexed %s in %.1fs" % (", ".join("%s %d loose/%d vpk" % (
            g.name, len(g.loose), len(g.vpks)) for g in self.games + ([self.mount] if self.mount else [])),
            time.time() - t), file=sys.stderr)
        self.vmtcache = {}

    def locate(self, key, pak, mount):
        """(first hit, archived anywhere, loose spellings in priority order)."""
        games = self.games + ([self.mount] if mount and self.mount else [])
        first, archived, loose = None, pak.has(key), []
        if archived:
            first = ("bsppak", "pak", key)
        for g in games:     # a game's VPKs are searched before its directory (`path`)
            v = g.in_vpk(key)
            r = g.loose.get(key)
            if v is not None:
                archived = True
                if first is None:
                    first = (g.name, "vpk", key)
            if r is not None:
                loose.append((g.name, r))
                if first is None:
                    first = (g.name, "loose", r)
        return first, archived, loose

    def read(self, key, pak, mount):
        if pak.has(key):
            return pak.read(key)
        games = self.games + ([self.mount] if mount and self.mount else [])
        for g in games:
            v = g.in_vpk(key)
            if v is not None:
                return v.read(key)
            r = g.loose.get(key)
            if r is not None:
                try:
                    with open(os.path.join(g.root, r), "rb") as f:
                        return f.read()
                except OSError:
                    return None
        return None


def clean(v):
    return v.strip().strip('"').replace("\\", "/").lstrip("/")


def vmt_refs_asis(data):
    """mapdeps.vmt_refs, keeping each value's case: [(key, issued path)], [include paths]."""
    s = data.decode("latin-1", "replace")
    tex, inc = [], []
    for key, q, b in mapdeps._KV.findall(s):
        if key.lower() not in mapdeps.TEXKEYS:
            continue
        v = clean(q or b)
        lv = v.lower()
        if not v or lv in mapdeps.NOT_A_FILE or lv.startswith("_rt_"):
            continue
        if lv.endswith(".vtf"):
            v = v[:-4]
        tex.append((key.lower(), "materials/" + v + ".vtf"))
    for q, b in mapdeps._INCLUDE.findall(s):
        v = clean(q or b)
        if not v:
            continue
        if not v.lower().endswith(".vmt"):
            v += ".vmt"
        inc.append(v if v.lower().startswith("materials/") else "materials/" + v)
    return tex, inc


class MapCensus:
    def __init__(self, world, name, path, mount):
        self.w, self.name, self.path, self.mount = world, name, path, mount
        self.refs = {}          # lowercase key -> record

    def ref(self, kind, issued, pak):
        key = issued.lower()
        if key in self.refs:
            return self.refs[key]
        first, archived, loose = self.w.locate(key, pak, self.mount)
        rec = {"kind": kind, "issued": issued, "found": first is not None,
               "first": first[1] if first else None, "pack": first[0] if first else None,
               "disk": first[2] if first and first[1] == "loose" else None,
               "archived": archived}
        exact_lc = any(r == key for _g, r in loose)
        exact_as = any(r == issued for _g, r in loose)
        rec["case_lc"] = bool(first) and not archived and not exact_lc
        rec["case_asis"] = bool(first) and not archived and not exact_as
        # a loose copy wins under fs_cache 1 but an exact-case miss falls to an archive copy (other bytes possible)
        rec["fallback"] = bool(first) and first[1] == "loose" and archived and first[2] != issued
        self.refs[key] = rec
        return rec

    def material(self, issued, pak, depth=0):
        """issued: materials/<name>.vmt as the engine asks for it."""
        rec = self.ref("vmt", issued, pak)
        if not rec["found"] or depth > 4 or rec.get("chased"):
            return rec
        rec["chased"] = True
        data = self.w.read(issued.lower(), pak, self.mount)
        if not data:
            return rec
        tex, inc = vmt_refs_asis(data)
        for _k, t in tex:
            self.ref("vtf", t, pak)
        for i in inc:
            self.material(i, pak, depth + 1)
        return rec

    def run(self):
        bsp = LazyBsp(self.path)
        try:
            pak = mapdeps.BspPak(bsp)
            for m in sorted(set(mapdeps.bsp_materials(bsp))):
                # texdata names are lowercased before lookup; cubemap-patched names fall back.
                # A name already starting materials/ is not prefixed again (mat_vmt.c:4432-4434).
                if m.lower().replace("\\", "/").startswith("materials/"):
                    m = m[len("materials/"):]
                for cand in mapdeps.candidates(m):
                    if self.material(cand, pak)["found"]:
                        break
            ents = mapdeps.bsp_entities(bsp)
            models = set()
            raw = mapdeps.game_lump(bsp, b"sprp")
            if raw and len(raw) >= 4:
                n = struct.unpack_from("<i", raw, 0)[0]
                if 0 <= n < 65536 and 4 + n * 128 <= len(raw):
                    for i in range(n):
                        s = raw[4 + i * 128: 4 + i * 128 + 128].split(b"\0", 1)[0]
                        models.add(clean(s.decode("latin-1")))
            for mm in mapdeps._ENTMODEL.finditer(ents):
                models.add(clean(mm.group(1).decode("latin-1")))
            for mdl in sorted(m for m in models if m.lower().endswith(".mdl")):
                self.model(mdl, pak)
            sky = re.search(rb'"skyname"\s*"([^"]*)"', ents[:400000], re.I)
            if sky and sky.group(1).strip():
                s = sky.group(1).decode("latin-1").strip()
                for suf in mapdeps.SKY_SUF:
                    for cand in ("materials/skybox/%s_hdr%s.vtf" % (s, suf),
                                 "materials/skybox/%s%s.vtf" % (s, suf),
                                 "materials/skybox/%s%s.vmt" % (s, suf)):
                        if self.ref("sky", cand, pak)["found"]:
                            break
            for _k, v in SNDKEY.findall(ents.decode("latin-1", "replace")):
                v = clean(v).lstrip(SNDSTRIP)
                if v:
                    self.ref("sound", v if v.lower().startswith("sound/") else "sound/" + v, pak)
            if pak.zip:
                pak.zip.close()
        finally:
            bsp.close()
        return self

    def model(self, mdl, pak):
        rec = self.ref("mdl", mdl, pak)
        if not rec["found"]:
            return
        stem = mdl[:-4]
        self.ref("mdl", stem + ".vvd", pak)
        for v in mapdeps.VTX:
            if self.ref("mdl", stem + v, pak)["found"]:
                break
        try:
            cands = mapdeps.mdl_materials(self.w.read(mdl.lower(), pak, self.mount) or b"", mdl)
        except Exception:
            cands = []
        for paths in cands:
            for c in paths:
                p = "materials/" + clean(c) + ".vmt"
                if self.w.locate(p.lower(), pak, self.mount)[0]:
                    self.material(p, pak)
                    break

    def summary(self):
        r = self.refs.values()
        return {"map": self.name, "bytes": os.path.getsize(self.path), "mount": self.mount,
                "refs": len(self.refs), "found": sum(x["found"] for x in r),
                "loose_first": sum(x["first"] == "loose" for x in r),
                "case_lc": sum(x["case_lc"] for x in r),
                "case_asis": sum(x["case_asis"] for x in r),
                "fallback": sum(x["fallback"] for x in r),
                "list": sorted(({"kind": x["kind"], "issued": x["issued"], "disk": x["disk"],
                                 "pack": x["pack"], "lc": x["case_lc"], "asis": x["case_asis"]}
                                for x in r if x["case_lc"] or x["case_asis"]),
                               key=lambda d: d["issued"].lower())}


def library():
    maps = {}
    for _n, root in LIVE:
        d = os.path.join(root, "maps")
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                if fn.lower().endswith(".bsp"):
                    maps.setdefault(fn[:-4].lower(), (fn[:-4], os.path.join(d, fn)))
    return maps


def deps():
    out = {}
    try:
        for line in open(MAPDEPS, encoding="utf-8"):
            p = line.split(None, 2)
            if len(p) == 3 and p[0] == "dep":
                out.setdefault(p[1].lower(), []).append(p[2].strip())
    except OSError:
        pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maps", nargs="*", default=[])
    ap.add_argument("--all", action="store_true", help="scan the whole library and rank")
    ap.add_argument("--maxmb", type=float, default=0)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--json")
    ap.add_argument("--list", type=int, default=40, help="case-dependent rows shown per map")
    a = ap.parse_args()

    lib, dep = library(), deps()
    world = World(with_mount=True)
    # a map needing a pack other than Momentum's mount is excluded from ranking: the rig has none
    ok_dep = {"steam:Momentum Mod Playtest/mount"}
    names = [m.lower() for m in a.maps]
    if a.all:
        names += [k for k in sorted(lib) if k not in names]
    results, skipped = [], {}
    t = time.time()
    for i, k in enumerate(names):
        if k not in lib:
            print("no such map: %s" % k, file=sys.stderr)
            continue
        disk, path = lib[k]
        explicit = k in [m.lower() for m in a.maps]
        if not explicit:
            if a.maxmb and os.path.getsize(path) > a.maxmb * 1048576:
                skipped["size"] = skipped.get("size", 0) + 1
                continue
            if any(d not in ok_dep for d in dep.get(k, [])):
                skipped["deps"] = skipped.get("deps", 0) + 1
                continue
        mount = "steam:Momentum Mod Playtest/mount" in dep.get(k, [])
        try:
            s = MapCensus(world, disk, path, mount).run().summary()
        except Exception as e:
            print("%s: unreadable (%s)" % (disk, e), file=sys.stderr)
            continue
        s["explicit"] = explicit
        results.append(s)
        if (i + 1) % 100 == 0:
            print("  %d/%d %.0fs" % (i + 1, len(names), time.time() - t), file=sys.stderr)

    fmt = "%-34s %7s %5s %5s %5s %5s %5s %5s"
    print(fmt % ("map", "MB", "refs", "found", "loose", "lc", "asis", "fallb"))
    rank = sorted(results, key=lambda s: (-s["case_lc"], s["map"].lower()))
    shown = [s for s in results if s["explicit"]] + [s for s in rank if not s["explicit"]][:a.top]
    for s in shown:
        print(fmt % (s["map"], "%.1f" % (s["bytes"] / 1048576.0), s["refs"], s["found"],
                     s["loose_first"], s["case_lc"], s["case_asis"], s["fallback"]))
    if a.all:
        print("ranked %d maps (%s skipped: %s)" % (len(rank), sum(skipped.values()), skipped))
        print("maps with case_lc > 0: %d; with case_asis > 0: %d" % (
            sum(s["case_lc"] > 0 for s in rank), sum(s["case_asis"] > 0 for s in rank)))
    for s in results:
        if not s["explicit"] or not s["list"]:
            continue
        print("\n%s: %d case-dependent (lc %d, asis %d)" % (s["map"], len(s["list"]), s["case_lc"], s["case_asis"]))
        for d in s["list"][:a.list]:
            print("  %-5s %s%s  issued %s  disk %s/%s" % (d["kind"], "L" if d["lc"] else "-", "A" if d["asis"] else "-",
                                                       d["issued"], d["pack"], d["disk"]))
        if len(s["list"]) > a.list:
            print("  ...and %d more" % (len(s["list"]) - a.list))
    if a.json:
        with open(a.json, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"results": results, "skipped": skipped}, f, indent=1)


if __name__ == "__main__":
    main()
