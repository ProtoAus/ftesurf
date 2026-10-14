#!/usr/bin/env python3
"""Client-free source-binding, native-actor and failure-lifecycle controls.

Set FTESURF_TEST_SCRATCH to an existing owned scratch directory.
"""
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import MagicMock, patch

import test_update_native_journal_interrupt as gate
from test_update_native_journal_deferred_unit import scratch, executable


class InterruptTests(unittest.TestCase):
    def fixture(self, before=False):
        code = bytearray(0x600)
        listing = ('0000000140001200 T QKU_ReplayJournal\n'
                   '0000000140001000 t QKU_CommitJournal.part.0\n')
        code[:8] = bytes.fromhex('57 b8 30 18 00 00 56 53')
        code[8:16] = bytes.fromhex('e8 00 00 00 00 48 29 c4')
        if before:
            code[0x260:0x266] = bytes.fromhex('e8 00 00 00 00 89')
            disassembly = ('0000000140001200 <QKU_ReplayJournal>:\n'
                '  140001248: e8 00 00 00 00 call   140005000 <FS_Remove>\n'
                '  140001260: e8 00 00 00 00 call   140006000 <FS_Rename>\n')
        else:
            code[0x40:0x47] = bytes.fromhex('ff 15 00 00 00 00 85')
            disassembly = ('0000000140001000 <QKU_CommitJournal.part.0>:\n'
                '  14000100d: 48 29 c4 sub    %rax,%rsp\n'
                '  140001040: ff 15 00 00 00 00 call   *0x0(%rip) # 140005000 <__imp_MoveFileExW>\n'
                '\n0000000140001100 <QKU_CommitJournal>:\n'
                '  140001130: 48 83 c4 28 add    $0x28,%rsp\n'
                '  140001134: e9 00 00 00 00 jmp    140001000 <QKU_CommitJournal.part.0>\n'
                '\n0000000140001200 <QKU_ReplayJournal>:\n'
                '  140001260: e8 00 00 00 00 call   140001100 <QKU_CommitJournal>\n')
        return code, listing, disassembly

    def bind(self, before=False, code=None, listing=None, disassembly=None):
        initial, names, assembly = self.fixture(before)
        return gate.bind_code(0x140000000, 0x1000, initial if code is None else code,
            names if listing is None else listing, assembly if disassembly is None else disassembly, before)

    def test_exact_old_and_subject_call_return_boundaries(self):
        subject, old = self.bind(), self.bind(True)
        self.assertEqual((subject['pre_rva'], subject['post_rva'], subject['cold_caller_rva']), (0x1040, 0x1046, 0x1265))
        self.assertEqual((old['pre_rva'], old['post_rva'], old['abi']), (0x1260, 0x1265, 'fs'))

    def test_companion_mismatch_refuses_without_tool_or_client(self):
        with scratch() as root:
            engine, symbols = root / 'engine', root / 'symbols'
            executable(engine)
            executable(symbols, b'wrong code')
            with patch.object(gate.subprocess, 'check_output') as tool, self.assertRaisesRegex(AssertionError, 'companion text differs'):
                gate.bind_commit(engine, symbols, Path('nm'), Path('objdump'), False)
            tool.assert_not_called()

    def test_missing_duplicate_or_wrong_symbol_refuses(self):
        unused, names, unused = self.fixture()
        for text in ('', names * 2, names.replace('QKU_CommitJournal.part.0', 'QKU_Other')):
            with self.subTest(text=text), self.assertRaises(AssertionError):
                self.bind(listing=text)

    def test_disjoint_fresh_paths_accept_without_creating_anything(self):
        with scratch() as root:
            runtime, evidence = root / 'runtime', root / 'evidence'
            self.assertEqual(gate.preflight_paths(runtime, evidence), (runtime, evidence))
            self.assertEqual(list(root.iterdir()), [])

    def test_equal_or_nested_roots_refuse_before_mutation(self):
        with scratch() as root:
            runtime = root / 'runtime'
            for evidence, run in ((runtime, runtime), (runtime / 'evidence', runtime),
                                  (runtime, runtime / 'child'), (runtime / '..' / 'runtime', runtime)):
                with self.subTest(evidence=evidence, runtime=run), self.assertRaisesRegex(AssertionError, 'disjoint'):
                    gate.preflight_paths(run, evidence)
                self.assertEqual(list(root.iterdir()), [])

    def test_existing_root_refuses_before_mutation(self):
        with scratch() as root:
            with self.assertRaisesRegex(AssertionError, 'fresh'):
                gate.preflight_paths(root, root.parent / (root.name + '-evidence'))
            self.assertEqual(list(root.iterdir()), [])

    def test_runtime_hashes_retain_protection_and_content_actor(self):
        with scratch() as root:
            dest = root / 'runtime'
            files = {'ftesurf/ftesurf.cfg': b'owned settings',
                     'ftesurf/data/runs/player-sentinel.rec': b'owned recording',
                     'ftesurf/gfx/crosshairs/xhair1.png': b'landed content',
                     'ftesurf/data/zones/local/owned.json': b'edited local zone'}
            for path, data in files.items():
                p = dest / path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)
            target = root / 'evidence'
            gate.snapshot(dest, target)
            self.assertEqual(json.loads((target / 'runtime-files.sha256.json').read_text()),
                             {path: gate.sha(data) for path, data in files.items()})

    def test_wrong_stack_prologue_refuses(self):
        code, unused, unused = self.fixture()
        code[2] ^= 1
        with self.assertRaisesRegex(AssertionError, 'stack frame'):
            self.bind(code=code)

    def test_wrong_frame_allocation_refuses(self):
        code, unused, unused = self.fixture()
        code[15] ^= 1
        with self.assertRaisesRegex(AssertionError, 'frame allocation'):
            self.bind(code=code)

    def test_non_tail_wrapper_refuses(self):
        unused, unused, assembly = self.fixture()
        with self.assertRaisesRegex(AssertionError, 'tail wrapper'):
            self.bind(disassembly=assembly.replace('jmp    140001000', 'call   140001000'))

    def test_missing_real_replace_import_refuses(self):
        unused, unused, assembly = self.fixture()
        with self.assertRaisesRegex(AssertionError, 'real replace'):
            self.bind(disassembly=assembly.replace('__imp_MoveFileExW', '__imp_CopyFileW'))

    def test_disassembly_native_bytes_mismatch_refuses(self):
        code, unused, unused = self.fixture()
        code[0x42] ^= 1
        with self.assertRaisesRegex(AssertionError, 'call mismatch'):
            self.bind(code=code)

    def test_trapped_return_instruction_refuses(self):
        code, unused, unused = self.fixture()
        code[0x46] = 0xcc
        with self.assertRaisesRegex(AssertionError, 'return instruction'):
            self.bind(code=code)

    def test_old_missing_preceding_unlink_refuses(self):
        unused, unused, assembly = self.fixture(True)
        with self.assertRaisesRegex(AssertionError, 'preceding unlink'):
            self.bind(True, disassembly=assembly.replace('FS_Remove', 'FS_Other'))

    def events(self, mode='crash-after'):
        result = [dict(event='child', pid=1234),
                  dict(event='before', rva=0x1040, thread=8, paths_verified=True)]
        if mode != 'crash-before':
            result.append(dict(event='after', rva=0x1046, thread=8, native_result=1))
        hits = len(result)-1
        if mode != 'none':
            result.append(dict(event='interrupt', code=86, hits=hits))
        result.append(dict(event='exit', pid=1234, code=1 if mode == 'none' else 86, hits=hits))
        return result

    def test_raw_crash_before_after_and_unlocked_actors(self):
        for mode in ('none', 'crash-before', 'crash-after'):
            self.assertEqual(gate.grade_events(self.events(mode), self.bind(), mode), (1234, 1 if mode == 'none' else 86))

    def test_unacted_or_wrong_call_return_thread_path_exit_refuses(self):
        for field, value, index in [('rva', 77, 1), ('paths_verified', False, 1),
                ('rva', 77, 2), ('thread', 9, 2), ('native_result', 0, 2),
                ('code', 90, 3), ('pid', 999, 4), ('code', 0, 4), ('hits', 1, 4)]:
            events = self.events()
            events[index][field] = value
            with self.subTest(field=field, index=index), self.assertRaises(AssertionError):
                gate.grade_events(events, self.bind(), 'crash-after')
        for index in (0, 1, 2, 3, 4):
            events = self.events()
            del events[index]
            with self.subTest(missing=index), self.assertRaises(AssertionError):
                gate.grade_events(events, self.bind(), 'crash-after')

    def test_unknown_or_reordered_events_refuse(self):
        events = self.events()
        events.insert(3, dict(event='uninspected'))
        with self.assertRaisesRegex(AssertionError, 'event order'):
            gate.grade_events(events, self.bind(), 'crash-after')
        events = self.events()
        events[1], events[2] = events[2], events[1]
        with self.assertRaisesRegex(AssertionError, 'event order'):
            gate.grade_events(events, self.bind(), 'crash-after')

    def failure(self, export_error=False, containment_error=False):
        with scratch() as root:
            dest, phase = root / 'runtime', root / 'phase'
            meta = dest / '.ftesurf-updater/ingame'
            (meta / 'staged').mkdir(parents=True)
            (meta / 'journal.tmp').write_bytes(b'native pending sibling at interruption')
            native = MagicMock()
            native.NtResumeProcess.return_value = 0
            native.CloseHandle.return_value = 1
            process = MagicMock(pid=1234, _handle=5678)
            process.poll.return_value = 90
            process.wait.side_effect = subprocess.TimeoutExpired('owned-helper', 30)
            try:
                with patch.object(gate.subprocess, 'Popen', return_value=process), \
                     patch.object(gate, 'owned_job', return_value='unit-job'), \
                     patch.object(gate.ctypes, 'WinDLL', return_value=native, create=True), \
                     patch.object(gate, 'stop_win_job', side_effect=AssertionError('acted containment failure') if containment_error else None) as stop, \
                     patch.object(gate.shutil, 'copyfile', side_effect=OSError('acted export failure') if export_error else shutil_copy):
                    expected = OSError if export_error else AssertionError if containment_error else subprocess.TimeoutExpired
                    with self.assertRaises(expected):
                        gate.interrupt(Path('external-client'), Path('helper'), self.bind(), dest, phase, 'crash-before')
                self.assertEqual(json.loads((phase / 'process.json').read_text())['status'], 'FAIL')
                stop.assert_called_once()
                if export_error or containment_error:
                    self.assertIn(phase, gate.UNCONFIRMED_PHASES)
                    with self.assertRaisesRegex(AssertionError, 'unconfirmed'):
                        gate.ensure_retirable()
                else:
                    self.assertNotIn(phase, gate.UNCONFIRMED_PHASES)
                    self.assertEqual((phase / 'state/metadata/ingame/journal.tmp').read_bytes(), b'native pending sibling at interruption')
                self.assertTrue(dest.exists())
            finally:
                gate.UNCONFIRMED_PHASES.discard(phase)

    def test_helper_timeout_exports_exact_temp_and_FAIL(self):
        self.failure()

    def test_export_error_retains_guard_and_runtime(self):
        self.failure(export_error=True)

    def test_containment_error_retains_guard_and_FAIL(self):
        self.failure(containment_error=True)


shutil_copy = gate.shutil.copyfile
if __name__ == '__main__':
    unittest.main(verbosity=2)
