#!/usr/bin/env python3
"""Default-HTTPS launcher acceptance in fresh owned installs; never starts the game.

Trust the LOCAL release receipt hash from the prepared candidate, not hashes just
fetched from the website. Logs/install fixtures stay local. This is not a visual,
performance, multiplayer, or full updater adversarial test.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from email.parser import Parser

import updatefeed

SITE = 'https://proto.bar/ftesurf/'


def get(url, limit, root, name):
    # Same supported transport as release.ps1; the public edge refuses urllib.
    headers = root / (name + '.headers')
    result = subprocess.run(['curl.exe', '--disable', '--fail', '--silent', '--show-error',
        '--proto', '=https', '--max-time', '90', '--max-filesize', str(limit),
        '--header', 'Cache-Control: no-cache', '--dump-header', str(headers), url], capture_output=True, check=True)
    blocks = headers.read_text(encoding='iso8859-1').replace('\r\n', '\n').strip().split('\n\n')
    lines = blocks[-1].split('\n')
    if not re.match(r'^HTTP/\S+ 200\b', lines[0]) or len(result.stdout) > limit:
        raise ValueError('unexpected public status/redirect/size')
    return result.stdout, Parser().parsestr('\n'.join(lines[1:]))


def expected_receipt(path, sha):
    updatefeed.no_link(path)
    if not re.fullmatch(r'[0-9a-fA-F]{64}', sha):
        raise ValueError('trusted receipt SHA256 required')
    data = path.read_bytes()
    if len(data) > 2 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != sha.lower():
        raise ValueError('local receipt SHA256 mismatch')
    receipt = json.loads(data)
    if not re.fullmatch(r'\d+\.\d+\.\d+', receipt['version']) or receipt['overrides']:
        raise ValueError('invalid version or override/control receipt')
    return receipt


def run_launcher(root, platform, distro):
    binary = root / ('ftesurf-launcher.exe' if platform == 'win64' else 'ftesurf-launcher')
    if platform == 'win64':
        if os.name != 'nt':
            raise ValueError('Windows launcher smoke requires Windows')
        cmd = [str(binary), '--yes', '--no-launch']
    else:
        mapped = subprocess.check_output(['wsl.exe', '-d', distro, '--exec', 'wslpath', '-a', str(root)], text=True).strip()
        subprocess.run(['wsl.exe', '-d', distro, '--exec', 'chmod', '0755', mapped + '/ftesurf-launcher'], check=True)
        # timeout owns only this synthetic launcher, never a game/owner process.
        cmd = ['wsl.exe', '-d', distro, '--cd', mapped, '--exec', 'timeout', '--kill-after=5s', '180s',
               './ftesurf-launcher', '--yes', '--no-launch']
    with (root / 'launcher.log').open('wb') as log:
        subprocess.run(cmd, cwd=root, stdout=log, stderr=subprocess.STDOUT, timeout=195, check=True)


def smoke(receipt, root, distro):
    version = receipt['version']
    public_bytes, _ = get(SITE + 'version.json', 2 * 1024 * 1024, root, 'version')
    public = json.loads(public_bytes)
    if public['version'] != version or public['bootstrap_downloads'] != receipt['bootstrap_downloads']:
        raise ValueError('public version/launcher metadata differs from local receipt')
    feed, headers = get(SITE + 'update.json', updatefeed.MAX_FEED, root, 'feed')
    sha = hashlib.sha256(feed).hexdigest()
    if sha != receipt['update_feed']['sha256'].lower() or sha != public['update_feed']['sha256'].lower():
        raise ValueError('default public feed SHA256 differs from local receipt')
    payload = updatefeed.verify(feed)
    updatefeed.validate(payload)
    if payload['version'] != version or not any(x in headers.get('Cache-Control', '') for x in ('no-cache', 'no-store')):
        raise ValueError('default public feed version/cache policy mismatch')
    (root / 'update.json').write_bytes(feed)
    results = []
    wanted = {'win64', 'linux64'} if 'linux' in receipt else {'win64'}
    artifacts = {a['platform']: a for a in receipt['bootstrap_downloads']}
    if set(artifacts) != wanted or len(artifacts) != len(receipt['bootstrap_downloads']):
        raise ValueError('unexpected standalone launcher platform set')
    for platform in sorted(wanted):
        artifact = artifacts[platform]
        name = f'ftesurf-launcher-{version}' + ('.exe' if platform == 'win64' else '-linux-x86_64')
        url = 'https://dl.proto.bar/ftesurf/' + name
        if artifact['name'] != name or artifact['url'] != url:
            raise ValueError('smoke requires canonical production launcher URLs')
        data, _ = get(url, 32 * 1024 * 1024, root, platform + '-launcher')
        if len(data) != artifact['bytes'] or hashlib.sha256(data).hexdigest() != artifact['sha256'].lower():
            raise ValueError('downloaded launcher differs from prepared build')
        install = root / platform
        install.mkdir()
        (install / ('ftesurf-launcher.exe' if platform == 'win64' else 'ftesurf-launcher')).write_bytes(data)
        files = [f for f in payload['files'] if f['platform'] == platform]
        zone = next(f['path'] for f in files if f['path'].startswith('ftesurf/maps/zones/local/') and f['path'].endswith('.json'))
        sentinels = {'ftesurf/ftesurf.cfg': b'// synthetic release smoke settings\n',
                     'ftesurf/data/release-smoke-sentinel.txt': b'synthetic player-data sentinel\n',
                     zone: b'{"synthetic_user_edit":true}\n'}
        for rel, content in sentinels.items():
            path = install / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        run_launcher(install, platform, distro)
        for rel, content in sentinels.items():
            if (install / rel).read_bytes() != content:
                raise ValueError('launcher changed a protected synthetic sentinel')
        checked = 0
        for f in files:
            if f['path'] in sentinels:
                continue
            path = install / f['path']
            updatefeed.no_link(path)
            actual = path.read_bytes()
            if len(actual) != f['size'] or hashlib.blake2b(actual, digest_size=32).hexdigest() != f['hash']:
                raise ValueError('installed managed file differs from signed feed: ' + f['path'])
            checked += 1
        results.append({'platform': platform, 'launcher_sha256': artifact['sha256'], 'managed_files_rehashed': checked,
                        'protected_sentinels': len(sentinels), 'no_game_launch': True})
        print(f'{platform}: default HTTPS; {checked} managed files rehashed; {len(sentinels)} sentinels preserved; no game launch')
    return {'version': version, 'feed_sha256': sha, 'platforms': results}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--receipt', type=Path, required=True)
    ap.add_argument('--receipt-sha256', required=True)
    ap.add_argument('--work-root', type=Path, required=True)
    ap.add_argument('--distro', default='Ubuntu-22.04')
    a = ap.parse_args()
    receipt = expected_receipt(a.receipt, a.receipt_sha256)
    root = a.work_root.resolve()
    updatefeed.no_link(a.work_root)
    if root.exists() or not any((p / 'OWNER.md').is_file() for p in root.parents):
        ap.error('fresh smoke folder under an existing owned task root required')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', a.distro):
        ap.error('invalid WSL distro name')
    root.mkdir(parents=True)
    owner = root / 'OWNER.md'
    owner.write_text('Owned release-smoke synthetic installs. Status: active. Never a real player install.\n')
    proof = {'utc': datetime.now(timezone.utc).isoformat(), 'receipt_sha256': a.receipt_sha256.lower(), 'passed': False}
    try:
        proof.update(smoke(receipt, root, a.distro))
        proof['passed'] = True
    finally:
        (root / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')
        owner.write_text('Owned release-smoke synthetic installs. Status: ' + ('passed' if proof['passed'] else 'failed') + '; retain proof/logs, disposable payloads.\n')


if __name__ == '__main__':
    main()
