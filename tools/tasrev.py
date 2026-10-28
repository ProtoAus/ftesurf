#!/usr/bin/env python3
"""P1089: a TAS project revision's hash -- the twin of SV_TASPRead's (src/server/sv_tasproject.qc).

A file counts only if it is exactly what the game writes (SV_TASPLineCanon): the writer's
key order (only cp and i repeat), printable ASCII under 3000 bytes a line, single spaces,
none of tokenize's punctuation and ':' only in `saved`, every number in the writer's own
text (%.0f integers, %.9g of a float32), lowercase hex, fixed words. As in the game's fgets
loop the first empty line ends the file; a CR anywhere is refused, where fgets would drop it.

The hash is a chain: h0 = sha256("FTESURF-TASREV-CANON 1"), h = sha256(h + "\\n" + line)
over the canonical lines -- saved, revision, origin, parent and revsha left out, and `base`
without its local save id. Keep this file and the QuakeC in step.

  tasrev.py FILE.tasp            print the hash, or why the file is refused
  tasrev.py --check FILE.tasp    exit 1 unless accepted and its revsha line matches
"""
import hashlib, re, struct, sys

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
    try:
        return t == ('%.0f' if whole else '%.9g') % f32(t)
    except (ValueError, OverflowError):
        return False


def check_line(line, rank):
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
    return r


def canon(line):
    w = line.split(' ')
    if w[0] in DROP:
        return None
    return 'base %s %s' % (w[2], w[3]) if w[0] == 'base' else line


def revhash(data):
    """(hash, stated revsha or None) for the bytes of a .tasp; raises Refused."""
    h = hashlib.sha256(b'FTESURF-TASREV-CANON 1').hexdigest()
    stated, rank, ended = None, -1, False
    if b'\r' in data:
        raise Refused('a carriage return (the game never writes one; its fgets would drop it)')
    for raw in data.split(b'\n'):
        line = raw
        if not line:
            break                   # the game's fgets loop ends at the first empty line
        try:
            line = line.decode('ascii')
        except UnicodeDecodeError:
            raise Refused('bytes the game does not write')
        rank = check_line(line, rank)
        k = line.split(' ')[0]
        if ended and k != 'revsha':
            raise Refused('data after end')
        ended = ended or k == 'end'
        if k == 'revsha':
            stated = line.split(' ')[1]
        c = canon(line)
        if c is not None:
            h = hashlib.sha256((h + '\n' + c).encode('ascii')).hexdigest()
    if not ended:
        raise Refused('incomplete file (no end line)')
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
