#!/usr/bin/env python3
"""Signed finish-clock binding against one captured recording observation.

Generated keys/evidence only. Exercises crypto, readers and real SQLite sweep.
No client authenticity, calibration or historical reread is inferred.
"""
import contextlib
import io
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'surfd'))
import test_sweep as fixtures
import ed25519
import rcptcheck
import reccheck
import test_rcptcheck as snapshots


class FinishTicks(unittest.TestCase):
    def setUp(self):
        self.m, self.sw, _runs = fixtures.fresh()
        self.sw.TOOLS = fixtures.TOOLS
        self.old_game = rcptcheck.GAME
        self.addCleanup(setattr, rcptcheck, 'GAME', self.old_game)
        self.c = self.m.connect()
        self.addCleanup(self.c.close)

    def signed(self, ticks=None, server_ticks=None, rec=True, ver=9):
        runid = '20261008-000300-0'
        recording, view = fixtures.angle_pair(runid, ver=ver)
        recording = recording.replace('\nbegin\n', '\nnonce d6c6820bca16750c77166d96dcf02787\nbegin\n', 1)
        # The existing grammar fixture chooses nontrivial per-move durations.
        report = reccheck.check_rec('fixture.rec', data=recording.encode())
        self.assertTrue(report.ok)
        actual = report.info['ticks']
        if ticks is None:
            ticks = actual
        if server_ticks is None:
            server_ticks = ticks
        path, _pub = fixtures.make_receipt(self.m.EVIDENCE_DIR, runid, view=view.encode(), age=1)
        with open(path, encoding='utf-8') as fh:
            lines = fh.read().splitlines()
        lines = [('signed ticks %s' % ticks) if line.startswith('signed ticks ') else
                 ('svticks %s' % server_ticks) if line.startswith('svticks ') else line for line in lines]
        message = (lines[0]+'\n'+''.join(line[7:]+'\n' for line in lines if line.startswith('signed '))).encode()
        signature = ed25519.sign(b'\x01'*32, message).hex()
        lines = [('sig '+signature) if line.startswith('sig ') else line for line in lines]
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('\n'.join(lines)+'\n')
        os.utime(path, (1, 1))
        if rec:
            fixtures.with_rec(self.m, self.sw, runid, recording)
        else:
            rcptcheck.GAME = os.path.join(os.environ['SURFD_HOME'], 'game')
        parsed = rcptcheck.read(path)
        self.assertIs(parsed.ok, True)  # genuine signature, not a malformed-input fault
        self.assertEqual(parsed.faults, [])
        return path, recording, actual

    def test_matching_signed_recording_finish_remains_valid(self):
        path, _rec, actual = self.signed()
        with mock.patch.object(reccheck, 'check_rec', wraps=reccheck.check_rec) as parser:
            result = self.sw.read_receipt(path)
        self.assertEqual((result[0], result[3], result[5]), ('VALID', 'OK', 1))
        self.assertEqual(parser.call_count, 1)  # nonce/ticks/angles share one parsed capture
        r = rcptcheck.read(path)
        rcptcheck.join_rec(r)
        self.assertTrue(any('recording finish ticks agree' in n and str(actual) in n for n in r.notes))

    def test_signed_duration_difference_faults_content_not_signature(self):
        for delta in (-1, 1):
            _path, _rec, actual = self.signed()
            path, _rec, _actual = self.signed(ticks=actual+delta)
            result = self.sw.read_receipt(path)
            self.assertEqual((result[0], result[3], result[5]), ('FAULT', 'OK', 1))
            self.assertIn('recording finish', result[4])
            self.assertIn(str(actual+delta), result[4])
            self.assertIn(str(actual), result[4])

    def test_real_sweep_stores_clock_fault_and_valid_signature(self):
        _path, _rec, actual = self.signed()
        self.signed(ticks=actual+1)
        self.assertEqual(self.sw.receipt_step(self.c), (1, 1))
        row = self.c.execute('SELECT verdict,sig,angles,reason FROM receipts').fetchone()
        self.assertEqual(tuple(row[:3]), ('FAULT', 1, 'OK'))
        self.assertIn('recording finish', row[3])

    def test_existing_server_disagreement_survives(self):
        _path, _rec, actual = self.signed()
        path, _rec, _actual = self.signed(server_ticks=actual+1)
        result = self.sw.read_receipt(path)
        self.assertEqual((result[0], result[5]), ('FAULT', 1))
        self.assertIn('this server counted', result[4])

    def test_unkept_negative_sentinel_is_not_a_recording_time(self):
        path, _rec, _actual = self.signed(ticks=-1)
        result = self.sw.read_receipt(path)
        self.assertEqual((result[0], result[3], result[5]), ('VALID', 'OK', 1))

    def test_zero_abandon_latch_is_not_a_recording_time(self):
        path, _rec, actual = self.signed(ticks=0)
        self.assertGreater(actual, 0)
        result = self.sw.read_receipt(path)
        self.assertEqual((result[0], result[3], result[5]), ('VALID', 'OK', 1))

    def test_off_host_absence_is_not_a_clock_fault(self):
        path, _rec, _actual = self.signed(rec=False)
        result = self.sw.read_receipt(path)
        self.assertEqual((result[0], result[3], result[5], result[12]), ('VALID', '', 1, True))

    def test_legacy_readable_trailer_still_checks_ticks(self):
        path, _rec, actual = self.signed(ver=5)
        good = self.sw.read_receipt(path)
        self.assertEqual((good[0], good[5]), ('VALID', 1))
        path, _rec, _actual = self.signed(ticks=actual+1, ver=5)
        bad = self.sw.read_receipt(path)
        self.assertEqual((bad[0], bad[5]), ('FAULT', 1))
        self.assertIn('recording finish', bad[4])

    def test_missing_trailer_does_not_invent_a_finish(self):
        path, recording, _actual = self.signed()
        changed = '\n'.join(line for line in recording.splitlines() if not line.startswith('end '))+'\n'
        fixtures.with_rec(self.m, self.sw, '20261008-000300-0', changed)
        r = rcptcheck.read(path)
        rcptcheck.join_rec(r)
        self.assertEqual(r.faults, [])
        self.assertTrue(any('recording tick check unavailable' in n for n in r.notes))

    def test_unselected_header_read_failure_preserves_discovery_policy(self):
        path, _rec, _actual = self.signed()
        recpath = os.path.join(rcptcheck.GAME, 'data', 'evidence', 'bhop_eazy', '20261008-000300-0.rec')
        original = open
        attempts = []
        def opening(p, *args, **kwargs):
            if p == recpath:
                attempts.append(p)
                raise PermissionError('generated unavailable recording')
            return original(p, *args, **kwargs)
        with mock.patch('builtins.open', side_effect=opening):
            result = self.sw.read_receipt(path)
        self.assertEqual(len(attempts), 1)
        # Existing absent selected-recording discovery behavior is preserved.
        self.assertEqual((result[0], result[5], result[12]), ('VALID', 1, True))

    def test_fractional_trailer_does_not_truncate_into_a_clock_assertion(self):
        path, recording, actual = self.signed()
        changed = recording.replace('\nend %d ' % actual, '\nend %g ' % (actual+0.5))
        self.assertNotEqual(changed, recording)
        fixtures.with_rec(self.m, self.sw, '20261008-000300-0', changed)
        r = rcptcheck.read(path)
        rcptcheck.join_rec(r)
        self.assertEqual(r.faults, [])
        self.assertTrue(any('recording tick check unavailable' in n for n in r.notes))
        self.assertIsNone(r.rec_report.finish_ticks)

    def test_header_cannot_supply_the_computed_finish(self):
        path, recording, actual = self.signed()
        changed = recording.replace('\nbegin\n', '\nfinish_ticks 1\nbegin\n', 1)
        fixtures.with_rec(self.m, self.sw, '20261008-000300-0', changed)
        r = rcptcheck.read(path)
        rcptcheck.join_rec(r)
        self.assertEqual(r.faults, [])
        self.assertEqual(r.rec_report.finish_ticks, actual)
        # The unknown header remains only a legacy header string, never authority.
        self.assertEqual(r.rec_report.info['finish_ticks'], '1')
        fractional = changed.replace('\nend %d ' % actual, '\nend %g ' % (actual+0.5))
        fixtures.with_rec(self.m, self.sw, '20261008-000300-0', fractional)
        r = rcptcheck.read(path)
        rcptcheck.join_rec(r)
        self.assertEqual(r.faults, [])
        self.assertIsNone(r.rec_report.finish_ticks)
        self.assertTrue(any('recording tick check unavailable' in n for n in r.notes))

    def test_near_integer_fraction_is_not_rounded_into_a_find(self):
        _path, _rec, actual = self.signed()
        path, recording, _actual = self.signed(ticks=actual+1)
        changed = recording.replace('\nend %d ' % actual, '\nend %d.0000000000000001 ' % actual)
        self.assertNotEqual(changed, recording)
        fixtures.with_rec(self.m, self.sw, '20261008-000300-0', changed)
        r = rcptcheck.read(path)
        rcptcheck.join_rec(r)
        self.assertEqual(r.faults, [])
        self.assertIsNone(r.rec_report.finish_ticks)
        self.assertTrue(any('recording tick check unavailable' in n for n in r.notes))
        result = self.sw.read_receipt(path)
        self.assertEqual((result[0], result[5]), ('VALID', 1))

    def test_optional_exact_counter_bounds_and_exponent_notation(self):
        for raw, wanted in [('400', 400), ('4e2', 400), ('400.000', 400),
                            ('2147483647', 2147483647), ('2147483648', None),
                            ('1e999999999', None), ('0', 0), ('-1', None),
                            ('NaN', None), ('Infinity', None), ('garbage', None),
                            ('400.0000000000000001', None), ('0'*129+'400', None)]:
            self.assertEqual(reccheck.exact_finish_ticks(raw), wanted)

    def test_close_time_replacement_does_not_change_captured_clock(self):
        path, recording, actual = self.signed()
        replacement = recording.replace('\nend %d ' % actual, '\nend %d ' % (actual+1))
        self.assertNotEqual(replacement, recording)
        recpath = os.path.join(rcptcheck.GAME, 'data', 'evidence', 'bhop_eazy', '20261008-000300-0.rec')
        with snapshots.swap_after_close(recpath, replacement.encode()) as state:
            result = self.sw.read_receipt(path)
        self.assertEqual(state, {'reads': 1, 'swaps': 1})
        self.assertEqual((result[0], result[3], result[5]), ('VALID', 'OK', 1))
        later = self.sw.read_receipt(path)
        self.assertEqual((later[0], later[5]), ('FAULT', 1))
        self.assertIn('recording finish', later[4])

    def test_rejoining_same_report_replaces_only_its_parser_cache(self):
        path, recording, actual = self.signed()
        r = rcptcheck.read(path)
        rcptcheck.join_rec(r)
        self.assertEqual(r.faults, [])
        changed = recording.replace('\nend %d ' % actual, '\nend %d ' % (actual+1))
        fixtures.with_rec(self.m, self.sw, '20261008-000300-0', changed)
        rcptcheck.join_rec(r)
        self.assertEqual(r.rec_report.finish_ticks, actual+1)
        self.assertTrue(any('recording finish' in f for f in r.faults))

    def test_partial_pair_observations_also_check_selected_recording(self):
        _path, _rec, actual = self.signed()
        path, _rec, _actual = self.signed(ticks=actual+1)
        for options in ({'rec_only': True}, {'view_only': True}):
            result = self.sw.read_receipt(path, **options)
            self.assertEqual((result[0], result[5]), ('FAULT', 1))
            self.assertIn('recording finish', result[4])
        # A journal-only retry must not rejudge an old recording/history.
        result = self.sw.read_receipt(path, journal_only=True)
        self.assertEqual((result[0], result[5]), ('VALID', 1))

    def test_cli_exposes_content_fault_without_invalid_signature_claim(self):
        _path, _rec, actual = self.signed()
        path, _rec, _actual = self.signed(ticks=actual+1)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            exitcode = rcptcheck.main([path])
        self.assertEqual(exitcode, 1)
        self.assertIn('recording finish', output.getvalue())
        self.assertNotIn('SIGNATURE DOES NOT VERIFY', output.getvalue())


if __name__ == '__main__':
    unittest.main()
