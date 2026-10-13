#!/usr/bin/env python3
"""Real publish.sh retention controls in fresh owned sites; public test key, no network.

Run on Linux/WSL with --work-root <fresh evidence root> and optionally
--control-publish <preserved oldest-first publish.sh>. Sites are retired; logs,
exact survivor sets and source hashes remain. Not a Unix-permission/HTTPS test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import ed25519
import updatefeed as feed
from test_update_publication import KEY, SEED, shell_controls, stage


CASES = (
    ('first-page', (), '0.1.25', (), ()),
    ('below-limit', ('0.1.1', '0.1.24'), '0.1.25', (), ('0.1.1', '0.1.24', '0.1.25')),
    ('exact-limit', ('0.1.1', '0.1.2', '0.1.3', '0.1.24'), '0.1.25', (),
     ('0.1.1', '0.1.2', '0.1.3', '0.1.24', '0.1.25')),
    ('six-increasing', ('0.1.0', '0.1.1', '0.1.2', '0.1.3', '0.1.24'), '0.1.25', (),
     ('0.1.1', '0.1.2', '0.1.3', '0.1.24', '0.1.25')),
    ('seven-increasing', ('0.1.0', '0.1.1', '0.1.2', '0.1.3', '0.1.4', '0.1.24'), '0.1.25', (),
     ('0.1.2', '0.1.3', '0.1.4', '0.1.24', '0.1.25')),
    ('numeric-major', ('2.0.0', '9.0.0', '10.0.0', '11.0.0', '12.0.0'), '25.0.0', (),
     ('9.0.0', '10.0.0', '11.0.0', '12.0.0', '25.0.0')),
    ('numeric-minor', ('0.2.0', '0.9.0', '0.10.0', '0.11.0', '0.12.0'), '0.25.0', (),
     ('0.9.0', '0.10.0', '0.11.0', '0.12.0', '0.25.0')),
    ('numeric-components', ('0.9.12', '0.10.1', '1.2.10', '1.10.2', '2.0.0'), '10.0.0', (),
     ('0.10.1', '1.2.10', '1.10.2', '2.0.0', '10.0.0')),
    ('numeric-patch', ('0.1.2', '0.1.9', '0.1.10', '0.1.11', '0.1.12'), '0.1.25', (),
     ('0.1.9', '0.1.10', '0.1.11', '0.1.12', '0.1.25')),
    ('multiple-prunes', tuple(f'0.1.{n}' for n in range(8)), '0.1.25', (),
     ('0.1.4', '0.1.5', '0.1.6', '0.1.7', '0.1.25')),
    ('oldest-current', ('0.1.1', '0.1.2', '0.1.3', '0.1.4', '0.1.5', '0.1.6'), '0.0.1', (),
     ('0.0.1', '0.1.2', '0.1.3', '0.1.4', '0.1.5', '0.1.6')),
    ('signed-history', ('0.1.0', '0.1.1', '0.1.2', '0.1.3', '0.1.24'), '0.1.25', ('0.1.0',),
     ('0.1.0', '0.1.1', '0.1.2', '0.1.3', '0.1.24', '0.1.25')),
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): sha(p) for p in root.rglob('*') if p.is_file()}


def publish_case(runtime: Path, evidence: Path, fixture: Path, publisher: Path,
                 name: str, versions: tuple[str, ...], version: str,
                 signed: tuple[str, ...], expected: tuple[str, ...]) -> dict:
    site = runtime / name
    site.mkdir()
    (site / 'OWNER.md').write_text('Fresh synthetic site; no live paths, production keys or network.\n')
    for helper in ('updatefeed.py', 'ed25519.py'):
        shutil.copyfile(fixture / 'tools' / helper, site / helper)
    releases = site / 'releases'
    releases.mkdir()
    for old in (*versions, 'notes', '0.1.2-beta', 'v0.1.3'):
        page = releases / old
        page.mkdir()
        (page / 'index.html').write_text(f'sentinel {old}\n')
        if old in signed:
            shutil.copyfile(fixture / f'feed-{old}/update.json', page / 'update.json')
    if versions:
        # All live predecessors here are unsigned pages. Signed-forward gates
        # are tested separately by the existing production shell controls.
        (site / 'static').symlink_to(f'releases/{versions[-1]}', target_is_directory=True)
    incoming = site / '.incoming' / version
    incoming.mkdir(parents=True)
    (incoming / 'index.html').write_text(f'candidate {name}\n')
    shutil.copyfile(fixture / f'feed-{version}/update.json', incoming / 'update.json')
    payload = feed.verify((incoming / 'update.json').read_bytes(), KEY)
    proof = {'version': version, 'feed_sha256': sha(incoming / 'update.json'),
             'objects': len(feed.validate(payload)), 'verification': 'r2-roundtrip-blake2b-256'}
    (incoming / 'update-verified.json').write_text(json.dumps(proof))
    snapshots = {p.name: files(p) for p in releases.iterdir()}
    snapshots[version] = files(incoming)
    result = subprocess.run(['sh', str(publisher), version, 'none', str(site)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
    (evidence / f'{name}.log').write_text(result.stdout)
    actual = set(p.name for p in releases.iterdir())
    wanted = set(expected or (version,)) | {'notes', '0.1.2-beta', 'v0.1.3'}
    row = {'case': name, 'rc': result.returncode, 'actual': sorted(actual), 'expected': sorted(wanted),
           'publisher_sha256': sha(publisher), 'pruned': sorted(set(versions) - wanted)}
    (evidence / f'{name}.json').write_text(json.dumps(row, indent=2) + '\n')
    assert result.returncode == 0, (name, result.returncode, result.stdout)
    assert 'update publication checks passed' in result.stdout and f'published {version}' in result.stdout, result.stdout
    assert (site / 'static').readlink() == Path(f'releases/{version}'), name
    assert not incoming.exists(), name
    assert actual == wanted, (name, 'retention mismatch', row)
    pruned = {line.removeprefix('  pruned old release ') for line in result.stdout.splitlines()
              if line.startswith('  pruned old release ')}
    assert pruned == set(versions) - wanted, (name, pruned, row)
    assert {p.name: files(p) for p in releases.iterdir()} == {n: snapshots[n] for n in wanted}, name
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--publish', type=Path, default=Path(__file__).resolve().parents[1] / 'src/release/publish.sh')
    parser.add_argument('--control-publish', type=Path)
    args = parser.parse_args()
    if args.work_root.exists():
        parser.error('fresh owned evidence root required')
    args.work_root.mkdir(parents=True)
    (args.work_root / 'OWNER.md').write_text('Public RFC8032 synthetic publisher controls. Runtime below this root; retain logs/results.\n')
    evidence = args.work_root
    rows = []
    with tempfile.TemporaryDirectory(prefix='.runtime-', dir=evidence) as runtime_name:
        runtime = Path(runtime_name)
        (runtime / 'OWNER.md').write_text('Disposable synthetic runtime; created by test_release_retention.py.\n')
        fixture = runtime / 'fixture'
        tools = fixture / 'tools'
        tools.mkdir(parents=True)
        source = Path(feed.__file__).read_text()
        literal = f'PUBLIC_KEY = "{feed.PUBLIC_KEY}"'
        assert source.count(literal) == 1
        (tools / 'updatefeed.py').write_text(source.replace(literal, f'PUBLIC_KEY = "{KEY}"'))
        shutil.copyfile(Path(ed25519.__file__), tools / 'ed25519.py')
        stages = {platform: stage(fixture / platform, platform) for platform in ('win64', 'linux64')}
        for version in sorted({case[2] for case in CASES} | {v for case in CASES for v in case[3]}):
            feed.build(stages, fixture / f'feed-{version}', version, ['https://mock.invalid/update'], SEED, KEY)
        if args.control_publish:
            case = next(case for case in CASES if case[0] == 'seven-increasing')
            control_expected = ('0.1.0', '0.1.1', '0.1.2', '0.1.3', '0.1.4', '0.1.25')
            rows.append(publish_case(runtime, evidence, fixture, args.control_publish,
                                     'oldest-first-control', *case[1:4], control_expected))
        for case in CASES:
            rows.append(publish_case(runtime, evidence, fixture, args.publish, *case))
        feed.build(stages, fixture / 'prior', '0.1.24', ['https://mock.invalid/update'], SEED, KEY)
        feed.build(stages, fixture / 'next', '0.1.25', ['https://mock.invalid/update'], SEED, KEY,
                   previous=(fixture / 'prior/update.json').read_bytes(), previous_objects=fixture / 'prior/objects')
        feed.build(stages, fixture / 'older', '0.1.23', ['https://mock.invalid/update'], SEED, KEY)
        shell_controls(fixture, evidence / 'publication', args.publish)
    assert not runtime.exists()
    result = {'verdict': 'PASS', 'publisher_sha256': sha(args.publish), 'results': rows,
              'retention_subject_cases': len(CASES), 'publication_cases': 10,
              'runtime_path': str(runtime), 'runtime_retired': True}
    (evidence / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f'PASS {len(CASES)} retention cases, {int(bool(args.control_publish))} oldest-first control, '
          '10 production publication controls; runtime retired')


if __name__ == '__main__':
    main()
