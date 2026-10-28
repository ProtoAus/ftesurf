#!/usr/bin/env python3
"""P1089: a TAS project revision's hash -- the twin of SV_TASPRevHash (src/server/sv_tasproject.qc).

A hash chain over the file's canonical lines: h0 = sha256("FTESURF-TASREV-CANON 1"), then
h = sha256(h + "\\n" + line) per line, lowercase hex. Left out: saved, revision, origin,
parent, revsha and empty lines; `base <id> <sha> <tick>` loses its local save id. Lines are
taken byte-for-byte as written (the game writes %.9g text; nothing is re-parsed).

  tasrev.py FILE.tasp            print the hash and whether the file's revsha line matches
  tasrev.py --check FILE.tasp    exit 1 unless a revsha line is present and matches
"""
import hashlib, sys

DROP = {'saved', 'revision', 'origin', 'parent', 'revsha'}


def canon(line):
    w = line.split()
    if not w or w[0] in DROP:
        return None
    if w[0] == 'base':
        return 'base %s %s' % (w[2], w[3]) if len(w) >= 4 else line
    return line


def revhash(text):
    h = hashlib.sha256(b'FTESURF-TASREV-CANON 1').hexdigest()
    stated = None
    for line in text.split('\n'):
        line = line.rstrip('\r')
        w = line.split()
        if w and w[0] == 'revsha' and len(w) == 2 and stated is None:
            stated = w[1]
        c = canon(line)
        if c is not None:
            h = hashlib.sha256((h + '\n' + c).encode('latin-1')).hexdigest()
    return h, stated


def main(argv):
    check = '--check' in argv
    paths = [a for a in argv[1:] if a != '--check']
    if len(paths) != 1:
        print(__doc__.strip()); return 2
    with open(paths[0], 'rb') as f:
        h, stated = revhash(f.read().decode('latin-1'))
    print('%s %s' % (h, 'matches revsha' if stated == h else ('revsha %s DIFFERS' % stated if stated else 'no revsha line')))
    return 0 if (not check or stated == h) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
