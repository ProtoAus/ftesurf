#!/usr/bin/env python3
"""Stdlib-only parser checks; no compiler, make, game or private data touched."""
from pathlib import Path
import unittest
from clangdb import native_path, parse_commands


class ClangDatabaseTests(unittest.TestCase):
    def test_paths(self):
        msys = Path("C:/msys64")
        self.assertEqual(native_path("/c/repo/a.c", msys), "C:/repo/a.c")
        self.assertEqual(native_path("/usr/include/opus", msys), "C:/msys64/usr/include/opus")
        self.assertEqual(native_path("/home/Lex/fteqw/a.c", msys), "C:/msys64/home/Lex/fteqw/a.c")
        self.assertEqual(native_path("./libs/include", msys), "./libs/include")
        self.assertEqual(native_path("C:\\repo\\a.c", msys), "C:/repo/a.c")

    def test_real_shape_and_non_compile_rows(self):
        text = '\n'.join([
            'cc -MM -I/c/repo/engine /c/repo/engine/server/sv_user.c > a.d; ' + chr(92),
            'cc -x c-header -o a.gch -c /c/repo/engine/client/quakedef.h',
            'cc -o game.exe a.o -lws2_32',
            'cc -DCONFIG_FILE_NAME=config_fteqw.h -DGLQUAKE -I/c/repo/engine/client '
            '-I/usr/include/opus -I. -o /c/repo/out/a.o -c /c/repo/engine/server/sv_user.c',
        ])
        entries = parse_commands(text, Path("C:/repo/engine"), Path("C:/msys64"), Path("C:/msys64/ucrt64/bin/gcc.exe"))
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["file"], "C:/repo/engine/server/sv_user.c")
        self.assertEqual(entry["directory"], "C:/repo/engine")
        self.assertEqual(entry["arguments"][0], "C:/msys64/ucrt64/bin/gcc.exe")
        self.assertIn("-DCONFIG_FILE_NAME=config_fteqw.h", entry["arguments"])
        self.assertIn("-IC:/msys64/usr/include/opus", entry["arguments"])
        self.assertIn("C:/repo/out/a.o", entry["arguments"])

    def test_quoted_paths_and_duplicate(self):
        line = 'gcc -I"/c/repo with spaces/engine" -o a.o -c "/c/repo with spaces/engine/a.c"'
        entries = parse_commands(line + '\n' + line, Path("C:/repo with spaces/engine"), Path("C:/msys64"), Path("C:/gcc.exe"))
        self.assertEqual(len(entries), 1)
        self.assertIn("-IC:/repo with spaces/engine", entries[0]["arguments"])

    def test_empty_is_not_success(self):
        with self.assertRaises(ValueError):
            parse_commands('echo nothing', Path('.'), Path('.'), Path('gcc.exe'))


if __name__ == "__main__":
    unittest.main()
