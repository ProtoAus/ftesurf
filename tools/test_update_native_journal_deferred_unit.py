#!/usr/bin/env python3
"""Client-free boundary/containment/export negatives for the deferred live gate.

Set FTESURF_TEST_SCRATCH to an existing owned task scratch directory. No default
TEMP runtime overlay and no native client/listener is started by these tests.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import test_update_native_journal_deferred as gate
import test_update_native_journal as cold
from test_update_native_journal_live import retire_runtime


@contextmanager
def scratch():
    root = Path(os.environ['FTESURF_TEST_SCRATCH']).resolve(strict=True)
    assert root.is_dir() and not root.is_symlink()
    with tempfile.TemporaryDirectory(prefix='deferred-units-', dir=root) as d:
        yield Path(d)


def executable(path, code=b'\x48\x83\xec\x28\xc3'):
    data = bytearray(0x200 + len(code))
    struct.pack_into('<I', data, 0x3c, 0x80)
    data[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HH', data, 0x84, 0x8664, 1)
    struct.pack_into('<H', data, 0x94, 0xf0)
    struct.pack_into('<H', data, 0x98, 0x20b)
    struct.pack_into('<Q', data, 0x98 + 24, 0x140000000)
    section = 0x98 + 0xf0
    data[section:section + 8] = b'.text\0\0\0'
    struct.pack_into('<IIII', data, section + 8, len(code), 0x1000, len(code), 0x200)
    data[0x200:] = code
    path.write_bytes(data)


class DeferredGateTests(unittest.TestCase):
    listing = '0000000140001000 t QKU_WriteJournal.constprop.0\n'
    disassembly = ('  140002000: e8 fb ef ff ff call   140001000 <QKU_WriteJournal.constprop.0>\n'
                   '  140002100: e8 fb ee ff ff call   140001000 <QKU_WriteJournal.constprop.0>\n')

    def bind(self, engine, symbols, listing=None, disassembly=None):
        with patch.object(gate.subprocess, 'check_output', side_effect=[
                self.listing if listing is None else listing,
                self.disassembly if disassembly is None else disassembly]):
            return gate.bind_writer(engine, symbols, Path('nm'), Path('objdump'))

    def test_exact_companion_writer_and_two_call_sites(self):
        with scratch() as root:
            engine, symbols = root / 'engine', root / 'symbols'
            executable(engine)
            executable(symbols)
            b = self.bind(engine, symbols)
            self.assertEqual(b['rva'], 0x1000)
            self.assertEqual(b['prologue_byte'], 0x48)
            self.assertEqual(b['caller_rvas'], [0x2005, 0x2105])
            self.assertEqual(b['engine_sha256'], b['symbols_sha256'])

    def test_companion_code_mismatch_refuses_before_debug_launch(self):
        with scratch() as root:
            engine, symbols = root / 'engine', root / 'symbols'
            executable(engine)
            executable(symbols, b'\x55\xc3')
            with self.assertRaisesRegex(AssertionError, 'companion text differs'):
                self.bind(engine, symbols)

    def test_missing_or_duplicate_writer_refuses(self):
        with scratch() as root:
            engine, symbols = root / 'engine', root / 'symbols'
            executable(engine)
            executable(symbols)
            for listing in ('', self.listing * 2):
                with self.subTest(listing=listing), self.assertRaisesRegex(AssertionError, 'unique optimized writer'):
                    self.bind(engine, symbols, listing=listing)

    def test_missing_or_extra_callsite_refuses(self):
        with scratch() as root:
            engine, symbols = root / 'engine', root / 'symbols'
            executable(engine)
            executable(symbols)
            for text in ('', self.disassembly * 2):
                with self.subTest(text=text), self.assertRaisesRegex(AssertionError, 'exact initial/deferred'):
                    self.bind(engine, symbols, disassembly=text)

    def test_already_patched_writer_refuses(self):
        with scratch() as root:
            engine, symbols = root / 'engine', root / 'symbols'
            executable(engine, b'\xcc\xc3')
            executable(symbols, b'\xcc\xc3')
            with self.assertRaises(AssertionError):
                self.bind(engine, symbols)

    def test_job_exit_delivery_race_requires_observed_empty(self):
        receipt = {}
        with patch.object(gate, 'job_count', side_effect=[1, 0]), patch.object(gate.time, 'sleep'):
            gate.wait_job_empty('owned-job', receipt, 'census')
        self.assertEqual(receipt, {'census': 0, 'census_observations': [1, 0]})

    def test_persistent_job_is_failure_not_killed_success(self):
        receipt = {}
        with patch.object(gate, 'job_count', return_value=1), patch.object(gate.time, 'monotonic', side_effect=[0, 11]):
            with self.assertRaisesRegex(AssertionError, 'did not quiesce'):
                gate.wait_job_empty('owned-job', receipt, 'census')
        self.assertEqual(receipt['census'], 1)

    def test_snapshot_preserves_tmp_authority_stage_and_nested_log(self):
        with scratch() as root:
            dest, out = root / 'runtime', root / 'evidence'
            meta = dest / '.ftesurf-updater/ingame'
            (meta / 'staged').mkdir(parents=True)
            (meta / 'journal.tmp').write_bytes(b'pending-only native sibling')
            (meta / 'journal.json').write_bytes(b'original full authority')
            (meta / 'staged/object').write_bytes(b'signed object fixture')
            log = dest / 'ftesurf/deferred.log'
            log.parent.mkdir(parents=True)
            log.write_bytes(b'early native log')
            gate.snapshot(dest, out)
            self.assertEqual((out / 'metadata/ingame/journal.tmp').read_bytes(), b'pending-only native sibling')
            self.assertEqual((out / 'metadata/ingame/journal.json').read_bytes(), b'original full authority')
            self.assertEqual((out / 'logs/ftesurf/deferred.log').read_bytes(), b'early native log')
            self.assertEqual(json.loads((out / 'staging.json').read_text()), {'object': gate.digest(b'signed object fixture')})

    def test_helper_directory_refuses_before_runtime_mutation(self):
        with scratch() as root:
            with self.assertRaisesRegex(AssertionError, 'regular unlinked debugger helper'):
                gate.helper_identity(root)
            self.assertEqual(list(root.iterdir()), [])

    def test_cold_cleanup_kills_even_reaped_leader_then_observes_empty(self):
        k = MagicMock()
        k.TerminateJobObject.return_value = 1
        process = MagicMock()
        process.poll.return_value = 0  # reaped leader says nothing about descendants
        receipt = {}
        with patch.object(cold.ctypes, 'WinDLL', return_value=k, create=True), \
             patch.object(cold, 'win_job_active', side_effect=[1, 0]), patch.object(cold.time, 'sleep'):
            cold.stop_win_job('owned-job', process, receipt)
        k.TerminateJobObject.assert_called_once_with('owned-job', 91)
        self.assertEqual(receipt['job_active_after_cleanup'], 0)
        self.assertEqual(receipt['job_active_after_cleanup_observations'], [1, 0])

    @unittest.skipUnless(os.name == 'nt', 'Windows cold runner cleanup branch')
    def test_cold_timeout_persistent_job_retains_guard_and_FAIL(self):
        with scratch() as root:
            dest, phase = root / 'runtime', root / 'cold-phase'
            (dest / 'ftesurf/data/runs').mkdir(parents=True)
            (dest / 'ftesurf/ftesurf.cfg').write_bytes(b'owned settings')
            (dest / 'ftesurf/data/runs/player-sentinel.rec').write_bytes(b'owned recording')
            process = MagicMock(pid=1234, _handle=5678)
            process.poll.return_value = 0
            process.wait.side_effect = gate.subprocess.TimeoutExpired('owned-client', 30)
            native = MagicMock()
            native.NtResumeProcess.return_value = 0
            native.TerminateJobObject.return_value = 1
            native.CloseHandle.return_value = 1
            try:
                with patch.object(cold.subprocess, 'Popen', return_value=process), \
                     patch('test_update_handoff.owned_job', return_value='unit-owned-job'), \
                     patch.object(cold.ctypes, 'WinDLL', return_value=native), \
                     patch.object(cold, 'win_job_active', return_value=1), \
                     patch.object(cold.time, 'monotonic', side_effect=[0, 11]):
                    with self.assertRaisesRegex(AssertionError, 'did not quiesce'):
                        cold.run_native(Path('external-client'), dest, phase)
                self.assertIn(phase, cold.UNCONFIRMED_PHASES)
                receipt = json.loads((phase / 'process.json').read_text())
                self.assertEqual(receipt['status'], 'FAIL')
                self.assertEqual(receipt['job_active_after_cleanup'], 1)
                self.assertIn('containment_error', receipt)
                with self.assertRaisesRegex(AssertionError, 'unconfirmed'):
                    cold.ensure_retirable()
            finally:
                cold.UNCONFIRMED_PHASES.discard(phase)

    def test_cold_failure_tmp_exported_exactly_before_retirement(self):
        with scratch() as root:
            runtime, evidence = root / 'runtime', root / 'evidence'
            dest = runtime / 'cold-failed-case'
            meta = dest / '.ftesurf-updater/ingame'
            meta.mkdir(parents=True)
            evidence.mkdir()
            (meta / 'journal.tmp').write_bytes(b'cold-phase failed rewrite exact bytes')
            result = {'status': 'FAIL', 'error': 'acted cold failure before normal snapshot'}
            retire_runtime(runtime, evidence, result, dest)
            exported = evidence / 'failed-final-state/metadata/ingame/journal.tmp'
            self.assertEqual(exported.read_bytes(), b'cold-phase failed rewrite exact bytes')
            self.assertEqual(result['status'], 'FAIL')
            self.assertTrue(result['runtime_retired'])
            self.assertFalse(runtime.exists())

    def test_live_early_exit_export_error_keeps_unconfirmed(self):
        with scratch() as root:
            dest, evidence = root / 'runtime', root / 'evidence'
            dest.mkdir()
            process = MagicMock(pid=1234, _handle=5678)
            process.poll.return_value = 0
            process.wait.return_value = 0
            native = MagicMock()
            native.NtResumeProcess.return_value = 0
            k = MagicMock()
            k.TerminateJobObject.return_value = 1
            k.CloseHandle.return_value = 1
            phase = str(evidence)
            try:
                with patch.object(gate.subprocess, 'Popen', return_value=process), \
                     patch.object(gate, 'owned_job', return_value='unit-owned-job'), \
                     patch.object(gate.ctypes, 'WinDLL', return_value=native, create=True), \
                     patch.object(gate, 'kernel32', return_value=k), \
                     patch.object(gate, 'job_count', return_value=0), \
                     patch.object(gate, 'snapshot', side_effect=OSError('acted live export fault')):
                    with self.assertRaisesRegex(OSError, 'acted live export fault'):
                        gate.live(Path('external-client'), Path('helper'), {'rva': 1, 'prologue_byte': 0x48},
                                  dest, evidence, 'none', False, {'url': 'http://127.0.0.1:1/update.json'})
                self.assertIn(phase, gate.UNCONFIRMED_PHASES)
                with self.assertRaisesRegex(AssertionError, 'unconfirmed'):
                    gate.ensure_retirable()
                self.assertTrue(dest.exists())
                self.assertFalse((evidence / 'process.json').exists())
                k.TerminateJobObject.assert_called_once_with('unit-owned-job', 91)
            finally:
                gate.UNCONFIRMED_PHASES.discard(phase)

    def test_export_error_keeps_unconfirmed_retirement_guard(self):
        phase = 'unit-only-export-failure'
        gate.UNCONFIRMED_PHASES.add(phase)
        try:
            with scratch() as root:
                meta = root / 'runtime/.ftesurf-updater'
                meta.mkdir(parents=True)
                (meta / 'journal.tmp').write_bytes(b'failed native sibling')
                with patch.object(gate.shutil, 'copyfile', side_effect=OSError('acted export fault')):
                    with self.assertRaisesRegex(OSError, 'acted export fault'):
                        gate.snapshot(root / 'runtime', root / 'evidence')
                with self.assertRaisesRegex(AssertionError, 'unconfirmed'):
                    gate.ensure_retirable()
                self.assertTrue((meta / 'journal.tmp').exists())
        finally:
            gate.UNCONFIRMED_PHASES.discard(phase)


if __name__ == '__main__':
    unittest.main(verbosity=2)
