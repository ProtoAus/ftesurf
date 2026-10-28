#!/usr/bin/env python3
"""P1089/P1090: tools/tasrev.py against mutations of a game-written project.

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
    sb = next(n for n, l in enumerate(lines) if l.startswith('supply ') or l.startswith('base '))
    ps = 'parentsha ' + '0' * 64
    out.append(('twoparents', put(lines[:sb] + [ps, ps] + lines[sb:]), 'refused'))
    out.append(('upperhex', put(lines[:sb] + ['parentsha ' + 'A' * 64] + lines[sb:]), 'refused'))
    out.append(('colon', put(at(k, lines[k] + ' 1:2')), 'refused'))
    out.append(('afterrevsha', put(lines + ['revsha ' + '0' * 64, 'i 0 0 0 0 0 0 0']), 'refused'))
    # Review 2: the twin must also hold the reader's meaning, not just its form.
    out.append(('justend', b'end 1\n', 'refused'))
    out.append(('version3', put(at(0, 'tasproject 3')), 'refused'))
    mp = next(n for n, l in enumerate(lines) if l.startswith('map '))
    out.append(('maptwo', put(at(mp, lines[mp] + ' extra')), 'refused'))
    out.append(('shortrow', put(at(k, 'i 1 2 3')), 'refused'))
    out.append(('rowrange', put(at(k, 'i 99999 0 0 0 0 0 99')), 'refused'))
    e = next(n for n, l in enumerate(lines) if l.startswith('end '))
    out.append(('endcount', put(at(e, 'end 7')), 'refused'))
    c = next(n for n, l in enumerate(lines) if l.startswith('cp '))
    cw = lines[c].split(' ')
    out.append(('cpfar', put(at(c, ' '.join(cw[:4] + ['5000000'] + cw[5:]))), 'refused'))
    named = [n for n, l in enumerate(lines) if l.startswith('cp ') and l.split(' ')[2] == '1']
    if named:
        nw = lines[named[0]].split(' ')
        dup = ' '.join(['cp', str(int(nw[1]) + 1)] + nw[2:])
        out.append(('dupname', put(lines[:named[0] + 1] + [dup] + lines[named[0] + 1:]), 'refused'))
    zero = [n for n, l in enumerate(lines) if l.startswith('i ') and ' 0' in l]
    if zero:
        zw = lines[zero[0]].split(' '); zi = zw.index('0', 1); zw[zi] = '-0'
        out.append(('negzero', put(at(zero[0], ' '.join(zw))), 'refused'))
    out.append(('exponent', put(at(c, ' '.join(cw[:4] + ['9.99999975e-06'] + cw[5:]))), 'different'))
    # Review 3: the hashed assist line is required; identity values only in the game's form.
    asl = next(n for n, l in enumerate(lines) if l == 'assist tas')
    out.append(('noassist', put(lines[:asl] + lines[asl + 1:]), 'refused'))
    mc = next(n for n, l in enumerate(lines) if l.startswith('mapcrc '))
    out.append(('shortcrc', put(at(mc, 'mapcrc 0')), 'refused'))
    pp = next(n for n, l in enumerate(lines) if l.startswith('pmpin '))
    out.append(('pinjunk', put(at(pp, 'pmpin x')), 'refused'))
    # P1090: the supply line -- required in version 2, inside the project, all of a root's ticks.
    sp = [n for n, l in enumerate(lines) if l.startswith('supply ')]
    if sp:
        sp = sp[0]
        base = int(lines[b].split(' ')[3]); head = int(next(l for l in lines if l.startswith('head ')).split(' ')[1])
        root = not any(l.startswith('parentsha ') for l in lines)
        sw = lines[sp].split(' ')
        out.append(('nosupply', put(lines[:sp] + lines[sp + 1:]), 'refused'))
        out.append(('v1supply', put(at(0, 'tasproject 1')), 'refused'))
        out.append(('supplytwo', put(lines[:sp] + [lines[sp]] + lines[sp:]), 'refused'))
        out.append(('supplyzero', put(at(sp, 'supply 0 %d' % head)), 'refused'))
        out.append(('supplynan', put(at(sp, 'supply nan nan')), 'refused'))
        out.append(('supplypast', put(at(sp, 'supply %d %d' % (base + 1, head + 1))), 'refused'))
        out.append(('supplybefore', put(at(sp, 'supply %d %d' % (base, head))), 'refused'))
        if head > base + 1:
            out.append(('supplyback', put(at(sp, 'supply %d %d' % (head, base + 1))), 'refused'))
        out.append(('supplynone', put(at(sp, 'supply none')), 'same' if sw[1] == 'none' else ('refused' if root else 'different')))
        if not root:
            full = sw[1:] == [str(base + 1), str(head)]
            ps = next(n for n, l in enumerate(lines) if l.startswith('parentsha '))
            out.append(('rootsupply', put(lines[:ps] + lines[ps + 1:]), 'different' if full else 'refused'))
    else:
        out.append(('version2', put(at(0, 'tasproject 2')), 'refused'))
    # The twin is stricter than the game here (the game stops at an empty line, drops a CR).
    out.append(('trailing', data.rstrip(b'\n') + b'\n\n\x00 junk end 99\n', 'refused'))
    out.append(('nofinalnl', data.rstrip(b'\n'), 'refused'))
    return out


TWIN_STRICTER = {'crinside', 'trailing', 'nofinalnl'}   # the game may hash these as the original


def main(argv):
    data = Path(argv[1]).read_bytes()
    h, stated = tasrev.revhash(data)
    fails = 0
    print('original %s (%s)' % (h, 'revsha matches' if stated == h else 'revsha %s' % stated))
    for name, mut, expect in mutations(data):
        try:
            got = tasrev.revhash(mut)[0]
            res = 'same' if got == h else 'different'
        except tasrev.Refused as e:
            res = 'refused'
        ok = res == expect
        fails += not ok
        print('%-4s %-12s expect %-8s got %s' % ('ok' if ok else 'FAIL', name, expect, res))
    return 1 if fails or stated != h else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
