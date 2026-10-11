#!/usr/bin/env python3
"""Patch 641's grader: a config still on the HUD's old defaults is moved to the new ones, once.

python tools/test_p641migrate.py <runlines_smoke.log of cfg/test/p641migrate.cfg>

    python tools/runlines_smoke.py ftesurf/cfg/test/p641migrate.cfg --mount --content C:/FTESurf \
        --output-dir <owned dir> --timeout 300

The cfg stands for a config that holds every old default (`seta` lines before the map) and starts
the game code three times.  Graded from the values the game prints, the one line the move prints
about itself, and the config it then saves (found beside the log's folder).  The old and new
values are tools/p637_tables.py's.

It cannot see: a real saved config from an older release (the `seta` lines stand in for one), nor
how a moved layout looks beside elements a player placed.

Three verdicts: passed (exit 0), failed (1), or a step the checks need is not in the log (2).
"""
import pathlib
import re
import sys

from p637_tables import CHANGED

STAMP = re.compile(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', re.M)
PARTNERS = {'hud_timer_x': '0.5', 'hud_speed_x': '0.5', 'hud_results_y': '0.5'}
# 14 elements (a place is one move) and 17 settings
PLACES = ('timer', 'splits', 'seq', 'trainer', 'board', 'boarding', 'speed', 'linegraph', 'debug',
          'saveloc', 'gfx', 'vote', 'net', 'results')
MOVES = len(PLACES) + sum(1 for n in CHANGED if not n.endswith(('_x', '_y')))
KEPT = {'hud_splits_x': '0.06', 'hud_splits_y': '0.2', 'hud_seq_x': '-0.25', 'hud_seq_y': '0.31',
        'hud_lines_order': '6', 'hud_timer_y': '0.0351'}
LINE = re.compile(r'^hud: (\d+) element\(s\) and setting\(s\) still on the old defaults', re.M)


def same(a, b):
    try:
        return abs(float(a) - float(b)) < 1e-6
    except (TypeError, ValueError):
        return a == b


def sections(text):
    text = STAMP.sub('', text)
    out = {}
    parts = re.split(r'^(?:P641 (.+?)|====.*)\s*$', text, flags=re.M)
    for i in range(1, len(parts) - 1, 2):
        if parts[i] is not None:
            out[parts[i].strip()] = parts[i + 1]
    return out


def reads(body):
    return {m.group(1): m.group(2) for m in re.finditer(r'^"([A-Za-z0-9_]+)" is "([^"]*)"', body or '', re.M)}


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    log = pathlib.Path(sys.argv[1])
    sec = sections(log.read_text(encoding='utf-8', errors='replace'))
    results = []

    def check(name, ok, detail):
        results.append((name, ok, detail))

    def table(name, got, want):
        if not got:
            check(name, None, 'nothing read')
            return
        bad = ['%s %s (want %s)' % (n, got.get(n, 'not read'), v) for n, v in want.items()
               if n not in got or not same(got[n], v)]
        check(name, not bad, '%d of %d%s' % (len(want) - len(bad), len(want),
                                             ('; ' + '; '.join(bad[:8])) if bad else ''))

    def said(marker):
        m = LINE.search(sec.get(marker, ''))
        return int(m.group(1)) if m else None

    first, second, third = reads(sec.get('first read')), reads(sec.get('second read')), reads(sec.get('third read'))
    table('first start: every setting saved at its old default is the owner\'s', first, CHANGED)
    table('... the axes the patch did not move are as they were, and the config is marked',
          first, dict(PARTNERS, hud_layout_rev='637'))
    if 'first' not in sec:
        check('first start: the game says what it did', None, 'section not in the log')
    else:
        check('first start: the game says how many it moved', said('first') == MOVES,
              'said %s (want %d: %d elements, %d settings)' % (said('first'), MOVES, len(PLACES), MOVES - len(PLACES)))

    saved = None
    for f in log.parent.parent.rglob('p641save.cfg'):
        saved = f.read_text(encoding='utf-8', errors='replace')
    if saved is None:
        check('the saved config', None, 'p641save.cfg not found beside the log')
    else:
        got = dict(re.findall(r'^seta (\w+) "([^"]*)"', saved, re.M))
        bad = [n for n, v in dict(CHANGED, hud_layout_rev='637').items() if n not in got or not same(got[n], v)]
        check('the config saved after it holds the new values and the mark', not bad,
              '%d of %d in the file%s' % (len(CHANGED) + 1 - len(bad), len(CHANGED) + 1,
                                          ('; not: %s' % bad[:8]) if bad else ''))

    table('second start (mark cleared): what a player touched is left -- one axis moved, a setting '
          'off its old default, a value a hair off', second, KEPT)
    table('... and a setting put back on its old default moves again', second,
          {'hud_boarding': '0', 'hud_layout_rev': '637'})
    if 'second' in sec:
        check('second start: the game says it moved that one', said('second') == 1, 'said %s (want 1)' % said('second'))
    table('third start (mark in place): what the player put back by hand is left', third,
          {'hud_timer_y': '0.035', 'hud_linegraph_plots': '1', 'hud_layout_rev': '637'})
    if 'third' in sec:
        check('third start: nothing is said', said('third') is None, 'said %s' % said('third'))

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if ok is False)
    unmeasured = sum(1 for _, ok, _ in results if ok is None)
    for name, ok, detail in results:
        print('%-12s %s: %s' % ('ok' if ok else ('NOT MEASURED' if ok is None else 'FAIL'), name, detail))
    print('P641: %d passed, %d failed, %d not measured, of %d' % (passed, failed, unmeasured, len(results)))
    return 1 if failed else (2 if unmeasured else 0)


if __name__ == '__main__':
    raise SystemExit(main())
