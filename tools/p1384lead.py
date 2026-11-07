#!/usr/bin/env python3
"""P1384 arm: a tapped save load at a simulated ping (cl_delay_packets) against a dedicated server.

    python -B tools/p1384lead.py --out <dir under an OWNER.md root> --progs <build.ps1 -NoDeploy dir>
                                 --src <that build's src> [--delays 0,150,300] [--lead 1]

surf_dune's end room with the main start box moved into its corner (prepare). Each round: setpos into
the box, walk out (the run starts) for 2 s, save, walk 1 s, stop, then tap the load key
(`+sl_hold 50;-sl_hold 50`) or, with --hold, hold it 2.5 s in a second round.

The arm's csprogs is --src plus one TEST-ONLY probe (never shipped): with p1384_probe 1 it prints,
every rendered frame from the press until 1.5 s after the release, the client's own hold state, the
travel's state, the rendered eye (VF_ORIGIN after SaveLoc_Camera) and the predicted body. The engine's
cl_prederror 4 lines ("prederr: ...") are the misprediction witness. Graded per tap: the press frame
to the travel's first frame, the release frame, the largest eye jump between frames while held, and
prederr lines from the press to 3 s after it. Needs the rig lock and an announcement to peers.
"""
import argparse
import hashlib
import json
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p840clock as R  # noqa: E402  take_lock/drop_lock/free_mb/owned
from spec_chat_smoke import Peer  # noqa: E402

CONTENT = Path('C:/FTESurf')
MAP = 'surf_dune'
# The end room (x 11360..12032, y 10944..11904, floor 12912) with a start box in its corner and the
# end moved far away, so a walk out of the box is a run and a save in the room is a running save.
BOX = (11500, 11600, 11080, 11180)  # clear of the room's chamfered corners
O = (11550.0, 11130.0, 12914.0)     # in the box; yaw 55 walks ~800 u of floor toward the far corner

PROBE = r'''
// P1384 ARM ONLY -- never shipped.
float p1384_was, p1384_rel;
void() P1384_Probe =
{
	local vector cam;
	if (rec_sl_holding) p1384_was = TRUE;
	else if (p1384_was) { p1384_was = FALSE; p1384_rel = cltime; }
	if (!rec_sl_holding && cltime - p1384_rel > 1.5) return;
	cam = getproperty(VF_ORIGIN);
	print(sprintf("P1384 t %.4f t0 %.4f hold %g wop %g buf %g pend %g left %.3f ", cltime, rec_sl_holdt0,
		rec_sl_holding, rec_sl_wophold, sl_lead_buf >= 1, sl_lead_pending > 0, SaveLead_Remaining()),
		sprintf("shold %g up %g cam %.2f %.2f %.2f ", getstatf(STAT_FS_HOLD), rec_sl_upwait, cam_x, cam_y, cam_z),
		sprintf("body %.2f %.2f %.2f txt [%s]\n", pmove_org_x, pmove_org_y, pmove_org_z, SaveLoc_LeadText()));
};
'''


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def build_probe(src, out):
    tree = out / 'cstree'
    shutil.copytree(src, tree / 'src', ignore=shutil.ignore_patterns('*.dat', '*.lno', 'rig'))
    (tree / 'ftesurf').mkdir()
    f = tree / 'src/client/cl_savelead.qc'
    f.write_bytes(f.read_bytes() + PROBE.encode())
    f = tree / 'src/client/cl_main.qc'
    t = f.read_bytes().decode()
    hook = '\tSaveLoc_Camera();               // Patch 430: a load drawn before its reply\n'
    assert t.count(hook) == 1
    f.write_bytes(t.replace(hook, hook + '\tif (cvar("p1384_probe")) P1384_Probe();   // ARM ONLY\n').encode())
    r = subprocess.run([str(tree / 'src/fteqcc64.exe'), '-srcfile', 'cl_progs.src'], cwd=tree / 'src',
                       capture_output=True, text=True)
    (out / 'cs-build.log').write_text(r.stdout + r.stderr)
    warn = [l for l in (r.stdout + r.stderr).splitlines() if 'warning' in l.lower() and '0 warnings' not in l]
    assert r.returncode == 0 and not warn and (tree / 'ftesurf/csprogs.dat').is_file(), 'probe build failed'
    return tree / 'ftesurf/csprogs.dat'


def prepare(out, name, progs, csprogs):
    base = out / name
    game = base / 'ftesurf'
    for folder in ('glsl', 'scripts', 'models', 'particles'):
        if (CONTENT / 'ftesurf' / folder).is_dir():
            shutil.copytree(CONTENT / 'ftesurf' / folder, game / folder)
    for folder in ('fonts', 'ui'):
        if (CONTENT / 'ftesurf/gfx' / folder).is_dir():
            shutil.copytree(CONTENT / 'ftesurf/gfx' / folder, game / 'gfx' / folder)
    for folder in ('cfg', 'maps/zones/local', 'logs', 'data', 'downloads/csprogsvers'):
        (game / folder).mkdir(parents=True)
    (game / 'data/consent.txt').write_text('version 4\n')
    shutil.copy2(CONTENT / f'ftesurf/maps/{MAP}.bsp', game / f'maps/{MAP}.bsp')
    z = json.loads((CONTENT / f'ftesurf/maps/zones/local/{MAP}.json').read_text(encoding='utf-8'))
    main = z['tracks']['main']['zones']
    seg = main['segments'][0]
    seg['limitStartGroundSpeed'] = False
    reg = seg['checkpoints'][0]['regions'][0]
    end = main['end']['regions'][0]
    main['end']['regions'] = [dict(end, points=reg['points'], bottom=reg['bottom'], height=reg['height'])]
    reg['points'] = [[BOX[0], BOX[2]], [BOX[0], BOX[3]], [BOX[1], BOX[3]], [BOX[1], BOX[2]]]
    reg['bottom'], reg['height'] = 12912, 200
    reg.pop('teleDestTargetname', None)
    main['segments'] = [seg]
    z['tracks'] = {'main': z['tracks']['main']}
    (game / f'maps/zones/local/{MAP}.json').write_text(json.dumps(z), encoding='utf-8')
    shutil.copy2(progs / 'qwprogs.dat', game / 'qwprogs.dat')
    shutil.copy2(progs / 'menu.dat', game / 'menu.dat')
    shutil.copy2(csprogs, game / 'csprogs.dat')
    shutil.copy2(CONTENT / 'ftesurf/cfg/default.cfg', game / 'cfg/default.cfg')
    shutil.copy2(CONTENT / 'fteplug_hl2_x64.dll', base / 'fteplug_hl2_x64.dll')
    (base / 'default.fmf').write_text(
        'FTEMANIFEST 1\nGAME FTESurfP1384Fixture\nBASEGAME ftesurf\n'
        'DISABLEHOMEDIR 1\nMAINCONFIG p1384-unused\n'
        'set sv_mintic 0.015\nset sv_maxtic 0.015\nset cl_netfps 66.6667\n')
    subprocess.run([sys.executable, str(HERE / 'seed_csprogs.py'), str(game / 'csprogs.dat')],
                   check=True, capture_output=True)
    return base


ROW = re.compile(r'P1384 t (\S+) t0 (\S+) hold (\S+) wop (\S+) buf (\S+) pend (\S+) left (\S+) shold (\S+) '
                 r'up (\S+) cam (\S+) (\S+) (\S+) body (\S+) (\S+) (\S+) txt \[(.*?)\]')


def grade(seg):
    rows = []
    for m in ROW.finditer(seg):
        g = m.groups()
        rows.append(dict(t=float(g[0]), t0=float(g[1]), hold=int(float(g[2])), wop=int(float(g[3])),
                         buf=int(float(g[4])), pend=int(float(g[5])), left=float(g[6]), shold=int(float(g[7])),
                         cam=tuple(float(x) for x in g[9:12]), body=tuple(float(x) for x in g[12:15]), txt=g[15]))
    held = [r for r in rows if r['hold']]
    if not held:
        # Down and up inside one frame: no rendered frame was held (lead-in 0 on a predicted load).
        return {'frames_held': 0, 'press_to_travel': None, 'press_to_release': 0.0 if 'run resumed' in seg else None,
                'eye_jumps_held': [], 'texts': [], 'first_countdown': None,
                'prederr': len(re.findall(r'prederr: ', seg))}
    t0 = held[0]['t0']
    first = held[0]['t']
    travel = next((r for r in held if r['buf'] and not r['pend']), None)
    rel = next((r for r in rows if r['t'] > first and not r['hold']), None)
    jump, prev, jumps = 0.0, None, []
    for r in held:
        if prev is not None:
            d = sum((a - b) ** 2 for a, b in zip(r['cam'], prev)) ** 0.5
            jump = max(jump, d)
            if d > 30:                  # walking at 200 u/s moves the eye ~2 u a frame
                jumps.append((round(r['t'] - t0, 3), round(d)))
        prev = r['cam']
    gaps = [(round(b['t'] - t0, 3), round(b['t'] - a['t'], 3)) for a, b in zip(rows, rows[1:])
            if b['t'] - a['t'] > 0.03]
    texts = []
    for r in held:
        k = re.sub(r'\d+ ms', 'N ms', r['txt'])
        if not texts or texts[-1] != k:
            texts.append(k)
    return {'frames_held': len(held), 'press_to_first_frame': round(first - t0, 4),
            'press_to_travel': None if travel is None else round(travel['t'] - t0, 4),
            'press_to_release': None if rel is None else round(rel['t'] - t0, 4),
            'max_eye_jump_held': round(jump, 1), 'eye_jumps_held': jumps, 'first_countdown': next((r['txt'] for r in held if 'ms' in r['txt']), None),
            'texts': texts, 'frame_gaps': gaps, 'prederr': len(re.findall(r'prederr: ', seg))}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--src', type=Path, required=True)
    ap.add_argument('--delays', default='0,150,300')
    ap.add_argument('--lead', default='1')
    ap.add_argument('--hold', action='store_true')
    ap.add_argument('--port', type=int, default=27621)
    ap.add_argument('--bigpic', type=int, default=0,
                    help='prepend this many synthetic rows to the saved trail.txt (a long picture)')
    a = ap.parse_args()
    a.out = a.out.resolve()
    R.owned(a.out)
    a.out.mkdir(parents=True, exist_ok=False)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1', a.port))
    phys, commit = R.free_mb()
    print('free physical %d MB, commit %d MB' % (phys, commit), flush=True)
    if phys < 1500 or commit < 2200:
        raise SystemExit('not enough free memory for a server and a client')
    cs = build_probe(a.src, a.out)
    report = {'qwprogs': sha(a.progs / 'qwprogs.dat'), 'csprogs_probe': sha(cs), 'src': str(a.src),
              'client': sha(CONTENT / 'ftesurf64.exe'), 'server': sha('C:/FTEQuake/fteqwsv64.exe'),
              'lead': a.lead, 'taps': {}}
    print('hashes', report, flush=True)
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs', 'log_name probe',
              'log_readable 1', 'developer 0', 'set cl_idlefps 0', 'set cl_maxfps 100', 'set run_resume 0',
              'set lobby_dir ""', 'set lobby_master ""', 'set cl_run_upload 0', 'set cl_board_url ""',
              'set sv_public 0', 'set milk_enable 0', 'set update_autocheck 0']
    R.take_lock('p1384lead (ftesurf-3a)')
    sv = cl = None
    try:
        svb = prepare(a.out, 'server', a.progs, cs)
        (svb / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
            f'sv_port {a.port}', 'sv_playerslots 2', 'sv_maxclients 2', f'map {MAP}']) + '\n')
        sv = Peer(Path('C:/FTEQuake/fteqwsv64.exe'), svb, 'probe.cfg', True)
        sv.wait(r'Server spawned\.', timeout=120)
        sv.send('sv_cheats 1')
        clb = prepare(a.out, 'client', a.progs, cs)
        (clb / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
            'name "P1384Arm"', f'connect 127.0.0.1:{a.port}']) + '\n')
        cl = Peer(CONTENT / 'ftesurf64.exe', clb, 'probe.cfg')
        cl.wait('FTESurf CSQC loaded', timeout=120)
        time.sleep(4)
        for line in ('menu_restart; ui_close', 'cl_prederror 4', f'cl_sl_leadin {a.lead}', 'cl_forwardspeed 200',
                     'rec_savelock 1', 'p1384_probe 0'):
            cl.send(line)
            time.sleep(0.3)
        time.sleep(1)
        rounds = [(int(d), False) for d in a.delays.split(',')]
        if a.hold:
            rounds += [(int(d), True) for d in a.delays.split(',')]
        for d, hold in rounds:
            label = f'd{d}' + ('hold' if hold else 'tap')
            cl.send(f'cl_delay_packets {d}')
            cl.send(f'setpos {O[0]} {O[1]} {O[2]} 0 55 0')
            time.sleep(2.0)
            cl.send('+forward')                     # out of the box: the run starts
            time.sleep(2.0)
            before = {p: p.stat().st_mtime for p in clb.glob('ftesurf/data/saves/**/trail.txt')}
            cl.send('sl_save')                      # on the run, moving
            time.sleep(1.0)
            if a.bigpic:
                new = [p for p in clb.glob('ftesurf/data/saves/**/trail.txt') if before.get(p) != p.stat().st_mtime]
                assert len(new) == 1, new
                lines = new[0].read_text(encoding='utf-8').splitlines()
                tok = lines[1].split()
                t0, x0 = float(tok[0]), float(tok[1])
                pad = []
                for k in range(a.bigpic, 0, -1):
                    tok[0], tok[1] = '%.6f' % (t0 - k * 0.015), '%.6f' % (x0 - k * 0.5)
                    pad.append(' '.join(tok))
                new[0].write_text('\n'.join(lines[:1] + pad + lines[1:]) + '\n', encoding='utf-8')
                report.setdefault('bigpic', []).append(len(pad) + len(lines) - 1)
            cl.send('-forward')
            time.sleep(2.0)
            cl.send('p1384_probe 1')
            off = len(cl.text())
            cl.send(f'echo P1384 MARK {label}')
            if hold:
                cl.send('+sl_hold 50')
                time.sleep(2.5)
                cl.send('-sl_hold 50')
            else:
                cl.send('+sl_hold 50;-sl_hold 50')
            time.sleep(4.0)
            cl.send('p1384_probe 0')
            time.sleep(0.5)
            seg = cl.text()[off:]
            (a.out / f'{label}.log').write_text(seg, encoding='utf-8')
            report['taps'][label] = grade(seg)
            print(label, json.dumps(report['taps'][label]), flush=True)
        cl.send('cl_delay_packets 0')
    finally:
        for p in (cl, sv):
            if p is not None:
                p.stop()
        R.drop_lock()
    (a.out / 'report.json').write_text(json.dumps(report, indent=1))
    print('report', a.out / 'report.json')


if __name__ == '__main__':
    main()
