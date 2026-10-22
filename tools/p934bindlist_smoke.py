#!/usr/bin/env python3
"""Native bindlist control/subject using synthetic bindings in an owned rig.
Never inspect/dump the owner's bindings or send keys to the owner's process.
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
    p.add_argument('--engine', type=Path, required=True)
    p.add_argument('--progs', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--control', action='store_true')
    a = p.parse_args()
    a.content = Path('C:/FTESurf')
    a.output_dir = a.out.resolve()
    a.output_dir.mkdir(parents=True, exist_ok=True)
    a.progs = a.progs.resolve()
    a.engine = a.engine.resolve()
    rig, gd, links = L.build_rig(a)
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 4
    client = subprocess.Popen([
        str(a.engine), '-plugin', '-nobrowse', '-basedir', str(rig),
        '-manifest', str(rig / 'default.fmf'), '-window', '-nosound',
        '+set', 'cfg_save_auto', '0', '+set', 'con_savehistory', '0',
        '+set', 'cl_idlefps', '0', '+set', 'cl_maxfps', '100',
        '+set', 'rec_terms', '0', '+set', 'log_enable', '1',
        '+set', 'log_dir', 'logs', '+set', 'log_name', 'p934bindlist'],
        cwd=a.content, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, startupinfo=si)
    record = a.output_dir / 'process.json'
    record.write_text(json.dumps({'pid': client.pid, 'rig': str(rig)}))
    log = gd / 'logs/p934bindlist.log'

    def send(cmd, delay=.35):
        assert client.poll() is None, 'Owned client exited'
        client.stdin.write((cmd + '\n').encode('ascii'))
        client.stdin.flush()
        time.sleep(delay)

    def text():
        return log.read_text(errors='replace') if log.exists() else ''

    def saved_bindings(leaf):
        files = list(rig.rglob(leaf))
        assert len(files) == 1, (leaf, len(files))
        return [s for s in files[0].read_text(errors='replace').splitlines()
                if re.match(r'^(?:bind|bindlevel|in_bind) ', s)]

    try:
        time.sleep(12)
        send('unbindall; bind a +forward; bind b "echo fixture-b"; bind z "echo fixture-z"')
        send('bind ctrl+a "echo fixture-ctrl"; bindlevel f5 30 "echo fixture-level"')
        send('bind mouse3 "echo fixture-quote; echo fixture-two"; in_bind 2 mouse1 "echo fixture-map"')
        send('bind a; bind ctrl+a; in_bind 2 mouse1')
        assert all(s in text() for s in ['+forward', 'fixture-ctrl', 'fixture-map']), 'Fixtures did not ACT'
        send('cfg_save p934_before.cfg', .5)
        before = saved_bindings('p934_before.cfg')
        assert before, 'No saved binding control'
        send('echo P934_BEGIN; bindlist; echo P934_END', .6)
        section = text().split('P934_BEGIN')[-1].split('P934_END')[0]
        if a.control:
            assert 'Unknown command "bindlist"' in section, section
            print('PASS old control: fixtures acted, bindlist absent')
        else:
            assert '7 bound key entries.' in section, section
            assert 'Bindmap 2' in section and '(level 30)' in section, section
            assert all(s in section for s in ['+forward', 'fixture-b', 'fixture-z', 'fixture-ctrl',
                                             'fixture-level', 'fixture-quote; echo fixture-two', 'fixture-map'])
            groups = section.split('Bindmap 2')
            base = []
            for line in groups[0].splitlines():
                line = re.sub(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', '', line)
                if '"' in line and ('fixture-' in line or '+forward' in line):
                    base.append(line.split(None, 1)[0])
            assert len(base) == 6 and base == sorted(base, key=str.casefold), base
            print('PASS seven entries, sorted base keys, modifier override, level and alternate bindmap')
        send('cfg_save p934_after.cfg', .5)
        assert saved_bindings('p934_after.cfg') == before, 'Listing changed bindings'
        print('PASS saved binding directives unchanged')
        if not a.control:
            send('unbindall; echo P934_EMPTY; bindlist', .5)
            assert '0 bound key entries.' in text().split('P934_EMPTY')[-1]
            print('PASS empty listing')
        print('evidence', rig)
    finally:
        if client.poll() is None:
            try:
                send('quit', .1)
                client.wait(timeout=8)
            except (OSError, subprocess.TimeoutExpired):
                client.kill()
                client.wait(timeout=5)
        for link in links:
            if link.exists():
                link.rmdir()
        record.write_text(json.dumps({'pid': client.pid, 'stopped': True, 'rig': str(rig)}))


if __name__ == '__main__':
    main()
