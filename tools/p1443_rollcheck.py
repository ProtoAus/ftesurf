"""P1443 falsifier: every `tas optimize` candidate is predicted by tas_rollout before its tape plays;
the real mover's landing must equal the prediction (the optimizer prints the worst gap).

Adapted from the P1088 arm (stage6/artifacts/p1088_optimize_socket.py): bhop_eazy fixture, walk out
of the moved start, `tas pause`. A ground search (8 ticks from the pause) and an air search (24 ticks
after a jump). --control runs the installed server exe, which has no tas_rollout: no check line.
"""
from pathlib import Path
import sys, time, re, json, hashlib, shutil, socket, argparse, datetime
ROOT = Path(r'C:\FTESurf')
sys.path.insert(0, str(ROOT / 'tools'))
import p840clock as clock          # noqa: E402
from spec_chat_smoke import Peer   # noqa: E402
p = argparse.ArgumentParser()
p.add_argument('--out', type=Path, required=True); p.add_argument('--progs', type=Path, required=True)
p.add_argument('--svexe', type=Path, required=True); p.add_argument('--clexe', type=Path, default=ROOT / 'ftesurf64.exe')
p.add_argument('--port', type=int, default=27618); p.add_argument('--control', action='store_true')
a = p.parse_args()
assert a.out.is_absolute() and a.progs.is_absolute(), 'absolute paths only (Peer runs from C:/FTESurf)'
assert any((x / 'OWNER.md').is_file() for x in a.out.parents)
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sk: sk.bind(('127.0.0.1', a.port))
a.out.mkdir(parents=True, exist_ok=False)
peers = []; checks = []
def sha(f): return hashlib.sha256(Path(f).read_bytes()).hexdigest()
r = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'control': a.control,
     'svexe': [str(a.svexe), sha(a.svexe)], 'clexe': [str(a.clexe), sha(a.clexe)],
     'progs': {n: sha(a.progs / n) for n in ['qwprogs.dat', 'csprogs.dat', 'menu.dat']}, 'checks': checks}
def check(name, ok, data=None):
    checks.append({'name': name, 'pass': bool(ok), 'data': data}); print(('PASS ' if ok else 'FAIL ') + name, data if not ok else '', flush=True); assert ok, name
statuspat = r'tas: paused (\d+) pending (\d+) completed (\d+) request (\d+) native (\d+) fault (\d+)'
def status():
    time.sleep(.3); m = cl.query('tas status', statuspat); return tuple(map(int, m.groups()))
def tick():
    time.sleep(.3); return int(cl.query('tas status', r'tas: timeline tick (\d+)')[1])
def grant(line, count):
    before = status(); cl.send(line); end = time.monotonic() + 45
    while True:
        now = status()
        if now[1] == 0 and now[2] == before[2] + count and now[3] == before[3] + 1: return now
        assert now[5] == 0 and time.monotonic() < end, (line, before, now)
def endpoint():
    off = len(cl.text()); cl.send('cmd viewpos')
    m = cl.wait(r'setpos ([\d.-]+) ([\d.-]+) ([\d.-]+)', off); v = cl.wait(r'velocity ([\d.-]+) ([\d.-]+) ([\d.-]+)', off)
    return [float(x) for x in m.groups() + v.groups()]
CAND = r'tas optimize: (\d+)  turn ([\d.]+) deg/tick -> ([\d.]+) u/s'
BEST = r'tas optimize: best (left|right) turn ([\d.]+) deg/tick over (\d+) ticks: exit ([\d.]+) u/s \((\d+) candidates\); paused at (\d+)'
ROLL = r'tas optimize: rollout check: (\d+) landings predicted \((\d+) bit-equal\), worst ([\d.]+) u and ([\d.]+) u/s off([^\n]*)'
EACH = r'tas optimize: rollout (\d+) off by ([\d.]+) u, ([\d.]+) u/s'
def optimize(n, side):
    off = len(cl.text()); cl.send(f'tas optimize {n} {side}')
    m = cl.wait(BEST + r'|tas optimize: stopped[^\n]*', off, 300)
    time.sleep(1.0)
    text = cl.text()[off:]
    return m, text
try:
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs', 'log_name probe', 'log_readable 1',
              'cl_idlefps 0', 'cl_maxfps 100', 'cl_netfps 100', 'cl_threadedphysics 0', 'set run_resume 0', 'set lobby_dir ""',
              'set lobby_master ""', 'set lobby_enable 0', 'set cl_run_upload 0', 'set cl_board_url ""', 'sv_public 0',
              'sensitivity 0', 'set m_accel 0', 'cl_forwardspeed 70', 'cl_sidespeed 70']
    for side in ['sv', 'cl']:
        base = clock.prepare(a.out, side, a.progs, a.progs / 'csprogs.dat')
        z = base / 'ftesurf/maps/zones/local/bhop_eazy.json'; z.write_text(z.read_text().replace('-272', '400').replace('-240', '432'))
        d = base / 'ftesurf/cfg/default.cfg'; t = d.read_text()
        if 'set vid_fullscreen        1' in t:
            d.write_text(t.replace('set vid_fullscreen        1', 'set vid_fullscreen        0'))
        lines = common + ([f'sv_port {a.port}', 'sv_playerslots 4', 'sv_maxclients 4', 'sv_demoAutoRecord 0', 'developer 1',
                           'log_developer 1', 'pm_physicsmode 1', 'pm_ticrate 0.015', 'sv_tickparts 1', 'set sv_gamemode surf',
                           'set rec_stream 0', 'map bhop_eazy'] if side == 'sv' else
                          ['cl_hid 0', 'vid_renderer gl', 'developer 1', 'name RolloutProbe', f'connect 127.0.0.1:{a.port}'])
        (base / 'ftesurf/probe.cfg').write_text('\n'.join(lines) + '\n')
        exe = a.svexe if side == 'sv' else a.clexe
        peer = Peer(exe, base, 'probe.cfg', side == 'sv', headless=False); peers.append(peer)
        if side == 'sv': sv = peer; sv.wait(r'Server spawned\.')
        else: cl = peer; cl.wait('FTESurf CSQC loaded'); time.sleep(2)
    cl.send('menu_restart; ui_close; cmd zone_goto 0'); time.sleep(1); cl.send('+forward'); deadline = time.monotonic() + 15
    while endpoint()[0] <= -330:
        assert time.monotonic() < deadline, 'start walk failed'; time.sleep(.1)
    cl.send('-forward; tas pause'); cl.wait('movement paused', timeout=10); time.sleep(.3)
    check('acting TAS session', status()[4] == 1, status())
    # ground: 8 ticks from the pause
    h0 = tick(); m0, t0 = optimize(8, 'left'); r['ground'] = [m0.group(0), re.findall(EACH, t0), re.findall(ROLL, t0)]
    check('ground search finished', m0.group(1) == 'left', m0.group(0))
    rc0 = re.search(ROLL, t0)
    if a.control:
        check('control: no rollout check without the builtin', rc0 is None and not re.findall(EACH, t0), t0[-400:])
        r['result'] = 'PASS'; raise SystemExit(0)
    check('ground: every landing predicted', rc0 and int(rc0.group(1)) == int(m0.group(5)), rc0 and rc0.group(0))
    check('ground: the rollout is the real mover, bit for bit', int(rc0.group(2)) == int(rc0.group(1)), rc0.group(0))
    cl.send('tas back 8'); time.sleep(1.5)
    # air: a jump, then 24 ticks
    grant('tas next manual 31 -71 13 23 5 12', 12)
    e0 = endpoint(); r['air_start'] = e0
    check('airborne with speed', e0[2] > 64.5 and (e0[3] ** 2 + e0[4] ** 2) ** .5 > 40, e0)
    m1, t1 = optimize(24, 'left'); r['air'] = [m1.group(0), re.findall(EACH, t1), re.findall(ROLL, t1)]
    rc1 = re.search(ROLL, t1)
    check('air: every landing predicted', rc1 and int(rc1.group(1)) == int(m1.group(5)), rc1 and rc1.group(0))
    check('air: the rollout is the real mover, bit for bit', int(rc1.group(2)) == int(rc1.group(1)), rc1.group(0))
    # speed: rollouts from the paused body, timed by the server's wall clock
    BENCH = r'tas rollbench: (\d+) rollouts of (\d+) ticks \((\d+) ticks\) in ([\d.]+) s: (\d+) rollouts/s, (\d+) ticks/s'
    r['bench'] = []
    for n, c in ((128, 1000), (600, 300)):
        off = len(cl.text()); cl.send(f'cmd tas rollbench {n} {c}')
        b = cl.wait(BENCH + r'|tas rollbench: refused[^\n]*', off, 120)
        r['bench'].append(b.group(0)); print('     ', b.group(0), flush=True)
    check('rollbench ran', all('rollouts/s' in x for x in r['bench']), r['bench'])
    r['result'] = 'PASS'
except SystemExit: pass
except BaseException as e: r['result'] = 'FAIL'; r['failure'] = str(e); raise
finally:
    for peer in reversed(peers): peer.stop()
    r['owned_peers_stopped'] = all(peer.proc.poll() is not None for peer in peers)
    (a.out / 'report.json').write_text(json.dumps(r, indent=2))
