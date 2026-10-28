#!/usr/bin/env python3
"""Isolated, deny-by-default zone upload service using linked Steam key proofs.

No surfd schema migration or leaderboard writes. Run behind the existing HTTPS
host on a loopback socket; do not replace a sealed surfd generation. The
operator creates this service's separate store and grants roles explicitly.
P815: with publish directories configured, an admin's accepted upload is queued
and written into each of them (the lobbies' zones/local and the site's zones)
once no lobby has had the map loaded for a while (zonepub_publish.py, zonepub.md).
"""
import argparse
from contextlib import contextmanager
import os
import hashlib
import json
import math
from pathlib import Path
import re
import secrets
import sqlite3
import sys
import time
from flask import Flask, jsonify, request
import accounts
import zonepub_publish as pub

MAX_ZONE_BYTES = 262144
# A string only P815's cl_zonepublish.qc carries: the P729 client signs the same kind and
# posts the same body, from any server and any click.
PUBLISH_MARKER = b'a command cannot start a publish'
# P1081: only a client that offers "reload now" may ask for it (cl_zonepublish.qc's dialog text).
NOW_MARKER = b'Lobbies on it are warned, then reload'
SITE = 'play.proto.bar:443'
KIND = -6
NAME = re.compile(r'[a-z0-9_-]{1,64}')
HEX64 = re.compile(r'[0-9a-f]{64}')
PREFIX = re.compile(rb'^\{"nonce":"([0-9a-f]{32})","pub":"([0-9a-f]{64})","sig":"([0-9a-f]{128})","game":"([0-9a-f]{64})","zones":')
SQL = '''
CREATE TABLE IF NOT EXISTS roles(steamid TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS challenges(nonce TEXT PRIMARY KEY, map TEXT NOT NULL,
 sha TEXT NOT NULL, peer TEXT NOT NULL, created INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
 nonce_now TEXT);
CREATE TABLE IF NOT EXISTS drafts(id TEXT PRIMARY KEY, map TEXT NOT NULL,
 sha TEXT NOT NULL, steamid TEXT NOT NULL, pub TEXT NOT NULL, created INTEGER NOT NULL,
 body BLOB NOT NULL, UNIQUE(map,sha));
''' + pub.SQL


def valid_name(name):
    return isinstance(name, str) and NAME.fullmatch(name) is not None


@contextmanager
def connect(path, readonly=False):
    uri = Path(path).resolve().as_uri() + ('?mode=ro' if readonly else '?mode=rw')
    db = sqlite3.connect(uri, uri=True, timeout=0.25)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


def migrate(db):
    # P1081 columns on a store made before them; CREATE IF NOT EXISTS leaves old tables alone.
    if 'nonce_now' not in {r[1] for r in db.execute('PRAGMA table_info(challenges)')}:
        db.execute('ALTER TABLE challenges ADD COLUMN nonce_now TEXT')
    pub.migrate(db)


def initialize(path):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    try:
        with db:
            db.executescript(SQL)
            migrate(db)
    finally: db.close()
    os.chmod(path, 0o600)


def validate(body):
    """Only what the game reads, read the same way: sh_zonefile.qc's limits, and no
    construct the engine's JSON parser reads differently from Python's."""
    if not 16 <= len(body) <= MAX_ZONE_BYTES:
        raise ValueError('Zone file size outside supported range')
    # The engine keeps duplicate keys (finds the first) and stores key escapes raw;
    # no zone file needs either, and the shipped 648 contain neither.
    if b'\\' in body: raise ValueError('Escapes are not accepted in zone files')
    def pairs(items):
        keys = [k for k, _ in items]
        if len(keys) != len(set(keys)): raise ValueError('Duplicate key')
        return dict(items)
    def constant(_):
        raise ValueError('Non-finite coordinate')
    def num(cast):
        # The engine reads at most 127 characters of a number (json.c JSON_ReadFloat).
        def parse(token):
            if len(token) > 32: raise ValueError('Number too long')
            return cast(token)
        return parse
    obj = json.loads(body.decode('utf-8'), parse_constant=constant, object_pairs_hook=pairs,
                     parse_float=num(float), parse_int=num(int))
    todo, nodes = [(obj, 0)], 0
    while todo:
        item, depth = todo.pop(); nodes += 1
        if nodes > 50000: raise ValueError('Zone structure too complex')
        if isinstance(item, (dict, list)):
            kids = item.values() if isinstance(item, dict) else item
            if kids and depth >= 16: raise ValueError('Zone structure too deep')
            todo.extend((v, depth + 1) for v in kids)
        elif isinstance(item, (int, float)) and not isinstance(item, bool):
            if not (math.isfinite(item) and abs(item) <= 1e30): raise ValueError('Number out of range')
    if not isinstance(obj, dict) or type(obj.get('formatVersion')) is not int or obj.get('formatVersion') != 1:
        raise ValueError('Expected Momentum zone formatVersion 1')
    # P841: the lobbies' speed cap. 0 is "not set"; the engine ignores anything outside 1..100000.
    if 'maxVelocity' in obj:
        mv = obj['maxVelocity']
        if isinstance(mv, bool) or not isinstance(mv, (int, float)) or not (mv == 0 or 1 <= mv <= 100000):
            raise ValueError('maxVelocity must be 0 or 1..100000')
    count = points = 0
    def number(x):
        if isinstance(x, bool) or not isinstance(x, (int, float)) or abs(x) > 10000000:
            raise ValueError('Invalid zone coordinate')
        return x
    def regions(value, empty=False):
        nonlocal count, points
        if not isinstance(value, list) or len(value) > 128 or (not value and not empty):
            raise ValueError('Expected regions')
        for r in value:
            if not isinstance(r, dict): raise ValueError('Expected region')
            p = r.get('points')
            if not isinstance(p, list) or not 3 <= len(p) <= 128: raise ValueError('Invalid polygon')
            for xy in p:
                if not isinstance(xy, list) or len(xy) != 2: raise ValueError('Invalid point')
                number(xy[0]); number(xy[1])
            if abs(sum(p[i][0]*p[(i+1)%len(p)][1]-p[(i+1)%len(p)][0]*p[i][1] for i in range(len(p)))) < 0.01:
                raise ValueError('Collapsed polygon')
            number(r.get('bottom')); h = number(r.get('height'))
            if h <= 0: raise ValueError('Invalid zone height')
            if 'teleDestPos' in r:
                d = r['teleDestPos']
                if not isinstance(d, list) or len(d) != 3: raise ValueError('Invalid teleport destination')
                for v in d: number(v)
            if 'teleDestYaw' in r: number(r['teleDestYaw'])
            if 'teleDestTargetname' in r and (not isinstance(r['teleDestTargetname'], str)
                                              or len(r['teleDestTargetname']) > 128):
                raise ValueError('Invalid teleport target')
            count += 1; points += len(p)
            if count > 256 or points > 2048: raise ValueError('Zone file exceeds game table capacity')
        return len(value)
    tracks = obj.get('tracks')
    if not isinstance(tracks, dict) or not isinstance(tracks.get('main'), dict):
        raise ValueError('Missing main track')
    bonuses = tracks.get('bonuses')
    if bonuses is None: bonuses = []
    if not isinstance(bonuses, list) or len(bonuses) > 16: raise ValueError('Too many bonus tracks')
    for track in [tracks['main']] + bonuses:
        z = track.get('zones') if isinstance(track, dict) else None
        if not isinstance(z, dict): raise ValueError('Missing track zones')
        segs = z.get('segments')
        if not isinstance(segs, list) or not 1 <= len(segs) <= 128: raise ValueError('Missing start zone')
        for seg in segs:
            cps = seg.get('checkpoints') if isinstance(seg, dict) else None
            if not isinstance(cps, list) or not 1 <= len(cps) <= 128: raise ValueError('Missing segment start')
            for cp in cps:
                if not isinstance(cp, dict): raise ValueError('Empty checkpoint')
                regions(cp.get('regions'))
        end = z.get('end')
        if not isinstance(end, dict): raise ValueError('Missing finish zone')
        regions(end.get('regions'))
    global_regions = obj.get('globalRegions')
    if global_regions is not None:
        if not isinstance(global_regions, dict): raise ValueError('Invalid global regions')
        for value in global_regions.values(): regions(value, empty=True)
    return obj


SWEEP_LOG = '/srv/nvme/surfd/logs/sweep.log'


def create_app(store, account_db, game_files, clock=time.time, verify=None, publish_dirs=(),
               maps_fn=None, sweep_log=SWEEP_LOG, rcon_fn=pub.lobby_rcon):
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = MAX_ZONE_BYTES + 1024
    store, account_db = Path(store), Path(account_db)
    if store.exists():
        with connect(store) as db: migrate(db)
    if maps_fn is None:     # account_db is surfd.db: its lobbies and replays tables too
        maps_fn = lambda: pub.lobby_state(account_db, sweep_log, clock())
    games = tuple(Path(p) for p in game_files)
    publish_dirs = tuple(Path(p) for p in publish_dirs)
    peer_salt = secrets.token_bytes(32)
    # P826: a refusal answers 200 with ok=0. The game's HTTP client keeps no body for any
    # other status (httpclient.c), so the reason would never reach the player.
    def fail(message, status): return jsonify(ok=0, error=message, status=status), 200
    @app.before_request
    def body_budget():
        # Older Werkzeug does not enforce MAX_CONTENT_LENGTH in get_data().
        # Native HTTP and the buffering nginx proxy both supply an exact length.
        if request.method == 'POST':
            size = request.content_length
            if size is None or size <= 0: return fail('Request length required', 411)
            if size > app.config['MAX_CONTENT_LENGTH']: return fail('Upload too large', 413)
    def known_game(code, now_mode=False):
        for path in games:
            try:
                # No links or request-selected paths; one bounded read for hash and marker.
                if path.is_symlink() or not path.is_file() or path.stat().st_size > 16*1024*1024: continue
                with path.open('rb') as f:
                    before = os.fstat(f.fileno())
                    data = f.read(16*1024*1024 + 1)
                    after = os.fstat(f.fileno())
                current = path.stat()
                identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
                if identity(before) != identity(after) or identity(after) != identity(current): continue
                # Publishing: only a csprogs carrying P815's upload flow, whatever is deployed.
                if publish_dirs and PUBLISH_MARKER not in data: continue
                if now_mode and NOW_MARKER not in data: continue
                if secrets.compare_digest(hashlib.sha256(data).hexdigest(), code): return True
            except OSError: continue
        return False
    def signature(pub_key, nonce, code, sig):
        message = (accounts.STATEMENT % (SITE, nonce, KIND, 1, code)).encode()
        ed = verify
        if ed is None:
            tools = os.environ.get('SURFD_TOOLS', str(Path(__file__).resolve().parent.parent / 'tools'))
            if tools not in sys.path: sys.path.insert(0, tools)
            try: import ed25519 as ed
            except ImportError: return None
        return bool(ed.verify(bytes.fromhex(pub_key), message, bytes.fromhex(sig)))
    def apply(now):
        return pub.apply_ready(connect, store, publish_dirs, valid_name, maps_fn, now, MAX_ZONE_BYTES, rcon_fn)
    app.config['ZONEPUB_APPLY'] = apply     # zonepub_wsgi.py's minute tick
    @app.after_request
    def private(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
    @app.post('/api/zones/challenge')
    def challenge():
        data = request.get_json(silent=True)
        if not isinstance(data, dict): return fail('Invalid request', 400)
        name, sha = data.get('map', ''), data.get('sha', '')
        if not isinstance(name, str) or not NAME.fullmatch(name) or not isinstance(sha, str) or not HEX64.fullmatch(sha):
            return fail('Invalid map or saved-file hash', 400)
        now = int(clock())
        peer = hashlib.sha256(peer_salt + (request.remote_addr or '').encode()).hexdigest()
        try:
            with connect(store) as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('DELETE FROM challenges WHERE created<?', (now-180,))
                if db.execute('SELECT COUNT(*) FROM challenges').fetchone()[0] >= 256 or db.execute(
                        'SELECT COUNT(*) FROM challenges WHERE peer=?', (peer,)).fetchone()[0] >= 8:
                    return fail('Upload service busy; try later', 429)
                nonce = secrets.token_hex(16)
                # P1081: a second nonce for the same map and bytes; signing it asks for "reload now".
                now_nonce = secrets.token_hex(16) if publish_dirs else None
                h = lambda n: hashlib.sha256(n.encode()).hexdigest() if n else None
                db.execute('INSERT INTO challenges(nonce,map,sha,peer,created,nonce_now) VALUES(?,?,?,?,?,?)',
                           (h(nonce),name,sha,peer,now,h(now_nonce)))
            if now_nonce: return jsonify(ok=1, nonce=nonce, nonce_now=now_nonce, map=name, sha=sha)
            return jsonify(ok=1, nonce=nonce, map=name, sha=sha)
        except sqlite3.Error: return fail('Zone uploads unavailable', 503)
    @app.post('/api/zones/draft')
    def upload():
        envelope = request.get_data(cache=False)
        match = PREFIX.match(envelope)
        if not match or not envelope.endswith(b'}'): return fail('Invalid upload proof', 400)
        nonce, pub_key, sig, code = [x.decode('ascii') for x in match.groups()]
        raw = envelope[match.end():-1]
        now = int(clock())
        key = hashlib.sha256(nonce.encode()).hexdigest()
        try:
            with connect(store) as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT nonce, nonce_now FROM challenges WHERE (nonce=? OR nonce_now=?) '
                                 'AND created>=? AND attempts<3', (key,key,now-180)).fetchone()
                if row is None: return fail('Upload confirmation expired or already used', 409)
                slot, force = row['nonce'], row['nonce_now'] == key    # one challenge, either nonce, once
                db.execute('UPDATE challenges SET attempts=attempts+1 WHERE nonce=?', (slot,))
        except sqlite3.Error: return fail('Zone uploads unavailable', 503)
        if not known_game(code, force): return fail('Update your game before uploading', 403)
        ok = signature(pub_key, nonce, code, sig)
        if ok is None: return fail('Signature verifier unavailable', 503)
        if not ok: return fail('Invalid upload proof', 403)
        try:
            # Existing linked Steam identity and bans; no caller-provided identity.
            with connect(account_db, readonly=True) as main:
                state, sid = accounts.ranked_as(main, pub_key)
            if state != accounts.RANK_LINKED: return fail('Link an unbanned Steam account first', 403)
            now = int(clock())
            with connect(store) as db:
                db.execute('BEGIN IMMEDIATE')
                if db.execute('SELECT 1 FROM roles WHERE steamid=?', (sid,)).fetchone() is None:
                    return fail('This Steam account is not a zone admin', 403)
                grant = db.execute('SELECT * FROM challenges WHERE nonce=? AND created>=?', (slot, now-180)).fetchone()
                if grant is None: return fail('Upload confirmation expired or already used', 409)
                if not secrets.compare_digest(hashlib.sha256(raw).hexdigest(), grant['sha']):
                    return fail('Saved zone file changed; start the upload again', 409)
                try: validate(raw)
                except ValueError as e:
                    if str(e).startswith('maxVelocity'): return fail(str(e), 400)   # P841
                    return fail('Invalid or incomplete zone geometry', 400)
                except (TypeError, KeyError, RecursionError, UnicodeDecodeError):
                    return fail('Invalid or incomplete zone geometry', 400)
                rid = None
                if publish_dirs:
                    rid = pub.queue(db, grant['map'], raw, sid, now, force)
                    if rid is None: return fail('Too many publishes this hour; try again later', 429)
                    pub.log('queued', grant['map'], grant['sha'][:12], 'by', pub.who(db, sid), 'now' if force else '')
                prior = db.execute('SELECT id FROM drafts WHERE map=? AND sha=?', (grant['map'],grant['sha'])).fetchone()
                if prior is None:
                    count = db.execute('SELECT COUNT(*) FROM drafts').fetchone()[0]
                    if count >= 128:
                        if not publish_dirs: return fail('Draft store full; ask an operator', 507)
                        # Publishing: a draft is history, so the oldest goes rather than the upload.
                        db.execute('DELETE FROM drafts WHERE id IN (SELECT id FROM drafts ORDER BY created, id LIMIT ?)', (count-127,))
                    ident = secrets.token_hex(12)
                    db.execute('INSERT INTO drafts VALUES(?,?,?,?,?,?,?)', (ident,grant['map'],grant['sha'],sid,pub_key,now,raw))
                else: ident = prior['id']
                db.execute('DELETE FROM challenges WHERE nonce=?', (slot,))
            if not publish_dirs:
                return jsonify(ok=1, draft=ident, note='Saved as an admin draft; review and activation are still required')
            name = grant['map']
            # The queued row's own kind, whoever applied it (this call or the minute tick).
            try: apply(now)
            except Exception as e: pub.log('apply after upload failed:', e)
            try:
                with connect(store, readonly=True) as db:
                    row = db.execute('SELECT kind FROM publications WHERE id=?', (rid,)).fetchone()
                done = row['kind'] if row else 'superseded'
            except sqlite3.Error: done = 'pending'
            if done in ('live', 'noop'):
                return jsonify(ok=1, draft=ident, published=1, note='Published: lobbies time with these zones from '
                               'their next map load' if done == 'live' else 'These zones are already live')
            if done in ('failed', 'partial'):
                return fail('Accepted, but the zone files could not be written; an operator must look', 500)
            if force:
                return jsonify(ok=1, draft=ident, published=0, now=1,
                               note='Accepted: lobbies on %s are warned and reload with these zones once its '
                                    'runs are verified, usually within %d minutes' % (name, (pub.FORCE_NOTICE + 360) // 60))
            return jsonify(ok=1, draft=ident, published=0,
                           note='Accepted: live once no lobby has had %s loaded for %d minutes and its runs are '
                                'verified' % (name, pub.QUIET // 60))
        except sqlite3.Error: return fail('Zone uploads unavailable', 503)
    return app


def stage(store, draft, expected_sha, bsp, output, times_policy, reviewed_bsp_sha):
    """Prepare reviewed public geometry, NOT a live activation or board mutation."""
    if times_policy != 'keep':
        raise ValueError('hide/archive require a separately reviewed leaderboard operation; nothing staged')
    if not re.fullmatch(r'[0-9a-f]{24}', draft) or not HEX64.fullmatch(expected_sha):
        raise ValueError('Expected draft ID and explicitly reviewed SHA256')
    output, bsp = Path(output), Path(bsp)
    if output.exists() or output.is_symlink(): raise ValueError('Use a new owned staging directory')
    if not any((p/'OWNER.md').is_file() for p in output.parents):
        raise ValueError('Staging must be under an explicitly owned task root')
    with connect(store, readonly=True) as db:
        row = db.execute('SELECT map,sha,body FROM drafts WHERE id=?',(draft,)).fetchone()
    if row is None or not secrets.compare_digest(row['sha'],expected_sha):
        raise ValueError('Draft absent or differs from reviewed bytes')
    body = bytes(row['body']); validate(body)
    if hashlib.sha256(body).hexdigest()!=expected_sha: raise ValueError('Draft integrity failure')
    if not HEX64.fullmatch(reviewed_bsp_sha): raise ValueError('Expected explicitly reviewed BSP SHA256')
    if bsp.name != row['map']+'.bsp' or not bsp.is_file() or bsp.stat().st_size>1024*1024*1024:
        raise ValueError('Supply the target map BSP to bind the reviewed geometry')
    h=hashlib.sha256()
    with bsp.open('rb') as f:
        before=os.fstat(f.fileno())
        if before.st_size>1024*1024*1024: raise ValueError('BSP exceeds supported review size')
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
        after=os.fstat(f.fileno())
    current=bsp.stat()
    identity=lambda st:(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)
    if identity(before)!=identity(after) or identity(after)!=identity(current):
        raise ValueError('BSP changed during review')
    if not secrets.compare_digest(h.hexdigest(),reviewed_bsp_sha):
        raise ValueError('BSP differs from the explicitly reviewed revision')
    output.mkdir(parents=True)
    (output/(row['map']+'.json')).write_bytes(body)
    # Envelope identity stays private. Raw zone annotations still need review;
    # this writes owned staging only, never a public site or live game.
    report=dict(map=row['map'],zone_sha256=expected_sha,bsp_sha256=h.hexdigest(),times_policy=times_policy,
                status='STAGED ONLY: verify/publish to site and fleet, no mid-run table reload')
    (output/'REVIEW.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--store', type=Path, required=True)
    sub = ap.add_subparsers(dest='command', required=True)
    sub.add_parser('init')
    for word in ('grant', 'revoke'):
        sub.add_parser(word).add_argument('--identity-file', type=Path, required=True,
                                         help='private file containing the approved SteamID64')
    st = sub.add_parser('stage')
    st.add_argument('--draft', required=True)
    st.add_argument('--reviewed-sha256', required=True)
    st.add_argument('--reviewed-bsp-sha256', required=True)
    st.add_argument('--bsp', type=Path, required=True)
    st.add_argument('--output', type=Path, required=True)
    st.add_argument('--times', choices=('keep','hide','archive'), required=True)
    for word, text in (('apply', 'publish what is pending and quiet now'),
                       ('rollback', "put back what a map's publish replaced")):
        p = sub.add_parser(word, help=text)
        p.add_argument('--publish-dir', type=Path, action='append', required=True,
                       help="the service's publish directories")
        p.add_argument('--accounts', type=Path, default=Path('/srv/nvme/surfd/data/surfd.db'),
                       help="surfd's database: its lobbies and replays tables")
        p.add_argument('--sweep-log', type=Path, default=Path(SWEEP_LOG))
    rb = sub.choices['rollback']
    rb.add_argument('--map', required=True)
    rb.add_argument('--id', type=int, help='that publish rather than the newest live one')
    rb.add_argument('--anyway', action='store_true', help='even while a lobby has the map loaded')
    serve = sub.add_parser('serve')
    serve.add_argument('--accounts', type=Path, required=True)
    serve.add_argument('--game', type=Path, action='append', required=True)
    serve.add_argument('--publish-dir', type=Path, action='append', default=[])
    serve.add_argument('--port', type=int, default=8087)
    args = ap.parse_args()
    if args.command in ('apply', 'rollback') and hasattr(os, 'geteuid') and os.geteuid() == 0:
        ap.error('run as the service user (proto), not root: the publish directories are proto-writable')
    if args.command == 'init': initialize(args.store); return
    if args.command in ('apply', 'rollback'):
        lobbies = lambda: pub.lobby_state(args.accounts, args.sweep_log, time.time())
    if args.command == 'apply':
        print(pub.apply_ready(connect, args.store, args.publish_dir, valid_name, lobbies,
                              int(time.time()), MAX_ZONE_BYTES))
        return
    if args.command == 'rollback':
        restored = pub.rollback(connect, args.store, args.publish_dir, args.map, valid_name, lobbies,
                                int(time.time()), MAX_ZONE_BYTES, args.id, args.anyway)
        print('Rolled back %s: %s' % (args.map, ', '.join(s[:12] if s else 'removed' for s in restored)))
        return
    if args.command == 'stage':
        stage(args.store,args.draft,args.reviewed_sha256,args.bsp,args.output,args.times,args.reviewed_bsp_sha256)
        print('Reviewed geometry staged only; no live zones or existing times changed')
        return
    if args.command in ('grant','revoke'):
        sid = args.identity_file.read_text().strip()
        if not re.fullmatch(r'7656119[0-9]{10}', sid): ap.error('Expected a SteamID64 in the private identity file')
        with connect(args.store) as db:
            if args.command == 'grant': db.execute('INSERT OR IGNORE INTO roles VALUES(?)', (sid,))
            else: db.execute('DELETE FROM roles WHERE steamid=?', (sid,))
        print('Zone role updated')
        return
    # Development only; production uses a separately owned Gunicorn unit.
    create_app(args.store, args.accounts, args.game, publish_dirs=args.publish_dir).run(host='127.0.0.1', port=args.port)


if __name__ == '__main__': main()
