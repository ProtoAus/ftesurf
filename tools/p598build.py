#!/usr/bin/env python3
"""Build the pinned service or real-source host controls in owned output dirs."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ('imgui.cpp', 'imgui_draw.cpp', 'imgui_tables.cpp', 'imgui_widgets.cpp')
# Since Patch 614 ui_imgui.cpp also links ImPlot's core (the host fixtures include that file, so
# they need it as well); an engine tree from before the patch has no such source.
SINCE_614 = ('implot.cpp',)


def build(fte: Path, out: Path, cc: Path, host=False, index32=False, host_source=None):
    source = fte/'plugins/ui_imgui'
    checks = json.loads((source/'vendor/SHA256.json').read_text())
    for name, expected in checks.items():
        if hashlib.sha256((source/'vendor'/name).read_bytes()).hexdigest() != expected:
            raise RuntimeError('Pinned vendor hash differs: '+name)
    env = os.environ.copy()
    env['PATH'] = str(cc.parent)+os.pathsep+env['PATH']
    flags = ['-std=c++17', '-DFTEPLUGIN', '-DIMGUI_USE_WCHAR32', '-Wall', '-Wextra', '-Werror']
    flags += ['-I'+str(fte/p) for p in ('plugins', 'engine/client', 'engine/common', 'engine/server', 'engine/gl')]
    flags += ['-I'+str(source)]
    if index32:
        flags += ['-DImDrawIdx=ImU32']
    out.mkdir(parents=True, exist_ok=True)
    objects, entries = [], []
    sources = [source/'backend.cpp']
    sources += [(host_source or ROOT/'tools/fixtures/p598imgui_host.cpp') if host else source/'ui_imgui.cpp']
    sources += [source/'vendor'/p for p in VENDOR]
    sources += [source/'vendor'/p for p in SINCE_614 if (source/'vendor'/p).is_file()]
    with (out/'compile.log').open('w') as log:
        for p in sources:
            obj = out/(p.stem+'.o')
            # GCC 16 -O2 diagnoses upstream mouse array bounds despite its assertion;
            # pin vendor to -O1, unchanged source, no warning suppression. Adapter -O2.
            cmd = [str(cc), *flags, '-O1' if p.parent.name == 'vendor' else '-O2', '-c', str(p), '-o', str(obj)]
            entries.append({'directory': str(fte), 'file': str(p), 'arguments': cmd})
            subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            objects.append(str(obj))
        target = out/('host32.exe' if index32 else 'host.exe') if host else out/'fteplug_ui_imgui_x64.dll'
        cmd = [str(cc), '-static-libgcc', '-static-libstdc++', '-static', *([] if host else ['-shared']), *objects, '-o', str(target)]
        subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    if (out/'compile.log').read_text().strip():
        raise RuntimeError('Compiler/linker warnings: '+str(out/'compile.log'))
    (out/'compile_commands.json').write_text(json.dumps(entries, indent=2)+'\n')
    return target


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fte', type=Path, default=Path('C:/msys64/home/Lex/fteqw-ui-bridge'))
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--cc', type=Path, default=Path('C:/msys64/ucrt64/bin/g++.exe'))
    p.add_argument('--host', action='store_true')
    p.add_argument('--index32', action='store_true')
    p.add_argument('--host-source', type=Path, help='Alternate real-source host control fixture (requires --host)')
    a = p.parse_args()
    if a.host_source and not a.host:
        p.error('--host-source requires --host')
    print(build(a.fte.resolve(), a.out.resolve(), a.cc.resolve(), a.host, a.index32,
                a.host_source.resolve() if a.host_source else None))
