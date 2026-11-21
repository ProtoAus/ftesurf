"""P1702 tools/pi_retention.py: keep the newest two, never what is live. python3 -B tools/test_pi_retention.py"""
import contextlib
import io
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pi_retention as r

DAY = 86400


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); d = Path(self.tmp.name)
        self.saved = {k: getattr(r, k) for k in ('AGENT_WORK', 'OPS', 'TASUPD_RELEASES', 'BACKUP_DIRS', 'config_text', 'in_use')}
        self.data, self.aw, self.ops, self.rel = d / 'data', d / 'agent-work', d / 'ops', d / 'opt-tasupd'
        for p in (self.data, self.aw, self.ops, self.rel): p.mkdir()
        r.BACKUP_DIRS, r.AGENT_WORK, r.OPS, r.TASUPD_RELEASES = (str(self.data),), str(self.aw), str(self.ops), str(self.rel)
        r.AW_NAME = __import__('re').compile(__import__('re').escape(str(self.aw)) + r'/([A-Za-z0-9._-]+)')
        self.text, self.used = '', set()
        r.config_text = lambda: self.text; r.in_use = lambda: self.used
        self.now = time.time()

    def tearDown(self):
        for k, v in self.saved.items(): setattr(r, k, v)
        r.AW_NAME = __import__('re').compile(r'/srv/nvme/agent-work/([A-Za-z0-9._-]+)')
        for dp, dn, fn in os.walk(self.tmp.name):
            for n in dn: os.chmod(os.path.join(dp, n), 0o700)
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


class Backups(Base):
    def test_newest_two_of_each_name_stay_and_companions_go_with_their_copy(self):
        d = self.data
        oldest = [self.file(d / 'surfd.db.bak-pre1580-a', 30), self.file(d / 'surfd.db.bak-pre1580-a-shm', 30),
                  self.file(d / 'surfd.db.bak-pre1580-a-wal', 30)]
        keep = [self.file(d / 'surfd.db.bak-pre1650-b', 2), self.file(d / 'surfd.db.bak-pre1674-c', 1),
                self.file(d / 'surfd.db.bak-pre1674-c-wal', 1)]
        rec = [self.file(d / 'receipts-pre1500-x.jsonl', 9), self.file(d / 'receipts-pre1580-y.jsonl', 5),
               self.file(d / 'receipts-pre1580r-z.jsonl', 4)]
        two = [self.file(d / 'ksfgrab.py.pre996-q', 40), self.file(d / 'ksfgrab.py.pre-906bfd78-w', 39)]
        plain = [self.file(d / n, 50) for n in ('prefs.cfg', 'x.prefs', 'unit.prev', 'csprogs.dat', 'notes.backup')]
        remove, kept = r.backup_plan('', set())
        self.assertEqual(sorted(remove), sorted(oldest + rec[:1]))
        for p in keep + rec[1:] + two: self.assertIn(p, kept)
        for p in plain: self.assertNotIn(p, remove + kept)

    def test_a_named_or_used_copy_stays_past_two(self):
        d = self.data
        a, b = self.file(d / 'run.sh.pre1-a', 9), self.file(d / 'run.sh.pre2-b', 8)
        self.file(d / 'run.sh.pre3-c', 2); self.file(d / 'run.sh.pre4-d', 1)
        remove, _ = r.backup_plan('ExecStartPre=/bin/cat ' + a, {b})
        self.assertEqual(remove, [])

    def test_a_link_is_never_a_copy(self):
        d = self.data
        target = self.file(d / 'elsewhere', 1)
        for i in range(4): os.symlink(target, d / ('fteqw-svarm64.pre%d' % i))
        self.assertEqual(r.backup_plan('', set()), ([], []))


class Roots(Base):
    def test_old_unnamed_roots_go_and_the_live_and_marked_stay(self):
        aw = self.aw
        g = [self.dir(aw / n, 20) for n in ('gen1674-20261121-e3', 'gen1650-20261120-ed', 'gen1635-20261120-ed')]
        old = self.dir(aw / 'surfd825-20261019T0815Z', 30)
        named = self.dir(aw / 'playerfix-import-01a1c798', 30)
        marked = self.dir(aw / 'tq1635-ed', 30); self.file(aw / 'tq1635-ed' / 'RETAIN', 30)
        busy = self.dir(aw / 'deep', 30); self.file(aw / 'deep' / 'a' / 'b' / 'c' / 'new.txt', 1)
        running = self.dir(aw / 'pictures-coverage-d25cd9e', 30)
        os.symlink(old, aw / 'link-root')
        self.text = 'ReadOnlyPaths=%s/state' % named
        self.used = {running + '/bin/worker.py'}
        remove, kept = r.root_plan(self.text, self.used, self.now)
        self.assertEqual(sorted(remove), sorted([g[2], old]))
        why = dict(kept)
        self.assertEqual(why[g[0]], 'one of the newest generations'); self.assertEqual(why[g[1]], 'one of the newest generations')
        self.assertIn('named', why[named]); self.assertIn('named', why[running])
        self.assertEqual(why[marked], 'holds RETAIN'); self.assertIn('changed', why[busy])
        self.assertEqual(why[str(aw / 'link-root')], 'not a directory')

    def test_a_referenced_old_generation_stays(self):
        aw = self.aw
        for n in ('gen1674-a', 'gen1650-b'): self.dir(aw / n, 20)
        g = self.dir(aw / 'gen1603-c', 40)
        remove, _ = r.root_plan('BindReadOnlyPaths=%s/backend' % g, set(), self.now)
        self.assertEqual(remove, [])


class Checkouts(Base):
    def test_newest_two_and_the_released_stay(self):
        o = self.ops
        live = self.dir(o / 'tasupd-src-1a144758', 9)
        (self.rel / ('1a144758' + '9' * 32)).mkdir()
        old = self.dir(o / 'tasupd-src-73229378', 8)
        n1, n2 = self.dir(o / 'tasupd-src-091ad1e9', 2), self.dir(o / 'tasupd-src-e5ecca2b', 1)
        self.dir(o / 'retention', 50)
        self.assertEqual(r.checkout_plan('', set()), [old])


class Run(Base):
    def test_dry_run_removes_nothing_and_apply_removes_and_logs(self):
        d, aw = self.data, self.aw
        files = [self.file(d / ('qwprogs.dat.pre%d-x' % i), 10 - i) for i in range(4)]
        root = self.dir(aw / 'surfd770-20261018T0000b', 40)
        ro = Path(root) / 'nginx-before'; ro.mkdir(); self.file(ro / 'site.conf', 40); os.chmod(ro, 0o500)
        os.utime(ro, (self.now - 40 * DAY,) * 2)
        os.utime(root, (self.now - 40 * DAY,) * 2)
        log = str(self.ops / 'retention.log')
        out = io.StringIO()
        with contextlib.redirect_stdout(out): rc = r.main(['--log', log])
        self.assertEqual(rc, 0); self.assertIn('would remove: 2 backup copies', out.getvalue())
        for p in files: self.assertTrue(os.path.exists(p))
        self.assertTrue(os.path.isdir(root))
        with contextlib.redirect_stdout(io.StringIO()): rc = r.main(['--apply', '--log', log])
        self.assertEqual(rc, 0)
        self.assertEqual([os.path.exists(p) for p in files], [False, False, True, True])
        self.assertFalse(os.path.exists(root))
        body = Path(log).read_text()
        self.assertIn('would remove', body); self.assertIn('removed: 2 backup copies', body)

    def test_the_log_keeps_its_last_2000_lines(self):
        log = self.ops / 'retention.log'; log.write_text('old\n' * 2500)
        with contextlib.redirect_stdout(io.StringIO()): r.main(['--log', str(log)])
        lines = log.read_text().splitlines()
        self.assertEqual(len(lines), 2000); self.assertIn('would remove', lines[-1])


class Patterns(unittest.TestCase):
    def test_backup_names(self):
        m = lambda n: (r.BACKUP.match(n) or [None, None])[0] and r.BACKUP.match(n).group('name')
        self.assertEqual(m('surfd.db.bak-pre1674-20261120T175713Z'), 'surfd.db')
        self.assertEqual(m('csprogs.dat.pre1648-20261120T101329Z'), 'csprogs.dat')
        self.assertEqual(m('story.txt.pre1681-20261121T014239Z'), 'story.txt')
        self.assertEqual(m('receipts-pre1580r-20261117T215426Z.jsonl'), 'receipts')
        self.assertEqual(m('ftesurf.nginx.pre-p699'), 'ftesurf.nginx')
        self.assertEqual(m('crontab.bak-20261005-ksf'), 'crontab')
        self.assertEqual(m('index.html.pre1700'), 'index.html')
        for n in ('prefs.cfg', 'x.prefs', 'unit.prev', 'preview.png', 'p1702-sweep.py', 'a.backup', 'bakery.txt'):
            self.assertIsNone(r.BACKUP.match(n), n)


if __name__ == '__main__':
    unittest.main()
