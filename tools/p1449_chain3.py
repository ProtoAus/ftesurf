"""P1449: a waypoint chain from a human's save. A practice save of the demo's own state a few samples before it
boards --first's ramp (sl_saveview: origin, velocity, angles) is loaded, then each ride is chased in halves --
its bottom (lowest point), its leave, the next ramp's board -- each a target on the ramp's face (Lex, 9 Nov:
the walk-off start was ~300 vE short, so ramp-to-ramp conversion is tested from a human's start).

A target-guided chain of fast energy searches down surf_null. Targets are a demo's boarding points (the
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
sys.path.insert(0, r'C:\FTESurf-worktrees\xhair-20261108-b8\qc1435\tools')   # surfledger.py at main
import surfledger   # noqa: E402
from spec_chat_smoke import Peer   # noqa: E402
p = argparse.ArgumentParser()
p.add_argument('--out', type=Path, required=True); p.add_argument('--progs', type=Path, required=True)
p.add_argument('--svexe', type=Path, required=True); p.add_argument('--clexe', type=Path, default=ROOT / 'ftesurf64.exe')
p.add_argument('--targets', type=Path, default=None); p.add_argument('--demo', type=Path, required=True)
p.add_argument('--port', type=int, default=27618); p.add_argument('--ramps', type=int, default=3)
p.add_argument('--backtrack', type=int, default=0, help='times a failed link may send the chain back to search the link before it again')
p.add_argument('--tries', type=int, default=5); p.add_argument('--radius', type=int, default=160)
p.add_argument('--budget', type=float, default=500, help='seconds of chaining before stopping')
p.add_argument('--ledger', type=Path, default=None, help='surfledger.py JSON of the demo (its segments are the rides)')
p.add_argument('--rides', choices=['ledger', 'physics'], default='ledger',
               help="physics: rides are the demo's contact stretches of 0.3 s or more (vz off free fall), for maps whose "
               "ramps bend between faces and the ledger splits one ride in two (surf_monolith)")
p.add_argument('--developer', type=int, default=0)
p.add_argument('--noviz', action='store_true', help='client tas_viz 0 (the search drawing off)')
p.add_argument('--shots', type=int, default=0, help='screenshots of the drawn search (pairs: mid-search, played)')
p.add_argument('--shot-after', type=float, default=12.0)
p.add_argument('--chase', default='', help='client chase camera: back,up (e.g. 400,250) for the shots')
p.add_argument('--sides', default='right,left', help='sides each try searches (curve: one is enough, its grid spans both)')
p.add_argument('--bench', action='store_true', help='time rollouts at the placed state (developer 1), then stop')
p.add_argument('--horizon', type=int, default=0, help='ticks a link searches (fast: up to 512, played as tapes); 0: the demo stretch x1.25 + 10')
p.add_argument('--seed', action='store_true', help="start each curve search from the demo's own command over the link (tas seed)")
p.add_argument('--mid-radius', type=int, default=300, help='radius of the mid-air waypoints (boards use --radius)')
p.add_argument('--hop', action='store_true', help="demo modes hold jump (pm_autobunny hops platforms), and each of the demo's "
               "platform hops between ramps is a waypoint just after it")
p.add_argument('--hop-tube', type=int, default=0, help='the tube for links that end at a hop and the link after one (0: --tube); '
               "a hop chain needs the demo's timing: 300 u let the platform link fly a wider arc, 90 u low")
p.add_argument('--hop-radius', type=int, default=100, help='radius of the hop waypoints (a jump within it)')
p.add_argument('--look', type=int, default=0, help='with --tube: ticks of the demo route past each waypoint a reach is scored on surviving '
               '(the horizon grows by as much)')
p.add_argument('--map', default='surf_null', help='the map (its .bsp from the Momentum maps folder, its zones from ftesurf/maps/zones/local)')
p.add_argument('--bsp', type=Path, default=None, help='the .bsp to use instead of <maps>/<map>.bsp')
p.add_argument('--tube', type=int, default=0, help="demo modes: candidates stay within this many units of the demo's path (0 off)")
p.add_argument('--finish', action='store_true', help="after the last ride, a waypoint at the demo's last sample (the end zone)")
p.add_argument('--midair', action='store_true', help="a waypoint at each flight's middle (no face), so steered flights follow the demo's route")
p.add_argument('--boards-only', action='store_true', help='each link is board to next board: ride and flight in one search')
p.add_argument('--bottoms', action='store_true', help="also a waypoint at each ride's lowest point (default: the ride is one link)")
p.add_argument('--demo-check', action='store_true', help="replay the demo's own inputs from the save to each waypoint, then stop")
p.add_argument('--lead', type=int, default=2, help='the save is this many samples before the demo boards the first ramp')
p.add_argument('--first', type=int, default=0, help='first target index (ramp) the chain aims for')
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
Z0 = None                                        # the demo's first row's height (demo_rows sets it)
def ve(o, v):
    q = v[0]**2 + v[1]**2 + v[2]**2 + 1600 * (o[2] - Z0)   # signed: the speed worth at the demo's start height
    return math.copysign(math.sqrt(abs(q)), q)
def demo_rows():
    rows = {}
    for line in open(a.demo, encoding='latin-1'):
        q = line.split()
        if q and (q[0][0] == '-' or q[0][0].isdigit()):
            try: v = [float(x) for x in q[:7]]
            except ValueError: continue
            rows[round(v[0] / 0.015)] = v
    global Z0
    if Z0 is None and rows: Z0 = rows[min(rows)][3]
    return rows
def prepare(name):
    base = a.out / name; game = base / 'ftesurf'
    for folder in ('glsl', 'scripts', 'particles'):
        if (ROOT / 'ftesurf' / folder).is_dir(): shutil.copytree(ROOT / 'ftesurf' / folder, game / folder)
    for folder in ('fonts', 'ui'):
        if (ROOT / 'ftesurf/gfx' / folder).is_dir(): shutil.copytree(ROOT / 'ftesurf/gfx' / folder, game / 'gfx' / folder)
    for folder in ('cfg', 'maps/zones/local', 'logs', 'data', 'downloads/csprogsvers'): (game / folder).mkdir(parents=True)
    (game / 'data/consent.txt').write_text('version 4\n')
    shutil.copy2(a.bsp or MOM / f'{a.map}.bsp', game / f'maps/{a.map}.bsp')
    if (ROOT / f'ftesurf/maps/zones/local/{a.map}.json').is_file():
        shutil.copy2(ROOT / f'ftesurf/maps/zones/local/{a.map}.json', game / f'maps/zones/local/{a.map}.json')
    for f in ('qwprogs.dat', 'menu.dat', 'csprogs.dat'): shutil.copy2(a.progs / f, game / f)
    shutil.copy2(ROOT / 'ftesurf/cfg/default.cfg', game / 'cfg/default.cfg')
    shutil.copy2(a.demo, game / 'data/tasdemo.rec')   # the server's tas demo reads it
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
BEST = r'tas optimize: best (left|right) turn (-?[\d.]+) deg/tick over (\d+) ticks: (exit|energy) (-?[\d.]+) u/s \((\d+) candidates\); paused at (\d+)'
REACH = r'tas optimize: target reached at tick (\d+) of (\d+) \(([\d.]+) u from it\), (?:energy|speed) (-?[\d.]+) u/s there'
MISS = r'tas optimize: target not reached: closest ([\d.]+) u at tick (\d+) of (\d+)'
SHOTS = []
def optimize(line):
    off = len(cl.text()); cl.send(f'tas optimize {line}')
    if a.shots and len(SHOTS) < a.shots:
        # the search drawn mid-way (cl_tasoptviz.qc), then once more when the best is played
        time.sleep(a.shot_after); cl.send('screenshot'); SHOTS.append(('search', line, time.monotonic()))
    m = cl.wait(BEST + r'|tas optimize: stopped[^\n]*', off, 300)
    time.sleep(1.0)
    if a.shots and len(SHOTS) < a.shots:
        cl.send('screenshot'); SHOTS.append(('played', line, time.monotonic())); time.sleep(2.5)
    t = cl.text()[off:]
    rm = re.search(REACH, t); mm = re.search(MISS, t)
    return m, t, rm, mm
def back(n):
    while n > 0:                                    # tas back takes 1..128
        c = min(128, n); n -= c
        time.sleep(.3); off = len(cl.text()); cl.send(f'tas back {c}'); cl.wait(rf'tas: back {c} to tick', off, 20); time.sleep(.8)
try:
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs', 'log_name probe', 'log_readable 1',
              'cl_idlefps 0', 'cl_maxfps 100', 'cl_netfps 100', 'cl_threadedphysics 0', 'set run_resume 0', 'set lobby_dir ""',
              'set lobby_master ""', 'set lobby_enable 0', 'set cl_run_upload 0', 'set cl_board_url ""', 'sv_public 0',
              'sensitivity 0', 'set m_accel 0']
    for side in ['sv', 'cl']:
        base = prepare(side)
        lines = common + ([f'sv_port {a.port}', 'sv_playerslots 4', 'sv_maxclients 4', 'sv_demoAutoRecord 0', 'developer 1',
                           'log_developer 1', 'pm_physicsmode 1', 'pm_ticrate 0.015', 'sv_tickparts 1', 'set sv_gamemode surf',
                           'set rec_stream 0', 'sv_cheats 1', f'developer {a.developer}', f'map {a.map}'] if side == 'sv' else
                          ['cl_hid 0', 'vid_renderer gl', 'developer 1', 'name ChainProbe'] + (['set tas_viz 0'] if a.noviz else []) + [f'connect 127.0.0.1:{a.port}'])
        (base / 'ftesurf/probe.cfg').write_text('\n'.join(lines) + '\n')
        peer = Peer(a.svexe if side == 'sv' else a.clexe, base, 'probe.cfg', side == 'sv', headless=False); peers.append(peer)
        if side == 'sv': sv = peer; sv.wait(r'Server spawned\.', timeout=180)
        else: cl = peer; cl.wait('FTESurf CSQC loaded', timeout=180); time.sleep(3)
    rows = []                                       # the demo's samples: t, origin, velocity, pitch, yaw
    for line in open(a.demo, encoding='latin-1'):
        q = line.split()
        if q and (q[0][0] == '-' or q[0][0].isdigit()):
            try: v = [float(x) for x in q[:14]]
            except ValueError: continue
            rows.append(v)
    if a.rides == 'ledger':
        assert a.ledger, '--rides ledger needs --ledger'
        L = json.load(open(a.ledger)); L = L[next(iter(L))]; segs = L['segments']
    # the demo's turn command per sample (sv_tasoptimize.qc SV_TASOptFollow's q): its strafe side and the
    # wish direction against the velocity before the sample's move; 0 where no side key is held
    kbs = []; kb = 0
    for line in open(a.demo, encoding='latin-1'):
        q = line.split()
        if q and q[0] == 'ksfbuttons' and len(q) >= 3: kb = int(q[2]); continue
        if q and (q[0][0] == '-' or q[0][0].isdigit()):
            try: [float(x) for x in q[:14]]
            except ValueError: continue
            kbs.append(kb)
    DQ = [0.0]
    for i in range(1, len(rows)):
        r0, r1 = rows[i - 1], rows[i]
        if r1[12] == 0: DQ.append(0.0); continue
        wy = math.radians(r1[8]) + (math.pi / 2 if r1[12] < 0 else -math.pi / 2)
        x = r0[4] * math.cos(wy) + r0[5] * math.sin(wy)
        DQ.append(max(-120.0, min(120.0, (1 if r1[12] < 0 else -1) * (30 - x))))
    def seed_knots(i0, H, K):
        # each knot: the demo's command averaged over its share of the link (i0: the demo sample the link starts on)
        out = []
        h = (H - 1) / (K - 1)
        for j in range(K):
            c = i0 + j * h
            lo, hi = int(max(i0, c - h / 2)), int(min(i0 + H - 1, c + h / 2))
            seg = [DQ[i] for i in range(lo, hi + 1) if 0 <= i < len(DQ)]
            out.append(sum(seg) / len(seg) if seg else 0.0)
        return out
    # waypoints: each ride's bottom (vz crosses 0 nearest the lowest point) and its leave on the ramp's
    # face, then the next ramp's board on its face -- a long ride in two halves (Lex, 9 Nov)
    # each waypoint's face: the plane the demo touches at that tick (a ride crosses many planes: the
    # board plane at the bottom of ramp 0 is not the one under the body there)
    class _NoPlanes:
        def find(self, n, d): return -1
    _, lrows = surfledger.read_rec(a.demo)
    lt, _ = surfledger.ledger(lrows, _NoPlanes(), 800, 150, 0.015, 30, 250, 16)
    def face(t, fallback):
        c = [k for k in lt if k['kind'] == 'clip' and k['n'] and k['n'][2] > 0.3 and abs(k['t'] - t) <= 0.05]
        if not c: return fallback, None
        k = min(c, key=lambda k: abs(k['t'] - t))
        return list(k['n']), k['t']
    if a.rides == 'physics':
        # a ride: samples whose vz is off free fall (g * dt a sample) for 0.3 s or more, entered falling
        # (a ground start or a platform hop is not one); its face from the demo's clip at the board
        segs = []; st = None
        for r0, r1 in zip(rows, rows[1:]):
            off = abs((r1[6] - r0[6]) + 800 * 0.015) > 1.5
            if off and st is None: st = r1
            if not off and st is not None:
                if r0[0] - st[0] >= 0.3 - 1e-6 and st[6] < -100:
                    n, _ = face(st[0], None)
                    if n: segs.append({'t_board': st[0], 't_leave': r0[0], 'n': n})
                st = None
        print('      rides from physics: ' + ', '.join(f"{x['t_board']:.2f}-{x['t_leave']:.2f}" for x in segs), flush=True)
    W = []
    for k in range(a.first, min(len(segs), a.first + a.ramps)):
        sg = segs[k]
        R = [x for x in rows if sg['t_board'] - 1e-6 <= x[0] <= sg['t_leave'] + 1e-6]
        if k > a.first:
            W.append(('board', k, R[0], sg['n']))
        lo = min(R, key=lambda x: x[3])
        if a.bottoms and R.index(lo) not in (0, len(R) - 1): W.append(('bottom', k, lo, sg['n']))
        if not a.boards_only: W.append(('leave', k, R[-1], sg['n']))
        if a.midair and k + 1 < len(segs):
            # the flight's middle (by time, leave to the next board), no face: steered flights follow the demo's route
            tm = (sg['t_leave'] + segs[k + 1]['t_board']) / 2
            W.append(('mid', k, min(rows, key=lambda x: abs(x[0] - tm)), None))
        if a.hop and k + 1 < len(segs):
            # a landing the demo hopped off between this ramp and the next (vz down -> up at one height): a
            # waypoint that asks for a jump near where it landed (floor normal) -- a point in the air after
            # it was reached by hopping at the platform's near edge, 240 u low at the next one (Lex: hop at
            # the end of the platform)
            fl = [x for x in rows if sg['t_leave'] < x[0] < segs[k + 1]['t_board']]
            for i in range(1, len(fl) - 7):
                # the landing sample can read vz 0 (a grounded tick) before the jump's sample
                if fl[i - 1][6] < -100 and fl[i][6] > -1 and any(x[6] > 150 for x in fl[i:i + 3])                         and abs(fl[i][3] - fl[i - 1][3]) < 40:
                    W.append(('hop', k, fl[i], [0.0, 0.0, 1.0]))
    if a.finish and a.first + a.ramps >= len(segs):
        W.append(('finish', len(segs), rows[-1], None))   # the run's last sample: in the end zone
    if a.first + a.ramps < len(segs):
        sg = segs[a.first + a.ramps]
        W.append(('board', a.first + a.ramps, next(x for x in rows if x[0] >= sg['t_board'] - 1e-6), sg['n']))
    W.sort(key=lambda w: w[2][0])                   # time order (hops, mids and boards interleave)
    W2 = []
    for (what, k, wr, n) in W:
        if n is None or what == 'hop':
            if what == 'hop': print(f'      waypoint hop {k}: demo t={wr[0]:.3f} o {tuple(round(x) for x in wr[1:4])} (a jump within {a.hop_radius} u)', flush=True)
            W2.append((what, k, wr, n)); continue
        fn, ft = face(wr[0], n)
        print(f'      waypoint {what} {k}: demo t={wr[0]:.3f} o {tuple(round(x) for x in wr[1:4])}; face from t={ft} '
              f'({sum(x * y for x, y in zip(fn, n)):.3f} against the board plane)', flush=True)
        W2.append((what, k, wr, fn))
    W = W2
    sg = segs[a.first]
    bi = next(i for i, x in enumerate(rows) if x[0] >= sg['t_board'] - 1e-6)
    sr = rows[bi - a.lead]                          # the save: a.lead samples before the demo boards
    r['save_row'] = sr[:10]
    cl.send('menu_restart; ui_close; cmd zone_goto 0'); time.sleep(2)
    cl.send('tas pause'); cl.wait('movement paused', timeout=10); time.sleep(.3)
    # the demo's state: setpos for the view, pe_state (P1404, sv_cheats) for origin and velocity before the
    # next move, then one TAS step on the demo's own input for that sample
    cl.send(f'cmd setpos {sr[1]:.6f} {sr[2]:.6f} {sr[3]:.6f} {sr[7]:.4f} {sr[8]:.4f} 0'); time.sleep(1)
    off = len(cl.text())
    cl.send(f'cmd pe_state -1 {sr[1]:.6f} {sr[2]:.6f} {sr[3]:.6f} {sr[4]:.6f} {sr[5]:.6f} {sr[6]:.6f}'); time.sleep(1)
    st = status(); r['after_pe_state'] = st
    applied = re.search(r'pe_state: on command', cl.text()[off:]) is not None
    kb = 0
    for line in open(a.demo, encoding='latin-1'):
        q = line.split()
        if q and q[0] == 'ksfbuttons' and len(q) >= 3: kb = int(q[2]); continue
        if q and (q[0][0] == '-' or q[0][0].isdigit()):
            try: t = float(q[0])
            except ValueError: continue
            if abs(t - sr[0]) < 1e-6: break
    bits = (1 if kb & 2 else 0) | (2 if kb & 4 else 0)
    print(f'      pe_state applied while paused: {applied}; status {st}', flush=True)
    before = st[2]
    cl.send(f'tas next manual {int(round(sr[11]))} {int(round(sr[12]))} {sr[7]:.4f} {sr[8]:.4f} {bits} 1')
    end = time.monotonic() + 20
    while True:
        st = status()
        if st[1] == 0 and st[2] >= before + 1: break
        assert st[5] == 0 and time.monotonic() < end, ('placement step', st)
    applied = applied or re.search(r'pe_state: on command', cl.text()[off:]) is not None
    check('pe_state landed', applied, cl.text()[off:][-400:])
    e0 = endpoint(); nr = rows[bi - a.lead + 1]; r['placed'] = e0
    print(f'      one tick after the save (demo t={nr[0]:.3f}): ours {tuple(round(x, 1) for x in e0[:3])} v {tuple(round(x, 1) for x in e0[3:])}'
          f'; demo {tuple(round(x, 1) for x in nr[1:4])} v {tuple(round(x, 1) for x in nr[4:7])}', flush=True)
    check('placed on the demo state, one tick on (a ducked demo is 8.5 u off: the save stands)', math.dist(e0[:3], nr[1:4]) < 12 and math.dist(e0[3:], nr[4:7]) < 60, (e0, nr[:7]))
    check('acting TAS session', status()[4] == 1, status())
    D = demo_rows()
    if a.bench:
        for n, c in ((24, 400), (194, 60), (194, 300)):
            off = len(cl.text()); cl.send(f'cmd tas rollbench {n} {c}')
            m = cl.wait(r'tas rollbench: [^\n]*', off, 120)
            print('      ' + m.group(0), flush=True)
        W = []
    if a.demo_check:
        # the demo's own inputs in this mover from the same state: what its line is worth here
        tnow = rows[bi - a.lead + 1][0]
        for (what, k, wr, n) in W:
            cnt = round((wr[0] - tnow) / 0.015)
            if cnt < 1: continue
            off = len(cl.text()); cl.send(f'tas demo tasdemo.rec {cnt} {tnow:.4f}')
            m = cl.wait(r'tas demo: (done[^\n]*?|stopped[^\n]*?) after (\d+) rows|tas demo: (cannot open|the optimizer)[^\n]*', off, 120)
            check(f'demo inputs to {what} {k}', m.group(0).startswith('tas demo: done') and int(m.group(2)) == cnt, m.group(0))
            e1 = endpoint(); v = ve(e1[:3], e1[3:]); dv = ve(wr[1:4], wr[4:7])
            print(f'      demo inputs to {what} {k} (t={wr[0]:.3f}, {cnt} ticks): ours {tuple(round(x) for x in e1[:3])} speed {math.hypot(e1[3], e1[4]):6.0f} vE {v:7.1f}'
                  f'  | demo {tuple(round(x) for x in wr[1:4])} speed {math.hypot(wr[4], wr[5]):6.0f} vE {dv:7.1f}  (off {math.dist(e1[:3], wr[1:4]):.1f} u)', flush=True)
            r.setdefault('demo_check', []).append({'point': f'{what} {k}', 'ours': e1, 'demo': wr[:7], 'vE': v, 'demo_vE': dv})
            tnow = wr[0]
        W = []
    if a.chase:
        cb, cu = a.chase.split(',')
        cl.send(f'chase_active 1; chase_back {cb}; chase_up {cu}; scr_sshot_type png'); time.sleep(1)
    chain = []; t_start = time.monotonic(); tprev = rows[bi - a.lead + 1][0]
    print('      point     try  side  result                          | demo there', flush=True)
    prev_what = 'board'
    i = 0; starts = {}; tprevs = {}; prevs = {}; backs = 0
    while i < len(W):
        what, k, wr, n = W[i]
        starts[i] = tick(); tprevs[i] = tprev; prevs[i] = prev_what
        # the horizon: the demo's own ticks for this stretch, with room (--horizon 0), or fixed
        H = a.horizon or min(768, max(16, round(1.25 * (wr[0] - tprev) / 0.015) + 10 + (a.look if a.tube else 0)))
        if 'demo' in a.modes.split():
            # a row's input produced it: the link's first input is the row after its state
            off = len(cl.text()); cl.send(f'tas demorows tasdemo.rec {tprev + 0.015:.4f}')
            m = cl.wait(r'tas demorows: (\d+) rows', off, 15)
            check(f'demo rows for {what} {k}', int(m.group(1)) >= H, m.group(0))
        if a.seed:
            km = re.search(r'curve (\d+)', a.modes); K = int(km.group(1)) if km else 8
            i0 = min(range(len(rows)), key=lambda i: abs(rows[i][0] - tprev)) + 1   # DQ[i]: the move from sample i-1 to i
            sk = seed_knots(i0, H, K)
            off = len(cl.text()); cl.send('tas seed ' + ' '.join(f'{x:.2f}' for x in sk))
            cl.wait(r'tas seed: \d+ knots kept', off, 10)
            print(f'      seed for {what} {k}: ' + ' '.join(f'{x:.0f}' for x in sk), flush=True)
        tprev = wr[0]
        o = wr[1:4]; off = len(cl.text())
        cl.send(f'tas target {o[0]:.1f} {o[1]:.1f} {o[2]:.1f} {a.hop_radius if what == "hop" else a.radius} {n[0]:.4f} {n[1]:.4f} {n[2]:.4f}' if n is not None
                else f'tas target {o[0]:.1f} {o[1]:.1f} {o[2]:.1f} {a.hop_radius if what == "hop" else a.mid_radius}')
        cl.wait(r"tas target: '", off, 10)
        demo_tick = round(wr[0] / 0.015); dr = D.get(demo_tick)
        dv = ve(dr[1:4], dr[4:7]) if dr else float('nan')
        tg = f'{what} {k}'
        reached = False
        for tr in range(a.tries):
            if time.monotonic() - t_start > a.budget: break
            h = tick(); results = []
            single = len(a.sides.split(',')) * len(MODES) == 1   # nothing to choose: keep the search's play
            for side in a.sides.split(','):
                for mode in MODES:
                    tb = a.hop_tube if a.hop_tube and (what == 'hop' or prev_what == 'hop') else a.tube
                    how = f'{side} {mode}' + (f' tube {tb}' if tb and 'demo' in mode.split() else '') \
                        + (' hop' if a.hop and 'demo' in mode.split() else '') \
                        + (f' look {a.look}' if a.look and tb and 'demo' in mode.split() else '')
                    m, t, rm, mm = optimize(f'{H} {how} energy fast')
                    if not m.group(0).startswith('tas optimize: best'):
                        results.append((how, None, None, m.group(0)))
                        if tick() != h: back(tick() - h)
                        continue
                    if rm: results.append((how, (1, float(rm.group(4))), int(rm.group(1)), m.group(0)))
                    elif mm: results.append((how, (0, -float(mm.group(1))), int(mm.group(2)), m.group(0)))
                    else: results.append((how, None, None, m.group(0)))
                    if single: kept = (m, t, rm, mm)
                    else: back(tick() - h)
            ok = [x for x in results if x[1] is not None]
            if not ok:
                print(f'      {tg:9} {tr:4d}  both stopped: {results[0][3][:80]}', flush=True); break
            side, key, kt, line = max(ok, key=lambda x: x[1])
            # the search is random (CEM): a second search is not a replay of the first
            m, t, rm, mm = kept if single else optimize(f'{H} {side} energy fast')
            check(f'{tg} try {tr}: the played best is the searched one', 'world moved' not in t and 'differs from the search' not in t
                  and 'the real move ended' not in t, t[-300:])
            if rm:
                kt = int(rm.group(1))
                if tick() - h > kt: back(tick() - h - kt)   # P1449: the best now plays to the reach tick
                e1 = endpoint(); T = tick(); v = ve(e1[:3], e1[3:])
                chain.append({'point': tg, 'try': tr, 'side': side, 'tick': T, 'vE': v, 'pos': e1, 'demo_vE': dv, 'demo_tick': demo_tick})
                sp = math.hypot(e1[3], e1[4]); dsp = math.hypot(dr[4], dr[5]) if dr else float('nan')
                print(f'      {tg:9} {tr:4d} {side:>18}  reached at run tick {T}, vE {v:7.1f}, speed {sp:6.0f}   | tick {demo_tick}, vE {dv:7.1f}, speed {dsp:6.0f}', flush=True)
                # the next link's demo rows (its commands, the tube) start where the demo came nearest this state
                near = min((x for x in rows if abs(x[0] - wr[0]) <= 2.0), key=lambda x: math.dist(x[1:4], e1[:3]))
                tprev = near[0]
                print(f'      {tg:9}      next link from demo t={tprev:.3f} ({math.dist(near[1:4], e1[:3]):.0f} u from here; the board was t={wr[0]:.3f})', flush=True)
                reached = True; break
            e1 = endpoint()
            print(f'      {tg:9} {tr:4d} {side:>18}  miss, closest {(-key[1]):.0f} u; now at {tuple(round(x) for x in e1[:3])} speed {math.hypot(e1[3], e1[4]):.0f}', flush=True)
            if tick() != h: back(tick() - h)   # the next try searches again from the link's start (the search is random)
        if not reached:
            if backs < a.backtrack and i > 0 and time.monotonic() - t_start <= a.budget:
                # back to the previous link's start and search it again: the search is random, and a
                # different state there may let this link through
                backs += 1
                print(f'      {tg:9}  not reached in {a.tries} tries; backtrack {backs}: {W[i - 1][0]} {W[i - 1][1]} again', flush=True)
                if tick() != starts[i - 1]: back(tick() - starts[i - 1])
                i -= 1; tprev = tprevs[i]; prev_what = prevs[i]
                if chain and chain[-1].get('point') == f'{W[i][0]} {W[i][1]}': chain.pop()
                continue
            chain.append({'point': tg, 'reached': False})
            print(f'      {tg:9}  not reached in {a.tries} tries; stopping the chain', flush=True)
            break
        prev_what = what
        i += 1
    r['chain'] = chain
    r['result'] = 'PASS'
except BaseException as e: r['result'] = 'FAIL'; r['failure'] = str(e); raise
finally:
    for peer in reversed(peers): peer.stop()
    r['owned_peers_stopped'] = all(peer.proc.poll() is not None for peer in peers)
    (a.out / 'report.json').write_text(json.dumps(r, indent=2, default=str))
