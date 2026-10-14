#!/usr/bin/env python3
"""Process-free P693 driver falsifiers; NOT engine/product acceptance."""
import copy
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import test_p693_ui as ui

ARTIFACTS = ui.rig.ROOT.parent / 'artifacts'


class DriverTests(unittest.TestCase):
    def setUp(self):
        self.results = [dict(name=name, passed=name != 'integer focus precision') for name in ui.GROUPS]
        self.results[2]['error'] = 'full profile integer focus mismatch 16777217/16777216: selected #1500'
        self.witness = [dict(source='full', picked_ms=16777217, held_ms=16777216,
                             profile_json_ms=16777217, board_json_ms=16777216,
                             requested=1500, selected=1500, offset=1494)]

    def test_acted_collision_and_regressions(self):
        self.assertTrue(ui.precision_control_acted(self.results, self.witness))
        # Overflow validation is optional in the predecessor, never a substitute.
        self.results[1].update(passed=False, error='overflow accepted')
        self.assertTrue(ui.precision_control_acted(self.results, self.witness))

    def test_witness_mutants_refuse(self):
        for key in self.witness[0]:
            with self.subTest(key=key):
                mutant = copy.deepcopy(self.witness)
                mutant[0][key] = 'wrong' if isinstance(mutant[0][key], str) else mutant[0][key] + 1
                self.assertFalse(ui.precision_control_acted(self.results, mutant))
        self.assertFalse(ui.precision_control_acted(self.results, []))

    def test_unrelated_failures_and_missing_groups_refuse(self):
        for index in (0, 3, 4):
            mutant = copy.deepcopy(self.results)
            mutant[index]['passed'] = False
            self.assertFalse(ui.precision_control_acted(mutant, self.witness))
        for error in ('arm exceeded bounded runtime', 'target absent', 'integer focus status did not act'):
            mutant = copy.deepcopy(self.results)
            mutant[2]['error'] = error
            self.assertFalse(ui.precision_control_acted(mutant, self.witness))
        for mutant in (self.results[:-1], self.results + [self.results[0]], self.results[::-1]):
            self.assertFalse(ui.precision_control_acted(mutant, self.witness))
        mutant = copy.deepcopy(self.results)
        mutant[2]['passed'] = True
        self.assertFalse(ui.precision_control_acted(mutant, self.witness))

    def run_main(self, mode=(), failure=None, gate=None, hashes=None, effective=None):
        # Tool-managed bounded lifetime; no install/build copies or engine launch.
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='p693-driver-', dir=ARTIFACTS) as tmp:
            root = Path(tmp)
            (root / 'OWNER.md').write_text('Owned process-free driver fixture; remove on test exit.\n')
            output = root / 'out'
            arm = root / 'arm'
            arm.mkdir()
            (arm / 'precision-observations.json').write_text(json.dumps(self.witness))
            argv = ['test_p693_ui.py', '--output-dir', str(output), '--progs', str(root / 'progs'),
                    '--client', str(root / 'client.exe'), '--server', str(root / 'server.exe'), *mode]
            saved = ui.rig.Fixture, ui.rig.Runtime, ui.rig.overlay, ui.Runtime.baseline
            try:
                with patch.object(sys, 'argv', argv), patch.object(ui.rig, 'process_gate', side_effect=gate), \
                     patch.object(ui, 'input_hashes', side_effect=hashes or [dict(progs='exact'), dict(progs='exact')]), \
                     patch.object(ui.rig, 'arm', side_effect=failure,
                                  return_value=dict(rig=str(arm), results=self.results,
                                                    **(effective if effective is not None else dict(
                                                        requested_port=27588, port=27588,
                                                        runtime_budget_seconds=300)))) as launch:
                    code = ui.main()
                    self.last_launch_args = launch.call_args.args[0] if launch.called else None
                    report = json.loads((output / 'runtime-report.json').read_text())
                    return code, report, launch.call_count
            finally:
                ui.rig.Fixture, ui.rig.Runtime, ui.rig.overlay, ui.Runtime.baseline = saved

    def test_requested_port_and_budget_reach_arm_and_receipt(self):
        code, report, launches = self.run_main(('--baseline', '--port', '27520', '--budget', '37'),
            effective=dict(requested_port=27520, port=27520, runtime_budget_seconds=37))
        self.assertEqual((code, report['state'], launches), (0, 'evidence_only', 1))
        self.assertEqual((self.last_launch_args.port, self.last_launch_args.budget), (27520, 37))
        self.assertEqual((report['requested_port'], report['requested_budget_seconds'],
                          report['port'], report['runtime_budget_seconds']), (27520, 37, 27520, 37))

    def test_missing_or_changed_effective_launch_options_refuse_acceptance(self):
        good = dict(requested_port=27588, port=27588, runtime_budget_seconds=300)
        mutants = [{}]
        for key in good:
            changed = dict(good)
            changed[key] += 1
            mutants.append(changed)
            untyped = dict(good)
            untyped[key] = float(good[key])
            mutants.append(untyped)
        for effective in mutants:
            with self.subTest(effective=effective):
                code, report, _ = self.run_main(('--baseline',), effective=effective)
                self.assertEqual((code, report['state'], report['runtime_verified']), (1, 'failed', False))
                self.assertIn('effective launch port/budget', report['error'])

    def test_invalid_launch_options_refuse_before_output_or_gate(self):
        for flags in (('--port', '27698'), ('--port', '27519'), ('--port', '27621'),
                      ('--budget', '0'), ('--budget', '-1'), ('--budget', '301')):
            with self.subTest(flags=flags), \
                 tempfile.TemporaryDirectory(prefix='p693-driver-', dir=ARTIFACTS) as tmp:
                root = Path(tmp)
                (root / 'OWNER.md').write_text('Owned invalid-option fixture; no engines.\n')
                output = root / 'out'
                argv = ['test_p693_ui.py', '--output-dir', str(output), '--progs', str(root / 'progs'),
                        '--client', str(root / 'client.exe'), '--server', str(root / 'server.exe'), *flags]
                with patch.object(sys, 'argv', argv), patch.object(ui.rig, 'process_gate') as gate, \
                     patch.object(ui.rig, 'arm') as launch, self.assertRaises(SystemExit) as error:
                    ui.main()
                self.assertEqual(error.exception.code, 2)
                gate.assert_not_called()
                launch.assert_not_called()
                self.assertFalse(output.exists())

    def test_blocked_is_third_verdict_without_launch(self):
        code, report, launches = self.run_main(gate=ui.rig.Blocked('foreign engine fixture'))
        self.assertEqual((code, report['state'], launches), (2, 'blocked', 0))
        self.assertFalse(report['runtime_verified'])
        self.assertFalse(report['images_verified'])
        self.assertNotIn('inputs_sha256', report)

    def test_baseline_exit_zero_is_evidence_only(self):
        code, report, launches = self.run_main(('--baseline',))
        self.assertEqual((code, report['state'], launches), (0, 'evidence_only', 1))
        self.assertFalse(report['runtime_verified'])

    def test_precision_control_accepts_only_witness(self):
        code, report, _ = self.run_main(('--precision-control',))
        self.assertEqual((code, report['state']), (0, 'control_verified'))
        self.assertFalse(report['runtime_verified'])
        self.witness[0]['selected'] = 0
        code, report, _ = self.run_main(('--precision-control',))
        self.assertEqual((code, report['state']), (1, 'failed'))

    def test_subject_requires_five_groups_and_images_stay_unverified(self):
        code, report, _ = self.run_main()
        self.assertEqual((code, report['state']), (1, 'failed'))
        self.results[2]['passed'] = True
        run = self.precision_runtime(True)
        run.precision()
        self.witness = run.precision_observations
        code, report, _ = self.run_main()
        self.assertEqual((code, report['state']), (0, 'runtime_verified'))
        self.assertTrue(report['runtime_verified'])
        self.assertFalse(report['images_verified'])
        self.results.pop()
        code, report, _ = self.run_main()
        self.assertEqual((code, report['state']), (1, 'failed'))

    def test_subject_rejects_wrong_or_missing_exact_observations(self):
        self.results[2]['passed'] = True
        run = self.precision_runtime(True)
        run.precision()
        good = run.precision_observations
        mutants = [good[:-1], list(reversed(good))]
        for index, key, value in ((1, 'selected', 15000), (5, 'selected', 10),
                                  (0, 'profile_json_ms', 16777216), (4, 'board_json_ms', 16777217)):
            mutant = copy.deepcopy(good)
            mutant[index][key] = value
            mutants.append(mutant)
        for mutant in mutants:
            with self.subTest(mutant=mutant):
                self.witness = mutant
                code, report, _ = self.run_main()
                self.assertEqual((code, report['state'], report['runtime_verified']), (1, 'failed', False))

    def test_output_directory_alias_refuses_before_gate_or_target_write(self):
        self.output_alias('directory')

    def test_dangling_report_alias_refuses_before_gate_or_target_write(self):
        self.output_alias('report')

    def output_alias(self, kind):
        with tempfile.TemporaryDirectory(prefix='p693-driver-', dir=ARTIFACTS) as tmp:
            root = Path(tmp)
            (root / 'OWNER.md').write_text('Owned alias falsifier, no engines.\n')
            output, target = root / 'out', root / 'separate-target'
            try:
                if kind == 'directory':
                    target.mkdir()
                    output.symlink_to(target, target_is_directory=True)
                    forbidden = target / 'runtime-report.json'
                else:
                    output.mkdir()
                    (output / 'runtime-report.json').symlink_to(target)
                    forbidden = target
            except OSError as exc:
                self.skipTest('cannot create fixture symlink: ' + str(exc))
            argv = ['test_p693_ui.py', '--output-dir', str(output), '--progs', str(root / 'progs'),
                    '--client', str(root / 'client.exe'), '--server', str(root / 'server.exe')]
            with patch.object(sys, 'argv', argv), \
                 patch.object(ui.rig, 'process_gate', side_effect=ui.rig.Blocked('foreign fixture')) as gate, \
                 self.assertRaises(SystemExit) as error:
                ui.main()
            self.assertEqual(error.exception.code, 2)
            self.assertEqual(gate.call_count, 0)
            self.assertFalse(forbidden.exists())

    def test_native_input_inventory_includes_sibling_plugins_and_detects_change(self):
        with tempfile.TemporaryDirectory(prefix='p693-driver-', dir=ARTIFACTS) as tmp:
            root = Path(tmp)
            (root / 'OWNER.md').write_text('Owned plugin hash fixture, no engines.\n')
            progs = root / 'progs'
            progs.mkdir()
            for name in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
                (progs / name).write_bytes(name.encode())
            names = ('fteqw64.exe', 'fteqwsv64.exe', *(
                'fteplug_' + p + '_x64.dll' for p in ('hl2', 'cod', 'box3d', 'ode', 'ui_imgui')))
            for name in names:
                (root / name).write_bytes(name.encode())
            args = SimpleNamespace(progs=progs, client=root / 'fteqw64.exe', server=root / 'fteqwsv64.exe')
            before = ui.input_hashes(args)
            self.assertEqual(len(before), 10)
            (root / 'fteplug_hl2_x64.dll').write_bytes(b'changed sibling plugin')
            self.assertNotEqual(before, ui.input_hashes(args))

    def test_changed_inputs_and_arm_failure_refuse(self):
        code, report, _ = self.run_main(('--baseline',), hashes=[dict(progs='before'), dict(progs='after')])
        self.assertEqual((code, report['state']), (1, 'failed'))
        code, report, _ = self.run_main(failure=RuntimeError('socket spawn did not act'))
        self.assertEqual((code, report['state']), (1, 'failed'))
        code, report, _ = self.run_main(failure=ui.rig.Blocked('foreign process after dedicated launch'))
        self.assertEqual((code, report['state']), (2, 'blocked'))

    def precision_runtime(self, fresh_prints):
        run = ui.Runtime.__new__(ui.Runtime)
        run.fixture = ui.Fixture()
        run.precision_observations = []
        text = ['(16777217 ms)\n(2147483647 ms)\n']
        run.log = type('Log', (), {'text': lambda _: text[0]})()
        status = ['profile requested #0, selected #0']

        def send(command, delay=0):
            if command.startswith('hud_player view '):
                run.fixture.answer('/api/board?player=' + command.split()[-1])
            elif command.startswith('scores on '):
                run.fixture.answer('/api/board?player=' + command.split()[-1] + '&on=' + ui.rig.MAP)
            elif command.startswith('set ui_board_request '):
                status[0] = 'profile requested #1500, selected #1500'

        def click(target):
            if target == 'pf_map0':
                run.fixture.answer('/api/board?map=surf_result&offset=1494&limit=100')
                picked, held, rank = run.fixture.profile_ms, run.fixture.neighbors[1499]['ms'], 1500
            else:
                run.fixture.answer('/api/board?map=' + ui.rig.MAP + '&tier=ranked&style=clean&offset=0')
                picked, held, rank = run.fixture.on_ms, run.fixture.rows[0]['ms'], 1
            selected = rank if picked == held else 0
            status[0] = 'profile requested #%d, selected #%d' % (rank, selected)
            if fresh_prints and selected:
                text[0] += '(%d ms)\n' % picked

        run.send, run.click = send, click
        run.section = lambda *args: 'rows 1/1'
        run.focused_status = lambda: status[0]
        return run

    def test_positive_rank_prefix_mutants_refuse(self):
        for expected, wrong in ((1500, 15000), (1, 10)):
            with self.subTest(expected=expected):
                run = self.precision_runtime(True)
                original = run.focused_status
                run.focused_status = lambda: re.sub(r'selected #%d\b' % expected,
                                                     'selected #%d' % wrong, original())
                with self.assertRaisesRegex(AssertionError, 'focus mismatch'):
                    run.precision()

    def test_positive_exact_print_must_belong_to_current_case(self):
        run = self.precision_runtime(False)
        with self.assertRaisesRegex(AssertionError, 'integer handoff rounded its milliseconds'):
            run.precision()
        self.assertEqual(len(run.precision_observations), 2)

    def test_precision_witnesses_cover_all_full_and_compact_cases(self):
        run = self.precision_runtime(True)
        run.precision()
        self.assertEqual([(o['source'], o['picked_ms'], o['held_ms'], o['selected'])
                          for o in run.precision_observations], [
            ('full', 16777217, 16777216, 0), ('full', 16777217, 16777217, 1500),
            ('full', 2147483647, 2147483646, 0), ('full', 2147483647, 2147483647, 1500),
            ('compact', 16777217, 16777216, 0), ('compact', 16777217, 16777217, 1)])


if __name__ == '__main__':
    unittest.main(verbosity=2)
