# Folded-MD4 csprogs cache seeder: computes the checksum the engine
# advertises (CalcHashInt(hash_md4): XOR the 16 digest bytes by i%4, read
# as a little-endian int, printed %x) and copies csprogs.dat to
# downloads/csprogsvers/<hash>.dat so test clients validate locally
# instead of stalling on the network download.
import struct, sys

def md4(msg):
    def lrot(x, n): return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF
    msg = bytearray(msg); ml = len(msg)
    msg.append(0x80)
    while len(msg) % 64 != 56: msg.append(0)
    msg += struct.pack('<Q', ml * 8)
    a, b, c, d = 0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476
    for off in range(0, len(msg), 64):
        x = list(struct.unpack('<16I', bytes(msg[off:off+64])))
        aa, bb, cc, dd = a, b, c, d
        def F(x,y,z): return (x & y) | (~x & z)
        def G(x,y,z): return (x & y) | (x & z) | (y & z)
        def H(x,y,z): return x ^ y ^ z
        for k in range(16):
            f = (F, G, H)[k // 8 if k < 16 else 0]
        # round 1
        for k, s in zip(range(16), [3,7,11,19]*4):
            f = F(b, c, d); a = lrot((a + f + x[k]) & 0xFFFFFFFF, s)
            a, b, c, d = d, a, b, c
        # round 2
        for k, s in zip([0,4,8,12,1,5,9,13,2,6,10,14,3,7,11,15], [3,5,9,13]*4):
            f = G(b, c, d); a = lrot((a + f + x[k] + 0x5A827999) & 0xFFFFFFFF, s)
            a, b, c, d = d, a, b, c
        # round 3
        for k, s in zip([0,8,4,12,2,10,6,14,1,9,5,13,3,11,7,15], [3,9,11,15]*4):
            f = H(b, c, d); a = lrot((a + f + x[k] + 0x6ED9EBA1) & 0xFFFFFFFF, s)
            a, b, c, d = d, a, b, c
        a = (a + aa) & 0xFFFFFFFF; b = (b + bb) & 0xFFFFFFFF
        c = (c + cc) & 0xFFFFFFFF; d = (d + dd) & 0xFFFFFFFF
    return struct.pack('<4I', a, b, c, d)

path = sys.argv[1] if len(sys.argv) > 1 else r"C:\FTESurf\ftesurf\csprogs.dat"
data = open(path, 'rb').read()
dig = md4(data)
fold = [0, 0, 0, 0]
for i, byte in enumerate(dig): fold[i % 4] ^= byte
h = '%x' % struct.unpack('<I', bytes(fold))[0]
print('digest', dig.hex(), 'folded', h)

import os, shutil
d = os.path.join(os.path.dirname(os.path.abspath(path)), 'downloads', 'csprogsvers')
if os.path.isdir(d):
    dst = os.path.join(d, h + '.dat')
    shutil.copyfile(path, dst)
    print('seeded', dst)
    for f in os.listdir(d):
        if f.endswith(('.tmp', '.dcl')) or (f.endswith('.dat') and f != h + '.dat'):
            os.remove(os.path.join(d, f))
            print('removed stale', f)
else:
    print('no', d, '-- copy manually')
