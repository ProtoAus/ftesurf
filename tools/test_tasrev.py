#!/usr/bin/env python3
"""P1089: tools/tasrev.py against mutations of a game-written project.

  test_tasrev.py FILE.tasp     every mutation that changes what the game would load or hash
                               must be refused; a new save time must keep the hash.

mutations() is also used by the P1089 arm, which writes the same files into a server's
data/tasproj and requires `tas project hash` to refuse them as well.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tasrev


def mutations(data):
    """(name, bytes, expect) with expect 'same' (same hash) or 'refused'."""
    lines = data.decode('ascii').rstrip('\n').split('\n')
    lines = [l for l in lines if not l.startswith('revsha ')]
    k = next(n for n, l in enumerate(lines) if l.startswith('i '))
    s = next(n for n, l in enumerate(lines) if l.startswith('saved '))
    row = lines[k].split(' ')

    def put(ls):
        return ('\n'.join(ls) + '\n').encode('ascii')

    def at(n, l):
        return lines[:n] + [l] + lines[n + 1:]
    out = [('savedtime', put(at(s, 'saved 1999-01-01T00:00:00')), 'same')]
    # Review 1's construction: a padded `saved` line that fgets splits into a hidden input row.
    out.append(('longsaved', put(at(s, 'saved ' + 'x' * 4089 + 'X' + 'i 9 9 9 9 9 9 0')), 'refused'))
    out.append(('blankmid', put(lines[:k] + [''] + lines[k:]), 'refused'))
    out.append(('crinside', put(at(k, lines[k].replace(' ', ' \r', 1))), 'refused'))
    out.append(('unknownkey', put(lines[:k] + ['note hello'] + lines[k:]), 'refused'))
    out.append(('quoted', put(at(k, '"i" ' + ' '.join(row[1:]))), 'refused'))
    out.append(('comment', put(at(k, lines[k] + ' //x')), 'refused'))
    out.append(('leadingzero', put(at(k, ' '.join(row[:1] + ['0' + row[1]] + row[2:]))), 'refused'))
    out.append(('plussign', put(at(k, ' '.join(row[:1] + ['+' + row[1].lstrip('-')] + row[2:]))), 'refused'))
    out.append(('floatint', put(at(k, ' '.join(row[:1] + [row[1] + '.0'] + row[2:]))), 'refused'))
    out.append(('doublespace', put(at(k, lines[k].replace(' ', '  ', 1))), 'refused'))
    m = next(n for n, l in enumerate(lines) if l.startswith('mapcrc '))
    out.append(('reordered', put(lines[:m - 1] + [lines[m], lines[m - 1]] + lines[m + 1:]), 'refused'))
    b = next(n for n, l in enumerate(lines) if l.startswith('base '))
    ps = 'parentsha ' + '0' * 64
    out.append(('twoparents', put(lines[:b] + [ps, ps] + lines[b:]), 'refused'))
    out.append(('upperhex', put(lines[:b] + ['parentsha ' + 'A' * 64] + lines[b:]), 'refused'))
    out.append(('colon', put(at(k, lines[k] + ' 1:2')), 'refused'))
    out.append(('afterrevsha', put(lines + ['revsha ' + '0' * 64, 'i 0 0 0 0 0 0 0']), 'refused'))
    return out


def main(argv):
    data = Path(argv[1]).read_bytes()
    h, stated = tasrev.revhash(data)
    fails = 0
    print('original %s (%s)' % (h, 'revsha matches' if stated == h else 'revsha %s' % stated))
    for name, mut, expect in mutations(data):
        try:
            got = tasrev.revhash(mut)[0]
            res = 'same' if got == h else 'different hash'
        except tasrev.Refused as e:
            res = 'refused'
        ok = res == expect
        fails += not ok
        print('%-4s %-12s expect %-8s got %s' % ('ok' if ok else 'FAIL', name, expect, res))
    return 1 if fails or stated != h else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
