#!/usr/bin/env python3
"""Client-free acted byte mutations for the Windows staged retirement grader."""
from collections import Counter
import copy
import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import test_update_native_staging_windows as native


class StagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get('FTESURF_TEST_SCRATCH'))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = dict(version='0.1.25')
        self.payload = {'ftesurf/gfx/crosshairs/xhair1.png': b'new ordinary one',
            'ftesurf/gfx/crosshairs/xhair2.png': b'new ordinary two',
            'ftesurf/gfx/env/missingtexture.png': b'shared signed bytes',
            'ftesurf/textures/no_texture.png': b'shared signed bytes',
            'ftesurf/maps/zones/local/owned.json': b'new managed zone'}
        self.files = {p: dict(hash=native.digest(b), size=len(b), exec=False) for p, b in self.payload.items()}
        self.signed = b'owned signed-envelope stand-in; verification tested separately'
        self.count = 0

    def fixture(self, kind='unique', first=False):
        self.count += 1
        return native.prepare(self.root, str(self.count), kind, first, self.signed,
            self.manifest, self.files, self.payload)

    def stage(self, f, path):
        return f['meta'] / 'ingame/staged' / self.files[path]['hash']

    def act(self, f, complete=False):
        # Independent byte-level fixture actor; never call expected_stage.
        state = copy.deepcopy(f['ledger'])
        state['files'][f['resolved']] = self.files[f['resolved']]['hash']
        (f['dest'] / f['resolved']).write_bytes(self.payload[f['resolved']])
        if complete:
            (f['dest'] / f['pending']).write_bytes(self.payload[f['pending']])
            state['version'] = self.manifest['version']
            state['files'][f['pending']] = self.files[f['pending']]['hash']
            (f['meta'] / 'ingame/journal.json').unlink()
            (f['meta'] / 'installed.json').write_bytes(self.signed)
            self.stage(f, f['pending']).unlink()
        else:
            pending = dict(version=self.manifest['version'], attempts=2, files=[dict(p=f['pending'],
                h=self.files[f['pending']]['hash'], s=self.files[f['pending']]['size'], x=0)])
            if f['kind'] == 'rewrite-failure':
                (f['meta'] / 'ingame/journal.tmp').write_text(json.dumps(pending))
                f['failed_temp'] = (f['meta'] / 'ingame/journal.tmp').read_bytes()
            else:
                (f['meta'] / 'ingame/journal.json').write_text(json.dumps(pending))
        if complete or f['kind'] != 'rewrite-failure':
            if f['kind'] not in ('shared', 'reduced-orphan') and self.stage(f, f['resolved']).exists():
                self.stage(f, f['resolved']).unlink()
            if f['kind'] not in ('corrupt-resolved', 'wrong-size-resolved', 'reduced-orphan') and self.stage(f, f['zone']).exists():
                self.stage(f, f['zone']).unlink()
        (f['meta'] / 'state.json').write_text(json.dumps(state))

    def test_all_partial_and_complete_states_act_in_both_orders(self):
        for kind in native.KINDS:
            for first in (False, True):
                f = self.fixture(kind, first)
                self.act(f)
                native.grade(f, False, {})
                self.act(f, True)
                native.grade(f, True, {})

    def test_shared_hash_required_and_unique_hashes_discriminate(self):
        files = copy.deepcopy(self.files)
        files['ftesurf/textures/no_texture.png']['hash'] = '0' * 64
        with self.assertRaisesRegex(AssertionError, 'shared/unique'):
            native.select_paths(files, 'shared')
        files = copy.deepcopy(self.files)
        files['ftesurf/gfx/crosshairs/xhair2.png']['hash'] = files['ftesurf/gfx/crosshairs/xhair1.png']['hash']
        with self.assertRaisesRegex(AssertionError, 'shared/unique'):
            native.select_paths(files, 'unique')

    def test_retirement_and_pending_retention_both_must_act(self):
        for path_key, data in [('resolved', self.payload['ftesurf/gfx/crosshairs/xhair1.png']), ('pending', None)]:
            f = self.fixture()
            self.act(f)
            if data is None:
                self.stage(f, f[path_key]).unlink()
            else:
                self.stage(f, f[path_key]).write_bytes(data)
            with self.assertRaisesRegex(AssertionError, 'staged'):
                native.grade(f, False, {})

    def test_shared_object_survives_partial_but_not_complete(self):
        f = self.fixture('shared')
        self.act(f)
        self.stage(f, f['pending']).unlink()
        with self.assertRaisesRegex(AssertionError, 'staged'):
            native.grade(f, False, {})
        self.stage(f, f['pending']).write_bytes(self.payload[f['pending']])
        self.act(f, True)
        native.grade(f, True, {})
        self.stage(f, f['pending']).write_bytes(self.payload[f['pending']])
        with self.assertRaisesRegex(AssertionError, 'staged'):
            native.grade(f, True, {})

    def test_corrupt_resolved_and_unreferenced_objects_cannot_be_removed(self):
        for kind, select in [('corrupt-resolved', lambda f: self.stage(f, f['zone'])),
                             ('wrong-size-resolved', lambda f: self.stage(f, f['zone'])),
                             ('reduced-orphan', lambda f: self.stage(f, f['resolved'])),
                             ('unique', lambda f: f['meta'] / 'ingame/staged' / native.digest(b'valid unreferenced staged sentinel')),
                             ('unique', lambda f: f['meta'] / 'ingame/staged' / native.digest(b'expected bytes not stored'))]:
            f = self.fixture(kind)
            self.act(f)
            self.act(f, True)
            select(f).unlink()
            with self.assertRaisesRegex(AssertionError, 'staged'):
                native.grade(f, True, {})

    def test_corrupt_resolved_discriminates_hash_and_size_guards(self):
        signed = self.payload['ftesurf/maps/zones/local/owned.json']
        for kind in ('corrupt-resolved', 'wrong-size-resolved'):
            f = self.fixture(kind)
            data = self.stage(f, f['zone']).read_bytes()
            self.assertEqual(len(data) == len(signed), kind == 'corrupt-resolved')
            self.assertNotEqual(native.digest(data), native.digest(signed))
            self.act(f)
            native.grade(f, False, {})
            self.stage(f, f['zone']).unlink()  # hash/size-guard bypass would wrongly remove it
            with self.assertRaisesRegex(AssertionError, 'staged'):
                native.grade(f, False, {})

    def test_pending_journal_requires_exact_hash_size_exec_count_and_budget(self):
        for field, value in [('h', '0' * 64), ('s', 0), ('x', 1), ('p', 'different')]:
            f = self.fixture()
            self.act(f)
            path = f['meta'] / 'ingame/journal.json'
            data = json.loads(path.read_text())
            data['files'][0][field] = value
            path.write_text(json.dumps(data))
            with self.assertRaises(AssertionError):
                native.grade(f, False, {})
        for mutate in [lambda j: j.update(attempts=1), lambda j: j['files'].append(j['files'][0])]:
            f = self.fixture()
            self.act(f)
            path = f['meta'] / 'ingame/journal.json'
            data = json.loads(path.read_text())
            mutate(data)
            path.write_text(json.dumps(data))
            with self.assertRaises(AssertionError):
                native.grade(f, False, {})

    def test_false_partial_version_ledger_and_certificate_refuse(self):
        for mutation in ('version', 'zone', 'certificate'):
            f = self.fixture()
            self.act(f)
            path = f['meta'] / 'state.json'
            state = json.loads(path.read_text())
            if mutation == 'version':
                state['version'] = self.manifest['version']
            elif mutation == 'zone':
                state['files'][f['zone']] = self.files[f['zone']]['hash']
            else:
                (f['meta'] / 'installed.json').write_bytes(self.signed)
            path.write_text(json.dumps(state))
            with self.assertRaises(AssertionError):
                native.grade(f, False, {})

    def test_rewrite_failure_requires_original_authority_all_objects_and_temp(self):
        for mutation in ('authority', 'retire', 'temp'):
            f = self.fixture('rewrite-failure')
            self.act(f)
            if mutation == 'authority':
                (f['meta'] / 'ingame/journal.json').unlink()
            elif mutation == 'retire':
                self.stage(f, f['resolved']).unlink()
            else:
                (f['meta'] / 'ingame/journal.tmp').write_text('{}')
            with self.assertRaises((AssertionError, FileNotFoundError)):
                native.grade(f, False, {})

    def test_http_request_rejects_even_after_completion(self):
        f = self.fixture()
        self.act(f)
        self.act(f, True)
        for path in ('/update.json', '/objects/aa/object', '/unknown'):
            with self.assertRaisesRegex(AssertionError, 'HTTP'):
                native.grade(f, True, {path: 1})

    def test_late_accepted_http_worker_is_joined_before_final_census(self):
        entered, release, closing, counted = (threading.Event() for _ in range(4))
        addresses, errors = [], []
        class LateCounter(Counter):
            def __setitem__(self, key, value):
                entered.set()
                if not release.wait(10):
                    errors.append('late handler was not released')
                super().__setitem__(key, value)
                counted.set()
        class EventServer(native.OfflineHTTPServer):
            def __init__(self, address, handler):
                super().__init__((address[0], 0), handler)
                addresses.append(self.server_address)
            def server_close(self):
                closing.set()
                super().server_close()
        def request():
            try:
                connection = http.client.HTTPConnection(*addresses[0], timeout=10)
                try:
                    connection.request('GET', '/late-accepted-request')
                    response = connection.getresponse()
                    if response.status != 503:
                        errors.append('wrong HTTP rejection')
                    response.read()
                finally:
                    connection.close()
            except BaseException as error:
                errors.append(repr(error))
        def release_on_close():
            if not closing.wait(10):
                errors.append('server_close did not start')
            release.set()
        client = threading.Thread(target=request)
        unblock = threading.Thread(target=release_on_close)
        with patch.object(native, 'Counter', LateCounter), patch.object(native, 'OfflineHTTPServer', EventServer):
            try:
                with native.offline_mirror(dict(mirrors=['http://127.0.0.1:1'])) as hits:
                    client.start()
                    self.assertTrue(entered.wait(10))
                    self.assertFalse(hits, 'late GET must not be counted before teardown')
                    unblock.start()
                self.assertTrue(counted.is_set(), 'mirror returned before its accepted worker finished')
                result = dict(status='FAIL')
                with self.assertRaisesRegex(AssertionError, 'final.*HTTP'):
                    native.final_http(hits, result)
                self.assertEqual(result, dict(status='FAIL'))
            finally:
                release.set()
                for thread in (client, unblock):
                    if thread.ident is not None:
                        thread.join(timeout=10)
                        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])

    def test_changed_player_sentinel_refuses(self):
        f = self.fixture()
        self.act(f)
        for path, data in f['sentinels'].items():
            (f['dest'] / path).write_bytes(b'changed')
            with self.assertRaisesRegex(AssertionError, 'sentinel'):
                native.grade(f, False, {})
            (f['dest'] / path).write_bytes(data)

    def test_grade_failure_receipt_is_fail_and_write_denial_retains_guard(self):
        f = self.fixture()
        self.act(f)
        phase = self.root / 'phase'
        phase.mkdir()
        (f['meta'] / 'installed.json').write_bytes(self.signed)
        with self.assertRaises(AssertionError):
            native.grade_phase(f, phase, False, {})
        self.assertEqual(json.loads((phase / 'grade.json').read_text())['status'], 'FAIL')
        guard = phase / 'semantic-receipt-guard'
        with patch.object(Path, 'write_text', side_effect=OSError('receipt denial')):
            with self.assertRaisesRegex(OSError, 'receipt denial'):
                native.grade_phase(f, phase, False, {})
        self.assertIn(guard, native.UNCONFIRMED_PHASES)
        native.UNCONFIRMED_PHASES.remove(guard)


if __name__ == '__main__':
    unittest.main()
