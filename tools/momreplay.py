"""Read Momentum Mod replays (.mtv) -- header, run stats and the player's state every tick.

  python tools/momreplay.py <file.mtv> [--ticks a:b] [--csv out.csv] [--summary]
  python tools/momreplay.py --check <dir> [--jobs N]
  parse(path) -> {"header", "stats", "tick_interval", "events", "ticks": [TickState]}

Read-only.  zstd payloads need the `zstandard` module; LZMA ones need nothing.

FORMAT (MMTV v1/v2, Momentum Mod 0.10 on Strata).  Decoded against the game's own
binaries: the recorded props and their MomTV encodings are engine.dll's registry
(0x39ea0) and encoder (0x74de0), a value's width is the server.dll SendProp of that
name, and the frame grammar is engine.dll's writer (0x761b0).  Offsets are v1; v2
inserts one byte at 0xC2, so the JSON length sits at 0xC2 (v1) or 0xC3 (v2).

  00 "MMTV"  04 u32 version  08 u64 recorded (unix ms)  10 char[64] map
  50 char[41] map SHA1 hex   79 u8 game mode  7A u8 codec 1=LZMA 2=zstd
  7B f32 tick interval  7F u64 SteamID64  87 char[32] player
  A7 u8 track type 0 main 1 stage 2 bonus  A8 u8 track number  A9 f64 run time (s)
  B1 u32 ticks  B5 u32 keyframes  B9 u32 entities  BD u8 classes
  BE u8 temp-entity classes  BF u8 sounds  C0 u8 prop-index bits  C1 u8 unknown (2)
  [v2: C2 u8 unknown]  u32 n, n bytes JSON run stats, then the payload:
  "LZMA" u32 size u32 packed, 5 props, raw LZMA1 -- or one zstd frame

  payload:
    u16 n, n x {u32 tick, u8 type, type 2: u8 major, u8 minor}
        0 timer start, 1 stop (the last tick), 2 split, 3 unknown (always first,
        at the second keyframe's tick)
    classes x {u8 id, cstr name, u8 n, n x cstr prop}
    temp-entity classes x {u8 id, cstr}, sounds x cstr
    u32 n, n bytes of {u32 server tick, varint ent, ubv class, u16 nbits, record}
    keyframes x {u32 tick, u32 offset in keyframe blob, u32 offset in delta blob}
    u32 n + keyframe blob, u32 n + delta blob

  Bitstreams are LSB-first.  ubv = Source UBitVar (6 bits, the top two add 0/4/8/28);
  varint = protobuf varint in 8-bit groups.
    frame   = bit unknown (rare), bit [ubv n, n x {varint ent, varint slot, varint serial}],
              ubv n, n x ubv slot, one record per slot, trailer, byte alignment
    record  = ubv n, n x {prop index (C0 bits), element index}, then n values
    element = m_hViewModel 2 bits; m_hMyWeapons and zone vectors ubv, where a
              zone vector's element 0 is its length (3 or 7 bits)
    trailer = bit [ubv n, n x ubv removed], bit [msg TempEntities], bit [msg Sounds],
              bit [ubv n, n x msg], bit [ubv n, n x msg]
    msg     = varint type, varint length, protobuf bytes
  A value uses its class's SendProp unless MomTV overrides it:
    tick props: 1 bit (set) + int32, relative to the frame's tick when set
    time props: 1 bit (set) + float, relative to curtime when set
    m_nSequence (view model), m_dNetworkRunTime: varint age in ticks + the value
    m_nModelIndex: 32-bit hash
  Keyframe k is the state at its tick, over each entity's creation record; a prop
  in neither is zero.  The delta blob is one frame per tick: segment 0 covers
  0..t1, segment k>0 covers t0+1..t1.  m_dNetworkRunTime is an int64 holding a
  double's bits.
"""
import argparse
import collections
import csv
import json
import lzma
import math
import os
import re
import struct
import sys
import time

try:
    import zstandard
except ImportError:
    zstandard = None

_F = struct.Struct("<f")
_I = struct.Struct("<I")

FL_ONGROUND, FL_DUCKING = 1, 2
IN_JUMP, IN_DUCK, IN_MOVELEFT, IN_MOVERIGHT = 2, 4, 512, 1024


class Bits:
    __slots__ = ("d", "p", "n")

    def __init__(self, data, pos=0):
        self.d = data
        self.p = pos
        self.n = len(data) * 8

    def u(self, k):
        if not k:
            return 0
        p = self.p
        e = p + k
        if e > self.n:
            raise EOFError("read past end of stream")
        self.p = e
        return (int.from_bytes(self.d[p >> 3:(e + 7) >> 3], "little") >> (p & 7)) & ((1 << k) - 1)

    def s(self, k):
        v = self.u(k)
        return v - (1 << k) if v >> (k - 1) else v

    def ubv(self):
        v = self.u(6)
        sel = v & 48
        if sel == 16:
            v = (v & 15) | (self.u(4) << 4)
        elif sel == 32:
            v = (v & 15) | (self.u(8) << 4)
        elif sel == 48:
            v = (v & 15) | (self.u(28) << 4)
        return v

    def var(self):
        v = sh = 0
        while True:
            x = self.u(8)
            v |= (x & 0x7F) << sh
            sh += 7
            if not x & 0x80 or sh > 63:
                return v

    def f32(self):
        return _F.unpack(_I.pack(self.u(32)))[0]

    def coord(self):
        # engine.dll ReadBitCoord: Strata widened the integer part to 16 bits
        i = self.u(1)
        f = self.u(1)
        if not (i or f):
            return 0.0
        neg = self.u(1)
        v = (self.u(16) + 1 if i else 0) + (self.u(5) / 32.0 if f else 0.0)
        return -v if neg else v


# ---------------------------------------------------------------------------
# prop values

def U(n):
    return lambda r: r.u(n)


def S(n):
    return lambda r: r.s(n)


def F32(r):
    return r.f32()


def QF(n, lo, hi):
    m = (1 << n) - 1
    return lambda r: lo + (hi - lo) * r.u(n) / m


def ANG(n):
    return QF(n, 0.0, 360.0)


def VEC(c, k=3):
    return lambda r: tuple(c(r) for _ in range(k))


def CELL(n):
    return lambda r: r.u(n) + r.u(5) / 32.0


def COORD(r):
    return r.coord()


def STR(r):
    n = r.u(9)
    return bytes(r.u(8) for _ in range(n)).decode("utf-8", "replace")


def I64(r):
    neg = r.u(1)
    v = r.u(32) | (r.u(31) << 32)
    return -v if neg else v


class Tick(tuple):
    """(set, value): set means value is relative to the frame's tick."""


def TICK(inner):
    return lambda r: Tick((r.u(1), inner(r)))


def TIME(inner):
    return lambda r: Tick((r.u(1), inner(r)))


class Aged(tuple):
    """(age in ticks, value)."""


def AGE(inner):
    return lambda r: Aged((r.var(), inner(r)))


EH = U(23)      # SendPropEHandle, server.dll 0x465b50
HASH = U(32)    # MomTV model-index hash
TK = TICK(S(32))
# SendPropFloat narrows a ROUNDDOWN range by one step at the top (server.dll 0x497cd0)
VIEWXY = QF(8, -32.0, 32.0 - 64.0 / 256)

BASE = {
    "m_bSimulatedEveryTick": U(1), "m_fEffects": U(15), "m_nModelIndex": HASH, "m_nRenderMode": U(8),
    "m_clrRender": U(32), "moveparent": EH, "m_hOwnerEntity": EH, "m_hOwner": EH,
    "m_bClientSideAnimation": U(1), "m_cellbits": U(5), "m_cellX": U(12), "m_cellY": U(12),
    "m_cellZ": U(12), "m_vecOrigin": VEC(CELL(5)), "m_angRotation": VEC(ANG(13)),
    "m_vecMinsPreScaled": VEC(F32), "m_vecMaxsPreScaled": VEC(F32),
}
PLAYER = {
    "m_vecOrigin": VEC(F32, 2), "m_vecOrigin[2]": F32, "m_nBody": S(32), "m_clrModelPrimary": U(32),
    "m_clrModelSecondary": U(32), "m_fFlags": U(11), "m_angEyeAngles[0]": ANG(11),
    "m_angEyeAngles[1]": ANG(11), "m_ubEFNoInterpParity": U(2), "m_vecViewOffset[0]": VIEWXY,
    "m_vecViewOffset[1]": VIEWXY, "m_vecViewOffset[2]": QF(10, 0.0, 128.0), "m_hViewModel": EH,
    "m_vecVelocity[0]": F32, "m_vecVelocity[1]": F32, "m_vecVelocity[2]": F32,
    "m_flGroundPositionZ": F32, "m_nPhysicalButtons": S(32), "m_afButtonDisabled": S(32),
    "m_afButtonForced": S(32), "m_nButtonsToggled": S(32), "m_iLandTick": TK, "m_iJumpTick": TK,
    "m_iEarlyJumpTiming": S(32), "m_hMyWeapons": EH, "m_hActiveWeapon": EH, "m_hPrimaryTimer": EH,
    "m_dropTeleportState": U(4), "wishVel": VEC(F32, 2), "wishVel[2]": F32, "moveStatus": U(8),
    "acceleration": F32, "maxspeed": F32, "friction": F32, "hasteEndTick": TK,
    "damageBoostEndTick": TK, "slickEndTick": TK, "flightEndTick": TK, "defragTimerEndTick": TK,
    "defragTimerFlags": U(8), "m_bCanAirJump": U(1), "m_bRefreshAirJumpOnLand": U(1),
    "m_bCanDoubleJump": U(1), "m_bRefreshDoubleJumpOnLand": U(1),
}
VIEWMODEL = {
    "m_hWeapon": EH, "m_nBody": S(32), "m_nSkin": S(10), "m_nSequence": AGE(U(8)),
    "m_nViewModelIndex": U(2), "m_flPlaybackRate": QF(8, -4.0 + 16.0 / 256, 12.0),
    "m_nAnimationParity": U(3), "m_nNewSequenceParity": U(3), "m_nResetEventsParity": U(3),
    "m_nMuzzleFlashParity": U(2), "m_bShouldIgnoreOffsetAndAccuracy": U(1),
}
WEAPON = {
    "m_flNextPrimaryAttack": F32, "m_flNextSecondaryAttack": F32, "m_flTimeWeaponIdle": F32,
    "m_nNextThinkTick": TK, "m_iState": U(2), "m_iClip1": U(8), "m_bBurstMode": U(1),
    "m_flSmackTime": TIME(F32), "m_fInSpecialReload": U(2), "m_bRedraw": U(1), "m_bPinPulled": U(1),
    "m_fThrowTime": TIME(F32), "m_iFireAngle": U(4), "m_bBeamActive": U(1),
}
TIMER = {
    "m_trackId": U(16), "m_state": U(8), "m_dNetworkRunTime": AGE(I64), "m_nMajorNum": U(8),
    "m_nMinorNum": U(8), "m_eRunStyle": U(8), "m_nSegmentsCount": U(8),
    "m_nSegmentCheckpointsCount": U(8), "m_limitedRunSplitsB64": STR,
}
ZONE = {
    "m_trackIds": S(16), "m_renderMode": S(32), "m_bCanSwitchPrimaryTimer": U(1),
    "m_renderPoints": VEC(F32, 2), "m_flRenderBottom": F32, "m_flRenderHeight": F32,
    "m_flRenderSafeHeight": F32,
}
PROJECTILE = {"m_angRotation": VEC(ANG(6))}
CLASS_SPECS = {
    "CMomentumPlayer": PLAYER, "CMomentumViewModel": VIEWMODEL, "CMomentumTimerInstance": TIMER,
    "CMomentumZoneRegion": ZONE,
    "CSpriteTrail": {"m_flLifeTime": F32, "m_flStartWidth": F32, "m_flEndWidth": F32},
    "CFuncRotating": {"m_vecOrigin": VEC(COORD), "m_angRotation[0]": ANG(13),
                      "m_angRotation[1]": ANG(13), "m_angRotation[2]": ANG(13)},
    "CFuncMoveLinear": {"m_strSoundStart": STR, "m_strSoundStop": STR},
    "CMomPickup": {"m_nBody": S(32), "m_nSequence": U(12)},
    "CMomRocket": PROJECTILE, "CMomDFRocket": PROJECTILE, "CMomDFPlasma": PROJECTILE,
    "CMomDFBFGRocket": PROJECTILE, "CMomDFGrenade": PROJECTILE,
}
ARRAY_BITS = {("CMomentumPlayer", "m_hViewModel"): 2}
ARRAY_UBV = {("CMomentumPlayer", "m_hMyWeapons")}
UTLVEC_LEN = {("CMomentumZoneRegion", "m_trackIds"): 3, ("CMomentumZoneRegion", "m_renderMode"): 3,
              ("CMomentumZoneRegion", "m_bCanSwitchPrimaryTimer"): 3,
              ("CMomentumZoneRegion", "m_renderPoints"): 7}
# weapon classes share WEAPON; anything else not listed falls back to BASE
WEAPON_PREFIXES = ("CMomentum",)


class FormatError(Exception):
    pass


def spec(cls, prop):
    t = CLASS_SPECS.get(cls)
    if t is None and cls.startswith(WEAPON_PREFIXES):
        t = WEAPON
    if t is not None and prop in t:
        return t[prop]
    return BASE.get(prop)


class ClassDec:
    """Decodes one class's records: entries first, then values in entry order."""

    def __init__(self, cid, name, props, idx_bits):
        self.cid, self.name, self.props, self.idx_bits = cid, name, props, idx_bits
        self.index = {p: i for i, p in enumerate(props)}
        self.rd = [spec(name, p) for p in props]
        self.elem = []
        for p in props:
            key = (name, p)
            if key in ARRAY_BITS:
                self.elem.append((0, ARRAY_BITS[key]))
            elif key in ARRAY_UBV:
                self.elem.append((1, 0))
            elif key in UTLVEC_LEN:
                self.elem.append((2, UTLVEC_LEN[key]))
            else:
                self.elem.append(None)

    def read(self, r):
        ib = self.idx_bits
        nprops = len(self.props)
        ents = []
        for _ in range(r.ubv()):
            i = r.u(ib)
            if i >= nprops:
                raise FormatError("prop index %d >= %d in %s" % (i, nprops, self.name))
            e = self.elem[i]
            ents.append((i, None if e is None else (r.u(e[1]) if e[0] == 0 else r.ubv())))
        out = []
        for i, el in ents:
            e = self.elem[i]
            if e is not None and e[0] == 2 and el == 0:
                v = r.u(e[1])
            else:
                rd = self.rd[i]
                if rd is None:
                    raise FormatError("no decoder for %s.%s" % (self.name, self.props[i]))
                v = rd(r)
            out.append((i, el, v))
        return out


def read_msg(r):
    t = r.var()
    n = r.var()
    return (t, bytes(r.u(8) for _ in range(n)))


def read_trailer(r):
    out = {}
    if r.u(1):
        out["removed"] = [r.ubv() for _ in range(r.ubv())]
    if r.u(1):
        out["tempents"] = read_msg(r)
    if r.u(1):
        out["sounds"] = read_msg(r)
    if r.u(1):
        out["messages"] = [read_msg(r) for _ in range(r.ubv())]
    if r.u(1):
        out["entmsgs"] = [read_msg(r) for _ in range(r.ubv())]
    return out


def read_frame(data, pos, slot_ent, ent_dec):
    """Frame at byte pos -> (records, trailer, next byte pos); updates slot_ent."""
    r = Bits(data, pos * 8)
    r.u(1)
    if r.u(1):
        for _ in range(r.ubv()):
            e = r.var()
            s = r.var()
            r.var()
            slot_ent[s] = e
    slots = [r.ubv() for _ in range(r.ubv())]
    recs = []
    for s in slots:
        ent = slot_ent.get(s)
        dec = ent_dec.get(ent)
        if dec is None:
            raise FormatError("slot %d has no entity/class" % s)
        recs.append((ent, dec, dec.read(r)))
    return recs, read_trailer(r), (r.p + 7) >> 3


# ---------------------------------------------------------------------------
# container

def cstr(b, pos, n=None):
    end = b.index(b"\0", pos) if n is None else pos + n
    return b[pos:end].split(b"\0")[0].decode("utf-8", "replace"), end + (1 if n is None else 0)


def read_header(b):
    if b[:4] != b"MMTV":
        raise FormatError("not an MMTV file")
    ver = _I.unpack_from(b, 4)[0]
    h = {
        "version": ver,
        "recorded_ms": struct.unpack_from("<Q", b, 0x08)[0],
        "map": cstr(b, 0x10, 64)[0],
        "map_sha1": cstr(b, 0x50, 41)[0],
        "game_mode": b[0x79],
        "codec": b[0x7A],
        "tick_interval": _F.unpack_from(b, 0x7B)[0],
        "steam_id": struct.unpack_from("<Q", b, 0x7F)[0],
        "player": cstr(b, 0x87, 32)[0],
        "track_type": b[0xA7],
        "track_number": b[0xA8],
        "run_time": struct.unpack_from("<d", b, 0xA9)[0],
        "ticks": _I.unpack_from(b, 0xB1)[0],
        "keyframes": _I.unpack_from(b, 0xB5)[0],
        "entities": _I.unpack_from(b, 0xB9)[0],
        "classes": b[0xBD],
        "tempent_classes": b[0xBE],
        "sounds": b[0xBF],
        "prop_index_bits": b[0xC0],
        "unknown_c1": b[0xC1],
    }
    jo = 0xC2
    if ver >= 2:
        h["unknown_c2"] = b[0xC2]
        jo = 0xC3
    if ver not in (1, 2):
        raise FormatError("unknown MMTV version %d" % ver)
    jl = _I.unpack_from(b, jo)[0]
    h["json_offset"] = jo + 4
    h["payload_offset"] = jo + 4 + jl
    return h


def decompress(b, h):
    e = h["payload_offset"]
    if h["codec"] == 1:
        if b[e:e + 4] != b"LZMA":
            raise FormatError("codec byte says LZMA, payload starts %r" % b[e:e + 4])
        size, packed = struct.unpack_from("<II", b, e + 4)
        x = b[e + 12]
        lc, x = x % 9, x // 9
        lp, pb = x % 5, x // 5
        dec = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=[
            {"id": lzma.FILTER_LZMA1, "lc": lc, "lp": lp, "pb": pb,
             "dict_size": _I.unpack_from(b, e + 13)[0]}])
        d = dec.decompress(b[e + 17:e + 17 + packed], size)
        if len(d) != size:
            raise FormatError("LZMA gave %d of %d bytes" % (len(d), size))
        return d
    if h["codec"] == 2:
        if zstandard is None:
            raise RuntimeError("zstd payload: this Python has no 'zstandard' module")
        return zstandard.ZstdDecompressor().decompress(b[e:], max_output_size=1 << 31)
    raise FormatError("unknown codec %d" % h["codec"])


def layout(d, h):
    L = {}
    nev = struct.unpack_from("<H", d, 0)[0]
    pos = 2
    evs = []
    for _ in range(nev):
        t, ty = struct.unpack_from("<IB", d, pos)
        pos += 5
        args = ()
        if ty == 2:
            args = (d[pos], d[pos + 1])
            pos += 2
        evs.append((t, ty, args))
    L["events"] = evs
    classes = []
    for _ in range(h["classes"]):
        cid = d[pos]
        name, pos = cstr(d, pos + 1)
        n = d[pos]
        pos += 1
        props = []
        for _ in range(n):
            p, pos = cstr(d, pos)
            props.append(p)
        classes.append((cid, name, props))
    L["classes"] = classes
    L["tempents"] = []
    for _ in range(h["tempent_classes"]):
        name, npos = cstr(d, pos + 1)
        L["tempents"].append((d[pos], name))
        pos = npos
    L["sounds"] = []
    for _ in range(h["sounds"]):
        s, pos = cstr(d, pos)
        L["sounds"].append(s)
    n = _I.unpack_from(d, pos)[0]
    L["creation"] = d[pos + 4:pos + 4 + n]
    pos += 4 + n
    L["index"] = [struct.unpack_from("<III", d, pos + 12 * k) for k in range(h["keyframes"])]
    pos += 12 * h["keyframes"]
    n = _I.unpack_from(d, pos)[0]
    L["kf"] = d[pos + 4:pos + 4 + n]
    pos += 4 + n
    n = _I.unpack_from(d, pos)[0]
    L["delta"] = d[pos + 4:pos + 4 + n]
    pos += 4 + n
    if pos != len(d):
        raise FormatError("payload layout ends at %d of %d bytes" % (pos, len(d)))
    return L


def creation_records(sec):
    """-> [(server tick, entity, class id, bit start, nbits)]"""
    p = 0
    out = []
    while p < len(sec):
        tick = _I.unpack_from(sec, p)[0]
        r = Bits(sec, (p + 4) * 8)
        ent = r.var()
        cid = r.ubv()
        n = r.u(16)
        out.append((tick, ent, cid, r.p, n))
        p = (r.p + n + 7) >> 3
    if p != len(sec):
        raise FormatError("creation records overrun their section")
    return out


# ---------------------------------------------------------------------------
# replay

TickState = collections.namedtuple("TickState", [
    "tick", "x", "y", "z", "pitch", "yaw", "view_x", "view_y", "view_z", "vx", "vy", "vz",
    "flags", "buttons", "land_tick", "jump_tick", "timer_state", "track_type", "track_number",
    "major", "minor", "run_time", "wish_x", "wish_y", "wish_z", "noint"])

PLAYER_FIELDS = ("m_vecOrigin", "m_vecOrigin[2]", "m_angEyeAngles[0]", "m_angEyeAngles[1]",
                 "m_vecViewOffset[0]", "m_vecViewOffset[1]", "m_vecViewOffset[2]",
                 "m_vecVelocity[0]", "m_vecVelocity[1]", "m_vecVelocity[2]", "m_fFlags",
                 "m_nPhysicalButtons", "m_iLandTick", "m_iJumpTick",
                 "wishVel", "wishVel[2]", "m_ubEFNoInterpParity")
# None where the player's class does not record the prop (the 33-prop format has no
# wishVel), as against 0 for "recorded, zero".  noint is m_ubEFNoInterpParity, which
# steps when the server teleports the player: 7555 of the wishvel corpus's 7766
# in-run steps are jumps the velocity does not cover.
OPTIONAL_FIELDS = ("wishVel", "wishVel[2]", "m_ubEFNoInterpParity")


def _signed_angle(a):
    return a - 360.0 if a > 180.0 else a


def _tick_value(v, tick):
    """A tick prop as an absolute replay tick, or None when unset (stored as <= 0)."""
    rel, x = v
    if rel:
        return x + tick
    return x if x > 0 else None


class Replay:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as fh:
            b = fh.read()
        self.header = h = read_header(b)
        raw = b[h["json_offset"]:h["payload_offset"]].rstrip(b"\0")
        self.stats = json.loads(raw.decode("utf-8", "replace")) if raw else {}
        self.tick_interval = h["tick_interval"]
        self.L = L = layout(decompress(b, h), h)
        self.events = L["events"]
        self.classes = {cid: ClassDec(cid, name, props, h["prop_index_bits"])
                        for cid, name, props in L["classes"]}
        self.ent_dec = {}
        self.baseline = {}
        self.created = creation_records(L["creation"])
        sec = L["creation"]
        for tick, ent, cid, start, n in self.created:
            dec = self.classes.get(cid)
            if dec is None:
                raise FormatError("creation record names unknown class %d" % cid)
            if n == 0:
                # empty records occur (8 in the corpus); a non-empty one for the same entity wins
                self.ent_dec.setdefault(ent, dec)
                self.baseline.setdefault(ent, {})
                continue
            r = Bits(sec, start)
            vals = dec.read(r)
            if r.p - start != n:
                raise FormatError("creation record for entity %d (%s): %d bits decoded of %d"
                                  % (ent, dec.name, r.p - start, n))
            self.ent_dec[ent] = dec
            self.baseline[ent] = {(i, el): v for i, el, v in vals}
        self.player_ent = self._pick_player()

    def _pick_player(self):
        best = None
        for ent, dec in self.ent_dec.items():
            if dec.name == "CMomentumPlayer":
                size = len(self.baseline.get(ent, {}))
                if best is None or size > best[0] or (size == best[0] and ent < best[1]):
                    best = (size, ent)
        return None if best is None else best[1]

    def segments(self):
        idx = self.L["index"]
        for k, (t0, ko, do) in enumerate(idx):
            last = k + 1 == len(idx)
            yield (k, t0, ko, len(self.L["kf"]) if last else idx[k + 1][1], do,
                   len(self.L["delta"]) if last else idx[k + 1][2], None if last else idx[k + 1][0])

    def frames(self, check=None):
        """Yield (tick, state, trailer) per delta frame; state maps entity -> {(prop, elem): value}.

        Tick, time and aged props are stored resolved: absolute replay tick, replay
        time, and (tick the value was set, value).  Each keyframe restarts the state.
        check, if a dict, counts keyframe props that the deltas before it did not
        reproduce ("kf_props", "kf_mismatch", "kf_examples").
        """
        kf, delta = self.L["kf"], self.L["delta"]
        ti = self.tick_interval
        state = None
        for k, t0, ko, kend, do, dend, t1 in self.segments():
            slot_ent = {}
            recs, _, end = read_frame(kf, ko, slot_ent, self.ent_dec)
            if end != kend:
                raise FormatError("keyframe %d: %d bytes decoded of %d" % (k, end - ko, kend - ko))
            prev = state
            state = {e: dict(v) for e, v in self.baseline.items()}
            self._apply(state, recs, t0, ti)
            if check is not None and prev is not None:
                for ent, dec, vals in recs:
                    for i, el, _ in vals:
                        check["kf_props"] = check.get("kf_props", 0) + 1
                        a = prev.get(ent, {}).get((i, el))
                        b = state[ent][(i, el)]
                        if a != b and not (a != a and b != b):
                            check["kf_mismatch"] = check.get("kf_mismatch", 0) + 1
                            ex = check.setdefault("kf_examples", [])
                            if len(ex) < 3:
                                ex.append((t0, dec.name, dec.props[i], el, a, b))
            o = do
            tick = t0 if k == 0 else t0 + 1
            while o < dend:
                recs, tr, o = read_frame(delta, o, slot_ent, self.ent_dec)
                self._apply(state, recs, tick, ti)
                yield tick, state, tr
                tick += 1
            if o != dend:
                raise FormatError("segment %d overran its frames by %d bytes" % (k, o - dend))
            if t1 is not None and tick != t1 + 1:
                raise FormatError("segment %d holds %d frames, index says %d"
                                  % (k, tick - (t0 if k == 0 else t0 + 1), t1 - t0 + (k == 0)))

    @staticmethod
    def _apply(state, recs, tick, ti):
        for ent, dec, vals in recs:
            st = state.get(ent)
            if st is None:
                st = state[ent] = {}
            for i, el, v in vals:
                if isinstance(v, Tick):
                    if isinstance(v[1], float):
                        v = (v[1] + tick * ti) if v[0] else (v[1] if v[1] > 0 else None)
                    else:
                        v = _tick_value(v, tick)
                elif isinstance(v, Aged):
                    v = (tick - v[0], v[1])
                st[(i, el)] = v

    def ticks(self, check=None):
        """Per-tick TickState for the player (and its track's timer, when there is one)."""
        dec = self.ent_dec.get(self.player_ent)
        if dec is None:
            return []
        pi = [dec.index.get(n) for n in PLAYER_FIELDS]
        timer = self._timer_ent()
        tdec = self.ent_dec.get(timer)
        ti = self.tick_interval
        out = []
        tstate_tick = last_tstate = None
        # (value bits, tick it was set): the set tick moves only when the value does --
        # in 10 of the corpus's files the timer re-sends an unchanged value with age 0
        # every tick, which would otherwise pin the clock to the current tick
        rt_base = None
        # a prop missing from the creation record and every update is at its zero default:
        # 2253 of 2313 first appearances in sampled deltas were non-zero, and the 60 zeros
        # were 11-bit angles, where a float change can quantise to the same 0
        zero = ((0.0, 0.0), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0, None, None,
                (0.0, 0.0), 0.0, 0)
        absent = [i is None and n in OPTIONAL_FIELDS for i, n in zip(pi, PLAYER_FIELDS)]
        for tick, state, _ in self.frames(check):
            st = state.get(self.player_ent, {})
            g = [None if ab else (st.get((i, None), z) if i is not None else z)
                 for i, z, ab in zip(pi, zero, absent)]
            xy = g[0]
            wv = g[14]
            pitch, yaw = _signed_angle(g[2]), _signed_angle(g[3])
            tt = tn = maj = mnr = tstate = rt = None
            if tdec is not None:
                ts = state.get(timer, {})
                tv = {tdec.props[i]: v for (i, el), v in ts.items()}
                tstate = tv.get("m_state", 0)
                tid = tv.get("m_trackId")
                if tid is not None:
                    tt, tn = tid & 0xFF, tid >> 8
                maj, mnr = tv.get("m_nMajorNum", 0), tv.get("m_nMinorNum", 0)
                if tstate != last_tstate:
                    tstate_tick, last_tstate = tick, tstate
                nrt = tv.get("m_dNetworkRunTime")
                if nrt is not None:
                    if rt_base is None or rt_base[0] != nrt[1]:
                        rt_base = (nrt[1], nrt[0])
                    bits, base_tick = rt_base
                    base = struct.unpack("<d", struct.pack("<q", bits))[0]
                    if tstate == 2:
                        rt = base + (tick - base_tick) * ti
                    elif tstate == 3:
                        rt = base + (tstate_tick - base_tick) * ti
            out.append(TickState(tick, xy[0], xy[1], g[1], pitch, yaw, g[4], g[5], g[6], g[7], g[8],
                                 g[9], g[10], g[11], g[12], g[13], tstate, tt, tn, maj, mnr, rt,
                                 None if wv is None else wv[0], None if wv is None else wv[1],
                                 g[15], g[16]))
        return out

    def _timer_ent(self):
        """The timer instance whose m_trackId is the header's track ((number << 8) | type)."""
        want = (self.header["track_number"] << 8) | self.header["track_type"]
        found = []
        for ent, dec in self.ent_dec.items():
            if dec.name != "CMomentumTimerInstance":
                continue
            i = dec.index.get("m_trackId")
            tid = self.baseline.get(ent, {}).get((i, None))
            found.append((tid == want, ent))
        found.sort(key=lambda x: (not x[0], x[1]))
        return found[0][1] if found and found[0][0] else None


def parse(path):
    """-> dict: header, stats (the JSON), tick_interval, events, ticks (list of TickState)."""
    rep = Replay(path)
    return {"header": rep.header, "stats": rep.stats, "tick_interval": rep.tick_interval,
            "events": rep.events, "ticks": rep.ticks(), "replay": rep}


# ---------------------------------------------------------------------------
# validation: numbers only, nothing here decides a verdict

def _pct(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * (len(xs) - 1) + 0.5))]


def run_window(events):
    """(start tick, stop tick) of the last start before the stop event, or None."""
    stops = [t for t, ty, _ in events if ty == 1]
    if not stops:
        return None
    starts = [t for t, ty, _ in events if ty == 0 and t <= stops[-1]]
    return (starts[-1], stops[-1]) if starts else None


def validate(rep, ticks):
    h, ti = rep.header, rep.tick_interval
    v = {"ticks_decoded": len(ticks), "ticks_header": h["ticks"],
         "first_tick": ticks[0].tick if ticks else None, "last_tick": ticks[-1].tick if ticks else None}
    win = v["window"] = run_window(rep.events)
    by = {t.tick: t for t in ticks}
    ts = rep.stats.get("trackStats") or {}

    # 1. origin step over the interval against the stored velocity.  Horizontal is
    # compared whole; vertical is kept signed on airborne ticks, because Source applies
    # half the gravity after the move (expect +sv_gravity * interval / 2 there).
    en, es, ez = [], [], []
    for a, b in zip(ticks, ticks[1:]):
        dx, dy, dz = (b.x - a.x) / ti, (b.y - a.y) / ti, (b.z - a.z) / ti
        en.append(math.hypot(dx - b.vx, dy - b.vy))
        es.append(math.hypot(dx - a.vx, dy - a.vy))
        if not (a.flags | b.flags) & FL_ONGROUND:
            ez.append(dz - b.vz)
    v["vel_pairs"], v["vel_air_pairs"] = len(en), len(ez)
    v["vel_next_med"], v["vel_next_p99"] = _pct(en, 0.5), _pct(en, 0.99)
    v["vel_same_med"], v["vel_same_p99"] = _pct(es, 0.5), _pct(es, 0.99)
    v["vel_next_over1"] = sum(1 for e in en if e > 1.0)
    v["vel_z_air_med"] = _pct(ez, 0.5)
    med = v["vel_z_air_med"]
    v["vel_z_air_near"] = sum(1 for e in ez if abs(e - med) < 0.01) if ez else 0

    # 2. speed, ticks, time
    run = [t for t in ticks if win and win[0] <= t.tick <= win[1]]
    v["hspeed_max"] = max((math.hypot(t.vx, t.vy) for t in run), default=None)
    v["speed_max"] = max((math.sqrt(t.vx * t.vx + t.vy * t.vy + t.vz * t.vz) for t in run), default=None)
    v["json_hspeed_max"] = ts.get("maxHorizontalSpeed")
    v["json_speed_max"] = ts.get("maxOverallSpeed")
    # the JSON's own samples: start velocity at the start tick; each split's velocity
    # and timeReached at its split event (type 2, args (segment, subsegment))
    vs = vn = 0
    split_off = collections.Counter()
    segs = rep.stats.get("segments") or []
    if win:
        split = {a: t for t, ty, a in rep.events if ty == 2}
        want = [(win[0], segs[0].get("effectiveStartVelocity"), None)] if segs else []
        for si, seg in enumerate(segs):
            for sub in seg.get("subsegments") or []:
                tick = split.get((si + 1, sub.get("minorNum")))
                if tick is not None:
                    want.append((tick, sub.get("velocityWhenReached"), sub.get("timeReached")))
        for tick, vel, reached in want:
            t = by.get(tick)
            if t is not None and vel and len(vel) == 3:
                vn += 1
                vs += [t.vx, t.vy, t.vz] == [float(x) for x in vel]
            if reached is not None and t is not None and t.run_time is not None:
                # in whole ticks; 1e-4 s off a tick boundary means it is not on one
                d = (t.run_time - reached) / ti
                split_off[round(d) if abs(d - round(d)) * ti < 1e-4 else "off-grid"] += 1
    v["json_vel_samples"], v["json_vel_exact"] = vn, vs
    v["json_split_offsets"] = split_off
    v["time_header"] = h["run_time"]
    v["time_events"] = (win[1] - win[0]) * ti if win else None
    # in ticks, to the half tick: the header time is not always on the tick grid
    v["time_events_off"] = math.floor((v["time_events"] - h["run_time"]) / ti * 2 + 0.5) / 2 if win else None
    end = by.get(win[1]) if win else None
    v["time_timer"] = end.run_time if end else None
    m = re.search(r"-(\d+\.\d+)\.mtv$", os.path.basename(rep.path))
    v["time_filename"] = float(m.group(1)) if m else None

    # 3. jumps and strafes inside the run
    jumps = press = keys = dirs = 0
    lastdir = prev = None
    for t in ticks:
        if prev is not None and win and win[0] < t.tick <= win[1]:
            if t.jump_tick is not None and t.jump_tick != prev.jump_tick:
                jumps += 1
            b0, b1 = prev.buttons, t.buttons
            if b1 & IN_JUMP and not b0 & IN_JUMP:
                press += 1
            keys += bool(b1 & IN_MOVELEFT and not b0 & IN_MOVELEFT)
            keys += bool(b1 & IN_MOVERIGHT and not b0 & IN_MOVERIGHT)
            side = b1 & (IN_MOVELEFT | IN_MOVERIGHT)
            if side in (IN_MOVELEFT, IN_MOVERIGHT) and side != lastdir:
                dirs += 1
                lastdir = side
        prev = t
    v["jumps"], v["jump_presses"], v["json_jumps"] = jumps, press, ts.get("jumps")
    v["strafe_keys"], v["strafe_dirs"], v["json_strafes"] = keys, dirs, ts.get("strafes")

    # 4. angles
    p = [t.pitch for t in ticks]
    y = [t.yaw for t in ticks]
    v["pitch_range"] = (min(p), max(p)) if p else None
    v["yaw_range"] = (min(y), max(y)) if y else None
    dy = [abs((b - a + 180.0) % 360.0 - 180.0) for a, b in zip(y, y[1:])]
    v["yaw_step_p99"], v["yaw_step_max"] = _pct(dy, 0.99), max(dy, default=None)
    v["pitch_step_max"] = max((abs(b - a) for a, b in zip(p, p[1:])), default=None)

    # 5. ground flag against vz and the land tick; duck flag against view height
    g = [t for t in ticks if t.flags & FL_ONGROUND]
    v["ground_ticks"], v["ground_vz0"] = len(g), sum(1 for t in g if t.vz == 0.0)
    lands = agree = 0
    for a, b in zip(ticks, ticks[1:]):
        if b.land_tick is not None and b.land_tick != a.land_tick:
            lands += 1
            agree += bool(b.land_tick == b.tick and b.flags & FL_ONGROUND and not a.flags & FL_ONGROUND)
    v["land_changes"], v["land_agree"] = lands, agree
    for key, want in (("view_z_ducked", True), ("view_z_standing", False)):
        c = collections.Counter(round(t.view_z, 3) for t in ticks if bool(t.flags & FL_DUCKING) == want)
        v[key] = c.most_common(3)
    # the button bits checked against a flag the game sets from them
    v["duck_ticks"] = sum(1 for t in ticks if t.flags & FL_DUCKING)
    v["duck_held"] = sum(1 for t in ticks if t.flags & FL_DUCKING and t.buttons & IN_DUCK)
    v["held_ticks"] = sum(1 for t in ticks if t.buttons & IN_DUCK)
    return v


# ---------------------------------------------------------------------------
# CLI

def _f(x, fmt="%.3f"):
    return "-" if x is None else (fmt % x if isinstance(x, float) else str(x))


def print_header(rep, w=sys.stdout.write):
    h = rep.header
    w("%s\n" % rep.path)
    for k in ("version", "codec", "map", "map_sha1", "game_mode", "player", "steam_id", "track_type",
              "track_number", "run_time", "tick_interval", "ticks", "keyframes", "entities",
              "classes", "tempent_classes", "sounds", "prop_index_bits"):
        w("  %-16s %s\n" % (k, h[k]))
    w("  %-16s %s (%s UTC)\n" % ("recorded_ms", h["recorded_ms"], time.strftime(
        "%Y-%m-%d %H:%M:%S", time.gmtime(h["recorded_ms"] / 1000.0))))
    w("  %-16s %s\n" % ("events", " ".join("%d:%d%s" % (t, ty, "(%d,%d)" % a if a else "")
                                         for t, ty, a in rep.events)))
    w("  %-16s %s\n" % ("prop tables", ", ".join("%s(%d)" % (d.name, len(d.props))
                                              for d in rep.classes.values())))
    if rep.stats.get("trackStats"):
        w("  %-16s %s\n" % ("trackStats", json.dumps(rep.stats["trackStats"], sort_keys=True)))


def print_summary(v, w=sys.stdout.write):
    w("  ticks            decoded %d (%s..%s), header %d, run window %s\n"
      % (v["ticks_decoded"], v["first_tick"], v["last_tick"], v["ticks_header"], v["window"]))
    w("  velocity xy      |d(origin)/dt - v[t+1]| median %s p99 %s (%d of %d pairs over 1 u/s);"
      " against v[t] median %s p99 %s\n"
      % (_f(v["vel_next_med"], "%.4f"), _f(v["vel_next_p99"]), v["vel_next_over1"], v["vel_pairs"],
         _f(v["vel_same_med"], "%.4f"), _f(v["vel_same_p99"])))
    w("  velocity z       in the air, dz/dt - vz[t+1] median %s (%d of %d within 0.01 of it)\n"
      % (_f(v["vel_z_air_med"], "%.4f"), v["vel_z_air_near"], v["vel_air_pairs"]))
    w("  max speed        horizontal %s (json %s), overall %s (json %s)\n"
      % (_f(v["hspeed_max"]), _f(v["json_hspeed_max"]), _f(v["speed_max"]), _f(v["json_speed_max"])))
    w("  json samples     velocity %d of %d (start + splits) equal to the decoded one on that tick;"
      " timer run time at a split event minus its timeReached, in ticks: %s\n"
      % (v["json_vel_exact"], v["json_vel_samples"], dict(v["json_split_offsets"]) or "no splits"))
    w("  run time         header %s, timer %s, events %s, filename %s\n"
      % (_f(v["time_header"], "%.4f"), _f(v["time_timer"], "%.4f"), _f(v["time_events"], "%.4f"),
         _f(v["time_filename"])))
    w("  jumps            jump-tick changes %d, IN_JUMP presses %d, json %s\n"
      % (v["jumps"], v["jump_presses"], _f(v["json_jumps"])))
    w("  strafes          key presses %d, side changes %d, json %s\n"
      % (v["strafe_keys"], v["strafe_dirs"], _f(v["json_strafes"])))
    w("  angles           pitch %s, yaw %s, yaw step p99 %s max %s, pitch step max %s\n"
      % (v["pitch_range"] and "%.3f..%.3f" % v["pitch_range"],
         v["yaw_range"] and "%.3f..%.3f" % v["yaw_range"],
         _f(v["yaw_step_p99"]), _f(v["yaw_step_max"]), _f(v["pitch_step_max"])))
    w("  ground           %d ticks on ground, %d with vz == 0; %d land-tick changes, %d on a 0->1 edge\n"
      % (v["ground_ticks"], v["ground_vz0"], v["land_changes"], v["land_agree"]))
    w("  view z           ducked %s, standing %s\n" % (v["view_z_ducked"], v["view_z_standing"]))
    w("  duck             %d ticks ducked, %d of them with IN_DUCK held; IN_DUCK held on %d ticks\n"
      % (v["duck_ticks"], v["duck_held"], v["held_ticks"]))


def _row(t):
    # 9 significant digits round-trip a float32
    return [("%.9g" % x) if isinstance(x, float) else ("" if x is None else x) for x in t]


def main_file(a):
    rep = Replay(a.file)
    ticks = rep.ticks()
    print_header(rep)
    if a.summary or not (a.ticks or a.csv):
        print_summary(validate(rep, ticks))
    if a.ticks:
        lo, colon, hi = a.ticks.partition(":")
        lo = int(lo) if lo else 0
        hi = int(hi) if hi else (ticks[-1].tick + 1 if colon and ticks else lo + 1)
        print("  " + " ".join(TickState._fields))
        for t in ticks:
            if lo <= t.tick < hi:
                print("  " + " ".join(str(x) for x in _row(t)))
    if a.csv:
        with open(a.csv, "w", newline="") as fh:
            cw = csv.writer(fh)
            cw.writerow(TickState._fields)
            cw.writerows(_row(t) for t in ticks)
        print("  wrote %d rows to %s" % (len(ticks), a.csv))
    return 0


def check_one(path):
    """-> (path, verdict, detail, validations, facts); never raises."""
    facts = {}
    try:
        rep = Replay(path)
        h = rep.header
        facts = {"version": h["version"], "codec": h["codec"],
                 "tables": tuple((d.name, tuple(d.props)) for d in rep.classes.values())}
        kfc = {}
        ticks = rep.ticks(kfc)
    except RuntimeError as e:
        return path, "SKIP", str(e), None, facts
    except Exception as e:
        return path, "FAIL", "%s: %s" % (type(e).__name__, e), None, facts
    v = validate(rep, ticks)
    v["kf_props"], v["kf_mismatch"] = kfc.get("kf_props", 0), kfc.get("kf_mismatch", 0)
    v["kf_examples"] = kfc.get("kf_examples", [])
    facts["entities_eq_records"] = h["entities"] == len(rep.created)
    m = re.search(r"-(\d{10})-(main|[sb]\d{3})-", os.path.basename(path))
    if m:
        kind = m.group(2)
        track = (0, 1) if kind == "main" else ({"s": 1, "b": 2}[kind[0]], int(kind[1:]))
        facts["name_eq_header"] = (int(m.group(1)) == h["recorded_ms"] // 1000
                                   and track == (h["track_type"], h["track_number"]))
    if not ticks:
        return path, "FAIL", "no player entity", v, facts
    if v["ticks_decoded"] != h["ticks"] or v["first_tick"] != 0 or v["last_tick"] != h["ticks"] - 1:
        return path, "FAIL", "decoded ticks %s..%s, header says %d" % (
            v["first_tick"], v["last_tick"], h["ticks"]), v, facts
    return path, "ok", "", v, facts


def _close(a, b, tol):
    return a is not None and b is not None and abs(a - b) <= tol


def check_line(path, root, verdict, detail, v):
    name = os.path.relpath(path, root)
    if v is None or verdict != "ok":
        return "%-4s %s  %s" % (verdict, name, detail)
    eq = lambda a, b, tol: "-" if a is None or b is None else ("=" if abs(a - b) <= tol else "!")
    splits = ",".join("%s:%d" % kv for kv in sorted(v["json_split_offsets"].items(), key=str)) or "-"
    return ("%-4s %s  %dt kf %d/%d | vel %s/%s z%s | hspd %s%s%s jv %d/%d | time %s timer%s events%+g"
            " name%s splits %s | jumps %d/%s | strafes k%d d%d j%s | pitch %s yaw %s"
            " | gnd vz0 %d/%d land %d/%d" % (
                verdict, name, v["ticks_decoded"], v["kf_props"] - v["kf_mismatch"], v["kf_props"],
                _f(v["vel_next_med"]), _f(v["vel_next_p99"], "%.2f"), _f(v["vel_z_air_med"], "%.2f"),
                _f(v["hspeed_max"], "%.2f"), eq(v["hspeed_max"], v["json_hspeed_max"], 0.01),
                _f(v["json_hspeed_max"], "%.2f"), v["json_vel_exact"], v["json_vel_samples"],
                _f(v["time_header"]), eq(v["time_timer"], v["time_header"], 1e-4),
                v["time_events_off"] or 0, eq(v["time_filename"], v["time_header"], 0.0015), splits,
                v["jumps"], _f(v["json_jumps"]), v["strafe_keys"], v["strafe_dirs"],
                _f(v["json_strafes"]), "%.1f..%.1f" % v["pitch_range"], "%.1f..%.1f" % v["yaw_range"],
                v["ground_vz0"], v["ground_ticks"], v["land_agree"], v["land_changes"]))


def main_check(a):
    files = sorted(os.path.join(dp, f) for dp, _, fs in os.walk(a.check)
                   for f in fs if f.lower().endswith(".mtv"))
    if not files:
        print("no .mtv files under %s" % a.check)
        return 1
    tot = collections.Counter()
    fails, warns = collections.defaultdict(list), collections.defaultdict(list)
    tables = collections.Counter()
    agg = collections.defaultdict(list)
    zduck, zstand = collections.Counter(), collections.Counter()
    pool = None
    if a.jobs > 1:
        import multiprocessing
        pool = multiprocessing.Pool(a.jobs)
        results = pool.imap(check_one, files, chunksize=4)
    else:
        results = map(check_one, files)
    for path, verdict, detail, v, facts in results:
        rel = os.path.relpath(path, a.check)
        print(check_line(path, a.check, verdict, detail, v), flush=True)
        tot["verdict " + verdict] += 1
        if facts:
            tot["format v%d %s" % (facts["version"], {1: "lzma", 2: "zstd"}.get(facts["codec"], "?"))] += 1
            for t in facts["tables"]:
                tables[t] += 1
        if verdict != "ok":
            (warns if verdict == "SKIP" else fails)[re.sub(r"\d+", "N", detail)].append(rel)
            continue
        tot["header: entities == creation records"] += facts.get("entities_eq_records", False)
        if "name_eq_header" in facts:
            tot["header: filename time+track == header"] += facts["name_eq_header"]
            tot["header: filename time+track != header"] += not facts["name_eq_header"]
        tot["json velocity samples"] += v["json_vel_samples"]
        tot["json velocity samples exact"] += v["json_vel_exact"]
        for off, n in v["json_split_offsets"].items():
            tot["json splits: timer at the event - timeReached = %s ticks" % off] += n
        tot["duck: ducked ticks"] += v["duck_ticks"]
        tot["duck: ducked ticks with IN_DUCK"] += v["duck_held"]
        tot["duck: IN_DUCK ticks"] += v["held_ticks"]
        tot["kf props compared"] += v["kf_props"]
        tot["kf props not reproduced"] += v["kf_mismatch"]
        for t0, cls, prop, el, was, kf in v["kf_examples"]:
            warns["a keyframe's %s.%s differs from the deltas before it (e.g. tick %d: %r vs %r)"
                  % (cls, prop, t0, was, kf)].append(rel)
        tot["vel xy: v[t+1] fits better than v[t]"] += (v["vel_next_med"] or 0) <= (v["vel_same_med"] or 0)
        for k in ("vel_next_med", "vel_next_p99", "vel_z_air_med", "yaw_step_p99"):
            agg[k].append(v[k])
        hs, js = v["hspeed_max"], v["json_hspeed_max"]
        if js is None or hs is None:
            tot["hspeed: json or window missing"] += 1
        else:
            tot["hspeed: within 0.01 of json" if abs(hs - js) <= 0.01 else
                "hspeed: within 1% of json" if abs(hs - js) <= 0.01 * js else "hspeed: off by >1%"] += 1
        th = v["time_header"]
        tot["time: timer final %s header" % ("==" if _close(v["time_timer"], th, 1e-4) else "!=")] += 1
        tot["time: (stop-start)*interval - header = %s ticks" % v["time_events_off"]] += 1
        if v["time_filename"] is not None:
            tot["time: filename %s header" % ("==" if _close(v["time_filename"], th, 0.0015) else "!=")] += 1
        if v["json_jumps"] is None:
            tot["jumps: json missing"] += 1
        else:
            tot["jumps: jump-tick changes %s json" % ("==" if v["jumps"] == v["json_jumps"] else "!=")] += 1
            tot["jumps: IN_JUMP presses %s json" % ("==" if v["jump_presses"] == v["json_jumps"] else "!=")] += 1
            agg["jumps minus json"].append(v["jumps"] - v["json_jumps"])
        if v["json_strafes"] == 0:
            tot["strafes: json says 0"] += 1
        elif v["json_strafes"] is not None:
            tot["strafes: json > 0"] += 1
            tot["strafes: json > 0, key presses equal"] += v["strafe_keys"] == v["json_strafes"]
            tot["strafes: json > 0, side changes equal"] += v["strafe_dirs"] == v["json_strafes"]
        pr = v["pitch_range"]
        tot["pitch %s [-89,89]" % ("within" if pr[0] >= -89.0001 and pr[1] <= 89.0001 else "outside")] += 1
        for k in ("ground_ticks", "ground_vz0", "land_changes", "land_agree"):
            tot["ground: " + k] += v[k]
        for z, n in v["view_z_ducked"]:
            zduck[z] += n
        for z, n in v["view_z_standing"]:
            zstand[z] += n
    if pool is not None:
        pool.close()
    print("\nTOTALS over %d files under %s" % (len(files), a.check))
    for k in sorted(tot):
        print("  %-48s %d" % (k, tot[k]))
    for k, xs in sorted(agg.items()):
        xs = [x for x in xs if x is not None]
        if xs:
            print("  %-48s median %.4g  p99 %.4g  min %.4g  max %.4g  (n=%d)"
                  % (k, _pct(xs, 0.5), _pct(xs, 0.99), min(xs), max(xs), len(xs)))
    print("  %-48s %s" % ("view z when ducked (top 4)", zduck.most_common(4)))
    print("  %-48s %s" % ("view z when standing (top 4)", zstand.most_common(4)))
    print("  %-48s %d" % ("distinct prop tables", len(tables)))
    for (name, props), n in sorted(tables.items()):
        print("    %5d  %s (%d props)" % (n, name, len(props)))
    for title, d in (("FAILURE", fails), ("WARNING", warns)):
        for reason, paths in sorted(d.items(), key=lambda kv: -len(kv[1])):
            print("  %s x%d: %s  in %s" % (title, len(paths), reason, paths[0]))
    return 2 if fails else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read Momentum Mod .mtv replays.")
    ap.add_argument("file", nargs="?", help="a .mtv file")
    ap.add_argument("--ticks", help="print per-tick rows a:b (half-open; either side may be empty)")
    ap.add_argument("--csv", help="write every tick to this CSV")
    ap.add_argument("--summary", action="store_true", help="print the validation summary")
    ap.add_argument("--check", metavar="DIR", help="decode every .mtv under DIR and report")
    ap.add_argument("--jobs", type=int, default=max(1, min(8, (os.cpu_count() or 2) - 2)),
                    help="worker processes for --check")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if a.check:
        return main_check(a)
    if not a.file:
        ap.error("give a .mtv file or --check DIR")
    return main_file(a)


if __name__ == "__main__":
    sys.exit(main())
