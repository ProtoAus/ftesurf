#!/usr/bin/env python3
"""Prepare an inspected Git-pinned similarity tool; install only its fixed runtime path.

prepare requires a clean checkout and an exact commit SHA. Transport the resulting
small package over the operator's trusted channel, then install at the caller's
resolved game tools directory. Install is DRY RUN unless --apply is explicit.
No host defaults, credentials, network, player files or collector calls here.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

PAIRED = ('rcptcheck.py', 'hidcheck.py', 'reccheck.py', 'ed25519.py')
MAX_BYTES = 1 << 20
HEX40 = re.compile(r'[0-9a-f]{40}')
HEX64 = re.compile(r'[0-9a-f]{64}')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def bounded(path):
    with Path(path).open('rb') as f:
        data = f.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('support file exceeds package budget')
    return data


def prepare(repo, ref, output):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args])

    if not HEX40.fullmatch(ref) or git('rev-parse', ref).decode().strip() != ref:
        raise ValueError('use one exact inspected commit SHA')
    if git('status', '--porcelain').strip():
        raise ValueError('source checkout must be clean; no loose work is shipped')
    recsim = git('show', ref+':tools/census/recsim.py')
    installer = git('show', ref+':tools/simcheck_runtime.py')
    if max(len(recsim), len(installer)) > MAX_BYTES:
        raise ValueError('support file exceeds package budget')
    manifest = {'version': 1, 'commit': ref, 'recsim_sha256': digest(recsim),
                'installer_sha256': digest(installer),
                'paired_sha256': {p: digest(git('show', ref+':tools/'+p)) for p in PAIRED}}
    out = Path(output)
    out.mkdir()  # caller owns a fresh package, never overwrite an existing one
    (out/'recsim.py').write_bytes(recsim)
    (out/'simcheck_runtime.py').write_bytes(installer)
    (out/'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    return manifest


def probe(path):
    """Import only the explicit verified path, with no neighborhood fallback."""
    old = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec = importlib.util.spec_from_file_location('_simcheck_runtime_probe', str(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = old
    if Path(mod.__file__).resolve() != Path(path).resolve() or not callable(getattr(mod, 'compare_paths', None)):
        raise ValueError('runtime comparison capability/path unavailable')
    return mod


def install(package, tools_dir, expected_previous, apply=False):
    package = Path(package).resolve(strict=True)
    raw = bounded(package/'manifest.json')
    if len(raw) > 8192:
        raise ValueError('manifest exceeds budget')
    m = json.loads(raw)
    if (not isinstance(m, dict) or set(m) != {'version','commit','recsim_sha256','installer_sha256','paired_sha256'}
            or type(m['version']) is not int or m['version'] != 1
            or not isinstance(m['commit'], str) or not HEX40.fullmatch(m['commit'])
            or not isinstance(m['paired_sha256'], dict) or set(m['paired_sha256']) != set(PAIRED)):
        raise ValueError('unsupported package manifest')
    for h in [m['recsim_sha256'], m['installer_sha256'], *m['paired_sha256'].values()]:
        if not isinstance(h, str) or not HEX64.fullmatch(h):
            raise ValueError('invalid package hash')
    data = bounded(package/'recsim.py')
    if digest(data) != m['recsim_sha256'] or digest(bounded(package/'simcheck_runtime.py')) != m['installer_sha256']:
        raise ValueError('package bytes changed')
    # Verify the invoked installer too: a staged helper must be from this package.
    if digest(bounded(__file__)) != m['installer_sha256']:
        raise ValueError('invoked installer is not the pinned version')
    if not Path(tools_dir).is_absolute():
        raise ValueError('tools directory must be explicitly absolute')
    tools = Path(tools_dir).resolve(strict=True)
    for p,h in m['paired_sha256'].items():
        if digest(bounded(tools/p)) != h:
            raise ValueError('paired runtime reader differs: '+p)
    parent, target = tools/'census', tools/'census'/'recsim.py'
    if parent.is_symlink() or target.is_symlink():
        raise ValueError('runtime census path must not be a symlink')
    previous = bounded(target) if target.exists() else None
    have = digest(previous) if previous is not None else 'absent'
    if expected_previous != have:
        raise ValueError('runtime predecessor/absence changed')
    probe(package/'recsim.py')  # capability must act before destination mutation
    result = {'version':1, 'commit':m['commit'], 'target':str(target), 'sha256':m['recsim_sha256'],
              'previous':have, 'state':'unchanged' if previous == data else 'planned'}
    if not apply or previous == data:
        return result
    parent.mkdir(exist_ok=True)
    if previous is not None:
        backup = target.with_name(target.name+'.pre-'+m['commit'][:12])
        with backup.open('xb') as f:
            f.write(previous)
        os.chmod(backup, 0o600)
        result['backup'] = str(backup)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=parent, prefix='recsim-owned-', suffix='.new', delete=False) as f:
            temporary = Path(f.name)
            f.write(data)
        os.chmod(temporary, 0o644)
        # Recheck immediately before swap; unrelated destination edits are blockers.
        current = bounded(target) if target.exists() else None
        if current != previous:
            raise ValueError('runtime predecessor raced')
        temporary.replace(target)
        temporary = None
        if digest(bounded(target)) != m['recsim_sha256']:
            raise ValueError('installed hash differs')
        probe(target)
        for p,h in m['paired_sha256'].items():
            if digest(bounded(tools/p)) != h:
                raise ValueError('paired runtime reader raced: '+p)
    finally:
        if temporary is not None:
            temporary.unlink()  # only our exact temporary; failure is visible
    result['state'] = 'installed'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--repo', required=True);p.add_argument('--ref', required=True);p.add_argument('--output', required=True)
    p = sub.add_parser('install')
    p.add_argument('--package', required=True);p.add_argument('--tools-dir', required=True)
    p.add_argument('--expect-previous', required=True, help='exact predecessor sha256, or absent')
    p.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.action == 'prepare':result=prepare(args.repo,args.ref,args.output)
    else:result=install(args.package,args.tools_dir,args.expect_previous,args.apply)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
