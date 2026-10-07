"""Collector and authenticated history distinguish skips from measured zero."""
import importlib
import logging
import os
from pathlib import Path
import shutil
import sys
import unittest
from unittest import mock

import admin
import test_admin as at
import test_sweep as suite

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from test_recsim_parsing import recording, rs


class Observations(unittest.TestCase):
    def setUp(self):
        self.start = len(at.HOMES)
        self.handlers = []
        self.addCleanup(self.cleanup)
        self.m = at.fresh(SURFD_ADMIN_HASH=admin.hash_password('test password only', n=2**10),
                          SURFD_ADMIN_SECRET='temporary-test-secret-not-a-real-secret',
                          SURFD_ADMIN_INSECURE_COOKIE='1')
        self.handlers = self.m.log.handlers[:]
        self.admin = importlib.import_module('admin')
        self.sim = importlib.import_module('simcheck')
        self.c = self.m.connect(); self.addCleanup(self.c.close)
        self.aid = suite.add_replay(self.c, self.m.RUNS_DIR, 'synthetic', '0000080_run.rec', make_file=False)
        self.bid = suite.add_replay(self.c, self.m.RUNS_DIR, 'synthetic', '0000081_run.rec', make_file=False)
        self.c.execute("UPDATE replays SET kind='run' WHERE id IN (?,?)", (self.aid, self.bid))
        self.c.commit()
        root = Path(self.m.RUNS_DIR) / 'synthetic/main'
        root.mkdir(parents=True, exist_ok=True)
        self.a = root/'0000080_run.rec'; self.b = root/'0000081_run.rec'
        self.a.write_text(recording()); self.b.write_text(recording())
        self.client = self.m.app.test_client()
        self.assertEqual(at.login(self.client, 'test password only').status_code, 302)
        patch = mock.patch.object(self.sim, '_recsim', return_value=(rs, 'test reader'))
        patch.start(); self.addCleanup(patch.stop)

    def cleanup(self):
        logger = logging.getLogger('surfd')
        for home in at.HOMES[self.start:]:
            for handler in set(self.handlers + logger.handlers[:]):
                if getattr(handler, 'baseFilename', '').startswith(os.path.abspath(home)+os.sep):
                    logger.removeHandler(handler); handler.close()
            if os.path.exists(home):
                shutil.rmtree(home)
            self.assertFalse(os.path.exists(home))

    def collect(self):
        self.assertEqual(self.sim.similarity_step(self.c, self.m, limit=10)[0], 1)
        stored = self.c.execute('SELECT * FROM sims').fetchone()
        route = '/admin/api/run/%d' % self.aid
        self.assertEqual(self.m.app.test_client().get(route).status_code, 401)
        reply = self.client.get(route)
        self.assertEqual(reply.status_code, 200)
        projected = reply.get_json()['similarity']['pairs'][0]
        self.assertNotIn('0000080', projected['reason'])
        self.assertNotIn('sims', self.m.VER_SQL)
        return stored, projected

    def test_valid_control(self):
        stored, projected = self.collect()
        self.assertEqual((stored['verdict'], stored['match'], stored['compared']), ('compared', 1.0, 80))
        self.assertEqual(projected['metrics']['match'], 1.0)

    def test_malformed_item_one(self):
        self.a.write_text(recording().replace('in 40 40 0', 'in 40 nan 0'))
        stored, projected = self.collect()
        self.assertEqual(stored['verdict'], 'skip')
        self.assertEqual(stored['compared'], 0)
        self.assertEqual(stored['reason'], 'malformed required move-stream input')
        self.assertIsNone(projected['metrics'])
        self.assertEqual(projected['reason'], 'unjudgeable (legacy detail withheld)')

    def test_measured_zero_item_two(self):
        self.b.write_text(recording(other=True))
        stored, projected = self.collect()
        self.assertEqual((stored['verdict'], stored['match']), ('compared', 0.0))
        self.assertGreater(stored['compared'], 0)
        self.assertEqual(projected['metrics']['match'], 0.0)
        self.assertGreater(projected['metrics']['compared'], 0)

    def test_unreadable_item_three(self):
        with mock.patch.object(rs, 'open', side_effect=PermissionError('synthetic denial'), create=True):
            stored, projected = self.collect()
        self.assertEqual((stored['verdict'], stored['compared']), ('skip', 0))
        self.assertIn('synthetic denial', stored['reason'])
        self.assertIsNone(projected['metrics'])
        self.assertEqual(projected['reason'], 'unjudgeable (legacy detail withheld)')

    def test_no_rows_control(self):
        self.a.write_text('begin\n')
        stored, projected = self.collect()
        self.assertEqual((stored['verdict'], stored['compared']), ('skip', 0))
        self.assertIsNone(projected['metrics'])
        self.assertEqual(projected['reason'], 'no sample rows')


if __name__ == '__main__':
    unittest.main()
