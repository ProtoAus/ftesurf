#!/usr/bin/env python3
"""Isolated, deny-by-default zone DRAFT service using linked Steam key proofs.

No surfd schema migration or live-zone/leaderboard writes. Run behind the existing
HTTPS host on a loopback socket; do not replace a sealed surfd generation. The
operator creates this service's separate store and grants roles explicitly.
Draft activation is a separate reviewed operation (see zonepub.md).
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

MAX_ZONE_BYTES = 262144
SITE = 'play.proto.bar:443'
KIND = -6
NAME = re.compile(r'[a-z0-9_-]{1,64}')
HEX64 = re.compile(r'[0-9a-f]{64}')
PREFIX = re.compile(rb'^\{"nonce":"([0-9a-f]{32})","pub":"([0-9a-f]{64})","sig":"([0-9a-f]{128})","game":"([0-9a-f]{64})","zones":')
SQL = '''
CREATE TABLE IF NOT EXISTS roles(steamid TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS challenges(nonce TEXT PRIMARY KEY, map TEXT NOT NULL,
 sha TEXT NOT NULL, peer TEXT NOT NULL, created INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS drafts(id TEXT PRIMARY KEY, map TEXT NOT NULL,
 sha TEXT NOT NULL, steamid TEXT NOT NULL, pub TEXT NOT NULL, created INTEGER NOT NULL,
 body BLOB NOT NULL, UNIQUE(map,sha));
'''


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


def initialize(path):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    try:
        with db: db.executescript(SQL)
    finally: db.close()
    os.chmod(path, 0o600)


def validate(body):
    """Accept only complete bounded Momentum-v1 timer geometry within QC capacity."""
    if not 16 <= len(body) <= MAX_ZONE_BYTES:
        raise ValueError('Zone file size outside supported range')
    def constant(_):
        raise ValueError('Non-finite coordinate')
    obj = json.loads(body.decode('utf-8'), parse_constant=constant)
    # Bound the entire object too, including unknown upstream annotations.
    todo, nodes = [(obj, 0)], 0
    while todo:
        item, depth = todo.pop(); nodes += 1
        if depth > 24 or nodes > 50000:
            raise ValueError('Zone structure too complex')
        if isinstance(item, dict): todo.extend((v, depth+1) for v in item.values())
        elif isinstance(item, list): todo.extend((v, depth+1) for v in item)
        elif isinstance(item, float) and not math.isfinite(item): raise ValueError('Non-finite number')
    if not isinstance(obj, dict) or type(obj.get('formatVersion')) is not int or obj.get('formatVersion') != 1:
        raise ValueError('Expected Momentum zone formatVersion 1')
    count = points = 0
    def number(x):
        if isinstance(x, bool) or not isinstance(x, (int, float)) or abs(x) > 10000000 or not math.isfinite(x):
            raise ValueError('Invalid zone coordinate')
        return x
    def regions(value):
        nonlocal count, points
        if not isinstance(value, list): raise ValueError('Expected regions')
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
            count += 1; points += len(p)
            if count > 256 or points > 2048: raise ValueError('Zone file exceeds game table capacity')
        return len(value)
    tracks = obj.get('tracks')
    if not isinstance(tracks, dict) or not isinstance(tracks.get('main'), dict):
        raise ValueError('Missing main track')
    bonuses = tracks.get('bonuses', [])
    if not isinstance(bonuses, list) or len(bonuses) > 32: raise ValueError('Too many bonus tracks')
    for track in [tracks['main']] + bonuses:
        z = track.get('zones') if isinstance(track, dict) else None
        if not isinstance(z, dict): raise ValueError('Missing track zones')
        segs = z.get('segments')
        if not isinstance(segs, list) or not segs: raise ValueError('Missing start zone')
        for seg in segs:
            cps = seg.get('checkpoints') if isinstance(seg, dict) else None
            if not isinstance(cps, list) or not cps: raise ValueError('Missing segment start')
            for cp in cps:
                if not isinstance(cp, dict) or not regions(cp.get('regions')): raise ValueError('Empty checkpoint')
        end = z.get('end')
        if not isinstance(end, dict) or not regions(end.get('regions')): raise ValueError('Missing finish zone')
    global_regions = obj.get('globalRegions', {})
    if not isinstance(global_regions, dict): raise ValueError('Invalid global regions')
    for name in ('cancel', 'allowBhop', 'overbounce'):
        if name in global_regions: regions(global_regions[name])
    return obj


def create_app(store, account_db, game_files, clock=time.time, verify=None):
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = MAX_ZONE_BYTES + 1024
    store, account_db = Path(store), Path(account_db)
    games = tuple(Path(p) for p in game_files)
    peer_salt = secrets.token_bytes(32)
    def fail(message, status): return jsonify(ok=0, error=message), status
    @app.before_request
    def body_budget():
        # Older Werkzeug does not enforce MAX_CONTENT_LENGTH in get_data().
        # Native HTTP and the buffering nginx proxy both supply an exact length.
        if request.method == 'POST':
            size = request.content_length
            if size is None or size <= 0: return fail('Request length required', 411)
            if size > app.config['MAX_CONTENT_LENGTH']: return fail('Upload too large', 413)
    def known_game(code):
        for path in games:
            try:
                # No bulk reads, links or arbitrary request-selected file paths.
                if path.is_symlink() or not path.is_file() or path.stat().st_size > 16*1024*1024: continue
                with path.open('rb') as f:
                    before = os.fstat(f.fileno())
                    h = hashlib.sha256()
                    for block in iter(lambda: f.read(65536), b''): h.update(block)
                    after = os.fstat(f.fileno())
                current = path.stat()
                identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
                if identity(before) != identity(after) or identity(after) != identity(current): continue
                if secrets.compare_digest(h.hexdigest(), code): return True
            except OSError: continue
        return False
    def signature(pub, nonce, code, sig):
        message = (accounts.STATEMENT % (SITE, nonce, KIND, 1, code)).encode()
        ed = verify
        if ed is None:
            tools = os.environ.get('SURFD_TOOLS', str(Path(__file__).resolve().parent.parent / 'tools'))
            if tools not in sys.path: sys.path.insert(0, tools)
            try: import ed25519 as ed
            except ImportError: return None
        return bool(ed.verify(bytes.fromhex(pub), message, bytes.fromhex(sig)))
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
                db.execute('INSERT INTO challenges(nonce,map,sha,peer,created) VALUES(?,?,?,?,?)', (hashlib.sha256(nonce.encode()).hexdigest(),name,sha,peer,now))
            return jsonify(ok=1, nonce=nonce, map=name, sha=sha)
        except sqlite3.Error: return fail('Zone uploads unavailable', 503)
    @app.post('/api/zones/draft')
    def upload():
        envelope = request.get_data(cache=False)
        match = PREFIX.match(envelope)
        if not match or not envelope.endswith(b'}'): return fail('Invalid upload proof', 400)
        nonce, pub, sig, code = [x.decode('ascii') for x in match.groups()]
        raw = envelope[match.end():-1]
        now = int(clock())
        key = hashlib.sha256(nonce.encode()).hexdigest()
        try:
            with connect(store) as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT 1 FROM challenges WHERE nonce=? AND created>=? AND attempts<3', (key,now-180)).fetchone()
                if row is None: return fail('Upload confirmation expired or already used', 409)
                db.execute('UPDATE challenges SET attempts=attempts+1 WHERE nonce=?', (key,))
        except sqlite3.Error: return fail('Zone uploads unavailable', 503)
        if not known_game(code): return fail('Update your game before uploading', 403)
        ok = signature(pub, nonce, code, sig)
        if ok is None: return fail('Signature verifier unavailable', 503)
        if not ok: return fail('Invalid upload proof', 403)
        try:
            # Existing linked Steam identity and bans; no caller-provided identity.
            with connect(account_db, readonly=True) as main:
                state, sid = accounts.ranked_as(main, pub)
            if state != accounts.RANK_LINKED: return fail('Link an unbanned Steam account first', 403)
            now = int(clock())
            with connect(store) as db:
                db.execute('BEGIN IMMEDIATE')
                if db.execute('SELECT 1 FROM roles WHERE steamid=?', (sid,)).fetchone() is None:
                    return fail('This Steam account is not a zone admin', 403)
                key = hashlib.sha256(nonce.encode()).hexdigest()
                grant = db.execute('SELECT * FROM challenges WHERE nonce=? AND created>=?', (key, now-180)).fetchone()
                if grant is None: return fail('Upload confirmation expired or already used', 409)
                if not secrets.compare_digest(hashlib.sha256(raw).hexdigest(), grant['sha']):
                    return fail('Saved zone file changed; start the upload again', 409)
                try: validate(raw)
                except (ValueError, TypeError, KeyError, RecursionError): return fail('Invalid or incomplete zone geometry', 400)
                prior = db.execute('SELECT id FROM drafts WHERE map=? AND sha=?', (grant['map'],grant['sha'])).fetchone()
                if prior is None:
                    if db.execute('SELECT COUNT(*) FROM drafts').fetchone()[0] >= 128: return fail('Draft store full; ask an operator', 507)
                    ident = secrets.token_hex(12)
                    db.execute('INSERT INTO drafts VALUES(?,?,?,?,?,?,?)', (ident,grant['map'],grant['sha'],sid,pub,now,raw))
                else: ident = prior['id']
                db.execute('DELETE FROM challenges WHERE nonce=?', (key,))
            return jsonify(ok=1, draft=ident, note='Saved as an admin draft; review and activation are still required')
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
    serve = sub.add_parser('serve')
    serve.add_argument('--accounts', type=Path, required=True)
    serve.add_argument('--game', type=Path, action='append', required=True)
    serve.add_argument('--port', type=int, default=8087)
    args = ap.parse_args()
    if args.command == 'init': initialize(args.store); return
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
    create_app(args.store, args.accounts, args.game).run(host='127.0.0.1', port=args.port)


if __name__ == '__main__': main()
