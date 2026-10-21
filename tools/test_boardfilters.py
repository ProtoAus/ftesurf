#!/usr/bin/env python3
"""Native board filter smoke using p635's real-surfd isolated fixture."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time

from p635board import start_surfd

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    a = ap.parse_args()
    a.out = a.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in a.out.parents):
        ap.error('--out must be under an owned task root')
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / 'client').mkdir(exist_ok=True)
    server = start_surfd(a.out / ('surfd-home-%d' % time.time_ns()))
    import surfd
    from flask import request
    asks = []
    real = surfd.app.view_functions['board']

    def counted():
        asks.append(dict(request.args))
        return real()
    surfd.app.view_functions['board'] = counted
    terms = re.search(r'^#define FS_TERMS_ONLINE\s+(\d+)',
                      (ROOT / 'src/shared/sh_defs.qc').read_text(), re.M).group(1)
    cfg = f'''cfg_save_auto 0
cl_idlefps 0
cl_maxfps 100
vid_fullscreen 0
vid_winmaximize 0
vid_width 1280
vid_height 800
vid_conautoscale 1
log_enable 1
log_dir logs
log_name runlines_smoke
con_notifytime 0
sv_public 0
waitms 1500
map surf_voyager
waitmap 60
waitms 3500
set lobby_dir_gen 1
menu_restart
waitms 500
ui_close
set rec_terms {terms}
set lobby_dir "http://127.0.0.1:27634"
set hud_scale 2
scores open
waitms 1500
echo FILTER DEFAULT
scores status
hud_edit ui
screenshot filters_default.png
'''
    for style in ('sw', 'hsw', 'bw', 'clean'):
        cfg += f'''scores style {style}
waitms 700
scores segmented 1
waitms 700
scores status
screenshot filters_{style}_seg.png
scores segmented 0
waitms 500
'''
    cfg += f'''scores source ksf
waitms 700
scores status
map surf_voyager
waitmap 60
waitms 2500
ui_close
scores open
waitms 1000
echo FILTER NEWMAP
scores status
scores close
disconnect
waitms 500
menu_restart
waitms 500
togglemenu
set rec_terms {terms}
set lobby_dir "http://127.0.0.1:27634"
ui_board_test surf_voyager
waitms 1200
ui_board_test
ui_board_test style hsw
waitms 700
ui_board_test segmented 1
waitms 700
ui_board_test
screenshot filters_menu.png
vid_conautoscale 0
vid_conwidth 640
vid_conheight 480
waitms 500
ui_cursor
ui_click 62 169
waitms 700
echo FILTER MENU KNOB
ui_board_test
ui_click 150 169
waitms 700
echo FILTER MENU LABEL
ui_board_test
screenshot filters_menu_narrow.png
ui_board_test close
echo FILTER DONE
echo RUNLINES COMPLETE
quit
'''
    path = a.out / 'filters.cfg'
    path.write_text(cfg)
    consent = a.out / 'consent.txt'
    consent.write_text('FTESURF-CONSENT 1\nversion ' + terms + '\n')
    try:
        proc = subprocess.run([sys.executable, str(ROOT / 'tools/runlines_smoke.py'), str(path),
                               '--mount', '--content', 'C:/FTESurf',
                               '--output-dir', str(a.out / 'client'), '--csqc', str(a.progs / 'csprogs.dat'),
                               '--mqc', str(a.progs / 'menu.dat'),
                               '--put', 'data/consent.txt=' + str(consent), '--timeout', '100'],
                              cwd='C:/FTESurf', capture_output=True, text=True)
        (a.out / 'harness.log').write_text(proc.stdout + proc.stderr)
    finally:
        server.shutdown()
    logs = sorted((a.out / 'client').rglob('runlines_smoke.log'), key=lambda p: p.stat().st_mtime)
    text = logs[-1].read_text(errors='replace') if logs else ''
    checks = []

    def check(name, ok):
        checks.append({'name': name, 'pass': bool(ok)})
        print(('PASS ' if ok else 'FAIL ') + name)

    check('native client completed', proc.returncode == 0 and 'FILTER DONE' in text)
    check('first board is WOS only', bool(asks) and asks[0].get('tier') == 'ranked')
    for style in ('clean', 'sw', 'hsw', 'bw', 'segmented', 'segmented_sw', 'segmented_hsw', 'segmented_bw'):
        check('independent style filter ' + style, any(q.get('style') == style and q.get('tier') == 'ranked' for q in asks))
    tiers = [q['tier'] for q in asks if 'tier' in q]
    check('KSF remains an explicit choice', 'ksf' in tiers)
    check('new map returns to WOS', bool(re.search(r'FILTER NEWMAP.*?list 0\s+tier ranked', text, re.S)))
    check('manual KSF top-up button absent', 'sui_element [sb_ksmore]' not in text)
    check('menu opens on WOS', 'board: opened surf_voyager on ranked;' in text)
    check('menu remains open on segmented Half-Sideways',
          bool(re.search(r'board: open: surf_voyager tab ranked style segmented_hsw, ok', text)))
    check('narrow menu knob changes segmentation off',
          bool(re.search(r'FILTER MENU KNOB.*?board: open: surf_voyager tab ranked style hsw, ok', text, re.S)))
    check('narrow menu label changes segmentation on',
          bool(re.search(r'FILTER MENU LABEL.*?board: open: surf_voyager tab ranked style segmented_hsw, ok', text, re.S)))
    (a.out / 'report.json').write_text(json.dumps({'checks': checks, 'requests': asks}, indent=2))
    return int(any(not c['pass'] for c in checks))


if __name__ == '__main__':
    sys.exit(main())
