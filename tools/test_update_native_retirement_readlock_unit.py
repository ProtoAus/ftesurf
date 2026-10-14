#!/usr/bin/env python3
"""Client-free oracle/order controls, not native acceptance."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_update_native_retirement_readlock as gate


class ReadlockOracleTests(unittest.TestCase):
    def setUp(self):
        root = Path(__import__('os').environ['FTESURF_TEST_SCRATCH'])
        root.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=root)
        self.root = Path(self.tmp.name)
        paths = ['ftesurf/gfx/crosshairs/xhair1.png', 'ftesurf/gfx/crosshairs/xhair2.png',
                 'ftesurf/maps/zones/local/test.json']
        payload = {p: ('signed ' + p).encode() for p in paths}
        files = {p: dict(hash=gate.staging.digest(b), size=len(b), exec=False) for p, b in payload.items()}
        self.f = gate.prepare(self.root, b'unit envelope only', dict(version='0.1.25'), files, payload)

    def tearDown(self):
        self.tmp.cleanup()

    def retire(self):
        for k in ('resolved', 'pending', 'zone'):
            (self.f['meta'] / 'ingame/staged' / self.f['files'][self.f[k]]['hash']).unlink()
        (self.f['meta'] / 'ingame/journal.json').unlink()

    def test_seed_is_attempt3_complete_with_large_preserved_edit(self):
        self.assertEqual(json.loads(self.f['raw_authority'])['attempts'], 3)
        self.assertGreater(len(gate.EDIT), 6 * 1024 * 1024)
        self.assertEqual(gate.grade(self.f, False)['retired'], False)

    def test_refusal_oracle_rejects_actual_retirement(self):
        self.retire()
        with self.assertRaises(AssertionError):
            gate.grade(self.f, False)
        self.assertEqual(len(gate.grade(self.f, True)['removed']), 4)

    def test_retirement_oracle_requires_action(self):
        with self.assertRaises(AssertionError):
            gate.grade(self.f, True)

    def test_protected_edit_and_unrelated_objects_cannot_disappear(self):
        self.retire()
        (self.f['dest'] / self.f['zone']).write_bytes(b'wrong')
        with self.assertRaises(AssertionError):
            gate.grade(self.f, True)

    def test_new_metadata_is_not_hidden(self):
        (self.f['meta'] / 'ingame/journal.tmp').write_bytes(b'new')
        with self.assertRaises(AssertionError):
            gate.grade(self.f, False)

    def test_completion_ledger_reformat_only_is_allowed(self):
        self.retire()
        (self.f['meta'] / 'state.json').write_text(json.dumps(self.f['ledger'], indent=2))
        gate.grade(self.f, True)
        self.f['ledger']['version'] = 'bad'
        with self.assertRaises(AssertionError):
            gate.grade(self.f, True)

    def test_full_namespace_and_siblings_are_graded_in_both_modes(self):
        for retired in (False, True):
            if retired:
                self.retire()
            for path in ('arbitrary.txt', 'ftesurf/data/extra',
                         '.ftesurf-updater/ingame/staged/' + 'c' * 64 + '.install'):
                target = self.f['dest'] / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'extra')
                with self.assertRaises(AssertionError):
                    gate.grade(self.f, retired)
                target.unlink()
            for path in self.f['extras']:
                target = self.f['meta'] / path
                original = target.read_bytes()
                target.unlink()
                with self.assertRaises(AssertionError):
                    gate.grade(self.f, retired)
                target.write_bytes(original)
            gate.grade(self.f, retired)

    def test_empty_extra_directory_is_not_hidden(self):
        target = self.f['dest'] / 'unexpected-empty'
        target.mkdir()
        with self.assertRaises(AssertionError):
            gate.grade(self.f, False)
        self.retire()
        with self.assertRaises(AssertionError):
            gate.grade(self.f, True)

    def test_refusal_rejects_ledger_formatting_mutation(self):
        (self.f['meta'] / 'state.json').write_text(json.dumps(self.f['ledger'], indent=2))
        with self.assertRaises(AssertionError):
            gate.grade(self.f, False)

    def test_release_precedes_full_export_and_grade(self):
        events = []
        receipt = dict(status='FAIL', natural_exit=True, job_active_before_cleanup=0, job_active_after_cleanup=0)
        with patch.object(gate, 'snapshot', side_effect=lambda *a: events.append('export')):
            gate.finalize_phase(self.root, self.root, receipt, lambda: events.append('release'),
                                lambda: events.append('grade'))
        self.assertEqual(events, ['release', 'export', 'grade'])
        self.assertEqual(receipt['status'], 'PASS')

    def test_unknown_export_or_job_cannot_be_pass(self):
        for key in ('job_active_before_cleanup', 'job_active_after_cleanup', 'natural_exit', 'export'):
            with self.subTest(key=key):
                receipt = dict(status='FAIL', natural_exit=True, job_active_before_cleanup=0, job_active_after_cleanup=0)
                if key != 'export':
                    receipt[key] = 1 if key != 'natural_exit' else False
                with patch.object(gate, 'snapshot', side_effect=OSError('export denied') if key == 'export' else None):
                    with self.assertRaises((AssertionError, OSError)):
                        gate.finalize_phase(self.root, self.root, receipt, lambda: None, lambda: {})
                self.assertEqual(receipt['status'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
