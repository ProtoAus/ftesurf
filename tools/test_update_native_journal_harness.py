#!/usr/bin/env python3
"""Client-free negative tests for journal harness evidence/containment/retirement.

All real processes below are owned Python sleepers, never games or installed
clients. Pass an owned root; temporary fixtures are created only beneath it.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import test_update_native_journal as cold
import test_update_native_journal_live as live

WORK = None


class JournalHarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=WORK)
        self.root = Path(self.temp.name)
        self.assertFalse(cold.UNCONFIRMED_PHASES)

    def tearDown(self):
        self.assertFalse(cold.UNCONFIRMED_PHASES)
        self.temp.cleanup()

    @unittest.skipUnless(os.name == 'posix', 'owned POSIX group falsifier')
    def test_reaped_leader_surviving_member_is_terminated(self):
        # Both remain in this test driver's session; the second owned direct child
        # joins the first's unique group. A waiter reaps it as cleanup kills it.
        leader = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                                  preexec_fn=lambda: os.setpgid(0, 0))
        member = None
        waiter = None
        try:
            member = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                                      preexec_fn=lambda: os.setpgid(0, leader.pid))
            leader.terminate()
            leader.wait(timeout=10)
            self.assertIsNotNone(leader.poll())
            self.assertTrue(cold.group_active(leader.pid), 'surviving group control did not ACT')
            waiter = threading.Thread(target=member.wait, daemon=True)
            waiter.start()
            cold.stop_posix_group(leader)
            waiter.join(timeout=10)
            self.assertFalse(waiter.is_alive())
            self.assertEqual(member.returncode, -signal.SIGKILL)
            self.assertFalse(cold.group_active(leader.pid))
        finally:
            try:
                os.killpg(leader.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            leader.wait(timeout=10)
            if member is not None:
                member.wait(timeout=10)
            if waiter:
                waiter.join(timeout=10)

    @unittest.skipUnless(os.name == 'posix', 'POSIX cleanup timeout contract')
    def test_group_that_remains_cannot_be_confirmed(self):
        class Reaped:
            pid = 424242  # synthetic; all signal calls mocked, never sent to this PID
            def poll(self):
                return 0
        with patch.object(cold, 'group_active', return_value=True), patch.object(os, 'killpg') as send:
            with self.assertRaisesRegex(AssertionError, 'owned group remains'):
                cold.stop_posix_group(Reaped(), timeout=0)
            send.assert_called_once_with(424242, signal.SIGKILL)

    def make_fake_launch(self, name):
        dest = self.root / 'dest'
        dest.mkdir()
        for path in ['ftesurf/ftesurf.cfg', 'ftesurf/data/runs/player-sentinel.rec']:
            p = dest / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b'owned synthetic sentinel\n')
        gamelog = dest / 'ftesurf/logs' / ('journal-' + name + '.log')
        gamelog.parent.mkdir(parents=True)
        gamelog.write_bytes(b'native diagnostics before early wait failure\n')
        phase = self.root / 'evidence' / name
        return dest, phase, gamelog

    @unittest.skipUnless(os.name == 'posix', 'mocked POSIX cold-launch branch')
    def test_early_wait_failure_exports_native_log_and_contains(self):
        dest, phase, gamelog = self.make_fake_launch('early')
        class FailedWait:
            pid = 424242
            def wait(self, timeout):
                raise subprocess.TimeoutExpired('client-free fake', timeout)
            def poll(self):
                return 0
        with patch.object(subprocess, 'Popen', return_value=FailedWait()), \
             patch.object(cold, 'stop_posix_group') as stop:
            with self.assertRaises(subprocess.TimeoutExpired):
                cold.run_native(Path(sys.executable), dest, phase)
            stop.assert_called_once()
        self.assertEqual((phase / ('game-' + gamelog.name)).read_bytes(), gamelog.read_bytes())
        receipt = json.loads((phase / 'process.json').read_text())
        self.assertEqual(receipt['status'], 'FAIL')
        self.assertFalse(receipt['group_active_after_cleanup'])
        cold.ensure_retirable()

    @unittest.skipUnless(os.name == 'posix', 'mocked POSIX evidence-failure branch')
    def test_failed_log_export_prevents_retirement_even_if_contained(self):
        dest, phase, gamelog = self.make_fake_launch('unexported')
        class FailedWait:
            pid = 424242
            def wait(self, timeout):
                raise subprocess.TimeoutExpired('client-free fake', timeout)
            def poll(self):
                return 0
        try:
            with patch.object(subprocess, 'Popen', return_value=FailedWait()), \
                 patch.object(cold, 'stop_posix_group') as stop, \
                 patch.object(cold.shutil, 'copyfile', side_effect=OSError('owned export denial')):
                with self.assertRaisesRegex(OSError, 'owned export denial'):
                    cold.run_native(Path(sys.executable), dest, phase)
                stop.assert_called_once()
            with self.assertRaisesRegex(AssertionError, 'unconfirmed'):
                cold.ensure_retirable()
            self.assertTrue(gamelog.exists(), 'unexported native evidence lost')
            receipt = json.loads((phase / 'process.json').read_text())
            self.assertEqual(receipt['status'], 'FAIL')
            self.assertIn('export_error', receipt)
        finally:
            # This unit used no real client; synthetic phase can be retired by unittest.
            cold.UNCONFIRMED_PHASES.discard(phase)

    def retirement_fixture(self):
        root, evidence = self.root / 'runtime', self.root / 'evidence'
        root.mkdir()
        evidence.mkdir()
        return root, evidence

    def test_retirement_failure_downgrades_pass_receipt(self):
        root, evidence = self.retirement_fixture()
        result = dict(status='PASS')
        with patch.object(live.shutil, 'rmtree', side_effect=PermissionError('owned retirement denial')):
            with self.assertRaisesRegex(PermissionError, 'owned retirement denial'):
                live.retire_runtime(root, evidence, result)
        receipt = json.loads((evidence / 'result.json').read_text())
        self.assertEqual(receipt['status'], 'FAIL')
        self.assertFalse(receipt['runtime_retired'])
        self.assertIn('retirement_error', receipt)
        self.assertTrue(root.exists())

    def test_failed_state_export_never_deletes_runtime(self):
        root, evidence = self.retirement_fixture()
        dest = root / 'failed-case'
        dest.mkdir()
        (dest / 'native.log').write_bytes(b'owned native failure log\n')
        result = dict(status='FAIL')
        with patch.object(live.shutil, 'copyfile', side_effect=OSError('failed-state export denial')), \
             patch.object(live.shutil, 'rmtree') as remove:
            with self.assertRaisesRegex(OSError, 'failed-state export denial'):
                live.retire_runtime(root, evidence, result, dest)
            remove.assert_not_called()
        self.assertTrue((dest / 'native.log').exists())
        self.assertEqual(json.loads((evidence / 'result.json').read_text())['status'], 'FAIL')

    def test_unconfirmed_native_phase_prevents_runtime_deletion(self):
        root, evidence = self.retirement_fixture()
        phase = self.root / 'synthetic-unconfirmed-phase'
        cold.UNCONFIRMED_PHASES.add(phase)
        try:
            with self.assertRaisesRegex(AssertionError, 'unconfirmed'):
                live.retire_runtime(root, evidence, dict(status='PASS'))
            self.assertTrue(root.exists())
            receipt = json.loads((evidence / 'result.json').read_text())
            self.assertEqual(receipt['status'], 'FAIL')
            self.assertFalse(receipt['runtime_retired'])
        finally:
            cold.UNCONFIRMED_PHASES.discard(phase)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work-root', type=Path, required=True)
    args, remainder = ap.parse_known_args()
    WORK = args.work_root.absolute()
    assert not WORK.exists(), 'fresh owned root required'
    WORK.mkdir(parents=True)
    (WORK / 'OWNER.md').write_text('Client-free journal harness negative tests, owned Python groups/synthetic failures only.\n')
    unittest.main(argv=[sys.argv[0]] + remainder)
