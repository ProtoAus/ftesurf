#!/usr/bin/env python3
"""Run a cfg in a private, retained content overlay; never use install player data.

python tools/runlines_smoke.py ftesurf/cfg/test/runlines_ui.cfg \
    --content C:/FTESurf --output-dir C:/FTESurf-private/checkpoints
Progs/configs and shader overrides come from this checkout. Other content is
read through junctions; only junctions we created are removed, never targets.
"""
import argparse
import hashlib
import pathlib
import shlex
import shutil
import socket
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTENT_DIRS = ('maps', 'gfx', 'glsl', 'models', 'particles', 'scripts')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('cfg', type=pathlib.Path)
    ap.add_argument('--content', type=pathlib.Path, default=pathlib.Path('C:/FTESurf'))
    ap.add_argument('--client', type=pathlib.Path, help='Explicit installed client for compatibility controls')
    ap.add_argument('--output-dir', type=pathlib.Path)
    ap.add_argument('--recording', type=pathlib.Path,
                    help='copy a control recording into the overlay, never alter its source')
    ap.add_argument('--also', action='append', default=[], metavar='NAME=PATH',
                    help='another recording, copied to cfg/test/NAME in the overlay')
    ap.add_argument('--put', action='append', default=[], metavar='REL=PATH',
                    help='a file copied to REL under the overlay\'s game directory, e.g. '
                         'data/runs/<map>/main/0004000_run.rec: a Local board row')
    ap.add_argument('--mount', action='store_true',
                    help='mount the default list of other games (fs_addons.default.txt), so a map that '
                         'lives in one of them loads; an overlay has no fs_addons.txt of its own')
    ap.add_argument('--port', type=int, default=27619)
    ap.add_argument('--dedicated', action='store_true')
    ap.add_argument('--map', default='surf_dune', help='with --dedicated: the map the server starts')
    ap.add_argument('--server-arg', action='append', default=[],
                    help='with --dedicated: extra server arguments, e.g. "+set sv_minping 120"')
    ap.add_argument('--timeout', type=int, default=150)
    a = ap.parse_args()
    rig = pathlib.Path(tempfile.mkdtemp(prefix='ftesurf-runlines-', dir=a.output_dir))
    gd = rig / 'ftesurf'
    gd.mkdir()
    junctions = []
    server = client = None
    try:
        shutil.copyfile(ROOT / 'default.fmf', rig / 'default.fmf')
        for name in CONTENT_DIRS:
            source = a.content / 'ftesurf' / name
            target = gd / name
            if name in ('glsl', 'scripts'):
                # Writable local overlays: never override a shared content junction.
                if source.is_dir():
                    shutil.copytree(source, target)
                overrides = ROOT / 'ftesurf' / name
                if overrides.is_dir():
                    shutil.copytree(overrides, target, dirs_exist_ok=True)
            elif source.is_dir():
                subprocess.run(['cmd', '/c', 'mklink', '/J', str(target), str(source)],
                               check=True, capture_output=True)
                junctions.append(target)
        for name in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
            shutil.copyfile(ROOT / 'ftesurf' / name, gd / name)
            print(name, hashlib.sha256((gd / name).read_bytes()).hexdigest())
        shutil.copyfile(ROOT / 'ftesurf/fs_addons.default.txt', gd / 'fs_addons.default.txt')
        if a.mount:
            shutil.copyfile(ROOT / 'ftesurf/fs_addons.default.txt', gd / 'fs_addons.txt')
        paths = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files',
                                         'ftesurf/cfg'], text=True).splitlines()
        for rel in paths:
            source = ROOT / rel
            target = rig / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        if a.recording:
            target = gd / 'cfg/test/runlines_sample.rec'
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(a.recording, target)
        for pair in a.also:
            name, _, source = pair.partition('=')
            if not source or pathlib.PurePath(name).name != name:
                raise ValueError('--also wants NAME=PATH, NAME a bare file name: %s' % pair)
            target = gd / 'cfg/test' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        for pair in a.put:
            # ONLY under the overlay's own data/, spelled exactly.  The content folders
            # beside it are JUNCTIONS into the install, and Windows finds a folder under
            # any case, a trailing dot or its short name: `Maps/x`, `maps./x` and
            # `PARTIC~1/x` all wrote through one into the install's copy (the review of
            # Patch 635, on a fake install).  So a list of names to refuse is not a guard:
            # one name is allowed, and no component on the way may be a link.
            rel, _, source = pair.partition('=')
            parts = pathlib.PurePosixPath(rel).parts
            if (not source or len(parts) < 2 or parts[0] != 'data'
                    or any(p in ('.', '..') or p != p.strip(' .') or set(p) & set(':\\~*?"<>|')
                           for p in parts)):
                raise ValueError('--put wants REL=PATH with REL under data/ in the game '
                                 'directory, plain names only: %s' % pair)
            walk = gd
            for part in parts[:-1]:
                walk = walk / part
                if walk.exists() and (walk.is_symlink() or walk.lstat().st_file_attributes & 0x400):
                    raise ValueError('--put: %s is a link, not a folder of this overlay' % walk)
            target = gd.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_dir():
                raise ValueError('--put: %s is a directory' % target)
            shutil.copyfile(source, target)
        cfg = a.cfg if a.cfg.is_absolute() else ROOT / a.cfg
        target = gd / 'cfg/test/runlines_smoke.cfg'
        target.parent.mkdir(parents=True, exist_ok=True)
        text = cfg.read_text(encoding='utf-8')
        if a.dedicated:
            if not 27520 <= a.port <= 27620:
                raise ValueError('Use a dedicated lobby-range port')
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.bind(('127.0.0.1', a.port))
            if f'map {a.map}\n' not in text:
                raise ValueError(f'cfg has no "map {a.map}" line to turn into a connect')
            text = text.replace(f'map {a.map}\n', f'connect 127.0.0.1:{a.port}\n')
        target.write_text(text, encoding='utf-8')
        (gd / 'downloads/csprogsvers').mkdir(parents=True)
        subprocess.run(['python', str(ROOT / 'tools/seed_csprogs.py'), str(gd / 'csprogs.dat')],
                       check=True, capture_output=True)
        common = ['-basedir', str(rig), '-manifest', str(rig / 'default.fmf')]
        if a.dedicated:
            extra = [word for arg in a.server_arg for word in shlex.split(arg)]
            server = subprocess.Popen(['C:/FTEQuake/fteqwsv64.exe', *common, '+sv_public', '0',
                                       '-port', str(a.port), '+log_enable', '1', '+log_name',
                                       'runlines_server', *extra, '+map', a.map], cwd=a.content,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        executable = a.client or a.content / 'ftesurf64.exe'
        client = subprocess.Popen([str(executable), *common, '-window',
                                   '+exec', 'cfg/test/runlines_smoke.cfg'], cwd=a.content,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        client.wait(timeout=a.timeout)
        log = gd / 'logs/runlines_smoke.log'
        if not log.is_file():
            raise RuntimeError('No client log: control did not act')
        text = log.read_text(errors='replace')
        if 'FTESurf CSQC loaded' not in text or 'RUNLINES COMPLETE' not in text:
            raise RuntimeError('Client did not complete the control')
        bad = ('Unknown command', 'QC VM error', 'Cannot call', 'stack overflow')
        if any(word in text for word in bad):
            raise RuntimeError('Runtime errors in retained log')
        print('Runtime completed without command/VM errors; inspect controls and screenshots.')
        return 0
    finally:
        for process in (client, server):
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
        for path in junctions:
            if not path.lstat().st_file_attributes & 0x400:
                raise RuntimeError(f'Refusing removal: not our junction: {path}')
            path.rmdir()
        print('Retained private rig:', rig)


if __name__ == '__main__':
    raise SystemExit(main())
