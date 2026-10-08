"""One actual reader load per enabled pass; replacements are next-pass state."""
from pathlib import Path
import unittest
from unittest import mock

import test_simcheck_sources as fixture

sc = fixture.sc


class PassReader(unittest.TestCase):
    setUp = fixture.StoredSources.setUp

    def setUp(self):
        fixture.StoredSources.setUp(self)
        self.tools = self.root/'tools'; (self.tools/'census').mkdir(parents=True)
        self.target = self.tools/'census/recsim.py'
        self.code = (fixture.ROOT/'tools/census/recsim.py').read_bytes()
        self.target.write_bytes(self.code+b"\nREVISION = 'before'\n")
        self.after = self.code+b"\nREVISION = 'after'\n"
        self.loads = []; self.calls = []
        self.real_load = sc._recsim

    def load(self, tools):
        self.assertEqual(tools, str(self.tools))
        mod, why = self.real_load(tools)
        self.loads.append(mod.REVISION if mod else None)
        if mod:
            original = mod.compare_paths
            def compare(a, b, **kw):
                self.assertFalse(self.conn.in_transaction)
                verdict, data = original(a, b, **kw)
                self.assertEqual((verdict, data['compared']), ('compared',80))
                self.calls.append(mod.REVISION)
                if len(self.calls) == 1:
                    self.target.write_bytes(self.after)
                    self.assertEqual(self.target.read_bytes(), self.after)
                return verdict, data
            mod.compare_paths = compare
        return mod, why

    def step(self, **kw):
        return sc.similarity_step(self.conn, self.sf, tools_dir=str(self.tools),
                                  max_seconds=30., **kw)

    def test_midpass_replacement_acts_only_next_pass_and_missing_never_cached(self):
        with mock.patch.object(sc, '_recsim', side_effect=self.load):
            self.assertEqual(self.step()[:2], (3,3))
            self.assertEqual(self.calls, ['before']*3)
            self.assertEqual(self.loads, ['before'])
            # New source gives the next pass real work and a distinguishable reader.
            self.conn.execute("INSERT INTO replays VALUES(4,'synthetic',0,0,'run','ranked','synthetic')")
            self.conn.commit(); self.paths[4] = self.root/'4.rec'
            self.paths[4].write_bytes(fixture.source())
            self.assertEqual(self.step()[:2], (3,3))
            self.assertEqual(self.calls, ['before']*3+['after']*3)
            self.assertEqual(self.loads, ['before','after'])
            self.target.unlink()
            out = self.step()
            self.assertEqual(out[:2], (0,0))
            self.assertIn('similarity skipped', out[2])
            self.assertEqual(self.loads, ['before','after',None])
            self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0],6)

    def test_direct_caller_still_resolves_explicit_tools_and_reloads(self):
        row = self.conn.execute('SELECT * FROM replays WHERE id=1').fetchone()
        with mock.patch.object(sc, '_recsim', side_effect=self.load):
            self.assertEqual(sc.compare_run(self.sf,self.conn,row,limit_peers=1,
                                            tools_dir=str(self.tools)), (1,0,1))
            self.assertEqual(sc.compare_run(self.sf,self.conn,row,limit_peers=1,
                                            tools_dir=str(self.tools)), (1,0,1))
        self.assertEqual(self.loads, ['before','after'])
        self.assertEqual(self.calls, ['before','after'])

    def test_disabled_pass_has_no_load_or_database_mutation(self):
        before = tuple(self.conn.iterdump())
        with mock.patch.object(sc, '_recsim', side_effect=AssertionError('disabled load')):
            self.assertEqual(self.step(max_pairs=0), (0,0,''))
        self.assertEqual(tuple(self.conn.iterdump()), before)


if __name__ == '__main__': unittest.main()
