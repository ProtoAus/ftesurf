#!/usr/bin/env python3
"""Patch 635's arm: the TAB board's Online list (every game's, a filter switch and slider) and the
LINE heading.

python tools/p635board.py --output-dir <owned dir> [--content C:/FTESurf] [--timeout 300]
python tools/p635board.py --grade <rig>/ftesurf/logs/runlines_smoke.log

Starts THIS CHECKOUT'S surfd in a thread on 127.0.0.1:27634 over a scratch database (surf_voyager's
main board: two ranked, three Momentum, four KSF rows; bonus 1: ranked only; bonus 2: 130 rows),
puts ten Local recordings in a private overlay (tools/runlines_smoke.py --put) and runs
cfg/test/p635board.cfg there.  The board the game shows is therefore the answer of the real surfd,
not of a stand-in written from it.

Graded from the client's own prints: `scores status` (the tier asked, the footer's sentence, the
first rows' names AS DRAWN), `board_status`, `scores lines`, the panel's hit rects, each click's own
line; and from the requests surfd saw.  Three verdicts: passed (exit 0), failed (1), or a step the
checks need is not there (2: also when the port is taken or the game does not run).  --grade reads a
log again without a run; what surfd saw is then not part of the grade.

It leaves under the output dir: the overlay (runlines_smoke.py says where) and
surfd-home-<time>/ with the scratch database and surfd's log.
"""
import argparse
import os
import pathlib
import re
import socket
import subprocess
import sys
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 27634
MAP = 'surf_voyager'
STAMP = re.compile(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', re.M)
# main: tier, player, name, millis, replay id, demo hash.  Two, three and four rows, so a total
# read from the wrong tier's count is a different number; one name long enough to need cutting.
ROWS = (
    ('ranked',   '76561198000000101', 'OursFast', 60000, 11, ''),
    ('ranked',   '76561198000000102', 'OursSlow', 70000, 0, ''),
    ('momentum', '76561198000000201', 'MomWatch', 55000, 21, ''),
    ('momentum', '76561198000000202', 'MomGet',   65000, 0, 'ab' * 20),
    ('momentum', '76561198000000203', 'MomPlain', 75000, 0, ''),
    ('ksf',      '76561198000000301', 'KsfA',     50000, 0, ''),
    ('ksf',      '76561198000000302', 'KsfB',     80000, 0, ''),
    ('ksf',      '76561198000000303', 'KsfC',     85000, 0, ''),
    ('ksf',      '76561198000000304', 'KsfDWithAVeryLongName24', 90000, 0, ''),
)
COUNT = {t: sum(1 for r in ROWS if r[0] == t) for t in ('ranked', 'momentum', 'ksf')}
BY_TIME = [r[2] for r in sorted(ROWS, key=lambda r: r[3])]
SOURCE = {r[2]: {'ranked': '', 'momentum': 'momentum', 'ksf': 'ksf'}[r[0]] for r in ROWS}
TAG = {'': '', 'momentum': '[mom] ', 'ksf': '[ksf] '}
BONUS1 = ('B1Fast', 'B1Slow')           # track 1: ranked only
BIG = (60, 70)                          # track 2: ranked, ksf rows -- more than one page of 100
LOCALS = 10
SLOTS = 8
FIRST_LOCAL = 4421
REQUESTS = []


def start_surfd(home):
    home.mkdir(parents=True)
    (home / 'surfd.env').write_text('SURFD_KEY=p635-not-a-real-key\n')
    os.environ.update(SURFD_HOME=str(home), SURFD_DB=str(home / 'p635.db'),
                      SURFD_ENV=str(home / 'surfd.env'), SURFD_RUNS=str(home / 'runs'),
                      SURFD_MAPS=str(home / 'maps'), SURFD_WEBSHOTS=str(home / 'shots'),
                      SURFD_TOOLS=str(ROOT / 'tools'),
                      # a file that exists, so the start-up log has no error line of its own
                      SURFD_GAME_CODE=str(ROOT / 'ftesurf/csprogs.dat'))
    for k in ('SURFD_PUBLIC_HOST', 'SURFD_TRUSTED', 'SURFD_PROXIES', 'SURFD_ADMIN_HASH',
              'SURFD_STEAM_KEY', 'SURFD_GAME'):
        os.environ.pop(k, None)
    sys.path.insert(0, str(ROOT / 'surfd'))
    import logging
    import surfd
    from flask import request
    from werkzeug.serving import make_server
    logging.getLogger('werkzeug').setLevel(logging.ERROR)   # REQUESTS holds what matters

    conn = surfd.connect()
    when = int(time.time()) - 600

    def row(track, tier, player, name, ms, rep=0, demo=''):
        conn.execute(
            'INSERT INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate,'
            ' millis, flags, node, runid, submitted, replay_id, momdemo)'
            " VALUES (?, ?, 0, ?, 'clean', ?, ?, ?, 66.6667, ?, 0, 'p635', '', ?, ?, ?)",
            (MAP, track, tier, player, name, ms // 15, ms, when, rep, demo))

    for tier, player, name, ms, rep, demo in ROWS:
        row(0, tier, player, name, ms, rep, demo)
    for i, name in enumerate(BONUS1):
        row(1, 'ranked', '7656119800000040%d' % i, name, 30000 + i * 1005)
    for i in range(BIG[0]):
        row(2, 'ranked', '765611980000050%02d' % i, 'R%03d' % i, 40005 + i * 150)
    for i in range(BIG[1]):
        row(2, 'ksf', '765611980000060%02d' % i, 'K%03d' % i, 39000 + i * 135)
    conn.commit()
    conn.close()

    real = surfd.app.view_functions['board']

    def counted():
        REQUESTS.append((request.args.get('tier') or 'ranked', request.args.get('track') or '0'))
        return real()
    surfd.app.view_functions['board'] = counted
    server = make_server('127.0.0.1', PORT, surfd.app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def sections(text):
    text = STAMP.sub('', text)
    out = {}
    parts = re.split(r'^(?:P635 (.+?)|====.*)\s*$', text, flags=re.M)
    for i in range(1, len(parts) - 1, 2):
        if parts[i] is not None:
            out[parts[i].strip()] = parts[i + 1]
    return out


def status(body):
    """The LAST `scores status` of the section."""
    heads = list(re.finditer(r'^scores: (pinned\+held|pinned|held|closed) on ', body, re.M))
    if not heads:
        return None
    mode = heads[-1].group(1)
    body = body[heads[-1].start():]
    a = re.search(r'tab (\S+)\s+filter (\S+)\s+cols (\S+)\s+type (\S+)', body)
    b = re.search(r'list (\S+)\s+tier (\S+)\s+holds (\S+)', body)
    c = re.search(r'room list: (\S+) best', body)
    foot = re.search(r'^\s+foot "(.*)"\s*$', body, re.M)
    if not a or not b:
        return None
    return {'mode': mode, 'tab': a.group(1), 'cols': int(float(a.group(3))), 'state': int(float(b.group(1))),
            'tier': b.group(2), 'holds': int(float(b.group(3))), 'room': int(float(c.group(1))) if c else None,
            'foot': foot.group(1) if foot else None,
            'drawn': [m.group(1) for m in re.finditer(r'^\s+drawn \d+ "(.*)"\s*$', body, re.M)]}


def board(body):
    """The LAST `board_status` print of the section (`scores status` prints the store too)."""
    body = body[body.rfind('online board:'):] if 'online board:' in body else ''
    head = re.search(r'board: (\S+) track (\S+) leg (\S+)\s+tier (\S+)\s+style (\S+)', body)
    if not head or 'online board: ok' not in body:
        return None
    rows = []
    for m in re.finditer(r'^\s+(\d+)\s+(\S+)\s+(\S+)\s+ticks \S+ @ \S+ Hz\s+flags \S+\s+(.*)$', body, re.M):
        tail = m.group(4).split()
        why = 'momentum' if 'momentum' in tail else ('ksf' if 'ksf' in tail else '')
        rows.append((int(m.group(1)), m.group(2), why, 'watch' if 'watch' in tail else 'none'))
    return {'tier': head.group(4), 'rows': rows}


def rects(body):
    """`hud_edit ui`: id -> (x, y, w, h)."""
    return {m.group(1): tuple(float(v) for v in m.groups()[1:])
            for m in re.finditer(r'sui_element \[([^\]]+)\] (\S+) (\S+) (\S+) (\S+)', body)}


def lines(body):
    """`scores lines`: the keys held, from the LAST print of the section (None: no print).
    A print is its `line N <state>  <key>` rows, then one `lines: N drawn` tail."""
    tails = [m.start() for m in re.finditer(r'^\s+lines: \d+ drawn', body, re.M)]
    if not tails:
        return None
    start = tails[-2] if len(tails) > 1 else 0
    return [k for _, _, k in re.findall(r'^\s+line (\d+) (.+?)  (\S+)', body[start:tails[-1]], re.M)]


def read(body, cvar):
    m = re.search(r'"%s" is "([^"]*)"' % cvar, body or '')
    return m.group(1) if m else None


def grade(text, requests, rig):
    sec = sections(text)
    results = []

    def check(name, ok, detail):
        results.append((name, ok, detail))

    def need(marker):
        if marker not in sec:
            check(marker, None, 'section not in the log')
            return None
        return sec[marker]

    def listed(marker, tier, state, names, holds, foot):
        """One list: what was asked, its rows, their sources, the total and the footer's sentence."""
        body = need(marker)
        if body is None:
            return None
        st, bd = status(body), board(body)
        if not st or not bd:
            check(marker, None, 'status %s, board %s' % (bool(st), bool(bd)))
            return None
        got = [n for _, n, _, _ in bd['rows']]
        ranks = [r for r, _, _, _ in bd['rows']]
        why = [(n, w) for _, n, w, _ in bd['rows'] if w != SOURCE.get(n, w)]
        check('%s: asks surfd for %s' % (marker, tier), st['tier'] == tier and bd['tier'] == tier
              and st['state'] == state, 'list %d, asks %s, holds a %s board' % (st['state'], st['tier'], bd['tier']))
        check('%s: its rows, in time order' % marker, got == names and ranks == list(range(1, len(names) + 1)),
              '%s ranks %s' % (' '.join(got) or '(none)', ranks))
        check('%s: each row says its source' % marker, not why,
              ('wrong: %s' % why) if why else (', '.join('%s %s' % (n, w or 'ours') for _, n, w, _ in bd['rows']) or 'no rows'))
        check('%s: the total and the footer' % marker, st['holds'] == holds and st['foot'] == foot,
              'holds %d (want %d); footer "%s"%s' % (st['holds'], holds, st['foot'],
                                                     '' if st['foot'] == foot else ' -- want "%s"' % foot))
        return st

    ours = [n for n in BY_TIME if SOURCE[n] == '']
    mom = [n for n in BY_TIME if SOURCE[n] == 'momentum']
    ksf = [n for n in BY_TIME if SOURCE[n] == 'ksf']
    total = len(ROWS)

    # --- the default: every game's ---------------------------------------------------------
    st = listed('default', 'combined', 1, BY_TIME, total, '%d clean time(s) on main, every game' % total)
    body = need('default')
    if body is not None:
        check('default: the filter is off on a fresh config',
              read(body, 'sb_filter') == '0' and read(body, 'sb_filter_src') == '0',
              'sb_filter %r, sb_filter_src %r' % (read(body, 'sb_filter'), read(body, 'sb_filter_src')))
        r = rects(body)
        ids = ['sb_t0', 'sb_t1', 'sb_t2', 'sb_flt', 'sb_src0', 'sb_src1', 'sb_src2', 'sb_tref']
        if not r:
            check('default: the header', None, 'no controls listed')
        elif any(i not in r for i in ids) or 'sb_t3' in r:
            check('default: the header\'s controls', False,
                  'missing %s; a fourth tab: %s' % ([i for i in ids if i not in r], 'sb_t3' in r))
        else:
            # left to right, none over the next, all on the tabs' row
            edge = [(i, r[i][0], r[i][0] + r[i][2]) for i in ids]
            over = [(a[0], b[0]) for a, b in zip(edge, edge[1:]) if a[2] > b[1] + 0.5]
            rows_y = {i: (r[i][1], r[i][1] + r[i][3]) for i in ids}
            off = [i for i in ids if rows_y[i][1] < rows_y['sb_t0'][0] or rows_y[i][0] > rows_y['sb_t0'][1]]
            check('default: tabs, the switch, three stops, refresh -- left to right, none over the next',
                  not over and not off, 'x: %s%s%s' % (', '.join('%s %.0f-%.0f' % e for e in edge),
                                                       ('; OVERLAP %s' % over) if over else '',
                                                       ('; off the row: %s' % off) if off else ''))
        if st:
            check('default: no tag where the WHY column is drawn', st['cols'] == 9 and st['drawn'] == BY_TIME,
                  '%d columns; drawn %s' % (st['cols'], st['drawn']))
            check('default: the room list has its own board', st['room'] == COUNT['ranked'],
                  'room list holds %s best times beside a merged list (want %d)' % (st['room'], COUNT['ranked']))
    body = need('narrow')
    if body is not None:
        st = status(body)
        if not st or not st['drawn']:
            check('narrow', None, 'no status, or no names printed')
        else:
            want = [TAG[SOURCE[n]] + n for n in BY_TIME]
            cut = [d for d in st['drawn'] if d.endswith('..')]
            whole = [d == w for d, w in zip(st['drawn'], want) if not d.endswith('..')]
            starts = [d[:-2] == w[:len(d) - 2] for d, w in zip(st['drawn'], want) if d.endswith('..')]
            check('narrow: the WHY column gone, each import tagged before its name',
                  st['cols'] < 9 and len(st['drawn']) == len(want) and all(whole) and all(starts),
                  '%d columns; drawn %s' % (st['cols'], st['drawn']))
            check('narrow: a name too long for its column is cut', len(cut) >= 1 and all(len(d) < len(w) for d, w in zip(st['drawn'], want) if d.endswith('..')),
                  '%d cut: %s' % (len(cut), cut))

    # --- the filter: the slider's three stops, and the switch -------------------------------
    for marker, tier, state, names, word, src in (
            ('ftesurf', 'ranked', 0, ours, 'clean', '0'), ('momentum', 'momentum', 2, mom, 'Momentum', '1'),
            ('ksf', 'ksf', 3, ksf, 'KSF', '2')):
        listed(marker, tier, state, names, len(names), '%d %s time(s) on main' % (len(names), word))
        body = need(marker)
        if body is not None:
            check('%s: a press on its stop turns the filter on there, saved' % marker,
                  read(body, 'sb_filter') == '1' and read(body, 'sb_filter_src') == src,
                  'sb_filter %r, sb_filter_src %r' % (read(body, 'sb_filter'), read(body, 'sb_filter_src')))
    listed('off', 'combined', 1, BY_TIME, total, '%d clean time(s) on main, every game' % total)
    body = need('off')
    if body is not None:
        check('off: the switch alone, the stop kept', read(body, 'sb_filter') == '0' and read(body, 'sb_filter_src') == '2',
              'sb_filter %r, sb_filter_src %r' % (read(body, 'sb_filter'), read(body, 'sb_filter_src')))
    body = need('on')
    if body is not None:
        st = status(body)
        check('on: the switch again, back on the stop it was left at',
              bool(st) and st['tier'] == 'ksf' and read(body, 'sb_filter') == '1' and read(body, 'sb_filter_src') == '2',
              'asks %s; sb_filter %r, sb_filter_src %r' % (st and st['tier'], read(body, 'sb_filter'), read(body, 'sb_filter_src')))
    body = need('held')
    if body is not None:
        st = status(body)
        took = re.findall(r'vote key: scan 512 down (\S+) took (\S+)', body)
        if not st or len(took) < 2:
            check('held', None, 'status %s, key events %s' % (bool(st), took))
        else:
            check('a mouse1 on a board that is only held reaches no control',
                  read(body, 'sb_filter') == '0' and st['tier'] == 'combined' and st['mode'] == 'held',
                  'the board is %s; sb_filter %r after the press, asks %s; the events were taken: %s'
                  % (st['mode'], read(body, 'sb_filter'), st['tier'], [t for _, t in took]))

    # --- what a saved config holds -------------------------------------------------------------
    saved = None
    if rig is not None:
        for f in rig.rglob('p635save.cfg'):
            saved = f.read_text(encoding='utf-8', errors='replace')
    if saved is None:
        check('saved config', None, 'p635save.cfg not found under the rig')
    else:
        got = dict(re.findall(r'^seta (sb_filter(?:_src)?) "([^"]*)"', saved, re.M))
        check('saved config: the switch and the stop', got == {'sb_filter': '1', 'sb_filter_src': '1'},
              'holds %s' % got)

    # --- the LINE heading --------------------------------------------------------------------
    watch = sorted('r%d:0' % r[4] for r in ROWS if r[4])
    for marker, said, want, what in (
            ('lineall online', '2 ticked', watch, 'the rows with a recording on surfd, and no other'),
            ('lineall online again', '2 unticked', [], 'the same click unticks them'),
            ('head click', '2 ticked', watch, 'a click on the heading is that command')):
        body = need(marker)
        if body is None:
            continue
        got = lines(body)
        if got is None:
            check(marker, None, 'no `scores lines` print')
            continue
        per = len(re.findall(r'^scores: line \d+ o[nf]', STAMP.sub('', body), re.M))
        check('%s: %s' % (marker, what),
              ('scores: lines: %s' % said) in body and sorted(got) == want and per == 0,
              'said %s; lines held: %s; %d lines of console print besides'
              % (re.findall(r'scores: lines: ([^\n]+)', body), got, per))
    body = need('lineall online')
    if body is not None:
        st = status(body)
        check('lineall online: the footer says what the click did', bool(st) and st['foot'] == 'lines: 2 ticked',
              'footer "%s"' % (st and st['foot']))

    # --- legs ------------------------------------------------------------------------------------
    body = need('bonus 1')
    if body is not None:
        st, bd = status(body), board(body)
        if not st or not bd:
            check('bonus 1', None, 'status %s, board %s' % (bool(st), bool(bd)))
        else:
            check('a leg with our times only: every game\'s list is those',
                  st['tier'] == 'combined' and [n for _, n, _, _ in bd['rows']] == list(BONUS1)
                  and st['foot'] == '2 clean time(s) on bonus 1, every game',
                  'asks %s; rows %s; footer "%s"' % (st['tier'], [n for _, n, _, _ in bd['rows']], st['foot']))
    body = need('bonus 1 momentum')
    if body is not None:
        st, bd = status(body), board(body)
        if not st or not bd:
            check('bonus 1 momentum', None, 'status %s, board %s' % (bool(st), bool(bd)))
        else:
            check('... and one game\'s alone is empty there, and says whose',
                  st['tier'] == 'momentum' and not bd['rows'] and st['foot'] == '0 Momentum time(s) on bonus 1',
                  'asks %s; %d rows; footer "%s"' % (st['tier'], len(bd['rows']), st['foot']))
    body = need('bonus 2')
    if body is not None:
        st = status(body)
        want = '100 clean time(s) on bonus 2, every game  (top 100 of %d shown)' % sum(BIG)
        if not st:
            check('bonus 2', None, 'no status')
        else:
            check('more than a page: the footer says how many there are',
                  st['tier'] == 'combined' and st['holds'] == sum(BIG) and st['foot'] == want,
                  'holds %d; footer "%s"' % (st['holds'], st['foot']))

    # --- tabs ------------------------------------------------------------------------------------
    body = need('segmented')
    if body is not None:
        st, r = status(body), rects(body)
        if not st or not r:
            check('segmented', None, 'status %s, controls %d' % (bool(st), len(r)))
        else:
            check('segmented: ours alone, and no filter drawn',
                  st['tab'] == 'segmented' and st['tier'] == 'ranked' and st['state'] == 0
                  and not any(i in r for i in ('sb_flt', 'sb_src0')),
                  'tab %s asks %s; filter listed: %s' % (st['tab'], st['tier'], 'sb_flt' in r))
    listed('legacy', 'imported', 4, [n for n in BY_TIME if SOURCE[n]], COUNT['momentum'] + COUNT['ksf'],
           '%d imported time(s) on main' % (COUNT['momentum'] + COUNT['ksf']))
    body = need('legacy cleared')
    if body is not None:
        st = status(body)
        check('`scores tab imported` does not outlive the tab (two arrow keys)',
              bool(st) and st['tab'] == 'online' and st['state'] == 1 and st['tier'] == 'combined',
              ('tab %s, list %d, asks %s' % (st['tab'], st['state'], st['tier'])) if st else 'no status')

    # --- Local ------------------------------------------------------------------------------------
    first = ['l:data/runs/%s/main/%07d_run.rec' % (MAP, FIRST_LOCAL + i) for i in range(SLOTS)]
    body = need('local')
    if body is not None:
        got, st = lines(body), status(body)
        if got is None:
            check('local', None, 'no `scores lines` print')
        else:
            check('local: %d rows, the FIRST %d ticked, and the footer says so' % (LOCALS, SLOTS),
                  ('scores: lines: %d ticked, the first of %d' % (SLOTS, LOCALS)) in body and sorted(got) == first
                  and bool(st) and (st['foot'] or '').startswith('lines: %d ticked, the first of %d' % (SLOTS, LOCALS)),
                  'said %s; %d lines held, the first %d: %s; footer "%s"'
                  % (re.findall(r'scores: lines: ([^\n]+)', body), len(got), SLOTS, sorted(got) == first, st and st['foot']))
    body = need('full')
    if body is not None:
        st = status(body)
        check('full: the Online list says why it ticked none, in the footer too',
              'slots hold lines of other lists' in body and bool(st) and 'slots hold lines of other lists' in (st['foot'] or ''),
              'said %s; footer "%s"' % (re.findall(r'scores: lines: ([^\n]+)', body), st and st['foot']))
    body = need('local off')
    if body is not None:
        got = lines(body)
        check('local off: the same click unticks all %d' % SLOTS,
              ('scores: lines: %d unticked' % SLOTS) in body and got == [],
              'said %s; lines held: %s' % (re.findall(r'scores: lines: ([^\n]+)', body), got))

    # --- what surfd saw ------------------------------------------------------------------------
    if requests is not None:
        tiers = [t for t, _ in requests]
        per = {t: tiers.count(t) for t in sorted(set(tiers))}
        check('surfd: every list asked for, none hammered',
              all(per.get(t, 0) >= 1 for t in ('ranked', 'combined', 'momentum', 'ksf', 'imported'))
              and len(requests) <= 60, '%d board requests: %s' % (len(requests), per))
        # Not the room list's request: a build whose room list never asked passed a cut of this
        # line that looked for a ranked request among the first three (the FTESurf stop's click
        # is one).  The room list is graded by its own count, above.
        check('surfd: the first request it saw is for every game\'s list',
              bool(requests) and requests[0] == ('combined', '0'), 'the first three: %s' % requests[:3])

    bad = [w for w in ('sui_probe: no control', 'Unknown command') if w in text]
    check('no refused probe or unknown command', not bad, 'found %s' % bad if bad else 'none in the log')

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if ok is False)
    unmeasured = sum(1 for _, ok, _ in results if ok is None)
    for name, ok, detail in results:
        print('%-12s %s: %s' % ('ok' if ok else ('NOT MEASURED' if ok is None else 'FAIL'), name, detail))
    print('P635: %d passed, %d failed, %d not measured, of %d' % (passed, failed, unmeasured, len(results)))
    return 1 if failed else (2 if unmeasured else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--output-dir', type=pathlib.Path)
    ap.add_argument('--content', type=pathlib.Path, default=pathlib.Path('C:/FTESurf'))
    ap.add_argument('--timeout', type=int, default=300)
    ap.add_argument('--grade', type=pathlib.Path, help='grade this log; no run')
    a = ap.parse_args()
    if a.grade:
        text = a.grade.read_text(encoding='utf-8', errors='replace')
        return grade(text, None, a.grade.parent.parent.parent)
    if not a.output_dir:
        ap.error('--output-dir or --grade')
    out = a.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(('127.0.0.1', PORT))
    except OSError as exc:
        print('P635: not measured -- 127.0.0.1:%d is held by something else (%s)' % (PORT, exc))
        return 2
    home = out / ('surfd-home-%d' % int(time.time()))
    server = start_surfd(home)
    print('surfd (this checkout) on 127.0.0.1:%d; its scratch home stays at %s' % (PORT, home))
    before = set(out.glob('ftesurf-runlines-*'))
    rec = ROOT / 'ftesurf/cfg/test/p492voy.rec'
    cmd = [sys.executable, '-B', str(ROOT / 'tools/runlines_smoke.py'),
           str(ROOT / 'ftesurf/cfg/test/p635board.cfg'), '--mount', '--content', str(a.content),
           '--output-dir', str(out), '--timeout', str(a.timeout)]
    for i in range(LOCALS):
        cmd += ['--put', 'data/runs/%s/main/%07d_run.rec=%s' % (MAP, FIRST_LOCAL + i, rec)]
    try:
        run = subprocess.run(cmd, capture_output=True, text=True)
    finally:
        server.shutdown()
    print(run.stdout.strip())
    rigs = sorted(set(out.glob('ftesurf-runlines-*')) - before)
    if run.returncode or len(rigs) != 1:
        print(run.stderr.strip()[-2000:])
        print('P635: not measured -- the run did not complete (exit %d, %d new rigs)' % (run.returncode, len(rigs)))
        return 2
    log = rigs[0] / 'ftesurf/logs/runlines_smoke.log'
    print('rig %s' % rigs[0])
    return grade(log.read_text(encoding='utf-8', errors='replace'), list(REQUESTS), rigs[0])


if __name__ == '__main__':
    raise SystemExit(main())
