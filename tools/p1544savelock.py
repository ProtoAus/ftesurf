#!/usr/bin/env python3
"""P1544 arm: save-load lock at ping -- taps right after a save, back-to-back taps, holds (Mark, 14 Nov).

    python -B tools/p1544savelock.py --out <dir under an OWNER.md root> --progs <build.ps1 -NoDeploy dir>
        --src <that build's src> [--delays 0,250,500] [--gaps 2.0,0.15] [--holdfor 0.8] [--force-first]

Takes the rig lock and launches a dedicated server and a client: announce to peers first.

Reuses tools/p1384lead.py (fixture, probe csprogs, grade) from the worktree at --tools. Every tap is
made with +forward held, so the body moving again is the release the player feels: press_to_move is
the press to the first frame the predicted body leaves the loaded spot. SLX lines add the client's
load path (wop = rode a usercmd), its answer counter and whether the trail request FIFO was busy.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--progs', type=Path, required=True)
ap.add_argument('--src', type=Path, required=True)
ap.add_argument('--tools', type=Path, default=Path(__file__).resolve().parent)
ap.add_argument('--delays', default='0,250')
ap.add_argument('--gaps', default='2.0,0.15', help='seconds from the save to the first tap')
ap.add_argument('--loop', type=int, default=3, help='taps per round (each --every s after the last)')
ap.add_argument('--every', type=float, default=1.2, help='seconds between taps in a round')
ap.add_argument('--holdfor', type=float, default=0, help='hold the load key this long instead of a tap')
ap.add_argument('--force-first', action='store_true', help='ARM ONLY: tap 1 of each round takes the stringcmd path')
ap.add_argument('--port', type=int, default=27623)
a = ap.parse_args()
sys.path.insert(0, str(a.tools))
import p1384lead as L  # noqa: E402

L.PROBE += r'''
void() SLX_Probe =
{
	if (!rec_sl_holding && cltime - p1384_rel > 1.5) return;
	print(sprintf("SLX t %.4f ack %g slack %g busy %g pred %g sent %g up %g\n", cltime, rec_sl_holdack,
		getstatf(STAT_FS_SLACK), Trail_RequestBusy(), rec_sl_pred, rec_sl_sent, rec_sl_upwait));
	print(sprintf("SLT t %.4f ans %g done %g a %g b %g wop %g dt %.3f\n", cltime, SaveLoc_LoadAnswered(), SaveLoc_LeadDone(),
		rec_sl_holdack > 0, getstatf(STAT_FS_SLACK) >= rec_sl_holdack, rec_sl_wophold, cltime - rec_sl_holdt0));
};
'''
_orig_build = L.build_probe


def build_probe(src, out, split_stats=0):
    # Hook SLX_Probe beside P1384_Probe in the copied cl_main.qc before compiling.
    import subprocess
    real_run = subprocess.run

    def run(cmd, *k, **kw):
        if isinstance(cmd, list) and cmd and str(cmd[0]).endswith('fteqcc64.exe'):
            f = out / 'cstree/src/client/cl_main.qc'
            t = f.read_text()
            hook = '\tif (cvar("p1384_probe")) P1384_Probe();   // ARM ONLY\n'
            assert t.count(hook) == 1
            t = t.replace(hook, hook + '\tif (cvar("p1384_probe")) SLX_Probe();   // ARM ONLY\n')
            reg = '\tregistercvar("p1384_probe", "0", 0);\n'
            assert t.count(reg) == 1
            f.write_text(t.replace(reg, reg + '\tregistercvar("p1544_forcestr", "0", 0);\n'))
            # ARM ONLY: one load press refused before the warp-op gates takes the stringcmd path.
            w = out / 'cstree/src/client/cl_warpop.qc'
            t = w.read_text()
            mark = '\twop_loadpred = FALSE;\n\tif (!WarpOp_Able()'
            assert t.count(mark) == 1
            w.write_text(t.replace(mark, '\twop_loadpred = FALSE;\n\tif (cvar("p1544_forcestr")) { cvar_set("p1544_forcestr", "0"); '
                                         'print("P1544 forced stringcmd load\\n"); return FALSE; }\n\tif (!WarpOp_Able()'))
        return real_run(cmd, *k, **kw)
    L.subprocess.run = run
    try:
        return _orig_build(src, out, split_stats)
    finally:
        L.subprocess.run = real_run


ROW = L.ROW
SLX = re.compile(r'SLX t (\S+) ack (\S+) slack (\S+) busy (\S+) pred (\S+) sent (\S+) up (\S+)')


def grade(seg):
    g = L.grade(seg)
    rows = [(float(m.group(1)), float(m.group(2)), int(float(m.group(3))), int(float(m.group(4))),
             tuple(float(x) for x in m.groups()[12:15])) for m in ROW.finditer(seg)]
    held = [r for r in rows if r[2]]
    if held:
        t0 = held[0][1]
        tele = None
        for p, r in zip(rows, rows[1:]):
            if r[0] >= t0 and sum((x - y) ** 2 for x, y in zip(r[4], p[4])) ** 0.5 > 30:
                tele = r
                break
        move = None
        if tele:
            for r in rows:
                if r[0] > tele[0] and sum((x - y) ** 2 for x, y in zip(r[4], tele[4])) ** 0.5 > 2:
                    move = r
                    break
        g['press_to_teleport'] = None if tele is None else round(tele[0] - t0, 4)
        g['press_to_move'] = None if move is None else round(move[0] - t0, 4)
        g['wop'] = held[0][3]
    x = [m.groups() for m in SLX.finditer(seg)]
    if x:
        g['fifo_busy_frames'] = sum(1 for r in x if r[3] == '1')
        g['first_slx'] = x[0]
    g['forced'] = seg.count('P1544 forced stringcmd load')
    return g


def main():
    a.out = a.out.resolve()
    L.R.owned(a.out)
    a.out.mkdir(parents=True, exist_ok=False)
    phys, commit = L.R.free_mb()
    print('free physical %d MB, commit %d MB' % (phys, commit), flush=True)
    if phys < 1500 or commit < 2200:
        raise SystemExit('not enough free memory for a server and a client')
    cs = build_probe(a.src, a.out)
    report = {'qwprogs': L.sha(a.progs / 'qwprogs.dat'), 'csprogs_probe': L.sha(cs), 'src': str(a.src),
              'client': L.sha(L.CONTENT / 'ftesurf64.exe'), 'server': L.sha('C:/FTEQuake/fteqwsv64.exe'),
              'taps': {}}
    print('hashes', report, flush=True)
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs', 'log_name probe',
              'log_readable 1', 'developer 0', 'set cl_idlefps 0', 'set cl_maxfps 100', 'set run_resume 0',
              'set lobby_dir ""', 'set lobby_master ""', 'set cl_run_upload 0', 'set cl_board_url ""',
              'set sv_public 0', 'set milk_enable 0', 'set update_autocheck 0']
    L.R.take_lock('p1544savelock')
    sv = cl = None
    try:
        svb = L.prepare(a.out, 'server', a.progs, cs)
        (svb / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
            f'sv_port {a.port}', 'sv_playerslots 2', 'sv_maxclients 2', f'map {L.MAP}']) + '\n')
        sv = L.Peer(Path('C:/FTEQuake/fteqwsv64.exe'), svb, 'probe.cfg', True)
        sv.wait(r'Server spawned\.', timeout=120)
        sv.send('sv_cheats 1')
        clb = L.prepare(a.out, 'client', a.progs, cs)
        (clb / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
            'name "SaveLockArm"', f'connect 127.0.0.1:{a.port}']) + '\n')
        cl = L.Peer(L.CONTENT / 'ftesurf64.exe', clb, 'probe.cfg')
        cl.wait('FTESurf CSQC loaded', timeout=120)
        time.sleep(4)
        for line in ('menu_restart; ui_close', 'cl_prederror 4', 'cl_sl_leadin 1', 'cl_forwardspeed 200',
                     'rec_savelock 1', 'p1384_probe 0'):
            cl.send(line)
            time.sleep(0.3)
        time.sleep(1)
        O = L.O
        for d in [int(x) for x in a.delays.split(',')]:
            for gap in [float(x) for x in a.gaps.split(',')]:
                cl.send(f'cl_delay_packets {d}')
                cl.send(f'setpos {O[0]} {O[1]} {O[2]} 0 55 0')
                time.sleep(2.0)
                cl.send('+forward')                 # out of the box: the run starts; held to the end
                time.sleep(2.0)
                cl.send('sl_save')
                time.sleep(gap)
                for k in range(a.loop):
                    label = f'd{d}_gap{gap}_tap{k + 1}'
                    cl.send('p1384_probe 1')
                    off = len(cl.text())
                    cl.send(f'echo P1384 MARK {label}')
                    if a.force_first and k == 0:
                        cl.send('p1544_forcestr 1')
                    if a.holdfor:
                        cl.send('+sl_hold 50')
                        time.sleep(a.holdfor)
                        cl.send('-sl_hold 50')
                    else:
                        cl.send('+sl_hold 50;-sl_hold 50')
                    time.sleep(a.every if k + 1 < a.loop else 2.5)
                    seg = cl.text()[off:]
                    (a.out / f'{label}.log').write_text(seg, encoding='utf-8')
                    report['taps'][label] = grade(seg)
                    print(label, json.dumps(report['taps'][label]), flush=True)
                cl.send('p1384_probe 0')
                cl.send('-forward')
                time.sleep(1.0)
        cl.send('cl_delay_packets 0')
    finally:
        for p in (cl, sv):
            if p is not None:
                p.stop()
        L.R.drop_lock()
    (a.out / 'report.json').write_text(json.dumps(report, indent=1))
    print('report', a.out / 'report.json')


if __name__ == '__main__':
    main()
