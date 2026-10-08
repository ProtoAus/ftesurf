#!/usr/bin/env python3
"""Buffered native replay diagnostic. Never instruments/deploys an owner tree.

Install seams in a NEW clean isolated engine worktree, build its private server,
then compare it against an independently clean server with one immutable input.
No live FPS/tick-rate equivalence or physical-ramp-exit acceptance is implied.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile

from offramp_contact_smoke import isolated
from stitched_rewind_smoke import once
from offramp_buffer import compare

ROOT = Path(__file__).resolve().parent.parent


def instrument(engine):
    isolated(engine)
    source = engine / 'engine/common/pm_source.c'
    server = engine / 'engine/server/sv_ccmds.c'
    # Validate all seams before touching any tracked file.
    edits = [
        (source, 'void PM_AddTouchedEnt (int num);',
         'void PM_AddTouchedEnt (int num);\n#include "offramp_buffer_native.inc"'),
        (source, '\t\tVectorMA (fixed_origin, time_left, pmove.velocity, end);',
         '\t\tVectorMA (fixed_origin, time_left, pmove.velocity, end);\n\t\tPMSrc_OfframpSweep(fixed_origin, end);'),
        (source, '\t\t\t\tpmove.rampcontact = 1;',
         '\t\t\t\tPMSrc_OfframpContact(&pm, bumpcount, stuck_on_ramp && has_valid_plane && fixramps);\n\t\t\t\tpmove.rampcontact = 1;'),
        (source, '\t\tPMSrc_Tick ();', '\t\tPMSrc_Tick ();\n\t\tPMSrc_OfframpTick();'),
        (source, 'void PMSrc_Init (void)\n{',
         'void PMSrc_Init (void)\n{\n\tCvar_Register(&offrampbuf_replay, "Private diagnostics");'),
        (server, '#include "quakedef.h"', '#include "quakedef.h"\n'
         'void PMSrc_OfframpBegin(int mode, qboolean exact);\n'
         'void PMSrc_OfframpRow(int row, int packet, int mt);\n'
         'void PMSrc_OfframpEnd(void);'),
        (server, '\t\tfor (mode = 0; mode < (verify ? 1 : 2); mode++)\t/* Patch 349: the verifier is the open loop */\n\t\t{',
         '\t\tfor (mode = 0; mode < (verify ? 1 : 2); mode++)\t/* Patch 349: the verifier is the open loop */\n\t\t{\n\t\t\tPMSrc_OfframpBegin(mode, exact);'),
        (server, '\t\t\t\tPM_PlayerMove(exact ? gamespeed : 1.0f);',
         '\t\t\t\tPMSrc_OfframpRow(i, r->pk, r->mt);\n\t\t\t\tPM_PlayerMove(exact ? gamespeed : 1.0f);'),
        (server, '\t\t}\n\n\t\tif (nrestart && verify)',
         '\t\t\tPMSrc_OfframpEnd();\n\t\t}\n\n\t\tif (nrestart && verify)'),
    ]
    for path, old, _ in edits:
        if path.read_text().count(old) != 1:
            raise RuntimeError(f'Expected one seam: {path}: {old[:75]!r}')
    target = engine / 'engine/common/offramp_buffer_native.inc'
    if target.exists():
        raise RuntimeError('Refusing to overwrite an existing native buffer include')
    shutil.copyfile(ROOT / 'tools/offramp_buffer_native.inc', target)
    for path in (source, server):
        text = path.read_text()
        for p, old, new in edits:
            if p == path:
                text = once(text, old, new)
        path.write_text(text)
    print('Private buffered replay seams installed:', engine)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(server, recording, output, content, progs, buffered, packets, port, timeout):
    rig = Path(tempfile.mkdtemp(prefix='offramp-buffer-', dir=output))
    gd = rig / 'ftesurf'
    junctions = []
    process = None
    try:
        shutil.copytree(ROOT / 'ftesurf/cfg', gd / 'cfg')
        (gd / 'cfg/test').mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / 'default.fmf', rig / 'default.fmf')
        for name in ('maps', 'models', 'particles', 'gfx'):
            source = content / 'ftesurf' / name
            target = gd / name
            if source.is_dir():
                subprocess.run(['cmd', '/c', 'mklink', '/J', str(target), str(source)],
                               check=True, capture_output=True)
                junctions.append(target)
        for name in ('qwprogs.dat', 'csprogs.dat', 'menu.dat', 'fs_addons.default.txt'):
            shutil.copyfile(progs / name, gd / name)
        target = gd / 'cfg/test/input.rec'
        shutil.copyfile(recording, target)
        # Use only the pinned map name, not any player/identity metadata.
        names = [line.split()[1:] for line in target.read_text().splitlines()
                 if line.startswith('map ')]
        if len(names) != 1 or len(names[0]) != 1:
            raise RuntimeError('Expected one map header')
        mapname = names[0][0]
        if not mapname or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in mapname):
            raise RuntimeError('Unsafe map header')
        bsp = content / 'ftesurf/maps' / (mapname + '.bsp')
        map_sha256 = sha(bsp)
        text = 'cfg_save_auto 0\n'
        if buffered is not None:
            text += f'pm_offramp_replay {int(buffered)}\n'
        text += f'pm_recsim cfg/test/input.rec {packets}\necho OFFRAMPBUF_COMPLETE\nquit\n'
        (gd / 'cfg/test/diagnostic.cfg').write_text(text)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(('127.0.0.1', port))
        # Native sv-rel does not contain the VBSP loader. Execute a LOCAL copy
        # beside the identical installed loader in every arm, never alter its source.
        executable = rig / 'fteqwsv64.exe'
        plugin = rig / 'fteplug_hl2_x64.dll'
        shutil.copyfile(server, executable)
        shutil.copyfile(content / plugin.name, plugin)
        command = [str(executable), '-basedir', str(rig), '-manifest', str(rig / 'default.fmf'),
                   '-homedir', str(rig / 'home'), '-port', str(port), '+sv_public', '0',
                   '+log_enable', '1', '+log_name', 'offramp_buffer',
                   '+cfg_save_auto', '0', '+plug_load', 'hl2', '+map', mapname,
                   '+exec', 'cfg/test/diagnostic.cfg']
        started = datetime.now(timezone.utc).isoformat()
        process = subprocess.Popen(command, cwd=content, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        process.wait(timeout=timeout)
        completed = datetime.now(timezone.utc).isoformat()
        logs = list(rig.rglob('offramp_buffer.log'))
        if len(logs) != 1:
            raise RuntimeError(f'Expected one retained server log; got {len(logs)}')
        result = {'rig': str(rig), 'log': str(logs[0]), 'exit_code': process.returncode,
                  'started_utc': started, 'completed_utc': completed,
                  'game_source_commit': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
                  'server_sha256': sha(executable), 'hl2_plugin_sha256': sha(plugin),
                  'recording_sha256': sha(target),
                  'map': mapname, 'map_sha256': map_sha256,
                  'progs': {name: sha(gd / name) for name in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')}}
        (rig / 'provenance.json').write_text(json.dumps(result, indent=2) + '\n')
        if process.returncode:
            raise RuntimeError('Server failed; inspect retained rig')
        if sha(bsp) != map_sha256:
            raise RuntimeError('Map changed during control')
        return result
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        for path in junctions:
            if not path.lstat().st_file_attributes & 0x400:
                raise RuntimeError(f'Refusing removal: not our junction: {path}')
            path.rmdir()
        print('Retained private rig:', rig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--instrument-native', type=Path)
    ap.add_argument('--server', type=Path)
    ap.add_argument('--control-server', type=Path)
    ap.add_argument('--recording', type=Path)
    ap.add_argument('--output-dir', type=Path)
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--progs', type=Path, default=ROOT / 'ftesurf')
    ap.add_argument('--packets', type=int, default=1000)
    ap.add_argument('--port', type=int, default=27618)
    ap.add_argument('--timeout', type=int, default=120)
    a = ap.parse_args()
    if a.instrument_native:
        instrument(a.instrument_native)
        return
    if not all((a.server, a.control_server, a.recording, a.output_dir)):
        ap.error('Need --server, --control-server, --recording and --output-dir')
    if not (ROOT / '.git').is_file():
        ap.error('Run diagnostics only from an isolated game worktree')
    if a.packets <= 10 or not (a.port == 27510 or 27520 <= a.port <= 27620) or a.timeout <= 0:
        ap.error('Use >10 packets, a lobby-range port and a positive timeout')
    if sha(a.server) == sha(a.control_server):
        ap.error('Control must be an independently clean, different server binary')
    a.output_dir.mkdir(parents=True, exist_ok=False)
    arms = {}
    for name, exe, capture in [('clean', a.control_server, None), ('off', a.server, False),
                               ('on', a.server, True), ('repeat', a.server, True)]:
        arms[name] = run(exe.resolve(), a.recording.resolve(), a.output_dir, a.content.resolve(),
                         a.progs.resolve(), capture, a.packets, a.port, a.timeout)
        (a.output_dir / 'arms.json').write_text(json.dumps(arms, indent=2) + '\n')
    identities = [(x['recording_sha256'], x['hl2_plugin_sha256'], x['map_sha256'], x['progs'])
                  for x in arms.values()]
    if any(x != identities[0] for x in identities):
        raise AssertionError('Input/map/plugin/progs changed between arms')
    if len({arms[n]['server_sha256'] for n in ('off', 'on', 'repeat')}) != 1:
        raise AssertionError('Subject binary changed between arms')
    result = compare(*(Path(arms[n]['log']).read_text(errors='replace')
                       for n in ('clean', 'off', 'on', 'repeat')))
    result['arms'] = arms
    (a.output_dir / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Buffered replay controls:', result['structural_gates'])
    print('Native ticks/contacts/airborne losses:', result['ticks'], result['contacts'], len(result['losses']))
    print('Physical-exit and live-stage acceptance: NOT_TESTED')


if __name__ == '__main__':
    main()
