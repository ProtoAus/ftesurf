"""P1478 rig driver: Jargon courses on a real dedicated server + windowed client, graded on the game's own lines.

  python -B jgcourse.py --out <fresh dir under this root> --progs <build dir> --map surf_shape
      --rec data/online/surf_shape/bonus_1/x.rec=C:/FTESurf/ftesurf/data/online/... (copied into the fixture)
      --plan "<demo> <words>" (repeatable: `tas autosurf <demo> plan <words>`, the reply recorded)
      --chain "<demo> <words>"  (`tas autosurf <demo> <words>`, waits for finished / stuck / stopped)
      --stopafter K             (stop the chain once it has saved stretch K for Continue)
      --cont "<track> <leg> <words>" (then `tas autosurf continue ...`, waits again)

Takes C:/FTESurf-worktrees/rig.lock (this process's pid) for the run; waits for a quiet machine first.
"""
from pathlib import Path
import sys, time, re, json, shutil, socket, argparse, datetime, subprocess, hashlib, ctypes, os
ROOT = Path(r'C:\FTESurf')
MOM = Path(r'C:/Program Files (x86)/Steam/steamapps/common/Momentum Mod Playtest/momentum/maps')
sys.path.insert(0, str(ROOT / 'tools'))
from spec_chat_smoke import Peer   # noqa: E402

p = argparse.ArgumentParser()
p.add_argument('--out', type=Path, required=True); p.add_argument('--progs', type=Path, required=True)
p.add_argument('--svexe', type=Path, default=Path(r'C:\FTEQuake\fteqwsv64.exe')); p.add_argument('--clexe', type=Path, default=ROOT / 'ftesurf64.exe')
p.add_argument('--map', required=True); p.add_argument('--port', type=int, default=27613)
p.add_argument('--rec', action='append', default=[], help='rel=src: a replay copied into the fixture gamedir at rel')
p.add_argument('--plan', action='append', default=[]); p.add_argument('--chain', default='')
p.add_argument('--stopafter', type=int, default=0); p.add_argument('--cont', default='')
p.add_argument('--budget', type=float, default=900); p.add_argument('--developer', type=int, default=0)
p.add_argument('--shots', default='', help='client screenshots at these seconds into the chain, comma separated')
p.add_argument('--clcmd', action='append', default=[], help='client lines before the tests (e.g. "tas optimizer")')
p.add_argument('--panelshot', action='store_true', help='open the TAS panel and take a screenshot before the tests')
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


def take_lock():
    quiet = 0
    while True:   # quiet first (no game 20 s, no lock, 2.5 GB free), then the lock, then look again
        if LOCK.exists() or games() or freemb() < 2500:
            quiet = 0; time.sleep(5); continue
        quiet += 5
        if quiet < 20: time.sleep(5); continue
        try: LOCK.mkdir()
        except FileExistsError: quiet = 0; continue
        (LOCK / 'owner.txt').write_text('ftesurf-16 jargon-courses pid=%d since=%s for=P1478 %s\n' % (
            os.getpid(), datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'), a.out.name))
        if games(): drop_lock(); quiet = 0; continue
        return


def drop_lock():
    (LOCK / 'owner.txt').unlink()
    LOCK.rmdir()


def prepare(name):
    base = a.out / name; game = base / 'ftesurf'
    for folder in ('glsl', 'scripts', 'particles'):
        if (ROOT / 'ftesurf' / folder).is_dir(): shutil.copytree(ROOT / 'ftesurf' / folder, game / folder)
    for folder in ('fonts', 'ui'):
        if (ROOT / 'ftesurf/gfx' / folder).is_dir(): shutil.copytree(ROOT / 'ftesurf/gfx' / folder, game / 'gfx' / folder)
    for folder in ('cfg', 'maps/zones/local', 'logs', 'data', 'downloads/csprogsvers'): (game / folder).mkdir(parents=True)
    (game / 'data/consent.txt').write_text('version 4\n')
    shutil.copy2(MOM / f'{a.map}.bsp', game / f'maps/{a.map}.bsp')
    shutil.copy2(ROOT / f'ftesurf/maps/zones/local/{a.map}.json', game / f'maps/zones/local/{a.map}.json')
    for f in ('qwprogs.dat', 'menu.dat', 'csprogs.dat'): shutil.copy2(a.progs / f, game / f)
    shutil.copy2(ROOT / 'ftesurf/cfg/default.cfg', game / 'cfg/default.cfg')
    (game / 'models').mkdir(parents=True, exist_ok=True)
    for f in (ROOT / 'ftesurf/models').glob('player*'):
        if f.is_file(): shutil.copy2(f, game / 'models' / f.name)
    for spec in a.rec:
        rel, src = spec.split('=', 1)
        (game / rel).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, game / rel)
    shutil.copy2(ROOT / 'fteplug_hl2_x64.dll', base / 'fteplug_hl2_x64.dll')
    (base / 'default.fmf').write_text('FTEMANIFEST 1\nGAME FTESurfP1478Fixture\nBASEGAME ftesurf\nDISABLEHOMEDIR 1\n'
                                      'MAINCONFIG p1478-unused\nset sv_mintic 0.015\nset sv_maxtic 0.015\nset cl_netfps 66.6667\n')
    subprocess.run([sys.executable, '-B', str(ROOT / 'tools/seed_csprogs.py'), str(game / 'csprogs.dat')], check=True, capture_output=True)
    d = game / 'cfg/default.cfg'; t = d.read_text()
    if 'set vid_fullscreen        1' in t: d.write_text(t.replace('set vid_fullscreen        1', 'set vid_fullscreen        0'))
    return base


ENDS = r'tas autosurf: (?:finished[^\n]*|stuck[^\n]*|stopped[^\n]*|the saved run[^\n]*|nothing saved[^\n]*|the loaded run[^\n]*)'
r = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'map': a.map, 'svexe': [str(a.svexe), sha(a.svexe)[:8]],
     'clexe': [str(a.clexe), sha(a.clexe)[:8]], 'progs': {n: sha(a.progs / n)[:8] for n in ['qwprogs.dat', 'csprogs.dat', 'menu.dat']},
     'plans': [], 'chain': None}
a.out.mkdir(parents=True, exist_ok=False)
peers = []
take_lock()
try:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sk: sk.bind(('127.0.0.1', a.port))
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs', 'log_name probe', 'log_readable 1',
              'cl_idlefps 0', 'cl_maxfps 100', 'cl_netfps 100', 'cl_threadedphysics 0', 'set run_resume 0', 'set lobby_dir ""',
              'set lobby_master ""', 'set lobby_enable 0', 'set cl_run_upload 0', 'set cl_board_url ""', 'sv_public 0',
              'sensitivity 0', 'set m_accel 0']
    for side in ['sv', 'cl']:
        base = prepare(side)
        lines = common + ([f'sv_port {a.port}', 'sv_playerslots 4', 'sv_maxclients 4', 'sv_demoAutoRecord 0',
                           'log_developer 1', 'pm_physicsmode 1', 'pm_ticrate 0.015', 'sv_tickparts 1', 'set sv_gamemode surf',
                           'set rec_stream 0', 'sv_cheats 1', f'developer {a.developer}', f'map {a.map}'] if side == 'sv' else
                          ['cl_hid 0', 'vid_renderer gl', 'developer 1', 'name CourseProbe', f'connect 127.0.0.1:{a.port}'])
        (base / 'ftesurf/probe.cfg').write_text('\n'.join(lines) + '\n')
        peer = Peer(a.svexe if side == 'sv' else a.clexe, base, 'probe.cfg', side == 'sv', headless=False); peers.append(peer)
        if side == 'sv': sv = peer; sv.wait(r'Server spawned\.', timeout=180)
        else: cl = peer; cl.wait('FTESurf CSQC loaded', timeout=180); time.sleep(3)
    cl.send('menu_restart; ui_close; cmd zone_goto 0'); time.sleep(2)
    cl.send('tas pause'); cl.wait('movement paused', timeout=10); time.sleep(.5)
    for line in a.clcmd: cl.send(line); time.sleep(1.5)
    if a.panelshot:
        cl.send('tas optimizer'); time.sleep(3); cl.send('screenshot'); time.sleep(2.5); cl.send('tas menu'); time.sleep(1)
    for pl in a.plan:
        off = len(cl.text()); cl.send(f'tas autosurf {pl}')
        try: m = cl.wait(r'tas autosurf: [^\n]*', off, 30).group(0)
        except RuntimeError: m = '(no reply)'
        time.sleep(.5)
        rows = re.findall(r'tas autosurf: [^\n]*', cl.text()[off:])
        print(f'  plan {pl}\n    -> ' + '\n    -> '.join(rows), flush=True)
        r['plans'].append({'cmd': pl, 'reply': rows})
    if a.chain:
        t0 = time.monotonic(); shots = sorted(float(x) for x in a.shots.split(',') if x)
        off = len(cl.text()); cl.send(f'tas autosurf {a.chain}')
        stopped = False
        while time.monotonic() - t0 < a.budget:
            t = cl.text()[off:]
            if shots and time.monotonic() - t0 >= shots[0]: shots.pop(0); cl.send('screenshot')
            if a.stopafter and not stopped and re.search(rf'saved for Continue: [^\n]*to stretch {a.stopafter} of', t):
                cl.send('tas autosurf stop'); stopped = True
            if re.search(ENDS, t): break
            time.sleep(1)
        time.sleep(1)
        rows = re.findall(r'tas autosurf: [^\n]*|tas project: [^\n]*|tas: legal start[^\n]*|tas: the run started[^\n]*', cl.text()[off:])
        r['chain'] = {'cmd': a.chain, 'secs': round(time.monotonic() - t0), 'lines': rows}
        print('  chain ' + a.chain + f' ({r["chain"]["secs"]} s)\n    ' + '\n    '.join(rows), flush=True)
        if a.cont:
            time.sleep(2); t0 = time.monotonic()
            off = len(cl.text()); cl.send(f'tas autosurf continue {a.cont}')
            while time.monotonic() - t0 < a.budget:
                if re.search(ENDS, cl.text()[off:]): break
                time.sleep(1)
            time.sleep(1)
            rows = re.findall(r'tas autosurf: [^\n]*|tas project: [^\n]*|tas: legal start[^\n]*', cl.text()[off:])
            r['cont'] = {'cmd': a.cont, 'secs': round(time.monotonic() - t0), 'lines': rows}
            print('  continue ' + a.cont + f' ({r["cont"]["secs"]} s)\n    ' + '\n    '.join(rows), flush=True)
    time.sleep(1)
finally:
    for peer in reversed(peers):
        try: peer.stop()
        except Exception as e: print('stop:', e)
    drop_lock()
    for f in a.out.rglob('identity.pfx'): f.unlink()
    (a.out / 'result.json').write_text(json.dumps(r, indent=1))
    print('result', a.out / 'result.json')
