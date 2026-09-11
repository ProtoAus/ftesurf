"""
DMX binary reader, scoped to what a Source .pcf actually uses.

Validation gate, deliberately: parse() asserts the cursor lands EXACTLY on EOF.
A DMX attribute walk that guesses a type code wrong does not crash -- it reads
plausible floats out of the next attribute's bytes and keeps going, so the only
honest check is "did the whole file account for itself".  Refuse rather than
return a number.  (Same rule as the BSP census gate: it refused 242 maps three
times running, and each refusal was a wrong guess that would otherwise have
shipped as a confident figure.)
"""
import struct, re

# DmAttributeType.  1..14 scalar, +14 for the array form.
T_ELEMENT, T_INT, T_FLOAT, T_BOOL, T_STRING, T_VOID, T_TIME = 1, 2, 3, 4, 5, 6, 7
T_COLOR, T_VECTOR2, T_VECTOR3, T_VECTOR4 = 8, 9, 10, 11
T_QANGLE, T_QUATERNION, T_VMATRIX = 12, 13, 14
T_ARRAY_BASE = 14

TYPENAME = {
    1: "element", 2: "int", 3: "float", 4: "bool", 5: "string", 6: "void",
    7: "time", 8: "color", 9: "vector2", 10: "vector3", 11: "vector4",
    12: "qangle", 13: "quaternion", 14: "vmatrix",
}


class DmxError(Exception):
    pass


class Element:
    __slots__ = ("type", "name", "guid", "attr")

    def __init__(self, type_, name, guid):
        self.type = type_
        self.name = name
        self.guid = guid
        self.attr = {}

    def __repr__(self):
        return "<%s %r %d attrs>" % (self.type, self.name, len(self.attr))

    def get(self, key, default=None):
        return self.attr.get(key, default)


class Dmx:
    def __init__(self, elements, encoding, enc_ver, fmt, fmt_ver):
        self.elements = elements
        self.encoding = encoding
        self.encoding_version = enc_ver
        self.format = fmt
        self.format_version = fmt_ver

    @property
    def root(self):
        return self.elements[0] if self.elements else None

    def by_type(self, t):
        return [e for e in self.elements if e.type == t]


_HDR = re.compile(
    rb"<!--\s*dmx\s+encoding\s+(\w+)\s+(\d+)\s+format\s+(\w+)\s+(\d+)\s*-->")


class _Reader:
    def __init__(self, data):
        self.d = data
        self.p = 0

    def u8(self):
        v = self.d[self.p]; self.p += 1; return v

    def u16(self):
        v = struct.unpack_from("<H", self.d, self.p)[0]; self.p += 2; return v

    def i32(self):
        v = struct.unpack_from("<i", self.d, self.p)[0]; self.p += 4; return v

    def f32(self):
        v = struct.unpack_from("<f", self.d, self.p)[0]; self.p += 4; return v

    def floats(self, n):
        v = struct.unpack_from("<%df" % n, self.d, self.p); self.p += 4 * n
        return list(v)

    def cstr(self):
        e = self.d.index(b"\0", self.p)
        s = self.d[self.p:e].decode("latin-1")
        self.p = e + 1
        return s

    def blob(self, n):
        v = self.d[self.p:self.p + n]; self.p += n; return v


def parse(data):
    m = _HDR.match(data)
    if not m:
        raise DmxError("not a DMX file: header is %r" % data[:64])
    encoding = m.group(1).decode()
    enc_ver = int(m.group(2))
    fmt = m.group(3).decode()
    fmt_ver = int(m.group(4))

    if encoding != "binary":
        raise DmxError("encoding %r is not supported (only binary)" % encoding)
    # 2 is what every pcf 1 file in the Momentum library uses.  3 moves element
    # NAMES into the string table; 4/5 widen the table count to int and index
    # strings by int.  Refuse rather than half-read one.
    if enc_ver not in (2,):
        raise DmxError(
            "binary encoding version %d is not supported (only 2). "
            "v3 puts element names in the string table and v4/v5 widen the "
            "table -- both need real code, not a tweak." % enc_ver)

    r = _Reader(data)
    r.p = data.index(b"\0", m.end()) + 1 if b"\0" in data[m.end():m.end() + 8] else m.end()
    # the header is followed by \n\0; be tolerant about which we landed on
    while r.p < len(data) and data[r.p - 1] not in (0,):
        r.p += 1

    nstr = r.u16()
    strings = [r.cstr() for _ in range(nstr)]

    def s(i):
        if i < 0 or i >= len(strings):
            raise DmxError("string index %d out of range (%d)" % (i, len(strings)))
        return strings[i]

    nelem = r.i32()
    if nelem < 0 or nelem > 1 << 20:
        raise DmxError("implausible element count %d" % nelem)

    elements = []
    for _ in range(nelem):
        tn = s(r.u16())
        name = r.cstr()            # binary 2: element names are INLINE
        guid = r.blob(16)
        elements.append(Element(tn, name, guid))

    def value(t):
        if t == T_ELEMENT:
            return r.i32()          # index into elements, -1 = null, -2 = extern
        if t == T_INT:
            return r.i32()
        if t == T_FLOAT:
            return r.f32()
        if t == T_BOOL:
            return bool(r.u8())
        if t == T_STRING:
            return r.cstr()
        if t == T_VOID:
            return r.blob(r.i32())
        if t == T_TIME:
            return r.i32() / 10000.0
        if t == T_COLOR:
            return [r.u8(), r.u8(), r.u8(), r.u8()]
        if t == T_VECTOR2:
            return r.floats(2)
        if t in (T_VECTOR3, T_QANGLE):
            return r.floats(3)
        if t in (T_VECTOR4, T_QUATERNION):
            return r.floats(4)
        if t == T_VMATRIX:
            return r.floats(16)
        raise DmxError("unknown attribute type %d at offset %d" % (t, r.p))

    for e in elements:
        for _ in range(r.i32()):
            an = s(r.u16())
            at = r.u8()
            if at > T_ARRAY_BASE:
                base = at - T_ARRAY_BASE
                e.attr[an] = [value(base) for _ in range(r.i32())]
            else:
                e.attr[an] = value(at)

    # THE GATE.  Everything above can be wrong without raising; this is the
    # only statement that can tell.
    if r.p != len(data):
        raise DmxError(
            "cursor stopped at %d of %d bytes -- the attribute walk is wrong, "
            "and a partial parse here yields plausible garbage rather than an "
            "error. Refusing." % (r.p, len(data)))

    return Dmx(elements, encoding, enc_ver, fmt, fmt_ver)


def load(path):
    with open(path, "rb") as f:
        return parse(f.read())
