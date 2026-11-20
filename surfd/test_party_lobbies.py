"""Real Ed25519, synthetic linked accounts and isolated SQLite; no network."""
import hashlib
import importlib
import json
import os
from pathlib import Path
import random
import shutil
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode
from unittest.mock import patch
import test_tournaments as fixture

shutil.copyfile(Path(__file__).resolve().parents[1] / 'tools/ed25519.py', fixture.HOME / 'tools/ed25519.py')
S = importlib.reload(fixture.S)
import party_lobbies as P
import social
spec = importlib.util.spec_from_file_location('fixture_ed', fixture.HOME / 'tools/ed25519.py')
ED = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ED)


def tearDownModule():
    fixture.tearDownModule()


class PartyAPI(unittest.TestCase):
    heartbeat = fixture.API.heartbeat
    post = fixture.API.post

    def setUp(self):
        fixture.API.setUp(self)
        for table in ('tournament_parties', 'tournament_party_members', 'tournament_party_requests', 'tournament_party_proofs', 'lobby_handoffs'):
            self.db.execute('DELETE FROM '+table)
        self.seeds = [bytes([i+1])*32 for i in range(3)]
        self.pubs = [ED.publickey(seed).hex() for seed in self.seeds]
        self.db.execute('DELETE FROM keylinks')
        for i, pub in enumerate(self.pubs):
            self.db.execute('INSERT INTO keylinks(pub,steamid,linked_at) VALUES(?,?,?)', (pub, str(76561198000000001+i), self.now))
        self.db.commit()

    def tearDown(self):
        fixture.API.tearDown(self)

    def form(self, op, i=0, m=None, **fields):
        self.serial += 1
        data = dict(op=op, id=m['id'] if m else '-', revision=m['revision'] if m else 0,
                    request='%032x' % self.serial, capacity=2, round_seconds=60, target='-', map='-', value=0,
                    kind='surf', tiers=7, profile='default', pool='-', text='-')
        data.update(fields)
        payload = urlencode(data)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        ch = self.client.get('/api/tournament-lobbies/challenge?hash='+digest).get_json()
        self.assertEqual(ch['ok'], 1, ch)
        sig = ED.sign(self.seeds[i], (social.MENU_STATEMENT % (ch['nonce'], 'tournament', digest)).encode()).hex()
        return dict(payload=payload, nonce=ch['nonce'], expires=ch['expires'], ticket=ch['ticket'], pub=self.pubs[i], sig=sig)

    def send(self, form, client=None):
        return (client or self.client).post('/api/tournament-lobbies/action', data=form).get_json()

    def act(self, op, i=0, m=None, **fields):
        out = self.send(self.form(op, i, m, **fields))
        self.assertEqual(out['ok'], 1, out)
        return out

    def drafted(self, **settings):
        m = self.act('create', **settings)['party']
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_reservations').fetchone()[0], 0)
        m = self.act('join', 1, m)['party']
        m = self.act('seat', 0, m, target=self.whos[1], value=1)['party']
        m = self.act('accept', 0, m)['party']
        m = self.act('accept', 1, m)['party']
        m = self.act('lock', 0, m)['party']
        while m['phase'] == 'draft':
            i = self.whos.index(m['turn_who'])
            m = self.act(m['turn_kind'], i, m, map=next(c['name'] for c in m['maps'] if c['status']=='pool'))['party']
        self.assertEqual((m['menu_phase'], m['round_index'], m['generation']), ('ready', 1, 1))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_matches').fetchone()[0], 0)
        return m

    def ready(self, **settings):
        m = self.drafted(**settings)
        for i in (0,1):
            out = self.act('ready', i, m, value=1)
            self.assertIsNone(out['launch'])
            m = out['party']
        return m

    def test_mainmenu_draft_nodezero_same_launch_and_allocator_exclusion(self):
        m = self.ready()
        out = self.act('start', 0, m)
        launch = out['launch']
        self.assertTrue(launch)
        self.assertEqual(self.act('state', 1)['launch'], launch)
        self.assertEqual(self.send(self.form('state', 2, m))['ok'], 0)
        live = json.loads(self.db.execute('SELECT state FROM tournament_matches').fetchone()[0])
        self.assertEqual((live['phase'], live['round_index'], live['generation'], live['menu_started']), ('loading', 1, 1, 1))
        self.assertEqual(live['schedule'], m['schedule'])
        self.assertEqual(self.client.get('/api/join?map=surf_b').status_code, 503)
        self.assertEqual(self.client.get('/api/tournaments').get_json()['rows'], [])
        public = json.dumps(self.client.get('/api/tournament-lobbies').get_json())
        for secret in ('76561198', '_accounts', 'addr', '127.0.0.1', 'launch'):
            self.assertNotIn(secret, public)
        self.now += P.IDLE_TTL+1
        self.act('state', 0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_reservations').fetchone()[0], 1)

    def test_signature_tamper_unlinked_forgedhost_expiry_peer(self):
        form = self.form('create')
        bad = dict(form, payload=form['payload'].replace('capacity=2', 'capacity=3'))
        self.assertEqual(self.send(bad)['ok'], 0)
        self.assertEqual(self.send(dict(form, sig='0'*128))['ok'], 0)
        self.assertEqual(self.client.post('/api/tournament-lobbies/action', data=form, environ_base={'REMOTE_ADDR':'192.0.2.1'}).get_json()['ok'], 0)
        self.now += 31
        self.assertEqual(self.send(form)['ok'], 0)
        m = self.act('create')['party']
        m = self.act('join', 1, m)['party']
        self.assertEqual(self.send(self.form('cancel', 1, m))['ok'], 0)
        self.db.execute('DELETE FROM keylinks WHERE pub=?', (self.pubs[1],))
        self.db.commit()
        self.assertEqual(self.send(self.form('state', 1, m))['ok'], 0)

    def test_persisted_alpha_room_refuses_settings_but_keeps_recovery(self):
        m = self.act('create')['party']
        self.act('join', 1, m)  # Successful current-protocol positive control.
        m = json.loads(self.db.execute('SELECT state FROM tournament_parties').fetchone()[0])
        for key in ('settings', 'ruleset_id', '_pins', '_zonegen'):
            m.pop(key)
        saved = S.game_json(m)
        self.db.execute('UPDATE tournament_parties SET state=? WHERE id=?', (saved,m['id']))
        self.db.commit()
        for op in ('configure', 'lock', 'start'):
            out = self.send(self.form(op, m=m))
            self.assertEqual((out['ok'], out['status']), (0,'refused'))
            self.assertIn('Pre-Beta', out['error'])
            self.assertEqual(self.db.execute('SELECT state FROM tournament_parties').fetchone()[0], saved)
            self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_reservations').fetchone()[0], 0)
        state = self.act('state')['party']
        self.assertNotIn('settings', state)
        state = self.act('leave', 1, state)['party']
        self.assertEqual(len(state['players']), 1)
        state = self.act('cancel', m=state)['party']
        self.assertEqual(state['phase'], 'cancelled')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_party_members').fetchone()[0], 0)
        self.assertIn('settings', self.act('create')['party'])

    def test_strict_fourteen_field_parser(self):
        payload = self.form('create')['payload']
        for bad in (payload+'&op=create', payload.replace('value=0','unknown=0'),
                    payload.replace('&value=0',''), payload.replace('target=-','target=%FF'),
                    payload.replace('map=-','map=%ZZ'), payload.replace('revision=0','revision=-1'),
                    '&'.join(payload.split('&')[:9]), payload.replace('kind=surf', 'kind=race'),
                    payload.replace('tiers=7','tiers=07'), payload.replace('profile=default','profile=ag'),
                    payload.replace('capacity=2','capacity=02'), payload.replace('pool=-','pool=surf_a,surf_a'),
                    payload.replace('&text=-', ''), payload.replace('text=-', 'text=hello'),
                    payload.replace('tiers=7', 'tiers=2048'), payload.replace('tiers=7', 'tiers=2097151')):
            with self.assertRaises(P.rules.Refusal):
                P.parse_payload(bad)
        self.assertEqual(P.parse_payload(payload)['op'], 'create')

    def test_room_chat(self):
        m = self.act('create')['party']
        m = self.act('join', 1, m)['party']
        revision = m['revision']
        # Chat ignores the revision (no race with roster edits) and does not bump it.
        out = self.act('say', 1, dict(m, revision=1), text='glhf \u00e9')['party']
        self.assertEqual(out['revision'], revision)
        self.assertEqual([(c['who'], c['text'], c['seq']) for c in out['chat']], [(self.whos[1], 'glhf \u00e9', 1)])
        for bad in ('', ' padded', 'x' * 201, 'tab\there', '-'):
            refused = self.send(self.form('say', 0, m, text=bad))
            self.assertEqual(refused['ok'], 0, bad)
        keep, P.CHAT_KEEP = P.CHAT_KEEP, 4
        try:
            for i in range(7):
                m = self.act('say', i % 2, m, text='line %d' % i)['party']
        finally:
            P.CHAT_KEEP = keep
        self.assertEqual([c['text'] for c in m['chat']], ['line 3', 'line 4', 'line 5', 'line 6'])
        self.assertEqual(m['chat'][-1]['seq'], 8)
        self.assertNotIn('chat', self.client.get('/api/tournament-lobbies?brief=1').get_json()['rows'][0])
        full = self.client.get('/api/tournament-lobbies').get_json()['rows'][0]
        self.assertNotIn('chat', full)
        self.assertFalse(any('menu_online' in p for p in full['players']))
        stranger = self.send(self.form('say', 2, m, text='hi'))
        self.assertEqual(stranger['ok'], 0)

    def test_replay_idempotency_cas_and_current_membership(self):
        f = self.form('create')
        m = self.send(f)['party']
        self.now += 5
        self.assertEqual(self.send(f)['party']['id'], m['id'])
        self.assertEqual(self.db.execute('SELECT touched FROM tournament_parties').fetchone()[0], self.now-5)
        self.assertEqual(self.send(self.form('create'))['ok'], 0)
        stale = m
        m = self.act('join', 1, m)['party']
        self.assertEqual(self.send(self.form('accept', 0, stale))['ok'], 0)
        m = self.act('leave', 1, m)['party']
        self.assertEqual(self.send(self.form('state', 1, m))['ok'], 0)
        self.now += P.IDLE_TTL+1
        self.assertIsNone(self.act('state')['party'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_reservations').fetchone()[0], 0)

    def test_occupied_disabled_stale_no_node_pending_refuse(self):
        m = self.ready()
        for sql in ('UPDATE lobbies SET players=1', 'UPDATE tournament_nodes SET native_occupants=1', 'UPDATE tournament_nodes SET seen=0', 'DELETE FROM tournament_nodes', "INSERT INTO assignments VALUES('n1','surf_b','surf_b',2000000000,'fixture')"):
            self.db.execute(sql)
            self.db.commit()
            self.assertEqual(self.send(self.form('start', 0, m))['ok'], 0, sql)
            self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_matches').fetchone()[0], 0)
            self.db.execute('DELETE FROM assignments')
            self.db.commit()
            self.heartbeat()
            self.post('state', enabled=1, occupants=0)
        with patch.dict(os.environ, SURFD_TOURNAMENTS='0'):
            self.assertEqual(self.send(self.form('start', 0, m))['ok'], 0)
        self.now += P.ONLINE_TTL+1
        self.assertEqual(self.send(self.form('start', 0, m))['ok'], 0)

    def locked(self):
        m = self.act('create')['party']
        m = self.act('join', 1, m)['party']
        m = self.act('join', 2, m)['party']
        m = self.act('seat', 0, m, target=self.whos[1], value=1)['party']
        m = self.act('accept', 0, m)['party']
        m = self.act('accept', 1, m)['party']
        return self.act('lock', 0, m)['party']

    def test_p1650_leave_in_draft_or_ready_check_returns_room_to_lobby(self):
        m = self.locked()
        name = m['players'][1]['name']
        out = self.act('leave', 1, m)['party']
        self.assertEqual((out['phase'], out['menu_phase'], out['maps'], out['schedule']), ('lobby', 'waiting', [], []))
        self.assertEqual([(p['who'], p['accepted']) for p in out['players']], [(self.whos[0], 1), (self.whos[2], 0)])
        self.assertEqual(out['note'], '%s left: back to the lobby. The host can start the draft again.' % name)
        self.assertIsNone(self.act('state', 1)['party'])
        self.act('cancel', 0, out)
        m = self.ready()
        out = self.act('leave', 1, m)['party']
        self.assertEqual((out['phase'], out['menu_phase'], out['round_index']), ('lobby', 'waiting', 0))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_matches').fetchone()[0], 0)

    def test_p1650_host_unseats_in_draft_and_ready_check(self):
        m = self.locked()
        # A spectator cannot be seated mid-draft.
        self.assertEqual(self.send(self.form('seat', 0, m, target=self.whos[2], value=1))['ok'], 0)
        out = self.act('seat', 0, m, target=self.whos[1], value=0)['party']
        self.assertEqual((out['phase'], out['menu_phase'], out['maps']), ('lobby', 'waiting', []))
        self.assertEqual([(p['role'], p['accepted']) for p in out['players']], [('player', 1), ('spectator', 0), ('spectator', 0)])
        self.assertEqual(self.act('state', 1)['party']['id'], m['id'])
        self.act('cancel', 0, out)
        m = self.ready()
        out = self.act('seat', 0, m, target=self.whos[1], value=0)['party']
        self.assertEqual((out['phase'], out['menu_phase']), ('lobby', 'waiting'))
        self.assertTrue(all(p.get('menu_ready', 0) == 0 for p in out['players']))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_matches').fetchone()[0], 0)

    def raw(self):
        return json.loads(self.db.execute('SELECT state FROM tournament_parties').fetchone()[0])

    def test_p1650_draft_turn_clock_bans_then_picks_for_idle_players(self):
        m = self.locked()
        self.assertEqual((self.raw()['_turn_at'], m['turn_left']), ([0, self.now], 45))
        first = m['turn_who']
        name = next(p['name'] for p in m['players'] if p['who'] == first)
        self.now += 44
        self.assertEqual(self.act('state', 2)['party']['revision'], m['revision'])
        self.now += 1
        expected = random.Random('%s:clock:0' % self.raw()['_seed']).choice(
            sorted(c['name'] for c in m['maps'] if c['status'] == 'pool'))
        out = self.act('state', 2)['party']
        self.assertEqual([(c['name'], c['by']) for c in out['maps'] if c['status'] == 'banned'], [(expected, first)])
        self.assertEqual(out['note'], '%s ran out of time; a map was banned for them.' % name)
        self.assertEqual((out['revision'], out['turn_left']), (m['revision'] + 1, 45))
        self.assertNotEqual(out['turn_who'], first)
        self.assertEqual(self.act('state', 0)['party']['revision'], out['revision'])
        notes = []
        while out['phase'] == 'draft':
            self.now += 45
            out = self.act('state', 2)['party']
            notes.append(out['note'])
        self.assertIn('ran out of time; a map was picked for them.', notes[-1])
        self.assertEqual((out['phase'], out['menu_phase'], len(out['schedule'])), ('loading', 'ready', 1))
        self.assertEqual(sum(c['status'] == 'banned' for c in out['maps']), 2)
        self.assertNotIn('_turn_at', self.raw())
        self.assertNotIn('turn_left', out)

    def test_p1650_draft_turn_clock_applies_once_under_concurrent_polls_and_browse(self):
        m = self.locked()
        self.now += 45
        forms = [self.form('state', 0), self.form('state', 1)]
        def run(f):
            with S.app.test_client() as client:
                return self.send(f, client)['ok']
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertEqual(list(executor.map(run, forms)), [1, 1])
        raw = self.raw()
        self.assertEqual((raw['revision'], raw['_turn'], sum(c['status'] == 'banned' for c in raw['maps'])), (m['revision'] + 1, 1, 1))
        # The public directory poll drives the clock too.
        self.now += 45
        row = self.client.get('/api/tournament-lobbies?brief=1').get_json()['rows'][0]
        self.assertEqual((row['revision'], self.raw()['_turn']), (m['revision'] + 2, 2))
        # A room drafted before the clock existed starts its clock on first sight, not with a move.
        legacy = self.raw()
        legacy.pop('_turn_at')
        self.db.execute('UPDATE tournament_parties SET state=?', (json.dumps(legacy),))
        self.db.commit()
        self.now += 300
        self.assertEqual(self.act('state', 0)['party']['revision'], legacy['revision'])
        self.assertEqual(self.raw()['_turn_at'], [2, self.now])

    def test_p1650_draft_clock_skips_a_room_it_cannot_move(self):
        m = self.locked()
        odd = self.raw()
        odd['turn_who'] = ''
        self.db.execute('UPDATE tournament_parties SET state=?', (json.dumps(odd),))
        self.db.commit()
        self.now += 45
        self.assertEqual(self.client.get('/api/tournament-lobbies?brief=1').status_code, 200)
        self.assertEqual(self.act('state', 1)['party']['revision'], m['revision'])
        self.assertEqual(self.act('leave', 1, m)['party']['phase'], 'lobby')

    def test_p1650_join_open_room_as_spectator_any_phase_and_learn_launch(self):
        m = self.act('create')['party']
        m = self.act('join', 1, m)['party']
        m = self.act('seat', 0, m, target=self.whos[1], value=1)['party']
        m = self.act('accept', 0, m)['party']
        m = self.act('accept', 1, m)['party']
        m = self.act('lock', 0, m)['party']
        # Joining needs no current revision and never takes a seat.
        out = self.act('join', 2, dict(m, revision=1))['party']
        self.assertEqual((out['phase'], out['players'][-1]['who'], out['players'][-1]['role']), ('draft', self.whos[2], 'spectator'))
        m = self.act('leave', 2, out)['party']
        while m['phase'] == 'draft':
            i = self.whos.index(m['turn_who'])
            m = self.act(m['turn_kind'], i, m, map=next(c['name'] for c in m['maps'] if c['status'] == 'pool'))['party']
        for i in (0, 1):
            m = self.act('ready', i, m, value=1)['party']
        host = self.act('start', 0, m)
        self.now += P.JOIN_COOLDOWN
        late = self.act('join', 2, dict(m, revision=1))
        self.assertEqual(late['party']['players'][-1]['role'], 'spectator')
        self.assertEqual(late['launch'], host['launch'])
        self.assertEqual(self.act('state', 2)['launch']['addr'], host['launch']['addr'])

    def test_p1650_leave_ban_pick_skip_the_revision_check(self):
        m = self.locked()
        stale = dict(m, revision=1)
        i = self.whos.index(m['turn_who'])
        out = self.act('ban', i, stale, map=next(c['name'] for c in m['maps'] if c['status'] == 'pool'))['party']
        self.assertEqual(out['revision'], m['revision'] + 1)
        # The turn still guards ban/pick: the same stale request from the wrong player is refused.
        self.assertEqual(self.send(self.form('ban', i, stale, map=next(c['name'] for c in out['maps'] if c['status'] == 'pool')))['error'], 'not your draft turn')
        self.assertEqual(self.send(self.form('seat', 0, stale, target=self.whos[1], value=0))['error'], 'stale revision; resync')
        self.assertEqual(self.act('leave', 2, stale)['party']['revision'], out['revision'] + 1)

    def test_p1650_join_cooldown_per_account_per_room(self):
        m = self.act('create')['party']
        m = self.act('join', 1, m)['party']
        m = self.act('leave', 1, m)['party']
        self.assertEqual(self.send(self.form('join', 1, m))['error'], 'try again shortly')
        self.act('join', 2, m)
        self.now += P.JOIN_COOLDOWN
        self.assertEqual(self.act('join', 1, m)['party']['players'][-1]['who'], self.whos[1])

    def test_p1650_host_kicks_spectators_before_launch(self):
        m = self.locked()
        self.assertEqual(self.send(self.form('kick', 0, m, target=self.whos[1]))['ok'], 0)
        out = self.act('kick', 0, m, target=self.whos[2])['party']
        self.assertEqual((out['phase'], [p['who'] for p in out['players']]), ('draft', self.whos[:2]))
        self.assertIsNone(self.act('state', 2)['party'])
        self.act('cancel', 0, out)
        m = self.ready()
        m = self.act('join', 2, m)['party']
        self.assertEqual(self.act('kick', 0, m, target=self.whos[2])['party']['phase'], 'loading')

    def test_host_kick_removes_and_bars_rejoin(self):
        m = self.act('create')['party']
        m = self.act('join', 1, m)['party']
        self.assertEqual(self.send(self.form('kick', 1, m, target=self.whos[0]))['ok'], 0)
        self.assertEqual(self.send(self.form('kick', 0, m, target=self.whos[0]))['ok'], 0)
        m = self.act('kick', 0, m, target=self.whos[1])['party']
        self.assertEqual([p['who'] for p in m['players']], [self.whos[0]])
        self.assertIsNone(self.act('state', 1)['party'])
        self.assertEqual(self.send(self.form('join', 1, m))['ok'], 0)

    def test_journal_keeps_per_account_and_retires_closed_rooms(self):
        m = self.act('create')['party']
        keep, P.JOURNAL_KEEP = P.JOURNAL_KEEP, 3
        try:
            for _ in range(6):
                m = self.act('configure', 0, m, round_seconds=60 + 60 * (m['round_seconds'] == 60))['party']
        finally:
            P.JOURNAL_KEEP = keep
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_party_requests').fetchone()[0], 3)
        self.act('say', 0, m, text='hi')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_party_requests').fetchone()[0], 3)
        self.act('cancel', 0, m)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_parties').fetchone()[0], 0)

    def test_launch_waits_for_round_map_arrival(self):
        m = self.ready()
        launch = self.act('start', 0, m)['launch']
        self.assertEqual(launch['ready'], 0)
        live = json.loads(self.db.execute('SELECT state FROM tournament_matches').fetchone()[0])
        live['_arrived'] = 1
        self.db.execute('UPDATE tournament_matches SET state=?', (json.dumps(live),))
        self.db.commit()
        self.assertEqual(self.act('state', 1)['launch']['ready'], 1)

    def test_concurrent_start_and_retry(self):
        m = self.ready()
        forms = [self.form('start', 0, m), self.form('start', 0, m)]
        def run(f):
            with S.app.test_client() as client:
                return self.send(f, client)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(run, forms))
        self.assertEqual(sorted(r['ok'] for r in results), [0,1])
        winner = next(i for i,r in enumerate(results) if r['ok'])
        self.assertEqual(self.send(forms[winner])['launch'], results[winner]['launch'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_matches').fetchone()[0], 1)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_reservations').fetchone()[0], 1)
        joined = self.act('state', 1)['party']
        previous = self.form('state', 1, joined)
        self.assertTrue(self.send(previous)['launch'])
        self.act('leave', 1, joined)
        self.assertTrue(self.send(forms[winner])['launch'])
        self.assertEqual(self.send(previous)['ok'], 0)
        self.assertEqual(self.act('state', 1)['launch'], None)
        self.assertEqual(json.loads(self.db.execute('SELECT state FROM tournament_matches').fetchone()[0])['phase'], 'loading')

    def test_concurrent_create_one_active_party(self):
        forms = [self.form('create'), self.form('create')]
        def run(f):
            with S.app.test_client() as client:
                return self.send(f, client)['ok']
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertEqual(sorted(executor.map(run, forms)), [0,1])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_parties').fetchone()[0], 1)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_matches').fetchone()[0], 0)

    @patch.dict(os.environ, SURFD_TOURNAMENT_HOLD='0')  # ordinary joins may reach the tournament node
    def test_concurrent_start_ordinary_allocator_exclusion(self):
        m = self.ready()
        form = self.form('start', 0, m)
        def run(kind):
            with S.app.test_client() as client:
                if kind == 'start':
                    return self.send(form, client)['ok']
                return client.get('/api/join?map=surf_b').status_code
        with ThreadPoolExecutor(max_workers=2) as executor:
            start, ordinary = list(executor.map(run, ('start','ordinary')))
        self.assertIn((start, ordinary), ((1,503), (0,200)))
        reservations = self.db.execute('SELECT COUNT(*) FROM tournament_reservations').fetchone()[0]
        assignments = self.db.execute('SELECT COUNT(*) FROM assignments').fetchone()[0]
        self.assertEqual(reservations+assignments, 1)

    @patch.dict(os.environ, SURFD_TOURNAMENT_HOLD='0')  # ordinary joins may reach the tournament node
    def test_same_map_handoff_blocks_start_across_empty_heartbeat(self):
        m = self.ready()
        ordinary = self.client.get('/api/join?map=surf_alpha')
        self.assertEqual(ordinary.status_code, 200)
        self.assertEqual(ordinary.get_json()['why'], 'already running')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM assignments').fetchone()[0], 0)
        self.assertEqual(self.send(self.form('start', 0, m))['ok'], 0)
        self.heartbeat(players=0)
        self.post('state', enabled=1, occupants=0)
        self.assertEqual(self.send(self.form('start', 0, m))['ok'], 0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_matches').fetchone()[0], 0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_reservations').fetchone()[0], 0)
        # Handoff exclusion is finite, independent of empty heartbeat/assignment ACK.
        self.now += S.ASSIGN_TTL+1
        self.heartbeat()
        self.post('state', enabled=1, occupants=0)
        for i in (0,1):
            m = self.act('state', i)['party']
        self.assertTrue(self.act('start', 0, m)['launch'])

    @patch.dict(os.environ, SURFD_TOURNAMENT_HOLD='0')  # ordinary joins may reach the tournament node
    def test_map_change_handoff_survives_assignment_ack(self):
        m = self.ready()
        first = self.client.get('/api/join?map=surf_b')
        self.assertEqual((first.status_code, first.get_json()['why']), (200, 'starting'))
        # Loading reuse also renews the ordinary client's arrival window.
        self.now += 1
        second = self.client.get('/api/join?map=surf_b')
        self.assertEqual((second.status_code, second.get_json()['why']), (200, 'loading'))
        self.assertEqual(self.db.execute('SELECT until FROM lobby_handoffs').fetchone()[0], self.now+S.ASSIGN_TTL)
        self.heartbeat(mapname='surf_b', players=0)
        self.post('state', enabled=1, occupants=0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM assignments').fetchone()[0], 0)
        self.assertEqual(self.send(self.form('start', 0, m))['ok'], 0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_reservations').fetchone()[0], 0)

    def same_map_concurrent_order(self, first):
        m = self.ready()
        form = self.form('start', 0, m)
        held, attempted, release = threading.Event(), threading.Event(), threading.Event()
        join_lobby, loading = S._join_lobby, P.rules.loading
        def pause():
            held.set()
            if not release.wait(10):
                raise AssertionError('timed out holding first transaction')
        def join_held(*args):
            if first == 'join':
                pause()
            return join_lobby(*args)
        def loading_held(*args):
            if first == 'start':
                pause()
            return loading(*args)
        def run(kind, second=False):
            with S.app.test_client() as client:
                if second:
                    attempted.set()
                if kind == 'start':
                    return self.send(form, client)['ok']
                return client.get('/api/join?map=surf_alpha').status_code
        with patch.object(S, '_join_lobby', join_held), patch.object(P.rules, 'loading', loading_held):
            with ThreadPoolExecutor(max_workers=2) as executor:
                one = executor.submit(run, first)
                try:
                    self.assertTrue(held.wait(10), 'first transaction did not acquire lock')
                    two = executor.submit(run, 'start' if first == 'join' else 'join', True)
                    self.assertTrue(attempted.wait(10), 'second request did not begin')
                finally:
                    release.set()
                self.assertEqual((one.result(), two.result()), (200,0) if first == 'join' else (1,503))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_matches').fetchone()[0], int(first == 'start'))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_reservations').fetchone()[0], int(first == 'start'))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM lobby_handoffs').fetchone()[0], int(first == 'join'))

    @patch.dict(os.environ, SURFD_TOURNAMENT_HOLD='0')  # ordinary joins may reach the tournament node
    def test_concurrent_same_map_join_transaction_first(self):
        self.same_map_concurrent_order('join')

    @patch.dict(os.environ, SURFD_TOURNAMENT_HOLD='0')  # ordinary joins may reach the tournament node
    def test_concurrent_same_map_start_transaction_first(self):
        self.same_map_concurrent_order('start')

    def test_terminal_match_retires_from_browse_and_preserves_reservation(self):
        m = self.act('start', 0, self.ready())['party']
        aborted = self.post('abort', id=m['id'], revision=m['revision'], epoch=m['epoch'])
        self.assertEqual(aborted['ok'], 1, aborted)
        self.assertEqual(self.client.get('/api/tournament-lobbies').get_json()['rows'], [])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_party_members').fetchone()[0], 0)
        # The closed room's row is gone at once; the match and its reservation stay for release.
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_parties').fetchone()[0], 0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_matches').fetchone()[0], 1)
        self.assertIsNone(self.act('state')['party'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_reservations').fetchone()[0], 1)
        released = self.post('release', id=m['id'], revision=aborted['match']['revision'], epoch=m['epoch'], restored=1)
        self.assertEqual(released['ok'], 1, released)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_reservations').fetchone()[0], 0)

    def test_directory_filters_history_before_limit(self):
        active = self.act('create')['party']
        active_id = 'f'*32
        self.db.execute('UPDATE tournament_parties SET id=? WHERE id=?', (active_id, active['id']))
        raw = json.loads(self.db.execute('SELECT state FROM tournament_parties').fetchone()[0])
        raw['id'] = active_id
        self.db.execute('UPDATE tournament_parties SET state=? WHERE id=?', (json.dumps(raw), active_id))
        self.db.execute('UPDATE tournament_party_members SET party=?', (active_id,))
        for i in range(200):
            historical = dict(raw, id='%032x' % i, phase='cancelled' if i % 2 else 'lobby')
            self.db.execute('INSERT INTO tournament_parties VALUES(?,?,?)', (historical['id'], json.dumps(historical), self.now-P.IDLE_TTL-1))
        self.db.commit()
        rows = self.client.get('/api/tournament-lobbies').get_json()['rows']
        self.assertEqual([r['id'] for r in rows], [active_id])
        for i in range(201):
            extra = dict(raw, id='e%031x' % i)
            self.db.execute('INSERT INTO tournament_parties VALUES(?,?,?)', (extra['id'], json.dumps(extra), self.now))
        self.db.commit()
        rows = self.client.get('/api/tournament-lobbies').get_json()['rows']
        self.assertEqual(len(rows), 200)
        self.assertTrue(all(r['phase'] == 'lobby' for r in rows))

    def test_brief_directory_bounds_200_full_rosters_and_carries_join_revision(self):
        first = self.act('create')['party']
        original = self.client.get('/api/tournament-lobbies').get_json()['rows'][0]
        self.assertIn('players', original)  # Existing full representation unchanged.
        raw = json.loads(self.db.execute('SELECT state FROM tournament_parties').fetchone()[0])
        raw['players'] = [dict(raw['players'][0], who=('%012x' % (i+1)),
                               name='\U0001f642'*64, role='player' if i < 8 else 'spectator') for i in range(72)]
        raw['players'][0]['who'] = raw['host']
        raw['capacity'] = 8
        self.db.execute('DELETE FROM tournament_parties')
        for i in range(200):
            room = dict(raw, id='%032x' % (i+1))
            self.db.execute('INSERT INTO tournament_parties VALUES(?,?,?)', (room['id'], json.dumps(room), self.now))
        self.db.commit()
        response = self.client.get('/api/tournament-lobbies?brief=1')
        rows = response.get_json()['rows']
        self.assertEqual(len(rows), 200)
        self.assertLess(len(response.data), 131072)
        for row in rows:
            self.assertEqual(set(row), {'id','host','name','capacity','phase','revision','members'})
            self.assertEqual((row['revision'], row['members'], row['capacity']), (first['revision'], 72, 8))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_matches').fetchone()[0], 0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_reservations').fetchone()[0], 0)

    def test_default_off_and_no_start_before_draft_or_readiness(self):
        with patch.dict(os.environ):
            os.environ.pop('SURFD_TOURNAMENTS', None)
            self.assertEqual(self.client.get('/api/tournament-lobbies').get_json()['enabled'], 0)
            self.assertEqual(self.send(self.form('create'))['ok'], 0)
        m = self.act('create')['party']
        self.assertEqual(self.send(self.form('start', 0, m))['ok'], 0)
        self.act('cancel', 0, m)
        m = self.drafted()
        self.assertEqual(self.send(self.form('start', 0, m))['ok'], 0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_reservations').fetchone()[0], 0)

    def test_configure_host_only_invalidates_and_nonconfig_fields_never_overwrite(self):
        m = self.act('create')['party']
        self.assertEqual(m['settings'], dict(kind='surf',tiers=7,profile='default',tick_us=15000,pool=None))
        m = self.act('join', 1, m)['party']
        m = self.act('seat', 0, m, target=self.whos[1], value=1)['party']
        m = self.act('accept', 0, m)['party']
        m = self.act('accept', 1, m)['party']
        self.assertEqual(self.send(self.form('configure', 1, m, capacity=3))['ok'], 0)
        changed = self.act('configure', 0, m, capacity=3, round_seconds=90, tiers=15, pool='_')['party']
        self.assertEqual((changed['capacity'], changed['round_seconds'], changed['settings']['tiers'], changed['settings']['pool']), (3,90,15,[]))
        self.assertTrue(all(p['accepted'] == p['ready'] == p['menu_ready'] == 0 for p in changed['players']))
        read = self.act('state', 0, changed, kind='bhop', profile='ag-100')['party']
        self.assertEqual(read['settings'], changed['settings'])
        self.assertEqual((read['capacity'],read['round_seconds']), (3,90))
        for i in (0,1):
            changed = self.act('accept', i, changed)['party']
        self.assertEqual(self.send(self.form('lock', 0, changed))['ok'], 0)
        changed = self.act('configure', 0, changed)['party']
        for i in (0,1):
            changed = self.act('accept', i, changed)['party']
        changed = self.act('lock', 0, changed)['party']
        self.assertEqual(self.send(self.form('configure', 0, changed))['ok'], 0)

    def test_read_state_does_not_fill_mutation_journal_and_proof_replay_still_refuses(self):
        m = self.act('create')['party']
        for _ in range(130):
            self.now += 2
            m = self.act('state', 0, m)['party']
        # Reads are never journaled; mutations are kept per account (JOURNAL_KEEP), with no shared cap to fill.
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_party_requests').fetchone()[0], 1)
        self.assertEqual(self.send(self.form('accept', 0, m))['ok'], 1)
        f = self.form('state', 0, m)
        self.assertEqual(self.send(f)['ok'], 1)
        self.assertEqual(self.send(f)['ok'], 0)

    def test_unknown_paid_policy_all_host_entrypoints_fail_closed_but_leave_cancel_work(self):
        form = self.form('create')
        m = self.send(form)['party']
        with patch.dict(os.environ, SURFD_TOURNAMENT_ACCESS='paid'):
            for f in (form, self.form('create', 1), self.form('configure', 0, m)):
                self.assertEqual(self.send(f)['ok'], 0)
            m = self.act('join', 1, m)['party']
            m = self.act('leave', 1, m)['party']
            self.act('cancel', 0, m)
        m = self.ready()
        with patch.dict(os.environ, SURFD_TOURNAMENT_ACCESS='paid'):
            self.assertEqual(self.send(self.form('start', 0, m))['ok'], 0)
        for table in ('tournament_matches','tournament_reservations'):
            self.assertEqual(self.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0], 0)
        self.assertTrue(self.act('start', 0, m)['launch'])

    def test_start_revalidates_reserve_pin_and_held_stamp_atomically(self):
        m = self.ready()
        raw_before = self.db.execute('SELECT state FROM tournament_parties').fetchone()[0]
        sessions = [tuple(r) for r in self.db.execute('SELECT * FROM social_sessions')]
        path = fixture.HOME / 'qualifications.json'
        registry = json.loads(path.read_text())
        reserve = m['reserve']
        original = registry['maps'][reserve]['default']['zonepin']
        registry['maps'][reserve]['default']['zonepin'] = 'f'*64
        path.write_text(json.dumps(registry))
        self.assertEqual(self.send(self.form('start', 0, m))['ok'], 0)
        self.assertEqual(self.db.execute('SELECT state FROM tournament_parties').fetchone()[0], raw_before)
        self.assertEqual([tuple(r) for r in self.db.execute('SELECT * FROM social_sessions')], sessions)
        for table in ('tournament_matches','tournament_reservations'):
            self.assertEqual(self.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0], 0)
        registry['maps'][reserve]['default']['zonepin'] = original
        path.write_text(json.dumps(registry))
        # A changed held stat is independently refused without hash work on HTTP.
        bsp = fixture.HOME / 'maps' / (reserve+'.bsp')
        before = bsp.read_bytes()
        bsp.write_bytes(before+b'change')
        self.assertEqual(self.send(self.form('start', 0, m))['ok'], 0)
        bsp.write_bytes(before)
        # Restoration changes ctime; only an explicit fresh synthetic approval may qualify again.
        registry['maps'][reserve]['default'].update(fixture.pin_for(reserve))
        path.write_text(json.dumps(registry))
        # Frozen stamp differs; restoring content alone must not revive this draft.
        self.assertEqual(self.send(self.form('start', 0, m))['ok'], 0)

    def test_default_node_at_either_kind_tick_is_selected_p1639(self):
        m = self.ready()
        # A default-profile node that last loaded a bhop map (100 Hz) still hosts; a split tick/clock does not.
        self.post('state', enabled=1, occupants=0, movement='default', tick_us=10000, clock_us=15000)
        self.assertEqual(self.send(self.form('start', 0, m))['ok'], 0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_reservations').fetchone()[0], 0)
        self.post('state', enabled=1, occupants=0, movement='default', tick_us=10000, clock_us=10000)
        self.assertTrue(self.act('start', 0, m)['launch'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM tournament_reservations').fetchone()[0], 1)

    def test_preconfigured_profile_empty_node_selection_and_frozen_pins_copy(self):
        path = fixture.HOME / 'qualifications.json'
        registry = json.loads(path.read_text())
        for profiles in registry['maps'].values():
            profiles['ag-1000'] = dict(profiles['default'])
        path.write_text(json.dumps(registry))
        m = self.ready(profile='ag-1000')
        self.assertEqual(m['settings']['profile'], 'ag-1000')
        for sql in ("UPDATE tournament_nodes SET movement=''", "UPDATE tournament_nodes SET movement='default'",
                    "UPDATE tournament_nodes SET movement='ag1000-v1',tick_us=15000,clock_us=1000",
                    "UPDATE tournament_nodes SET movement='ag1000-v1',tick_us=1000,clock_us=15000"):
            self.db.execute(sql)
            self.db.commit()
            self.assertEqual(self.send(self.form('start', 0, m))['ok'], 0)
            for table in ('tournament_matches','tournament_reservations'):
                self.assertEqual(self.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0], 0)
        self.post('state', enabled=1, occupants=0, movement='ag1000-v1', tick_us=1000, clock_us=1000)
        stored = json.loads(self.db.execute('SELECT state FROM tournament_parties').fetchone()[0])
        self.assertTrue(self.act('start', 0, m)['launch'])
        live = json.loads(self.db.execute('SELECT state FROM tournament_matches').fetchone()[0])
        for key in ('settings','_pins','ruleset_id'):
            self.assertEqual(live[key], stored[key])
        self.assertNotIn('_pins', json.dumps(self.client.get('/api/tournament-lobbies').get_json()))


if __name__ == '__main__':
    unittest.main()
