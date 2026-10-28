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
  GET  /api/tasrev/map/<map>[?before=<seq>]   revisions on a map, newest first.

Every arrival (revision or statement) takes the next number of one sequence; "before" and
"earliest" below mean by that number, never by a clock.

CREDIT is stored per revision as tick ranges naming the revision that supplied each row. A tick
whose row equals the parent's takes the parent's supplier. A changed tick takes the supplier of
the nearest ancestor holding the same row there (a revert credits whoever first supplied it),
found by visiting only the ancestors that changed that tick; if none holds it, it is this
revision's own -- unless it is at or before the parent's base (never a child's: tools/tasrev.py),
or the search could not see the whole chain (an unseen ancestor, a cut), which is
"unknown-ancestry": cannot tell. A revision with the same map, base and rows as an earlier one
takes that one's credit, unless the earlier one descends from it; if that cannot be told (a gap
in the earlier one's chain), "unknown-ancestry". Arrivals queue the revisions whose credit may
change; every POST works through the queue for a moment, and a waiting revision reads `pending`.

A supplier revision's ticks go to the first statement about it that names its fields, spans the
tick, names a released csprogs (codes.txt) and arrived before the revision itself; others are
skipped, never blocking. Its account is the one its key was linked to WHEN THE STATEMENT ARRIVED
(unlinked or banned then: nobody); later links and relinks never move it. So a player links
before signing, and the client registers a statement before it shares the revision.
"""
from bisect import bisect_right
from collections import OrderedDict
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
import threading
import time
from flask import Flask, Response, jsonify, request
import accounts

MAX_BODY = 4700 * 1024              # 96000 rows of the widest canonical form (46 bytes) fit
NAME = re.compile(r'[A-Za-z0-9_.+-]{1,64}')
HEX64 = re.compile(r'[0-9a-f]{64}')
UNKNOWN = 'unknown-ancestry'
WALK_MAX, WORK_MAX = 4096, 1000000  # ancestors visited, rows compared, per credit computation (Pi: ~1 s)
DRAIN_SECONDS = 0.5                 # queue work per POST
PEER_ITEMS, PEER_BYTES = 200, 64 * 1024 ** 2          # a peer's day of uploads
DAY_ITEMS, DAY_BYTES = 5000, 1024 ** 3                 # everyone's day
PEER_READS = 60                     # a peer's reads a minute
STORE_CAP, STATEMENT_CAP, PER_REVISION, PER_KEY = 2 * 1024 ** 3, 200000, 32, 4
SQL = '''
CREATE TABLE IF NOT EXISTS revisions(sha TEXT PRIMARY KEY, seq INTEGER NOT NULL UNIQUE, map TEXT NOT NULL,
 mapcrc TEXT NOT NULL, parentsha TEXT, version TEXT NOT NULL, base INTEGER NOT NULL, head INTEGER NOT NULL,
 supply_a INTEGER, supply_b INTEGER, first_seen INTEGER NOT NULL, size INTEGER NOT NULL, inputs TEXT NOT NULL,
 rows BLOB NOT NULL, changed TEXT, credit TEXT NOT NULL, body BLOB NOT NULL);
CREATE INDEX IF NOT EXISTS revisions_map ON revisions(map, seq);
CREATE INDEX IF NOT EXISTS revisions_parent ON revisions(parentsha);
CREATE INDEX IF NOT EXISTS revisions_inputs ON revisions(inputs, seq);
CREATE TABLE IF NOT EXISTS statements(id TEXT PRIMARY KEY, seq INTEGER NOT NULL UNIQUE, sha TEXT NOT NULL,
 parent TEXT NOT NULL, mapcrc TEXT NOT NULL, first INTEGER NOT NULL, last INTEGER NOT NULL, code TEXT NOT NULL,
 pub TEXT NOT NULL, line TEXT NOT NULL, first_seen INTEGER NOT NULL, steamid TEXT NOT NULL, state TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS statements_sha ON statements(sha, seq);
CREATE INDEX IF NOT EXISTS statements_key ON statements(sha, pub);
CREATE TABLE IF NOT EXISTS stale(id INTEGER PRIMARY KEY AUTOINCREMENT, sha TEXT NOT NULL UNIQUE);
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
        with db:
            db.execute('INSERT OR IGNORE INTO meta(k, v) VALUES (?, ?)', ('salt', secrets.token_hex(32)))
            db.execute("INSERT OR IGNORE INTO meta(k, v) VALUES ('seq', '0')")
    finally: db.close()
    os.chmod(path, 0o600)


def released_codes(path):
    """The csprogs sha256s a statement's `code` may name, one a line (appended at each release or
    deploy). None when the list cannot be read: "cannot tell" is not "nothing is released"."""
    try: text = Path(path).read_text(encoding='utf-8-sig')
    except (OSError, UnicodeDecodeError): return None
    codes = frozenset(w.lower() for w in text.split() if HEX64.fullmatch(w.lower()))
    return codes or None


def next_seq(db):
    db.execute("UPDATE meta SET v = CAST(v AS INTEGER) + 1 WHERE k = 'seq'")
    return int(db.execute("SELECT v FROM meta WHERE k = 'seq'").fetchone()[0])


# Rows are 7 int16 (tools/tasrev.py bounds every i value to -32768..32767), 14 bytes a tick.
def pack_rows(rows):
    return b''.join(struct.pack('<7h', *(int(v) for v in r)) for r in rows)


def row_at(blob, base, t):
    i = t - base - 1
    if i < 0 or (i + 1) * 14 > len(blob): return None
    return blob[i * 14:(i + 1) * 14]


def span(blob, base, a, b):
    """Rows a..b as one slice, or None unless the blob holds all of them."""
    if a <= base or (b - base) * 14 > len(blob): return None
    return blob[(a - base - 1) * 14:(b - base) * 14]


def to_ranges(ticks):
    out = []
    for t in ticks:
        if out and out[-1][1] == t - 1: out[-1][1] = t
        else: out.append([t, t])
    return out


def intersect(x, y):
    out, i, j = [], 0, 0
    while i < len(x) and j < len(y):
        a, b = max(x[i][0], y[j][0]), min(x[i][1], y[j][1])
        if a <= b: out.append([a, b])
        if x[i][1] < y[j][1]: i += 1
        else: j += 1
    return out


def diff_ranges(blob, base, pblob, pbase):
    """Ticks where the two revisions' rows differ, one holding a row and the other not included."""
    lo = min(base, pbase) + 1
    hi = max(base + len(blob) // 14, pbase + len(pblob) // 14)
    changed, t = [], lo
    while t <= hi:
        e = min(hi, t + 63)
        a, b = span(blob, base, t, e), span(pblob, pbase, t, e)
        if a is None or a != b:
            changed += [x for x in range(t, e + 1) if row_at(blob, base, x) != row_at(pblob, pbase, x)]
        t = e + 1
    return to_ranges(changed)


class Lookup:
    def __init__(self, ranges):
        self.r = ranges; self.starts = [r[0] for r in ranges]
    def __call__(self, t):
        i = bisect_right(self.starts, t) - 1
        return self.r[i][2] if i >= 0 and t <= self.r[i][1] else UNKNOWN


def inputs_digest(mp, mapcrc, base, rows_blob):
    return hashlib.sha256(('%s %s %d\n' % (mp, mapcrc, base)).encode() + rows_blob).hexdigest()


def descends(db, child, ancestor):
    """True if `ancestor` is in `child`'s chain, False if the chain reaches a root without it,
    None if a link is unseen or the walk is cut: cannot tell."""
    cur = child
    for _ in range(WALK_MAX):
        row = db.execute('SELECT parentsha FROM revisions WHERE sha = ?', (cur,)).fetchone()
        if row is None: return None
        cur = row['parentsha']
        if cur is None: return False
        if cur == ancestor: return True
    return None


def compute(db, r):
    """(credit, changed) for revision row-like `r` (sha, seq, base, rows, parentsha, inputs)."""
    sha, base, blob = r['sha'], r['base'], bytes(r['rows'])
    n = len(blob) // 14
    lo, hi = base + 1, base + n
    whole = lambda w: [[lo, hi, w]] if n else []
    par = db.execute('SELECT sha, base, rows, credit, changed, parentsha FROM revisions WHERE sha = ?',
                     (r['parentsha'],)).fetchone() if r['parentsha'] else None
    if r['parentsha'] is None: changed = [[lo, hi]] if n else []
    else: changed = diff_ranges(blob, base, bytes(par['rows']), par['base']) if par is not None else None
    same = db.execute('SELECT sha, credit FROM revisions WHERE inputs = ? AND seq < ? ORDER BY seq LIMIT 1',
                      (r['inputs'], r['seq'])).fetchone()
    if same is not None:
        d = descends(db, same['sha'], sha)
        if d is None: return whole(UNKNOWN), changed
        if d is False: return json.loads(same['credit']), changed
    if r['parentsha'] is None: return whole(sha), changed
    if par is None: return whole(UNKNOWN), changed
    mine = intersect(changed, [[lo, hi]])
    who = {}
    pending, prev, cur = mine, par['changed'], par['parentsha']
    steps = work = 0
    cut = False
    while pending and cur is not None:
        # The row at a tick changes along the chain only at an ancestor that changed it: compare
        # this revision's rows with B (= cur) where B's child (prev) changed them.
        if prev is None: cut = True; break
        steps += 1
        b = db.execute('SELECT sha, base, credit, changed, parentsha FROM revisions WHERE sha = ?', (cur,)).fetchone()
        prev_r = json.loads(prev)
        work += len(prev_r) + len(pending)
        if b is None or steps > WALK_MAX or work > WORK_MAX: cut = True; break
        both = intersect(pending, prev_r)
        if both:
            brows = bytes(db.execute('SELECT rows FROM revisions WHERE sha = ?', (cur,)).fetchone()[0])
            bwho = Lookup(json.loads(b['credit']))
            found, bb, bn = [], b['base'] + 1, len(brows) // 14
            for a, z in both:
                work += z - a + 1
                for t in range(max(a, bb), min(z, bb + bn - 1) + 1):
                    i, j = (t - bb) * 14, (t - lo) * 14
                    if brows[i:i + 14] == blob[j:j + 14]:
                        who[t] = bwho(t); found.append(t)
            if found:
                gone = set(found)
                pending = to_ranges([t for a, z in pending for t in range(a, z + 1) if t not in gone])
        prev, cur = b['changed'], b['parentsha']
    for a, z in pending:
        for t in range(a, z + 1):
            who[t] = UNKNOWN if cut or t <= par['base'] else sha
    # Unchanged stretches take the parent's ranges whole; changed ticks one by one.
    out, pr = [], json.loads(par['credit'])
    pstarts = [p[0] for p in pr]
    def add(a, z, w):
        if out and out[-1][2] == w and out[-1][1] == a - 1: out[-1][1] = z
        else: out.append([a, z, w])
    edges = sorted(set([lo, hi + 1] + [a for a, z in mine] + [z + 1 for a, z in mine]))
    inmine = Lookup([[a, z, 1] for a, z in mine])
    for a, z in zip(edges, edges[1:]):
        z -= 1
        if inmine(a) == 1:
            for t in range(a, z + 1): add(t, t, who[t])
            continue
        for x, y, w in pr[max(0, bisect_right(pstarts, a) - 1):]:
            if x > z: break
            x, y = max(x, a), min(y, z)
            if x <= y: add(x, y, w)
    return out, changed


def recompute(db, sha):
    r = db.execute('SELECT sha, seq, base, rows, parentsha, inputs, credit, changed FROM revisions WHERE sha = ?',
                   (sha,)).fetchone()
    if r is None: return
    cr, ch = compute(db, r)
    crj, chj = json.dumps(cr), (json.dumps(ch) if ch is not None else None)
    if crj != r['credit'] or chj != r['changed']:
        db.execute('UPDATE revisions SET credit = ?, changed = ? WHERE sha = ?', (crj, chj, sha))
        db.executemany('INSERT OR IGNORE INTO stale(sha) VALUES (?)',
                       db.execute('SELECT sha FROM revisions WHERE parentsha = ?', (sha,)).fetchall())
    if db.execute('SELECT 1 FROM revisions WHERE inputs = ? AND seq < ?', (r['inputs'], r['seq'])).fetchone() is None:
        # The earliest of its inputs: the later copies read its credit and its chain.
        db.executemany('INSERT OR IGNORE INTO stale(sha) VALUES (?)',
                       db.execute('SELECT sha FROM revisions WHERE inputs = ? AND seq > ?', (r['inputs'], r['seq'])).fetchall())


def drain(db, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        row = db.execute('SELECT id, sha FROM stale ORDER BY id LIMIT 1').fetchone()
        if row is None: return
        db.execute('DELETE FROM stale WHERE id = ?', (row['id'],))
        recompute(db, row['sha'])


def create_app(store, account_db, codes_file, clock=time.time):
    tr = load_tasrev()
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = MAX_BODY
    store, account_db = Path(store), Path(account_db)
    with connect(store) as db:
        db.execute('PRAGMA journal_mode=WAL')
        salt = bytes.fromhex(db.execute("SELECT v FROM meta WHERE k = 'salt'").fetchone()['v'])
    reads, reads_lock = {}, threading.Lock()
    shown, shown_lock = OrderedDict(), threading.Lock()   # (sha, credit, codes) -> answer
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
    def codes_now():
        codes = released_codes(codes_file)
        if codes is None: raise Unavailable('the released-code list cannot be read')
        return codes
    @app.errorhandler(sqlite3.Error)
    def busy(e): return fail('The TAS service is busy; try again', 503)
    @app.errorhandler(Unavailable)
    def unavailable(e): return fail('The TAS service cannot tell right now: %s; try again' % e, 503)
    @app.before_request
    def budgets():
        if request.method == 'POST':
            size = request.content_length
            if size is None or size <= 0: return fail('Request length required', 411)
            if size > MAX_BODY: return fail('Upload too large', 413)
        else:
            p, minute = peer(), int(clock() // 60)
            with reads_lock:
                if len(reads) > 50000: reads.clear()
                k = (p, minute); reads[k] = reads.get(k, 0) + 1
                if reads[k] > PEER_READS: return fail('Too many requests; try again in a minute', 429)
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
        w = line.split(' ')
        sid = hashlib.sha256(line.encode('ascii')).hexdigest()
        state, steamid = binding(pub)
        with connect(store) as db, writing(db):
            if db.execute('SELECT 1 FROM statements WHERE id = ?', (sid,)).fetchone() is None:
                if db.execute('SELECT COUNT(*) FROM statements').fetchone()[0] >= STATEMENT_CAP:
                    return fail('The statement store is full', 507)
                if db.execute('SELECT COUNT(*) FROM statements WHERE sha = ?', (w[2],)).fetchone()[0] >= PER_REVISION:
                    return fail('Too many statements about this revision', 429)
                # A key may sign one revision again (a released build after a dev one), a few times.
                if db.execute('SELECT COUNT(*) FROM statements WHERE sha = ? AND pub = ?', (w[2], pub)).fetchone()[0] >= PER_KEY:
                    return fail('Too many statements by this key about this revision', 429)
                db.execute('INSERT INTO statements(id, seq, sha, parent, mapcrc, first, last, code, pub, line, first_seen, steamid,'
                           ' state) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                           (sid, next_seq(db), w[2], w[3], w[4], int(w[5]), int(w[6]), w[7], pub, line, now, steamid, state))
            row = db.execute('SELECT id, seq, first_seen, state FROM statements WHERE id = ?', (sid,)).fetchone()
            have = db.execute('SELECT seq FROM revisions WHERE sha = ?', (w[2],)).fetchone()
            drain(db, DRAIN_SECONDS)
        return jsonify(ok=1, id=row['id'], first_seen=row['first_seen'], linked=row['state'] == accounts.RANK_LINKED,
                       revision=have is not None, before_revision=have is None or row['seq'] < have['seq'])
    @app.post('/api/tasrev/revision')
    def revision():
        if request.mimetype != 'text/x-tasrev': return fail('Expected text/x-tasrev', 415)
        now = int(clock())
        with connect(store) as db, writing(db):
            if not spend(db, request.content_length, now): return fail('Too many uploads today', 429)
        body = request.get_data(cache=False)
        try: info = tr.parse(body)
        except tr.Refused as e: return fail('Revision refused: %s' % e, 400)
        if info['stated'] != info['h']: return fail('Revision refused: its revsha is not its hash', 400)
        mp = body.split(b'\n', 2)[1].decode('ascii').split(' ')[1]
        if not NAME.fullmatch(mp): return fail('Invalid map', 400)
        rows, parent = pack_rows(info['rows']), info['parentsha']
        supply = info['supply'] if isinstance(info['supply'], tuple) else (None, None)
        inputs = inputs_digest(mp, info['mapcrc'], info['base'], rows)
        with connect(store) as db, writing(db):
            known = db.execute('SELECT seq, first_seen, parentsha FROM revisions WHERE sha = ?', (info['h'],)).fetchone()
            if known is not None:
                return jsonify(ok=1, sha=info['h'], seq=known['seq'], first_seen=known['first_seen'], parent=known['parentsha'])
            prow = db.execute('SELECT base, rows FROM revisions WHERE sha = ?', (parent,)).fetchone() if parent else None
            if prow is not None and info['version'] == '2':
                # tools/tasrev.py check_supply over the stored rows: the changed ticks after the parent's base.
                ch = [t for a, z in intersect(diff_ranges(rows, info['base'], bytes(prow['rows']), prow['base']),
                                              [[max(prow['base'], info['base']) + 1, info['base'] + len(info['rows'])]])
                      for t in (a, z)]
                want = (ch[0], ch[-1]) if ch else None
                if info['supply'] != want:
                    return fail('Revision refused: supply %s, but the rows differ over %s' % (info['supply'], want), 400)
            if db.execute('SELECT COALESCE(SUM(size), 0) FROM revisions').fetchone()[0] + len(body) > STORE_CAP:
                return fail('The revision store is full', 507)
            r = dict(sha=info['h'], seq=next_seq(db), base=info['base'], rows=rows, parentsha=parent, inputs=inputs)
            cr, ch = compute(db, r)
            db.execute('INSERT INTO revisions(sha, seq, map, mapcrc, parentsha, version, base, head, supply_a, supply_b,'
                       ' first_seen, size, inputs, rows, changed, credit, body) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                       (r['sha'], r['seq'], mp, info['mapcrc'], parent, info['version'], info['base'],
                        info['base'] + len(info['rows']), supply[0], supply[1], now, len(body), inputs, rows,
                        json.dumps(ch) if ch is not None else None, json.dumps(cr), body))
            db.executemany('INSERT OR IGNORE INTO stale(sha) VALUES (?)',
                           db.execute('SELECT sha FROM revisions WHERE parentsha = ?', (r['sha'],)).fetchall())
            drain(db, DRAIN_SECONDS)
        return jsonify(ok=1, sha=r['sha'], seq=r['seq'], first_seen=now, parent=parent, parent_known=parent is None or prow is not None)
    def qualifying(db, rev, codes):
        """[(first, last, account)] from the statements that credit this revision, earliest first."""
        if rev['supply_a'] is None: return []           # version 1, or a revision that supplies nothing
        out = []
        for st in db.execute('SELECT first, last, code, steamid, state FROM statements WHERE sha = ? AND seq < ? AND parent = ?'
                             ' AND mapcrc = ? AND first = ? AND last = ? ORDER BY seq',
                             (rev['sha'], rev['seq'], rev['parentsha'] or '-', rev['mapcrc'], rev['supply_a'], rev['supply_b'])):
            if st['code'] in codes:
                out.append((st['first'], st['last'], st['steamid'] if st['state'] == accounts.RANK_LINKED else 'unattributed'))
        return out
    def resolve(db, credit, codes):
        """Supplier ranges -> account ranges, range by range (never per tick)."""
        cache, out = {}, []
        def add(a, z, w):
            if out and out[-1][2] == w and out[-1][1] == a - 1: out[-1][1] = z
            else: out.append([a, z, w])
        for a, z, sup in credit:
            if sup not in cache:
                srow = db.execute('SELECT sha, seq, parentsha, mapcrc, supply_a, supply_b FROM revisions WHERE sha = ?',
                                  (sup,)).fetchone() if HEX64.fullmatch(sup) else None
                cache[sup] = qualifying(db, srow, codes) if srow is not None else None
            spans = cache[sup]
            if spans is None: add(a, z, UNKNOWN); continue
            t = a
            while t <= z:
                hit = next(((x, y, acc) for x, y, acc in spans if x <= t <= y), None)
                if hit is None:
                    nxt = min([x for x, y, acc in spans if x > t] + [z + 1])
                    add(t, min(z, nxt - 1), 'unsigned'); t = min(z, nxt - 1) + 1
                else:
                    add(t, min(z, hit[1]), hit[2]); t = min(z, hit[1]) + 1
        return out
    @app.get('/api/tasrev/rev/<sha>')
    def show(sha):
        if not HEX64.fullmatch(sha): return fail('Invalid hash', 400)
        codes = codes_now()
        with connect(store, readonly=True) as db:
            rev = db.execute('SELECT sha, seq, map, mapcrc, parentsha, version, base, head, supply_a, supply_b, first_seen, credit'
                             ' FROM revisions WHERE sha = ?', (sha,)).fetchone()
            sts = [dict(id=s['id'], ticks=[s['first'], s['last']], first_seen=s['first_seen'], released_code=s['code'] in codes,
                        account=s['steamid'] if s['state'] == accounts.RANK_LINKED else '',
                        before_revision=rev is None or s['seq'] < rev['seq'])
                   for s in db.execute('SELECT id, seq, first, last, code, first_seen, steamid, state FROM statements'
                                       ' WHERE sha = ? ORDER BY seq', (sha,))]
            if rev is None:
                if not sts: return fail('Unknown revision', 404)
                return jsonify(ok=1, revision=None, statements=sts, credit=[], pending=False)
            pending = db.execute('SELECT 1 FROM stale WHERE sha = ?', (sha,)).fetchone() is not None
            key = (sha, hashlib.sha256(rev['credit'].encode()).hexdigest(), hash(codes))
            with shown_lock: credit = shown.get(key)
            if credit is None:
                credit = resolve(db, json.loads(rev['credit']), codes)
                with shown_lock:
                    shown[key] = credit
                    while len(shown) > 64: shown.popitem(last=False)
        rv = dict(rev); rv.pop('credit')
        return jsonify(ok=1, revision=rv, statements=sts, credit=credit, pending=pending)
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
        codes = codes_now()
        before = request.args.get('before', '')
        before = int(before) if before.isdigit() and len(before) < 16 else 2 ** 62
        with connect(store, readonly=True) as db:
            rows = [dict(r) for r in db.execute('SELECT sha, seq, parentsha, mapcrc, base, head, supply_a, supply_b, first_seen FROM revisions'
                                                ' WHERE map = ? AND seq < ? ORDER BY seq DESC LIMIT 100', (mp, before))]
            for r in rows:
                r['signed'] = len({acc for a, z, acc in qualifying(db, r, codes) if acc != 'unattributed'})
        return jsonify(ok=1, map=mp, revisions=rows)
    return app


def main():
    import argparse
    ap = argparse.ArgumentParser(description='P1091 TAS revision service store')
    ap.add_argument('--store', required=True)
    ap.add_argument('command', choices=['init', 'recompute'])
    a = ap.parse_args()
    if a.command == 'init':
        initialize(a.store)
        print('tasrevd store ready: %s' % a.store)
        return
    with connect(a.store) as db:
        n = 0
        while True:
            with writing(db):
                left = db.execute('SELECT COUNT(*) FROM stale').fetchone()[0]
                if not left: break
                drain(db, 2.0); n += 1
        print('tasrevd: queue empty after %d passes' % n)


if __name__ == '__main__':
    main()
