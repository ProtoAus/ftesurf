"""Durable free-Beta tournament API. Reservations are explicit, never TTL leases."""
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from flask import Response, request
import accounts
import social
import tournament_rules as rules
import tournament_pool

DDL = (
    "CREATE TABLE IF NOT EXISTS tournament_matches (id TEXT PRIMARY KEY, node TEXT NOT NULL, state TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS tournament_reservations (node TEXT PRIMARY KEY, match_id TEXT NOT NULL UNIQUE)",
    "CREATE TABLE IF NOT EXISTS tournament_nodes (node TEXT PRIMARY KEY, seen INTEGER NOT NULL, native_occupants INTEGER NOT NULL DEFAULT -1)",
    "CREATE TABLE IF NOT EXISTS tournament_requests (node TEXT NOT NULL, request TEXT NOT NULL, actor TEXT NOT NULL, fingerprint TEXT NOT NULL, reply TEXT NOT NULL, PRIMARY KEY(node,request))",
)
REQUEST = re.compile(r'[0-9a-f]{1,64}\Z')
NODE = re.compile(r'[A-Za-z0-9_-]{1,64}\Z')
CAP_TTL = 20
REQUEST_LIMIT = 50000


def schema(db):
    for statement in DDL:
        db.execute(statement)
    columns = {row[1] for row in db.execute('PRAGMA table_info(tournament_nodes)')}
    for name, sqltype, default in (('movement', 'TEXT', "''"), ('tick_us', 'INTEGER', '0'), ('clock_us', 'INTEGER', '0')):
        if name not in columns:
            db.execute('ALTER TABLE tournament_nodes ADD COLUMN ' + name + ' ' + sqltype + ' NOT NULL DEFAULT ' + default)
    if 'native_occupants' not in columns:
        db.execute('ALTER TABLE tournament_nodes ADD COLUMN native_occupants INTEGER NOT NULL DEFAULT -1')


def reserved(db, node):
    return db.execute('SELECT 1 FROM tournament_reservations WHERE node=?', (node,)).fetchone() is not None


def current(db, node):
    row = db.execute('SELECT m.state FROM tournament_matches m JOIN tournament_reservations r'
                     ' ON r.match_id=m.id WHERE r.node=?', (node,)).fetchone()
    return json.loads(row['state']) if row else None


def hosting_allowed(d):
    return (d.setting('SURFD_TOURNAMENTS', '0') == '1' and
            d.setting('SURFD_TOURNAMENT_ACCESS', 'free_beta') == 'free_beta')


def require_hosting(d):
    rules.require(hosting_allowed(d), 'free Beta hosting unavailable')


def map_pool(db, d, settings):
    return tournament_pool.selected(db, d, settings)


def compatible(row, settings):
    profile = rules.PROFILES[settings['profile']]
    return (row['movement'] == profile['movement'] and
            row['tick_us'] == row['clock_us'] and row['tick_us'] in rules.node_ticks(settings['profile']))


def drift(match, data):
    if match and match.get('_arrived') and match['phase'] in ('loading', 'countdown', 'live'):
        try:
            rules.observe(match, data)
        except rules.Refusal:
            match = rules.transition(match, 'abort', '', '', {})
            match['note'] = 'No contest: loaded map or effective rules changed; restoration required.'
    return match


def register(app, d):
    def enabled():
        return d.setting('SURFD_TOURNAMENTS', '0') == '1'

    def reply(ok, status, match=None, error=None):
        out = dict(v=1, ok=int(ok), status=status, match=rules.public(match) if match else None)
        if error:
            out['error'] = error
        return out

    def response(payload, code=200):
        return Response(d.game_json(payload), status=code, mimetype='application/json')

    @app.get('/api/tournament-map-pool')
    def pool_read():
        if not enabled():
            return response(dict(ok=1, v=1, enabled=0, rows=[]))
        if not d.rate_ok(d.rate_key(), int(d.clock()), 240, 'pool-read'):
            return response(dict(ok=0, v=1, error='try again shortly'), 429)
        try:
            rules.require(set(request.args) <= {'kind', 'tiers', 'profile', 'offset', 'limit'} and
                          all(len(request.args.getlist(k)) == 1 for k in request.args), 'bad filters')
            data = dict(kind=request.args.get('kind', 'surf'), tiers=request.args.get('tiers', '7'),
                        profile=request.args.get('profile', 'default'), pool='-')
            settings = rules.settings(data)
            offset = rules.integer({'offset': request.args.get('offset', '0')}, 'offset', 0, 8192)
            limit = rules.integer({'limit': request.args.get('limit', '8')}, 'limit', 1, 16)
            qualified, unqualified = tournament_pool.catalogue(d.get_db(), d, settings)
            rows = [{k: c[k] for k in ('name', 'kind', 'tier', 'mt', 'kt')} for c in qualified.values()]
            return response(dict(ok=1, v=1, enabled=1, policy='free_beta', hosting=int(hosting_allowed(d)),
                                 rows=rows[offset:offset+limit], total=len(rows), unqualified=unqualified,
                                 offset=offset, limit=limit, filters={k: settings[k] for k in ('kind', 'tiers', 'profile')},
                                 tick_us=settings['tick_us'], profiles=[dict(v, id=k, tick_us=rules.tick_for(k, settings['kind'])) for k, v in rules.PROFILES.items()]))
        except rules.Refusal as exc:
            return response(dict(ok=0, v=1, enabled=1, error=str(exc)), 400)

    @app.get('/api/tournaments')
    def browse():
        if not enabled():
            return response(dict(v=1, enabled=0, rows=[], slots=[]))
        db, now = d.get_db(), int(d.clock())
        rows = []
        for row in db.execute('SELECT m.state FROM tournament_matches m JOIN tournament_reservations r'
                              ' ON r.match_id=m.id ORDER BY m.id LIMIT 200'):
            m = json.loads(row['state'])
            if m['phase'] not in rules.TERMINAL and not m.get('menu_started'):
                rows.append(dict(id=m['id'], node=m['node'], name=m['name'], addr=m['addr'],
                                 phase=m['phase'], players=len(rules.competitors(m)),
                                 capacity=m['capacity'], map=m['current_map']))
        ticks = rules.node_ticks('default')
        slots = [dict(node=r['node'], name=r['name'][:64], addr=r['addr'], map=r['map'])
                 for r in db.execute(('SELECT l.* FROM lobbies l JOIN tournament_nodes t ON t.node=l.node'
                                     ' WHERE l.last_seen>? AND l.last_seen<=? AND t.seen>? AND t.seen<=?'
                                     " AND l.players=0 AND t.native_occupants=0 AND t.movement='default' AND t.tick_us=t.clock_us AND t.tick_us IN (%s) AND NOT EXISTS"
                                     ' (SELECT 1 FROM tournament_reservations r WHERE r.node=l.node)'
                                     ' AND NOT EXISTS (SELECT 1 FROM assignments a WHERE a.node=l.node AND a.asked_at>=?)'
                                     ' ORDER BY l.node LIMIT 200') % ','.join('?' * len(ticks)),
                                     (now-d.lobby_ttl, now, now-CAP_TTL, now, *ticks, now-d.assign_ttl))]
        return response(dict(v=1, enabled=1, rows=rows, slots=slots))

    @app.post('/api/tournaments/game')
    def game():
        key = request.form.get('key', '')
        if not d.secret() or not key or not hmac.compare_digest(key, d.secret()):
            return response(reply(False, 'forbidden', error='forbidden'), 403)
        data = request.form.to_dict()
        node, op = data.get('node', ''), data.get('op', '')
        if not NODE.fullmatch(node):
            return response(reply(False, 'invalid', error='bad node'))
        db, now = d.get_db(), int(d.clock())
        try:
            with db:
                db.execute('BEGIN IMMEDIATE')
                m = current(db, node)
                if op == 'state':
                    # Polling can advertise capability but cannot free a reservation.
                    if enabled() and data.get('enabled') == '1':
                        lobby = db.execute('SELECT 1 FROM lobbies WHERE node=?', (node,)).fetchone()
                        if lobby:
                            native = rules.integer(data, 'occupants', 0, 256)
                            movement = data.get('movement', '')
                            movement = movement if movement in {p['movement'] for p in rules.PROFILES.values()} else ''
                            ticks = []
                            for field in ('tick_us', 'clock_us'):
                                try:
                                    ticks.append(rules.integer(data, field, 1000, 15000))
                                except rules.Refusal:
                                    ticks.append(0)
                            db.execute('INSERT INTO tournament_nodes(node,seen,native_occupants,movement,tick_us,clock_us) VALUES(?,?,?,?,?,?)'
                                       ' ON CONFLICT(node) DO UPDATE SET seen=excluded.seen,'
                                       ' native_occupants=excluded.native_occupants,movement=excluded.movement,'
                                       ' tick_us=excluded.tick_us,clock_us=excluded.clock_us', (node, now, native, movement, *ticks))
                    elif data.get('enabled') == '0':
                        db.execute('DELETE FROM tournament_nodes WHERE node=?', (node,))
                    changed = drift(m, data)
                    if changed != m:
                        m = changed
                        db.execute('UPDATE tournament_matches SET state=? WHERE id=?', (d.game_json(m), m['id']))
                    return response(reply(True, 'ok' if enabled() else 'disabled', m))
                # Abort/release remain available when the feature is disabled.
                rules.require(enabled() or op in ('abort', 'release', 'leave', 'cancel'), 'tournaments disabled')
                if op in ('create', 'configure', 'start'):
                    require_hosting(d)
                actor, sid, display = '', '', ''
                if op not in rules.SERVER_OPS:
                    session = social.session(db, data.get('token', ''), node, now)
                    rules.require(session is not None, 'valid server-held linked account token required')
                    sid = session['steamid']
                    actor = accounts.who_of(sid)
                    display = accounts.game_name(db.execute('SELECT name FROM accounts WHERE steamid=?',
                                                           (sid,)).fetchone()['name'])
                request_id = data.get('request', '')
                rules.require(bool(REQUEST.fullmatch(request_id)), 'request must be 1..64 lowercase hex')
                # Tokens may rotate on reconnect; account identity, not capability bytes, owns retries.
                canonical = {k: v for k, v in data.items() if k not in ('key', 'token')}
                fingerprint = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
                old = db.execute('SELECT * FROM tournament_requests WHERE node=? AND request=?',
                                 (node, request_id)).fetchone()
                if old:
                    rules.require(old['actor'] == sid and old['fingerprint'] == fingerprint,
                                  'request id reused with different action')
                    return response(json.loads(old['reply']))
                rules.require(op in ('abort', 'release') or
                              db.execute('SELECT COUNT(*) FROM tournament_requests').fetchone()[0] < REQUEST_LIMIT,
                              'alpha request journal full; abort/release or operator archival required')
                if op == 'create':
                    rules.require(m is None, 'node already reserved')
                    rules.require(rules.integer(data, 'revision', 0, 0) == 0, 'create revision must be zero')
                    rules.integer(data, 'occupants', 1, 1)
                    row = db.execute('SELECT l.*,t.native_occupants,t.movement,t.tick_us,t.clock_us FROM lobbies l JOIN tournament_nodes t ON t.node=l.node'
                                     ' WHERE l.node=? AND l.last_seen>? AND l.last_seen<=?'
                                     ' AND t.seen>? AND t.seen<=?',
                                     (node, now-d.lobby_ttl, now, now-CAP_TTL, now)).fetchone()
                    rules.require(row is not None, 'fresh heartbeat and enabled=1 capability poll required')
                    rules.require(row['players'] <= 1 and 0 <= row['native_occupants'] <= 1,
                                  'node occupied by other clients')
                    rules.require(row['maxplayers'] >= rules.integer(data, 'capacity', 2, 8),
                                  'node has too few client slots')
                    rules.require(db.execute('SELECT 1 FROM assignments WHERE node=? AND asked_at>=?',
                                             (node, now-d.assign_ttl)).fetchone() is None, 'ordinary assignment pending')
                    configured = rules.settings(data, legacy=True)
                    map_pool(db, d, configured)
                    rules.require(compatible(row, configured), 'node profile incompatible')
                    rules.require(db.execute('SELECT 1 FROM lobby_handoffs WHERE node=? AND until>=?', (node, now)).fetchone() is None, 'ordinary handoff pending')
                    m = rules.create(secrets.token_hex(16), node, display, row['addr'], actor, display, data)
                    m['_accounts'][actor] = sid
                    db.execute('INSERT INTO tournament_matches VALUES(?,?,?)', (m['id'], node, d.game_json(m)))
                    db.execute('INSERT INTO tournament_reservations VALUES(?,?)', (node, m['id']))
                else:
                    rules.require(m is not None and data.get('id') == m['id'], 'match not owned by node')
                    rules.require(rules.integer(data, 'revision', 1, 2147483647) == m['revision'], 'stale revision; resync')
                    if op in rules.SERVER_OPS:
                        rules.require(data.get('epoch') == m['epoch'], 'wrong ownership epoch')
                    if actor:
                        rules.require(actor not in m['_accounts'] or m['_accounts'][actor] == sid,
                                      'ambiguous public account handle')
                        rules.require(actor in m['_accounts'] or len(m['_accounts']) < 256,
                                      'alpha account history full')
                    if op in ('configure', 'lock', 'start'):
                        rules.require_current_settings(m)
                    if op == 'configure':
                        map_pool(db, d, rules.settings(data))
                    if op == 'start':
                        tournament_pool.revalidate(db, d, m)
                    m = rules.transition(m, op, actor, display, data,
                                         map_pool(db, d, m['settings']) if op == 'lock' else ())
                    if actor:
                        m['_accounts'][actor] = sid
                    db.execute('UPDATE tournament_matches SET state=? WHERE id=?', (d.game_json(m), m['id']))
                    if op == 'release':
                        db.execute('DELETE FROM tournament_reservations WHERE node=? AND match_id=?', (node, m['id']))
                out = reply(True, 'released' if op == 'release' else 'ok', m)
                db.execute('INSERT INTO tournament_requests VALUES(?,?,?,?,?)',
                           (node, request_id, sid, fingerprint, d.game_json(out)))
                return response(out)
        except rules.Refusal as exc:
            return response(reply(False, 'refused', current(db, node), str(exc)))
        except sqlite3.Error:
            d.log.exception('tournament storage error')
            return response(reply(False, 'storage', error='storage unavailable; retry same request'))
