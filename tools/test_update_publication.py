#!/usr/bin/env python3
"""Bounded synthetic-key updater release/publication controls; never contacts storage."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import ed25519
import updatefeed as feed

SEED = bytes.fromhex('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60')
KEY = ed25519.publickey(SEED).hex()


def stage(root: Path, platform: str) -> Path:
    for p in ('default.fmf', 'ftesurf/menu.dat', 'ftesurf/csprogs.dat', 'ftesurf/qwprogs.dat',
              'ftesurf64.exe' if platform == 'win64' else 'ftesurf64'):
        dest = root / p
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((p + '\n').encode())
    return root


def run(argv: list[str], log: Path) -> subprocess.CompletedProcess:
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
    log.write_text(result.stdout, encoding='utf-8')
    return result


def shell_controls(fixture: Path, evidence: Path, publish: Path) -> None:
    if evidence.exists():
        raise ValueError('fresh owned shell evidence root required')
    evidence.mkdir(parents=True)
    (evidence / 'OWNER.md').write_text('Synthetic site publication controls. Runtime sites beneath this owned evidence root; no network. Retain logs/results.\n')
    source = fixture / 'prior/update.json'
    current = fixture / 'next/update.json'
    old_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    results = []
    with tempfile.TemporaryDirectory(prefix='.runtime-sites-', dir=evidence) as runtime:
        runtime = Path(runtime)
        (runtime / 'OWNER.md').write_text('Owned synthetic publication sites; retire this exact runtime tree after controls, preserve sibling evidence.\n')
        for name, old, prior, candidate, error in (
            ('first-positive', False, 'none', source, None),
            ('advance-positive', True, old_sha, current, None),
            ('missing-feed', True, old_sha, current, 'update.json'),
            ('missing-proof', True, old_sha, current, 'update-verified.json'),
            ('wrong-proof', True, old_sha, current, 'receipt does not match'),
            ('local-proof-not-roundtrip', True, old_sha, current, 'receipt does not match'),
            ('stale-predecessor', True, '0' * 64, current, 'prior feed changed'),
            ('first-on-existing', True, 'none', current, 'existing published feed'),
            ('same-version', True, old_sha, source, 'version must advance'),
            ('rollback', True, old_sha, fixture / 'older/update.json', 'version must advance'),
        ):
            site = runtime / name
            site.mkdir()
            for p in ('updatefeed.py', 'ed25519.py'):
                shutil.copyfile(fixture / 'tools' / p, site / p)
            if old:
                previous = site / 'releases/0.1.24'
                previous.mkdir(parents=True)
                shutil.copyfile(source, previous / 'update.json')
                (previous / 'index.html').write_text('old site sentinel')
                (site / 'static').symlink_to('releases/0.1.24', target_is_directory=True)
            version = feed.verify(candidate.read_bytes(), KEY)['version']
            incoming = site / '.incoming' / version
            incoming.mkdir(parents=True)
            (incoming / 'index.html').write_text(name)
            shutil.copyfile(candidate, incoming / 'update.json')
            payload = feed.verify(candidate.read_bytes(), KEY)
            proof = {'version': version, 'feed_sha256': hashlib.sha256(candidate.read_bytes()).hexdigest(),
                     'objects': len(feed.validate(payload)), 'verification': 'r2-roundtrip-blake2b-256'}
            if name == 'wrong-proof':
                proof['feed_sha256'] = '0' * 64
            if name == 'local-proof-not-roundtrip':
                proof['verification'] = 'local-blake2b-256'
            (incoming / 'update-verified.json').write_text(json.dumps(proof))
            if name == 'missing-proof':
                (incoming / 'update-verified.json').unlink()
            if name == 'missing-feed':
                (incoming / 'update.json').unlink()
            # Same-version refusal must reach the version gate, not pre-existing DST.
            if name == 'same-version':
                previous.rename(site / 'releases/prior')
                (site / 'static').unlink()
                (site / 'static').symlink_to('releases/prior', target_is_directory=True)
            before = (site / 'static').readlink() if old else None
            result = run(['sh', str(publish), version, prior, str(site)], evidence / f'{name}.log')
            if error:
                assert result.returncode != 0 and error in result.stdout, (name, result.returncode, result.stdout)
                assert ((site / 'static').readlink() if old else None) == before, name
                if old:
                    assert (site / 'static/index.html').read_text() == 'old site sentinel'
                    assert (site / 'static/update.json').read_bytes() == source.read_bytes()
            else:
                assert result.returncode == 0 and 'update publication checks passed' in result.stdout and f'published {version}' in result.stdout, (name, result.stdout)
                assert (site / 'static').readlink() == Path(f'releases/{version}')
                assert (site / 'static/update.json').read_bytes() == candidate.read_bytes()
                assert (site / 'static/index.html').read_text() == name
            results.append({'case': name, 'rc': result.returncode, 'expected_error': error,
                            'static': str((site / 'static').readlink()) if (site / 'static').is_symlink() else None})
    assert not runtime.exists()
    (evidence / 'result.json').write_text(json.dumps({'results': results, 'runtime_path': str(runtime), 'runtime_retired': True}, indent=2) + '\n')
    print(f'PASS {len(results)} production publish.sh controls; runtime retired')


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work-root', type=Path, required=True)
    p.add_argument('--control-tool', type=Path)
    p.add_argument('--prior-control-tool', type=Path)
    p.add_argument('--shell-only', action='store_true')
    p.add_argument('--fixture-root', type=Path)
    p.add_argument('--publish', type=Path)
    p.add_argument('--distro', default='Ubuntu-22.04')
    a = p.parse_args()
    if a.shell_only:
        shell_controls(a.fixture_root, a.work_root, a.publish)
        return
    if a.work_root.exists() or not a.control_tool or not a.prior_control_tool:
        p.error('fresh owned work root AND preserved --control-tool/--prior-control-tool required')
    root = a.work_root
    root.mkdir(parents=True)
    (root / 'OWNER.md').write_text('Updater publication test: synthetic RFC8032 key, byte-copy R2 mock, owned fixtures. No production keys/network. Retain evidence.\n')
    tools = root / 'tools'
    tools.mkdir()
    original = Path(feed.__file__).read_text()
    literal = f'PUBLIC_KEY = "{feed.PUBLIC_KEY}"'
    assert original.count(literal) == 1
    (tools / 'updatefeed.py').write_text(original.replace(literal, f'PUBLIC_KEY = "{KEY}"'), encoding='utf-8')
    shutil.copyfile(Path(ed25519.__file__), tools / 'ed25519.py')
    (root / 'seed').write_bytes(SEED)
    win, linux = stage(root / 'win', 'win64'), stage(root / 'linux', 'linux64')
    stages = {'win64': win, 'linux64': linux}
    feed.build(stages, root / 'prior', '0.1.24', ['https://mock.invalid/ftesurf/update'], SEED, KEY)
    previous = (root / 'prior/update.json').read_bytes()
    feed.build({'win64': win}, root / 'next', '0.1.25', ['https://mock.invalid/ftesurf/update'], SEED, KEY,
               previous=previous, previous_objects=root / 'prior/objects')
    feed.build(stages, root / 'older', '0.1.23', ['https://mock.invalid/ftesurf/update'], SEED, KEY)
    m = feed.verify(previous, KEY)
    linux_file = next(f for f in m['files'] if f['path'] == 'ftesurf64')
    (root / 'fixture.json').write_text(json.dumps({'linux_object': f"{linux_file['hash'][:2]}/{linux_file['hash']}"}))
    spec = importlib.util.spec_from_file_location('pre_feed_wiring', a.control_tool)
    control = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(control)
    control.build({'win64': win}, root / 'before', '0.1.25', ['https://mock.invalid/ftesurf/update'], SEED, KEY, previous=previous)
    before = feed.verify((root / 'before/update.json').read_bytes(), KEY)
    reason = None
    try:
        feed.verify_objects(root / 'before/objects', before)
    except ValueError as e:
        reason = str(e)
    assert reason and 'missing referenced object' in reason and linux_file['hash'] in reason, reason
    (root / 'control.json').write_text(json.dumps({'verdict': 'EXPECTED PRE-FIX MISSING LINUX OBJECT', 'error': reason,
        'control_source_sha256': hashlib.sha256(a.control_tool.read_bytes()).hexdigest(),
        'subject_source_sha256': hashlib.sha256(Path(feed.__file__).read_bytes()).hexdigest()}, indent=2))
    spec = importlib.util.spec_from_file_location('pre_prior_validation', a.prior_control_tool)
    prior_control = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior_control)
    prior_results = []
    for name, data, error in [('empty', b'', 'Expecting value'),
                              ('object', feed.envelope({}, SEED, KEY), 'unsupported update feed'),
                              ('null', feed.envelope(None, SEED, KEY), 'must be an object')]:
        prior_file = root / f'invalid-prior-{name}.json'
        prior_file.write_bytes(data)
        before_output = root / f'before-prior-{name}'
        prior_control.build({'win64': win}, before_output, '0.1.25', ['https://mock.invalid/ftesurf/update'], SEED, KEY, previous=data)
        acted = feed.verify((before_output / 'update.json').read_bytes(), KEY)
        assert {f['platform'] for f in acted['files']} == {'win64'}
        cli_output = root / f'cli-invalid-prior-{name}'
        cli = run(['python', str(tools / 'updatefeed.py'), '--windows', str(win), '--previous', str(prior_file),
                   '--output', str(cli_output), '--version', '0.1.25', '--mirror', 'https://mock.invalid/ftesurf/update',
                   '--seed-file', str(root / 'seed')], root / f'prior-cli-{name}.log')
        assert cli.returncode != 0 and error in cli.stdout and not (cli_output / 'update.json').exists(), cli.stdout
        assert not (cli_output / 'objects.txt').exists()
        prior_results.append({'case': name, 'before': 'WINDOWS-ONLY FEED WRITTEN', 'after_cli_rc': cli.returncode, 'expected_error': error})
    (root / 'prior-control.json').write_text(json.dumps({'results': prior_results,
        'control_source_sha256': hashlib.sha256(a.prior_control_tool.read_bytes()).hexdigest(),
        'subject_source_sha256': hashlib.sha256(Path(feed.__file__).read_bytes()).hexdigest()}, indent=2) + '\n')
    result = run(['pwsh', '-NoProfile', '-File', str(Path(__file__).with_suffix('.ps1')),
                  '-FixtureRoot', str(root), '-WorkRoot', str(root / 'powershell')], root / 'powershell.log')
    assert result.returncode == 0, result.stdout
    cli = run(['python', str(tools / 'updatefeed.py'), '--windows', str(win), '--first-release',
               '--output', str(root / 'invalid-first'), '--version', '0.1.25', '--mirror', 'https://mock.invalid/ftesurf/update',
               '--seed-file', str(root / 'seed')], root / 'first-cli.log')
    assert cli.returncode != 0 and 'Windows AND Linux' in cli.stdout and not (root / 'invalid-first').exists(), cli.stdout
    def wslpath(path: Path) -> str:
        return subprocess.check_output(['wsl.exe', '-d', a.distro, '--exec', 'wslpath', '-a', str(path.resolve())], text=True).strip()
    result = run(['wsl.exe', '-d', a.distro, '--exec', 'python3', wslpath(Path(__file__)), '--shell-only',
                  '--fixture-root', wslpath(root), '--work-root', wslpath(root / 'shell'),
                  '--publish', wslpath(Path(__file__).parent.parent / 'src/release/publish.sh')], root / 'shell.log')
    assert result.returncode == 0, result.stdout
    (root / 'result.json').write_text(json.dumps({'verdict': 'PASS', 'control': 'missing retained Linux object acted',
        'powershell_cases': 11, 'shell_cases': 10, 'first_feed_cli_refusal': True, 'invalid_prior_before_after_cases': 3}, indent=2) + '\n')
    print('PASS missing-object control, 3 acted invalid-prior before/after CLI controls, 11 production PowerShell cases, 10 production shell cases, first-feed CLI refusal')


if __name__ == '__main__':
    main()
