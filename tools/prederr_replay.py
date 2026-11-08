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
  REPRODUCED      a prediction error of 8+ units within 3 commands of the worst command ("(smaller)"
                  when under half the report's), the server path having matched the report up to
                  there and at the error. "(expected: ...)" when today's client files it under a
                  not-reported rule.
  NOT REPRODUCED  the server path matched (origin within PATH_TOL, velocity within VEL_TOL of the
                  report's) before and at the worst command, and no such error
  CANNOT TELL     the replayed path left the report's before the worst command (or the state never
                  landed, or the rows were not all replayed)

The rig: fteqwsv64 + one windowed client, C:/FTEQuake/fteqw64.exe (or --clexe), under C:/FTESurf-worktrees/rig.lock,
in RIGROOT/<report stem>/. Nothing is written outside RIGROOT.
"""
import argparse, datetime, hashlib, os, pathlib, re, shutil, socket, subprocess, sys, time

LOCK = pathlib.Path(r'C:\FTESurf-worktrees\rig.lock')
PORT = 27931
PATH_TOL = 32.0         # units: the replayed server origin against the report's (one hull width)
VEL_TOL = 10.0          # u/s: its velocity; a step or an edge offsets the origin, not the velocity
SETTLE = 12             # commands after the state lands before an error counts (ping + margin)


def parse(path):
    rep = {'srv': {}, 'ring': {}, 'acks': {}, 'name': None, 'names': {}, 'fs_tn': None, 'map': None, 'ping': None, 'worst': None, 'worst_seq': None,
           'netfps': '66.6667', 'maxfps': '1000'}
    sect = None
    acks = False
    for ln in open(path, encoding='utf-8', errors='replace'):
        ln = ln.rstrip('\n')
        if ln.startswith('== '):
            sect = ln[3:].strip()
            acks = False
            continue
        if ln.startswith('# acks:'):      # P1403: one row per acknowledged snapshot, full precision
            acks = True
            continue
        if ln.startswith('map ') and rep['map'] is None:
            rep['map'] = ln.split()[1]
        m = re.match(r'client \S+ worst (\S+) seq (\d+)', ln)
        if m:
            rep['worst'], rep['worst_seq'] = float(m.group(1)), int(m.group(2))
        m = re.match(r'activator name "(.*?)"(?: fs_tn "(.*?)")?$', ln)     # P1405 reports
        if m:
            rep['name'], rep['fs_tn'] = m.group(1), m.group(2)
        if ln.startswith('names '):
            rep['names'] = dict((int(g), n) for g, n in re.findall(r'(\d+) "([^"]*)"', ln))
        m = re.match(r'ping (\d+)', ln)
        if m and rep['ping'] is None:
            rep['ping'] = int(m.group(1))
        m = re.match(r'cvars cl_netfps (\S+) rate \S+ cl_maxfps (\S+)', ln)
        if m:
            try:      # numbers only: these go into the rig's cfg (review)
                rep['netfps'], rep['maxfps'] = '%g' % float(m.group(1)), '%g' % float(m.group(2))
            except ValueError:
                pass
        if ln.startswith('#') or not ln or not (ln[0].isdigit() or ln[0] == '-'):
            continue
        f = ln.split()
        if acks and len(f) >= 11:
            rep['acks'][int(f[2])] = {'org': tuple(map(float, f[4:7])), 'vel': tuple(map(float, f[7:10])),
                                      'gen': int(float(f[11])) if len(f) > 11 else None}
            continue
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


def settle(rep):
    # the restored state and name reach the client a round trip after the state lands (sv_minping = ping)
    return max(SETTLE, int(2 * (rep['ping'] or 0) / 15.0) + 6)


def plan(rep, a):
    ring = rep['ring']
    if not ring or rep['worst_seq'] is None:
        raise SystemExit('report has no ring or no worst line')
    w = rep['worst_seq']
    lo = min(ring)
    rep['settle'] = settle(rep)
    start = a.start if a.start is not None else max(lo + 1, w - max(a.before, rep['settle'] + 48))
    if start + rep['settle'] > w:
        raise SystemExit('CANNOT TELL: the error is at command %d, %d after the recording starts: no lead-in to replay'
                         % (w, w - lo))
    while start - 1 not in ring and start - 1 > lo:   # the ring skipped it: start a command earlier
        start -= 1
    if start - 1 not in ring:
        raise SystemExit('no ring row for the state before command %d' % start)
    end = min(max(ring), w + a.after)
    good = sorted(s for s, r in ring.items() if r['cmdvalid'])
    rows, filled, msfix = [], 0, 0
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
        sm = rep['srv'].get(s, {}).get('msec')
        if sm is not None and abs(sm - r['msec']) > 0.01:
            r = dict(r, msec=sm)            # the lobby ran this long (review 3: 200 ms filled as 15)
            msfix += 1
        rows.append((s, r, imp))
    if not rows:
        raise SystemExit('CANNOT TELL: no ring rows from command %d' % start)
    if msfix:
        print('note: %d command durations taken from the lobby\'s rows' % msfix)
    if filled:
        print('note: %d of %d commands were not in the ring; their inputs are held/interpolated' % (filled, len(rows)))
    rep['start_name'] = None
    if rep['fs_tn'] is not None and rep['fs_tn'] != '1':
        print('note: the lobby did not publish names (fs_tn "%s"): name filters were the server\'s' % rep['fs_tn'])
    if start - 1 in rep['acks']:     # P1403 rows carry the state to 0.001
        st = rep['acks'][start - 1]
        print('start state from the ack rows (full precision)')
        g = st.get('gen')
        if g is not None and g in rep['names']:
            rep['start_name'] = rep['names'][g]
        elif g is not None:
            rep['start_name_why'] = 'its generation (%d) is older than the report keeps' % g
        return start, st['org'], st['vel'], rows
    return start, ring[start - 1]['sorg'], ring[start - 1]['svel'], rows


def write_replay(path, start, org, vel, rows, name=None):
    with open(path, 'w', newline='\n', encoding='utf-8') as f:
        f.write('FTESURF-PEREPLAY 1\n')
        f.write('start %d %.3f %.3f %.3f %.3f %.3f %.3f%s\n' % ((start,) + tuple(org) + tuple(vel) +
                ((' "%s"' % name) if name is not None else '',)))
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
    total = 120 + secs_play       # map load (the client quits itself after the replay)
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
        'set cl_prederr_report 8\nset cl_prederr_ask 0\nset cl_trigdebug 1\n'
        'set pe_replay_auto replay.rpl\nconnect 127.0.0.1:%d\n' % (rep['maxfps'], rep['netfps'], PORT))
    take_lock('prederr_replay ' + rig.name)
    p = c = None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:   # after the lock: the last holder has quit
            s.bind(('127.0.0.1', PORT))
        with open(rig / 'stdout.log', 'w') as out:
            p = subprocess.Popen([str(rig / 'fteqwsv64.exe'), '-basedir', str(rig), '-manifest',
                                  str(rig / 'default.fmf'), '-homedir', str(rig / 'home'), '-port', str(PORT),
                                  '+sv_public', '0', '+log_enable', '1', '+log_name', 'arm', '+cfg_save_auto', '0',
                                  '+exec', 'cfg/test/arm.cfg'], cwd=str(rig), stdout=out, stderr=subprocess.STDOUT)
            time.sleep(10)
            clexe = str(a.clexe)
            if a.clexe.name != 'fteqw64.exe' or a.clexe.parent != pathlib.Path(r'C:\FTEQuake'):
                cd = rig / 'clbin'
                cd.mkdir()
                shutil.copyfile(a.clexe, cd / 'fteqw64.exe')
                for d in a.clexe.parent.glob('fteplug_*.dll'):
                    shutil.copyfile(d, cd / d.name)
                clexe = str(cd / 'fteqw64.exe')
            print('client %s sha256 %s' % (clexe, hashlib.sha256(open(clexe, 'rb').read()).hexdigest()[:8]))
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
    if int(m.group(1)) != len(rows):
        return 'CANNOT TELL', ['the client loaded %s of %d rows' % (m.group(1), len(rows))]
    landed = re.search(r'pe_state: on command (\d+) at', txt)
    if not landed:
        return 'CANNOT TELL', ['the lobby never applied the state (no "pe_state: on command" line)']
    land = int(landed.group(1))
    if land != s0:      # rows s0..land-1 ran from the idle spot: the path is not the report's
        return 'CANNOT TELL', ['the state landed on command %d, %d after the first row' % (land, land - s0)]
    done = re.search(r'pe_replay: done at command (\d+)', txt) is not None
    shift = start - s0                  # report seq = replay seq + shift (row r runs on command s0 + r)
    errs = []
    for mm in re.finditer(r'prederr: seq (\d+) origin off by ([\d.]+) \(predicted', txt):
        rs = int(mm.group(1))
        if rs >= land + rep['settle']:
            errs.append((rs + shift, float(mm.group(2))))
    ring = rig / 'clhome' / 'ftesurf' / 'data' / 'prederr' / 'replay_ring.txt'
    dev, vdev, have = {}, {}, set()
    if ring.exists():
        for ln in open(ring, encoding='utf-8', errors='replace'):
            f = ln.split()
            if len(f) < 25 or not f[1].isdigit():
                continue
            rseq = int(f[1]) + shift
            have.add(rseq)       # the replay measured this command
            r = rep['ring'].get(rseq)
            if r:
                dev[rseq] = dist(tuple(map(float, f[5:8])), r['sorg'])
                vdev[rseq] = dist(tuple(map(float, f[11:14])), r['svel'])
    w, worst = rep['worst_seq'], rep['worst']
    span = [x for x in sorted(dev) if land + rep['settle'] + shift <= x < w]
    if not span:
        return 'CANNOT TELL', out + ['no replayed server state to compare before the worst command']
    first_bad = next((x for x in span if dev[x] > PATH_TOL or vdev[x] > VEL_TOL), None)
    out.append('path: %d commands compared before the worst, max deviation %.1f units / %.1f u/s%s' % (
        len(span), max(dev[x] for x in span), max(vdev[x] for x in span),
        '' if first_bad is None else ', first over %.0f units or %.0f u/s at report command %d' % (PATH_TOL, VEL_TOL, first_bad)))
    out.append('errors after settling: ' + (', '.join('%d:%.1f' % (x, e) for x, e in errs[:12]) or 'none'))
    why = {}                          # report seq -> today's report decision for its error
    for mm in re.finditer(r'pe note \d+: prederr \d+ (\d+) [\d.]+[^\n]*\n[^\n]*pe note \d+: (not reported: [^\n]*)', txt):
        why[int(mm.group(1)) + shift] = mm.group(2)
    at = [x for x in range(w, w + 4) if x in dev]          # what the rig's server did at the error
    at_bad = [x for x in at if dev[x] > PATH_TOL or vdev[x] > VEL_TOL]
    at_why = None
    if len(at) < 2 or at_bad:
        at_why = 'the rig\'s server did not do what the report\'s did at the error (%s)' % (
            'compared %d of 4 commands' % len(at) if len(at) < 2 else
            'command %d off by %.1f units / %.1f u/s' % (at_bad[0], dev[at_bad[0]], vdev[at_bad[0]]))
    hits = sorted(((x, e) for x, e in errs if abs(x - w) <= 3 and e >= 8.0), key=lambda t: -t[1])
    if hits and (first_bad is None or first_bad >= hits[0][0] - 1):
        if at_why:
            return 'CANNOT TELL', out + [at_why]
        h, e = hits[0]
        v = 'REPRODUCED' + (' (smaller)' if e < 0.5 * worst else '') + \
            (' (expected: %s)' % why[h][len('not reported: '):] if h in why else '')
        return v, out + ['%.1f units at report command %d (report: %.1f at %d)' % (e, h, worst, w)]
    if first_bad is not None:
        warps = [x for x, _, imp in rows if imp >= 201 and x <= first_bad]
        return 'CANNOT TELL', out + ['the replay left the recorded path before the error' +
                                     (' (a warp op at report command %d is not replayed)' % warps[-1] if warps else '')]
    if at_why:
        return 'CANNOT TELL', out + [at_why]
    nf = re.findall(r'(\d+) name-filtered\)', txt)
    if rep.get('start_name') is None and nf and int(nf[-1]) > 0:
        return 'CANNOT TELL', out + ['the player\'s name at the start is unknown and the map has %s name-filtered '
                                     'triggers' % nf[-1]]
    near = [x for x in range(w - 3, w + 4) if x in have]   # the report's own ring may skip some
    if not done or len(near) < 5:
        return 'CANNOT TELL', out + ['nothing measured at the worst command (%d of 7 rows around it%s)' % (
            len(near), '' if done else ', replay unfinished')]
    return 'NOT REPRODUCED', out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('report', type=pathlib.Path)
    ap.add_argument('--rigroot', type=pathlib.Path)
    ap.add_argument('--progs', type=pathlib.Path, help='build dir with qwprogs.dat and csprogs.dat (P1404 or later)')
    ap.add_argument("--before", type=int, default=60)
    ap.add_argument('--after', type=int, default=60)
    ap.add_argument('--start', type=int)
    ap.add_argument('--ping', type=int)
    # P1411: fteqw64.exe is that install's live client; its ftesurf64.exe was a stale 5 Nov build.
    ap.add_argument('--clexe', type=pathlib.Path, default=pathlib.Path(r'C:\FTEQuake\fteqw64.exe'))
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
    write_replay(rig / 'replay.rpl', start, org, vel, rows, rep.get('start_name'))
    if rep.get('start_name') is None:
        print('note: the player\'s name at the start is not known (%s): not restored' % rep.get(
            'start_name_why', 'the report predates the name rows'))
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
