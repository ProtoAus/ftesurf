"""P1443 stage 3: `tas optimize ... fast` (candidates scored by tas_rollout, only the best played) against the
played search from the same airborne start (bhop_eazy fixture, as p1443_rollcheck.py), plus an energy search.

Pass: the fast search ends paused on its best with the replay equal to the search (no "world moved"), takes a
fraction of the played search's wall time, and scores at least the played search's exit speed.
"""
from pathlib import Path
import sys, time, re, json, hashlib, socket, argparse, datetime
ROOT = Path(r'C:\FTESurf')
sys.path.insert(0, str(ROOT / 'tools'))
import p840clock as clock          # noqa: E402
from spec_chat_smoke import Peer   # noqa: E402
p = argparse.ArgumentParser()
p.add_argument('--out', type=Path, required=True); p.add_argument('--progs', type=Path, required=True)
p.add_argument('--svexe', type=Path, required=True); p.add_argument('--clexe', type=Path, default=ROOT / 'ftesurf64.exe')
p.add_argument('--port', type=int, default=27618)
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
BEST = r'tas optimize: best (left|right) turn ([\d.]+) deg/tick over (\d+) ticks: (exit|energy) ([\d.]+) u/s \((\d+) candidates\); paused at (\d+)'
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
                          ['cl_hid 0', 'vid_renderer gl', 'developer 1', 'name FastProbe', f'connect 127.0.0.1:{a.port}'])
        (base / 'ftesurf/probe.cfg').write_text('\n'.join(lines) + '\n')
        peer = Peer(a.svexe if side == 'sv' else a.clexe, base, 'probe.cfg', side == 'sv', headless=False); peers.append(peer)
        if side == 'sv': sv = peer; sv.wait(r'Server spawned\.')
        else: cl = peer; cl.wait('FTESurf CSQC loaded'); time.sleep(2)
    cl.send('menu_restart; ui_close; cmd zone_goto 0'); time.sleep(1); cl.send('+forward'); deadline = time.monotonic() + 15
    while endpoint()[0] <= -330:
        assert time.monotonic() < deadline, 'start walk failed'; time.sleep(.1)
    cl.send('-forward; tas pause'); cl.wait('movement paused', timeout=10); time.sleep(.3)
    check('acting TAS session', status()[4] == 1, status())
    grant('tas next manual 31 -71 13 23 5 12', 12)
    h = tick(); e0 = endpoint(); r['start'] = [h, e0]
    check('airborne with speed', e0[2] > 64.5 and (e0[3] ** 2 + e0[4] ** 2) ** .5 > 40, e0)
    mf, tf, wf = optimize('24 left board flick fast'); r['fast'] = [mf.group(0), wf, re.findall(r'tas optimize: with[^\n]*', tf)]
    print('      fast:', mf.group(0), f'{wf:.1f} s', flush=True)
    check('fast finished on its best', mf.group(1) == 'left' and int(mf.group(7)) == h + 24, mf.group(0))
    check('fast: the replay is the search (no world-moved warning)', 'differs from the search' not in tf and 'world moved' not in tf, tf[-500:])
    back(24); check('back at the start', tick() == h, (h, tick()))
    ms, ts, ws = optimize('24 left board flick'); r['played'] = [ms.group(0), ws, re.findall(r'tas optimize: with[^\n]*', ts)]
    print('    played:', ms.group(0), f'{ws:.1f} s', flush=True)
    check('played search finished', ms.group(1) == 'left', ms.group(0))
    check('fast scores at least the played search', float(mf.group(5)) >= float(ms.group(5)) - 0.05, (mf.group(5), ms.group(5)))
    check('fast takes a fraction of the time', wf < ws / 4, (wf, ws))
    back(24); check('back at the start again', tick() == h, (h, tick()))
    me, te, we = optimize('24 left energy fast'); r['energy'] = [me.group(0), we]
    print('    energy:', me.group(0), f'{we:.1f} s', flush=True)
    check('energy search finished on its best', me.group(4) == 'energy' and 'world moved' not in te, me.group(0))
    r['result'] = 'PASS'
except BaseException as e: r['result'] = 'FAIL'; r['failure'] = str(e); raise
finally:
    for peer in reversed(peers): peer.stop()
    r['owned_peers_stopped'] = all(peer.proc.poll() is not None for peer in peers)
    (a.out / 'report.json').write_text(json.dumps(r, indent=2))
