#!/usr/bin/env python3
"""P1091: owner/root installation of the NEW isolated TAS revision service; default dry run.

Modelled on install_zonepub.py: a clean inspected source commit, an exact nginx predecessor
hash and --apply (the files are the commit's git objects). Never changes or restarts surfd, its DB, zonepub or a lobby. Refuses existing
destination files rather than taking over a peer's. The released-code list (codes.txt) is
seeded from --code (sha256 of each released or deployed csprogs.dat) and only ever appended to.

P1119 --upgrade-from <installed commit>: a new release under RELEASES (every directory above it
root's alone), and the unit pointed at it. Root runs nothing a proto-owned tree controls: git and
the import check run as the checkout's owner and as proto. Only when the unit is byte for byte what this installer wrote for that release and
the nginx snippet is unchanged; state, codes and nginx are not touched. The old unit is put back
and restarted if the new release does not serve its own source.
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import signal
import socket
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path('/srv/nvme/ftesurf-ops/tasrevd')
RELEASES = Path('/opt/ftesurf-tasrevd')   # P1119: upgrades; /srv/nvme/ftesurf-ops above ROOT is proto's
STATE = Path('/srv/nvme/ftesurf-ops/tasrevd-state')
ENABLED = Path('/etc/nginx/sites-enabled/play.proto.bar.conf')
SITE = ENABLED.resolve() if ENABLED.is_symlink() else ENABLED
BACKUPS = Path('/etc/nginx')   # never sites-enabled: a backup there would be loaded as config
SNIPPET = Path('/etc/nginx/snippets/ftesurf-tasrevd.conf')
UNIT = Path('/etc/systemd/system/ftesurf-tasrevd.service')
PORT = 8089
NGINX = '''location ^~ /api/tasrev/ {
    limit_except GET POST { deny all; }
    client_max_body_size 4800k;
    proxy_pass http://127.0.0.1:%d;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_connect_timeout 2s;
    proxy_read_timeout 120s;      # a 96000-row upload parses for tens of seconds on the Pi
    proxy_send_timeout 30s;
    access_log off;
}
''' % PORT
FILES = {'surfd/tasrevd.py': 'tasrevd.py', 'surfd/tasrevd_wsgi.py': 'tasrevd_wsgi.py',
         'surfd/accounts.py': 'accounts.py', 'surfd/steam.py': 'steam.py',   # accounts imports steam
         'tools/tasrev.py': 'tools/tasrev.py', 'tools/ed25519.py': 'tools/ed25519.py'}
HEX64 = re.compile('[0-9a-f]{64}')


def sha(body): return hashlib.sha256(body).hexdigest()
def run(*args, timeout=30, **kw): return subprocess.run(args, check=True, capture_output=True, timeout=timeout, **kw)
def as_user(name, *args):
    # P1119: as root, a command over a proto-owned tree runs as its owner (repo config, release code).
    return (('/usr/sbin/runuser', '-u', name, '--') + args) if os.geteuid() == 0 else args
def safe_path(p):
    if not re.fullmatch(r'/[a-zA-Z0-9_./-]+', str(p)) or '..' in Path(p).parts: raise ValueError('Unsafe configured path')


def check_accounts(path):
    with contextlib.closing(sqlite3.connect('file:' + str(path) + '?mode=ro', uri=True)) as db:
        db.execute('SELECT steamid,banned_at FROM accounts LIMIT 0')
        db.execute('SELECT pub,steamid FROM keylinks LIMIT 0')


def check_port():
    with socket.socket() as probe: probe.bind(('127.0.0.1', PORT))


def check_imports(blobs):
    # The release directory holds only FILES: they must import with nothing else beside them, as proto.
    with tempfile.TemporaryDirectory() as d:
        os.chmod(d, 0o755)
        for dest, body in blobs.items():
            p = Path(d) / dest; p.parent.mkdir(parents=True, exist_ok=True); p.parent.chmod(0o755); p.write_bytes(body); p.chmod(0o644)
        env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
        env['SURFD_TOOLS'] = str(Path(d) / 'tools')
        try: run(*as_user('proto', sys.executable, '-c', 'import tasrevd, accounts; tasrevd.load_tasrev()'), cwd=d, env=env)
        except subprocess.CalledProcessError as e:
            raise RuntimeError('Service files do not import on their own: ' + (e.stderr or b'').decode(errors='replace')[-400:])


def probe_app(commit, url='http://127.0.0.1:%d/api/tasrev/map/tasrevd_install_probe' % PORT):
    with urllib.request.urlopen(url, timeout=10) as response:
        if response.headers.get('X-Tasrevd-Source') != commit: raise RuntimeError('Unexpected serving source')
        body = json.loads(response.read(65536))
    if body.get('ok') != 1 or body.get('revisions') != []: raise RuntimeError('New service map control did not act')


def service_env(release, account_db, commit):
    return dict(TASREVD_STORE=str(STATE / 'tasrev.sqlite3'), TASREVD_ACCOUNTS=str(account_db),
                TASREVD_CODES=str(STATE / 'codes.txt'), SURFD_TOOLS=str(release / 'tools'), TASREVD_SOURCE=commit)


def write_release(release, commit, blobs):
    # Modes set outright: an owner's umask 077 would leave proto unable to enter the release.
    release.mkdir(parents=True, mode=0o755); release.chmod(0o755)
    for dest, body in blobs.items():
        p = release / dest
        if p.parent != release: p.parent.mkdir(exist_ok=True); p.parent.chmod(0o755)
        p.write_bytes(body); p.chmod(0o644)
    src = release / 'SOURCE.json'
    src.write_text(json.dumps(dict(commit=commit, files={k: sha(v) for k, v in blobs.items()}), indent=2) + '\n'); src.chmod(0o644)


def source_owner(source): return pwd.getpwuid(os.stat(source).st_uid).pw_name


def commit_blobs(source, commit):
    # The commit's own bytes, not the working tree's (skip-worktree hides edits from status).
    owner = source_owner(source)
    return {dest: run(*as_user(owner, 'git', '-C', str(source), '-c', 'core.fsmonitor=false', 'cat-file', 'blob',
                               '%s:%s' % (commit, src))).stdout
            for src, dest in FILES.items()}


def await_probe(commit, url=None, tries=20, pause=.25):
    for attempt in range(tries):
        try: probe_app(commit, url) if url else probe_app(commit); return
        except (OSError, ValueError, RuntimeError):
            if attempt == tries - 1: raise
            time.sleep(pause)


def replace_unit(body):
    tmp = UNIT.with_name(UNIT.name + '.p1119-new')
    tmp.write_bytes(body); tmp.chmod(0o644); os.replace(tmp, UNIT)


def unit_property(name):
    return run('/usr/bin/systemctl', 'show', '--value', '--property=' + name, 'ftesurf-tasrevd.service').stdout.decode().strip()


def check_chain(path):
    # Root writes the release here: the directory and all above it must be root's, unlinked, unshared.
    for p in [path] + list(path.parents):
        st = os.lstat(p)
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
            raise RuntimeError('%s is not a directory only root can write' % p)


def rollback(oldunit, newunit, oldcommit, why):
    """Puts the old unit back and proves it serves; returns what happened, for the error."""
    try:
        if UNIT.read_bytes() != newunit:
            return 'upgrade failed (%r) and the unit changed meanwhile: left as it is; owner inspection' % why
        replace_unit(oldunit)
        try: run('/usr/bin/systemctl', 'reset-failed', 'ftesurf-tasrevd.service')
        except subprocess.CalledProcessError: pass   # not failed: nothing to reset
        run('/usr/bin/systemctl', 'daemon-reload')
        run('/usr/bin/systemctl', 'restart', 'ftesurf-tasrevd.service', timeout=120)
        await_probe(oldcommit)
    except BaseException as e:
        return ('upgrade failed (%r); the old unit is back but did not serve (%r): systemctl status ftesurf-tasrevd'
                % (why, e))
    return 'upgrade failed (%r); rolled back, %s serves again (the new release directory stays)' % (why, oldcommit[:12])


def upgrade(a, blobs):
    """P1119: the installed release `a.upgrade_from` -> `a.commit`; see the module doc."""
    old = RELEASES / a.upgrade_from if (RELEASES / a.upgrade_from).is_dir() else ROOT / a.upgrade_from
    new = RELEASES / a.commit
    if a.upgrade_from == a.commit: raise RuntimeError('Upgrade to the installed commit')
    if any(p.exists() or p.is_symlink() for p in (new, ROOT / a.commit)): raise RuntimeError('The new release directory already exists')
    if json.loads((old / 'SOURCE.json').read_text()).get('commit') != a.upgrade_from:
        raise RuntimeError('The old release directory is not that commit')
    oldunit = unit_text(old, service_env(old, a.account_db, a.upgrade_from)).encode()
    if UNIT.read_bytes() != oldunit: raise RuntimeError('The unit is not the one this installer wrote for that release; owner inspection')
    if SNIPPET.read_bytes() != NGINX.encode(): raise RuntimeError('The nginx snippet changed; owner inspection')
    if not (STATE / 'tasrev.sqlite3').is_file() or not (STATE / 'codes.txt').is_file(): raise RuntimeError('Service state missing')
    if unit_property('ActiveState') != 'active': raise RuntimeError('The service is not running; owner inspection')
    if unit_property('DropInPaths') or unit_property('NeedDaemonReload') != 'no' or unit_property('FragmentPath') != str(UNIT):
        raise RuntimeError('The unit has drop-ins, a pending reload or another unit file; owner inspection')
    check_chain(RELEASES if RELEASES.exists() or RELEASES.is_symlink() else RELEASES.parent)
    probe_app(a.upgrade_from)   # what serves now is the old release
    check_accounts(a.account_db)
    check_imports(blobs)
    print('Preflight (upgrade): the commit\'s files, the unit and snippet this installer wrote for %s, state present, serving it'
          % a.upgrade_from[:12])
    if not a.apply:
        print('DRY RUN: no changes; owner may rerun under sudo with --apply')
        return
    if os.geteuid() != 0: raise RuntimeError('Owner sudo/root is required for --apply')
    RELEASES.mkdir(mode=0o755, exist_ok=True); RELEASES.chmod(0o755)
    check_chain(RELEASES)
    write_release(new, a.commit, blobs)
    newunit = unit_text(new, service_env(new, a.account_db, a.commit)).encode()
    if UNIT.read_bytes() != oldunit: raise RuntimeError('The unit changed during the upgrade; nothing switched (the new release directory stays)')
    # The switch and its proof are one step: Ctrl-C or a dropped session must not leave the unit ahead of systemd.
    held = {n: signal.signal(n, signal.SIG_IGN) for n in (signal.SIGINT, signal.SIGHUP)}
    try:
        replace_unit(newunit)
        try:
            run('/usr/bin/systemctl', 'daemon-reload')
            run('/usr/bin/systemctl', 'restart', 'ftesurf-tasrevd.service', timeout=120)
            await_probe(a.commit)
            await_probe(a.commit, 'https://play.proto.bar/api/tasrev/map/tasrevd_install_probe', pause=.5)
        except BaseException as e:
            outcome = rollback(oldunit, newunit, a.upgrade_from, e)
            (new / 'UPGRADE.txt').write_text(outcome + '\n')   # for an owner whose session dropped
            raise RuntimeError(outcome) from e
    finally:
        for n, h in held.items(): signal.signal(n, h)
    outcome = 'Upgraded the TAS revision service to %s (the old release stays at %s)' % (a.commit, old)
    (new / 'UPGRADE.txt').write_text(outcome + '\n')
    print(outcome)


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
MemoryMax=384M
CPUQuota=50%%
Nice=10
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
    ap.add_argument('--expected-nginx-sha256')
    ap.add_argument('--upgrade-from', help='P1119: the installed release commit to replace')
    ap.add_argument('--account-db', type=Path, default=Path('/srv/nvme/surfd/data/surfd.db'))
    ap.add_argument('--code', action='append', default=[], help='sha256 of a released or deployed csprogs.dat; repeatable')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', a.commit): ap.error('Expected full inspected source SHA')
    if a.upgrade_from is not None:
        if not re.fullmatch('[0-9a-f]{40}', a.upgrade_from): ap.error('--upgrade-from: the installed commit, 40 lowercase hex')
        if a.expected_nginx_sha256 or a.code: ap.error('An upgrade changes neither nginx nor codes.txt')
    else:
        if not re.fullmatch('[0-9a-f]{64}', a.expected_nginx_sha256 or ''): ap.error('Expected exact predecessor nginx SHA256')
        if not a.code or not all(HEX64.fullmatch(c) for c in a.code): ap.error('At least one --code (64 lowercase hex)')
    for p in (a.source, a.account_db): safe_path(p)
    if run(*as_user(source_owner(a.source), 'git', '-C', str(a.source), 'rev-parse', 'HEAD')).stdout.decode().strip() != a.commit:
        raise RuntimeError('Source ref differs')
    blobs = commit_blobs(a.source, a.commit)
    if a.upgrade_from is not None:
        upgrade(a, blobs)
        return
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
    print('Preflight: the files of that commit, exact nginx predecessor, separate new service/state, %d released codes' % len(a.code))
    if not a.apply:
        print('DRY RUN: no changes; owner may rerun under sudo with --apply')
        return
    if os.geteuid() != 0: raise RuntimeError('Owner sudo/root is required for --apply')
    release = ROOT / a.commit
    write_release(release, a.commit, blobs)
    owner = pwd.getpwnam('proto'); STATE.mkdir(mode=0o700); os.chown(STATE, owner.pw_uid, owner.pw_gid)
    run('/usr/sbin/runuser', '-u', 'proto', '--', '/usr/bin/python3', str(release / 'tasrevd.py'), '--store', str(STATE / 'tasrev.sqlite3'), 'init')
    codes = STATE / 'codes.txt'; codes.write_text(''.join(c + '\n' for c in a.code)); os.chown(codes, owner.pw_uid, owner.pw_gid); codes.chmod(0o600)
    unit = unit_text(release, service_env(release, a.account_db, a.commit))
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
