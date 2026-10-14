"""Initial full-row authority/namespace mutation falsifiers; no native launch."""
import copy
import json
import unittest

from test_update_native_initial_superset import initial_namespace, partial_authority
from test_update_native_publication_superset import full_authority, grade_state
from test_update_native_staging_windows import journal
from test_update_native_journal_deferred_unit import scratch


class InitialSupersetTests(unittest.TestCase):
    def setUp(self):
        self.files = {'a': dict(hash='1'*64, size=3, exec=False),
                      'b': dict(hash='2'*64, size=4, exec=True)}
        self.paths = ['a', 'b']
        self.full = journal(self.files, self.paths, 'v', 1)

    def test_initial_full_rows_not_partial_or_reordered(self):
        full_authority(self.full, self.files, self.paths, 'v', 1)
        for rows in (self.full['files'][:1], self.full['files'][::-1], self.full['files']*2):
            bad = self.full | {'files': rows}
            with self.assertRaises(AssertionError):
                full_authority(bad, self.files, self.paths, 'v', 1)

    def test_signed_tuple_version_and_attempt_mutations(self):
        for key, value in [('p', 'outside'), ('h', '3'*64), ('s', 9), ('x', 1)]:
            bad = copy.deepcopy(self.full)
            bad['files'][0][key] = value
            with self.assertRaises(AssertionError):
                full_authority(bad, self.files, self.paths, 'v', 1)
        for key, value in [('version', 'other'), ('attempts', 0), ('attempts', 2)]:
            with self.assertRaises(AssertionError):
                full_authority(self.full | {key: value}, self.files, self.paths, 'v', 1)

    def test_partial_both_pending_positions_discriminate_legacy(self):
        for pending in self.paths:
            self.assertFalse(partial_authority(journal(self.files, self.paths, 'v', 2),
                self.files, self.paths, pending, 'v', False))
            self.assertTrue(partial_authority(journal(self.files, [pending], 'v', 2),
                self.files, self.paths, pending, 'v', True))
            with self.assertRaises(AssertionError):
                partial_authority(journal(self.files, [pending], 'v', 2),
                    self.files, self.paths, pending, 'v', False)
            with self.assertRaises(AssertionError):
                partial_authority(journal(self.files, self.paths, 'v', 1),
                    self.files, self.paths, pending, 'v', False)

    def test_namespace_authority_absence_full_stage_and_all_siblings(self):
        with scratch() as root:
            ingame = root / 'ingame'
            (ingame / 'staged').mkdir(parents=True)
            stages = {'1'*64: b'one', '2'*64: b'two'}
            expected = {'manifest.json': b'signed', 'journal.tmp': b'full'} | {
                'staged/' + k: v for k, v in stages.items()}
            for p, data in expected.items():
                (ingame / p).write_bytes(data)
            def grade():
                initial_namespace(root, b'signed', stages, temp=b'full')
            grade()
            for path, data in expected.items():
                (ingame / path).unlink()
                with self.assertRaises(AssertionError):
                    grade()
                (ingame / path).write_bytes(b'wrong')
                with self.assertRaises(AssertionError):
                    grade()
                (ingame / path).write_bytes(data)
            for path in ('journal.json', 'journal.other', 'staged/unknown.part', 'staged/other.install'):
                (ingame / path).write_bytes(b'extra')
                with self.assertRaises(AssertionError):
                    grade()
                (ingame / path).unlink()
            (ingame / 'journal.tmp').rename(ingame / 'journal.json')
            initial_namespace(root, b'signed', stages, authority=b'full')

    def test_entire_closure_ledger_consent_certificate_mutations(self):
        with scratch() as root:
            meta = root / '.ftesurf-updater'
            (meta / 'ingame').mkdir(parents=True)
            expected = {'managed': b'signed', 'protected': b'edit', 'unmanaged': b'local'}
            ledger = dict(version='0.1.24', files={'managed': 'hash', 'outside': 'outside-hash'})
            for p, data in expected.items():
                (root / p).write_bytes(data)
            initial = {'state.json': json.dumps(ledger).encode(), 'consent': b'1\n', 'ingame/manifest.json': b'envelope'}
            for p, data in initial.items():
                (meta / p).write_bytes(data)
            def grade(complete=False, state=ledger):
                grade_state(root, meta, expected, state, b'envelope', 'v', complete)
            grade()
            for p, data in expected.items():
                (root / p).write_bytes(b'wrong')
                with self.assertRaises(AssertionError):
                    grade()
                (root / p).write_bytes(data)
            for p, data in initial.items():
                (meta / p).write_bytes(b'wrong')
                with self.assertRaises((AssertionError, json.JSONDecodeError)):
                    grade()
                (meta / p).write_bytes(data)
            for changed in (ledger | {'version': 'v'}, ledger | {'files': {'managed': 'hash'}}):
                (meta / 'state.json').write_text(json.dumps(changed))
                with self.assertRaises(AssertionError):
                    grade()
            (meta / 'state.json').write_text(json.dumps(ledger))
            (meta / 'installed.json').write_bytes(b'envelope')
            with self.assertRaises(AssertionError):
                grade()
            final = ledger | {'version': 'v'}
            (meta / 'state.json').write_text(json.dumps(final))
            grade(True, final)
            (meta / 'installed.json').write_bytes(b'wrong')
            with self.assertRaises(AssertionError):
                grade(True, final)


if __name__ == '__main__':
    unittest.main()
