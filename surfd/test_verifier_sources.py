#!/usr/bin/env python3
"""Verifier source-stability fence; synthetic stdout, real files/SQLite/badge SQL.

Controls prove the runner and replacement ACTED. This does not prove immutable
engine input, hostile-host change-and-restore detection, or historical revocation.
"""
import hashlib
import os
import unittest
from unittest import mock

import test_sweep as suite
import test_verifier_counts as controls


class Sources(unittest.TestCase):
    setUp = controls.Counts.setUp
    cleanup_home = controls.Counts.cleanup_home

    def source(self, number=662, known=True):
        leaf = '%07d_p-2c8f36b6_run.rec' % number
        rid = suite.add_replay(self.c, self.m.RUNS_DIR, 'bhop_eazy', leaf, make_file=False)
        path = os.path.join(self.m.RUNS_DIR, 'bhop_eazy', 'main', leaf)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = (b'FTESURF-REC 9\nmap bhop_eazy\ntrack 0\nleg 0\n'
                b'tickrate 0.01\nflags 0\nbegin\n# source A\n')
        with open(path, 'wb') as fh:
            fh.write(data)
        digest = hashlib.sha256(data).hexdigest()
        self.c.execute('UPDATE replays SET sha=?, sha_at=? WHERE id=?',
                       (digest if known else '', 1 if known else 0, rid))
        self.c.execute(
            "INSERT INTO runs (map,track,leg,tier,style,player,name,ticks,tickrate,"
            "millis,flags,node,runid,submitted,replay_id) VALUES "
            "('bhop_eazy',0,0,'ranked','normal',?, 'n',662,100,6620,0,'1','',1,?)",
            ('synthetic-%d' % number, rid))
        self.c.commit()
        return rid, path, data, digest

    def state(self, rid):
        v = self.c.execute('SELECT verdict,counts_metrics FROM verdicts WHERE replay_id=? '
                           'ORDER BY id DESC LIMIT 1', (rid,)).fetchone()
        checked = self.c.execute('SELECT checked FROM replays WHERE id=?', (rid,)).fetchone()[0]
        badge = self.c.execute('SELECT '+self.m.VER_SQL+' FROM runs r WHERE replay_id=?',
                               (rid,)).fetchone()[0]
        return v['verdict'], checked, badge, v['counts_metrics']

    def replace(self, path, data):
        changed = data.replace(b'source A', b'source B')
        self.assertEqual(len(changed), len(data))
        self.assertNotEqual(hashlib.sha256(changed).digest(), hashlib.sha256(data).digest())
        before = self.m._rec_meta(path)[0]
        with open(path+'.new', 'wb') as fh:
            fh.write(changed)
        os.replace(path+'.new', path)
        self.assertEqual(self.m._rec_meta(path)[0], before)
        with open(path, 'rb') as fh:
            self.assertEqual(fh.read(), changed)  # replacement positively observed

    def run_pass(self, action=None, now=100):
        acted = []
        def runner(map_dir, paths):
            acted.extend(paths)
            output = sum((controls.section(p, '7 record(s): what the input ring delivered is what the view read',
                                  'PASS ticks 662 rows 634') for p in paths), [])
            if action:
                action()
            return output
        result = self.sw.sweep(self.c, 20, runner=runner, now=now)
        return acted, result

    def test_stable_known_source_verifies_and_exposes_badge(self):
        rid, _path, _data, _digest = self.source()
        acted, result = self.run_pass()
        self.assertEqual(len(acted), 1)
        self.assertEqual(result, {'PASS': 1})
        self.assertEqual(self.state(rid)[:3], ('PASS', 1, 1))
        self.assertIn('"records":7', self.state(rid)[3])

    def test_changed_known_submission_is_not_sent_to_verifier(self):
        rid, path, data, _digest = self.source()
        self.replace(path, data)
        acted, result = self.run_pass()
        self.assertEqual(acted, [])
        self.assertEqual(result, {'ERROR': 1})
        self.assertEqual(self.state(rid), ('ERROR', 0, 0, ''))

    def test_changed_during_verifier_has_no_terminal_result_or_metrics(self):
        rid, path, data, _digest = self.source()
        acted, result = self.run_pass(lambda: self.replace(path, data))
        self.assertEqual(len(acted), 1)
        self.assertEqual(result, {'ERROR': 1})
        self.assertEqual(self.state(rid), ('ERROR', 0, 0, ''))
        self.assertEqual(self.c.execute('SELECT submitted FROM replays WHERE id=?',
                                       (rid,)).fetchone()[0], 1)

    def test_disappeared_during_verifier_is_unavailable(self):
        rid, path, _data, _digest = self.source()
        acted, result = self.run_pass(lambda: os.remove(path))
        self.assertEqual(len(acted), 1)
        self.assertFalse(os.path.exists(path))
        self.assertEqual(result, {'ERROR': 1})
        self.assertEqual(self.state(rid), ('ERROR', 0, 0, ''))

    def test_legacy_unknown_digest_still_verifies_without_backfill(self):
        rid, _path, _data, _digest = self.source(known=False)
        acted, result = self.run_pass()
        self.assertEqual(len(acted), 1)
        self.assertEqual(result, {'PASS': 1})
        self.assertEqual(self.state(rid)[:3], ('PASS', 1, 1))
        self.assertEqual(tuple(self.c.execute('SELECT sha,sha_at FROM replays WHERE id=?',
                                             (rid,)).fetchone()), ('', 0))

    def test_group_failure_does_not_contaminate_stable_companion(self):
        a, path, data, _digest = self.source()
        b, _path, _data, _digest = self.source(663)
        acted, result = self.run_pass(lambda: self.replace(path, data))
        self.assertEqual(len(acted), 2)
        self.assertEqual(result, {'ERROR': 1, 'PASS': 1})
        self.assertEqual(self.state(a), ('ERROR', 0, 0, ''))
        self.assertEqual(self.state(b)[:3], ('PASS', 1, 1))

    def test_restored_source_recovers_within_retry_budget(self):
        rid, path, data, _digest = self.source()
        self.run_pass(lambda: self.replace(path, data))
        self.assertEqual(self.state(rid)[:3], ('ERROR', 0, 0))
        with open(path, 'wb') as fh:
            fh.write(data)
        acted, result = self.run_pass(now=101)
        self.assertEqual(len(acted), 1)
        self.assertEqual(result, {'PASS': 1})
        self.assertEqual(self.state(rid)[:3], ('PASS', 1, 1))

    def test_source_read_failure_is_retryable_not_a_player_finding(self):
        rid, path, _data, _digest = self.source()
        real_open = open
        def denied(p, *args, **kw):
            if os.fspath(p) == path:
                raise PermissionError('synthetic unavailable source')
            return real_open(p, *args, **kw)
        with mock.patch('builtins.open', side_effect=denied):
            acted, result = self.run_pass()
        self.assertEqual((acted, result), ([], {'ERROR': 1}))
        self.assertEqual(self.state(rid), ('ERROR', 0, 0, ''))
        self.assertEqual(self.run_pass(now=101)[1], {'PASS': 1})

    def test_replacement_during_hash_is_not_a_stable_observation(self):
        _rid, path, data, _digest = self.source()
        real_stat = self.sw.os.fstat
        calls = []
        def replace_on_second_stat(fd):
            calls.append(fd)
            if len(calls) == 2:
                # Rename while the captured old handle is still open.
                self.replace(path, data)
            return real_stat(fd)
        with mock.patch.object(self.sw.os, 'fstat', side_effect=replace_on_second_stat):
            self.assertIsNone(self.sw.source_sha(path))
        self.assertGreaterEqual(len(calls), 2)

    def test_same_bytes_with_new_metadata_remain_valid(self):
        rid, path, data, _digest = self.source()
        def touch():
            st = os.stat(path)
            os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1000000000))
            self.assertNotEqual(os.stat(path).st_mtime_ns, st.st_mtime_ns)
        acted, result = self.run_pass(touch)
        self.assertEqual(len(acted), 1)
        self.assertEqual(result, {'PASS': 1})
        self.assertEqual(self.state(rid)[:3], ('PASS', 1, 1))

    def test_stale_filing_digest_is_not_current_or_backfilled(self):
        rid, path, data, digest = self.source()
        self.c.execute('UPDATE replays SET sha_at=0 WHERE id=?', (rid,))
        self.c.commit()
        self.replace(path, data)
        acted, result = self.run_pass()
        self.assertEqual(len(acted), 1)
        self.assertEqual(result, {'PASS': 1})
        self.assertEqual(self.state(rid)[:3], ('PASS', 1, 1))
        self.assertEqual(tuple(self.c.execute('SELECT sha,sha_at FROM replays WHERE id=?',
                                             (rid,)).fetchone()), (digest, 0))

    def test_both_evidence_copies_are_fenced(self):
        self.m.EVIDENCE_DIR = os.path.join(self.m.BASE_DIR, 'ftesurf', 'data', 'evidence')
        self.m.KEEP_DIR = os.path.join(self.m.BASE_DIR, 'keep')
        for changed_root in (self.m.EVIDENCE_DIR, self.m.KEEP_DIR):
            runid = '20261008-00000%d-0-p27510' % (0 if changed_root == self.m.EVIDENCE_DIR else 1)
            data = suite.evbody(runid, abandoned=False)
            rid = suite.add_evidence(self.c, runid, data)
            disk_path = os.path.join(changed_root, 'surf_aser', runid+'.rec')
            def change():
                with open(disk_path, 'a', newline='\n') as fh:
                    fh.write('# changed copy\n')
                with open(disk_path) as fh:
                    self.assertTrue(fh.read().endswith('# changed copy\n'))
            acted, result = self.run_pass(change)
            self.assertTrue(any(runid in p for p in acted))
            self.assertIn('ERROR', result)
            self.assertEqual(tuple(suite.latest(self.c, rid))[::2], ('ERROR', -1))
            stored = self.c.execute('SELECT v.counts_metrics,r.checked FROM verdicts v '
                                    'JOIN replays r ON r.id=v.replay_id WHERE r.id=? '
                                    'ORDER BY v.id DESC LIMIT 1', (rid,)).fetchone()
            self.assertEqual(tuple(stored), ('', 0))
            # Isolate this arm from subsequent pending/retry selection.
            self.c.execute('UPDATE replays SET checked=1 WHERE id=?', (rid,))
            self.c.commit()

    def test_hashing_does_not_hold_writer_transaction(self):
        self.source()
        real = self.sw.verifier_source_sha
        observed = []
        def outside_write(row, path):
            observed.append(self.c.in_transaction)
            return real(row, path)
        with mock.patch.object(self.sw, 'verifier_source_sha', side_effect=outside_write):
            self.assertEqual(self.run_pass()[1], {'PASS': 1})
        self.assertEqual(observed, [False, False])

    def test_source_error_does_not_revoke_an_existing_pass(self):
        rid, path, data, _digest = self.source()
        self.assertEqual(self.run_pass()[1], {'PASS': 1})
        self.c.execute('UPDATE replays SET checked=0,recheck_at=101 WHERE id=?', (rid,))
        self.c.commit()
        self.replace(path, data)
        acted, result = self.run_pass(now=102)
        self.assertEqual((acted, result), ([], {'ERROR': 1}))
        # Existing policy ignores ERROR, rather than claiming a new judgement.
        self.assertEqual(self.state(rid), ('ERROR', 0, 1, ''))

    def test_persistent_mismatch_spends_existing_error_budget(self):
        rid, path, data, _digest = self.source()
        self.replace(path, data)
        for t in range(self.sw.MAX_ERRORS):
            acted, result = self.run_pass(now=100+t)
            self.assertEqual((acted, result), ([], {'ERROR': 1}))
        self.assertEqual(self.run_pass(now=200), ([], {}))
        self.assertEqual(self.state(rid)[:3], ('ERROR', 0, 0))
        # Simulate an explicit refiling: updated evidence identity/window.
        with open(path, 'rb') as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        self.c.execute('UPDATE replays SET sha=?,sha_at=201,submitted=201 WHERE id=?',
                       (digest, rid))
        self.c.commit()
        acted, result = self.run_pass(now=202)
        self.assertEqual(len(acted), 1)
        self.assertEqual(result, {'PASS': 1})
        self.assertEqual(self.state(rid)[:3], ('PASS', 1, 1))


if __name__ == '__main__':
    unittest.main()
