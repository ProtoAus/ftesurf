#!/usr/bin/env python3
"""P1130: actual menu switches, cached reopen, completion cards and show-all reset.

Uses synthetic surfd data only, one owned window, and p840's shared runtime lock.
python -B tools/test_stats_modes.py --progs <NoDeploy dir> --out <owned artifacts>
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import p840clock as P


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out = a.out.resolve()
    P.owned(a.out)
    a.out.mkdir(parents=True, exist_ok=False)
    home = a.out / 'service'
    (home / 'maps').mkdir(parents=True)
    os.environ.update(SURFD_HOME=str(home), SURFD_DB=str(home / 'test.db'),
                      SURFD_MAPS=str(home / 'maps'))
    sys.path.insert(0, str(ROOT / 'surfd'))
    import surfd as S
    import ksfimport as K
    from werkzeug.serving import make_server
    K.fetch = lambda *args, **kw: (_ for _ in ()).throw(AssertionError('no external imports'))
    names = ['surf_uiwos', 'surf_uiimport', 'bhop_uiwos', 'bhop_uinext']
    data = Path(S.DATA_DIR)
    watch = data / 'mapwatch'
    watch.mkdir(parents=True)
    manifest = 'FTESURF-MAPDL 1\n' + ''.join(
        f'dl {n} {n.split("_")[0]} m 1 100 2026-10-30 0 1 0\n' for n in names)
    (watch / 'mapdl.txt').write_text(manifest)
    (data / 'momtracks.tsv').write_text(''.join(f'{n}\t1\t1\t1\t0\t1\n' for n in names))
    for directory in (S.ZONES_DIR, S.ZONES_LOCAL_DIR):
        Path(directory).mkdir(parents=True, exist_ok=True)
    for name in names:
        (home / 'maps' / (name + '.bsp')).write_bytes(b'synthetic catalogue, never loaded')
        (Path(S.ZONES_DIR) / (name + '.json')).write_text('{}')
    S.maps_reset()
    S.MOMTRACKS_PATH = str(data / 'momtracks.tsv')
    S._mt['at'] = -1e9
    me = 'fixture-ui-person'
    db = S.connect()
    for i, (name, tier) in enumerate(zip(names[:3], ['ranked', 'momentum', 'ranked'])):
        db.execute("INSERT INTO runs(map,track,leg,tier,style,player,name,ticks,tickrate,millis,flags,node,runid,submitted,replay_id) "
                   "VALUES(?,0,0,?,'clean',?,'UI Fixture',100,100,?,0,'fixture',?,1,0)",
                   (name, tier, me, 1000 + i * 100, 'ui-' + str(i)))
    db.commit()
    db.close()
    S.people_reset()
    who = S.web_handle(me)
    asks = []

    @S.app.before_request
    def observe():
        from flask import request
        if request.path == '/api/board':
            asks.append(dict(request.args))

    server = make_server('127.0.0.1', 0, S.app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{server.server_port}'
    checks = []
    proc = None
    locked = False
    try:
        P.take_lock('P1130 stats modes')
        locked = True
        # P840's legacy process names omit owned client.exe windows. Refuse those too.
        gate = subprocess.run(['pwsh', '-NoProfile', '-Command',
            'Get-CimInstance Win32_Process | Where-Object { $_.Name -match "^(client|ftesurf64|fteqw64|fteqwsv64)\\.exe$" } | ForEach-Object { "ACTIVE $($_.ProcessId)" }'],
            capture_output=True, text=True, check=True)
        if gate.stdout.strip():
            raise RuntimeError('owner/peer game present: ' + gate.stdout)
        base = P.prepare(a.out, 'client', a.progs, a.progs / 'csprogs.dat')
        game = base / 'ftesurf'
        shutil.copy2(P.CONTENT / 'ftesurf64.exe', base / 'client.exe')
        (game / 'data/consent.txt').write_text('version 8\n')
        (game / 'data/story_me.txt').write_text('FTESURF-STORYME 1\n' + who + '\n')
        (game / 'data/mapdl.txt').write_text(manifest)
        (game / 'probe.cfg').write_text('\n'.join([
            'cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs',
            'log_name probe', 'log_readable 1', 'developer 1', 'log_developer 1',
            'set cl_idlefps 0', 'set cl_maxfps 100', 'set lobby_master ""',
            f'set lobby_dir "{url}"', 'set ui_maps_showall 1', 'echo P1130 READY']) + '\n')
        log = game / 'logs/probe.log'

        def text():
            return log.read_text(encoding='utf-8', errors='replace') if log.exists() else ''

        def send(line):
            proc.stdin.write((line + '\n').encode('ascii'))
            proc.stdin.flush()

        def wait(pattern, start=0, timeout=35):
            end = time.monotonic() + timeout
            while time.monotonic() < end:
                match = re.search(pattern, text()[start:])
                if match:
                    return match
                if proc.poll() is not None:
                    raise RuntimeError('client exited ' + str(proc.returncode))
                time.sleep(0.1)
            raise AssertionError('not observed: ' + pattern)

        def check(label, condition):
            checks.append({'name': label, 'pass': bool(condition)})
            print(('PASS ' if condition else 'FAIL ') + label, flush=True)
            if not condition:
                raise AssertionError(label)

        def click(element):
            send('ui_hover @' + element)
            time.sleep(0.25)
            send('ui_mouse down')
            time.sleep(0.15)
            send('ui_mouse up')
            time.sleep(0.5)

        def shot(name):
            send('ui_hover 0 0')
            time.sleep(0.3)
            send('screenshot p1130_' + name + '.png')
            time.sleep(1)

        def launch():
            return subprocess.Popen([str(base / 'client.exe'), '-plugin', '-nohome', '-noreset', '-nobrowse',
                '-basedir', str(base), '-manifest', str(base / 'default.fmf'), '-window',
                '-width', '1600', '-height', '900', '-nosound', '+set', 'cfg_save_auto', '0',
                '+exec', 'probe.cfg'], cwd=P.CONTENT, stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        proc = launch()
        (a.out / 'owned-pid.txt').write_text(str(proc.pid))
        wait('P1130 READY')
        time.sleep(6)
        send('ui_showall')
        wait(r'ui_showall: 0')
        check('old archived show-all value cannot enable it at launch', True)
        send('ui_home_probe')
        wait(r'home: stats .* state 2')
        check('synthetic home has Surf and Bhop tables', 'kind 0 kinds 1' in text())
        shot('home_all')
        for place, kind, name in [(0, 1, 'surf'), (1, 2, 'bhop'), (2, 0, 'all')]:
            click('home_stats_kind' + str(place))
            mark = len(text())
            send('ui_home_probe')
            wait(rf'home: tierdata .* kind {kind} kinds 1', mark)
            shot('home_' + name)
        click('home_stats_kind0')
        send('ui_stats open')
        time.sleep(3)
        send('ui_stats')
        wait(r'ui_stats: kind 1 rows-kind 1 rows-source 1 rows 1/1 waiting 0 first surf_uiwos')
        check('first stats opening asks for Surf WOS records',
              any(q.get('player') == who and q.get('mode') == 'surf' for q in asks))
        shot('stats_surf')
        send('ui_stats close')
        time.sleep(1)
        click('home_stats_kind1')
        count = len(asks)
        mark = len(text())
        send('ui_stats open')
        time.sleep(2)
        send('ui_stats')
        wait(r'ui_stats: kind 2 rows-kind 2 rows-source 1 rows 1/1 waiting 0 first bhop_uiwos', mark)
        check('cached reopen really re-asks Bhop rows', any(q.get('mode') == 'bhop' for q in asks[count:]))
        shot('stats_bhop_reopen')
        click('pf_cm_sw0')
        time.sleep(1)
        mark = len(text())
        send('ui_stats')
        wait(r'ui_stats: kind 1 rows-kind 1 rows-source 1 rows 1/1 waiting 0 first surf_uiwos', mark)
        check('full-page three-way switch changes its rows', True)
        shot('stats_clicked_surf')
        click('pf_cs_sw')
        mark = len(text())
        send('ui_stats')
        wait(r'ui_stats: kind 1 rows-kind 1 rows-source 0 rows 2/2 waiting 0', mark)
        check('Everything source includes the imported Surf finish', True)
        click('pf_cm_sw2')
        mark = len(text())
        send('ui_stats')
        wait(r'ui_stats: kind 0 rows-kind 0 rows-source 0 rows 3/3 waiting 0', mark)
        check('full-page All includes both kinds on Everything', True)
        shot('stats_all_everything')
        send('ui_stats close')
        send('ui_showall 1')
        send('ui_strip_test screen create')
        time.sleep(1)
        send('ui_strip_test screen main')
        time.sleep(1)
        send('ui_strip_test screen create')
        time.sleep(1)
        mark = len(text())
        send('ui_showall')
        wait(r'ui_showall: 1', mark)
        check('show-all choice survives same-session screen navigation', True)
        click('cs_sort2')
        time.sleep(1)
        mark = len(text())
        send('ui_compsort')
        wait(r'ui_compsort: mode 2 .* complete 2 incomplete 2 unknown 0', mark)
        wait(r'ui_compsort: first (surf|bhop)_uiwos done 1', mark)
        check('completed-first order uses only the two WOS finishes', True)
        send('ui_menu_probe')
        time.sleep(1)
        shot('mapcards')
        check('map cards request reached the synthetic service', any('cards' in q for q in asks))
        check('WOS completed sort asks for its explicit source',
              any('completed' in q and q.get('source') == 'wos' for q in asks))
        check('no missing test controls or QC runtime fault',
              not re.search(r'no control \[|(?i:boundcheck|stack overflow|assignment to const)', text()))
        # A second actual launch must not inherit the session choice or archived cvar.
        send('quit')
        proc.wait(timeout=10)
        proc = launch()
        (a.out / 'owned-relaunch-pid.txt').write_text(str(proc.pid))
        time.sleep(8)
        mark = len(text())
        send('ui_showall')
        wait(r'ui_showall: 0', mark)
        check('second launch resets Show all off again', True)
        send('ui_strip_test screen main')
        send('vid_conautoscale 0')
        send('vid_conwidth 640')
        send('vid_conheight 480')
        time.sleep(2)
        shot('home_narrow')
    finally:
        if proc and proc.poll() is None:
            try:
                proc.stdin.write(b'quit\n')
                proc.stdin.flush()
                proc.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                proc.terminate()
                proc.wait(timeout=10)
        if locked:
            P.drop_lock()
        server.shutdown()
        (a.out / 'requests.json').write_text(json.dumps(asks, indent=2) + '\n')
        (a.out / 'checks.json').write_text(json.dumps(checks, indent=2) + '\n')


if __name__ == '__main__':
    main()
