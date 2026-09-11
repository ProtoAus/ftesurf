#!/usr/bin/env python3
"""
mapdeps.py -- which maps need an asset pack that FTESurf does not mount.

WHY THIS EXISTS.  ftesurf/fs_addons.txt mounts Momentum, CS:S and HL2 at boot
and leaves CS:GO and TF2 commented out, because those two packs are 85% of
everything the engine indexes and cost 13 seconds of EVERY launch for the
benefit of a handful of maps.  That trade is right, and it has one cost: the
maps that DO need them come up as a checkerboard, and the only way to find out
which pack to mount was to load the map and read the console.  Portal 2 and
Portal are never mounted at boot either, and unlike CS:GO/TF2 they were not in
this tool's ADDONS list at all until 2026-09-07 -- see the note there.

Output is ftesurf/data/mapdeps.txt, read by the engine's fs_automount at the top
of SV_Map_f, which mounts what a map needs for that map and no other.  A map
with no line needs nothing and pays nothing, which is almost all of them.

WHAT CHANGED, AND WHY IT MATTERS (the v2 rewrite).  Version 1 of this tool asked
only "does the .vmt exist".  It never opened one.  That is not the question the
engine asks, and the difference is not academic:

    surf_tensor2 ships three .vmt stubs inside its own BSP pakfile whose
    $basetexture points at concrete/tunnel_concretewall_01b.vtf and
    concrete/hr_c/hr_concrete_floor_05_dirty_color.vtf, and those .vtf files
    exist only in CS:GO.  Every material "resolved", so no dep line was
    written, so CS:GO was never mounted, so those surfaces rendered untextured.

Auditing the whole library the old way missed **155 maps** with exactly that
shape -- surf_sodacity (87 broken textures), surf_monotony (82, and it needs
BOTH packs), surf_fortum (81), surf_journeys (71).  So v2 opens every material
it resolves and follows it to the actual image files, through the same keys
plugins/hl2/mat_vmt.c reads, including `include`/`patch` inheritance.  It also
looks at the two other things a map can be missing and v1 never checked: the
skybox named in worldspawn, and static prop models with their .vvd/.vtx
siblings and their own materials.

And it now writes MORE THAN ONE dep line per map.  v1 picked a single
best-scoring pack with max(); six maps need the other one too.  The engine has
always looped over several lines -- fs.c, "No break: a map may name more than
one pack" -- so only the writer was ever the limit.

HOW A MAP'S MATERIAL LIST IS READ.  Lump 43 (TexdataStringData) is a blob of
NUL-separated names and lump 44 (TexdataStringTable) is the array of offsets
into it -- the offsets matter because the blob is not simply a NUL-separated
list in index order.  Either lump may be LZMA-compressed with Valve's own
17-byte header, which is not a container any stdlib decoder recognises.
vbsp_env.py's Bsp class already handles both, so it is imported rather than
reimplemented.  Game lumps (the `sprp` static prop list) carry their OWN
per-lump LZMA, separately from the lump they live in -- see game_lump().

Usage:
    python tools/mapdeps.py                 # scan, write data/mapdeps.txt
    python tools/mapdeps.py --dry           # scan, write nothing
    python tools/mapdeps.py --map surf_tensor2   # one map, verbose, says why
    python tools/mapdeps.py --audit         # classify every map's breakage
"""

import argparse
import lzma
import os
import re
import struct
import sys
import time
import zipfile
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vbsp_env import Bsp                                    # noqa: E402

STEAM = r"C:\Program Files (x86)\Steam\steamapps\common"
FTESURF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "ftesurf")

LUMP_ENTITIES = 0
LUMP_PAKFILE = 40
LUMP_TEXDATA_STRDATA = 43
LUMP_TEXDATA_STRTABLE = 44
LUMP_GAME_LUMP = 35

#The packs fs_addons.txt mounts at boot, in its own priority order.  A file
#found in any of these is not a dependency on anything -- it is just there.
MOUNTED = [
    ("momentum", os.path.join(STEAM, "Momentum Mod Playtest", "momentum")),
    ("cstrike",  os.path.join(STEAM, "Counter-Strike Source", "cstrike")),
    ("hl2",      os.path.join(STEAM, "Half-Life 2", "hl2")),
]

#The packs it does NOT, and the fs_automount spec that mounts each.
#
#Order is the attribution order -- Resolver.find takes the FIRST addon that has
#the file -- so it must stay stable or every regeneration churns the output.
#New packs go on the end.
#
#Portal 2 was missing until 2026-09-07 and it is not a small omission: Momentum's
#own momentum/gameinfo.txt mounts four appids (440 TF2, 240 CS:S, 4465480 CS:GO
#legacy, 620 Portal 2) and this tool knew about only the first three, so every
#Portal-sourced texture fell into the "in no pack at all, unfixable by mounting"
#bucket.  That is how surf_monolith's 397-face concrete/concrete_bts_modular_
#wall001a came to be diagnosed as a map packing bug: the file was never missing,
#the mount was.  Portal 1 earns a line of its own because two maps
#(bhop_theory_hard, surf_portal_game4) reference dx8/older variants that Portal 2
#dropped -- Portal 2 first, since it covers all but those.
ADDONS = [
    ("tf2",  os.path.join(STEAM, "Team Fortress 2", "tf"),
     "steam:Team Fortress 2/tf"),
    ("csgo", os.path.join(STEAM, "Counter-Strike Global Offensive", "csgo"),
     "steam:Counter-Strike Global Offensive/csgo"),
    ("portal2", os.path.join(STEAM, "Portal 2", "portal2"),
     "steam:Portal 2/portal2"),
    ("portal", os.path.join(STEAM, "Portal", "portal"),
     "steam:Portal/portal"),
    #Momentum Mod's OWN content mount, and the second time a missing candidate here
    #was mistaken for missing content (see Portal 2 above).  momentum/gameinfo.txt
    #mounts `game mount/hl2_dir.vpk`, a 35,474-file bundle of HL2 plus both episodes,
    #and fs_addons.txt said that directory "ships empty" -- it does not.  So every
    #episode-only prop fell into the "-" bucket: surf_fantasy's pine trees, ferns,
    #stumps and fallen trees (126 of its 2345 static props, measured 2026-09-09) were
    #filed as unfixable while this pack had every one of them.  Chosen over
    #`steam:Half-Life 2/ep2`, which has them too at identical checksums, because the
    #map library IS this install: anyone who has the maps has the mount, and nobody
    #needs to own a second game.  Last, like every addition, so no existing
    #attribution moves.
    ("mount", os.path.join(STEAM, "Momentum Mod Playtest", "mount"),
     "steam:Momentum Mod Playtest/mount"),
]

#The VMT keys plugins/hl2/mat_vmt.c actually turns into a texture load, at
#mat_vmt.c:378-597.  Keys it parses and DISCARDS ($detail, $blendmodulatetexture,
#$refracttexture, $reflecttexture, $phong*, $parallaxmap) are deliberately absent:
#a missing file behind one of those cannot produce a visible miss, and counting
#them would attribute breakage to maps that render fine.
TEXKEYS = (
    "basetexture", "basetexture2", "texture2",
    "bumpmap", "bumpmap2",
    "envmap", "envmapmask",
    "selfillummask", "dudvmap",
    "hdrbasetexture", "hdrcompressedtexture",
    "refracttinttexture",
)
#Of those, the ones whose absence is VISIBLE as an untextured surface rather than
#a missing effect.  $envmap in particular is usually the literal "env_cubemap".
VISIBLE_TEXKEYS = ("basetexture", "basetexture2", "texture2", "bumpmap", "bumpmap2")

#A value that names a runtime target rather than a file on disk.
NOT_A_FILE = ("env_cubemap", "_rt_camera", "_rt_waterreflection",
              "_rt_waterrefraction", "_rt_fullframefb", "_rt_smallfb0",
              "_rt_smallfb1")

#Key/value, tolerating "$basetexture" "x", $basetexture x, and mixed quoting.
#Deliberately NOT anchored to end-of-line: these files are CRLF, and a `$`
#anchor never matches because the \r is still there after the closing quote --
#which silently returned "no textures referenced" for every material and is
#exactly the mistake that made surf_tensor2 look clean.
_KV = re.compile(r'"?\$([A-Za-z0-9_]+)"?[ \t]+(?:"([^"\r\n]*)"|([^\s"]+))')
_INCLUDE = re.compile(r'"?include"?[ \t]+(?:"([^"\r\n]*)"|([^\s"]+))', re.I)
_SKYNAME = re.compile(rb'"skyname"\s*"([^"]*)"', re.I)
_ENTMODEL = re.compile(rb'"model"\s*"([^"]*\.mdl)"', re.I)


# --------------------------------------------------------------------------
#  VPK -- directory AND payload
# --------------------------------------------------------------------------

class Vpk:
    """A _dir.vpk, indexed by path, with the ability to read a file back out.

    v1 of this tool only ever needed the name list.  Chasing a material to its
    textures means actually reading the .vmt, and a VMT in CS:S or HL2 lives
    inside the archive, so the payload side has to exist too.

    Layout: the tree is three nested runs of NUL-terminated strings (extension /
    directory / filename), each run ended by an empty string, with a fixed
    18-byte entry after every filename followed by `preload` inline bytes.  A
    directory of " " means the archive root.  An archive index of 0x7fff means
    the payload is in THIS file, after the tree; anything else means the sibling
    <base>_%03d.vpk.  Small files are often entirely preload, with no payload at
    all, which is why `length` of 0 is normal and not an error.
    """

    def __init__(self, path):
        self.path = path
        self.base = path[:-8] if path.lower().endswith("_dir.vpk") else path
        self.entries = {}

        with open(path, "rb") as f:
            head = f.read(28)
            sig, ver = struct.unpack_from("<II", head, 0)
            if sig != 0x55AA1234:
                return
            treesize = struct.unpack_from("<I", head, 8)[0]
            hdr = 12 if ver == 1 else 28
            f.seek(hdr)
            data = f.read(treesize)
        self.database = hdr + treesize

        pos = 0

        def cstr():
            nonlocal pos
            e = data.index(b"\0", pos)
            s = data[pos:e].decode("latin-1")
            pos = e + 1
            return s

        try:
            while True:
                ext = cstr()
                if not ext:
                    break
                while True:
                    folder = cstr()
                    if not folder:
                        break
                    while True:
                        name = cstr()
                        if not name:
                            break
                        crc, preload, arch, offset, length, _term = \
                            struct.unpack_from("<IHHIIH", data, pos)
                        pos += 18
                        pre = data[pos:pos + preload]
                        pos += preload
                        full = name if folder == " " else folder + "/" + name
                        key = (full + "." + ext).lower().replace("\\", "/")
                        self.entries[key] = (arch, offset, length, pre)
        except (ValueError, struct.error):
            #A truncated tree is worth continuing with rather than discarding:
            #everything parsed before the damage is still valid.
            pass

    def __contains__(self, key):
        return key in self.entries

    def size(self, key):
        arch, offset, length, pre = self.entries[key]
        return length + len(pre)

    def read(self, key):
        arch, offset, length, pre = self.entries[key]
        if not length:
            return pre
        if arch == 0x7fff:
            src, base = self.path, self.database
        else:
            src, base = "%s_%03d.vpk" % (self.base, arch), 0
        try:
            with open(src, "rb") as f:
                f.seek(base + offset)
                return pre + f.read(length)
        except OSError:
            return None


class Pack:
    """One game directory: its loose files and its VPKs, as the engine sees them.

    Only materials/ and models/ are walked for loose files -- a game dir also
    holds sound, maps and a few hundred megabytes of things no material or model
    reference can name, and walking those is pure cost.
    """

    def __init__(self, name, root):
        self.name = name
        self.root = root
        self.loose = {}
        self.vpks = []

        for sub in ("materials", "models"):
            base = os.path.join(root, sub)
            if not os.path.isdir(base):
                continue
            for dirpath, _dirs, files in os.walk(base):
                rel = os.path.relpath(dirpath, root).replace("\\", "/").lower()
                for fn in files:
                    self.loose[rel + "/" + fn.lower()] = os.path.join(dirpath, fn)

        if os.path.isdir(root):
            for fn in sorted(os.listdir(root)):
                if fn.lower().endswith("_dir.vpk"):
                    self.vpks.append(Vpk(os.path.join(root, fn)))

    def __len__(self):
        return len(self.loose) + sum(len(v.entries) for v in self.vpks)

    def has(self, key):
        if key in self.loose:
            return True
        return any(key in v for v in self.vpks)

    def read(self, key):
        p = self.loose.get(key)
        if p:
            try:
                with open(p, "rb") as f:
                    return f.read()
            except OSError:
                return None
        for v in self.vpks:
            if key in v:
                return v.read(key)
        return None

    def size(self, key):
        p = self.loose.get(key)
        if p:
            try:
                return os.path.getsize(p)
            except OSError:
                return 0
        for v in self.vpks:
            if key in v:
                return v.size(key)
        return 0


class BspPak(Pack):
    """The map's own embedded pakfile (lump 40) wearing the same interface.

    A map that ships its own copy of something depends on no pack for it, so
    this has to sit alongside the real packs in the same lookup order.  A
    corrupt or absent pak is an empty one, not an error -- plenty of maps have
    none.
    """

    def __init__(self, bsp):
        self.name = "bsppak"
        self.loose = {}
        self.vpks = []
        self.zip = None
        self._names = {}
        try:
            raw = bsp.lump(LUMP_PAKFILE)
            if not raw:
                return
            self.zip = zipfile.ZipFile(BytesIO(raw))
            self._names = {n.lower().replace("\\", "/"): n
                           for n in self.zip.namelist()}
        except Exception:
            self.zip = None
            self._names = {}

    def __len__(self):
        return len(self._names)

    def has(self, key):
        return key in self._names

    def read(self, key):
        if key not in self._names:
            return None
        try:
            return self.zip.read(self._names[key])
        except Exception:
            return None

    def size(self, key):
        if key not in self._names:
            return 0
        try:
            return self.zip.getinfo(self._names[key]).file_size
        except Exception:
            return 0


# --------------------------------------------------------------------------
#  BSP
# --------------------------------------------------------------------------

def bsp_materials(bsp):
    """The map's material names, as the texdata string table orders them."""
    blob = bsp.lump(LUMP_TEXDATA_STRDATA)
    table = bsp.lump(LUMP_TEXDATA_STRTABLE)
    out = []
    for i in range(len(table) // 4):
        ofs = struct.unpack_from("<i", table, i * 4)[0]
        if 0 <= ofs < len(blob):
            e = blob.find(b"\0", ofs)
            if e < 0:
                e = len(blob)
            n = blob[ofs:e].decode("latin-1").strip()
            if n:
                out.append(n)
    return out


def bsp_pak_names(bsp):
    """Back-compat: the embedded pakfile's contents as a lowercased name set."""
    return set(BspPak(bsp)._names)


def bsp_entities(bsp):
    try:
        return bsp.lump(LUMP_ENTITIES) or b""
    except Exception:
        return b""


def bsp_skyname(bsp):
    m = _SKYNAME.search(bsp_entities(bsp)[:400000])
    if not m:
        return None
    s = m.group(1).decode("latin-1").strip().lower()
    return s or None


def bsp_entity_models(bsp):
    """`model` keys naming a .mdl, from prop_dynamic/prop_physics and friends.

    These are NOT in the sprp game lump and were invisible to v1 twice over:
    surf_tensor2 has nine of them and zero appear in sprp.
    """
    out = set()
    for m in _ENTMODEL.finditer(bsp_entities(bsp)):
        v = m.group(1).decode("latin-1").strip().lower().replace("\\", "/")
        if v.endswith(".mdl"):
            out.add(v.lstrip("/"))
    return out


def game_lump(bsp, want=b"sprp"):
    """One game sub-lump, decompressed.

    Game lumps carry their OWN LZMA independently of the lump they live in
    (mod_vbsp.c: `flags & 1`), which is why reading lump 35 raw gives garbage.
    A 12-byte stub with declared_uncompressed == 12 is a genuinely EMPTY prop
    list -- what Strata writes -- not a parse failure.
    """
    try:
        blob = bsp.lump(LUMP_GAME_LUMP)
    except Exception:
        return None
    if not blob or len(blob) < 4:
        return None
    count = struct.unpack_from("<i", blob, 0)[0]
    if not 0 < count < 4096:
        return None
    for i in range(count):
        o = 4 + i * 16
        if o + 16 > len(blob):
            return None
        gid, flags, ver, fileofs, filelen = struct.unpack_from("<IHHii", blob, o)
        tag = struct.pack(">I", gid)
        if tag != want:
            continue
        #fileofs is an absolute offset into the BSP, and Bsp already holds the
        #whole file, so this is a slice rather than a second read.
        if fileofs < 0 or filelen <= 0 or fileofs + filelen > len(bsp.data):
            return None
        raw = bsp.data[fileofs:fileofs + filelen]
        if len(raw) < 4:
            return None
        if flags & 1:
            if raw[:4] != b"LZMA":
                return None
            au, ac = struct.unpack_from("<II", raw, 4)
            props = raw[12:17]
            try:
                dec = lzma.LZMADecompressor(
                    format=lzma.FORMAT_RAW,
                    filters=[lzma._decode_filter_properties(lzma.FILTER_LZMA1, props)])
                raw = dec.decompress(raw[17:], au)
            except Exception:
                return None
        return raw
    return None


def bsp_static_props(bsp):
    """The static prop model dictionary: `int count` then count * char[128]."""
    raw = game_lump(bsp, b"sprp")
    if not raw or len(raw) < 4:
        return set()
    n = struct.unpack_from("<i", raw, 0)[0]
    if not 0 <= n < 65536 or 4 + n * 128 > len(raw):
        return set()
    out = set()
    for i in range(n):
        s = raw[4 + i * 128: 4 + i * 128 + 128].split(b"\0", 1)[0]
        s = s.decode("latin-1").strip().lower().replace("\\", "/")
        if s.endswith(".mdl"):
            out.add(s.lstrip("/"))
    return out


# --------------------------------------------------------------------------
#  Materials
# --------------------------------------------------------------------------

def candidates(mat):
    """Every path a material name could resolve through, lowercased.

    Source patches a cubemapped material by writing a per-instance copy under
    maps/<map>/<original>_<x>_<y>_<z>, so an unresolved name of that shape is
    really a reference to the original -- and it is the ORIGINAL's pack that has
    to be mounted.  Stripping back to it is what makes surf_utopia's three
    glasswindow entries attribute to TF2 rather than to nothing.
    """
    m = mat.lower().replace("\\", "/").lstrip("/")
    #Some maps write the extension into the texdata name ("water/water_well_
    #beneath.vmt").  Source tolerates it and so does FTE, so a name that already
    #carries it must not be turned into a .vmt.vmt that matches nothing.
    if m.endswith(".vmt"):
        m = m[:-4]
    outs = ["materials/" + m + ".vmt"]

    if m.startswith("maps/"):
        parts = m.split("/", 2)
        if len(parts) == 3:
            inner = parts[2]
            bits = inner.rsplit("_", 3)          #trailing _<x>_<y>_<z>, maybe negative
            if len(bits) == 4 and all(b.lstrip("-").isdigit() for b in bits[1:]):
                inner = bits[0]
            outs.append("materials/" + inner + ".vmt")
    return outs


def texpath(value):
    """A VMT texture value as the path the engine will look for."""
    v = value.strip().strip('"').replace("\\", "/").lstrip("/").lower()
    if not v or v in NOT_A_FILE or v.startswith("_rt_"):
        return None
    if v.endswith(".vtf"):
        v = v[:-4]
    return "materials/" + v + ".vtf"


def vmt_refs(text):
    """(texture paths, include paths) a VMT asks for.

    Returned separately because an `include`/`patch` parent is chased
    recursively while a texture is a leaf.
    """
    try:
        s = text.decode("latin-1", "replace")
    except Exception:
        return [], []
    tex = []
    for key, quoted, bare in _KV.findall(s):
        k = key.lower()
        if k in TEXKEYS:
            p = texpath(quoted or bare)
            if p:
                tex.append((k, p))
    inc = []
    for quoted, bare in _INCLUDE.findall(s):
        v = (quoted or bare).strip().replace("\\", "/").lstrip("/").lower()
        if not v:
            continue
        if not v.endswith(".vmt"):
            v += ".vmt"
        inc.append(v if v.startswith("materials/") else "materials/" + v)
    return tex, inc


# --------------------------------------------------------------------------
#  Resolution
# --------------------------------------------------------------------------

class Resolver:
    """Where a path is, over an ordered list of packs.

    `live` is what is mounted for this map right now (the map's own pakfile plus
    the boot packs); `addons` are the candidates we are deciding about.  A hit in
    live is free; a hit in an addon is a dependency; a hit in neither is content
    the map shipped without and no mount can fix.
    """

    def __init__(self, live, addons):
        self.live = live
        self.addons = addons
        self.vmtcache = {}          #path -> (tex, inc), shared across maps
        self.mdlcache = {}          #path -> the .mdl's material candidates, likewise

    def find(self, path):
        for p in self.live:
            if p.has(path):
                return p, None
        for p in self.addons:
            if p.has(path):
                return p, p.name
        return None, "-"

    def read_vmt(self, path, pack):
        hit = self.vmtcache.get(path)
        if hit is not None:
            return hit
        data = pack.read(path) if pack else None
        out = vmt_refs(data) if data else ([], [])
        #Only cache reads from the shared packs.  A map's own pakfile is
        #per-map, and two maps can ship different files at the same path.
        if pack is None or pack.name != "bsppak":
            self.vmtcache[path] = out
        return out


def resolve_material(rs, mat, need, seen, depth=0, prefer=None):
    """Walk one material to its textures, recording every pack it needs.

    `need` is a dict pack-name -> set of paths that pack alone supplies.
    Missing-from-everything lands under "-".

    `prefer` is an addon pack credited AHEAD of ADDONS order for anything the
    live packs lack -- resolve_model passes the pack the model itself came from.
    Content authored together should be served together: surf_fantasy's episode
    pines come from Momentum's mount and wear arbre01.vtf, which TF2 (first in
    ADDONS) also ships with DIFFERENT bytes.  Order alone credits TF2, which both
    serves a texture the model was not authored with and mounts a 147k-entry
    index for it.  World materials pass no preference and are unchanged.
    """
    def find(path):
        p, w = rs.find(path)
        if w and prefer is not None and prefer.has(path):
            return prefer, prefer.name
        return p, w

    for cand in candidates(mat):
        pack, who = find(cand)
        if pack is None:
            continue
        if who:
            need.setdefault(who, set()).add(cand)
        if cand in seen or depth > 4:
            return True
        seen.add(cand)
        tex, inc = rs.read_vmt(cand, pack)
        for key, t in tex:
            if t in seen:
                continue
            seen.add(t)
            tpack, twho = find(t)
            if twho:
                need.setdefault(twho, set()).add(t)
                if key in VISIBLE_TEXKEYS:
                    need.setdefault("visible:" + twho, set()).add(t)
        for i in inc:
            resolve_material(rs, i[len("materials/"):-len(".vmt")], need, seen,
                             depth + 1, prefer)
        return True
    #No candidate resolved anywhere at all
    need.setdefault("-", set()).add(candidates(mat)[0])
    need.setdefault("visible:-", set()).add(candidates(mat)[0])
    return False


VTX = (".dx90.vtx", ".dx80.vtx", ".vtx", ".sw.vtx")


def resolve_model(rs, mdl, need, seen):
    """A .mdl plus the siblings mod_hl2.c actually opens.

    .vvd is required and has one name; .vtx is required and the loader takes the
    first of .dx90/.dx80/plain/.sw (mod_hl2.c:924-946); .phy is optional and only
    affects collision (mod_phy.c:548-558), so its absence is not counted.
    """
    if mdl in seen:
        return
    seen.add(mdl)
    stem = mdl[:-4]
    pack, who = rs.find(mdl)
    if pack is None:
        need.setdefault("-", set()).add(mdl)
        return
    if who:
        need.setdefault(who, set()).add(mdl)
    for sib in (stem + ".vvd",):
        _p, w = rs.find(sib)
        if w and w != "-":
            need.setdefault(w, set()).add(sib)
    if not any(rs.find(stem + v)[0] for v in VTX):
        need.setdefault("-", set()).add(stem + ".dx90.vtx")
    else:
        for v in VTX:
            p, w = rs.find(stem + v)
            if p is not None:
                if w and w != "-":
                    need.setdefault(w, set()).add(stem + v)
                break

    #...and the model's OWN materials, which the docstring at the top of this file
    #has claimed since v2 and this function never did.  Measured on surf_fantasy:
    #its pakfile carries arbre01.vmt, ferns01.vmt and arbrefallen01.vmt while the
    #.vtf behind every one of them is in Momentum's mount only -- the surf_tensor2
    #shape (a packed stub over an unmounted texture), for props.  Trees whose .mdl
    #was missing as well got their dep line from the model; tree_pine04x2, packed
    #whole and wearing the same arbre01, would not have.
    cands = rs.mdlcache.get(mdl) if pack.name != "bsppak" else None
    if cands is None:
        try:
            cands = mdl_materials(pack.read(mdl) or b"", mdl)
        except Exception:
            cands = []
        if pack.name != "bsppak":
            rs.mdlcache[mdl] = cands
    #A model from an addon pack credits that pack first for its own materials; see
    #resolve_material's `prefer`.  A model resolved from a live pack has no addon
    #of its own to prefer.
    mine = pack if who else None
    for paths in cands:
        for c in paths:
            if rs.find(candidates(c)[0])[0] is not None or (mine is not None and mine.has(candidates(c)[0])):
                resolve_material(rs, c, need, seen, prefer=mine)
                break
        else:
            if paths:
                resolve_material(rs, paths[0], need, seen, prefer=mine)


def mdl_materials(data, mdl):
    """For each texture a .mdl names, its material candidates in probe order.

    mod_hl2.c:630-655 tries every texture under each $cdmaterials path in turn
    and the first .vmt that exists wins; a model with no path list uses its own
    directory.  Names only -- no materials/ prefix and no .vmt, the form
    resolve_material takes.  Offsets are the studiohdr_t fields the loader reads:
    texture count/offset at 204/208, cdtexture count/offset at 212/216, and a
    64-byte mstudiotexture_t whose name offset is relative to itself.
    """
    if len(data) < 220 or data[:4] != b"IDST":
        return []
    try:
        texn, texo = struct.unpack_from("<ii", data, 204)
        pathn, patho = struct.unpack_from("<ii", data, 212)
        if not (0 <= texn <= 1024 and 0 <= pathn <= 256):
            return []

        def cstr(o):
            return data[o:data.index(b"\0", o)].decode("latin-1")

        paths = [cstr(struct.unpack_from("<i", data, patho + i * 4)[0])
                 for i in range(pathn)]
        out = []
        for i in range(texn):
            base = texo + i * 64
            name = cstr(base + struct.unpack_from("<i", data, base)[0])
            if paths:
                out.append([p + name for p in paths])
            else:
                out.append([mdl[:-4] + "/" + name])
        return out
    except (struct.error, ValueError, IndexError):
        return []


# --------------------------------------------------------------------------

SKY_SUF = ("rt", "bk", "lf", "ft", "up", "dn")


def resolve_sky(rs, sky, need, seen):
    """Six faces, as engine/gl/gl_shader.c Shader_ParseSkySides probes for them.

    It loads faces as IMAGES, so the .vtf is what has to be there; a .vmt at the
    same name is what the engine cannot currently follow (see the sky work in the
    plan), so a face that has only a .vmt is recorded as an engine gap, not as a
    pack dependency.
    """
    for suf in SKY_SUF:
        base = "materials/skybox/" + sky + suf
        hdr = "materials/skybox/" + sky + "_hdr" + suf
        for cand in (hdr + ".vtf", base + ".vtf"):
            pack, who = rs.find(cand)
            if pack is not None:
                if who and who != "-":
                    need.setdefault(who, set()).add(cand)
                break
        else:
            #no direct image; is there a material naming one?
            for cand in (hdr + ".vmt", base + ".vmt"):
                pack, who = rs.find(cand)
                if pack is not None:
                    if who and who != "-":
                        need.setdefault(who, set()).add(cand)
                    need.setdefault("sky:indirect", set()).add(cand)
                    break
            else:
                need.setdefault("sky:missing", set()).add(base + ".vtf")


def scan(bsp_path, live_packs, addon_packs, do_models=True, do_sky=True):
    """{bucket -> set of paths} for one map.  Buckets are pack names, '-' for
    'in no pack', 'visible:<x>' for the subset that shows as an untextured
    surface, and 'sky:*' for the two sky conditions."""
    try:
        bsp = Bsp(bsp_path)
        mats = bsp_materials(bsp)
    except Exception:
        return None

    pak = BspPak(bsp)
    rs = Resolver([pak] + live_packs, addon_packs)
    need, seen = {}, set()

    for mat in sorted(set(mats)):
        resolve_material(rs, mat, need, seen)

    if do_models:
        try:
            for mdl in sorted(bsp_static_props(bsp) | bsp_entity_models(bsp)):
                resolve_model(rs, mdl, need, seen)
        except Exception:
            pass

    if do_sky:
        try:
            sky = bsp_skyname(bsp)
            if sky:
                resolve_sky(rs, sky, need, seen)
        except Exception:
            pass

    #Never mount a pack when the other packs this map already needs have every file
    #it would supply.  Attribution above is first-in-ADDONS-order per FILE, which is
    #right for one file and wrong for the set: surf_fantasy's arbre01.vtf lands on
    #TF2, first in the list, while Momentum's mount -- needed anyway, for the models
    #that wear it -- has the same file, and mounting TF2 for two textures costs the
    #map a 147k-entry index on every load.  Biggest pack first, since dropping it
    #saves the most; a pack stays if even one of its files is only its own.
    chosen = [p for p in addon_packs if need.get(p.name)]
    for p in sorted(chosen, key=len, reverse=True):
        others = [q for q in chosen if q is not p and need.get(q.name)]
        mine = need.get(p.name)
        if not others or not mine:
            continue
        #...and only onto a copy that is the SAME FILE.  A same-path file is not the
        #same file: the first version of this prune went by path alone and moved 47
        #files on 11 maps that already drew correctly, and 25 of those 47 differ byte
        #for byte (Portal 1's concrete_modular_floor001a against Portal 2's, CS:GO's
        #train_box.mdl against Portal 2's).  That silently re-textures a working map.
        import hashlib
        home = {}
        for f in mine:
            mine_h = hashlib.sha1(p.read(f) or b"").digest()
            q = next((q for q in others
                      if q.has(f) and hashlib.sha1(q.read(f) or b"").digest() == mine_h), None)
            if q is None:
                break
            home[f] = q
        else:
            vis = need.pop("visible:" + p.name, set())
            need.pop(p.name)
            for f, q in home.items():
                need.setdefault(q.name, set()).add(f)
                if f in vis:
                    need.setdefault("visible:" + q.name, set()).add(f)

    if pak.zip:
        try:
            pak.zip.close()
        except Exception:
            pass
    return need


def specs_for(need, addons):
    """Which addon specs this map needs, in ADDONS order (stable output)."""
    out = []
    for name, _root, spec in addons:
        if need.get(name):
            out.append((name, spec))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="scan but write nothing")
    ap.add_argument("--map", help="scan one map by name and say why")
    ap.add_argument("--audit", action="store_true",
                    help="classify every map's breakage instead of writing")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-models", action="store_true")
    a = ap.parse_args()

    t0 = time.time()
    print("indexing mounted packs...")
    live = []
    for name, root in MOUNTED:
        if not os.path.isdir(root):
            print("  %-10s MISSING %s" % (name, root))
            continue
        p = Pack(name, root)
        live.append(p)
        print("  %-10s %7d files" % (name, len(p)))

    print("indexing unmounted addon packs...")
    addon_packs, addon_meta = [], []
    for name, root, spec in ADDONS:
        if not os.path.isdir(root):
            print("  %-10s not installed" % name)
            continue
        p = Pack(name, root)
        addon_packs.append(p)
        addon_meta.append((name, root, spec))
        print("  %-10s %7d files" % (name, len(p)))
    print("  %.1fs" % (time.time() - t0))

    bsps = {}
    for _n, root in MOUNTED:
        d = os.path.join(root, "maps")
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.lower().endswith(".bsp"):
                bsps.setdefault(fn[:-4], os.path.join(d, fn))

    if a.map:
        path = bsps.get(a.map)
        if not path:
            raise SystemExit("no such map: %s" % a.map)
        need = scan(path, live, addon_packs, not a.no_models)
        if need is None:
            raise SystemExit("unreadable: %s" % path)
        print("\n%s" % a.map)
        for bucket in sorted(need):
            paths = sorted(need[bucket])
            print("  [%s] %d" % (bucket, len(paths)))
            for p in paths[:40]:
                print("      %s" % p)
            if len(paths) > 40:
                print("      ...and %d more" % (len(paths) - 40))
        print("\n  dep lines: %s" %
              (", ".join(s for _n, s in specs_for(need, addon_meta)) or "none"))
        return

    print("\nscanning %d maps..." % len(bsps))
    rows, broken = [], 0
    classA, classC, skygap = [], [], []
    t1 = time.time()
    for i, (name, path) in enumerate(sorted(bsps.items())):
        if a.limit and i >= a.limit:
            break
        need = scan(path, live, addon_packs, not a.no_models)
        if need is None:
            broken += 1
            continue
        specs = specs_for(need, addon_meta)
        if specs:
            rows.append((name, [s for _n, s in specs]))
            classA.append((name, sum(len(need.get("visible:" + n, ()))
                                     for n, _s in specs)))
        if need.get("visible:-"):
            classC.append((name, len(need["visible:-"])))
        if need.get("sky:indirect") or need.get("sky:missing"):
            skygap.append((name, "indirect" if need.get("sky:indirect") else "missing"))
        if (i + 1) % 100 == 0:
            print("  %d/%d  %.0fs" % (i + 1, len(bsps), time.time() - t1))

    print("\n%d maps scanned in %.0fs, %d unreadable" %
          (len(bsps), time.time() - t1, broken))
    print("%d need at least one addon pack (%d need more than one)" %
          (len(rows), sum(1 for _n, s in rows if len(s) > 1)))
    print("%d have content NO pack supplies (unfixable by mounting)" % len(classC))
    print("%d have a skybox the engine cannot currently resolve" % len(skygap))

    if a.audit:
        print("\nworst by broken visible textures an addon would fix:")
        for n, c in sorted(classA, key=lambda kv: -kv[1])[:20]:
            print("    %-38s %d" % (n, c))
        print("\nworst with content in no pack at all:")
        for n, c in sorted(classC, key=lambda kv: -kv[1])[:20]:
            print("    %-38s %d" % (n, c))
        print("\nskybox gaps: %s" % ", ".join(
            "%s(%s)" % (n, k) for n, k in skygap[:25]))
        return
    if a.dry:
        return

    out = os.path.join(FTESURF, "data", "mapdeps.txt")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    nlines = 0
    with open(out, "w", newline="\n") as f:
        f.write("FTESURF-MAPDEPS 1\n")
        f.write("# <mapname> <fs_automount spec>   -- written by tools/mapdeps.py\n")
        f.write("# Maps whose materials, model or sky files do not all resolve\n")
        f.write("# against the packs fs_addons.txt mounts at boot.  A map with no\n")
        f.write("# line here needs nothing extra; that is most of them.\n")
        f.write("# A map MAY have more than one line -- the engine loops.\n")
        for name, specs in rows:
            for spec in specs:
                f.write("dep %s %s\n" % (name, spec))
                nlines += 1
    print("\nwrote %s (%d maps, %d dependency line(s))" % (out, len(rows), nlines))


if __name__ == "__main__":
    main()
