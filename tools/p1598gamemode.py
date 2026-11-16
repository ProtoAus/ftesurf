"""P1598 falsifier: `hud_gamemode` switches the movement profile in a game you host, and only there.

  p1598gamemode.py --runtime <new dir under an OWNER.md root> --source <qc tree> --progs <dir with
      qwprogs/csprogs/menu .dat> --engine <dir with fteqw64/fteqwsv64 + hl2 plugin> --phase local|remote|old
      [--port 27589] [--rendered]

local   a rendered local game on bhop_1n5an3: the panel opens (screenshot), digit 2 through the client's input
        chain (`vote key`) picks hl2-pre and its release is the panel's (no save), digit 4 picks ag-100, each
        reload's serverinfo carries the identity, `hud_gamemode 1` returns to default.
remote  a headless client on a dedicated server: the panel says "only in a game you host", a pick does nothing,
        and the engine's `movementprofile` refuses.
old     --engine without the command (P1591): the panel says it needs P1598's engine.
Run under rig.lock."""
import argparse, json, re, shutil, socket, subprocess, sys, time
from pathlib import Path

MAPS = Path(r'C:/Program Files (x86)/Steam/steamapps/common/Momentum Mod Playtest/momentum/maps')
MAP = 'bhop_1n5an3'
STATUS = re.compile(r'hud_gamemode: open (\d) mode (\d) (\S*) why "([^"]*)"')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for k in ('runtime', 'source', 'progs', 'engine'):
        ap.add_argument('--' + k, type=Path, required=True)
    ap.add_argument('--phase', choices=('local', 'remote', 'old'), required=True)
    ap.add_argument('--port', type=int, default=27589)
    a = ap.parse_args()
    root = a.runtime.resolve()
    assert any((p / 'OWNER.md').is_file() for p in root.parents), 'runtime must sit under an OWNER.md root'
    root.mkdir(parents=True, exist_ok=False)
    sides = ('client', 'server') if a.phase == 'remote' else ('client',)
    dirs = {}
    for side in sides:
        base = root / side
        game = base / 'ftesurf'
        (game / 'maps').mkdir(parents=True)
        shutil.copy2(a.source / 'default.fmf', base / 'default.fmf')
        shutil.copytree(a.source / 'ftesurf/cfg', game / 'cfg')
        for c in (game / 'cfg').rglob('*.cfg'):
            c.write_text(re.sub(r'https?://[^\s"]+', 'http://127.0.0.1:1', c.read_text(errors='replace')))
        shutil.copy2(MAPS / (MAP + '.bsp'), game / 'maps' / (MAP + '.bsp'))
        for f in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
            if (a.progs / f).is_file():
                shutil.copy2(a.progs / f, game / f)
        dirs[side] = base
    safe = 'set lobby_enable 0\nset lobby_master "http://127.0.0.1:1"\nset lobby_dir "http://127.0.0.1:1"\nsv_public 0\n'
    common = ['-plugin', '-noreset', '-nobrowse', '-nohome', '-nosound', '-ip', '127.0.0.1',
              '+set', 'forceqmenu', '0', '+set', 'update_enabled', '0', '+set', 'update_autocheck', '0']
    rendered = a.phase == 'local'
    clcfg = 'cfg_save_auto 0\nexec cfg/default.cfg\n' + safe + 'log_enable 1\nlog_name p1598cl\ncl_idlefps 0\ncl_maxfps 100\nset vid_headless_sleep 0\n'
    clcfg += 'rcon_password p1598-owned-fixture\n'           # the local server shares it: rcon reaches this same process
    clcfg += ('connect 127.0.0.1:%d\n' % a.port) if a.phase == 'remote' else ('map ' + MAP + '\n')
    (dirs['client'] / 'ftesurf/p1598-client.cfg').write_text(clcfg)
    procs = []
    out = {'phase': a.phase}
    clpath = dirs['client'] / 'ftesurf/logs/p1598cl.log'
    try:
        if a.phase == 'remote':
            (dirs['server'] / 'ftesurf/p1598-server.cfg').write_text(
                'exec cfg/default.cfg\n' + safe + 'log_enable 1\nlog_name p1598sv\nmap ' + MAP + '\n')
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.bind(('127.0.0.1', a.port))
            procs.append(subprocess.Popen([str(a.engine / 'fteqwsv64.exe'), *common, '-basedir', str(dirs['server']),
                                           '-manifest', str(dirs['server'] / 'default.fmf'), '-port', str(a.port),
                                           '+exec', 'p1598-server.cfg'], cwd=dirs['server'], stdin=subprocess.PIPE,
                                          stdout=(root / 'server-console.log').open('x'), stderr=subprocess.STDOUT,
                                          creationflags=0x08000000))
            time.sleep(4)
        cl = [str(a.engine / 'fteqw64.exe'), *common, '-basedir', str(dirs['client']), '-manifest',
              str(dirs['client'] / 'default.fmf'), '-port', str(a.port + 1),
              *(['+set', 'vid_renderer', 'gl', '+set', 'vid_fullscreen', '0', '+set', 'vid_width', '960',
                 '+set', 'vid_height', '600'] if rendered else ['+set', 'vid_renderer', 'headless']),
              '+exec', 'p1598-client.cfg']
        client = subprocess.Popen(cl, cwd=dirs['client'], stdin=subprocess.PIPE,
                                  stdout=(root / 'client-console.log').open('x'), stderr=subprocess.STDOUT,
                                  creationflags=0x08000000)
        procs.append(client)

        def send(line):
            client.stdin.write((line + '\n').encode())
            client.stdin.flush()

        def lines_from(seen):
            return clpath.read_text(errors='replace').splitlines()[seen:] if clpath.is_file() else []

        def count():
            return len(clpath.read_text(errors='replace').splitlines()) if clpath.is_file() else 0

        def ask(cmd, pat, wait=8):
            seen = count()
            send(cmd)
            end = time.monotonic() + wait
            while time.monotonic() < end:
                for ln in lines_from(seen):
                    m = re.search(pat, ln)
                    if m:
                        return m
                time.sleep(0.2)
            return None

        def status(label):
            m = ask('hud_gamemode status', STATUS.pattern)
            assert m, 'no hud_gamemode status for ' + label
            out[label] = {'open': int(m.group(1)), 'mode': int(m.group(2)), 'sel': m.group(3), 'why': m.group(4)}
            return out[label]

        def spawned(wait=90):
            end = time.monotonic() + wait
            while time.monotonic() < end:
                m = ask('cmd viewpos', r'setpos (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) -?[\d.]+ -?[\d.]+ -?[\d.]+\s*$', 3)
                if m and [float(v) for v in m.groups()] != [0.0, 0.0, 0.0]:
                    return True
                time.sleep(1)
            return False

        assert spawned(), 'the player never spawned'
        out['start'] = status('start')
        if a.phase == 'local':
            send('hud_gamemode open')
            time.sleep(1.0)
            out['opened'] = status('opened')
            send('screenshot p1598panel')
            time.sleep(2.0)
            m = ask('vote key 50 1 50', r'vote key: scan 50 down 1 took (\d) .* saves (\d+)')
            out['key2_down'] = m.groups() if m else None
            time.sleep(1.0)
            assert spawned(), 'no respawn after the hl2-pre pick'
            out['after2'] = status('after2')
            # The running mode's digit closes without a reload: its repeat and release stay the panel's.
            send('hud_gamemode open')
            time.sleep(0.5)
            m = ask('vote key 50 1 50', r'vote key: scan 50 down 1 took (\d) .* saves (\d+)')
            out['same_down'] = m.groups() if m else None
            m = ask('vote key 50 1 50', r'vote key: scan 50 down 1 took (\d) .* saves (\d+)')
            out['same_repeat'] = m.groups() if m else None
            m = ask('vote key 50 0 50', r'vote key: scan 50 down 0 took (\d) .* saves (\d+)')
            out['key2_up'] = m.groups() if m else None
            out['after_same'] = status('after_same')
            send('hud_gamemode open')
            time.sleep(0.5)
            send('vote key 52 1 52')
            send('vote key 52 0 52')
            time.sleep(1.0)
            assert spawned(), 'no respawn after the ag-100 pick'
            out['after4'] = status('after4')
            # A click: a row's centre through the whole chain (sui wants motion first, then press and release).
            send('hud_gamemode open')
            time.sleep(0.5)
            m = ask('hud_gamemode status', r'hud_gamemode: rows x (\S+) w (\S+) y (\S+) pitch (\S+)')
            assert m, 'no panel geometry'
            x0, w, y0, pitch = (float(v) for v in m.groups())
            cx, cy = x0 + w * 0.5, y0 + pitch * 4.5          # row 5, ag-250
            for dx in (-6, -3, 0):
                send('hud_gamemode mouse %g %g' % (cx + dx, cy))
                time.sleep(0.1)
            send('vote key 512 1')
            time.sleep(0.3)
            send('vote key 512 0')
            time.sleep(1.0)
            assert spawned(), 'no respawn after the click'
            out['after_click'] = status('after_click')
            # The console is the player's own (RESTRICT_LOCAL); rcon to this same server is not.
            send('movementprofile cs16')
            time.sleep(1.0)
            assert spawned(), 'no respawn after the console switch'
            out['after_console'] = status('after_console')
            seen = count()
            send('rcon movementprofile ag-1000')
            time.sleep(2.0)
            out['rcon_lines'] = [ln[20:] for ln in lines_from(seen) if 'movementprofile' in ln]
            out['after_rcon'] = status('after_rcon')
            send('hud_gamemode 1')
            time.sleep(1.0)
            assert spawned(), 'no respawn after the default pick'
            out['after1'] = status('after1')
            # Server text while hosting: this listen server stuffs its own client (svc_stufftext, RESTRICT_SERVER).
            seen = count()
            send('stuffcmd Player hud_gamemode 7')
            time.sleep(1.0)
            send('stuffcmd Player hud_gamemode open')
            time.sleep(1.0)
            out['stuffed_open'] = status('stuffed_open')
            send('hud_gamemode open')
            time.sleep(0.5)
            send('stuffcmd Player vote key 55 1 55')
            time.sleep(0.5)
            send('stuffcmd Player vote key 55 0 55')
            time.sleep(0.5)
            send('hud_gamemode close')
            send('stuffcmd Player movementprofile cs16')
            # rcon_level is no cvar in a client exe (cmd.c: fixed at 20); rcon_password is, and P1598 marks it.
            send('stuffcmd Player rcon_password p1598-stuffed')
            time.sleep(1.5)
            out['stuffed_lines'] = [ln[20:] for ln in lines_from(seen)
                                    if 'movementprofile' in ln or 'rcon_' in ln or 'hud_gamemode:' in ln]
            m = ask('rcon_password', r'"rcon_password" is "([^"]*)"')
            out['rcon_password'] = m.group(1) if m else None
            out['after_stuffed'] = status('after_stuffed')
        else:
            seen = count()
            send('hud_gamemode 4')
            send('movementprofile ag-100')
            if a.phase == 'remote':
                procs[0].stdin.write(b'stuffcmd Player movementprofile cs16\n')   # stufftext: RESTRICT_SERVER
                procs[0].stdin.flush()
            time.sleep(2.0)
            out['refusals'] = [ln[20:] for ln in lines_from(seen) if 'hud_gamemode:' in ln or 'movementprofile:' in ln]
            out['after_pick'] = status('after_pick')
    finally:
        for p in procs:
            try:
                p.stdin.write(b'quit\n')
                p.stdin.flush()
            except OSError:
                pass
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=5)
    log = clpath.read_text(errors='replace') if clpath.is_file() else ''
    out['engine_lines'] = [ln[20:] for ln in log.splitlines() if 'movementprofile:' in ln][:12]
    out['panel_lines'] = [ln[20:] for ln in log.splitlines() if 'hud_gamemode:' in ln and 'open ' not in ln][:8]
    out['screenshots'] = [str(p) for p in dirs['client'].rglob('p1598panel*')]
    c = {}
    if a.phase == 'local':
        c['hosting, engine has the command (why empty)'] = out['start']['why'] == '' and out['start']['mode'] == 1
        c['the panel opens'] = out['opened']['open'] == 1
        c['digit 2 taken by the panel %s' % (out['key2_down'],)] = bool(out['key2_down']) and out['key2_down'][0] == '1'
        c['same mode: press, repeat and release all the panel\'s, no save %s %s %s' % (out['same_down'], out['same_repeat'], out['key2_up'])] = \
            all(x and x[0] == '1' for x in (out['same_down'], out['same_repeat'], out['key2_up'])) \
            and out['same_down'][1] == out['key2_up'][1] and out['after_same']['mode'] == 2 and out['after_same']['open'] == 0
        c['after 2: hl2-pre'] = out['after2']['mode'] == 2 and out['after2']['sel'] == 'hl2-pre'
        c['after 4: ag-100'] = out['after4']['mode'] == 4 and out['after4']['sel'] == 'ag-100'
        c['a click on row 5: ag-250'] = out['after_click']['mode'] == 5
        c['the console switches: cs16'] = out['after_console']['mode'] == 7
        c['rcon to the same server is refused %s' % (out['rcon_lines'],)] = out['after_rcon']['mode'] == 7 \
            and any('only from your own console or binds' in ln for ln in out['rcon_lines'])
        c['after 1: default'] = out['after1']['mode'] == 1
        # A stuffed `hud_gamemode 7`/`open` stops at the panel's own gate; a stuffed digit into the panel the
        # player opened reaches the engine, which refuses it.
        c['stuffed hud_gamemode refused by the panel, a stuffed digit by the engine %s' % (out['stuffed_lines'],)] = \
            sum('hud_gamemode: only from your own console or binds' in ln for ln in out['stuffed_lines']) >= 2 \
            and any('only from your own key press, click or console' in ln for ln in out['stuffed_lines'])
        c['a stuffed open leaves the panel shut'] = out['stuffed_open']['open'] == 0 \
            and any('hud_gamemode: only from your own console or binds' in ln for ln in out['stuffed_lines'])
        c['stuffed movementprofile refused'] = any('only from your own console or binds' in ln for ln in out['stuffed_lines'])
        c['stuffed rcon_password refused (%s)' % out['rcon_password']] = out['rcon_password'] == 'p1598-owned-fixture' \
            and any('Server tried setting rcon_password' in ln for ln in out['stuffed_lines'])
        c['the mode never moved: default'] = out['after_stuffed']['mode'] == 1
        c['engine reloaded five times'] = sum('reloading the map' in ln for ln in out['engine_lines']) == 5
        c['screenshot written'] = bool(out['screenshots'])
    elif a.phase == 'remote':
        c['not hosting: the panel says so'] = out['start']['why'].startswith('Only in a game you host')
        c['the pick changed nothing'] = out['after_pick']['mode'] == 1
        c['the console command refused (not hosting)'] = any('only in a game you host' in ln for ln in out['refusals'])
        c['the stuffed line refused by its level'] = any('only from your own console or binds' in ln for ln in out['refusals'])
    else:
        c['old engine: the panel says so'] = 'needs P1598' in out['start']['why']
    out['checks'] = c
    (root / 'result.json').write_text(json.dumps(out, indent=2))
    for k, v in c.items():
        print(('PASS ' if v else 'FAIL ') + k)
    for k in ('start', 'opened', 'key2_down', 'after2', 'same_down', 'same_repeat', 'key2_up', 'after_same', 'after4', 'after_click', 'after_console', 'rcon_lines',
              'after_rcon', 'after1', 'stuffed_lines', 'rcon_password', 'after_stuffed', 'refusals', 'after_pick',
              'engine_lines', 'panel_lines', 'screenshots'):
        if k in out:
            print(' ', k, out[k])
    return 0 if all(c.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
