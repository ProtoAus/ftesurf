#!/usr/bin/env python3
"""Patch 902: the title screen's version lines, against the real update feed.

One client per case, each in its own basedir under --out (p744spec.py's fixture, the real
default.fmf as in p876notes.py). A loopback feed cannot stand in: the manifest is signed
(qkupdate.c "signature is invalid"). So the real one is asked and the fixture's
.ftesurf-updater/state.json decides the verdict; nothing downloads, and update_stage_only 1
would stop an install if anything did:
  newer  installed one patch behind the feed: Latest is lit
  same   installed at the feed's version: Latest is not lit
         Both end "launcher" (the delta includes the engine binaries): the fixture's
         one-entry state is not a launcher's, and the installed exe takes no version fast
         path from it. So both pictures carry the "restart through the launcher" line.
  off    no .ftesurf-updater/consent: nothing asked, Latest unknown
each at 1280x720 and 1920x1080 menu units. Graded on the cvars the menu reads (printed by the cfg);
the pictures (title, F2's Updates page) are kept for looking at.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p744spec import prepare  # noqa: E402

FEED_URL = 'https://proto.bar/ftesurf/update.json'
CFG = r'''cfg_save_auto 0
con_savehistory 0
cl_idlefps 0
cl_maxfps 100
mastervolume 0
log_enable 1
log_dir logs
log_name probe
log_developer 1
developer 1
waitms 6000
menu_restart
waitms 16000
echo P902 STATE
update_state
update_version
ui_release_version
screenshot p902_title
waitms 1500
ui_journal updates
waitms 1500
screenshot p902_f2
waitms 1500
echo P902 ARM COMPLETE
quit
'''


def feed_version():
    with urllib.request.urlopen(FEED_URL, timeout=20) as r:
        payload = json.load(r)['payload']
    return json.loads(payload)['version']        # the signed text itself, a JSON string


def run(a, name, installed, size, permit):
    base = prepare(a, name)
    game = base / 'ftesurf'
    (game / 'data/consent.txt').write_text('FTESURF-CONSENT 1\nversion 7\naccepted 20261020-000000\n')
    shutil.copy2(a.content / 'default.fmf', base / 'default.fmf')
    if permit:
        (base / '.ftesurf-updater').mkdir()
        (base / '.ftesurf-updater/consent').write_text('1\n')
        (base / '.ftesurf-updater/state.json').write_text(json.dumps({'version': installed, 'files': {'p902.txt': '0' * 64}}))
    w, h = size
    # The window here can come up at the desktop's size whatever -width says, so the case's
    # size is the menu's virtual screen: what the menu lays out against.
    (game / 'probe.cfg').write_text('vid_conautoscale 0\nvid_conwidth %d\nvid_conheight %d\n' % (w, h) + CFG)
    proc = subprocess.Popen(
        [str(a.client), '-nohome', '-noreset', '-nobrowse', '-basedir', str(base),
         '-manifest', str(base / 'default.fmf'), '-window', '-width', str(w), '-height', str(h),
         '-nosound', '+set', 'cfg_save_auto', '0',
         '+set', 'update_manifest_url', FEED_URL, '+set', 'update_stage_only', '1', '+set', 'ui_release_version', installed,
         '+exec', 'probe.cfg'],
        cwd='C:/FTESurf', stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    quit_ok = True
    try:
        proc.wait(timeout=180)
    except subprocess.TimeoutExpired:
        proc.terminate()
        proc.wait(timeout=10)
        quit_ok = False
    logf = game / 'logs/probe.log'
    log = logf.read_text(encoding='utf-8', errors='replace') if logf.exists() else ''
    (a.out / f'{name}.log').write_text(log)
    for s in sorted((game / 'screenshots').glob('p902_*')):
        shutil.copy2(s, a.out / f'{name}-{s.name}')
    shutil.rmtree(base)
    return log, quit_ok


def cvar(log, name):
    m = re.search(r'"%s" is "([^"]*)"' % name, log[log.find('P902 STATE'):])
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--only', default='', help='comma-separated cases: newer,same,off')
    ap.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    ap.add_argument('--plugin', type=Path, default=Path('C:/FTESurf/fteplug_hl2_x64.dll'))
    a = ap.parse_args()
    a.out = a.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in a.out.parents):
        ap.error('--out must be beneath an owned task root')
    a.out.mkdir(parents=True, exist_ok=False)
    feed = feed_version()
    v = [int(x) for x in feed.split('.')]
    older = '%d.%d.%d' % (v[0], v[1], v[2] - 1) if v[2] else '0.0.1'
    print('feed', feed, 'older', older, flush=True)
    fails = 0
    for kind, installed, permit, want in (('newer', older, True, 'launcher'), ('same', feed, True, 'launcher'),
                                          ('off', older, False, 'idle')):
        if a.only and kind not in a.only.split(','):
            continue
        for size in ((1280, 720), (1920, 1080)):
            name = f'{kind}{size[0]}'
            log, ok = run(a, name, installed, size, permit)
            ver, st = cvar(log, 'update_version'), cvar(log, 'update_state')
            good = ok and 'P902 ARM COMPLETE' in log and ver == (feed if permit else '') and st == want and \
                not re.search(r'(?i)runaway|QC crash|boundcheck', log)
            fails += not good
            print('%s %s: update_version %r state %r' % ('PASS' if good else 'FAIL', name, ver, st), flush=True)
    print('pictures in', a.out, 'failures', fails)
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
