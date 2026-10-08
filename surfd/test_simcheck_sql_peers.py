"""Peer-query VM abstention and preservation of earlier measured observations."""
import sqlite3
import unittest
from types import SimpleNamespace
from unittest import mock

import test_simcheck_sql_sources as controls

sc = controls.sc
fixture = controls.fixture


class PeerConnection(controls.TrackedConnection):
    def execute(self, sql, parameters=()):
        self.current_sql = sql
        return super().execute(sql, parameters)

    def set_progress_handler(self, callback, quantum):
        def track():
            result = callback()
            if result: self.interrupts.append(self.current_sql)
            return result
        return super().set_progress_handler(track if callback else None, quantum)


class SqlPeers(unittest.TestCase):
    def setUp(self):
        fixture.StoredSources.setUp(self)
        self.conn.close()
        self.conn = sqlite3.connect(str(self.db), factory=PeerConnection)
        self.conn.row_factory=sqlite3.Row; self.conn.handlers=[]; self.conn.interrupts=[]
        self.addCleanup(self.conn.close)

    def row(self): return self.conn.execute('SELECT * FROM replays WHERE id=1').fetchone()

    def run_source(self, obj, reader=fixture.rs, pairs=2):
        with mock.patch.object(sc,'_recsim',return_value=(reader,'')):
            return sc.compare_run(self.sf,self.conn,self.row(),limit_peers=pairs,
                                  **controls.options(sc.compare_run,obj))

    def test_costly_peer_read_has_no_partial_admission_and_releases_handler(self):
        self.conn.executemany("INSERT INTO replays VALUES (?,'synthetic',0,0,'run','','s')",
                              [(i,) for i in range(4,2004)])
        self.conn.commit()
        resolved=[]; old=self.sf.replay_file
        self.sf.replay_file=lambda row:(resolved.append(row['id']) or old(row))
        obj=controls.budget(self.conn,5000)
        caught=False
        try: self.run_source(obj,pairs=1)
        except getattr(sc,'ReadLimit',RuntimeError): caught=True
        self.assertTrue(caught)
        self.assertTrue(any('FROM replays p' in sql for sql in self.conn.interrupts))
        self.assertEqual(resolved,[])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0],0)
        self.assertEqual(sc._cursor(self.conn,'peer',1),0)
        self.assertEqual(self.conn.handlers[-1],(False,0))
        self.assertFalse(self.conn.in_transaction)
        # Same database, fresh allowance, native 80-opportunity ACTED positive.
        self.assertEqual(self.run_source(controls.budget(self.conn,1000000),pairs=1),(1,0,1))
        self.assertEqual(self.conn.execute('SELECT compared FROM sims').fetchone()[0],80)

    def test_late_check_exhaustion_flushes_prior_success_not_fake_skip(self):
        obj=controls.budget(self.conn,1000000)
        acted=[]
        def compare(a,b,**kw):
            self.assertFalse(self.conn.handlers and self.conn.handlers[-1][0])
            self.assertFalse(self.conn.in_transaction)
            result=fixture.rs.compare_paths(a,b,**kw)
            acted.append(result[1]['compared'])
            if obj is not None: obj.remaining=0  # only dimension: next SQL admission
            return result
        result=self.run_source(obj,SimpleNamespace(compare_paths=compare),pairs=2)
        self.assertEqual(result,(1,0,1))
        self.assertEqual(acted,[80])
        rows=self.conn.execute('SELECT a_id,b_id,verdict,compared FROM sims').fetchall()
        self.assertEqual([tuple(r) for r in rows],[(1,2,'compared',80)])
        self.assertEqual(sc._cursor(self.conn,'peer',1),2)
        self.assertTrue(obj.exhausted)
        self.assertEqual(self.conn.handlers[-1],(False,0))
        self.assertEqual(self.run_source(controls.budget(self.conn,1000000)),(1,0,1))
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0],2)

    def test_step_reports_peer_query_limit_once_without_source_prose(self):
        obj=controls.budget(self.conn,1000000)
        original=sc.compare_run; calls=[]
        def peers(*args,**kwargs):
            calls.append(1)
            if obj is not None: obj.remaining=0
            return original(*args,**kwargs)
        with mock.patch.object(sc,'compare_run',side_effect=peers):
            out=sc.similarity_step(self.conn,self.sf,tools_dir=str(fixture.ROOT/'tools'),
                                  max_seconds=30,**controls.options(sc.similarity_step,obj))
        self.assertEqual(out[:2],(0,0))
        self.assertEqual(out[2].count('SQL read limit'),1)
        self.assertIn('coverage not measured',out[2])
        self.assertEqual(calls,[1])
        self.assertNotIn('row failed',out[2])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0],0)

    def test_high_budget_preserves_orientation_exclusion_and_cursor(self):
        self.assertEqual(self.run_source(controls.budget(self.conn,1000000),pairs=1),(1,0,1))
        old=tuple(self.conn.execute('SELECT * FROM sims').fetchone())
        self.assertEqual(self.run_source(controls.budget(self.conn,1000000)),(1,0,1))
        self.assertEqual(tuple(self.conn.execute('SELECT * FROM sims WHERE id=?',(old[0],)).fetchone()),old)
        self.assertEqual(sc._cursor(self.conn,'peer',1),3)
        self.assertEqual([r[0] for r in self.conn.execute('SELECT compared FROM sims')],[80,80])

if __name__=='__main__': unittest.main()
