#!/usr/bin/env python3
"""Owned, offline UI smoke: real menu selection and browser-open behavior.

No clipboard access, no server, no credentials, no owner process manipulation.
Use --control for the unmodified VM: the double-click must NOT select all.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time

import p615link as L


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--progs', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--control', action='store_true')
    a = p.parse_args()
    a.content = Path('C:/FTESurf')
    a.output_dir = a.out.resolve()
    a.output_dir.mkdir(parents=True, exist_ok=True)
    a.progs = a.progs.resolve()
    rig, gd, links = L.build_rig(a)
    (gd / 'data').mkdir(exist_ok=True)
    # The same isolated consent fixture as p655text; otherwise the Terms screen
    # correctly replaces the forced Name screen before a field can act.
    (gd / 'data/consent.txt').write_text('FTESURF-CONSENT 1\nversion 1\naccepted 20261022-000000\n')
    (gd / 'data/friends_menu.txt').write_text('FTESURF-FRIENDS 1\n3 "Fixture Alice"\n3 "Fixture Bob"\n')
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 4
    client = subprocess.Popen([
        str(a.content / 'ftesurf64.exe'), '-plugin', '-nobrowse', '-basedir', str(rig),
        '-manifest', str(rig / 'default.fmf'), '-window', '-nosound',
        '+set', 'cfg_save_auto', '0', '+set', 'con_savehistory', '0',
        '+set', 'cl_idlefps', '0', '+set', 'cl_maxfps', '100',
        '+set', 'vid_width', '1280', '+set', 'vid_height', '900',
        '+set', 'vid_fullscreen', '0', '+set', 'rec_terms', '0',
        '+set', 'log_enable', '1', '+set', 'log_dir', 'logs', '+set', 'log_name', 'p933ui'],
        cwd=a.content, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, startupinfo=si)
    (a.output_dir / 'process.json').write_text(json.dumps({'pid': client.pid, 'rig': str(rig)}))
    logpath = gd / 'logs/p933ui.log'

    def text():
        return logpath.read_text(errors='replace') if logpath.exists() else ''

    def send(cmd, delay=.12):
        assert client.poll() is None, 'Owned client exited'
        client.stdin.write((cmd + '\n').encode('ascii'))
        client.stdin.flush()
        time.sleep(delay)

    def state():
        send('ui_name field; ui_name sel', .25)
        fields = re.findall(r'ui_name: field "(.*)" caret (-?\d+)', text())
        sels = re.findall(r'ui_name: sel (-?\d+) mods (\d+)', text())
        assert fields and sels, 'No acted name-field telemetry'
        return fields[-1][0], int(fields[-1][1]), int(sels[-1][0])

    def fill():
        send('ui_name screen', .3)
        send('ui_key tab', .3)
        for c in 'surfer':
            send(f'ui_key {c} down {ord(c)}; ui_key {c} up', .025)
        assert state() == ('surfer', 6, -1), state()
        send('ui_hover @nm_field 0 0', .25)

    def click():
        send('ui_mouse down', .04)
        send('ui_mouse up', .04)

    try:
        time.sleep(12)
        send('menu_restart', 2)
        send('togglemenu', .5)
        fill()
        click()
        click()
        got = state()
        if a.control:
            assert got[0] == 'surfer' and got[2] == -1, got
        else:
            assert got == ('surfer', 6, 0), got
            send('ui_key z down 122; ui_key z up')
            assert state() == ('z', 1, -1), state()
        print('PASS double-click acted:', got, 'control' if a.control else 'subject')
        fill()
        click()
        time.sleep(.5)
        click()
        got = state()
        assert got[0] == 'surfer' and got[2] == -1, got
        print('PASS slow clicks do not select all:', got)
        send('ui_key escape; set ui_maps_friends 0', .5)
        send('ui_hover @mm_play 0 0', .3)
        click()
        send('ui_menu_probe', .5)
        probes = re.findall(r'ui_menu_probe: filters=.*? friends=(\d+)', text())
        assert probes and int(probes[-1]) == (0 if a.control else 1), probes
        assert 'friends_draw=2' in text(), 'Saved two-row fixture was not read'
        print('PASS browser-open friends:', probes[-1], 'two-row fixture loaded')
        send('screenshot p933-browser.png', .5)
        print('evidence', rig)
    finally:
        if client.poll() is None:
            try:
                send('quit', .1)
                client.wait(timeout=8)
            except (OSError, subprocess.TimeoutExpired):
                client.kill()
                client.wait(timeout=5)
        # Links point at shared content. Unlink only; never recurse into them.
        for link in links:
            if link.exists():
                link.rmdir()
        (a.output_dir / 'process.json').write_text(json.dumps({'pid': client.pid, 'stopped': True, 'rig': str(rig)}))


if __name__ == '__main__':
    main()
