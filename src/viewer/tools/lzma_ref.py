"""Reference digests for tools/lzma_check.ts: every LZMA lump of a Source BSP
and every entry of its pakfile, decompressed by Python's lzma/zipfile.

    python tools/lzma_ref.py MAP.bsp  ->  one "<kind> <index-or-name> <sha256>" line each
"""
import hashlib
import io
import lzma
import struct
import sys
import zipfile


def lzma_lump(blob):
    # Valve's 17-byte header: 'LZMA', actualSize, lzmaSize, 5 property bytes.
    actual, _packed = struct.unpack_from('<II', blob, 4)
    props = blob[12:17]
    d = props[0]
    lc, lp, pb = d % 9, (d // 9) % 5, d // 45
    dict_size = struct.unpack_from('<I', props, 1)[0]
    dec = lzma.LZMADecompressor(lzma.FORMAT_RAW, filters=[
        {'id': lzma.FILTER_LZMA1, 'lc': lc, 'lp': lp, 'pb': pb, 'dict_size': dict_size}])
    return dec.decompress(blob[17:], actual)[:actual]


def main(path):
    data = open(path, 'rb').read()
    ident, ver = struct.unpack_from('<4si', data, 0)
    assert ident == b'VBSP', ident
    pak = None
    for i in range(64):
        off, length, lver, four = struct.unpack_from('<iiii', data, 8 + i * 16)
        if length <= 0:
            continue
        blob = data[off:off + length]
        if i == 40:
            pak = blob
        if blob[:4] == b'LZMA':
            print('lump', i, hashlib.sha256(lzma_lump(blob)).hexdigest())
    if pak is not None:
        with zipfile.ZipFile(io.BytesIO(pak)) as z:
            for info in z.infolist():
                if info.compress_type == 0:
                    continue
                print('pak', info.filename.lower().replace('\\', '/'), hashlib.sha256(z.read(info)).hexdigest())


if __name__ == '__main__':
    main(sys.argv[1])
