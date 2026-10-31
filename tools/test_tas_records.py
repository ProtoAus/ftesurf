#!/usr/bin/env python3
"""New local category filenames against the actual recording reader."""
import unittest

import test_reccheck as fixture


class TASRecords(unittest.TestCase):
    def test_full_tas_and_slowmo_archives(self):
        for flags in (257, 4194561):  # practice+cheat, optionally explicit TAS tools
            with self.subTest(flags=flags):
                lines = fixture.head(fixture.build(), 'flags', str(flags))
                faults, notes = fixture.run(lines, name='0000000100_tas.rec')
                self.assertEqual(faults, [], (faults, notes))

    def test_named_tas_cannot_claim_clean_flags(self):
        for name in ('0000000100_tas.rec', '0000000100_taslobby.rec'):
            faults, _ = fixture.run(fixture.build(), name=name)
            self.assertTrue(any('practice/cheat safety flags' in fault for fault in faults), faults)

    def test_header_only_remote_summary_is_separate(self):
        lines = ['FTESURF-REC 5', 'map surf_test', 'track 0', 'startseg 0', 'leg 0',
                 'tickrate 0.015', 'owner fixture', 'runid fixture', 'flags 257',
                 'clock counted', 'lobby fixture', 'samples 0']
        faults, notes = fixture.run(lines, name='0000000100_taslobby.rec')
        # Summary rows deliberately are not valid movement recordings. Do not
        # weaken the full-recording checker to turn them into replay evidence.
        self.assertEqual(faults, ["no 'begin' line: the header never ends"], notes)
        self.assertFalse(any('safety flags' in fault for fault in faults))


if __name__ == '__main__':
    unittest.main()
