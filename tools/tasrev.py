#!/usr/bin/env python3
"""P1089: a TAS project revision's hash -- the twin of SV_TASPRead (src/server/sv_tasproject.qc).

A file counts only if it is exactly what the game writes and its reader would load with the
identity lines present: SV_TASPLineCanon's form (the writer's key order, only cp and i repeat;
printable ASCII under 3000 bytes a line; single spaces; none of tokenize's punctuation and ':'
only in `saved`; %.0f integers and %.9g float32 values with no "-0"; lowercase hex; fixed
words) and SV_TASPRead's meaning (version, bounds, row counts, checkpoint order and names,
required lines). Stricter than the game, never looser: the whole file must be its lines each
ended by one newline (the game would stop at an empty line and ignore the rest), no CR.

The hash is a chain: h0 = sha256("FTESURF-TASREV-CANON 1"), h = sha256(h + "\\n" + line)
over the canonical lines -- saved, revision, origin, parent and revsha left out, and `base`
without its local save id. Keep this file and the QuakeC in step.

  tasrev.py FILE.tasp            print the hash, or why the file is refused
  tasrev.py --check FILE.tasp    exit 1 unless accepted and its revsha line matches
"""
import hashlib, re, struct, sys

VERSION, TASP_MAX, TASP_CPMAX = 1, 96000, 48
RANK = {k: i for i, k in enumerate(['tasproject', 'map', 'mapcrc', 'zonecrc', 'pmpin', 'assist', 'origin',
                                    'saved', 'revision', 'parent', 'parentsha', 'base', 'baseat', 'head',
                                    'cp', 'i', 'end', 'revsha'])}
DROP = {'saved', 'revision', 'origin', 'parent', 'revsha'}
BAD = set('"\'/()[]{},;\\')
HEX = re.compile(r'[0-9a-f]+\Z')
NAME = re.compile(r'[a-z0-9_-]{1,32}\Z')   # SV_TASPNameOK
SAVED = re.compile(r'saved \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\Z')


class Refused(Exception):
    pass


def f32(t):
    x = float(t)
    if x != x or x in (float('inf'), float('-inf')):
        raise ValueError(t)
    return struct.unpack('<f', struct.pack('<f', x))[0]


def canon_num(t, whole):
    if t == '-0':
        return False                # the writer writes zero for negative zero (SV_TASPZ)
    try:
        return t == ('%.0f' if whole else '%.9g') % f32(t)
    except (ValueError, OverflowError):
        return False


def num(t, lo, hi):
    """A canonical value's float32 within [lo, hi], else Refused (SV_TASPNum / SV_TASPFloat)."""
    x = f32(t)
    if not (lo <= x <= hi):
        raise Refused('value %s out of range' % t)
    return x


def check_form(line, rank):
    if not (0 < len(line) < 3000) or line != line.strip(' ') or '  ' in line:
        raise Refused('spacing or length')
    w = line.split(' ')
    k = w[0]
    if any(ord(c) < 32 or ord(c) > 126 or c in BAD for c in line) or (':' in line and k != 'saved'):
        raise Refused('bytes the game does not write')
    r = RANK.get(k, -1)
    if r < 0 or r < rank or (r == rank and k not in ('cp', 'i')):
        raise Refused('key %r out of the writer\'s order' % k)
    a = w[1:]
    ok = True
    if k == 'assist': ok = line == 'assist tas'
    elif k == 'origin': ok = line == 'origin local'
    elif k in ('mapcrc', 'zonecrc'): ok = len(a) == 1 and bool(HEX.match(a[0]))
    elif k in ('parentsha', 'revsha'): ok = len(a) == 1 and len(a[0]) == 64 and bool(HEX.match(a[0]))
    elif k == 'base': ok = len(a) == 3 and canon_num(a[0], True) and len(a[1]) == 64 and bool(HEX.match(a[1])) and canon_num(a[2], True)
    elif k == 'saved': ok = bool(SAVED.match(line))
    elif k == 'parent': ok = len(a) == 2 and bool(NAME.match(a[0])) and canon_num(a[1], True)
    elif k == 'cp':
        ok = (len(a) == 9 and canon_num(a[0], True) and a[1] in ('0', '1') and (bool(NAME.match(a[2])) if a[1] == '1' else a[2] == '-')
              and all(canon_num(x, False) for x in a[3:]))
    elif k == 'baseat': ok = len(a) == 6 and all(canon_num(x, False) for x in a)
    elif k in ('tasproject', 'revision', 'head', 'i', 'end'): ok = len(a) >= 1 and all(canon_num(x, True) for x in a)
    if not ok:
        raise Refused('%s line not in the writer\'s form' % k)
    return r, k, a


def canon(line):
    w = line.split(' ')
    if w[0] in DROP:
        return None
    return 'base %s %s' % (w[2], w[3]) if w[0] == 'base' else line


def revhash(data):
    """(hash, stated revsha or None) for the bytes of a .tasp; raises Refused."""
    if b'\r' in data or not data.endswith(b'\n') or b'\n\n' in data:
        raise Refused('not one newline-ended line after another (CR, empty line or no final newline)')
    try:
        text = data.decode('ascii')
    except UnicodeDecodeError:
        raise Refused('bytes the game does not write')
    h = hashlib.sha256(b'FTESURF-TASREV-CANON 1').hexdigest()
    stated, rank, ended = None, -1, False
    have, base, size, n, cps, names = set(), None, None, 0, [], set()
    try:
        for line in text[:-1].split('\n'):
            rank, k, a = check_form(line, rank)
            if ended and k != 'revsha':
                raise Refused('data after end')
            if k == 'tasproject':
                if a != [str(VERSION)]: raise Refused('unknown project version')
            elif k == 'map':
                if len(a) != 1: raise Refused('map line')
            elif k == 'pmpin':
                if not a: raise Refused('empty movement pin')
            elif k == 'revision':
                if len(a) != 1: raise Refused('bad revision')
                num(a[0], 1, 16000000)
            elif k == 'parent':
                num(a[1], 0, 16000000)
            elif k == 'base':
                num(a[0], 1, 99999); base = num(a[2], 0, 16000000)
            elif k == 'baseat':
                for x in a: num(x, -1000000, 1000000)
            elif k == 'head':
                if base is None or len(a) != 1: raise Refused('bad head')
                size = num(a[0], base + 1, base + TASP_MAX) - base
            elif k == 'i':
                if size is None or len(a) != 7 or n >= size: raise Refused('bad input row')
                v = [num(x, -32768, 32767) for x in a]
                if not 0 <= v[6] <= 7: raise Refused('bad input row %d' % (n + 1))
                n += 1
            elif k == 'cp':
                if len(cps) >= TASP_CPMAX: raise Refused('too many checkpoints')
                t = num(a[0], 0, 16000000)
                if cps and t <= cps[-1]: raise Refused('checkpoints out of order')
                if a[1] == '1':
                    if a[2] in names: raise Refused('bad checkpoint name')
                    names.add(a[2])
                for x in a[3:]: num(x, -1000000, 1000000)
                cps.append(t)
            elif k == 'end':
                if len(a) != 1 or num(a[0], 1, TASP_MAX) != n or n != size:
                    raise Refused('row count does not match its trailer')
                ended = True
            elif k == 'revsha':
                stated = a[0]
            have.add(k)
            c = canon(line)
            if c is not None:
                h = hashlib.sha256((h + '\n' + c).encode('ascii')).hexdigest()
    except (ValueError, OverflowError):
        raise Refused('a value the game cannot read')
    if not ended:
        raise Refused('incomplete file (no end line)')
    if not {'tasproject', 'map', 'base', 'head', 'baseat'} <= have:
        raise Refused('missing header lines')
    if not {'mapcrc', 'zonecrc', 'pmpin'} <= have:
        raise Refused('missing map, zone or movement-rule line')
    if cps and (cps[0] <= base or cps[-1] > base + n):
        raise Refused('checkpoint outside the project')
    return h, stated


def main(argv):
    check = '--check' in argv
    paths = [a for a in argv[1:] if a != '--check']
    if len(paths) != 1:
        print(__doc__.strip()); return 2
    with open(paths[0], 'rb') as f:
        data = f.read()
    try:
        h, stated = revhash(data)
    except Refused as e:
        print('refused: %s' % e); return 1
    print('%s %s' % (h, 'matches revsha' if stated == h else ('revsha %s DIFFERS' % stated if stated else 'no revsha line')))
    return 0 if (not check or stated == h) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
