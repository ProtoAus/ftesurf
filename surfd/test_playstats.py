"""Activity through real account proofs/routes, with no production DB or HTTP."""
import json
import sqlite3
import unittest
from unittest.mock import patch

import test_social as fixture
import playstats as P

S, F = fixture.S, fixture.F


class PlayStats(unittest.TestCase):
    hello = fixture.Friends.hello
    heartbeat = fixture.Friends.heartbeat
    post = fixture.Friends.post

    def setUp(self):
        fixture.Friends.setUp(self)
        for table in ('play_sessions', 'play_maps', 'play_attempts', 'runs'):
            self.db.execute('DELETE FROM ' + table)
        self.db.commit()
        S.profile_forget()
        S._people.update(at=-1, by_handle={}, list=[], entry={}, by_mark={}, main_maps=set())

    def send(self, index=0, **extra):
        form = dict(token=self.tokens[index], stream='a' * 32, map='surf_test',
                    seconds='30', attempts='0:0:3,0:1:4,0:2:2,1:0:1,1:1:2')
        form.update(extra)
        return self.post('/api/social/playstats', **form)

    def stats(self, index=0, mp='surf_test'):
        return P.profile(self.db, fixture.IDS[index], mp)

    def test_retries_reordering_and_independent_counters(self):
        self.assertEqual(self.send().status_code, 200)
        self.assertEqual(self.send().status_code, 200)
        self.assertEqual(self.send(seconds='10', attempts='0:0:1').status_code, 200)
        first = self.stats()
        self.assertEqual(first['seconds'], 30)
        self.assertEqual([r['n'] for r in first['attempts']], [3, 4, 2, 1, 2])
        self.assertEqual(self.send(seconds='40', attempts='0:0:4').status_code, 200)
        self.assertEqual(self.send(seconds='35', attempts='0:2:3').status_code, 200)
        result = self.stats()
        self.assertEqual(result['seconds'], 40)
        self.assertEqual([r['n'] for r in result['attempts']], [4, 4, 3, 1, 2])

    def test_maps_reconnects_and_installs_share_only_the_steam_account(self):
        self.send()
        self.assertEqual(self.send(index=3, stream='b' * 32, seconds='20').status_code, 200)
        self.assertEqual(self.send(stream='c' * 32, map='surf_elsewhere', seconds='10').status_code, 200)
        self.assertEqual(self.stats()['seconds'], 60)
        self.assertEqual(self.stats()['map_seconds'], 50)
        self.assertEqual(self.stats(mp='surf_elsewhere')['map_seconds'], 10)
        self.assertEqual(self.stats(index=1)['seconds'], 0)
        self.assertEqual(self.send(index=1).status_code, 400)  # pinned stream
        self.assertEqual(self.send(map='surf_other').status_code, 400)
        self.assertEqual(self.stats()['seconds'], 60)

    def test_authority_is_capability_not_posted_account_or_guid(self):
        for extra in ({'key': 'wrong'}, {'token': '0' * 64}, {'node': 'p27511'}):
            form = dict(key='testkey', node='p27510', token=self.tokens[0], stream='a' * 32,
                        map='surf_test', seconds='30', attempts='0:0:1')
            form.update(extra)
            response = self.client.post('/api/social/playstats', data=form)
            self.assertEqual(response.status_code, 403)
        self.assertEqual(self.send(steamid=fixture.IDS[1], player=fixture.IDS[1]).status_code, 200)
        self.assertEqual((self.stats()['seconds'], self.stats(1)['seconds']), (30, 0))
        self.db.execute('DELETE FROM keylinks WHERE pub=?', (fixture.PUBS[0],))
        self.db.commit()
        self.assertEqual(self.send(seconds='60').status_code, 403)
        self.assertEqual(self.stats()['seconds'], 30)

    def test_invalid_and_dense_payloads(self):
        for extra in ({'seconds': '-1'}, {'seconds': 'nan'}, {'seconds': '1.5'},
                      {'seconds': '16777216'}, {'stream': '../bad'}, {'map': '../bad'},
                      {'attempts': '12:0:1'}, {'attempts': '0:24:1'},
                      {'attempts': '0:0:1,0:0:2'}, {'attempts': '0:0:0'},
                      {'attempts': '0:0:16777216'}, {'attempts': 'x' * 8001}):
            with self.subTest(extra=extra):
                self.assertEqual(self.send(**extra).status_code, 400)
        dense = ','.join(f'{t}:{l}:16777215' for t in range(12) for l in range(24))
        self.assertEqual(self.send(attempts=dense).status_code, 200)
        self.assertEqual(len(self.stats()['attempts']), 288)

    def test_rollback_and_restart_watermarks(self):
        self.send()
        with patch.object(P, 'store', side_effect=sqlite3.OperationalError('fixture')):
            self.assertEqual(self.send(seconds='60').status_code, 503)
        self.assertEqual(self.stats()['seconds'], 30)
        S.migrate()
        self.assertEqual(self.send().status_code, 200)
        self.assertEqual(self.stats()['seconds'], 30)

    def test_profiles_exist_before_a_finish_and_expose_map_attempts(self):
        self.send()
        # Build the real directory with activity but deliberately no run rows.
        S._people_install(*S._people_build(self.db), at=self.now)
        who = S.web_handle(fixture.IDS[0])
        response = self.client.get('/api/board?player=' + who)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        profile = response.get_json()
        self.assertEqual(profile['n'], 0)
        self.assertEqual(profile['playtime']['seconds'], 30)
        response = self.client.get('/api/board?player=' + who + '&on=surf_test')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['playtime'], self.stats())
        self.assertEqual(data['rows'], [])
        self.assertNotIn('steamid', json.dumps(data))
        self.assertNotIn(self.tokens[0], json.dumps(data))

    def test_schema24_upgrade_preserves_activity_and_existing_tables(self):
        self.send()
        snapshot = [tuple(r) for r in self.db.execute('SELECT * FROM accounts')]
        self.db.execute('PRAGMA user_version=24')
        self.db.commit()
        S.migrate()
        S.migrate()
        self.assertEqual(self.db.execute('PRAGMA user_version').fetchone()[0], 25)
        self.assertEqual([tuple(r) for r in self.db.execute('SELECT * FROM accounts')], snapshot)
        self.assertEqual(self.stats()['seconds'], 30)


if __name__ == '__main__':
    unittest.main()
