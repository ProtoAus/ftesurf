#!/usr/bin/env python3
"""Offline exact-commit KSF shipping falsifiers; no SSH, app or game launch.

Run with --out beneath an owned task root. Requires pwsh 7, git and sh;
Windows genuine flock/SQLite controls also require WSL Ubuntu-22.04. Windows
mode shims do not prove native POSIX executable permissions. Only synthetic
Git repositories/layouts created under --out may be modified here.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
KSF_SET = {'surfd/surfd.py', 'surfd/ksfimport.py', 'surfd/ksfgrab.py',
           'tools/ksfconvert.py', 'tools/ksfreplay_info.py'}


def run(cmd, *, cwd=None, env=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, env=env, text=True, encoding='utf-8',
                       errors='replace', capture_output=True, timeout=120)
    if check and r.returncode:
        raise AssertionError('%r exited %d\n%s\n%s' %
                             (cmd, r.returncode, r.stdout, r.stderr))
    return r


def git(repo, *args):
    return run(['git', '-C', str(repo), *args]).stdout.strip()


def powershell(code, **values):
    env = dict(os.environ, DEPLOY_TEST_TOOLS=str(TOOLS))
    env.update({k: str(v) for k, v in values.items()})
    return run(['pwsh', '-NoProfile', '-NonInteractive', '-Command', code],
               env=env, check=False)


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for tool in ('pwsh', 'git', 'sh'):
            if not shutil.which(tool):
                raise RuntimeError('required offline test tool absent: '+tool)
        cls.ref = git(REPO, 'rev-parse', '--verify', args.ref+'^{commit}')
        cls.ksf_set = set(KSF_SET)
        if run(['git', '-C', str(REPO), 'cat-file', '-e', cls.ref+':surfd/ksfprofile.py'], check=False).returncode == 0:
            cls.ksf_set.add('surfd/ksfprofile.py')
        if run(['git', '-C', str(REPO), 'cat-file', '-e', cls.ref+':surfd/social.py'], check=False).returncode == 0:
            cls.ksf_set.update({'surfd/accounts.py', 'surfd/social.py'})
        if run(['git', '-C', str(REPO), 'cat-file', '-e', cls.ref+':surfd/mapmanifest.py'], check=False).returncode == 0:
            cls.ksf_set.update({'surfd/admin.py', 'surfd/mapmanifest.py', 'surfd/templates/admin_maps.html'})
        if run(['git', '-C', str(REPO), 'cat-file', '-e', cls.ref+':surfd/hidupload.py'], check=False).returncode == 0:
            cls.ksf_set.add('surfd/hidupload.py')
        if run(['git', '-C', str(REPO), 'cat-file', '-e', cls.ref+':surfd/momprofile.py'], check=False).returncode == 0:
            cls.ksf_set.update({'surfd/accounts.py', 'surfd/steamsync.py', 'surfd/momwatch.py',
                                'surfd/momprofile.py', 'tools/momfetch.py', 'tools/msml.py'})

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=self._testMethodName+'-', dir=args.out)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def plan(self, repo=REPO, ref=None, only=(), *, succeeds=True):
        r = powershell('''
$ErrorActionPreference = 'Stop'
. (Join-Path $env:DEPLOY_TEST_TOOLS 'surfd-deploy-plan.ps1')
$p = @{Repo=$env:DEPLOY_TEST_REPO; Ref=$env:DEPLOY_TEST_REF}
if ($env:DEPLOY_TEST_ONLY) { $p.Only = @($env:DEPLOY_TEST_ONLY | ConvertFrom-Json) }
Get-SurfdDeployPlan @p | ConvertTo-Json -Depth 4
''', DEPLOY_TEST_REPO=repo, DEPLOY_TEST_REF=ref or self.ref,
           DEPLOY_TEST_ONLY=json.dumps(list(only)))
        if succeeds:
            self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
            return json.loads(r.stdout.lstrip('\ufeff'))
        self.assertNotEqual(r.returncode, 0, r.stdout+r.stderr)
        return r

    def test_full_and_selective_ksf_sets_and_flattened_destinations(self):
        full = self.plan()
        self.assertEqual(full['Commit'], self.ref)
        self.assertTrue(self.ksf_set <= set(full['Files']))
        self.assertEqual({f for f in full['Files'] if f.startswith('tools/')},
                         {'tools/ksfconvert.py', 'tools/ksfreplay_info.py'} |
                         ({'tools/momfetch.py'} if 'surfd/momprofile.py' in self.ksf_set else set()))
        for entry in self.ksf_set-{'surfd/surfd.py'}:
            p = self.plan(only=[entry, entry])
            self.assertEqual(set(p['Files']), self.ksf_set)
            self.assertEqual(len(p['Files']), len(self.ksf_set))
            self.assertTrue(set(p['Files']) <= set(p['StageFiles']))
            self.assertIn('surfd/test_ksfgrab.py', p['StageFiles'])
            pairs = dict(zip(p['Files'], p['Destinations']))
            self.assertEqual(pairs['surfd/ksfgrab.py'], 'ksfgrab.py')
            self.assertEqual(pairs['tools/ksfconvert.py'], 'tools/ksfconvert.py')
            self.assertEqual(set(p['AddedDependencies']), self.ksf_set-{entry})
        # Schema18 app/profile demand and its worker are one generation. Older
        # commits still allow a narrowly scoped app-only deployment.
        p = self.plan(only=['surfd/surfd.py'])
        self.assertEqual(set(p['Files']), self.ksf_set if 'surfd/ksfprofile.py' in self.ksf_set else {'surfd/surfd.py'})
        self.assertGreater(len(p['StageFiles']), len(p['Files']))

    def test_public_proxy_configuration_is_test_input_not_a_ship_target(self):
        p = self.plan()
        self.assertIn('src/release/ftesurf.nginx', p['StageFiles'])
        self.assertNotIn('src/release/ftesurf.nginx', p['Files'])
        self.assertNotIn('src/release/ftesurf.nginx', p['Destinations'])
        self.plan(only=['src/release/ftesurf.nginx'], succeeds=False)

    def test_unknown_paths_and_refs_refuse(self):
        for path in ('surfd/missing.py', '../surfd/surfd.py', 'tools/runlines_smoke.py',
                     'tools/test_ksfconvert.py', 'surfd'):
            r = self.plan(only=[path], succeeds=False)
            self.assertIn('not a deployable file', r.stderr)
        for ref in ('no-such-ref-offline', '--help'):
            self.plan(ref=ref, succeeds=False)

    def test_guarded_helper_mode_is_narrow_and_requires_no_reload(self):
        for only, no_reload, guard, ok in (
                ('surfd/momgrab.py', True, '/owned/guard', True),
                ('surfd/momgrab.py', False, '/owned/guard', False),
                ('surfd/surfd.py', True, '/owned/guard', False),
                ('surfd/momgrab.py', True, '/owned/../guard', False)):
            r = powershell('''
function ssh { throw 'network forbidden' }
function scp { throw 'network forbidden' }
$p=@{PlanOnly=$true;Ref=$env:DEPLOY_TEST_REF;Only=@($env:DEPLOY_TEST_ONLY);
     GuardStateDir=$env:DEPLOY_TEST_GUARD;NoReload=($env:DEPLOY_TEST_NORELOAD -eq '1')}
& (Join-Path $env:DEPLOY_TEST_TOOLS 'surfd-deploy.ps1') @p
''', DEPLOY_TEST_REF=self.ref, DEPLOY_TEST_ONLY=only, DEPLOY_TEST_GUARD=guard,
                 DEPLOY_TEST_NORELOAD='1' if no_reload else '0')
            self.assertEqual(r.returncode == 0, ok, r.stdout+r.stderr)

    def test_backup_replacement_does_not_rescan_destination(self):
        script = os.environ.get('SURFD_DEPLOY_TEST_SCRIPT', str(TOOLS/'surfd-deploy.ps1'))
        r = powershell('''
$source=Get-Content -Raw $env:DEPLOY_TEST_SCRIPT
$source=$source.Substring($source.IndexOf('# ---- 3. back up'))
$match=[regex]::Match($source,'-Body (\\(\\$body -replace [^\\r\\n]+\\))')
$body="cd REMOTE`nDB=TAG";$Remote='/owned/pubTAG';$dbBackupTag='bak-valid'
$result=Invoke-Expression $match.Groups[1].Value
if ($result -cne "cd /owned/pubTAG`nDB=bak-valid") { throw 'destination rescanned as backup marker' }
'BACKUP_DESTINATION_LITERAL_ACTED'
''', DEPLOY_TEST_SCRIPT=script)
        self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
        self.assertIn('BACKUP_DESTINATION_LITERAL_ACTED', r.stdout)

    def test_guarded_markers_and_double_anchors_refuse(self):
        script = os.environ.get('SURFD_DEPLOY_TEST_SCRIPT', str(TOOLS/'surfd-deploy.ps1'))
        for remote in ('//owned/pub', '/owned/pub__PID__', '/owned/pub__STAGE__'):
            r = powershell('''
$source=Get-Content -Raw $env:DEPLOY_TEST_SCRIPT
$start=$source.IndexOf('if ($GuardStateDir) {')
$gate=$source.Substring($start,$source.IndexOf('if ($PlanOnly)')-$start)
$plan=[pscustomobject]@{Files=@('surfd/momgrab.py')}
$GuardStateDir='/owned/guard';$Remote=$env:DEPLOY_TEST_REMOTE;$NoReload=$true
Invoke-Expression $gate
'INPUT_ACCEPTED'
''', DEPLOY_TEST_SCRIPT=script, DEPLOY_TEST_REMOTE=remote)
            self.assertNotEqual(r.returncode, 0, r.stdout+r.stderr)
            self.assertNotIn('INPUT_ACCEPTED', r.stdout)

    def test_guarded_identity_precedes_destination_backup(self):
        remote = self.root/'source_home'
        (remote/'data').mkdir(parents=True)
        with sqlite3.connect(remote/'data/surfd.db') as db:
            db.execute('CREATE TABLE sentinel(value TEXT)')
            db.execute("INSERT INTO sentinel VALUES ('original')")
        db.close()
        before = {str(p.relative_to(remote)): p.read_bytes() for p in remote.rglob('*') if p.is_file()}
        script = os.environ.get('SURFD_DEPLOY_TEST_SCRIPT', str(TOOLS/'surfd-deploy.ps1'))
        r = powershell('''
$source=Get-Content -Raw $env:DEPLOY_TEST_SCRIPT
$start=[Math]::Min($source.IndexOf('# ---- 3. back up'),$source.IndexOf('# ---- 4. read'))
$section=$source.Substring($start,$source.IndexOf('# ---- 5. copy')-$start)
$Remote=$env:DEPLOY_TEST_REMOTE;$GuardStateDir='/owned/guard';$stage='/owned/stage'
$NoBackup=$false;$dbBackupTag='fixture-backup';$script:PiExit=0
function Step($m) {}
function Fail($m) { throw "BLOCKED:$m" }
function Invoke-PiScript($Name,$Body,[switch]$AllowFail) {
 if ($Name -eq 'identify') { return "PIDFILE=1234`n1234 1 gunicorn witness_wsgi:app`nCOUNT=1" }
 if ($Name -eq 'guarded-master') { $script:PiExit=1; return 'DESTINATION_REFUSED' }
 if ($Name -eq 'backup') {
  [IO.File]::Copy((Join-Path $Remote 'data/surfd.db'),(Join-Path $Remote 'data/surfd.db.fixture-backup'))
  return "BACKUP_OK`nBACKUP_MODE=600 fixture"
 }
 throw 'unexpected operation'
}
try { Invoke-Expression $section; throw 'refusal did not stop transaction' }
catch { if ($_.ToString() -notmatch 'BLOCKED:') { throw } }
'GUARD_REFUSAL_ACTED'
''', DEPLOY_TEST_SCRIPT=script, DEPLOY_TEST_REMOTE=remote)
        self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
        self.assertIn('GUARD_REFUSAL_ACTED', r.stdout)
        after = {str(p.relative_to(remote)): p.read_bytes() for p in remote.rglob('*') if p.is_file()}
        self.assertEqual(set(after), set(before), 'refused destination was written before guard validation')
        self.assertTrue(all(after[k] == before[k] for k in before), 'refused subtree bytes changed')

    def test_planonly_does_not_call_transport_or_create_workspace(self):
        marker = self.root/'transport-called'
        workspaces = Path('C:/FTESurf-worktrees')
        before = set(workspaces.glob('surfdship-*'))
        # Functions shadow executables in this PowerShell process: ANY attempt
        # to call the network is an acted failure, not a real SSH connection.
        r = powershell('''
function ssh { Set-Content $env:DEPLOY_TEST_MARKER ssh; throw 'network forbidden' }
function scp { Set-Content $env:DEPLOY_TEST_MARKER scp; throw 'network forbidden' }
& (Join-Path $env:DEPLOY_TEST_TOOLS 'surfd-deploy.ps1') -PlanOnly -Ref $env:DEPLOY_TEST_REF -Only @('surfd/ksfgrab.py')
''', DEPLOY_TEST_REF=self.ref, DEPLOY_TEST_MARKER=marker)
        self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
        self.assertFalse(marker.exists())
        self.assertEqual(set(workspaces.glob('surfdship-*')), before)
        p = json.loads(r.stdout.lstrip('\ufeff'))
        self.assertEqual(p['Commit'], self.ref)
        self.assertEqual(set(p['Files']), self.ksf_set)

    def fixture_repo(self):
        repo = self.root/'repo'
        repo.mkdir()
        git(repo, 'init', '-q')
        def write(name, text='pass\n'):
            p = repo/name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        def commit():
            files = [p.relative_to(repo).as_posix() for p in repo.rglob('*.py')]
            git(repo, 'add', '--', *files)
            git(repo, '-c', 'user.name=Offline fixture', '-c', 'user.email=fixture@example.invalid',
                '-c', 'commit.gpgsign=false', 'commit', '-qm', 'fixture')
            return git(repo, 'rev-parse', 'HEAD')
        write('surfd/surfd.py')
        write('surfd/ksfimport.py')
        legacy = commit()
        for name in KSF_SET:
            write(name)
        write('tools/test_ksfconvert.py')
        complete = commit()
        return repo, legacy, complete

    def test_profile_schema_app_and_importer_must_ship_together(self):
        repo, legacy, complete = self.fixture_repo()
        (repo/'surfd/ksfprofile.py').write_text('SQL = "profile fixture"\n')
        git(repo, 'add', '--', 'surfd/ksfprofile.py')
        git(repo, '-c', 'user.name=Offline fixture', '-c', 'user.email=fixture@example.invalid',
            '-c', 'commit.gpgsign=false', 'commit', '-qm', 'profile generation')
        for only in ('surfd/surfd.py', 'surfd/ksfimport.py', 'surfd/ksfprofile.py'):
            self.assertEqual(set(self.plan(repo, 'HEAD', [only])['Files']), KSF_SET|{'surfd/ksfprofile.py'})
        self.assertEqual(self.plan(repo, complete, ['surfd/surfd.py'])['Files'], ['surfd/surfd.py'])

    def test_p1117_momprofile_ships_with_its_importers(self):
        repo, _, _ = self.fixture_repo()
        mom = {'surfd/accounts.py', 'surfd/steamsync.py', 'surfd/momwatch.py', 'surfd/momprofile.py',
               'tools/momfetch.py', 'tools/msml.py'}
        for name in sorted(mom):
            (repo/name).parent.mkdir(parents=True, exist_ok=True)
            # Real unconditional imports, not pass-only fetcher placeholders.
            text = (TOOLS/Path(name).name).read_text() if name.startswith('tools/') else 'pass\n'
            (repo/name).write_text(text)
            git(repo, 'add', '--', name)
        git(repo, '-c', 'user.name=Offline fixture', '-c', 'user.email=fixture@example.invalid',
            '-c', 'commit.gpgsign=false', 'commit', '-qm', 'momprofile generation')
        for entry in sorted(mom | {'surfd/surfd.py'}):
            p = self.plan(repo, 'HEAD', [entry])
            self.assertEqual(set(p['Files']), mom | {'surfd/surfd.py'})
            # P1117 review 2: momwatch's fetcher lands flat beside it, as on the Pi.
            destinations = dict(zip(p['Files'], p['Destinations']))
            self.assertEqual(destinations['tools/momfetch.py'], 'momfetch.py')
            self.assertEqual(destinations['tools/msml.py'], 'msml.py')
        # Act the actual installed layout in an empty directory. Test-stage tools
        # or a pre-existing Pi msml must not hide a missing runtime dependency.
        p = self.plan(repo, 'HEAD')
        dest = self.root/'real-flat-runtime'
        dest.mkdir()
        for source, target in zip(p['Files'], p['Destinations']):
            path = dest/target
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(git(repo, 'show', 'HEAD:' + source) + '\n', encoding='utf-8')
        code = ('import pathlib,sys; p=pathlib.Path(sys.argv[1]).resolve(); '
                'sys.path.insert(0,str(p)); import momfetch,msml; '
                'assert pathlib.Path(momfetch.__file__).resolve().parent == p; '
                'assert pathlib.Path(msml.__file__).resolve().parent == p')
        run([sys.executable, '-I', '-B', '-c', code, str(dest)], cwd=dest)

    def test_social_schema_app_accounts_and_ksf_close_both_dependency_groups(self):
        repo, _, _ = self.fixture_repo()
        for name in ('surfd/accounts.py', 'surfd/social.py', 'surfd/ksfprofile.py'):
            (repo/name).write_text('SQL = "synthetic schema20 dependency"\n')
            git(repo, 'add', '--', name)
        git(repo, '-c', 'user.name=Offline fixture', '-c', 'user.email=fixture@example.invalid',
            '-c', 'commit.gpgsign=false', 'commit', '-qm', 'social generation')
        expected = KSF_SET | {'surfd/accounts.py', 'surfd/social.py', 'surfd/ksfprofile.py'}
        for entry in expected:
            p = self.plan(repo, 'HEAD', [entry])
            self.assertEqual(set(p['Files']), expected)
            self.assertEqual(set(p['AddedDependencies']), expected-{entry})
        git(repo, 'rm', '--cached', '--', 'surfd/accounts.py')
        git(repo, '-c', 'user.name=Offline fixture', '-c', 'user.email=fixture@example.invalid',
            '-c', 'commit.gpgsign=false', 'commit', '-qm', 'missing committed account dependency')
        r = self.plan(repo, 'HEAD', ['surfd/social.py'], succeeds=False)
        self.assertIn('social runtime dependency', r.stderr)
        self.assertTrue((repo/'surfd/accounts.py').is_file())

    def test_map_pool_app_admin_and_template_ship_together(self):
        repo, _, _ = self.fixture_repo()
        entries = {'surfd/surfd.py', 'surfd/admin.py', 'surfd/mapmanifest.py',
                   'surfd/templates/admin_maps.html'}
        for name in entries-{'surfd/surfd.py'}:
            path = repo/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('synthetic policy generation\n')
            git(repo, 'add', '--', name)
        git(repo, '-c', 'user.name=Offline fixture', '-c', 'user.email=fixture@example.invalid',
            '-c', 'commit.gpgsign=false', 'commit', '-qm', 'map pool generation')
        for entry in entries:
            p = self.plan(repo, 'HEAD', [entry])
            self.assertEqual(set(p['Files']), entries)
            self.assertEqual(set(p['AddedDependencies']), entries-{entry})
        git(repo, 'rm', '--cached', '--', 'surfd/templates/admin_maps.html')
        git(repo, '-c', 'user.name=Offline fixture', '-c', 'user.email=fixture@example.invalid',
            '-c', 'commit.gpgsign=false', 'commit', '-qm', 'missing committed map dependency')
        result = self.plan(repo, 'HEAD', ['surfd/surfd.py'], succeeds=False)
        self.assertIn('map-pool runtime dependency', result.stderr)
        self.assertTrue((repo/'surfd/templates/admin_maps.html').is_file())

    def test_legacy_ref_and_committed_dependency_not_working_tree(self):
        repo, legacy, complete = self.fixture_repo()
        self.assertEqual(set(self.plan(repo, legacy)['Files']),
                         {'surfd/surfd.py', 'surfd/ksfimport.py'})
        self.assertEqual(set(self.plan(repo, legacy, ['surfd/ksfimport.py'])['Files']),
                         {'surfd/ksfimport.py'})
        self.assertEqual(set(self.plan(repo, complete)['Files']), KSF_SET)
        git(repo, 'update-index', '--force-remove', 'tools/ksfreplay_info.py')
        git(repo, '-c', 'user.name=Offline fixture', '-c', 'user.email=fixture@example.invalid',
            '-c', 'commit.gpgsign=false', 'commit', '-qm', 'missing committed dependency')
        self.assertTrue((repo/'tools/ksfreplay_info.py').is_file())
        r = self.plan(repo, 'HEAD', ['surfd/ksfgrab.py'], succeeds=False)
        self.assertIn('runtime dependency', r.stderr)
        # Immutable full-ref plan survives a symbolic ref advancing after plan.
        git(repo, 'update-ref', 'refs/heads/planned', complete)
        p = self.plan(repo, 'planned')
        git(repo, 'update-ref', 'refs/heads/planned', legacy)
        self.assertEqual(p['Commit'], complete)
        self.assertEqual(set(self.plan(repo, p['Commit'])['Files']), KSF_SET)

    def test_flattened_commit_layout_import_control_and_collector_api(self):
        p = self.plan()
        layout = self.root/'flat'
        layout.mkdir()
        # Preserve ONLY commit bytes at planned installation destinations.
        for src, dst in zip(p['Files'], p['Destinations']):
            dest = layout/dst
            dest.parent.mkdir(parents=True, exist_ok=True)
            blob = subprocess.check_output(['git', '-C', str(REPO), 'show', p['Commit']+':'+src])
            dest.write_bytes(blob)
        env = dict(os.environ, SURFD_HOME=str(self.root/'home'),
                   PYTHONDONTWRITEBYTECODE='1', PYTHONPATH='')
        probe = '''import ksfgrab as G; from pathlib import Path
assert Path(G.C.__file__).resolve().parent == Path.cwd()/'tools'
assert Path(G.C.K.__file__).resolve().parent == Path.cwd()/'tools'
print('FLAT_CODEC_ACTED')'''
        r = run([sys.executable, '-c', probe], cwd=layout, env=env)
        self.assertIn('FLAT_CODEC_ACTED', r.stdout)
        for leaf in ('ksfconvert.py', 'ksfreplay_info.py'):
            dest = layout/'tools'/leaf
            held = dest.with_suffix('.held')
            dest.rename(held)
            try:
                r = run([sys.executable, '-c', probe], cwd=layout, env=env, check=False)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn('ModuleNotFoundError', r.stderr)
            finally:
                held.rename(dest)
        # Existing real SQLite/index and Flask test-client suite. No socket,
        # HTTP listener, upstream request or game is launched by this suite.
        output = args.out/'flattened-collector'
        r = run([sys.executable, 'test_ksfgrab.py', '--out', str(output)], cwd=layout, env=env)
        (args.out/'flattened-collector.log').write_text(r.stdout+r.stderr)
        count = re.search(r'Ran (\d+) tests', r.stderr)
        self.assertIsNotNone(count, r.stderr)
        self.assertGreaterEqual(int(count[1]), 16)
        self.assertIn('OK', r.stderr)

    @staticmethod
    def posix(path):
        if os.name == 'nt':
            return run(['cygpath', '-u', str(path)]).stdout.strip()
        return str(path)

    def shell_body(self, marker):
        r = powershell('''
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile((Join-Path $env:DEPLOY_TEST_TOOLS 'surfd-deploy.ps1'), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
$b=@($ast.FindAll({param($n) $n -is [System.Management.Automation.Language.StringConstantExpressionAst] -and $n.Value.Contains($env:DEPLOY_TEST_BODY_MARKER)}, $true))
if ($b.Count -ne 1) { throw 'expected exactly one shell body' }
@{Body=$b[0].Value} | ConvertTo-Json
''', DEPLOY_TEST_BODY_MARKER=marker)
        self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
        return json.loads(r.stdout.lstrip('\ufeff'))['Body'].replace('\r\n', '\n')

    def test_actual_suite_shell_passes_args_and_propagates_all_failures(self):
        stage = self.root/'stage'
        (stage/'surfd').mkdir(parents=True)
        (stage/'tools').mkdir()
        (stage/'tmp').mkdir()
        (stage/'OWNER.md').write_text('Owned synthetic deploy-suite fixture\n')
        (stage/'surfd/test_ksfgrab.py').write_text('''import os, pathlib, sys
assert sys.argv[1]=='--out'
p=pathlib.Path(sys.argv[2]); assert p.name=='ksfgrab' and p.parent.name=='tmp'
assert any((x/'OWNER.md').is_file() for x in p.parents)
print('GRAB_ARGS_ACTED')
sys.exit(int(os.environ.get('GRAB_FAIL','0')))
''')
        (stage/'surfd/test_ksftopup.py').write_text('''import os
home=os.environ['SURFD_HOME'].replace('\\\\','/')
tmp=os.environ['TMPDIR'].replace('\\\\','/')
assert home.rsplit('/',1)[0]==tmp, (home,tmp)
print('TOPUP_OWNED_HOME_ACTED')
''')
        (stage/'surfd/test_social.py').write_text('''import os, sys
print('SOCIAL_SUITE_ACTED')
sys.exit(int(os.environ.get('SOCIAL_FAIL','0')))
''')
        (stage/'tools/test_ksfconvert.py').write_text('''import os, sys
print('CONVERTER_ACTED')
sys.exit(int(os.environ.get('CONVERT_FAIL','0')))
''')
        # sh on Windows (MSYS) needs POSIX paths inside the shell body. Convert
        # via cygpath if present; Linux passes its absolute path unchanged.
        def posix(path):
            if os.name == 'nt':
                return run(['cygpath', '-u', str(path)]).stdout.strip()
            return str(path)
        body = self.shell_body('cd STAGE/surfd').replace('STAGE', posix(stage))
        shell = self.root/'suite.sh'
        shell.write_text(body, newline='\n')
        # Use the current Python interpreter, not an accidentally different
        # python3 on PATH. This wrapper is confined to our synthetic fixture.
        bindir = self.root/'bin'
        bindir.mkdir()
        shim = bindir/'python3'
        shim.write_text("#!/bin/sh\nexec '"+posix(Path(sys.executable))+"' \"$@\"\n", newline='\n')
        shim.chmod(0o700)
        for failure in ('', 'GRAB_FAIL', 'CONVERT_FAIL', 'SOCIAL_FAIL'):
            env = dict(os.environ)
            # Setting the POSIX PATH inside sh avoids Windows PATH rewriting.
            command = 'PATH="'+posix(bindir)+':$PATH"; export PATH; sh "'+posix(shell)+'"'
            if failure:
                command = failure+'=1; export '+failure+'; '+command
            r = run(['sh', '-c', command], env=env, check=False)
            (args.out/('suite-'+(failure or 'pass')+'.log')).write_text(r.stdout+r.stderr)
            self.assertEqual(r.returncode, 1 if failure else 0, r.stdout+r.stderr)
            if not failure:
                for acted in ('GRAB_ARGS_ACTED', 'CONVERTER_ACTED', 'TOPUP_OWNED_HOME_ACTED', 'SOCIAL_SUITE_ACTED'):
                    self.assertIn(acted, r.stdout)
            else:
                self.assertIn('FAILED', r.stdout)

    def test_publication_query_failure_refuses_before_transport_or_workspace(self):
        repo, _, complete = self.fixture_repo()
        for name in ('surfd-deploy.ps1', 'surfd-deploy-plan.ps1'):
            shutil.copyfile(TOOLS/name, repo/'tools'/name)
        marker = self.root/'transport-called'
        workspaces = Path('C:/FTESurf-worktrees')
        before = set(workspaces.glob('surfdship-*'))
        r = powershell('''
function ssh { Set-Content $env:DEPLOY_TEST_MARKER ssh; throw 'network forbidden' }
function scp { Set-Content $env:DEPLOY_TEST_MARKER scp; throw 'network forbidden' }
function New-Item { Set-Content $env:DEPLOY_TEST_MARKER workspace; throw 'workspace forbidden' }
& (Join-Path $env:DEPLOY_TEST_REPO 'tools/surfd-deploy.ps1') -Ref $env:DEPLOY_TEST_REF
''', DEPLOY_TEST_REPO=repo, DEPLOY_TEST_REF=complete, DEPLOY_TEST_MARKER=marker)
        self.assertNotEqual(r.returncode, 0, r.stdout+r.stderr)
        self.assertIn('could not establish publication', r.stdout+r.stderr)
        self.assertFalse(marker.exists())
        self.assertEqual(set(workspaces.glob('surfdship-*')), before)

    def test_actual_destination_hash_refuses_text_filter_equivalence(self):
        repo = self.root/'destination'
        repo.mkdir()
        git(repo, 'init', '-q')
        (repo/'.gitattributes').write_text('*.py text eol=lf\n')
        (repo/'app.py').write_bytes(b'print("fixture")\r\n')
        git(repo, 'add', '--', '.gitattributes', 'app.py')
        want = git(repo, 'rev-parse', ':app.py')
        self.assertEqual(git(repo, 'hash-object', 'app.py'), want)  # Old filtered control ACTED.
        self.assertNotEqual(git(repo, 'hash-object', '--no-filters', '--', 'app.py'), want)
        body = self.shell_body('VERIFY_BAD=').replace('__REMOTE__', self.posix(repo))
        body = body.replace('__MANIFEST__', 'app.py '+want+' 644')
        shell = self.root/'verify.sh'
        shell.write_text(('stat() { echo 644; }\n' if os.name == 'nt' else '')+body, newline='\n')
        r = run(['sh', self.posix(shell)], check=False)
        self.assertEqual(r.returncode, 1, r.stdout+r.stderr)
        self.assertIn('VERIFY_BAD=1', r.stdout)
        self.assertIn('DIFFERS app.py', r.stdout)
        (repo/'app.py').write_bytes(b'print("fixture")\n')
        r = run(['sh', self.posix(shell)])
        self.assertIn('VERIFY_BAD=0', r.stdout)

    def test_actual_reload_refuses_stale_workers_logs_master_and_health(self):
        body = self.shell_body('SIGHUP_SENT=')
        for scenario in ('fresh', 'draining', 'rotated', 'stale', 'historical', 'wrong-ready-pid',
                         'master-changed', 'unhealthy', 'slow-health', 'ps-failed', 'signal-failed'):
            remote = self.root/scenario
            (remote/'logs').mkdir(parents=True)
            (remote/'surfd.pid').write_text('100\n')
            (remote/'step').write_text('0\n')
            (remote/'elapsed').write_text('0\n')
            (remote/'logs/surfd.log').write_text('old INFO [101] surfd ready (db=fixture)\n')
            # All process/signal/HTTP actors are shell functions. No process is
            # signalled, no socket is opened and fake sleeps never wait.
            mocks = '''
SCENARIO=__SCENARIO__
cd __REMOTE__
awk() {
  if [ "${2-}" = /proc/uptime ]; then cat elapsed
  else command awk "$@"; fi
}
ps() {
  [ "$SCENARIO" != ps-failed ] || return 7
  if [ "$1" = -o ]; then
    echo 'gunicorn: master [surfd:app]'; return
  fi
  echo '100 1 gunicorn: master [surfd:app]'
  step=$(cat step)
  if [ "$step" = 0 ] || [ "$SCENARIO" = stale ]; then
    echo '101 100 gunicorn: worker [surfd:app]'
  else
    if [ "$SCENARIO" = draining ] && [ "$step" = 1 ]; then
      echo '101 100 gunicorn: worker [surfd:app]'
    fi
    echo '102 100 gunicorn: worker [surfd:app]'
  fi
}
kill() {
  echo SIGNAL_ACTED > signal
  [ "$SCENARIO" != signal-failed ] || return 9
}
sleep() {
  elapsed=$(cat elapsed); echo "$((elapsed+$1))" > elapsed
  step=$(cat step); step=$((step+1)); echo "$step" > step
  if [ "$step" = 1 ]; then
    case "$SCENARIO" in
      rotated) mv logs/surfd.log logs/surfd.log.1; echo 'new INFO [102] surfd ready (db=fixture)' > logs/surfd.log ;;
      master-changed) echo 200 > surfd.pid ;;
      historical|stale) ;;
      wrong-ready-pid) echo 'new INFO [101] surfd ready (db=fixture)' >> logs/surfd.log ;;
      *) echo 'new INFO [102] surfd ready (db=fixture)' >> logs/surfd.log ;;
    esac
  fi
}
curl() {
  cat step > health-step
  if [ "$SCENARIO" = slow-health ]; then
    elapsed=$(cat elapsed); echo "$((elapsed+$3))" > elapsed
    echo '{"ok":false}'
  elif [ "$SCENARIO" = unhealthy ]; then echo '{"ok":false}'
  else echo '{"ok":true}'; fi
}
'''.replace('__SCENARIO__', scenario).replace('__REMOTE__', self.posix(remote))
            shell = remote/'reload.sh'
            script = body.replace('__REMOTE__', self.posix(remote)).replace('__MASTER__', '100')
            script = script.replace('cd REMOTE', 'cd '+self.posix(remote))  # Prior-script red control.
            shell.write_text(mocks+script, newline='\n')
            r = run(['sh', self.posix(shell)], check=False)
            (args.out/('reload-'+scenario+'.log')).write_text(r.stdout+r.stderr)
            with self.subTest(scenario=scenario):
                self.assertLessEqual(int((remote/'elapsed').read_text()), 60)
                if scenario in ('fresh', 'draining', 'rotated'):
                    self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
                    self.assertIn('RELOAD_VERIFIED=100 worker=102', r.stdout)
                    self.assertEqual(int((remote/'health-step').read_text()),
                                     2 if scenario == 'draining' else 1)
                else:
                    self.assertNotEqual(r.returncode, 0, r.stdout+r.stderr)
                    self.assertNotIn('RELOAD_VERIFIED=', r.stdout)
                    if scenario not in ('unhealthy', 'slow-health'):
                        self.assertFalse((remote/'health-step').exists())

    @staticmethod
    def linux_path(path):
        if os.name == 'nt':
            return '/mnt/'+path.drive[0].lower()+'/'+path.as_posix()[3:]
        return str(path)

    def linux_run(self, body, *, check=True):
        shell = self.root/'linux-probe.sh'
        environment = "TMPDIR='"+self.linux_path(self.root)+"'; export TMPDIR\n"
        environment += 'PYTHONDONTWRITEBYTECODE=1; export PYTHONDONTWRITEBYTECODE\n'
        shell.write_text(environment+body, newline='\n')
        cmd = ['sh', self.linux_path(shell)]
        if os.name == 'nt':
            cmd = ['wsl', '-d', 'Ubuntu-22.04', '--', *cmd]
        return run(cmd, check=check)

    def copy_body(self, stage, remote, tag):
        return (self.shell_body('COPIED=')
                .replace('/tmp/surfd-sweep.lock', self.linux_path(self.root/'sweep.lock'))
                .replace('__REMOTE__', self.linux_path(remote))
                .replace('__STAGE__', self.linux_path(stage))
                .replace('__TAG__', tag)
                .replace('__FILES__', 'surfd/run.sh run.sh 755\nsurfd/not-executable.sh not-executable.sh 644'))

    def test_actual_install_modes_and_file_backup_collision(self):
        stage = self.root/'stage'
        (stage/'surfd').mkdir(parents=True)
        remote = self.root/'remote'
        remote.mkdir()
        for name in ('run.sh', 'not-executable.sh'):
            (stage/'surfd'/name).write_text('#!/bin/sh\necho ENTRYPOINT_ACTED\n')
            (remote/name).write_text('original '+name+'\n')
        # Windows drvfs has no POSIX mode metadata. The shim records install's
        # requested mode while copying real bytes; native Linux uses real modes.
        shim = """
install() {
  command install "$@"
  for last; do :; done
  echo "$2" > "$last.mode"
}
mv() { command mv "$@"; command mv "$2.mode" "$3.mode"; }
stat() {
  if [ "$1" = -c ] && [ "$2" = '%a' ]; then
    for last; do :; done
    cat "$last.mode"
  else command stat "$@"; fi
}
""" if os.name == 'nt' else ''
        copy = self.copy_body(stage, remote, 'pre-first')
        r = self.linux_run(shim+copy)
        self.assertIn('COPIED=2', r.stdout)
        manifest = []
        for name, mode in (('run.sh', '755'), ('not-executable.sh', '644')):
            h = git(REPO, 'hash-object', '--no-filters', '--', str(remote/name))
            manifest.append(name+' '+h+' '+mode)
        verify = (self.shell_body('VERIFY_BAD=')
                  .replace('__REMOTE__', self.linux_path(remote))
                  .replace('__MANIFEST__', '\n'.join(manifest)))
        r = self.linux_run(shim+verify)
        self.assertIn('VERIFY_BAD=0', r.stdout)
        if os.name == 'nt':
            (remote/'run.sh.mode').write_text('644\n')
        else:
            (remote/'run.sh').chmod(0o644)
        r = self.linux_run(shim+verify, check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('MODE_DIFFERS run.sh', r.stdout)
        original = (remote/'run.sh.pre-first').read_bytes()
        r = self.linux_run(shim+copy, check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('REFUSE_BACKUP_EXISTS', r.stdout)
        self.assertEqual((remote/'run.sh.pre-first').read_bytes(), original)
        r = self.linux_run(shim+self.copy_body(stage, remote, 'pre-second'))
        self.assertIn('COPIED=2', r.stdout)
        if os.name != 'nt':
            r = self.linux_run('cd '+self.linux_path(remote)+'; ./run.sh')
            self.assertIn('ENTRYPOINT_ACTED', r.stdout)
        (args.out/'install-backup.log').write_text(
            'COPIED=2; VERIFY_BAD=0; wrong-mode refused; same-tag refused; distinct-tag COPIED=2\n'+
            ('Windows: install/stat mode shims; native executable proof PENDING\n' if os.name == 'nt'
             else 'Native POSIX entrypoint executed: ENTRYPOINT_ACTED\n'))

    def test_plan_modes_are_exact_commit_not_suffix_or_worktree(self):
        repo, _, _ = self.fixture_repo()
        for name in ('run.sh', 'not-executable.sh'):
            (repo/'surfd'/name).write_text('#!/bin/sh\necho acted\n')
            git(repo, 'add', '--', 'surfd/'+name)
        git(repo, 'update-index', '--chmod=+x', 'surfd/run.sh')
        git(repo, 'update-index', '--chmod=-x', 'surfd/not-executable.sh')
        git(repo, '-c', 'user.name=Offline fixture', '-c', 'user.email=fixture@example.invalid',
            '-c', 'commit.gpgsign=false', 'commit', '-qm', 'modes')
        ref = git(repo, 'rev-parse', 'HEAD')
        git(repo, 'update-index', '--chmod=-x', 'surfd/run.sh')
        plan = self.plan(repo, ref)
        modes = dict(zip(plan['Files'], plan['Modes']))
        self.assertEqual(modes['surfd/run.sh'], '755')
        self.assertEqual(modes['surfd/not-executable.sh'], '644')

    def test_actual_database_backup_exclusive_collision(self):
        import sqlite3
        remote = self.root/'remote'
        (remote/'data').mkdir(parents=True)
        db = sqlite3.connect(remote/'data/surfd.db')
        db.execute('create table witness(n)')
        db.execute('insert into witness values(1)')
        db.commit(); db.close()
        body = (self.shell_body('import os, sqlite3')
                .replace('REMOTE', self.linux_path(remote)).replace('TAG', 'bak-first'))
        r = self.linux_run(body)
        self.assertIn('BACKUP_OK', r.stdout)
        db = sqlite3.connect(remote/'data/surfd.db')
        db.execute('update witness set n=2'); db.commit(); db.close()
        r = self.linux_run(body, check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn('BACKUP_OK', r.stdout)
        db = sqlite3.connect(remote/'data/surfd.db.bak-first')
        self.assertEqual(db.execute('select n from witness').fetchone()[0], 1)
        db.close()
        r = self.linux_run(body.replace('bak-first', 'bak-second'))
        self.assertIn('BACKUP_OK', r.stdout)
        db = sqlite3.connect(remote/'data/surfd.db.bak-second')
        self.assertEqual(db.execute('select n from witness').fetchone()[0], 2)
        db.close()
        (args.out/'db-backup.log').write_text('BACKUP_OK first; same-tag FileExistsError; original n=1 preserved; distinct-tag BACKUP_OK n=2\n')

    def test_actual_transaction_holder_interleaving_eof_and_timeout(self):
        holder = self.root/'holder.sh'
        holder.write_text(self.shell_body('flock -w 120 8').replace(
            '/tmp/surfd-deploy.lock', self.linux_path(self.root/'transaction.lock')),
            newline='\n')
        # The actual copy bodies are the payloads, not a reimplementation.
        stage = self.root/'stage'
        (stage/'surfd').mkdir(parents=True)
        remote = self.root/'remote'
        remote.mkdir()
        for name in ('run.sh', 'not-executable.sh'):
            (stage/'surfd'/name).write_text('A bytes\n')
        a = self.root/'copy-a.sh'; a.write_text(self.copy_body(stage, remote, 'pre-a'), newline='\n')
        b = self.root/'copy-b.sh'; b.write_text(self.copy_body(stage, remote, 'pre-b'), newline='\n')
        verify = self.root/'verify-a.sh'
        manifest = '\n'.join(name+' '+git(REPO, 'hash-object', '--no-filters', '--',
                                       str(stage/'surfd'/name))+' '+mode
                             for name, mode in (('run.sh', '755'), ('not-executable.sh', '644')))
        verify_body = (self.shell_body('VERIFY_BAD=')
                       .replace('__REMOTE__', self.linux_path(remote))
                       .replace('__MANIFEST__', manifest))
        # WSL drvfs lacks modes; hash checking remains real in this schedule.
        mode_shim = 'stat() { case "$4" in run.sh) echo 755;; *) echo 644;; esac; }\n' if os.name == 'nt' else ''
        verify.write_text(mode_shim+verify_body, newline='\n')
        fast_holder = self.root/'fast-holder.sh'
        fast_holder.write_text(holder.read_text().replace('flock -w 120 8', 'flock -w 1 8'), newline='\n')
        driver = self.root/'driver.py'
        driver.write_text("""import atexit, subprocess, threading, pathlib
root=pathlib.Path(__file__).parent
children=[]
def start(name='holder.sh'):
 p=subprocess.Popen(['sh',str(root/name)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 children.append(p)
 return p
def cleanup():
 for p in children:
  if not p.stdin.closed: p.stdin.close()
  p.wait(timeout=5)
atexit.register(cleanup)
def ack(p, token):
 p.stdin.write(token+'\\n'); p.stdin.flush()
 assert p.stdout.readline().strip()=='LOCK_ACK='+token
A=start(); assert A.stdout.readline().strip()=='LOCK_ACQUIRED'
subprocess.run(['sh',str(root/'copy-a.sh')],check=True)
subprocess.run(['sh',str(root/'verify-a.sh')],check=True)
ack(A,'A_VERIFIED')
B=start(); acquired=threading.Event()
def deploy_b():
 assert B.stdout.readline().strip()=='LOCK_ACQUIRED'
 acquired.set()
 subprocess.run(['sh',str(root/'copy-b.sh')],check=True)
thread=threading.Thread(target=deploy_b,daemon=True); thread.start()
# The actual holder's acquisition deadline must refuse while A holds it.
probe=start('fast-holder.sh')
out,err=probe.communicate(timeout=5)
assert probe.returncode==1 and 'LOCK_ACQUIRED' not in out and not acquired.is_set()
print('ACTUAL_HOLDER_TIMEOUT_REFUSED',flush=True)
assert (root/'remote/run.sh').read_text()=='A bytes\\n'
print('B_ATTEMPTED_AND_BLOCKED_AFTER_A_VERIFY',flush=True)
for name in ('run.sh','not-executable.sh'): (root/'stage/surfd'/name).write_text('B bytes\\n')
ack(A,'A_RELOAD_ACCEPTED'); ack(A,'ACCEPTED:'+('a'*40)+':invocation-a')
assert not acquired.is_set() and (root/'remote/run.sh').read_text()=='A bytes\\n'
print('A_RECEIPT_WITH_A_BYTES',flush=True)
A.stdin.close(); assert A.wait(timeout=5)==0
thread.join(timeout=10); assert not thread.is_alive() and acquired.is_set()
assert (root/'remote/run.sh').read_text()=='B bytes\\n'
print('B_INSTALLED_ONLY_AFTER_A_RECEIPT_AND_EOF',flush=True)
B.stdin.close(); assert B.wait(timeout=5)==0
# Failure/disconnect uses the same EOF path: no stale lock or signal.
C=start(); assert C.stdout.readline().strip()=='LOCK_ACQUIRED'
C.stdin.close(); assert C.wait(timeout=5)==0
D=start(); assert D.stdout.readline().strip()=='LOCK_ACQUIRED'
ack(D,'AFTER_FAILURE_ACTED'); D.stdin.close(); assert D.wait(timeout=5)==0
print('EOF_FAILURE_RELEASE_ACTED',flush=True)
""", newline='\n')
        r = self.linux_run('python3 '+self.linux_path(driver))
        for witness in ('VERIFY_BAD=0', 'ACTUAL_HOLDER_TIMEOUT_REFUSED',
                        'B_ATTEMPTED_AND_BLOCKED_AFTER_A_VERIFY', 'A_RECEIPT_WITH_A_BYTES',
                        'B_INSTALLED_ONLY_AFTER_A_RECEIPT_AND_EOF', 'EOF_FAILURE_RELEASE_ACTED'):
            self.assertIn(witness, r.stdout)
        (args.out/'transaction.log').write_text(r.stdout+r.stderr)

    def test_actual_transaction_ack_refuses_disconnected_holder(self):
        # Evaluate the exact PowerShell guard functions, using only our own
        # synthetic child process. No SSH executable is launched.
        r = powershell('''
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile((Join-Path $env:DEPLOY_TEST_TOOLS 'surfd-deploy.ps1'), [ref]$tokens, [ref]$errors)
foreach ($name in @('Read-DeployLockLine','Assert-DeployLock')) {
 $f=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name}, $true)
 Invoke-Expression $f.Extent.Text
}
$script:DeployLock=[System.Diagnostics.Process]::new()
$i=[System.Diagnostics.ProcessStartInfo]::new('pwsh')
$i.UseShellExecute=$false; $i.RedirectStandardInput=$true; $i.RedirectStandardOutput=$true
$i.ArgumentList.Add('-NoProfile'); $i.ArgumentList.Add('-Command'); $i.ArgumentList.Add('exit 0')
$script:DeployLock.StartInfo=$i
[void]$script:DeployLock.Start(); $script:DeployLock.WaitForExit()
try { Assert-DeployLock -Token ('ACCEPTED:'+('a'*40)+':invocation-a'); throw 'BAD_RECEIPT' }
catch { if ($_.ToString() -match 'holder exited') { 'DISCONNECTED_HOLDER_REFUSED_ACTED' } else { throw } }
finally { $script:DeployLock.Dispose() }
''')
        self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
        self.assertIn('DISCONNECTED_HOLDER_REFUSED_ACTED', r.stdout)
        (args.out/'disconnected-holder.log').write_text(r.stdout+r.stderr)

    def test_actual_receipt_failure_retains_stage_and_cleanup_is_post_acceptance(self):
        for scenario in ('ack-failure', 'cleanup-failure', 'cleanup-result-lost', 'success'):
            with self.subTest(scenario=scenario):
                fixture = self.root/scenario
                fixture.mkdir()
                r = powershell('''
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile((Join-Path $env:DEPLOY_TEST_TOOLS 'surfd-deploy.ps1'), [ref]$tokens, [ref]$errors)
foreach ($name in @('Read-DeployLockLine','Assert-DeployLock')) {
 $f=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name}, $true)
 Invoke-Expression $f.Extent.Text
}
$transaction=$ast.Find({param($n) $n -is [System.Management.Automation.Language.TryStatementAst] -and $n.Body.Extent.Text -match 'ACCEPTED:'}, $true)
$cleanup=$transaction.Body.Statements | Where-Object { $_.Extent.Text -match '^Step "8\\.' } | Select-Object -First 1
$accept=$transaction.Body.Statements | Where-Object { $_.Extent.Text -match '^Assert-DeployLock -Token "ACCEPTED:' } | Select-Object -First 1
if (-not $cleanup -or -not $accept) { throw 'receipt tail not found' }
$start=[Math]::Min($cleanup.Extent.StartOffset,$accept.Extent.StartOffset)
$tail=$ast.Extent.Text.Substring($start,$transaction.Body.Extent.EndOffset-$start-1)
$work=Join-Path $env:DEPLOY_TEST_FIXTURE work
$stage=Join-Path $env:DEPLOY_TEST_FIXTURE stage
[void](New-Item -ItemType Directory -Path $work,$stage)
Set-Content (Join-Path $work OWNER.md) 'synthetic receipt owner'
Set-Content (Join-Path $stage suite.out) 'retained suite witness'
$commit='a'*40; $nonce='synthetic-invocation'; $sha='aaaaaaa'
$PiHost='synthetic.invalid'; $Remote='synthetic-remote'
$backupTag='pre-synthetic'; $dbBackupTag='bak-synthetic'
function Step { param($m) }
function Fail { param($m) throw $m }
function Invoke-PiSsh {
 param($Cmd)
 if ($env:DEPLOY_TEST_SCENARIO -eq 'cleanup-failure') { $script:PiExit=1 }
 else { Remove-Item -LiteralPath $stage -Recurse; $script:PiExit=if ($env:DEPLOY_TEST_SCENARIO -eq 'cleanup-result-lost') {255} else {0} }
}
$script:DeployLock=[System.Diagnostics.Process]::new()
$i=[System.Diagnostics.ProcessStartInfo]::new('pwsh')
$i.UseShellExecute=$false; $i.RedirectStandardInput=$true; $i.RedirectStandardOutput=$true
$i.ArgumentList.Add('-NoProfile'); $i.ArgumentList.Add('-Command')
$child=if ($env:DEPLOY_TEST_SCENARIO -eq 'ack-failure') { 'exit 0' } else {
 'while (($line=[Console]::In.ReadLine()) -ne $null) { [Console]::Out.WriteLine("LOCK_ACK=$line"); [Console]::Out.Flush() }'
}
$i.ArgumentList.Add($child); $script:DeployLock.StartInfo=$i
[void]$script:DeployLock.Start()
if ($env:DEPLOY_TEST_SCENARIO -eq 'ack-failure') { $script:DeployLock.WaitForExit() }
try {
 $caught=$false
 try { $output=Invoke-Expression $tail 6>&1 3>&1 | Out-String }
 catch { $caught=$true; if ($_.ToString() -notmatch 'holder exited') { throw } }
 $owner=Get-Content (Join-Path $work OWNER.md) -Raw
 if ($env:DEPLOY_TEST_SCENARIO -eq 'ack-failure') {
  if (-not $caught -or -not (Test-Path (Join-Path $stage suite.out)) -or $owner -match 'Accepted UTC') { throw 'unaccepted stage lost or receipt recorded' }
  'PRE_ACCEPTANCE_FAILURE_RETAINS_STAGE_ACTED'
 } elseif ($env:DEPLOY_TEST_SCENARIO -like 'cleanup-*') {
  $exists=Test-Path (Join-Path $stage suite.out)
  $expected=($env:DEPLOY_TEST_SCENARIO -eq 'cleanup-failure')
  if ($caught -or $exists -ne $expected -or $owner -notmatch 'remote stage cleanup unconfirmed' -or $output -notmatch 'DEPLOYED' -or $output -notmatch 'unconfirmed') { throw 'accepted unknown cleanup outcome misreported' }
  if ($expected) { 'ACCEPTED_CLEANUP_FAILURE_UNCONFIRMED_ACTED' } else { 'ACCEPTED_LOST_CLEANUP_RESULT_UNCONFIRMED_ACTED' }
 } else {
  if ($caught -or (Test-Path $stage) -or $owner -notmatch 'remote stage removed' -or $output -notmatch 'DEPLOYED') { throw 'accepted success did not clean/report' }
  'ACCEPTED_SUCCESS_REMOVES_STAGE_ACTED'
 }
} finally {
 if (-not $script:DeployLock.HasExited) { $script:DeployLock.StandardInput.Close(); if (-not $script:DeployLock.WaitForExit(5000)) { throw 'own fixture holder did not exit' } }
 $script:DeployLock.Dispose()
}
''', DEPLOY_TEST_FIXTURE=fixture, DEPLOY_TEST_SCENARIO=scenario)
                (args.out/('receipt-'+scenario+'.log')).write_text(r.stdout+r.stderr)
                self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
                witness = {'ack-failure':'PRE_ACCEPTANCE_FAILURE_RETAINS_STAGE_ACTED',
                           'cleanup-failure':'ACCEPTED_CLEANUP_FAILURE_UNCONFIRMED_ACTED',
                           'cleanup-result-lost':'ACCEPTED_LOST_CLEANUP_RESULT_UNCONFIRMED_ACTED',
                           'success':'ACCEPTED_SUCCESS_REMOVES_STAGE_ACTED'}[scenario]
                self.assertIn(witness, r.stdout)

    def test_powershell_sources_parse(self):
        r = powershell('''
foreach ($name in @('surfd-deploy.ps1','surfd-deploy-plan.ps1')) {
 $tokens=$null; $errors=$null
 [void][System.Management.Automation.Language.Parser]::ParseFile((Join-Path $env:DEPLOY_TEST_TOOLS $name), [ref]$tokens, [ref]$errors)
 if ($errors.Count) { throw ($errors | Out-String) }
}
'PARSE_ACTED'
''')
        self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
        self.assertIn('PARSE_ACTED', r.stdout)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--ref', default='HEAD', help='committed source for layout gates')
    args, rest = parser.parse_known_args()
    args.out = args.out.resolve()
    if not any((p/'OWNER.md').is_file() for p in [args.out, *args.out.parents]):
        parser.error('--out requires an ancestor OWNER.md')
    args.out.mkdir(parents=True, exist_ok=True)
    unittest.main(argv=[sys.argv[0], *rest])
