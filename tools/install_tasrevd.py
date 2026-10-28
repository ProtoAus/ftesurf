#!/usr/bin/env python3
"""P1091: owner/root installation of the NEW isolated TAS revision service; default dry run.

Modelled on install_zonepub.py: a clean inspected source commit, an exact nginx predecessor
hash and --apply. Never changes or restarts surfd, its DB, zonepub or a lobby. Refuses existing
destination files rather than taking over a peer's. The released-code list (codes.txt) is
seeded from --code (sha256 of each released or deployed csprogs.dat) and only ever appended to.
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path('/srv/nvme/ftesurf-ops/tasrevd')
STATE = Path('/srv/nvme/ftesurf-ops/tasrevd-state')
ENABLED = Path('/etc/nginx/sites-enabled/play.proto.bar.conf')
SITE = ENABLED.resolve() if ENABLED.is_symlink() else ENABLED
BACKUPS = Path('/etc/nginx')   # never sites-enabled: a backup there would be loaded as config
SNIPPET = Path('/etc/nginx/snippets/ftesurf-tasrevd.conf')
UNIT = Path('/etc/systemd/system/ftesurf-tasrevd.service')
PORT = 8089
NGINX = '''location ^~ /api/tasrev/ {
    limit_except GET POST { deny all; }
    client_max_body_size 4100k;
    proxy_pass http://127.0.0.1:%d;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_connect_timeout 2s;
    proxy_read_timeout 30s;
    proxy_send_timeout 30s;
    access_log off;
}
''' % PORT
FILES = {'surfd/tasrevd.py': 'tasrevd.py', 'surfd/tasrevd_wsgi.py': 'tasrevd_wsgi.py',
         'surfd/accounts.py': 'accounts.py', 'surfd/steam.py': 'steam.py',   # accounts imports steam
         'tools/tasrev.py': 'tools/tasrev.py', 'tools/ed25519.py': 'tools/ed25519.py'}
HEX64 = re.compile('[0-9a-f]{64}')


def sha(body): return hashlib.sha256(body).hexdigest()
def run(*args): return subprocess.run(args, check=True, capture_output=True, timeout=30)
def safe_path(p):
    if not re.fullmatch(r'/[a-zA-Z0-9_./-]+', str(p)) or '..' in Path(p).parts: raise ValueError('Unsafe configured path')


def check_accounts(path):
    with contextlib.closing(sqlite3.connect('file:' + str(path) + '?mode=ro', uri=True)) as db:
        db.execute('SELECT steamid,banned_at FROM accounts LIMIT 0')
        db.execute('SELECT pub,steamid FROM keylinks LIMIT 0')


def check_port():
    with socket.socket() as probe: probe.bind(('127.0.0.1', PORT))


def check_imports(blobs):
    # The release directory holds only FILES: they must import with nothing else beside them.
    with tempfile.TemporaryDirectory() as d:
        for dest, body in blobs.items():
            p = Path(d) / dest; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(body)
        env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
        env['SURFD_TOOLS'] = str(Path(d) / 'tools')
        r = subprocess.run([sys.executable, '-c', 'import tasrevd, accounts; tasrevd.load_tasrev()'],
                           cwd=d, env=env, capture_output=True, timeout=30)
    if r.returncode: raise RuntimeError('Service files do not import on their own: ' + r.stderr.decode(errors='replace')[-400:])


def probe_app(commit, url='http://127.0.0.1:%d/api/tasrev/map/tasrevd_install_probe' % PORT):
    with urllib.request.urlopen(url, timeout=10) as response:
        if response.headers.get('X-Tasrevd-Source') != commit: raise RuntimeError('Unexpected serving source')
        body = json.loads(response.read(65536))
    if body.get('ok') != 1 or body.get('revisions') != []: raise RuntimeError('New service map control did not act')


def unit_text(release, env):
    entries = ''.join('Environment="%s=%s"\n' % (k, v.replace('\\', '\\\\').replace('"', '\\"')) for k, v in env.items())
    return """[Unit]
Description=World of Surf TAS revisions and author statements (P1091)
After=network.target
[Service]
User=proto
Group=proto
UMask=0077
WorkingDirectory=%s
ExecStart=/usr/bin/python3 -m gunicorn --bind 127.0.0.1:%d --workers 1 --threads 4 --timeout 30 --access-logfile /dev/null tasrevd_wsgi:app
%sRestart=on-failure
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=%s
[Install]
WantedBy=multi-user.target
""" % (release, PORT, entries, STATE)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--commit', required=True)
    ap.add_argument('--expected-nginx-sha256', required=True)
    ap.add_argument('--account-db', type=Path, default=Path('/srv/nvme/surfd/data/surfd.db'))
    ap.add_argument('--code', action='append', default=[], help='sha256 of a released or deployed csprogs.dat; repeatable')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', a.commit): ap.error('Expected full inspected source SHA')
    if not re.fullmatch('[0-9a-f]{64}', a.expected_nginx_sha256): ap.error('Expected exact predecessor nginx SHA256')
    if not a.code or not all(HEX64.fullmatch(c) for c in a.code): ap.error('At least one --code (64 lowercase hex)')
    for p in (a.source, a.account_db): safe_path(p)
    if run('git', '-C', str(a.source), 'rev-parse', 'HEAD').stdout.decode().strip() != a.commit: raise RuntimeError('Source ref differs')
    if run('git', '-C', str(a.source), 'status', '--porcelain', '--', *FILES).stdout: raise RuntimeError('Service source is not clean at the inspected commit')
    blobs = {dest: (a.source / src).read_bytes() for src, dest in FILES.items()}
    before = SITE.read_bytes()
    if sha(before) != a.expected_nginx_sha256: raise RuntimeError('nginx changed; inspect again')
    anchor = b'include snippets/surfd.conf;'
    if before.count(anchor) != 1: raise RuntimeError('Expected one existing public surfd include')
    if any(p.exists() or p.is_symlink() for p in (SNIPPET, UNIT, STATE, ROOT / a.commit)):
        raise RuntimeError('Destination already exists; do not overwrite a peer/previous installation')
    if not a.account_db.is_file(): raise RuntimeError('Configured accounts DB absent')
    check_accounts(a.account_db)
    check_port()
    if run('/usr/bin/systemctl', 'show', '--value', '--property=LoadState', 'ftesurf-tasrevd.service').stdout.decode().strip() != 'not-found':
        raise RuntimeError('Existing loaded unit requires owner inspection')
    check_imports(blobs)
    backup = BACKUPS / (SITE.name + '.pre-tasrevd-' + a.commit[:12])
    if backup.exists(): raise RuntimeError('nginx backup collision; nothing overwritten')
    run('/usr/bin/python3', '-c', 'import flask,gunicorn')
    print('Preflight: clean source, exact nginx predecessor, separate new service/state, %d released codes' % len(a.code))
    if not a.apply:
        print('DRY RUN: no changes; owner may rerun under sudo with --apply')
        return
    if os.geteuid() != 0: raise RuntimeError('Owner sudo/root is required for --apply')
    release = ROOT / a.commit
    release.mkdir(parents=True, mode=0o755)
    for dest, body in blobs.items():
        p = release / dest; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(body); p.chmod(0o644)
    (release / 'SOURCE.json').write_text(json.dumps(dict(commit=a.commit, files={k: sha(v) for k, v in blobs.items()}), indent=2) + '\n')
    owner = pwd.getpwnam('proto'); STATE.mkdir(mode=0o700); os.chown(STATE, owner.pw_uid, owner.pw_gid)
    run('/usr/sbin/runuser', '-u', 'proto', '--', '/usr/bin/python3', str(release / 'tasrevd.py'), '--store', str(STATE / 'tasrev.sqlite3'), 'init')
    codes = STATE / 'codes.txt'; codes.write_text(''.join(c + '\n' for c in a.code)); os.chown(codes, owner.pw_uid, owner.pw_gid); codes.chmod(0o600)
    env = dict(TASREVD_STORE=str(STATE / 'tasrev.sqlite3'), TASREVD_ACCOUNTS=str(a.account_db), TASREVD_CODES=str(codes),
               SURFD_TOOLS=str(release / 'tools'), TASREVD_SOURCE=a.commit)
    unit = unit_text(release, env)
    wanted = before.replace(anchor, anchor + b'\n    include snippets/ftesurf-tasrevd.conf;')
    backup.write_bytes(before); backup.chmod(0o600)
    written = unit_written = False
    try:
        with UNIT.open('x') as f: f.write(unit)
        unit_written = True
        with SNIPPET.open('xb') as f: f.write(NGINX.encode())
        run('/usr/bin/systemctl', 'daemon-reload')
        run('/usr/bin/systemctl', 'enable', '--now', 'ftesurf-tasrevd.service')
        for attempt in range(20):
            try: probe_app(a.commit); break
            except (OSError, ValueError, RuntimeError):
                if attempt == 19: raise
                time.sleep(.25)
        if SITE.read_bytes() != before: raise RuntimeError('nginx changed during service setup')
        SITE.write_bytes(wanted); written = True
        run('/usr/sbin/nginx', '-t')
        if b'location ^~ /api/tasrev/' not in run('/usr/sbin/nginx', '-T').stdout:
            raise RuntimeError('nginx -T does not show the tasrev route; nothing is public')
        run('/usr/bin/systemctl', 'reload', 'nginx')
        for attempt in range(20):
            try: probe_app(a.commit, 'https://play.proto.bar/api/tasrev/map/tasrevd_install_probe'); break
            except (OSError, ValueError, RuntimeError):
                if attempt == 19: raise
                time.sleep(.5)
    except Exception:
        if written and SITE.read_bytes() == wanted:
            SITE.write_bytes(before); run('/usr/sbin/nginx', '-t'); run('/usr/bin/systemctl', 'reload', 'nginx')
        if unit_written:
            if UNIT.read_text() != unit: raise RuntimeError('Unit changed; foreign service not stopped')
            run('/usr/bin/systemctl', 'disable', '--now', 'ftesurf-tasrevd.service')
        raise   # source, state, unit, snippet and backup stay for inspection
    print('Installed the TAS revision service at https://play.proto.bar/api/tasrev/')


if __name__ == '__main__': main()
