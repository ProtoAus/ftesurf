#!/usr/bin/env python3
"""Offline Linux PowerShell path/guard controls; synthetic compiler, no deployment.

Run --out beneath an owned task root. Real QC compilation is a separate check.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'src/build.ps1'
DEPLOY = ROOT / 'tools/surfd-deploy.ps1'


def run_ps(arguments, env):
    return subprocess.run(['pwsh', '-NoLogo', '-NoProfile', '-NonInteractive', *arguments],
                          env=env, capture_output=True, text=True, timeout=60)


class LinuxDeploy(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=args.out, prefix='linux-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.env = dict(os.environ)
        for name in ('OS', 'FTESURF_FTEROOT', 'FTESURF_QUAKEDIR', 'FTESURF_MAKE'):
            self.env.pop(name, None)
        self.env['NO_COLOR'] = '1'

    def fixture(self, source=None):
        workspace = self.home / 'fixture workspace'
        src = workspace / 'ftesurf/src'
        src.mkdir(parents=True)
        game = src.parent / 'ftesurf'
        game.mkdir()
        (src / 'build.ps1').write_bytes(source if source is not None else BUILD.read_bytes())
        (src.parent / 'VERSION').write_text('0.1.48\n')
        for manifest, output in (('sv', 'qwprogs'), ('cl', 'csprogs'), ('m', 'menu')):
            (src / (manifest + '_progs.src')).write_text('../ftesurf/' + output + '.dat\n')
            (game / (output + '.dat')).write_text('previous installed bytes\n')
        compiler = workspace / 'ftequakers/engine/release/fteqcc64'
        compiler.parent.mkdir(parents=True)
        compiler.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
with open(os.environ['FAKE_CC_CALLS'], 'a') as f:
    f.write(json.dumps(sys.argv) + '\\n')
if '--help' in sys.argv:
    print('omitarraydefs supported')
else:
    manifest = Path(sys.argv[sys.argv.index('-srcfile') + 1])
    output = Path(manifest.read_text(encoding='utf-8-sig').splitlines()[0])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('synthetic QC output\\n')
''')
        compiler.chmod(0o755)
        self.env['FAKE_CC_CALLS'] = str(self.home / 'compiler-calls.jsonl')
        return src, game, compiler

    def test_old_discovery_fails_then_native_no_deploy_acts_without_install_changes(self):
        old = subprocess.check_output(['git', '-C', str(ROOT), 'show', args.baseline + ':src/build.ps1'])
        src, game, compiler = self.fixture(old)
        before = {p.name: p.read_bytes() for p in game.iterdir()}
        failed = run_ps(['-File', str(src / 'build.ps1'), '-NoDeploy'], self.env)
        (args.out / 'old-compiler-discovery.log').write_text(failed.stdout + failed.stderr)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn('fteqcc not found', failed.stdout + failed.stderr)
        self.assertFalse(Path(self.env['FAKE_CC_CALLS']).exists())
        (src / 'build.ps1').write_bytes(BUILD.read_bytes())
        acted = run_ps(['-File', str(src / 'build.ps1'), '-NoDeploy'], self.env)
        self.assertEqual(acted.returncode, 0, acted.stdout + acted.stderr)
        self.assertEqual({p.name: p.read_bytes() for p in game.iterdir()}, before)
        builds = list((src.parent / 'rig').glob('build-nodeploy-*'))
        self.assertEqual(len(builds), 1)
        self.assertEqual({p.name for p in builds[0].glob('*.dat')}, {'qwprogs.dat', 'csprogs.dat', 'menu.dat'})
        self.assertFalse(list(src.glob('build-nodeploy-*')))
        calls = [json.loads(line) for line in Path(self.env['FAKE_CC_CALLS']).read_text().splitlines()]
        self.assertEqual(len(calls), 4)
        self.assertTrue(all(c[0] == str(compiler) for c in calls))
        self.assertIn('-Fomitarraydefs', calls[2])
        self.assertIn('-DUI_MENU_VERSION="0.1.48"', calls[3])
        self.assertIn('-DUI_MENU_DEVELOPMENT=1', calls[3])

    def test_engine_override_and_unix_compiler_ignore_windows_executable(self):
        src, _, compiler = self.fixture()
        alternate = self.home / 'alternate engine'
        (alternate / 'engine/release').mkdir(parents=True)
        moved = alternate / 'engine/release/fteqcc64'
        compiler.rename(moved)
        (src / 'fteqcc64.exe').write_text('never execute a Windows compiler on Linux')
        self.env['FTESURF_FTEROOT'] = str(alternate)
        result = run_ps(['-File', str(src / 'build.ps1'), '-NoDeploy'], self.env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = [json.loads(line) for line in Path(self.env['FAKE_CC_CALLS']).read_text().splitlines()]
        self.assertTrue(all(c[0] == str(moved) for c in calls))

    def test_unsupported_native_and_no_deploy_conflicts_refuse_before_compiler(self):
        src, _, _ = self.fixture()
        for flags in (['-Engine', '-NoDeploy'], ['-Full', '-NoDeploy'],
                      ['-Pi', '-NoDeploy'], ['-Run', '-NoDeploy']):
            with self.subTest(flags=flags):
                result = run_ps(['-File', str(src / 'build.ps1'), *flags], self.env)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(Path(self.env['FAKE_CC_CALLS']).exists())
                self.assertFalse((src.parent / 'rig').exists())

    def test_official_pi_body_is_unchanged(self):
        old = self.home / 'baseline.ps1'
        old.write_bytes(subprocess.check_output(['git', '-C', str(ROOT), 'show', args.baseline + ':src/build.ps1']))
        self.env.update(TEST_OLD=str(old), TEST_NEW=str(BUILD))
        result = run_ps(['-Command', r'''
$ErrorActionPreference='Stop'
$result = foreach($file in @($env:TEST_OLD,$env:TEST_NEW)) {
 $t=$null;$e=$null
 $ast=[System.Management.Automation.Language.Parser]::ParseFile($file,[ref]$t,[ref]$e)
 if($e.Count){throw 'parse error'}
 $pi=@($ast.FindAll({param($n) $n -is [System.Management.Automation.Language.IfStatementAst] -and $n.Clauses[0].Item1.Extent.Text -ceq '$Pi'},$true))
 if($pi.Count -ne 1){throw 'Pi body not unique'}
 @{text=$pi[0].Extent.Text.Replace("`r`n","`n");count=$pi[0].Clauses[0].Item2.Statements.Count}
}
ConvertTo-Json -Depth 3 -InputObject @($result) -Compress
'''], self.env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        before, after = json.loads(result.stdout)
        self.assertEqual(before, after)
        self.assertEqual(after['count'], 45)
        raw = BUILD.read_bytes()
        self.assertEqual(raw.count(b'\n'), raw.count(b'\r\n'), 'preserve retained helper CRLF')

    def test_legacy_apply_workroot_requires_ordinary_owned_absolute_directory(self):
        root = self.home / 'owned'
        root.mkdir()
        owner = root / 'OWNER.md'
        owner.write_text('synthetic owner\n')
        linked = self.home / 'linked'
        linked.symlink_to(root, target_is_directory=True)
        nested = root / 'nested'
        nested.mkdir()
        (nested / 'OWNER.md').write_text('synthetic nested owner\n')
        sentinel = root / 'sentinel'
        sentinel.write_bytes(b'protected fixture target')
        quoted = self.home / "Lex's task"
        quoted.mkdir()
        (quoted / 'OWNER.md').write_text('synthetic quoted owner\n')
        code = r'''
$ErrorActionPreference='Stop'
$source=Get-Content -Raw $env:TEST_DEPLOY
$start=$source.IndexOf('if (-not $WorkRoot) {')
$end=$source.IndexOf('$script:PiExit = 0', $start)
if($start -lt 0 -or $end -le $start){throw 'workspace gate not found'}
$WorkRoot=$env:TEST_WORKROOT
Invoke-Expression $source.Substring($start,$end-$start)
'WORKROOT_ACCEPTED'
'''
        self.env['TEST_DEPLOY'] = str(DEPLOY)
        for path, allowed in (('', False), ('relative', False), (str(linked), False),
                              (str(linked / 'nested'), False), (str(root), True), (str(quoted), True)):
            with self.subTest(path=path):
                self.env['TEST_WORKROOT'] = path
                result = run_ps(['-Command', code], self.env)
                self.assertEqual(result.returncode == 0, allowed, result.stdout + result.stderr)
                self.assertEqual('WORKROOT_ACCEPTED' in result.stdout, allowed)
        owner.unlink()
        self.env['TEST_WORKROOT'] = str(root)
        self.assertNotEqual(run_ps(['-Command', code], self.env).returncode, 0)
        real_owner = self.home / 'real-owner'
        real_owner.write_text('synthetic owner\n')
        owner.symlink_to(real_owner)
        self.assertNotEqual(run_ps(['-Command', code], self.env).returncode, 0)
        self.assertEqual({p.name for p in root.iterdir()}, {'OWNER.md', 'nested', 'sentinel'},
                         'workspace validation must not create a stage')
        self.assertEqual(sentinel.read_bytes(), b'protected fixture target')

    def helper_code(self, name):
        self.env.update(TEST_DEPLOY=str(DEPLOY), TEST_HELPER=name)
        return r'''
$ErrorActionPreference='Stop'
$t=$null;$e=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile($env:TEST_DEPLOY,[ref]$t,[ref]$e)
if($e.Count){throw 'parse error'}
$node=@($ast.FindAll({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -ceq $env:TEST_HELPER},$true))
if($node.Count -ne 1){throw 'helper not unique'}
Invoke-Expression $node[0].Extent.Text
'''

    def test_mount_redirection_parser_refuses_aliases_but_accepts_normal_subvolume(self):
        code = self.helper_code('Assert-NoWorkRootMountAlias') + r'''
Assert-NoWorkRootMountAlias -Path $env:TEST_PATH -Lines @(ConvertFrom-Json $env:TEST_LINES)
'MOUNT_ACCEPTED'
'''
        normal = '1 0 8:1 / / rw - ext4 /dev/test rw'
        cases = [
            ('/owned/task', [normal], True),
            ('/owned/view/task', [normal, '2 1 8:1 /protected /owned/view rw - ext4 /dev/test rw'], False),
            ('/owned/view/task', [normal, '2 1 8:2 /protected /owned/view rw - ext4 /dev/other rw'], False),
            ('/owned/view/task', [normal, '2 1 8:2 /@home/protected /owned/view rw - btrfs /dev/other rw,subvol=/@home'], False),
            ('/owned/view/task', [normal, '2 1 8:1 /owned/view /owned/view rw - ext4 /dev/test rw'], True),
            ('/home/lex/task', ['1 0 8:1 /@ / rw - btrfs /dev/test rw,subvol=/@',
                                '2 1 8:1 /@home /home rw - btrfs /dev/test rw,subvol=/@home'], True),
            ('/home/lex/task', [normal, '2 1 8:2 /@home /home rw - btrfs /dev/other rw,subvol=/@home'], True),
            ('/owned/view with space/task', [normal, r'2 1 8:1 /protected /owned/view\040with\040space rw - ext4 /dev/test rw'], False),
            ('/alias/task', [normal, '2 1 8:1 / /alias rw - ext4 /dev/test rw'], False),
            ('/owned/task', ['malformed'], False),
            ('/owned/task', [], False),
        ]
        for path, lines, allowed in cases:
            with self.subTest(path=path, lines=lines):
                self.env.update(TEST_PATH=path, TEST_LINES=json.dumps(lines))
                result = run_ps(['-Command', code], self.env)
                self.assertEqual(result.returncode == 0, allowed, result.stdout + result.stderr)
                self.assertEqual('MOUNT_ACCEPTED' in result.stdout, allowed)

    def test_stage_command_preserves_quoted_receipts_without_shell_injection(self):
        code = self.helper_code('New-SurfdStageCommand') + r'''
New-SurfdStageCommand -Stage $env:TEST_STAGE -Commit 'fixture123' -Receipt $env:TEST_RECEIPT
'''
        injected = self.home / 'injected'
        receipts = ['normal task', "Lex's task", "receipt'; touch '" + str(injected) + "'; printf '"]
        for index, receipt in enumerate(receipts):
            stage = self.home / "stage's parent" / ('stage-' + str(index))
            self.env.update(TEST_STAGE=str(stage), TEST_RECEIPT=receipt)
            result = run_ps(['-Command', code], self.env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            command = result.stdout.strip()
            syntax = subprocess.run(['sh', '-n'], input=command, capture_output=True, text=True)
            self.assertEqual(syntax.returncode, 0, syntax.stderr)
            acted = subprocess.run(['sh', '-c', command], capture_output=True, text=True)
            self.assertEqual(acted.returncode, 0, acted.stdout + acted.stderr)
            self.assertEqual((stage / 'OWNER.md').read_text(),
                             'Owner: surfd-deploy.ps1; commit fixture123; local receipt ' + receipt +
                             '; status active, retained on failure.\n')
            self.assertTrue((stage / 'surfd').is_dir())
            self.assertTrue((stage / 'tmp').is_dir())
            self.assertFalse(injected.exists())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--baseline', default='39df032513819ef631b1689e493d91146cc90cc7')
    args, extra = parser.parse_known_args()
    args.out = args.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in (args.out, *args.out.parents)):
        parser.error('--out needs an ancestor OWNER.md')
    args.out.mkdir(parents=True, exist_ok=True)
    if not shutil.which('pwsh'):
        parser.error('pwsh required')
    unittest.main(argv=[__file__, *extra])
