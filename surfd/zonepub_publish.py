"""P815: what an accepted admin upload does to the publish directories, and when.

An upload is queued (`publications`, kind pending) and goes live only when no lobby
has had its map loaded for QUIET seconds, with every lobby heard throughout, nothing
of the map owed a verdict and a sweep since: a lobby on the map keeps its table
until its next map load, but `retry` reloads it (a run would change zones
mid-attempt), and the sweeper verifies a finished run against the files as they are
then. mapwatch.py holds Momentum's zones on the first condition alone.

Kinds: pending, applying (files being written; recovered at the next tick), live,
noop (already live), superseded, failed (files put back), partial (put back failed:
an operator's rollback), rollback; P1081 adds expired, live-partial and noop-partial.
`result` is each directory's sha after a live or rollback row, which is what the files
must still be for a later rollback.

P1081 `force` (the admin chose "reload now"), pending:
  0. every lobby on or assigned to the map must be one of ours (lobby_port: a cfg sv_port at
     SURFD_PUBLIC_HOST or a literal address of this machine); otherwise it holds (`hold` says
     why). An empty target set counts only when no lobby is on the map at all.
  1. warn each target (`say`, then `status` as the ack: say prints nothing to rcon). The ack is
     weak -- it shows the lobby answered, not that a player read the line. All must answer or
     the round is retried; unanswered for WARN_EXPIRE, the row is `expired` (nothing installed).
  2. after FORCE_NOTICE, record the newest sweep completion stamp (`sweepbase`; none readable:
     not ready); ready once two newer completions are in the log (sweeps cannot overlap,
     flock -n, so the second STARTED after the grace) and nothing of the map is owed a verdict.
     A lobby whose own warning is older than REWARN is told again first.
  3. at the write the targets are read again; a lobby not yet warned is warned and waited for,
     and every target must answer `status` just before put(). Pending past FORCE_EXPIRE: expired.
Then, live: one round per ROUND_GAP reads each lobby in `todo`, and any the table now shows on
the map, with `serverinfo`. Done means its `zonecrc` (the hash of the table it runs, sv_zones.qc)
equals the crc the client stated for these bytes (`crc`, bound to the nonce) -- and, unless its
read before the write showed this map with another crc (_mode), also a load after the write: a
lobby found later, re-armed or recovered, or one whose crc cannot tell old from new, needs both
(no crc stated, legacy: the load time alone). The load time is its uptime against a MONO stamp
taken after put() (_since); in another boot it cannot be measured, and a mode-1 lobby is held
("cannot tell after restart") until a re-arm stamps again. A lobby that loaded after the write
and runs another table (a shadowing file, a crc that never matches) is left, never changelevelled
again.
Otherwise `changelevel`; one not warned for this reload is told first and given a minute. A try
is spent only on a changelevel sent; RELOAD_TRIES, SILENT_ROUNDS without an answer, or
RELOAD_EXPIRE leave it too. Left lobbies are `partial`, still read, cleared if they later run the
table; a lobby's state outlives its moves off and back. A newer write of the map (a rollback,
another publish, a partial one) ends the watch. The row ends (`done_at`) only in a round whose lobby table was
read, after WATCH_ROUNDS such rounds, with every lobby done, moved off or left (`live-partial`);
`zonepub.py reload` re-arms it with its own clock (`rearmed`). Bytes already live reload nobody.
A crash between the write and the reload recovers as live, which starts the reload. Never past
an owed verdict; evidence posted after the warning and not yet indexed meets the new zones.
"""
from contextlib import contextmanager
import hashlib
import hmac
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import socket
import stat
import sys
import sqlite3
import threading
import time
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
WARN_EXPIRE = 900   # a first warning nobody could be given by then: expired, nothing installed
FORCE_EXPIRE = 3600 # a force publish still pending by then: expired
ROUND_GAP = 55      # one reload round per row per tick, however often apply() is called
RELOAD_TRIES = 5    # changelevels sent to one lobby before it is left for an operator
RELOAD_EXPIRE = 1800
SILENT_ROUNDS = 4   # rounds a lobby may not answer after the write before it is an operator alarm
WATCH_ROUNDS = 2    # readable lobby-table rounds after the write (or re-arm) before a reload may end
ZP_BUDGET = 4       # zonepub's rcon packets per port per 30 s, all its processes (a lobby's write
                    # tick: serverinfo before put(), then serverinfo, status, changelevel);
                    # admin.py keeps 8 (rcon.py), and the engine blocks for 24 h past 15
LOBBY_CFG_DIR = '/srv/nvme/ftesurf-server/game/ftesurf/cfg/lobby'   # admin.py's, sv_port per lobby
RCON_ENV = '/srv/nvme/surfd/surfd.env'      # SURFD_RCON_PASSWORD and SURFD_PUBLIC_HOST
NOTICE = 'Zone update for %s: this map reloads in a few minutes, finish your run'
NOTICE_SHORT = 'Zone update: this map reloads in a few minutes, finish your run'
CLOCK = time.time   # wall moments: `live`, warnings, expiries (tests set it)
MONO = time.monotonic   # the rcon budget, ROUND_GAP and the load-time test: a clock step moves none


def _boot_id():
    try:
        with open('/proc/sys/kernel/random/boot_id') as f: return f.read().strip()
    except OSError: return 'no-boot-id'


BOOT = _boot_id     # MONO restarts with each boot, so a MONO stamp is good only within its boot
NOFOLLOW = getattr(os, 'O_NOFOLLOW', 0)
BINARY = getattr(os, 'O_BINARY', 0)
SQL = '''
CREATE TABLE IF NOT EXISTS publications(id INTEGER PRIMARY KEY AUTOINCREMENT, map TEXT NOT NULL,
 sha TEXT NOT NULL, steamid TEXT NOT NULL, at INTEGER NOT NULL, kind TEXT NOT NULL,
 body BLOB, prev TEXT, result TEXT, live INTEGER, force INTEGER, notice INTEGER, warned INTEGER,
 warned_ports TEXT, sweepbase TEXT, todo TEXT, round INTEGER, partial TEXT, hold TEXT, reload TEXT,
 rearmed INTEGER, done_at INTEGER, crc TEXT, watch INTEGER, since_mono REAL, since_boot TEXT);
CREATE TABLE IF NOT EXISTS mapseen(map TEXT PRIMARY KEY, at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v INTEGER NOT NULL);
'''
# Added to a store made before P1081 (zonepub.py `init`); every older INSERT names its columns.
COLUMNS = (('force', 'INTEGER'), ('notice', 'INTEGER'), ('warned', 'INTEGER'), ('warned_ports', 'TEXT'),
           ('sweepbase', 'TEXT'), ('todo', 'TEXT'), ('round', 'INTEGER'), ('partial', 'TEXT'),
           ('hold', 'TEXT'), ('reload', 'TEXT'), ('rearmed', 'INTEGER'), ('done_at', 'INTEGER'),
           ('crc', 'TEXT'), ('watch', 'INTEGER'), ('since_mono', 'REAL'), ('since_boot', 'TEXT'))
LIVE_KINDS = ('live', 'live-partial', 'rollback')      # rows whose files are the map's current ones
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


def same_zones(a, b):
    """The same zone JSON: whitespace, key order and number spelling (64, 64.0) aside; False when
    either is missing or cannot be read."""
    canon = lambda body: json.dumps(json.loads(body, parse_int=float), sort_keys=True, separators=(',', ':'))
    if a is None or b is None: return False
    try: return canon(a) == canon(b)
    except (ValueError, UnicodeDecodeError, RecursionError): return False


def key(directory):
    return str(Path(directory).resolve())


def sha(body):
    return hashlib.sha256(body).hexdigest() if body is not None else None


# sweep.pending's predicate: a run or evidence row the sweeper still owes a verdict.
OWED_SQL = """SELECT DISTINCT r.map FROM replays r
 WHERE r.checked = 0 AND r.kind IN ('run', 'evidence')
   AND (SELECT COUNT(*) FROM verdicts v WHERE v.replay_id = r.id AND v.verdict = 'ERROR'
        AND v.at >= MAX(r.submitted, r.recheck_at)) < ?"""


def env_value(name, path=RCON_ENV):
    """One NAME=value of surfd's env file, as admin.py's _from_env_file reads it ("" if absent)."""
    try:
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                k, _, v = line.strip().partition('=')
                if k.strip() == name: return v.strip().strip('\'"')
    except OSError: pass
    return ''


def rcon_password(path=RCON_ENV): return env_value('SURFD_RCON_PASSWORD', path)


def public_host(path=RCON_ENV):
    """The name surfd writes into a trusted lobby's address (surfd.py PUBLIC_HOST)."""
    return env_value('SURFD_PUBLIC_HOST', path).lower()


_PORTS = {}


def our_ports(cfgdir=LOBBY_CFG_DIR, ttl=60):
    """Every lobby's sv_port from its lobby<N>.cfg (admin.py discover_lobbies), cached a minute;
    None, not cached, when the directory or a cfg cannot be read (lobby_state: unreadable)."""
    hit = _PORTS.get(cfgdir)
    if hit and time.monotonic() - hit[0] < ttl: return hit[1]
    found = set()
    try: names = os.listdir(cfgdir)
    except OSError: return None
    for n in names:
        if not re.fullmatch(r'lobby\d+\.cfg', n): continue
        try:
            with open(os.path.join(cfgdir, n), encoding='utf-8', errors='replace') as fh:
                for line in fh:
                    m = re.match(r'\s*set\s+sv_port\s+"?(\d+)', line)
                    if m: found.add(int(m.group(1))); break
        except OSError: return None
    _PORTS[cfgdir] = (time.monotonic(), frozenset(found))
    return _PORTS[cfgdir][1]


def literal_ip(host):
    """The address a host string spells literally, or None: names are never looked up here."""
    try: return ipaddress.ip_address(str(host).strip('[]'))
    except ValueError: return None


_SELF = {}


def is_self(host):
    """A literal address of this machine (binding to it works only here); cached, bounded."""
    ip = literal_ip(host)
    if ip is None: return False
    if ip.is_loopback: return True
    k = str(ip)
    if k not in _SELF:
        if len(_SELF) >= 64: _SELF.clear()
        try:
            with socket.socket(socket.AF_INET6 if ip.version == 6 else socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.bind((k, 0))
            _SELF[k] = True
        except OSError: _SELF[k] = False
    return _SELF[k]


def lobby_port(addr, ours, public, local=is_self):
    """The rcon port of a heartbeat address if it is one of our lobbies, else None. surfd writes
    a trusted lobby as SURFD_PUBLIC_HOST:port and anything else with its source host, so a lobby
    elsewhere can share our port numbers and must never be sent a command on 127.0.0.1."""
    host, _, port = str(addr or '').rpartition(':')
    if not port.isdigit() or int(port) not in ours or not host: return None
    if (public and host.lower() == public) or local(host): return int(port)
    return None


def sweep_stamps(path, limit=65536):
    """The completion stamps of the sweeps in the log's tail (sweep.py prints its summary last)."""
    try:
        with open(path, 'rb') as f:
            f.seek(0, os.SEEK_END); f.seek(max(0, f.tell() - limit))
            tail = f.read().decode('utf-8', 'replace')
    except (OSError, TypeError): return []
    return re.findall(r'^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d) sweep: ', tail, re.M)


def lobby_state(surfd_db, sweep_log, now, max_errors=3, local=is_self, ours=None, public=None):
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
    # P1081: our lobbies on (or told to move to) each map by rcon port, and how many there are not.
    ours = our_ports() if ours is None else ours
    if ours is None: return None
    public = public_host() if public is None else public
    ports, unresolved = {}, {}
    for m, addr in [(r[0], r[2]) for r in rows] + asked:
        m = str(m).lower()
        port = lobby_port(addr, ours, public, local)
        if port is None: unresolved[m] = unresolved.get(m, 0) + 1
        elif port not in ports.setdefault(m, []): ports[m].append(port)
    return {'maps': {str(r[0]).lower() for r in rows} | sent, 'owed': owed, 'swept': swept, 'posted': posted,
            'ports': ports, 'unresolved': unresolved, 'stamps': sweep_stamps(sweep_log)}


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
    return db.execute("SELECT * FROM publications WHERE map=? AND kind IN %s ORDER BY id DESC LIMIT 1"
                      % (LIVE_KINDS,), (name,)).fetchone()


def queue(db, name, body, steamid, now, force=False, crc=None):
    """In the upload's transaction: the pending row's id, or None over the account's hourly rate."""
    n = db.execute("SELECT COUNT(*) FROM publications WHERE steamid=? AND at>? AND kind!='rollback'",
                   (steamid, now - 3600)).fetchone()[0]
    if n >= RATE: return None
    db.execute("UPDATE publications SET kind='superseded' WHERE map=? AND kind='pending'", (name,))
    return db.execute("INSERT INTO publications(map,sha,steamid,at,kind,body,force,crc) VALUES(?,?,?,?,'pending',?,?,?)",
                      (name, sha(body), steamid, now, body, 1 if force else 0, crc)).lastrowid


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


def lobby_rcon(port, argv, reply=False):
    """One command to the lobby on 127.0.0.1:port through rcon.py's argument check and budget;
    its printed reply when asked for ("" when none came)."""
    import rcon
    return rcon.Rcon('127.0.0.1', port, rcon_password()).execute(argv, expect_reply=reply)


def budget_take(store, port):
    """One of ZP_BUDGET packets per port per 30 s, shared by every zonepub process (the service
    and the apply/rollback command lines) through a locked file beside the store. The moment is
    taken inside the lock on the monotonic clock (system-wide); an entry up to 30 s newer than it is
    kept, one further ahead is from before a reboot (the clock restarts) and dropped."""
    path = Path(store).with_name('rcon-budget.json')
    with BUDGET_LOCK, open(path, 'a+') as f:
        if fcntl: fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            now = MONO()
            f.seek(0)
            try: book = json.loads(f.read() or '{}')
            except ValueError: book = {}
            sent = [t for t in book.get(str(port), []) if isinstance(t, (int, float)) and now - 30 < t <= now + 30]
            if len(sent) >= ZP_BUDGET: return False
            book[str(port)] = sent + [now]
            f.seek(0); f.truncate(); f.write(json.dumps(book)); f.flush()
            return True
        finally:
            if fcntl: fcntl.flock(f.fileno(), fcntl.LOCK_UN)


COLOUR = r'\^(?:[0-9]|x[0-9A-Fa-f]{3}|b|s|r|a|m)'


def lobby_status(text):
    """(map, seconds since it loaded) from a `status` reply, or None (no reply, or not one)."""
    text = re.sub(COLOUR, '', text or '')
    m = re.search(r'^current map\s*:\s*(\S+)', text, re.M)
    u = re.search(r'^map uptime\s*:\s*(.*)$', text, re.M)
    if not m or not u: return None
    units = re.findall(r'(\d+)\s*([dhms]?)', u.group(1))
    if not units: return None
    return m.group(1).lower(), sum(int(n) * {'d': 86400, 'h': 3600, 'm': 60}.get(k, 1) for n, k in units)


def lobby_info(text):
    """serverinfo's keys from an rcon `serverinfo` reply (InfoBuf_Print: "key value" lines, colour
    codes around them); {} when none came or it is not one. The lobby's own `zonecrc`
    (sv_zones.qc) is the direct statement of the table it runs."""
    out = {}
    for line in re.sub(COLOUR, '', text or '').splitlines():
        m = re.match(r'(\S+)\s+(.*)$', line.strip())
        if m: out[m.group(1).lower()] = m.group(2).strip()
    return out if out.get('map') else {}


def sender(store, rcon_fn):
    """send(port, argv, reply) -> the reply text, or None when refused (budget) or failed."""
    def send(port, argv, reply=False):
        if not budget_take(store, port):
            log('rcon budget', port, argv[0]); return None
        try: return rcon_fn(port, argv, reply) or ''
        except Exception as e:
            log('rcon', port, argv[0], type(e).__name__); return None
    return send


def warn(send, ports, name):
    """`say` to each port, then `serverinfo` as the ack. ({port: answered}, all answered); an empty
    set is not an answer -- the caller decides whether nobody being on the map is fine."""
    said = {}
    for port in sorted(set(ports)):
        ok = send(port, ['say', notice_text(name)]) is not None
        said[port] = ok and bool(lobby_info(send(port, ['serverinfo'], True)))
    return said, bool(said) and all(said.values())


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
        # P1081: a recovered write has no time of its own; the recovery's, after the files are as
        # they are, is the safe side (a lobby loaded in between is reloaded once more, never skipped).
        since = _since() if kind in ('live', 'rollback') else (row['since_mono'], row['since_boot'])
        db.execute('UPDATE publications SET kind=?, live=?, since_mono=?, since_boot=? WHERE id=?',
                   (kind, math.ceil(CLOCK()) if kind in ('live', 'rollback') else row['live']) + since + (row['id'],))
        log('recovered', row['map'], row['sha'][:12], kind)


def prune(db):
    keep = set(r[0] for r in db.execute(
        "SELECT MAX(id) FROM publications WHERE kind IN ('live','live-partial','rollback','pending','applying',"
        "'rollingback','partial') GROUP BY map, kind"))
    rows = db.execute('SELECT id, map FROM publications ORDER BY id DESC').fetchall()
    seen, drop = {}, []
    for i, (rid, m) in enumerate(rows):
        seen[m] = seen.get(m, 0) + 1
        if rid not in keep and (seen[m] > KEEP_PER_MAP or i >= KEEP_TOTAL): drop.append(rid)
    db.executemany('DELETE FROM publications WHERE id=?', [(r,) for r in drop])


def _set(connect, store, rid, **cols):
    with connect(store) as db:
        db.execute('UPDATE publications SET %s WHERE id=?' % ', '.join('%s=?' % c for c in cols),
                   tuple(cols.values()) + (rid,))


def _note(connect, store, rid, text):
    with connect(store) as db:
        was = db.execute('SELECT reload FROM publications WHERE id=?', (rid,)).fetchone()
        was = (was[0] if was else None) or ''
        db.execute('UPDATE publications SET reload=? WHERE id=?', ((((was + '; ') if was else '') + text)[-2000:], rid))


def _hold(connect, store, row, why):
    """Why a pending force row waits, said once per change of reason."""
    with connect(store) as db:
        was = db.execute('SELECT hold FROM publications WHERE id=?', (row['id'],)).fetchone()[0]
        if was != why:
            db.execute('UPDATE publications SET hold=? WHERE id=?', (why, row['id']))
            log('holding', row['map'], row['sha'][:12], why)


def _unreachable(st, name):
    """Why the map's lobbies cannot all be told and reloaded, or ''. Nobody on it is fine."""
    if st is None: return 'the lobbies cannot all be heard'
    if name not in st['maps']: return ''
    n = st.get('unresolved', {}).get(name, 0)
    if n or not st['ports'].get(name):
        return '%d lobby(s) on or sent to %s are not ours by address and port' % (max(n, 1), name)
    return ''


def _told(row):
    """{port: when it was last warned}; any earlier P1081 shape (a list of ports) is read too."""
    try: raw = json.loads(row['warned_ports'] or '{}')
    except ValueError: raw = {}
    if isinstance(raw, dict):
        return {int(p): t for p, t in raw.items() if str(p).isdigit() and isinstance(t, (int, float))}
    return {int(p): row['warned'] or 0 for p in raw if isinstance(p, int) or str(p).isdigit()}


def _todo(raw):
    """{port: [tries, silent, mode, gave, where]}, from any P1081 shape too (a list of ports,
    {port: tries}, {port: [tries, silent]}, round 4's [tries, silent, blind, gave]).
    mode 0: its crc before the write was not the new one, so the crc alone confirms it; 1: nothing
    tells old from new by crc (it already matched, nothing was read before the write -- found
    later, re-armed, recovered -- or no crc is stated), so it must also have loaded after the write.
    gave 1: left for an operator; 2: loaded after the write and runs another table. Both are still
    read, never changelevelled. where 0: on the map; 1: done; 2: moved off (state kept if it returns)."""
    try: v = json.loads(raw or '{}')
    except ValueError: v = {}
    if isinstance(v, list): v = {p: 0 for p in v}
    out = {}
    for p, t in (v.items() if isinstance(v, dict) else []):
        if not str(p).isdigit(): continue
        t = [int(x) if isinstance(x, (int, float)) else 0 for x in (t if isinstance(t, list) else [t])][:5]
        if len(t) < 3: t = (t + [0, 0])[:2] + [1]          # no mode recorded: both checks
        out[int(p)] = (t + [0, 0])[:5]
    return out


def _warn_round(connect, store, row, send, ports, name, now):
    said, ok = warn(send, ports, name)
    _note(connect, store, row['id'], 'warn ' + ' '.join('%d:%s' % (p, 'ok' if a else 'no')
                                                        for p, a in sorted(said.items())))
    if ok:
        with connect(store) as db:
            told = _told(db.execute('SELECT warned, warned_ports FROM publications WHERE id=?',
                                    (row['id'],)).fetchone())
        told.update({int(p): now for p in ports})
        _set(connect, store, row['id'], warned=now, hold=None,
             warned_ports=json.dumps({str(p): t for p, t in sorted(told.items())}))
        log('warned', name, row['sha'][:12], sorted(ports))
    else:
        _hold(connect, store, row, 'not every lobby on %s answered the warning: %s'
              % (name, ' '.join(str(p) for p, a in sorted(said.items()) if not a)))
    return ok


def _force_pending(connect, store, row, maps, send, now):
    """One step of a pending force publish; True when it may be written now."""
    name = row['map']
    with connect(store) as db:
        cur = db.execute('SELECT * FROM publications WHERE id=?', (row['id'],)).fetchone()
    if cur is None or cur['kind'] != 'pending': return False
    expired = (now - cur['at'] > FORCE_EXPIRE or (cur['notice'] is None and now - cur['at'] > WARN_EXPIRE))
    if expired:
        _set(connect, store, row['id'], kind='expired')
        _note(connect, store, row['id'], 'expired, nothing installed: ' + (cur['hold'] or 'not ready in time'))
        log('expired', name, row['sha'][:12], cur['hold'] or '')
        return False
    why = _unreachable(maps, name)
    if why: _hold(connect, store, row, why); return False
    targets = maps['ports'].get(name, [])
    if cur['notice'] is None:
        if not targets:                         # nobody on the map: nobody to tell
            _set(connect, store, row['id'], notice=now, warned=now, warned_ports='{}', hold=None)
            _note(connect, store, row['id'], 'warn nobody on it')
        elif _warn_round(connect, store, row, send, targets, name, now):
            _set(connect, store, row['id'], notice=now)
        return False
    r = dict(cur)
    if r['sweepbase'] is None:
        if now >= r['notice'] + FORCE_NOTICE:
            stamps = maps.get('stamps') or []
            if stamps: _set(connect, store, row['id'], sweepbase=max(stamps))
            else: _hold(connect, store, row, 'the sweep log has no completion line to wait from')   # fail closed
        return False
    if not force_ready(r, maps, now):
        _hold(connect, store, row, 'a verdict on %s is owed' % name if name in maps['owed']
              else 'waiting for the warning minute and two sweeps')
        return False
    told = _told(cur)
    stale = [p for p in targets if p in told and now - told[p] > REWARN]
    if stale:                                   # each lobby's own warning: told again, then a minute
        _warn_round(connect, store, row, send, stale, name, now)
        return False
    return True


def _expected(db, name):
    """What the map's current files hash to, as stated by the row that put them there (a rollback
    carries the crc of the bytes it restored); None: not stated."""
    cur = state(db, name)
    return ((cur['crc'] or '').lower() or None) if cur is not None else None


def _newer_write(db, name, rid):
    """A row newer than `rid` that changed the map's files (a rollback, another publish, or a
    partial one: the files are mixed), or None."""
    return db.execute('SELECT id, kind FROM publications WHERE map=? AND id>? AND kind IN %s '
                      'ORDER BY id DESC LIMIT 1' % (LIVE_KINDS + ('partial',),), (name, rid)).fetchone()


def _since():
    """(MONO, boot) a lobby's load must come after: one second past now, as `status` uptime is whole
    seconds. Stamped after put(), at a recovery (later than the write: a load in between is reloaded
    again) and at a re-arm."""
    return MONO() + 1, BOOT()


def _mode(info, name, exp):
    """0 when the lobby's read before the write showed THIS map with a crc that is not the new one
    (the old table), so the crc alone confirms it; else 1 (crc and load time)."""
    crc = (info.get('zonecrc') or '').lower()
    return 0 if exp and (info.get('map') or '').lower() == name and crc and crc != exp else 1


def _force_reload(connect, store, rid, send, now, st):
    """One round of a live force publish's reload, at most one per ROUND_GAP. Per lobby (_todo's
    entry): done when its serverinfo `zonecrc` is the current files' crc and, in mode 1, it loaded
    after the row's MONO stamp (`since_*`); one that loaded after it and runs another table is left,
    never changelevelled again. Where the stamp is from another boot the load time cannot be
    measured: mode 0 goes by the crc alone (never "another table"), mode 1 is held, "cannot tell
    after restart", until a re-arm stamps again. The lobby table is read again each round. A newer
    write of the map ends the watch; otherwise the row ends only in a round whose table was read,
    after WATCH_ROUNDS such rounds, with every lobby done, moved off or left (`live-partial`)."""
    with connect(store) as db:
        row = db.execute('SELECT * FROM publications WHERE id=?', (rid,)).fetchone()
        if row is None: return
        exp = _expected(db, row['map'])
        newer = _newer_write(db, row['map'], rid)
    if newer is not None:
        # Its crc and lobbies are no longer this row's to chase (a rollback says nothing to them).
        _set(connect, store, rid, done_at=now)
        _note(connect, store, rid, 'reload ended: %s %d changed the files since' % (newer['kind'], newer['id']))
        log('reload ended', row['map'], row['sha'][:12], newer['kind'], newer['id'])
        return
    mono = MONO()
    if row['round'] is not None and 0 <= mono - row['round'] < ROUND_GAP: return
    name = row['map']
    since = row['since_mono']
    measurable = since is not None and row['since_boot'] == BOOT() and mono >= since - 1
    base = row['rearmed'] or row['live'] or now
    todo, told = _todo(row['todo']), _told(row)
    readable = st is not None
    for p in (st['ports'].get(name, []) if readable else []):
        e = todo.setdefault(int(p), [0, 0, 1, 0, 0])
        if e[4] == 2: e[4] = 0                          # back on the map: its tries and verdict kept
    expired = now - base > RELOAD_EXPIRE
    words = []
    for p, e in sorted(todo.items()):
        tries, silent, mode, gave, where = e
        if where: continue
        info = lobby_info(send(p, ['serverinfo'], True))
        if not info:
            e[1] = silent = silent + 1                  # no answer: no try spent
            if not gave and (silent >= SILENT_ROUNDS or expired):
                e[3] = 1; words.append('%d:GAVE UP (silent)' % p); log('reload given up', name, p, 'silent')
            else: words.append('%d:silent' % p)
            continue
        e[1] = 0
        if info['map'].lower() != name: e[4] = 2; words.append('%d:moved off' % p); continue
        crc_ok = bool(exp) and info.get('zonecrc', '').lower() == exp
        if crc_ok and mode == 0:
            e[3], e[4] = 0, 1; words.append('%d:done' % p); continue
        if mode == 1 and not measurable:
            if gave != 3: log('reload held', name, p, 'cannot tell after restart')
            e[3] = 3; words.append('%d:cannot tell after restart' % p); continue
        after = False
        if measurable:
            s = lobby_status(send(p, ['status'], True))
            after = s is not None and s[0] == name and s[1] < MONO() - since
        if after and (crc_ok or not exp):
            e[3], e[4] = 0, 1
            words.append('%d:done (%s)' % (p, 'crc and load time' if exp else 'load time; no crc stated'))
            continue
        if after:                                       # a shadowing file, or a crc that never matches
            if gave != 2: log('reload left', name, p, 'loaded another table')
            e[3] = 2; words.append('%d:loaded another table' % p); continue
        if gave: words.append('%d:still old' % p); continue
        if tries >= RELOAD_TRIES or expired:
            e[3] = 1; words.append('%d:GAVE UP' % p); log('reload given up', name, p); continue
        if p not in told or (row['rearmed'] and told[p] < row['rearmed']):
            # Not warned for this reload (found after the write, or re-armed): told, then a minute.
            if send(p, ['say', notice_text(name)]) is not None: told[p] = now
            words.append('%d:warned' % p); continue
        if now - told[p] < FORCE_NOTICE: words.append('%d:waiting' % p); continue
        sent = send(p, ['changelevel', name]) is not None
        e[0] = tries + (1 if sent else 0)
        words.append('%d:changelevel%s' % (p, '' if sent else '-failed'))
    watch = (row['watch'] or 0) + (1 if readable else 0)
    gave_ports = sorted(p for p, e in todo.items() if e[3])
    cols = dict(todo=json.dumps({str(p): e for p, e in sorted(todo.items())}), round=mono, watch=watch,
                partial=json.dumps(gave_ports) if gave_ports else None,
                warned_ports=json.dumps({str(p): t for p, t in sorted(told.items())}))
    if readable and watch >= WATCH_ROUNDS and all(e[3] or e[4] for e in todo.values()):
        cols['done_at'] = now
        if gave_ports: cols['kind'] = 'live-partial' if row['kind'] == 'live' else 'noop-partial'
    _set(connect, store, rid, **cols)
    said = ' '.join(words) or ('no lobby on it' if not todo else 'nothing left to read')
    _note(connect, store, rid, 'reload ' + said + ('' if readable else ' (table unread)'))
    log('reload', name, row['sha'][:12], said)


def rearm(connect, store, name):
    """`zonepub.py reload`: the map's newest force publish reloads its lobbies again, with its own
    clock (RELOAD_EXPIRE and the watch count from now, not from the write). Every lobby is judged
    afresh in mode 1. Refused once a newer row changed the files (a rollback, another publish)."""
    with locked(store), connect(store) as db:
        row = db.execute("SELECT * FROM publications WHERE map=? AND force=1 AND kind IN "
                         "('live','live-partial','noop','noop-partial') ORDER BY id DESC LIMIT 1", (name,)).fetchone()
        if row is None: raise ValueError('No reload-now publish of %s to re-arm' % name)
        newer = _newer_write(db, name, row['id'])
        if newer is not None:
            raise ValueError('%s %d changed the files of %s since; nothing re-armed' % (newer['kind'], newer['id'], name))
        kind = 'live' if row['kind'].startswith('live') else 'noop'
        # The write's stamp while it can still be measured (a lobby loaded since stays done); a new one
        # from now after a reboot, or for a row that wrote nothing (every lobby is reloaded once more).
        keep = row['since_mono'] is not None and row['since_boot'] == BOOT() and MONO() >= row['since_mono'] - 1
        since = (row['since_mono'], row['since_boot']) if keep else _since()
        db.execute('UPDATE publications SET kind=?, todo=NULL, round=NULL, partial=NULL, done_at=NULL, watch=0, '
                   'rearmed=?, since_mono=?, since_boot=? WHERE id=?', (kind, int(CLOCK())) + since + (row['id'],))
    log('re-armed', name, row['sha'][:12])
    return row['id']


def apply_ready(connect, store, dirs, valid_name, maps_fn, now, limit, rcon_fn=lobby_rcon):
    """Put every pending publish whose map is quiet into the directories. Returns {map: kind}."""
    paths_of = lambda m: [zone_path(d, m, valid_name) for d in dirs]
    done = {}
    if not dirs: return done        # no publish directories: nothing may be marked live
    maps = maps_fn()                # outside the transaction
    send = sender(store, rcon_fn)
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
                "SELECT id FROM publications WHERE force=1 AND kind IN ('live','noop') AND done_at IS NULL ORDER BY id")]
        for row in todo:
            name = row['map']
            fresh, pre = None, {}
            if row['force']:
                if not _force_pending(connect, store, row, maps, send, now): continue
                fresh = maps_fn()           # who is on the map at the write, not at the tick's start
                why = _unreachable(fresh, name)
                if why: _hold(connect, store, row, why); continue
                if name in fresh['owed']: continue
                with connect(store) as db:
                    told = _told(db.execute('SELECT warned, warned_ports FROM publications WHERE id=?',
                                            (row['id'],)).fetchone())
                targets = sorted(fresh['ports'].get(name, []))
                new = [p for p in targets if p not in told]
                if new:                     # moved onto the map since the warning: told, then a minute
                    _warn_round(connect, store, row, send, new, name, now)
                    continue
                # Each target answers just before the write, or nothing is written (a flood that
                # silences rcon must not leave the reload blind); its crc now says whether the
                # crc will tell its reload apart (an edit hashing the same needs its load time).
                pre = {p: lobby_info(send(p, ['serverinfo'], True)) for p in targets}
                quiet_ports = [p for p, info in pre.items() if not info]
                if quiet_ports:
                    _hold(connect, store, row, 'no answer just before the write from %s'
                          % ' '.join(str(p) for p in quiet_ports))
                    continue
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
                if all(same_zones(p, body) for p in prev):
                    # Already live: nothing changed, so a force reloads nobody (P1081 round 3).
                    db.execute("UPDATE publications SET kind='noop', live=?, hold=NULL, done_at=? WHERE id=?",
                               (math.ceil(CLOCK()), now, row['id']))
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
                with connect(store) as db:  # after put(): "loaded since" never includes before
                    db.execute('UPDATE publications SET kind=?, live=?, hold=NULL, since_mono=?, since_boot=? WHERE id=?',
                               (kind, math.ceil(CLOCK())) + _since() + (row['id'],))
                    if kind == 'live': log('live', name, row['sha'][:12], 'by', who(db, row['steamid']))
                done[name] = kind
            if row['force'] and kind == 'live':
                exp = (row['crc'] or '').lower()
                todo_now = {str(p): [0, 0, _mode(pre[p], name, exp), 0, 0] for p in sorted(fresh['ports'].get(name, []))}
                _set(connect, store, row['id'], round=None, watch=0, todo=json.dumps(todo_now))
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
            target = cur_state if cur_state is not None and cur_state['kind'] in ('live', 'live-partial') else None
        else:
            target = db.execute("SELECT * FROM publications WHERE id=? AND map=? AND kind IN "
                                "('live','live-partial','partial')", (to_id, name)).fetchone()
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
        # P1081: the crc of the bytes put back, from a row that wrote them live (None: not stated);
        # a crc stated by an upload that never went live is nobody's word for the files.
        back = db.execute('SELECT crc FROM publications WHERE map=? AND sha=? AND crc IS NOT NULL AND kind IN %s '
                          'ORDER BY id DESC LIMIT 1' % (LIVE_KINDS,),
                          (name, sha(prev[0]))).fetchone() if prev and prev[0] else None
        # `live` stays NULL until put() is done, as a publish's does (_recover stamps a crashed one).
        rid = db.execute("INSERT INTO publications(map,sha,steamid,at,kind,prev,result,crc) "
                         "VALUES(?,?,?,?,'rollingback',?,?,?)",
                         (name, target['sha'], target['steamid'], now,
                          json.dumps([[k, b.hex() if b is not None else None] for k, b in zip(keys, cur)]),
                          json.dumps([[k, sha(b)] for k, b in zip(keys, prev)]),
                          back[0] if back else None)).lastrowid
        db.commit()                 # the row first, as a publish does (_recover finishes it after a crash)
        try:
            put(paths, prev, limit)
        except (OSError, ValueError, PartialPublish) as e:     # anything else stays for _recover
            db.execute('UPDATE publications SET kind=? WHERE id=?',
                       ('partial' if isinstance(e, PartialPublish) else 'failed', rid)); db.commit()
            raise
        db.execute("UPDATE publications SET kind='rollback', live=? WHERE id=?", (math.ceil(CLOCK()), rid))
        db.commit()                 # live: the moment after put(), as a publish stamps it
    log('rollback', name, 'of', target['sha'][:12])
    return [sha(p) for p in prev]
