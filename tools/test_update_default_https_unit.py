#!/usr/bin/env python3
"""Offline adversarial graders for Windows default HTTPS acceptance; no processes."""
import argparse
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest

from test_update_default_https import FEED, OwnedGame, grade_exits, grade_handoff, grade_return

ROOT = None


@unittest.skipUnless(os.name == 'nt', 'Windows command-line parser')
class Grades(unittest.TestCase):
    def rows(self):
        dest = Path('C:/owned synthetic install')
        rows = [
            {'pid': 1, 'image': 'C:/external/real-engine.exe', 'argv': 'real-engine.exe', 'exit': 0},
            {'pid': 2, 'image': str(dest / 'ftesurf-launcher.exe'), 'argv': f'"{dest}/ftesurf-launcher.exe" --dir "{dest}/." --wait-for-game --yes', 'exit': 0},
            {'pid': 3, 'image': str(dest / 'ftesurf64.exe'), 'argv': f'"{dest}/ftesurf64.exe" -manifest default.fmf', 'exit': 0},
            {'pid': 4, 'image': str(Path(os.environ['SystemRoot']) / 'System32/conhost.exe'), 'argv': 'conhost.exe 0x4', 'exit': 109},
        ]
        return dest, rows

    def test_real_fixed_vector(self):
        dest, rows = self.rows()
        grade_handoff(rows, dest, 1)
        grade_exits(rows)
        self.assertIn('ERROR_BROKEN_PIPE', rows[3]['classification'])

    def test_real_extended_drive_prefix(self):
        dest, rows = self.rows()
        rows[2]['argv'] = '"' + '\\\\?\\' + str(dest / 'ftesurf64.exe') + '" -manifest default.fmf'
        grade_handoff(rows, dest, 1)

    def test_extra_launcher_flag(self):
        dest, rows = self.rows(); rows[1]['argv'] += ' --offline'
        with self.assertRaises(AssertionError): grade_handoff(rows, dest, 1)

    def test_injected_return_command(self):
        dest, rows = self.rows(); rows[1]['argv'] += ' -- +exec injected.cfg'
        with self.assertRaises(AssertionError): grade_handoff(rows, dest, 1)

    def test_wrong_order(self):
        dest, rows = self.rows(); rows[1]['argv'] = rows[1]['argv'].replace('--wait-for-game --yes', '--yes --wait-for-game')
        with self.assertRaises(AssertionError): grade_handoff(rows, dest, 1)

    def test_return_game_extra_argv(self):
        dest, rows = self.rows(); rows[2]['argv'] += ' +exec injected.cfg'
        with self.assertRaises(AssertionError): grade_handoff(rows, dest, 1)

    def test_other_process_not_accepted(self):
        dest, rows = self.rows(); rows.append({'pid': 5, 'image': 'C:/outside/actor.exe', 'argv': 'actor.exe', 'exit': 0})
        with self.assertRaises(AssertionError): grade_handoff(rows, dest, 1)

    # P823: no Updates screen (7); a returning game is graded on the title menu.
    def test_old_updates_screen_rejected(self):
        with self.assertRaises(AssertionError):
            grade_return('ui_update_probe: consent=1 state=uptodate screen=7 client=1\nmanifest     : ' + FEED)

    def test_title_menu_accepted(self):
        grade_return('ui_update_probe: consent=1 state=uptodate screen=0 client=1\nmanifest     : ' + FEED)

    def test_product_nonzero_rejected(self):
        _, rows = self.rows(); rows[2]['exit'] = 109
        with self.assertRaises(AssertionError): grade_exits(rows)

    def test_other_conhost_exit_rejected(self):
        _, rows = self.rows(); rows[3]['exit'] = 123
        with self.assertRaises(AssertionError): grade_exits(rows)

    def test_failed_exit_preserves_complete_census(self):
        self.failed_census(0)

    def test_failed_initiator_preserves_complete_census(self):
        self.failed_census(3)

    def failed_census(self, initial_exit):
        dest, rows = self.rows()
        rows[0]['exit'] = initial_exit
        rows[2]['exit'] = 0 if initial_exit else 3
        game = OwnedGame.__new__(OwnedGame)
        game.dest, game.evidence, game.name = dest, ROOT, 'unit-failed-exit-' + str(initial_exit)
        game.rows = {r['pid']: dict(r) for r in rows}
        codes = {r['pid']: r['exit'] for r in rows}
        for row in game.rows.values(): row.pop('exit')
        game.handles = {pid: pid for pid in game.rows}
        def exit_code(handle, pointer):
            pointer._obj.value = codes[handle]
            return True
        game.k = SimpleNamespace(GetExitCodeProcess=exit_code)
        game.p = SimpleNamespace(wait=lambda timeout: None, returncode=initial_exit, pid=1)
        game.pids = lambda: []
        game.stop = SimpleNamespace(set=lambda: None)
        game.thread = SimpleNamespace(join=lambda timeout: None, is_alive=lambda: False)
        game.errors = []
        with self.assertRaises(AssertionError): game.finish(restart=True)
        saved = json.loads((ROOT / (game.name + '-processes.json')).read_text())
        self.assertEqual({r['pid']: r['exit'] for r in saved}, codes)
        self.assertEqual(json.loads((ROOT / (game.name + '-precleanup.json')).read_text())['active_before_cleanup'], 0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    args, rest = parser.parse_known_args()
    ROOT = args.work_root.absolute()
    assert not ROOT.exists() and ROOT.parent.is_dir(), 'fresh owned unit evidence root required'
    ROOT.mkdir()
    (ROOT / 'OWNER.md').write_text('Offline acceptance grader falsifiers; no process/network/player data. Retained census evidence.\n')
    unittest.main(argv=[__file__, *rest])
