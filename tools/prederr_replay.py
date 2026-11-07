#!/usr/bin/env python3
"""prederr_replay.py -- P1404: replay a prederror report on a rig and say whether the error comes back.

    python -I tools/prederr_replay.py REPORT --rigroot DIR --progs BUILD_DIR [--before N] [--after N]
                                      [--start SEQ] [--ping MS] [--clexe EXE] [--plan] [--keep]

REPORT is a lobby-stored report (data/prederr/<map>_<utc>_p<port>_s<slot>.txt). The replay starts at
report command START (default: the worst command minus --before), from the lobby's state after
START-1 as the report's ring recorded it, and feeds the recorded angles, moves and buttons of every
command after it (cl_prederr.qc pe_replay; the lobby side is sv_prederr.qc pe_state, sv_cheats only).
Warp ops (impulse 201 up) are not replayed; the tool says when the span has one.

Verdicts (three, because a replay that leaves the recorded path measures nothing):
  REPRODUCED      a prediction error of at least half the report's (and 8+ units) within 3 commands
                  of the worst command, the path having matched the report up to there
  NOT REPRODUCED  the path matched (server origin within PATH_TOL of the report's) and no such error
  CANNOT TELL     the replayed path left the report's before the worst command (or the state never
                  landed, or the rows were not all replayed)

The rig: fteqwsv64 + one windowed client from C:/FTEQuake (or --clexe), under C:/FTESurf-worktrees/rig.lock,
in RIGROOT/<report stem>/. Nothing is written outside RIGROOT.
"""
import argparse, datetime, os, pathlib, re, shutil, socket, subprocess, sys, time

LOCK = pathlib.Path(r'C:\FTESurf-worktrees\rig.lock')
PORT = 27931
PATH_TOL = 4.0          # units: the replayed server origin against the report's
SETTLE = 40             # commands after the state lands before an error counts


def parse(path):
    rep = {'srv': {}, 'ring': {}, 'map': None, 'ping': None, 'worst': None, 'worst_seq': None,
           'netfps': '66.6667', 'maxfps': '1000'}
    sect = None
    for ln in open(path, encoding='utf-8', errors='replace'):
        ln = ln.rstrip('\n')
        if ln.startswith('== '):
            sect = ln[3:].strip()
            continue
        if ln.startswith('map ') and rep['map'] is None:
            rep['map'] = ln.split()[1]
        m = re.match(r'client \S+ worst (\S+) seq (\d+)', ln)
        if m:
            rep['worst'], rep['worst_seq'] = float(m.group(1)), int(m.group(2))
        m = re.match(r'ping (\d+)', ln)
        if m and rep['ping'] is None:
            rep['ping'] = int(m.group(1))
        m = re.match(r'cvars cl_netfps (\S+) rate \S+ cl_maxfps (\S+)', ln)
        if m:
            rep['netfps'], rep['maxfps'] = m.group(1), m.group(2)
        if ln.startswith('#') or not ln or not (ln[0].isdigit() or ln[0] == '-'):
            continue
        f = ln.split()
        if sect == 'server' and len(f) >= 16:
            seq = int(f[3])
            rep['srv'][seq] = {'org': tuple(map(float, f[7:10])), 'vel': tuple(map(float, f[10:13])),
                               'impulse': int(float(f[15])), 'msec': float(f[4])}
        elif sect == 'ring' and len(f) >= 25:
            seq = int(f[1])
            rep['ring'][seq] = {'porg': tuple(map(float, f[2:5])), 'sorg': tuple(map(float, f[5:8])),
                                'svel': tuple(map(float, f[11:14])), 'msec': float(f[17]),
                                'ang': tuple(map(float, f[18:21])), 'mv': tuple(map(float, f[21:24])),
                                'btn': int(float(f[24])), 'cmdvalid': int(f[25]) if len(f) > 25 else 1}
    return rep


def dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def plan(rep, a):
    ring = rep['ring']
    if not ring or rep['worst_seq'] is None:
        raise SystemExit('report has no ring or no worst line')
    w = rep['worst_seq']
    lo = min(ring)
    start = a.start if a.start is not None else max(lo + 1, w - a.before)
    if start - 1 not in ring:
        raise SystemExit('no ring row for the state before command %d' % start)
    end = min(max(ring), w + a.after)
    good = sorted(s for s, r in ring.items() if r['cmdvalid'])
    rows, filled = [], 0
    for s in range(start, end + 1):
        r = ring.get(s)
        if r is None or not r['cmdvalid']:
            # a command the ring skipped: hold the moves and buttons, interpolate the view
            prv = max((g for g in good if g < s), default=None)
            nxt = min((g for g in good if g > s), default=None)
            if prv is None:
                raise SystemExit('no ring row at or before command %d' % s)
            p = ring[prv]
            ang = p['ang']
            if nxt is not None:
                q, t = ring[nxt], (s - prv) / float(nxt - prv)
                ang = tuple(x + ((y - x + 180) % 360 - 180) * t for x, y in zip(p['ang'], q['ang']))
            r = dict(p, ang=ang)
            filled += 1
        imp = rep['srv'].get(s, {}).get('impulse', 0)
        rows.append((s, r, imp))
    if filled:
        print('note: %d of %d commands were not in the ring; their inputs are held/interpolated' % (filled, len(rows)))
    return start, ring[start - 1]['sorg'], ring[start - 1]['svel'], rows


def write_replay(path, start, org, vel, rows):
    with open(path, 'w', newline='\n') as f:
        f.write('FTESURF-PEREPLAY 1\n')
        f.write('start %d %.3f %.3f %.3f %.3f %.3f %.3f\n' % ((start,) + tuple(org) + tuple(vel)))
        for s, r, imp in rows:
            f.write('%d %.2f %.3f %.3f %.3f %g %g %g %d %d\n' % ((s, r['msec']) + r['ang'] + r['mv'] + (r['btn'], imp)))


def take_lock(what):
    while True:
        if LOCK.exists():
            time.sleep(5)
            continue
        try:
            LOCK.mkdir()
        except FileExistsError:
            continue
        (LOCK / 'owner.txt').write_text('prederr_replay pid=%d since=%s for=%s\n' % (
            os.getpid(), datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'), what))
        return


def drop_lock():
    (LOCK / 'owner.txt').unlink()
    LOCK.rmdir()


def run(rep, a, rig, rows):
    secs_play = (len(rows) + 30) / float(rep['netfps']) + 4
    ping = a.ping if a.ping is not None else (rep['ping'] or 0)
    (rig / 'ftesurf' / 'cfg' / 'test').mkdir(parents=True)
    shutil.copyfile(r'C:\FTEQuake\fteqwsv64.exe', rig / 'fteqwsv64.exe')
    shutil.copyfile(r'C:\FTEQuake\fteplug_hl2_x64.dll', rig / 'fteplug_hl2_x64.dll')
    shutil.copyfile(r'C:\FTESurf\default.fmf', rig / 'default.fmf')
    shutil.copyfile(a.progs / 'qwprogs.dat', rig / 'ftesurf' / 'qwprogs.dat')
    shutil.copyfile(a.progs / 'csprogs.dat', rig / 'ftesurf' / 'csprogs.dat')
    shutil.copyfile(r'C:\FTESurf\ftesurf\fs_addons.default.txt', rig / 'ftesurf' / 'fs_addons.txt')
    shutil.copyfile(r'C:\FTESurf\ftesurf\cfg\default.cfg', rig / 'ftesurf' / 'cfg' / 'default.cfg')
    total = 22 + secs_play + 6
    (rig / 'ftesurf' / 'cfg' / 'test' / 'arm.cfg').write_text(
        'set plug_loaddefault 3\nplug_load hl2\nexec cfg/default.cfg\ncfg_save_auto 0\nsv_cheats 1\n'
        'sv_minping %d\nmap %s\nwaitms %d\nquit\n' % (ping, rep['map'], int((total + 20) * 1000)))
    ch = rig / 'clhome'
    (ch / 'ftesurf' / 'cfg' / 'test').mkdir(parents=True)
    (ch / 'ftesurf' / 'data' / 'prederr').mkdir(parents=True)
    shutil.copyfile(rig / 'replay.rpl', ch / 'ftesurf' / 'data' / 'prederr' / 'replay.rpl')
    shutil.copyfile(a.progs / 'csprogs.dat', ch / 'ftesurf' / 'csprogs.dat')
    shutil.copyfile(r'C:\FTESurf\ftesurf\fs_addons.default.txt', ch / 'ftesurf' / 'fs_addons.txt')
    (ch / 'ftesurf' / 'cfg' / 'test' / 'cl.cfg').write_text(
        'cfg_save_auto 0\ncl_idlefps 0\ncl_maxfps %s\ncl_netfps %s\nset cl_prederror 4\n'
        'set cl_prederr_report 0\nset cl_trigdebug 1\nconnect 127.0.0.1:%d\nwaitms 22000\n'
        'echo PEREPLAY BEGIN\npe_replay replay.rpl\nwaitms %d\nprederr_dump replay_ring.txt\nwaitms 800\n'
        'echo PEREPLAY END\nquit\n' % (rep['maxfps'], rep['netfps'], PORT, int(secs_play * 1000)))
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1', PORT))
    take_lock('prederr_replay ' + rig.name)
    p = c = None
    try:
        with open(rig / 'stdout.log', 'w') as out:
            p = subprocess.Popen([str(rig / 'fteqwsv64.exe'), '-basedir', str(rig), '-manifest',
                                  str(rig / 'default.fmf'), '-homedir', str(rig / 'home'), '-port', str(PORT),
                                  '+sv_public', '0', '+log_enable', '1', '+log_name', 'arm', '+cfg_save_auto', '0',
                                  '+exec', 'cfg/test/arm.cfg'], cwd=str(rig), stdout=out, stderr=subprocess.STDOUT)
            time.sleep(10)
            clexe = str(a.clexe)
            if a.clexe.name != 'ftesurf64.exe' or a.clexe.parent != pathlib.Path(r'C:\FTEQuake'):
                cd = rig / 'clbin'
                cd.mkdir()
                shutil.copyfile(a.clexe, cd / 'fteqw64.exe')
                for d in a.clexe.parent.glob('fteplug_*.dll'):
                    shutil.copyfile(d, cd / d.name)
                clexe = str(cd / 'fteqw64.exe')
            c = subprocess.Popen([clexe, '-basedir', r'C:\FTEQuake', '-homedir', str(ch), '-nosound', '-window',
                                  '-width', '960', '-height', '540', '+set', 'cfg_save_auto', '0',
                                  '+log_enable', '1', '+log_name', 'cl', '+exec', 'cfg/test/cl.cfg'],
                                 cwd=str(rig), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                c.wait(timeout=total + 30)
            except subprocess.TimeoutExpired:
                c.kill()
                c.wait()
            p.kill()
            p.wait()
    finally:
        for q in (c, p):
            if q is not None and q.poll() is None:
                q.kill()
                q.wait()
        drop_lock()
    for f in rig.rglob('identity.pfx'):
        f.unlink()


def grade(rep, rig, start, rows):
    cl = rig / 'clhome' / 'ftesurf' / 'logs' / 'cl.log'
    txt = cl.read_text(encoding='utf-8', errors='replace') if cl.exists() else ''
    out = []
    m = re.search(r'pe_replay: (\d+) rows, state on command (\d+)', txt)
    if not m:
        return 'CANNOT TELL', ['the replay did not start (no "pe_replay: N rows" line in cl.log)']
    s0 = int(m.group(2))
    landed = re.search(r'pe_state: on command (\d+) at', txt)
    if not landed:
        return 'CANNOT TELL', ['the lobby never applied the state (no "pe_state: on command" line)']
    off = int(landed.group(1)) - s0
    if off:
        out.append('state landed %d commands late; rows shift by that much' % off)
    done = re.search(r'pe_replay: done at command (\d+)', txt)
    if not done:
        out.append('the replay did not finish (no "pe_replay: done")')
    shift = start - s0                  # report seq = replay seq + shift (rows start at s0)
    errs = []
    for mm in re.finditer(r'prederr: seq (\d+) origin off by ([\d.]+) \(predicted (\S+) (\S+) (\S+), server (\S+) (\S+) (\S+)\)', txt):
        rs = int(mm.group(1))
        if rs < s0 + SETTLE:
            continue
        errs.append((rs + shift, float(mm.group(2))))
    ring = rig / 'clhome' / 'ftesurf' / 'data' / 'prederr' / 'replay_ring.txt'
    dev = {}
    if ring.exists():
        for ln in open(ring, encoding='utf-8', errors='replace'):
            f = ln.split()
            if len(f) < 25 or not f[1].isdigit():
                continue
            rseq = int(f[1]) + shift
            r = rep['ring'].get(rseq)
            if r:
                dev[rseq] = dist(tuple(map(float, f[5:8])), r['sorg'])
    w, worst = rep['worst_seq'], rep['worst']
    span = [s for s in sorted(dev) if s0 + SETTLE + shift <= s < w]
    if not span:
        return 'CANNOT TELL', out + ['no replayed server state to compare before the worst command']
    first_bad = next((s for s in span if dev[s] > PATH_TOL), None)
    out.append('path: %d commands compared before the worst, max deviation %.1f units%s' % (
        len(span), max(dev[s] for s in span), '' if first_bad is None else ', first over %.0f at report command %d' % (PATH_TOL, first_bad)))
    hits = [(s, e) for s, e in errs if abs(s - w) <= 3 and e >= max(8.0, 0.5 * worst)]
    out.append('errors after settling: ' + (', '.join('%d:%.1f' % (s, e) for s, e in errs[:12]) or 'none'))
    if hits:
        return 'REPRODUCED', out + ['%.1f units at report command %d (report: %.1f at %d)' % (hits[0][1], hits[0][0], worst, w)]
    if first_bad is not None:
        return 'CANNOT TELL', out + ['the replay left the recorded path before the error']
    return 'NOT REPRODUCED', out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('report', type=pathlib.Path)
    ap.add_argument('--rigroot', type=pathlib.Path)
    ap.add_argument('--progs', type=pathlib.Path, help='build dir with qwprogs.dat and csprogs.dat (P1404 or later)')
    ap.add_argument('--before', type=int, default=200)
    ap.add_argument('--after', type=int, default=60)
    ap.add_argument('--start', type=int)
    ap.add_argument('--ping', type=int)
    ap.add_argument('--clexe', type=pathlib.Path, default=pathlib.Path(r'C:\FTEQuake\ftesurf64.exe'))
    ap.add_argument('--plan', action='store_true', help='write the replay file and stop')
    a = ap.parse_args()
    rep = parse(a.report)
    start, org, vel, rows = plan(rep, a)
    warps = [(s, imp) for s, _, imp in rows if imp >= 201]
    print('report %s: map %s, worst %.1f at %d, ping %s; replay %d..%d (%d rows) from %s vel %s' % (
        a.report.name, rep['map'], rep['worst'], rep['worst_seq'], rep['ping'], start, rows[-1][0], len(rows),
        ' '.join('%.1f' % x for x in org), ' '.join('%.1f' % x for x in vel)))
    if warps:
        print('note: warp ops in the span are not replayed:', warps[:6])
    if not a.rigroot:
        raise SystemExit('--rigroot is required')
    rig = a.rigroot / a.report.stem
    if rig.exists():
        raise SystemExit('rig exists: %s' % rig)
    rig.mkdir(parents=True)
    write_replay(rig / 'replay.rpl', start, org, vel, rows)
    if a.plan:
        print('wrote', rig / 'replay.rpl')
        return
    if not a.progs:
        raise SystemExit('--progs is required to run')
    run(rep, a, rig, rows)
    verdict, notes = grade(rep, rig, start, rows)
    print('VERDICT', verdict)
    for n in notes:
        print('  ' + n)


if __name__ == '__main__':
    main()
