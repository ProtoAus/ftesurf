"""Independent mutation falsifiers for the retained live apply gate."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from collections import Counter
import test_update_native_retained_apply as gate
from test_update_native_journal import UNCONFIRMED_PHASES


class RetainedApplyTests(unittest.TestCase):
    def setUp(self):
        self.seed = {'asset.png': b'signed content', 'ftesurf/data/runs/test.rec': b'protected',
            '.ftesurf-updater/ingame/journal.json': b'original full rows',
            '.ftesurf-updater/ingame/manifest.json': b'signed old envelope',
            '.ftesurf-updater/ingame/staged/hash': b'corrupt stage',
            '.ftesurf-updater/state.json': b'old ledger', 'unmanaged.log': b'unmanaged log'}

    def test_unchanged_positive(self):
        self.assertEqual(gate.grade_unchanged(self.seed, dict(self.seed))['unchanged_files'], len(self.seed))

    def test_every_seed_mutation_refused(self):
        for path in self.seed:
            with self.subTest(path=path):
                altered = self.seed | {path: b'replacement'}
                with self.assertRaises(AssertionError):
                    gate.grade_unchanged(self.seed, altered)

    def test_every_seed_removal_refused(self):
        for path in self.seed:
            altered = dict(self.seed)
            del altered[path]
            with self.assertRaises(AssertionError):
                gate.grade_unchanged(self.seed, altered)

    def test_new_authority_and_object_refused(self):
        for path in ('.ftesurf-updater/ingame/journal.tmp', '.ftesurf-updater/ingame/staged/new', 'new.png'):
            with self.assertRaises(AssertionError):
                gate.grade_unchanged(self.seed, self.seed | {path: b'new'})

    def test_only_exact_live_log_excluded(self):
        gate.grade_unchanged(self.seed, self.seed | {gate.LIVE_LOG: b'append'})
        with self.assertRaises(AssertionError):
            gate.grade_unchanged(self.seed, self.seed | {'unregistered.log': b'append'})

    def test_refusal_requires_manifest_request_and_no_objects(self):
        files = {'asset.png': {'hash': 'a'*64}}
        gate.grade_http(Counter({'/update.json': 1}), 'asset.png', files, True)
        for hits in ({}, {'/update.json': 2}, {'/update.json': 1, '/objects/aa/'+'a'*64: 1}):
            with self.assertRaises(AssertionError):
                gate.grade_http(Counter(hits), 'asset.png', files, True)

    def test_positive_control_requires_exact_object_get(self):
        files = {'asset.png': {'hash': 'a'*64}}
        good = {'/update.json': 1, '/objects/aa/'+'a'*64: 1}
        gate.grade_http(Counter(good), 'asset.png', files, False)
        for hits in ({'/update.json': 1}, good | {'/unexpected': 1}, good | {'/update.json': 2}):
            with self.assertRaises(AssertionError):
                gate.grade_http(Counter(hits), 'asset.png', files, False)

    def positive_fixture(self):
        f = dict(files={'asset.png': {'hash': 'a' * 64}}, payload={'asset.png': b'new signed content'},
                 signed=b'signed envelope', ledger={'version': '0.1.25', 'files': {'asset.png': 'a' * 64}})
        before = dict(self.seed)
        del before['.ftesurf-updater/ingame/journal.json']
        before['.ftesurf-updater/state.json'] = json.dumps(f['ledger']).encode()
        before['.ftesurf-updater/ingame/staged/' + 'a' * 64] = b'old named stage'
        before['.ftesurf-updater/ingame/journal.tmp'] = b'old sibling'
        before['.ftesurf-updater/consent'] = b'1\n'
        after = dict(before)
        after['asset.png'] = f['payload']['asset.png']
        after['.ftesurf-updater/installed.json'] = f['signed']
        after['.ftesurf-updater/ingame/manifest.json'] = f['signed']
        after['.ftesurf-updater/state.json'] = json.dumps(f['ledger'], indent=2).encode()
        del after['.ftesurf-updater/ingame/staged/' + 'a' * 64]
        del after['.ftesurf-updater/ingame/journal.tmp']
        return f, before, after

    def test_exact_positive_state_acts(self):
        f, before, after = self.positive_fixture()
        self.assertEqual(gate.grade_installed(f, 'asset.png', before, after)['exact_files'], len(after))

    def test_positive_every_survivor_mutation_refused(self):
        f, before, after = self.positive_fixture()
        for path in after:
            with self.subTest(path=path):
                changed = after | {path: b'wrong bytes'}
                if path == '.ftesurf-updater/state.json':
                    changed[path] = b'{"version":"9.0.0","files":{}}'
                with self.assertRaises(AssertionError):
                    gate.grade_installed(f, 'asset.png', before, changed)

    def test_positive_every_survivor_removal_refused(self):
        f, before, after = self.positive_fixture()
        for path in after:
            changed = dict(after)
            del changed[path]
            with self.subTest(path=path), self.assertRaises((AssertionError, KeyError)):
                gate.grade_installed(f, 'asset.png', before, changed)

    def test_positive_unexpected_paths_refused(self):
        f, before, after = self.positive_fixture()
        for path in ('ftesurf/data/runs/new.rec', 'unregistered.log',
                     '.ftesurf-updater/ingame/staged/new', '.ftesurf-updater/ingame/journal.json',
                     '.ftesurf-updater/state.json.tmp'):
            with self.subTest(path=path), self.assertRaises(AssertionError):
                gate.grade_installed(f, 'asset.png', before, after | {path: b'new bytes'})

    def test_positive_consumed_names_cannot_survive(self):
        f, before, after = self.positive_fixture()
        for path in ('.ftesurf-updater/ingame/staged/' + 'a' * 64, '.ftesurf-updater/ingame/journal.tmp'):
            with self.assertRaises(AssertionError):
                gate.grade_installed(f, 'asset.png', before, after | {path: before[path]})

    def test_failed_live_joined_http_receipt_retained(self):
        with tempfile.TemporaryDirectory(dir=os.environ['FTESURF_TEST_SCRATCH']) as temp:
            target = Path(temp) / 'not-yet-launched/http'
            gate.persist_http(target, Counter({'/update.json': 1}), {'joined': True}, False)
            receipt = json.loads((target / 'census.json').read_text())
            self.assertEqual(receipt, {'status': 'FAIL', 'joined': True, 'live_completed': False,
                                      'hits': {'/update.json': 1}})

    def test_unjoined_http_cannot_claim_pass(self):
        with tempfile.TemporaryDirectory(dir=os.environ['FTESURF_TEST_SCRATCH']) as temp:
            target = Path(temp) / 'http'
            gate.persist_http(target, Counter(), {}, True)
            self.assertEqual(json.loads((target / 'census.json').read_text())['status'], 'FAIL')

    def test_active_export_exact_exemptions(self):
        base = os.environ.get('FTESURF_TEST_SCRATCH')
        self.assertTrue(base, 'owned FTESURF_TEST_SCRATCH required')
        with tempfile.TemporaryDirectory(dir=base) as temp:
            root = Path(temp) / 'runtime'
            for p, data in self.seed.items() | {gate.LOCK: b'held lock', gate.LIVE_LOG: b'appending log'}.items():
                target = root / p
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            target = Path(temp) / 'active'
            gate.active_snapshot(root, target)
            exported = json.loads((target / 'inventory.json').read_text())
            self.assertFalse(exported['full_export'])
            self.assertEqual(set(exported['excluded']), {gate.LOCK, gate.LIVE_LOG})
            self.assertEqual({x['path'] for x in exported['files']}, set(self.seed))

    def test_failed_semantic_guard_retained(self):
        base = os.environ.get('FTESURF_TEST_SCRATCH')
        with tempfile.TemporaryDirectory(dir=base) as temp:
            phase = Path(temp)
            def fail():
                raise AssertionError('mutation')
            try:
                with self.assertRaises(AssertionError):
                    gate.semantic(phase, fail)
                self.assertIn(phase / 'semantic-guard', UNCONFIRMED_PHASES)
                self.assertEqual(json.loads((phase / 'grade.json').read_text())['status'], 'FAIL')
            finally:
                UNCONFIRMED_PHASES.discard(phase / 'semantic-guard')


if __name__ == '__main__':
    unittest.main()
