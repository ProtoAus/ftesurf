"""P1443 stage 3 on a real surf map: surf_null's drop onto ramp 0. From the start zone, TAS steps walk east off
the platform; once falling outside the zone, `tas optimize 128 <side> board flick energy fast` searches the drop,
the board and the start of the ride by rollout (candidates that miss the ramp meet reset teleports and are cut),
then plays the best through the real mover. Pass: it finishes on its best, the replay equals the search, and the
candidate landing check is bit-equal. Reports energy at the end (speed worth at the start height).
"""
from pathlib import Path
import sys, time, re, json, hashlib, shutil, socket, argparse, datetime, subprocess
ROOT = Path(r'C:\FTESurf')
MOM = Path(r'C:/Program Files (x86)/Steam/steamapps/common/Momentum Mod Playtest/momentum/maps')
sys.path.insert(0, str(ROOT / 'tools'))
from spec_chat_smoke import Peer   # noqa: E402
p = argparse.ArgumentParser()
p.add_argument('--out', type=Path, required=True); p.add_argument('--progs', type=Path, required=True)
p.add_argument('--svexe', type=Path, required=True); p.add_argument('--clexe', type=Path, default=ROOT / 'ftesurf64.exe')
p.add_argument('--port', type=int, default=27618); p.add_argument('--walk', type=int, default=110)
a = p.parse_args()
assert a.out.is_absolute() and a.progs.is_absolute()
assert any((x / 'OWNER.md').is_file() for x in a.out.parents)
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sk: sk.bind(('127.0.0.1', a.port))
a.out.mkdir(parents=True, exist_ok=False)
peers = []; checks = []
def sha(f): return hashlib.sha256(Path(f).read_bytes()).hexdigest()
r = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'svexe': [str(a.svexe), sha(a.svexe)],
     'progs': {n: sha(a.progs / n) for n in ['qwprogs.dat', 'csprogs.dat', 'menu.dat']}, 'checks': checks}
def check(name, ok, data=None):
    checks.append({'name': name, 'pass': bool(ok), 'data': data}); print(('PASS ' if ok else 'FAIL ') + name, data if not ok else '', flush=True); assert ok, name
def prepare(name):
    base = a.out / name; game = base / 'ftesurf'
    for folder in ('glsl', 'scripts', 'particles'):
        if (ROOT / 'ftesurf' / folder).is_dir(): shutil.copytree(ROOT / 'ftesurf' / folder, game / folder)
    for folder in ('fonts', 'ui'):
        if (ROOT / 'ftesurf/gfx' / folder).is_dir(): shutil.copytree(ROOT / 'ftesurf/gfx' / folder, game / 'gfx' / folder)
    for folder in ('cfg', 'maps/zones/local', 'logs', 'data', 'downloads/csprogsvers'): (game / folder).mkdir(parents=True)
    (game / 'data/consent.txt').write_text('version 4\n')
    shutil.copy2(MOM / 'surf_null.bsp', game / 'maps/surf_null.bsp')
    shutil.copy2(ROOT / 'ftesurf/maps/zones/local/surf_null.json', game / 'maps/zones/local/surf_null.json')
    for f in ('qwprogs.dat', 'menu.dat', 'csprogs.dat'): shutil.copy2(a.progs / f, game / f)
    shutil.copy2(ROOT / 'ftesurf/cfg/default.cfg', game / 'cfg/default.cfg')
    shutil.copy2(ROOT / 'fteplug_hl2_x64.dll', base / 'fteplug_hl2_x64.dll')
    (base / 'default.fmf').write_text('FTEMANIFEST 1\nGAME FTESurfP1443Fixture\nBASEGAME ftesurf\nDISABLEHOMEDIR 1\n'
                                      'MAINCONFIG p1443-unused\nset sv_mintic 0.015\nset sv_maxtic 0.015\nset cl_netfps 66.6667\n')
    subprocess.run([sys.executable, str(ROOT / 'tools/seed_csprogs.py'), str(game / 'csprogs.dat')], check=True, capture_output=True)
    d = game / 'cfg/default.cfg'; t = d.read_text()
    if 'set vid_fullscreen        1' in t: d.write_text(t.replace('set vid_fullscreen        1', 'set vid_fullscreen        0'))
    return base
statuspat = r'tas: paused (\d+) pending (\d+) completed (\d+) request (\d+) native (\d+) fault (\d+)'
def status():
    time.sleep(.3); m = cl.query('tas status', statuspat); return tuple(map(int, m.groups()))
def tick():
    time.sleep(.3); return int(cl.query('tas status', r'tas: timeline tick (\d+)')[1])
def grant(line, count, timeout=60):
    before = status(); cl.send(line); end = time.monotonic() + timeout
    while True:
        now = status()
        if now[1] == 0 and now[2] == before[2] + count and now[3] == before[3] + 1: return now
        assert now[5] == 0 and time.monotonic() < end, (line, before, now)
def endpoint():
    off = len(cl.text()); cl.send('cmd viewpos')
    m = cl.wait(r'setpos ([\d.-]+) ([\d.-]+) ([\d.-]+)', off); v = cl.wait(r'velocity ([\d.-]+) ([\d.-]+) ([\d.-]+)', off)
    return [float(x) for x in m.groups() + v.groups()]
BEST = r'tas optimize: best (left|right) turn ([\d.]+) deg/tick over (\d+) ticks: (exit|energy) ([\d.]+) u/s \((\d+) candidates\); paused at (\d+)'
ROLL = r'tas optimize: rollout check: (\d+) landings predicted \((\d+) bit-equal\)[^\n]*'
def optimize(line):
    off = len(cl.text()); t0 = time.monotonic(); cl.send(f'tas optimize {line}')
    m = cl.wait(BEST + r'|tas optimize: stopped[^\n]*', off, 400)
    wall = time.monotonic() - t0
    time.sleep(1.0)
    return m, cl.text()[off:], wall
def back(n):
    time.sleep(.3); off = len(cl.text()); cl.send(f'tas back {n}'); cl.wait(rf'tas: back {n} to tick', off, 20); time.sleep(.8)
try:
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs', 'log_name probe', 'log_readable 1',
              'cl_idlefps 0', 'cl_maxfps 100', 'cl_netfps 100', 'cl_threadedphysics 0', 'set run_resume 0', 'set lobby_dir ""',
              'set lobby_master ""', 'set lobby_enable 0', 'set cl_run_upload 0', 'set cl_board_url ""', 'sv_public 0',
              'sensitivity 0', 'set m_accel 0']
    for side in ['sv', 'cl']:
        base = prepare(side)
        lines = common + ([f'sv_port {a.port}', 'sv_playerslots 4', 'sv_maxclients 4', 'sv_demoAutoRecord 0', 'developer 1',
                           'log_developer 1', 'pm_physicsmode 1', 'pm_ticrate 0.015', 'sv_tickparts 1', 'set sv_gamemode surf',
                           'set rec_stream 0', 'map surf_null'] if side == 'sv' else
                          ['cl_hid 0', 'vid_renderer gl', 'developer 1', 'name NullProbe', f'connect 127.0.0.1:{a.port}'])
        (base / 'ftesurf/probe.cfg').write_text('\n'.join(lines) + '\n')
        peer = Peer(a.svexe if side == 'sv' else a.clexe, base, 'probe.cfg', side == 'sv', headless=False); peers.append(peer)
        if side == 'sv': sv = peer; sv.wait(r'Server spawned\.', timeout=180)
        else: cl = peer; cl.wait('FTESurf CSQC loaded', timeout=180); time.sleep(3)
    cl.send('menu_restart; ui_close; cmd zone_goto 0'); time.sleep(2)
    e = endpoint(); r['zone'] = e
    cl.send('tas pause'); cl.wait('movement paused', timeout=10); time.sleep(.3)
    check('acting TAS session', status()[4] == 1, status())
    # walk east (yaw 0) at full forward until out of the zone (x > -11392) and falling
    for i in range(40):
        grant('tas next manual 450 0 0 0 0 10', 10, 60)
        e0 = endpoint()
        if e0[0] > -11380 and e0[5] < -50: break
    e0 = endpoint(); r['start'] = e0; h = tick()
    print('      start', e0, 'tick', h, flush=True)
    check('out of the start zone and falling', e0[0] > -11392 and e0[5] < -50, e0)
    results = {}
    for side in ('left', 'right'):
        m, t, w = optimize(f'128 {side} board flick energy fast')
        rc = re.search(ROLL, t)
        results[side] = (m.group(0), w, rc.group(0) if rc else None, re.findall(r'tas optimize: with[^\n]*', t),
                         re.findall(r'tas optimize: rollout meets [^\n]*', t)[:3])
        print(f'      {side}:', m.group(0), f'{w:.1f} s', '|', rc.group(0) if rc else 'no check', flush=True)
        check(f'{side}: finished on its best', m.group(1) == side, m.group(0))
        check(f'{side}: the replay is the search', 'world moved' not in t and 'differs from the search' not in t, t[-400:])
        check(f'{side}: the played best was predicted bit for bit', rc and rc.group(1) == rc.group(2) and int(rc.group(1)) >= 1,
              rc and rc.group(0))
        e1 = endpoint(); results[side] += (e1,)
        back(128); check(f'{side}: back at the start', tick() == h, (h, tick()))
    r['results'] = results
    r['result'] = 'PASS'
except BaseException as e: r['result'] = 'FAIL'; r['failure'] = str(e); raise
finally:
    for peer in reversed(peers): peer.stop()
    r['owned_peers_stopped'] = all(peer.proc.poll() is not None for peer in peers)
    (a.out / 'report.json').write_text(json.dumps(r, indent=2, default=str))
