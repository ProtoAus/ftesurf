#!/usr/bin/env python3
"""Patch 876: the patch notes, read from a local patchnotes.json -- in F2 since Patch 902.

Four clients, one after the other, each in its own basedir under --out (p744spec.py's
fixture). A loopback HTTP server stands in for proto.bar: update_manifest_url points
at it (update_allow_insecure 1), so the notes URL is its /patchnotes.json.

  subject   the real default.fmf and .ftesurf-updater/consent "1": FTESurf's updater,
            live and allowed (its own check of /update.json 404s). Graded on the menu's
            own lines: nothing asked on the title screen (P902: no panel there), ui_notes
            open shows F2's notes page and asks, the list parsed and wrapped, scroll took,
            close left F2, a menu_restart asked nothing, open asked again.
  inert     p744's fixture manifest: update_consent reads 1 but the updater is not
            FTESurf's and does nothing (qkupdate.c QKU_MenuAction) -- no request.
  noperm    the real manifest with no permission file (update_consent -1) -- no request.

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
waitms 8000
ui_notes status
screenshot p876_0_title
ui_notes open
waitms 4000
ui_notes status
screenshot p876_1_open
waitms 2500
ui_notes scroll 900
waitms 1000
screenshot p876_2_scrolled
waitms 2500
ui_notes select @OLDER@
waitms 500
ui_notes status
screenshot p876_5_older
ui_notes select @NEWEST@
waitms 500
ui_notes status
ui_notes close
waitms 1000
ui_notes status
screenshot p876_3_closed
waitms 2500
menu_restart
waitms 8000
ui_journal updates
waitms 3000
ui_notes status
ui_notes open
waitms 3000
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


def run(a, name, version, port, real=True, permit=True, extra=()):
    base = prepare(a, name)
    game = base / 'ftesurf'
    (game / 'data/consent.txt').write_text(f'FTESURF-CONSENT 1\nversion {a.tier}\naccepted 20261020-000000\n')
    if real:
        shutil.copy2(a.content / 'default.fmf', base / 'default.fmf')
        assert not (base / '.ftesurf-updater/consent').exists()
        if permit:
            (base / '.ftesurf-updater').mkdir()
            (base / '.ftesurf-updater/consent').write_text('1\n')
    (game / 'probe.cfg').write_text(CFG.replace('@OLDER@', a.older).replace('@NEWEST@', version))
    proc = subprocess.Popen(
        [str(a.client), '-nohome', '-noreset', '-nobrowse', '-basedir', str(base),
         '-manifest', str(base / 'default.fmf'), '-window', '-width', '1280', '-height', '800',
         '-nosound', '+set', 'cfg_save_auto', '0',
         '+set', 'update_manifest_url', f'http://127.0.0.1:{port}/update.json',
         '+set', 'update_allow_insecure', '1', '+set', 'ui_release_version', version,
         *extra, '+exec', 'probe.cfg'],
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
    a.older = notes['releases'][-1]['version']
    selected_items = 1 + sum(1 + len(p['points']) for p in notes['releases'][0]['patches'])
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
        log, ok = run(a, 'subject', newest, a.port)
        asked = Quiet.seen[:]
        st = re.findall(r'ui_notes: state (\S+) shown (\S+) items (\S+) lines (\S+) wrap (\S+) scroll (\S+)', log)
        inst = re.findall(r'ui_notes: installed (\S*) listed (\S+) url (\S*)', log)
        report['subject'] = {'requests': asked, 'status': st, 'installed': inst,
                             'parsed': re.findall(r'notes:(?:\^7)? ([^\n]*)', log)}
        check(ok and 'P876 ARM COMPLETE' in log, 'subject: the cfg ran to its end')
        check(f'asking http://127.0.0.1:{a.port}/patchnotes.json' in log and '/patchnotes.json' in asked,
              'subject: the menu asked and the server answered /patchnotes.json')
        check(f'{len(notes["releases"])} releases, {items} items; installed {newest} listed 1' in log,
              f'subject: parsed {len(notes["releases"])} releases and {items} items, {newest} listed')
        # One status per ui_notes command: status, open, status, scroll, close, status,
        # status, open, status, status.
        selections = re.findall(r'ui_notes: selected (\S+) of (\d+)', log)
        check((a.older, str(len(notes['releases']))) in selections,
              'subject: an older version was selected')
        check(len(ask := re.findall(r'notes:(?:\^7)? asking http', log)) == 2,
              'subject: version selection does not fetch the feed again')
        check(len(st) == 14 and st[5][5] == '0' and st[7][5] == '0',
              'subject: changing version resets the reading position')
        # Exclude the select/status pairs for the original permission/lifecycle checks.
        st = st[:4] + st[8:]
        inst = inst[:4] + inst[8:]
        full = len(st) == 10 and len(inst) == 10
        ask = [m.start() for m in re.finditer(r'notes:(?:\^7)? asking http', log)]
        opened = [m.start() for m in re.finditer(r'ui_notes: state', log)]
        check(full and st[0][:2] == ('0', '0') and ask and ask[0] > opened[1],
              'subject: nothing asked or shown on the title screen; asked after the open')
        check(full and st[1][1] == '1' and st[2][:2] == ('2', '1') and int(st[2][3]) > selected_items,
              'subject: F2 shows the selected release, wrapped into more lines than its items')
        check(full and st[3][5] == '900', 'subject: the list took the scroll')
        check(full and st[4][1] == '0' and st[5][1] == '0', 'subject: close left F2')
        check(full and st[6][:2] == ('0', '0'), 'subject: after menu_restart, F2 on its Updates page for 3 s: nothing asked')
        check(full and st[8][:2] == ('2', '1') and len(ask) == 2, 'subject: ui_notes open asked and showed it again')
        check(full and inst[9][2] == '', 'subject: no http URL without update_allow_insecure')
        check(not re.search(r'(?i)boundcheck|runaway|stack overflow|QC crash|PR_memfree', log), 'subject: no menu VM faults')

        for name, kw in (('inert', {'real': False}), ('noperm', {'permit': False})):
            Quiet.seen.clear()
            log, ok = run(a, name, newest, a.port, **kw)
            st = re.findall(r'ui_notes: state (\S+) shown (\S+)', log)
            report[name] = {'requests': Quiet.seen[:], 'status': st}
            check(ok and 'P876 ARM COMPLETE' in log, f'{name}: the cfg ran to its end')
            check('/patchnotes.json' not in Quiet.seen and 'asking http' not in log, f'{name}: no request')
            check(len(st) == 14 and all(s[0] == '0' for s in st), f'{name}: nothing loaded, even when opened')

    finally:
        httpd.shutdown()
    report['failures'] = sum(1 for c in checks if not c['pass'])
    (a.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('report', a.out / 'report.json', 'failures', report['failures'])
    sys.exit(1 if report['failures'] else 0)


if __name__ == '__main__':
    main()
