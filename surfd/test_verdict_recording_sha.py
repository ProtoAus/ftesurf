#!/usr/bin/env python3
"""Future per-attempt recording identity: real files/SQLite, acting runner seams.

Native challenge-origin/execution has separate controls. This neither backfills
history, changes badges nor authenticates a hostile OS or today's file forever.
"""
import hashlib
import os
import sqlite3
import threading
import unittest
from types import SimpleNamespace
from unittest import mock

import test_sweep as suite
import test_verifier_counts as counts
import test_verifier_sources as sources


class RecordingSha(unittest.TestCase):
    setUp = counts.Counts.setUp
    cleanup_home = counts.Counts.cleanup_home
    source = sources.Sources.source
    replace = sources.Sources.replace
    run_pass = sources.Sources.run_pass

    def stored(self, rid):
        return [tuple(r) for r in self.c.execute(
            'SELECT verdict,recording_sha256 FROM verdicts WHERE replay_id=? ORDER BY id', (rid,))]

    def drop_identity(self):
        if 'recording_sha256' in {r[1] for r in self.c.execute('PRAGMA table_info(verdicts)')}:
            self.c.execute('ALTER TABLE verdicts DROP COLUMN recording_sha256')
            self.c.commit()

    def test_fresh_column_is_explicit_unknown_by_default(self):
        cols = {r[1]: tuple(r) for r in self.c.execute('PRAGMA table_info(verdicts)')}
        self.assertIn('recording_sha256', cols)
        self.assertEqual(cols['recording_sha256'][2:5], ('TEXT', 1, "''"))
        self.assertEqual(self.c.execute('PRAGMA user_version').fetchone()[0], 20)

    def test_accepted_pass_persists_exact_loaded_digest(self):
        rid, _path, _data, digest = self.source()
        acted, got = self.run_pass()
        self.assertEqual(len(acted), 1)
        self.assertEqual(got, {'PASS': 1})
        self.assertEqual(self.stored(rid), [('PASS', digest)])
        self.assertEqual(self.c.execute('SELECT checked FROM replays WHERE id=?', (rid,)).fetchone()[0], 1)

    def test_bound_hold_and_refuse_retain_their_own_digest(self):
        for i, terminal in enumerate(('HOLD control', 'REFUSE control')):
            rid, _path, _data, digest = self.source(662+i)
            acted = []
            def runner(_map, paths):
                acted.extend(paths)
                return suite.input_bound_stub(self.sw, paths, ['VERIFY '+paths[0]+' '+terminal])
            verdict = terminal.split()[0]
            self.assertEqual(self.sw.sweep(self.c, 20, runner=runner, now=100), {verdict: 1})
            self.assertEqual(len(acted), 1)
            self.assertEqual(self.stored(rid), [(verdict, digest)])

    def test_missing_file_refusal_cannot_claim_consumption(self):
        rid, path, _data, digest = self.source()
        self.assertEqual(len(digest), 64)
        os.unlink(path)
        acted, got = self.run_pass()
        self.assertEqual(acted, [])
        self.assertEqual(got, {'REFUSE': 1})
        self.assertEqual(self.stored(rid), [('REFUSE', '')])

    def test_unaccepted_reports_never_copy_the_known_filing_digest(self):
        for i, variant in enumerate(('missing', 'mismatch', 'duplicate-source', 'duplicate-verdict')):
            with self.subTest(variant=variant):
                rid, _path, _data, digest = self.source(662+i)
                acted = []
                def runner(_map, paths):
                    acted.extend(paths)
                    source = 'VERIFY-SOURCE %s SHA256 %s' % (paths[0], digest)
                    end = 'VERIFY '+paths[0]+' PASS ticks 662 rows 1'
                    if variant == 'missing': return [end]
                    if variant == 'mismatch': return [source.replace(digest, '0'*64), end]
                    if variant == 'duplicate-source': return [source, source, end]
                    return [source, end, end]
                self.assertEqual(self.sw.sweep(self.c, 20, runner=runner, now=100), {'ERROR': 1})
                self.assertEqual(len(acted), 1)
                self.assertEqual(self.stored(rid), [('ERROR', '')])
                self.c.execute('UPDATE replays SET checked=1 WHERE id=?', (rid,))
                self.c.commit()

    def test_failed_actual_runner_exit_cannot_store_a_valid_looking_report(self):
        rid, _path, _data, digest = self.source()
        acted = []
        def process(cmd, **_kwargs):
            i = cmd.index('+pm_verify')
            path, challenge = cmd[i+1:i+3]
            acted.append((path, challenge))
            text = ('VERIFY-INPUT %s SHA256 %s CHALLENGE %s\n'
                    'VERIFY %s PASS ticks 662 rows 1') % (path, digest, challenge, path)
            return SimpleNamespace(stdout=text, stderr='', returncode=3)
        with mock.patch.object(self.sw.subprocess, 'run', side_effect=process):
            self.assertEqual(self.sw.sweep(self.c, 20, now=100), {'ERROR': 1})
        self.assertEqual(len(acted), 1)
        self.assertEqual(self.stored(rid), [('ERROR', '')])

    def test_post_run_replacement_clears_attempt_binding(self):
        rid, path, data, _digest = self.source()
        acted, got = self.run_pass(lambda: self.replace(path, data))
        self.assertEqual(len(acted), 1)
        self.assertEqual(got, {'ERROR': 1})
        self.assertEqual(self.stored(rid), [('ERROR', '')])

    def test_stable_companion_is_not_assigned_the_other_attempt_digest(self):
        bad, _path, _data, _digest = self.source(known=False)
        good, path, data, _digest = self.source(663, known=False)
        with open(path, 'ab') as f:
            f.write(b'# distinct companion bytes\n')
        digest = hashlib.sha256(data+b'# distinct companion bytes\n').hexdigest()
        acted = []
        def runner(_map, paths):
            acted.extend(paths)
            return (['VERIFY-SOURCE %s SHA256 %s' % (paths[0], '0'*64),
                     'VERIFY-SOURCE %s SHA256 %s' % (paths[1], digest)] +
                    sum((counts.section(p, None, 'PASS ticks 662 rows 1') for p in paths), []))
        self.assertEqual(self.sw.sweep(self.c, 20, runner=runner, now=100), {'ERROR': 1, 'PASS': 1})
        self.assertEqual(len(acted), 2)
        self.assertEqual(self.stored(bad), [('ERROR', '')])
        self.assertEqual(self.stored(good), [('PASS', digest)])

    def test_recheck_appends_current_digest_without_rewriting_history_or_filing(self):
        rid, path, data, first = self.source(known=False)
        self.assertEqual(self.run_pass()[1], {'PASS': 1})
        self.replace(path, data)
        with open(path, 'rb') as f:
            second = hashlib.sha256(f.read()).hexdigest()
        self.assertNotEqual(first, second)
        self.c.execute('UPDATE replays SET checked=0,recheck_at=101 WHERE id=?', (rid,))
        self.c.commit()
        self.assertEqual(self.run_pass(now=102)[1], {'PASS': 1})
        self.assertEqual(self.stored(rid), [('PASS', first), ('PASS', second)])
        self.assertEqual(tuple(self.c.execute('SELECT sha,sha_at FROM replays WHERE id=?', (rid,)).fetchone()), ('', 0))

    def test_migration_and_new_attempt_do_not_backfill_legacy_history(self):
        rid, _path, _data, digest = self.source(known=False)
        self.sw.record(self.c, rid, 'PASS', 'historical control', 662, 'e', 'p', 10)
        self.c.commit()
        self.drop_identity()
        before = dict(self.c.execute('SELECT * FROM verdicts').fetchone())
        board = self.m.app.test_client().get('/api/board?map=bhop_eazy').get_json()
        for _ in range(2):
            self.m.migrate()
            self.assertEqual(dict(self.c.execute('SELECT * FROM verdicts').fetchone()),
                             dict(before, recording_sha256=''))
            self.assertEqual(self.m.app.test_client().get('/api/board?map=bhop_eazy').get_json(), board)
        self.c.execute('UPDATE replays SET checked=0,recheck_at=100 WHERE id=?', (rid,))
        self.c.commit()
        self.assertEqual(self.run_pass(now=101)[1], {'PASS': 1})
        self.assertEqual(self.stored(rid), [('PASS', ''), ('PASS', digest)])
        self.assertEqual(tuple(self.c.execute('SELECT sha,sha_at FROM replays WHERE id=?', (rid,)).fetchone()), ('', 0))
        client = self.m.app.test_client()
        route = '/admin/api/run/%d' % rid
        self.assertEqual(client.get(route).status_code, 401)
        self.assertEqual(counts.at.login(client, 'test password only').status_code, 302)
        self.assertNotIn('recording_sha256', client.get(route).get_json()['verdicts'][0])

    def test_ensure_schema_repairs_only_the_missing_column(self):
        rid, _path, _data, _digest = self.source()
        self.sw.record(self.c, rid, 'PASS', 'legacy control', 662, 'e', 'p', 1)
        self.c.commit()
        self.drop_identity()
        before = dict(self.c.execute('SELECT * FROM verdicts').fetchone())
        self.sw.ensure_schema(self.c)
        self.assertEqual(dict(self.c.execute('SELECT * FROM verdicts').fetchone()),
                         dict(before, recording_sha256=''))

    def test_simultaneous_additive_migration_and_real_io_error(self):
        rid, _path, _data, _digest = self.source()
        self.sw.record(self.c, rid, 'PASS', 'legacy control', 662, 'e', 'p', 1)
        self.c.commit()
        self.drop_identity()
        before = dict(self.c.execute('SELECT * FROM verdicts').fetchone())
        barrier, observed, errors = threading.Barrier(2), [], []
        def migrate():
            c = sqlite3.connect(self.m.DB_PATH, timeout=10)
            try:
                class Paused:
                    def execute(_self, sql):
                        if sql.startswith('PRAGMA'):
                            rows = c.execute(sql).fetchall()
                            observed.append('recording_sha256' not in {r[1] for r in rows})
                            barrier.wait(timeout=5)
                            return rows
                        return c.execute(sql)
                self.m.verdict_metrics(Paused())
                c.commit()
            except Exception as error:
                errors.append(error)
            finally:
                c.close()
        workers = [threading.Thread(target=migrate) for _ in range(2)]
        for w in workers: w.start()
        for w in workers: w.join(timeout=15)
        self.assertFalse(any(w.is_alive() for w in workers))
        self.assertEqual(observed, [True, True])
        self.assertEqual(errors, [])
        self.assertEqual(dict(self.c.execute('SELECT * FROM verdicts').fetchone()),
                         dict(before, recording_sha256=''))
        class IOFailure:
            def execute(_self, sql):
                if sql.startswith('PRAGMA'): return [(0, 'counts_metrics')]
                raise sqlite3.OperationalError('synthetic disk I/O error')
        with self.assertRaisesRegex(sqlite3.OperationalError, 'disk I/O'):
            self.m.verdict_metrics(IOFailure())

    def test_digest_and_checked_update_roll_back_as_one_attempt(self):
        rid, _path, _data, digest = self.source()
        before = tuple(self.c.execute('SELECT seen,checked FROM replays WHERE id=?', (rid,)).fetchone())
        self.c.execute("CREATE TRIGGER fail_checked BEFORE UPDATE OF checked ON replays "
                       "BEGIN SELECT RAISE(ABORT,'synthetic checked failure'); END")
        self.c.commit()
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'synthetic checked failure'):
            self.run_pass()
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM verdicts').fetchone()[0], 0)
        self.assertEqual(tuple(self.c.execute('SELECT seen,checked FROM replays WHERE id=?', (rid,)).fetchone()), before)
        self.assertFalse(self.c.in_transaction)
        self.c.execute('DROP TRIGGER fail_checked')
        self.c.commit()
        self.assertEqual(self.run_pass(now=101)[1], {'PASS': 1})
        self.assertEqual(self.stored(rid), [('PASS', digest)])


if __name__ == '__main__':
    unittest.main()
