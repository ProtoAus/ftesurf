#!/usr/bin/env python3
"""Only the similarity dry-run subsection is non-initializing; not the whole CLI."""
import argparse
import contextlib
import hashlib
import importlib
import io
from pathlib import Path
import sqlite3
import sys
import unittest
from unittest import mock

import simcheck
import test_sweep
from test_admin_metric_bounds import ObservationFixture


class DrySchema(ObservationFixture):
    def setUp(self):
        super().setUp()
        sys.modules.pop('sweep', None)
        self.sw = importlib.import_module('sweep')
        self.sw.TOOLS = str(Path(self.sw.__file__).resolve().parents[1]/'tools')
        self.sw.GAME = self.m.BASE_DIR
        self.peer = test_sweep.add_replay(self.c, self.m.RUNS_DIR, 'bhop_eazy', '0000101_run.rec', make_file=False)
        self.c.execute('DROP TABLE sims')
        self.c.execute('DROP TABLE IF EXISTS sim_cursor')
        self.c.commit()

    def snapshot(self):
        schema = [tuple(r) for r in self.c.execute("SELECT type,name,sql FROM sqlite_master"
                                                 " WHERE name LIKE 'sims%' OR name='sim_cursor' ORDER BY name")]
        rows = [tuple(r) for r in self.c.execute('SELECT * FROM sims')] if any(r[1] == 'sims' for r in schema) else []
        return schema, rows

    def dry(self):
        attempts, traces = [], []
        mutations = {sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_CREATE_INDEX,
                     sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_INSERT,
                     sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE}
        def deny(action, first, second, db, source):
            objects = (first or '', second or '')
            if action in mutations and any(s == 'sim_cursor' or s == 'sims' or s.startswith('sims_') for s in objects):
                attempts.append((action, first, second))
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        self.c.set_authorizer(deny)
        self.c.set_trace_callback(traces.append)
        args = argparse.Namespace(dry_run=True, summary=False, receipts_only=False,
                                  sims_only=False, limit=50, sims=1, sims_sql_steps=1000000)
        out = io.StringIO()
        try:
            with mock.patch.object(self.sw, '_simcheck', return_value=(simcheck, '')), contextlib.redirect_stdout(out):
                self.assertEqual(self.sw._main_connected(self.c, args), 0)
        finally:
            # Python 3.10's None callback can deny cached statements; allow explicitly.
            self.c.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
            self.c.set_trace_callback(None)
        self.assertEqual(attempts, [])  # predecessor tries DDL even with current schema
        self.assertTrue(any('sqlite_master' in sql and 'sims' in sql for sql in traces))
        return out.getvalue(), traces

    def test_absent_stays_absent_and_reports_unavailable(self):
        before = self.snapshot()
        out, traces = self.dry()
        self.assertIn('sims pending: unavailable (table missing)', out)
        self.assertIn('sims: unavailable (table missing)', out)
        self.assertEqual(self.snapshot(), before)

    def test_legacy_remains_exact_and_counts_actual_eligible_candidates(self):
        self.c.executescript(simcheck.SIMS_SQL)
        self.c.execute('ALTER TABLE sims DROP COLUMN source_capture')
        self.c.execute('ALTER TABLE sims DROP COLUMN skip_code')
        self.c.execute("INSERT INTO sims(a_id,b_id,map,track,leg,verdict,reason,at)"
                       " VALUES(800,801,'bhop_eazy',0,0,'skip','synthetic legacy control',1)")
        self.c.commit()
        before = self.snapshot()
        out, traces = self.dry()
        self.assertIn('sims pending: 2 run(s) with unobserved eligible pairs', out)
        self.assertIn('1 pairs, 0 compared, 1 unjudgeable', out)
        self.assertIn('legacy_unknown=1', out)
        self.assertTrue(any('COUNT(*)' in sql and 'FROM replays r' in sql for sql in traces))
        self.assertEqual(self.snapshot(), before)

    def test_current_schema_stays_exact(self):
        simcheck.ensure_schema(self.c)
        before = self.snapshot()
        out, traces = self.dry()
        self.assertIn('sims pending: 2 run(s) with unobserved eligible pairs', out)
        self.assertIn('sims: no pairs stored yet', out)
        self.assertEqual(self.snapshot(), before)

    def test_normal_collector_still_initializes_and_measures_real_sources(self):
        lines = ['FTESURF-REC 9', 'map bhop_eazy', 'track 0', 'leg 0', 'tickrate 100', 'begin']
        lines += ['in %d %d 0 100 0 0 0 0 0 1' % (i, i) for i in range(80)]
        lines += ['end 80']
        folder = Path(self.m.RUNS_DIR)/'bhop_eazy'/'main'
        folder.mkdir(parents=True, exist_ok=True)
        for leaf in ('0000100_run.rec', '0000101_run.rec'):
            (folder/leaf).write_text('\n'.join(lines) + '\n', encoding='utf-8')
        self.assertEqual(self.snapshot(), ([], []))
        stored, notable, note = self.sw.similarity_step(self.c, limit=50, max_pairs=1)
        self.assertEqual((stored, notable), (1, 1))
        row = self.c.execute('SELECT * FROM sims').fetchone()
        self.assertEqual((row['a_id'], row['b_id'], row['verdict'], row['compared']),
                         (self.rid, self.peer, 'compared', 80))
        captured = simcheck.source_snapshot(row['source_capture'])
        raw = (folder/'0000100_run.rec').read_bytes()
        self.assertEqual(captured['a'], {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
        self.assertIsNotNone(self.c.execute("SELECT 1 FROM sqlite_master WHERE name='sim_cursor'").fetchone())


if __name__ == '__main__':
    unittest.main()
