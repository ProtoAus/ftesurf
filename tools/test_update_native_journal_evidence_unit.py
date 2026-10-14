#!/usr/bin/env python3
"""Client-free post-mutation/export/receipt/containment falsifiers.

FTESURF_TEST_SCRATCH names an existing owned directory. All process handles in
these tests are mocks; no client, listener or installed player data is used.
"""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import MagicMock, patch

import test_update_native_journal as cold
import test_update_native_journal_live as live
import test_update_native_journal_deferred as deferred
import test_update_native_journal_interrupt as interrupt
import test_update_native_journal_initial as initial
from test_update_native_journal_deferred_unit import scratch


WRITE_TEXT = Path.write_text
READ_BYTES = Path.read_bytes
COPYFILE = cold.shutil.copyfile
SCANDIR = os.scandir


def fixture(dest):
    files = {'default.fmf': b'owned manifest',
             'ftesurf/ftesurf.cfg': b'owned settings',
             'ftesurf/data/runs/player-sentinel.rec': b'owned recording',
             'ftesurf/gfx/changed.txt': b'old managed content',
             '.ftesurf-updater/consent': b'0\n',
             '.ftesurf-updater/state.json': b'{"version":"old"}',
             '.ftesurf-updater/ingame/journal.tmp': b'completed native temp',
             '.ftesurf-updater/ingame/staged/object': b'owned staged input',
             'ftesurf/logs/early.log': b'native acted log'}
    for name, data in files.items():
        p = dest / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return files


def write_fault(name):
    def write(path, *args, **kwargs):
        if path.name == name:
            raise OSError('acted receipt fault: ' + name)
        return WRITE_TEXT(path, *args, **kwargs)
    return write


class EvidenceTests(unittest.TestCase):
    def test_full_export_includes_changed_content_and_non_game_root_files(self):
        with scratch() as root:
            dest, out = root / 'runtime', root / 'evidence'
            files = fixture(dest)
            files['ftesurf/gfx/changed.txt'] = b'actual landed content before grading failure'
            (dest / 'ftesurf/gfx/changed.txt').write_bytes(files['ftesurf/gfx/changed.txt'])
            cold.snapshot(dest, out)
            self.assertEqual(json.loads((out / 'all-runtime-files.sha256.json').read_text()),
                             {p: cold.sha(data) for p, data in files.items()})
            self.assertEqual((out / 'metadata/ingame/journal.tmp').read_bytes(), files['.ftesurf-updater/ingame/journal.tmp'])
            self.assertEqual((out / 'logs/ftesurf/logs/early.log').read_bytes(), files['ftesurf/logs/early.log'])
            receipt = json.loads((out / 'full-export.json').read_text())
            self.assertEqual((receipt['status'], receipt['full_export'], receipt['guard_retained']), ('PASS', True, False))
            cold.ensure_retirable()

    def test_active_publication_export_excludes_only_install_lock_not_full_certificate(self):
        for unreadable in ('install.lock', 'journal.tmp'):
            with self.subTest(unreadable=unreadable), scratch() as root:
                dest, out = root / 'runtime', root / 'evidence'
                fixture(dest)
                (dest / '.ftesurf-updater/install.lock').write_bytes(b'lock control')
                def locked(path):
                    if path.name == unreadable:
                        raise PermissionError('acted exclusive byte-lock')
                    return READ_BYTES(path)
                with patch.object(Path, 'read_bytes', locked):
                    if unreadable == 'journal.tmp':
                        with self.assertRaisesRegex(PermissionError, 'acted exclusive'):
                            cold.publication_snapshot(dest, out)
                    else:
                        cold.publication_snapshot(dest, out)
                        with self.assertRaisesRegex(PermissionError, 'acted exclusive'):
                            cold.snapshot(dest, root / 'full')
                receipt = json.loads((out / 'active-export.json').read_text())
                self.assertFalse(receipt['full_export'])
                self.assertEqual(receipt['active_export'], unreadable == 'install.lock')
                if unreadable == 'install.lock':
                    self.assertEqual(receipt['excluded_paths'], ['.ftesurf-updater/install.lock'])
                    self.assertNotIn('.ftesurf-updater/install.lock', json.loads((out / 'active-runtime-files.sha256.json').read_text()))
                    self.assertFalse((out / 'all-runtime-files.sha256.json').exists())
                    self.assertIn(root / 'full/full-snapshot-guard', cold.UNCONFIRMED_PHASES)
                else:
                    self.assertIn(out / 'active-snapshot-guard', cold.UNCONFIRMED_PHASES)
                    self.assertEqual(receipt['status'], 'FAIL')

    def test_snapshot_inside_runtime_refuses_without_writing_evidence(self):
        with scratch() as root:
            dest = root / 'runtime'
            fixture(dest)
            with self.assertRaisesRegex(AssertionError, 'evidence inside runtime'):
                cold.snapshot(dest, dest / 'evidence')
            self.assertFalse((dest / 'evidence').exists())

    def test_missing_runtime_is_not_an_empty_passing_export(self):
        with scratch() as root:
            with self.assertRaisesRegex(AssertionError, 'missing or linked'):
                cold.snapshot(root / 'missing', root / 'evidence')
            self.assertIn(root / 'evidence/full-snapshot-guard', cold.UNCONFIRMED_PHASES)
            self.assertEqual(json.loads((root / 'evidence/full-export.json').read_text())['status'], 'FAIL')

    def test_final_copy_hash_inventory_or_receipt_failure_blocks_fallback_retirement(self):
        for fault in ('copy', 'hash', 'read', 'inventory', 'receipt'):
            with self.subTest(fault=fault), scratch() as root:
                runtime, evidence = root / 'runtime', root / 'evidence'
                dest = runtime / 'case'
                fixture(dest)
                evidence.mkdir()
                target = evidence / 'final'
                if fault == 'copy':
                    failure = patch.object(cold.shutil, 'copyfile', side_effect=OSError('acted copy fault'))
                elif fault == 'hash':
                    failure = patch.object(cold, 'sha', side_effect=OSError('acted hash fault'))
                elif fault == 'read':
                    def denied(path):
                        if path.name == 'journal.tmp':
                            raise PermissionError('acted locked-file read fault')
                        return READ_BYTES(path)
                    failure = patch.object(Path, 'read_bytes', denied)
                else:
                    failure = patch.object(Path, 'write_text', write_fault(
                        'full-export.json' if fault == 'receipt' else 'all-runtime-files.sha256.json'))
                with failure, self.assertRaisesRegex(OSError, 'acted'):
                    cold.snapshot(dest, target)
                self.assertIn(target / 'full-snapshot-guard', cold.UNCONFIRMED_PHASES)
                if fault != 'receipt':
                    self.assertEqual(json.loads((target / 'full-export.json').read_text())['status'], 'FAIL')
                result = {'status': 'PASS'}
                # A SUCCESSFUL complete fallback cannot erase the earlier guard.
                with self.assertRaisesRegex(AssertionError, 'unconfirmed'):
                    live.retire_runtime(runtime, evidence, result, dest)
                self.assertTrue(dest.exists())
                self.assertFalse(result['runtime_retired'])
                self.assertEqual(result['status'], 'FAIL')

    def test_root_or_subtree_listing_failure_is_not_an_incomplete_full_pass(self):
        for subtree in ('', '.ftesurf-updater/ingame/staged', 'ftesurf/gfx'):
            with self.subTest(subtree=subtree), scratch() as root:
                runtime, evidence = root / 'runtime', root / 'evidence'
                dest, out = runtime / 'case', evidence / 'final'
                fixture(dest)
                blocked = dest / subtree
                calls = []
                def listing(path):
                    calls.append(Path(path))
                    if Path(path) == blocked:
                        raise PermissionError('acted directory listing refusal')
                    return SCANDIR(path)
                with patch.object(cold.os, 'scandir', side_effect=listing), self.assertRaisesRegex(PermissionError, 'acted directory listing'):
                    cold.snapshot(dest, out)
                self.assertIn(blocked, calls)
                receipt = json.loads((out / 'full-export.json').read_text())
                self.assertEqual((receipt['status'], receipt['full_export'], receipt['guard_retained']), ('FAIL', False, True))
                self.assertIn(out / 'full-snapshot-guard', cold.UNCONFIRMED_PHASES)
                with self.assertRaisesRegex(AssertionError, 'unconfirmed'):
                    live.retire_runtime(runtime, evidence, {'status': 'FAIL'}, dest)
                self.assertTrue(dest.exists())

    def test_failed_target_cannot_be_reused_or_overwrite_any_export_history(self):
        for active in (False, True):
            for fault in ('read', 'copy', 'hash', 'receipt'):
                with self.subTest(active=active, fault=fault), scratch() as root:
                    runtime, evidence = root / 'runtime', root / 'evidence'
                    dest, out = runtime / 'case', evidence / 'state'
                    fixture(dest)
                    exporter = cold.publication_snapshot if active else cold.snapshot
                    if fault == 'read':
                        def denied(path):
                            if path.name == 'journal.tmp':
                                raise PermissionError('acted read fault')
                            return READ_BYTES(path)
                        failure = patch.object(Path, 'read_bytes', denied)
                    elif fault == 'copy':
                        failure = patch.object(cold.shutil, 'copyfile', side_effect=OSError('acted copy fault'))
                    elif fault == 'hash':
                        failure = patch.object(cold, 'sha', side_effect=OSError('acted hash fault'))
                    else:
                        failure = patch.object(Path, 'write_text', write_fault('active-export.json' if active else 'full-export.json'))
                    with failure, self.assertRaisesRegex(OSError, 'acted'):
                        exporter(dest, out)
                    before = {p.relative_to(out): p.read_bytes() for p in out.rglob('*') if p.is_file()}
                    for retry in (cold.snapshot, cold.publication_snapshot):
                        with self.assertRaisesRegex(AssertionError, 'previous export'):
                            retry(dest, out)
                        self.assertEqual({p.relative_to(out): p.read_bytes() for p in out.rglob('*') if p.is_file()}, before)
                    guard = out / ('active-snapshot-guard' if active else 'full-snapshot-guard')
                    self.assertIn(guard, cold.UNCONFIRMED_PHASES)
                    cold.snapshot(dest, evidence / 'separate-current-state')
                    with self.assertRaisesRegex(AssertionError, 'unconfirmed'):
                        live.retire_runtime(runtime, evidence, {'status': 'FAIL'}, dest)
                    self.assertTrue(dest.exists())

    def test_actual_initial_and_interrupt_duplicate_calls_preserve_one_shot_failures(self):
        for gate in (initial, interrupt):
            for fault in ('read', 'hash', 'receipt'):
                with self.subTest(gate=gate.__name__, fault=fault), scratch() as root:
                    runtime, evidence = root / 'runtime', root / 'evidence'
                    dest, phase = runtime / 'case', evidence / 'live'
                    fixture(dest)
                    process = MagicMock(pid=1234, _handle=5678, returncode=0)
                    process.poll.return_value = 0
                    native = MagicMock()
                    native.NtResumeProcess.return_value = 0
                    native.CloseHandle.return_value = 1
                    binding = {k: 1 for k in ('entry_rva', 'pre_rva', 'post_rva', 'entry_byte', 'pre_byte', 'post_byte', 'initial_caller_rva', 'commit_caller_rva', 'cold_caller_rva')}
                    binding.update(abi='mock-only', before=False)
                    def started(*args, **kwargs):
                        (phase / 'debug.jsonl').write_text('{}\n')
                        (dest / 'ftesurf/journal-initial.log').write_text('JOURNAL_INITIAL_READY\nupdate: 2 file\nupdate state : available\nJOURNAL_INITIAL_AVAILABLE\nJOURNAL_INITIAL_APPLY\n')
                        return process
                    def census(job, receipt, key):
                        receipt[key] = 0
                        receipt[key + '_observations'] = [0]
                    calls = []
                    def one_read(path):
                        if path == dest / '.ftesurf-updater/state.json' and not calls:
                            calls.append('read')
                            raise PermissionError('acted one-shot read fault')
                        return READ_BYTES(path)
                    real_sha = cold.sha
                    def one_hash(data):
                        if not calls:
                            calls.append('hash')
                            raise OSError('acted one-shot hash fault')
                        return real_sha(data)
                    def one_receipt(path, *args, **kwargs):
                        if path.name == 'full-export.json' and not calls:
                            calls.append('receipt')
                            raise OSError('acted one-shot receipt fault')
                        return WRITE_TEXT(path, *args, **kwargs)
                    with ExitStack() as stack:
                        stack.enter_context(patch.object(gate.subprocess, 'Popen', side_effect=started))
                        stack.enter_context(patch.object(gate, 'owned_job', return_value='mock-owned-job'))
                        stack.enter_context(patch.object(gate.ctypes, 'WinDLL', return_value=native, create=True))
                        stack.enter_context(patch.object(gate, 'grade_events', return_value=(4321, 86)))
                        stack.enter_context(patch.object(gate, 'wait_win_job_empty', side_effect=census))
                        if fault == 'read':
                            stack.enter_context(patch.object(Path, 'read_bytes', one_read))
                        elif fault == 'hash':
                            stack.enter_context(patch.object(cold, 'sha', side_effect=one_hash))
                        else:
                            stack.enter_context(patch.object(Path, 'write_text', one_receipt))
                        with self.assertRaisesRegex(AssertionError, 'previous export'):
                            if gate is initial:
                                gate.live(Path('mock-client'), Path('mock-helper'), binding, dest, phase, 'crash-before', {'url': 'http://127.0.0.1:1/feed'}, lambda event: None)
                            else:
                                gate.interrupt(Path('mock-client'), Path('mock-helper'), binding, dest, phase, 'crash-before')
                    self.assertEqual(calls, [fault])
                    receipt = json.loads((phase / 'process.json').read_text())
                    self.assertEqual(receipt['status'], 'FAIL')
                    self.assertIn('acted one-shot', receipt['error'])
                    self.assertIn('previous export', receipt['cleanup_error'])
                    self.assertFalse(receipt['full_export'])
                    self.assertTrue(receipt['containment_confirmed'])
                    self.assertIn(phase, cold.UNCONFIRMED_PHASES)
                    self.assertIn(phase / 'state/full-snapshot-guard', cold.UNCONFIRMED_PHASES)
                    if fault != 'receipt':
                        self.assertEqual(json.loads((phase / 'state/full-export.json').read_text())['status'], 'FAIL')
                    else:
                        self.assertFalse((phase / 'state/full-export.json').exists())
                    native.TerminateJobObject.assert_not_called()
                    with self.assertRaisesRegex(AssertionError, 'unconfirmed'):
                        live.retire_runtime(runtime, evidence, {'status': 'FAIL'}, dest)
                    self.assertTrue(dest.exists())

    def test_copy_that_changes_bytes_is_rejected_not_certified(self):
        with scratch() as root:
            dest, out = root / 'runtime', root / 'evidence'
            fixture(dest)
            def corrupt(source, target):
                COPYFILE(source, target)
                Path(target).write_bytes(b'changed by the export negative')
            with patch.object(cold.shutil, 'copyfile', side_effect=corrupt), self.assertRaisesRegex(AssertionError, 'exported bytes differ'):
                cold.snapshot(dest, out)
            self.assertIn(out / 'full-snapshot-guard', cold.UNCONFIRMED_PHASES)

    def test_retirement_result_receipt_failure_precedes_root_removal(self):
        with scratch() as root:
            runtime, evidence = root / 'runtime', root / 'evidence'
            dest = runtime / 'case'
            fixture(dest)
            evidence.mkdir()
            result = {'status': 'PASS'}
            with patch.object(Path, 'write_text', write_fault('result.json')), self.assertRaisesRegex(OSError, 'acted receipt fault'):
                live.retire_runtime(runtime, evidence, result, dest)
            self.assertTrue(dest.exists())
            self.assertEqual(result['status'], 'FAIL')
            self.assertFalse(result['runtime_retired'])

    def test_each_legacy_driver_uses_the_shared_fresh_disjoint_preflight(self):
        for gate in (live, deferred, interrupt):
            self.assertIs(gate.preflight_paths, cold.preflight_paths)
        with scratch() as root:
            for runtime, evidence in ((root / 'runtime', root / 'runtime'),
                    (root / 'runtime', root / 'runtime/evidence'),
                    (root / 'evidence/runtime', root / 'evidence')):
                with self.assertRaisesRegex(AssertionError, 'disjoint'):
                    cold.preflight_paths(runtime, evidence)
            self.assertEqual(list(root.iterdir()), [])

    @unittest.skipUnless(os.name == 'nt', 'Windows cold process branch')
    def test_cold_post_mutation_grading_failure_and_independent_failure_guards(self):
        for fault in (None, 'hash', 'receipt', 'containment', 'handle'):
            with self.subTest(fault=fault), scratch() as root:
                runtime, evidence = root / 'runtime', root / 'evidence'
                dest, phase = runtime / 'case', evidence / 'cold'
                fixture(dest)
                landed = b'native wait mutation ACTED before grader refusal'
                process = MagicMock(pid=1234, _handle=5678, returncode=0)
                process.poll.return_value = 0
                process.wait.side_effect = lambda **unused: (dest / 'ftesurf/gfx/changed.txt').write_bytes(landed)
                native = MagicMock()
                native.NtResumeProcess.return_value = 0
                native.CloseHandle.return_value = 0 if fault == 'handle' else 1
                def census(job, receipt, key):
                    if fault == 'containment' and key == 'job_active_after_cleanup':
                        receipt[key] = 1
                        raise AssertionError('acted containment fault')
                    receipt[key] = 0
                    receipt[key + '_observations'] = [0]
                with ExitStack() as stack:
                    stack.enter_context(patch.object(cold.subprocess, 'Popen', return_value=process))
                    stack.enter_context(patch('test_update_handoff.owned_job', return_value='mock-owned-job'))
                    stack.enter_context(patch.object(cold.ctypes, 'WinDLL', return_value=native))
                    stack.enter_context(patch.object(cold, 'wait_win_job_empty', side_effect=census))
                    if fault == 'hash':
                        stack.enter_context(patch.object(cold, 'sha', side_effect=OSError('acted hash fault')))
                    if fault == 'receipt':
                        stack.enter_context(patch.object(Path, 'write_text', write_fault('process.json')))
                    with self.assertRaises((AssertionError, OSError)):
                        cold.run_native(Path('external-client'), dest, phase)
                self.assertEqual((dest / 'ftesurf/gfx/changed.txt').read_bytes(), landed)
                if fault != 'receipt':
                    receipt = json.loads((phase / 'process.json').read_text())
                    self.assertEqual(receipt['status'], 'FAIL')  # negative assertion is not PASS
                    self.assertEqual(receipt['full_export'], fault != 'hash')
                    self.assertEqual(receipt['containment_confirmed'], fault != 'containment')
                if fault:
                    self.assertIn(phase, cold.UNCONFIRMED_PHASES)
                    with self.assertRaisesRegex(AssertionError, 'unconfirmed'):
                        live.retire_runtime(runtime, evidence, {'status': 'FAIL'}, dest)
                    self.assertTrue(dest.exists())
                else:
                    self.assertNotIn(phase, cold.UNCONFIRMED_PHASES)
                    self.assertEqual(json.loads((phase / 'state/runtime-files.sha256.json').read_text())['ftesurf/gfx/changed.txt'], cold.sha(landed))
                    native.TerminateJobObject.assert_not_called()  # don't manufacture a natural zero
                    self.assertEqual(receipt['job_active_before_cleanup'], 0)
                    self.assertEqual(receipt['job_active_after_cleanup'], 0)
                    result = {'status': 'FAIL', 'error': 'acted grader refusal'}
                    live.retire_runtime(runtime, evidence, result, dest)
                    self.assertTrue(result['runtime_retired'])
                    self.assertEqual(result['status'], 'FAIL')
                    self.assertEqual(json.loads((evidence / 'failed-final-state/runtime-files.sha256.json').read_text())['ftesurf/gfx/changed.txt'], cold.sha(landed))

    def test_both_legacy_live_callers_preserve_early_failure_and_export_or_containment_guards(self):
        for gate in (live, deferred):
            for fault in (None, 'hash', 'receipt', 'containment', 'handle'):
                with self.subTest(gate=gate.__name__, fault=fault), scratch() as root:
                    dest, phase = root / 'runtime', root / 'evidence'
                    fixture(dest)
                    process = MagicMock(pid=1234, _handle=5678)
                    process.poll.return_value = 90  # acts early exit before READY
                    native = MagicMock()
                    native.NtResumeProcess.return_value = 0
                    native.CloseHandle.return_value = 0 if fault == 'handle' else 1
                    def stopped(job, proc, receipt):
                        receipt['job_active_after_cleanup'] = 0
                        if fault == 'containment':
                            raise AssertionError('acted containment fault')
                    with ExitStack() as stack:
                        stack.enter_context(patch.object(gate.subprocess, 'Popen', return_value=process))
                        stack.enter_context(patch.object(gate, 'owned_job', return_value='mock-owned-job'))
                        stack.enter_context(patch.object(gate.ctypes, 'WinDLL', return_value=native, create=True))
                        stack.enter_context(patch.object(gate, 'kernel32', return_value=native))
                        stop = stack.enter_context(patch.object(gate, 'stop_win_job', side_effect=stopped))
                        if fault == 'hash':
                            stack.enter_context(patch.object(cold, 'sha', side_effect=OSError('acted hash fault')))
                        if fault == 'receipt':
                            stack.enter_context(patch.object(Path, 'write_text', write_fault('process.json')))
                        with self.assertRaises((AssertionError, OSError)):
                            if gate is live:
                                gate.live(Path('external-client'), dest, phase, 'initial-failure', False, {'url': 'http://127.0.0.1:1/update.json'})
                            else:
                                gate.live(Path('external-client'), Path('helper'), {'rva': 1, 'prologue_byte': 0x48},
                                          dest, phase, 'none', False, {'url': 'http://127.0.0.1:1/update.json'})
                    stop.assert_called_once()
                    guard = phase if gate is live else str(phase)
                    if fault == 'receipt':
                        self.assertFalse((phase / 'process.json').exists())
                    else:
                        receipt = json.loads((phase / 'process.json').read_text())
                        self.assertEqual(receipt['status'], 'FAIL')
                        self.assertEqual(receipt['full_export'], fault != 'hash')
                        self.assertEqual(receipt['containment_confirmed'], fault != 'containment')
                    self.assertEqual(guard in cold.UNCONFIRMED_PHASES, fault is not None)
                    if fault:
                        with self.assertRaisesRegex(AssertionError, 'unconfirmed'):
                            cold.ensure_retirable()
                    else:
                        self.assertEqual((phase / 'state/metadata/ingame/journal.tmp').read_bytes(), b'completed native temp')
                    self.assertTrue(dest.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
