#!/usr/bin/env python3
"""Process-free P693 pointer/key dispatch and actual Python transport falsifiers.

Run: python [-O] -B tools/test_p693_wheel.py
The fake stdin/log adapter resets its cursor at physical command-line boundaries.
It is a declared model, not native input, QC, socket, GPU or product acceptance.
"""
import re
import time
import types
import unittest
from unittest import mock

import test_p693_ui as p


def receipt(scan, down, took):
    return f'vote key: scan {scan} down {down} took {took} pick 0 capture 0 saves 0\n'


class DispatchTests(unittest.TestCase):
    def runtime(self, text):
        rt = p.Runtime.__new__(p.Runtime)
        rt.calls = []
        def section(command, delay=.8):
            rt.calls.append((command, delay))
            return text
        rt.section = section
        return rt

    def test_panel_wheel_is_one_dispatch_with_pointer_before_down_up(self):
        text = receipt(516, 1, 1) + receipt(516, 0, 1)
        rt = self.runtime(text)
        self.assertEqual(rt.key_at(516, 1408, 348, consumed=True), text)
        self.assertEqual(rt.calls, [('zone_edit pointer 1408 348; vote key 516 1; vote key 516 0; zone_edit status', .2)])

    def test_other_direction_is_batched(self):
        rt = self.runtime(receipt(515, 1, 1) + receipt(515, 0, 1))
        rt.key_at(515, 1408, 348, consumed=True)
        self.assertEqual(len(rt.calls), 1)
        self.assertIn('vote key 515 1; vote key 515 0', rt.calls[0][0])

    def test_outside_wheel_must_prove_declined_down(self):
        rt = self.runtime(receipt(516, 1, 0) + receipt(516, 0, 0))
        rt.key_at(516, 24, 24, consumed=False)
        self.assertEqual(len(rt.calls), 1)
        self.assertTrue(rt.calls[0][0].startswith('zone_edit pointer 24 24;'))

    def test_mouse2_uses_same_chain_without_assuming_release_consumption(self):
        rt = self.runtime(receipt(513, 1, 1) + receipt(513, 0, 0))
        rt.key_at(513, 1408, 348)
        self.assertEqual(len(rt.calls), 1)

    def test_empty_receipts_refuse(self):
        with self.assertRaises(AssertionError):
            self.runtime('NAV-ACK-1\n').key_at(516, 1408, 348)

    def test_missing_release_refuses(self):
        with self.assertRaises(AssertionError):
            self.runtime(receipt(516, 1, 1)).key_at(516, 1408, 348)

    def test_missing_down_refuses(self):
        with self.assertRaises(AssertionError):
            self.runtime(receipt(516, 0, 1)).key_at(516, 1408, 348)

    def test_other_scan_refuses(self):
        with self.assertRaises(AssertionError):
            self.runtime(receipt(515, 1, 1) + receipt(515, 0, 1)).key_at(516, 1408, 348)

    def test_duplicate_receipts_refuse(self):
        text = receipt(516, 1, 1) + receipt(516, 1, 1) + receipt(516, 0, 1)
        with self.assertRaises(AssertionError):
            self.runtime(text).key_at(516, 1408, 348)

    def test_reversed_receipts_refuse(self):
        with self.assertRaises(AssertionError):
            self.runtime(receipt(516, 0, 1) + receipt(516, 1, 1)).key_at(516, 1408, 348)

    def test_unconsumed_panel_wheel_refuses(self):
        with self.assertRaises(AssertionError):
            self.runtime(receipt(516, 1, 0) + receipt(516, 0, 0)).key_at(516, 1408, 348, consumed=True)

    def test_consumed_outside_wheel_refuses(self):
        with self.assertRaises(AssertionError):
            self.runtime(receipt(516, 1, 1) + receipt(516, 0, 1)).key_at(516, 24, 24, consumed=False)

    def test_native_overwrite_model_falsifies_split_dispatch(self):
        rt = p.Runtime.__new__(p.Runtime)
        calls = []
        def section(command, delay=.8):
            # Declared model; actual native behavior requires the live arm.
            mouse = (24, 24)
            out = ''
            calls.append(command)
            for cmd in command.split('; '):
                pointer = re.fullmatch(r'zone_edit pointer (\d+) (\d+)', cmd)
                key = re.fullmatch(r'vote key (\d+) ([01])', cmd)
                if pointer:
                    mouse = tuple(map(int, pointer.groups()))
                elif key:
                    scan, down = map(int, key.groups())
                    out += receipt(scan, down, int(mouse == (1408, 348)))
                elif cmd == 'zone_edit status':
                    pass  # State validation is exercised separately below.
                else:
                    self.fail('unexpected command in model: ' + cmd)
            return out
        rt.section = section
        rt.key_at(516, 1408, 348, consumed=True)
        self.assertEqual(len(calls), 1)
        # Acted negative control: the split mechanism loses the position.
        section('zone_edit pointer 1408 348')
        self.assertIn('down 1 took 0', section('vote key 516 1'))

    def test_panel_release_must_also_be_consumed(self):
        with self.assertRaises(AssertionError):
            self.runtime(receipt(516, 1, 1) + receipt(516, 0, 0)).key_at(516, 1408, 348, consumed=True)

    def test_packet_is_short_single_line_and_has_status_after_release(self):
        rt = self.runtime(receipt(516, 1, 1) + receipt(516, 0, 1))
        rt.key_at(516, 1408, 348)
        packet = rt.calls[0][0]
        self.assertLess(len((packet + '\n').encode('ascii')), 256)
        self.assertNotIn('\n', packet)
        self.assertTrue(packet.endswith('vote key 516 0; zone_edit status'))

    def test_overlong_packet_refuses_before_transport(self):
        rt = self.runtime('')
        with self.assertRaises(AssertionError):
            rt.key_at(int('9' * 300), 1408, 348)
        self.assertEqual(rt.calls, [])

    def state(self, *, cursor=1, row=0, state=1, dirty=0):
        return (f'zone_edit: state {state} map surf_tensor2 zones 44 points 210 dirty {dirty} crc beb5aabb\n'
                f'zone_edit: cursor {cursor} polygon 0 corners 0 window 1228 112\n'
                f'zone_edit: first list row {row}\n')

    def test_clean_state_witness_acts(self):
        rt = self.runtime('')
        text = self.state(cursor=1, row=2)
        self.assertEqual(rt.zone_witness(text, cursor=1, row=2), text)

    def test_missing_state_refuses(self):
        with self.assertRaises(AssertionError):
            self.runtime('').zone_witness(receipt(516, 1, 1), cursor=1, row=2)

    def test_stale_duplicate_state_refuses(self):
        with self.assertRaises(AssertionError):
            self.runtime('').zone_witness(self.state() + self.state(), cursor=1, row=0)

    def test_wrong_state_cursor_row_and_dirty_each_refuse(self):
        for change in ({'state': 2}, {'cursor': 0}, {'row': 2}, {'dirty': 1}):
            with self.subTest(change=change), self.assertRaises(AssertionError):
                self.runtime('').zone_witness(self.state(**change), cursor=1, row=0)

    def test_zone_reinjects_pointer_for_both_directions_and_both_mouse2_toggles(self):
        rt = p.Runtime.__new__(p.Runtime)
        rt.cursor, rt.row, rt.placing = 1, 0, False
        rt.packets, rt.sends = [], []
        def send(command, delay=.8):
            rt.sends.append(command)
            if command == 'zone_edit place stage':
                rt.placing, rt.cursor = True, 0
            elif command == 'vote key 513 1' and rt.placing:
                rt.placing, rt.cursor = False, 1
        def section(command, delay=.8):
            if command == 'zone_edit status':
                return self.state(cursor=rt.cursor, row=rt.row)
            rt.packets.append(command)
            mouse, out = (0, 0), ''
            for cmd in command.split('; '):
                pointer = re.fullmatch(r'zone_edit pointer (\d+) (\d+)', cmd)
                key = re.fullmatch(r'vote key (\d+) ([01])', cmd)
                if pointer:
                    mouse = tuple(map(int, pointer.groups()))
                elif key:
                    scan, down = map(int, key.groups())
                    inside = mouse == (1252, 312)
                    took = int(inside)
                    if down and inside:
                        if scan == 516:
                            rt.row += 2
                        elif scan == 515:
                            rt.row = max(0, rt.row - 2)
                        elif scan == 513:
                            rt.cursor = 1 - rt.cursor
                        else:
                            self.fail('unexpected panel scan')
                    out += receipt(scan, down, took)
                elif cmd == 'zone_edit status':
                    out += self.state(cursor=rt.cursor, row=rt.row)
                else:
                    self.fail('unexpected packet command: ' + cmd)
            return out
        rt.send, rt.section = send, section
        rt.zone()
        self.assertEqual(len(rt.packets), 6)
        self.assertTrue(all(packet.startswith('zone_edit pointer ') for packet in rt.packets))
        self.assertTrue(all(packet.endswith('; zone_edit status') for packet in rt.packets))
        self.assertEqual([re.search(r'vote key (\d+) 1', packet)[1] for packet in rt.packets],
                         ['516', '515', '516', '515', '513', '513'])
        self.assertEqual([packet.split(';')[0] for packet in rt.packets],
                         ['zone_edit pointer 0 0'] * 2 + ['zone_edit pointer 1252 312'] * 4)
        self.assertFalse(any(cmd.startswith('zone_edit pointer') for cmd in rt.sends))
        self.assertIn('vote key 32 1', rt.sends)
        self.assertIn('zone_edit place stage', rt.sends)
        self.assertIn('vote key 513 1', rt.sends)
        self.assertEqual((rt.cursor, rt.row, rt.placing), (1, 0, False))


class TransportTests(unittest.TestCase):
    def runtime(self, *, acknowledge=True):
        rt = p.Runtime.__new__(p.Runtime)
        rt.dispatch, rt.deadline = [], time.monotonic() + 10
        rt.writes, rt.flushes, rt.text, rt.manifests = [], 0, '', []
        class MemoryPath:
            def __truediv__(self, name):
                return self
            def write_text(self, text):
                rt.manifests.append(text)
        rt.out = MemoryPath()
        rt.cursor, rt.row = 1, 0
        rt.log = types.SimpleNamespace(text=lambda: rt.text)
        def write(payload):
            rt.writes.append(payload)
            for line in payload.decode('ascii').splitlines():
                # Declared model, not a claim about historical native events.
                mouse = (0, 0)
                for command in line.split('; '):
                    pointer = re.fullmatch(r'zone_edit pointer (\d+) (\d+)', command)
                    key = re.fullmatch(r'vote key (\d+) ([01])', command)
                    if pointer:
                        mouse = tuple(map(int, pointer.groups()))
                    elif key:
                        scan, down = map(int, key.groups())
                        took = int(mouse == (1252, 312))
                        if took and down:
                            if scan == 516:
                                rt.row += 2
                            elif scan == 515:
                                rt.row = max(0, rt.row - 2)
                            elif scan == 513:
                                rt.cursor = 1 - rt.cursor
                        rt.text += receipt(scan, down, took)
                    elif command == 'zone_edit status':
                        rt.text += DispatchTests().state(cursor=rt.cursor, row=rt.row)
                    elif command.startswith('echo NAV-ACK-'):
                        if acknowledge:
                            rt.text += command[5:] + '\n'
                    else:
                        self.fail('unexpected transport command: ' + command)
            return len(payload)
        def flush():
            rt.flushes += 1
        rt.client = types.SimpleNamespace(stdin=types.SimpleNamespace(write=write, flush=flush), poll=lambda: None)
        return rt

    def test_actual_sender_writes_packet_and_ack_in_one_flush(self):
        rt = self.runtime()
        with mock.patch.object(p.time, 'sleep'):
            text = rt.key_at(516, 1252, 312, consumed=True)
        rt.zone_witness(text, cursor=1, row=2)
        self.assertEqual(rt.writes, [b'zone_edit pointer 1252 312; vote key 516 1; vote key 516 0; zone_edit status\necho NAV-ACK-1\n'])
        self.assertEqual(rt.flushes, 1)
        self.assertEqual(len(rt.dispatch), 1)
        self.assertEqual(len(rt.manifests), 1)
        self.assertIn('NAV-ACK-1', text)

    def test_actual_transport_reinjects_for_reverse_wheel(self):
        rt = self.runtime()
        with mock.patch.object(p.time, 'sleep'):
            down = rt.key_at(516, 1252, 312, consumed=True)
            up = rt.key_at(515, 1252, 312, consumed=True)
        rt.zone_witness(down, cursor=1, row=2)
        rt.zone_witness(up, cursor=1, row=0)
        self.assertEqual(len(rt.writes), 2)
        self.assertTrue(all(payload.startswith(b'zone_edit pointer 1252 312; ') for payload in rt.writes))
        self.assertNotIn('first list row 2', up)

    def test_actual_outside_transport_declines_and_preserves_state(self):
        rt = self.runtime()
        with mock.patch.object(p.time, 'sleep'):
            text = rt.key_at(516, 0, 0, consumed=False)
        rt.zone_witness(text, cursor=1, row=0)
        self.assertEqual(rt.row, 0)
        self.assertIn('down 1 took 0', text)
        self.assertIn('down 0 took 0', text)

    def test_receipts_without_ack_do_not_make_send_succeed(self):
        rt = self.runtime(acknowledge=False)
        # Receipts cannot substitute for the real sender's missing ACK marker.
        rt.client.poll = lambda: 0
        with mock.patch.object(p.time, 'sleep'), self.assertRaisesRegex(TimeoutError, 'console dispatch did not act'):
            rt.key_at(516, 1252, 312, consumed=True)
        self.assertEqual(len(rt.writes), 1)
        self.assertIn('down 1 took 1', rt.text)
        self.assertNotIn('NAV-ACK-1', rt.text)

    def test_stale_prefix_is_excluded_by_actual_section(self):
        rt = self.runtime()
        rt.text = DispatchTests().state(cursor=0, row=9)
        with mock.patch.object(p.time, 'sleep'):
            text = rt.key_at(516, 1252, 312, consumed=True)
        rt.zone_witness(text, cursor=1, row=2)
        self.assertNotIn('cursor 0', text)
        self.assertNotIn('first list row 9', text)

    def test_native_line_boundary_254_bare_bytes_has_room_for_newline(self):
        rt = self.runtime()
        scan = int('9' * 94)
        with mock.patch.object(p.time, 'sleep'):
            rt.key_at(scan, 10, 0)
        line = rt.writes[0].split(b'\n')[0] + b'\n'
        self.assertEqual(len(line), 255)
        self.assertEqual(len(rt.writes), 1)

    def test_native_line_boundary_255_bare_bytes_refuses_before_write(self):
        rt = self.runtime()
        scan = int('9' * 95)
        command = 'zone_edit pointer 0 0; vote key %d 1; vote key %d 0; zone_edit status' % (scan, scan)
        self.assertEqual(len(command.encode('ascii')), 255)
        with mock.patch.object(p.time, 'sleep'), self.assertRaisesRegex(AssertionError, 'stdin line contract'):
            rt.key_at(scan, 0, 0)
        self.assertEqual(rt.writes, [])
        self.assertEqual(rt.dispatch, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
