"""Steam-linked lobby activity, never run evidence or ranking authority.

Lobbies post cumulative per-connection/map snapshots under an existing proven
social capability. Retries and reordered replies merge maxima, not additions.
Retain session watermarks: deleting them would make a replay count twice.
Times are real connected seconds (including spectating), not movement ticks.
"""
import hashlib
import json
import re
import hmac


def binding(db, pub, steamid):
    """Public association generation, never a capability or evidence digest.

    Link timestamps are not epochs: two confirmations can share a second.
    SQL triggers rotate this persistent, non-reused generation even for an
    older compatible writer. Missing generation fails closed, never to time.
    """
    row = db.execute('SELECT e.generation FROM play_link_epochs e JOIN keylinks k'
                     ' ON k.pub=e.pub WHERE k.pub=? AND k.steamid=?',
                     (pub, steamid)).fetchone()
    if row is None:
        return ''
    message = 'FS_ACTIVITY_LINK1\n' + pub + '\n' + steamid + '\n' + str(row['generation'])
    return hashlib.sha256(message.encode('ascii')).hexdigest()[:32]


MAX_COUNT = 16777215  # exact integers in the QC producer
TRACKS, LEGS = 12, 24
SQL = """
CREATE TABLE IF NOT EXISTS play_sessions (
 node TEXT NOT NULL, stream TEXT NOT NULL, steamid TEXT NOT NULL, map TEXT NOT NULL,
 seconds INTEGER NOT NULL, attempts TEXT NOT NULL, updated INTEGER NOT NULL,
 PRIMARY KEY(node,stream));
CREATE TABLE IF NOT EXISTS play_maps (
 steamid TEXT NOT NULL, map TEXT NOT NULL, seconds INTEGER NOT NULL,
 PRIMARY KEY(steamid,map));
CREATE TABLE IF NOT EXISTS play_attempts (
 steamid TEXT NOT NULL, map TEXT NOT NULL, track INTEGER NOT NULL,
 leg INTEGER NOT NULL, attempts INTEGER NOT NULL,
 PRIMARY KEY(steamid,map,track,leg));
CREATE TABLE IF NOT EXISTS play_link_epochs (
 generation INTEGER PRIMARY KEY AUTOINCREMENT,
 pub TEXT NOT NULL UNIQUE);
INSERT INTO play_link_epochs(pub) SELECT pub FROM keylinks
 WHERE pub NOT IN (SELECT pub FROM play_link_epochs);
CREATE TRIGGER IF NOT EXISTS play_link_insert AFTER INSERT ON keylinks BEGIN
 DELETE FROM play_link_epochs WHERE pub=new.pub;
 INSERT INTO play_link_epochs(pub) VALUES(new.pub);
END;
CREATE TRIGGER IF NOT EXISTS play_link_update
 AFTER UPDATE OF steamid,linked_at ON keylinks BEGIN
 DELETE FROM play_link_epochs WHERE pub=new.pub;
 INSERT INTO play_link_epochs(pub) VALUES(new.pub);
END;
CREATE TRIGGER IF NOT EXISTS play_link_delete AFTER DELETE ON keylinks BEGIN
 DELETE FROM play_link_epochs WHERE pub=old.pub;
END;
"""


def number(raw):
    if not isinstance(raw, str) or not re.fullmatch(r"[0-9]{1,8}", raw):
        raise ValueError("Bad play statistics")
    value = int(raw)
    if value > MAX_COUNT:
        raise ValueError("Bad play statistics")
    return value


def parse(stream, seconds, attempts):
    if not isinstance(stream, str) or not re.fullmatch(r"[0-9a-f]{32}", stream):
        raise ValueError("Bad statistics stream")
    seconds = number(seconds)
    if not isinstance(attempts, str) or len(attempts) > 8000:
        raise ValueError("Bad attempts")
    out = {}
    rows = attempts.split(',') if attempts else []
    if len(rows) > TRACKS * LEGS:
        raise ValueError("Too many attempt counters")
    for row in rows:
        fields = row.split(':')
        if len(fields) != 3:
            raise ValueError("Bad attempt counter")
        track, leg, count = map(number, fields)
        key = f"{track}:{leg}"
        if track >= TRACKS or leg >= LEGS or key in out or not count:
            raise ValueError("Bad attempt counter")
        out[key] = count
    return seconds, out


def store(db, steamid, node, stream, mapname, seconds, attempts, now):
    """Caller holds BEGIN IMMEDIATE and has authenticated both node and Steam.

    Identity/map are pinned before totals change. A capability renewal can keep
    the stream; relinking cannot transfer old activity to the new account.
    """
    old = db.execute("SELECT * FROM play_sessions WHERE node=? AND stream=?",
                     (node, stream)).fetchone()
    if old and (old['steamid'] != steamid or old['map'] != mapname):
        raise ValueError("Statistics stream belongs to another account or map")
    before_seconds = old['seconds'] if old else 0
    before = json.loads(old['attempts']) if old else {}
    seconds = max(seconds, before_seconds)
    merged = dict(before)
    db.execute("INSERT INTO play_maps(steamid,map,seconds) VALUES(?,?,?)"
               " ON CONFLICT(steamid,map) DO UPDATE SET seconds=seconds+excluded.seconds",
               (steamid, mapname, seconds - before_seconds))
    for key, count in attempts.items():
        previous = before.get(key, 0)
        if count <= previous:
            continue
        track, leg = map(int, key.split(':'))
        db.execute("INSERT INTO play_attempts VALUES(?,?,?,?,?)"
                   " ON CONFLICT(steamid,map,track,leg) DO UPDATE SET attempts=attempts+excluded.attempts",
                   (steamid, mapname, track, leg, count - previous))
        merged[key] = count
    db.execute("INSERT INTO play_sessions VALUES(?,?,?,?,?,?,?)"
               " ON CONFLICT(node,stream) DO UPDATE SET seconds=excluded.seconds,"
               " attempts=excluded.attempts,updated=excluded.updated",
               (node, stream, steamid, mapname, seconds,
                json.dumps(merged, sort_keys=True, separators=(',', ':')), now))


def client_snapshot(raw, pub, digest, capture_binding, clean_map):
    """A self-reported local ledger, bound to its native MENU proof's key.

    This does not verify gameplay or grant any ranking/receipt authority.
    Server and client snapshots share node/stream watermarks to avoid counting
    the same connected session twice when both transports deliver it.
    """
    if not isinstance(raw, str) or len(raw) > 7000 or not raw.isascii():
        raise ValueError('Bad activity snapshot')
    if hashlib.sha256(raw.encode('ascii')).hexdigest() != digest:
        raise ValueError('Activity snapshot does not match its proof')
    rows = raw.split('\n')
    if len(rows) != 10 or rows[0] != 'FTESURF-PLAYSTATS 2' or rows[-1] != '':
        raise ValueError('Bad activity snapshot format')
    values = {}
    for key, row in zip(('pub', 'node', 'stream', 'map', 'seconds', 'revision', 'attempts', 'binding'), rows[1:-1]):
        prefix = key + ' '
        if not row.startswith(prefix):
            raise ValueError('Bad activity snapshot field')
        values[key] = row[len(prefix):]
    if not re.fullmatch(r'[0-9a-f]{64}', values['pub']) or values['pub'] != pub:
        raise ValueError('Activity snapshot belongs to another key')
    if not re.fullmatch(r'[a-z0-9_-]{1,32}', values['node']):
        raise ValueError('Bad activity node')
    canonical = clean_map(values['map'])
    if not canonical or canonical != values['map']:
        raise ValueError('Bad activity map')
    if not re.fullmatch(r'[0-9a-f]{32}', values['binding']) or not hmac.compare_digest(values['binding'], capture_binding):
        raise ValueError('Activity belongs to an earlier or unassigned account association')
    number(values['revision'])
    seconds, attempts = parse(values['stream'], values['seconds'], values['attempts'])
    return values['node'], values['stream'], values['map'], seconds, attempts


def profile(db, steamid, mapname=None):
    seconds = db.execute("SELECT COALESCE(SUM(seconds),0) FROM play_maps WHERE steamid=?",
                         (steamid,)).fetchone()[0]
    result = {'seconds': seconds, 'scope': 'steam_linked_game'}
    if mapname is not None:
        row = db.execute("SELECT seconds FROM play_maps WHERE steamid=? AND map=?",
                         (steamid, mapname)).fetchone()
        result['map_seconds'] = row[0] if row else 0
        result['attempts'] = [dict(track=r[0], leg=r[1], n=r[2]) for r in db.execute(
            "SELECT track,leg,attempts FROM play_attempts WHERE steamid=? AND map=?"
            " ORDER BY track,leg", (steamid, mapname))]
    return result
