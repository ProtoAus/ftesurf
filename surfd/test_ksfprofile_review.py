#!/usr/bin/env python3
"""Acted P1142 review regressions, using the existing local-only KSF fixture."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_ksfprofile as T
K, P, PLAYER = T.K, T.P, T.PLAYER


class Review(unittest.TestCase):
    setUp = T.Profiles.setUp
    tearDown = T.Profiles.tearDown
    queue = T.Profiles.queue
    step = T.Profiles.step
    count = T.Profiles.count
    stage_world = T.Profiles.stage_world
    at_stage = T.Profiles.at_stage
    zones = T.Profiles.zones

    def test_invalid_main_semantics_are_not_sanitized_to_null(self):
        self.src.n = 1
        original = self.src
        for field in ('stage_id', 'zone_id'):
            for bad in ({'id': 1}, [1], 'x' * 257):
                with self.subTest(field=field, bad=type(bad).__name__):
                    self.db.execute('DELETE FROM ksfprofiles')
                    self.db.execute('DELETE FROM runs'); self.db.commit()
                    self.queue(now=1000)
                    def fetch(url, field=field, bad=bad):
                        doc = json.loads(original(url))
                        doc['records'][0][field] = bad
                        return json.dumps(doc)
                    with patch.object(K, 'fetch', side_effect=fetch):
                        self.step()
                    self.assertEqual(self.count(), 0)
                    self.assertEqual(P.status(self.db, PLAYER)['unavailable'], 1)
                    for page in Path(self.cache, 'profiles').rglob('0-1.json'):
                        page.unlink()
        self.db.execute('DELETE FROM ksfprofiles'); self.db.commit()
        self.queue(now=2000); self.step()
        self.assertEqual(self.count(), 1)  # valid nulls remain MAIN

    def test_stage_cursor_keeps_map_and_zone_identities(self):
        self.stage_world()
        initial = [('surf_profile0', {1}), ('surf_profile1', {1}), ('surf_profile2', {1})]
        with patch.object(P, 'stage_maps', return_value=initial):
            P.step(K, self.cache, K.Pacer(0, 10), self.have, 3000, 5)
        self.assertEqual(P.status(self.db, PLAYER)['next'], 1)
        before = len(self.src.calls)
        changed = [('surf_profile-1', {9}), ('surf_profile1', {2}), ('surf_profile2', {3})]
        with patch.object(P, 'stage_maps', return_value=changed):
            P.step(K, self.cache, K.Pacer(0, 10), self.have, 3001, 2)
        asked = [x.split('/records/map/')[1] for x in self.src.calls[before:]
                 if '/records/map/' in x]
        self.assertEqual(asked, ['surf_profile1?game=css&mode=0', 'surf_profile2?game=css&mode=0'])
        for mp in ('surf_profile1', 'surf_profile2'):
            self.assertEqual([(r[0], r[1]) for r in self.zones(mp)], [(0, 0), (0, 1)])

    def test_stage_snapshot_replays_after_filing_before_ack(self):
        self.at_stage()
        with patch.object(P, 'advance', side_effect=RuntimeError('before stage ack')):
            with self.assertRaisesRegex(RuntimeError, 'before stage ack'):
                self.step()
        before = [tuple(r) for r in self.zones()]
        self.assertEqual(P.status(self.db, PLAYER)['next'], 0)
        with patch.object(P, 'stage_maps', return_value=[]), \
                patch.object(K, 'fetch', side_effect=AssertionError('durable replay must not ask')):
            got = P.stage_step(K, self.cache, K.Pacer(0, 0), self.have, 3002, PLAYER,
                               K.S.steam2(PLAYER), P.STAGE_MODE, 0, 1000, False)
        self.assertEqual(got, (0, 'partial', P.STAGE_MODE, 1))
        self.assertEqual([tuple(r) for r in self.zones()], before)

    def test_old_stage_offset_without_snapshot_rewinds(self):
        self.at_stage()
        for f in Path(self.cache, 'profiles').rglob('stage-maplist-0.json'):
            f.unlink()
        self.db.execute('UPDATE ksfprofiles SET cursor=1'); self.db.commit()
        with patch.object(K, 'fetch', side_effect=AssertionError('rewind must not ask')):
            got = P.stage_step(K, self.cache, K.Pacer(0, 0), self.have, 3002, PLAYER,
                               K.S.steam2(PLAYER), P.STAGE_MODE, 1, 1000, False)
        self.assertEqual(got, (0, 'partial', P.STAGE_MODE, 0))
        self.assertEqual(P.status(self.db, PLAYER)['next'], 0)

    def test_interrupted_rewind_does_not_publish_a_replacement_plan(self):
        self.at_stage()
        plans = list(Path(self.cache, 'profiles').rglob('stage-maplist-0.json'))
        self.assertEqual(len(plans), 1)
        plans[0].unlink()
        self.db.execute('UPDATE ksfprofiles SET cursor=1'); self.db.commit()
        with patch.object(P, 'advance', side_effect=RuntimeError('before rewind ack')):
            with self.assertRaisesRegex(RuntimeError, 'before rewind ack'):
                self.step()
        self.assertFalse(plans[0].exists())
        self.assertEqual(P.status(self.db, PLAYER)['next'], 1)
        with patch.object(K, 'fetch', side_effect=AssertionError('rewind must not ask')):
            got = P.stage_step(K, self.cache, K.Pacer(0, 0), self.have, 3002, PLAYER,
                               K.S.steam2(PLAYER), P.STAGE_MODE, 1, 1000, False)
            self.assertEqual(got, (0, 'partial', P.STAGE_MODE, 0))
            self.assertFalse(plans[0].exists())
            got = P.stage_step(K, self.cache, K.Pacer(0, 0), self.have, 3003, PLAYER,
                               K.S.steam2(PLAYER), P.STAGE_MODE, 0, 1000, False)
        self.assertIsNone(got)   # map0 is pending, not skipped
        self.assertTrue(plans[0].exists())
        self.assertEqual(P.status(self.db, PLAYER)['next'], 0)

    def test_stage_dates_are_bounded_before_filing(self):
        self.at_stage()
        rows = [dict(zoneId=1, record_id=8001, surfTime=6.5, date_set_at='9999-01-01T00:00:00Z'),
                dict(zoneId=2, record_id=8002, surfTime=7.5, date_set_at='2026-10-01T00:00:01Z')]
        self.src.fail = {'surf_profile0': {'records': rows,
                                         'basicInfo': {'steamID': K.S.steam2(PLAYER)}}}
        self.step()
        self.assertEqual([(r[0], r[1]) for r in self.zones()], [(0, 0), (0, 2)])


if __name__ == '__main__':
    unittest.main()
