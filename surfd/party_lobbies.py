"""Main-menu parties. Presence expires in 35s; pre-launch idle parties in 15min.
Launch reservations have no menu TTL and use the existing restoration-gated release.
"""
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
import random
import re
import secrets
import sqlite3
from urllib.parse import parse_qsl
from flask import Response, request
import accounts
import social
import tournaments
import tournament_pool
import tournament_rules as rules

ONLINE_TTL = 35
IDLE_TTL = 900
TURN_SECONDS = 45  # per party draft ban/pick, then a seeded map is chosen for that player
JOIN_COOLDOWN = 10  # seconds between one account's joins of one room: each join bumps the revision
JOURNAL_KEEP = 64  # request ids per account: retries come seconds apart, and this bounds the table
FIELDS = ('op', 'id', 'revision', 'request', 'capacity', 'round_seconds', 'target', 'map', 'value', 'kind', 'tiers', 'profile', 'pool', 'text')
OPS = frozenset(('configure', 'create', 'state', 'join', 'leave', 'cancel', 'seat', 'accept', 'lock', 'ban', 'pick', 'ready', 'start', 'say', 'kick'))
CHAT_KEEP = 40
CHAT_TEXT = 200
HEX32 = re.compile(r'[0-9a-f]{32}\Z')
_BAD_ROOMS = set()  # room ids already logged as unreadable: one log per room per process, not per poll
DDL = (
    'CREATE TABLE IF NOT EXISTS tournament_parties(id TEXT PRIMARY KEY,state TEXT NOT NULL,touched INTEGER NOT NULL)',
    'CREATE TABLE IF NOT EXISTS tournament_party_members(account TEXT PRIMARY KEY,party TEXT NOT NULL,seen INTEGER NOT NULL)',
    'CREATE TABLE IF NOT EXISTS tournament_party_requests(account TEXT NOT NULL,request TEXT NOT NULL,fingerprint TEXT NOT NULL,PRIMARY KEY(account,request))',
    'CREATE TABLE IF NOT EXISTS tournament_party_proofs(proof TEXT PRIMARY KEY,until INTEGER NOT NULL)',
)


def schema(db):
    for sql in DDL:
        db.execute(sql)


def parse_payload(payload):
    rules.require(0 < len(payload) <= 2048 and payload.isascii(), 'bad payload')
    rules.require(not re.search(r'%(?![0-9A-Fa-f]{2})', payload), 'bad encoding')
    try:
        # UTF-8 for chat text; every other field is still checked against ASCII patterns below.
        pairs = parse_qsl(payload, strict_parsing=True, encoding='utf-8', errors='strict', max_num_fields=14)
    except (ValueError, UnicodeError):
        raise rules.Refusal('bad payload')
    rules.require(tuple(k for k, v in pairs) == FIELDS, 'all fourteen ordered fields required')
    data = dict(pairs)
    rules.require(data['op'] in OPS, 'bad operation')
    rules.require(data['id'] == '-' or HEX32.fullmatch(data['id']), 'bad id')
    rules.require(bool(HEX32.fullmatch(data['request'])), 'bad request')
    rules.require(all(re.fullmatch(r'0|[1-9][0-9]*', data[k])
                      for k in ('revision', 'capacity', 'round_seconds')), 'noncanonical integer')
    rules.integer(data, 'revision', 0, 2147483647)
    rules.integer(data, 'capacity', 2, 8)
    rules.integer(data, 'round_seconds', 60, 900)
    rules.require(data['value'] in ('0', '1'), 'bad value')
    rules.require(data['target'] == '-' or bool(re.fullmatch(r'[0-9a-f]{8}', data['target'])), 'bad target')
    rules.require(data['map'] == '-' or bool(rules.MAP_NAME.fullmatch(data['map'])), 'bad map')
    text = data['text']
    if data['op'] == 'say':
        rules.require(0 < len(text) <= CHAT_TEXT and text == text.strip() and text != '-'
                      and all(c.isprintable() for c in text), 'bad text')
    else:
        rules.require(text == '-', 'bad text')
    rules.settings(data)
    return data


def bad_room(log, ident):
    """Call from an except block: logs a room that cannot be read or listed, once."""
    if ident not in _BAD_ROOMS and len(_BAD_ROOMS) < 1024:
        _BAD_ROOMS.add(ident)
        log.exception('party room %s skipped', ident)


def room_state(row):
    """A room row's JSON state; ValueError when it is unreadable or names another id."""
    m = json.loads(row['state'])
    if not isinstance(m, dict) or m.get('id') != row['id']:
        raise ValueError('room state does not match its row')
    return m


def turn_clock(m, now):
    """Party draft clock: stamps each new turn and makes an overdue turn's ban/pick.
    Returns the new state, or None when nothing changed. Callers hold BEGIN IMMEDIATE."""
    if m is None or m.get('menu_started'):
        return None
    if m['phase'] != 'draft':
        return {k: v for k, v in m.items() if k != '_turn_at'} if '_turn_at' in m else None
    at = m.get('_turn_at')  # [turn index, start time]
    if not (isinstance(at, list) and len(at) == 2 and at[0] == m['_turn']):
        return dict(m, _turn_at=[m['_turn'], now])
    if now < at[1] + TURN_SECONDS:
        return None
    who, kind = m['turn_who'], m['turn_kind']
    name = next((p['name'] for p in m['players'] if p['who'] == who), who)
    choices = sorted(c['name'] for c in m['maps'] if c['status'] == 'pool')
    if kind not in ('ban', 'pick') or not choices:
        return None
    chosen = random.Random('%s:clock:%d' % (m['_seed'], m['_turn'])).choice(choices)
    try:
        m = rules.transition(m, kind, who, name, dict(map=chosen))
    except rules.Refusal:
        return None  # an odd room must not refuse every member action or break the directory
    m['note'] = '%s ran out of time; a map was %s for them.' % (
        rules.short(name, rules.NAME_BYTES), 'banned' if kind == 'ban' else 'picked')
    if m['phase'] == 'draft':
        m['_turn_at'] = [m['_turn'], now]
    else:
        m.pop('_turn_at', None)
        m['menu_phase'] = 'ready'
    return m


def register(app, d):
    try:
        tools = d.setting('SURFD_TOOLS') or str(Path(d.setting('SURFD_GAME') or '/srv/nvme/ftesurf-server/game') / 'tools')
        spec = importlib.util.spec_from_file_location('party_ed25519', Path(tools) / 'ed25519.py')
        ed = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ed)
    except (OSError, ImportError, AttributeError):
        ed = None

    def enabled():
        return d.setting('SURFD_TOURNAMENTS', '0') == '1'

    def response(out, code=200):
        return Response(d.game_json(dict(v=1, **out)), status=code, mimetype='application/json')

    def ticket(nonce, digest, expires, peer):
        secret = d.secret()
        if not secret:
            return ''
        msg = json.dumps(['tournament-menu-v1', nonce, digest, expires, peer], separators=(',', ':'))
        return hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()

    def expire(db, now):
        # No launched party is ever retired by a waiting-room clock.
        # Binds use the row key, never the JSON id.
        def reap(ident):
            db.execute('DELETE FROM tournament_party_members WHERE party=?', (ident,))
            db.execute('DELETE FROM tournament_parties WHERE id=?', (ident,))

        for row in db.execute('SELECT * FROM tournament_parties').fetchall():
            try:
                m = room_state(row)
                if m.get('menu_started'):
                    live = db.execute('SELECT state FROM tournament_matches WHERE id=?', (row['id'],)).fetchone()
                    phase = json.loads(live['state'])['phase'] if live else None
                    # A closed room's row goes at once: its members are gone and nothing reads it
                    # again (the match row stays for release/restoration), so the scan stays the live set.
                    if phase in rules.TERMINAL:
                        reap(row['id'])
                    continue
                if m['phase'] in rules.TERMINAL or row['touched'] < now-IDLE_TTL:
                    reap(row['id'])
            except sqlite3.Error:
                raise
            except Exception:
                bad_room(d.log, row['id'])
                # Unreadable rooms still idle out by the column alone, freeing their members.
                if row['touched'] < now-IDLE_TTL:
                    reap(row['id'])

    def snapshot(db, m, now):
        out = rules.public(m)
        # Detailed and public snapshots never carry a handoff or node address.
        out.pop('addr', None)
        out.pop('node', None)
        seen = {r['account']: r['seen'] for r in db.execute('SELECT account,seen FROM tournament_party_members WHERE party=?', (m['id'],))}
        for p in out['players']:
            sid = m['_accounts'].get(p['who'])
            p['menu_online'] = int(sid in seen and now-ONLINE_TTL < seen[sid] <= now)
            p.setdefault('menu_ready', 0)
        at = m.get('_turn_at')
        if m['phase'] == 'draft' and isinstance(at, list):
            out['turn_left'] = max(0, at[1] + TURN_SECONDS - now)
        return out

    def clock(m, now):
        try:
            return turn_clock(m, now)
        except Exception:  # one bad room must not fail the directory or its members' requests
            bad_room(d.log, m.get('id') if isinstance(m, dict) else None)
            return None

    def listing(db, row, now, brief):
        m = room_state(row)
        ticked = clock(m, now)
        if ticked:
            m = ticked
            db.execute('UPDATE tournament_parties SET state=? WHERE id=?', (d.game_json(m), row['id']))
        if m['phase'] in rules.TERMINAL or not (m.get('menu_started') or row['touched'] >= now-IDLE_TTL):
            return None
        if brief:
            # The menu browser needs no rosters/map pools. Bound its
            # wire size even with 200 rooms of 72 long-named members.
            return dict(id=m['id'], host=m['host'], name=m['name'], capacity=m['capacity'],
                        phase=m['phase'], revision=m['revision'], members=len(m['players']))
        # Room chat and who is at the menu right now are for members only.
        out = snapshot(db, m, now)
        out.pop('chat', None)
        for p in out['players']:
            p.pop('menu_online', None)
        return out

    def result(db, m, sid, now, status='ok'):
        launch = None
        if m and m.get('menu_started'):
            member = db.execute('SELECT 1 FROM tournament_party_members WHERE account=? AND party=?', (sid, m['id'])).fetchone()
            live = db.execute('SELECT state FROM tournament_matches WHERE id=?', (m['id'],)).fetchone()
            if member and live and tournaments.reserved(db, m['node']):
                match = json.loads(live['state'])
                if match['phase'] not in rules.TERMINAL:
                    # Clients connect only once the node has loaded the round's map (its
                    # `arrive`): one still loading the waiting map when the node changes
                    # level hangs on "Changing map" (SV_Begin_f from different level).
                    ready = int(bool(match.get('_arrived')) or match['phase'] != 'loading' or match.get('generation', 1) > 1)
                    launch = dict(id=m['id'], epoch=m['epoch'], addr=m['addr'], map=m['schedule'][0], ready=ready)
        return dict(ok=1, status=status, me=accounts.who_of(sid), party=snapshot(db, m, now) if m else None, launch=launch)

    @app.get('/api/tournament-lobbies', endpoint='party_browse')
    def browse():
        if not enabled():
            return response(dict(enabled=0, rows=[]))
        db, now = d.get_db(), int(d.clock())
        if not d.rate_ok(d.rate_key(), now, 240, 'party-browse'):
            return response(dict(ok=0, error='try again shortly'), 429)
        rows = []
        brief = request.args.get('brief') == '1'
        with db:
            db.execute('BEGIN IMMEDIATE')
            expire(db, now)
            # Historical rows must not consume the bounded active-directory quota.
            for row in db.execute('SELECT * FROM tournament_parties ORDER BY id').fetchall():
                try:
                    out = listing(db, row, now, brief)
                except sqlite3.Error:
                    raise
                except Exception:
                    bad_room(d.log, row['id'])
                    continue
                if out is not None:
                    rows.append(out)
                    if len(rows) == 200:
                        break
        return response(dict(enabled=1, rows=rows))

    @app.get('/api/tournament-lobbies/challenge', endpoint='party_challenge')
    def challenge():
        now, peer = int(d.clock()), d.rate_key()
        digest = request.args.get('hash', '')
        if not d.rate_ok(peer, now, 240, 'party-challenge'):
            return response(dict(ok=0, error='try again shortly'), 429)
        if not social.TOKEN.fullmatch(digest) or len(request.query_string) > 80:
            return response(dict(ok=0, error='bad hash'), 400)
        nonce, expires = secrets.token_hex(16), str(now+social.MENU_TTL)
        proof = ticket(nonce, digest, expires, peer)
        if not ed or not proof:
            return response(dict(ok=0, error='proof unavailable'), 503)
        return response(dict(ok=1, nonce=nonce, expires=expires, ticket=proof))

    @app.post('/api/tournament-lobbies/action', endpoint='party_action')
    def action():
        now, peer = int(d.clock()), d.rate_key()
        sid, m = '', None
        try:
            rules.require((request.content_length or 0) <= 8192, 'request too large')
            rules.require(d.rate_ok(peer, now, 240, 'party-action'), 'try again shortly')
            f = request.form
            rules.require(set(f) == {'payload', 'nonce', 'expires', 'ticket', 'pub', 'sig'} and all(len(f.getlist(k)) == 1 for k in f), 'bad proof fields')
            data = parse_payload(f['payload'])
            digest = hashlib.sha256(f['payload'].encode('ascii')).hexdigest()
            nonce, until, pub, sig = f['nonce'], f['expires'], f['pub'], f['sig']
            rules.require(bool(HEX32.fullmatch(nonce) and social.MENU_EXP.fullmatch(until) and social.TOKEN.fullmatch(pub) and social.MENU_SIG.fullmatch(sig) and social.TOKEN.fullmatch(f['ticket'])), 'bad proof')
            expected = ticket(nonce, digest, until, peer)
            rules.require(bool(expected) and now <= int(until) <= now+social.MENU_TTL and hmac.compare_digest(f['ticket'], expected), 'proof expired or wrong peer')
            # tools/ed25519.py is pure Python, ~3.6 ms a verify: 1200/min is ~7% of a core,
            # enough for ~60 room members polling every 3 s.
            rules.require(ed is not None and d.rate_ok('all', now, 1200, 'party-verify'), 'proof unavailable')
            rules.require(ed.verify(bytes.fromhex(pub), (social.MENU_STATEMENT % (nonce, 'tournament', digest)).encode('ascii'), bytes.fromhex(sig)), 'invalid signature')
            db = d.get_db()
            with db:
                db.execute('BEGIN IMMEDIATE')
                account = db.execute('SELECT k.steamid,a.name FROM keylinks k JOIN accounts a USING(steamid) WHERE pub=? AND a.banned_at=0', (pub,)).fetchone()
                rules.require(account is not None, 'linked account required')
                sid = account['steamid']
                who, name = accounts.who_of(sid), accounts.game_name(account['name'])
                rules.require(d.rate_ok(sid, now, 120, 'party-account'), 'try again shortly')
                expire(db, now)
                active = db.execute('SELECT party FROM tournament_party_members WHERE account=?', (sid,)).fetchone()
                ident = active['party'] if data['id'] == '-' and active else data['id']
                row = db.execute('SELECT id,state FROM tournament_parties WHERE id=?', (ident,)).fetchone()
                try:
                    m = room_state(row) if row else None
                except ValueError:
                    raise rules.Refusal('That room is broken; it will be cleared shortly.')
                ticked = clock(m, now)
                if ticked:
                    # Kept even by a replayed request; a refused action rolls it back and the next poll redoes it.
                    m = ticked
                    db.execute('UPDATE tournament_parties SET state=? WHERE id=?', (d.game_json(m), row['id']))
                op = data['op']
                if op in ('create', 'configure', 'start'):
                    tournaments.require_hosting(d)
                old = db.execute('SELECT fingerprint FROM tournament_party_requests WHERE account=? AND request=?', (sid, data['request'])).fetchone()
                if old:
                    rules.require(old['fingerprint'] == digest, 'request reused with different action')
                    # Return current authorized state, never a cached launch capability.
                    if op == 'create' and active:
                        m = json.loads(db.execute('SELECT state FROM tournament_parties WHERE id=?', (active['party'],)).fetchone()['state'])
                    rules.require(m is None or any(p['who'] == who for p in m['players']), 'not a current member')
                    return response(result(db, m, sid, now))
                proof = hashlib.sha256((pub+nonce).encode()).hexdigest()
                db.execute('DELETE FROM tournament_party_proofs WHERE until<?', (now,))
                rules.require(not db.execute('SELECT 1 FROM tournament_party_proofs WHERE proof=?', (proof,)).fetchone(), 'proof replay')
                rules.require(enabled() or op in ('state', 'leave', 'cancel'), 'tournaments disabled')
                if op == 'create':
                    rules.require(active is None and data['id'] == '-' and data['revision'] == '0', 'already in a party or bad create')
                    rules.require(d.rate_ok(sid, now, 10, 'party-create'), 'try again shortly')
                    tournaments.map_pool(db, d, rules.settings(data))
                    m = rules.create(secrets.token_hex(16), '', name, '', who, name, data)
                    m.update(menu_phase='waiting')
                    m['_accounts'][who] = sid
                    db.execute('INSERT INTO tournament_parties VALUES(?,?,?)', (m['id'], d.game_json(m), now))
                    db.execute('INSERT INTO tournament_party_members VALUES(?,?,?)', (sid, m['id'], now))
                elif op == 'state':
                    rules.require(m is None or active is not None and active['party'] == m['id'], 'not a current member')
                else:
                    rules.require(m is not None, 'party not found')
                    # No revision check where churn could starve members: chat, join (as a spectator),
                    # leave, and ban/pick (the turn and card status already guard those).
                    rules.require(op in ('say', 'join', 'leave', 'ban', 'pick') or int(data['revision']) == m['revision'],
                                  'stale revision; resync')
                    if op == 'join':
                        # Any open room, even after launch: result() then hands the joiner the launch address.
                        rules.require(active is None and m['phase'] not in rules.TERMINAL, 'party closed or already joined')
                        rules.require(who not in m['_accounts'] or m['_accounts'][who] == sid, 'ambiguous account handle')
                        rules.require(who not in m.get('_kicked', ()), 'removed from this room')
                        rules.require(who in m['_accounts'] or len(m['_accounts']) < 256, 'account history full')
                        joins = m.setdefault('_joins', {})
                        rules.require(now >= joins.get(who, 0) + JOIN_COOLDOWN, 'try again shortly')
                        joins[who] = now
                        m = rules.transition(m, 'enter', who, name, data)
                        m['_accounts'][who] = sid
                        db.execute('INSERT INTO tournament_party_members VALUES(?,?,?)', (sid, m['id'], now))
                    else:
                        rules.require(active is not None and active['party'] == m['id'], 'not a current member')
                        rules.require(not m.get('menu_started') or op == 'leave', 'chat is closed' if op == 'say' else 'already started')
                        if op in ('configure', 'lock', 'start'):
                            rules.require_current_settings(m)
                        if op == 'kick':
                            target = next((p for p in m['players'] if p['who'] == data['target']), None)
                            rules.require(who == m['host'] and target is not None and target['who'] != who and
                                          (m['phase'] == 'lobby' or target['role'] == 'spectator'),
                                          'host removes competitors in the waiting room, spectators before launch')
                            m['players'] = [p for p in m['players'] if p['who'] != target['who']]
                            m.setdefault('_kicked', []).append(target['who'])
                            db.execute('DELETE FROM tournament_party_members WHERE account=? AND party=?',
                                       (m['_accounts'].get(target['who'], ''), m['id']))
                            # Only the removed player's state goes; the others keep their accepts (as seat).
                            m['revision'] += 1
                        elif op == 'say':
                            rules.require(d.rate_ok(sid, now, 20, 'party-say'), 'try again shortly')
                            m['chat_seq'] = m.get('chat_seq', 0) + 1
                            chat = m.setdefault('chat', [])
                            chat.append(dict(who=who, name=name, text=data['text'], at=now, seq=m['chat_seq']))
                            del chat[:-CHAT_KEEP]
                        elif op == 'leave' and m.get('menu_started'):
                            # Menu departure revokes handoff visibility, not live game ownership.
                            m['players'] = [p for p in m['players'] if p['who'] != who]
                            m['revision'] += 1
                            db.execute('DELETE FROM tournament_party_members WHERE account=?', (sid,))
                        elif op == 'ready':
                            rules.require(m['menu_phase'] == 'ready', 'draft required')
                            p = next(p for p in m['players'] if p['who'] == who)
                            rules.require(p['role'] == 'player', 'no competitor seat')
                            if p.get('menu_ready', 0) != int(data['value']):  # a re-send changes nothing
                                p['menu_ready'] = int(data['value'])
                                m['revision'] += 1
                        elif op == 'start':
                            rules.require(who == m['host'] and m['menu_phase'] == 'ready', 'host start after draft only')
                            for p in rules.competitors(m):
                                seen = db.execute('SELECT seen FROM tournament_party_members WHERE account=?', (m['_accounts'][p['who']],)).fetchone()
                                rules.require(p.get('menu_ready') and seen and now-ONLINE_TTL < seen['seen'] <= now, 'every competitor must be online and ready')
                            tournament_pool.revalidate(db, d, m)
                            # A default-profile node may sit at either kind's tick until it loads the round (P1639).
                            ticks = rules.node_ticks(m['settings']['profile'])
                            node = db.execute(('SELECT l.* FROM lobbies l JOIN tournament_nodes t ON t.node=l.node WHERE l.last_seen>? AND l.last_seen<=? AND t.seen>? AND t.seen<=? AND l.players=0 AND t.native_occupants=0 AND t.movement=? AND t.tick_us=t.clock_us AND t.tick_us IN (%s) AND l.maxplayers>=? AND NOT EXISTS(SELECT 1 FROM tournament_reservations r WHERE r.node=l.node) AND NOT EXISTS(SELECT 1 FROM assignments a WHERE a.node=l.node AND a.asked_at>=?) AND NOT EXISTS(SELECT 1 FROM lobby_handoffs h WHERE h.node=l.node AND h.until>=?) ORDER BY l.node LIMIT 1') % ','.join('?' * len(ticks)), (now-d.lobby_ttl, now, now-tournaments.CAP_TTL, now, rules.PROFILES[m['settings']['profile']]['movement'], *ticks, len(m['players']), now-d.assign_ttl, now)).fetchone()
                            rules.require(node is not None, 'no enabled empty fresh node')
                            rules.require(bool(re.fullmatch(r'[A-Za-z0-9.-]+:[0-9]{1,5}', node['addr'])) and 1 <= int(node['addr'].rsplit(':',1)[1]) <= 65535, 'unsafe node address')
                            m.update(node=node['node'], addr=node['addr'], menu_started=1, menu_phase='starting', revision=m['revision']+1)
                            rules.loading(m)
                            db.execute('INSERT INTO tournament_matches VALUES(?,?,?)', (m['id'], m['node'],
                                       d.game_json({k: v for k, v in m.items() if k not in ('chat', 'chat_seq')})))
                            db.execute('INSERT INTO tournament_reservations VALUES(?,?)', (m['node'], m['id']))
                        elif op == 'seat':
                            target = next((p for p in m['players'] if p['who'] == data['target']), None)
                            # Unseating also works in the draft and ready check (rules.transition returns to the lobby).
                            rules.require(target is not None and who == m['host'] and m['phase'] in ('lobby', 'draft', 'loading'),
                                          'host seat in waiting room only')
                            # A seat already in the asked role is a true no-op: no revision bump, readies kept.
                            if (target['role'] == 'player') != (data['value'] == '1'):
                                m = rules.transition(m, 'seat', who, name, data)
                                for p in m['players']:
                                    p['menu_ready'] = 0
                        else:
                            if op == 'configure':
                                tournaments.map_pool(db, d, rules.settings(data))
                            m = rules.transition(m, op, who, name, data, tournaments.map_pool(db, d, m['settings']) if op == 'lock' else ())
                            if op == 'leave':
                                db.execute('DELETE FROM tournament_party_members WHERE account=?', (sid,))
                    if m['phase'] in rules.TERMINAL:
                        m['menu_phase'] = 'cancelled'
                        db.execute('DELETE FROM tournament_party_members WHERE party=?', (m['id'],))
                    elif not m.get('menu_started'):
                        m['menu_phase'] = 'draft' if m['phase'] == 'draft' else 'ready' if m['phase'] == 'loading' else 'waiting'
                m = clock(m, now) or m  # stamps a turn this action began, clears it off the draft
                if m and m['phase'] in rules.TERMINAL:
                    db.execute('DELETE FROM tournament_parties WHERE id=?', (m['id'],))
                elif m:
                    db.execute('UPDATE tournament_parties SET state=?,touched=? WHERE id=?', (d.game_json(m), now, m['id']))
                    db.execute('UPDATE tournament_party_members SET seen=? WHERE account=? AND party=?', (now, sid, m['id']))
                db.execute('INSERT INTO tournament_party_proofs VALUES(?,?)', (proof, int(until)))
                if op not in ('state', 'say'):
                    db.execute('INSERT INTO tournament_party_requests VALUES(?,?,?)', (sid, data['request'], digest))
                    db.execute('DELETE FROM tournament_party_requests WHERE account=? AND rowid NOT IN '
                               '(SELECT rowid FROM tournament_party_requests WHERE account=? ORDER BY rowid DESC LIMIT ?)',
                               (sid, sid, JOURNAL_KEEP))
                return response(result(db, m, sid, now))
        except rules.Refusal as exc:
            return response(dict(ok=0, status='refused', error=str(exc)[:160], me=accounts.who_of(sid) if sid else '', party=None, launch=None))
        except sqlite3.Error:
            d.log.exception('party storage error')
            return response(dict(ok=0, status='storage', error='storage unavailable; retry same request', me='', party=None, launch=None))
