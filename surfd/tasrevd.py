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
DAY_ITEMS, DAY_BYTES = 50000, 1024 ** 3                # everyone's day (bytes bound the work; items the spam)
PEER_READS = 60                     # a peer's reads a minute; a large credit costs one more a 32 KB
CACHE_BYTES, CACHE_ONE = 16 * 1024 ** 2, 4 * 1024 ** 2   # resolved credit kept as JSON text
HEAVY = 2                           # parses and credit resolutions at once (each tens of MB at 96000 rows)
STORE_CAP, STATEMENT_CAP, PER_REVISION, PER_KEY = 2 * 1024 ** 3, 200000, 32, 4   # bytes stored; unlinked statements
ORPHAN_DAYS = 7                     # a statement whose revision never arrives is dropped after this
SQL = '''
CREATE TABLE IF NOT EXISTS revisions(sha TEXT PRIMARY KEY, seq INTEGER NOT NULL UNIQUE, map TEXT NOT NULL,
 mapcrc TEXT NOT NULL, parentsha TEXT, version TEXT NOT NULL, base INTEGER NOT NULL, head INTEGER NOT NULL,
 supply_a INTEGER, supply_b INTEGER, first_seen INTEGER NOT NULL, size INTEGER NOT NULL, inputs TEXT NOT NULL,
 rows BLOB NOT NULL, changed TEXT, credit TEXT NOT NULL, body BLOB NOT NULL, stored INTEGER NOT NULL);
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
    db = sqlite3.connect(uri, uri=True, timeout=15.0, isolation_level=None)
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


def jdump(x):
    return json.dumps(x, separators=(',', ':')) if x is not None else None


def stored_bytes(body, rows, credit, changed):
    return len(body) + len(rows) + len(credit) + len(changed or '')


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


def subtract(x, y):
    """Sorted, disjoint range lists: the ticks of x not in y."""
    out, j = [], 0
    for a, z in x:
        cur = a
        while j < len(y) and y[j][1] < cur: j += 1
        k = j
        while k < len(y) and y[k][0] <= z and cur <= z:
            if y[k][0] > cur: out.append([cur, y[k][0] - 1])
            cur = max(cur, y[k][1] + 1)
            k += 1
        if cur <= z: out.append([cur, z])
    return out


def diff_ranges(blob, base, pblob, pbase):
    """Ticks where the two revisions' rows differ, one holding a row and the other not included.
    Only the held spans are walked: a tick neither holds is the same in both."""
    held = []
    for a, z in sorted([[base + 1, base + len(blob) // 14], [pbase + 1, pbase + len(pblob) // 14]]):
        if a > z: continue
        if held and a <= held[-1][1] + 1: held[-1][1] = max(held[-1][1], z)
        else: held.append([a, z])
    changed = []
    for lo, hi in held:
        t = lo
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


def legal(version):
    """P1100: version 3 counts ticks from a start-zone placement, 1 and 2 from a base save: rows of
    the two are never compared tick for tick."""
    return version == '3'


def compute(db, r):
    """(credit, changed) for revision row-like `r` (sha, seq, base, rows, parentsha, inputs, version)."""
    sha, base, blob = r['sha'], r['base'], bytes(r['rows'])
    n = len(blob) // 14
    lo, hi = base + 1, base + n
    whole = lambda w: [[lo, hi, w]] if n else []
    par = db.execute('SELECT sha, base, rows, credit, changed, parentsha, version FROM revisions WHERE sha = ?',
                     (r['parentsha'],)).fetchone() if r['parentsha'] else None
    if par is not None and legal(par['version']) != legal(r['version']):
        return whole(UNKNOWN), None     # the intake refuses this pair; a parent that came later cannot tell
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
        b = db.execute('SELECT sha, base, credit, changed, parentsha, version FROM revisions WHERE sha = ?', (cur,)).fetchone()
        prev_r = json.loads(prev)
        work += len(prev_r) + len(pending)
        if b is None or steps > WALK_MAX or work > WORK_MAX or legal(b['version']) != legal(r['version']): cut = True; break
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
                gone = to_ranges(found)
                work += len(pending) + len(gone)
                pending = subtract(pending, gone)
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


DESCENDANTS = (
    'WITH RECURSIVE d(sha, n) AS (SELECT sha, 1 FROM revisions WHERE parentsha = ?'
    ' UNION SELECT r.sha, d.n + 1 FROM revisions r JOIN d ON r.parentsha = d.sha WHERE d.n < ?)'
    ' SELECT sha FROM d GROUP BY sha ORDER BY MIN(n) LIMIT 20000')


def queue_readers(db, sha, cap=20000):
    """Queues every revision whose credit may read `sha`'s: its descendants (they read their
    ancestors' rows, changes and credit), the later copies of each of those and of `sha` (they read
    the earliest's credit and chain), and the copies' descendants. Called when `sha` arrives or its
    credit or changes move -- never otherwise, so the queue settles."""
    seen, roots, out = {sha}, [sha], []
    while roots and len(out) < cap:
        s = roots.pop()
        for d in [s] + [d for (d,) in db.execute(DESCENDANTS, (s, WALK_MAX))]:
            if d not in seen: seen.add(d); out.append(d)
            for (cp,) in db.execute('SELECT c.sha FROM revisions c JOIN revisions o ON c.inputs = o.inputs AND c.seq > o.seq'
                                    ' WHERE o.sha = ?', (d,)):
                if cp not in seen: seen.add(cp); out.append(cp); roots.append(cp)
    db.executemany('INSERT OR IGNORE INTO stale(sha) VALUES (?)', [(x,) for x in out[:cap]])


def recompute(db, sha):
    r = db.execute('SELECT sha, seq, base, rows, parentsha, inputs, credit, changed, size, version FROM revisions WHERE sha = ?',
                   (sha,)).fetchone()
    if r is None: return
    cr, ch = compute(db, r)
    crj, chj = jdump(cr), jdump(ch)
    if crj != r['credit'] or chj != r['changed']:
        db.execute('UPDATE revisions SET credit = ?, changed = ?, stored = ? WHERE sha = ?',
                   (crj, chj, r['size'] + len(r['rows']) + len(crj) + len(chj or ''), sha))
        queue_readers(db, sha)


def prune(db, now, rows=500):
    """A slice of the statements whose revision never arrived within ORPHAN_DAYS, removed; a cursor
    in meta walks the table a slice at a time so no POST scans it whole."""
    start = int((db.execute("SELECT v FROM meta WHERE k = 'prune'").fetchone() or ['0'])[0])
    batch = db.execute('SELECT seq, id, sha, first_seen FROM statements WHERE seq > ? ORDER BY seq LIMIT ?', (start, rows)).fetchall()
    cutoff = now - ORPHAN_DAYS * 86400
    gone = [(s['id'],) for s in batch if s['first_seen'] < cutoff
            and db.execute('SELECT 1 FROM revisions WHERE sha = ?', (s['sha'],)).fetchone() is None]
    db.executemany('DELETE FROM statements WHERE id = ?', gone)
    nxt = batch[-1]['seq'] if len(batch) == rows else 0
    db.execute("INSERT INTO meta(k, v) VALUES ('prune', ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v", (str(nxt),))
    return len(gone)


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
    shown, shown_lock = OrderedDict(), threading.Lock()   # (sha, credit, codes) -> credit JSON text
    heavy = threading.BoundedSemaphore(HEAVY)
    def charge(extra):
        p, minute = peer(), int(clock() // 60)
        with reads_lock: reads[(p, minute)] = reads.get((p, minute), 0) + extra
    app.tasrevd_cache_bytes = lambda: sum(len(v) for v in shown.values())
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
            prune(db, now)
            if db.execute('SELECT 1 FROM statements WHERE id = ?', (sid,)).fetchone() is None:
                # Free keys share the cap; a linked signer is bounded by accounts and budgets instead.
                if state != accounts.RANK_LINKED and db.execute(
                        "SELECT COUNT(*) FROM statements WHERE state != 'linked'").fetchone()[0] >= STATEMENT_CAP:
                    return fail('The statement store is full', 507)
                # Unlinked keys are free to make, so they share a cap a flood cannot take from a linked signer.
                if state != accounts.RANK_LINKED and db.execute("SELECT COUNT(*) FROM statements WHERE sha = ? AND state != 'linked'",
                                                                (w[2],)).fetchone()[0] >= PER_REVISION:
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
        with heavy:
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
                pk = known['parentsha'] is None or db.execute('SELECT 1 FROM revisions WHERE sha = ?', (known['parentsha'],)).fetchone() is not None
                return jsonify(ok=1, sha=info['h'], seq=known['seq'], first_seen=known['first_seen'], parent=known['parentsha'], parent_known=pk)
            prow = db.execute('SELECT base, rows, version FROM revisions WHERE sha = ?', (parent,)).fetchone() if parent else None
            if prow is not None and legal(prow['version']) != legal(info['version']):
                return fail('Revision refused: a legal start and a base save count ticks from different places', 400)
            if prow is not None and info['version'] in ('2', '3'):
                # tools/tasrev.py check_supply over the stored rows: the changed ticks after the parent's base.
                ch = [t for a, z in intersect(diff_ranges(rows, info['base'], bytes(prow['rows']), prow['base']),
                                              [[max(prow['base'], info['base']) + 1, info['base'] + len(info['rows'])]])
                      for t in (a, z)]
                want = (ch[0], ch[-1]) if ch else None
                if info['supply'] != want:
                    return fail('Revision refused: supply %s, but the rows differ over %s' % (info['supply'], want), 400)
            r = dict(sha=info['h'], seq=next_seq(db), base=info['base'], rows=rows, parentsha=parent, inputs=inputs,
                     version=info['version'])
            cr, ch = compute(db, r)
            crj, chj = jdump(cr), jdump(ch)
            stored = stored_bytes(body, rows, crj, chj)
            # Everything a revision keeps counts: a fragmented credit can be several times its body.
            if db.execute('SELECT COALESCE(SUM(stored), 0) FROM revisions').fetchone()[0] + stored > STORE_CAP:
                return fail('The revision store is full', 507)
            db.execute('INSERT INTO revisions(sha, seq, map, mapcrc, parentsha, version, base, head, supply_a, supply_b,'
                       ' first_seen, size, inputs, rows, changed, credit, body, stored)'
                       ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                       (r['sha'], r['seq'], mp, info['mapcrc'], parent, info['version'], info['base'],
                        info['base'] + len(info['rows']), supply[0], supply[1], now, len(body), inputs, rows,
                        chj, crj, body, stored))
            # The peer's day pays for what was kept beyond the body it sent.
            db.execute('UPDATE uploads SET bytes = bytes + ? WHERE peer = ? AND day = ?', (stored - len(body), peer(), int(now // 86400)))
            queue_readers(db, r['sha'])
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
            db.execute('BEGIN')         # one snapshot: the credit and its pending flag agree
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
                with heavy: credit = json.dumps(resolve(db, json.loads(rev['credit']), codes), separators=(',', ':'))
                if len(credit) <= CACHE_ONE:
                    with shown_lock:
                        shown[key] = credit
                        while sum(len(v) for v in shown.values()) > CACHE_BYTES: shown.popitem(last=False)
        charge(len(credit) // 32768)
        rv = dict(rev); rv.pop('credit')
        return Response('{"ok":1,"revision":%s,"statements":%s,"credit":%s,"pending":%s}\n'
                        % (json.dumps(rv), json.dumps(sts), credit, 'true' if pending else 'false'), mimetype='application/json')
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
        before = int(before) if re.fullmatch('[0-9]{1,15}', before) else 2 ** 62
        with connect(store, readonly=True) as db:
            rows = [dict(r) for r in db.execute('SELECT sha, seq, parentsha, mapcrc, base, head, supply_a, supply_b, first_seen FROM revisions'
                                                ' WHERE map = ? AND seq < ? ORDER BY seq DESC LIMIT 100', (mp, before))]
            for r in rows:
                r['signers'] = len({acc for a, z, acc in qualifying(db, r, codes) if acc != 'unattributed'})
        return jsonify(ok=1, map=mp, revisions=rows)
    return app


def main():
    import argparse
    ap = argparse.ArgumentParser(description='P1091 TAS revision service store')
    ap.add_argument('--store', required=True)
    ap.add_argument('command', choices=['init', 'recompute', 'rebuild'])
    a = ap.parse_args()
    if a.command == 'init':
        initialize(a.store)
        print('tasrevd store ready: %s' % a.store)
        return
    with connect(a.store) as db:
        if a.command == 'rebuild':      # repairs a store: every revision recomputed, oldest first
            with writing(db): db.execute('INSERT OR IGNORE INTO stale(sha) SELECT sha FROM revisions ORDER BY seq')
        n = 0
        while True:
            with writing(db):
                left = db.execute('SELECT COUNT(*) FROM stale').fetchone()[0]
                if not left: break
                drain(db, 2.0); n += 1
        print('tasrevd: queue empty after %d passes' % n)


if __name__ == '__main__':
    main()
