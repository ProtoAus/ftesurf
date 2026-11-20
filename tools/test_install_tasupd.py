#!/usr/bin/env python3
"""install_tasupd.py: the fresh install and --upgrade-from, against a temporary tree (Linux: needs pwd).

The upgrade cases are test_install_tasrevd.py's, renamed; Fresh is new.

systemctl is modelled as systemd behaves: the unit file is read at daemon-reload, and a restart
serves what was loaded then. Probes record their URL; git serves the commit's bytes (the working
tree differs); `runuser -u X --` prefixes are recorded and stripped. Run as a normal user or root:
python3 tools/test_install_tasupd.py
"""
import contextlib
import io
import json
import os
from pathlib import Path
import signal
import sqlite3
import stat
import sys
import tempfile
import types
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install_tasupd as t

OLD, NEW = 'a' * 40, 'b' * 40
PUBLIC = 'https://play.proto.bar/tasup/api/health'
REAL_EUID = os.geteuid()


class Upgrade(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); d = Path(self.tmp.name)
        self.saved = {k: getattr(t, k) for k in ('ROOT', 'RELEASES', 'STATE', 'UNIT', 'SNIPPET', 'ZONES', 'root_only', 'run', 'probe_app',
                                                 'check_accounts', 'check_chain', 'write_release', 'replace_unit')}
        t.ROOT, t.RELEASES, t.STATE = d / 'srv-ops/tasupd', d / 'opt/ftesurf-tasupd', d / 'srv-ops/tasupd-state'
        t.UNIT, t.SNIPPET, t.ZONES = d / 'ftesurf-tasupd.service', d / 'ftesurf-tasupd.conf', d / 'tasupd-zones.conf'
        t.root_only = lambda p: None
        (d / 'opt').mkdir()
        self.src = d / 'src'; (self.src / '.git').mkdir(parents=True)
        self.fail_reload_after_switch = False
        for rel in t.FILES:   # the working tree differs from the commit
            (self.src / rel).parent.mkdir(parents=True, exist_ok=True); (self.src / rel).write_bytes(b'# edited, not committed\n')
        self.install_old(t.ROOT)
        t.STATE.mkdir(); (t.STATE / 'tasup.sqlite3').write_bytes(b'db')
        t.SNIPPET.write_text(t.NGINX); t.ZONES.write_text(t.NGINX_ZONES)
        self.calls, self.envs, self.probes, self.held, self.chains, self.imports = [], [], [], [], [], []
        self.active, self.dropins, self.loaded, self.serving = 'active', '', OLD, OLD
        self.fail_new = self.fail_old_after = False
        self.pending = 'Id=surfd.service\nNeedDaemonReload=no\n\nId=nginx.service\nNeedDaemonReload=no'
        t.run = self.fake_run; t.probe_app = self.fake_probe
        t.check_accounts = lambda path: None; t.check_chain = self.chains.append
        self.euid = os.geteuid; os.geteuid = lambda: 0
        self.umask = os.umask(0o022); os.umask(self.umask)

    def installer_blob(self): return Path(t.__file__).resolve().read_bytes()

    def install_old(self, root):
        old = root / OLD; old.mkdir(parents=True)
        (old / 'SOURCE.json').write_text(json.dumps(dict(commit=OLD, files={})))
        t.UNIT.write_text(t.unit_text(old, t.service_env(old, Path('/srv/nvme/surfd/data/surfd.db'), OLD)))

    def tearDown(self):
        for k, v in self.saved.items(): setattr(t, k, v)
        os.geteuid = self.euid; os.umask(self.umask); os.environ.pop('SUDO_UID', None)
        self.tmp.cleanup()

    def source_of_unit(self):
        line = [l for l in t.UNIT.read_text().splitlines() if 'TASUPD_SOURCE=' in l][0]
        return line.split('TASUPD_SOURCE=')[1].rstrip('"')

    def fake_run(self, *args, timeout=30, **kw):
        user = None
        if args[:2] == ('/usr/sbin/runuser', '-u'): user, args = args[2], args[4:]
        self.calls.append((user,) + args)
        out = b''
        if args[:1] == ('git',):
            self.envs.append(kw.get('env'))
            if 'rev-parse' in args: out = (NEW + '\n').encode()
            elif 'cat-file' in args and args[-1].endswith(':tools/install_tasupd.py'): out = self.installer_blob()
            elif 'cat-file' in args: out = b'# committed ' + args[-1].encode() + b'\n'
        elif args[:1] == (sys.executable,):   # the import check: what proto would see
            cwd = Path(kw['cwd'])
            self.imports.append([stat.S_IMODE(p.stat().st_mode) for p in [cwd, cwd / 'tools', cwd / 'tasupd.py', cwd / 'tools/tasplaus.py']])
        elif args[:2] == ('/usr/bin/systemctl', 'show'):
            prop = [x for x in args if x.startswith('--property=')][0].split('=', 1)[1]
            out = (self.pending if prop == 'Id,NeedDaemonReload' else {
                'ActiveState': self.active, 'DropInPaths': self.dropins, 'NeedDaemonReload': 'no',
                'FragmentPath': str(t.UNIT)}[prop]).encode() + b'\n'
        elif args[:2] == ('/usr/bin/systemctl', 'daemon-reload'):
            if self.fail_reload_after_switch and self.serving == NEW: raise OSError('systemd busy')
            self.loaded = self.source_of_unit()
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
        argv = ['install_tasupd.py', '--source', str(self.src), '--commit', NEW, '--upgrade-from', OLD] + list(extra)
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
        # Known handlers first: under nohup/& both are already ignored, and the hold must still show.
        saved = {n: signal.signal(n, signal.SIG_DFL) for n in (signal.SIGINT, signal.SIGHUP)}
        try: self.main('--apply')
        finally: after = {n: signal.getsignal(n) for n in saved}; [signal.signal(n, h) for n, h in saved.items()]
        new = t.RELEASES / NEW
        self.assertEqual(t.UNIT.read_text(), t.unit_text(new, t.service_env(new, Path('/srv/nvme/surfd/data/surfd.db'), NEW)))
        for src, dest in t.FILES.items():
            self.assertEqual((new / dest).read_bytes(), b'# committed ' + ('%s:%s' % (NEW, src)).encode() + b'\n')
            self.assertEqual(stat.S_IMODE((new / dest).stat().st_mode), 0o644)
        for d in (t.RELEASES, new, new / 'tools'): self.assertEqual(stat.S_IMODE(d.stat().st_mode), 0o755)
        self.assertEqual(self.serving, NEW)
        self.assertIn((NEW, PUBLIC), self.probes)
        self.assertEqual(self.held, [True])                  # Ctrl-C and hangup held across the switch
        self.assertEqual(after, {signal.SIGINT: signal.SIG_DFL, signal.SIGHUP: signal.SIG_DFL})   # restored
        self.assertEqual(self.chains, [t.RELEASES.parent, t.RELEASES])
        self.assertTrue((t.ROOT / OLD).is_dir())
        self.assertIn('Upgraded', (new / 'UPGRADE.txt').read_text())
        self.assertEqual((t.STATE / 'tasup.sqlite3').read_bytes(), b'db')

    def test_the_schema_step_runs_before_the_switch(self):
        self.main('--apply')
        init = [i for i, c in enumerate(self.calls) if 'init' in c and str(c[2]).endswith('tasupd.py')]
        restart = [i for i, c in enumerate(self.calls) if c[1:3] == ('/usr/bin/systemctl', 'restart')]
        self.assertEqual(len(init), 1)
        self.assertEqual(self.calls[init[0]][0], 'proto')
        self.assertEqual(self.calls[init[0]][2], str(t.RELEASES / NEW / 'tasupd.py'))
        self.assertLess(init[0], restart[0])

    def test_an_upgrade_refuses_pending_unit_edits(self):
        self.pending = 'Id=surfd.service\nNeedDaemonReload=yes'
        with self.assertRaisesRegex(RuntimeError, 'surfd.service'): self.main('--apply')
        self.assertFalse((t.RELEASES / NEW).exists())

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
        self.assertTrue(git and all(c[0] == 'proto' and c[2:4] == ('-c', 'safe.directory=' + str(self.src)) for c in git))
        self.assertTrue(self.envs and all(not any(k.startswith('SUDO_') for k in e) for e in self.envs))
        self.assertEqual([c[0] for c in self.calls if c[1:2] == (sys.executable,)], ['proto'])
        self.assertEqual(self.imports, [[0o755, 0o755, 0o644, 0o644]])   # readable by proto under any umask

    def test_a_foreign_unit_is_refused(self):
        t.UNIT.write_text(t.UNIT.read_text().replace('MemoryMax=512M', 'MemoryMax=1G'))
        with self.assertRaisesRegex(RuntimeError, 'not the one this installer wrote'): self.main('--apply')
        self.assertFalse((t.RELEASES / NEW).exists())

    def test_a_crlf_unit_is_refused(self):
        t.UNIT.write_bytes(t.UNIT.read_bytes().replace(b'\n', b'\r\n'))
        with self.assertRaisesRegex(RuntimeError, 'not the one this installer wrote'): self.main('--apply')

    def test_drop_ins_are_refused(self):
        self.dropins = '/etc/systemd/system/ftesurf-tasupd.service.d/override.conf'
        with self.assertRaisesRegex(RuntimeError, 'drop-ins'): self.main('--apply')

    def test_a_changed_snippet_is_refused(self):
        t.SNIPPET.write_text(t.NGINX + '# edited\n')
        with self.assertRaisesRegex(RuntimeError, 'snippet or its zones changed'): self.main('--apply')


    def test_changed_zones_are_refused(self):
        t.ZONES.write_text(t.NGINX_ZONES + '# edited\n')
        with self.assertRaisesRegex(RuntimeError, 'snippet or its zones changed'): self.main('--apply')
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
        self.assertIn((None, '/usr/bin/systemctl', 'reset-failed', 'ftesurf-tasupd.service'), self.calls)
        self.assertIn('rolled back', (t.RELEASES / NEW / 'UPGRADE.txt').read_text())

    def test_a_rollback_whose_reload_fails_says_systemd_may_run_the_new_release(self):
        self.fail_new = self.fail_reload_after_switch = True
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaisesRegex(RuntimeError, 'may still run the new release'):
            self.main('--apply')
        self.assertIn('may still run the new release', out.getvalue())   # printed too, not only raised

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

    def test_the_outcome_file_is_written_even_when_the_terminal_is_gone(self):
        test = self
        class Gone(io.StringIO):   # the session drops during the switch (the restart)
            def write(self, s):
                if any(c[1:3] == ('/usr/bin/systemctl', 'restart') for c in test.calls): raise OSError(5, 'Input/output error')
                return super().write(s)
        with contextlib.redirect_stdout(Gone()): self.main('--apply')
        self.assertIn('Upgraded', (t.RELEASES / NEW / 'UPGRADE.txt').read_text())

    def test_an_upgrade_takes_no_nginx_hash(self):
        with self.assertRaises(SystemExit): self.main('--expected-nginx-sha256', 'c' * 64)


SITE = b'''server {
    listen 443 ssl http2;
    client_max_body_size 16k;
    include snippets/surfd.conf;
    include snippets/ftesurf-tasrevd.conf;
    location / { return 404; }
}
'''


class Fresh(unittest.TestCase):
    """The first install: service and probe first, then the one nginx include, put back on failure."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); d = Path(self.tmp.name)
        names = ('ROOT', 'RELEASES', 'STATE', 'UNIT', 'SNIPPET', 'ZONES', 'SITE', 'BACKUPS', 'run', 'probe_app', 'check_accounts',
                 'check_port', 'pwd', 'check_chain', 'root_only')
        self.saved = {k: getattr(t, k) for k in names}
        t.ROOT, t.STATE, t.RELEASES = d / 'srv-ops/tasupd', d / 'srv-ops/tasupd-state', d / 'opt-tasupd'
        t.check_chain = lambda p: None
        self.pending = 'Id=surfd.service\nNeedDaemonReload=no'
        t.UNIT, t.SNIPPET, t.SITE, t.BACKUPS = d / 'unit.service', d / 'snippet.conf', d / 'site.conf', d
        t.ZONES = d / 'zones.conf'; t.root_only = lambda p: None
        (d / 'srv-ops').mkdir()
        t.SITE.write_bytes(SITE)
        self.src = d / 'src'; (self.src / '.git').mkdir(parents=True)
        self.account_db = d / 'surfd.db'; self.account_db.write_bytes(b'')
        t.check_accounts = lambda p: None; t.check_port = lambda: None
        t.pwd = types.SimpleNamespace(getpwnam=lambda n: types.SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid()))
        t.run = self.fake_run; t.probe_app = self.fake_probe
        self.calls, self.probes, self.held, self.cwds = [], [], [], {}
        self.loadstate, self.public_fails, self.serving = 'not-found', False, None
        self.nginx_tests, self.nginx_t_fails_at = 0, None
        self.euid = os.geteuid; os.geteuid = lambda: 0
        self.sleep = t.time.sleep; t.time.sleep = lambda s: None   # the time module itself: put back below

    def tearDown(self):
        for k, v in self.saved.items(): setattr(t, k, v)
        os.geteuid = self.euid; t.time.sleep = self.sleep
        self.tmp.cleanup()

    def fake_run(self, *args, timeout=30, **kw):
        user = None
        if args[:2] == ('/usr/sbin/runuser', '-u'): user, args = args[2], args[4:]
        self.calls.append((user,) + args)
        out = b''
        if args[:1] == ('git',):
            if 'rev-parse' in args: out = (NEW + '\n').encode()
            elif 'cat-file' in args and args[-1].endswith(':tools/install_tasupd.py'): out = self.installer_blob()
            elif 'cat-file' in args: out = b'# committed ' + args[-1].encode() + b'\n'
        elif args[:2] == ('/usr/bin/systemctl', 'show') and '--property=Id,NeedDaemonReload' in args: out = self.pending.encode()
        elif args[:2] == ('/usr/bin/systemctl', 'show'): out = (self.loadstate + '\n').encode()
        elif args[:2] == ('/usr/sbin/nginx', '-t'):
            self.nginx_tests += 1
            if self.nginx_tests == self.nginx_t_fails_at: raise OSError('nginx -t failed')
        elif args[:2] == ('/usr/bin/systemctl', 'enable'): self.serving = NEW
        elif args[:2] == ('/usr/sbin/nginx', '-T'):
            out = t.SITE.read_bytes() + (t.SNIPPET.read_bytes() if b'ftesurf-tasupd.conf' in t.SITE.read_bytes() else b'')
        elif len(args) > 1 and str(args[1]).endswith('tasupd.py') and 'init' in args:
            t.STATE.joinpath('tasup.sqlite3').write_bytes(b'db')
        elif args[:2] == ('/usr/bin/python3', '-I'):
            self.cwds['flask'] = kw.get('cwd')
        return types.SimpleNamespace(stdout=out, returncode=0)

    def installer_blob(self): return Path(t.__file__).resolve().read_bytes()

    def fake_probe(self, commit, url=None):
        self.probes.append(url)
        self.held.append(signal.getsignal(signal.SIGINT) is signal.SIG_IGN and signal.getsignal(signal.SIGHUP) is signal.SIG_IGN)
        if self.serving != commit: raise RuntimeError('not serving')
        if url and self.public_fails: raise self.public_fails if isinstance(self.public_fails, BaseException) else RuntimeError('public route does not answer')

    def main(self, *extra, nginx=None):
        argv = ['install_tasupd.py', '--source', str(self.src), '--commit', NEW, '--account-db', str(self.account_db),
                '--expected-nginx-sha256', nginx or t.sha(SITE)] + list(extra)
        old, sys.argv = sys.argv, argv
        try:
            with contextlib.redirect_stdout(io.StringIO()) as out: t.main()
        finally: sys.argv = old
        return out.getvalue()

    def test_dry_run_changes_nothing(self):
        out = self.main()
        self.assertIn('DRY RUN', out)
        self.assertEqual(t.SITE.read_bytes(), SITE)
        for p in (t.UNIT, t.SNIPPET, t.STATE, t.ROOT): self.assertFalse(p.exists())
        self.assertEqual(self.probes, [])

    def test_apply_installs_and_adds_one_include(self):
        out = self.main('--apply')
        self.assertIn('Installed the TAS upload service at https://play.proto.bar/tasup/', out)
        self.assertEqual(t.SITE.read_bytes(), SITE.replace(b'include snippets/surfd.conf;',
                                                           b'include snippets/surfd.conf;\n    include snippets/ftesurf-tasupd.conf;'))
        self.assertEqual(t.SNIPPET.read_text(), t.NGINX)
        self.assertEqual(t.ZONES.read_text(), t.NGINX_ZONES)
        self.assertIn('client_max_body_size 8300k', t.NGINX)
        self.assertIn('limit_conn tasupd_addr', t.NGINX)
        self.assertIn('zone=tasupd_addr', t.NGINX_ZONES)
        unit = t.UNIT.read_text()
        self.assertIn('TASUPD_SOURCE=%s' % NEW, unit)
        self.assertIn('TASUPD_URL=https://play.proto.bar/tasup', unit)
        self.assertIn('TASUPD_ZONES=' + os.pathsep.join(t.ZONE_DIRS), unit)
        self.assertIn('ReadWritePaths=%s' % t.STATE, unit)
        self.assertEqual(len(t.ZONE_DIRS), len(set(t.ZONE_DIRS)))
        self.assertEqual(self.probes[0], None)                       # loopback before nginx changes
        self.assertEqual(self.probes[-1], t.PUBLIC_URL + '/api/health')
        self.assertTrue(self.held and all(self.held))               # Ctrl-C and hangup held from the unit on
        self.assertIn('MemorySwapMax=0', unit)
        self.assertIn('TASUPD_MAPCFG=/srv/nvme/ftesurf-server/game/ftesurf/cfg/maps', unit)
        self.assertEqual((t.BACKUPS / ('site.conf.pre-tasupd-' + NEW[:12])).read_bytes(), SITE)
        init = [c for c in self.calls if 'init' in c]
        self.assertEqual([c[0] for c in init], ['proto'])
        for src, dest in t.FILES.items():
            self.assertEqual((t.RELEASES / NEW / dest).read_bytes(), b'# committed ' + ('%s:%s' % (NEW, src)).encode() + b'\n')
        self.assertFalse((t.ROOT / NEW).exists())                     # not under proto's /srv/nvme/ftesurf-ops

    def test_a_public_route_that_does_not_answer_puts_nginx_back(self):
        self.public_fails = True
        with self.assertRaisesRegex(RuntimeError, 'public route'): self.main('--apply')
        self.assertEqual(t.SITE.read_bytes(), SITE)
        self.assertIn((None, '/usr/bin/systemctl', 'disable', '--now', 'ftesurf-tasupd.service'), self.calls)

    def test_an_interrupt_after_the_include_puts_nginx_back(self):
        self.public_fails = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): self.main('--apply')
        self.assertEqual(t.SITE.read_bytes(), SITE)
        self.assertIn((None, '/usr/bin/systemctl', 'disable', '--now', 'ftesurf-tasupd.service'), self.calls)

    def test_a_failed_site_write_leaves_the_site_whole(self):
        real = t.os.replace
        def failing(src, dst):
            if Path(dst) == t.SITE: raise OSError(28, 'No space left on device')
            return real(src, dst)
        t.os.replace = failing
        try:
            with self.assertRaisesRegex(OSError, 'No space'): self.main('--apply')
        finally:
            t.os.replace = real
        self.assertEqual(t.SITE.read_bytes(), SITE)
        self.assertEqual(sorted(x.name for x in t.BACKUPS.iterdir() if x.name.startswith('.tasupd-site')), [])
        self.assertIn((None, '/usr/bin/systemctl', 'disable', '--now', 'ftesurf-tasupd.service'), self.calls)

    def test_the_site_keeps_its_mode(self):
        t.SITE.chmod(0o640)
        self.main('--apply')
        self.assertEqual(stat.S_IMODE(t.SITE.stat().st_mode), 0o640)
        self.assertIn(b'include snippets/ftesurf-tasupd.conf;', t.SITE.read_bytes())

    def test_the_flask_check_runs_isolated_from_the_owner_directory(self):
        self.main()
        self.assertEqual(self.cwds.get('flask'), '/')

    def test_a_rollback_whose_nginx_test_fails_still_disables_the_unit(self):
        self.public_fails = True; self.nginx_t_fails_at = 3   # preflight, after the include, the rollback's
        with self.assertRaisesRegex(RuntimeError, 'rollback: nginx put back but not reloaded'): self.main('--apply')
        self.assertEqual(t.SITE.read_bytes(), SITE)
        self.assertIn((None, '/usr/bin/systemctl', 'disable', '--now', 'ftesurf-tasupd.service'), self.calls)

    def test_a_site_someone_else_changed_is_not_put_back(self):
        real = self.fake_probe
        def probe(commit, url=None):
            if url: t.SITE.write_bytes(SITE + b'# a peer\n'); raise RuntimeError('public route does not answer')
            return real(commit, url)
        self.fake_probe = probe; t.probe_app = probe
        with self.assertRaisesRegex(RuntimeError, 'the site changed meanwhile: not put back'): self.main('--apply')
        self.assertEqual(t.SITE.read_bytes(), SITE + b'# a peer\n')
        self.assertIn((None, '/usr/bin/systemctl', 'disable', '--now', 'ftesurf-tasupd.service'), self.calls)

    def test_pending_unit_edits_are_refused(self):
        self.pending = 'Id=surfd.service\nNeedDaemonReload=yes\n\nId=nginx.service\nNeedDaemonReload=no'
        with self.assertRaisesRegex(RuntimeError, 'surfd.service'): self.main('--apply')
        self.assertFalse(t.UNIT.exists())

    def test_another_installer_is_refused(self):
        self.installer_blob = lambda: b'# some other installer\n'
        with self.assertRaisesRegex(RuntimeError, 'not tools/install_tasupd.py'): self.main()

    def test_a_non_root_dry_run_leaves_nginx_t_to_the_apply(self):
        os.geteuid = lambda: 1000
        out = self.main()
        self.assertIn('DRY RUN', out)
        self.assertNotIn(('/usr/sbin/nginx', '-t'), [c[1:3] for c in self.calls])

    def test_pending_reloads_include_stopped_units(self):
        self.main()
        show = [c for c in self.calls if '--property=Id,NeedDaemonReload' in c]
        self.assertTrue(show and all('--all' in c for c in show))

    def test_the_state_directory_is_made_through_descriptors(self):
        real = t.STATE.parent
        real.mkdir(parents=True, exist_ok=True)
        elsewhere = Path(self.tmp.name) / 'elsewhere'; elsewhere.mkdir()
        moved = real.with_name('srv-ops-real'); real.rename(moved); real.symlink_to(elsewhere)
        try:
            with self.assertRaises(OSError): t.make_state()           # a symlink on the way: refused
            self.assertEqual(list(elsewhere.iterdir()), [])
        finally:
            real.unlink(); moved.rename(real)
        t.make_state()
        self.assertTrue(t.STATE.is_dir() and not t.STATE.is_symlink())

    def test_the_flask_check_runs_as_proto(self):
        self.main()
        flask = [c for c in self.calls if c[1:4] == ('/usr/bin/python3', '-I', '-c')]
        self.assertEqual([c[0] for c in flask], ['proto'])

    def test_changed_nginx_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'nginx changed'): self.main('--apply', nginx='0' * 64)
        self.assertFalse(t.UNIT.exists())

    def test_an_existing_installation_is_refused(self):
        t.SNIPPET.write_text('peer')
        with self.assertRaisesRegex(RuntimeError, 'already exists'): self.main('--apply')
        self.assertEqual(t.SITE.read_bytes(), SITE)

    def test_a_loaded_unit_is_refused(self):
        self.loadstate = 'loaded'
        with self.assertRaisesRegex(RuntimeError, 'owner inspection'): self.main('--apply')


class RootOnly(unittest.TestCase):
    def test_a_file_root_does_not_own_is_refused(self):
        with tempfile.NamedTemporaryFile() as f:
            if os.geteuid() == 0: self.skipTest('as root the file is root-owned')
            with self.assertRaisesRegex(RuntimeError, 'someone other than root'): t.root_only(Path(f.name))


class Probe(unittest.TestCase):
    def fake(self, url, headers, body):
        class R:
            def __enter__(s): return s
            def __exit__(s, *a): return False
            def read(s, n): return json.dumps(body).encode()
        R.headers = headers
        self.urls.append(url)
        return R()

    def test_the_probe_reads_health_and_wants_the_accounts(self):
        self.urls, real = [], t.urllib.request.urlopen
        try:
            t.urllib.request.urlopen = lambda url, timeout: self.fake(url, {'X-Tasupd-Source': NEW}, {'ok': 1, 'store': 1, 'accounts': 1})
            t.probe_app(NEW)
            self.assertEqual(self.urls, ['http://127.0.0.1:8091/tasup/api/health'])
            t.urllib.request.urlopen = lambda url, timeout: self.fake(url, {'X-Tasupd-Source': NEW}, {'ok': 1})
            with self.assertRaisesRegex(RuntimeError, 'health control'): t.probe_app(NEW)
            t.urllib.request.urlopen = lambda url, timeout: self.fake(url, {'X-Tasupd-Source': OLD}, {'ok': 1, 'accounts': 1})
            with self.assertRaisesRegex(RuntimeError, 'serving source'): t.probe_app(NEW)
        finally:
            t.urllib.request.urlopen = real


class Accounts(unittest.TestCase):
    def test_the_preflight_leaves_no_side_files(self):
        # P1618: root recreating -wal/-shm would hide what the sandboxed service sees.
        with tempfile.TemporaryDirectory() as d:
            db_path = Path(d) / 'surfd.db'
            with contextlib.closing(sqlite3.connect(db_path)) as db:
                db.execute('PRAGMA journal_mode=WAL')
                with db: db.execute('CREATE TABLE accounts (steamid TEXT, name TEXT, banned_at INTEGER)')
                with db: db.execute('CREATE TABLE runs (map TEXT, track INTEGER, leg INTEGER, style TEXT, millis INTEGER)')
            self.assertEqual(os.listdir(d), ['surfd.db'])
            t.check_accounts(db_path)
            self.assertEqual(os.listdir(d), ['surfd.db'])
            with contextlib.closing(sqlite3.connect(db_path)) as db:
                db.execute('CREATE TABLE other (x)')
            with contextlib.closing(sqlite3.connect(db_path)) as db:
                db.execute('DROP TABLE accounts')
            with self.assertRaises(sqlite3.Error): t.check_accounts(db_path)

    def test_the_preflight_wants_the_board_runs(self):
        with tempfile.TemporaryDirectory() as d:
            db_path = Path(d) / 'surfd.db'
            with contextlib.closing(sqlite3.connect(db_path)) as db, db:
                db.execute('CREATE TABLE accounts (steamid TEXT, name TEXT, banned_at INTEGER)')
            with self.assertRaisesRegex(sqlite3.Error, 'runs'): t.check_accounts(db_path)


class Chain(unittest.TestCase):
    def check(self, bad):
        real = t.os.lstat
        def lstat_(p):
            uid = 1000 if str(p) == bad else 0
            return os.stat_result((stat.S_IFDIR | 0o755, 1, 1, 2, uid, 0, 0, 0, 0, 0))
        t.os.lstat = lstat_
        try: t.check_chain(Path('/opt/ftesurf-tasupd'))
        finally: t.os.lstat = real

    def test_every_directory_above_is_checked(self):
        self.check(None)
        for bad in ('/opt/ftesurf-tasupd', '/opt', '/'):
            with self.assertRaisesRegex(RuntimeError, 'only root can write'): self.check(bad)

    @unittest.skipIf(REAL_EUID == 0, 'as root the temporary tree is root-owned')
    def test_a_real_directory_not_owned_by_root_is_refused(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaisesRegex(RuntimeError, 'only root can write'):
            t.check_chain(Path(d))


class CurrentClosure(unittest.TestCase):
    def test_current_service_files_import_without_the_checkout(self):
        if os.geteuid() == 0:
            import pwd
            try:
                pwd.getpwnam('proto')
            except KeyError:
                self.skipTest('root import probe requires the configured proto identity')
        source = Path(__file__).resolve().parents[1]
        blobs = {dest: (source / src).read_bytes() for src, dest in t.FILES.items()}
        # Unlike Upgrade's modelled subprocess, exercise the actual current
        # import closure in the installer's isolated temporary release.
        t.check_imports(blobs)


if __name__ == '__main__':
    unittest.main()
