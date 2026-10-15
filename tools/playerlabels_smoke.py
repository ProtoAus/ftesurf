#!/usr/bin/env python3
"""Two real lobby clients, actual body stream and zone warps; owned overlay only.
Use --fixture only with the separately instrumented fixture CSQC build.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--progs-dir', type=Path, required=True)
    ap.add_argument('--fixture', action='store_true')
    a = ap.parse_args()
    out = a.output_dir.resolve(); out.mkdir(parents=True, exist_ok=True)
    if not any((p / 'OWNER.md').exists() for p in (out, *out.parents)):
        raise SystemExit('Owned root required')
    if os.name == 'nt':
        busy = subprocess.run(['pwsh', '-NoProfile', '-Command',
            'if (Get-Process ftesurf64,fteqw64,fteqwsv64 -ErrorAction SilentlyContinue) { exit 2 }'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if busy.returncode:
            print('Desktop rig busy; no owner/peer process stopped'); return 2
    head = '''cfg_save_auto 0
developer 1
log_developer 1
log_enable 1
log_dir logs
log_name runlines_smoke
con_notifytime 0
con_notifylines 0
cl_idlefps 0
cl_maxfps 100
vid_fullscreen 0
vid_winmaximize 0
vid_width 1280
vid_height 720
vid_conautoscale 1
sv_public 0
volume 0
waitms 2000
%s
waitmap 60
waitms 8000
menu_restart
ui_close
set hud_scale 2
cmd zone_goto 0 0 0
waitms 1000
'''
    primary = head % 'map surf_dune' + '''+back
waitms 800
-back
waitms 1500
cmd viewpos
body_stats
playerlabels_status detail
waitms 2000
playerlabels_status detail
screenshot labels_near.png
set cl_yawspeed 45
'''
    if a.fixture:
        primary += '''set label_fixture 1
waitms 1000
playerlabels_status detail
screenshot labels_fixture_near.png
set label_fixture 2
waitms 1000
playerlabels_status detail
screenshot labels_fixture_far.png
set label_fixture 3
waitms 1000
playerlabels_status detail
screenshot labels_fixture_wall.png
set label_fixture 4
waitms 1000
playerlabels_status detail
screenshot labels_fixture_off.png
set label_fixture 0
'''
    primary += '+left\n' + '\n'.join('waitms 500\nplayerlabels_status detail' for _ in range(16)) + '''
-left
waitms 30000
echo RUNLINES COMPLETE
quit
'''
    secondary = head % 'connect 127.0.0.1:27619' + 'waitms 18000\necho RUNLINES COMPLETE\nquit\n'
    procs = []; handles = []
    try:
        for i, cfg in enumerate((primary, secondary)):
            folder = out / ('client%d' % i); folder.mkdir()
            path = folder / 'control.cfg'; path.write_text(cfg)
            log = (folder / 'harness.log').open('w'); handles.append(log)
            cmd = [sys.executable, '-B', str(ROOT / 'tools/runlines_smoke.py'), str(path), '--mount',
                   '--output-dir', str(folder), '--timeout', '130', '--ssqc', str(a.progs_dir / 'qwprogs.dat'),
                   '--csqc', str(a.progs_dir / 'csprogs.dat'), '--mqc', str(a.progs_dir / 'menu.dat')]
            if not i: cmd += ['--dedicated', '--port', '27619', '--server-arg',
                '+set maxclients 8 +set sv_playerslots 8 +set lobby_enable 1 +set lobby_nocollide 1']
            procs.append(subprocess.Popen(cmd, stdout=log, stderr=log))
            if not i: time.sleep(6)
        for p in procs:
            if p.wait(timeout=150): raise RuntimeError('Native harness error')
        path, = (out / 'client0').glob('ftesurf-runlines-*/ftesurf/logs/runlines_smoke.log')
        text = path.read_text(errors='replace')
        print('\n'.join(l for l in text.splitlines() if 'label ' in l or 'playerlabels:' in l or 'body: cltime' in l))
        acted = any(int(n) for n in re.findall(r'playerlabels: drawn (\d+)', text))
        checks = {'Real body label actually drawn': acted}
        if a.fixture:
            chunks = {int(m.group(1)): text[m.end():] for m in re.finditer(r'label fixture mode (\d+)', text)}
            for mode in list(chunks):
                chunks[mode] = chunks[mode].split('label fixture mode', 1)[0]
            near = chunks.get(1, ''); far = chunks.get(2, ''); wall = chunks.get(3, ''); off = chunks.get(4, '')
            checks['Near name/picture actually draw'] = 'playerlabels: drawn 1' in near and 'name alpha 0.999' in near
            match = re.search(r'name alpha 0.000 picture offset ([-.0-9]+) width ([.0-9]+)', far)
            checks['Far name fades to zero and picture centers'] = bool(match and 'drawn 1' in far and abs(float(match[1]) + float(match[2]) / 2) < .02)
            checks['Actual world wall control acted'] = bool(re.search(r'label fixture wall acted: fraction 0\.', text))
            checks['Wall blocks despite in-view real PVS body'] = 'drawn 0' in wall and 'inview 1 blocked 1 pvs 1' in wall
            checks['Behind camera does not draw'] = 'drawn 0' in off and 'fresh 1 inview 0' in off
        for label, ok in checks.items(): print(('ok   ' if ok else 'FAIL ') + label)
        return 0 if all(checks.values()) else 1
    finally:
        for p in procs:
            if p.poll() is None: p.wait(timeout=150)
        for log in handles: log.close()

if __name__ == '__main__':
    raise SystemExit(main())
