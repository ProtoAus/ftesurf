#!/usr/bin/env python3
"""The initial optional-panel schema SELECT shares the owned SQL allowance."""
import sqlite3
import unittest
from unittest import mock

import simcheck
from test_admin_metric_bounds import ObservationFixture


class SimilarityProbe(ObservationFixture):
    def test_actual_api_budget_acts_at_initial_schema_probe_and_tears_down(self):
        self.pair(1000, compared=80)
        before = tuple(self.c.iterdump())
        connect = sqlite3.connect
        statements, callbacks, slots, after = [], [], [], []

        class Connection(sqlite3.Connection):
            active = False

            def set_progress_handler(self, handler, interval):
                self.active = handler is not None
                slots.append((self.active, interval))
                if handler is not None:
                    def tick():
                        value = handler()
                        callbacks.append(value)
                        return value
                    return super().set_progress_handler(tick, interval)
                return super().set_progress_handler(None, 0)

            def close(self):
                after.append(self.execute('SELECT SUM(id) FROM sims').fetchone()[0])
                super().close()

        def tracked(*args, **kw):
            c = connect(*args, **dict(kw, factory=Connection))
            c.set_trace_callback(lambda sql: statements.append((sql, c.active)))
            return c

        with mock.patch.object(self.a, 'SIM_SQL_STEPS', 1), mock.patch.object(sqlite3, 'connect', side_effect=tracked):
            value = self.detail()
        probes = [(sql, active) for sql, active in statements if "name='sims'" in sql]
        self.assertEqual(len(probes), 1)
        self.assertTrue(probes[0][1], probes)
        self.assertIn(1, callbacks)  # real SQLite interruption
        self.assertFalse(any('table_info(sims)' in sql for sql, active in statements))
        self.assertFalse(any('FROM sims WHERE' in sql for sql, active in statements))
        self.assertEqual(slots[-1], (False, 0))
        self.assertEqual(len(after), 1)  # actual SQL still works on the cleared slot
        limited = value['similarity']
        self.assertEqual((limited['state'], limited['available'], limited['pairs'], limited['more']),
                         ('read_limit', False, [], False))
        self.assertEqual(value['run']['id'], self.rid)
        normal = self.detail()['similarity']
        self.assertEqual(normal['pairs'][0]['metrics']['compared'], 80)
        self.assertEqual(tuple(self.c.iterdump()), before)
        self.assertEqual(self.m.app.test_client().get(self.route).status_code, 401)

    def test_missing_tiny_allowance_is_unknown_not_confirmed_missing(self):
        self.c.execute('DROP TABLE sims');self.c.commit()
        before = tuple(self.c.iterdump())
        limited = self.a.similarity_for(self.c, self.rid, own_read_budget=True, max_sql_steps=1)
        self.assertEqual(limited['state'], 'read_limit')
        self.assertFalse(limited['available'])
        normal = self.a.similarity_for(self.c, self.rid, own_read_budget=True)
        self.assertEqual(normal['state'], 'missing')
        self.assertEqual(normal['pairs'], [])
        self.assertEqual(tuple(self.c.iterdump()), before)
        simcheck.ensure_schema(self.c)
        empty = self.detail()['similarity']
        self.assertEqual((empty['state'], empty['available'], empty['pairs']), ('ok', True, []))

    def test_borrowed_handler_survives_and_unrelated_errors_still_error(self):
        self.pair(1000, compared=80)
        calls = []
        self.c.set_progress_handler(lambda: calls.append(1) or 0, 1)
        try:
            value = self.a.similarity_for(self.c, self.rid)
            self.assertEqual(value['pairs'][0]['metrics']['compared'], 80)
            n = len(calls)
            self.c.execute('SELECT SUM(id) FROM sims').fetchone()
            self.assertGreater(len(calls), n)
        finally:
            self.c.set_progress_handler(None, 0)
        with mock.patch.object(simcheck, '_read', side_effect=sqlite3.OperationalError('synthetic I/O control')):
            self.assertEqual(self.client.get(self.route).status_code, 500)


if __name__ == '__main__':
    unittest.main()
