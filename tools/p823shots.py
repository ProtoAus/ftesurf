#!/usr/bin/env python3
"""Patch 823: the first-boot screens beside a Dusk panel, for looking at.

One client, no server, in its own basedir under --out (p744spec.py's fixture), online
consent (--tier) and no update permission on disk (`.ftesurf-updater/consent` absent,
so update_consent is -1). Screenshots, in order: the create panel (the reference look),
the terms summary and full details, the Steam offer, F2's panel, the title menu.

Graded on the menu's own lines:
  shots    six screenshots written
  f2       `ui_update_probe` after F2's command reports the journal screen (8); a
           pre-P823 build reports 7, the Updates screen (--control expects that)
  main     the title menu is SCREEN_MAIN (0) with no permission on disk; a pre-P823
           build is sent to the Updates screen (7) instead (--control)
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p744spec import prepare, sha  # noqa: E402

CFG = r'''cfg_save_auto 0
con_savehistory 0
cl_idlefps 0
cl_maxfps 100
vid_vsync 0
mastervolume 0
log_enable 1
log_dir logs
log_name probe
log_developer 1
developer 1
waitms 6000
menu_restart
waitms 20000
ui_strip_test screen create
waitms 2500
screenshot p823_1_create
waitms 2500
ui_strip_test screen terms
waitms 1500
ui_strip_test screen fit
screenshot p823_2_terms
waitms 2500
ui_strip_test screen termsfull
waitms 1500
ui_strip_test screen fit
screenshot p823_3_termsfull
waitms 2500
ui_strip_test screen steam
waitms 1500
screenshot p823_4_steam
waitms 2500
%(f2)s
waitms 1500
ui_update_probe
screenshot p823_5_f2
waitms 2500
ui_strip_test screen main
waitms 2500
ui_update_probe
screenshot p823_6_main
waitms 2500
echo P823 ARM COMPLETE
quit
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--tier', type=int, default=7)
    ap.add_argument('--control', action='store_true', help='a pre-P823 build: F2 and main reach the Updates screen')
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    ap.add_argument('--plugin', type=Path, default=Path('C:/FTESurf/fteplug_hl2_x64.dll'))
    a = ap.parse_args()
    a.out = a.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in a.out.parents):
        ap.error('--out must be beneath an owned task root')
    a.out.mkdir(parents=True, exist_ok=False)
    checks = []
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'control': a.control,
              'progs': {p: sha(a.progs / p)[:16] for p in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')},
              'client': sha(a.client)[:16], 'checks': checks}

    def check(ok, name):
        checks.append({'name': name, 'pass': bool(ok)})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)

    base = prepare(a, 'client')
    game = base / 'ftesurf'
    (game / 'data/consent.txt').write_text(f'FTESURF-CONSENT 1\nversion {a.tier}\naccepted 20261019-000000\n')
    # The real manifest: under p744's fixture one the updater is not FTESurf's and
    # update_consent reads 1 (qkupdate.c); this way it is -1, nothing decided.
    shutil.copy2(a.content / 'default.fmf', base / 'default.fmf')
    assert not (base / '.ftesurf-updater/consent').exists()
    (game / 'probe.cfg').write_text(CFG % {'f2': 'ui_updates' if a.control else 'ui_journal'})
    proc = subprocess.Popen(
        [str(a.client), '-nohome', '-noreset', '-nobrowse', '-basedir', str(base),
         '-manifest', str(base / 'default.fmf'), '-window', '-width', '1280', '-height', '800',
         '-nosound', '+set', 'cfg_save_auto', '0', '+exec', 'probe.cfg'],
        cwd='C:/FTESurf', stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        proc.wait(timeout=180)
    except subprocess.TimeoutExpired:
        proc.terminate()
        proc.wait(timeout=10)
        check(False, 'the client quit by itself')
    log = (game / 'logs/probe.log').read_text(encoding='utf-8', errors='replace') \
        if (game / 'logs/probe.log').exists() else ''
    (a.out / 'probe.log').write_text(log)
    shots = sorted((game / 'screenshots').glob('p823_*'))
    for s in shots:
        shutil.copy2(s, a.out / s.name)
    report['screenshots'] = [s.name for s in shots]
    report['fit'] = re.findall(r'ui_strip_test: terms panel ([^\n]*)', log)
    probes = re.findall(r'ui_update_probe: consent=(\S+) state=(\S+) screen=(\d+) client=(\d+)', log)
    report['probes'] = probes
    check(len(shots) == 6, 'six screenshots written')
    check(probes and all(p[0] == '-1' for p in probes), 'no update permission was decided in the rig')
    want = ('7', '7') if a.control else ('8', '0')
    check(len(probes) == 2 and (probes[0][2], probes[1][2]) == want,
          'F2 then the title menu report screens %s and %s' % want)
    check('P823 ARM COMPLETE' in log, 'the cfg ran to its end')
    check(not re.search(r'(?i)boundcheck|runaway|stack overflow|QC crash', log), 'no menu VM faults')
    report['failures'] = sum(1 for c in checks if not c['pass'])
    (a.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    shutil.rmtree(base)
    print('report', a.out / 'report.json', 'failures', report['failures'])
    sys.exit(1 if report['failures'] else 0)


if __name__ == '__main__':
    main()
