"""Minimal VBSP reader: entity lump + models lump, seek-based, LZMA-aware."""
import struct, lzma, re, os

HDRSZ = 8 + 64 * 16 + 4


def _delump(raw):
    if raw[:4] == b'LZMA':
        actual, lsize = struct.unpack('<II', raw[4:12])
        props = raw[12:17]
        flt = [{"id": lzma.FILTER_LZMA1, "lc": props[0] % 9, "lp": (props[0] // 9) % 5,
                "pb": props[0] // 45, "dict_size": struct.unpack('<I', props[1:5])[0]}]
        dec = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=flt)
        try:
            return dec.decompress(raw[17:17 + lsize])
        except lzma.LZMAError:
            return b''
    return raw


def lumps(fh):
    fh.seek(0)
    hdr = fh.read(HDRSZ)
    if hdr[:4] != b'VBSP':
        return None
    out = []
    for i in range(64):
        o, l, v, f = struct.unpack('<iiii', hdr[8 + i * 16:8 + i * 16 + 16])
        out.append((o, l, v, f))
    return out


def lump(fh, tbl, idx):
    o, l, v, f = tbl[idx]
    if l <= 0:
        return b''
    fh.seek(o)
    return _delump(fh.read(l))


def parse_ents(raw):
    es = []
    for block in re.findall(rb'\{(.*?)\}', raw, re.S):
        kv = re.findall(rb'"([^"]+)"\s*"([^"]*)"', block)
        if kv:
            es.append({k.decode('latin1').lower(): v.decode('latin1') for k, v in kv})
    return es


def parse_models(raw):
    n = len(raw) // 48
    out = []
    for i in range(n):
        b = raw[i * 48:i * 48 + 48]
        mins = struct.unpack('<3f', b[0:12])
        maxs = struct.unpack('<3f', b[12:24])
        org = struct.unpack('<3f', b[24:36])
        out.append((mins, maxs, org))
    return out


def read(path):
    with open(path, 'rb') as fh:
        tbl = lumps(fh)
        if tbl is None:
            return None, None
        ents = parse_ents(lump(fh, tbl, 0))
        models = parse_models(lump(fh, tbl, 14))
    return ents, models
