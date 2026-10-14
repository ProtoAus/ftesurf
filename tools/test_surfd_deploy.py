#!/usr/bin/env python3
"""Offline exact-commit KSF shipping falsifiers; no SSH, app or game launch.

Run with --out beneath an owned task root. Requires pwsh 7, git and sh. Only
synthetic Git repositories/layouts created under --out may be modified here.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
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
        self.assertTrue(KSF_SET <= set(full['Files']))
        self.assertEqual({f for f in full['Files'] if f.startswith('tools/')},
                         {'tools/ksfconvert.py', 'tools/ksfreplay_info.py'})
        for entry in KSF_SET-{'surfd/surfd.py'}:
            p = self.plan(only=[entry, entry])
            self.assertEqual(set(p['Files']), KSF_SET)
            self.assertEqual(len(p['Files']), 5)
            self.assertTrue(set(p['Files']) <= set(p['StageFiles']))
            self.assertIn('surfd/test_ksfgrab.py', p['StageFiles'])
            pairs = dict(zip(p['Files'], p['Destinations']))
            self.assertEqual(pairs['surfd/ksfgrab.py'], 'ksfgrab.py')
            self.assertEqual(pairs['tools/ksfconvert.py'], 'tools/ksfconvert.py')
            self.assertEqual(set(p['AddedDependencies']), KSF_SET-{entry})
        # Selecting the app alone is a normal narrowly scoped app change, not
        # authority to replace all importers. The default plan ships all of them.
        p = self.plan(only=['surfd/surfd.py'])
        self.assertEqual(p['Files'], ['surfd/surfd.py'])
        self.assertGreater(len(p['StageFiles']), len(p['Files']))

    def test_unknown_paths_and_refs_refuse(self):
        for path in ('surfd/missing.py', '../surfd/surfd.py', 'tools/runlines_smoke.py',
                     'tools/test_ksfconvert.py', 'surfd'):
            r = self.plan(only=[path], succeeds=False)
            self.assertIn('not a deployable file', r.stderr)
        for ref in ('no-such-ref-offline', '--help'):
            self.plan(ref=ref, succeeds=False)

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
        self.assertEqual(set(p['Files']), KSF_SET)

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
        return json.loads(r.stdout.lstrip('\ufeff'))['Body']

    def test_actual_suite_shell_passes_args_and_propagates_both_failures(self):
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
        for failure in ('', 'GRAB_FAIL', 'CONVERT_FAIL'):
            env = dict(os.environ)
            # Setting the POSIX PATH inside sh avoids Windows PATH rewriting.
            command = 'PATH="'+posix(bindir)+':$PATH"; export PATH; sh "'+posix(shell)+'"'
            if failure:
                command = failure+'=1; export '+failure+'; '+command
            r = run(['sh', '-c', command], env=env, check=False)
            (args.out/('suite-'+(failure or 'pass')+'.log')).write_text(r.stdout+r.stderr)
            self.assertEqual(r.returncode, 1 if failure else 0, r.stdout+r.stderr)
            if not failure:
                for acted in ('GRAB_ARGS_ACTED', 'CONVERTER_ACTED', 'TOPUP_OWNED_HOME_ACTED'):
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
        body = body.replace('__MANIFEST__', 'app.py '+want)
        shell = self.root/'verify.sh'
        shell.write_text(body, newline='\n')
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
