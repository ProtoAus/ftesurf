#!/usr/bin/env python3
"""Patch 841: a zone file's maxVelocity sets the map's speed cap (engine sv_phys.c).

python tools/p841caps.py --server <fteqwsv64.exe> --qwprogs <qwprogs.dat> --out <dir> [--control]

One dedicated server in a private overlay loads seven maps and prints sv_maxvelocity after
each; the expectation is computed here from the same files in the engine's order. Planted
files (overlay data/ only): a zone-less local file with maxVelocity 7777 (surf_dune: engine
and QC read different files, the QC must say so), an out-of-range 200000 (surf_joutsenlaulu:
ignored, cfg/maps stands), a curated copy at 6100 (surf_santorini with sv_zones_curated 1).
--control grades the old engine: every cap from cfg/maps or the default, no ruleset line.
Content junctions are read-only links into C:/FTESurf; only the overlay's data/ is written.
"""
import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTENT = pathlib.Path('C:/FTESurf')
STEAM = pathlib.Path('C:/Program Files (x86)/Steam/steamapps/common')
MOUNTS = [STEAM / 'Momentum Mod Playtest/momentum', STEAM / 'Counter-Strike Source/cstrike',
          STEAM / 'Half-Life 2/hl2']
JUNCTIONS = ('maps', 'gfx', 'glsl', 'models', 'particles', 'scripts')
# (map, sv_zones_curated)
ARMS = [('surf_boreas', 0), ('surf_ofrenda', 0), ('surf_santorini', 0), ('surf_axil', 0),
        ('surf_dune', 0), ('surf_joutsenlaulu', 0), ('surf_santorini', 1)]


def cfg_cap(gd, m):
    cap = 3500.0
    p = gd / 'cfg/maps' / ('map_%s.cfg' % m)
    if p.is_file():
        for line in p.read_text(errors='replace').splitlines():
            t = line.split('//')[0].split()
            if len(t) >= 3 and t[0] == 'set' and t[1] == 'sv_maxvelocity':
                cap = float(t[2])
    return cap


def has_regions(t):
    if isinstance(t, dict):
        return (isinstance(t.get('regions'), list) and bool(t['regions'])) or \
            any(has_regions(v) for v in t.values())
    return isinstance(t, list) and any(has_regions(v) for v in t)


def zone_file(gd, m, curated):
    """The file the engine reads: per name, a loose data/<name> if it exists, else <name> on the
    search path (game dir, then mounts); a file with no region moves to the next name. Packed
    files are not on these paths, so they read as absent, as the engine reads them."""
    names = (['data/maps/zones/local', 'maps/zones/curated'] if curated else []) + \
            ['maps/zones/local', 'maps/zones/online']
    for n in names:
        rel = '%s/%s.json' % (n, m)
        cands = [gd / rel] if n.startswith('data/') else \
            [gd / 'data' / rel, gd / rel] + [mt / rel for mt in MOUNTS]
        hit = next((c for c in cands if c.is_file()), None)
        if hit is None:
            continue
        try:
            j = json.loads(hit.read_text(encoding='utf-8'))
        except ValueError:
            continue
        if not isinstance(j, dict) or not (has_regions(j.get('tracks'))
                                           or any(isinstance(v, list) and v for v in
                                                  (j.get('globalRegions') or {}).values())):
            continue
        mv = j.get('maxVelocity')
        return hit, (mv if isinstance(mv, (int, float)) and not isinstance(mv, bool) else 0)
    return None, 0


def expect(gd, m, curated, control):
    cap = cfg_cap(gd, m)
    if control:
        return cap, None
    hit, mv = zone_file(gd, m, curated)
    if hit is not None and mv and 1 <= mv <= 100000:
        return float(mv), hit
    return cap, None


def plant(gd):
    src = CONTENT / 'ftesurf/maps/zones/local'
    d = gd / 'data/maps/zones/local'
    d.mkdir(parents=True)
    # A region the engine counts but QC cannot build (two points): QC skips the file and
    # times with the next name's, so the two read different files and QC must say so.
    (d / 'surf_dune.json').write_text(json.dumps(
        {'formatVersion': 1, 'maxVelocity': 7777,
         'tracks': {'main': {'zones': {'segments': [], 'end': {'regions': [
             {'points': [[0, 0], [1, 1]], 'bottom': 0, 'height': 10}]}}}}}))
    # A packed data/ copy at 9000: the engine reads it as absent, QC times with it.
    j = json.loads((src / 'surf_boreas.json').read_text(encoding='utf-8'))
    j['maxVelocity'] = 9000
    with zipfile.ZipFile(gd / 'zzz_p841.pk3', 'w') as z:
        z.writestr('data/maps/zones/local/surf_boreas.json', json.dumps(j))
        # A packed map ruleset (no loose one exists): the new engine refuses it, the old reads it.
        z.writestr('cfg/maps/map_surf_santorini.cfg', 'set sv_maxvelocity 7000\n')
        # A pak symlink to a loose file: surf has no mode file, so the old engine follows this
        # one to mode_bhop.cfg on every surf map; the new one judges the link, not its target.
        link = zipfile.ZipInfo('cfg/lobby/mode_surf.cfg')
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        z.writestr(link, 'mode_bhop.cfg')
    j = json.loads((src / 'surf_joutsenlaulu.json').read_text(encoding='utf-8'))
    j['maxVelocity'] = 200000
    (d / 'surf_joutsenlaulu.json').write_text(json.dumps(j))
    c = gd / 'data/maps/zones/curated'
    c.mkdir(parents=True)
    j = json.loads((src / 'surf_santorini.json').read_text(encoding='utf-8'))
    j['maxVelocity'] = 6100
    (c / 'surf_santorini.json').write_text(json.dumps(j))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--server', type=pathlib.Path, required=True)
    ap.add_argument('--qwprogs', type=pathlib.Path, required=True)
    ap.add_argument('--out', type=pathlib.Path, required=True)
    ap.add_argument('--control', action='store_true')
    ap.add_argument('--port', type=int, default=27618)
    ap.add_argument('--timeout', type=int, default=420)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    rig = pathlib.Path(tempfile.mkdtemp(prefix='p841-', dir=a.out))
    gd = rig / 'ftesurf'
    gd.mkdir()
    made = []
    try:
        shutil.copyfile(ROOT / 'default.fmf', rig / 'default.fmf')
        for name in JUNCTIONS:
            s = CONTENT / 'ftesurf' / name
            if s.is_dir():
                subprocess.run(['cmd', '/c', 'mklink', '/J', str(gd / name), str(s)],
                               check=True, capture_output=True)
                made.append(gd / name)
        shutil.copyfile(a.qwprogs, gd / 'qwprogs.dat')
        for f in ('fs_addons.default.txt',):
            shutil.copyfile(ROOT / 'ftesurf' / f, gd / f)
        shutil.copyfile(ROOT / 'ftesurf/fs_addons.default.txt', gd / 'fs_addons.txt')
        for rel in subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', 'ftesurf/cfg'],
                                           text=True).splitlines():
            t = rig / rel
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, t)
        plant(gd)
        lines = ['cfg_save_auto 0', 'developer 1', 'log_dir logs', 'log_name p841caps',
                 'log_enable 1', 'waitms 1000']
        for i, (m, cur) in enumerate(ARMS):
            lines += ['set sv_zones_curated %d' % cur, 'map %s' % m, 'waitms 6000',
                      'echo P841 ARM %d %s %d' % (i, m, cur), 'sv_maxvelocity', 'movement',
                      'echo P841 END %d' % i]
        lines += ['waitms 500', 'quit']
        (gd / 'cfg/test').mkdir(parents=True, exist_ok=True)
        (gd / 'cfg/test/p841caps.cfg').write_text('\n'.join(lines) + '\n')
        proc = subprocess.run([str(a.server), '-basedir', str(rig), '-manifest',
                               str(rig / 'default.fmf'), '+sv_public', '0', '-port', str(a.port),
                               '+exec', 'cfg/test/p841caps.cfg'],
                              cwd=str(a.server.parent), timeout=a.timeout,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log = gd / 'logs/p841caps.log'
        if not log.is_file():
            print('FAIL: no server log (exit %s): the arm did not act' % proc.returncode)
            return 1
        text = re.sub(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', '',
                      log.read_text(errors='replace'), flags=re.M)
        ok = True
        for i, (m, cur) in enumerate(ARMS):
            blk = text.split('P841 ARM %d ' % i, 1)
            pre = text.split('P841 ARM %d ' % i, 1)[0].rsplit('P841 END %d' % (i - 1), 1)[-1] \
                if i else text.split('P841 ARM 0 ', 1)[0]
            if len(blk) < 2:
                print('FAIL %s: arm never reached' % m)
                ok = False
                continue
            body = blk[1].split('P841 END %d' % i, 1)[0]
            got = re.search(r'"sv_maxvelocity" is "([^"]*)"', body)
            want, hit = expect(gd, m, cur, a.control)
            if a.control and m == 'surf_santorini':
                want = 7000.0           # the old engine takes the packed map ruleset
            line = re.search(r'map ruleset: %s sv_maxvelocity (\S+) from (\S+)' % re.escape(m), pre)
            warn = re.search(r'zones: %s asks maxVelocity (\S+), this server runs sv_maxvelocity (\S+)'
                             % re.escape(m), pre)
            res = got is not None and abs(float(got[1]) - want) < 0.001
            if a.control:
                res = res and line is None
            else:
                res = res and ((line is not None and float(line[1]) == want) if hit else line is None)
            # Planted files: each must leave its own line.
            if not a.control:
                res = res and 'cvars from cfg/lobby/mode_surf.cfg' not in pre and \
                    'cfg/lobby/mode_surf.cfg is not in a trusted directory - not read' in pre
                if m == 'surf_boreas':      # packed: the engine reads it as absent, QC times with it
                    res = res and warn is not None and warn[1] == '9000' and \
                        'data/maps/zones/local/surf_boreas.json is not in a trusted directory' in pre
                elif m == 'surf_dune':      # the engine's file has a region QC cannot build
                    res = res and warn is not None and warn[2] == '7777'
                elif m == 'surf_joutsenlaulu':  # out of range: unset on both sides
                    res = res and warn is None and 'maxVelocity is not 1..100000 - ignored' in pre
                elif m == 'surf_santorini':     # the packed map ruleset is not read
                    res = res and 'cfg/maps/map_surf_santorini.cfg is not in a trusted directory - not read' in pre
            else:                           # the control proves the link and the pack were live
                res = res and 'cvars from cfg/lobby/mode_surf.cfg' in pre
            print('%s %-18s curated %d: cap %s want %g; ruleset line %s; qc warning %s'
                  % ('ok  ' if res else 'FAIL', m, cur, got[1] if got else None, want,
                     '%s %s' % (line[1], line[2]) if line else '-',
                     '%s/%s' % (warn[1], warn[2]) if warn else '-'))
            ok = ok and res
        bad = [w for w in ('QC VM error', 'stack overflow', "Couldn't load") if w in text]
        if bad:
            print('FAIL: %s in the log' % bad)
            ok = False
        print('P841 %s: %s' % ('CONTROL' if a.control else 'SUBJECT', 'PASS' if ok else 'FAIL'))
        print('log:', log)
        return 0 if ok else 1
    finally:
        for p in made:
            if not p.lstat().st_file_attributes & 0x400:
                raise RuntimeError('Refusing removal: not our junction: %s' % p)
            p.rmdir()
        print('retained overlay (data/ and logs only):', rig)


if __name__ == '__main__':
    sys.exit(main())
