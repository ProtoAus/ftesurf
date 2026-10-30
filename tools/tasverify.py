#!/usr/bin/env python3
"""Bounded authoritative TAS replay (Pi only), not a human-run verifier.

The operator supplies a TRUSTED runtime manifest, never the uploader. A job freezes
one canonical legal-start .tasp and runs pinned real dedicated/client engines in a
fresh private gamedir. Only a native natural finish with matching run inputs may
PASS. Editor checkpoints are comparisons, never placements or finish authority.
No account/API credentials, POSTs, human-board writes, migrations or live services.

  tasverify.py runtime --fixture DIR --server EXE --client EXE --plugin SO \
      --map MAP --gamemode surf --output runtime.json
  tasverify.py run --runtime runtime.json --project FILE --out OWNED_ROOT/job --port 27616

The manifest and native paths belong to the trusted operator/worker. This does not
protect against a hostile OS or same-UID writer. Queue promotion must additionally
bind the manifest to the currently approved board rules; a CLI receipt alone is not
a board admission. No submitted .rec, claimed time or supplied state can be a PASS.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import signal
import socket
import stat
import subprocess
import sys
import time

import reccheck
import tasrev

MAX_PROJECT = 4700 * 1024
MAX_REC = 32 * 1024 * 1024
MAX_LOG = 64 * 1024 * 1024
MAX_ASSET = 512 * 1024 * 1024
MAX_ASSETS = 2 * 1024 * 1024 * 1024
MAX_DYNAMIC = 256 * 1024 * 1024
MAX_FILES = 8192
WORLD_WARPS = {b'tele', b'telerel', b'bhop', b'speed', b'push', b'lift', b'catapult', b'reverse'}
TICK = Decimal('0.015')
TF_TAS = 1 << 22
SAFE_MAP = re.compile(r'[A-Za-z0-9_+.-]{1,64}\Z')
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
PLUGIN_POLICY_ACK = b'Plugin search: binary-directory only'
_cancelled = False


class Held(Exception):
    """Cannot prove a finish; retryable, never player guilt."""


class Refused(Exception):
    """The submitted bytes are not an admissible legal-start project."""


def check_cancel():
    if _cancelled:
        raise Held('CANCELLED')


def require_plugin_policy(peer):
    if PLUGIN_POLICY_ACK not in bounded(peer.base / 'console.log', MAX_LOG):
        raise Held('PLUGIN_SEARCH_POLICY')


def bounded(path, cap):
    with Path(path).open('rb') as f:
        data = f.read(cap + 1)
    if len(data) > cap:
        raise Held('SIZE_LIMIT')
    return data


def digest(data):
    return hashlib.sha256(data).hexdigest()


def filehash(path):
    h = hashlib.sha256()
    n = 0
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            n += len(block)
            if n > MAX_ASSET:
                raise Held('ASSET_SIZE_LIMIT')
            h.update(block)
    return h.hexdigest()


def unique_header(data, key):
    prefix = key.encode() + b' '
    rows = [line[len(prefix):].decode('ascii') for line in data.splitlines() if line.startswith(prefix)]
    if len(rows) != 1:
        raise Held('HEADER_' + key.upper())
    return rows[0]


def admit(data):
    if len(data) > MAX_PROJECT:
        raise Refused('PROJECT_SIZE')
    try:
        p = tasrev.parse(data)
    except (tasrev.Refused, ValueError, OverflowError) as error:
        raise Refused('PROJECT_GRAMMAR') from error
    if p['h'] != p['stated']:
        raise Refused('REVISION_HASH')
    if p['version'] != '3':
        raise Refused('LEGAL_START_REQUIRED')
    mp = unique_header(data, 'map')
    if not SAFE_MAP.fullmatch(mp) or mp in ('.', '..'):
        raise Refused('MAP_NAME')
    if not p['startat'] or p['startat'] >= len(p['rows']):
        raise Held('NO_RUN_INPUTS')
    if any(max(abs(x) for x in row[:3]) > 450 for row in p['rows']):
        raise Refused('MOVE_RANGE')
    return p


def wire_angle(token):
    """The writer prints degrees to four decimals; a short step is ~0.00549 deg.

    Reject non-wire-shaped values, not just arbitrary rounding into a valid short.
    Decimal avoids accepting non-finite/overflow tokens or a platform rounding tie.
    """
    try:
        value = Decimal(token)
        if not value.is_finite() or abs(value) > 360:
            raise Held('INPUT_ANGLE')
        word = int((value * 65536 / 360).to_integral_value())
        if abs(value - Decimal(word) * 360 / 65536) > Decimal('0.000051'):
            raise Held('INPUT_ANGLE_PRECISION')
        return ((word + 32768) % 65536) - 32768
    except InvalidOperation as error:
        raise Held('INPUT_ANGLE') from error


def compare_inputs(project, rec):
    rows = project['rows']
    start = project['startat']
    count = 0
    previous = first = None
    for line in rec.splitlines():
        if not line.startswith(b'in '):
            continue
        w = line.decode('ascii').split()
        if len(w) != 12:
            raise Held('INPUT_SHAPE')
        mt = int(w[2])  # column 1 is packet ordinal, NOT the mover tick
        if previous is not None and mt != previous + 1:
            raise Held('INPUT_CLOCK')
        if first is None:
            first = mt
        previous = mt
        actual = tuple(int(x) for x in w[4:7]) + tuple(wire_angle(x) for x in w[7:10]) + (int(w[10]),)
        if start + count >= len(rows) or actual != rows[start + count]:
            raise Held('INPUT_MISMATCH')
        count += 1
    if not count:
        raise Held('MISSING_INPUTS')
    horizon = unique_header(rec, 'instart').split()
    end = unique_header(rec, 'inend').split()
    if len(horizon) != 2 or len(end) != 2 or int(horizon[0]) != first or int(horizon[1]) != first or int(end[0]) != previous + 1:
        raise Held('INPUT_HORIZON')
    return count


def assess(project_bytes, rec_bytes, rec_path):
    """Grade ONLY a fresh native recording captured by run(), never an upload API.

    Kept separate for unit controls; passing attacker-provided recordings here is
    outside its authority boundary and is not a trusted replay/board receipt.
    """
    p = admit(project_bytes)
    if len(rec_bytes) > MAX_REC:
        raise Held('RECORDING_SIZE')
    r = reccheck.check_rec(str(rec_path), data=rec_bytes)
    if r.faults or not r.finish_ticks or r.finish_ticks <= 0:
        raise Held('RECORDING_INVALID_OR_UNFINISHED')
    for key in ('map', 'mapcrc', 'zonecrc', 'pmpin'):
        if unique_header(rec_bytes, key) != unique_header(project_bytes, key):
            raise Held('PIN_' + key.upper())
    if Decimal(unique_header(rec_bytes, 'tickrate')) != TICK:
        raise Held('TICKRATE')
    if any(Decimal(x) for x in unique_header(rec_bytes, 'startjit').split()):
        raise Held('START_JITTER')
    if not int(unique_header(rec_bytes, 'flags')) & TF_TAS:
        raise Held('MISSING_TAS_ANCESTRY')
    if any(line.startswith((b'resume ', b'retry ', b'session ', b'pause ', b'ghost '))
           for line in rec_bytes.splitlines()):
        raise Held('RESTORED_OR_HELD_CONTEXT')
    # Real map teleports belong to the simulated world. Save/spec/restore warps do not.
    if any(line.startswith(b'warp ') and (len(line.split()) < 5 or line.split()[4] not in WORLD_WARPS)
           for line in rec_bytes.splitlines()):
        raise Held('NON_WORLD_WARP')
    count = compare_inputs(p, rec_bytes)
    if count != r.finish_ticks:
        raise Held('CLOCK_INPUT_COUNT')
    track = unique_header(rec_bytes, 'track')
    leg = unique_header(rec_bytes, 'leg')
    return {'ticks': r.finish_ticks, 'finish': True, 'run_input_rows': count,
            'legal_finish_row': p['startat'] + count,
            'unused_tail_rows': len(p['rows']) - p['startat'] - count,
            'map': unique_header(project_bytes, 'map'), 'track': track, 'leg': leg,
            'project_sha256': digest(project_bytes), 'revision': p['h'],
            'recording_sha256': digest(rec_bytes), 'recording_bytes': len(rec_bytes),
            'consumed_rows': [p['startat'] + 1, p['startat'] + count]}


def runtime_manifest(fixture, server, client, plugin, mp, gamemode):
    """Operator-only admission of a minimal trusted runtime, not a submitted file."""
    if not SAFE_MAP.fullmatch(mp) or mp in ('.', '..') or gamemode not in ('surf', 'bhop'):
        raise ValueError('map/gamemode')
    fixture = Path(fixture).resolve()
    game = fixture / 'sv/ftesurf'
    assets = {}
    selected = [game / p for p in ('qwprogs.dat', 'csprogs.dat', 'menu.dat', 'cfg/default.cfg',
                                   'maps/' + mp + '.bsp', 'maps/zones/local/' + mp + '.json')]
    case_roots = [game / folder for folder in
                  ('glsl', 'models', 'gfx', 'particles', 'scripts', 'downloads/csprogsvers')]
    for folder in case_roots:
        selected += sorted(p for p in folder.rglob('*') if p.is_file())
    optional = ['cfg/maps/map_' + mp + '.cfg', 'cfg/maps/entfix_' + mp + '.cfg',
                'cfg/lobby/mode_' + gamemode + '.cfg', 'data/mapmeta.txt',
                'data/maps/zones/local/' + mp + '.json', 'maps/zones/curated/' + mp + '.json',
                'maps/zones/online/' + mp + '.json']
    absent = []
    for rel in optional:
        path = game / rel
        if path.exists():
            selected.append(path)
        else:
            absent.append(str(path))
    for path in sorted((game / 'maps').iterdir()):
        if path.is_file() and path.name.casefold().startswith(mp.casefold() + '.'):
            if not path.name.startswith(mp + '.') or path.suffix != path.suffix.lower():
                raise Held('DEPENDENCY_CASE_ALIAS')
            selected.append(path)
    # Native SV_LoadRulesetFile reads these exact layers. Never omit a present
    # mode/map override and silently verify against the fallback 15 ms profile.
    for rel in ('cfg/default.cfg', 'cfg/lobby/mode_' + gamemode + '.cfg', 'cfg/maps/map_' + mp + '.cfg'):
        path = game / rel
        if not path.exists():
            continue
        for line in bounded(path, 65536).decode('ascii').splitlines():
            match = re.match(r'\s*(?:set\s+)?pm_ticrate\s+"?([0-9.]+)', line)
            if match and Decimal(match[1]) != TICK:
                raise Held('UNSUPPORTED_TAS_TICKRATE')
    # Source's model physics lookup is beside every selected .mdl, not beside the BSP.
    for mdl in (game / 'models').rglob('*'):
        if mdl.is_file() and mdl.suffix.casefold() == '.mdl':
            if not mdl.with_suffix('.phy').exists():
                absent.append(str(mdl.with_suffix('.phy')))
    for suffix in ('.phy', '.ent', '.edo', '.entities', '.lit', '.vis', '.rtlights'):
        path = game / 'maps' / (mp + suffix)
        if not path.exists():
            absent.append(str(path))
    reject_case_aliases(case_roots + selected + [Path(p) for p in absent])
    for p in selected:
        if not p.is_file() or p.is_symlink() or not p.resolve().is_relative_to(game):
            raise ValueError('missing or linked fixture asset: ' + str(p))
        assets['ftesurf/' + p.relative_to(game).as_posix()] = {'path': str(p), 'sha256': filehash(p)}
    native = {}
    for name, path in [('server', server), ('client', client), ('plugin', plugin)]:
        p = Path(path).resolve()
        if not p.is_file():
            raise ValueError('missing native: ' + str(p))
        native[name] = {'path': str(p), 'sha256': filehash(p)}
    return {'format': 1, 'map': mp, 'gamemode': gamemode, 'tickrate': str(TICK),
            'mount_policy': 'exclusive-vfs-1', 'absent_dependencies': absent,
            'case_roots': [str(p) for p in case_roots], 'native': native, 'assets': assets}


def reject_case_aliases(paths):
    # Native VFS lookup ignores case. Reject aliases/collisions rather than
    # approving a different dependency set, including aliases in parent dirs.
    siblings = {}
    for path in paths:
        path = Path(path)
        while path.parent != path:
            parent = path.parent
            if parent not in siblings:
                try:
                    names = [p.name for p in parent.iterdir()]
                except FileNotFoundError:
                    names = []
                siblings[parent] = {}
                for name in names:
                    siblings[parent].setdefault(name.casefold(), []).append(name)
            if any(name != path.name for name in siblings[parent].get(path.name.casefold(), ())):
                raise Held('DEPENDENCY_CASE_ALIAS')
            path = parent


def validate_runtime(r, mp):
    if (r.get('format') != 1 or r.get('map') != mp or r.get('gamemode') not in ('surf', 'bhop') or
            r.get('tickrate') != str(TICK) or r.get('mount_policy') != 'exclusive-vfs-1' or
            not isinstance(r.get('case_roots'), list)):
        raise Held('RUNTIME_PROFILE')
    reject_case_aliases(r['case_roots'] + [item['path'] for item in r['assets'].values()] + r['absent_dependencies'])
    if any(Path(p).exists() for p in r['absent_dependencies']):
        raise Held('DEPENDENCY_APPEARED')
    for item in list(r['native'].values()) + list(r['assets'].values()):
        if not HEX64.fullmatch(item['sha256']) or filehash(item['path']) != item['sha256']:
            raise Held('RUNTIME_HASH')
    if set(r['native']) != {'server', 'client', 'plugin'}:
        raise Held('RUNTIME_NATIVE')
    for dest in r['assets']:
        p = PurePosixPath(dest)
        if p.is_absolute() or '..' in p.parts or not dest.startswith('ftesurf/') or '\\' in dest or ':' in dest:
            raise Held('RUNTIME_PATH')
        tail = dest[len('ftesurf/'):]
        allowed = (tail in ('qwprogs.dat', 'csprogs.dat', 'menu.dat', 'cfg/default.cfg',
                           'cfg/maps/map_' + mp + '.cfg', 'cfg/maps/entfix_' + mp + '.cfg',
                           'cfg/lobby/mode_' + r['gamemode'] + '.cfg', 'data/mapmeta.txt',
                           'data/maps/zones/local/' + mp + '.json', 'maps/zones/local/' + mp + '.json',
                           'maps/zones/curated/' + mp + '.json', 'maps/zones/online/' + mp + '.json') or
                   any(tail.startswith(x + '/') for x in ('glsl', 'models', 'gfx', 'particles', 'scripts', 'downloads/csprogsvers')) or
                   (tail.startswith('maps/' + mp + '.') and '/' not in tail[len('maps/'):]))
        if not allowed:
            raise Held('RUNTIME_SHADOW_PATH')
    required = {'ftesurf/' + p for p in ('qwprogs.dat', 'csprogs.dat', 'menu.dat', 'cfg/default.cfg',
                                       'maps/' + mp + '.bsp', 'maps/zones/local/' + mp + '.json')}
    if not required.issubset(r['assets']):
        raise Held('RUNTIME_ASSETS')
    return r


def copy_checked(source, target, wanted):
    target.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    h = hashlib.sha256()
    with Path(source).open('rb') as src, target.open('xb') as dst:
        for block in iter(lambda: src.read(1024 * 1024), b''):
            total += len(block)
            if total > MAX_ASSET:
                raise Held('ASSET_SIZE_LIMIT')
            h.update(block)
            dst.write(block)
    if h.hexdigest() != wanted:
        raise Held('ASSET_CHANGED')
    target.chmod(0o444)
    return total


def plugin_image(peer, wanted):
    """Bind the actual Linux mapped HL2 image, not merely a nominated .so copy."""
    modules = {}
    maps = bounded(Path('/proc') / str(peer.proc.pid) / 'maps', 2 * 1024 * 1024)
    for line in maps.decode('ascii').splitlines():
        w = line.split(None, 5)
        if len(w) != 6:
            continue
        name = re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), w[5])
        if not Path(name.removesuffix(' (deleted)')).name.startswith('fteplug_hl2'):
            continue
        if name.endswith(' (deleted)'):
            raise Held('PLUGIN_DELETED')
        path = Path(name)
        st = path.stat()
        dev = tuple(int(x, 16) for x in w[3].split(':'))
        if dev != (os.major(st.st_dev), os.minor(st.st_dev)) or int(w[4]) != st.st_ino:
            raise Held('PLUGIN_INODE')
        if filehash(path) != wanted:
            raise Held('PLUGIN_IMAGE')
        modules[(st.st_dev, st.st_ino)] = path
    if len(modules) != 1:
        raise Held('UNIQUE_PLUGIN_IMAGE_REQUIRED')
    (device, inode), path = next(iter(modules.items()))
    return {'sha256': wanted, 'device_inode': [device, inode], 'name': path.name}


def native_limits():
    # Import before fork. The child callback performs only resource/syscall setup.
    import resource
    def apply():
        os.nice(19)
        for kind, cap in ((resource.RLIMIT_FSIZE, MAX_LOG), (resource.RLIMIT_CORE, 0),
                          (resource.RLIMIT_AS, 768 * 1024 * 1024)):
            _, hard = resource.getrlimit(kind)
            if hard != resource.RLIM_INFINITY:
                cap = min(cap, hard)
            resource.setrlimit(kind, (cap, cap))
    return apply


class Peer:
    def __init__(self, exe, base, server, watch=None):
        import pty
        self.base = base
        self.log = base / 'ftesurf/logs/tasverify.log'
        self.log.parent.mkdir(parents=True, exist_ok=True)
        self.offset = 0
        self.window = b''
        self.window_start = 0
        self.stopped = False
        self.proc = None
        self.master = self.console = None
        self.watch = watch if watch is not None else []
        self.last_inventory = 0.0
        self.static = {p: p.stat().st_size for p in base.rglob('*') if p.is_file()}
        self.master, slave = pty.openpty()
        # Linux's default QC address-space reservation is 2 GiB per VM. Select
        # bounded VM arenas before loading; never relax the child's hard AS cap.
        args = [exe, '-basedir', str(base), '-manifest', str(base / 'default.fmf'),
                '-nohome', '-pluginrootonly', '-ip', '127.0.0.1', '+set', 'pr_ssqc_memsize', '128m',
                '+set', 'pr_csqc_memsize', '128m', '+set', 'pr_menu_memsize', '64m']
        if not server:
            args += ['+set', 'vid_renderer', 'headless', '-nosound']
        args += ['+exec', 'verify.cfg']
        try:
            self.console = (base / 'console.log').open('xb')
            self.proc = subprocess.Popen(args, stdin=slave, stdout=self.console, stderr=subprocess.STDOUT,
                                         cwd=base, start_new_session=True, preexec_fn=native_limits())
            # Register immediately: even a later identity-read/cleanup failure is owned.
            self.watch.append(self)
            st = Path('/proc/' + str(self.proc.pid) + '/exe').stat()
            self.image_identity = [st.st_dev, st.st_ino]
            source = Path(exe).stat()
            if (st.st_dev, st.st_ino) != (source.st_dev, source.st_ino):
                raise Held('EXECUTABLE_INODE')
        except BaseException:
            self.stop()
            raise
        finally:
            os.close(slave)

    def guard(self):
        check_cancel()
        # Check both sinks for BOTH peers while either one is awaited. RLIMIT_FSIZE
        # additionally bounds producer bursts, including uncaptured native stderr.
        for path in (self.log, self.base / 'console.log'):
            if path.exists() and (not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size >= MAX_LOG):
                raise Held('LOG_OUTPUT_LIMIT')
        now = time.monotonic()
        if now - self.last_inventory >= .25:
            self.last_inventory = now
            total = count = 0
            for root, dirs, files in os.walk(self.base, followlinks=False):
                if any((Path(root) / d).is_symlink() for d in dirs):
                    raise Held('JOB_SYMLINK')
                for name in files:
                    path = Path(root) / name
                    st = path.lstat()
                    count += 1
                    if count > MAX_FILES or not stat.S_ISREG(st.st_mode):
                        raise Held('JOB_FILE_LIMIT')
                    if path in self.static and st.st_size != self.static[path]:
                        raise Held('JOB_STATIC_CHANGED')
                    if path not in self.static:
                        total += st.st_size
                        if st.st_size >= MAX_LOG or total >= MAX_DYNAMIC:
                            raise Held('JOB_OUTPUT_LIMIT')
        if self.proc is not None and self.proc.poll() is not None:
            raise Held('ENGINE_EXIT')

    def scan(self):
        self.guard()
        if self.log.exists():
            size = self.log.stat().st_size
            if size < self.offset or size > MAX_LOG:
                raise Held('LOG_TRUNCATED_OR_LIMIT')
            with self.log.open('rb') as f:
                f.seek(self.offset)
                added = f.read(size - self.offset)
            if len(added) != size - self.offset:
                raise Held('LOG_TRUNCATED')
            self.window += added
            self.offset += len(added)
            if len(self.window) > 256 * 1024:
                self.window = self.window[-256 * 1024:]
            self.window_start = self.offset - len(self.window)
        return self.offset

    def send(self, command):
        os.write(self.master, (command + '\n').encode('ascii'))

    def wait(self, pattern, deadline, after=0):
        rx = re.compile(pattern)
        while time.monotonic() < deadline:
            for peer in self.watch:
                if peer is not self:
                    peer.guard()
            self.scan()
            m = rx.search(self.window, max(0, after - self.window_start))
            if m:
                if time.monotonic() >= deadline:
                    raise Held('TIME_LIMIT')
                return m
            time.sleep(.05)
        raise Held('TIME_LIMIT')

    def stop(self):
        if self.stopped:
            return
        try:
            if self.proc is not None and self.proc.poll() is None:
                if self.master is None:
                    self.proc.terminate()
                else:
                    try:
                        self.send('quit')
                    except OSError:
                        self.proc.terminate()
                try:
                    self.proc.wait(5)
                except subprocess.TimeoutExpired:
                    self.proc.terminate()
                    try:
                        self.proc.wait(5)
                    except subprocess.TimeoutExpired:
                        self.proc.kill()
                        self.proc.wait(5)
        finally:
            master, self.master = self.master, None
            console, self.console = self.console, None
            try:
                if master is not None:
                    os.close(master)
            finally:
                try:
                    if console is not None:
                        console.close()
                finally:
                    self.stopped = self.proc is None or self.proc.poll() is not None


def prepare(out, runtime, project, token, port, copied):
    total = 0
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs',
              'log_name tasverify', 'log_readable 1', 'set cl_idlefps 0', 'set cl_maxfps 100',
              'set cl_netfps 100', 'set cl_threadedphysics 0', 'set run_resume 0', 'set lobby_dir ""',
              'set lobby_master ""', 'set lobby_enable 0', 'set cl_run_upload 0',
              'set cl_board_url ""', 'sv_public 0', 'sensitivity 0', 'set m_accel 0',
              'cl_forwardspeed 70', 'cl_sidespeed 70', 'plug_load hl2']
    for side in ('sv', 'cl'):
        base = out / side
        base.mkdir()
        (base / 'default.fmf').write_text('FTEMANIFEST 1\nGAME FTESurfTASVerify\nBASEGAME ftesurf\n'
                                        'DISABLEHOMEDIR 1\nMAINCONFIG verify-unused\n')
        for dest, source in runtime['assets'].items():
            target = base / dest
            total += copy_checked(source['path'], target, source['sha256'])
            copied.append((target, source['sha256']))
            if total > MAX_ASSETS:
                raise Held('RUNTIME_SIZE_LIMIT')
        for kind in ('plugin', 'server' if side == 'sv' else 'client'):
            native = runtime['native'][kind]
            target = base / Path(native['path']).name
            total += copy_checked(native['path'], target, native['sha256'])
            if total > MAX_ASSETS:
                raise Held('RUNTIME_SIZE_LIMIT')
            if kind != 'plugin':
                target.chmod(0o555)
            copied.append((target, native['sha256']))
        cfg = list(common)
        if side == 'sv':
            cfg += ['sv_port ' + str(port), 'sv_playerslots 2', 'sv_maxclients 2', 'sv_demoAutoRecord 0',
                    'developer 1', 'log_developer 1', 'pm_physicsmode 1', 'pm_ticrate 0.015',
                    'sv_tickparts 1', 'set sv_gamemode ' + runtime['gamemode'], 'set rec_stream 0',
                    'map ' + runtime['map']]
        else:
            cfg += ['set cl_hid 0', 'set vid_headless_sleep 0', 'name TASVerifier', 'connect 127.0.0.1:' + str(port)]
        (base / 'ftesurf/verify.cfg').write_text('\n'.join(cfg) + '\n')
        data = base / 'ftesurf/data'
        data.mkdir(exist_ok=True)
        (data / 'consent.txt').write_text('version 4\n')
    path = out / 'sv/ftesurf/data/tasproj' / runtime['map'] / (token + '.tasp')
    path.parent.mkdir(parents=True)
    path.write_bytes(project)
    path.chmod(0o400)
    return path


def run(runtime_path, project_path, out, port):
    """A local worker invocation, not a public HTTP handler. Result is one receipt."""
    if sys.platform != 'linux' or os.uname().machine not in ('aarch64', 'arm64'):
        raise Held('AUTHORITATIVE_PI_REQUIRED')
    out = Path(out).absolute()
    if out.exists() or not any((p / 'OWNER.md').is_file() for p in out.parents):
        raise Held('FRESH_OWNED_ROOT_REQUIRED')
    if not 27520 <= port <= 27620:
        raise Held('PORT_RANGE')
    try:
        raw = bounded(project_path, MAX_PROJECT)
    except Held as error:
        if str(error) == 'SIZE_LIMIT':
            raise Refused('PROJECT_SIZE') from error
        raise
    p = admit(raw)
    runtime_bytes = bounded(runtime_path, 4 * 1024 * 1024)
    runtime = validate_runtime(json.loads(runtime_bytes), unique_header(raw, 'map'))
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', port))
    out.mkdir(mode=0o700)
    report = {'format': 1, 'utc': datetime.now(timezone.utc).isoformat(), 'result': 'HOLD',
              'runtime_sha256': digest(runtime_bytes), 'project_sha256': digest(raw),
              'revision': p['h'], 'run_token': secrets.token_hex(12), 'checks': {},
              'verifier_files': {name: filehash(Path(__file__).with_name(name)) for name in
                                 ('tasverify.py', 'tasrev.py', 'ed25519.py', 'reccheck.py', 'heldmeta.py')},
              'authority': 'isolated Pi native replay; queue approval required for board promotion'}
    (out / 'project.tasp').write_bytes(raw)
    (out / 'project.tasp').chmod(0o400)
    (out / 'runtime.json').write_bytes(runtime_bytes)
    peers = []
    copied = []
    begin = None
    try:
        check_cancel()
        path = prepare(out, runtime, raw, report['run_token'], port, copied)
        check_cancel()
        startup = time.monotonic() + 180
        sv = Peer(str(out / 'sv' / Path(runtime['native']['server']['path']).name), out / 'sv', True, watch=peers)
        sv.wait(rb'Server spawned\.', startup)
        check_cancel()
        cl = Peer(str(out / 'cl' / Path(runtime['native']['client']['path']).name), out / 'cl', False, watch=peers)
        cl.wait(rb'Headless \(Null\) renderer initialized', startup)
        cl.wait(rb'FTESurf CSQC loaded', startup)
        # CSQC loads before PutClientInServer; early stringcmds can disappear and
        # viewpos can report an unspawned zero body. Gate on SSQC's actual join.
        sv.wait(rb'TASVerifier\^7 joined', startup)
        for peer in peers:
            require_plugin_policy(peer)
        report['checks']['binary_directory_only_plugins'] = True
        cut = cl.scan(); cl.send('vid_headless_sleep')
        cl.wait(rb'"vid_headless_sleep" is "0"', startup, cut)
        cl.wait(b'Default: "100"', startup, cut)
        report['checks']['registered_headless_sleep_zero'] = True
        plugin_before = [plugin_image(peer, runtime['native']['plugin']['sha256']) for peer in peers]
        cl.send('menu_restart; ui_close')
        # Commands before actual spawn can vanish. A real server reply gates the load.
        ready = False
        while time.monotonic() < startup:
            cut = cl.scan(); cl.send('cmd viewpos')
            try:
                cl.wait(rb'setpos [-\d.]+ [-\d.]+ [-\d.]+', min(startup, time.monotonic() + .5), cut)
                ready = True
                break
            except Held as error:
                if str(error) != 'TIME_LIMIT':
                    raise
        if not ready:
            raise Held('SPAWN_TIMEOUT')
        begin = time.monotonic()
        budget = float(TICK) * len(p['rows']) * 2
        deadline = begin + budget
        report['replay_wall_limit_seconds'] = budget
        cut = load_cut = cl.scan()
        binding_cut = sv.scan()
        cl.send('cmd tas project load ' + report['run_token'])
        cl.wait(b'tas project: loading ' + report['run_token'].encode() + rb' rev ', deadline, cut)
        binding_prefix = b'tas project: binding ' + report['run_token'].encode() + b' '
        binding = sv.wait(binding_prefix + rb'([0-9a-f]{64}) (\d+) (\d+) (\d+) (\d+)', deadline, binding_cut)
        rev, zone, track, leg, pre = [x.decode() for x in binding.groups()]
        if rev != p['h'] or zone != unique_header(raw, 'start') or int(pre) != p['startat']:
            raise Held('NATIVE_PROJECT_BINDING')
        report['native_binding'] = {'revision': rev, 'zone': zone, 'track': track, 'leg': leg, 'startat': int(pre)}
        terminal = cl.wait(rb'tas project: (?:loaded [^\n]+|load stopped[^\n]+)|tas: legal start session ended[^\n]+', deadline, cut)
        report['checks']['editor_terminal_sha256'] = digest(terminal.group(0))
        cut = cl.scan(); cl.send('cmd timer')
        state = cl.wait(rb'timer[^\n]*: (idle|armed|running|finished) on ' + re.escape(runtime['map'].encode()), deadline, cut)
        if state.group(1) != b'finished':
            raise Held('MISSING_NATURAL_FINISH')
        report['checks']['native_timer_finished'] = True
        plugin_after = [plugin_image(peer, runtime['native']['plugin']['sha256']) for peer in peers]
        if plugin_after != plugin_before:
            raise Held('PLUGIN_IMAGE_CHANGED')
        report['loaded_plugins'] = plugin_after
        for peer in reversed(peers):
            peer.stop()
        full_log = bounded(cl.log, MAX_LOG)
        if b'Unknown command' in full_log or b'QC VM error' in full_log:
            raise Held('UNSUPPORTED_CLIENT_OR_VM')
        log = full_log[load_cut:]
        ack = b'tas project: loading ' + report['run_token'].encode() + b' rev '
        server_log = bounded(sv.log, MAX_LOG)[binding_cut:]
        if log.count(ack) != 1 or server_log.count(binding_prefix) != 1:
            raise Held('DUPLICATE_OR_MISSING_LOAD_ACK')
        for terminal_pattern in (rb'tas project: loaded [^\n]+', rb'tas project: load stopped[^\n]+',
                                 rb'tas: legal start session ended[^\n]+'):
            if len(re.findall(terminal_pattern, log)) > 1:
                raise Held('DUPLICATE_EDITOR_TERMINAL')
        if len(re.findall(rb'timer[^\n]*: finished on ' + re.escape(runtime['map'].encode()), log)) != 1:
            raise Held('DUPLICATE_OR_MISSING_TIMER_FINISH')
        report['checks']['fresh_ack_and_finish'] = True
        report['processes'] = [{'pid': peer.proc.pid, 'image_device_inode': peer.image_identity,
                                'exit': peer.proc.returncode} for peer in peers]
        report['configuration'] = {side: {name: filehash(out / side / name) for name in
                                  ('default.fmf', 'ftesurf/verify.cfg')} for side in ('sv', 'cl')}
        if bounded(path, MAX_PROJECT) != raw:
            raise Held('ADMITTED_FILE_CHANGED')
        candidates = []
        for rec in sorted((out / 'sv/ftesurf/data/runs').rglob('*.rec')):
            data = bounded(rec, MAX_REC)
            if int(unique_header(data, 'flags')) & TF_TAS:
                candidates.append((rec, data))
        if len(candidates) != 1:
            raise Held('UNIQUE_NATIVE_TAS_RECORDING_REQUIRED')
        rec, data = candidates[0]
        measured = assess(raw, data, rec)
        if measured['track'] != report['native_binding']['track'] or measured['leg'] != report['native_binding']['leg']:
            raise Held('START_TARGET_CHANGED')
        report.update(measured)
        report['recording'] = rec.relative_to(out).as_posix()
        validate_runtime(runtime, runtime['map'])
        report['checks']['runtime_still_matches'] = True
        if any(filehash(Path(__file__).with_name(name)) != wanted for name, wanted in report['verifier_files'].items()):
            raise Held('VERIFIER_FILES_CHANGED')
        report['result'] = 'PASS'
    except (Held, Refused) as error:
        report['reason'] = str(error)
    except Exception as error:
        report['result'] = 'ERROR'
        report['reason'] = type(error).__name__
        # Native/raw logs remain private; do not embed untrusted exception text in a receipt.
    finally:
        cleanup_errors = []
        for peer in reversed(peers):
            try:
                peer.stop()
            except Exception:
                cleanup_errors.append('PROCESS_STOP')
        report['checks']['owned_peers_stopped'] = all(peer.proc.poll() is not None for peer in peers)
        report['processes'] = [{'pid': peer.proc.pid, 'image_device_inode': getattr(peer, 'image_identity', None),
                                'exit': peer.proc.returncode} for peer in peers]
        if not report['checks']['owned_peers_stopped']:
            cleanup_errors.append('PROCESS_ALIVE')
        # Retire ONLY verified unchanged static copies. Keep every generated data/log file.
        retired = 0
        for path, wanted in copied:
            try:
                if not path.is_file() or path.is_symlink() or filehash(path) != wanted:
                    cleanup_errors.append('STATIC_COPY_CHANGED')
                    continue
                path.unlink()
                retired += 1
            except OSError:
                cleanup_errors.append('STATIC_COPY_RETIRE')
        report['checks']['unchanged_static_copies_retired'] = retired
        if cleanup_errors:
            report['result'] = 'ERROR'
            report['reason'] = 'CLEANUP_' + cleanup_errors[0]
        finish_replay_budget(report, begin)
        # This final latch read commits the CLI decision; later signals during
        # serialization/printing are late. Queue promotion needs its own fence.
        if _cancelled and not cleanup_errors:
            report['result'] = 'HOLD'
            report['reason'] = 'CANCELLED'
        (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def finish_replay_budget(report, begin):
    if begin is None:
        return
    elapsed = time.monotonic() - begin
    report['replay_wall_seconds'] = elapsed
    if report['result'] == 'PASS' and elapsed > report['replay_wall_limit_seconds']:
        report['result'] = 'HOLD'
        report['reason'] = 'TIME_LIMIT'


def main():
    global _cancelled
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='command', required=True)
    m = sub.add_parser('runtime')
    for key in ('fixture', 'server', 'client', 'plugin', 'output'):
        m.add_argument('--' + key, type=Path, required=True)
    m.add_argument('--map', required=True)
    m.add_argument('--gamemode', choices=('surf', 'bhop'), required=True)
    m = sub.add_parser('run')
    for key in ('runtime', 'project', 'out'):
        m.add_argument('--' + key, type=Path, required=True)
    m.add_argument('--port', type=int, default=27616)
    a = ap.parse_args()
    if a.command == 'runtime':
        data = runtime_manifest(a.fixture, a.server, a.client, a.plugin, a.map, a.gamemode)
        with a.output.open('x') as f:
            json.dump(data, f, indent=2)
        return 0
    previous_cancelled, _cancelled = _cancelled, False
    def cancel(signum, frame):
        global _cancelled
        _cancelled = True
    handlers = {sig: signal.signal(sig, cancel) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        result = run(a.runtime, a.project, a.out, a.port)
    except (Held, Refused) as error:
        kind = 'REFUSE' if isinstance(error, Refused) else 'HOLD'
        print('VERIFY-TAS ' + kind + ' ' + str(error))
        return 2
    except Exception as error:
        print('VERIFY-TAS ERROR ' + type(error).__name__)
        return 2
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
        _cancelled = previous_cancelled
    if result['result'] == 'PASS':
        print('VERIFY-TAS PASS ticks %d finish' % result['ticks'])
        return 0
    print('VERIFY-TAS ' + result['result'] + ' ' + result.get('reason', 'UNKNOWN'))
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
