#!/usr/bin/env python3
"""Patch 876: the title menu's patch notes, read from a local patchnotes.json.

Two clients, one after the other, each in its own basedir under --out (p744spec.py's
fixture). A loopback HTTP server stands in for proto.bar: update_manifest_url points
at it (update_allow_insecure 1), so the notes URL is its /patchnotes.json.

  subject   p744's fixture manifest, so update_consent reads 1 with the updater inert
            (qkupdate.c); ui_release_version is set to the newest release in the file,
            so the panel is "What's new". Graded on the menu's own lines: it asked the
            server, parsed the releases, showed the panel, Close hid it and wrote
            ui_notes_seen, a menu_restart kept it hidden, ui_notes open showed it again.
  control   the real default.fmf, so update_consent is -1 (nothing decided): the menu
            must not ask, and the server must see no request.

Screenshots (open, scrolled, closed, reopened) are kept for looking at.
"""
import argparse
from datetime import datetime, timezone
import functools
import http.server
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading

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
waitms 12000
ui_notes status
screenshot p876_1_open
waitms 2500
ui_notes scroll 900
waitms 1000
screenshot p876_2_scrolled
waitms 2500
ui_notes close
waitms 1000
ui_notes status
screenshot p876_3_closed
waitms 2500
menu_restart
waitms 8000
ui_notes status
ui_notes open
waitms 1500
ui_notes status
screenshot p876_4_reopened
waitms 2500
set update_allow_insecure 0
ui_notes status
echo P876 ARM COMPLETE
quit
'''


class Quiet(http.server.SimpleHTTPRequestHandler):
    seen = []

    def log_message(self, fmt, *args):
        Quiet.seen.append(self.path)


def run(a, name, manifest_real, version, port):
    base = prepare(a, name)
    game = base / 'ftesurf'
    (game / 'data/consent.txt').write_text(f'FTESURF-CONSENT 1\nversion {a.tier}\naccepted 20261020-000000\n')
    if manifest_real:
        shutil.copy2(a.content / 'default.fmf', base / 'default.fmf')
        assert not (base / '.ftesurf-updater/consent').exists()
    (game / 'probe.cfg').write_text(CFG)
    proc = subprocess.Popen(
        [str(a.client), '-nohome', '-noreset', '-nobrowse', '-basedir', str(base),
         '-manifest', str(base / 'default.fmf'), '-window', '-width', '1280', '-height', '800',
         '-nosound', '+set', 'cfg_save_auto', '0',
         '+set', 'update_manifest_url', f'http://127.0.0.1:{port}/update.json',
         '+set', 'update_allow_insecure', '1', '+set', 'ui_release_version', version,
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
    for s in sorted((game / 'screenshots').glob('p876_*')):
        shutil.copy2(s, a.out / f'{name}-{s.name}')
    shutil.rmtree(base)
    return log, quit_ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--notes', type=Path, required=True, help='a patchnotes.json as release.ps1 renders it')
    ap.add_argument('--tier', type=int, default=7)
    ap.add_argument('--port', type=int, default=8876)
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    ap.add_argument('--plugin', type=Path, default=Path('C:/FTESurf/fteplug_hl2_x64.dll'))
    a = ap.parse_args()
    a.out = a.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in a.out.parents):
        ap.error('--out must be beneath an owned task root')
    a.out.mkdir(parents=True, exist_ok=False)
    notes = json.loads(a.notes.read_text(encoding='utf-8'))
    newest = notes['releases'][0]['version']
    items = sum(1 + sum(1 + len(p['points']) for p in r['patches']) for r in notes['releases'])
    served = a.out / 'served'
    served.mkdir()
    shutil.copy2(a.notes, served / 'patchnotes.json')
    httpd = http.server.ThreadingHTTPServer(('127.0.0.1', a.port), functools.partial(Quiet, directory=str(served)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    checks = []
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'newest': newest, 'items': items,
              'progs': {p: sha(a.progs / p)[:16] for p in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')},
              'client': sha(a.client)[:16], 'checks': checks}

    def check(ok, name):
        checks.append({'name': name, 'pass': bool(ok)})
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)

    try:
        log, ok = run(a, 'subject', False, newest, a.port)
        asked = Quiet.seen[:]
        st = re.findall(r'ui_notes: state (\S+) shown (\S+) items (\S+) lines (\S+) wrap (\S+) scroll (\S+)', log)
        inst = re.findall(r'ui_notes: installed (\S*) listed (\S+) seen (\S*) url (\S*)', log)
        report['subject'] = {'requests': asked, 'status': st, 'installed': inst,
                             'parsed': re.findall(r'notes:(?:\^7)? ([^\n]*)', log)}
        check(ok and 'P876 ARM COMPLETE' in log, 'subject: the cfg ran to its end')
        check(f'asking http://127.0.0.1:{a.port}/patchnotes.json' in log and '/patchnotes.json' in asked,
              'subject: the menu asked and the server answered /patchnotes.json')
        check(f'{len(notes["releases"])} releases, {items} items; installed {newest} listed 1' in log,
              f'subject: parsed {len(notes["releases"])} releases and {items} items, {newest} listed')
        # One status per ui_notes command: status, scroll, close, status, status, open, status, status.
        full = len(st) == 8 and len(inst) == 8
        check(full and st[0][:2] == ('2', '1') and int(st[0][3]) > items,
              'subject: shown on the title menu, wrapped into more lines than items')
        check(full and st[1][5] == '900', 'subject: the list took the scroll')
        check(full and st[3][1] == '0' and inst[3][2] == newest, 'subject: Close hid it and wrote ui_notes_seen')
        check(full and st[4][:2] == ('0', '0'), 'subject: after menu_restart nothing asked or shown')
        check(full and st[6][1] == '1', 'subject: ui_notes open shows it again')
        check(full and inst[7][3] == '', 'subject: no http URL without update_allow_insecure')
        check(not re.search(r'(?i)boundcheck|runaway|stack overflow|QC crash|PR_memfree', log), 'subject: no menu VM faults')

        Quiet.seen.clear()
        log, ok = run(a, 'control', True, newest, a.port)
        st = re.findall(r'ui_notes: state (\S+) shown (\S+)', log)
        report['control'] = {'requests': Quiet.seen[:], 'status': st,
                             'probes': re.findall(r'ui_update_probe: ([^\n]*)', log)}
        check(ok and 'P876 ARM COMPLETE' in log, 'control: the cfg ran to its end')
        check(not Quiet.seen and 'asking http' not in log, 'control: no permission, no request')
        check(len(st) == 8 and all(s == ('0', '0') for s in st), 'control: nothing loaded or shown, even when opened')
    finally:
        httpd.shutdown()
    report['failures'] = sum(1 for c in checks if not c['pass'])
    (a.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('report', a.out / 'report.json', 'failures', report['failures'])
    sys.exit(1 if report['failures'] else 0)


if __name__ == '__main__':
    main()
