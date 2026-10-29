"""Paced, resumable KSF main-map completion walks, demanded by profile views.
HTTP queues only resolved Steam identities; ksfimport's shared lock/pacer and
host-wide refusal park own the network. Page durability precedes DB filing,
which precedes cursor acknowledgement. No replay/evidence authority is added.
"""
import calendar
import hashlib
import os
import sqlite3
import time
import urllib.parse

SQL = """
CREATE TABLE IF NOT EXISTS ksfprofiles (
 player TEXT PRIMARY KEY, mode INTEGER NOT NULL, cursor INTEGER NOT NULL,
 state TEXT NOT NULL, asked INTEGER NOT NULL, updated INTEGER NOT NULL,
 pages INTEGER NOT NULL DEFAULT 0, skipped INTEGER NOT NULL DEFAULT 0
);
"""
TTL = 86400
MAX_ACTIVE = 32
PAGE = 5                    # observed pagination.limit, not a request limit
MAX_POSITION = 10001         # safety bound; 'limited' is NOT complete
# P1117: after the four main walks, modes 4..7 walk style mode-4's stage and
# bonus PBs, one map a request: GET /api/players/<id>/records/map/<map>, the
# route ksf.surf's own player page uses (probed 29 Oct).  `cursor` indexes
# stage_maps(); the state stays 'partial' until mode 8.
STAGE_MODE = 4


def status(db, player):
    r = db.execute('SELECT state,mode,cursor,updated,pages,skipped FROM ksfprofiles WHERE player=?', (player,)).fetchone()
    return ({'state': r[0], 'mode': r[1], 'next': r[2], 'updated': r[3],
             'pages': r[4], 'unavailable': r[5]} if r else {'state': 'idle'})


def enqueue(db, player, now):
    # Only called after surfd resolved a public profile, never raw URL identity.
    if (len(player) != 17 or not player.isascii() or not player.isdigit()
            or int(player) >> 32 != 0x01100001):
        return {'state': 'ineligible'}
    old = db.execute('SELECT state,updated FROM ksfprofiles WHERE player=?', (player,)).fetchone()
    if old and (old[0] in ('queued', 'partial') or now - old[1] < TTL):
        return status(db, player)
    wait = db.execute('PRAGMA busy_timeout').fetchone()[0]
    try:
        db.execute('PRAGMA busy_timeout=50')
        with db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT state,updated FROM ksfprofiles WHERE player=?', (player,)).fetchone()
            if old and (old[0] in ('queued', 'partial') or now - old[1] < TTL):
                return status(db, player)
            n = db.execute("SELECT count(*) FROM ksfprofiles WHERE state IN ('queued','partial')").fetchone()[0]
            if n >= MAX_ACTIVE:
                return {'state': 'busy'}
            db.execute("INSERT INTO ksfprofiles(player,mode,cursor,state,asked,updated) VALUES (?,0,1,'queued',?,?) "
                       "ON CONFLICT(player) DO UPDATE SET mode=0,cursor=1,state='queued',asked=excluded.asked,updated=excluded.updated,pages=0,skipped=0", (player, now, now))
        return status(db, player)
    except sqlite3.OperationalError as e:
        if 'locked' not in str(e).lower() and 'busy' not in str(e).lower():
            raise
        return {'state': 'busy'}  # browsing still works; the next view retries
    finally:
        db.execute('PRAGMA busy_timeout=%d' % wait)


def pending(db):
    return db.execute("SELECT player,mode,cursor,asked FROM ksfprofiles WHERE state IN ('queued','partial') ORDER BY updated,asked,player LIMIT 3").fetchall()


def step(K, cache, pacer, have, now, budget=3):
    """Round-robin the selected players, at most budget pages, before the crawl.
    A page cache is retained even after import, so an interrupted write resumes
    without refetching and daily refreshes cannot reuse yesterday's snapshot.
    """
    db = K.S.connect()
    try:
        work = list(pending(db))
    finally:
        db.close()
    spent = 0
    for player, mode, start, asked in work:
        sid = K.S.steam2(player)
        if not sid:
            continue
        if mode >= STAGE_MODE:
            # A style with nothing to ask advances without spending a request.
            got = stage_step(K, cache, pacer, have, now, player, sid, mode, start, asked,
                             spent < budget)
            if got:
                spent += got[0]
                if got[1] == 'partial':
                    work.append((player, got[2], got[3], asked))
            continue
        if spent >= budget:
            continue
        leaf = hashlib.sha256(player.encode('ascii')).hexdigest()
        fn = os.path.join(cache, 'profiles', leaf, '%d-%d.json' % (mode, start))
        saved = K._load(fn)
        if not isinstance(saved, dict) or saved.get('asked') != asked:
            if pacer.left() <= 0:
                break
            try:
                doc = pacer.get('/api/players/%s/bestrecords/%d?game=css&mode=%d' % (sid, start, mode))
            except K.Refused as e:
                # This route's 500 is KSF's "not a player of mine" (ksfimport.NoSuchPlayer).
                # Parking the host on it stalled every crawl and demo from 2026-10-15 to
                # 10-17. At most one per tick; the crawl's next request still parks a
                # host that answers 500 to everything.
                if e.code != 500:
                    raise
                pacer.unanswered += 1   # never lifts a park (watch_mode)
                retire(K, player, mode, start, asked, now)
                return spent + 1
            saved = {'asked': asked, 'body': doc}
            # Invalid pages must not get a cursor, even if they are empty.
            validate(K, doc, start)
            durable(K, fn, saved)
        doc = saved.get('body')
        recs = validate(K, doc, start)
        rows, skipped = [], 0
        seen = set()
        for rec in recs:
            mp = K.S.clean_map(rec.get('mapName', ''))
            # This endpoint is MAIN records; never guess stage/bonus semantics.
            if rec.get('stage_id') is not None or rec.get('zone_id') is not None:
                raise K.Refused('profile contains non-main records')
            # bestrecords currently sends record_id:null, even for valid rows.
            # Completion identity is this player's MAIN map/style; null IDs
            # must NEVER acquire board/demo authority or fabricate a run ID.
            if not mp or mp in seen or K._when(rec) <= 0:
                raise K.Refused('profile map/date identity')
            seen.add(mp)
            if mp not in have:
                skipped += 1
                continue
            row = K.rec_row(mp, 0, mode, dict(rec, steamID=player))
            if row is None:
                raise K.Refused('profile record time')
            row['style'] = K.KSF_MODES[mode]
            row['binding'] = 'cache'  # never fresh board/demo authority
            rows.append(row)
        # A missing display name must not erase an already imported Steam name.
        db = K.S.connect()
        try:
            named = db.execute("SELECT name FROM runs WHERE player=? ORDER BY submitted DESC LIMIT 1", (player,)).fetchone()
        finally:
            db.close()
        for row in rows:
            row['name'] = named[0] if named else 'KSF player'
        K.write_rows(rows)          # FULL synchronous, idempotent; failure owes page
        nextmode, nxt, state = mode, start + len(recs), 'partial'
        if len(recs) < PAGE:
            nextmode, nxt = mode + 1, 1
            if nextmode == STAGE_MODE:
                nxt = 0             # P1117: on to the stage/bonus phase
        elif nxt >= MAX_POSITION:
            state = 'limited'
        db = K.S.connect()
        try:
            db.execute('PRAGMA synchronous=FULL')
            with db:
                db.execute('UPDATE ksfprofiles SET mode=?,cursor=?,state=?,updated=?,pages=pages+1,skipped=skipped+? '
                           "WHERE player=? AND mode=? AND cursor=? AND asked=? AND state IN ('queued','partial')",
                           (nextmode, nxt, state, now, skipped, player, mode, start, asked))
        finally:
            db.close()
        spent += 1
        if state == 'partial':
            work.append((player, nextmode, nxt, asked))
    return spent


def durable(K, fn, saved):
    K._save(fn, saved)
    with open(fn, 'r+b') as f:
        os.fsync(f.fileno())
    if os.name != 'nt':
        fd = os.open(os.path.dirname(fn), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def stage_maps(K, cache, player, style, have):
    """[(map, zones)]: the player's KSF main rows in `style` on installed maps
    whose cached map info names stages or bonuses (zones_of).  Never asks."""
    db = K.S.connect()
    try:
        maps = [r[0] for r in db.execute(
            "SELECT DISTINCT map FROM runs WHERE tier = ? AND player = ? AND style = ?"
            " AND track = 0 AND leg = 0 ORDER BY map",
            (K.S.TIER_KSF, player, K.KSF_MODES[style]))]
    finally:
        db.close()
    out = []
    for mp in maps:
        if mp not in have:
            continue
        try:
            info = K.map_info(mp, cache, K.Pacer(0, 0))
        except K.OverBudget:
            continue
        zones = set(K.zones_of(info)) - {0} if info else set()
        if zones:
            out.append((mp, zones))
    return out


def _iso(raw):
    try:
        return calendar.timegm(time.strptime(raw, '%Y-%m-%dT%H:%M:%SZ'))
    except (TypeError, ValueError):
        return 0


def stage_step(K, cache, pacer, have, now, player, sid, mode, start, asked, can_ask):
    """One map's stage/bonus PBs, or an advance past a style with none left.
    -> (requests, state, mode, cursor), or None when it would have to ask and may not.
    Rows are 'cache' bindings, as main completions are: never demo authority."""
    style = mode - STAGE_MODE
    maps = stage_maps(K, cache, player, style, have)
    made, state, nextmode, nxt = 0, 'partial', mode, start + 1
    if start >= len(maps):
        nextmode, nxt = mode + 1, 0
        if nextmode == 2 * STAGE_MODE:
            state, nextmode = 'complete', 2 * STAGE_MODE - 1
    else:
        mp, zones = maps[start]
        leaf = hashlib.sha256(player.encode('ascii')).hexdigest()
        fn = os.path.join(cache, 'profiles', leaf, '%d-%d-%s.json' % (mode, start, mp))
        saved = K._load(fn)
        if not isinstance(saved, dict) or saved.get('asked') != asked:
            if not can_ask or pacer.left() <= 0:
                return None
            made, saved = 1, None
            try:
                doc = pacer.get('/api/players/%s/records/map/%s?game=css&mode=%d'
                                % (sid, urllib.parse.quote(mp), style))
            except K.Refused as e:
                if e.code != 500:
                    raise
                pacer.unanswered += 1   # nothing there: the next map; never lifts a park
            else:
                saved = {'asked': asked, 'body': doc}
                validate_map(K, doc, sid)
                durable(K, fn, saved)
        rows = []
        for r in validate_map(K, saved['body'], sid) if saved else []:
            zone, when = r.get('zoneId'), _iso(r.get('date_set_at'))
            if type(zone) is not int or zone not in zones or when <= 0:
                continue
            row = K.rec_row(mp, zone, style, {'steamID': sid, 'time': r.get('surfTime'),
                                              'date': when, 'record_id': r.get('record_id')})
            if row:
                row['binding'] = 'cache'
                rows.append(row)
        if rows:
            db = K.S.connect()
            try:
                named = db.execute("SELECT name FROM runs WHERE player=? ORDER BY submitted DESC"
                                   " LIMIT 1", (player,)).fetchone()
            finally:
                db.close()
            for row in rows:
                row['name'] = named[0] if named else 'KSF player'
            K.write_rows(rows)
    db = K.S.connect()
    try:
        db.execute('PRAGMA synchronous=FULL')
        with db:
            db.execute('UPDATE ksfprofiles SET mode=?,cursor=?,state=?,updated=?,pages=pages+?'
                       " WHERE player=? AND mode=? AND cursor=? AND asked=? AND state IN ('queued','partial')",
                       (nextmode, nxt, state, now, made, player, mode, start, asked))
    finally:
        db.close()
    return made, state, nextmode, nxt


def validate_map(K, doc, sid):
    info = doc.get('basicInfo') if isinstance(doc, dict) else None
    if (not isinstance(info, dict) or info.get('steamID') != sid
            or not isinstance(doc.get('records'), list)
            or not all(isinstance(r, dict) for r in doc['records'])):
        raise K.Refused('profile map records shape')
    return doc['records']


def retire(K, player, mode, start, asked, now):
    """End a walk KSF answered 500 for: `unknown` before any page, else `limited`.
    A later profile view re-queues it after TTL, as for any finished walk."""
    db = K.S.connect()
    try:
        db.execute('PRAGMA synchronous=FULL')
        with db:
            db.execute("UPDATE ksfprofiles SET state=CASE WHEN pages=0 THEN 'unknown' ELSE 'limited' END,"
                       " updated=? WHERE player=? AND mode=? AND cursor=? AND asked=?"
                       " AND state IN ('queued','partial')", (now, player, mode, start, asked))
    finally:
        db.close()


def validate(K, doc, start):
    if not isinstance(doc, dict) or not isinstance(doc.get('records'), list):
        raise K.Refused('profile shape')
    pg = doc.get('pagination')
    if (not isinstance(pg, dict) or type(pg.get('offset')) is not int or
            pg['offset'] != start - 1 or type(pg.get('limit')) is not int or pg['limit'] != PAGE):
        raise K.Refused('profile offset/limit')
    rows = doc['records']
    if len(rows) > PAGE or not all(isinstance(r, dict) for r in rows):
        raise K.Refused('profile rows')
    return rows
