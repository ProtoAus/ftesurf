#!/usr/bin/env python3
"""Acted late-metadata/refresh/restart test in runlines_smoke's owned overlay.

Requires an owned --output-dir, installed P688+ binaries and mounted surf_rookie.
No install metadata or profile is written. --csqc selects a compiled control.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
STATUS = re.compile(r'milk_skyinfo: map (\S+) page (-?\d+) cell (-?\d+) scanning ([01]) rows (\d+) maxbatch (\d+)')
MARKER = re.compile(r'(?m)^.*? (META-[A-Z-]+)\s*$')


def grade(text, published):
    states = {}
    phase = None
    for line in text.splitlines():
        marker = MARKER.fullmatch(line)
        if marker:
            phase = marker[1]
        match = STATUS.search(line)
        if match and phase:
            states.setdefault(phase, []).append((match[1], *map(int, match.groups()[1:])))
    assert set(published) == {'META-MISSING', 'META-REPLACE', 'META-CLEAR', 'META-INVALID', 'META-RESTART', 'META-OFF', 'META-AUTO', 'META-DELETE', 'META-RESTORE'}, 'writer phases did not all act'
    checks = {
        'META-MISSING': (-1, -1), 'META-RECOVERED': (5, 0),
        'META-REPLACED': (5, 1), 'META-CLEARED': (-1, -1),
        'META-INVALID-DONE': (-1, -1), 'META-RESTART-DONE': (5, 0),
        'META-OFF-DONE': (5, 0), 'META-ON-DONE': (5, 1), 'META-AUTO-DONE': (5, 0),
        'META-DELETED': (-1, -1), 'META-RESTORED': (5, 0),
    }
    for key, coords in checks.items():
        assert key in states, f'{key}: no subject state'
        state = states[key][-1]
        assert state[0] == 'surf_rookie', f'{key}: map changed: {state}'
        assert state[1:3] == coords and state[3] == 0, f'{key}: expected completed {coords}, got {state}'
    assert states['META-RECOVERED'][-1][4] == 2, 'blank line before late row was not read'
    assert states['META-RESTORED'][-1][4] == 2, 'blank line before restored row was not read'
    assert states['META-REPLACED'][-1][4] == 1025, 'long-table target not reached'
    assert states['META-OFF-DONE'][-1][4] == 0, 'inactive sky read/retained an open scan'
    assert states['META-ON-DONE'][-1][4] == 1025, 're-enabled sky did not restart interrupted scan'
    budget = states.get('META-BUDGET', [])
    assert budget and budget[-1][3] == 1, 'bounded scan did not remain in flight'
    assert budget[-1][4] > 0 and budget[-1][5] == 64, f'bounded scan did not act: {budget}'
    assert states['META-REPLACED'][-1][5] == 64, 'long-table batch exceeded 64 rows'
    assert 'RUNLINES COMPLETE' in text, 'client did not complete'
    return states


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--csqc', type=Path)
    ap.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    ap.add_argument('--server', type=Path, default=Path('C:/FTEQuake/fteqwsv64.exe'))
    ap.add_argument('--port', type=int, default=27619)
    a = ap.parse_args()
    out = a.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    empty = out / 'initial-mapmeta.txt'
    empty.write_text('// private initially empty metadata\n', encoding='utf-8')
    before = set(out.glob('ftesurf-runlines-*'))
    command = [sys.executable, str(ROOT / 'tools/runlines_smoke.py'),
               'ftesurf/cfg/test/soundsky_metadata.cfg', '--content', 'C:/FTESurf',
               '--output-dir', str(out), '--client', str(a.client), '--server', str(a.server),
               '--dedicated', '--map', 'surf_rookie', '--mount', '--port', str(a.port),
               '--put', f'data/mapmeta.txt={empty}']
    if a.csqc:
        command += ['--csqc', str(a.csqc)]
    row = lambda cell: f'meta surf_rookie - - - - 5 {cell} - -\n'
    replacements = {
        'META-MISSING': '\n' + row(0),
        'META-REPLACE': ''.join(f'meta unused_{i} - - - - - - - -\n' for i in range(1024)) + row(1),
        'META-CLEAR': '// no matching row\n',
        'META-INVALID': 'meta surf_rookie - - - - nonsense 0 - -\n',
        'META-RESTART': row(0),
        'META-OFF': ''.join(f'meta unused_{i} - - - - - - - -\n' for i in range(1024)) + row(1),
        'META-AUTO': row(0),
        'META-DELETE': None,
        'META-RESTORE': '\n' + row(0),
    }
    published = {}
    rig = None
    started = time.monotonic()
    with (out / 'driver.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        try:
            while process.poll() is None:
                if time.monotonic() - started > 160:
                    raise TimeoutError('retained metadata arm exceeded 160 seconds')
                rigs = set(out.glob('ftesurf-runlines-*')) - before
                if len(rigs) == 1:
                    rig = rigs.pop()
                    client_log = rig / 'ftesurf/logs/runlines_smoke.log'
                    text = client_log.read_text(errors='replace') if client_log.exists() else ''
                    seen = set(MARKER.findall(text))
                    for marker, content in replacements.items():
                        if marker not in seen or marker in published:
                            continue
                        target = rig / 'ftesurf/data/mapmeta.txt'
                        assert target.exists() or 'META-DELETE' in published, 'initial private fixture vanished'
                        if target.exists():
                            assert target.is_file() and not target.is_symlink()
                            assert not getattr(target.lstat(), 'st_file_attributes', 0) & 0x400, 'private metadata is a link'
                        for parent in (target.parent, target.parent.parent):
                            assert not getattr(parent.lstat(), 'st_file_attributes', 0) & 0x400, 'private metadata parent is a link'
                        if content is None:
                            target.unlink()  # Only the fixture this test created, not install data.
                            digest = None
                        else:
                            stage = target.with_suffix('.new')
                            stage.write_text(content, encoding='utf-8')
                            stage.replace(target)
                            digest = hashlib.sha256(target.read_bytes()).hexdigest()
                        published[marker] = {'sha256': digest, 'elapsed': time.monotonic() - started}
                time.sleep(0.05)
            assert process.returncode == 0, f'runlines failed: {out / "driver.log"}'
            assert rig is not None, 'no unique private rig'
            text = (rig / 'ftesurf/logs/runlines_smoke.log').read_text(errors='replace')
            states = grade(text, published)
            shots = list((rig / 'ftesurf/screenshots').glob('meta_*'))
            assert len(shots) >= 5, 'pixel captures did not act'
            result = {'verdict': 'PASS', 'rig': str(rig), 'states': states, 'published': published,
                      'csqc_sha256': hashlib.sha256((rig / 'ftesurf/csprogs.dat').read_bytes()).hexdigest(),
                      'screenshots': [str(p) for p in shots]}
            (out / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            print(json.dumps(result, indent=2))
        finally:
            if process.poll() is None:
                # Only our retained runlines driver. Its finally owns client/server cleanup.
                # Allow the driver's bounded client timeout to execute rather than orphan it.
                process.wait(timeout=170)


if __name__ == '__main__':
    main()
