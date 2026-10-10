#!/usr/bin/env python3
"""Acting /2 bridge and real pinned-ImGui dense pages, both index widths, -Werror."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from p598build import build, ROOT
from test_p590bridge_unit import host_controls


def run(fte, cc, cxx, out):
    if not any((p/'OWNER.md').is_file() for p in [out, *out.parents]):
        raise RuntimeError('--out needs an owned task root')
    out.mkdir(parents=True, exist_ok=True)
    if host_controls(fte, cc, ROOT/'tools/fixtures/p603dense_bridge.c'):
        return 1
    env = os.environ.copy()
    env['PATH'] = str(cxx.parent)+os.pathsep+env.get('PATH', '')
    failures = 0
    for bits in (16, 32):
        exe = build(fte, out/f'host{bits}', cxx, host=True, index32=bits == 32,
                    host_source=ROOT/'tools/fixtures/p603dense_host.cpp')
        log = out/f'host{bits}.log'
        with log.open('w') as stream:
            result = subprocess.run([str(exe)], env=env, stdout=stream, stderr=subprocess.STDOUT)
        text = log.read_text()
        for line in text.splitlines():
            if line.startswith(('FAIL', 'P595 HOST', 'P603 SCORES', 'P603 DENSE')):
                print(line)
        if result.returncode or 'P603 DENSE indexbits=' not in text or 'failed=0' not in text.splitlines()[-1]:
            failures += 1
            print('Failed host log:', log)
    return bool(failures)


def control(subject, predecessor, cxx, out):
    manifest = json.loads((predecessor/'control.json').read_text())
    if manifest.get('variant') != 'six-row-limit': raise RuntimeError('wrong source control')
    differences = []
    for record in manifest['files']:
        path = predecessor/record['path']
        current = (subject/record['path']).read_bytes()
        if hashlib.sha256(current).hexdigest() != record['sha256']:
            raise RuntimeError('control source changed after snapshot: '+record['path'])
        if path.read_bytes() != current: differences.append(record['path'])
    if differences != ['plugins/ui_imgui/scores.inc']:
        raise RuntimeError('control is not a one-factor source freeze')
    before = (subject/differences[0]).read_text()
    if (predecessor/differences[0]).read_text() != before.replace('(m.count-base)/9 > 24','(m.count-base)/9 > 6'):
        raise RuntimeError('wrong bound mutation')
    env = os.environ.copy(); env['PATH'] = str(cxx.parent)+os.pathsep+env.get('PATH','')
    for bits in (16,32):
        for label, fte, expected in (('subject',subject,0),('six-row-control',predecessor,1)):
            directory = out/f'{label}-{bits}'
            exe = build(fte,directory,cxx,host=True,index32=bits==32,
                        host_source=ROOT/'tools/fixtures/p603dense_control.cpp')
            result = subprocess.run([str(exe)],env=env,capture_output=True,text=True)
            (directory/'host.log').write_text(result.stdout+result.stderr)
            if (result.returncode != expected or result.stdout.count('FAIL ') != expected or
                f'P603 DENSE CONTROL indexbits={bits} failed={expected}' not in result.stdout or
                (expected and 'FAIL 24-row acceptance falsifies six-row ceiling' not in result.stdout)):
                raise RuntimeError('control failed outside registered density oracle: '+str(directory))
            print(label,bits,'expected failures=',expected,'acting original scoreboard/font controls=3750')
    return 0


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fte', type=Path, default=Path('C:/msys64/home/Lex/fteqw-imgui-input'))
    p.add_argument('--cc', type=Path, default=Path('C:/msys64/ucrt64/bin/gcc.exe'))
    p.add_argument('--cxx', type=Path, default=Path('C:/msys64/ucrt64/bin/g++.exe'))
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--control', type=Path, help='One-factor source-only six-row bound control')
    a = p.parse_args()
    if a.control:
        if not any((p/'OWNER.md').is_file() for p in [a.out.resolve(),*a.out.resolve().parents]):
            p.error('--out needs an owned task root')
        raise SystemExit(control(a.fte.resolve(),a.control.resolve(),a.cxx.resolve(),a.out.resolve()))
    raise SystemExit(run(a.fte.resolve(), a.cc.resolve(), a.cxx.resolve(), a.out.resolve()))
