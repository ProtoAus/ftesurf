#!/usr/bin/env python3
"""P1119: install_tasrevd.py --upgrade-from, against a temporary tree (Linux: the installer needs pwd).

systemctl, nginx and the HTTP probe are faked: a restart serves whatever TASREVD_SOURCE the unit
file names, so the probe sees the unit actually swapped. Run: python3 tools/test_install_tasrevd.py
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install_tasrevd as t

OLD, NEW = 'a' * 40, 'b' * 40


class Upgrade(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); d = Path(self.tmp.name)
        self.saved = {k: getattr(t, k) for k in ('ROOT', 'STATE', 'UNIT', 'SNIPPET', 'run', 'probe_app', 'check_imports', 'check_accounts')}
        t.ROOT, t.STATE = d / 'tasrevd', d / 'tasrevd-state'
        t.UNIT, t.SNIPPET = d / 'ftesurf-tasrevd.service', d / 'ftesurf-tasrevd.conf'
        self.src = d / 'src'
        for rel in t.FILES: (self.src / rel).parent.mkdir(parents=True, exist_ok=True); (self.src / rel).write_bytes(b'# ' + rel.encode() + b'\n')
        old = t.ROOT / OLD; old.mkdir(parents=True)
        (old / 'SOURCE.json').write_text(json.dumps(dict(commit=OLD, files={})))
        t.STATE.mkdir(); (t.STATE / 'tasrev.sqlite3').write_bytes(b'db'); (t.STATE / 'codes.txt').write_text('c' * 64 + '\n')
        self.accounts = Path('/srv/nvme/surfd/data/surfd.db')
        t.UNIT.write_text(t.unit_text(old, t.service_env(old, self.accounts, OLD)))
        t.SNIPPET.write_text(t.NGINX)
        self.calls, self.active, self.serving, self.fail_new = [], 'active', OLD, False
        t.run = self.fake_run; t.probe_app = self.fake_probe
        t.check_imports = lambda blobs: None; t.check_accounts = lambda path: None
        self.euid = os.geteuid; os.geteuid = lambda: 0

    def tearDown(self):
        for k, v in self.saved.items(): setattr(t, k, v)
        os.geteuid = self.euid
        self.tmp.cleanup()

    def fake_run(self, *args):
        self.calls.append(args)
        out = b''
        if args[:2] == ('git', '-C'): out = (NEW + '\n').encode() if 'rev-parse' in args else b''
        elif args[-2:] == ('--property=ActiveState', 'ftesurf-tasrevd.service'): out = self.active.encode() + b'\n'
        elif args[:2] == ('/usr/bin/systemctl', 'restart'):
            src = [l for l in t.UNIT.read_text().splitlines() if 'TASREVD_SOURCE=' in l][0]
            self.serving = src.split('TASREVD_SOURCE=')[1].rstrip('"')
        return types.SimpleNamespace(stdout=out)

    def fake_probe(self, commit, url=None):
        if self.fail_new and self.serving == NEW: raise RuntimeError('new release did not serve')
        if self.serving != commit: raise RuntimeError('Unexpected serving source')

    def main(self, *extra):
        argv = ['install_tasrevd.py', '--source', str(self.src), '--commit', NEW, '--upgrade-from', OLD] + list(extra)
        old, sys.argv = sys.argv, argv
        try: t.main()
        finally: sys.argv = old

    def test_dry_run_changes_nothing(self):
        unit = t.UNIT.read_text()
        self.main()
        self.assertEqual(t.UNIT.read_text(), unit)
        self.assertFalse((t.ROOT / NEW).exists())
        self.assertFalse(any(c[:2] == ('/usr/bin/systemctl', 'restart') for c in self.calls))

    def test_apply_upgrades_and_serves_the_new_release(self):
        self.main('--apply')
        new = t.ROOT / NEW
        self.assertEqual(t.UNIT.read_text(), t.unit_text(new, t.service_env(new, self.accounts, NEW)))
        self.assertEqual(json.loads((new / 'SOURCE.json').read_text())['commit'], NEW)
        self.assertTrue(all((new / dest).is_file() for dest in t.FILES.values()))
        self.assertEqual(self.serving, NEW)
        self.assertTrue((t.ROOT / OLD).is_dir())                       # the old release stays
        self.assertEqual((t.STATE / 'codes.txt').read_text(), 'c' * 64 + '\n')
        self.assertEqual(t.SNIPPET.read_text(), t.NGINX)

    def test_a_foreign_unit_is_refused(self):
        t.UNIT.write_text(t.UNIT.read_text().replace('MemoryMax=384M', 'MemoryMax=1G'))
        with self.assertRaisesRegex(RuntimeError, 'not the one this installer wrote'): self.main('--apply')
        self.assertFalse((t.ROOT / NEW).exists())

    def test_a_changed_snippet_is_refused(self):
        t.SNIPPET.write_text(t.NGINX + '# edited\n')
        with self.assertRaisesRegex(RuntimeError, 'snippet changed'): self.main('--apply')

    def test_an_existing_new_release_is_refused(self):
        (t.ROOT / NEW).mkdir()
        with self.assertRaisesRegex(RuntimeError, 'already exists'): self.main('--apply')

    def test_a_stopped_service_is_refused(self):
        self.active = 'failed'
        with self.assertRaisesRegex(RuntimeError, 'not running'): self.main('--apply')

    def test_a_release_that_does_not_serve_puts_the_old_unit_back(self):
        oldunit = t.UNIT.read_text(); self.fail_new = True
        with self.assertRaises(RuntimeError): self.main('--apply')
        self.assertEqual(t.UNIT.read_text(), oldunit)
        self.assertEqual(self.serving, OLD)                             # restarted on the old release
        self.assertTrue((t.ROOT / NEW).is_dir())                        # kept for inspection

    def test_an_upgrade_takes_no_nginx_hash_or_codes(self):
        with self.assertRaises(SystemExit): self.main('--code', 'c' * 64)


if __name__ == '__main__':
    unittest.main()
