#!/usr/bin/env python3
"""Finish-duration binding: real POST/files/SQLite/public board, stub verifier.

No engine physics, historical reread or owner-review policy is claimed here.
"""
import hashlib
import os
import unittest
import test_sweep as suite
import test_verifier_counts as controls


class Finish(unittest.TestCase):
    setUp = controls.Counts.setUp
    cleanup_home = controls.Counts.cleanup_home

    def recording(self, leaf, ticks=662, runid='finish-control', rate='0.01'):
        path = os.path.join(self.m.RUNS_DIR, 'bhop_eazy', 'main', leaf)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('FTESURF-REC 9\nmap bhop_eazy\ntrack 0\nleg 0\n'
                     'runid %s\ntickrate %s\nflags 0\nbegin\n'
                     'end %d 1 0 0 1 0 0 0 0 0\n' % (runid, rate, ticks))
        return path

    def submit(self, ticks=662, present=True, player='synthetic-finish', runid='finish-control'):
        leaf = '%07d_synthetic-%s_run.rec' % (ticks, hashlib.sha256(player.encode()).hexdigest()[:8])
        if present:
            self.recording(leaf)
        response = self.m.app.test_client().post('/api/run', data={
            'key': 'testkey', 'map': 'bhop_eazy', 'ticks': str(ticks), 'tickrate': '100',
            'player': player, 'name': 'Synthetic', 'rec': leaf, 'runid': runid,
            'track': '0', 'leg': '0', 'flags': '0', 'node': 'p27510',
        }, environ_base={'REMOTE_ADDR': '127.0.0.1'})
        self.assertEqual(response.status_code, 200)  # actual POST accepted
        self.assertTrue(response.get_json()['ok'])
        row = self.c.execute('SELECT * FROM replays WHERE leaf=?', (leaf,)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row['ticks'], ticks)
        self.assertEqual(row['bound'], int(present))
        return row['id'], leaf

    def run_verifier(self, result='PASS ticks 662 rows 1', now=9999999999):
        acted = []
        def runner(map_dir, paths):
            self.assertEqual(map_dir, 'bhop_eazy')
            acted.extend(paths)
            return sum((controls.section(p, '7 record(s): what the input ring delivered is what the view read', result)
                        for p in paths), [])
        counts = self.sw.sweep(self.c, 20, runner=runner, now=now)
        self.assertTrue(acted)  # not a silent admission failure
        return counts

    def state(self, rid):
        row = self.c.execute('SELECT verdict,reason,ticks,counts_metrics FROM verdicts '
                             'WHERE replay_id=? ORDER BY id DESC LIMIT 1', (rid,)).fetchone()
        checked = self.c.execute('SELECT checked FROM replays WHERE id=?', (rid,)).fetchone()[0]
        board = self.m.app.test_client().get('/api/board?map=bhop_eazy').get_json()
        standing = next(r for r in board['rows'] if r['rep'] == rid)
        # Reasons/verdict details stay private, even for a HOLD.
        self.assertNotIn('reason', standing)
        return row, checked, standing['ver']

    def test_matching_finished_run_still_verifies(self):
        rid, _leaf = self.submit()
        self.assertEqual(self.run_verifier(), {'PASS': 1})
        row, checked, badge = self.state(rid)
        self.assertEqual((row['verdict'], row['ticks'], checked, badge), ('PASS', 662, 1, 1))
        self.assertIn('"records":7', row['counts_metrics'])

    def test_different_finish_cannot_badge_claimed_duration(self):
        for ticks in (661, 663):
            rid, _leaf = self.submit(ticks, player='synthetic-%d' % ticks)
            self.assertEqual(self.run_verifier(), {'HOLD': 1})
            row, checked, badge = self.state(rid)
            self.assertEqual((row['verdict'], row['ticks'], checked, badge), ('HOLD', 662, 1, 0))
            self.assertIn('662', row['reason'])
            self.assertIn(str(ticks), row['reason'])
            self.assertIn('"records":7', row['counts_metrics'])

    def test_fileless_arrival_binds_finish_without_refile(self):
        for ticks in (662, 661):
            rid, leaf = self.submit(ticks, present=False, player='arrival-%d' % ticks)
            self.recording(leaf)
            expected = 'PASS' if ticks == 662 else 'HOLD'
            self.assertEqual(self.run_verifier(), {expected: 1})
            row, checked, badge = self.state(rid)
            self.assertEqual((row['verdict'], checked, badge), (expected, 1, int(ticks == 662)))
            self.assertEqual(self.c.execute('SELECT bound,sha FROM replays WHERE id=?',
                                           (rid,)).fetchone()[:], (0, ''))

    def test_unavailable_finish_is_error_not_a_player_finding(self):
        rid, _leaf = self.submit()
        for turn, reason in enumerate(('', 'rows 1', 'ticks -1 rows 1', 'ticks 662 ticks 661 rows 1',
                                       'ticks 662.0 rows 1', 'ticks 662x rows 1', 'ticks 662 rows 1 extra',
                                       'ticks 9999999999 rows 1', 'ticks 662 rows 9999999999')):
            now = 9999999999 + turn
            self.c.execute('UPDATE replays SET checked=0,recheck_at=? WHERE id=?', (now, rid))
            self.c.commit()
            self.assertEqual(self.run_verifier('PASS '+reason, now=now), {'ERROR': 1})
            row, checked, badge = self.state(rid)
            self.assertEqual((row['verdict'], row['ticks'], checked, badge), ('ERROR', -1, 0, 0))
            self.assertEqual(row['counts_metrics'], '')

    def test_header_disagreement_still_holds(self):
        rid, leaf = self.submit(present=False)
        self.recording(leaf, runid='other-control')
        self.assertEqual(self.run_verifier(), {'HOLD': 1})
        row, _checked, badge = self.state(rid)
        self.assertIn('runid', row['reason'])
        self.assertEqual((row['verdict'], badge), ('HOLD', 0))

    def test_hold_and_refuse_keep_existing_reasons(self):
        for word in ('HOLD', 'REFUSE'):
            rid, _leaf = self.submit(player='outcome-'+word)
            self.assertEqual(self.run_verifier(word+' original control reason'), {word: 1})
            row, checked, badge = self.state(rid)
            self.assertEqual((row['verdict'], row['reason'], row['ticks'], checked, badge),
                             (word, 'original control reason', -1, 1, 0))

    def test_stable_group_companion_is_independent(self):
        good, _leaf = self.submit(player='group-good')
        bad, _leaf = self.submit(661, player='group-bad')
        self.assertEqual(self.run_verifier(), {'PASS': 1, 'HOLD': 1})
        self.assertEqual(self.state(good)[2], 1)
        self.assertEqual(self.state(bad)[2], 0)

    def test_owner_approval_still_overrides_hold(self):
        rid, _leaf = self.submit(661)
        self.c.execute("INSERT INTO reviews(replay_id,decision,note,at) VALUES (?, 'approve', 'synthetic control', ?)",
                       (rid, 9999999999))
        self.c.commit()
        self.assertEqual(self.run_verifier(), {'HOLD': 1})
        row, _checked, badge = self.state(rid)
        self.assertEqual((row['verdict'], badge), ('HOLD', 1))

    def test_abandoned_evidence_still_promotes_reproduction(self):
        self.m.EVIDENCE_DIR = os.path.join(self.m.BASE_DIR, 'ftesurf', 'data', 'evidence')
        self.m.KEEP_DIR = os.path.join(self.m.BASE_DIR, 'keep')
        runid = '20261008-000000-0-p27510'
        rid = suite.add_evidence(self.c, runid, suite.evbody(runid))
        acted = []
        def runner(map_dir, paths):
            acted.extend(paths)
            return ['VERIFY %s HOLD %s' % (p, self.sw.NO_FINISH) for p in paths]
        self.assertEqual(self.sw.sweep(self.c, 20, runner=runner, now=9999999999), {'PASS': 1})
        self.assertEqual(len(acted), 1)
        row = suite.latest(self.c, rid)
        self.assertEqual((row['verdict'], row['ticks']), ('PASS', 8262))


if __name__ == '__main__':
    unittest.main()
