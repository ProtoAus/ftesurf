#!/usr/bin/env python3
"""Native harness CLI selection only: no builds, games, grading or installs."""
import argparse
import ast
import contextlib
import importlib
import io
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

TOOLS = Path(__file__).resolve().parent
SCRIPTS = ('p598build.py', 'p600input.py', 'p601model.py', 'p603scores.py',
           'p603dense_variant.py', 'p603font_variant.py', 'p603perf.py')
SOURCE_ONLY = {'p598build.py', 'p603dense_variant.py', 'p603font_variant.py'}


def cli_block(script):
    tree = ast.parse((TOOLS / script).read_text(encoding='utf8'))
    return next(node for node in tree.body if isinstance(node, ast.If)
                and '__name__' in ast.unparse(node.test)).body


def namespace():
    result = {'argparse': argparse, 'Path': Path, 'ROOT': Path('/fixture/QC'),
              'ARMS': ('native1', 'native2', 'absent', 'drawonly', 'scale1', 'scale2'),
              '__doc__': 'CLI contract fixture'}
    if (TOOLS / 'native_test_paths.py').exists():
        module = importlib.import_module('native_test_paths')
        result.update(add_native_paths=module.add_native_paths,
                      resolve_native_paths=module.resolve_native_paths)
    return result


def parse_cli(script, argv):
    nodes = []
    for node in cli_block(script):
        nodes.append(node)
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'a' for t in node.targets):
            break
    scope = namespace()
    with mock.patch.object(sys, 'argv', [script, *argv]):
        exec(compile(ast.Module(body=nodes, type_ignores=[]), script, 'exec'), scope)
    return scope['p'], scope['a']


def full_cli(script, argv, grade_errors=None):
    scope = namespace()
    touched = []
    def forbidden(*args, **kwargs):
        touched.append('native work')
        raise AssertionError('Native/build/copy entrypoint reached without selected inputs')
    scope.update(run=forbidden, build=forbidden, create=forbidden,
                 cfg=lambda *args: None, transport=argparse.Namespace(run=forbidden),
                 grade=lambda rig: [] if grade_errors is None else grade_errors)
    with mock.patch.object(sys, 'argv', [script, *argv]):
        exec(compile(ast.Module(body=cli_block(script), type_ignores=[]), script, 'exec'), scope)
    return touched


def minimum(script):
    if script in SOURCE_ONLY:
        return ['--out', '/fixture/new-output']
    if script in {'p603scores.py', 'p603perf.py'}:
        return ['--qc-artifacts', '/fixture/VMs', '--plugin', '/fixture/plugin.dll', '--out', '/fixture/new-output']
    return []


class NativePathTests(unittest.TestCase):
    def setUp(self):
        self.environment = mock.patch.dict(os.environ, {'FTESURF_FTEROOT': ''})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_no_implicit_personal_worktree_in_actual_parsers(self):
        for script in SCRIPTS:
            with self.subTest(script=script):
                _, args = parse_cli(script, minimum(script))
                self.assertIsNone(getattr(args, 'fte', None), 'No engine source should be silently selected')
                self.assertIsNone(getattr(args, 'engine', None), 'No client should be silently selected')
                self.assertIsNone(getattr(args, 'server', None), 'No live/old server should be silently selected')

    def test_missing_inputs_stop_all_actual_cli_blocks_before_work(self):
        for script in SCRIPTS:
            with self.subTest(script=script), contextlib.redirect_stderr(io.StringIO()) as errors:
                with self.assertRaises(SystemExit) as failure:
                    full_cli(script, minimum(script))
                self.assertEqual(failure.exception.code, 2)
                self.assertIn('--fte', errors.getvalue())

    def test_selected_root_derives_matching_client_and_server(self):
        from native_test_paths import resolve_native_paths
        for script in SCRIPTS:
            with self.subTest(script=script):
                parser, args = parse_cli(script, ['--fte', '/fixture/pinned-engine', *minimum(script)])
                source_only = script in SOURCE_ONLY
                resolve_native_paths(parser, args, source=script != 'p603perf.py',
                                     client=not source_only, server=not source_only)
                self.assertEqual(args.fte, Path('/fixture/pinned-engine'))
                if not source_only:
                    self.assertEqual(args.engine, args.fte / 'engine/release/fteqw64.exe')
                    self.assertEqual(args.server, args.fte / 'engine/release/fteqwsv64.exe')

    def test_explicit_binaries_are_not_overwritten(self):
        from native_test_paths import resolve_native_paths
        for script in set(SCRIPTS) - SOURCE_ONLY:
            with self.subTest(script=script):
                parser, args = parse_cli(script, ['--fte', '/fixture/source', '--engine', '/fixture/client.exe',
                                                 '--server', '/fixture/server.exe', *minimum(script)])
                resolve_native_paths(parser, args)
                self.assertEqual(args.engine, Path('/fixture/client.exe'))
                self.assertEqual(args.server, Path('/fixture/server.exe'))

    def test_environment_root_and_explicit_root_precedence(self):
        from native_test_paths import resolve_native_paths
        with mock.patch.dict(os.environ, {'FTESURF_FTEROOT': '/fixture/environment-source'}):
            for script in SCRIPTS:
                with self.subTest(script=script):
                    _, args = parse_cli(script, minimum(script))
                    self.assertEqual(args.fte, Path('/fixture/environment-source'))
                    _, args = parse_cli(script, ['--fte', '/fixture/explicit-source', *minimum(script)])
                    self.assertEqual(args.fte, Path('/fixture/explicit-source'))

    def test_explicit_prebuilt_inputs_do_not_require_source(self):
        from native_test_paths import resolve_native_paths
        for script in ('p600input.py', 'p601model.py', 'p603scores.py', 'p603perf.py'):
            with self.subTest(script=script):
                parser, args = parse_cli(script, ['--engine', '/fixture/client.exe', '--server', '/fixture/server.exe',
                                                 '--plugin', '/fixture/plugin.dll', *minimum(script)])
                resolve_native_paths(parser, args, source=False)
                self.assertIsNone(args.fte)
                self.assertEqual(args.engine, Path('/fixture/client.exe'))

    def test_grade_only_keeps_results_and_needs_no_native_paths(self):
        for script in ('p600input.py', 'p601model.py', 'p603scores.py', 'p603perf.py'):
            argv = ['--grade', '/fixture/retained'] if script == 'p603scores.py' else ['grade', '/fixture/retained']
            for errors, expected in (([], False), (['existing retained failure'], True)):
                with self.subTest(script=script, errors=errors), contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit) as code:
                        full_cli(script, argv, grade_errors=errors)
                    self.assertEqual(bool(code.exception.code), expected)

    def test_help_still_works_without_native_paths(self):
        for script in SCRIPTS:
            with self.subTest(script=script), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as code:
                    full_cli(script, ['--help'])
                self.assertEqual(code.exception.code, 0)


if __name__ == '__main__':
    unittest.main()
