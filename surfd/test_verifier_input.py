#!/usr/bin/env python3
"""Consumed-input attribution: synthetic reports, real files/SQLite/badge SQL.

Native execution and challenge-origin checks have separate controls. These tests
neither authenticate a hostile OS nor retrofit historical verdict provenance.
"""
import hashlib
import os
import unittest
from types import SimpleNamespace
from unittest import mock

import test_sweep as suite
import test_verifier_counts as counts
import test_verifier_sources as sources


def report(path, digest):
    return 'VERIFY-SOURCE %s SHA256 %s' % (path, digest)


class Input(unittest.TestCase):
    setUp = counts.Counts.setUp
    cleanup_home = counts.Counts.cleanup_home
    source = sources.Sources.source
    state = sources.Sources.state

    def run_output(self, output, now=100):
        acted = []
        def runner(map_dir, paths):
            self.assertEqual(map_dir, 'bhop_eazy')
            acted.extend(paths)
            return output(paths)
        got = self.sw.sweep(self.c, 20, runner=runner, now=now)
        self.assertTrue(acted)
        return got

    def assert_unavailable(self, rid):
        self.assertEqual(self.state(rid), ('ERROR', 0, 0, ''))
        self.assertEqual(self.c.execute('SELECT ticks FROM verdicts WHERE replay_id=? '
                                       'ORDER BY id DESC LIMIT 1', (rid,)).fetchone()[0], -1)

    def test_missing_source_is_not_a_bound_pass(self):
        rid, _path, _data, _digest = self.source()
        self.assertEqual(self.run_output(lambda p: counts.section(p[0], None, 'PASS ticks 662 rows 1')), {'ERROR': 1})
        self.assert_unavailable(rid)

    def test_other_consumed_bytes_are_not_a_bound_pass(self):
        rid, _path, data, digest = self.source()
        other = hashlib.sha256(data+b'other bytes').hexdigest()
        self.assertNotEqual(other, digest)
        self.assertEqual(self.run_output(lambda p: [report(p[0], other)]+
                                       counts.section(p[0], '7 record(s): what the input ring delivered is what the view read',
                                                      'PASS ticks 662 rows 1')), {'ERROR': 1})
        self.assert_unavailable(rid)

    def test_ambiguous_malformed_and_late_reports_never_recover(self):
        for i, variant in enumerate(('duplicate', 'conflict', 'malformed', 'late', 'wrong-path')):
            with self.subTest(variant=variant):
                rid, _path, _data, digest = self.source(662+i)
                def output(paths):
                    p = paths[0]
                    terminal = counts.section(p, None, 'PASS ticks 662 rows 1')
                    if variant == 'duplicate':
                        return [report(p, digest)]*2+terminal
                    if variant == 'conflict':
                        return [report(p, '0'*64), report(p, digest)]+terminal
                    if variant == 'malformed':
                        return [report(p, digest+'suffix')]+terminal
                    if variant == 'late':
                        return terminal+[report(p, digest)]
                    return [report(p+'-other', digest)]+terminal
                self.assertEqual(self.run_output(output), {'ERROR': 1})
                self.assert_unavailable(rid)
                self.c.execute('UPDATE replays SET checked=1 WHERE id=?', (rid,))
                self.c.commit()

    def test_clean_companion_and_retry_have_their_own_binding(self):
        bad, _path, data, a = self.source()
        good, _path, _data, b = self.source(663)
        other = hashlib.sha256(data+b'other').hexdigest()
        def output(paths):
            self.assertEqual(len(paths), 2)
            return ([report(paths[0], other), report(paths[1], b)]+
                    counts.section(paths[0], None, 'PASS ticks 662 rows 1')+
                    counts.section(paths[1], '9 record(s): what the input ring delivered is what the view read',
                                   'PASS ticks 662 rows 1'))
        self.assertEqual(self.run_output(output), {'ERROR': 1, 'PASS': 1})
        self.assert_unavailable(bad)
        self.assertEqual(self.state(good)[:3], ('PASS', 1, 1))
        self.assertIn('"records":9', self.state(good)[3])
        self.assertEqual(self.run_output(lambda p: [report(p[0], a)]+
                                       counts.section(p[0], None, 'PASS ticks 662 rows 1'), now=101), {'PASS': 1})
        self.assertEqual(self.state(bad)[:3], ('PASS', 1, 1))

    def test_legacy_unknown_filing_hash_still_uses_fresh_bytes(self):
        rid, _path, _data, digest = self.source(known=False)
        self.assertEqual(self.run_output(lambda p: [report(p[0], digest)]+
                                       counts.section(p[0], None, 'PASS ticks 662 rows 1')), {'PASS': 1})
        self.assertEqual(self.state(rid)[:3], ('PASS', 1, 1))
        self.assertEqual(tuple(self.c.execute('SELECT sha,sha_at FROM replays WHERE id=?', (rid,)).fetchone()), ('', 0))

    def test_unbound_refuse_or_hold_is_unavailable_not_player_guilt(self):
        for i, outcome in enumerate(('HOLD control', 'REFUSE control')):
            with self.subTest(outcome=outcome):
                rid, _path, _data, _digest = self.source(662+i)
                self.assertEqual(self.run_output(lambda p: ['VERIFY '+p[0]+' '+outcome]), {'ERROR': 1})
                self.assert_unavailable(rid)
                self.c.execute('UPDATE replays SET checked=1 WHERE id=?', (rid,))
                self.c.commit()

    def test_missing_binding_cannot_promote_abandoned_evidence(self):
        self.m.EVIDENCE_DIR = os.path.join(self.m.BASE_DIR, 'ftesurf', 'data', 'evidence')
        self.m.KEEP_DIR = os.path.join(self.m.BASE_DIR, 'keep')
        rid = suite.add_evidence(self.c, '20261008-000000-0-p27510', suite.evbody('20261008-000000-0-p27510'))
        acted = []
        def runner(map_dir, paths):
            acted.extend(paths)
            return ['VERIFY '+paths[0]+' HOLD '+self.sw.NO_FINISH]
        self.assertEqual(self.sw.sweep(self.c, 20, runner=runner, now=100), {'ERROR': 1})
        self.assertEqual(len(acted), 1)
        self.assertEqual(tuple(self.c.execute('SELECT verdict,ticks,counts_metrics FROM verdicts '
                                             'WHERE replay_id=?', (rid,)).fetchone()), ('ERROR', -1, ''))

    def test_actual_runner_authenticates_report_origin_and_exit(self):
        variants = ('valid', 'wrong-challenge', 'forged-normalized', 'failed-process',
                    'old-native', 'bad-then-valid', 'valid-plus-forged-text')
        for number, variant in enumerate(variants, 662):
            with self.subTest(variant=variant):
                rid, _path, _data, digest = self.source(number)
                acted = []
                def process(cmd, **kwargs):
                    where = cmd.index('+pm_verify')
                    path, challenge = cmd[where+1:where+3]
                    self.assertRegex(challenge, r'^b[0-9a-f]{32}$')
                    acted.append((path, challenge))
                    native = 'VERIFY-INPUT %s SHA256 %s CHALLENGE %s' % (path, digest, challenge)
                    other = challenge[0]+('0' if challenge[1] != '0' else '1')+challenge[2:]
                    bad = 'VERIFY-INPUT %s SHA256 %s CHALLENGE %s' % (path, digest, other)
                    terminal = 'VERIFY '+path+' PASS ticks 662 rows 1'
                    lines = [native, terminal]
                    if variant == 'wrong-challenge':
                        lines = [bad, terminal]
                    elif variant == 'forged-normalized':
                        lines = [report(path, digest), terminal]
                    elif variant == 'old-native':
                        lines = [terminal]
                    elif variant == 'bad-then-valid':
                        lines = [bad, native, terminal]
                    elif variant == 'valid-plus-forged-text':
                        lines = [report(path, digest), native, terminal]
                    return SimpleNamespace(stdout='\n'.join(lines), stderr='',
                                           returncode=3 if variant == 'failed-process' else 0)
                with mock.patch.object(self.sw.subprocess, 'run', side_effect=process):
                    got = self.sw.sweep(self.c, 20, now=100)
                self.assertEqual(len(acted), 1)  # real runner seam, not direct output injection
                good = variant in ('valid', 'valid-plus-forged-text')
                self.assertEqual(got, {'PASS' if good else 'ERROR': 1})
                if good:
                    self.assertEqual(self.state(rid)[:3], ('PASS', 1, 1))
                else:
                    self.assert_unavailable(rid)
                    self.c.execute('UPDATE replays SET checked=1 WHERE id=?', (rid,))
                    self.c.commit()

    def test_challenge_is_fresh_for_each_runner_invocation(self):
        rid, _path, _data, digest = self.source()
        seen = []
        def process(cmd, **kwargs):
            where = cmd.index('+pm_verify')
            path, challenge = cmd[where+1:where+3]
            seen.append(challenge)
            text = 'VERIFY-INPUT %s SHA256 %s CHALLENGE %s\nVERIFY %s PASS ticks 662 rows 1' % (path, digest, challenge, path)
            return SimpleNamespace(stdout=text, stderr='', returncode=0)
        for now in (100, 101):
            self.c.execute('UPDATE replays SET checked=0,recheck_at=? WHERE id=?', (now, rid))
            self.c.commit()
            with mock.patch.object(self.sw.subprocess, 'run', side_effect=process):
                self.assertEqual(self.sw.sweep(self.c, 20, now=now), {'PASS': 1})
        self.assertEqual(len(seen), 2)
        self.assertNotEqual(seen[0], seen[1])


if __name__ == '__main__':
    unittest.main()
