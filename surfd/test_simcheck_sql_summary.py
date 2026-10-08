"""Whole-summary SQL instruction limits never invent empty/zero/calibration."""
import sqlite3
import unittest

import test_simcheck_sql_sources as controls
import test_simcheck_sql_peers as peers

sc=controls.sc


class SqlSummary(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:',factory=peers.PeerConnection)
        self.addCleanup(self.conn.close)
        self.conn.row_factory=sqlite3.Row; self.conn.handlers=[]; self.conn.interrupts=[]
        sc.ensure_schema(self.conn)

    def seed(self,n=1000):
        self.conn.executemany("INSERT INTO sims (a_id,b_id,map,track,leg,verdict,at,match,compared,who_a,who_b,same_who,skip_code) VALUES (?,?,'synthetic',0,0,?,1,?,80,?,?,?,?)",
            [(i,i+10000,'skip' if i%5==0 else 'compared',i%101/100.,
              '' if i%3==0 else 'a','b',i%2,'too_short' if i%5==0 else '')
             for i in range(1,n+1)])
        self.conn.commit()

    def summary(self,steps):
        return sc.summary(self.conn,**controls.options(sc.summary,controls.budget(self.conn,steps)))

    def line(self,steps):
        return sc.summary_line(self.conn,**controls.options(sc.summary_line,controls.budget(self.conn,steps)))

    def test_costly_sample_is_limited_not_prefix_zero_or_false_empty(self):
        self.seed()
        before=tuple(self.conn.iterdump())
        out=self.summary(10000)
        self.assertEqual(out['state'],'limited')
        self.assertTrue(all(value is None for key,value in out.items() if key!='state'))
        self.assertTrue(any('FROM sims GROUP BY' in sql for sql in self.conn.interrupts))
        self.assertEqual(self.line(10000),'sims: unavailable (SQL read limit; sample not measured)')
        self.assertNotIn('no pairs',self.line(10000)); self.assertNotIn('max',self.line(10000))
        self.assertEqual(self.conn.handlers[-1],(False,0))
        self.assertEqual(tuple(self.conn.iterdump()),before)
        self.assertFalse(self.conn.in_transaction)
        out=self.summary(1000000)
        self.assertEqual(out,sc.summary(self.conn))
        self.assertEqual((out['pairs'],out['compared'],out['skipped']),(1000,800,200))

    def test_metadata_exhaustion_is_limited_not_missing_or_error(self):
        self.seed(1)
        self.assertEqual(self.summary(1)['state'],'limited')
        self.assertEqual(self.conn.handlers[-1],(False,0))
        self.assertEqual(self.summary(100000)['state'],'available')

    def test_empty_missing_and_query_denial_stay_distinct_and_recover(self):
        self.assertEqual(self.summary(100000)['state'],'empty')
        self.assertEqual(self.line(100000),'sims: no pairs stored yet')
        self.seed(1); acted=[]
        def authorize(action,table,column,*rest):
            if action==sqlite3.SQLITE_READ and table=='sims':
                acted.append(column); return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        self.conn.set_authorizer(authorize)
        self.assertEqual(self.summary(100000)['state'],'error'); self.assertTrue(acted)
        self.assertEqual(self.line(100000),'sims: unavailable (query error)')
        self.assertFalse(self.conn.handlers and self.conn.handlers[-1][0])
        self.conn.set_authorizer(lambda *args:sqlite3.SQLITE_OK)
        self.assertEqual(self.summary(100000)['pairs'],1)
        self.conn.execute('DROP TABLE sims'); self.conn.commit()
        self.assertEqual(self.summary(100000)['state'],'missing')

    def test_old_schema_is_read_only_and_preserves_legacy_unknown(self):
        self.seed(5)
        self.conn.execute('ALTER TABLE sims DROP COLUMN skip_code'); self.conn.commit()
        before=tuple(self.conn.iterdump())
        out=self.summary(100000)
        self.assertEqual(out,sc.summary(self.conn))
        self.assertEqual(out['skip_codes'],{'legacy_unknown':1})
        self.assertEqual(tuple(self.conn.iterdump()),before)

    def test_unbudgeted_summary_does_not_clear_caller_callback(self):
        self.seed(20); calls=[]
        self.conn.set_progress_handler(lambda:calls.append(1) or 0,1)
        out=sc.summary(self.conn)
        self.assertEqual(out['pairs'],20); self.assertTrue(calls)
        before=len(calls); self.conn.execute('SELECT 1').fetchall()
        self.assertGreater(len(calls),before)
        self.conn.set_progress_handler(None,0)

if __name__=='__main__': unittest.main()
