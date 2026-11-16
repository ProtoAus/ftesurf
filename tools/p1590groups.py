#!/usr/bin/env python3
"""P1590's arm: the TAB board's mode row, Groups lines and leg badges, against THIS checkout's surfd.

python tools/p1590groups.py --output-dir <owned dir> --csqc <csprogs.dat> --mqc <menu.dat> --ssqc <qwprogs.dat>
python tools/p1590groups.py --grade <rig>/ftesurf/logs/runlines_smoke.log

surfd runs in a thread on 127.0.0.1:27636 over a scratch database: surf_voyager main, 150 Momentum
times (60.000 s + 0.1 s a rank) and ranked times placed in every group; bonus 1, 40 KSF times and
the player's own; main `sw`, 30 KSF; main `segmented` and `tas`, two rows each. ONE SEAM: the
client's `me` is whatever its *phash is, which a listen server's client may not have, so surfd's
_game_player answers every `me` with the fixture player (test_groups.py covers the real lookup).
Graded from the client's `scores status` (the mode, the groups store, each row's group, each leg's
badge) and from the requests surfd saw. 0 passed, 1 failed, 2 not measured.
"""
import argparse
import math
import os
import pathlib
import re
import socket
import subprocess
import sys
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 27636
MAP = 'surf_voyager'
STAMP = re.compile(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', re.M)
MOM = [60000 + i * 100 for i in range(150)]
# ranked main times: one per group and two past the cutoff; the player's own is 61800 (rank 19: G2)
RANKED = [60500, 61000, 61300, 62500, 63000, 64000, 65500, 68000, 72000, 80000]
MINE_MAIN, MINE_B1 = 61800, 47000
KSF_B1 = [40000 + i * 250 for i in range(40)]
KSF_SW = [90000 + i * 300 for i in range(30)]
REQUESTS = []


def half_up(v):
    return int(math.floor(v + 0.5))


def ranks(x):
    """Independent of surfd: Lex's calculator (16 Nov), defaults."""
    cut = min(x, max(100, half_up(0.67 * x)))
    e = [min(cut, max(15, 10 + half_up(0.02 * x)))]
    for i in range(1, 6):
        v = cut if i == 5 else half_up(e[0] * (cut / e[0]) ** (i / 5))
        e.append(min(cut, max(v, e[-1] + 5)))
    return [10] + e


def group(ms, board):
    """A time's group by its place on the reference board: 1 + the times strictly faster."""
    place = 1 + sum(1 for t in board if t < ms)
    for i, r in enumerate(ranks(len(board))):
        if place <= r:
            return i
    return 7


def start_surfd(home):
    home.mkdir(parents=True)
    (home / 'surfd.env').write_text('SURFD_KEY=p1590-not-a-real-key\n')
    os.environ.update(SURFD_HOME=str(home), SURFD_DB=str(home / 'p1590.db'),
                      SURFD_ENV=str(home / 'surfd.env'), SURFD_RUNS=str(home / 'runs'),
                      SURFD_MAPS=str(home / 'maps'), SURFD_WEBSHOTS=str(home / 'shots'),
                      SURFD_TOOLS=str(ROOT / 'tools'))
    for k in ('SURFD_PUBLIC_HOST', 'SURFD_TRUSTED', 'SURFD_PROXIES', 'SURFD_ADMIN_HASH',
              'SURFD_STEAM_KEY', 'SURFD_GAME'):
        os.environ.pop(k, None)
    sys.path.insert(0, str(ROOT / 'surfd'))
    import logging
    import surfd
    import ksfimport
    from flask import request
    from werkzeug.serving import make_server
    logging.getLogger('werkzeug').setLevel(logging.ERROR)

    def no_network(*a, **k):
        raise AssertionError('no network in the arm')
    ksfimport.fetch = no_network
    conn = surfd.connect()
    when = int(time.time()) - 600
    n = [0]

    def row(track, tier, style, player, ms):
        n[0] += 1
        conn.execute(
            'INSERT INTO runs (map, track, leg, tier, style, player, name, ticks, tickrate,'
            ' millis, flags, node, runid, submitted, replay_id)'
            " VALUES (?, ?, 0, ?, ?, ?, ?, ?, 100, ?, 0, 'p1590', '', ?, 0)",
            (MAP, track, tier, style, player, player[-8:], ms // 10, ms, when + n[0]))

    for i, ms in enumerate(MOM):
        row(0, 'momentum', 'clean', 'mom%05d' % i, ms)
    for i, ms in enumerate(RANKED):
        row(0, 'ranked', 'clean', 'ours%04d' % i, ms)
    row(0, 'ranked', 'clean', 'fixture-me', MINE_MAIN)
    for i, ms in enumerate(KSF_B1):
        row(1, 'ksf', 'clean', 'ksfb%04d' % i, ms)
    row(1, 'ranked', 'clean', 'fixture-me', MINE_B1)
    for i, ms in enumerate(KSF_SW):
        row(0, 'ksf', 'sw', 'ksfs%04d' % i, ms)
    row(0, 'ranked', 'segmented', 'fixture-me', 58000)
    row(0, 'ranked', 'segmented', 'segother', 59000)
    row(0, 'community', 'tas', 'fixture-me', 50000)
    row(0, 'community', 'tas', 'tasother', 52000)
    conn.commit()
    conn.close()
    surfd._game_player = lambda db, who, now: ('f1590f1590f1', 'fixture-me') if who else (who, None)

    real = surfd.app.view_functions['board']

    def counted():
        REQUESTS.append(dict(request.args))
        return real()
    surfd.app.view_functions['board'] = counted
    server = make_server('127.0.0.1', PORT, surfd.app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def sections(text):
    text = STAMP.sub('', text)
    parts = re.split(r'^P1590 (\S+)\s*$', text, flags=re.M)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def status(body):
    m = re.search(r'^\s+mode (.+?)   groups (\S*), (\S+) legs', body, re.M)
    if not m:
        return None
    leg = re.search(r'^\s+groups leg: (.+?), cuts ([\d ]+)$', body, re.M)
    rows = re.search(r'^\s+groups rows:([-\d ]*)$', body, re.M)
    badges = re.search(r'^\s+groups badges:(.*)$', body, re.M)
    tab = re.search(r'tab (\S+)\s+filter (\S+)', body)
    style = re.search(r'^\s+style (\S+)', body, re.M)
    return {'mode': m.group(1), 'key': m.group(2), 'legs': float(m.group(3)),
            'src': leg.group(1) if leg else None,
            'cuts': [int(float(v)) for v in leg.group(2).split()] if leg else None,
            'rows': [int(float(v)) for v in rows.group(1).split()] if rows else None,
            'badges': dict(b.split('=') for b in badges.group(1).split()) if badges else {},
            'tab': tab.group(1) if tab else None, 'filter': tab.group(2) if tab else None,
            'style': style.group(1) if style else None}


def grade(text, requests):
    sec = sections(text)
    results = []

    def check(name, ok, detail):
        results.append((name, ok, detail))

    def get(marker):
        if marker not in sec:
            check(marker, None, 'section not in the log')
            return None
        st = status(sec[marker])
        if st is None:
            check(marker, None, 'no status print')
        return st

    cuts_main = [MOM[r - 1] for r in ranks(len(MOM))]
    merged = sorted(MOM + RANKED + [MINE_MAIN])
    ours = sorted(RANKED + [MINE_MAIN])
    st = get('normal')
    if st:
        check('normal: Normal lit, the clean board', st['mode'] == 'Normal' and st['style'] == 'clean',
              'mode %s style %s' % (st['mode'], st['style']))
        check('normal: the ladder is Momentum\'s 150 times, cut at its ranks',
              st['src'] == 'Momentum, 150 times' and st['cuts'] == cuts_main,
              '%s cuts %s (want %s)' % (st['src'], st['cuts'], cuts_main))
        want = [group(ms, MOM) for ms in merged[:24]]
        check('normal: each row of every game\'s list in its group', st['rows'] == want,
              'rows %s (want %s)' % (st['rows'], want))
        check('normal: your badges -- main G2, bonus 1 from KSF', st['badges'].get('main') == 'G2'
              and st['badges'].get('bonus_1') == FS(group(MINE_B1, KSF_B1)),
              'badges %s' % st['badges'])
    st = get('ours')
    if st:
        want = [group(ms, MOM) for ms in ours]
        check('ours: World of Surf rows only, lines where the group changes', st['rows'] == want
              and len(set(want)) >= 7, 'rows %s (want %s)' % (st['rows'], want))
    st = get('segmented')
    if st:
        check('segmented: Segmented lit, no ladder, no badges', st['mode'] == 'Segmented'
              and st['style'] == 'segmented' and st['tab'] == 'segmented' and st['src'] is None
              and not st['badges'], '%s' % st)
    st = get('styleword')
    if st:
        check('console: `scores style hsw` on Segmented is the Half-Sideways mode', st['mode'] == 'Half-Sideways'
              and st['style'] == 'hsw' and st['tab'] == 'online', '%s' % st)
    st = get('segword')
    if st:
        check('console: `scores segmented 1` after a direction is the plain segmented board',
              st['mode'] == 'Segmented' and st['style'] == 'segmented', '%s' % st)
    st = get('tas')
    if st:
        check('tas: TAS lit, the tas board, no ladder', st['mode'] == 'TAS' and st['style'] == 'tas'
              and st['tab'] == 'tas' and st['src'] is None, '%s' % st)
    st = get('sideways')
    if st:
        check('sideways: Sideways lit, laddered on KSF\'s 30', st['mode'] == 'Sideways' and st['style'] == 'sw'
              and st['src'] == 'KSF, 30 times', '%s' % st)
    st = get('bonus')
    if st:
        want = [group(ms, KSF_B1) for ms in sorted(KSF_B1 + [MINE_B1])[:24]]
        check('bonus: KSF\'s 40, each row in its group', st['src'] == 'KSF, 40 times' and st['rows'] == want,
              '%s rows %s (want %s)' % (st['src'], st['rows'], want))
    st = get('localtas')
    if st:
        check('local: TAS on Local is the TAS class filter', st['tab'] == 'local' and st['filter'] == 'tas'
              and st['mode'] == 'TAS', '%s' % st)
    st = get('back')
    if st:
        check('back: `scores tab online` is the plain Online board', st['tab'] == 'online'
              and st['mode'] == 'Normal', '%s' % st)
    if requests is not None:
        asked = [r for r in requests if 'groups' in r]
        styles = sorted(set(r.get('style') for r in asked))
        check('surfd: one groups request a mode, not one a frame', 0 < len(asked) <= 12
              and {'clean', 'segmented', 'tas', 'sw'} <= set(styles),
              '%d groups requests, styles %s, me %s' % (len(asked), styles, sorted(set(r.get('me', '') for r in asked))))
    failed = [r for r in results if r[1] is False]
    unknown = [r for r in results if r[1] is None]
    for name, ok, detail in results:
        print('%s  %s: %s' % ({True: 'PASS', False: 'FAIL', None: 'N/M '}[ok], name, detail))
    print('%d checks, %d failed, %d not measured' % (len(results), len(failed), len(unknown)))
    return 1 if failed else (2 if unknown else 0)


def FS(g):
    return 'T10' if g == 0 else ('G%d' % g if g <= 6 else 'No group')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--output-dir', type=pathlib.Path)
    ap.add_argument('--content', type=pathlib.Path, default=pathlib.Path('C:/FTESurf'))
    ap.add_argument('--csqc', type=pathlib.Path)
    ap.add_argument('--mqc', type=pathlib.Path)
    ap.add_argument('--ssqc', type=pathlib.Path)
    ap.add_argument('--timeout', type=int, default=240)
    ap.add_argument('--grade', type=pathlib.Path)
    a = ap.parse_args()
    if a.grade:
        return grade(a.grade.read_text(encoding='utf-8', errors='replace'), None)
    if not a.output_dir:
        ap.error('--output-dir or --grade')
    out = a.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(('127.0.0.1', PORT))
    except OSError as exc:
        print('P1590: not measured -- 127.0.0.1:%d is held (%s)' % (PORT, exc))
        return 2
    home = out / ('surfd-home-%d' % int(time.time()))
    server = start_surfd(home)
    before = set(out.glob('ftesurf-runlines-*'))
    cmd = [sys.executable, '-B', str(ROOT / 'tools/runlines_smoke.py'),
           str(ROOT / 'ftesurf/cfg/test/p1590groups.cfg'), '--mount', '--content', str(a.content),
           '--output-dir', str(out), '--timeout', str(a.timeout)]
    for flag, path in (('--csqc', a.csqc), ('--mqc', a.mqc), ('--ssqc', a.ssqc)):
        if path:
            cmd += [flag, str(path)]
    try:
        run = subprocess.run(cmd, capture_output=True, text=True)
    finally:
        server.shutdown()
    print(run.stdout.strip()[-1500:])
    rigs = sorted(set(out.glob('ftesurf-runlines-*')) - before)
    if run.returncode or len(rigs) != 1:
        print(run.stderr.strip()[-2000:])
        print('P1590: not measured -- the run did not complete (exit %d, %d new rigs)' % (run.returncode, len(rigs)))
        return 2
    log = rigs[0] / 'ftesurf/logs/runlines_smoke.log'
    print('rig %s' % rigs[0])
    return grade(log.read_text(encoding='utf-8', errors='replace'), list(REQUESTS))


if __name__ == '__main__':
    raise SystemExit(main())
