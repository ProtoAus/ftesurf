"""P1702 tools/pi_retention.py: keep the newest two, never what is live. python3 -B tools/test_pi_retention.py"""
import contextlib
import io
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pi_retention as r

DAY = 86400
REAL = time.time()
NAMES = ('AGENT_WORK', 'OPS', 'TASUPD_RELEASES', 'BACKUP_DIRS', 'CONFIG_TREES', 'CONFIG_FLAT', 'CONFIG_FILES', 'CRONTAB',
         'NOW', 'AW_NAME', 'PATH', 'READER_PICKS', 'config_refs', 'in_use', 'blocker', 'remove_tree')


class Base(unittest.TestCase):
    """Ages are relative to a clock 30 days ahead: a test cannot backdate ctime, so every file's ctime reads old."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.d = d = Path(self.tmp.name)
        self.saved = {k: getattr(r, k) for k in NAMES}
        self.data, self.aw, self.ops, self.rel, self.etc = d / 'data', d / 'agent-work', d / 'ops', d / 'opt-tasupd', d / 'etc'
        for p in (self.data, self.aw, self.ops, self.rel, self.etc): p.mkdir()
        r.BACKUP_DIRS, r.AGENT_WORK, r.OPS, r.TASUPD_RELEASES = (str(self.data),), str(self.aw), str(self.ops), str(self.rel)
        r.CONFIG_TREES, r.CONFIG_FLAT, r.CONFIG_FILES, r.CRONTAB = (str(self.etc),), (), (), ('true',)
        r.READER_PICKS = ()
        r.AW_NAME = re.compile(re.escape(str(self.aw)) + r'/([A-Za-z0-9._-]+)')
        r.PATH = re.compile(re.escape(str(d)) + r'/[A-Za-z0-9._@+=/-]+')
        self.now = REAL + 30 * DAY; r.NOW = lambda: self.now
        self.refs, self.used = set(), set()
        r.config_refs = lambda: self.refs; r.in_use = lambda: self.used

    def tearDown(self):
        for k, v in self.saved.items(): setattr(r, k, v)
        for dp, dn, fn in os.walk(self.tmp.name):
            for n in dn: os.chmod(os.path.join(dp, n), 0o700)
            for n in fn:
                if not os.path.islink(os.path.join(dp, n)): os.chmod(os.path.join(dp, n), 0o600)
        self.tmp.cleanup()

    def file(self, path, age_days, body=b'x'):
        p = Path(path); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(body)
        t = self.now - age_days * DAY; os.utime(p, (t, t)); return str(p)

    def dir(self, path, age_days):
        p = Path(path); p.mkdir(parents=True, exist_ok=True)
        t = self.now - age_days * DAY
        for dp, dn, fn in os.walk(p):
            for n in dn + fn: os.utime(os.path.join(dp, n), (t, t))
        os.utime(p, (t, t)); return str(p)

    def run_main(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out): rc = r.main(list(args))
        return rc, out.getvalue()


class Backups(Base):
    def test_newest_two_of_each_name_stay_and_companions_go_with_their_copy(self):
        d = self.data
        oldest = [self.file(d / 'surfd.db.bak-pre1580-a', 29), self.file(d / 'surfd.db.bak-pre1580-a-shm', 29),
                  self.file(d / 'surfd.db.bak-pre1580-a-wal', 29)]
        keep = [self.file(d / 'surfd.db.bak-pre1650-b', 2), self.file(d / 'surfd.db.bak-pre1674-c', 1),
                self.file(d / 'surfd.db.bak-pre1674-c-wal', 1)]
        rec = [self.file(d / 'receipts-pre1500-x.jsonl', 9), self.file(d / 'receipts-pre1580-y.jsonl', 5),
               self.file(d / 'receipts-pre1580r-z.jsonl', 4)]
        two = [self.file(d / 'ksfgrab.py.pre996-q', 20), self.file(d / 'ksfgrab.py.pre9961-w', 19)]
        plain = [self.file(d / n, 50) for n in ('prefs.cfg', 'x.prefs', 'unit.prev', 'csprogs.dat', 'notes.backup')]
        remove, kept = r.backup_plan(set(), set())
        self.assertEqual(sorted(remove), sorted(oldest + rec[:1]))
        for p in keep + rec[1:] + two: self.assertIn(p, kept)
        for p in plain: self.assertNotIn(p, remove + kept)

    def test_the_time_in_the_name_beats_a_copied_mtime(self):
        """A deploy copy keeps the live file's mtime: fteqw-svarm64.pre1683-20261121T013746Z had mtime 17 Nov."""
        d = self.data
        self.file(d / 'fteqw-svarm64.pre1683-20261121T013746Z', 25)
        self.file(d / 'fteqw-svarm64.pre1650-20261120T083144Z', 3)
        old = self.file(d / 'fteqw-svarm64.pre1600-20261117T032800Z', 1)
        self.assertEqual(r.backup_plan(set(), set())[0], [old])

    def test_two_per_file_whatever_the_naming_and_a_readers_picks_stay(self):
        """Lex: 2 at most. tasupd trusts the newest two csprogs.dat.pre[0-9]* by mtime: those stay too."""
        d = self.data
        r.READER_PICKS = ((str(d / 'csprogs.dat.pre[0-9]*'), 2),)
        picks = [self.file(d / 'csprogs.dat.pre1648-20261120T101329Z', 9), self.file(d / 'csprogs.dat.pre1672-20261120T175500Z', 8)]
        gone = self.file(d / 'csprogs.dat.pre1600-20261117T032800Z', 20)
        newest = [self.file(d / 'csprogs.dat.bak', 1), self.file(d / 'csprogs.dat.pre-p1700', 1)]
        extra = self.file(d / 'csprogs.dat.bak-2', 2)
        remove, kept = r.backup_plan(set(), set())
        self.assertEqual(sorted(remove), sorted([gone, extra]))
        for p in picks + newest: self.assertIn(p, kept)

    def test_a_chgrp_does_not_make_an_old_unstamped_copy_newest(self):
        """ctime moves on chmod/chgrp: two 23 Oct copies must not push out the 20-21 Nov rollback copies."""
        d = self.data
        stamped = [self.file(d / 'csprogs.dat.pre0154-20261121T013746Z', 25), self.file(d / 'csprogs.dat.pre1692-20261120T202249Z', 25)]
        oct23 = 1792713600   # 2026-10-23T00:00Z
        old = [self.file(d / n, 0) for n in ('csprogs.dat.pre948-01a16480.prev', 'csprogs.dat.pre948-strcmp-01a16480.prev')]
        for p in old: os.utime(p, (oct23, oct23)); os.chmod(p, 0o640)          # fresh ctime
        self.assertEqual(sorted(r.backup_plan(set(), set())[0]), sorted(old))
        self.assertTrue(stamped)

    def test_a_named_or_used_copy_stays_past_two(self):
        d = self.data
        a, b = self.file(d / 'run.sh.pre1-a', 9), self.file(d / 'run.sh.pre2-b', 8)
        self.file(d / 'run.sh.pre3-c', 2); self.file(d / 'run.sh.pre4-d', 1)
        self.assertEqual(r.backup_plan({a}, {b})[0], [])

    def test_a_link_is_never_a_copy(self):
        d = self.data
        target = self.file(d / 'elsewhere', 1)
        for i in range(4): os.symlink(target, d / ('fteqw-svarm64.pre%d' % i))
        self.assertEqual(r.backup_plan(set(), set()), ([], []))


class Roots(Base):
    def test_old_unnamed_roots_go_and_the_live_and_marked_stay(self):
        aw = self.aw
        g = [self.dir(aw / n, 20) for n in ('gen1674-20261121-e3', 'gen1650-20261120-ed', 'gen1635-20261120-ed')]
        old = self.dir(aw / 'surfd825-20261019T0815Z', 25)
        named = self.dir(aw / 'playerfix-import-01a1c798', 25)
        marked = self.dir(aw / 'tq1635-ed', 25); self.file(aw / 'tq1635-ed' / 'RETAIN', 25)
        busy = self.dir(aw / 'deep', 25); self.file(aw / 'deep' / 'a' / 'b' / 'c' / 'new.txt', 1)
        running = self.dir(aw / 'pictures-coverage-d25cd9e', 25)
        os.symlink(old, aw / 'link-root')
        remove, kept = r.root_plan({named + '/state'}, {running + '/bin/worker.py'}, self.now)
        self.assertEqual(sorted(remove), sorted([g[2], old]))
        why = dict(kept)
        self.assertEqual(why[g[0]], 'one of the newest generations'); self.assertEqual(why[g[1]], 'one of the newest generations')
        self.assertIn('named', why[named]); self.assertIn('named', why[running])
        self.assertEqual(why[marked], 'holds RETAIN'); self.assertIn('changed', why[busy])
        self.assertEqual(why[str(aw / 'link-root')], 'not a directory')

    def test_a_copy_with_old_mtimes_is_recent_by_ctime(self):
        """cp -a / rsync -a / tar x keep old mtimes (the copy's own too): ctime says it is new."""
        self.now = REAL + DAY
        p = self.dir(self.aw / 'copied-just-now', 40)
        remove, kept = r.root_plan(set(), set(), self.now)
        self.assertEqual(remove, []); self.assertIn('changed', dict(kept)[p])

    def test_an_unreadable_part_keeps_the_root(self):
        if os.geteuid() == 0: self.skipTest('root reads everything')
        p = self.dir(self.aw / 'leftover', 25)
        locked = Path(p) / 'nginx-before'; locked.mkdir(); os.chmod(locked, 0)
        os.utime(p, (self.now - 25 * DAY,) * 2)
        remove, kept = r.root_plan(set(), set(), self.now)
        self.assertEqual(remove, []); self.assertEqual(dict(kept)[p], 'partly unreadable')

    def test_another_users_files_keep_the_root(self):
        p = self.dir(self.aw / 'theirs', 25)
        real = os.geteuid; os.geteuid = lambda: real() + 1
        try: remove, kept = r.root_plan(set(), set(), self.now)
        finally: os.geteuid = real
        self.assertEqual(remove, []); self.assertEqual(dict(kept)[p], 'owned by another user')

    def test_another_users_file_deep_inside_keeps_the_root(self):
        p = self.dir(self.aw / 'mixed', 25); inner = self.file(Path(p) / 'a' / 'root-owned.conf', 25)
        os.utime(Path(p) / 'a', (self.now - 25 * DAY,) * 2); os.utime(p, (self.now - 25 * DAY,) * 2)
        real = os.lstat
        def lstat(q, *a, **k):
            st = real(q, *a, **k)
            if str(q) != inner: return st
            return os.stat_result((st.st_mode, st.st_ino, st.st_dev, st.st_nlink, st.st_uid + 1, st.st_gid, st.st_size,
                                   st.st_atime, st.st_mtime, st.st_ctime))
        os.lstat = lstat
        try: remove, kept = r.root_plan(set(), set(), self.now)
        finally: os.lstat = real
        self.assertEqual(remove, []); self.assertEqual(dict(kept)[p], 'holds files owned by another user')

    def test_a_referenced_old_generation_stays(self):
        aw = self.aw
        for n in ('gen1674-a', 'gen1650-b'): self.dir(aw / n, 20)
        g = self.dir(aw / 'gen1603-c', 25)
        self.assertEqual(r.root_plan({g + '/backend'}, set(), self.now)[0], [])

    def test_the_real_process_scan_protects_a_root(self):
        busy = self.dir(self.aw / 'busy-cwd', 25); held = self.dir(self.aw / 'busy-file', 25)
        f = self.file(Path(held) / 'open.txt', 25); os.utime(held, (self.now - 25 * DAY,) * 2)
        proc = subprocess.Popen([sys.executable, '-c', 'import sys,time; f=open(sys.argv[1]); print(1, flush=True); time.sleep(60)', f],
                                cwd=busy, stdout=subprocess.PIPE)
        try:
            proc.stdout.readline()
            used = self.saved['in_use']()
            self.assertIn(busy, used); self.assertIn(f, used)
            remove, _ = r.root_plan(set(), used, self.now)
            self.assertNotIn(busy, remove); self.assertNotIn(held, remove)
        finally: proc.kill(); proc.wait(); proc.stdout.close()


class Checkouts(Base):
    def test_newest_two_and_the_released_stay(self):
        o = self.ops
        self.dir(o / 'tasupd-src-1a144758', 9)
        (self.rel / ('1a144758' + '9' * 32)).mkdir()
        old = self.dir(o / 'tasupd-src-73229378', 8)
        self.dir(o / 'tasupd-src-091ad1e9', 2); self.dir(o / 'tasupd-src-e5ecca2b', 1)
        self.dir(o / 'retention', 50)
        self.assertEqual(r.checkout_plan(set(), set()), [old])


class Refs(Base):
    def setUp(self):
        super().setUp(); r.config_refs = self.saved['config_refs']

    def test_paths_are_read_from_configuration_one_file_at_a_time(self):
        aw = str(self.aw); home = self.d / 'home'
        self.file(self.etc / 'surfd.service.d' / '10.conf', 1, (
            'ReadOnlyPaths="%s/gen1650-x/backend/primary"\nExecStartPre=/usr/bin/python3 -c "f=[\'%s/ac-1/state\', \'%s/run.sh\']\\nx"\n'
            % (aw, aw, home)).encode())
        self.file(self.etc / 'b.conf.pre1-x', 1, ('%s/also-config/x' % aw).encode())   # read: /etc is never skipped
        os.symlink('%s/linked/unit.service' % aw, self.etc / 'enabled.service')        # dangling: the link text counts
        self.file(home / 'run.sh', 1, ('exec %s/gen1674-y/backend/primary/control/guard.py --x' % aw).encode())
        self.file(home / 'old.log', 1, ('%s/dead-1/x' % aw).encode())
        self.file(home / 'surfd.py.pre-x', 1, ('%s/dead-2/x' % aw).encode())
        self.file(home / 'fixtures' / 'deep.json', 1, ('%s/dead-3/x' % aw).encode())
        self.file(Path(aw) / 'gen1674-y' / 'backend' / 'primary' / 'control' / 'manifest.json', 1,
                  ('{"routes": ["%s/from-manifest/x.py"]}' % aw).encode())
        r.CONFIG_FLAT = (str(home),)
        r.CRONTAB = ('sh', '-c', 'echo "0 * * * * %s/from-cron/run.sh"' % aw)
        refs = r.config_refs()
        for want in ('gen1650-x/backend/primary', 'ac-1/state', 'also-config/x', 'linked/unit.service',
                     'gen1674-y/backend/primary/control/guard.py', 'from-manifest/x.py', 'from-cron/run.sh'):
            self.assertIn('%s/%s' % (aw, want), refs)
        self.assertIn(str(home / 'run.sh'), refs)                        # stops at the quote and the literal \n
        for dead in ('dead-1', 'dead-2', 'dead-3'): self.assertFalse(any(dead in x for x in refs), dead)

    def test_unreadable_configuration_stops_the_run(self):
        if os.geteuid() == 0: self.skipTest('root reads everything')
        keepme = self.file(self.data / 'run.sh.pre1-a', 9)
        for i in range(3): self.file(self.data / ('run.sh.pre%d-b' % (i + 2)), 3 - i)
        conf = self.etc / 'surfd.service.d' / '10.conf'
        self.file(conf, 1, ('ReadOnlyPaths=%s' % keepme).encode())
        self.assertEqual(r.backup_plan(r.config_refs(), set())[0], [str(self.data / 'run.sh.pre2-b')])
        for lock in (conf, conf.parent):
            os.chmod(lock, 0)
            rc, out = self.run_main('--apply')
            os.chmod(lock, 0o700 if lock.is_dir() else 0o600)
            self.assertEqual(rc, 2, out); self.assertIn('STOPPED, nothing removed', out)
            self.assertTrue(os.path.exists(keepme)); self.assertTrue((self.data / 'run.sh.pre2-b').exists())

    def test_a_failed_crontab_stops_the_run_and_an_empty_one_does_not(self):
        r.CRONTAB = ('sh', '-c', 'echo boom >&2; exit 2')
        rc, out = self.run_main('--apply'); self.assertEqual(rc, 2); self.assertIn('crontab', out)
        r.CRONTAB = ('sh', '-c', 'echo "no crontab for proto" >&2; exit 1')
        self.assertEqual(self.run_main()[0], 0)

    def test_an_unreadable_copy_a_loader_picks_up_stops_the_run(self):
        if os.geteuid() == 0: self.skipTest('root reads everything')
        for rel in ('nginx/conf.d/x.pre-1.conf', 'systemd/system/foo.service.d/20-a.pre1.conf', 'systemd/system/a.service.pre1-x.service'):
            f = self.file(self.etc / rel, 1); os.chmod(f, 0)
            rc, out = self.run_main('--apply'); os.chmod(f, 0o600); os.unlink(f)
            self.assertEqual(rc, 2, rel)

    def test_a_link_to_something_unreadable_stops_the_run(self):
        if os.geteuid() == 0: self.skipTest('root reads everything')
        locked = self.d / 'locked'; self.file(locked / 'real.service', 1); os.chmod(locked, 0)
        os.symlink(locked / 'real.service', self.etc / 'enabled.service')
        rc, out = self.run_main('--apply'); os.chmod(locked, 0o700)
        self.assertEqual(rc, 2, out)

    def test_a_linked_configuration_folder_is_read(self):
        real = self.d / 'real-dropins'; self.file(real / '10.conf', 1, ('ReadOnlyPaths=%s/via-link/x' % self.aw).encode())
        os.symlink(real, self.etc / 'surfd.service.d')
        self.assertIn('%s/via-link/x' % self.aw, r.config_refs())

    def test_tls_keys_may_be_unreadable(self):
        if os.geteuid() == 0: self.skipTest('root reads everything')
        k = self.file(self.etc / 'nginx' / 'ssl' / 'site.key', 1); os.chmod(k, 0)
        self.assertEqual(self.run_main()[0], 0)

    def test_an_unreadable_copy_is_skipped_unless_nginx_loads_its_folder(self):
        if os.geteuid() == 0: self.skipTest('root reads everything')
        c = self.file(self.etc / 'nginx' / 'play.proto.bar.conf.pre-zonepub-887ffa7b8eb5', 1); os.chmod(c, 0)
        self.assertEqual(self.run_main()[0], 0)
        e = self.file(self.etc / 'nginx' / 'sites-enabled' / 'play.proto.bar.conf.pre-x', 1); os.chmod(e, 0)
        rc, out = self.run_main('--apply'); self.assertEqual(rc, 2); self.assertIn('sites-enabled', out)

    def test_a_path_named_beneath_a_copy_or_root_protects_it(self):
        self.assertTrue(r.named('/srv/nvme/x/a', {'/srv/nvme/x/a/b'}, set()))
        self.assertFalse(r.named('/srv/nvme/x/a', {'/srv/nvme/x/ab'}, set()))


class Run(Base):
    def test_dry_run_removes_nothing_and_apply_removes_and_logs(self):
        d, aw = self.data, self.aw
        files = [self.file(d / ('qwprogs.dat.pre%d-x' % i), 10 - i) for i in range(4)]
        root = self.dir(aw / 'surfd770-20261018T0000b', 25)
        ro = Path(root) / 'nginx-before'; ro.mkdir(); self.file(ro / 'site.conf', 25); os.chmod(ro, 0o500)
        os.utime(ro, (self.now - 25 * DAY,) * 2); os.utime(root, (self.now - 25 * DAY,) * 2)
        log = str(self.ops / 'retention.log')
        rc, out = self.run_main('--log', log)
        self.assertEqual(rc, 0); self.assertIn('would remove: 2 backup copies', out)
        for p in files: self.assertTrue(os.path.exists(p))
        self.assertTrue(os.path.isdir(root))
        rc, out = self.run_main('--apply', '--log', log)
        self.assertEqual(rc, 0, out)
        self.assertEqual([os.path.exists(p) for p in files], [False, False, True, True])
        self.assertFalse(os.path.exists(root))
        body = Path(log).read_text()
        self.assertIn('would remove', body); self.assertIn('removing: 2 backup copies', body)
        self.assertIn('done: 3 removed, 0 problems', body)

    def test_removal_leaves_the_parent_and_hard_linked_files_alone(self):
        parent = self.aw; os.chmod(parent, 0o2755); before = os.stat(parent).st_mode
        outside = self.file(self.d / 'live-binary', 1); os.chmod(outside, 0o755)
        root = self.dir(self.aw / 'old-root', 25)
        ro = Path(root) / 'ro'; ro.mkdir(); os.link(outside, ro / 'hardlink'); os.chmod(ro, 0o500)
        failed = []
        r.remove_tree(root, failed)
        self.assertEqual(failed, []); self.assertFalse(os.path.exists(root))
        self.assertEqual(os.stat(parent).st_mode, before)
        self.assertEqual(os.stat(outside).st_mode & 0o777, 0o755)

    def test_a_folder_we_do_not_own_is_not_made_writable(self):
        root = self.dir(self.aw / 'not-ours', 25)
        ro = Path(root) / 'ro'; ro.mkdir(); self.file(ro / 'f', 25); os.chmod(ro, 0o500)
        real = os.geteuid; os.geteuid = lambda: real() + 1
        failed = []
        try: r.remove_tree(root, failed)
        finally: os.geteuid = real
        self.assertTrue(failed); self.assertEqual(os.stat(ro).st_mode & 0o777, 0o500)

    def test_a_failure_is_logged_and_exits_one(self):
        root = self.dir(self.aw / 'stuck', 25)
        r.remove_tree = lambda p, failed: failed.append('%s: Permission denied' % p)
        log = str(self.ops / 'retention.log')
        rc, out = self.run_main('--apply', '--log', log)
        self.assertEqual(rc, 1); self.assertIn('NOT REMOVED %s' % root, Path(log).read_text())

    def test_the_plan_is_logged_before_anything_goes(self):
        self.dir(self.aw / 'doomed', 25)
        def killed(p, failed): raise KeyboardInterrupt
        r.remove_tree = killed
        log = str(self.ops / 'retention.log')
        with self.assertRaises(KeyboardInterrupt): self.run_main('--apply', '--log', log)
        self.assertIn('removing: 0 backup copies (0.0 MB), 1 task roots', Path(log).read_text())

    def test_a_root_written_after_planning_is_kept(self):
        root = self.dir(self.aw / 'woke-up', 25)
        calls = []
        def blocker(p, cut): calls.append(p); return 'changed in the last 14 days' if len(calls) > 1 else None
        r.blocker = blocker
        rc, out = self.run_main('--apply')
        self.assertEqual(rc, 1); self.assertTrue(os.path.isdir(root)); self.assertIn('(found after planning); kept', out)

    def test_the_log_keeps_its_last_2000_lines(self):
        log = self.ops / 'retention.log'; log.write_text('old\n' * 2500)
        self.run_main('--log', str(log))
        lines = log.read_text().splitlines()
        self.assertEqual(len(lines), 2000); self.assertIn('would remove', lines[-1])


class Patterns(unittest.TestCase):
    def test_backup_names(self):
        def m(n):
            x = r.BACKUP.match(n); return x and (x.group('name'), x.group('scheme'))
        self.assertEqual(m('surfd.db.bak-pre1674-20261120T175713Z'), ('surfd.db', '.bak'))   # name, scheme
        self.assertEqual(m('csprogs.dat.pre1648-20261120T101329Z'), ('csprogs.dat', '.pre'))
        self.assertEqual(m('story.txt.pre1681-20261121T014239Z'), ('story.txt', '.pre'))
        self.assertEqual(m('receipts-pre1580r-20261117T215426Z.jsonl'), ('receipts', '-pre'))
        self.assertEqual(m('ftesurf.nginx.pre-p699'), ('ftesurf.nginx', '.pre-'))
        self.assertEqual(m('crontab.bak-20261005-ksf'), ('crontab', '.bak'))
        for n in ('prefs.cfg', 'x.prefs', 'unit.prev', 'preview.png', 'p1702-sweep.py', 'a.backup', 'bakery.txt'):
            self.assertIsNone(r.BACKUP.match(n), n)

    def test_name_stamps(self):
        t = lambda n: time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(r.copy_time('/x/' + n, [])))
        self.assertEqual(t('a.pre1683-20261121T013746Z'), '2026-11-21 01:37:46')
        self.assertEqual(t('crontab.bak-20261104T1727Z'), '2026-11-04 17:27:00')
        self.assertEqual(t('a.pre490-20261005-024331'), '2026-10-05 02:43:31')


if __name__ == '__main__':
    unittest.main()
