#!/usr/bin/env python3
"""Patch 661's grader: what is written on the run lines.

python tools/test_p661labels.py <runlines_smoke.log of cfg/test/p661labels.cfg>

    python tools/runlines_smoke.py ftesurf/cfg/test/p661labels.cfg --mount --content C:/FTESurf \
        --output-dir <owned dir> --timeout 420

One run is every line, under a camera that rides a paused replay of it.

  a name past the eighth   line 12 alone has a name as line 5 alone has: `linegraph status`
                           lists it ("12 ..."), fully shown, and the shots with names on and
                           off differ beside its printed place.  Before, slots past the
                           graph's eleven had none
  in the line's colour     the bright pixels the name added are the colour the status prints,
                           which is the line's (a channel within COL of it)
  a crowd: nearest first   twenty lines of one run: every name and number sits where nineteen
                           others do.  `lines native` says for each one with room there are
                           (lines - 1) without, and one name is shown, the rest not
  the lanes still stack    at hud_lines_declutter 2 none is without room
  the numbers' own range   fewer labels within 600 u than as far as the line, and not none
  energy as the speedo     `replay marks`: "E -630" with no u/s; at hud_lines_units 0 "E -1004
                           u/s"; with speed off the label is the energy alone
  the pane                 `hud_edit status` lists a `labels` row
  a name keeps its range   at hud_lines_label_far 50 line 5's name is still fully shown: that
                           is the numbers' range (the first cut hid the name with them)
  a saved old zero         hud_lines_ref 1 with hud_labels_rev 0, then a map load: the zero is
                           0 and the mark 661 afterwards, and the game said so once

On an engine before Patch 645 a twelfth line is refused (Patch 654): its name is NOT MEASURED.

Three verdicts: passed (exit 0), failed (1), not measured (2).
"""
import pathlib
import re
import sys

from PIL import Image

STAMP = re.compile(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', re.M)
SEEN = 60       # pixels a name must change beside its place
COL = 0.25      # how far a channel of the name's ink may be from the printed colour


def block(text, start, end):
    m = re.search(r'^%s\s*\n(.*?)^%s' % (re.escape(start), re.escape(end)), text, re.S | re.M)
    return m.group(1) if m else None


def name_of(body, line):
    """(slot, x, y, text, colour, shown) of board line `line`'s name in a status block."""
    if body is None:
        return None
    for slot, x, y, text in re.findall(
            r'linegraph: label (\d+) at \S+ \S+ \S+ screen (-?[\d.]+) (-?[\d.]+) text \[(.*?)\]', body):
        if text.split(' ')[0] != str(line):
            continue
        m = re.search(r'linegraph: name %s colour (\S+) (\S+) (\S+) shown (\S+)' % slot, body)
        if not m:
            return None
        return int(slot), float(x), float(y), text, tuple(float(v) for v in m.groups()[:3]), float(m.group(4))
    return None


def ink(on, off, x, y):
    """Pixels the name added in the box up and right of (x, y): how many, and their brightest colour."""
    a, b = Image.open(on).convert('RGB'), Image.open(off).convert('RGB')
    box = (int(x), int(y) - 44, min(a.width, int(x) + 260), int(y) + 4)
    pa, pb = a.crop(box).load(), b.crop(box).load()
    w, h = box[2] - box[0], box[3] - box[1]
    changed = [pa[i, j] for j in range(h) for i in range(w) if pa[i, j] != pb[i, j]]
    bright = sorted(changed, key=max, reverse=True)[:max(1, len(changed) // 5)]
    if not bright:
        return 0, None
    top = max(max(c) for c in bright) or 1
    mean = tuple(sum(c[k] for c in bright) / len(bright) / top for k in range(3))
    return len(changed), mean


def labels(body):
    m = re.search(r'lines: last labels (\d+) with room, (\d+) without \(placing (-?\d+), within (\S+) u\)', body or '')
    return tuple(int(v) for v in m.groups()[:3]) if m else None


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    log = pathlib.Path(sys.argv[1])
    text = STAMP.sub('', log.read_text(encoding='utf-8', errors='replace'))
    shots = {p.stem: p for p in log.parent.parent.rglob('p661_*.png')}
    results = []

    def check(name, ok, detail):
        results.append((name, ok, detail))

    seen = {}
    for line in (5, 12):
        got = name_of(block(text, 'P661 NAME %d on' % line, 'P661 NAME %d end' % line), line)
        on, off = shots.get('p661_name%d_on' % line), shots.get('p661_name%d_off' % line)
        if block(text, 'P661 NAME %d on' % line, 'P661 NAME %d end' % line) is None or not (on and off):
            check('line %d alone has its name' % line, None, 'no status block or no shots')
            continue
        if not got:
            # An engine before Patch 645 keeps eight lines (Patch 654): a twelfth cannot be asked for.
            stage = block(text, '==== P661 NAME %d ====' % line, 'P661 NAME %d end' % line) or ''
            if line > 8 and re.search(r'^scores lineat <1\.\.8> <path>', stage, re.M):
                check('line %d alone has its name' % line, None, 'this engine keeps eight lines: line %d was refused' % line)
            else:
                check('line %d alone has its name' % line, False, 'the status lists no name for it')
            continue
        slot, x, y, word, colour, shown = got
        n, mean = ink(on, off, x, y)
        seen[line] = (colour, mean)
        check('line %d alone has its name' % line, shown >= 0.99 and n >= SEEN,
              'slot %d, "%s", shown %.2f; %d pixels change beside %.0f %.0f (bar %d)' % (slot, word, shown, n, x, y, SEEN))
    if 12 in seen and seen[12][1]:
        colour, mean = seen[12]
        top = max(colour) or 1
        want = tuple(c / top for c in colour)
        check('the name is the line\'s colour', all(abs(a - b) <= COL for a, b in zip(want, mean)),
              'printed %s, ink %s' % (' '.join('%.2f' % c for c in want), ' '.join('%.2f' % c for c in mean)))
    else:
        check('the name is the line\'s colour', None, 'line 12\'s name was not seen')

    # hud_lines_label_far is the numbers' range: a name keeps the line's (the first cut's did not).
    kept = name_of(block(text, 'P661 NAME 5 near', 'P661 NAME 5 end'), 5)
    if block(text, 'P661 NAME 5 near', 'P661 NAME 5 end') is None:
        check('a name keeps the line\'s range', None, 'no status at hud_lines_label_far 50')
    else:
        check('a name keeps the line\'s range', bool(kept) and kept[5] >= 0.99,
              'at hud_lines_label_far 50: %s' % (('shown %.2f' % kept[5]) if kept else 'no name listed'))

    crowd = block(text, 'P661 CROWD nearest', 'P661 CROWD lanes')
    lanes = block(text, 'P661 CROWD lanes', 'P661 CROWD again')
    drawn = re.search(r'lines: (\d+) drawn', crowd or '')
    near, lane = labels(crowd), labels(lanes)
    if not (drawn and near):
        check('a crowd: the nearest has the room', None, 'lines drawn %s, label counts %s' % (bool(drawn), bool(near)))
    else:
        n = int(drawn.group(1))
        shown = [float(v) for v in re.findall(r'linegraph: name \d+ colour \S+ \S+ \S+ shown (\S+)', crowd)]
        check('a crowd: the nearest has the room',
              n >= 8 and near[0] >= 2 and near[1] == (n - 1) * near[0]
              and sum(1 for v in shown if v >= 0.99) == 1 and sum(1 for v in shown if v <= 0.01) == n - 1,
              '%d lines of one run: %d labels with room, %d without (%d x %d = %d); names shown %d, hidden %d'
              % (n, near[0], near[1], n - 1, near[0], (n - 1) * near[0],
                 sum(1 for v in shown if v >= 0.99), sum(1 for v in shown if v <= 0.01)))
        if not lane:
            check('the lanes still stack them', None, 'no label count at hud_lines_declutter 2')
        else:
            check('the lanes still stack them', lane[2] == 2 and lane[1] == 0 and lane[0] == near[0] + near[1],
                  'placing %d: %d drawn, %d without room' % (lane[2], lane[0], lane[1]))

    far, close = labels(block(text, 'P661 RANGE line', 'P661 RANGE 600')), labels(block(text, 'P661 RANGE 600', 'P661 RANGE end'))
    if not (far and close):
        check('the numbers have their own range', None, 'label counts %s %s' % (bool(far), bool(close)))
    else:
        check('the numbers have their own range', 0 < sum(close[:2]) < sum(far[:2]),
              '%d labels as far as the line, %d within 600 u' % (sum(far[:2]), sum(close[:2])))

    forms = (('energy', r'~?\d+ u/s  E -?\d+', 'as the speedometer prints it'),
             ('speed', r'~?\d+ u/s  E -?\d+ u/s', 'as a speed'),
             ('alone', r'~?E -?\d+', 'alone'))
    ends = {'energy': 'P661 TEXT speed', 'speed': 'P661 TEXT alone', 'alone': 'P661 TEXT end'}
    for key, form, words in forms:
        body = block(text, 'P661 TEXT %s' % key, ends[key])
        got = re.findall(r'^lnml \d+ "(.*)"', body or '', re.M)
        if len(got) < 5:
            check('energy %s' % words, None, '%d labels listed' % len(got))
        else:
            bad = [g for g in got if not re.fullmatch(form, g)]
            check('energy %s' % words, not bad, '%d labels, the first "%s"; %d of another form%s'
                  % (len(got), got[0], len(bad), (', e.g. "%s"' % bad[0]) if bad else ''))

    pane = block(text, 'P661 PANE status', 'P661 PANE end')
    if pane is None:
        check('the editor has a Line labels pane', None, 'no status block')
    else:
        check('the editor has a Line labels pane', re.search(r'^\s*labels\s', pane, re.M) is not None,
              'rows listed: %d' % len(re.findall(r'^\s+\w+\s+\S+\s+x ', pane, re.M)))

    moved = block(text, 'P661 MOVED after', 'P661 MOVED end')
    ref = re.search(r'"hud_lines_ref" is "([^"]*)"', moved or '')
    rev = re.search(r'"hud_labels_rev" is "([^"]*)"', moved or '')
    if not (ref and rev):
        check('a saved old zero is moved once', None, 'the two settings were not read back after the map load')
    else:
        said = len(re.findall(r'^hud: line labels now measure energy', text, re.M))
        check('a saved old zero is moved once', float(ref.group(1)) == 0 and float(rev.group(1)) == 661 and said == 1,
              'hud_lines_ref %s, hud_labels_rev %s, said %d time(s)' % (ref.group(1), rev.group(1), said))

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if ok is False)
    unmeasured = sum(1 for _, ok, _ in results if ok is None)
    for name, ok, detail in results:
        print('%-12s %s: %s' % ('ok' if ok else ('NOT MEASURED' if ok is None else 'FAIL'), name, detail))
    print('P661: %d passed, %d failed, %d not measured, of %d' % (passed, failed, unmeasured, len(results)))
    return 1 if failed else (2 if unmeasured else 0)


if __name__ == '__main__':
    raise SystemExit(main())
