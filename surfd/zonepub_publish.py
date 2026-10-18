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
"""
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
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
NOFOLLOW = getattr(os, 'O_NOFOLLOW', 0)
BINARY = getattr(os, 'O_BINARY', 0)
SQL = '''
CREATE TABLE IF NOT EXISTS publications(id INTEGER PRIMARY KEY AUTOINCREMENT, map TEXT NOT NULL,
 sha TEXT NOT NULL, steamid TEXT NOT NULL, at INTEGER NOT NULL, kind TEXT NOT NULL,
 body BLOB, prev TEXT, result TEXT, live INTEGER);
CREATE TABLE IF NOT EXISTS mapseen(map TEXT PRIMARY KEY, at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v INTEGER NOT NULL);
'''
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


def lobby_state(surfd_db, sweep_log, now, max_errors=3):
    """What the lobbies have loaded, the maps the sweeper owes a verdict, and when it last
    wrote its log; None when the lobbies cannot all be heard. surfd's lobbies table, not
    /lobbies.json, which leaves out a silent lobby: any row older than two minutes means
    a lobby is down or not heard (mapwatch.live_maps' rule, at surfd's 30 s)."""
    try:
        c = sqlite3.connect(Path(surfd_db).resolve().as_uri() + '?mode=ro', uri=True, timeout=1)
        try:
            rows = c.execute('SELECT map, last_seen FROM lobbies').fetchall()
            owed = {str(r[0]).lower() for r in c.execute(OWED_SQL, (max_errors,))}
            # A lobby told to move to a map is on it already (it may load the old file next).
            sent = {str(r[0]).lower() for r in c.execute('SELECT map FROM assignments WHERE asked_at > ?',
                                                          (now - 300,))}
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
    return {'maps': {str(r[0]).lower() for r in rows} | sent, 'owed': owed, 'swept': swept, 'posted': posted}


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


def queue(db, name, body, steamid, now):
    """In the upload's transaction: the pending row's id, or None over the account's hourly rate."""
    n = db.execute("SELECT COUNT(*) FROM publications WHERE steamid=? AND at>? AND kind!='rollback'",
                   (steamid, now - 3600)).fetchone()[0]
    if n >= RATE: return None
    db.execute("UPDATE publications SET kind='superseded' WHERE map=? AND kind='pending'", (name,))
    return db.execute("INSERT INTO publications(map,sha,steamid,at,kind,body) VALUES(?,?,?,?,'pending',?)",
                      (name, sha(body), steamid, now, body)).lastrowid


def _recover(db, dirs, paths_of, limit):
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
        db.execute('UPDATE publications SET kind=? WHERE id=?', (kind, row['id']))
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


def apply_ready(connect, store, dirs, valid_name, maps_fn, now, limit):
    """Put every pending publish whose map is quiet into the directories. Returns {map: kind}."""
    paths_of = lambda m: [zone_path(d, m, valid_name) for d in dirs]
    done = {}
    if not dirs: return done        # no publish directories: nothing may be marked live
    maps = maps_fn()                # outside the transaction
    with locked(store):
        with connect(store) as db:
            db.execute('BEGIN IMMEDIATE')
            tick(db, maps, now)
            _recover(db, dirs, paths_of, limit)
            todo = db.execute("SELECT * FROM publications WHERE kind='pending' ORDER BY id").fetchall()
            for row in todo:
                if now - row['at'] >= 3600 and (now - row['at']) % 3600 < 60:
                    log('still pending', row['map'], row['sha'][:12], 'for', (now - row['at']) // 3600, 'h')
            prune(db)
        for row in todo:
            name = row['map']
            with connect(store) as db:
                db.execute('BEGIN IMMEDIATE')
                again = db.execute('SELECT kind FROM publications WHERE id=?', (row['id'],)).fetchone()
                if again is None or again['kind'] != 'pending' or not quiet(db, name, maps, now): continue
                body = bytes(row['body'])
                try:
                    paths = paths_of(name)
                    prev = [read_file(p, limit) for p in paths]
                except (OSError, ValueError) as e:
                    db.execute("UPDATE publications SET kind='failed' WHERE id=?", (row['id'],))
                    log('failed', name, row['sha'][:12], e); done[name] = 'failed'; continue
                if all(p == body for p in prev):
                    db.execute("UPDATE publications SET kind='noop', live=? WHERE id=?", (now, row['id']))
                    done[name] = 'noop'; continue
                db.execute("UPDATE publications SET kind='applying', prev=?, result=? WHERE id=?",
                           (json.dumps([[key(d), p.hex() if p is not None else None] for d, p in zip(dirs, prev)]),
                            json.dumps([[key(d), row['sha']] for d in dirs]), row['id']))
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
