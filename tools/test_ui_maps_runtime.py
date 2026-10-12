#!/usr/bin/env python3
"""Bounded navigation runtime falsifiers, never canonical fixture/progs writes.

Process-free: python tools/test_ui_maps_runtime.py --self-test
Gate only:    python tools/test_ui_maps_runtime.py --gate
Runtime:     python tools/test_ui_maps_runtime.py --run --control-progs DIR --subject-progs DIR

Runtime always starts control first, then subject in independent owned overlays.
Each launch is gated; foreign engine processes cause immediate BLOCKED exit 2.
Only this script's Popen handles may be stopped. No clipboard is read/written.
UI clicks use the existing hud_edit fixture helper, not console navigation
shortcuts. Requests, responses, console dispatch and screenshots are retained.
Native provider rectangles are not observable through this helper: native is
explicitly unmeasured, never inferred from fallback or source-only tests.
"""
import argparse
import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import unittest
from urllib.parse import parse_qs, urlsplit
import uuid

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / 'artifacts' / 'navigation-runtime'
SID = ('76561198000008003', '76561198000008002')
WHO = tuple(hashlib.sha256(s.encode('ascii')).hexdigest()[:8] for s in SID)
MAP = 'surf_voyager'
REP = 99001


class Blocked(RuntimeError):
    pass


def process_gate(owned=()):
    """No retries, sleeps, or process termination on a foreign process."""
    script = ("@(Get-CimInstance Win32_Process | Where-Object { "
              "$_.Name -match '(?i)^(ftesurf.*|fteqw.*|ftequake.*|glquake.*|qwsv.*)\\.exe$' "
              "} | Select-Object ProcessId,Name) | ConvertTo-Json -Compress")
    run = subprocess.run(['pwsh', '-NoProfile', '-Command', script],
                         text=True, capture_output=True, timeout=15, check=True)
    items = json.loads(run.stdout.strip() or '[]')
    if isinstance(items, dict):
        items = [items]
    foreign = [p for p in items if int(p['ProcessId']) not in owned]
    if foreign:
        raise Blocked('foreign engine processes: ' + ', '.join(
            '%s PID %s' % (p['Name'], p['ProcessId']) for p in foreign))
    return items


class Fixture:
    """Synthetic surfd protocol, not a test of the real backend implementation."""
    def __init__(self, replay=b'fixture replay'):
        self.events = []
        self.lock = threading.Lock()
        self.replay = replay
        self.rows = []
        for rank in range(1, 331):
            name = 'duplicate' if rank in (1, 2) else ('late-match' if rank >= 205 else 'ordinary-%03d' % rank)
            self.rows.append(dict(r=rank, name=name, ticks=2000 + rank, ms=30000 + rank * 15,
                                  rate=1000 / 15, flags=0, when=1, rep=REP if rank == 3 else 0,
                                  player=SID[rank - 1] if rank <= 2 else '76561198000009%03d' % rank,
                                  tr='ranked', av=0))

    def answer(self, path):
        u = urlsplit(path)
        q = {k: v[-1] for k, v in parse_qs(u.query, keep_blank_values=True).items()}
        delay = 0
        status = 200
        if u.path == '/api/board' and 'player' in q:
            who = q['player']
            if q.get('ct'):
                body = dict(who=who, ct=q['ct'], offset=int(q.get('offset', 0)), total=2, done=1,
                            maps=[dict(map='surf_finished', have=1, ms=45500, tr='ksf', s='segmented'),
                                  dict(map='surf_unfinished', have=0, tr='ranked')])
            else:
                body = dict(who=who, name='duplicate', src='ranked', n=2, maps=2, total=2,
                            by_tier=dict(ranked=1, momentum=1, ksf=0),
                            completion=dict(of=2, done=1, untiered=0,
                                            tiers=[dict(tier=1, of=2, done=1)]),
                            rows=[dict(map='surf_result', track=1, leg=2, tr='momentum',
                                       style='segmented', ms=12345, r=7, of=42, when=1),
                                  dict(map='surf_result_clean', track=0, leg=0, tr='ksf',
                                       ms=23456, r=9, of=50, when=1)])
        elif u.path == '/api/board' and q.get('tier', 'ranked') not in (
                'ranked', 'community', 'practice', 'cheated', 'momentum', 'ksf', 'imported', 'combined'):
            status, body = 400, dict(ok=False, error='bad tier')
        elif u.path == '/api/board' and 'players' not in q:
            name = q.get('name', '')
            rows = self.rows
            if q.get('tier') == 'combined':
                rows = [dict(r, tr='momentum' if r['r'] == 3 else ('ksf' if r['r'] == 4 else 'ranked')) for r in rows]
            if name not in ('missing', 'slow', 'fresh'):
                rows = [r for r in rows if name.lower() in r['name'].lower()]
            elif name == 'fresh':
                rows = [dict(self.rows[1], name='fresh-only')]
            elif name == 'slow':
                delay = 2.5
                rows = [dict(self.rows[0], name='stale-only')]
            off, limit = int(q.get('offset', 0)), int(q.get('limit', 100))
            body = dict(map=q.get('map', MAP), track=int(q.get('track', 0)), leg=int(q.get('leg', 0)),
                        tier=q.get('tier', 'ranked'), style=q.get('style', 'clean'), t=int(time.time()),
                        counts=dict(ranked=sum(r['tr'] == 'ranked' for r in rows), community=0,
                                    momentum=sum(r['tr'] == 'momentum' for r in rows),
                                    ksf=sum(r['tr'] == 'ksf' for r in rows)),
                        total=len(rows), more=off + limit < len(rows), offset=off,
                        rows=copy.deepcopy(rows[off:off + limit]))
            if name and name != 'missing':
                body['name'] = name
        elif u.path == '/api/players' or (u.path == '/api/board' and 'players' in q):
            body = dict(players=[dict(who=WHO[i], name='duplicate', n=2, src='ranked', av=0)
                                 for i in range(2)])
        elif u.path == '/api/replay/%d' % REP:
            body = self.replay
        else:
            status, body = 404, dict(error='fixture route absent')
        event = dict(path=u.path, query=q, status=status, body=body.decode('ascii', errors='replace')
                     if isinstance(body, bytes) else copy.deepcopy(body), delay=delay)
        with self.lock:
            self.events.append(event)
        return status, body, delay

    def since(self, at, path=None):
        with self.lock:
            return [copy.deepcopy(e) for e in self.events[at:] if path is None or e['path'] == path]


def browse_payload(payload):
    """Fixture-side mailbox contract model; not execution of MenuQC."""
    if len(payload) > 128 or not re.fullmatch(r'[A-Za-z0-9_ -]+', payload):
        return None
    words = payload.split()
    if len(words) != 5:
        return None
    mp, source, track, leg, style = words
    if len(mp) > 64 or not re.fullmatch(r'[A-Za-z0-9_-]+', mp):
        return None
    if source not in ('ranked', 'momentum', 'ksf', 'all') or style not in ('clean', 'segmented'):
        return None
    if not re.fullmatch(r'[0-9]{1,3}', track) or not re.fullmatch(r'[0-9]{1,3}', leg):
        return None
    if int(track) > 64 or int(leg) > 256:
        return None
    return mp, source, int(track), int(leg), style


def http_server(fixture):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status, body, delay = fixture.answer(self.path)
            if delay:
                time.sleep(delay)
            data = body if isinstance(body, bytes) else json.dumps(body).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'text/plain' if isinstance(body, bytes) else 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass  # intentionally stale-response client may cancel its request
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def overlay(a, progs, label, junctions):
    rig = a.output / (label + '-' + uuid.uuid4().hex[:10])
    rig.mkdir()
    (rig / 'OWNER.md').write_text('navigation runtime fixture; UTC %s\nOwned: this directory, child PIDs recorded in pids.json, junctions recorded in junctions.json.\nRetain logs/progs/evidence; remove only owned content junctions on stop.\n' % time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    gd = rig / 'ftesurf'
    gd.mkdir()
    shutil.copyfile(ROOT / 'default.fmf', rig / 'default.fmf')
    for name in ('maps', 'gfx', 'models', 'particles'):
        src = a.content / 'ftesurf' / name
        if src.is_dir():
            dst = gd / name
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(dst), str(src)],
                           check=True, capture_output=True)
            junctions.append(dst)
            (rig / 'junctions.json').write_text(json.dumps([str(x) for x in junctions]))
    for name in ('glsl', 'scripts'):
        src = a.content / 'ftesurf' / name
        if src.is_dir():
            shutil.copytree(src, gd / name)
    for name in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
        shutil.copyfile(progs / name, gd / name)
    for rel in subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', 'ftesurf/cfg'], text=True).splitlines():
        dst = rig / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dst)
    shutil.copyfile(ROOT / 'ftesurf/fs_addons.default.txt', gd / 'fs_addons.default.txt')
    (gd / 'data').mkdir()
    (gd / 'data/consent.txt').write_text('FTESURF-CONSENT 1\nversion 4\naccepted 20261012-000000\n')
    (gd / 'downloads/csprogsvers').mkdir(parents=True)
    subprocess.run([sys.executable, str(ROOT / 'tools/seed_csprogs.py'), str(gd / 'csprogs.dat')],
                   check=True, capture_output=True, timeout=30)
    (rig / 'hashes.json').write_text(json.dumps({n: hashlib.sha256((gd / n).read_bytes()).hexdigest()
                                               for n in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')}, indent=2))
    return rig, gd


class Runtime:
    def __init__(self, client, gd, fixture, out, deadline):
        from p615link import Log
        self.client, self.fixture, self.out, self.deadline = client, fixture, out, deadline
        self.gd = gd
        self.keys = None  # Bind the window only after the CSQC spawn control.
        self.log = Log(gd / 'logs/navigation-cl.log')
        self.dispatch = []
        self.results = []

    def send(self, text, wait=0.3):
        if time.monotonic() > self.deadline:
            raise TimeoutError('arm exceeded bounded runtime')
        self.dispatch.append(dict(t=time.monotonic(), command=text))
        (self.out / 'commands.json').write_text(json.dumps(self.dispatch, indent=2))
        marker = 'NAV-ACK-%d' % len(self.dispatch)
        at = len(self.log.text())
        self.client.stdin.write((text + '\necho ' + marker + '\n').encode('ascii'))
        self.client.stdin.flush()
        end = min(self.deadline, time.monotonic() + 20)
        while marker not in self.log.text()[at:]:
            if self.client.poll() is not None or time.monotonic() >= end:
                raise TimeoutError('console dispatch did not act: ' + text)
            time.sleep(0.05)
        if wait:
            time.sleep(wait)

    def section(self, command, wait=0.3):
        at = len(self.log.text())
        self.send(command, wait)
        return self.log.text()[at:]

    def click(self, target):
        probe = self.section('hud_edit ui hover ' + target)
        if 'sui_hover [%s]' % target not in probe:
            raise AssertionError('runtime target absent: ' + target)
        self.send('hud_edit ui down mouse1', 0.08)
        self.send('hud_edit ui up mouse1', 0.6)

    def check(self, name, prediction, action):
        with (self.out / 'predictions.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(name=name, prediction=prediction)) + '\n')
        at = len(self.log.text())
        try:
            action()
            result = dict(name=name, passed=True)
        except (AssertionError, TimeoutError) as exc:
            result = dict(name=name, passed=False, why=str(exc))
        result['console'] = self.log.text()[at:]
        self.results.append(result)
        (self.out / 'results.json').write_text(json.dumps(self.results, indent=2))
        self.send('screenshot nav_%02d' % len(self.results), 0.2)

    def require(self, value, why):
        if not value:
            raise AssertionError(why)

    def board(self):
        self.send('replay stop', 0.1)
        self.send('hud_player close', 0.1)
        self.send('menu_restart', 0.1)
        self.send('ui_close', 0.1)
        self.send('scores open', 0.2)
        self.send('scores tab online', 0.2)
        self.send('scores source ftesurf', 0.2)
        self.send('scores find ""', 0.5)
        self.send('scores oscroll 0', 0.5)
        end = time.monotonic() + 8
        while 'online board: ok' not in self.section('board_status', 0.15):
            if time.monotonic() >= end:
                raise AssertionError('board fetch positive control did not act')

    def owner(self, index, held=False):
        self.board()
        if held:
            self.send('scores close', 0.1)
            self.send('+showscores', 0.5)
        at = len(self.fixture.events)
        if held:
            # A held scoreboard intentionally has no cursor claim. Feed the
            # same fixture event chain; refusal must be positively observed.
            probe = self.section('hud_edit ui hover sb_owner%d' % index)
            self.send('hud_edit ui down mouse1', 0.08)
            self.send('hud_edit ui up mouse1', 0.3)
            self.require('no cursor panel' in probe, 'held TAB did not refuse cursor panel')
        else:
            self.click('sb_owner%d' % index)
        asks = self.fixture.since(at, '/api/board')
        who = [e['query'].get('player') for e in asks if 'player' in e['query']]
        status = self.section('hud_player status')
        if held:
            self.send('-showscores', 0.1)
            self.require(not who and 'hud_player: open 0' in status,
                         'held TAB opened a profile or requested player data')
        else:
            self.require(WHO[index] in who, 'owner did not request exact stable ID: ' + repr(who))
            self.require('view "%s"' % WHO[index] in status and 'hud_player: open 1' in status,
                         'profile did not open for exact owner')

    def query_cases(self):
        self.board()
        at = len(self.fixture.events)
        self.click('pf_qb')
        self.keys.type('late')  # real window key messages, not scores find
        time.sleep(1.0)
        status = self.section('board_status')
        asks = [e for e in self.fixture.since(at, '/api/board') if e['query'].get('name') == 'late']
        self.require(bool(asks), 'typed query did not reach whole board API')
        self.require('205  late-match' in status, 'late real rank205 did not become first match')
        self.require('ranked 126' in status, 'filtered count is not 126')
        self.require(any(e['path'] == '/api/players' or 'players' in e['query']
                         for e in self.fixture.since(at)),
                     'typed query lost player-search dropdown request')
        self.send('scores oscroll 90', 1.0)
        status = self.section('board_status')
        nexts = [e for e in self.fixture.since(at, '/api/board') if e['query'].get('name') == 'late'
                 and int(e['query'].get('offset', 0)) > 0]
        self.require(bool(nexts) and 'rows 126' in status, 'next page did not preserve filter/load matches')
        self.click('pf_qb')
        for _ in range(4):
            self.keys.press('back')
        time.sleep(1.0)
        status = self.section('board_status')
        self.require('ranked 330' in status and 'duplicate' in status,
                     'clear did not restore whole-board count/ranks')

    def echo_cases(self):
        self.board()
        self.send('scores find missing', 1.0)
        missing = self.section('board_status')
        self.require('online board: failed' in missing and 'duplicate' not in missing,
                     'missing active echo displayed whole-table matches')
        self.send('scores find slow', 0.65)
        self.send('scores find fresh', 3.4)
        status = self.section('board_status')
        self.require('fresh-only' in status and 'stale-only' not in status,
                     'late prior query replaced active query')

    def replay_line(self):
        self.board()
        at = len(self.fixture.events)
        self.click('sb_ln2')
        end = time.monotonic() + 8
        lines = self.section('scores lines', 0.5)
        while not re.search(r'line \d+ drawn\s', lines) and time.monotonic() < end:
            lines = self.section('scores lines', 0.5)
        self.require(bool(self.fixture.since(at, '/api/replay/%d' % REP)), 'LINE fetched no replay')
        self.require(re.search(r'line \d+ drawn\s', lines), 'LINE did not draw its fetched recording: ' + lines)
        self.click('sb_ln2')
        # Legacy replay row target, distinct from its owner-cell and LINE box.
        # Hover helper selects the row center; no scores click shortcut.
        at = len(self.fixture.events)
        self.click('sb_ob2')
        state = self.section('replay status', 1.0)
        self.require('replay: nothing loaded' not in state and re.search(r'owner .* map surf_voyager .* samples [1-9]', state),
                     'WATCH did not load fixture samples: ' + state)
        self.require(bool(self.fixture.since(at, '/api/replay/%d' % REP)) or 'replay:' in state,
                     'WATCH had no fetch/cache-open evidence')
        self.send('replay stop', 0.1)

    def rehover(self):
        self.board()
        probe = self.section('hud_edit ui hover sb_owner5')
        self.require('sui_hover [sb_owner5]' in probe, 'owner hover control did not act')
        self.send('vote key 516 1', 0.1)
        self.send('vote key 516 0', 0.4)
        at = len(self.fixture.events)
        # No second hover: P646 requires the resting pointer to target new row6.
        self.send('hud_edit ui down mouse1', 0.08)
        self.send('hud_edit ui up mouse1', 0.7)
        expected = hashlib.sha256(self.fixture.rows[6]['player'].encode('ascii')).hexdigest()[:12]
        asks = [e['query'].get('player') for e in self.fixture.since(at, '/api/board')]
        self.require(expected in asks, 'stationary wheel click retained old owner row: ' + repr(asks))

    def map_pick(self, target, tier=False, finished=False):
        self.send('scores close', 0.1)
        self.send('ui_close', 0.1)
        self.send('hud_player find ""', 0.1)
        self.send('hud_player view ' + WHO[0], 0.8)
        if tier:
            self.send('hud_player tier 1', 0.7)
        before = self.section('status')
        at, log_at = len(self.fixture.events), len(self.log.text())
        self.click(target)
        self.send('ui_board_test status', 0.4)
        after = self.section('status')
        asks = self.fixture.since(at, '/api/board')
        want = dict(map=('surf_finished' if finished else 'surf_unfinished') if tier else 'surf_result',
                    tier=('ksf' if finished else 'ranked') if tier else 'momentum', track='0' if tier else '1',
                    leg='0' if tier else '2', style='segmented' if (finished or not tier) else 'clean')
        self.require(any(all(e['query'].get(k) == v for k, v in want.items()) for e in asks),
                     'browse scope not dispatched exactly: ' + repr(want))
        # Engine status must provide a map observation; absent evidence is a failure.
        extract = lambda s: re.findall(r'(?im)\bmap\s*[:=]\s*(\S+)', s)
        self.require(extract(before) and extract(before)[-1:] == extract(after)[-1:] == [MAP],
                     'server map unchanged not demonstrated by engine status')
        text = self.log.text()[log_at:]
        self.require(not re.search(r'(?i)downloading.*(?:map|bsp)|connecting to|FTESurf CSQC loaded', text),
                     'browse caused download/connect/reload')
        self.require(not (self.gd / 'downloads/maps').exists(), 'browse wrote downloaded maps')
        mailbox = self.section('ui_board_request')
        self.require('ui_board_request' in mailbox and '""' in mailbox, 'mailbox was not consumed/cleared')

    def mailbox_validation(self):
        self.send('ui_close', 0.1)
        invalid = ['bad;echo NAV-INJECTION ranked 0 0 clean', 'map ranked -1 0 clean',
                   'map ranked 65 0 clean', 'map ranked 0 257 clean', 'map ranked 1.5 0 clean',
                   'map ranked 0 0 clean extra', 'map unknown 0 0 clean', 'map ranked 0 0 unknown',
                   'a' * 65 + ' ranked 0 0 clean', 'a' * 129]
        at, log_at = len(self.fixture.events), len(self.log.text())
        for payload in invalid:
            # Constant data contain no quote/backslash; semicolons remain quoted cvar data.
            self.send('set ui_board_request "' + payload + '"', 0.3)
        console = self.log.text()[log_at:]
        self.require(console.count('rejected browse request') == len(invalid),
                     'not all malformed mailbox requests positively rejected')
        self.require(not self.fixture.since(at, '/api/board'), 'invalid mailbox dispatched a board request')
        self.require('NAV-INJECTION' not in console.replace(invalid[0], ''), 'mailbox data executed')
        self.send('set ui_board_request "surf_all all 0 0 clean"', 0.6)
        first = [e for e in self.fixture.since(at, '/api/board') if e['query'].get('map') == 'surf_all']
        self.require(first and first[-1]['query'].get('tier') == 'combined', 'all scope did not use the combined wire tier')
        self.require({r['tr'] for r in first[-1]['body']['rows']} == {'ranked', 'momentum', 'ksf'},
                     'all fixture did not return mixed sources')
        count = len(first)
        time.sleep(0.4)
        first = [e for e in self.fixture.since(at, '/api/board') if e['query'].get('map') == 'surf_all']
        self.require(len(first) == count, 'mailbox was consumed more than once')
        self.send('ui_board_test tab ranked', 0.6)
        first = [e for e in self.fixture.since(at, '/api/board') if e['query'].get('map') == 'surf_all']
        self.require(first[-1]['query'].get('tier') == 'ranked', 'same-tab activation retained all override')
        self.send('ui_board_test close', 0.1)
        self.send('ui_board_test surf_default ranked', 0.6)
        defaults = [e for e in self.fixture.since(at, '/api/board') if e['query'].get('map') == 'surf_default']
        self.require(defaults and all(defaults[-1]['query'].get(k) == v
                                     for k, v in dict(tier='ranked', track='0', leg='0', style='clean').items()),
                     'ordinary Mlb_Open did not restore main/clean defaults')

    def run(self):
        self.check('owner-noav-noreplay-A', 'duplicate row0 opens WHO[0], never WATCH', lambda: self.owner(0))
        self.check('owner-duplicate-B', 'same display name row1 opens distinct WHO[1]', lambda: self.owner(1))
        self.check('held-TAB-refusal', 'no profile request/open while scoreboard is held', lambda: self.owner(0, True))
        self.check('stationary-wheel-rehover', 'one wheel notch changes resting owner5 target to row6 identity', self.rehover)
        self.check('whole-board-filter', 'rank205 is first of126 matches; paging preserves name; clear restores330', self.query_cases)
        self.check('missing-and-stale-echo', 'missing echo fails closed; slow prior query cannot replace fresh', self.echo_cases)
        self.check('LINE-and-WATCH', 'distinct controls fetch recording and produce LINE/replay state', self.replay_line)
        self.check('profile-map-scope', 'result click browses momentum track1 leg2 segmented without moving server', lambda: self.map_pick('pf_map0'))
        self.check('finished-tier-map', 'finished entry s=segmented browses ksf/main/segmented', lambda: self.map_pick('pf_ctmap0', True, True))
        self.check('mailbox-validation', 'invalid data rejected/cleared once, all retained then same-tab resets ranked', self.mailbox_validation)
        self.check('unfinished-tier-map', 'unfinished map clicks browse ranked/main/clean without moving server', lambda: self.map_pick('pf_ctmap1', True))
        return self.results


def arm(a, progs, label):
    junctions = []
    server = client = web = None
    rig = None
    fixture = Fixture((ROOT / 'ftesurf/cfg/test/p492voy.rec').read_bytes())
    try:
        process_gate()  # gate before creating runtime overlay too
        rig, gd = overlay(a, progs, label, junctions)
        web = http_server(fixture)
        url = 'http://127.0.0.1:%d' % web.server_port
        port = None
        for candidate in range(27520, 27621):
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                try:
                    probe.bind(('127.0.0.1', candidate))
                    port = candidate
                    break
                except OSError:
                    continue
        if port is None:
            raise Blocked('no free dedicated lobby test port')
        common = ['-basedir', str(rig), '-manifest', str(rig / 'default.fmf'), '+set', 'cfg_save_auto', '0',
                  '+set', 'log_enable', '1', '+set', 'log_dir', 'logs']
        process_gate()  # immediately before server launch
        server = subprocess.Popen([str(a.server), *common, '+set', 'log_name', 'navigation-sv',
                                   '+set', 'developer', '1', '+set', 'sv_public', '0',
                                   '+set', 'lobby_master', '', '+set', 'sv_guidkey', 'navigation-fixture',
                                   '+set', 'sv_port', str(port), '+map', MAP], cwd=a.content,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (rig / 'pids.json').write_text(json.dumps(dict(server=server.pid)))
        time.sleep(3)
        if server.poll() is not None:
            raise RuntimeError('owned dedicated server exited')
        process_gate((server.pid,))  # immediately before client launch
        client = subprocess.Popen([str(a.client), '-plugin', '-nobrowse', *common,
                                   '+set', 'log_name', 'navigation-cl', '-window', '-nosound',
                                   '+set', 'vid_width', '1600', '+set', 'vid_height', '900',
                                   '+set', 'vid_conautoscale', '1', '+set', 'hud_scale', '2',
                                   '+set', 'ui_native_scores', '0', '+set', 'cl_idlefps', '0',
                                   '+set', 'cl_maxfps', '100', '+set', 'con_savehistory', '0',
                                   '+set', 'developer', '0', '+set', 'log_developer', '0',
                                   '+set', 'lobby_dir', url, '+connect', '127.0.0.1:%d' % port],
                                  cwd=a.content, stdin=subprocess.PIPE,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (rig / 'pids.json').write_text(json.dumps(dict(server=server.pid, client=client.pid)))
        run = Runtime(client, gd, fixture, rig, time.monotonic() + 300)
        if not run.log.wait('FTESurf CSQC loaded', 40):
            raise RuntimeError('socket spawn/CSQC load control did not act')
        from p615link import Keys
        run.keys = Keys(client.pid)
        run.send('closemenu', 0.1)
        run.send('con_notifytime 0', 0.1)
        end = time.monotonic() + 20
        while MAP not in run.section('scores status', 0.2):
            if time.monotonic() >= end:
                raise RuntimeError('scoreboard map/spawn control did not act')
        results = run.run()
        return dict(label=label, rig=str(rig), results=results,
                    native='not measured: production provider hit rectangles not available through SUI helper',
                    paste='not measured: no explicit clipboard fixture helper authorized')
    finally:
        for process in (client, server):
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()  # exact owned child handle only
                    process.wait(timeout=5)
        if web is not None:
            web.shutdown()
            web.server_close()
        if rig is not None:
            (rig / 'requests.json').write_text(json.dumps(fixture.events, indent=2))
        for path in junctions:
            if not (path.lstat().st_file_attributes & 0x400):
                raise RuntimeError('refusing removal of non-junction: ' + str(path))
            path.rmdir()


class FixtureTests(unittest.TestCase):
    def test_original_rank_filter_counts_paging_clear(self):
        f = Fixture()
        _, body, _ = f.answer('/api/board?name=late&limit=100')
        self.assertEqual((body['rows'][0]['r'], body['total'], body['name']), (205, 126, 'late'))
        _, body, _ = f.answer('/api/board?name=late&limit=100&offset=100')
        self.assertEqual((len(body['rows']), body['rows'][0]['r'], body['more']), (26, 305, False))
        _, body, _ = f.answer('/api/board')
        self.assertEqual(body['counts']['ranked'], 330)
        self.assertNotIn('name', body)
        status, rejected, _ = f.answer('/api/board?tier=all')
        self.assertEqual((status, rejected['error']), (400, 'bad tier'))
        _, allbody, _ = f.answer('/api/board?tier=combined')
        self.assertEqual({r['tr'] for r in allbody['rows']}, {'ranked', 'momentum', 'ksf'})
        self.assertEqual(sum(allbody['counts'].values()), 330)

    def test_duplicate_stable_ids_no_picture_no_recording(self):
        f = Fixture()
        a, b = f.rows[:2]
        self.assertEqual(a['name'], b['name'])
        self.assertNotEqual(a['player'], b['player'])
        self.assertEqual((a['av'], b['av'], a['rep'], b['rep']), (0, 0, 0, 0))
        self.assertNotEqual(*WHO)

    def test_missing_and_delayed_echo(self):
        f = Fixture()
        _, body, _ = f.answer('/api/board?name=missing')
        self.assertNotIn('name', body)
        _, body, delay = f.answer('/api/board?name=slow')
        self.assertEqual((body['name'], body['rows'][0]['name']), ('slow', 'stale-only'))
        self.assertGreater(delay, 2)
        _, body, _ = f.answer('/api/board?name=fresh')
        self.assertEqual(body['rows'][0]['name'], 'fresh-only')

    def test_profiles_scope_and_unfinished(self):
        f = Fixture()
        _, body, _ = f.answer('/api/board?player=' + WHO[0])
        r = body['rows'][0]
        self.assertEqual((r['track'], r['leg'], r['tr'], r['style']), (1, 2, 'momentum', 'segmented'))
        self.assertNotIn('style', body['rows'][1])
        _, body, _ = f.answer('/api/board?player=' + WHO[0] + '&ct=1')
        self.assertEqual((body['maps'][0]['tr'], body['maps'][0]['s']), ('ksf', 'segmented'))
        self.assertEqual((body['maps'][1]['map'], body['maps'][1]['have']), ('surf_unfinished', 0))
        self.assertNotIn('s', body['maps'][1])

    def test_mailbox_bounds_and_untrusted_data(self):
        self.assertEqual(browse_payload('surf_result momentum 1 2 segmented'),
                         ('surf_result', 'momentum', 1, 2, 'segmented'))
        self.assertEqual(browse_payload('surf_all all 64 256 clean'), ('surf_all', 'all', 64, 256, 'clean'))
        invalid = ['', 'map ranked 0 0 clean extra', 'map ranked -1 0 clean',
                   'map ranked 65 0 clean', 'map ranked 0 257 clean', 'map ranked 1.0 0 clean',
                   'map ranked 1e2 0 clean', 'map other 0 0 clean', 'map ranked 0 0 other',
                   '"map" ranked 0 0 clean', 'map ranked 0 0 clean;echo BAD',
                   'map/other ranked 0 0 clean', 'a' * 65 + ' ranked 0 0 clean', 'a' * 129]
        for payload in invalid:
            with self.subTest(payload=payload):
                self.assertIsNone(browse_payload(payload))

    def test_http_wire_echo_and_body_capture(self):
        from urllib.request import urlopen
        f = Fixture()
        web = http_server(f)
        try:
            with urlopen('http://127.0.0.1:%d/api/board?name=late&offset=100' % web.server_port,
                         timeout=3) as reply:
                body = json.load(reply)
            self.assertEqual((body['name'], body['rows'][0]['r']), ('late', 305))
            self.assertEqual(f.events[0]['query']['name'], 'late')
            self.assertEqual(f.events[0]['body'], body)
            _, body, _ = f.answer('/api/board?name=%C3%86')
            self.assertEqual(body['name'], 'Æ')  # echo preserves nonASCII, no case rejection
        finally:
            web.shutdown()
            web.server_close()

    def test_gate_foreign_and_owned_no_launch(self):
        from unittest.mock import patch
        fake = subprocess.CompletedProcess([], 0, '[{"Name":"ftesurf64.exe","ProcessId":18888}]', '')
        with patch.object(subprocess, 'run', return_value=fake):
            with self.assertRaisesRegex(Blocked, 'ftesurf64.exe PID 18888'):
                process_gate()
            self.assertEqual(len(process_gate((18888,))), 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--self-test', action='store_true')
    mode.add_argument('--gate', action='store_true')
    mode.add_argument('--run', action='store_true')
    ap.add_argument('--control-progs', type=Path)
    ap.add_argument('--subject-progs', type=Path)
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    ap.add_argument('--server', type=Path, default=Path('C:/FTEQuake/fteqwsv64.exe'))
    ap.add_argument('--output', type=Path, default=OUT)
    a = ap.parse_args()
    if a.self_test:
        return 0 if unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FixtureTests)).wasSuccessful() else 1
    a.output = a.output.resolve()
    if a.output != OUT.resolve():
        ap.error('--output must be the owned artifacts/navigation-runtime path')
    a.output.mkdir(parents=True, exist_ok=True)
    try:
        process_gate()
        if a.gate:
            (a.output / 'gate.json').write_text(json.dumps(dict(status='quiet')))
            print('QUIET: no engine processes; this is not launch authorization')
            return 0
        if not a.control_progs or not a.subject_progs:
            ap.error('--run requires --control-progs and --subject-progs')
        for directory in (a.control_progs, a.subject_progs):
            for name in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
                if not (directory / name).is_file():
                    ap.error('missing progs: ' + str(directory / name))
        for name in ('csprogs.dat', 'menu.dat'):
            if (a.control_progs / name).read_bytes() == (a.subject_progs / name).read_bytes():
                ap.error('control and subject must have distinct ' + name)
        reports = [arm(a, a.control_progs.resolve(), 'control'), arm(a, a.subject_progs.resolve(), 'subject')]
        (a.output / 'runtime-report.json').write_text(json.dumps(reports, indent=2))
        subject_ok = all(r['passed'] for r in reports[1]['results'])
        new = ('owner-noav-noreplay-A', 'owner-duplicate-B', 'whole-board-filter',
               'missing-and-stale-echo', 'profile-map-scope', 'finished-tier-map', 'mailbox-validation', 'unfinished-tier-map')
        control_rejected = all(not r['passed'] for r in reports[0]['results'] if r['name'] in new)
        control_regressions = all(r['passed'] for r in reports[0]['results']
                                  if r['name'] in ('held-TAB-refusal', 'LINE-and-WATCH'))
        # No full acceptance while native/paste remain unmeasured.
        print('Fallback subject=%s; base falsifiers rejected=%s; base regressions=%s; native/paste UNMEASURED' %
              (subject_ok, control_rejected, control_regressions))
        return 0 if subject_ok and control_rejected and control_regressions else 1
    except Blocked as exc:
        (a.output / 'gate.json').write_text(json.dumps(dict(status='blocked', reason=str(exc)), indent=2))
        print('BLOCKED: ' + str(exc))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
