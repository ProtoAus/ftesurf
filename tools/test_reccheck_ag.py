#!/usr/bin/env python3
"""AG metadata never turns shape validation into a Source physics verdict."""
import unittest
import reccheck
from test_reccheck import build


class AGModelIdentity(unittest.TestCase):
    def recording(self, mode=2, flags=1024):
        lines = build()
        lines = [('pmpin ' + reccheck_pin(mode)) if x.startswith('pmpin ') else
                 ('flags ' + str(flags)) if x.startswith('flags ') else x for x in lines]
        if mode == 2:
            lines.insert(1, 'movementprofile ag-100-v1')
        return ('\n'.join(lines) + '\n').encode()

    def test_ag_explicitly_unsupported_not_source_verdict(self):
        report = reccheck.check_rec('fixture.rec', data=self.recording())
        self.assertEqual(report.info['movementprofile'], 'ag-100-v1')
        self.assertTrue(any('UNSUPPORTED physics mode 2' in n and 'no physics verdict' in n
                            for n in report.notes))
        self.assertFalse(any('unknown header key' in n and 'movementprofile' in n for n in report.notes))

    def test_ag_without_unranked_flag_is_faulted(self):
        report = reccheck.check_rec('fixture.rec', data=self.recording(flags=0))
        self.assertTrue(any('AG recording lacks' in f for f in report.faults))

    def test_source_does_not_acquire_ag_identity_or_refusal(self):
        report = reccheck.check_rec('fixture.rec', data=self.recording(mode=1, flags=0))
        self.assertNotIn('movementprofile', report.info)
        self.assertFalse(any('UNSUPPORTED physics mode 2' in n for n in report.notes))

    def test_declared_optional_identity_without_pin_is_faulted(self):
        data=b'\n'.join(line for line in self.recording().split(b'\n') if not line.startswith(b'pmpin '))
        report = reccheck.check_rec('fixture.rec', data=data)
        self.assertTrue(any('no matching AG physics pin' in f for f in report.faults))
        self.assertTrue(any('UNSUPPORTED optional' in n for n in report.notes))

    def test_restated_ag_pin_cannot_look_like_source(self):
        lines=build(pms=((1, 0),))
        lines=[('pm 1 0 '+reccheck_pin(2)) if line.startswith('pm ') else line for line in lines]
        report=reccheck.check_rec('fixture.rec', data=('\n'.join(lines)+'\n').encode())
        self.assertTrue(any('UNSUPPORTED physics mode 2 in pm restatement' in n for n in report.notes))

    def test_numeric_model_spellings_are_not_fallbacks(self):
        for value in (b'2.0', b'2e0'):
            report=reccheck.check_rec('fixture.rec', data=self.recording().replace(b'physmode=2 ', b'physmode='+value+b' '))
            self.assertTrue(any('UNSUPPORTED physics mode 2' in n for n in report.notes))

    def test_malformed_flags_remain_reported_not_exception(self):
        report = reccheck.check_rec('fixture.rec', data=self.recording(flags='invalid'))
        self.assertTrue(report.faults)


def reccheck_pin(mode):
    return 'pmsrcver=1 physmode=%d gravity=800 maxspeed=320 ticrate=0.00999999978 bounce=1e-05' % mode


if __name__ == '__main__':
    unittest.main()
