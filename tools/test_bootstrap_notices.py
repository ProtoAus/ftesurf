#!/usr/bin/env python3
"""Small notice-generator falsifiers; all fixtures stay under an explicit owned root."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import bootstrap_notices


class NoticeTests(unittest.TestCase):
    root: Path

    def fixture(self, names=('main', 'dependency', 'unreachable')):
        root = self.root / self._testMethodName
        root.mkdir()
        packages = []
        for name in names:
            directory = root / name; directory.mkdir()
            (directory / 'Cargo.toml').write_text('fixture\n')
            if name != 'unreachable':
                (directory / 'LICENSE').write_text('MIT notice for ' + name + '\n')
            packages.append({'id': name, 'name': name, 'version': '1.0.0',
                             'manifest_path': str(directory / 'Cargo.toml'), 'license': 'MIT', 'license_file': None})
        metadata = {'packages': packages, 'resolve': {'root': 'main', 'nodes': [
            {'id': 'main', 'deps': [{'pkg': 'dependency'}]},
            {'id': 'dependency', 'deps': []}, {'id': 'unreachable', 'deps': []}]}}
        return root, metadata

    def test_target_reachability(self):
        root, metadata = self.fixture()
        with patch('bootstrap_notices.subprocess.run', return_value=SimpleNamespace(stdout=json.dumps(metadata))) as run:
            text = bootstrap_notices.collect(root, ['x86_64-pc-windows-msvc'])
        self.assertIn('MIT notice for main', text)
        self.assertIn('MIT notice for dependency', text)
        self.assertNotIn('unreachable 1.0.0', text)
        self.assertNotIn(str(root), text)
        self.assertIn('--locked', run.call_args.args[0])
        self.assertIn('--filter-platform', run.call_args.args[0])

    def test_missing_license_fails(self):
        root, metadata = self.fixture()
        (root / 'dependency/LICENSE').unlink()
        with patch('bootstrap_notices.subprocess.run', return_value=SimpleNamespace(stdout=json.dumps(metadata))):
            with self.assertRaisesRegex(ValueError, 'license texts missing: dependency'):
                bootstrap_notices.collect(root, ['x86_64-pc-windows-msvc'])

    def test_explicit_notice_and_license_directory(self):
        root, metadata = self.fixture()
        dep = root / 'dependency'
        (dep / 'LICENSE').unlink()
        (dep / 'legal.txt').write_text('Explicit license text\n')
        (dep / 'licenses').mkdir()
        (dep / 'licenses/ISC.txt').write_text('Nested ISC text\n')
        metadata['packages'][1]['license_file'] = 'legal.txt'
        with patch('bootstrap_notices.subprocess.run', return_value=SimpleNamespace(stdout=json.dumps(metadata))):
            text = bootstrap_notices.collect(root, ['x86_64-pc-windows-msvc'])
        self.assertIn('Explicit license text', text)
        self.assertIn('Nested ISC text', text)

    def test_outside_license_path_refused(self):
        root, metadata = self.fixture()
        (root / 'outside.txt').write_text('owned outside notice sentinel\n')
        metadata['packages'][1]['license_file'] = '../outside.txt'
        with patch('bootstrap_notices.subprocess.run', return_value=SimpleNamespace(stdout=json.dumps(metadata))):
            with self.assertRaisesRegex(ValueError, 'unsafe license path: dependency'):
                bootstrap_notices.collect(root, ['x86_64-pc-windows-msvc'])

    def test_platform_union(self):
        root, windows = self.fixture()
        linux = json.loads(json.dumps(windows))
        (root / 'unreachable/LICENSE').write_text('Linux-only notice\n')
        linux['resolve']['nodes'][0]['deps'].append({'pkg': 'unreachable'})
        results = [SimpleNamespace(stdout=json.dumps(item)) for item in (windows, linux)]
        with patch('bootstrap_notices.subprocess.run', side_effect=results):
            text = bootstrap_notices.collect(root, ['x86_64-pc-windows-msvc', 'x86_64-unknown-linux-gnu'])
        self.assertIn('Linux-only notice', text)
        self.assertEqual(text.count('MIT notice for main'), 1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    args = parser.parse_args()
    if args.work_root.exists():
        parser.error('use a fresh owned test root')
    args.work_root.mkdir(parents=True)
    (args.work_root / 'OWNER.md').write_text('Notice generator unit fixtures; retained updater task evidence.\n')
    NoticeTests.root = args.work_root.resolve()
    unittest.main(argv=['test_bootstrap_notices', '-v'])
