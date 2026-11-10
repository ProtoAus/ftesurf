"""P1483 Jargon benchmark: fixed courses, several chains each, one headless fixture per map, graded on the game's own lines.

  python -B jgbench.py --out <fresh dir under this root> --progs <build dir> [--runs 3] [--budget 600]
      [--courses all|name,name] [--svset "set tas_jargon_rules 0;..."] [--effort "tries 2 rideknots low"] [--seed 1]

Per chain: finished (and time), furthest stretch of N, the energy share (ours/guide) at each stretch reached, backtracks,
effort steps, minutes. Writes runs.json and prints a summary table. Takes C:/FTESurf-worktrees/rig.lock per map and
waits for a quiet machine; a HOLD file in this task root pauses it between maps.
"""
from pathlib import Path
import sys, time, re, json, shutil, socket, argparse, datetime, subprocess, hashlib, ctypes, os, statistics
ROOT = Path(r'C:\FTESurf')
TASK = Path(r'C:\FTESurf-worktrees\jargon-courses-1111a')
MOM = Path(r'C:/Program Files (x86)/Steam/steamapps/common/Momentum Mod Playtest/momentum/maps')
ONLINE = ROOT / 'ftesurf/data/online'
sys.path.insert(0, str(ROOT / 'tools'))
from spec_chat_smoke import Peer   # noqa: E402

# name: map, guide (relative to the game dir), course track, leg
COURSES = {
    't2s2': ('surf_tensor2', 'data/online/surf_tensor2/stage_2/00m12.570s_proto_r8.rec', 0, 2),
    't2s5': ('surf_tensor2', 'data/online/surf_tensor2/stage_5/00m23.565s_stotty_r48365.rec', 0, 5),
    'shb1': ('surf_shape', 'data/online/surf_shape/bonus_1/00m14.475s_x_r36649.rec', 1, 0),
    'mob4': ('surf_monolith', 'data/online/surf_monolith/bonus_4/00m23.850s_x_r21120.rec', 4, 0),
    'acb2': ('surf_aircontrol', 'data/online/surf_aircontrol/bonus_2/00m22.380s_hashy_r9401.rec', 2, 0),
}
p = argparse.ArgumentParser()
p.add_argument('--out', type=Path, required=True); p.add_argument('--progs', type=Path, required=True)
p.add_argument('--svexe', type=Path, default=Path(r'C:\FTEQuake\fteqwsv64.exe')); p.add_argument('--clexe', type=Path, default=ROOT / 'ftesurf64.exe')
p.add_argument('--port', type=int, default=27614); p.add_argument('--runs', type=int, default=3); p.add_argument('--budget', type=float, default=600)
p.add_argument('--courses', default='all'); p.add_argument('--svset', default=''); p.add_argument('--effort', default='tries 2 rideknots low')
p.add_argument('--seed', type=int, default=1, help='tas_jargon_seed of the first run; each run adds 1')
p.add_argument('--label', default='')
p.add_argument('--sameseed', action='store_true', help='every run the first seed (a learning arm: runs differ by what earlier runs saved)')
a = p.parse_args()
assert a.out.is_absolute() and a.progs.is_absolute()
assert any((x / 'OWNER.md').is_file() for x in a.out.parents)
LOCK = Path(r'C:\FTESurf-worktrees\rig.lock')
GAMES = ('ftesurf64.exe', 'fteqw64.exe', 'fteqwsv64.exe', 'worldofsurf.exe')


def sha(f): return hashlib.sha256(Path(f).read_bytes()).hexdigest()


def games():
    out = subprocess.run(['tasklist', '/fo', 'csv', '/nh'], capture_output=True, text=True).stdout.lower()
    return [g for g in GAMES if '"' + g + '"' in out]


def freemb():
    class M(ctypes.Structure):
        _fields_ = [('l', ctypes.c_ulong), ('load', ctypes.c_ulong), ('tot', ctypes.c_ulonglong), ('avail', ctypes.c_ulonglong),
                    ('a', ctypes.c_ulonglong), ('b', ctypes.c_ulonglong), ('c', ctypes.c_ulonglong), ('d', ctypes.c_ulonglong), ('e', ctypes.c_ulonglong)]
    m = M(); m.l = ctypes.sizeof(M); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.avail // (1024 * 1024)


def take_lock(what):
    quiet = 0
    while True:   # quiet first (no game 20 s, no lock, no HOLD, 2.5 GB free), then the lock, then look again
        if LOCK.exists() or (TASK / 'HOLD').exists() or games() or freemb() < 2500:
            quiet = 0; time.sleep(5); continue
        quiet += 5
        if quiet < 20: time.sleep(5); continue
        try: LOCK.mkdir()
        except FileExistsError: quiet = 0; continue
        (LOCK / 'owner.txt').write_text('ftesurf-16 jargon-bench pid=%d since=%s for=P1483 %s\n' % (
            os.getpid(), datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'), what))
        if games(): drop_lock(); quiet = 0; continue
        return


def drop_lock():
    (LOCK / 'owner.txt').unlink()
    LOCK.rmdir()


def prepare(base, mapname, guides):
    game = base / 'ftesurf'
    for folder in ('glsl', 'scripts', 'particles'):
        if (ROOT / 'ftesurf' / folder).is_dir(): shutil.copytree(ROOT / 'ftesurf' / folder, game / folder)
    for folder in ('fonts', 'ui'):
        if (ROOT / 'ftesurf/gfx' / folder).is_dir(): shutil.copytree(ROOT / 'ftesurf/gfx' / folder, game / 'gfx' / folder)
    for folder in ('cfg', 'maps/zones/local', 'logs', 'data', 'downloads/csprogsvers'): (game / folder).mkdir(parents=True)
    (game / 'data/consent.txt').write_text('version 4\n')
    shutil.copy2(MOM / f'{mapname}.bsp', game / f'maps/{mapname}.bsp')
    shutil.copy2(ROOT / f'ftesurf/maps/zones/local/{mapname}.json', game / f'maps/zones/local/{mapname}.json')
    for f in ('qwprogs.dat', 'menu.dat', 'csprogs.dat'): shutil.copy2(a.progs / f, game / f)
    shutil.copy2(ROOT / 'ftesurf/cfg/default.cfg', game / 'cfg/default.cfg')
    for g in guides:
        (game / g).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / 'ftesurf' / g, game / g)
    shutil.copy2(ROOT / 'fteplug_hl2_x64.dll', base / 'fteplug_hl2_x64.dll')
    (base / 'default.fmf').write_text('FTEMANIFEST 1\nGAME FTESurfP1483Fixture\nBASEGAME ftesurf\nDISABLEHOMEDIR 1\n'
                                      'MAINCONFIG p1483-unused\nset sv_mintic 0.015\nset sv_maxtic 0.015\nset cl_netfps 66.6667\n')
    subprocess.run([sys.executable, '-B', str(ROOT / 'tools/seed_csprogs.py'), str(game / 'csprogs.dat')], check=True, capture_output=True)
    d = game / 'cfg/default.cfg'; t = d.read_text()
    if 'set vid_fullscreen        1' in t: d.write_text(t.replace('set vid_fullscreen        1', 'set vid_fullscreen        0'))


ENDS = r'tas autosurf: (?:finished[^\n]*|stuck[^\n]*|stopped[^\n]*)'


def grade(text, secs):
    r = {'secs': round(secs), 'finished': None, 'time': None, 'stretch': 0, 'of': 0, 'shares': [], 'backs': 0, 'esc': 0, 'end': ''}
    for m in re.finditer(r'stretch (\d+) reached: (-?\d+) u/s at the guide\'s board height, the guide (\d+)', text):
        k, ours, guide = int(m.group(1)), float(m.group(2)), float(m.group(3))
        r['stretch'] = max(r['stretch'], k)
        if guide > 0: r['shares'].append((k, round(ours / guide, 4)))
    m = re.search(r'(\d+) stretches ahead', text)
    if m: r['of'] = int(m.group(1))
    r['backs'] = len(re.findall(r'backtrack \d+', text))
    r['esc'] = len(re.findall(r'trying harder', text))
    m = re.search(r'tas autosurf: finished (?:stage|bonus|the main)[^\n]* in ([0-9:.]+)', text)
    if m: r['finished'] = True; r['time'] = m.group(1)
    else: r['finished'] = False
    e = re.findall(ENDS, text)
    r['end'] = e[-1] if e else '(budget)'
    return r


courses = list(COURSES) if a.courses == 'all' else a.courses.split(',')
bymap = {}
for c in courses: bymap.setdefault(COURSES[c][0], []).append(c)
res = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'label': a.label, 'svset': a.svset, 'effort': a.effort,
       'progs': {n: sha(a.progs / n)[:8] for n in ['qwprogs.dat', 'csprogs.dat']}, 'runs': []}
a.out.mkdir(parents=True, exist_ok=False)
for mapname, cs in bymap.items():
    base = a.out / mapname
    take_lock(f'{a.out.name} {mapname}')
    peers = []
    try:
        for side in ('sv', 'cl'):
            prepare(base / side, mapname, [COURSES[c][1] for c in cs])
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sk: sk.bind(('127.0.0.1', a.port))
        common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs', 'log_name probe', 'log_readable 1',
                  'cl_idlefps 0', 'cl_maxfps 100', 'cl_netfps 100', 'cl_threadedphysics 0', 'set run_resume 0', 'set lobby_dir ""',
                  'set lobby_master ""', 'set lobby_enable 0', 'set cl_run_upload 0', 'set cl_board_url ""', 'sv_public 0']
        for side in ('sv', 'cl'):
            b = base / side
            lines = common + ([f'sv_port {a.port}', 'sv_playerslots 4', 'sv_maxclients 4', 'sv_demoAutoRecord 0', 'log_developer 1',
                               'pm_physicsmode 1', 'pm_ticrate 0.015', 'sv_tickparts 1', 'set sv_gamemode surf', 'set rec_stream 0',
                               'sv_cheats 1', 'developer 0', f'map {mapname}'] if side == 'sv' else
                              ['cl_hid 0', 'developer 0', 'name BenchProbe', f'connect 127.0.0.1:{a.port}'])
            (b / 'ftesurf/probe.cfg').write_text('\n'.join(lines) + '\n')
            pe = Peer(a.svexe if side == 'sv' else a.clexe, b, 'probe.cfg', side == 'sv', headless=True); peers.append(pe)
            if side == 'sv':
                sv = pe; sv.wait(r'Server spawned\.', timeout=240)
                for line in filter(None, (x.strip() for x in a.svset.split(';'))): sv.send(line)
            else:
                cl = pe; cl.wait('FTESurf CSQC loaded', timeout=240); time.sleep(3)
        cl.send('cmd zone_goto 0'); time.sleep(2)
        cl.send('tas pause'); cl.wait('movement paused', timeout=20); time.sleep(.5)
        for c in cs:
            _, guide, tr, leg = COURSES[c]
            for k in range(a.runs):
                sd = a.seed if a.sameseed else a.seed + k
                sv.send(f'set tas_jargon_seed {sd}'); time.sleep(.3)
                t0 = time.monotonic(); off = len(cl.text())
                cl.send(f'tas autosurf {guide} {a.effort} finish start course {tr} {leg}')
                while time.monotonic() - t0 < a.budget:
                    if re.search(ENDS, cl.text()[off:]): break
                    time.sleep(2)
                else:
                    cl.send('tas autosurf stop'); time.sleep(3)
                text = cl.text()[off:]
                g = grade(text, time.monotonic() - t0); g.update({'course': c, 'run': k, 'seed': sd})
                res['runs'].append(g)
                (a.out / 'runs.json').write_text(json.dumps(res, indent=1))
                print(f"{c} run {k}: {'FIN ' + g['time'] if g['finished'] else 'stretch %d/%d' % (g['stretch'], g['of'])} "
                      f"backs {g['backs']} esc {g['esc']} {g['secs']} s -- {g['end'][:80]}", flush=True)
                time.sleep(2)
    finally:
        for pe in reversed(peers):
            try: pe.stop()
            except Exception as ex: print('stop:', ex)
        drop_lock()
        for f in base.rglob('identity.pfx'): f.unlink()
        for sub in ('maps', 'glsl', 'gfx', 'particles', 'scripts'):     # fixtures, not evidence (logs and data stay)
            for side in ('sv', 'cl'):
                shutil.rmtree(base / side / 'ftesurf' / sub, ignore_errors=False) if (base / side / 'ftesurf' / sub).exists() else None
    time.sleep(45)      # a peer's turn between maps
# summary
print('\ncourse  fin   stretch(med)  share-at-last(med)  minutes(med)')
for c in courses:
    rs = [r for r in res['runs'] if r['course'] == c]
    if not rs: continue
    fin = sum(1 for r in rs if r['finished'])
    st = statistics.median([r['stretch'] / max(1, r['of']) for r in rs])
    sh = statistics.median([r['shares'][-1][1] for r in rs if r['shares']] or [0])
    mn = statistics.median([r['secs'] / 60 for r in rs])
    print(f'{c:6s}  {fin}/{len(rs)}   {st:.2f}          {sh:.3f}               {mn:.1f}')
(a.out / 'runs.json').write_text(json.dumps(res, indent=1))
