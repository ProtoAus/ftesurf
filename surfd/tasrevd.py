#!/usr/bin/env python3
"""P1091: TAS revisions and their author statements (TAS plan 5.3), and credit (5.4).

An isolated service beside surfd, like zonepub: its own store, read-only use of surfd's
accounts (key links), no surfd schema change. tools/tasrev.py is the one reader and verifier
(the game's twin), so nothing here parses a revision or rebuilds a statement itself.

  POST /api/tasrev/statement   {"line": "tasrev 1 sha parent|- mapcrc first last code pub sig"}
                               verified alone (no content needed): registering it at signing
                               time fixes the key's first-seen time for that revision.
  POST /api/tasrev/revision    a .tasp body, exactly as the game wrote it; kept by its hash.
  GET  /api/tasrev/rev/<sha>   the revision, its statements (each checked against the content),
                               and its credit: tick ranges and who supplied them.
  GET  /api/tasrev/rev/<sha>/file   the body, for a client to open as a project.
  GET  /api/tasrev/map/<map>   revisions on a map, newest first.

Credit (5.4): a tick's row goes to the EARLIEST revision of the known chain holding that row
at that tick (a revert credits whoever first supplied it), and through it to the first
statement about that revision whose signature verifies against its content, whose ticks span
the tick, and whose game code is a released csprogs. A run of equal rows that reaches a parent
this service has not seen is "ancestry unknown": nobody's. Keys resolve to accounts through
an append-only history this service keeps (surfd's keylinks is overwritten on relink): a
statement belongs to the first account its key is seen linked to at or after the statement
first arrived.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys
import time
from flask import Flask, Response, jsonify, request
import accounts

MAX_BODY = 4 * 1024 * 1024          # 96000 rows of the widest canonical form, with room
NAME = re.compile(r'[A-Za-z0-9_.+-]{1,64}')
HEX64 = re.compile(r'[0-9a-f]{64}')
PEER_DAY = 400                      # uploads a peer may make in a day
STORE_CAP = 2 * 1024 ** 3           # bodies kept, in all
SQL = '''
CREATE TABLE IF NOT EXISTS revisions(sha TEXT PRIMARY KEY, map TEXT NOT NULL, mapcrc TEXT NOT NULL,
 parentsha TEXT, version TEXT NOT NULL, base INTEGER NOT NULL, head INTEGER NOT NULL,
 supply_a INTEGER, supply_b INTEGER, first_seen INTEGER NOT NULL, size INTEGER NOT NULL, body BLOB NOT NULL);
CREATE INDEX IF NOT EXISTS revisions_map ON revisions(map, first_seen);
CREATE TABLE IF NOT EXISTS statements(id TEXT PRIMARY KEY, sha TEXT NOT NULL, line TEXT NOT NULL,
 pub TEXT NOT NULL, code TEXT NOT NULL, first_seen INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS statements_sha ON statements(sha, first_seen);
CREATE TABLE IF NOT EXISTS keyseen(pub TEXT NOT NULL, steamid TEXT NOT NULL, state TEXT NOT NULL,
 seen_at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS keyseen_pub ON keyseen(pub, seen_at);
CREATE TABLE IF NOT EXISTS uploads(peer TEXT NOT NULL, day INTEGER NOT NULL, n INTEGER NOT NULL,
 PRIMARY KEY(peer, day));
'''


def load_tasrev():
    tools = os.environ.get('SURFD_TOOLS', str(Path(__file__).resolve().parent.parent / 'tools'))
    if tools not in sys.path: sys.path.insert(0, tools)
    import tasrev
    return tasrev    # tools/tasrev.py: this module is tasrevd so the two names never meet


@contextmanager
def connect(path, readonly=False):
    uri = Path(path).resolve().as_uri() + ('?mode=ro' if readonly else '?mode=rw')
    db = sqlite3.connect(uri, uri=True, timeout=1.0)
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


def released_codes(path):
    """The csprogs sha256s a statement's `code` may name: one per line, appended at each release
    or deploy (statements are signed offline and arrive later, so a list, never "the current")."""
    try: text = Path(path).read_text(encoding='ascii')
    except (OSError, UnicodeDecodeError): return frozenset()
    return frozenset(w for w in text.split() if HEX64.fullmatch(w))


def observe(db, account_db, pub, now):
    """Append what surfd's keylinks says of this key now, when it differs from the last record."""
    try:
        with connect(account_db, readonly=True) as adb: state, sid = accounts.ranked_as(adb, pub)
    except sqlite3.Error:
        return
    last = db.execute('SELECT steamid, state FROM keyseen WHERE pub = ? ORDER BY seen_at DESC, rowid DESC LIMIT 1',
                      (pub,)).fetchone()
    if last is None or (last['steamid'], last['state']) != (sid, state):
        db.execute('INSERT INTO keyseen(pub, steamid, state, seen_at) VALUES (?, ?, ?, ?)', (pub, sid, state, now))


def account_of(db, pub, since):
    """The first account this key was seen linked to at or after `since`; '' if none yet."""
    row = db.execute("SELECT steamid FROM keyseen WHERE pub = ? AND seen_at >= ? AND state = ?"
                     " ORDER BY seen_at, rowid LIMIT 1", (pub, since, accounts.RANK_LINKED)).fetchone()
    if row is None:   # linked before the statement arrived and never changed since
        row = db.execute("SELECT steamid, state FROM keyseen WHERE pub = ? AND seen_at < ?"
                         " ORDER BY seen_at DESC, rowid DESC LIMIT 1", (pub, since)).fetchone()
        if row is None or row['state'] != accounts.RANK_LINKED: return ''
    return row['steamid']


def credit(db, tr, sha, codes):
    """[(first, last, who)] over the revision's ticks: who is a steamid, 'unsigned',
    'unattributed' (signed by an unlinked key or unknown code), or 'unknown-ancestry'."""
    chain, cur = [], sha
    while cur and len(chain) < 4096:
        row = db.execute('SELECT sha, parentsha, body FROM revisions WHERE sha = ?', (cur,)).fetchone()
        if row is None: break
        chain.append((row['sha'], tr.parse(bytes(row['body']))))
        cur = row['parentsha']
    if not chain: return []
    unknown_tail = bool(cur)          # the oldest revision held names a parent we have not seen
    rows = [{c['base'] + 1 + i: r for i, r in enumerate(c['rows'])} for _, c in chain]
    who_of = {}
    def who(rev_sha, info, t):
        key = (rev_sha, t)
        for st in db.execute('SELECT line, pub, code, first_seen FROM statements WHERE sha = ? ORDER BY first_seen, id',
                             (rev_sha,)):
            try: tr.check_sig(st['line'], info)
            except tr.Refused: continue
            w = st['line'].split(' ')
            if not int(w[5]) <= t <= int(w[6]): continue
            if st['code'] not in codes: return 'unattributed'
            return account_of(db, st['pub'], st['first_seen']) or 'unattributed'
        return 'unsigned'
    out = []
    for t in sorted(rows[0]):
        # The earliest revision holding this row, contiguous or not: a revert credits whoever
        # first supplied the row, not whoever restored it.
        k = max(i for i in range(len(chain)) if rows[i].get(t) == rows[0][t])
        if k == len(chain) - 1 and unknown_tail and chain[k][1]['parentsha'] is not None:
            w = 'unknown-ancestry'
        else:
            w = who(chain[k][0], chain[k][1], t)
        if out and out[-1][2] == w and out[-1][1] == t - 1: out[-1][1] = t
        else: out.append([t, t, w])
    return [tuple(x) for x in out]


def create_app(store, account_db, codes_file, clock=time.time):
    tr = load_tasrev()
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = MAX_BODY
    store, account_db = Path(store), Path(account_db)
    peer_salt = secrets.token_bytes(32)
    # A refusal answers 200 with ok=0: the game's HTTP client keeps no body for other statuses.
    def fail(message, status): return jsonify(ok=0, error=message, status=status), 200
    def peer():
        a = request.headers.get('X-Forwarded-For', request.remote_addr or '')
        return hashlib.sha256(peer_salt + a.encode()).hexdigest()[:24]
    def budget(db, now):
        day = int(now // 86400); p = peer()
        row = db.execute('SELECT n FROM uploads WHERE peer = ? AND day = ?', (p, day)).fetchone()
        if row and row['n'] >= PEER_DAY: return False
        db.execute('INSERT INTO uploads(peer, day, n) VALUES (?, ?, 1) ON CONFLICT(peer, day) DO UPDATE SET n = n + 1', (p, day))
        db.execute('DELETE FROM uploads WHERE day < ?', (day - 2,))
        return True
    @app.before_request
    def body_budget():
        if request.method == 'POST':
            size = request.content_length
            if size is None or size <= 0: return fail('Request length required', 411)
            if size > MAX_BODY: return fail('Upload too large', 413)
    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
    @app.post('/api/tasrev/statement')
    def statement():
        data = request.get_json(silent=True)
        line = data.get('line') if isinstance(data, dict) else None
        if not isinstance(line, str) or len(line) > 600: return fail('Invalid statement', 400)
        try: pub = tr.check_sig(line)
        except tr.Refused as e: return fail('Statement refused: %s' % e, 400)
        w = line.split(' '); sha, code = w[2], w[7]
        sid = hashlib.sha256(line.encode('ascii')).hexdigest()
        now = int(clock())
        with connect(store) as db:
            known = db.execute('SELECT first_seen FROM statements WHERE id = ?', (sid,)).fetchone()
            if known is None:
                if not budget(db, now): return fail('Too many uploads today', 429)
                db.execute('INSERT INTO statements(id, sha, line, pub, code, first_seen) VALUES (?, ?, ?, ?, ?, ?)',
                           (sid, sha, line, pub, code, now))
            observe(db, account_db, pub, now)
            have = db.execute('SELECT 1 FROM revisions WHERE sha = ?', (sha,)).fetchone() is not None
        return jsonify(ok=1, id=sid, first_seen=known['first_seen'] if known else now, revision=have,
                       released_code=code in released_codes(codes_file))
    @app.post('/api/tasrev/revision')
    def revision():
        body = request.get_data(cache=False)
        try: info = tr.parse(body)
        except tr.Refused as e: return fail('Revision refused: %s' % e, 400)
        if info['stated'] != info['h']: return fail('Revision refused: its revsha is not its hash', 400)
        mp = body.split(b'\n', 2)[1].decode('ascii').split(' ')[1]
        if not NAME.fullmatch(mp): return fail('Invalid map', 400)
        supply = info['supply'] if isinstance(info['supply'], tuple) else (None, None)
        now = int(clock())
        with connect(store) as db:
            known = db.execute('SELECT first_seen FROM revisions WHERE sha = ?', (info['h'],)).fetchone()
            if known is None:
                total = db.execute('SELECT COALESCE(SUM(size), 0) FROM revisions').fetchone()[0]
                if total + len(body) > STORE_CAP: return fail('The revision store is full', 507)
                if not budget(db, now): return fail('Too many uploads today', 429)
                db.execute('INSERT INTO revisions(sha, map, mapcrc, parentsha, version, base, head, supply_a, supply_b,'
                           ' first_seen, size, body) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                           (info['h'], mp, info['mapcrc'], info['parentsha'], info['version'], info['base'],
                            info['base'] + len(info['rows']), supply[0], supply[1], now, len(body), body))
            parent = info['parentsha']
            parent_known = parent is None or db.execute('SELECT 1 FROM revisions WHERE sha = ?', (parent,)).fetchone() is not None
        return jsonify(ok=1, sha=info['h'], first_seen=known['first_seen'] if known else now,
                       parent=parent, parent_known=parent_known)
    @app.get('/api/tasrev/rev/<sha>')
    def show(sha):
        if not HEX64.fullmatch(sha): return fail('Invalid hash', 400)
        codes = released_codes(codes_file)
        with connect(store) as db:
            row = db.execute('SELECT sha, map, mapcrc, parentsha, version, base, head, supply_a, supply_b, first_seen'
                             ' FROM revisions WHERE sha = ?', (sha,)).fetchone()
            sts = []
            info = tr.parse(bytes(db.execute('SELECT body FROM revisions WHERE sha = ?', (sha,)).fetchone()['body'])) if row else None
            for pub in {r['pub'] for r in db.execute('SELECT pub FROM statements WHERE sha = ?', (sha,))}:
                observe(db, account_db, pub, int(clock()))   # a key linked since its statement arrived
            for st in db.execute('SELECT id, line, pub, code, first_seen FROM statements WHERE sha = ? ORDER BY first_seen, id', (sha,)):
                for_rev = None
                if info is not None:
                    try: tr.check_sig(st['line'], info); for_rev = True
                    except tr.Refused: for_rev = False
                w = st['line'].split(' ')
                sts.append(dict(id=st['id'], pub=st['pub'], ticks=[int(w[5]), int(w[6])], first_seen=st['first_seen'],
                                about_this_revision=for_rev, released_code=st['code'] in codes,
                                account=account_of(db, st['pub'], st['first_seen'])))
            cr = credit(db, tr, sha, codes) if row else []
        if row is None and not sts: return fail('Unknown revision', 404)
        return jsonify(ok=1, revision=dict(row) if row else None, statements=sts,
                       credit=[dict(first=a, last=b, who=w) for a, b, w in cr])
    @app.get('/api/tasrev/rev/<sha>/file')
    def file(sha):
        if not HEX64.fullmatch(sha): return fail('Invalid hash', 400)
        with connect(store) as db:
            row = db.execute('SELECT body FROM revisions WHERE sha = ?', (sha,)).fetchone()
        if row is None: return fail('Unknown revision', 404)
        return Response(bytes(row['body']), mimetype='text/plain')
    @app.get('/api/tasrev/map/<mp>')
    def by_map(mp):
        if not NAME.fullmatch(mp): return fail('Invalid map', 400)
        with connect(store) as db:
            rows = db.execute('SELECT r.sha, r.parentsha, r.base, r.head, r.supply_a, r.supply_b, r.first_seen,'
                              ' (SELECT COUNT(*) FROM statements s WHERE s.sha = r.sha) AS statements'
                              ' FROM revisions r WHERE r.map = ? ORDER BY r.first_seen DESC LIMIT 200', (mp,)).fetchall()
        return jsonify(ok=1, map=mp, revisions=[dict(r) for r in rows])
    return app


def main():
    import argparse
    ap = argparse.ArgumentParser(description='P1091 TAS revision service store')
    ap.add_argument('--store', required=True)
    ap.add_argument('command', choices=['init'])
    a = ap.parse_args()
    initialize(a.store)
    print('tasrevd store ready: %s' % a.store)


if __name__ == '__main__':
    main()
