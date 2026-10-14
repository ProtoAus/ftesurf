"""Independent signed-row, closure and stage inventory oracle negatives."""
import copy
from pathlib import Path
import unittest

from test_update_native_publication_superset import full_authority, check_bytes, stage_map, grade_state
from test_update_native_staging_windows import journal
from test_update_native_journal_deferred_unit import scratch


class PublicationSupersetOracle(unittest.TestCase):
    def setUp(self):
        self.files = {'a': dict(hash='1'*64, size=3, exec=False),
                      'b': dict(hash='2'*64, size=4, exec=True)}
        self.paths = ['a', 'b']
        self.authority = journal(self.files, self.paths, '0.1.25', 1)

    def grade(self, value):
        full_authority(value, self.files, self.paths, '0.1.25', 1)

    def test_full_rows_both_orders(self):
        self.grade(self.authority)
        full_authority(journal(self.files, ['b', 'a'], '0.1.25', 1),
                       self.files, ['b', 'a'], '0.1.25', 1)

    def test_legacy_reduction_fails_full_authority(self):
        with self.assertRaises(AssertionError):
            self.grade(journal(self.files, ['b'], '0.1.25', 1))

    def test_signed_tuple_budget_version_order_mutations(self):
        for key, value in [('h', '3'*64), ('s', 9), ('x', 1), ('p', 'outside')]:
            with self.subTest(key=key):
                bad = copy.deepcopy(self.authority)
                bad['files'][0][key] = value
                with self.assertRaises(AssertionError):
                    self.grade(bad)
        for key, value in [('attempts', 2), ('version', '0.1.24'),
                           ('files', list(reversed(self.authority['files']))),
                           ('files', self.authority['files'] * 2)]:
            bad = copy.deepcopy(self.authority)
            bad[key] = value
            with self.assertRaises(AssertionError):
                self.grade(bad)

    def test_full_closure_protected_and_unmanaged_bytes(self):
        with scratch() as root:
            expected = {'managed': b'signed', 'protected': b'edited', 'unmanaged': b'local'}
            for name, data in expected.items():
                (root / name).write_bytes(data)
            check_bytes(root, expected)
            for name, data in expected.items():
                (root / name).write_bytes(b'wrong')
                with self.assertRaises(AssertionError):
                    check_bytes(root, expected)
                (root / name).write_bytes(data)

    def test_ledger_version_consent_manifest_certificate_mutations(self):
        with scratch() as root:
            meta = root / '.ftesurf-updater'
            (meta / 'ingame').mkdir(parents=True)
            ledger = dict(version='0.1.24', files={'a': '1'*64})
            import json
            (root / 'a').write_bytes(b'signed')
            initial = {'state.json': json.dumps(ledger).encode(), 'consent': b'1\n',
                       'ingame/manifest.json': b'signed envelope'}
            for path, data in initial.items():
                (meta / path).write_bytes(data)
            def grade():
                grade_state(root, meta, {'a': b'signed'}, ledger, b'signed envelope', '0.1.25')
            grade()
            for path, data in [('state.json', b'{"version":"0.1.25","files":{"a":"wrong"}}'),
                               ('consent', b'0\n'), ('ingame/manifest.json', b'wrong')]:
                (meta / path).write_bytes(data)
                with self.assertRaises(AssertionError):
                    grade()
                (meta / path).write_bytes(initial[path])
            (meta / 'installed.json').write_bytes(b'premature certificate')
            with self.assertRaises(AssertionError):
                grade()

    def test_stage_map_includes_outside_siblings_and_changed_bytes(self):
        with scratch() as root:
            stage = root / '.ftesurf-updater/ingame/staged'
            stage.mkdir(parents=True)
            expected = {'1'*64: b'signed', 'outside.part': b'part'}
            for name, data in expected.items():
                (stage / name).write_bytes(data)
            self.assertEqual(stage_map(root), expected)
            (stage / ('1'*64)).unlink()
            self.assertNotEqual(stage_map(root), expected)
            (stage / ('1'*64)).write_bytes(b'corrupt')
            self.assertNotEqual(stage_map(root), expected)


if __name__ == '__main__':
    unittest.main()
