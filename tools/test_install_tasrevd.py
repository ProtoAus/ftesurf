#!/usr/bin/env python3
"""P1119: install_tasrevd.py --upgrade-from, against a temporary tree (Linux: the installer needs pwd).

systemctl is modelled as systemd behaves: the unit file is read at daemon-reload, and a restart
serves what was loaded then. Probes record their URL; git serves the commit's bytes (the working
tree differs); `runuser -u X --` prefixes are recorded and stripped. Run as a normal user or root:
python3 tools/test_install_tasrevd.py
"""
import contextlib
import io
import json
import os
from pathlib import Path
import pwd
import signal
import stat
import sys
import tempfile
import types
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install_tasrevd as t

OLD, NEW = 'a' * 40, 'b' * 40
PUBLIC = 'https://play.proto.bar/api/tasrev/map/tasrevd_install_probe'
REAL_EUID = os.geteuid()
ME = pwd.getpwuid(os.getuid()).pw_name   # who made the temporary checkout, independent of the code


class Upgrade(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); d = Path(self.tmp.name)
        self.saved = {k: getattr(t, k) for k in ('ROOT', 'RELEASES', 'STATE', 'UNIT', 'SNIPPET', 'run', 'probe_app',
                                                 'check_accounts', 'check_chain', 'write_release', 'replace_unit')}
        t.ROOT, t.RELEASES, t.STATE = d / 'srv-ops/tasrevd', d / 'opt/ftesurf-tasrevd', d / 'srv-ops/tasrevd-state'
        t.UNIT, t.SNIPPET = d / 'ftesurf-tasrevd.service', d / 'ftesurf-tasrevd.conf'
        (d / 'opt').mkdir()
        self.src = d / 'src'; (self.src / '.git').mkdir(parents=True)
        for rel in t.FILES:   # the working tree differs from the commit
            (self.src / rel).parent.mkdir(parents=True, exist_ok=True); (self.src / rel).write_bytes(b'# edited, not committed\n')
        self.install_old(t.ROOT)
        t.STATE.mkdir(); (t.STATE / 'tasrev.sqlite3').write_bytes(b'db'); (t.STATE / 'codes.txt').write_text('c' * 64 + '\n')
        t.SNIPPET.write_text(t.NGINX)
        self.calls, self.envs, self.probes, self.held, self.chains, self.imports = [], [], [], [], [], []
        self.active, self.dropins, self.loaded, self.serving = 'active', '', OLD, OLD
        self.fail_new = self.fail_old_after = False
        t.run = self.fake_run; t.probe_app = self.fake_probe
        t.check_accounts = lambda path: None; t.check_chain = self.chains.append
        self.euid = os.geteuid; os.geteuid = lambda: 0
        self.umask = os.umask(0o022); os.umask(self.umask)

    def install_old(self, root):
        old = root / OLD; old.mkdir(parents=True)
        (old / 'SOURCE.json').write_text(json.dumps(dict(commit=OLD, files={})))
        t.UNIT.write_text(t.unit_text(old, t.service_env(old, Path('/srv/nvme/surfd/data/surfd.db'), OLD)))

    def tearDown(self):
        for k, v in self.saved.items(): setattr(t, k, v)
        os.geteuid = self.euid; os.umask(self.umask); os.environ.pop('SUDO_UID', None)
        self.tmp.cleanup()

    def source_of_unit(self):
        line = [l for l in t.UNIT.read_text().splitlines() if 'TASREVD_SOURCE=' in l][0]
        return line.split('TASREVD_SOURCE=')[1].rstrip('"')

    def fake_run(self, *args, timeout=30, **kw):
        user = None
        if args[:2] == ('/usr/sbin/runuser', '-u'): user, args = args[2], args[4:]
        self.calls.append((user,) + args)
        out = b''
        if args[:1] == ('git',):
            self.envs.append(kw.get('env'))
            if 'rev-parse' in args: out = (NEW + '\n').encode()
            elif 'cat-file' in args: out = b'# committed ' + args[-1].encode() + b'\n'
        elif args[:1] == (sys.executable,):   # the import check: what proto would see
            cwd = Path(kw['cwd'])
            self.imports.append([stat.S_IMODE(p.stat().st_mode) for p in [cwd, cwd / 'tools', cwd / 'tasrevd.py', cwd / 'tools/tasrev.py']])
        elif args[:2] == ('/usr/bin/systemctl', 'show'):
            prop = [x for x in args if x.startswith('--property=')][0].split('=', 1)[1]
            out = {'ActiveState': self.active, 'DropInPaths': self.dropins, 'NeedDaemonReload': 'no',
                   'FragmentPath': str(t.UNIT)}[prop].encode() + b'\n'
        elif args[:2] == ('/usr/bin/systemctl', 'daemon-reload'): self.loaded = self.source_of_unit()
        elif args[:2] == ('/usr/bin/systemctl', 'restart'):
            self.held.append(signal.getsignal(signal.SIGINT) is signal.SIG_IGN and signal.getsignal(signal.SIGHUP) is signal.SIG_IGN)
            self.serving = self.loaded
        return types.SimpleNamespace(stdout=out, returncode=0)

    def fake_probe(self, commit, url=None):
        self.probes.append((commit, url))
        if self.fail_new and self.serving == NEW: raise RuntimeError('new release did not serve')
        if self.fail_old_after and self.serving == OLD and any(c[1:3] == ('/usr/bin/systemctl', 'restart') for c in self.calls):
            raise RuntimeError('old release did not serve either')
        if self.serving != commit: raise RuntimeError('Unexpected serving source')

    def main(self, *extra):
        argv = ['install_tasrevd.py', '--source', str(self.src), '--commit', NEW, '--upgrade-from', OLD] + list(extra)
        old, sys.argv = sys.argv, argv
        try: t.main()
        finally: sys.argv = old

    def test_dry_run_changes_nothing(self):
        unit = t.UNIT.read_bytes()
        self.main()
        self.assertEqual(t.UNIT.read_bytes(), unit)
        self.assertFalse(t.RELEASES.exists())
        self.assertFalse(any(c[1:3] == ('/usr/bin/systemctl', 'restart') for c in self.calls))
        self.assertEqual(self.chains, [t.RELEASES.parent])   # /opt checked before it holds anything

    def test_apply_installs_the_commit_and_proves_it_publicly(self):
        os.umask(0o077)   # an owner's tight umask must not lock proto out
        self.main('--apply')
        new = t.RELEASES / NEW
        self.assertEqual(t.UNIT.read_text(), t.unit_text(new, t.service_env(new, Path('/srv/nvme/surfd/data/surfd.db'), NEW)))
        for src, dest in t.FILES.items():
            self.assertEqual((new / dest).read_bytes(), b'# committed ' + ('%s:%s' % (NEW, src)).encode() + b'\n')
            self.assertEqual(stat.S_IMODE((new / dest).stat().st_mode), 0o644)
        for d in (t.RELEASES, new, new / 'tools'): self.assertEqual(stat.S_IMODE(d.stat().st_mode), 0o755)
        self.assertEqual(self.serving, NEW)
        self.assertIn((NEW, PUBLIC), self.probes)
        self.assertEqual(self.held, [True])                  # Ctrl-C and hangup held across the switch
        self.assertEqual(signal.getsignal(signal.SIGINT), signal.default_int_handler)
        self.assertEqual(self.chains, [t.RELEASES.parent, t.RELEASES])
        self.assertTrue((t.ROOT / OLD).is_dir())
        self.assertIn('Upgraded', (new / 'UPGRADE.txt').read_text())
        self.assertEqual((t.STATE / 'codes.txt').read_text(), 'c' * 64 + '\n')

    def test_a_later_upgrade_from_an_opt_release(self):
        (t.ROOT / OLD / 'SOURCE.json').unlink(); (t.ROOT / OLD).rmdir()
        self.install_old(t.RELEASES)
        self.main('--apply')
        self.assertEqual(self.serving, NEW)
        self.assertEqual(self.chains, [t.RELEASES, t.RELEASES])

    def test_root_runs_no_proto_controlled_code(self):
        os.environ['SUDO_UID'] = '1000'   # git would trust a .git owned by that uid
        self.main()
        git = [c for c in self.calls if c[1:2] == ('git',)]
        self.assertTrue(git and all(c[0] == ME for c in git))
        self.assertTrue(self.envs and all(not any(k.startswith('SUDO_') for k in e) for e in self.envs))
        self.assertEqual([c[0] for c in self.calls if c[1:2] == (sys.executable,)], ['proto'])
        self.assertEqual(self.imports, [[0o755, 0o755, 0o644, 0o644]])   # readable by proto under any umask

    def test_a_checkout_whose_git_has_another_owner_is_refused(self):
        real = os.stat
        def stat_(p, *a, **k):
            r = real(p, *a, **k)
            return os.stat_result((r.st_mode, r.st_ino, r.st_dev, r.st_nlink, r.st_uid + 1) + tuple(r)[5:10]) if str(p).endswith('.git') else r
        t.os.stat = stat_
        try:
            with self.assertRaisesRegex(RuntimeError, 'different owners'): self.main()
        finally: t.os.stat = real

    def test_a_foreign_unit_is_refused(self):
        t.UNIT.write_text(t.UNIT.read_text().replace('MemoryMax=384M', 'MemoryMax=1G'))
        with self.assertRaisesRegex(RuntimeError, 'not the one this installer wrote'): self.main('--apply')
        self.assertFalse((t.RELEASES / NEW).exists())

    def test_a_crlf_unit_is_refused(self):
        t.UNIT.write_bytes(t.UNIT.read_bytes().replace(b'\n', b'\r\n'))
        with self.assertRaisesRegex(RuntimeError, 'not the one this installer wrote'): self.main('--apply')

    def test_drop_ins_are_refused(self):
        self.dropins = '/etc/systemd/system/ftesurf-tasrevd.service.d/override.conf'
        with self.assertRaisesRegex(RuntimeError, 'drop-ins'): self.main('--apply')

    def test_a_changed_snippet_is_refused(self):
        t.SNIPPET.write_text(t.NGINX + '# edited\n')
        with self.assertRaisesRegex(RuntimeError, 'snippet changed'): self.main('--apply')

    def test_an_existing_new_release_is_refused(self):
        for where in (t.RELEASES, t.ROOT):
            (where / NEW).mkdir(parents=True)
            with self.assertRaisesRegex(RuntimeError, 'already exists'): self.main('--apply')
            (where / NEW).rmdir()

    def test_a_stopped_service_is_refused(self):
        self.active = 'failed'
        with self.assertRaisesRegex(RuntimeError, 'not running'): self.main('--apply')

    def test_a_unit_changed_during_the_upgrade_is_not_switched(self):
        def write_then_edit(release, commit, blobs):
            self.saved['write_release'](release, commit, blobs); t.UNIT.write_text(t.UNIT.read_text() + '# owner\n')
        t.write_release = write_then_edit
        with self.assertRaisesRegex(RuntimeError, 'changed during the upgrade'): self.main('--apply')
        self.assertEqual(self.serving, OLD)

    def test_a_release_that_does_not_serve_is_rolled_back_and_proved(self):
        oldunit = t.UNIT.read_bytes(); self.fail_new = True
        with self.assertRaisesRegex(RuntimeError, 'rolled back, aaaaaaaaaaaa serves again'): self.main('--apply')
        self.assertEqual(t.UNIT.read_bytes(), oldunit)
        self.assertEqual(self.serving, OLD)                 # needs the rollback's daemon-reload, not only the file
        self.assertIn((None, '/usr/bin/systemctl', 'reset-failed', 'ftesurf-tasrevd.service'), self.calls)
        self.assertIn('rolled back', (t.RELEASES / NEW / 'UPGRADE.txt').read_text())

    def test_a_rollback_that_does_not_serve_says_so(self):
        self.fail_new = self.fail_old_after = True
        with self.assertRaisesRegex(RuntimeError, 'restarted but did not serve'): self.main('--apply')

    def test_a_rollback_that_cannot_put_the_unit_back_says_so(self):
        self.fail_new = True; n = [0]
        def replace_once(body):
            n[0] += 1
            if n[0] > 1: raise OSError('disk full')
            self.saved['replace_unit'](body)
        t.replace_unit = replace_once
        with self.assertRaisesRegex(RuntimeError, 'could not be put back'): self.main('--apply')

    def test_the_outcome_is_printed_when_its_file_cannot_be_written(self):
        def write_and_block(release, commit, blobs):
            self.saved['write_release'](release, commit, blobs); (release / 'UPGRADE.txt').mkdir()
        t.write_release = write_and_block
        out = io.StringIO()
        with contextlib.redirect_stdout(out): self.main('--apply')
        self.assertIn('Upgraded', out.getvalue()); self.assertIn('could not write', out.getvalue())

    def test_an_upgrade_takes_no_nginx_hash_or_codes(self):
        with self.assertRaises(SystemExit): self.main('--code', 'c' * 64)


class Chain(unittest.TestCase):
    def check(self, bad):
        real = t.os.lstat
        def lstat_(p):
            uid = 1000 if str(p) == bad else 0
            return os.stat_result((stat.S_IFDIR | 0o755, 1, 1, 2, uid, 0, 0, 0, 0, 0))
        t.os.lstat = lstat_
        try: t.check_chain(Path('/opt/ftesurf-tasrevd'))
        finally: t.os.lstat = real

    def test_every_directory_above_is_checked(self):
        self.check(None)
        for bad in ('/opt/ftesurf-tasrevd', '/opt', '/'):
            with self.assertRaisesRegex(RuntimeError, 'only root can write'): self.check(bad)

    @unittest.skipIf(REAL_EUID == 0, 'as root the temporary tree is root-owned')
    def test_a_real_directory_not_owned_by_root_is_refused(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaisesRegex(RuntimeError, 'only root can write'):
            t.check_chain(Path(d))


if __name__ == '__main__':
    unittest.main()
