"""P1171 lobby-only activity through existing authenticated Flask routes."""
import json
import sqlite3
import unittest
from unittest.mock import patch

import test_social as fixture
import playstats as P

S = fixture.S


class PlayStats(unittest.TestCase):
    hello = fixture.Friends.hello
    heartbeat = fixture.Friends.heartbeat
    def post(self, path, **form):
        data = dict(key='testkey', node='p27510')
        data.update(form)
        return self.client.post(path, data=data)

    def setUp(self):
        fixture.Friends.setUp(self)
        for table in ('play_sessions', 'play_maps', 'play_attempts', 'runs'):
            self.db.execute('DELETE FROM ' + table)
        self.db.commit()
        S.profile_forget()
        S._people.update(at=-1, by_handle={}, list=[], entry={}, by_mark={}, main_maps=set())

    def tearDown(self):
        fixture.Friends.tearDown(self)

    def send(self, index=0, **extra):
        sid = self.db.execute('SELECT steamid FROM keylinks WHERE pub=?',
                              (fixture.PUBS[index],)).fetchone()
        capture = P.binding(self.db, fixture.PUBS[index], sid[0]) if sid else ''
        form = dict(token=self.tokens[index], stream='a' * 32, map='surf_test',
                    binding=capture, consent='8', seconds='30',
                    attempts='0:0:3,0:1:4,0:2:2,1:0:1,1:1:2')
        form.update(extra)
        return self.post('/api/social/playstats', **form)

    def stats(self, index=0, mp='surf_test'):
        return P.profile(self.db, fixture.IDS[index], mp)

    def test_retries_reordering_and_main_bonus_stage_counters(self):
        for values in ({}, {}, dict(seconds='10', attempts='0:0:1'),
                       dict(seconds='40', attempts='0:0:4'),
                       dict(seconds='35', attempts='0:2:3')):
            self.assertEqual(self.send(**values).status_code, 200)
        data = self.stats()
        self.assertEqual((data['seconds'], data['map_seconds']), (40, 40))
        self.assertEqual([(x['track'], x['leg'], x['n']) for x in data['attempts']],
                         [(0, 0, 4), (0, 1, 4), (0, 2, 3), (1, 0, 1), (1, 1, 2)])

    def test_consent_key_node_capability_and_revocation_fail_closed(self):
        for values in (dict(consent=''), dict(consent='7'), dict(consent='x8'), dict(key='wrong'),
                       dict(node='p27511'), dict(token='0' * 64)):
            self.assertEqual(self.send(**values).status_code, 403)
        self.assertEqual(self.stats()['seconds'], 0)
        self.assertEqual(self.send(steamid=fixture.IDS[1]).status_code, 200)
        self.assertEqual(self.stats(1)['seconds'], 0)
        self.db.execute('DELETE FROM keylinks WHERE pub=?', (fixture.PUBS[0],))
        self.db.commit()
        self.assertEqual(self.send(seconds='60').status_code, 403)
        self.assertEqual(self.stats()['seconds'], 30)

    def test_link_epoch_a_b_a_cannot_reassign_or_reuse_capture(self):
        capture = P.binding(self.db, fixture.PUBS[0], fixture.IDS[0])
        for sid in (fixture.IDS[0], fixture.IDS[1], fixture.IDS[0]):
            self.db.execute('UPDATE keylinks SET steamid=?,linked_at=linked_at+1 WHERE pub=?',
                            (sid, fixture.PUBS[0]))
            self.db.commit()
            self.assertIn(self.send(binding=capture).status_code, (400, 403))
        self.assertEqual(self.stats()['seconds'], 0)
        self.assertEqual(self.send(stream='e' * 32).status_code, 200)

    def test_maps_reconnects_and_installs_share_account_not_stream(self):
        self.send()
        self.assertEqual(self.send(index=3, stream='b' * 32, seconds='20').status_code, 200)
        self.assertEqual(self.send(stream='c' * 32, map='surf_elsewhere', seconds='10').status_code, 200)
        self.assertEqual((self.stats()['seconds'], self.stats()['map_seconds']), (60, 50))
        self.assertEqual(self.stats(mp='surf_elsewhere')['map_seconds'], 10)
        self.assertEqual(self.send(index=1).status_code, 400)
        self.assertEqual(self.send(map='surf_other').status_code, 400)

    def test_storage_failure_rolls_back_and_restart_keeps_watermark(self):
        self.send()
        with patch.object(P, 'store', side_effect=sqlite3.OperationalError('fixture')):
            self.assertEqual(self.send(seconds='60').status_code, 503)
        self.assertEqual(self.stats()['seconds'], 30)
        S.migrate()
        self.assertEqual(self.send().status_code, 200)
        self.assertEqual(self.stats()['seconds'], 30)

    def test_bounds_and_binding(self):
        for values in (dict(seconds='nan'), dict(seconds='-1'), dict(seconds='1.5'),
                       dict(stream='../bad'), dict(map='../bad'), dict(binding=''),
                       dict(attempts='0:0:1,0:0:2'), dict(attempts='12:0:1'),
                       dict(attempts='0:24:1'), dict(seconds='16777216')):
            self.assertEqual(self.send(**values).status_code, 400)
        self.assertEqual(self.stats()['seconds'], 0)

    def test_profile_before_finish_and_existing_inventory_are_preserved(self):
        S.inventory.ensure(self.db, fixture.IDS[0])
        self.db.commit()
        before = S.inventory.snapshot(self.db, fixture.IDS[0])
        self.send()
        S._people_install(*S._people_build(self.db), at=self.now)
        who = S.web_handle(fixture.IDS[0])
        response = self.client.get('/api/board?player=' + who + '&on=surf_test')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['total'], 0)
        self.assertEqual(self.client.get('/api/board?player=' + who).get_json()['n'], 0)
        self.assertEqual(data['playtime']['seconds'], 30)
        self.assertEqual(data['playtime']['coverage'], 'official_lobby')
        self.assertEqual(data['rows'], [])
        self.assertNotIn(self.tokens[0], json.dumps(data))
        self.assertEqual(S.inventory.snapshot(self.db, fixture.IDS[0]), before)

    def test_tracked_only_account_is_listed_under_a_game_safe_name(self):
        self.db.execute('UPDATE accounts SET name=? WHERE steamid=?',
                        ('co\x01nsole\n', fixture.IDS[0]))
        self.db.commit()
        self.send()
        _, people, _ = S._people_build(self.db)
        row = [e for e in people if e['who'] == S.web_handle(fixture.IDS[0])]
        self.assertEqual(len(row), 1)
        self.assertEqual(row[0]['name'], 'player')  # account_named() refuses it: no raw fallback
        self.assertNotIn('\n', row[0]['name'])

    def test_no_client_private_upload_route_was_enabled(self):
        self.assertFalse(fixture.F.menu_target('playstats', 'a' * 64))


if __name__ == '__main__':
    unittest.main()
