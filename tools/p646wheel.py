#!/usr/bin/env python3
"""Patch 646's arm: the mouse wheel scrolls the board's list, and so pages it.

python tools/p646wheel.py --output-dir <owned dir> [--content C:/FTESurf] [--timeout 300]
python tools/p646wheel.py --grade <rig>/ftesurf/logs/runlines_smoke.log

Runs cfg/test/p646wheel.cfg in a private overlay against THIS CHECKOUT'S surfd,
on p635board.py's fixture (surf_voyager bonus 2: 130 rows, one page of 100 and
a second).  Graded from the client's own prints: each wheel event's `took`
(`vote key`), the list's top row (`scores status`: scroll), the rows held
(`board_status`) and the row a click lands on.  Three verdicts: passed (0), failed (1), or a step the checks
need is not there (2).  The control is a csprogs without the patch: there the
wheel is never taken, the list does not move and the second page never comes.
"""
import argparse
import pathlib
import re
import socket
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import p635board as B   # noqa: E402  -- its surfd, its rows, its parsers

NOTCH_DOWN, NOTCH_UP = 516, 515


def sections(text):
    text = B.STAMP.sub('', text)
    out = {}
    parts = re.split(r'^==== P646 (\w+) ====\s*$', text, flags=re.M)
    for i in range(1, len(parts) - 1, 2):
        out[parts[i]] = parts[i + 1]
    return out


def scroll(body):
    m = re.findall(r'^\s+scroll (\S+)\s*$', body, re.M)
    return int(float(m[-1])) if m else None


def clicked(body):
    return [int(float(r)) for r in re.findall(r'scores: click row (\S+)', body)]


def hovered(body):
    return re.findall(r'sui_hover \[(\w+)\]', body)


def took(body, scan):
    """`took` of every key-DOWN of `scan` in the section."""
    return [int(float(t)) for t in re.findall(r'vote key: scan %d down 1 took (\S+)' % scan, body)]


def grade(text):
    sec = sections(text)
    bad, missing = [], []

    def check(label, ok, got):
        if ok is None:
            missing.append(label)
            print('n/a  %-58s %s' % (label, got))
        else:
            if not ok:
                bad.append(label)
            print('%-4s %-58s %s' % ('ok' if ok else 'FAIL', label, got))

    need = ('START', 'OFF', 'CLICK', 'DOWN', 'UP', 'PAGE', 'HELD', 'CLOSED', 'END')
    for n in need:
        if n not in sec:
            check('section %s' % n, None, 'not in the log: the run did not get that far')
    if missing:
        return 2
    st, bd = B.status(sec['START']), B.board(sec['START'])
    if not st or not bd or scroll(sec['START']) is None:
        check('start', None, 'no status, no board or no scroll line (a csprogs without the patch prints none)')
        return 2
    total = sum(B.BIG)
    check('start: pinned on bonus 2, one page held of %d, the list at its top' % total,
          st['mode'].startswith('pinned') and st['holds'] == total and len(bd['rows']) == 100
          and scroll(sec['START']) == 0,
          '%s, holds %d, rows %d, scroll %s' % (st['mode'], st['holds'], len(bd['rows']), scroll(sec['START'])))
    check('pinned, cursor off the lists: the wheel is not taken and nothing moves',
          hovered(sec['OFF']) == ['sb_flt'] and took(sec['OFF'], NOTCH_DOWN) == [0]
          and scroll(sec['OFF']) == 0,
          'on %s, took %s, scroll %s' % (hovered(sec['OFF']), took(sec['OFF'], NOTCH_DOWN), scroll(sec['OFF'])))
    check('over the list: five notches down are taken and move five rows',
          took(sec['DOWN'], NOTCH_DOWN) == [1] * 5 and scroll(sec['DOWN']) == 5,
          'took %s, scroll %s' % (took(sec['DOWN'], NOTCH_DOWN), scroll(sec['DOWN'])))
    first, then = clicked(sec['CLICK']), clicked(sec['DOWN'])
    check('...and a click there, the mouse not moved, lands five rows on from one before',
          len(first) == 1 and then == [first[0] + 5], 'row %s, then row %s' % (first, then))
    check('...and two up move two back',
          took(sec['UP'], NOTCH_UP) == [1] * 2 and scroll(sec['UP']) == 3,
          'took %s, scroll %s' % (took(sec['UP'], NOTCH_UP), scroll(sec['UP'])))
    bd = B.board(sec['PAGE'])
    ranks = [r[0] for r in bd['rows']] if bd else []
    check('seventy more: the list asks for the next page and holds all %d, in order' % total,
          len(took(sec['PAGE'], NOTCH_DOWN)) == 70 and all(took(sec['PAGE'], NOTCH_DOWN))
          and ranks == list(range(1, total + 1)) and (scroll(sec['PAGE']) or 0) >= 50,
          'notches %d, rows %d, scroll %s' % (len(took(sec['PAGE'], NOTCH_DOWN)), len(ranks), scroll(sec['PAGE'])))
    hs = B.status(sec['HELD'])
    check('held, not pinned: the wheel is the player\'s',
          bool(hs) and hs['mode'] == 'held' and took(sec['HELD'], NOTCH_DOWN) == [0],
          '%s, took %s' % (hs['mode'] if hs else None, took(sec['HELD'], NOTCH_DOWN)))
    check('closed: likewise', took(sec['CLOSED'], NOTCH_DOWN) == [0],
          'took %s' % took(sec['CLOSED'], NOTCH_DOWN))
    unknown = len(re.findall(r'Unknown command', text))
    check('no unknown command in the run', unknown == 0, '%d' % unknown)
    print('P646: %s' % ('FAILED: ' + '; '.join(bad) if bad else 'passed'))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--output-dir', type=pathlib.Path)
    ap.add_argument('--content', type=pathlib.Path, default=pathlib.Path('C:/FTESurf'))
    ap.add_argument('--timeout', type=int, default=300)
    ap.add_argument('--grade', type=pathlib.Path, help='grade this log; no run')
    a = ap.parse_args()
    if a.grade:
        return grade(a.grade.read_text(encoding='utf-8', errors='replace'))
    if not a.output_dir:
        ap.error('--output-dir or --grade')
    out = a.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(('127.0.0.1', B.PORT))
    except OSError as exc:
        print('P646: not measured -- 127.0.0.1:%d is held by something else (%s)' % (B.PORT, exc))
        return 2
    home = out / ('surfd-home-%d' % int(time.time()))
    server = B.start_surfd(home)
    print('surfd (this checkout) on 127.0.0.1:%d; its scratch home stays at %s' % (B.PORT, home))
    before = set(out.glob('ftesurf-runlines-*'))
    cmd = [sys.executable, '-B', str(ROOT / 'tools/runlines_smoke.py'),
           str(ROOT / 'ftesurf/cfg/test/p646wheel.cfg'), '--mount', '--content', str(a.content),
           '--output-dir', str(out), '--timeout', str(a.timeout)]
    try:
        run = subprocess.run(cmd, capture_output=True, text=True)
    finally:
        server.shutdown()
    print(run.stdout.strip())
    rigs = sorted(set(out.glob('ftesurf-runlines-*')) - before)
    if run.returncode or len(rigs) != 1:
        print(run.stderr.strip()[-2000:])
        print('P646: not measured -- the run did not complete (exit %d, %d new rigs)' % (run.returncode, len(rigs)))
        return 2
    print('rig %s' % rigs[0])
    return grade((rigs[0] / 'ftesurf/logs/runlines_smoke.log').read_text(encoding='utf-8', errors='replace'))


if __name__ == '__main__':
    raise SystemExit(main())
