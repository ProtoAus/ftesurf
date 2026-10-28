"""P815: what an accepted admin upload does to the publish directories, and when.

An upload is queued (`publications`, kind pending) and goes live only when no lobby
has had its map loaded for QUIET seconds, with every lobby heard throughout, nothing
of the map owed a verdict and a sweep since: a lobby on the map keeps its table
until its next map load, but `retry` reloads it (a run would change zones
mid-attempt), and the sweeper verifies a finished run against the files as they are
then. mapwatch.py holds Momentum's zones on the first condition alone.

Kinds: pending, applying (files being written; recovered at the next tick), live,
noop (already live), superseded, failed (files put back), partial (put back failed:
an operator's rollback), rollback. `result` is each directory's sha after a live or
rollback row, which is what the files must still be for a later rollback.

P1081 `force` (the admin chose "reload now"), pending:
  1. warn every local lobby on or assigned to the map (`say`, then `status` as the ack: say
     prints nothing to rcon); all must answer or the round is retried next tick.
  2. after FORCE_NOTICE, record the newest sweep completion stamp (`sweepbase`); ready once two
     newer completions are in the log (sweeps cannot overlap, flock -n, so the second STARTED
     after the grace) and nothing of the map is owed a verdict. A warning older than REWARN is
     given again first.
  3. targets read again, files written (or already live: noop), `todo` = those lobbies.
Then, live or noop: each tick asks each lobby in `todo` for `status`; gone from the map or
loaded after the current files were written is done, otherwise `changelevel` again, up to
RELOAD_TRIES rounds (then left for an operator in `reload`). A crash between the write and
the reload recovers as live with `todo` empty, which starts the reload. Never past an owed
verdict; evidence posted after the warning and not yet indexed is checked against the new zones.
"""
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import socket
import stat
import sys
import sqlite3
import threading
try:
    import fcntl
except ImportError:             # Windows test runs: one process, the thread lock is enough
    fcntl = None

QUIET = 600         # since the map left the last lobby
HEAR_GAP = 150      # a longer gap between lobby reads starts the watch again
LOBBY_SILENT = 30   # surfd's LOBBY_TTL: a lobby row older than this is down or not heard
SWEPT_AFTER = 360   # the sweep log must be newer than the map's last sighting by this much
RATE = 20           # publishes per account per hour
KEEP_PER_MAP = 32
KEEP_TOTAL = 1024
FORCE_NOTICE = 60   # P1081: from the lobbies' warning to the earliest reload
REWARN = 300        # a warning older than this is given again before the reload
RELOAD_TRIES = 5    # changelevel rounds per lobby before it is left for an operator
ZP_BUDGET = 3       # zonepub's rcon packets per port per 30 s, all its processes; admin.py keeps
                    # 8 (rcon.py), and the engine blocks for 24 h past 15
LOBBY_PORTS = range(27510, 27621)   # AGENT_NOTES: 27510, 27520..27620 (never 27698)
RCON_ENV = '/srv/nvme/surfd/surfd.env'      # SURFD_RCON_PASSWORD, as admin.py reads it
NOTICE = 'Zone update for %s: this map reloads in a few minutes, finish your run'
NOTICE_SHORT = 'Zone update: this map reloads in a few minutes, finish your run'
NOFOLLOW = getattr(os, 'O_NOFOLLOW', 0)
BINARY = getattr(os, 'O_BINARY', 0)
SQL = '''
CREATE TABLE IF NOT EXISTS publications(id INTEGER PRIMARY KEY AUTOINCREMENT, map TEXT NOT NULL,
 sha TEXT NOT NULL, steamid TEXT NOT NULL, at INTEGER NOT NULL, kind TEXT NOT NULL,
 body BLOB, prev TEXT, result TEXT, live INTEGER, force INTEGER, notice INTEGER, warned INTEGER,
 sweepbase TEXT, todo TEXT, tries INTEGER, reload TEXT);
CREATE TABLE IF NOT EXISTS mapseen(map TEXT PRIMARY KEY, at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v INTEGER NOT NULL);
'''
# Added to a store made before P1081 (zonepub.py `init`); every older INSERT names its columns.
COLUMNS = (('force', 'INTEGER'), ('notice', 'INTEGER'), ('warned', 'INTEGER'), ('sweepbase', 'TEXT'),
           ('todo', 'TEXT'), ('tries', 'INTEGER'), ('reload', 'TEXT'))
BUDGET_LOCK = threading.Lock()
# One publish or rollback touches the files at a time: gunicorn's two threads, and
# the `apply`/`rollback` command lines, which are other processes (a flock beside the store).
LOCK = threading.Lock()


@contextmanager
def locked(store):
    with LOCK:
        if fcntl is None:
            yield; return
        with open(Path(store).with_name('publish.lock'), 'a') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try: yield
            finally: fcntl.flock(f.fileno(), fcntl.LOCK_UN)


class PartialPublish(Exception):
    """A write failed and putting back what was already replaced failed too."""


def log(*words):
    print('zonepub:', *words, file=sys.stderr, flush=True)


def who(db, steamid):
    # Keyed per store: an unkeyed SteamID digest is reversible over the SteamID space.
    salt = _meta(db, 'salt')
    if salt is None:
        salt = int.from_bytes(os.urandom(7), 'big')
        db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', ('salt', salt))
    return hmac.new(str(salt).encode(), steamid.encode(), hashlib.sha256).hexdigest()[:12]


def zone_path(directory, name, valid_name):
    if not valid_name(name): raise ValueError('Invalid map name')
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir(): raise ValueError('Unsafe publish destination')
    path = directory / (name + '.json')
    if path.is_symlink(): raise ValueError('Unsafe publish destination')
    return path


def read_file(path, limit):
    try:
        # NONBLOCK: a FIFO put in a publish directory must not hang the lock.
        fd = os.open(path, os.O_RDONLY | NOFOLLOW | BINARY | getattr(os, 'O_NONBLOCK', 0))
    except FileNotFoundError:
        return None
    with os.fdopen(fd, 'rb') as f:
        st = os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_size > limit: raise ValueError('Unexpected publish destination')
        return f.read(limit + 1)


def write_file(path, body):
    # Same-directory temporary, then one rename: a lobby loading the map reads old or new, never half.
    tmp = path.with_name('.%s.zonepub-%s' % (path.name, os.urandom(6).hex()))
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW | BINARY, 0o644)
        with os.fdopen(fd, 'wb') as f:
            f.write(body); f.flush()
            if hasattr(os, 'fchmod'): os.fchmod(f.fileno(), 0o644)   # the unit's UMask is 0077
            os.fsync(f.fileno())
        os.replace(tmp, path)
        if hasattr(os, 'O_DIRECTORY'):
            d = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(d)
            finally: os.close(d)
    finally:
        if os.path.lexists(tmp): os.unlink(tmp)


def put(paths, bodies, limit):
    """Write each body (None removes); on failure put back what was already replaced."""
    done = []
    try:
        for path, body in zip(paths, bodies):
            old = read_file(path, limit)
            if body is None: path.unlink(missing_ok=True)
            else: write_file(path, body)
            done.append((path, old))
    except Exception as first:
        try:
            for path, old in reversed(done):
                if old is None: path.unlink(missing_ok=True)
                else: write_file(path, old)
        except Exception as second:
            raise PartialPublish('%s; restoring failed: %s' % (first, second)) from first
        raise


def key(directory):
    return str(Path(directory).resolve())


def sha(body):
    return hashlib.sha256(body).hexdigest() if body is not None else None


# sweep.pending's predicate: a run or evidence row the sweeper still owes a verdict.
OWED_SQL = """SELECT DISTINCT r.map FROM replays r
 WHERE r.checked = 0 AND r.kind IN ('run', 'evidence')
   AND (SELECT COUNT(*) FROM verdicts v WHERE v.replay_id = r.id AND v.verdict = 'ERROR'
        AND v.at >= MAX(r.submitted, r.recheck_at)) < ?"""


_LOCAL = {}


def is_local(host):
    """An address of this machine: binding to it works only here (cached)."""
    host = host.strip('[]')
    if host in ('127.0.0.1', '::1', 'localhost'): return True
    if host not in _LOCAL:
        try:
            with socket.socket(socket.AF_INET6 if ':' in host else socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.bind((host, 0))
            _LOCAL[host] = True
        except (OSError, ValueError): _LOCAL[host] = False
    return _LOCAL[host]


def lobby_port(addr, local):
    """The rcon port of a heartbeat address, if it is a lobby on this machine; else None.
    surfd stores the heartbeat's source host with the lobby's port, so a lobby elsewhere has
    the same port numbers as ours and must never be sent a command on 127.0.0.1."""
    host, _, port = str(addr or '').rpartition(':')
    if not port.isdigit() or int(port) not in LOBBY_PORTS or not host or not local(host): return None
    return int(port)


def sweep_stamps(path, limit=65536):
    """The completion stamps of the sweeps in the log's tail (sweep.py prints its summary last)."""
    try:
        with open(path, 'rb') as f:
            f.seek(0, os.SEEK_END); f.seek(max(0, f.tell() - limit))
            tail = f.read().decode('utf-8', 'replace')
    except (OSError, TypeError): return []
    return re.findall(r'^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d) sweep: ', tail, re.M)


def lobby_state(surfd_db, sweep_log, now, max_errors=3, local=is_local):
    """What the lobbies have loaded, the maps the sweeper owes a verdict, and when it last
    wrote its log; None when the lobbies cannot all be heard. surfd's lobbies table, not
    /lobbies.json, which leaves out a silent lobby: any row older than two minutes means
    a lobby is down or not heard (mapwatch.live_maps' rule, at surfd's 30 s)."""
    try:
        c = sqlite3.connect(Path(surfd_db).resolve().as_uri() + '?mode=ro', uri=True, timeout=1)
        try:
            rows = c.execute('SELECT map, last_seen, addr FROM lobbies').fetchall()
            owed = {str(r[0]).lower() for r in c.execute(OWED_SQL, (max_errors,))}
            # A lobby told to move to a map is on it already (it may load the old file next).
            asked = c.execute('SELECT a.map, l.addr FROM assignments a LEFT JOIN lobbies l ON l.node = a.node '
                              'WHERE a.asked_at > ?', (now - 300,)).fetchall()
            sent = {str(r[0]).lower() for r in asked}
            # A stage posted is evidence the sweeper indexes from disk later: a sighting.
            posted = {str(r[0]).lower(): r[1] for r in c.execute(
                'SELECT map, MAX(submitted) FROM runs WHERE leg > 0 AND submitted > ? GROUP BY map', (now - 86400,))}
        finally:
            c.close()
    except sqlite3.Error:
        return None
    if not rows or any((r[1] or 0) < now - LOBBY_SILENT for r in rows): return None
    try: swept = os.stat(sweep_log).st_mtime
    except (OSError, TypeError): swept = None
    # P1081: this machine's lobbies on (or told to move to) each map, by their rcon port.
    ports = {}
    for m, addr in [(r[0], r[2]) for r in rows] + asked:
        port = lobby_port(addr, local)
        if port is not None and port not in ports.setdefault(str(m).lower(), []):
            ports[str(m).lower()].append(port)
    return {'maps': {str(r[0]).lower() for r in rows} | sent, 'owed': owed, 'swept': swept, 'posted': posted,
            'ports': ports, 'stamps': sweep_stamps(sweep_log),
            'all_ports': sorted({p for v in ports.values() for p in v})}


def _meta(db, k):
    row = db.execute('SELECT v FROM meta WHERE k=?', (k,)).fetchone()
    return row[0] if row else None


def tick(db, st, now):
    """Record what the lobbies have loaded; a gap in hearing them restarts the watch."""
    if st is None: return
    last = _meta(db, 'watch_last')
    if last is None or now - last > HEAR_GAP:
        db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', ('watch_since', now))
    db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', ('watch_last', now))
    for m in st['maps']:
        db.execute('INSERT OR REPLACE INTO mapseen VALUES(?,?)', (m, now))


def quiet(db, name, st, now):
    """No lobby on the map for QUIET, the lobbies heard all along, nothing of the map owed a
    verdict, and a sweep since it left (the evidence that sweep indexes is then owed above)."""
    if st is None or name in st['maps'] or name in st['owed']: return False
    since = _meta(db, 'watch_since')
    if since is None or now - since < QUIET: return False
    row = db.execute('SELECT at FROM mapseen WHERE map=?', (name,)).fetchone()
    last = max(row[0] if row is not None else since, st.get('posted', {}).get(name, 0))
    if now - last < QUIET: return False
    return st['swept'] is not None and st['swept'] >= last + SWEPT_AFTER


def state(db, name):
    """The newest row that changed the files of `name`: what they must still be."""
    return db.execute("SELECT * FROM publications WHERE map=? AND kind IN ('live','rollback') "
                      "ORDER BY id DESC LIMIT 1", (name,)).fetchone()


def queue(db, name, body, steamid, now, force=False):
    """In the upload's transaction: the pending row's id, or None over the account's hourly rate."""
    n = db.execute("SELECT COUNT(*) FROM publications WHERE steamid=? AND at>? AND kind!='rollback'",
                   (steamid, now - 3600)).fetchone()[0]
    if n >= RATE: return None
    db.execute("UPDATE publications SET kind='superseded' WHERE map=? AND kind='pending'", (name,))
    return db.execute("INSERT INTO publications(map,sha,steamid,at,kind,body,force) VALUES(?,?,?,?,'pending',?,?)",
                      (name, sha(body), steamid, now, body, 1 if force else 0)).lastrowid


def migrate(db):
    have = {r[1] for r in db.execute('PRAGMA table_info(publications)')}
    for column, decl in COLUMNS:
        if column not in have:
            db.execute('ALTER TABLE publications ADD COLUMN %s %s' % (column, decl))


def notice_text(name):
    text = NOTICE % name
    return text if len(text) <= 120 else NOTICE_SHORT     # rcon.py refuses an argument over 128


def force_ready(row, st, now):
    """P1081: warned at least FORCE_NOTICE ago, nothing of the map owed a verdict, and two sweeps
    completed after the grace's base stamp: the second of them started after the grace."""
    if st is None or row['notice'] is None or row['sweepbase'] is None or row['map'] in st['owed']:
        return False
    if now < (row['warned'] or row['notice']) + FORCE_NOTICE: return False
    return len({s for s in st.get('stamps', []) if s > row['sweepbase']}) >= 2


def rcon_password(path=RCON_ENV):
    try:
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                k, _, v = line.strip().partition('=')
                if k.strip() == 'SURFD_RCON_PASSWORD': return v.strip().strip('\'"')
    except OSError: pass
    return ''


def lobby_rcon(port, argv, reply=False):
    """One command to the lobby on 127.0.0.1:port through rcon.py's argument check and budget;
    its printed reply when asked for ("" when none came)."""
    import rcon
    return rcon.Rcon('127.0.0.1', port, rcon_password()).execute(argv, expect_reply=reply)


def budget_take(store, port, now):
    """One of ZP_BUDGET packets per port per 30 s, shared by every zonepub process (the service
    and the apply/rollback command lines) through a locked file beside the store."""
    path = Path(store).with_name('rcon-budget.json')
    with BUDGET_LOCK, open(path, 'a+') as f:
        if fcntl: fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.seek(0)
            try: book = json.loads(f.read() or '{}')
            except ValueError: book = {}
            sent = [t for t in book.get(str(port), []) if isinstance(t, (int, float)) and 0 <= now - t < 30]
            if len(sent) >= ZP_BUDGET: return False
            book[str(port)] = sent + [now]
            f.seek(0); f.truncate(); f.write(json.dumps(book)); f.flush()
            return True
        finally:
            if fcntl: fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def lobby_status(text):
    """(map, seconds since it loaded) from a `status` reply, or None (no reply, or not one)."""
    text = re.sub(r'\^(?:[0-9]|x[0-9A-Fa-f]{3}|b|s|r|a|m)', '', text or '')
    m = re.search(r'^current map\s*:\s*(\S+)', text, re.M)
    u = re.search(r'^map uptime\s*:\s*(.*)$', text, re.M)
    if not m or not u: return None
    units = re.findall(r'(\d+)\s*([dhms]?)', u.group(1))
    if not units: return None
    return m.group(1).lower(), sum(int(n) * {'d': 86400, 'h': 3600, 'm': 60}.get(k, 1) for n, k in units)


def sender(store, rcon_fn, now):
    """send(port, argv, reply) -> the reply text, or None when refused (budget) or failed."""
    def send(port, argv, reply=False):
        if not budget_take(store, port, now):
            log('rcon budget', port, argv[0]); return None
        try: return rcon_fn(port, argv, reply) or ''
        except Exception as e:
            log('rcon', port, argv[0], type(e).__name__); return None
    return send


def warn(send, ports, name):
    """`say` to each port, then `status` as the ack. ({port: answered}, all answered)."""
    said = {}
    for port in sorted(set(ports)):
        ok = send(port, ['say', notice_text(name)]) is not None
        said[port] = ok and lobby_status(send(port, ['status'], True)) is not None
    return said, all(said.values())


def _recover(db, dirs, paths_of, limit, now=None):
    # A row left `applying` by a crash (the file lock makes it never another process's):
    # whatever the files say now; a newer upload of the map supersedes it.
    for row in db.execute("SELECT * FROM publications WHERE kind IN ('applying','rollingback')").fetchall():
        try:
            cur = [sha(read_file(p, limit)) for p in paths_of(row['map'])]
            prev = {k: v for k, v in json.loads(row['prev'])}
            before = [sha(bytes.fromhex(prev[key(d)])) if prev[key(d)] is not None else None for d in dirs]
        except (OSError, ValueError, KeyError) as e:
            kind = 'partial'; log('recover', row['map'], row['sha'][:12], e)
        else:
            newer = db.execute("SELECT 1 FROM publications WHERE map=? AND kind='pending' AND id>?",
                               (row['map'], row['id'])).fetchone()
            if row['kind'] == 'rollingback':
                # result holds what the rollback was putting back, prev what it replaced
                after = {k: v for k, v in json.loads(row['result'])}
                if cur == [after[key(d)] for d in dirs]: kind = 'rollback'
                elif cur == before: kind = 'failed'
                else: kind = 'partial'
            elif all(c == row['sha'] for c in cur): kind = 'live'
            elif cur == before: kind = 'superseded' if newer else 'pending'
            else: kind = 'partial'
        # P1081: a recovered write has no time of its own; the recovery's is the safe side for
        # a force row's reload (a lobby loaded in between is reloaded once more, never skipped).
        db.execute('UPDATE publications SET kind=?, live=COALESCE(live, ?) WHERE id=?',
                   (kind, now if kind in ('live', 'rollback') else None, row['id']))
        log('recovered', row['map'], row['sha'][:12], kind)


def prune(db):
    keep = set(r[0] for r in db.execute(
        "SELECT MAX(id) FROM publications WHERE kind IN ('live','rollback','pending','applying','rollingback','partial') "
        "GROUP BY map, kind"))
    rows = db.execute('SELECT id, map FROM publications ORDER BY id DESC').fetchall()
    seen, drop = {}, []
    for i, (rid, m) in enumerate(rows):
        seen[m] = seen.get(m, 0) + 1
        if rid not in keep and (seen[m] > KEEP_PER_MAP or i >= KEEP_TOTAL): drop.append(rid)
    db.executemany('DELETE FROM publications WHERE id=?', [(r,) for r in drop])


def _note(connect, store, rid, text):
    with connect(store) as db:
        was = db.execute('SELECT reload FROM publications WHERE id=?', (rid,)).fetchone()
        was = (was[0] if was else None) or ''
        db.execute('UPDATE publications SET reload=? WHERE id=?', ((((was + '; ') if was else '') + text)[-2000:], rid))


def _force_pending(connect, store, row, maps, send, now):
    """One step of a pending force publish; True when it may be written now."""
    name = row['map']
    with connect(store) as db:
        cur = db.execute('SELECT kind, notice, warned, sweepbase FROM publications WHERE id=?', (row['id'],)).fetchone()
    if cur is None or cur['kind'] != 'pending' or maps is None: return False
    r = dict(cur); r['map'] = name
    stale = r['warned'] is not None and now - r['warned'] > REWARN
    if r['notice'] is None or (stale and force_ready(r, maps, now)):
        said, ok = warn(send, maps['ports'].get(name, []), name)
        text = 'warn ' + (' '.join('%d:%s' % (p, 'ok' if a else 'no') for p, a in sorted(said.items())) or '-')
        _note(connect, store, row['id'], text)
        if ok:
            with connect(store) as db:
                db.execute('UPDATE publications SET notice=COALESCE(notice, ?), warned=? WHERE id=?', (now, now, row['id']))
            log('warned', name, row['sha'][:12], text)
        else: log('warning not delivered', name, row['sha'][:12], text)
        return False
    if r['sweepbase'] is None:
        if now >= r['notice'] + FORCE_NOTICE:
            with connect(store) as db:
                db.execute('UPDATE publications SET sweepbase=? WHERE id=?', (max(maps.get('stamps') or ['']), row['id']))
        return False
    return force_ready(r, maps, now)


def _force_reload(connect, store, rid, send, now, st):
    """One round of a live force publish's reload: done, or changelevel again (RELOAD_TRIES)."""
    with connect(store) as db:
        row = db.execute('SELECT * FROM publications WHERE id=?', (rid,)).fetchone()
        cur = state(db, row['map']) if row is not None else None
    if row is None: return
    name = row['map']
    written = cur['live'] if cur is not None and cur['live'] else row['live']   # when these files went in
    if row['todo'] is None:         # just written, or recovered after a crash: whoever is on it now
        if st is None: return
        todo = sorted(st['ports'].get(name, []))
    else: todo = json.loads(row['todo'])
    tries = row['tries'] or 0
    left, words = [], []
    for port in todo:
        s = lobby_status(send(port, ['status'], True))
        if s is not None and (s[0] != name or s[1] < now - written):
            words.append('%d:done' % port); continue        # moved off, or loaded since the write
        if tries >= RELOAD_TRIES:
            words.append('%d:GAVE UP' % port); log('reload given up', name, port); continue
        if s is None: words.append('%d:silent' % port)
        else: words.append('%d:changelevel%s' % (port, '' if send(port, ['changelevel', name]) is not None else '-failed'))
        left.append(port)
    with connect(store) as db:
        db.execute('UPDATE publications SET todo=?, tries=? WHERE id=?',
                   (json.dumps(left), tries + (1 if left else 0), rid))
    _note(connect, store, rid, 'reload ' + (' '.join(words) or 'no lobby on it'))
    log('reload', name, row['sha'][:12], ' '.join(words) or 'no lobby on it')


def apply_ready(connect, store, dirs, valid_name, maps_fn, now, limit, rcon_fn=lobby_rcon):
    """Put every pending publish whose map is quiet into the directories. Returns {map: kind}."""
    paths_of = lambda m: [zone_path(d, m, valid_name) for d in dirs]
    done = {}
    if not dirs: return done        # no publish directories: nothing may be marked live
    maps = maps_fn()                # outside the transaction
    send = sender(store, rcon_fn, now)
    with locked(store):
        with connect(store) as db:
            db.execute('BEGIN IMMEDIATE')
            tick(db, maps, now)
            _recover(db, dirs, paths_of, limit, now)
            todo = db.execute("SELECT * FROM publications WHERE kind='pending' ORDER BY id").fetchall()
            for row in todo:
                if now - row['at'] >= 3600 and (now - row['at']) % 3600 < 60:
                    log('still pending', row['map'], row['sha'][:12], 'for', (now - row['at']) // 3600, 'h')
            prune(db)
            reloads = [r['id'] for r in db.execute(
                "SELECT id FROM publications WHERE force=1 AND kind IN ('live','noop') "
                "AND (todo IS NULL OR todo != '[]') AND live > ? ORDER BY id", (now - 86400,))]
        for row in todo:
            name = row['map']
            fresh = None
            if row['force']:
                if not _force_pending(connect, store, row, maps, send, now): continue
                fresh = maps_fn()           # who is on the map at the write, not at the tick's start
                if fresh is None or name in fresh['owed']: continue
            with connect(store) as db:
                db.execute('BEGIN IMMEDIATE')
                again = db.execute('SELECT kind FROM publications WHERE id=?', (row['id'],)).fetchone()
                if again is None or again['kind'] != 'pending': continue
                if not row['force'] and not quiet(db, name, maps, now): continue
                body = bytes(row['body'])
                try:
                    paths = paths_of(name)
                    prev = [read_file(p, limit) for p in paths]
                except (OSError, ValueError) as e:
                    db.execute("UPDATE publications SET kind='failed' WHERE id=?", (row['id'],))
                    log('failed', name, row['sha'][:12], e); done[name] = 'failed'; continue
                if all(p == body for p in prev):
                    db.execute("UPDATE publications SET kind='noop', live=? WHERE id=?", (now, row['id']))
                    done[name] = kind = 'noop'
                else:
                    db.execute("UPDATE publications SET kind='applying', prev=?, result=? WHERE id=?",
                               (json.dumps([[key(d), p.hex() if p is not None else None] for d, p in zip(dirs, prev)]),
                                json.dumps([[key(d), row['sha']] for d in dirs]), row['id']))
                    kind = None
            if kind is None:
                # Committed: the row that undoes this exists before any file changes.
                try:
                    put(paths, [body] * len(paths), limit)
                    kind = 'live'
                except PartialPublish as e:
                    kind = 'partial'; log('partial', name, row['sha'][:12], e)
                except (OSError, ValueError) as e:
                    kind = 'failed'; log('failed', name, row['sha'][:12], e)
                with connect(store) as db:
                    db.execute('UPDATE publications SET kind=?, live=? WHERE id=?', (kind, now, row['id']))
                    if kind == 'live': log('live', name, row['sha'][:12], 'by', who(db, row['steamid']))
                done[name] = kind
            if row['force'] and kind in ('live', 'noop'):
                with connect(store) as db:
                    db.execute('UPDATE publications SET todo=?, tries=0 WHERE id=?',
                               (json.dumps(sorted(fresh['ports'].get(name, []))), row['id']))
                _force_reload(connect, store, row['id'], send, now, fresh)
        for rid in reloads:
            _force_reload(connect, store, rid, send, now, maps)
    return done


def rollback(connect, store, dirs, name, valid_name, maps_fn, now, limit, to_id=None, anyway=False):
    """Put back what publish `to_id` (default the newest live one) replaced. A `partial` row
    (its put-back failed) is repaired only by id and with `anyway`: its files are mixed."""
    paths = [zone_path(d, name, valid_name) for d in dirs]
    st = maps_fn()
    with locked(store), connect(store) as db:
        db.execute('BEGIN IMMEDIATE')
        tick(db, st, now)
        if not anyway and not quiet(db, name, st, now):
            raise ValueError('a lobby has had %s loaded recently, a verdict is owed, or the lobbies or the '
                             'sweeper cannot be heard; try later or pass --anyway' % name)
        cur_state = state(db, name)
        if to_id is None:
            target = cur_state if cur_state is not None and cur_state['kind'] == 'live' else None
        else:
            target = db.execute("SELECT * FROM publications WHERE id=? AND map=? AND kind IN ('live','partial')",
                                (to_id, name)).fetchone()
            if target is not None and target['kind'] == 'partial' and not anyway:
                raise ValueError('publish %d is partial: repair it with --anyway' % to_id)
        if target is None: raise ValueError('No live publish of this map to roll back')
        recorded = {k: bytes.fromhex(v) if v is not None else None for k, v in json.loads(target['prev'])}
        keys = [key(d) for d in dirs]
        if sorted(keys) != sorted(recorded): raise ValueError('Publish directories differ from the recorded publish')
        cur = [read_file(p, limit) for p in paths]
        if target['kind'] != 'partial':
            want = {k: v for k, v in json.loads(cur_state['result'])}
            for k, p, body in zip(keys, paths, cur):
                if sha(body) != want.get(k):
                    raise ValueError('%s changed since the last publish or rollback; nothing rolled back' % p)
        prev = [recorded[k] for k in keys]
        # A rollback is the map's newest word: a publish still waiting must not undo it.
        db.execute("UPDATE publications SET kind='superseded' WHERE map=? AND kind='pending'", (name,))
        rid = db.execute("INSERT INTO publications(map,sha,steamid,at,kind,prev,result,live) "
                         "VALUES(?,?,?,?,'rollingback',?,?,?)",
                         (name, target['sha'], target['steamid'], now,
                          json.dumps([[k, b.hex() if b is not None else None] for k, b in zip(keys, cur)]),
                          json.dumps([[k, sha(b)] for k, b in zip(keys, prev)]), now)).lastrowid
        db.commit()                 # the row first, as a publish does (_recover finishes it after a crash)
        try:
            put(paths, prev, limit)
        except (OSError, ValueError, PartialPublish) as e:     # anything else stays for _recover
            db.execute('UPDATE publications SET kind=? WHERE id=?',
                       ('partial' if isinstance(e, PartialPublish) else 'failed', rid)); db.commit()
            raise
        db.execute("UPDATE publications SET kind='rollback' WHERE id=?", (rid,)); db.commit()
    log('rollback', name, 'of', target['sha'][:12])
    return [sha(p) for p in prev]
