#!/usr/bin/env python3
"""Grade cfg/test/p632lines.cfg's log (Patch 632: the Run lines pane and the lines' colours).

python tools/runlines_smoke.py ftesurf/cfg/test/p632lines.cfg --mount --output-dir <dir>
python tools/test_p632lines.py <rig>/ftesurf/logs/runlines_smoke.log

What is read: the pane's hit rects (`hud_edit ui`) and the cvar after each click;
`replay colours`, which prints ln_col itself, the vector the strip is drawn from,
and ends `lnce <mode> <ranked> <place> <tint> <of> <age>`: the slot's colouring, its
place among the `of` lines of its leg ranked by time, the blend toward blue it was
last drawn with and how long ago a drawer drew it; `replay marktrace`, each mark
the pass drew and the label it queued; `replay marks`, whose `lnf` lines are the
contact marks that are also a top or a bottom.  A place's colour is worked out
here from the place, not read back.
Three verdicts: passed (exit 0), failed (1), or a step the checks need is not in
this log (2).
"""
import pathlib
import re
import sys

STAMP = re.compile(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', re.M)
BLUE, GREEN, YELLOW, RED = (0.300, 0.650, 1.000), (0.300, 1.000, 0.350), (1.000, 0.900, 0.220), (1.000, 0.220, 0.220)
PLAIN = 5
DRAWN = 0.5             # seconds: a slot some drawer reached on a recent frame


def sections(text):
    text = STAMP.sub('', text)
    out = {}
    parts = re.split(r'^(?:P632 (.+?)|====.*)\s*$', text, flags=re.M)
    for i in range(1, len(parts) - 1, 2):
        if parts[i] is not None:
            out[parts[i].strip()] = parts[i + 1]
    return out


def by_time(place, of):
    """The colour of place `place` (0 the fastest) among `of` lines: green, through yellow, to red."""
    f = place / (of - 1) if of > 1 else 0.0
    if f < 0.5:
        return tuple(a + (b - a) * f * 2 for a, b in zip(GREEN, YELLOW))
    return tuple(a + (b - a) * (f - 0.5) * 2 for a, b in zip(YELLOW, RED))


def near(a, b):
    return all(abs(x - y) <= 0.002 for x, y in zip(a, b))


def name(c):
    for n, v in (('blue', BLUE), ('green', GREEN), ('yellow', YELLOW), ('red', RED)):
        if near(c, v):
            return n
    return '(%.3f %.3f %.3f)' % c


def colours(body):
    """A `replay colours` dump."""
    head = re.search(r'^lncb (\S+) (\S+) (\S+) (\S+)', body, re.M)
    tail = re.search(r'^lnce (\S+) (\S+) (\S+) (\S+) (\S+) (\S+)', body, re.M)
    if not head or not tail:
        return None
    rows = [tuple(float(v) for v in m.groups())
            for m in re.finditer(r'^lnc \S+ \S+ (\S+) (\S+) (\S+) \S+', body, re.M)]
    return {'slot': int(float(head.group(1))), 'mode': int(float(head.group(2))), 'n': int(float(head.group(3))),
            'rows': rows, 'ranked': int(float(tail.group(2))), 'place': int(float(tail.group(3))),
            'tint': float(tail.group(4)), 'of': int(float(tail.group(5))), 'age': float(tail.group(6))}


def marks(body):
    """`replay marktrace`: (kind, time, labelled) for each mark the pass drew."""
    return [(int(float(m.group(1))), float(m.group(2)), m.group(3) != '-')
            for m in re.finditer(r'^lndm \S+ (\S+) (\S+) \S+ \S+ (.+)$', body, re.M)]


def read(body, cvar):
    m = re.search(r'"%s" is "([^"]*)"' % cvar, body or '')
    return m.group(1) if m else None


def main():
    text = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8', errors='replace')
    sec = sections(text)
    results = []

    def check(what, ok, detail):
        results.append((what, ok, detail))

    def values(marker, want):
        body = sec.get(marker)
        got = {cv: read(body, cv) for cv in want}
        if body is None or any(v is None for v in got.values()):
            check(marker, None, 'read %s' % got)
            return
        bad = {cv: got[cv] for cv in want if float(got[cv]) != want[cv]}
        check(marker, not bad, ', '.join('%s %s' % (cv, got[cv]) for cv in want)
              + ((' -- want %s' % {cv: want[cv] for cv in bad}) if bad else ''))

    # --- a saved config, and reset all -----------------------------------------------------
    values('migrated', {'hud_lines_color_own': 3, 'hud_lines_color_others': 3, 'hud_watch_path_color': 0})
    values('reset all', {'hud_lines_color_own': 5, 'hud_lines_color_others': 5, 'cl_playerfade': 1,
                         'cl_playerfade_near': 32, 'cl_playerfade_far': 128})

    # --- the pane ---------------------------------------------------------------------------
    body = sec.get('pane')
    if body is None:
        check('pane', None, 'section not in the log')
    else:
        ids = set(re.findall(r'sui_element \[(he_o_[^\]]+)\]', body))
        # Patch 661 moved hud_lines_nums to the Line labels pane; Patch 745 added the demo's two.
        want = ['he_o_hud_trail', 'he_o_hud_watch_path', 'he_o_hud_lines_board', 'he_o_hud_lines_order',
                'he_o_hud_lines_demo', 'he_o_hud_lines_color_own', 'he_o_hud_lines_color_others',
                'he_o_hud_watch_path_px', 'he_o_hud_watch_path_far', 'he_o_hud_lines_demo_far',
                'he_o_hud_lines_reveal']
        if not ids:
            check('pane', None, 'no option chips listed')
        else:
            missing = [i for i in want if i not in ids]
            extra = sorted(ids - set(want))
            check('pane: its eleven rows', not missing, 'missing %s' % missing if missing else 'all eleven listed')
            check('pane: nothing else (the nearby-player rows are gone)', not extra,
                  'also listed: %s' % extra if extra else 'no other row')
    for marker, cv, want in (('read nums a', 'hud_lines_nums', 0), ('read nums b', 'hud_lines_nums', 1),
                             ('read nums c', 'hud_lines_nums', 3), ('read nums d', 'hud_lines_nums', 2),
                             ('read own', 'hud_lines_color_own', 0), ('read others', 'hud_lines_color_others', 0)):
        values(marker, {cv: want})

    # --- your line ---------------------------------------------------------------------------
    def trail(prefix):
        got = [colours(sec[k]) for k in (prefix + ' 9', prefix + ' 10') if k in sec]
        got = [c for c in got if c and c['rows']]
        return max(got, key=lambda c: c['n']) if got else None

    plain, speed, gain = trail('own plain'), trail('own speed'), trail('own gain')
    if not plain or not speed or not gain:
        check('your line', None, 'no live line with points (plain %s, speed %s, gain %s)'
              % (bool(plain), bool(speed), bool(gain)))
    else:
        off = [r for r in plain['rows'] if not near(r, BLUE)]
        check('your line: plain blue', plain['mode'] == PLAIN and not off,
              'slot %d, mode %d, %d of %d sampled points blue' % (plain['slot'], plain['mode'],
                                                                  len(plain['rows']) - len(off), len(plain['rows'])))
        # more than one colour: alone it had no speed range and every point was the slow end's red
        check('your line: speed, over its own range', speed['mode'] == 0 and len(set(speed['rows'])) > 1,
              'mode %d, %d distinct colours in %d sampled points' % (speed['mode'], len(set(speed['rows'])),
                                                                    len(speed['rows'])))
        check('your line: gain', gain['mode'] == 1 and len(set(gain['rows'])) > 1,
              'mode %d, %d distinct colours in %d sampled points' % (gain['mode'], len(set(gain['rows'])),
                                                                    len(gain['rows'])))

    # --- the other lines, by time -------------------------------------------------------------
    def ranked(marker, place, of, why=''):
        c = colours(sec[marker]) if marker in sec else None
        if not c or not c['rows']:
            check(marker, None, 'no colour dump')
            return None
        want = by_time(place, of)
        off = [r for r in c['rows'] if not near(r, want)]
        check('%s: place %d of %d, %s%s' % (marker, place + 1, of, name(want), why),
              c['mode'] == PLAIN and c['ranked'] == 1 and c['place'] == place and c['of'] == of and not off,
              'mode %d ranked %d place %d of %d; %d of %d sampled points that colour%s'
              % (c['mode'], c['ranked'], c['place'] + 1, c['of'], len(c['rows']) - len(off), len(c['rows']),
                 (', e.g. %s' % name(off[0])) if off else ''))
        return c

    ranked('three slot 0', 2, 3)            # the 66.3 s run
    ranked('three slot 1', 1, 3)            # 6.3 s
    ranked('three slot 2', 0, 3)            # 3.3 s
    ranked('four slot 0', 3, 4)
    ranked('four slot 1', 1, 4, ' (shared)')
    ranked('four slot 3', 1, 4, ' (shared)')   # the same 6.3 s: the two share a place
    ranked('four slot 2', 0, 4)
    a = colours(sec['four slot 3']) if 'four slot 3' in sec else None
    b = colours(sec['tint slot 3']) if 'tint slot 3' in sec else None
    if not a or not b:
        check('an import\'s tint', None, 'dumps: plain %s, reading %s' % (bool(a), bool(b)))
    else:
        check('an import\'s tint: none under a plain colour',
              a['mode'] == PLAIN and a['tint'] == 0 and 0 <= a['age'] < DRAWN,
              'mode %d, drawn %.3f s ago with tint %g' % (a['mode'], a['age'], a['tint']))
        check('an import\'s tint: kept under a reading',
              b['mode'] == 0 and abs(b['tint'] - 0.55) < 0.001 and 0 <= b['age'] < DRAWN,
              'mode %d, drawn %.3f s ago with tint %g (hud_watch_path_foreign 0.55)' % (b['mode'], b['age'], b['tint']))
    ranked('leg slot 4', 0, 1, ': another leg\'s line is a list of its own')
    ranked('leg slot 2', 0, 4, ': and does not move this one')
    ranked('same slot 0', 0, 2, ': one run, watched and ticked')
    ranked('same slot 1', 0, 2, ': one run, watched and ticked')
    ranked('two slot 0', 1, 2)
    ranked('two slot 1', 0, 2)
    c = colours(sec['mode0 slot 0']) if 'mode0 slot 0' in sec else None
    if not c:
        check('mode0 slot 0', None, 'no colour dump')
    else:
        check('a demo no drawer draws is not ranked', c['ranked'] == 0 and not (0 <= c['age'] < DRAWN),
              'ranked %d; last drawn %.3f s ago' % (c['ranked'], c['age']))
    ranked('mode0 slot 1', 0, 1, ': the one line on screen')
    ranked('alone slot 0', 0, 1, ': the board\'s lines hidden')
    c = colours(sec['speed slot 0']) if 'speed slot 0' in sec else None
    if not c or not c['rows']:
        check('others: a reading when asked', None, 'no colour dump')
    else:
        check('others: a reading when asked', c['mode'] == 0 and len(set(c['rows'])) > 2,
              'mode %d, %d distinct colours in %d sampled points' % (c['mode'], len(set(c['rows'])), len(c['rows'])))

    # --- labels ----------------------------------------------------------------------------
    got = {k: marks(sec['labels ' + k]) for k in ('both', 'peaks', 'contacts') if ('labels ' + k) in sec}
    if len(got) < 3 or not all(got.values()):
        check('labels', None, 'marks traced: %s' % {k: len(v) for k, v in got.items()})
    else:
        def split(ms):
            return [l for k, _, l in ms if k in (1, 2, 3)], [l for k, _, l in ms if k in (4, 5)]
        bc, bp = split(got['both'])
        pc, pp = split(got['peaks'])
        cc, cp = split(got['contacts'])
        if not bc or not bp:
            check('labels', None, 'the view has %d contact marks and %d tops or bottoms' % (len(bc), len(bp)))
        else:
            check('labels both: every mark has its numbers', all(bc) and all(bp),
                  '%d of %d contacts, %d of %d tops and bottoms' % (sum(bc), len(bc), sum(bp), len(bp)))
            check('labels peaks: tops and bottoms only', len(pc) == len(bc) and not any(pc) and pp and all(pp),
                  '%d contacts drawn, %d labelled; %d of %d tops and bottoms labelled'
                  % (len(pc), sum(pc), sum(pp), len(pp)))
            check('labels contacts: contacts only', not cp and cc and all(cc),
                  '%d of %d contacts labelled; %d tops and bottoms drawn' % (sum(cc), len(cc), len(cp)))

    # A landing that is itself the bottom: at `peaks` its mark is where the number goes.
    # Every mark of the run, by the draw pass's own predicate (`replay marks`: lng, lnf).
    def gates(marker):
        body = sec.get(marker, '')
        on = {int(float(m.group(1))): (int(float(m.group(2))), int(float(m.group(3))))
              for m in re.finditer(r'^lng (\S+) (\S+) (\S+)', body, re.M)}
        fold = {int(float(m.group(1))) for m in re.finditer(r'^lnf (\S+) ', body, re.M)}
        return on, fold

    pk, pf = gates('marks peaks')
    bt, _ = gates('marks both')
    if not pk or not bt:
        check('labels peaks: a landing that is the bottom', None,
              'marks listed: %d at peaks, %d at both' % (len(pk), len(bt)))
    elif not pf:
        check('labels peaks: a landing that is the bottom', None, 'no such mark in this run\'s %d' % len(pk))
    else:
        contacts = [i for i, (k, _) in pk.items() if k in (1, 2, 3)]
        turns = [i for i, (k, _) in pk.items() if k in (4, 5)]
        plain = [i for i in contacts if i not in pf]
        check('labels peaks: a landing that is the bottom keeps its number',
              all(pk[i][1] for i in pf) and not any(pk[i][1] for i in plain) and all(pk[i][1] for i in turns),
              '%d marks: %d tops and bottoms, labelled %d; %d landings that are one, labelled %d; '
              '%d other contacts, labelled %d' % (len(pk), len(turns), sum(pk[i][1] for i in turns), len(pf),
                                                  sum(pk[i][1] for i in pf), len(plain), sum(pk[i][1] for i in plain)))
        check('labels both: every mark of the run', all(v for _, v in bt.values()),
              '%d of %d labelled' % (sum(v for _, v in bt.values()), len(bt)))

    bad = [w for w in ('sui_probe: no control', 'Unknown command') if w in text]
    check('no refused probe or unknown command', not bad, 'found %s' % bad if bad else 'none in the log')

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if ok is False)
    unmeasured = sum(1 for _, ok, _ in results if ok is None)
    for what, ok, detail in results:
        print('%-12s %s: %s' % ('ok' if ok else ('NOT MEASURED' if ok is None else 'FAIL'), what, detail))
    print('P632: %d passed, %d failed, %d not measured, of %d' % (passed, failed, unmeasured, len(results)))
    return 1 if failed else (2 if unmeasured else 0)


if __name__ == '__main__':
    raise SystemExit(main())
