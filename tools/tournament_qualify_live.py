#!/usr/bin/env python3
"""Qualify tournament maps against the LIVE lobby content, for surfd's
SURFD_TOURNAMENT_QUALIFICATIONS registry (surfd/tournament_pool.py registry()/catalogue()).

At arrival a lobby's QC reports *mapcrc, its zone pin and gamemode, and tournament_rules.py
checks them against the pins frozen from this registry, so the observation must come from the
lobby's own native binary, content, zone files and QC source:

  observer    (dev PC)  compile the observer qwprogs from the commit the lobbies run
                        (tools/tournament_qualify.py's OBSERVER + TQQ_Frame hook)
  candidates  (any)     /api/board?maps=1 MAPDL rows -> zoned, enabled surf/bhop maps, tier 1-10
  run         (the box) ONE disposable niced server reading the live basedir through an owned
                        base of symlinks plus -homedir: every write lands in the owned work root.
                        stdlib + surfd/tournament_rules.py only (Python 3.11 on the Pi).

A long run is meant to be launched detached (setsid nohup ... &); it writes a pidfile and
stops its own server on exit. `run` never deletes anything outside its own run directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pty
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'surfd'))
from tournament_rules import PROFILES, MAP_NAME, HEX8, HEX64, tick_for  # noqa: E402

PIN_FIELDS = ('mapcrc', 'zonepin', 'gamemode', 'sha256', 'map_stamp')
DEFAULT_LIVE = '/srv/nvme/ftesurf-server/game'
FAIL_MARKERS = ('QC runtime error', 'Host_Error:', 'Sys_Error:', 'PR_RunError', 'Segmentation fault')


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def stamp(path):
    st = os.stat(path)
    return [st.st_size, st.st_mtime_ns, st.st_ctime_ns]


# ---------------------------------------------------------------- candidates

def candidates_from_mapdl(text):
    """MAPDL as /api/board?maps=1 serves it: `dl stem mode src tier kb first new mt kt [of] of zoned enabled`."""
    if not text.startswith('FTESURF-MAPDL 1\n'):
        raise ValueError('not an FTESURF-MAPDL 1 list')
    out, seen = [], set()
    for line in text.splitlines():
        f = line.split()
        if len(f) < 12 or f[0] != 'dl':
            continue
        stem, mode, tier, zoned, enabled = f[1], f[2], f[4], f[-2], f[-1]
        if mode not in ('surf', 'bhop') or zoned != '1' or enabled != '1':
            continue
        if not tier.isdigit() or not 1 <= int(tier) <= 10 or not MAP_NAME.fullmatch(stem):
            continue
        if stem.lower() in seen:
            continue
        seen.add(stem.lower())
        out.append(dict(name=stem, mode=mode, tier=int(tier)))
    return out


# ---------------------------------------------------------------- observation

def parse_observation(line, name, profile, mode):
    """One TQQUAL line from the observer VM -> pin fields, or ValueError naming what is unqualified."""
    parts = line.strip().split('|')
    if len(parts) != 10 or parts[0] != 'TQQUAL' or parts[1].lower() != name.lower():
        raise ValueError('malformed or unexpected observation')
    _, _, crc, zonepin, movement, tick, clock, gamemode, generation, valid = parts
    want = PROFILES[profile]
    why = []
    if not HEX8.fullmatch(crc) or crc == '00000000':
        why.append('mapcrc ' + crc)
    if not HEX64.fullmatch(zonepin):
        why.append('no zone pin')
    if gamemode != mode:
        why.append('gamemode %s, list says %s' % (gamemode, mode))
    if movement != want['movement']:
        why.append('movement ' + movement)
    if tick != str(tick_for(profile, mode)) or clock != str(tick_for(profile, mode)):
        why.append('tick %s/%s' % (tick, clock))
    if not re.fullmatch(r'[1-9][0-9]{0,9}', generation):
        why.append('zone generation ' + generation)
    if valid != '1':
        why.append('course not valid')
    if why:
        raise ValueError('; '.join(why))
    return dict(mapcrc=crc, zonepin=zonepin, gamemode=gamemode, movement=movement,
                tick_us=int(tick), clock_us=int(clock), zone_generation=int(generation))


def record(observation, sha, map_stamp):
    return dict(approved=1, mapcrc=observation['mapcrc'], zonepin=observation['zonepin'],
                gamemode=observation['gamemode'], sha256=sha, map_stamp=list(map_stamp))


def zone_stats(zone_dirs, name):
    out = []
    for d in zone_dirs:
        for n in sorted({name, name.lower()}):
            p = os.path.join(d, n + '.json')
            try:
                st = os.stat(p)
            except FileNotFoundError:
                continue
            out.append([p, st.st_size, st.st_mtime_ns])
    return out


def resolve_bsp(maps_dir, listing, name):
    """The held file's real spelling (the registry key), matched case-insensitively once."""
    hits = [n for n in listing.get(name.lower(), ())]
    if len(hits) != 1:
        return None
    return os.path.join(maps_dir, hits[0] + '.bsp'), hits[0]


def reusable(prev_state, prev_registry, name, profile, map_stamp, zones):
    s = prev_state.get(name)
    r = prev_registry.get(name, {}).get(profile)
    return bool(s and r and s.get('map_stamp') == list(map_stamp) and s.get('zones') == zones
                and r.get('map_stamp') == list(map_stamp))


# ---------------------------------------------------------------- owned base

def build_base(live, base, manifest_text):
    """Symlink the live content directories and plugins into an owned base; write our own manifest.

    The gamedir symlink is read through; -homedir takes every gamedir write, and the base root
    (crash.log, installed.lst, probes) is a real owned directory."""
    base.mkdir(mode=0o700)
    linked = []
    for entry in sorted(os.listdir(live)):
        src = os.path.join(live, entry)
        if entry == 'tools':
            continue
        if os.path.isdir(src) and not os.path.islink(src):
            os.symlink(src, base / entry)
            linked.append(entry)
        elif re.fullmatch(r'fteplug_[a-z0-9_]+\.(so|dll)', entry):
            os.symlink(src, base / entry)
            linked.append(entry)
    lines = [ln for ln in manifest_text.splitlines() if not re.match(r'\s*DISABLEHOMEDIR\b', ln, re.I)]
    (base / 'default.fmf').write_text('\n'.join(lines) + '\n')
    return linked


def owned_work(work, live):
    work = Path(work).resolve(strict=True)
    st = os.stat(work)
    if not work.is_dir() or st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise ValueError('work root must be an owned 0700 directory')
    live = Path(live).resolve(strict=True)
    if work == live or live in work.parents or work in live.parents:
        raise ValueError('work root must be outside the live basedir')
    return work


def free_udp_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class Server:
    def __init__(self, run_dir, command, env):
        self.log_path = run_dir / 'server-console.log'
        self.log = open(self.log_path, 'ab')
        self.input, slave = pty.openpty()           # Linux FTE ignores non-tty stdin
        try:
            self.process = subprocess.Popen(command, cwd=run_dir, stdin=slave, stdout=self.log,
                                            stderr=subprocess.STDOUT, env=env, start_new_session=True,
                                            preexec_fn=lambda: os.nice(19))
        finally:
            os.close(slave)
        (run_dir / 'server.pid').write_text('%d\n' % self.process.pid)

    def send(self, text):
        data = (text + '\n').encode()
        while data:
            data = data[os.write(self.input, data):]

    def text_from(self, offset):
        with open(self.log_path, 'rb') as f:
            f.seek(offset)
            return f.read().decode(errors='replace')

    def size(self):
        return os.path.getsize(self.log_path)

    def stop(self):
        if self.process.poll() is None:
            try:
                self.send('quit')
            except OSError:
                pass
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGTERM)
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(self.process.pid, signal.SIGKILL)
                    self.process.wait(timeout=10)
        os.close(self.input)
        self.log.close()


def server_command(args, base, home, port, first):
    cmd = []
    if shutil.which('ionice'):
        cmd += ['ionice', '-c3']
    cmd += [args.binary, '-basedir', str(base), '-manifest', str(base / 'default.fmf'),
            '-homedir', str(home), '-nobrowse', '-nosound', '-ip', '127.0.0.1', '-port', str(port),
            '+set', 'cfg_save_auto', '0', '+developer', '1',
            '+exec', 'cfg/lobby/lobby.cfg',
            # Never a lobby: no directory heartbeat, no master key, no tournament or account traffic.
            '+set', 'lobby_enable', '0', '+set', 'lobby_master', '', '+set', 'lobby_master_key', '',
            '+set', 'tournament_enable', '0', '+set', 'game_account_enable', '0',
            '+set', 'sv_public', '0', '+set', 'sv_port', str(port),
            '+set', 'sv_movementprofile', args.profile,
            '+hostname', 'disposable tournament qualification (not a lobby)', '+map', first]
    return cmd


def run(args):
    live = os.path.realpath(args.live)
    work = owned_work(args.work, live)
    maps_dir = args.maps or os.path.join(live, 'momentum/maps')
    zone_dirs = args.zone_dir or [os.path.join(live, 'ftesurf/maps/zones/local'),
                                  os.path.join(live, 'momentum/maps/zones/local'),
                                  os.path.join(live, 'momentum/maps/zones/online')]
    args.binary = args.binary or os.path.join(live, 'fteqw-svarm64')
    if args.profile not in PROFILES:
        raise ValueError('unknown profile')
    cands = json.loads(Path(args.candidates).read_text())
    if args.only:
        want = {n.lower() for n in args.only.split(',')}
        cands = [c for c in cands if c['name'].lower() in want]
    if args.limit:
        cands = cands[:args.limit]
    prev_registry = json.loads(Path(args.previous).read_text())['maps'] if args.previous else {}
    prev_state = json.loads(Path(args.previous_state).read_text()) if args.previous_state else {}

    run_dir = work / time.strftime('run-%Y%m%dT%H%M%SZ', time.gmtime())
    run_dir.mkdir(mode=0o700)
    base, home = run_dir / 'base', run_dir / 'home'
    linked = build_base(live, base, Path(live, 'default.fmf').read_text())
    (home / 'ftesurf').mkdir(parents=True, mode=0o700)
    shutil.copyfile(args.observer, home / 'ftesurf/qwprogs.dat')
    for d in ('userhome', 'xdg-data', 'xdg-config', 'xdg-cache'):
        (run_dir / d).mkdir(mode=0o700)
    env = dict(PATH='/usr/bin:/bin', HOME=str(run_dir / 'userhome'), XDG_DATA_HOME=str(run_dir / 'xdg-data'),
               XDG_CONFIG_HOME=str(run_dir / 'xdg-config'), XDG_CACHE_HOME=str(run_dir / 'xdg-cache'), LANG='C.UTF-8')

    listing = {}
    for f in os.listdir(maps_dir):
        if f.lower().endswith('.bsp'):
            listing.setdefault(f[:-4].lower(), []).append(f[:-4])

    receipt = dict(v=1, tool_sha256=sha256_file(__file__), observer_vm_sha256=sha256_file(args.observer),
                   native_sha256=sha256_file(args.binary), live=live, maps_dir=maps_dir, zone_dirs=zone_dirs,
                   profile=args.profile, linked=linked, started=time.time(), maps=[],
                   scope='Observed on the live content with the lobby QC + observer; approval = valid observation')
    registry = {k: dict(v) for k, v in prev_registry.items()} if args.keep_previous else {}
    state = dict(prev_state) if args.keep_previous else {}
    server, loads = None, 0
    marker = run_dir / 'started.marker'
    marker.write_text('')

    def load(held, fresh):
        """`map` on the running server, or a new server; -> (TQQUAL line or None, last TQDIAG, started)."""
        nonlocal server, loads
        # A dedicated server keeps every model it loaded: one process died at map 17-36 on MAX_MOD_KNOWN.
        started = fresh or server is None or server.process.poll() is not None or loads >= args.recycle
        if started:
            if server is not None:
                server.stop()
            server = Server(run_dir, server_command(args, base, home, free_udp_port(), held), env)
            offset, loads = 0, 1
            receipt['maps'][-1]['server_started'] = True
        else:
            offset = server.size()
            server.send('map ' + held)
            loads += 1
        deadline, diag, obs = time.monotonic() + args.timeout, '', None
        while time.monotonic() < deadline:
            text = server.text_from(offset)
            for line in text.splitlines():
                i = line.find('TQQUAL|')
                if i >= 0 and line[i:].split('|')[1].lower() == held.lower():
                    obs = line[i:]
                j = line.find('TQDIAG|')
                if j >= 0:
                    diag = line[j:]
            bad = [m for m in FAIL_MARKERS if m in text]
            if obs or bad or server.process.poll() is not None:
                if bad:
                    raise ValueError('native failure: ' + bad[0])
                break
            time.sleep(0.25)
        return obs, diag, started

    def stop(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGHUP, stop)
    try:
        for c in cands:
            name, mode, t0 = c['name'], c['mode'], time.monotonic()
            row = dict(name=name, mode=mode, tier=c.get('tier'))
            receipt['maps'].append(row)
            hit = resolve_bsp(maps_dir, listing, name)
            if not hit:
                row.update(result='missing', reason='no single held BSP for this name')
                continue
            path, held = hit
            row['held'] = held
            try:
                before = stamp(path)
                with open(path, 'rb') as f:
                    if f.read(4) != b'VBSP':
                        raise ValueError('not a Source BSP')
                zones = zone_stats(zone_dirs, held)
                if reusable(prev_state, prev_registry, held, args.profile, before, zones):
                    registry.setdefault(held, {})[args.profile] = prev_registry[held][args.profile]
                    state[held] = dict(map_stamp=before, zones=zones)
                    row.update(result='reused')
                    continue
                sha = sha256_file(path)
                if stamp(path) != before:
                    raise ValueError('BSP changed while hashing')
                obs, diag, started = load(held, False)
                if not obs and not started and server.process.poll() is not None:
                    # A reused server can die of its own model table, not of this map: one try on a fresh one.
                    row['retried'] = 'reused server exited (rc %s)' % server.process.returncode
                    obs, diag, started = load(held, True)
                if not obs:
                    if server.process.poll() is not None:
                        raise ValueError('server exited (rc %s)' % server.process.returncode)
                    raise ValueError('no observation in %ds%s' % (args.timeout, (': ' + diag) if diag else ''))
                o = parse_observation(obs, held, args.profile, mode)
                if stamp(path) != before or zone_stats(zone_dirs, held) != zones:
                    raise ValueError('BSP or zone file changed during the load')
                registry.setdefault(held, {})[args.profile] = record(o, sha, before)
                state[held] = dict(map_stamp=before, zones=zones)
                row.update(result='valid', observation=o, sha256=sha, map_stamp=before)
            except ValueError as exc:
                row.update(result='invalid', reason=str(exc))
                registry.get(held, {}).pop(args.profile, None)
                if held in registry and not registry[held]:
                    del registry[held]
            finally:
                row['seconds'] = round(time.monotonic() - t0, 2)
                (run_dir / 'progress.json').write_text(json.dumps(dict(done=len(receipt['maps']), of=len(cands))))
    except KeyboardInterrupt:
        receipt['interrupted'] = True
    finally:
        if server is not None:
            server.stop()
        receipt['finished'] = time.time()
        out_reg = Path(args.out or run_dir / 'qualifications.json')
        out_reg.write_text(json.dumps(dict(v=1, maps=dict(sorted(registry.items()))), separators=(',', ':')) + '\n')
        Path(run_dir / 'state.json').write_text(json.dumps(state, separators=(',', ':')) + '\n')
        receipt['registry_sha256'] = sha256_file(out_reg)
        receipt['counts'] = {k: sum(1 for m in receipt['maps'] if m.get('result') == k)
                             for k in ('valid', 'reused', 'invalid', 'missing')}
        (run_dir / 'receipt.json').write_text(json.dumps(receipt, indent=1) + '\n')
        print(json.dumps(dict(run=str(run_dir), registry=str(out_reg), counts=receipt['counts'])))
    return 0 if not receipt.get('interrupted') else 130


# ---------------------------------------------------------------- observer (dev PC)

def observer(args):
    sys.path.insert(0, str(HERE))
    from tournament_qualify import OBSERVER
    root = HERE.parent
    commit = subprocess.check_output(['git', '-C', str(root), 'rev-parse', args.source_ref + '^{commit}'], text=True).strip()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='tq-observer-') as tmp:
        tmp = Path(tmp)
        tar = subprocess.run(['git', '-C', str(root), 'archive', commit, 'src'], check=True, capture_output=True).stdout
        subprocess.run(['tar', '-x', '-C', str(tmp)], input=tar, check=True)
        (tmp / 'ftesurf').mkdir()
        src = tmp / 'src/server/sv_tournament.qc'
        with src.open('a') as f:
            f.write(OBSERVER)
        main = tmp / 'src/server/sv_main.qc'
        text = main.read_text()
        if text.count('Tour_Frame();') != 1:
            raise ValueError('unexpected frame hook')
        main.write_text(text.replace('Tour_Frame();', 'Tour_Frame();\n\tTQQ_Frame();'))
        log = subprocess.run([args.compiler, '-O2', '-Wall', '-v', '-max_strings', '4194304', '-srcfile', 'sv_progs.src'],
                             cwd=tmp / 'src', capture_output=True, text=True, timeout=300)
        (out / 'observer-compile.log').write_text(log.stdout + log.stderr)
        if log.returncode or not (tmp / 'ftesurf/qwprogs.dat').is_file():
            raise RuntimeError('observer compile failed: ' + str(out / 'observer-compile.log'))
        shutil.copyfile(tmp / 'ftesurf/qwprogs.dat', out / 'observer-qwprogs.dat')
        meta = dict(source_ref=commit, compiler_sha256=sha256_file(args.compiler),
                    observer_source_sha256=sha256_file(src), vm_sha256=sha256_file(out / 'observer-qwprogs.dat'))
    (out / 'observer.json').write_text(json.dumps(meta, indent=1) + '\n')
    print(json.dumps(meta))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    o = sub.add_parser('observer')
    o.add_argument('--source-ref', required=True, help='the commit the lobbies run')
    o.add_argument('--compiler', required=True)
    o.add_argument('--out', required=True)
    c = sub.add_parser('candidates')
    c.add_argument('mapdl')
    c.add_argument('--out', required=True)
    r = sub.add_parser('run')
    r.add_argument('--work', required=True, help='owned 0700 directory outside the live basedir')
    r.add_argument('--live', default=DEFAULT_LIVE)
    r.add_argument('--binary', help='default: <live>/fteqw-svarm64')
    r.add_argument('--maps', help='default: <live>/momentum/maps (surfd MAPS_DIR)')
    r.add_argument('--zone-dir', action='append', help='default: the three lobby zone directories')
    r.add_argument('--observer', required=True)
    r.add_argument('--candidates', required=True)
    r.add_argument('--profile', default='default', choices=tuple(PROFILES))
    r.add_argument('--only', help='comma-separated names')
    r.add_argument('--limit', type=int)
    r.add_argument('--timeout', type=int, default=120, help='seconds per map')
    r.add_argument('--recycle', type=int, default=12, help='map loads per server process (default 12)')
    r.add_argument('--previous', help='previous registry (reuse unchanged maps)')
    r.add_argument('--previous-state', help="previous run's state.json")
    r.add_argument('--keep-previous', action='store_true', help='start from the previous registry instead of empty')
    r.add_argument('--out', help='registry path (default: <run>/qualifications.json)')
    args = ap.parse_args(argv)
    if args.cmd == 'observer':
        return observer(args)
    if args.cmd == 'candidates':
        rows = candidates_from_mapdl(Path(args.mapdl).read_text())
        Path(args.out).write_text(json.dumps(rows) + '\n')
        print('%d candidates (%d surf, %d bhop)' % (len(rows), sum(r['mode'] == 'surf' for r in rows),
                                                    sum(r['mode'] == 'bhop' for r in rows)))
        return 0
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
