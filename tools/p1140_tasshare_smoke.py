#!/usr/bin/env python3
"""Acted local TAS sharing/browser smoke with real tasrevd and native peers.

--out must be fresh beneath an OWNER.md; --progs is build.ps1's NoDeploy output
root, not a gamedir beneath it. Requires Flask/Werkzeug and the existing rig lock.
Only synthetic, unlinked signatures are used: this is NOT human-press acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'surfd')]
import p840clock as clock
from spec_chat_smoke import Peer
import tasrev
import tasrevd
import ed25519
from werkzeug.serving import make_server


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def deny_read(path, deny):
    # Read the current SID INSIDE the script; never log it or put it in argv.
    script = '''$ErrorActionPreference = 'Stop'
$p = '%s'
$a = Get-Acl -LiteralPath $p
$u = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
$r = [System.Security.AccessControl.FileSystemAccessRule]::new($u, [System.Security.AccessControl.FileSystemRights]::ReadData, [System.Security.AccessControl.AccessControlType]::Deny)
%s
Set-Acl -LiteralPath $p -AclObject $a
''' % (str(path).replace("'", "''"), '$a.AddAccessRule($r)' if deny else '$a.RemoveAccessRuleSpecific($r)')
    result = subprocess.run(['pwsh', '-NoProfile', '-NonInteractive', '-Command', '-'], input=script, text=True, capture_output=True)
    assert result.returncode == 0, 'owned ACL fixture operation failed (private stderr withheld)'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--native', type=Path, required=True)
    ap.add_argument('--port', type=int, default=27618)
    ap.add_argument('--resume-saved', action='store_true', help='reuse only a stopped, hash-identical four-check save-phase failure, retaining its original evidence')
    a = ap.parse_args()
    assert all(p.is_absolute() for p in (a.out, a.progs, a.native))
    assert any((p / 'OWNER.md').is_file() for p in a.out.parents)
    assert 27520 <= a.port <= 27620
    progs = {n: digest(a.progs / n) for n in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')}
    native = {n: digest(a.native / n) for n in ('fteqw64.exe', 'fteqwsv64.exe', 'fteplug_hl2_x64.dll')}
    online = int(re.search(r'^#define FS_TERMS_ONLINE (\d+)', (ROOT / 'src/shared/sh_defs.qc').read_text(), re.M)[1])
    previous = None
    if a.resume_saved:
        previous = json.loads((a.out/'report.json').read_text())
        assert previous['owned_peers_stopped'] and previous['result'] == 'FAIL'
        assert previous['progs'] == progs and previous['native'] == native
        assert len(previous['checks']) == 4 and all(c['pass'] for c in previous['checks'])
        assert all(m == 'GET' for m,_ in previous['http_calls'])
        assert not (a.out/'transfer-report.json').exists()
        assert all(not (a.out/s/'ftesurf/transfer.cfg').exists() for s in ('sv','cl'))
        assert f'sv_port {a.port}\n' in (a.out/'sv/ftesurf/probe.cfg').read_text()
        for side in ('sv','cl'):
            assert all(digest(a.out/side/'ftesurf'/name) == sha for name,sha in progs.items())
    else:
        a.out.mkdir(exist_ok=False, parents=True)
    checks, peers, calls, acl_paths = [], [], [], []
    report = {'progs': progs, 'native': native, 'checks': checks}
    if previous: report['reused_save_phase'] = {'sha256':digest(a.out/'report.json'),'checks':previous['checks']}
    main_db, store, codes = (a.out / n for n in ('accounts.db', 'tasrev.db', 'codes.txt'))
    if not previous:
        with sqlite3.connect(main_db) as db:
            db.executescript('CREATE TABLE accounts(steamid TEXT PRIMARY KEY, banned_at INTEGER); CREATE TABLE keylinks(pub TEXT, steamid TEXT);')
        codes.write_text(progs['csprogs.dat'] + '\n')
    else:
        assert codes.read_text().strip() == progs['csprogs.dat']
        with sqlite3.connect(store) as db: assert db.execute('SELECT count(*) FROM revisions').fetchone()[0] == 0
    tasrevd.initialize(store)
    app = tasrevd.create_app(store, main_db, codes)
    mode, override, detail_fixture = ['normal'], [b''], [None]
    arrived, release = threading.Event(), threading.Event()

    def application(env, respond):
        calls.append((env['REQUEST_METHOD'], env['PATH_INFO']))
        if mode[0] == 'wrong-map' and '/map/' in env['PATH_INFO']:
            respond('200 OK', [('Content-Type', 'application/json')])
            return [b'{"ok":1,"map":"wrong_map","revisions":[]}']
        if mode[0] in ('malformed', 'override') and env['PATH_INFO'].endswith('/file'):
            respond('200 OK', [('Content-Type', 'text/plain')])
            return [b'tasproject 3\ninvalid\n' if mode[0] == 'malformed' else override[0]]
        if mode[0].startswith('credit-') and re.fullmatch(r'/api/tasrev/rev/[0-9a-f]{64}',env['PATH_INFO']):
            # Synthetic consumer boundary DTOs, NOT a claimed ancestry history.
            count = int(mode[0].split('-')[1]); dto = dict(detail_fixture[0])
            dto['credit'] = [[i,i,'unattributed' if i % 2 else 'unknown-ancestry'] for i in range(1,count+1)]
            respond('200 OK', [('Content-Type','application/json')])
            return [json.dumps(dto).encode()]
        if (mode[0] == 'delay-file' and env['PATH_INFO'].endswith('/file')) or (mode[0] == 'delay-statement' and env['PATH_INFO'].endswith('/statement')):
            arrived.set()
            if not release.wait(10):
                respond('503 Service Unavailable', [('Content-Type','text/plain')]); return [b'fixture delay expired']
        return app(env, respond)

    http = make_server('127.0.0.1', 0, application, threaded=True)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{http.server_port}/api/tasrev'

    def check(name, value):
        checks.append({'name': name, 'pass': bool(value)})
        print(('PASS ' if value else 'FAIL ') + name, flush=True)
        assert value, name

    def start(side, cfg):
        base = a.out / side
        peer = Peer(a.native / ('fteqwsv64.exe' if side == 'sv' else 'fteqw64.exe'), base, cfg + '.cfg', side == 'sv')
        peer.log = base / f'ftesurf/logs/{cfg}.log'
        peers.append(peer)
        peer.wait(r'Server spawned\.' if side == 'sv' else 'FTESurf CSQC loaded')
        return peer

    locked = False
    try:
        clock.take_lock('P1140 sharing: owned dedicated/client roots')
        locked = True
        common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs', 'log_name probe', 'log_readable 1',
                  'cl_idlefps 0', 'cl_maxfps 100', 'cl_netfps 100', 'cl_threadedphysics 0', 'set run_resume 0', 'set lobby_dir ""',
                  'set lobby_dir_gen 1', 'set lobby_master ""', 'set lobby_enable 0', 'set cl_run_upload 0', 'set cl_board_url ""',
                  'sv_public 0', 'sensitivity 0', 'set m_accel 0', 'set rec_terms 0', f'set tas_directory "{url}"']
        if not previous:
            for side in ('sv', 'cl'):
                base = clock.prepare(a.out, side, a.progs, a.progs / 'csprogs.dat')
                (base / 'ftesurf/data/consent.txt').write_text('version 0\n')
                shutil.copy2(a.native / 'fteplug_hl2_x64.dll', base / 'fteplug_hl2_x64.dll')
                lines = common + ([f'sv_port {a.port}', 'sv_playerslots 4', 'sv_maxclients 4', 'sv_demoAutoRecord 0', 'developer 1',
                                   'log_developer 1', 'pm_physicsmode 1', 'pm_ticrate 0.015', 'sv_tickparts 1', 'set sv_gamemode surf',
                                   'set rec_stream 0', 'map bhop_eazy'] if side == 'sv' else
                                  ['vid_renderer gl', 'name SharingProbe', f'connect 127.0.0.1:{a.port}'])
                (base / 'ftesurf/probe.cfg').write_text('\n'.join(lines) + '\n')
                peer = start(side, 'probe')
                if side == 'cl': cl = peer
            time.sleep(2); cl.send('menu_restart; ui_close'); time.sleep(.5)
            for candidate in ('http://example.invalid/api/tasrev','http://127.0.0.1:0/api/tasrev',
                              'http://127.0.0.1:65536/api/tasrev','http://127.0.0.1:12@x/api/tasrev'):
                cl.query('set tas_directory "'+candidate+'";tas shared status',
                         r'tas shared: endpoint https://play\.proto\.bar/api/tasrev')
            cl.send('set tas_directory "'+url+'"')
            check('native endpoint policy refuses nonlocal and malformed overrides', not calls)
            before = len(calls)
            cl.query('tas shared', r'tas shared: accept the online terms first')
            time.sleep(.3); check('without online consent no directory request acts', len(calls) == before)
            cl.send('set rec_terms 999; tas shared refresh'); time.sleep(1)
            cl.query('tas shared status', r'tas shared: map bhop_eazy list 1 detail 0 request 0')
            check('current-map browser reads real empty directory', any('/map/bhop_eazy' in p for _, p in calls))
            mode[0] = 'wrong-map'; cl.send('tas shared refresh'); time.sleep(1)
            cl.query('tas shared status', r'tas shared: map bhop_eazy list 0 detail 0 request 0')
            check('wrong-map DTO is refused and stale rows cleared', True)
            mode[0] = 'normal'
            cl.query('tas start 0', r'tas: legal start at zone 0')
            cl.send('tas next manual 450 0 0 23 0 30'); time.sleep(2)
            cl.query('tas project save sharing', r'tas project: saved sharing')
        path = a.out / 'sv/ftesurf/data/tasproj/bhop_eazy/sharing.tasp'
        body = path.read_bytes(); info = tasrev.parse(body); sha = info['h']
        if not previous: check('actual game save is canonical legal-start v3', info['version'] == '3')
        else: assert info['version'] == '3'
        # Dedicated clients intentionally cannot use the LoopBack-only author
        # statement writer. Cold-seed a synthetic signature; do not weaken it.
        for peer in reversed(peers): peer.stop()
        legacy = body.replace(b'tasproject 3\n',b'tasproject 2\n').replace(b'start 0\n',b'base 1 '+b'ab'*32+b' 0\n')
        legacy = b'\n'.join(l for l in legacy.splitlines() if not l.startswith((b'startat ',b'revsha ')))+b'\n'
        legacysha = tasrev.revhash(legacy)[0]; legacy += b'revsha '+legacysha.encode()+b'\n'; tasrev.parse(legacy)
        legacy_path = path.parent/'rev'/f'{legacysha}.tasp'
        if legacy_path.exists(): assert legacy_path.read_bytes()==legacy
        else: legacy_path.write_bytes(legacy)
        first, last = info['supply']; parent = info['parentsha'] or '-'; seed = bytes([9]) * 32
        msg = tasrev.statement(sha, parent, info['mapcrc'], first, last, progs['csprogs.dat'])
        line = f'tasrev 1 {sha} {parent} {info["mapcrc"]} {first} {last} {progs["csprogs.dat"]} {ed25519.publickey(seed).hex()} {ed25519.sign(seed, msg).hex()}'
        statement = path.parent / 'rev' / f'{sha}.fixture.tasrev'
        if statement.exists(): assert statement.read_text() == line+'\n'
        else: statement.write_text(line+'\n')
        staged = path.parent / 'staged.tasp.download'
        if staged.exists(): assert staged.read_bytes() == b'keep staged bytes\n'
        else: staged.write_bytes(b'keep staged bytes\n')
        old = body.replace(b'i 450 ', b'i 449 ', 1)
        assert old != body
        old = b'\n'.join(l for l in old.splitlines() if not l.startswith(b'revsha ')) + b'\n'
        old += b'revsha ' + tasrev.revhash(old)[0].encode() + b'\n'
        tasrev.parse(old)
        recovery = path.parent / 'recover.tasp.new2'; recovery.write_bytes(old)
        for name in ('sealed.tasp', 'sealedstage.tasp.download'):
            p = path.parent / name; p.write_bytes(old); acl_paths.append(p); deny_read(p, True)
            try: p.read_bytes()
            except PermissionError: pass
            else: raise AssertionError('read-deny fixture did not act')
        for side in ('sv', 'cl'):
            base = a.out / side
            (base / 'ftesurf/data/consent.txt').write_text(f'version {online}\n')
            config = (base / 'ftesurf/probe.cfg').read_text().replace('log_name probe', 'log_name transfer')
            (base / 'ftesurf/transfer.cfg').write_text(re.sub(r'set tas_directory "[^"]+"',f'set tas_directory "{url}"',config))
            peer = start(side, 'transfer')
            if side == 'cl': cl = peer
        time.sleep(2); cl.send('menu_restart; ui_close')
        cl.query('cmd tas project load sharing', r'tas project: loading sharing')
        cl.wait(r'tas project: loaded sharing to tick 30'); time.sleep(.4)
        before = len(calls)
        cl.query('cmd tas project share', r'tas project share yes.*publicly uploads'); time.sleep(.4)
        check('no public upload without explicit confirmation', len(calls) == before)
        cl.query('tas project share yes', r'tas share/open: host this game locally first')
        check('client local-host gate acts without an upload', len(calls) == before)
        cl.query(f'cmd tas project share yes {legacysha}',r'tas share: only legal-start v3 projects are portable; no upload started')
        check('host-local legacy upload is refused before any statement or body request',len(calls)==before)
        time.sleep(.4); cl.query('cmd tas project share yes', r'tas share: shared revision', timeout=30)
        check('saved statement POST precedes revision POST', [p for m, p in calls[before:] if m == 'POST'] == ['/api/tasrev/statement', '/api/tasrev/revision'])
        with sqlite3.connect(store) as db:
            stored = db.execute('SELECT body FROM revisions WHERE sha=?', (sha,)).fetchone()[0]
        check('native buffer POST preserves every byte and final newline', bytes(stored) == body)
        with tasrevd.connect(store) as db, tasrevd.writing(db): tasrevd.drain(db, 10)
        with urlopen(url + '/rev/' + sha, timeout=5) as response: dto = json.load(response)
        check('service verifies fixture signature received before revision', len(dto['statements']) == 1 and dto['statements'][0]['before_revision'])
        check('unlinked fixture key gains no linked contribution credit', bool(dto['credit']) and all(r[2] == 'unattributed' for r in dto['credit']))
        detail_fixture[0] = dto
        cl.send('tas shared refresh'); time.sleep(1)
        cl.query('tas shared status', r'tas shared: map bhop_eazy list 1 detail 0 request 0')
        cl.send('tas shared select 0'); time.sleep(1)
        cl.query('tas shared status', r'tas shared: map bhop_eazy list 0 detail 1 request 0')
        check('browser adopts matching real detail and contribution ranges', True)
        cl.query(f'cmd tas project open {sha} downloaded', r'tas open: saved .* as downloaded', timeout=30)
        cl.wait(r'tas project: loaded downloaded to tick 30', timeout=30)
        check('download is byte-exact and deferred ordinary loader acts', (path.parent / 'downloaded.tasp').read_bytes() == body)
        time.sleep(.4); cl.query(f'cmd tas project open {sha} sharing', r'tas open: that project name already exists', timeout=30)
        check('occupied project name preserves saved bytes', path.read_bytes() == body)
        time.sleep(.4); cl.query(f'cmd tas project open {sha} staged', r'tas open: a staged download already exists', timeout=30)
        check('existing staged bytes are retained', staged.read_bytes() == b'keep staged bytes\n')
        time.sleep(.4); cl.query(f'cmd tas project open {sha} recover', r'tas open: recovery bytes already occupy', timeout=30)
        cl.query('cmd tas project status', r'tas project:', timeout=10); time.sleep(.4)
        cl.query('cmd tas project save', r'tas project: saved downloaded', timeout=30)
        check('refused recovery name plus ordinary attached save retains recovery bytes', recovery.read_bytes() == old and not (path.parent/'recover.tasp').exists())
        for name in ('sealed','sealedstage'):
            time.sleep(.4); cl.query(f'cmd tas project open {sha} {name}', r'tas open: (that project name|a staged download) already exists', timeout=30)
        for p in acl_paths: deny_read(p, False)
        check('unreadable existing final and writable stage retain exact bytes', all(p.read_bytes() == old for p in acl_paths))
        acl_paths.clear()
        # These appear AFTER startup; cached existence lookups alone are insufficient.
        for name, suffix in (('latefinal',''),('latestage','.download')):
            p = path.parent / (name+'.tasp'+suffix); p.write_bytes(old)
            acl_paths.append(p); deny_read(p,True)
            try: p.read_bytes()
            except PermissionError: pass
            else: raise AssertionError('late read-deny fixture did not act')
            time.sleep(.4); cl.query(f'cmd tas project open {sha} {name}',
                                    r'tas open: (that project name|a staged download) already exists',timeout=30)
        for p in acl_paths: deny_read(p,False)
        check('fresh census preserves unreadable files added after startup',all(p.read_bytes()==old for p in acl_paths))
        acl_paths.clear()
        for count, detail in ((4096,1),(4097,0),(40000,0)):
            mode[0] = f'credit-{count}'
            cl.send('tas shared refresh'); time.sleep(.7); cl.send('tas shared select 0'); time.sleep(.7)
            cl.query('tas shared status', fr'tas shared: map bhop_eazy list 0 detail {detail} request 0 selected 1')
            # On this real dedicated connection the native host gate must ACT:
            # passing it is not claimed. The old detail dependency returned silently.
            cl.query('tas shared open', r'tas open: host this map locally first')
            check(f'credit boundary {count}: selected Open remains reachable with bounded credit view', True)
        mode[0] = 'malformed'; time.sleep(.4)
        cl.query(f'cmd tas project open {sha} malformed', r'tas open: refused:', timeout=30)
        check('malformed download installs nothing and removes its own stage', not (path.parent / 'malformed.tasp').exists() and not (path.parent / 'malformed.tasp.download').exists())
        mode[0] = 'override'; override[0] = body; time.sleep(.4)
        cl.query('cmd tas project open ' + 'b' * 64 + ' wronghash', r'tas open: refused: the downloaded revision hash does not match', timeout=30)
        check('valid body from a wrong hash URL is refused', not (path.parent / 'wronghash.tasp').exists())
        override[0] = legacy; time.sleep(.4)
        cl.query(f'cmd tas project open {legacysha} nonportable', r'tas open: refused: this old project needs', timeout=30)
        check('old project requiring a private base save is not claimed portable', not (path.parent / 'nonportable.tasp').exists())
        mode[0] = 'delay-file'; arrived.clear(); release.clear()
        time.sleep(.4); cl.send(f'cmd tas project open {sha} departed')
        assert arrived.wait(5), 'delayed file request did not act'
        # Exercise real server teardown. The existing presentation-only `drop`
        # hook shadows QW's client disconnect string (separate recorded bug).
        sv = peers[-2]; off = len(cl.text()); sv.send('kick SharingProbe'); cl.wait(r'You were kicked',off,10)
        release.set(); time.sleep(1)
        check('late file reply after proved disconnect installs no project or stage', not (path.parent/'departed.tasp').exists() and not (path.parent/'departed.tasp.download').exists())
        mode[0] = 'normal'; off = len(cl.text()); cl.send(f'connect 127.0.0.1:{a.port}'); cl.wait('FTESurf CSQC loaded',off,20); time.sleep(1)
        cl.query('cmd tas project load sharing',r'tas project: loading sharing'); cl.wait(r'tas project: loaded sharing to tick 30'); time.sleep(.4)
        mode[0] = 'delay-statement'; arrived.clear(); release.clear(); before = len(calls)
        cl.send('cmd tas project share yes'); assert arrived.wait(5), 'delayed statement request did not act'
        off = len(cl.text()); sv.send('kick SharingProbe'); cl.wait(r'You were kicked',off,10)
        release.set(); time.sleep(1)
        check('late statement reply after proved disconnect sends no revision continuation', [p for m,p in calls[before:] if m == 'POST'] == ['/api/tasrev/statement'])
        mode[0] = 'normal'; off = len(cl.text()); cl.send(f'connect 127.0.0.1:{a.port}'); cl.wait('FTESurf CSQC loaded',off,20); time.sleep(1)
        child = (path.parent/'downloaded.tasp').read_bytes(); childsha = tasrev.parse(child)['h']; assert childsha != sha
        cl.query('cmd tas project status',r'tas project: none attached'); time.sleep(.4); before = len(calls)
        cl.query(f'cmd tas project share yes {childsha}',r'tas share: shared revision '+childsha,timeout=30)
        cl.wait(r'tas share: parent '+sha,timeout=5)
        with urlopen(url+'/rev/'+childsha+'/file',timeout=5) as response: assert response.read()==child
        check('explicit retained child uploads without an attached project or invented signature',
              [p for m,p in calls[before:] if m=='POST']==['/api/tasrev/revision'])
        report['result'] = 'PASS'
    except BaseException as exc:
        report['result'] = 'FAIL'; report['error'] = str(exc)
        raise
    finally:
        release.set()
        for peer in reversed(peers): peer.stop()
        for p in acl_paths: deny_read(p, False)
        if locked: clock.drop_lock()
        http.shutdown(); http.server_close(); thread.join(timeout=5)
        report['owned_peers_stopped'] = all(p.proc.poll() is not None for p in peers)
        report['http_calls'] = calls
        (a.out / ('transfer-report.json' if previous else 'report.json')).write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
