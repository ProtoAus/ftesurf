"""P1449: a target-guided chain of fast energy searches down surf_null. Targets are a demo's boarding points (the
surfledger JSON's board_o, ramp by ramp). Each link sets `tas target`, runs `tas optimize 128 <side> board flick
energy fast` for both sides, plays the better (reached beats not, then energy at the reach; else the nearer miss),
and when reached steps back to the reach tick so the next link starts at the boarding point. A target not reached
in --tries links is skipped. Prints each reach's energy beside the demo's at its own board.
"""
from pathlib import Path
import sys, time, re, json, math, hashlib, shutil, socket, argparse, datetime, subprocess
ROOT = Path(r'C:\FTESurf')
MOM = Path(r'C:/Program Files (x86)/Steam/steamapps/common/Momentum Mod Playtest/momentum/maps')
sys.path.insert(0, str(ROOT / 'tools'))
from spec_chat_smoke import Peer   # noqa: E402
p = argparse.ArgumentParser()
p.add_argument('--out', type=Path, required=True); p.add_argument('--progs', type=Path, required=True)
p.add_argument('--svexe', type=Path, required=True); p.add_argument('--clexe', type=Path, default=ROOT / 'ftesurf64.exe')
p.add_argument('--targets', type=Path, required=True); p.add_argument('--demo', type=Path, required=True)
p.add_argument('--port', type=int, default=27618); p.add_argument('--ramps', type=int, default=3)
p.add_argument('--tries', type=int, default=5); p.add_argument('--radius', type=int, default=160)
p.add_argument('--budget', type=float, default=500, help='seconds of chaining before stopping')
p.add_argument('--modes', default='board flick,zigzag board', help='comma-separated search shapes tried per side')
a = p.parse_args()
MODES = [x.strip() for x in a.modes.split(',') if x.strip()]
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
Z0 = 13376.03
def ve(o, v): return math.sqrt(max(0.0, v[0]**2 + v[1]**2 + v[2]**2 + 1600 * (o[2] - Z0)))
def demo_rows():
    rows = {}
    for line in open(a.demo, encoding='latin-1'):
        q = line.split()
        if q and (q[0][0] == '-' or q[0][0].isdigit()):
            try: v = [float(x) for x in q[:7]]
            except ValueError: continue
            rows[round(v[0] / 0.015)] = v
    return rows
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
    (base / 'default.fmf').write_text('FTEMANIFEST 1\nGAME FTESurfP1449Fixture\nBASEGAME ftesurf\nDISABLEHOMEDIR 1\n'
                                      'MAINCONFIG p1449-unused\nset sv_mintic 0.015\nset sv_maxtic 0.015\nset cl_netfps 66.6667\n')
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
REACH = r'tas optimize: target reached at tick (\d+) of (\d+) \(([\d.]+) u from it\), (?:energy|speed) ([\d.]+) u/s there'
MISS = r'tas optimize: target not reached: closest ([\d.]+) u at tick (\d+) of (\d+)'
def optimize(line):
    off = len(cl.text()); cl.send(f'tas optimize {line}')
    m = cl.wait(BEST + r'|tas optimize: stopped[^\n]*', off, 300)
    time.sleep(1.0)
    t = cl.text()[off:]
    rm = re.search(REACH, t); mm = re.search(MISS, t)
    return m, t, rm, mm
def back(n):
    if n <= 0: return
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
                          ['cl_hid 0', 'vid_renderer gl', 'developer 1', 'name ChainProbe', f'connect 127.0.0.1:{a.port}'])
        (base / 'ftesurf/probe.cfg').write_text('\n'.join(lines) + '\n')
        peer = Peer(a.svexe if side == 'sv' else a.clexe, base, 'probe.cfg', side == 'sv', headless=False); peers.append(peer)
        if side == 'sv': sv = peer; sv.wait(r'Server spawned\.', timeout=180)
        else: cl = peer; cl.wait('FTESurf CSQC loaded', timeout=180); time.sleep(3)
    cl.send('menu_restart; ui_close; cmd zone_goto 0'); time.sleep(2)
    cl.send('tas pause'); cl.wait('movement paused', timeout=10); time.sleep(.3)
    check('acting TAS session', status()[4] == 1, status())
    for i in range(40):
        grant('tas next manual 450 0 0 0 0 10', 10, 60)
        e0 = endpoint()
        if e0[0] > -11380 and e0[5] < -50: break
    check('out of the start zone and falling', e0[0] > -11380 and e0[5] < -50, e0)
    targets = json.load(open(a.targets)); D = demo_rows()
    chain = []; t_start = time.monotonic()
    print('      ramp  try  side  result                          | demo at its board', flush=True)
    for k, tg in enumerate(targets[:a.ramps]):
        o = tg['o']
        n = tg['n']; off = len(cl.text()); cl.send(f'tas target {o[0]:.1f} {o[1]:.1f} {o[2]:.1f} {a.radius} {n[0]:.4f} {n[1]:.4f} {n[2]:.4f}')
        cl.wait(r"tas target: '", off, 10)
        demo_tick = round(tg['t'] / 0.015); dr = D.get(demo_tick)
        dv = ve(dr[1:4], dr[4:7]) if dr else float('nan')
        reached = False
        for tr in range(a.tries):
            if time.monotonic() - t_start > a.budget: break
            h = tick(); results = []
            for side in ('right', 'left'):
                for mode in MODES:
                    how = f'{side} {mode}'
                    m, t, rm, mm = optimize(f'128 {how} energy fast')
                    if not m.group(0).startswith('tas optimize: best'):
                        results.append((how, None, None, m.group(0)))
                        if tick() != h: back(tick() - h)
                        continue
                    if rm: results.append((how, (1, float(rm.group(4))), int(rm.group(1)), m.group(0)))
                    elif mm: results.append((how, (0, -float(mm.group(1))), int(mm.group(2)), m.group(0)))
                    else: results.append((how, None, None, m.group(0)))
                    back(tick() - h)
            ok = [x for x in results if x[1] is not None]
            if not ok:
                print(f'      {k:4d} {tr:4d}  both stopped: {results[0][3][:80]}', flush=True); break
            side, key, kt, line = max(ok, key=lambda x: x[1])
            m, t, rm, mm = optimize(f'128 {side} energy fast')
            check(f'ramp {k} try {tr}: the replay is the search', 'world moved' not in t and 'differs from the search' not in t, t[-300:])
            if rm:
                kt = int(rm.group(1)); back(128 - kt)
                e1 = endpoint(); T = tick(); v = ve(e1[:3], e1[3:])
                chain.append({'ramp': k, 'try': tr, 'side': side, 'tick': T, 'vE': v, 'pos': e1, 'demo_vE': dv, 'demo_tick': demo_tick})
                sp = math.hypot(e1[3], e1[4]); dsp = math.hypot(dr[4], dr[5]) if dr else float('nan')
                print(f'      {k:4d} {tr:4d} {side:>18}  reached at run tick {T}, vE {v:7.1f}, speed {sp:6.0f}   | tick {demo_tick}, vE {dv:7.1f}, speed {dsp:6.0f}', flush=True)
                reached = True; break
            e1 = endpoint()
            print(f'      {k:4d} {tr:4d} {side:>18}  miss, closest {(-key[1]):.0f} u; now at {tuple(round(x) for x in e1[:3])} speed {math.hypot(e1[3], e1[4]):.0f}', flush=True)
        if not reached:
            chain.append({'ramp': k, 'reached': False})
            print(f'      {k:4d}  not reached in {a.tries} links; stopping the chain', flush=True)
            break
    r['chain'] = chain
    r['result'] = 'PASS'
except BaseException as e: r['result'] = 'FAIL'; r['failure'] = str(e); raise
finally:
    for peer in reversed(peers): peer.stop()
    r['owned_peers_stopped'] = all(peer.proc.poll() is not None for peer in peers)
    (a.out / 'report.json').write_text(json.dumps(r, indent=2, default=str))
