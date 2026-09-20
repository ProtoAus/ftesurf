#!/usr/bin/env python3
"""
ed25519.py -- Ed25519 (RFC 8032), in pure Python, for checking run receipts.

WHY NOT A LIBRARY.  The Pi has python-cryptography and this box does not, and
the checker has to run in both places: on the Pi because that is where the
sweeper reads the evidence, and here because that is where the test suite runs.
A dependency that is present on one of the two machines is a tool that only
works where nobody is looking.  So: the library is used when it is there (it is
faster and it is somebody else's audited code), and this falls in behind it.

IT IS THE RFC's OWN REFERENCE ARRANGEMENT, not a clever one -- big integers,
affine recovery, no constant-time anything.  That is fine for what it does: it
VERIFIES public signatures against public keys, offline, after the fact.  It
signs too, because the engine's C implementation has to be checked against
something and a checker that could only verify could not produce a vector.

NEVER USE THIS TO SIGN A REAL PLAYER'S RUNS.  Python cannot keep a secret from
its own host and this makes no attempt to: `sign` exists for fixtures and for
`--selftest`.  A player's key is made and used inside the engine, which is the
only place it belongs.

Self-check:  python tools/ed25519.py --selftest
"""

import hashlib
import sys

P = 2 ** 255 - 19
Q = 2 ** 252 + 27742317777372353535851937790883648493


def _sha512(b):
    return hashlib.sha512(b).digest()


def _sha512_modq(b):
    return int.from_bytes(_sha512(b), "little") % Q


def _inv(x):
    return pow(x, P - 2, P)


D = -121665 * _inv(121666) % P
MODP_SQRT_M1 = pow(2, (P - 1) // 4, P)


def _recover_x(y, sign):
    """The x with this y and this low bit, or None when the point is not on the curve."""
    if y >= P:
        return None
    x2 = (y * y - 1) * _inv(D * y * y + 1)
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (P + 3) // 8, P)
    if (x * x - x2) % P != 0:
        x = x * MODP_SQRT_M1 % P
    if (x * x - x2) % P != 0:
        return None
    if (x & 1) != sign:
        x = P - x
    return x


G_Y = 4 * _inv(5) % P
G_X = _recover_x(G_Y, 0)
G = (G_X, G_Y, 1, G_X * G_Y % P)


def _point_add(a, b):
    ax, ay, az, at = a
    bx, by, bz, bt = b
    A = (ay - ax) * (by - bx) % P
    B = (ay + ax) * (by + bx) % P
    C = 2 * at * bt * D % P
    Dd = 2 * az * bz % P
    E, F, Gg, H = B - A, Dd - C, Dd + C, B + A
    return (E * F % P, Gg * H % P, F * Gg % P, E * H % P)


def _point_mul(s, pt):
    out = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            out = _point_add(out, pt)
        pt = _point_add(pt, pt)
        s >>= 1
    return out


def _point_equal(a, b):
    if (a[0] * b[2] - b[0] * a[2]) % P != 0:
        return False
    return (a[1] * b[2] - b[1] * a[2]) % P == 0


def _point_compress(pt):
    x, y, z, _t = pt
    zi = _inv(z)
    x, y = x * zi % P, y * zi % P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _point_decompress(b):
    if len(b) != 32:
        return None
    y = int.from_bytes(b, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % P)


def _expand(seed):
    h = _sha512(seed[:32])
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return h, a


def publickey(seed):
    """-> the 32-byte public key for this 32-byte seed."""
    _h, a = _expand(seed)
    return _point_compress(_point_mul(a, G))


def sign(seed, msg):
    """-> the 64-byte signature.  Fixtures and self-tests only; see the header."""
    h, a = _expand(seed)
    pub = _point_compress(_point_mul(a, G))
    r = _sha512_modq(h[32:] + msg)
    big_r = _point_compress(_point_mul(r, G))
    k = _sha512_modq(big_r + pub + msg)
    return big_r + int.to_bytes((r + k * a) % Q, 32, "little")


def small_order(pub):
    """-> True when this public key has order 1, 2, 4 or 8.

    [8]A is the identity exactly for those.  A signature under such a key
    verifies for ANYBODY -- [k]A is the identity whatever k is, so the equation
    collapses to R == [s]B, which anyone satisfies by picking r and setting
    s = r.  Ordinary Ed25519 verifiers do not care, because one key means one
    signer; here the public key is a PLAYER'S IDENTITY, so a small-order key is
    a name eight people can wear at once with nothing broken.
    """
    a = _point_decompress(pub)
    if a is None:
        return False
    return _point_equal(_point_mul(8, a), (0, 1, 1, 0))


def verify(pub, msg, sig):
    """-> True when `sig` is a valid Ed25519 signature of `msg` under `pub`.

    Returns False rather than raising on anything malformed: a checker reading a
    file written by somebody else must treat "not a signature" and "the wrong
    signature" the same way, and neither is an error in the checker.
    """
    if len(sig) != 64 or len(pub) != 32:
        return False
    a = _point_decompress(pub)
    if a is None:
        return False
    if _point_equal(_point_mul(8, a), (0, 1, 1, 0)):
        return False            # small order -- see small_order() above
    big_r = _point_decompress(sig[:32])
    if big_r is None:
        return False
    s = int.from_bytes(sig[32:], "little")
    if s >= Q:
        return False
    k = _sha512_modq(sig[:32] + pub + msg)
    return _point_equal(_point_mul(s, G),
                        _point_add(big_r, _point_mul(k, a)))


# RFC 8032 section 7.1, the first two vectors and the 1023-byte one's short
# sibling.  Quoted, not derived: the point of a published vector is that it was
# computed by somebody else.
VECTORS = [
    ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
     "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
     "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
     "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
     "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
     "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
     "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
    ("c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
     "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
     "af82",
     "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac"
     "18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a"),
]


def selftest():
    bad = 0
    for seed, pub, msg, sig in VECTORS:
        s, p_, m, g = (bytes.fromhex(seed), bytes.fromhex(pub),
                       bytes.fromhex(msg), bytes.fromhex(sig))
        got_pub = publickey(s)
        got_sig = sign(s, m)
        ok_pub = got_pub == p_
        ok_sig = got_sig == g
        ok_ver = verify(p_, m, g)
        # AND IT MUST REFUSE.  A verifier that returns True unconditionally
        # passes every vector above; only the negative arms say otherwise.
        ok_ref = (not verify(p_, m + b"\x00", g)
                  and not verify(p_, m, g[:63] + bytes([g[63] ^ 1]))
                  and not verify(bytes(32), m, g))
        print("  %s  pk %s  sig %s  verify %s  refuse %s"
              % (seed[:16], "ok" if ok_pub else "FAIL",
                 "ok" if ok_sig else "FAIL", "ok" if ok_ver else "FAIL",
                 "ok" if ok_ref else "FAIL"))
        bad += (not ok_pub) + (not ok_sig) + (not ok_ver) + (not ok_ref)
    print("%d check(s) failed" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        sys.exit(selftest())
    print(__doc__.strip().splitlines()[0])
    print("run with --selftest")
