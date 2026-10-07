"""Typed skips are captured observations, never retrospective classifications."""
import sqlite3
import unittest
from unittest import mock
from test_simcheck_collection import simcheck
import admin

class SkipCodes(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:');self.conn.row_factory=sqlite3.Row
        self.addCleanup(self.conn.close)
        simcheck.ensure_schema(self.conn)
        self.conn.execute('CREATE TABLE replays (id INTEGER PRIMARY KEY,map TEXT,track INTEGER,leg INTEGER,kind TEXT,tier TEXT,player TEXT)')
        for i in (1,2):self.conn.execute("INSERT INTO replays VALUES (?,'synthetic',0,0,'run','ranked','synthetic')",(i,))
        self.conn.commit()
        self.sf=mock.Mock();self.sf.replay_file.side_effect=lambda r:(str(r['id']),'')
        self.reader=mock.Mock()

    def collect(self, verdict, detail):
        self.reader.reset_mock()
        self.reader.compare_paths.return_value=(verdict,detail)
        with mock.patch.object(simcheck,'_recsim',return_value=(self.reader,'')):
            result=simcheck.similarity_step(self.conn,self.sf)
        self.reader.compare_paths.assert_called_once()  # comparison ACTED
        return result,self.conn.execute('SELECT * FROM sims').fetchone()

    def code(self,row):
        return row['skip_code'] if 'skip_code' in row.keys() else None

    def test_reader_categories_persist_independently_of_prose(self):
        categories={'unreadable':'unreadable','no sample rows':'no_rows',
                    'too short':'too_short','same file':'same_file',
                    'malformed input':'malformed','no comparison opportunities':'no_opportunities',
                    'source limit':'source_limit','unexpected private detail':'unknown'}
        for verdict,code in categories.items():
            self.conn.execute('DELETE FROM sims');self.conn.commit()
            result,row=self.collect(verdict,'private path and exception prose')
            self.assertEqual(result[:2],(1,0))
            self.assertEqual((row['verdict'],row['compared']),( 'skip',0))
            self.assertEqual(self.code(row),code)
            summary=simcheck.summary(self.conn)
            self.assertEqual(summary.get('skip_codes'),{code:1})
            self.assertNotIn('private',simcheck.summary_line(self.conn))

    def test_unresolved_peer_has_a_fixed_code(self):
        self.sf.replay_file.side_effect=lambda r: (str(r['id']),'') if r['id']==1 else (None,'private location')
        with mock.patch.object(simcheck,'_recsim',return_value=(self.reader,'')):
            result=simcheck.similarity_step(self.conn,self.sf,max_pairs=1)
        self.reader.compare_paths.assert_not_called()
        self.assertEqual(result[:2],(1,0))
        self.assertEqual(self.code(self.conn.execute('SELECT * FROM sims').fetchone()),'peer_unresolved')

    def test_compared_control_has_no_skip_code(self):
        result,row=self.collect('compared',dict(match=1.,cover=1.,prefix=80,offset=0,compared=80,
                  moves_a=80,moves_b=80,tickrate_a=100.,tickrate_b=100.,who_a='',who_b='',same_who=False))
        self.assertEqual(result[:2],(1,1));self.assertEqual(row['compared'],80)
        self.assertEqual(self.code(row),'')
        self.assertEqual(simcheck.summary(self.conn).get('skip_codes'),{})

    def test_legacy_read_is_mutation_free_then_additive_ensure_twice(self):
        self.conn.execute('DROP TABLE sims')
        legacy=simcheck.SIMS_SQL.replace("    skip_code   TEXT NOT NULL DEFAULT '',\n",'')
        self.conn.executescript(legacy)
        self.conn.execute("INSERT INTO sims(a_id,b_id,map,track,leg,verdict,reason,at) VALUES (1,2,'synthetic',0,0,'skip','private unknown reason',1)")
        self.conn.commit()
        before=[tuple(r) for r in self.conn.execute('SELECT * FROM sims')]
        self.assertEqual(simcheck.summary(self.conn).get('skip_codes'),{'legacy_unknown':1})
        projected=admin.similarity_for(self.conn,1)['pairs'][0]
        self.assertEqual(projected.get('skip_code'),'legacy_unknown')
        self.assertNotIn('private',str(projected))
        self.assertEqual([tuple(r) for r in self.conn.execute('SELECT * FROM sims')],before)
        simcheck.ensure_schema(self.conn);simcheck.ensure_schema(self.conn)
        row=self.conn.execute('SELECT * FROM sims').fetchone()
        self.assertEqual(self.code(row),'')
        self.assertEqual(row['reason'],'private unknown reason')
        self.assertEqual(simcheck.summary(self.conn)['skip_codes'],{'legacy_unknown':1})

    def test_admin_uses_only_fixed_codes_and_hides_raw_detail(self):
        _,row=self.collect('source limit','private path or exception')
        projected=admin.similarity_for(self.conn,1)['pairs'][0]
        self.assertEqual(projected.get('skip_code'),'source_limit')
        self.assertEqual(projected['reason'],'source ingestion limit')
        self.assertIsNone(projected['metrics'])
        self.assertNotIn('private',str(projected))
        self.assertEqual(row['reason'],'private path or exception')
        self.conn.execute("UPDATE sims SET skip_code='private-unrecognized'");self.conn.commit()
        projected=admin.similarity_for(self.conn,1)['pairs'][0]
        self.assertEqual(projected['skip_code'],'unknown')
        self.assertNotIn('private',str(projected))

if __name__=='__main__':unittest.main()
