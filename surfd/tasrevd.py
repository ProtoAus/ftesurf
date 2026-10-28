#!/usr/bin/env python3
"""P1091: TAS revisions and their author statements (TAS plan 5.3), and credit (5.4).

An isolated service beside surfd, like zonepub: its own store, read-only use of surfd's
accounts (key links), no surfd schema change. tools/tasrev.py is the one reader and verifier
(the game's twin), so nothing here parses a revision or rebuilds a statement itself.

  POST /api/tasrev/statement   {"line": "tasrev 1 sha parent|- mapcrc first last code pub sig"}
                               verified alone on arrival; the key's account is read then.
  POST /api/tasrev/revision    a .tasp body as the game wrote it, Content-Type text/x-tasrev.
  GET  /api/tasrev/rev/<sha>   the revision, its statements and its credit.
  GET  /api/tasrev/rev/<sha>/file   the body, for a client to open as a project.
  GET  /api/tasrev/map/<map>[?before=<first_seen>]   revisions on a map, newest first.

CREDIT is computed once, when a revision arrives, and stored as tick ranges naming the revision
that supplied each row: the nearest ancestor (within CHAIN_DEPTH) holding the same row at that
tick passes on ITS supplier, so a revert credits whoever first supplied the row; a revision whose
parent this service has not seen supplies nothing yet ("unknown-ancestry") and is recomputed
when the parent arrives; a revision whose rows (and base) equal an earlier one's takes that
one's suppliers (a copy re-saved as a new root). A child's supply must be exact against a known
parent, or the upload is refused.

A supplier revision's ticks go to the first statement about it that verifies against it,
spans the tick, names a released csprogs (codes.txt) and was registered no later than the
revision itself; statements that fail any of these are skipped, never blocking. Its account
is the one its key was linked to WHEN THE STATEMENT ARRIVED (unlinked or banned then: nobody);
later links and relinks never move it. So a player links before signing, and the client
registers a statement before it shares the revision.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import struct
import sys
import time
from flask import Flask, Response, jsonify, request
import accounts

MAX_BODY = 4700 * 1024              # 96000 rows of the widest canonical form (46 bytes) fit
NAME = re.compile(r'[A-Za-z0-9_.+-]{1,64}')
HEX64 = re.compile(r'[0-9a-f]{64}')
TAIL = re.compile(rb'\nrevsha ([0-9a-f]{64})\n\Z')
CHAIN_DEPTH = 32                    # ancestors searched for a reverted row
PEER_ITEMS, PEER_BYTES = 200, 64 * 1024 ** 2          # a peer's day
DAY_ITEMS, DAY_BYTES = 5000, 1024 ** 3                 # everyone's day
STORE_CAP, STATEMENT_CAP, PER_REVISION, PER_KEY = 2 * 1024 ** 3, 200000, 32, 4
CASCADE = 64                        # revisions recomputed when a parent arrives
SQL = '''
CREATE TABLE IF NOT EXISTS revisions(sha TEXT PRIMARY KEY, map TEXT NOT NULL, mapcrc TEXT NOT NULL,
 parentsha TEXT, version TEXT NOT NULL, base INTEGER NOT NULL, head INTEGER NOT NULL,
 supply_a INTEGER, supply_b INTEGER, first_seen INTEGER NOT NULL, size INTEGER NOT NULL,
 inputs TEXT NOT NULL, rows BLOB NOT NULL, credit TEXT NOT NULL, body BLOB NOT NULL);
CREATE INDEX IF NOT EXISTS revisions_map ON revisions(map, first_seen);
CREATE INDEX IF NOT EXISTS revisions_parent ON revisions(parentsha);
CREATE INDEX IF NOT EXISTS revisions_inputs ON revisions(inputs, first_seen);
CREATE TABLE IF NOT EXISTS statements(id TEXT PRIMARY KEY, sha TEXT NOT NULL, line TEXT NOT NULL,
 pub TEXT NOT NULL, code TEXT NOT NULL, first_seen INTEGER NOT NULL,
 steamid TEXT NOT NULL, state TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS statements_sha ON statements(sha, first_seen);
CREATE INDEX IF NOT EXISTS statements_key ON statements(sha, pub);
CREATE TABLE IF NOT EXISTS uploads(peer TEXT NOT NULL, day INTEGER NOT NULL, n INTEGER NOT NULL,
 bytes INTEGER NOT NULL, PRIMARY KEY(peer, day));
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT NOT NULL);
'''


class Unavailable(Exception):
    pass


def load_tasrev():
    tools = os.environ.get('SURFD_TOOLS', str(Path(__file__).resolve().parent.parent / 'tools'))
    if tools not in sys.path: sys.path.insert(0, tools)
    import tasrev
    return tasrev    # tools/tasrev.py: this module is tasrevd so the two names never meet


@contextmanager
def connect(path, readonly=False):
    uri = Path(path).resolve().as_uri() + ('?mode=ro' if readonly else '?mode=rw')
    db = sqlite3.connect(uri, uri=True, timeout=5.0, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()


@contextmanager
def writing(db):
    db.execute('BEGIN IMMEDIATE')
    try:
        yield db
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK')
        raise


def initialize(path):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    try:
        db.execute('PRAGMA journal_mode=WAL')
        with db: db.executescript(SQL)
        with db: db.execute('INSERT OR IGNORE INTO meta(k, v) VALUES (?, ?)', ('salt', secrets.token_hex(32)))
    finally: db.close()
    os.chmod(path, 0o600)


def released_codes(path):
    """The csprogs sha256s a statement's `code` may name, one a line (appended at each release or
    deploy). None when the list cannot be read: "cannot tell" is not "nothing is released"."""
    try: text = Path(path).read_text(encoding='utf-8-sig')
    except (OSError, UnicodeDecodeError): return None
    codes = frozenset(w.lower() for w in text.split() if HEX64.fullmatch(w.lower()))
    return codes or None


def pack_rows(rows):
    return b''.join(struct.pack('<7h', *(int(v) for v in r)) for r in rows)


def row_at(blob, base, t):
    i = t - base - 1
    if i < 0 or (i + 1) * 14 > len(blob): return None
    return blob[i * 14:(i + 1) * 14]


def credit_of(db, sha, base, rows_blob, parentsha):
    """[[first, last, supplier]] for a revision whose rows are rows_blob: supplier is a revision
    sha or 'unknown-ancestry'. Reads only stored packed rows and stored credit."""
    n = len(rows_blob) // 14
    ticks = range(base + 1, base + n + 1)
    for same in db.execute('SELECT sha, credit FROM revisions WHERE inputs = ? AND sha != ? ORDER BY first_seen LIMIT 8',
                           (inputs_digest(base, rows_blob), sha)).fetchall():
        # A copy of an earlier revision takes its suppliers -- unless that one descends from this
        # one (a child that restored these rows exactly, uploaded first).
        if not descends(db, same['sha'], sha):
            return json.loads(same['credit'])
    if parentsha is None:
        return [[base + 1, base + n, sha]]
    chain, cur, missing = [], parentsha, False
    while cur and len(chain) < CHAIN_DEPTH:
        row = db.execute('SELECT sha, base, rows, credit, parentsha FROM revisions WHERE sha = ?', (cur,)).fetchone()
        if row is None: missing = True; break
        chain.append(row); cur = row['parentsha']
    if not chain:
        return [[base + 1, base + n, 'unknown-ancestry']]
    # A row no known ancestor holds is this revision's, unless the chain broke at an unseen
    # parent, which may hold it (a truncated revision restored by its child).
    fresh = 'unknown-ancestry' if missing else sha
    supplied = [dict() for _ in chain]      # per ancestor, its credit as a lookup by tick (lazy)
    def supplier(k, t):
        if t not in supplied[k]:
            for a, b, w in json.loads(chain[k]['credit']):
                for x in range(a, b + 1): supplied[k][x] = w
        return supplied[k].get(t, 'unknown-ancestry')
    out = []
    for t in ticks:
        mine = row_at(rows_blob, base, t)
        w = fresh
        for k, anc in enumerate(chain):
            if row_at(anc['rows'], anc['base'], t) == mine:
                w = supplier(k, t); break
        if out and out[-1][2] == w and out[-1][1] == t - 1: out[-1][1] = t
        else: out.append([t, t, w])
    return out


def descends(db, child, ancestor):
    cur, k = child, 0
    while cur and k < 4 * CHAIN_DEPTH:
        if cur == ancestor: return True
        row = db.execute('SELECT parentsha FROM revisions WHERE sha = ?', (cur,)).fetchone()
        cur = row['parentsha'] if row else None; k += 1
    return False


def inputs_digest(base, rows_blob):
    return hashlib.sha256(struct.pack('<i', base) + rows_blob).hexdigest()


def create_app(store, account_db, codes_file, clock=time.time):
    tr = load_tasrev()
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = MAX_BODY
    store, account_db = Path(store), Path(account_db)
    with connect(store) as db:
        db.execute('PRAGMA journal_mode=WAL')
        salt = bytes.fromhex(db.execute("SELECT v FROM meta WHERE k = 'salt'").fetchone()['v'])
    # A refusal answers 200 with ok=0: the game's HTTP client keeps no body for other statuses.
    def fail(message, status): return jsonify(ok=0, error=message, status=status), 200
    def peer():
        # nginx sets X-Forwarded-For to its peer; ProxyFix (tasrevd_wsgi) turns that into remote_addr.
        return hashlib.sha256(salt + (request.remote_addr or '').encode()).hexdigest()[:24]
    def spend(db, size, now):
        """Counts this request against the peer's and everyone's day before any work; False if over."""
        day = int(now // 86400); p = peer()
        tot = db.execute('SELECT COALESCE(SUM(n), 0), COALESCE(SUM(bytes), 0) FROM uploads WHERE day = ?', (day,)).fetchone()
        mine = db.execute('SELECT n, bytes FROM uploads WHERE peer = ? AND day = ?', (p, day)).fetchone()
        if tot[0] >= DAY_ITEMS or tot[1] + size > DAY_BYTES: return False
        if mine is not None and (mine['n'] >= PEER_ITEMS or mine['bytes'] + size > PEER_BYTES): return False
        db.execute('INSERT INTO uploads(peer, day, n, bytes) VALUES (?, ?, 1, ?) ON CONFLICT(peer, day)'
                   ' DO UPDATE SET n = n + 1, bytes = bytes + ?', (p, day, size, size))
        db.execute('DELETE FROM uploads WHERE day < ?', (day - 2,))
        return True
    def binding(pub):
        try:
            with connect(account_db, readonly=True) as adb: return accounts.ranked_as(adb, pub)
        except sqlite3.Error as e: raise Unavailable('the account list cannot be read (%s)' % e)
    @app.errorhandler(sqlite3.Error)
    def busy(e): return fail('The TAS service is busy; try again', 503)
    @app.errorhandler(Unavailable)
    def unavailable(e): return fail('The TAS service cannot tell right now: %s; try again' % e, 503)
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
        if request.mimetype != 'application/json': return fail('Expected application/json', 415)
        now = int(clock())
        with connect(store) as db, writing(db):
            if not spend(db, request.content_length, now): return fail('Too many uploads today', 429)
        data = request.get_json(silent=True)
        line = data.get('line') if isinstance(data, dict) else None
        if not isinstance(line, str) or len(line) > 600: return fail('Invalid statement', 400)
        try: pub = tr.check_sig(line)
        except tr.Refused as e: return fail('Statement refused: %s' % e, 400)
        w = line.split(' '); sha, code = w[2], w[7]
        sid = hashlib.sha256(line.encode('ascii')).hexdigest()
        state, steamid = binding(pub)
        with connect(store) as db, writing(db):
            if db.execute('SELECT COUNT(*) FROM statements').fetchone()[0] >= STATEMENT_CAP:
                return fail('The statement store is full', 507)
            if db.execute('SELECT 1 FROM statements WHERE id = ?', (sid,)).fetchone() is None:
                if db.execute('SELECT COUNT(*) FROM statements WHERE sha = ?', (sha,)).fetchone()[0] >= PER_REVISION:
                    return fail('Too many statements about this revision', 429)
                # A key may sign one revision again (a released build after a dev one), a few times.
                if db.execute('SELECT COUNT(*) FROM statements WHERE sha = ? AND pub = ?', (sha, pub)).fetchone()[0] >= PER_KEY:
                    return fail('Too many statements by this key about this revision', 429)
            db.execute('INSERT OR IGNORE INTO statements(id, sha, line, pub, code, first_seen, steamid, state)'
                       ' VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (sid, sha, line, pub, code, now, steamid, state))
            row = db.execute('SELECT id, first_seen, state FROM statements WHERE id = ?', (sid,)).fetchone()
            have = db.execute('SELECT first_seen FROM revisions WHERE sha = ?', (sha,)).fetchone()
        return jsonify(ok=1, id=row['id'], first_seen=row['first_seen'], linked=row['state'] == accounts.RANK_LINKED,
                       revision=have is not None, before_revision=have is None or row['first_seen'] <= have['first_seen'])
    @app.post('/api/tasrev/revision')
    def revision():
        if request.mimetype != 'text/x-tasrev': return fail('Expected text/x-tasrev', 415)
        now = int(clock())
        with connect(store) as db, writing(db):
            if not spend(db, request.content_length, now): return fail('Too many uploads today', 429)
        body = request.get_data(cache=False)
        m = TAIL.search(body)
        if not m: return fail('Revision refused: it does not end in its revsha line', 400)
        stated = m.group(1).decode()
        with connect(store) as db:
            known = db.execute('SELECT first_seen, parentsha FROM revisions WHERE sha = ?', (stated,)).fetchone()
        if known is not None:
            return jsonify(ok=1, sha=stated, first_seen=known['first_seen'], parent=known['parentsha'])
        try: info = tr.parse(body)
        except tr.Refused as e: return fail('Revision refused: %s' % e, 400)
        if info['stated'] != info['h']: return fail('Revision refused: its revsha is not its hash', 400)
        mp = body.split(b'\n', 2)[1].decode('ascii').split(' ')[1]
        if not NAME.fullmatch(mp): return fail('Invalid map', 400)
        rows = pack_rows(info['rows'])
        parent = info['parentsha']
        with connect(store, readonly=True) as db:
            prow = db.execute('SELECT body FROM revisions WHERE sha = ?', (parent,)).fetchone() if parent else None
        if prow is not None and info['version'] == '2':
            try: tr.check_supply(info, tr.parse(bytes(prow['body'])))
            except tr.Refused as e: return fail('Revision refused: %s' % e, 400)
        supply = info['supply'] if isinstance(info['supply'], tuple) else (None, None)
        with connect(store) as db, writing(db):
            total = db.execute('SELECT COALESCE(SUM(size), 0) FROM revisions').fetchone()[0]
            if total + len(body) > STORE_CAP: return fail('The revision store is full', 507)
            cr = credit_of(db, info['h'], info['base'], rows, parent)
            db.execute('INSERT OR IGNORE INTO revisions(sha, map, mapcrc, parentsha, version, base, head, supply_a, supply_b,'
                       ' first_seen, size, inputs, rows, credit, body) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                       (info['h'], mp, info['mapcrc'], parent, info['version'], info['base'], info['base'] + len(info['rows']),
                        supply[0], supply[1], now, len(body), inputs_digest(info['base'], rows), rows, json.dumps(cr), body))
            # Revisions that were waiting for this one as their parent (and theirs), recomputed now.
            todo, done = [info['h']], 0
            while todo and done < CASCADE:
                for ch in db.execute('SELECT sha, base, rows, parentsha FROM revisions WHERE parentsha = ?', (todo.pop(0),)).fetchall():
                    db.execute('UPDATE revisions SET credit = ? WHERE sha = ?',
                               (json.dumps(credit_of(db, ch['sha'], ch['base'], ch['rows'], ch['parentsha'])), ch['sha']))
                    todo.append(ch['sha']); done += 1
            first = db.execute('SELECT first_seen FROM revisions WHERE sha = ?', (info['h'],)).fetchone()['first_seen']
        return jsonify(ok=1, sha=info['h'], first_seen=first, parent=parent, parent_known=parent is None or prow is not None)
    def qualifying(db, rev, codes):
        """[(first, last, account)] from the statements that credit this revision, oldest first. The
        signature was verified when the statement arrived; here its fields must be the revision's."""
        if rev['supply_a'] is None: return []          # version 1, or a revision that supplies nothing
        fields = [rev['sha'], rev['parentsha'] or '-', rev['mapcrc'], str(rev['supply_a']), str(rev['supply_b'])]
        out = []
        for st in db.execute('SELECT line, code, first_seen, steamid, state FROM statements WHERE sha = ?'
                             ' ORDER BY first_seen, id', (rev['sha'],)):
            w = st['line'].split(' ')
            if st['first_seen'] > rev['first_seen'] or st['code'] not in codes or w[2:7] != fields: continue
            out.append((int(w[5]), int(w[6]), st['steamid'] if st['state'] == accounts.RANK_LINKED else 'unattributed'))
        return out
    @app.get('/api/tasrev/rev/<sha>')
    def show(sha):
        if not HEX64.fullmatch(sha): return fail('Invalid hash', 400)
        codes = released_codes(codes_file)
        if codes is None: raise Unavailable('the released-code list cannot be read')
        with connect(store, readonly=True) as db:
            rev = db.execute('SELECT sha, map, mapcrc, parentsha, version, base, head, supply_a, supply_b, first_seen, credit'
                             ' FROM revisions WHERE sha = ?', (sha,)).fetchone()
            sts = [dict(id=s['id'], ticks=[int(s['line'].split(' ')[5]), int(s['line'].split(' ')[6])], first_seen=s['first_seen'],
                        released_code=s['code'] in codes, account=s['steamid'] if s['state'] == accounts.RANK_LINKED else '',
                        before_revision=rev is None or s['first_seen'] <= rev['first_seen'])
                   for s in db.execute('SELECT id, line, code, first_seen, steamid, state FROM statements WHERE sha = ?'
                                       ' ORDER BY first_seen, id', (sha,))]
            if rev is None:
                if not sts: return fail('Unknown revision', 404)
                return jsonify(ok=1, revision=None, statements=sts, credit=[])
            cache, credit = {}, []
            for a, b, sup in json.loads(rev['credit']):
                if sup not in cache:
                    srow = db.execute('SELECT sha, parentsha, mapcrc, supply_a, supply_b, first_seen FROM revisions WHERE sha = ?',
                                      (sup,)).fetchone() if HEX64.fullmatch(sup) else None
                    cache[sup] = qualifying(db, srow, codes) if srow is not None else None
                spans = cache[sup]
                for t in range(a, b + 1):
                    if spans is None: who = sup if not HEX64.fullmatch(sup) else 'unknown-ancestry'
                    else: who = next((acc for x, y, acc in spans if x <= t <= y), 'unsigned')
                    if credit and credit[-1][2] == who and credit[-1][1] == t - 1: credit[-1][1] = t
                    else: credit.append([t, t, who])
        rv = dict(rev); rv.pop('credit')
        return jsonify(ok=1, revision=rv, statements=sts, credit=[dict(first=a, last=b, who=w) for a, b, w in credit])
    @app.get('/api/tasrev/rev/<sha>/file')
    def file(sha):
        if not HEX64.fullmatch(sha): return fail('Invalid hash', 400)
        with connect(store, readonly=True) as db:
            row = db.execute('SELECT body FROM revisions WHERE sha = ?', (sha,)).fetchone()
        if row is None: return fail('Unknown revision', 404)
        return Response(bytes(row['body']), mimetype='text/plain')
    @app.get('/api/tasrev/map/<mp>')
    def by_map(mp):
        if not NAME.fullmatch(mp): return fail('Invalid map', 400)
        before = request.args.get('before', '')
        before = int(before) if before.isdigit() else 2 ** 62
        with connect(store, readonly=True) as db:
            rows = db.execute('SELECT r.sha, r.parentsha, r.base, r.head, r.supply_a, r.supply_b, r.first_seen,'
                              ' (SELECT COUNT(*) FROM statements s WHERE s.sha = r.sha AND s.first_seen <= r.first_seen'
                              "  AND s.state = 'linked') AS signed"
                              ' FROM revisions r WHERE r.map = ? AND r.first_seen < ? ORDER BY r.first_seen DESC LIMIT 100',
                              (mp, before)).fetchall()
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
