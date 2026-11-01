#!/usr/bin/env python3
"""P1187: chat goes to everyone by default -- dedicated socket, synthetic backend.

A TEST-ONLY server progs (--src's sv_progs.src plus one fixture) links the first real
client for social (Social_Set, *phash); no account authority. A Flask stand-in for
surfd records room posts and serves three room lines once. Graded: what the lobby
posts, what it says, the draft's target, and which room lines it relays back.
--src is the QC tree the server progs are built from (the control passes the delivered
tree); --progs holds its csprogs.dat/menu.dat. --out: fresh, beneath an OWNER.md.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid

sys.dont_write_bytecode = True
from spec_chat_smoke import Peer, prepare, sha  # noqa: E402

WHO, TOKEN = 'aaaaaaaa', '1' * 64
K_TAB, K_ENTER = 9, 13
FIXTURE = '''// TEST ONLY (tools/p1187chat.py): link the first real client for social; no authority.
void() ChatFixture_Frame =
{
	local entity p;

	p = find(world, classname, "player");
	while (p)
	{
		if (clienttype(p) == CLIENTTYPE_REAL)
		{
			if (!p.social_here)
			{
				Social_Set(p, "%s", "%s");
				print("chat fixture: linked\\n");
			}
			if (infokey(p, "*phash") != "%s")
				forceinfokey(p, "*phash", "%s");
			return;
		}
		p = find(p, classname, "player");
	}
};
''' % (TOKEN, WHO, WHO, WHO)
ROOM = [dict(id='5', who=WHO, name='Looker', text='[#7] self line'),
        dict(id='6', who='bbbbbbbb', name='Nine', text='[#9] hello from nine'),
        dict(id='7', who='cccccccc', name='Menu', text='hello from menu')]


def build_server(src, out):
    gd = out / 'testprogs'
    gd.mkdir()
    (out / 'fixture.qc').write_text(FIXTURE)
    main = (src / 'server/sv_main.qc').read_text()
    assert main.count('Social_Frame();') == 1
    (out / 'main.qc').write_text(main.replace('Social_Frame();', 'ChatFixture_Frame(); Social_Frame();'))
    lines = [str(gd / 'qwprogs.dat')]
    for line in (src / 'sv_progs.src').read_text().splitlines()[1:]:
        if not line.strip() or line.lstrip().startswith('//'):
            continue
        if line == 'server/sv_account.qc':
            lines += [str(src / line), str(out / 'fixture.qc')]
        elif line == 'server/sv_main.qc':
            lines.append(str(out / 'main.qc'))
        else:
            lines.append(str(src / line))
    # fteqcc's old-style reader wants relative, unquoted paths and a manifest in src/.
    manifest = src / ('build-p1187-' + uuid.uuid4().hex + '.src')
    manifest.write_text('\n'.join(os.path.relpath(x, src).replace('\\', '/') for x in lines) + '\n')
    try:
        c = subprocess.run([str(src / 'fteqcc64.exe'), '-srcfile', manifest.name],
                           cwd=src, text=True, capture_output=True)
    finally:
        manifest.unlink()
    (out / 'compile.log').write_text(c.stdout + c.stderr)
    if c.returncode or not (gd / 'qwprogs.dat').is_file() or '0 warnings' not in c.stdout + c.stderr:
        raise RuntimeError('fixture build failed; see compile.log')
    return gd / 'qwprogs.dat'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--src', type=Path, default=Path(__file__).resolve().parents[1] / 'src')
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--port', type=int, default=27617)
    ap.add_argument('--http-port', type=int, default=27639)
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    ap.add_argument('--server', type=Path, default=Path('C:/FTEQuake/fteqwsv64.exe'))
    a = ap.parse_args()
    a.out, a.src = a.out.resolve(), a.src.resolve()
    if not any((p / 'OWNER.md').is_file() for p in a.out.parents):
        ap.error('--out must be beneath an owned task root')
    for kind, port in ((socket.SOCK_DGRAM, a.port), (socket.SOCK_STREAM, a.http_port)):
        with socket.socket(socket.AF_INET, kind) as probe:
            probe.bind(('127.0.0.1', port))
    a.out.mkdir(parents=True, exist_ok=False)
    progs = a.out / 'progs'
    progs.mkdir()
    shutil.copy2(build_server(a.src, a.out), progs / 'qwprogs.dat')
    for leaf in ('csprogs.dat', 'menu.dat'):
        shutil.copy2(a.progs / leaf, progs / leaf)
    a.progs = progs

    from flask import Flask, request
    from werkzeug.serving import make_server, WSGIRequestHandler
    app = Flask(__name__)
    posts, other = [], []
    room = {'serve': False, 'served': 0}

    @app.post('/api/social/poll')
    def poll():
        rows = json.loads(request.form.get('roster', '[]'))
        players = []
        for r in rows:
            if r.get('token') == TOKEN:
                row = dict(token=TOKEN, hash='b' * 64, rack='4')
                if room['serve'] and not room['served']:
                    row['room'], row['rack'] = ROOM, '7'
                    room['served'] += 1
                players.append(row)
        return {'ok': 1, 'players': players}

    @app.post('/api/social/action')
    def action():
        posts.append({k: request.form.get(k, '') for k in ('op', 'who', 'text')})
        return {'ok': 1, 'note': ''}

    @app.route('/<path:rest>', methods=['GET', 'POST'])
    def anything(rest):
        other.append(rest)
        return {'ok': 0, 'error': 'synthetic'}, 404

    class Quiet(WSGIRequestHandler):
        def log(self, *args):
            pass
    web = make_server('127.0.0.1', a.http_port, app, request_handler=Quiet)
    thread = threading.Thread(target=web.serve_forever, daemon=True)
    thread.start()

    checks = []
    report = {'src': str(a.src), 'progs': {p: sha(progs / p) for p in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')},
              'client': sha(a.client), 'server': sha(a.server), 'checks': checks}
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs',
              'log_name probe', 'log_readable 1', 'set cl_idlefps 0', 'set cl_maxfps 100',
              'set run_resume 0', 'set lobby_dir ""', 'set lobby_enable 1',
              'set cl_run_upload 0', 'set cl_board_url ""', 'set sv_public 0']

    def check(ok, name, seen=''):
        checks.append({'name': name, 'pass': bool(ok), 'seen': str(seen)})
        print(('PASS ' if ok else 'FAIL ') + name + (f'  [{seen}]' if seen != '' else ''), flush=True)

    def seen(peer, pattern, offset=0, timeout=8):
        try:
            return peer.wait(pattern, offset, timeout)
        except RuntimeError:
            return None

    peers = []
    try:
        base = prepare(a, 'server')
        (base / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
            f'sv_port {a.port}', 'sv_playerslots 4', 'sv_maxclients 4', 'set hostname "Open Lobby #7"',
            f'set lobby_master "http://127.0.0.1:{a.http_port}"', 'set lobby_master_key synthetic-test-key',
            'map spec_chat.map']) + '\n')
        sv = Peer(a.server, base, 'probe.cfg', True); peers.append(sv)
        sv.wait(r'Server spawned\.')

        base = prepare(a, 'client')
        (base / 'ftesurf/probe.cfg').write_text('\n'.join(common + [
            'set lobby_master ""', 'cl_threadedphysics 0', 'name Looker',
            f'connect 127.0.0.1:{a.port}']) + '\n')
        cl = Peer(a.client, base, 'probe.cfg'); peers.append(cl)
        cl.wait('FTESurf CSQC loaded', timeout=60)
        time.sleep(2)
        cl.query('menu_restart; ui_close; echo P1187_READY', 'P1187_READY')
        check(seen(sv, 'chat fixture: linked', timeout=20), 'the fixture linked the client')
        time.sleep(2)

        def key(scan):
            cl.query(f'vote key {scan} 1', r'vote key: scan %d down 1' % scan)
            cl.send(f'vote key {scan} 0')

        def target():
            m = cl.query('chat_rows', r'chat_rows: (?:not drawn yet|draft len \d+(?: to "([^"]*)")?)')
            return m.group(1)

        # 1. A plain line: said here AND posted to the room with this lobby's tag.
        cl.send('chat_say hello everyone'); time.sleep(.4)
        got = target()
        pos = len(cl.text())
        key(K_ENTER)
        said = seen(cl, r'Looker\S*: hello everyone', pos)
        time.sleep(1.5)
        check(len(posts) == 1 and posts[0] == {'op': 'message', 'who': '-', 'text': '[#7] hello everyone'},
              'a plain line is posted to the room tagged [#7]', posts)
        check(said, 'and said in this lobby')
        check(got == 'everyone', 'the draft opens to everyone', got)
        check(len(re.findall(r'hello everyone', cl.text()[pos:])) == 1, 'shown once (no second local echo)')
        time.sleep(1.5)                     # Social_Action's one-second spacing

        # 2. TAB: this lobby only.
        n = len(posts)
        cl.send('chat_say lobby line'); time.sleep(.4)
        key(K_TAB); time.sleep(.3)
        got = target()
        pos = len(cl.text())
        key(K_ENTER)
        said = seen(cl, r'Looker\S*: lobby line', pos)
        time.sleep(2.5)
        check(got == 'this lobby', 'TAB switches to this lobby', got)
        check(said and len(posts) == n, 'a this-lobby line is said, not posted', posts[n:])

        # 3. A !command to everyone stays here (WarpOp_Chat does not claim !p1187).
        n = len(posts)
        cl.send('chat_say !p1187'); time.sleep(.4)
        got = target()
        key(K_ENTER)
        time.sleep(2.5)
        check(got == 'everyone' and len(posts) == n, 'a !command typed to everyone is not posted',
              (got, posts[n:]))

        # 4. The room's lines: other lobbies tagged, the menu's [menu], this lobby's own skipped.
        pos = len(cl.text())
        room['serve'] = True
        nine = seen(cl, r'\[#9\](\^\d)? Nine(\^\d)?: hello from nine', pos, timeout=15)
        menu = seen(cl, r'\[menu\](\^\d)? Menu(\^\d)?: hello from menu', pos, timeout=5)
        time.sleep(1)
        check(room['served'] == 1, 'the backend served the room lines', room['served'])
        check(nine, 'a line from lobby #9 shows as [#9] Nine: ...')
        check(menu, 'an untagged line shows as [menu] Menu: ...')
        check('self line' not in cl.text()[pos:], "a room line from a player in this lobby is not relayed back")
        report['posts'], report['other_routes'] = posts, sorted(set(other))
    finally:
        for p in peers:
            p.stop()
        web.shutdown()
        thread.join(timeout=10)
        report['exits'] = [p.proc.returncode for p in peers]
        report['ok'] = all(c['pass'] for c in checks) and len(checks) == 12
        (a.out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print('ALL PASS' if report['ok'] else 'NOT ALL PASS')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
