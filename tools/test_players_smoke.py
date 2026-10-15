#!/usr/bin/env python3
"""Non-native lifecycle and fail-closed Players grader controls; owned output only."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

import players_smoke as P

OUTPUT = None


def sample_log():
    text = 'sui_event down mwheeldown took 1\nsui_event up mwheeldown took 1\n'
    for phase, rows, visible, drawn, generation, who in (
        ('inert', 1, '0..0', 1, 1, ''),
        ('top', 64, '0..10', 11, 2, ''),
        ('bottom', 64, '53..63', 11, 5, ''),
        ('search', 64, '53..63', 11, 10, ''),
        ('profile', 64, '53..63', 11, 10, P.WHO),
        ('back', 64, '53..63', 11, 11, ''),
    ):
        text += ('PLAYERS PHASE %s\nscores: pinned on surf_dune\n  tab players   filter all\n'
                 'PLAYERS FIXTURE mode 1 visible %s drawn %d gen %d\n'
                 '  players rows %d scroll %s wheel 0 profile %s\n'
                 % (phase, visible, drawn, generation, rows,
                    '0.0' if phase in ('inert', 'top') else '5.0', who))
        if phase == 'search':
            text += 'profile: search "Fixture" found 1\n'
        if phase == 'profile':
            text += 'sui_hover [pf_h0]\nprofile: '+P.WHO+' on surf_dune: 0 times\n'
    return text


class PlayersControls(unittest.TestCase):
    def folder(self):
        path = OUTPUT / self._testMethodName
        path.mkdir()
        return path

    def test_timeout_retains_cleanup_owner_and_reports_blocked(self):
        root = self.folder()
        # Wrapper's setup exceeds the outer deadline. Its later child and finally
        # must still act; killing the wrapper would prevent both completion files.
        script = root / 'delayed.py'
        script.write_text('import pathlib,subprocess,sys,time\n'
            'root=pathlib.Path(__file__).parent\n'
            'try:\n'
            ' time.sleep(.25)\n'
            ' code="import pathlib,time; time.sleep(.15); pathlib.Path(\\"child-done\\").write_text(\\"done\\")"\n'
            ' child=subprocess.Popen([sys.executable,"-c",code],cwd=root)\n'
            ' child.wait(timeout=5)\n'
            ' if child.returncode: raise RuntimeError("child failed")\n'
            'finally:\n'
            ' (root/"cleanup-done").write_text("done")\n')
        children = []
        try:
            with self.assertRaises(subprocess.TimeoutExpired):
                P.wait_owned([sys.executable, '-B', str(script)], children, timeout=.01,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.assertEqual(len(children), 1)
            self.assertIsNone(children[0].poll())
            with patch.object(P, 'desktop_idle', return_value=True):
                state = P.record_lifecycle(root, P.ACTIVE_STATUS, children)
            self.assertFalse(state['verified'])
            self.assertEqual(state['active_wrapper_pids'], [children[0].pid])
            self.assertIn('BLOCKED / cleanup-unverified', (root / 'OWNER.md').read_text())
        finally:
            # Exact test-owned wrapper, normal wait only; never kill by process name.
            for process in children:
                process.wait(timeout=10)
        self.assertEqual(children[0].returncode, 0)
        self.assertTrue((root / 'child-done').is_file())
        self.assertTrue((root / 'cleanup-done').is_file())
        self.assertIn('BLOCKED / cleanup-unverified', (root / 'OWNER.md').read_text())

    def test_cleanup_failure_cannot_claim_none(self):
        root = self.folder()
        script = root / 'cleanup_failure.py'
        script.write_text('import pathlib,subprocess,sys\n'
            'root=pathlib.Path(__file__).parent\n'
            'child=subprocess.Popen([sys.executable,"-c","pass"])\n'
            'child.wait(timeout=5)\n'
            '(root/"child-exited").write_text(str(child.returncode))\n'
            'raise RuntimeError("synthetic cleanup failure")\n')
        children = []
        with self.assertRaises(subprocess.CalledProcessError):
            P.wait_owned([sys.executable, '-B', str(script)], children, timeout=10,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.assertEqual((root / 'child-exited').read_text(), '0')
        with patch.object(P, 'desktop_idle', return_value=True):
            state = P.record_lifecycle(root, P.ACTIVE_STATUS, children)
        self.assertFalse(state['verified'])
        self.assertIn('BLOCKED / cleanup-unverified', (root / 'OWNER.md').read_text())

    def test_timeout_never_signals_wrapper(self):
        process = Mock()
        process.wait.side_effect = subprocess.TimeoutExpired(['synthetic'], 1)
        children = []
        with patch.object(P.subprocess, 'Popen', return_value=process):
            with self.assertRaises(subprocess.TimeoutExpired):
                P.wait_owned(['synthetic'], children, timeout=1)
        process.kill.assert_not_called()
        process.terminate.assert_not_called()
        self.assertEqual(children, [process])

    def test_success_requires_no_native_and_no_junctions(self):
        root = self.folder()
        process = Mock(pid=1)
        process.poll.return_value = 0
        with patch.object(P, 'desktop_idle', return_value=True):
            state = P.record_lifecycle(root, P.ACTIVE_STATUS, [process])
        self.assertTrue(state['verified'])
        self.assertIn('verified', (root / 'OWNER.md').read_text())
        with patch.object(P, 'desktop_idle', return_value=False):
            self.assertFalse(P.record_lifecycle(root, P.ACTIVE_STATUS, [process])['verified'])
        with patch.object(P, 'desktop_idle', return_value=True), \
             patch.object(P, 'retained_junctions', return_value=['owned-retained-link']):
            self.assertFalse(P.record_lifecycle(root, P.ACTIVE_STATUS, [process])['verified'])

    def test_positive_grade(self):
        self.assertTrue(all(P.grade_log(sample_log()).values()))

    def test_stale_draw_after_back_rejected(self):
        text = sample_log().replace('drawn 11 gen 11', 'drawn 11 gen 10')
        checks = P.grade_log(text)
        for key in ('Back restored pinned Players', 'Back advances roster draw generation', 'Back preserved scroll'):
            self.assertFalse(checks[key])

    def test_wrong_tab_after_back_rejected(self):
        first, back = sample_log().split('PLAYERS PHASE back')
        checks = P.grade_log(first+'PLAYERS PHASE back'+back.replace('tab players ', 'tab local '))
        self.assertFalse(checks['Back restored pinned Players'])
        self.assertFalse(checks['Back preserved scroll'])

    def test_unpinned_back_rejected(self):
        first, back = sample_log().split('PLAYERS PHASE back')
        checks = P.grade_log(first+'PLAYERS PHASE back'+back.replace('scores: pinned ', 'scores: hidden '))
        self.assertFalse(checks['Back restored pinned Players'])

    def test_zero_row_inert_control_rejected(self):
        text = sample_log().replace('players rows 1 scroll', 'players rows 0 scroll')
        self.assertFalse(P.grade_log(text)['inert renders exactly one real row'])

    def test_missing_generation_rejected(self):
        text = sample_log().replace(' gen 11', '')
        self.assertFalse(P.grade_log(text)['Back advances roster draw generation'])

    def test_fixture_not_shipped(self):
        for name in ('cl_progs.src', 'sv_progs.src', 'm_progs.src'):
            text = (P.ROOT / 'src' / name).read_text()
            self.assertNotIn('players_roster.qc', text)
            self.assertNotIn('PlayersFixture_', text)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', type=Path, required=True)
    args = ap.parse_args()
    OUTPUT = args.output_dir.resolve()
    if OUTPUT.exists() or not any((p / 'OWNER.md').is_file() for p in OUTPUT.parents):
        raise SystemExit('Use a NEW output directory beneath an OWNER-marked task root')
    OUTPUT.mkdir()
    (OUTPUT / 'OWNER.md').write_text('# Players non-native controls\n'
        'Owner: P722 continuation; UTC '+datetime.now(timezone.utc).isoformat()+'\n'
        'Owned paths: this output root; exact Python wrapper/child handles only.\n'
        'Status: active; no native games, app imports or network. Retain evidence.\n')
    result = unittest.main(argv=[sys.argv[0]], exit=False).result
    status = ('Status: complete; test-owned wrappers/children waited to exit;'
              if result.wasSuccessful() else 'Status: FAILED / cleanup-unverified; inspect per-case evidence;')
    (OUTPUT / 'OWNER.md').write_text((OUTPUT / 'OWNER.md').read_text().replace('Status: active;', status))
    raise SystemExit(0 if result.wasSuccessful() else 1)
