#!/usr/bin/env python3
"""Patch 1081 falsifier: `zone_edit publish` on a server this client does not host.

A private dedicated server holds surf_dune's published zones (p815zones' B); the client
holds its own saved edit (C), so its table is its own file, clean.

  control  installed progs: `zone_edit upload` is refused ("a command cannot start a publish").
  subject  `zone_edit sel 0` taints the table (a command, off-host): publish refuses; the
           panel's Reload clears it; `zone_edit publish` then opens the dialog (a challenge to
           the live zone service: no upload), and a command pressing Publish is refused.

Graded on the client's own lines. The subject sends one challenge to play.proto.bar (it
expires in 3 minutes, nothing is signed or uploaded); the control sends nothing.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p815zones as P


def step(cl, line, pattern, timeout=30):
    mark = len(cl.text())
    cl.send(line)
    return cl.wait(pattern, mark, timeout).group(0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--arm', choices=('control', 'subject'), required=True)
    ap.add_argument('--port', type=int, default=27593)
    ap.add_argument('--client', type=Path, default=P.FTESURF / 'ftesurf64.exe')
    ap.add_argument('--server', type=Path, default=Path('C:/FTEQuake/fteqwsv64.exe'))
    ap.add_argument('--plugin', type=Path, default=P.FTESURF / 'fteplug_hl2_x64.dll')
    a = ap.parse_args()
    a.cplugin = None
    a.out = a.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in a.out.parents):
        ap.error('--out must be beneath an owned task root')
    a.out.mkdir(parents=True, exist_ok=False)
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'arm': a.arm,
              'progs': {p: P.sha(a.progs / p)[:12] for p in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')},
              'client': P.sha(a.client)[:8], 'server': P.sha(a.server)[:8], 'steps': []}
    peers = []
    try:
        sbase = P.prepare(a, 'server', shipped=P.ZB)
        (sbase / 'ftesurf/probe.cfg').write_text('\n'.join(P.COMMON + [
            f'sv_port {a.port}', 'sv_playerslots 4', 'sv_maxclients 4', 'set sv_guidkey p1081-fixture',
            f'map {P.MAP}']) + '\n')
        sv = P.Peer(a.server, sbase, 'probe.cfg', True); peers.append(sv)
        sv.wait(r'Server spawned\.', timeout=120)
        cbase = P.prepare(a, 'client', shipped=P.ZA, own=P.ZC, online=P.ZB)
        # menu.dat sets rec_terms from this record after the cfg: uploads need FS_TERMS_ONLINE (8).
        (cbase / 'ftesurf/data/consent.txt').write_text('FTESURF-CONSENT 1\nversion 8\naccepted 20261028-000000\n')
        (cbase / 'ftesurf/probe.cfg').write_text('\n'.join(P.COMMON + [
            'set cl_download_zonesrc ""', 'set update_enabled 0', 'set update_autocheck 0',
            'name "P1081"', f'connect 127.0.0.1:{a.port}']) + '\n')
        cl = P.Peer(a.client, cbase, 'probe.cfg'); peers.append(cl)
        cl.wait('FTESurf CSQC loaded', timeout=180)
        report['table'] = cl.wait(r'zones: \d+ on surf_dune[^\n]*', timeout=60).group(0)
        time.sleep(3)
        say = lambda *s: report['steps'].append(step(cl, *s))
        say('zone_edit', r'zone_edit[^\n]*')
        time.sleep(1)
        if a.arm == 'control':
            say('zone_edit upload', r'zone_edit[^\n]*: [^\n]*publish[^\n]*')
        else:
            cl.send('zone_edit sel 0')               # a selection only: no visible change, but a command
            say('zone_edit status', r'zone_edit: track \d+ sel 0[^\n]*')
            say('zone_edit publish', r'zone_edit[^\n]*console command changed these zones[^\n]*')
            say('zone_edit press ze_rl', r'zone_edit[^\n]*reloaded: [^\n]*')
            time.sleep(1)
            say('zone_edit publish', r'zone_edit: publish dialog open for surf_dune[^\n]*')
            report['steps'].append(cl.wait(r'zone_edit: (publish dialog waiting|upload answered)[^\n]*',
                                           0, 30).group(0))
            time.sleep(1.5)                          # past the page's 0.6 s arming
            say('zone_edit press zp_go', r'zone_edit[^\n]*a command cannot start a publish[^\n]*')
            say('zone_edit press zp_no', r'zone_edit[^\n]*(cancelled|closed)[^\n]*')
            report['signed'] = 'signed under a real press' in cl.text()
        (a.out / 'client.txt').write_text(cl.text())
        print(json.dumps(report, indent=1), flush=True)
    finally:
        for p in peers:
            p.stop()
        (a.out / 'report.json').write_text(json.dumps(report, indent=1))
        for d in a.out.iterdir():
            if d.is_dir():
                log = d / 'ftesurf/logs/probe.log'
                if log.exists():
                    shutil.copy2(log, a.out / f'{d.name}-probe.log')
                shutil.rmtree(d)
        print('report', a.out / 'report.json', flush=True)


if __name__ == '__main__':
    main()
