#!/usr/bin/env python3
"""Three genuine dedicated clients + real surfd/proofs; synthetic Steam fixtures.

--output-dir MUST be under an owned task root, --progs-dir is the inspected
NoDeploy build. Logs/keys stay in that owned root; only sanitized verdicts print.
Other games/content are read via runlines_smoke's removable junctions. Does not
replace installs, contact Steam, or operate on another process. No account proof
bypass: the fixture associates newly seen keys with synthetic accounts, and the
ordinary account endpoint still verifies every actual signature/game code.
"""
import argparse
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--progs-dir', type=Path, required=True)
    ap.add_argument('--review-controls', action='store_true',
                    help='force first renewal HTTP failure; wheel/reorder/roster action controls')
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--port', type=int, default=27618)
    ap.add_argument('--http-port', type=int, default=27637)
    a = ap.parse_args()
    out = a.output_dir.resolve(); out.mkdir(parents=True, exist_ok=True)
    if not any((p / 'OWNER.md').is_file() for p in (out, *out.parents)):
        raise SystemExit('An owned task root with OWNER.md is required')
    if os.name == 'nt':
        busy = subprocess.run(['pwsh', '-NoProfile', '-Command',
            'if (Get-Process ftesurf64,fteqw64,fteqwsv64 -ErrorAction SilentlyContinue) { exit 2 }'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if busy.returncode:
            print('Desktop rig busy: owner/peer games must not be stopped; retry when idle')
            return 2
    for kind, port in ((socket.SOCK_DGRAM, a.port), (socket.SOCK_STREAM, a.http_port)):
        with socket.socket(socket.AF_INET, kind) as s: s.bind(('127.0.0.1', port))
    home = out / 'surfd-home'; home.mkdir()
    (home / 'surfd.env').write_text('SURFD_KEY=testkey\n')
    os.environ.update(SURFD_HOME=str(home), SURFD_DB=str(home / 'test.db'),
                      SURFD_ENV=str(home / 'surfd.env'), SURFD_LINK_HOSTS='127.0.0.1',
                      SURFD_GAME_CODE=str(a.progs_dir / 'csprogs.dat'),
                      SURFD_BOARD_URL='http://127.0.0.1:%d/board' % a.http_port,
                      SURFD_TOOLS=str(ROOT / 'tools'))
    os.environ.pop('SURFD_STEAM_KEY', None)
    sys.path.insert(0, str(ROOT / 'surfd'))
    import surfd as S
    import accounts as A
    from flask import Response, request
    from werkzeug.serving import make_server, WSGIRequestHandler
    ids = ['7656119800000000%d' % i for i in (1, 2, 3)]
    marks = [A.who_of(i) for i in ids]
    seen = {}
    control = {'third_present_at_send': False, 'sent_at': 0, 'expired': False,
               'refresh_faults': 0, 'actions': []}
    with S.app.app_context():
        with S.get_db() as db:
            for sid, name in zip(ids, ('Alice', 'Bob', 'Third')):
                db.execute('INSERT INTO accounts(steamid,name,created_at) VALUES(?,?,?)',
                           (sid, name, int(time.time())))

    @S.app.before_request
    def synthetic_link():
        # Avatar transport/render/cache fixture, not a live Steam/R2 fetch.
        avatar = request.args.get('avatar')
        if request.path == '/api/board' and avatar in marks:
            role = marks.index(avatar)
            colors = ('2488ffff', 'ff9944ff', '33dd88ff')
            rows = [''.join(colors[role] if ((x // 8 + y // 8) % 2) else 'eeeeeeff'
                            for x in range(32)) + '\n' for y in range(32)]
            return Response('FTESURF-AVATAR 1 32 32\n' + ''.join(rows), mimetype='text/plain')
        if request.path == '/api/social/action':
            control['actions'].append((request.form.get('op'), request.form.get('who')))
        if request.path == '/api/social/action' and request.form.get('op') == 'message':
            n = S.get_db().execute('SELECT count(DISTINCT steamid) FROM social_sessions WHERE seen>?',
                                  (int(time.time()) - 16,)).fetchone()[0]
            control['third_present_at_send'] = (n == 3)
            control['sent_at'] = int(time.time())
        if request.path == '/api/social/poll' and control['sent_at']:
            if time.time() > control['sent_at'] + 12 and not control['expired']:
                with S.get_db() as db:
                    db.execute('UPDATE social_sessions SET issued=? WHERE steamid=?',
                               (int(time.time()) - 86401, ids[0]))
                control['expired'] = True
        if request.path != '/api/account': return
        pub = request.form.get('pub', '')
        if not re.fullmatch('[0-9a-f]{64}', pub): return
        db = S.get_db()
        if pub not in seen:
            if len(seen) >= 3: return
            seen[pub] = ids[len(seen)]
        sid = seen[pub]
        if a.review_controls and control['expired'] and sid == ids[0] and not control['refresh_faults']:
            control['refresh_faults'] += 1
            return {'ok': False, 'error': 'synthetic transient renewal failure'}, 503
        with db:
            db.execute('INSERT OR IGNORE INTO accounts(steamid,name,created_at) VALUES(?,?,?)',
                       (sid, ['Alice', 'Bob', 'Third'][ids.index(sid)], int(time.time())))
            db.execute('INSERT OR IGNORE INTO keylinks(pub,steamid,linked_at) VALUES(?,?,?)',
                       (pub, sid, int(time.time())))

    class Quiet(WSGIRequestHandler):
        def log(self, *args): pass
    web = make_server('127.0.0.1', a.http_port, S.app, request_handler=Quiet)
    thread = threading.Thread(target=web.serve_forever, daemon=True); thread.start()
    base = '''cfg_save_auto 0
developer 1
log_developer 1
log_enable 1
log_dir logs
log_name runlines_smoke
con_notifytime 0
con_notifylines 0
cl_idlefps 0
cl_maxfps 100
vid_fullscreen 0
vid_winmaximize 0
vid_width 1280
vid_height 720
vid_conautoscale 1
sv_public 0
waitms 2000
%s
waitmap 60
waitms 6000
menu_restart
ui_close
set rec_terms 5
set hud_scale 2
set lobby_dir "http://127.0.0.1:%d"
cmd zone_goto 0 0 0
waitms 500
'''
    private_text = 'private hello; "literal" $no_execution'
    alice = base % ('map surf_dune', a.http_port) + '''waitms 35000
hud_player view %s
waitms 1500
hud_player status
screenshot friends_profile_add.png
hud_edit ui hover av_friend
waitms 200
hud_edit ui down mouse1
waitms 100
hud_edit ui up mouse1
waitms 500
hud_player close
waitms 35000
friends_status
hud_player friends
waitms 500
hud_edit ui hover fr_msg%s
waitms 200
hud_edit ui down mouse1
waitms 100
hud_edit ui up mouse1
waitms 300
chat_rows
%s
vote key 13 1
vote key 13 0
waitms 6000
scores open
waitms 500
scores tab players
waitms 1000
scores status
scores pics
screenshot friends_players.png
scores close
hud_player view %s
waitms 1500
hud_edit ui hover pf_qa
waitms 200
hud_edit ui down mouse1
waitms 100
hud_edit ui up mouse1
waitms 200
hud_player status
vote key 27 1
vote key 27 0
waitms 300
hud_player status
hud_player friends
waitms 1000
friends_status
screenshot friends_account.png
hud_player close
+back
waitms 800
-back
waitms 800
body_stats
cmd pose_stats
set cl_yawspeed 45
+left
waitms 1000
playerlabels_status
waitms 1000
playerlabels_status
waitms 1000
playerlabels_status
waitms 1000
playerlabels_status
waitms 1000
playerlabels_status
waitms 1000
playerlabels_status
waitms 1000
playerlabels_status
waitms 1000
playerlabels_status
-left
screenshot friends_labels.png
waitms 30000
echo RUNLINES COMPLETE
quit
''' % (marks[1], marks[1], '\n'.join('vote key 0 1 %d\nvote key 0 0' % ord(c) for c in private_text), marks[1])
    bob = base % ('connect 127.0.0.1:%d' % a.port, a.http_port) + '''waitms 40000
cmd friend accept %s
waitms 35000
friends_status
chat_rows
echo RUNLINES COMPLETE
quit
''' % marks[0]
    third = base % ('set spectator 1\nconnect 127.0.0.1:%d' % a.port, a.http_port) + '''waitms 49000
friends_status
chat_rows
echo RUNLINES COMPLETE
quit
'''
    if a.review_controls:
        # Trusted local snapshot: synthetic UX rows, not backend authority.
        wheel = 'friend_begin\n' + ''.join(
            'friend_row %08x 1 0 Synthetic%d "" ""\n' % (j+1, j) for j in range(20))
        wheel += '''friend_end
waitms 200
hud_edit ui hover fr_list
hud_edit ui down mwheeldown
waitms 100
friends_status
hud_edit ui hover av_pg0
hud_edit ui up mwheeldown
hud_edit ui hover fr_list
hud_edit ui down mwheelup
waitms 100
friends_status
hud_edit ui up mwheelup
friend_begin
friend_row 00000001 3 0 Synthetic1 "" ""
friend_row 00000002 3 0 Synthetic2 "" ""
friend_end
waitms 200
hud_edit ui hover fr_del00000001
hud_edit ui down mouse1
waitms 100
friend_begin
friend_row 00000002 3 0 Synthetic2 "" ""
friend_row 00000001 3 0 Synthetic1 "" ""
friend_end
waitms 100
hud_edit ui up mouse1
waitms 300
friend_begin
friend_row RESTORE_BOB 3 1 Bob unnamed surf_dune
friend_end
waitms 200
'''.replace('RESTORE_BOB', marks[1])
        target = 'hud_edit ui hover fr_msg'+marks[1]
        alice = alice.replace(target, wheel+target)
        actions = '''hud_edit ui hover pl_chat1
hud_edit ui down mouse1
waitms 100
hud_edit ui up mouse1
waitms 200
hud_edit ui hover pl_chat1
hud_edit ui down mouse1
waitms 100
hud_edit ui up mouse1
waitms 200
hud_edit ui hover pl_voice1
hud_edit ui down mouse1
waitms 100
hud_edit ui up mouse1
waitms 200
cl_voip_mute
hud_edit ui hover pl_voice1
hud_edit ui down mouse1
waitms 100
hud_edit ui up mouse1
waitms 200
hud_edit ui hover pl_spec1
hud_edit ui down mouse1
waitms 100
hud_edit ui up mouse1
waitms 3000
spectate status
spectate off
waitms 2000
'''
        alice = alice.replace('screenshot friends_players.png\n', 'screenshot friends_players.png\n'+actions)
        join = '''hud_player friends
waitms 800
hud_edit ui hover fr_joinMARK
hud_edit ui down mouse1
waitms 100
hud_edit ui up mouse1
waitms 15000
'''.replace('MARK', marks[1])
        alice = alice.replace('echo RUNLINES COMPLETE', join+'echo RUNLINES COMPLETE')
    # Third must still be present WHEN the PM is sent, not merely earlier.
    bob = bob.replace('echo RUNLINES COMPLETE', 'waitms 80000\nchat_rows\necho RUNLINES COMPLETE')
    third = third.replace('echo RUNLINES COMPLETE', 'waitms 110000\nchat_rows\necho RUNLINES COMPLETE')
    processes = []
    outputs = []
    try:
        for i, cfg in enumerate((alice, bob, third)):
            folder = out / ('client%d' % i); folder.mkdir()
            path = folder / 'control.cfg'; path.write_text(cfg)
            log = (folder / 'harness.log').open('w'); outputs.append(log)
            cmd = [sys.executable, '-B', str(ROOT / 'tools/runlines_smoke.py'), str(path),
                   '--mount', '--content', str(a.content), '--output-dir', str(folder), '--timeout', '250',
                   '--ssqc', str(a.progs_dir / 'qwprogs.dat'), '--csqc', str(a.progs_dir / 'csprogs.dat'),
                   '--mqc', str(a.progs_dir / 'menu.dat')]
            if i == 0:
                cmd += ['--dedicated', '--port', str(a.port), '--map', 'surf_dune',
                        '--server-arg', '+set maxclients 8 +set sv_playerslots 8 +set lobby_enable 1 +set lobby_nocollide 1 +set lobby_mode 2 +set lobby_master http://127.0.0.1:%d +set lobby_master_key testkey' % a.http_port]
            p = subprocess.Popen(cmd, stdout=log, stderr=log); processes.append(p)
            # Sequential proof controls establish fixture identity, not arbitrary sleep.
            end = time.monotonic() + 60
            while time.monotonic() < end:
                if p.poll() is not None: raise RuntimeError('Client%d stopped before authenticating' % i)
                with sqlite3.connect(home / 'test.db') as db:
                    n = db.execute('SELECT count(DISTINCT steamid) FROM social_sessions').fetchone()[0]
                if n >= i + 1: break
                time.sleep(.2)
            else: raise RuntimeError('Client%d did not authenticate' % i)
        for p in processes:
            if p.wait(timeout=280): raise RuntimeError('Runtime harness did not complete')
        logs = []
        for i in range(3):
            paths = list((out / ('client%d' % i)).glob('ftesurf-runlines-*/ftesurf/logs/runlines_smoke.log'))
            if len(paths) != 1: raise RuntimeError('Expected one retained client log')
            logs.append(paths[0].read_text(errors='replace'))
        with sqlite3.connect(home / 'test.db') as db:
            renewed = db.execute('SELECT count(*) FROM social_sessions WHERE steamid=? AND issued>?',
                                 (ids[0], control['sent_at'] + 12)).fetchone()[0]
        refresh = logs[0].find('Refreshing%20Steam%20for%20Friends')
        renewed = renewed > 0 and refresh >= 0 and logs[0].find('friend_end', refresh) > refresh
        # Final disconnect intentionally zeros seen; it is NOT a failed renewal.
        # The fresh proof's issue timestamp + delivered list after the refresh
        # prove it acted without requiring a departed player to remain online.
        checks = {
            'Expired capability automatically refreshes through a new proof': control['expired'] and renewed,
            'Third present when message sent (privacy control acted)': control['third_present_at_send'],
            'Alice/Bob private friend list delivered': all('friends: ready 1 rows 1' in s for s in logs[:2]),
            'Third has no friendship list entries': 'friends: ready 1 rows 0' in logs[2],
            'Display pictures uploaded from avatar transport': bool(re.search(r'steampic: asked [1-9]\d* got [1-9]', logs[0])),
            'Pictures persist in game cache': len(list((out / 'client0').glob('ftesurf-runlines-*/ftesurf/data/cache/steampic/*.txt'))) >= 2,
            'Message button opens private chat draft': 'typing 1' in logs[0],
            'Private message reaches Bob': private_text in logs[1] and '[PM from Alice' in logs[1],
            'No private message reaches Third': private_text not in logs[2] and '[PM from Alice' not in logs[2],
            'Other profile open control acted': bool(re.search(r'hud_player: open 1 .*view "%s"' % marks[1], logs[0])),
            'Profile search focus control acted': bool(re.search(r'hud_player: open 1 .*keys 1', logs[0])),
            'One ESC fully closes other profile': bool(re.search(r'hud_player: open 0 ', logs[0])),
            'Overhead labels actually draw': any(int(n) > 0 for n in re.findall(r'playerlabels: drawn (\d+)', logs[0])),
        }
        if a.review_controls:
            checks.update({
                'First renewal HTTP failure actually acted': control['refresh_faults'] == 1,
                'Renewal recovers after forced failure': control['refresh_faults'] == 1 and renewed,
                'Friend wheel both edges owned': all('sui_event '+edge+' '+key+' took 1' in logs[0]
                    for edge in ('down', 'up') for key in ('mwheelup', 'mwheeldown')),
                'Friend wheel moved': any(float(v) > 0 for v in re.findall(r'friends: scroll ([0-9.]+)', logs[0])),
                'Wheel release after cursor left list': bool(re.search(
                    r'sui_event down mwheeldown took 1.*sui_hover \[av_pg0\].*sui_event up mwheeldown took 1',
                    logs[0], re.S)) and 'friends: scroll 0.0 wheel 0' in logs[0],
                'Reordered hold never targets replacement': 'sui_hover [fr_del00000001]' in logs[0]
                    and not any(who == '00000002' for op, who in control['actions']),
                'Roster chat mute toggled twice': 'Bob silenced' in logs[0] and 'Bob unsilenced' in logs[0],
                'Roster voice mute toggled twice': 'Added user Bob to mute list' in logs[0]
                    and 'Removed user Bob from mute list' in logs[0],
                'Roster Spectate control acted': 'sui_hover [pl_spec1]' in logs[0]
                    and bool(re.search(r'target.*Bob', logs[0])),
                'Friend Join reconnect acted': logs[0].count('Connecting to 127.0.0.1:') >= 2,
            })
        (out/'verdict.json').write_text(json.dumps(checks, indent=2))
        for label, ok in checks.items(): print(('ok   ' if ok else 'FAIL ') + label)
        return 0 if all(checks.values()) else 1
    finally:
        for p in processes:
            # Let runlines' bounded timeout/finally stop ITS native handles.
            # Killing this Python wrapper would bypass that cleanup on Windows.
            if p.poll() is None:
                try: p.wait(timeout=280)
                except subprocess.TimeoutExpired:
                    print('Retained active owned harness PID %d; cleanup blocked' % p.pid)
        for log in outputs: log.close()
        web.shutdown(); thread.join(timeout=10)


if __name__ == '__main__':
    raise SystemExit(main())
