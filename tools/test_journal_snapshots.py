#!/usr/bin/env python3
"""Typed store-only observations over captured, signed journal bytes."""
import hashlib
import json
import os
import tempfile
import unittest
from unittest import mock

import hidcheck
import rcptcheck
from test_hidcheck import Journal, run
from test_journal_diagnostics import (mouse_journal, fault_journal, unresolved_journal,
                                      receipt_for, join_journal)


class JournalSnapshots(unittest.TestCase):
    def test_measured_zero_and_each_axis(self):
        for counts in ([(2, 0)] * 6, [(0, 2)] * 6, [(0, 0)] * 6):
            text = mouse_journal(counts)
            h, r = run(text), receipt_for(text)
            self.assertTrue(h.ok, h.faults)  # control actually judged input
            self.assertEqual(h.info['identity_judged'], 5)
            snapshot = r.journal_metrics
            self.assertEqual(snapshot['version'], 1)
            for k, v in snapshot['metrics'].items():
                self.assertEqual(v, h.info[k], k)
            self.assertEqual(snapshot['metrics']['identity_pitch_mouse_frames'],
                             5 if counts[0][1] else 0)
            self.assertEqual(snapshot['metrics']['identity_yaw_exclusions'], {'seed': 1})
            self.assertEqual(json.loads(json.dumps(snapshot)), snapshot)
            self.assertEqual(r.journal, 'BLIND' if counts[0] == (0, 0) else 'OK')

    def test_fault_blind_and_abstention(self):
        for text, verdict in ((fault_journal(), 'FAULT'),
                              (unresolved_journal((3, 4)), 'BLIND'),
                              (Journal(mfilter=1).end(), 'BLIND')):
            h, r = run(text), receipt_for(text)
            self.assertEqual(r.journal, verdict)
            self.assertEqual(r.journal_metrics, rcptcheck.journal_snapshot(h.info))
            self.assertNotIn('identity_blind', r.journal_metrics['metrics'])
        self.assertNotIn('identity_mouse_frames', r.journal_metrics['metrics'])

    def test_counts_join_profile_is_typed(self):
        text = join_journal(['normal'] * 6)
        r = receipt_for(text)
        h = run(text)
        self.assertGreater(h.info['join_checked'], 0)
        self.assertEqual(r.journal_metrics['metrics']['join_checked'], h.info['join_checked'])
        self.assertIs(r.journal_metrics['metrics']['join_declared_transform_profile'], True)

    def test_allowlist_and_finite_values(self):
        info = dict(identity_mouse_frames=0, identity_mouse_pct=float('nan'),
                    identity_no_mouse_frames=True, view_records=-1,
                    join_windows=float('inf'), identity_ghosts='3',
                    nonce='private', device='private', identity='private',
                    identity_yaw_exclusions={'seed': 1, 'private': 2, 'mode': -1},
                    join_declared_transform_profile=False)
        self.assertEqual(rcptcheck.journal_snapshot(info), {'version': 1, 'metrics': {
            'identity_mouse_frames': 0, 'identity_yaw_exclusions': {'seed': 1},
            'join_declared_transform_profile': False}})

    def test_absent_mismatch_io_and_reader_failure_are_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'sample.rcpt')
            r = rcptcheck.Receipt(path)
            rcptcheck.join_journal(r)
            self.assertEqual(r.journal, 'ABSENT')
            self.assertIsNone(r.journal_metrics)
            data = mouse_journal([(2, 0)] * 6).encode()
            with open(os.path.splitext(path)[0] + '.hid', 'wb') as f:
                f.write(data)
            r = rcptcheck.Receipt(path)
            r.signed = [('hid', '%s %d 1' % ('0'*64, len(data)))]
            rcptcheck.join_journal(r)
            self.assertEqual(r.journal, 'FAULT')
            self.assertIsNone(r.journal_metrics)
            for target, effect in (('rcptcheck.file_bytes', PermissionError('control')),
                                   ('hidcheck.check_hid', RuntimeError('control'))):
                r = rcptcheck.Receipt(path)
                r.signed = [('hid', '%s %d 1' % (hashlib.sha256(data).hexdigest(), len(data)))]
                with mock.patch(target, side_effect=effect) as acted:
                    rcptcheck.join_journal(r)
                self.assertTrue(acted.called)
                self.assertIsNone(r.journal_metrics)

    def test_snapshot_uses_captured_signed_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'sample.rcpt')
            hp = os.path.splitext(path)[0] + '.hid'
            data = mouse_journal([(2, 0)] * 6).encode()
            with open(hp, 'wb') as f:
                f.write(data)
            r = rcptcheck.Receipt(path)
            r.signed = [('hid', '%s %d 1' % (hashlib.sha256(data).hexdigest(), len(data)))]
            rcptcheck.join_uploaded(r, {})
            with open(hp, 'wb') as f:
                f.write(fault_journal().encode())
            rcptcheck.join_journal(r)
            self.assertEqual(r.journal, 'OK')
            self.assertEqual(r.journal_metrics['metrics']['identity_violations'], 0)
            self.assertEqual(r.journal_metrics['metrics']['identity_mouse_frames'], 5)


if __name__ == '__main__':
    unittest.main()
