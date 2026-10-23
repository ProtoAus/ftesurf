#!/usr/bin/env python3
"""Pure cfg-transport regression; no native processes, overlays or player data."""
import unittest

from runlines_smoke import dedicated_cfg


class DedicatedCfg(unittest.TestCase):
    def test_map_command_not_cvar_suffix_or_comment(self):
        text = ('cfg_save_auto 0\nset fs_eventfog_map surf_666\n'
                '// map surf_666\nmap surf_666\nmap surf_other\n')
        result = dedicated_cfg(text, 'surf_666', 27618)
        self.assertEqual(result, text.replace('\nmap surf_666\n', '\nconnect 127.0.0.1:27618\n'))
        self.assertIn('set fs_eventfog_map surf_666\n', result)

    def test_only_cvar_or_comment_is_not_a_map_control(self):
        for text in ('set fs_eventfog_map surf_666\n', '// map surf_666\n'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                dedicated_cfg(text, 'surf_666', 27618)

    def test_quotes_whitespace_comment_and_last_line(self):
        self.assertEqual(dedicated_cfg('  map "surf_666" // target\n', 'surf_666', 27618),
                         '  connect 127.0.0.1:27618 // target\n')
        self.assertEqual(dedicated_cfg('map surf_666', 'surf_666', 27618),
                         'connect 127.0.0.1:27618')

    def test_repeat_commands_rewrite_without_prefix_matches(self):
        text = 'map surf_666\nmap surf_666_other\nmap surf_666\n'
        self.assertEqual(dedicated_cfg(text, 'surf_666', 27618),
                         'connect 127.0.0.1:27618\nmap surf_666_other\nconnect 127.0.0.1:27618\n')


if __name__ == '__main__':
    unittest.main()
