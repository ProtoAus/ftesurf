"""Initial full-row authority/namespace mutation falsifiers; no native launch."""
import test_update_native_initial_superset as gate
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

    def test_debit3_authority_refuses_reset_or_extra_debit_both_positions(self):
        for pending in self.paths:
            for before in (False, True):
                selected = [pending] if before else self.paths
                full = journal(self.files, selected, 'v', 3)
                self.assertEqual(partial_authority(full, self.files, self.paths, pending, 'v', before, 3), before)
                for attempts in (0, 1, 2, 4):
                    with self.assertRaises(AssertionError):
                        partial_authority(full | {'attempts': attempts}, self.files, self.paths,
                                          pending, 'v', before, 3)
                for key, value in [('version', 'other'), ('files', [])]:
                    with self.assertRaises(AssertionError):
                        partial_authority(full | {key: value}, self.files, self.paths,
                                          pending, 'v', before, 3)

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

    def test_complete_metadata_namespace_rejects_outer_siblings_and_survivor_changes(self):
        from test_update_native_journal_deferred_unit import scratch
        import json
        for complete in (False, True):
            with scratch() as meta:
                ledger = dict(version='v' if complete else 'old', files={'outside': 'known'})
                stages = {} if complete else {'hash': b'staged'}
                authority = None if complete else b'independently checked journal'
                temp = b'exact failed journal temp'
                expected = gate.METADATA_SENTINEL | {
                    'consent': b'1\n', 'state.json': json.dumps(ledger).encode(),
                    'install.lock': b'', 'ingame/manifest.json': b'signed',
                    'ingame/journal.tmp': temp}
                if complete:
                    expected['installed.json'] = b'signed'
                else:
                    expected['ingame/journal.json'] = authority
                    expected['ingame/staged/hash'] = b'staged'
                for path, data in expected.items():
                    target = meta / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                def grade():
                    gate.metadata_namespace(meta, b'signed', ledger, stages,
                                            authority=authority, temp=temp, complete=complete)
                grade()
                # Refusal/exhaustion cannot adopt an unexpected seed survivor.
                for path in ('state.json.enginetmp', 'state.json.tmp', 'installed.json.tmp',
                             'arbitrary-new-sibling', 'ingame/unexpected.tmp'):
                    (meta / path).write_bytes(b'unexpected')
                    with self.subTest(complete=complete, added=path), self.assertRaises(AssertionError):
                        grade()
                    (meta / path).unlink()
                for path, data in expected.items():
                    (meta / path).unlink()
                    with self.subTest(complete=complete, removed=path), self.assertRaises(AssertionError):
                        grade()
                    (meta / path).write_bytes(b'changed')
                    with self.subTest(complete=complete, changed=path), self.assertRaises((AssertionError, ValueError)):
                        grade()
                    (meta / path).write_bytes(data)
                grade()


if __name__ == '__main__':
    unittest.main()
