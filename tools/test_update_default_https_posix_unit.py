#!/usr/bin/env python3
"""Client-free falsifiers for Linux default-HTTPS argv/trace/actor/containment."""
import argparse
import copy
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import test_update_default_https_posix as gate

WORK = None


class Graders(unittest.TestCase):
    def setUp(self):
        self.dest = WORK / 'install with spaces'
        self.engine = WORK / 'native/fteqw64'
        self.rows = [
            {'pid': 11, 'exit': 0, 'errors': [], 'execs': [{'image': str(self.engine), 'argv': [str(self.engine)]}]},
            {'pid': 12, 'exit': 0, 'errors': [], 'execs': [{'image': str(self.dest/'ftesurf-launcher'),
             'argv': [str(self.dest/'ftesurf-launcher'), '--dir', str(self.dest) + '/', '--wait-for-game', '--yes']}]},
            {'pid': 13, 'exit': 0, 'errors': [], 'execs': [{'image': str(self.dest/'ftesurf64'),
             'argv': [str(self.dest/'ftesurf64'), '-manifest', 'default.fmf']}]},
            {'pid': 14, 'exit': 0, 'errors': [], 'execs': []}]
        for row, children in zip(self.rows, [[12, 14], [13], [], []]):
            row['children'] = children

    def grade(self, rows):
        gate.grade_chain(rows, self.engine, self.dest, True)

    def test_full_chain(self):
        self.grade(self.rows)

    def test_extra_or_reordered_launcher_argv(self):
        for argv in [self.rows[1]['execs'][0]['argv'] + ['--offline'],
                     [str(self.dest/'ftesurf-launcher'), '--yes', '--dir', str(self.dest), '--wait-for-game']]:
            rows = copy.deepcopy(self.rows); rows[1]['execs'][0]['argv'] = argv
            with self.assertRaises(AssertionError): self.grade(rows)

    def test_extra_or_reordered_return_argv(self):
        for argv in [self.rows[2]['execs'][0]['argv'] + ['+quit'],
                     [str(self.dest/'ftesurf64'), 'default.fmf', '-manifest']]:
            rows = copy.deepcopy(self.rows); rows[2]['execs'][0]['argv'] = argv
            with self.assertRaises(AssertionError): self.grade(rows)

    def test_missing_unrelated_or_same_process_actor(self):
        for index, field, value in [(1, 'execs', []), (2, 'execs', []), (2, 'pid', 12)]:
            rows = copy.deepcopy(self.rows); rows[index][field] = value
            with self.assertRaises(AssertionError): self.grade(rows)
        rows = copy.deepcopy(self.rows); rows[2]['execs'][0]['image'] = str(WORK/'unrelated')
        with self.assertRaises(AssertionError): self.grade(rows)

    def test_missing_trace_and_unrelated_ancestry(self):
        with self.assertRaises(AssertionError): self.grade(self.rows[:-1])
        rows = copy.deepcopy(self.rows); rows[0]['children'] += [13]; rows[1]['children'] = []
        with self.assertRaises(AssertionError): self.grade(rows)
        rows = copy.deepcopy(self.rows); rows.append({'pid': 99, 'children': [], 'exit': 0, 'errors': [], 'execs': []})
        with self.assertRaises(AssertionError): self.grade(rows)

    def test_nonzero_missing_or_invalid_exit_all_tasks(self):
        for index in range(len(self.rows)):
            for field, value in [('exit', 1), ('exit', None), ('errors', ['signal exit'])]:
                rows = copy.deepcopy(self.rows); rows[index][field] = value
                with self.assertRaises(AssertionError): self.grade(rows)

    def test_trace_strict_exec_and_exit(self):
        good = 'execve("/owned/game", ["/owned/game", "-manifest", "default.fmf"], 0x1 /* 1 var */) = 0\n+++ exited with 0 +++\n'
        row = gate.parse_trace_text(good, 11)
        self.assertEqual(row['execs'][0]['argv'], ['/owned/game', '-manifest', 'default.fmf'])
        self.assertEqual(row['exit'], 0); self.assertFalse(row['errors'])
        for text in [good.replace(' = 0', ' = -1 EACCES (Permission denied)'), good.replace('"default.fmf"', '...'),
                     good.replace('execve(', 'execveat('), good.replace('+++ exited with 0 +++', '+++ killed by SIGKILL +++'),
                     good + '+++ exited with 0 +++\n']:
            with self.subTest(text=text): self.assertTrue(gate.parse_trace_text(text, 11)['errors'])
        self.assertIsNone(gate.parse_trace_text(good.split('+++')[0], 11)['exit'])

    def test_resumed_child_creation_and_missing_file(self):
        text = 'clone(child_stack=NULL, flags=SIGCHLD <unfinished ...>\n<... clone resumed>) = 21\n+++ exited with 0 +++\n'
        row = gate.parse_trace_text(text, 20)
        self.assertEqual(row['children'], [21]); self.assertFalse(row['errors'])
        self.assertTrue(gate.parse_trace_text(text.split('<...')[0], 20)['errors'])
        with tempfile.TemporaryDirectory(dir=WORK, prefix='missing-trace-') as scratch:
            prefix = Path(scratch)/'trace'
            (prefix.parent/'trace.20').write_text('execve(' + json.dumps(str(self.engine)) + ', [' + json.dumps(str(self.engine)) + '], 0x1 /* 1 var */) = 0\n' + text)
            child = prefix.parent/'trace.21'; child.write_text('+++ exited with 0 +++\n')
            gate.grade_chain(gate.read_trace(prefix), self.engine, self.dest, False)
            child.unlink()
            with self.assertRaises(AssertionError): gate.grade_chain(gate.read_trace(prefix), self.engine, self.dest, False)

    def test_command_echo_is_not_marker_output(self):
        stamp = '2026-10-13 15:00:00 '
        self.assertFalse(gate.has_actor(stamp + 'echo HTTPS_READYui_update_probe: x\n', 'HTTPS_READY'))
        self.assertFalse(gate.has_actor(stamp + 'HTTPS_READY_OLD\n', 'HTTPS_READY'))
        self.assertTrue(gate.has_actor(stamp + 'HTTPS_READY\n', 'HTTPS_READY'))

    def test_real_return_requires_updates_pane(self):
        good = '2026-10-13 15:00:00 HTTPS_REAL_RETURNING_GAME\nui_update_probe: consent=1 state=uptodate screen=7 client=1\nmanifest     : ' + gate.FEED
        gate.grade_return(good)
        for text in [good.replace('screen=7', 'screen=0'), good.replace('client=1', 'client=2'),
                     good.replace('state=uptodate', 'state=idle'), good.replace(' HTTPS_REAL_RETURNING_GAME', ' echo HTTPS_REAL_RETURNING_GAME'),
                     good.replace(gate.FEED, 'http://127.0.0.1/update.json')]:
            with self.assertRaises(AssertionError): gate.grade_return(text)

    @unittest.skipUnless(os.name == 'posix', 'real Linux static symlinks')
    def test_export_root_ancestor_and_sentinel_links_never_followed(self):
        with tempfile.TemporaryDirectory(dir=WORK, prefix='links-') as scratch:
            root = Path(scratch); dest = root/'runtime'; evidence = root/'evidence'; canary = root/'external'
            dest.mkdir(); evidence.mkdir(); canary.mkdir(); (canary/'harmless.txt').write_bytes(b'canary must never export')
            (dest/'ftesurf').mkdir(); (dest/'ftesurf/logs').symlink_to(canary, target_is_directory=True)
            with self.assertRaises(AssertionError): gate.export_runtime(dest, evidence)
            self.assertFalse(list(evidence.rglob('harmless.txt')))
            (dest/'ftesurf/logs').unlink(); (dest/'ftesurf').rmdir(); (dest/'ftesurf').symlink_to(canary, target_is_directory=True)
            with self.assertRaises(AssertionError): gate.export_runtime(dest, evidence)
            (dest/'ftesurf').unlink(); (dest/'ftesurf').mkdir(); sentinel = dest/'ftesurf/player.cfg'; sentinel.symlink_to(canary/'harmless.txt')
            with self.assertRaises(AssertionError): gate.export_sentinels(dest, evidence, {'ftesurf/player.cfg': b'original'})
            self.assertFalse((evidence/'sentinels/ftesurf/player.cfg').exists())
            receipt = gate.preserve_recovery(dest, evidence, {'ftesurf/player.cfg': b'original'})
            self.assertIn('ftesurf/player.cfg', receipt['unsafe_sources_not_followed'])
            self.assertNotIn('ftesurf/player.cfg', receipt['files'])

    @unittest.skipUnless(os.environ.get('FTESURF_TEST_TMPFS'), 'owned real tmpfs required')
    def test_export_or_retirement_failure_preserves_verified_recovery_and_fail(self):
        for seam in ['export_runtime', 'retire_runtime']:
            with self.subTest(seam=seam), tempfile.TemporaryDirectory(dir=os.environ['FTESURF_TEST_TMPFS'], prefix='recovery-') as scratch, tempfile.TemporaryDirectory(dir=WORK, prefix='evidence-') as persistent:
                dest = Path(scratch); evidence = Path(persistent)
                entries = {'ftesurf/cfg/test/test.cfg': b'cfg_save_auto 0\n', '.ftesurf-updater/state.json': b'{}',
                           'ftesurf/logs/test.log': b'owned actor evidence\n', 'ftesurf/player.cfg': b'player sentinel\n'}
                for name, data in entries.items():
                    p = dest/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
                protected = {'ftesurf/player.cfg': entries['ftesurf/player.cfg']}
                result = {'verdict': 'PASS', 'arms': []}
                with mock.patch.object(gate, seam, side_effect=OSError('acted injected ' + seam)), self.assertRaises(OSError):
                    gate.finalize_runtime(dest, evidence, result, protected, gate.namespace_members())
                persisted = json.loads((evidence/'result.json').read_text())
                self.assertEqual(persisted['verdict'], 'FAIL'); self.assertFalse(persisted['runtime_retired'])
                recovered = gate.verify_recovery(evidence)
                self.assertEqual(set(recovered['files']), set(entries))
                self.assertTrue(dest.exists(), 'source prematurely retired')
                gate.retire_runtime(dest, evidence)
                # After tmpfs source disappearance, persistent recovery still verifies.
                self.assertFalse(dest.exists()); gate.verify_recovery(evidence)

    @unittest.skipUnless(os.environ.get('FTESURF_OWNED_PID_NAMESPACE') == '1', 'owned private namespace required')
    def test_early_actor_or_wait_failure_preserves_all_terminal_exits(self):
        for failure in ['missing-actor', 'wait-timeout']:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory(dir=WORK, prefix='failed-game-') as scratch:
                root = Path(scratch); dest = root/'runtime'; evidence = root/'evidence'; dest.mkdir(); evidence.mkdir()
                ready = dest/'child-ready'
                code = 'import os,time,pathlib; p=os.fork();\nif p==0:\n pathlib.Path(' + repr(str(ready)) + ').write_text(str(os.getpid())); time.sleep(120)\nelse:\n time.sleep(120)\n'
                engine = Path(sys.executable).resolve()
                game = gate.OwnedGame([str(engine), '-c', code], engine, dest, evidence, 'failure')
                try:
                    import time
                    until = time.monotonic()+5
                    while not ready.exists():
                        self.assertLess(time.monotonic(), until); time.sleep(.01)
                    if failure == 'missing-actor':
                        with self.assertRaises(AssertionError): game.wait('HTTPS_WITHHELD', timeout=.05)
                    else:
                        with mock.patch.object(game.p, 'wait', side_effect=subprocess.TimeoutExpired('strace', .05)), self.assertRaises(subprocess.TimeoutExpired):
                            game.finish()
                finally:
                    game.close()
                receipt = json.loads((evidence/'failure-processes.json').read_text())
                self.assertEqual(receipt['status'], 'FAIL')
                self.assertGreaterEqual(len(receipt['group_before_containment']), 3)
                self.assertTrue(receipt['tasks_before_containment'])
                self.assertTrue(all(r['terminal'] is not None for r in receipt['tasks']), receipt)
                ids = {r['pid'] for r in receipt['tasks']}
                self.assertTrue({c for r in receipt['tasks'] for c in r['children']} <= ids)
                self.assertFalse(receipt['group_after_cleanup'])

    @unittest.skipUnless(os.name == 'posix', 'real Linux process groups')
    def test_reaped_leader_group_is_still_contained(self):
        self.assertEqual(ctypes.CDLL(None).prctl(36, 1, 0, 0, 0), 0)
        with tempfile.TemporaryDirectory(dir=WORK, prefix='group-') as scratch:
            ready = Path(scratch)/'ready'
            code = 'import os,time,pathlib; p=os.fork();\nif p==0:\n pathlib.Path(' + repr(str(ready)) + ').write_text(str(os.getpid())); time.sleep(120)\nelse:\n while not pathlib.Path(' + repr(str(ready)) + ').exists(): time.sleep(.01)\n'
            p = subprocess.Popen([sys.executable, '-c', code], start_new_session=True)
            try:
                self.assertEqual(p.wait(timeout=10), 0)
                self.assertTrue(gate.group_members(p.pid), 'surviving child never ACTED')
                gate.stop_owned_group(p)
                self.assertFalse(gate.group_members(p.pid))
            finally:
                gate.stop_owned_group(p)

    @unittest.skipUnless(os.name == 'posix', 'real Linux strace fork/exec observation')
    def test_trace_complete_fast_orphan_exec_chain(self):
        self.assertEqual(ctypes.CDLL(None).prctl(36, 1, 0, 0, 0), 0)
        with tempfile.TemporaryDirectory(dir=WORK, prefix='trace-') as scratch:
            prefix = Path(scratch)/'trace'
            code = 'import os,sys; p=os.fork();\nif p==0: os.execl(sys.executable,sys.executable,"-c","pass")\n'
            p = subprocess.Popen(['strace','-f','-ff','-q','-s','65535','-e','trace=process','-o',str(prefix),'--',sys.executable,'-c',code],
                                 start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                self.assertEqual(p.wait(timeout=10), 0)
                gate.stop_owned_group(p)
                rows = gate.read_trace(prefix)
                self.assertEqual(len(rows), 2, rows)
                self.assertEqual(sum(len(r['execs']) for r in rows), 2, rows)
                self.assertTrue(all(r['exit']==0 and not r['errors'] for r in rows), rows)
            finally:
                gate.stop_owned_group(p)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--work-root', type=Path, required=True)
    args, remaining = ap.parse_known_args()
    WORK = args.work_root.absolute(); assert not WORK.exists() and WORK.parent.is_dir()
    WORK.mkdir(); (WORK/'OWNER.md').write_text('Owned client-free Linux HTTPS grader tests; fixtures retired by RAII.\n')
    unittest.main(argv=[sys.argv[0]] + remaining)
