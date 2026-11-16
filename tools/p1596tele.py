"""P1596 falsifier: a bhop door resets a player who stands on it, and a teleport lands the feet on the
destination under every hull.  Owned dedicated server + headless client on bhop_1n5an3 (door *1 over
trigger *136 -> t1 at -256 -384 96); positions are the server's own `cmd viewpos` replies.

  p1596tele.py --runtime <new dir under an OWNER.md root> --source <qc tree with a built rig> \
      --progs <dir with qwprogs.dat/csprogs.dat> --engine <dir with fteqwsv64/fteqw64 + hl2 plugin> \
      --profile default|ag-100 --port 27587 [--expect old]

Run under rig.lock.  --expect old grades the control (main before P1596): no door reset, and a GoldSrc
teleport lands the centre on the destination."""
import argparse, json, re, shutil, socket, subprocess, sys, time
from pathlib import Path

MAPS = Path(r'C:/Program Files (x86)/Steam/steamapps/common/Momentum Mod Playtest/momentum/maps')
MAP = 'bhop_1n5an3'
DEST = (-256.0, -384.0, 96.0)
DOOR_TOP = 64.0
POS = re.compile(r'setpos (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) -?[\d.]+ -?[\d.]+ -?[\d.]+\s*$')   # viewpos's reply, not our command


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for k in ('runtime', 'source', 'progs', 'engine'):
        ap.add_argument('--' + k, type=Path, required=True)
    ap.add_argument('--profile', default='default')
    ap.add_argument('--port', type=int, default=27587)
    ap.add_argument('--expect', choices=('new', 'old'), default='new')
    # A rendered client predicts (a headless one never does): count prediction errors across the
    # direct teleport, where cl_triggers.qc's mirror lands the body.
    ap.add_argument('--rendered', action='store_true')
    ap.add_argument('--expect-prederr', choices=('none', 'some'), default='none')
    a = ap.parse_args()
    root = a.runtime.resolve()
    assert any((p / 'OWNER.md').is_file() for p in root.parents), 'runtime must sit under an OWNER.md root'
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1', a.port))
    root.mkdir(parents=True, exist_ok=False)
    lift = 36.0 if a.profile.startswith('ag-') or a.profile == 'cs16' else 0.0
    dirs = {}
    for side in ('server', 'client'):
        base = root / side
        game = base / 'ftesurf'
        (game / 'maps').mkdir(parents=True)
        shutil.copy2(a.source / 'default.fmf', base / 'default.fmf')
        shutil.copytree(a.source / 'ftesurf/cfg', game / 'cfg')
        for c in (game / 'cfg').rglob('*.cfg'):
            c.write_text(re.sub(r'https?://[^\s"]+', 'http://127.0.0.1:1', c.read_text(errors='replace')))
        shutil.copy2(MAPS / (MAP + '.bsp'), game / 'maps' / (MAP + '.bsp'))
        for f in ('qwprogs.dat', 'csprogs.dat'):
            shutil.copy2(a.progs / f, game / f)
        dirs[side] = base
    safe = 'set lobby_enable 0\nset lobby_master "http://127.0.0.1:1"\nset lobby_dir "http://127.0.0.1:1"\nsv_public 0\n'
    (dirs['server'] / 'ftesurf/p1596-server.cfg').write_text(
        'exec cfg/default.cfg\n' + safe + 'log_enable 1\nlog_name p1596sv\ndeveloper 1\nsv_cheats 1\n'
        'sv_movementprofile ' + ('' if a.profile == 'default' else a.profile) + '\nmap ' + MAP + '\n')
    (dirs['client'] / 'ftesurf/p1596-client.cfg').write_text(
        'cfg_save_auto 0\n' + safe + 'log_enable 1\nlog_name p1596cl\ncl_download 0\ncl_idlefps 0\ncl_maxfps 100\nset vid_headless_sleep 0\n'
        'connect 127.0.0.1:' + str(a.port) + '\n')
    common = ['-plugin', '-noreset', '-nobrowse', '-nohome', '-nosound', '-ip', '127.0.0.1',
              '+set', 'forceqmenu', '0', '+set', 'update_enabled', '0', '+set', 'update_autocheck', '0']
    sv = [str(a.engine / 'fteqwsv64.exe'), *common, '-basedir', str(dirs['server']), '-manifest',
          str(dirs['server'] / 'default.fmf'), '-port', str(a.port), '+exec', 'p1596-server.cfg']
    cl = [str(a.engine / 'fteqw64.exe'), *common, '-basedir', str(dirs['client']), '-manifest',
          str(dirs['client'] / 'default.fmf'), '-port', str(a.port + 1),
          *(['+set', 'vid_renderer', 'gl', '+set', 'vid_fullscreen', '0', '+set', 'vid_width', '640', '+set', 'vid_height', '480']
            if a.rendered else ['+set', 'vid_renderer', 'headless']),
          '+exec', 'p1596-client.cfg']
    out = {'profile': a.profile, 'expect': a.expect, 'argv': [sv, cl]}
    procs = []
    try:
        svlog = (root / 'server-console.log').open('x')
        clpath = dirs['client'] / 'ftesurf/logs/p1596cl.log'      # the console goes to the log, not stdout
        cllog = (root / 'client-console.log').open('x')
        procs.append(subprocess.Popen(sv, cwd=dirs['server'], stdin=subprocess.PIPE, stdout=svlog,
                                      stderr=subprocess.STDOUT, creationflags=0x08000000))
        time.sleep(4)
        client = subprocess.Popen(cl, cwd=dirs['client'], stdin=subprocess.PIPE, stdout=cllog,
                                  stderr=subprocess.STDOUT, creationflags=0x08000000)
        procs.append(client)

        def send(line):
            client.stdin.write((line + '\n').encode())
            client.stdin.flush()

        def cvar(name, wait=6):
            seen = len(clpath.read_text(errors='replace').splitlines()) if clpath.is_file() else 0
            send(name)
            pat = re.compile(r'"' + name + r'" is "(-?[\d.]+)"')
            end = time.monotonic() + wait
            while time.monotonic() < end:
                for ln in (clpath.read_text(errors='replace').splitlines()[seen:] if clpath.is_file() else []):
                    m = pat.search(ln)
                    if m:
                        return float(m.group(1))
                time.sleep(0.2)
            raise AssertionError('no reply for ' + name)

        def viewpos(label, wait=6):
            seen = len(clpath.read_text(errors='replace').splitlines()) if clpath.is_file() else 0
            send('cmd viewpos')
            end = time.monotonic() + wait
            while time.monotonic() < end:
                lines = clpath.read_text(errors='replace').splitlines()[seen:] if clpath.is_file() else []
                for ln in lines:
                    m = POS.search(ln.strip())
                    if m:
                        out[label] = [float(v) for v in m.groups()]
                        return out[label]
                time.sleep(0.2)
            raise AssertionError('no viewpos reply for ' + label)

        # viewpos answers before the spawn too (0 0 0): wait for a placed body (~9 s of client map load).
        end = time.monotonic() + 90
        while True:
            try:
                if viewpos('spawn', 3) != [0.0, 0.0, 0.0]:
                    break
            except AssertionError:
                pass
            assert time.monotonic() < end, 'client never spawned'
            time.sleep(1)
        time.sleep(1)
        # A: stand on door *1 (feet 1 above its top), still, for 1 s.
        send('cmd setpos -256 -576 %g' % (DOOR_TOP + 1 + lift))
        time.sleep(1.0)
        viewpos('door')
        # B: a fall into trigger *136 beside the doors, from 102 u above its top (~0.5 s), so the
        # setpos snap (never predicted) is counted before the teleport the mirror predicts.
        if a.rendered:
            send('cl_prederror 0.5')
        send('cmd setpos -100 -800 %g' % (160 + lift))
        time.sleep(0.25)
        if a.rendered:
            out['prederr_before'] = cvar('cl_prederror_count')
        time.sleep(1.0)
        viewpos('tele')
        if a.rendered:
            out['prederr_after'] = cvar('cl_prederror_count')
        send('+forward')
        time.sleep(0.5)
        send('-forward')
        time.sleep(0.3)
        viewpos('walked')
    finally:
        for p in procs:
            try:
                p.stdin.write(b'quit\n')
                p.stdin.flush()
            except OSError:
                pass
        for p in procs:
            try:
                p.wait(timeout=8)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=5)
    svtext = (dirs['server'] / 'ftesurf/logs/p1596sv.log').read_text(errors='replace')
    out['bhopdoor_lines'] = [ln for ln in svtext.splitlines() if 'bhopdoor:' in ln][:6]
    # The subject's own landings (developer prints, P1596 build only); t1 floats 32 u above its floor,
    # so the viewpos a second later is the settled body, not the landing.
    vec = re.compile(r"(?:to|at) '?(-?[\d.]+) (-?[\d.]+) (-?[\d.]+)")     # %v prints without quotes here
    out['landings'] = [[float(v) for v in vec.search(ln).groups()] for ln in svtext.splitlines()
                       if ('teleport: ' in ln or 'bhopdoor:' in ln) and vec.search(ln)]
    want_z = DEST[2] + 1 + lift
    at_dest = lambda p: abs(p[0] - DEST[0]) < 0.5 and abs(p[1] - DEST[1]) < 0.5
    checks = {}
    if a.expect == 'new':
        checks['door reset printed'] = any('-- reset at' in ln for ln in out['bhopdoor_lines'])
        checks['door reset settled at t1 (%s)' % out['door']] = at_dest(out['door'])
        checks['every landing feet+1 on t1 (want z %.2f): %s' % (want_z, out['landings'])] = \
            len(out['landings']) >= 3 and all(at_dest(p) and abs(p[2] - want_z) < 0.05 for p in out['landings'])
    else:
        checks['control: still on the door (%s)' % out['door']] = abs(out['door'][0] + 256) < 2 and abs(out['door'][1] + 576) < 2
    checks['the trigger teleported to t1 (%s)' % out['tele']] = at_dest(out['tele'])
    if a.rendered:
        d = out['prederr_after'] - out['prederr_before']
        out['prederr_delta'] = d
        checks['prediction errors across the teleport: %g (want %s)' % (d, a.expect_prederr)] = \
            (d == 0) if a.expect_prederr == 'none' else (d > 0)
    moved = ((out['walked'][0] - out['tele'][0]) ** 2 + (out['walked'][1] - out['tele'][1]) ** 2) ** 0.5
    out['moved'] = moved
    checks['walks off the destination (%.1f u)' % moved] = moved > 10 or (a.expect == 'old' and lift > 0)
    out['checks'] = checks
    (root / 'result.json').write_text(json.dumps(out, indent=2))
    for k, v in checks.items():
        print(('PASS ' if v else 'FAIL ') + k)
    print('positions', {k: out[k] for k in ('spawn', 'door', 'tele', 'walked')})
    for ln in out['bhopdoor_lines']:
        print('  ' + ln)
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
