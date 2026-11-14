#!/usr/bin/env python3
"""Isolated TAS community boards; no physics certification or web replay grant."""
import os
import sqlite3
import unittest

import test_web as fixture


class TasBoards(unittest.TestCase):
    def setUp(self):
        self.m = fixture.fresh()
        self.c = self.m.app.test_client()

    def post(self, player, flags, **kw):
        form = dict(key='testkey', map='bhop_eazy', track='0', leg='0',
                    player=player, name=player, ticks='3000', tickrate='100',
                    flags=str(flags), node='p27510')
        form.update({k: str(v) for k, v in kw.items()})
        return self.c.post('/api/run', data=form)

    def test_classification_and_ordinary_boards(self):
        m = self.m
        for flags in (m.TF_CHEAT, m.TF_PRACTICE, m.TF_BANKTAINT,
                      m.TF_BANKTAINT | m.TF_SEGMENT, m.TF_CHEAT | m.TF_SEGMENT):
            self.assertIsNone(m.style_of(flags))
            self.assertEqual(self.post('refused', flags).status_code, 204)
        self.post('clean', 0, ticks=3000)
        self.post('segment', m.TF_SEGMENT, ticks=2000)
        for i, flags in enumerate((m.TF_TAS, m.TF_TAS | m.TF_CHEAT | m.TF_PRACTICE,
                                   m.TF_TAS | m.TF_SEGMENT | m.TF_BANKTAINT)):
            self.assertEqual(m.style_of(flags), 'tas')
            self.assertFalse(m.certifiable(flags))
            reply = self.post('tas%d' % i, flags, ticks=100 + i).get_json()
            self.assertEqual(reply['tier'], 'community')
        for style, player in (('clean', 'clean'), ('segmented', 'segment')):
            rows = self.c.get('/api/board?map=bhop_eazy&style=' + style).get_json()['rows']
            self.assertEqual([r['player'] for r in rows], [player])
        rows = self.c.get('/api/board?map=bhop_eazy&tier=community&style=tas').get_json()['rows']
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r['flags'] & m.TF_TAS and r['ver'] == 0 for r in rows))
        self.assertFalse(m._finishes({'track': 0, 'leg': 0, 'style': 'tas'}))
        self.assertTrue(m._finishes({'track': 0, 'leg': 0, 'style': 'clean'}))
        with sqlite3.connect(m._test_db) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM runs WHERE tier='ranked' AND style='tas'").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM story_runs WHERE player LIKE 'tas%'").fetchone()[0], 0)

    def test_web_counts_and_native_replay_gates(self):
        m = self.m
        flags = m.TF_TAS | m.TF_CHEAT
        lf = fixture.leaf(3000, 'tas')
        path = fixture.write_rec(m, 'run', 'bhop_eazy', 0, 0, lf)
        # The genuine header must bind to this submission, not a guessed file.
        text = ('FTESURF-REC 9\nmap bhop_eazy\ntrack 0\nleg 0\nowner tas\n'
                'runid rt\ntickrate 0.01\nclock counted\nflags %d\nbegin\n'
                'end 3000 0 0 0 0 0 0 0 0 0 1\n') % flags
        with open(path, 'w', newline='\n') as fh:
            fh.write(text)
        result = self.post('tas', flags, rec=lf, runid='rt').get_json()
        rid = result['rep']
        self.assertGreater(rid, 0)
        native = self.c.get('/api/replay/%d' % rid)
        self.assertEqual(native.status_code, 200)
        self.assertEqual(native.get_data(), text.encode())
        native.close()
        fixture.add_review(m, rid, 'approve')
        fixture.add_verdict(m, rid, 'pass', 1900000000)
        body = self.c.get('/board/api/map?map=bhop_eazy&style=tas&tier=community').get_json()
        self.assertEqual((body['tier'], body['n']), ('community', 1))
        self.assertEqual((body['rows'][0]['ver'], body['rows'][0]['rep'], body['rows'][0]['run']), (0, 0, 0))
        count = next(b for b in body['boards'] if b['style'] == 'tas')
        self.assertEqual((count['n'], count['ni'], count['nt']), (0, 0, 1))
        for suffix in ('', '/track'):
            self.assertEqual(self.c.get('/board/api/run/%d%s' % (rid, suffix)).status_code, 404)
        ordinary = self.c.get('/board/api/map?map=bhop_eazy&style=clean&tier=community').get_json()
        self.assertEqual((ordinary['tier'], ordinary['n']), ('ranked', 0))
        maps = self.c.get('/board/api/maps').get_json()['maps']
        row = next(r for r in maps if r['map'] == 'bhop_eazy')
        self.assertEqual((row['runs'], row['imp'], row['wr']), (0, 0, None))
        fixture.add_review(m, rid, 'reject')
        self.assertEqual(self.c.get('/api/replay/%d' % rid).status_code, 404)
        fixture.add_review(m, rid, 'approve')
        os.remove(path)
        self.assertEqual(self.c.get('/api/replay/%d' % rid).status_code, 404)

    def test_linked_tas_stays_community_and_banned_owner_refused(self):
        m = self.m
        m.RANKED_LINKED = True
        sid, pub = '76561198000000001', '11' * 32
        with sqlite3.connect(m._test_db) as db:
            db.execute('INSERT INTO accounts (steamid, name, created_at) VALUES (?,?,?)',
                       (sid, 'Tester', 1800000000))
            db.execute('INSERT INTO keylinks (pub, steamid, player, node, linked_at) VALUES (?,?,?,?,?)',
                       (pub, sid, '9fb6' + 'a1' * 14, 'p27510', 1800000000))
        reply = self.post('9fb6' + 'a1' * 14, m.TF_TAS | m.TF_CHEAT, pub=pub).get_json()
        self.assertEqual(reply['tier'], 'community')
        with sqlite3.connect(m._test_db) as db:
            self.assertEqual(db.execute('SELECT player FROM runs').fetchall(), [(sid,)])
            db.execute('UPDATE accounts SET banned_at=1800000001 WHERE steamid=?', (sid,))
        reply = self.post('9fb6' + 'a1' * 14, m.TF_TAS, pub=pub, ticks=2000).get_json()
        self.assertFalse(reply['stored'])
        self.assertEqual(reply['why'], 'banned')

    def test_submission_key_still_required(self):
        r = self.c.post('/api/run', data={'flags': self.m.TF_TAS, 'key': 'wrong'})
        self.assertEqual(r.status_code, 403)


if __name__ == '__main__':
    unittest.main()
