#!/usr/bin/env python3
"""Grade cfg/test/p631boarding.cfg's log (Patch 631: the Boarding window's levels).

python tools/runlines_smoke.py ftesurf/cfg/test/p631boarding.cfg --mount --output-dir <dir>
      (again with --dedicated --map surf_kitsune --server-arg "+set run_startjitter 0",
       and once more with --server-arg "+set sv_minping 120" added)
python tools/test_p631boarding.py <log> [<log> ...]

Every number is the client's own `boarding` print.  What a level is held against:
  live    the speedometer's e, printed in flight BEFORE the board (energy is kept in a
          fall, so the enter must read it), and the same ride on another kind of server
          when more than one log is given: the first cut read 139 on a listen server and
          42 behind 120 ms for one fall, and its checks, which compared the window with
          the Segments column, passed, because the column made the same mistake.
  replay  the recording itself: the energy of the sample before each board record.
The column is still compared, as two displays that must agree.  Three verdicts:
passed (exit 0), failed (1), or a step the checks need is not in a log (2).
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REC = ROOT / 'ftesurf/cfg/test/p492voy.rec'
STAMP = re.compile(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', re.M)
TOL = 0.15              # two prints of one number, a decimal each
FALL = 3.0              # a tick of flight between two readings of one energy
GRAVITY = 800.0
AIR, RAMP, BOARD = 1, 2, 3


def sections(text):
    text = STAMP.sub('', text)
    out = {}
    parts = re.split(r'^(?:P631 (.+?)|====.*)\s*$', text, flags=re.M)
    for i in range(1, len(parts) - 1, 2):
        if parts[i] is not None:
            out[parts[i].strip()] = parts[i + 1]
    return out


def parse(body):
    """One `boarding` print, or None when the section has none."""
    e = re.search(r'boarding: enter (\S+) u/s (\S+)e \(raw (\S+) ref (\S+)\) ok (\S+) cost (\S+) age (\S+)', body)
    l = re.search(r'boarding: leave (\S+) u/s (\S+)e \(raw (\S+) ref (\S+)\) ok (\S+) age (\S+)', body)
    z = re.search(r'boarding: zero now (\S+) e now (\S+)', body)
    if not (e and l and z):
        return None
    enter = dict(zip(('speed', 'level', 'raw', 'ref', 'ok', 'cost', 'age'), (float(v) for v in e.groups())))
    leave = dict(zip(('speed', 'level', 'raw', 'ref', 'ok', 'age'), (float(v) for v in l.groups())))
    rows = [(int(m.group(2)), float(m.group(3)))
            for m in re.finditer(r'boarding: row (\S+) kind (\S+) level (\S+)', body)]
    return {'enter': enter, 'leave': leave, 'zero': float(z.group(1)), 'enow': float(z.group(2)), 'rows': rows}


def recording():
    """[(board time, energy of the sample before its record)] from the fixture, in file order."""
    out, prev = [], None
    for line in REC.read_text(encoding='utf-8', errors='replace').splitlines():
        f = line.split()
        if not f:
            continue
        if f[0] == 'board' and len(f) >= 9 and prev is not None:
            out.append((float(f[1]), prev))
        elif (line[0].isdigit() or line[0] == '-') and len(f) >= 7:
            x = [float(v) for v in f[:7]]
            prev = x[3] + (x[4] * x[4] + x[5] * x[5] + x[6] * x[6]) / (2 * GRAVITY)
    return out


def grade(path, results):
    text = pathlib.Path(path).read_text(encoding='utf-8', errors='replace')
    sec = {k: parse(v) for k, v in sections(text).items()}
    name = pathlib.Path(path).parts[-5] if len(pathlib.Path(path).parts) >= 5 else str(path)

    def check(what, ok, detail):
        results.append(('%s: %s' % (name, what), ok, detail))

    # --- live: the enter against the energy held in flight --------------------------------
    steps = [(k, sec[k]) for k in ('riding 1', 'riding 2', 'riding 3', 'riding 4', 'after') if sec.get(k)]
    fresh = [(k, s) for k, s in steps if s['enter']['ok'] == 1 and 0 <= s['enter']['age'] < 5]
    before = [(k, s) for k, s in steps if not (s['enter']['age'] >= 0)]
    summary = None
    if not fresh or not before:
        check('live: the enter is the energy held in flight', None,
              '%d steps before a board, %d after one' % (len(before), len(fresh)))
    else:
        k, s = fresh[0]
        flight = before[-1][1]['enow']
        check('live: the enter is the energy held in flight', abs(s['enter']['level'] - flight) <= FALL,
              'enter %.1fe at %s; the speedometer read %.1f at %s, before the board (cost %.1f)'
              % (s['enter']['level'], k, flight, before[-1][0], s['enter']['cost']))
        # the air row the board closed is in the column on that same step
        if s['rows'] and s['rows'][-1][0] == AIR:
            check('live: the column\'s air row ends on the flight\'s energy too',
                  abs(s['rows'][-1][1] - flight) <= FALL,
                  'air row %.1f at %s, the speedometer %.1f in flight' % (s['rows'][-1][1], k, flight))
        summary = [s['enter']['level'], None]

    after = sec.get('after')
    if not after:
        check('live: after the ride', None, 'section not in the log')
    else:
        en, le, rows = after['enter'], after['leave'], after['rows']
        both = en['ok'] == 1 and le['ok'] == 1 and 0 <= le['age'] < en['age'] < 10
        check('live: both ends stamped, the leave after the enter', both,
              'enter ok %g %.2f s ago, leave ok %g %.2f s ago' % (en['ok'], en['age'], le['ok'], le['age']))
        # the ride's three rows: the last air, board, ramp run in what the column holds (behind
        # 120 ms the fall after the ramp had become a row of its own by this print)
        kinds = [k for k, _ in rows]
        at = [i for i in range(len(rows) - 2) if kinds[i:i + 3] == [AIR, BOARD, RAMP]]
        # one board in the ride: its leave is comparable with another server's
        if both and summary and kinds.count(BOARD) == 1:
            summary[1] = le['level']
        if not at:
            check('live: the column holds air, board, ramp', None, 'its rows are kinds %s' % kinds)
        else:
            air, board, ramp = (lv for _, lv in rows[at[-1]:at[-1] + 3])
            check('live: window and column agree', abs(air - en['level']) <= TOL
                  and abs(board - (en['level'] - en['cost'])) <= TOL and abs(ramp - le['level']) <= TOL,
                  'air %.1f / enter %.1f; board %.1f / enter less cost %.1f; ramp %.1f / leave %.1f'
                  % (air, en['level'], board, en['level'] - en['cost'], ramp, le['level']))

        moved = [(k, sec[k]) for k in ('moved 1', 'moved 2') if sec.get(k)]
        real = [(k, s) for k, s in moved if abs(s['zero'] - en['ref']) > 1]
        still = [k for k, s in moved if abs(s['zero'] - en['ref']) <= 1]
        if not real:
            check('live: levels keep their own zero', None,
                  'the zero never moved by more than 1: %s' % [(k, s['zero']) for k, s in moved])
        for k, s in real:
            same = (s['enter']['level'] == en['level'] and s['leave']['level'] == le['level']
                    and s['enter']['ref'] == en['ref'] and s['leave']['ref'] == le['ref'])
            check('live: levels keep their own zero (%s)' % k, same,
                  'zero now %.2f against %.2f; enter %.1f leave %.1f, were %.1f and %.1f%s'
                  % (s['zero'], en['ref'], s['enter']['level'], s['leave']['level'], en['level'], le['level'],
                     ('; %s did not move the zero and is not used' % ', '.join(still)) if still else ''))

    # --- a counter that is not news ---------------------------------------------------------
    for marker, what in (('after map', 'a new map shows no board'), ('after stop', 'closing a replay shows no board')):
        s = sec.get(marker)
        if not s:
            check(what, None, 'section "%s" not in the log' % marker)
        else:
            check(what, s['enter']['age'] < 0 and s['leave']['age'] < 0,
                  'enter %.2f s ago (%.1f u/s), leave %.2f s ago; -1 is never'
                  % (s['enter']['age'], s['enter']['speed'], s['leave']['age']))

    # --- replay: the enter against the recording ---------------------------------------------
    steps = [(float(k[7:]), s) for k, s in sec.items() if k.startswith('replay ') and s]
    boards = recording()
    usable, bad, zero = [], [], []
    for t, s in steps:
        if s['enter']['ok'] != 1 or s['enter']['age'] < 0:
            continue
        there = [b for b in boards if b[0] <= t + 0.001]
        if not there:
            continue
        usable.append(t)
        if abs(s['enter']['raw'] - there[-1][1]) > FALL:
            bad.append((t, s['enter']['raw'], round(there[-1][1], 2)))
        if abs(s['enter']['level'] - (s['enter']['raw'] - s['zero'])) > TOL:
            zero.append((t, s['enter']['level'], round(s['enter']['raw'] - s['zero'], 1)))
    if len(usable) < 3:
        check('replay: the enter is the recording\'s energy before the board', None,
              '%d of %d steps have a board behind them (3 wanted)' % (len(usable), len(steps)))
    else:
        check('replay: the enter is the recording\'s energy before the board', not bad,
              '%d steps%s' % (len(usable), (': %s' % bad) if bad else ' within %.0f of the sample before each record' % FALL))
        check('replay: read against the speedometer\'s zero, now', not zero,
              ('%s' % zero) if zero else 'level = raw less the zero now at all %d' % len(usable))
    if steps:
        shown = [t for t, s in steps if s['leave']['age'] >= 0]
        check('replay: no leave row (a replay has none)', not shown,
              'shown at %s' % shown if shown else 'blank at all %d' % len(steps))

    bad = [w for w in ('Unknown command',) if w in text]
    check('no unknown command', not bad, 'found %s' % bad if bad else 'none in the log')
    return name, summary


def main():
    results, rides = [], []
    for path in sys.argv[1:]:
        name, summary = grade(path, results)
        if summary:
            rides.append((name, summary))
    if len(sys.argv) > 2:
        for i, what in ((0, 'enter'), (1, 'leave')):
            v = [(n, s[i]) for n, s in rides if s[i] is not None]
            if len(v) < 2:
                results.append(('one ride on every server: the %s level' % what, None,
                                '%d logs hold a ride with one board' % len(v)))
            else:
                results.append(('one ride on every server: the %s level' % what,
                                max(x for _, x in v) - min(x for _, x in v) <= FALL,
                                ', '.join('%s %.1f' % (n, x) for n, x in v)))
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if ok is False)
    unmeasured = sum(1 for _, ok, _ in results if ok is None)
    for name, ok, detail in results:
        print('%-12s %s: %s' % ('ok' if ok else ('NOT MEASURED' if ok is None else 'FAIL'), name, detail))
    print('P631: %d passed, %d failed, %d not measured, of %d' % (passed, failed, unmeasured, len(results)))
    return 1 if failed else (2 if unmeasured else 0)


if __name__ == '__main__':
    raise SystemExit(main())
