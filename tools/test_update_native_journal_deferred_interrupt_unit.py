#!/usr/bin/env python3
"""Client-free deferred interruption actors and actual live export/guard faults."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

import test_update_native_journal_deferred_interrupt as gate
import test_update_native_journal_initial_unit as initial_units
from test_update_native_journal_deferred_unit import scratch


class DeferredInterruptTests(unittest.TestCase):
    def binding(self, before=False):
        return initial_units.InitialTests().bind(before) | dict(before=before)

    def events(self, mode='crash-after', before=False):
        b = self.binding(before)
        events = [dict(event='child', pid=1234),
                  dict(event='writer', ordinal=1, rva=b['entry_rva'], thread=8, caller_rva=b['initial_caller_rva']),
                  dict(event='writer', ordinal=2, rva=b['entry_rva'], thread=8, caller_rva=b['deferred_caller_rva']),
                  dict(event='before', rva=b['pre_rva'], thread=8, paths_verified=True, authority_absent=before)]
        if mode != 'crash-before':
            events.append(dict(event='after', rva=b['post_rva'], thread=8, native_result=1))
        hits = 2 if mode == 'crash-before' else 3
        if mode != 'none':
            events.append(dict(event='interrupt', code=86, hits=hits))
        events.append(dict(event='exit', pid=1234, calls=2, hits=hits, code=0 if mode == 'none' else 86))
        return events

    def test_old_and_subject_all_native_boundaries_act(self):
        for before in (False, True):
            for mode in ('none', 'crash-before', 'crash-after'):
                with self.subTest(before=before, mode=mode):
                    self.assertEqual(gate.grade_events(self.events(mode, before), self.binding(before), mode),
                                     (1234, 0 if mode == 'none' else 86))

    def test_each_ordinal_caller_thread_path_rva_authority_result_and_exit_discriminates(self):
        mutations = ((0,'pid',0),(1,'ordinal',2),(2,'ordinal',1),
            (1,'caller_rva',0x1565),(2,'caller_rva',0x1525),
            (1,'rva',99),(2,'rva',99),(1,'thread',0),(2,'thread',9),
            (3,'thread',9),(3,'rva',99),(3,'paths_verified',False),(3,'authority_absent',True),
            (4,'thread',9),(4,'rva',99),(4,'native_result',0),(4,'native_result',-1),
            (5,'code',90),(5,'hits',2),(6,'pid',999),(6,'calls',1),(6,'hits',2),(6,'code',0))
        for index, key, value in mutations:
            events = self.events()
            events[index][key] = value
            with self.subTest(index=index, key=key), self.assertRaises(AssertionError):
                gate.grade_events(events, self.binding(), 'crash-after')

    def test_old_boundary_must_observe_unlinked_authority(self):
        events = self.events(before=True)
        events[3]['authority_absent'] = False
        with self.assertRaises(AssertionError):
            gate.grade_events(events, self.binding(True), 'crash-after')

    def test_every_missing_reordered_duplicate_unknown_actor_refuses(self):
        original = self.events()
        variants = [original[:i]+original[i+1:] for i in range(len(original))]
        variants += [original+[dict(event='unknown')], original+[original[-1]]]
        swapped = copy.deepcopy(original)
        swapped[1], swapped[2] = swapped[2], swapped[1]
        variants.append(swapped)
        for events in variants:
            with self.subTest(events=events), self.assertRaises(AssertionError):
                gate.grade_events(events, self.binding(), 'crash-after')

    def test_initial_only_receipt_cannot_grade_deferred(self):
        events = initial_units.InitialTests().events('crash-after')
        with self.assertRaises(AssertionError):
            gate.grade_events(events, self.binding(), 'crash-after')

    def test_cold_request_cannot_hide_behind_accepted_live_counter(self):
        expected = {'/update.json': 1, '/objects/fixture': 1}
        for request in ('/update.json', '/objects/fixture', '/unexpected'):
            with self.subTest(request=request):
                hits = gate.Counter(expected)
                self.assertEqual(gate.grade_http(hits, expected), expected)
                # Acting cold phase: the same server counter advances after live admission.
                hits[request] += 1
                with self.assertRaisesRegex(AssertionError, 'unexpected HTTP request'):
                    gate.grade_http(hits, expected)

    def test_unknown_mode_refuses(self):
        with self.assertRaises(AssertionError):
            gate.grade_events(self.events(), self.binding(), 'source-lock')

    def failure(self, fault=None):
        with scratch() as root:
            runtime, evidence = root/'runtime', root/'evidence'
            dest, phase = runtime/'case', evidence/'live'
            meta = dest/'.ftesurf-updater/ingame'
            (meta/'staged').mkdir(parents=True)
            (meta/'journal.json').write_bytes(b'exact retained full authority')
            (meta/'journal.tmp').write_bytes(b'exact pending native sibling')
            (meta/'staged/object').write_bytes(b'owned staged content')
            target = dest/'ftesurf/gfx/landed.txt'
            target.parent.mkdir(parents=True)
            target.write_bytes(b'post-mutation landed content')
            native = MagicMock()
            native.NtResumeProcess.return_value = 0
            native.CloseHandle.return_value = 0 if fault == 'handle' else 1
            process = MagicMock(pid=1234, _handle=5678)
            process.poll.return_value = 90
            process.wait.return_value = 90
            original_write = Path.write_text
            def write(path, *args, **kwargs):
                if (fault == 'hash' and path.name == 'runtime-files.sha256.json') or (fault == 'receipt' and path.name == 'process.json'):
                    raise OSError('acted receipt/hash denial')
                return original_write(path, *args, **kwargs)
            before_guards = set(gate.UNCONFIRMED_PHASES)
            try:
                with patch.object(gate.subprocess, 'Popen', return_value=process), \
                     patch.object(gate, 'owned_job', return_value='unit-job'), \
                     patch.object(gate.ctypes, 'WinDLL', return_value=native, create=True), \
                     patch.object(gate, 'kernel32', return_value=native), \
                     patch.object(gate, 'stop_win_job', side_effect=AssertionError('acted containment denial') if fault == 'containment' else None) as stop, \
                     patch.object(Path, 'write_text', autospec=True, side_effect=write):
                    with self.assertRaises(OSError if fault in ('hash','receipt') else AssertionError):
                        gate.live(Path('client'), Path('helper'), self.binding(), dest, phase, 'crash-before',
                                  dict(url='http://127.0.0.1:1/update.json', pending='ftesurf/gfx/pending.txt'))
                stop.assert_called_once()
                if fault:
                    self.assertIn(phase, gate.UNCONFIRMED_PHASES)
                    with self.assertRaisesRegex(AssertionError, 'unconfirmed'):
                        gate.retire_runtime(runtime, evidence, dict(status='FAIL'), dest)
                    self.assertTrue(target.exists())
                    self.assertFalse(json.loads((evidence/'result.json').read_text())['runtime_retired'])
                else:
                    self.assertNotIn(phase, gate.UNCONFIRMED_PHASES)
                if fault != 'receipt':
                    receipt = json.loads((phase/'process.json').read_text())
                    self.assertEqual(receipt['status'], 'FAIL')
                    self.assertEqual(receipt['helper_exit'], 90)
                    self.assertEqual(receipt['full_export'], fault != 'hash')
                if fault != 'hash':
                    hashes = json.loads((phase/'state/runtime-files.sha256.json').read_text())
                    self.assertEqual(hashes['ftesurf/gfx/landed.txt'], gate.sha(b'post-mutation landed content'))
                    self.assertEqual((phase/'state/metadata/ingame/journal.tmp').read_bytes(), b'exact pending native sibling')
                    self.assertEqual((phase/'state/metadata/ingame/journal.json').read_bytes(), b'exact retained full authority')
            finally:
                # Unit created no native handles/process. Only its own acted guards retire.
                gate.UNCONFIRMED_PHASES.intersection_update(before_guards)

    def test_early_exit_keeps_FAIL_and_exports_current_landed_content(self):
        self.failure()

    def test_hash_export_denial_blocks_retirement(self):
        self.failure('hash')

    def test_containment_denial_blocks_retirement_even_with_full_export(self):
        self.failure('containment')

    def test_handle_failure_keeps_guard(self):
        self.failure('handle')

    def test_process_receipt_denial_keeps_guard(self):
        self.failure('receipt')


if __name__ == '__main__':
    unittest.main(verbosity=2)
