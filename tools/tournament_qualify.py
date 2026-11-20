#!/usr/bin/env python3
"""Observe exact native map/zone identities in a pristine, disposable prepared rig.

This is a LOCAL TEST helper, not a live-node approver or full VFS attestation.
Normal output has approved=0. --fixture-approve permits only the marked synthetic
playtest rig; it never reads an owner profile, installs a VM or contacts a service.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'surfd'))
from tournament_rules import PROFILES, tick_for
from seed_csprogs import md4, fold_md4

MAP_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z')
HEX8 = re.compile(r'[0-9a-f]{8}\Z')
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
OBSERVER = '''
// Disposable qualification VM only. No expected pins or client timing claims.
string tqq_last_map;
float tqq_diagat;
void() TQQ_Frame =
{
    local string line, movement;
    if (tqq_last_map == mapname || time < 1 || !zone_entsready || !zone_loaded) return;
    Tour_Observe();
    movement = Tour_Movement();
    // FTE runs startup frames before publishing its final spawned/locked state.
    // Never qualify that provisional snapshot or invent unknown numeric fields.
    if (!tq_observed_valid || movement == "unqualified")
    {
        if (time >= tqq_diagat)
        {
            line = strcat("TQDIAG|", mapname, "|rules=", serverkey("*ruleset"), "|movement=", movement);
            line = strcat(line, "|valid=", tq_observed_valid ? "1" : "0", "|course=", tq_observed_course ? "1" : "0");
            print(strcat(line, "|gen=", sprintf("%i", zone_generation), "\\n"));
            tqq_diagat = time + 5;
        }
        return;
    }
    // Bounded calls also avoid legacy vararg register limits. Serialize typed
    // integers and truth values explicitly, as the actual transport does.
    line = strcat("TQQUAL|", mapname, "|", infokey(world, "*mapcrc"), "|", tq_observed_pin);
    line = strcat(line, "|", movement, "|", ftos(Tour_TickUS(cvar("pm_ticrate"))), "|", ftos(Tour_TickUS(run_t_tick)));
    line = strcat(line, "|", serverkey("gamemode"), "|", sprintf("%i", zone_generation));
    print(strcat(line, "|", tq_observed_valid ? "1" : "0", "\\n"));
    if (strlen(tqq_last_map)) strunzone(tqq_last_map);
    tqq_last_map = strzone(mapname);
};
'''


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def stamp(path):
    st = Path(path).stat()
    return [st.st_size, st.st_mtime_ns, st.st_ctime_ns]


def held_asset(path):
    """Bind provenance before and after hashing; native checksum is separate SHA."""
    before = stamp(path)
    data = Path(path).read_bytes()
    if data[:4] != b'VBSP' or stamp(path) != before:
        raise ValueError('BSP missing, not Source, or changed during qualification hashing')
    return dict(sha256=hashlib.sha256(data).hexdigest(), map_stamp=before,
                mapcrc=f'{fold_md4(md4(data)):08x}')


def reject_sidecars(maps, name):
    # Prepared rigs mount a minimal asset tree. Refuse familiar loose overrides;
    # this is deliberately not presented as an audit of every possible VFS mount.
    candidates = [maps / (name + '.ent'), maps / (name + '.lmp')]
    candidates += list(maps.glob(name + '_l_*.lmp'))
    candidates += list((maps / name).glob('*.lmp'))
    if any(p.exists() for p in candidates):
        raise ValueError('Loose map override requires separate operator qualification: ' + name)


def parse_observation(line, name, profile, expected_crc):
    parts = line.strip().split('|')
    if len(parts) != 10 or parts[0] != 'TQQUAL' or parts[1] != name:
        raise ValueError('Malformed or unexpected native qualification observation')
    _, _, crc, zonepin, movement, tick, clock, mode, generation, valid = parts
    expected_movement = PROFILES[profile]['movement']
    expected_tick = tick_for(profile, mode) if mode in ('surf', 'bhop') else -1
    if (not HEX8.fullmatch(crc) or crc == '00000000' or crc != expected_crc
            or not HEX64.fullmatch(zonepin) or mode not in ('surf', 'bhop')
            or movement != expected_movement
            or tick != str(expected_tick) or clock != str(expected_tick)
            or not re.fullmatch(r'[1-9][0-9]{0,9}', generation) or valid != '1'):
        raise ValueError('Native map/course/movement/tick observation is unqualified: ' + name)
    return dict(name=name, mapcrc=crc, zonepin=zonepin, gamemode=mode,
                movement=movement, tick_us=int(tick), clock_us=int(clock),
                local_zone_generation=int(generation))


def registry_record(observation, asset, fixture_approve=False):
    return dict(approved=int(fixture_approve), mapcrc=observation['mapcrc'],
                zonepin=observation['zonepin'], gamemode=observation['gamemode'],
                sha256=asset['sha256'], map_stamp=asset['map_stamp'])


def qualify_prepared(prepared, compiler, profile='default', fixture_approve=False, timeout=90):
    import tournament_playtest as P
    prepared = P.owned_root(Path(prepared).resolve())
    compiler = Path(compiler).resolve()
    manifest = json.loads((prepared / 'manifest.json').read_text())
    if manifest.get('test_only') is not True or (prepared / 'backend').exists():
        raise ValueError('Qualification requires a pristine test-only prepared rig')
    if profile not in PROFILES or not compiler.is_file():
        raise ValueError('Unknown profile or unavailable inspected compiler')
    if digest(compiler) != manifest['native'].get('fteqcc64'):
        raise ValueError('Compiler does not match the prepared inspected toolchain')
    names = manifest.get('maps')
    if (not isinstance(names, list) or not names or len(names) > 24
            or len(set(names)) != len(names) or any(not isinstance(n, str) or not MAP_NAME.fullmatch(n) for n in names)):
        raise ValueError('Invalid bounded prepared map list')
    for name, sha in manifest['native'].items():
        if digest(prepared / 'bin' / name) != sha:
            raise ValueError('Prepared native changed: ' + name)
    for name, sha in manifest['vms'].items():
        if digest(prepared / 'ftesurf' / name) != sha:
            raise ValueError('Prepared VM changed: ' + name)
    q = prepared / 'qualification'
    q.mkdir()  # Never reuse a played or partially qualified native profile.
    receipt = dict(ok=False, test_only=True, profile=profile, fixture_approved=bool(fixture_approve),
                   scope='Isolated synthetic-fixture native identities only; not live approval or full VFS attestation',
                   compiler_sha256=digest(compiler), native=manifest['native'],
                   base_vms=manifest['vms'], observations=[])
    native = None
    try:
        shutil.copytree(prepared / 'src', q / 'src')
        rewrites = manifest.get('test_origin_rewrites', {})
        for relative, expected in manifest['source_files'].items():
            source_relative = Path(relative).relative_to('src')
            expected = rewrites.get(str(source_relative), expected)
            if digest(q / 'src' / source_relative) != expected:
                raise ValueError('Prepared source snapshot changed: ' + relative)
        shutil.copytree(prepared / 'bin', q / 'bin')
        shutil.copytree(prepared / 'server', q / 'server', symlinks=True)
        (q / 'ftesurf').mkdir()
        server_source = q / 'src/server/sv_tournament.qc'
        with server_source.open('a') as output:
            output.write(OBSERVER)
        main = q / 'src/server/sv_main.qc'
        text = main.read_text()
        if text.count('Tour_Frame();') != 1:
            raise ValueError('Unexpected frame hook; no native VM compiled')
        main.write_text(text.replace('Tour_Frame();', 'Tour_Frame();\n\tTQQ_Frame();'))
        with (q / 'compile.log').open('w') as output:
            subprocess.run([str(compiler), '-O2', '-Wall', '-v', '-max_strings', '4194304',
                            '-srcfile', 'sv_progs.src'], cwd=q / 'src',
                           stdout=output, stderr=subprocess.STDOUT, check=True, timeout=120)
        vm = q / 'ftesurf/qwprogs.dat'
        receipt['observer_vm_sha256'] = digest(vm)
        receipt['observer_source_sha256'] = digest(server_source)
        shutil.copy2(vm, q / 'server/ftesurf/qwprogs.dat')
        maps = prepared / 'server/ftesurf/maps'
        assets = {}
        for name in names:
            reject_sidecars(maps, name)
            assets[name] = held_asset(maps / (name + '.bsp'))
        receipt['assets'] = assets
        command = P.command_base(q, 'server', 'fteqw-sv64') + [
            '-ip', '127.0.0.1', '-port', str(P.free_port(P.socket.SOCK_DGRAM)),
            '+set', 'lobby_enable', '0', '+set', 'tournament_enable', '0',
            '+set', 'game_account_enable', '0', '+set', 'sv_movementprofile', profile,
            '+hostname', 'LOCAL disposable qualification', '+map', names[0]]
        native = P.Native(q, 'server', command)
        rows = {}
        for index, name in enumerate(names):
            if index:
                native.send('map ' + name)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                P.native_failures(q)
                if native.process.poll() is not None:
                    raise RuntimeError('Owned qualifier stopped; inspect retained server-console.log')
                lines = (q / 'server-console.log').read_text(errors='replace').splitlines()
                observations = [line[line.index('TQQUAL|'):] for line in lines
                                if 'TQQUAL|' in line and line[line.index('TQQUAL|'):].startswith('TQQUAL|' + name + '|')]
                if observations:
                    observation = parse_observation(observations[-1], name, profile, assets[name]['mapcrc'])
                    if stamp(maps / (name + '.bsp')) != assets[name]['map_stamp']:
                        raise ValueError('Held BSP changed during native load: ' + name)
                    rows[name] = {profile: registry_record(observation, assets[name], fixture_approve)}
                    receipt['observations'].append(observation)
                    print('Native qualification observed: ' + name, flush=True)
                    break
                time.sleep(.1)
            else:
                raise RuntimeError('Timed out observing native map: ' + name)
        registry = prepared / ('fixture-qualifications.json' if fixture_approve else 'qualification-proposal.json')
        registry.write_text(json.dumps(dict(v=1, maps=rows), indent=2) + '\n')
        receipt.update(ok=True, registry=str(registry))
        return registry
    except BaseException as exc:
        receipt['failure'] = str(exc) or type(exc).__name__
        raise
    finally:
        try:
            if native is not None:
                native.stop()
        finally:
            (q / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--profile', choices=tuple(PROFILES), default='default')
    parser.add_argument('--fixture-approve', action='store_true', help='Only for the marked disposable local rig, never live approval')
    args = parser.parse_args()
    print(qualify_prepared(args.prepared, args.compiler, args.profile, args.fixture_approve))


if __name__ == '__main__':
    main()
