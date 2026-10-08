"""Authenticated historical byte provenance, narrow projection and real DOM."""
import json
import unittest
from unittest import mock

import simcheck as sc
import test_admin_similarity as baseline


def snap():
    return {'version':1, 'a':{'sha256':'a'*64,'bytes':1204},
            'b':{'sha256':'b'*64,'bytes':1210}}


class Sources(baseline.Similarity):
    def install_snapshot(self, value):
        self.peer=baseline.suite.add_replay(self.c,self.m.RUNS_DIR,'bhop_eazy','0000101_run.rec')
        self.pair(self.peer)
        # Behavioral predecessor red: ignore the missing additive column.
        if 'source_capture' in {r[1] for r in self.c.execute('PRAGMA table_info(sims)')}:
            self.c.execute('UPDATE sims SET source_capture=? WHERE b_id=?',(value,self.peer))
            self.c.commit()

    def selected(self, out):
        return next(p for p in out['pairs'] if p['b_id']==self.peer)

    def test_authenticated_positive_capture_is_historical_and_text_only(self):
        self.install_snapshot(json.dumps(snap()))
        self.assertEqual(self.m.app.test_client().get(self.route).status_code,401)
        with mock.patch.object(sc,'_recsim',side_effect=AssertionError('reader must not execute')), \
             mock.patch.object(self.m,'replay_file',side_effect=AssertionError('source must not resolve')):
            out=self.detail()['similarity']
        pair=self.selected(out)
        self.assertEqual(pair['metrics']['compared'],80)  # acted measured fixture
        self.assertEqual(pair.get('sources'),snap())
        self.assertEqual(pair.get('source_state'),'captured')
        self.assertFalse(out['source_binding'])  # never a current-file claim
        text=self.render_dom(out)['text']
        for value in ('historical comparison','current files and authenticity not assessed',
                      'A SHA-256','a'*64,'B SHA-256','b'*64,'1204','1210'):
            self.assertIn(value,text)
        self.assertNotIn('source-byte provenance unavailable',text)

    def test_capture_orientation_is_not_swapped_when_viewing_b(self):
        self.install_snapshot(json.dumps(snap()))
        out=self.detail(self.peer)['similarity'];pair=self.selected(out)
        self.assertEqual((pair['a_id'],pair['b_id']),(self.rid,self.peer))
        self.assertEqual(pair.get('sources'),snap())

    def test_legacy_schema_is_read_only_and_explicitly_unbound(self):
        self.install_snapshot('')
        if 'source_capture' in {r[1] for r in self.c.execute('PRAGMA table_info(sims)')}:
            self.c.execute('ALTER TABLE sims DROP COLUMN source_capture');self.c.commit()
        before=[tuple(r) for r in self.c.execute('PRAGMA table_info(sims)')]
        out=self.detail()['similarity'];pair=self.selected(out)
        self.assertEqual(pair['metrics']['compared'],80)
        self.assertIsNone(pair.get('sources'));self.assertEqual(pair.get('source_state'),'legacy_unbound')
        self.assertIn('source-byte provenance unavailable (legacy/unbound observation)',self.render_dom(out)['text'])
        self.assertEqual([tuple(r) for r in self.c.execute('PRAGMA table_info(sims)')],before)

    def test_invalid_empty_future_oversized_and_skip_capture_do_not_hide_metrics(self):
        self.install_snapshot('')
        bad=['','{','['*1000,json.dumps(snap())+' '*1000,
             json.dumps(snap())+'\x00'+'x'*100000,
             json.dumps(snap())+'\x00',sc.sqlite3.Binary(b'\xff\x00')]
        for mutate in (lambda v:v.update(version=99),lambda v:v['a'].update(bytes=True),
                       lambda v:v['a'].update(path='<img src=x onerror=bad()>'),
                       lambda v:v['a'].update(sha256='<script>bad</script>')):
            value=snap();mutate(value);bad.append(json.dumps(value))
        for raw in bad:
            with self.subTest(raw=raw[:30]):
                self.c.execute('UPDATE sims SET source_capture=? WHERE b_id=?',(raw,self.peer));self.c.commit()
                out=self.detail()['similarity'];pair=self.selected(out)
                self.assertIsNone(pair.get('sources'))
                self.assertEqual(pair.get('source_state'),'legacy_unbound' if raw=='' else 'unavailable')
                self.assertEqual(pair['metrics']['compared'],80)
                self.assertNotIn('onerror',json.dumps(out));self.assertNotIn('bad</script>',json.dumps(out))
        self.c.execute("UPDATE sims SET verdict='skip',source_capture=? WHERE b_id=?",(json.dumps(snap()),self.peer));self.c.commit()
        pair=self.selected(self.detail()['similarity'])
        self.assertIsNone(pair.get('sources'));self.assertIsNone(pair['metrics'])

    def test_projection_limits_sql_payload_before_json_parser(self):
        self.install_snapshot('x'*100000)
        seen=[];project=sc.source_snapshot
        def spy(raw):seen.append(len(raw));return project(raw)
        with mock.patch.object(sc,'source_snapshot',side_effect=spy):
            out=self.a.similarity_for(self.c,self.rid)
        self.assertEqual(len(out['pairs']),1)
        self.assertTrue(seen);self.assertLessEqual(max(seen),513)
        self.assertEqual(max(seen),513)  # oversized source really visited, not hidden


if __name__=='__main__':unittest.main()
