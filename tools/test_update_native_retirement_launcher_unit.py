#!/usr/bin/env python3
"""Portable fail-closed falsifiers for the separate launcher-supersession oracle."""
from collections import Counter
import copy
import json
from pathlib import Path
import tempfile
import unittest

import test_update_native_retirement_launcher as gate
import test_update_native_retirement_windows as retirement
from test_update_native_recovery import digest


class Oracle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        payload = {'ftesurf/gfx/crosshairs/xhair1.png': b'first signed object',
                   'ftesurf/gfx/crosshairs/xhair2.png': b'second signed object',
                   'ftesurf/maps/zones/local/unit.json': b'signed protected zone',
                   'VERSION.txt': b'0.1.25\n'}
        files = {p: {'path': p, 'hash': digest(data), 'size': len(data), 'exec': False}
                 for p, data in payload.items()}
        signed = b'unit opaque envelope; signature tests are immutable load_inputs\n'
        self.f = retirement.prepare(root, 'install', 'corrupt-resolved', False,
            signed, {'version': '0.1.25'}, files, payload, attempts=3, completed=True)
        f, meta = self.f, self.f['meta']
        (meta / 'consent').write_bytes(b'1\n')
        self.original = (meta / 'ingame/journal.json').read_bytes()
        self.staged = {p.name: p.read_bytes() for p in (meta / 'ingame/staged').iterdir()}
        self.ledger = json.loads((meta / 'state.json').read_text())
        (meta / 'ingame/journal.json').rename(meta / 'recovered-ingame-123.json')
        (meta / 'installed.json').write_bytes(signed)
        st = copy.deepcopy(self.ledger)
        st['version'] = f['version']
        for path, entry in files.items():
            if path not in f['sentinels']:
                st['files'][path] = entry['hash']
        (meta / 'state.json').write_text(json.dumps(st))
        self.hits = Counter({'/update.json': 1})

    def grade(self):
        return gate.grade_repaired(self.f, self.original, self.staged, self.ledger, self.hits, {})

    def test_acting_positive(self):
        self.assertEqual(self.grade()['signed_file_count'], 4)

    def test_false_ready_without_parking(self):
        (self.f['meta'] / 'recovered-ingame-123.json').unlink()
        with self.assertRaises(AssertionError):
            self.grade()

    def test_old_authority_still_present(self):
        (self.f['meta'] / 'ingame/journal.json').write_bytes(self.original)
        with self.assertRaises(AssertionError):
            self.grade()

    def test_reduced_authority_cannot_be_parked_as_full(self):
        old = json.loads(self.original)
        old['files'] = old['files'][:1]
        (self.f['meta'] / 'recovered-ingame-123.json').write_text(json.dumps(old))
        with self.assertRaises(AssertionError):
            self.grade()

    def test_changed_signed_closure(self):
        (self.f['dest'] / 'VERSION.txt').write_bytes(b'wrong release')
        with self.assertRaises(AssertionError):
            self.grade()

    def test_changed_protected_edit(self):
        (self.f['dest'] / self.f['zone']).write_bytes(self.f['payload'][self.f['zone']])
        with self.assertRaises(AssertionError):
            self.grade()

    def test_swept_native_stage(self):
        retirement.stage_path(self.f, self.f['zone']).unlink()
        with self.assertRaises(AssertionError):
            self.grade()

    def test_adopted_failed_temp(self):
        (self.f['meta'] / 'ingame/journal.tmp').write_bytes(b'adopted failed temp')
        with self.assertRaises(AssertionError):
            self.grade()

    def test_false_protected_ledger_adoption(self):
        p = self.f['meta'] / 'state.json'
        st = json.loads(p.read_text())
        st['files'][self.f['zone']] = self.f['files'][self.f['zone']]['hash']
        p.write_text(json.dumps(st))
        with self.assertRaises(AssertionError):
            self.grade()

    def test_pending_rust_transaction(self):
        (self.f['meta'] / 'pending.json').write_bytes(b'incomplete')
        with self.assertRaises(AssertionError):
            self.grade()

    def test_late_object_request(self):
        self.hits['/objects/aa/unexpected'] += 1
        with self.assertRaises(AssertionError):
            self.grade()

    def test_refusal_metadata_mutation(self):
        before = gate.authority_inventory(self.f)
        gate.grade_unchanged(self.f, before)
        (self.f['meta'] / 'consent').write_bytes(b'0\n')
        with self.assertRaises(AssertionError):
            gate.grade_unchanged(self.f, before)


if __name__ == '__main__':
    unittest.main()
