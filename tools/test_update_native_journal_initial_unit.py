#!/usr/bin/env python3
"""Client-free initial publication binding, actor and lifecycle negatives.

FTESURF_TEST_SCRATCH must name an existing owned scratch directory.
"""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

import test_update_native_journal_initial as gate
from test_update_native_journal_deferred_unit import executable, scratch


class InitialTests(unittest.TestCase):
    def fixture(self, before=False):
        base = 0x140000000
        code = bytearray(0x1000)
        names = dict(QKU_Apply=0x1500)
        rows = []
        def function(name, rva):
            names[name] = rva
            rows.append(f'\n{base+rva:016x} <{name}>:')
        def raw(rva, data, assembly):
            code[rva-0x1000:rva-0x1000+len(data)] = data
            rows.append(f'  {base+rva:x}: ' + ' '.join(f'{b:02x}' for b in data) + ' ' + assembly)
        def call(rva, target, name):
            names[name] = target
            raw(rva, b'\xe8' + (target-rva-5).to_bytes(4, 'little', signed=True), f'call   {base+target:x} <{name}>')
        writer = 'QKU_WriteJournal.constprop.0'
        if before:
            function(writer, 0x1200)
            raw(0x1200, bytes.fromhex('55 57 56 53 48 81 ec 48 08 00 00'), 'push %rbp')
            call(0x1260, 0x1700, 'FS_Remove')
            call(0x1278, 0x1800, 'FS_Rename')
            raw(0x127d, b'\x90', 'nop')
        else:
            function('QKU_CommitJournal.part.0', 0x1000)
            raw(0x1000, bytes.fromhex('57 b8 30 18 00 00 56 53'), 'frame')
            call(0x1008, 0x1900, '___chkstk_ms')
            raw(0x100d, bytes.fromhex('48 29 c4'), 'sub %rax,%rsp')
            names['__imp_MoveFileExW'] = 0x5000
            raw(0x1040, bytes.fromhex('ff 15') + (0x5000-0x1046).to_bytes(4, 'little', signed=True), 'call   *0x0(%rip) # 140005000 <__imp_MoveFileExW>')
            raw(0x1046, b'\x85', 'test %eax,%eax')
            function('QKU_CommitJournal', 0x1100)
            raw(0x1130, bytes.fromhex('48 83 c4 28'), 'add    $0x28,%rsp')
            raw(0x1134, bytes.fromhex('e9 00 00 00 00'), 'jmp    140001000 <QKU_CommitJournal.part.0>')
            function(writer, 0x1200)
            raw(0x1200, bytes.fromhex('48 83 ec 28'), 'sub $0x28,%rsp')
            raw(0x1230, bytes.fromhex('48 83 c4 28'), 'add    $0x28,%rsp')
            raw(0x1234, bytes.fromhex('e9 00 00 00 00'), 'jmp    140001300 <QKU_WriteJournal.part.0.constprop.0>')
            function('QKU_WriteJournal.part.0.constprop.0', 0x1300)
            call(0x1360, 0x1100, 'QKU_CommitJournal')
        function('QKU_Apply', 0x1500)
        call(0x1520, 0x1200, writer)
        call(0x1560, 0x1200, writer)
        listing = ''.join(f'{base+rva:016x} {"I" if name.startswith("__imp_") else "t"} {name}\n' for name, rva in names.items())
        return code, listing, '\n'.join(rows) + '\n'

    def bind(self, before=False, code=None, listing=None, assembly=None):
        initial, names, disassembly = self.fixture(before)
        return gate.bind_code(0x140000000, 0x1000, initial if code is None else code,
            names if listing is None else listing, disassembly if assembly is None else assembly, before)

    def test_exact_old_and_subject_initial_native_sites(self):
        subject, old = self.bind(), self.bind(True)
        self.assertEqual((subject['entry_rva'], subject['pre_rva'], subject['post_rva'], subject['commit_caller_rva']), (0x1200, 0x1040, 0x1046, 0x1365))
        self.assertEqual((old['pre_rva'], old['post_rva'], old['abi']), (0x1278, 0x127d, 'fs'))
        self.assertEqual(subject['initial_caller_rva'], 0x1525)
        self.assertEqual(subject['deferred_caller_rva'], 0x1565)

    def test_companion_mismatch_precedes_tools_or_launch(self):
        with scratch() as root:
            engine, symbols = root / 'engine', root / 'symbols'
            executable(engine)
            executable(symbols, b'wrong code')
            with patch.object(gate.subprocess, 'check_output') as tool, self.assertRaisesRegex(AssertionError, 'companion'):
                gate.bind_initial(engine, symbols, Path('nm'), Path('objdump'))
            tool.assert_not_called()

    def test_missing_duplicate_symbols_refuse(self):
        unused, names, unused = self.fixture()
        for value in ('', names*2, names.replace('QKU_Apply', 'QKU_Other')):
            with self.subTest(value=value), self.assertRaises(AssertionError):
                self.bind(listing=value)

    def test_initial_direct_call_bytes_target_must_match(self):
        code, unused, unused = self.fixture()
        code[0x521] ^= 1
        with self.assertRaises(AssertionError):
            self.bind(code=code)
        unused, unused, assembly = self.fixture()
        with self.assertRaises(AssertionError):
            self.bind(assembly=assembly.replace('140001520: e8', '140001521: e8'))

    def test_missing_extra_or_non_apply_writer_call_refuses(self):
        unused, unused, assembly = self.fixture()
        first = next(line for line in assembly.splitlines() if '140001520:' in line)
        for variant in (assembly.replace(first, ''), assembly + first + '\n', assembly.replace('<QKU_Apply>:', '<QKU_Other>:')):
            with self.subTest(variant=variant), self.assertRaises(AssertionError):
                self.bind(assembly=variant)

    def test_wrong_commit_allocation_and_return_byte_refuse(self):
        for offset in (2, 15, 0x46):
            code, unused, unused = self.fixture()
            code[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(AssertionError):
                self.bind(code=code)

    def test_non_tail_writer_or_commit_wrapper_refuses(self):
        unused, unused, assembly = self.fixture()
        for target in ('140001000', '140001300'):
            with self.subTest(target=target), self.assertRaises(AssertionError):
                self.bind(assembly=assembly.replace('jmp    ' + target, 'call   ' + target))

    def test_import_and_stack_probe_actual_targets_required(self):
        code, names, assembly = self.fixture()
        for name in ('___chkstk_ms', '__imp_MoveFileExW'):
            old = next(line for line in names.splitlines() if line.endswith(' ' + name))
            wrong = f'{int(old.split()[0],16)+1:016x}' + old[16:]
            with self.subTest(name=name), self.assertRaises(AssertionError):
                self.bind(code=code, listing=names.replace(old,wrong), assembly=assembly)

    def test_missing_native_import_or_old_unlink_refuses(self):
        unused, unused, assembly = self.fixture()
        with self.assertRaises(AssertionError):
            self.bind(assembly=assembly.replace('__imp_MoveFileExW', '__imp_CopyFileW'))
        unused, unused, assembly = self.fixture(True)
        with self.assertRaises(AssertionError):
            self.bind(True, assembly=assembly.replace('FS_Remove', 'FS_Other'))

    def events(self, mode):
        result = [dict(event='child', pid=1234), dict(event='writer', ordinal=1, rva=0x1200, thread=8, caller_rva=0x1525),
                  dict(event='before', rva=0x1040, thread=8, paths_verified=True, authority_absent=True)]
        if mode == 'source-lock':
            result.append(dict(event='source-lock', rename_error=32, write_allowed=True))
        if mode != 'crash-before':
            result.append(dict(event='after', rva=0x1046, thread=8, native_result=0 if mode == 'source-lock' else 1))
        hits = 2 if mode == 'crash-before' else 3
        if mode.startswith('crash-'):
            result.append(dict(event='interrupt', code=86, hits=hits))
        result.append(dict(event='exit', pid=1234, code=86 if mode.startswith('crash-') else 0, hits=hits))
        return result

    def test_unlocked_fault_and_both_interruption_actors(self):
        for mode in ('none', 'source-lock', 'crash-before', 'crash-after'):
            self.assertEqual(gate.grade_events(self.events(mode), self.bind(), mode), (1234, 86 if mode.startswith('crash-') else 0))

    def test_deferred_ordinal_wrong_thread_path_caller_exit_refuse(self):
        for index, field, value in ((1,'ordinal',2),(1,'caller_rva',0x1565),(1,'rva',77), (1,'thread',0),
                (2,'rva',77),(2,'paths_verified',False),(2,'authority_absent',False),(3,'thread',9),
                (3,'native_result',0),(4,'code',90),(5,'pid',999),(5,'code',0),(5,'hits',2)):
            events = self.events('crash-after')
            events[index][field] = value
            with self.subTest(index=index, field=field), self.assertRaises(AssertionError):
                gate.grade_events(events, self.bind(), 'crash-after')

    def test_fault_requires_real_zero_return_and_probe32(self):
        for index, field, value in ((3,'rename_error',5),(3,'write_allowed',False),(4,'native_result',1)):
            events = self.events('source-lock')
            events[index][field] = value
            with self.subTest(field=field), self.assertRaises(AssertionError):
                gate.grade_events(events, self.bind(), 'source-lock')

    def test_missing_reordered_duplicate_unknown_events_refuse(self):
        original = self.events('crash-after')
        variants = [original[:i] + original[i+1:] for i in range(len(original))]
        variants += [original + [dict(event='unknown')], original + [original[-1]]]
        swapped = copy.deepcopy(original)
        swapped[1], swapped[2] = swapped[2], swapped[1]
        variants.append(swapped)
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(AssertionError):
                gate.grade_events(variant, self.bind(), 'crash-after')

    def test_overlapping_or_existing_roots_refuse_without_mutation(self):
        with scratch() as root:
            run = root / 'run'
            for runtime, evidence in ((run,run),(run,run/'evidence'),(run/'nested',run),(root,run)):
                with self.subTest(runtime=runtime), self.assertRaises(AssertionError):
                    gate.preflight_paths(runtime,evidence)
                self.assertEqual(list(root.iterdir()), [])

    def test_final_full_snapshot_failure_retains_guard(self):
        with scratch() as root:
            target=root/'final'
            guard=target/'full-snapshot-guard'
            try:
                with patch.object(gate,'snapshot',side_effect=OSError('acted final export failure')):
                    with self.assertRaises(OSError):
                        gate.full_snapshot(root/'runtime',target)
                self.assertIn(guard,gate.UNCONFIRMED_PHASES)
                with self.assertRaisesRegex(AssertionError,'unconfirmed'):
                    gate.ensure_retirable()
            finally:
                gate.UNCONFIRMED_PHASES.discard(guard)

    def cold_failure(self, hash_export_error=False, containment_error=False, receipt_error=False):
        with scratch() as root:
            runtime, evidence = root/'runtime', root/'evidence'
            dest, phase = runtime/'cold', evidence/'cold'
            target = dest/'ftesurf/gfx/managed.txt'
            target.parent.mkdir(parents=True)
            target.write_bytes(b'old managed destination')
            meta = dest/'.ftesurf-updater/ingame'
            (meta/'staged').mkdir(parents=True)
            (meta/'journal.tmp').write_bytes(b'complete retained sibling')
            def failed_runner(*args, **kwargs):
                phase.mkdir(parents=True)
                target.write_bytes(b'new post-mutation evidence')
                if containment_error:
                    gate.UNCONFIRMED_PHASES.add(phase)
                raise AssertionError('acted cold grading failure')
            original_write = Path.write_text
            def write(path, *args, **kwargs):
                if (hash_export_error and path.name == 'runtime-files.sha256.json') or (receipt_error and path.name == 'full-export.json'):
                    raise OSError('acted cold full-export denial')
                return original_write(path,*args,**kwargs)
            guard = phase/'full-export-guard'
            try:
                with patch.object(gate,'run_native',side_effect=failed_runner), patch.object(Path,'write_text',autospec=True,side_effect=write):
                    with self.assertRaises(OSError if hash_export_error or receipt_error else AssertionError):
                        gate.cold_phase(Path('client'),dest,phase)
                if hash_export_error or containment_error or receipt_error:
                    self.assertIn(guard,gate.UNCONFIRMED_PHASES)
                    with self.assertRaisesRegex(AssertionError,'unconfirmed'):
                        gate.retire_runtime(runtime,evidence,dict(status='FAIL'),dest)
                    self.assertTrue(target.exists())
                    self.assertEqual(target.read_bytes(),b'new post-mutation evidence')
                    self.assertFalse(json.loads((evidence/'result.json').read_text())['runtime_retired'])
                else:
                    gate.ensure_retirable()
                    hashes=json.loads((phase/'state/runtime-files.sha256.json').read_text())
                    self.assertEqual(hashes['ftesurf/gfx/managed.txt'],gate.sha(b'new post-mutation evidence'))
                    self.assertEqual((phase/'state/metadata/ingame/journal.tmp').read_bytes(),b'complete retained sibling')
                if not receipt_error:
                    receipt=json.loads((phase/'full-export.json').read_text())
                    self.assertEqual(receipt['status'],'FAIL')
                    self.assertEqual(receipt['guard_retained'],hash_export_error or containment_error)
            finally:
                gate.UNCONFIRMED_PHASES.discard(guard)
                gate.UNCONFIRMED_PHASES.discard(phase)

    def test_cold_grading_failure_exports_post_mutation_full_state(self):
        self.cold_failure()

    def test_cold_runtime_hash_export_failure_blocks_fallback_retirement(self):
        self.cold_failure(hash_export_error=True)

    def test_cold_containment_failure_keeps_independent_export_guard(self):
        self.cold_failure(containment_error=True)

    def test_cold_export_receipt_failure_cannot_release_guard(self):
        self.cold_failure(receipt_error=True)

    def failure(self, export_error=False, containment_error=False):
        with scratch() as root:
            dest, phase = root / 'runtime', root / 'phase'
            meta = dest / '.ftesurf-updater/ingame'
            meta.mkdir(parents=True)
            (meta / 'journal.tmp').write_bytes(b'exact failed native full sibling')
            native = MagicMock()
            native.NtResumeProcess.return_value = 0
            native.CloseHandle.return_value = 1
            process = MagicMock(pid=1234, _handle=5678)
            process.poll.return_value = 90
            process.wait.return_value = 90
            try:
                with patch.object(gate.subprocess,'Popen',return_value=process), \
                     patch.object(gate,'owned_job',return_value='unit-job'), \
                     patch.object(gate.ctypes,'WinDLL',return_value=native,create=True), \
                     patch.object(gate,'stop_win_job',side_effect=AssertionError('acted containment failure') if containment_error else None) as stop, \
                     patch.object(gate.shutil,'copyfile',side_effect=OSError('acted export failure') if export_error else shutil_copy):
                    with self.assertRaises(OSError if export_error else AssertionError):
                        gate.live(Path('client'),Path('helper'),self.bind(),dest,phase,'crash-before',dict(url='http://127.0.0.1:1/update.json'),lambda kind: None)
                stop.assert_called_once()
                self.assertEqual(json.loads((phase/'process.json').read_text())['status'],'FAIL')
                if export_error or containment_error:
                    self.assertIn(phase,gate.UNCONFIRMED_PHASES)
                    with self.assertRaisesRegex(AssertionError,'unconfirmed'):
                        gate.ensure_retirable()
                else:
                    self.assertNotIn(phase,gate.UNCONFIRMED_PHASES)
                    self.assertEqual((phase/'state/metadata/ingame/journal.tmp').read_bytes(),b'exact failed native full sibling')
                self.assertTrue(dest.exists())
            finally:
                gate.UNCONFIRMED_PHASES.discard(phase)

    def test_early_exit_exports_exact_temp_FAIL_and_job_cleanup(self):
        self.failure()

    def test_export_failure_retains_guard(self):
        self.failure(export_error=True)

    def test_containment_failure_retains_guard(self):
        self.failure(containment_error=True)


shutil_copy = gate.shutil.copyfile
if __name__ == '__main__':
    unittest.main(verbosity=2)
