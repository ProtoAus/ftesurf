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
from test_hidcheck import Journal, MOUSE0, PAD, run
from test_journal_diagnostics import (mouse_journal, fault_journal, unresolved_journal,
                                      receipt_for, join_journal)


def touchpad_journal(count=6):
    """Existing HID accepted-report source, not a new input/count channel."""
    j = Journal(devices=[MOUSE0, PAD])
    if count > 0:
        j.devices = [MOUSE0, ('touchpad', '1', PAD[2])]
    yaw = 0.0
    for i in range(max(0, count)):
        j.frame(3000 + i)
        j.mouse(4, 0, dev=1)
        yaw += j.k * 4
        j.view(4, 0, 10.0, yaw)
        j.pad(1, 7)
    return j.end(touchpad=count, padreports=count * 7 if count >= 0 else -1)


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

    def test_accepted_touchpad_count_uses_existing_hid_recording(self):
        for count in (0, 6):
            with self.subTest(count=count):
                text = touchpad_journal(count)
                h, r = run(text), receipt_for(text)
                self.assertTrue(h.ok, h.faults)
                self.assertEqual(h.info['touchpad'], count)  # reader ACTED
                self.assertEqual(r.journal, 'OK' if count else 'BLIND')
                self.assertEqual(r.journal_metrics['metrics']['touchpad'], count)
                self.assertEqual(r.journal_metrics, rcptcheck.journal_snapshot(h.info))
                self.assertNotIn('touchpad_digitizer_reports', r.journal_metrics['metrics'])
                self.assertNotIn(PAD[2], json.dumps(r.journal_metrics))
                if count:
                    self.assertEqual(h.info['identity_judged'], count - 1)

    def test_touchpad_unavailable_is_not_zero(self):
        for text in (mouse_journal([(2, 0)] * 6), touchpad_journal(-1)):
            h, r = run(text), receipt_for(text)
            self.assertTrue(h.ok, h.faults)
            self.assertNotIn('touchpad', h.info)
            self.assertNotIn('touchpad', r.journal_metrics['metrics'])

    def test_touchpad_snapshot_is_a_bounded_integer_count(self):
        for value in (-1, True, 1.0, '1', float('nan'), float('inf'), 10**12 + 1, 10**1000):
            snap = rcptcheck.journal_snapshot({'touchpad': value, 'identity_judged': 2})
            self.assertEqual(snap['metrics'], {'identity_judged': 2}, repr(value))
        for value in (0, 6, 10**12):
            snap = rcptcheck.journal_snapshot({'touchpad': value})
            self.assertEqual(snap['metrics'], {'touchpad': value})

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
