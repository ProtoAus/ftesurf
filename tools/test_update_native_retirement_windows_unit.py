#!/usr/bin/env python3
"""Independent byte actors falsify the new retirement oracle (no native claim)."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_update_native_retirement_windows as native


class RetirementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get('FTESURF_TEST_SCRATCH'))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = {'ftesurf/gfx/crosshairs/xhair1.png': b'new ordinary one',
            'ftesurf/gfx/crosshairs/xhair2.png': b'new ordinary two',
            'ftesurf/gfx/env/missingtexture.png': b'shared signed bytes',
            'ftesurf/textures/no_texture.png': b'shared signed bytes',
            'ftesurf/maps/zones/local/owned.json': b'new managed zone'}
        self.files = {p: dict(hash=native.byte_hash(b), size=len(b), exec=False) for p, b in self.payload.items()}
        self.manifest = dict(version='0.1.25')
        self.signed = b'unit-only envelope stand-in; native CLI verifies real signature'
        self.count = 0

    def fixture(self, kind='unique', first=False, attempts=1, completed=False):
        self.count += 1
        return native.prepare(self.root, str(self.count), kind, first, self.signed,
            self.manifest, self.files, self.payload, attempts, completed)

    def act(self, f, complete=False, attempts=2, blocked=(), journal_held=False, before=False):
        # Source-shaped actor written directly against fixture bytes. No oracle calls.
        state = copy.deepcopy(f['ledger'])
        state['files'][f['resolved']] = self.files[f['resolved']]['hash']
        (f['dest'] / f['resolved']).write_bytes(self.payload[f['resolved']])
        if complete:
            state['version'] = self.manifest['version']
            state['files'][f['pending']] = self.files[f['pending']]['hash']
            (f['dest'] / f['pending']).write_bytes(self.payload[f['pending']])
            (f['meta'] / 'installed.json').write_bytes(self.signed)
        (f['meta'] / 'state.json').write_text(json.dumps(state))
        for row in f['rows']:
            path = f['meta'] / 'ingame/staged' / row['h']
            if not path.exists() or row['h'] in blocked:
                continue
            # Shared pending protects both identical-hash signed destinations.
            if not complete and row['h'] == self.files[f['pending']]['hash']:
                continue
            data = path.read_bytes()
            if data == self.payload[row['p']]:
                path.unlink()
        survivor = any((f['meta'] / 'ingame/staged' / row['h']).exists() for row in f['rows'])
        journal = f['meta'] / 'ingame/journal.json'
        if not journal_held:
            if complete and (before or not survivor):
                journal.unlink(missing_ok=True)
            else:
                rows = [r for r in f['rows'] if r['p'] == f['pending']] if before else f['rows']
                journal.write_text(json.dumps(dict(version=self.manifest['version'], attempts=attempts, files=rows)))
        if not complete or (not before and not f['seed_complete']):
            (f['meta'] / 'ingame/journal.tmp').unlink(missing_ok=True)

    def test_full_superset_and_retirement_in_both_orders(self):
        for kind in ('unique', 'shared', 'corrupt-resolved', 'wrong-size-resolved', 'reduced-orphan'):
            for first in (False, True):
                f = self.fixture(kind, first)
                self.act(f)
                native.grade(f, False, 2)
                native.stage_path(f, f['pending']).write_bytes(self.payload[f['pending']])
                f['stage'][self.files[f['pending']]['hash']] = self.payload[f['pending']]
                self.act(f, True, 3)
                native.grade(f, True, 3)

    def test_before_reduction_and_unlink_defects_are_not_subject_passes(self):
        for complete in (False, True):
            f = self.fixture('corrupt-resolved')
            if complete:
                native.stage_path(f, f['pending']).write_bytes(self.payload[f['pending']])
                f['stage'][self.files[f['pending']]['hash']] = self.payload[f['pending']]
            self.act(f, complete, 2, before=True)
            native.grade(f, complete, 2, before=True)
            with self.assertRaises((AssertionError, FileNotFoundError)):
                native.grade(f, complete, 2)

    def test_before_partial_temp_stays_consumed_on_completion(self):
        f = self.fixture()
        self.act(f, before=True)
        native.grade(f, False, 2, before=True)
        f['partial_completed'] = True
        native.stage_path(f, f['pending']).write_bytes(self.payload[f['pending']])
        f['rows'] = [r for r in f['rows'] if r['p'] == f['pending']]
        f['stage'] = {p.name: p.read_bytes() for p in (f['meta'] / 'ingame/staged').iterdir() if len(p.name) == 64}
        self.act(f, True, 3, before=True)
        native.grade(f, True, 3, before=True)

    def test_shared_pending_removal_fails_independent_oracle(self):
        f = self.fixture('shared')
        self.act(f)
        native.stage_path(f, f['pending']).unlink()
        with self.assertRaisesRegex(AssertionError, 'staged'):
            native.grade(f, False, 2)

    def test_valid_removal_must_act_and_outside_objects_survive(self):
        for restore in (True, False):
            f = self.fixture()
            self.act(f)
            if restore:
                native.stage_path(f, f['resolved']).write_bytes(self.payload[f['resolved']])
            else:
                (f['meta'] / 'ingame/staged' / ('a' * 64 + '.part')).unlink()
            with self.assertRaisesRegex(AssertionError, 'staged'):
                native.grade(f, False, 2)

    def test_same_size_and_wrong_size_corrupt_stay_named(self):
        for kind in ('corrupt-resolved', 'wrong-size-resolved'):
            f = self.fixture(kind)
            data = native.stage_path(f, f['zone']).read_bytes()
            self.assertEqual(len(data) == self.files[f['zone']]['size'], kind == 'corrupt-resolved')
            self.assertNotEqual(native.byte_hash(data), self.files[f['zone']]['hash'])
            native.stage_path(f, f['pending']).write_bytes(self.payload[f['pending']])
            f['stage'][self.files[f['pending']]['hash']] = self.payload[f['pending']]
            self.act(f, True, 2)
            native.grade(f, True, 2)
            native.stage_path(f, f['zone']).unlink()
            with self.assertRaisesRegex(AssertionError, 'staged'):
                native.grade(f, True, 2)

    def test_completed3_cleanup_repeated_no_bump_and_release(self):
        f = self.fixture(attempts=3, completed=True)
        blocked = (self.files[f['resolved']]['hash'],)
        for _ in range(2):
            self.act(f, True, 3, blocked)
            native.grade(f, True, 3, blocked=blocked)
        self.act(f, True, 3)
        native.grade(f, True, 3)

    def test_admitted_completion_persists_bump(self):
        f = self.fixture(attempts=2)
        native.stage_path(f, f['pending']).write_bytes(self.payload[f['pending']])
        f['stage'][self.files[f['pending']]['hash']] = self.payload[f['pending']]
        blocked = (self.files[f['resolved']]['hash'],)
        self.act(f, True, 3, blocked)
        native.grade(f, True, 3, blocked=blocked)
        j = f['meta'] / 'ingame/journal.json'
        data = json.loads(j.read_text())
        data['attempts'] = 2
        j.write_text(json.dumps(data))
        with self.assertRaisesRegex(AssertionError, 'budget'):
            native.grade(f, True, 3, blocked=blocked)

    def test_final_journal_denial_repeated_and_release(self):
        f = self.fixture(attempts=2, completed=True)
        for _ in range(2):
            self.act(f, True, 2, journal_held=True)
            native.grade(f, True, 2, journal_held=True)
        self.act(f, True, 2)
        native.grade(f, True, 2)

    def test_exact_rows_exec_duplicate_tuple_attempts(self):
        for mutation in ('exec', 'duplicate', 'tuple'):
            f = self.fixture()
            self.act(f)
            native.mutate_authority(f, mutation)
            with self.assertRaisesRegex(AssertionError, 'superset'):
                native.grade(f, False, 2)

    def test_unresolved3_and_tamper_refusal_unchanged(self):
        for mutation in (None, 'tuple', 'exec', 'duplicate', 'unsigned', 'version', 'malformed'):
            f = self.fixture(attempts=3)
            if mutation:
                native.mutate_authority(f, mutation)
            native.unchanged(f)
            (f['dest'] / f['resolved']).write_bytes(self.payload[f['resolved']])
            with self.assertRaisesRegex(AssertionError, 'mutated'):
                native.unchanged(f)

    def test_full_signed_closure_and_new_metadata_mutation_refuse(self):
        f = self.fixture()
        self.act(f)
        path = 'ftesurf/textures/no_texture.png'
        (f['dest'] / path).write_bytes(b'unsigned changed outside transaction')
        with self.assertRaisesRegex(AssertionError, 'closure'):
            native.grade(f, False, 2)
        f = self.fixture(attempts=3)
        (f['meta'] / 'state.json.enginetmp').write_bytes(b'new mutation')
        with self.assertRaisesRegex(AssertionError, 'added'):
            native.unchanged(f)

    def test_no_authority_cannot_scan_or_adopt_temps(self):
        f = self.fixture(completed=True)
        (f['meta'] / 'ingame/journal.json').unlink()
        f['seed'] = native.inventory(f['dest'])
        native.unchanged(f)
        native.stage_path(f, f['resolved']).unlink()
        with self.assertRaisesRegex(AssertionError, 'mutated'):
            native.unchanged(f)

    @unittest.skipUnless(os.name == 'nt', 'real Windows sharing semantics required')
    def test_real_leaf_delete_denial_and_release(self):
        f = self.fixture(completed=True)
        case = self.root / 'lock-case'
        case.mkdir()
        path = native.stage_path(f, f['resolved'])
        with native.held_delete(path, case):
            self.assertEqual(path.read_bytes(), self.payload[f['resolved']])
        receipt = json.loads((case / 'lock.json').read_text())
        self.assertEqual(receipt['delete_error'], 32)
        self.assertEqual(receipt['status'], 'PASS')
        path.unlink()
        self.assertFalse(path.exists(), 'real released delete must ACT')

    def test_receipt_failure_preserves_guard_and_failed_grade_is_fail(self):
        phase = self.root / 'phase'
        phase.mkdir()
        def reject():
            raise AssertionError('acted failure')
        with self.assertRaisesRegex(AssertionError, 'acted'):
            native.semantic_phase(phase, reject)
        self.assertEqual(json.loads((phase / 'grade.json').read_text())['status'], 'FAIL')
        guard = phase / 'retirement-semantic-guard'
        try:
            with patch.object(Path, 'write_text', side_effect=OSError('denied')):
                with self.assertRaisesRegex(OSError, 'denied'):
                    native.semantic_phase(phase, lambda: {})
            self.assertIn(guard, native.UNCONFIRMED_PHASES)
        finally:
            native.UNCONFIRMED_PHASES.discard(guard)


if __name__ == '__main__':
    unittest.main()
