#!/usr/bin/env python3
"""P1177: a hud_player colour pick survives a restart (dedicated socket, owned overlays).

Launch 1 picks palette 5 through the panel's own setter (`hud_player swatch`),
reads the asked/saved pair and the lobby's grant, and saves a config. Launch 2
boots from that config (a hand-edited bad value appended), prints its userinfo before
connecting, then grades the restore line and the lobby's grant again.
--out must be fresh and beneath an owned task root; --progs is the build output.
"""
import argparse
import json
from pathlib import Path
import re
import socket
import sys
import time

sys.dont_write_bytecode = True
from spec_chat_smoke import Peer, prepare, sha  # noqa: E402

PORT_RANGE = range(27520, 27621)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--port', type=int, default=27617)
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    ap.add_argument('--server', type=Path, default=Path('C:/FTEQuake/fteqwsv64.exe'))
    a = ap.parse_args()
    a.out = a.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in a.out.parents):
        ap.error('--out must be beneath an owned task root')
    if a.port not in PORT_RANGE:
        ap.error('use a dedicated lobby-range port')
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', a.port))
    a.out.mkdir(parents=True, exist_ok=False)
    checks = []
    report = {'progs': {p: sha(a.progs / p) for p in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')},
              'client': sha(a.client), 'server': sha(a.server), 'checks': checks}
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs',
              'log_name probe', 'log_readable 1', 'set cl_idlefps 0', 'set cl_maxfps 100',
              'set run_resume 0', 'set lobby_dir ""', 'set lobby_master ""',
              'set lobby_enable 1', 'set lobby_avatars 1', 'set cl_run_upload 0', 'set cl_board_url ""', 'set sv_public 0']

    def check(ok, name, seen=''):
        checks.append({'name': name, 'pass': bool(ok), 'seen': seen})
        print(('PASS ' if ok else 'FAIL ') + name + (f'  [{seen}]' if seen else ''), flush=True)
        if not ok:
            raise AssertionError(name)

    def look(cl, key):
        line = cl.query('hud_player look', r'hud_player look \(asked/saved\):[^\n]*').group(0)
        m = re.search(key + r' "([^"]*)"/"([^"]*)"', line)
        return (m.group(1), m.group(2)) if m else None

    def granted(cl, want):  # the lobby's 1 Hz resolve publishes its grant as infokey lc
        for _ in range(8):
            lc = cl.query('hud_player look', r'granted lc "([^"]*)"').group(1)
            if lc == want:
                break
            time.sleep(.5)
        return lc

    peers = []
    try:
        base = prepare(a, 'server')
        (base / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
            f'sv_port {a.port}', 'sv_playerslots 4', 'sv_maxclients 4', 'map spec_chat.map']) + '\n')
        sv = Peer(a.server, base, 'probe.cfg', True); peers.append(sv)
        sv.wait(r'Server spawned\.')

        base = prepare(a, 'client')
        game = base / 'ftesurf'
        (game / 'probe.cfg').write_text('\n'.join(common + [
            'cl_threadedphysics 0', 'name Looker', f'connect 127.0.0.1:{a.port}']) + '\n')
        cl = Peer(a.client, base, 'probe.cfg'); peers.append(cl)
        cl.wait('FTESurf CSQC loaded')
        time.sleep(2)
        cl.query('menu_restart; ui_close; echo P1177_READY', 'P1177_READY')
        got = look(cl, 'lobbycolor')
        check(got == ('', ''), 'launch 1 starts with nothing asked or saved', str(got))
        check('saved look settings sent' not in cl.text(), 'launch 1 restores nothing')
        cl.send('hud_player swatch 5')
        time.sleep(2)
        got = look(cl, 'lobbycolor')
        check(got == ('5', '5'), 'the swatch asks 5 and saves 5', str(got))
        lc = granted(cl, '5')
        check(lc == '5', 'the lobby grants 5', lc)
        # Same process, new connection: the engine keeps userinfo (cleared only at shutdown).
        pos = len(cl.text())
        cl.send(f'disconnect; wait; connect 127.0.0.1:{a.port}')
        cl.wait('FTESurf CSQC loaded', pos)
        time.sleep(2)
        cl.query('menu_restart; ui_close; echo P1177_READY', 'P1177_READY')
        got = look(cl, 'lobbycolor')
        check(got == ('5', '5'), 'a reconnect without a restart still asks 5', str(got))
        lc = granted(cl, '5')
        check(lc == '5', 'the lobby grants 5 after the reconnect', lc)
        check('saved look settings sent' not in cl.text(), 'the reconnect sends nothing')
        # Bare cfg_save is the quit-time autosave (the manifest's MAINCONFIG); cfg_save_all 1
        # makes it write every cvar, the worst case for anything kept in a non-archived cvar.
        wrote = cl.query('set cfg_save_all 1; cfg_save; echo P1177_SAVED',
                         r'Wrote \$basedir/(\S+\.cfg)').group(1)
        cl.wait('P1177_SAVED')
        cl.stop(); peers.remove(cl)
        mainconfig = base / wrote
        saved = mainconfig.read_text(errors='replace')
        check('seta cl_lobbycolor "5"' in saved, 'the saved config keeps cl_lobbycolor 5')
        check(not re.search(r'^setinfo ', saved, re.M), 'no userinfo lines saved (cfg_save_infos 0)')
        check(re.search(r'^set ', saved, re.M), 'cfg_save_all 1 saved non-archived cvars too')
        with open(mainconfig, 'a') as f:
            f.write('seta cl_lobbylen "x"\n')

        (game / 'logs/probe.log').rename(game / 'logs/probe-launch1.log')
        (game / 'probe.cfg').write_text('\n'.join(common + [
            'cl_threadedphysics 0', 'name Looker', 'cl_lobbycolor', 'setinfo', 'echo P1177_BEFORE_CONNECT',
            f'connect 127.0.0.1:{a.port}']) + '\n')
        cl = Peer(a.client, base, 'probe.cfg'); peers.append(cl)
        before = cl.wait(r'([\s\S]*?)P1177_BEFORE_CONNECT').group(1)
        check('"cl_lobbycolor" is "5"' in before, 'launch 2 booted from the saved config')
        check(not re.search(r'\^2lobbycolor\s', before), 'launch 2 userinfo has no lobbycolor before CSQC')
        cl.wait('FTESurf CSQC loaded')
        sent = cl.wait(r'hud_player: (\d+) saved look settings sent').group(1)
        check(sent == '1', 'CSQC sends exactly the one safe saved setting', sent)
        time.sleep(2)
        cl.query('menu_restart; ui_close; echo P1177_READY', 'P1177_READY')
        got = look(cl, 'lobbycolor')
        check(got == ('5', '5'), 'after the restart the lobby sees 5 asked', str(got))
        got = look(cl, 'lobbylen')
        check(got == ('', 'x'), 'the unsafe saved value is not sent', str(got))
        lc = granted(cl, '5')
        check(lc == '5', 'the lobby grants 5 after the restart', lc)
        report['ok'] = True
    finally:
        for p in peers:
            p.stop()
        report['exits'] = [p.proc.returncode for p in peers]
        (a.out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
