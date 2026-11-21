#!/usr/bin/env python3
"""P1702 members-v1: the generation's own member list, hash-verified, keeping tour91-v1's runtime modules and refusing
names that would shadow an importable module. python3 -B tools/test_surfd_guard_members_profile.py"""
import copy
import hashlib
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest

GUARD = runpy.run_path(str(Path(__file__).with_name('surfd_transition_guard.py')))
sha = lambda b: hashlib.sha256(b).hexdigest()


class MembersProfile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); d = Path(os.path.realpath(self.tmp.name))
        self.home, tools = d / 'runtime', d / 'tools'
        files = set(GUARD['TOUR91_FILES']) | {'templates/admin_top10.html'}
        hashes = {}
        for n in sorted(files):
            p = self.home / n; p.parent.mkdir(parents=True, exist_ok=True); body = ('# %s\n' % n).encode()
            p.write_bytes(body); hashes[n] = sha(body)
        tools.mkdir(); ext = {}
        for n in ('momimport', 'momreimport', 'momreplay'):
            (tools / (n + '.py')).write_bytes(b'#\n'); ext[n] = {'origin': str(tools / (n + '.py')), 'sha256': sha(b'#\n')}
        self.m = {'generation': 'a' * 40, 'source_home': str(self.home), 'hashes': hashes, 'target_schema': 26,
                  'runtime_profile': 'members-v1', 'external_python': ext,
                  'routes': {'server': [os.path.realpath(sys.executable), str(self.home / 'surfd.py')]}}

    def tearDown(self): self.tmp.cleanup()

    def check(self, m): return GUARD['manifest_check'](m)

    def refused(self, m, why):
        with self.assertRaisesRegex(ValueError, why): self.check(m)

    def add(self, name, body=b'x\n'):
        m = copy.deepcopy(self.m); p = self.home / name; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body); m['hashes'][name] = sha(body); return m

    def test_an_added_template_is_accepted_and_verified_at_launch(self):
        """P1697's templates/admin_top10.html: no new profile needed."""
        self.check(self.m)
        GUARD['verify_hashes'](self.m)
        (self.home / 'templates/admin_top10.html').write_bytes(b'changed\n')
        with self.assertRaisesRegex(ValueError, 'raw hash mismatch: templates/admin_top10.html'): GUARD['verify_hashes'](self.m)

    def test_every_tour91_runtime_module_must_stay_but_tests_may_go(self):
        m = copy.deepcopy(self.m); del m['hashes']['tournament_pool.py']
        self.refused(m, 'keeps every tour91-v1 runtime module')
        m = copy.deepcopy(self.m); del m['hashes']['test_board.py']
        self.check(m)

    def test_names_that_would_shadow_an_import_are_refused(self):
        # winreg: stdlib but not importable on Linux (the rule is the same on every host)
        for n in ('json.py', 'os.py', 'json/tool.py', 'importlib/x.py', '__init__.py', 'winreg.py', 'flask.py', 'blinker.py',
                  'gunicorn.py', 'ed25519.py', 'rcptcheck.py', 'momimport.py', 'tools/ed25519.py', 'tools/rcptcheck.py',
                  'tools/__init__.py', 'web/__init__.py', 'static/index.html'):
            self.refused(self.add(n), 'added member name')
        for n in ('newmodule_p1702.py', 'web/extra.js', 'pkg_p1702/__init__.py', 'pkg_p1702/core.py', 'assets-p1702/a.json',
                  'tools/newtool_p1702.py'):
            self.check(self.add(n))

    def test_a_package_never_sits_beside_a_module_of_its_name(self):
        """Python imports the package X/ over X.py, which would still hash-verify (review: surfd/__init__.py)."""
        for n in ('surfd/__init__.py', 'admin/views.py', 'mapmanifest/x.py', 'tools/surfd.py'):
            self.refused(self.add(n), 'added member name')
        m = self.add('newpkg_p1702/__init__.py'); body = b'y\n'
        (self.home / 'newpkg_p1702.py').write_bytes(body); m['hashes']['newpkg_p1702.py'] = sha(body)
        self.refused(m, 'added member name')

    def test_the_rule_ignores_what_the_host_has_installed(self):
        """A package installed later must not change the verdict (review: it stopped `close` and `status`)."""
        dep = Path(self.tmp.name) / 'site'; dep.mkdir(); (dep / 'newmodule_p1702.py').write_bytes(b'')
        sys.path.insert(0, str(dep))
        try: self.check(self.add('newmodule_p1702.py'))
        finally: sys.path.remove(str(dep))

    def test_a_member_limit(self):
        m = copy.deepcopy(self.m)
        for i in range(GUARD['MEMBER_LIMIT'] - len(m['hashes']) + 1): m['hashes']['bulk_p1702/f%d.txt' % i] = sha(b'')
        self.refused(m, 'added member name')

    def test_bad_paths_and_suffixes_are_refused(self):
        for n in ('a/../b.py', 'a/./b.py', '.hidden.py', 'web/.x.js', 'a.b.py', 'deep/a/b/c.py', 'x.exe', 'x.sh', 'x', 'a//b.py',
                  'tools/ksfconvert.pyc'):
            m = copy.deepcopy(self.m); m['hashes'][n] = sha(b'')
            self.refused(m, 'added member name')
        m = copy.deepcopy(self.m); m['hashes']['/abs.py'] = sha(b'')
        self.refused(m, 'added member name')

    def test_schema_and_closure_are_still_required(self):
        m = copy.deepcopy(self.m); m['target_schema'] = 25
        self.refused(m, 'members-v1 requires explicit schema26')
        m = copy.deepcopy(self.m); del m['external_python']['momreplay']
        self.refused(m, 'three-converter external source closure')

    def test_tour91_stays_exact(self):
        m = copy.deepcopy(self.m); m['runtime_profile'] = 'tour91-v1'
        self.refused(m, 'exact schema26/profile raw hash set required')
        del m['hashes']['templates/admin_top10.html']
        self.check(m)


if __name__ == '__main__':
    unittest.main()
