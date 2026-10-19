#!/usr/bin/env python3
"""Owner/root installation of a NEW isolated zone upload/publish service; default dry run.

Requires a clean inspected source commit, an exact nginx predecessor hash, and
--apply. Never changes/restarts surfd, its DB/schema, or a lobby. No role grants.
Refuses existing destination files rather than taking ownership of a peer service.
--upgrade (P826) moves the installed service onto a new release and nothing else.
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path('/srv/nvme/ftesurf-ops/zonepub')
STATE = Path('/srv/nvme/ftesurf-ops/zonepub-state')
# The file nginx LOADS (nginx.conf includes sites-enabled/*). On the Pi it is a regular file, not a
# link to sites-available, so the first install edited a copy nginx never read and probed a 404.
ENABLED = Path('/etc/nginx/sites-enabled/play.proto.bar.conf')
SITE = ENABLED.resolve() if ENABLED.is_symlink() else ENABLED
BACKUPS = Path('/etc/nginx')   # never sites-enabled: a backup there would be loaded as config
SNIPPET = Path('/etc/nginx/snippets/ftesurf-zonepub.conf')
UNIT = Path('/etc/systemd/system/ftesurf-zonepub.service')
# P815: where an admin's accepted upload is written -- the lobbies' timing copy, then the site's.
PUBLISH = (Path('/srv/nvme/ftesurf-server/game/ftesurf/maps/zones/local'), Path('/srv/nvme/ftesurf-site/zones'))
NGINX = '''location ^~ /api/zones/ {
    limit_except POST { deny all; }
    client_max_body_size 264k;
    proxy_pass http://127.0.0.1:8087;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_connect_timeout 2s;
    proxy_read_timeout 15s;
    proxy_send_timeout 15s;
    access_log off;
}
'''
FILES = {'surfd/zonepub.py':'zonepub.py', 'surfd/zonepub_wsgi.py':'zonepub_wsgi.py',
         'surfd/zonepub_publish.py':'zonepub_publish.py',
         'surfd/accounts.py':'accounts.py', 'surfd/steam.py':'steam.py',   # accounts imports steam
         'tools/ed25519.py':'tools/ed25519.py'}


def sha(body): return hashlib.sha256(body).hexdigest()
def run(*args): return subprocess.run(args, check=True, capture_output=True, timeout=30)
def safe_path(p):
    if not re.fullmatch(r'/[a-zA-Z0-9_./-]+', str(p)) or '..' in p.parts: raise ValueError('Unsafe configured path')


def check_accounts(path):
    # The real DB is data/surfd.db; a historical empty sibling also exists.
    with contextlib.closing(sqlite3.connect('file:'+str(path)+'?mode=ro', uri=True)) as db:
        db.execute('SELECT steamid,banned_at FROM accounts LIMIT 0')
        db.execute('SELECT pub,steamid FROM keylinks LIMIT 0')


def check_port(port=8087):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', port))


def check_imports(blobs):
    # The release directory holds only FILES: they must import with nothing else beside them
    # (the first --apply died in `init` on accounts.py's `import steam`).
    with tempfile.TemporaryDirectory() as d:
        for dest, body in blobs.items():
            p = Path(d) / dest; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(body)
        env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
        r = subprocess.run([sys.executable, '-c', 'import zonepub, zonepub_publish, accounts'],
                           cwd=d, env=env, capture_output=True, timeout=30)
    if r.returncode:
        raise RuntimeError('Service files do not import on their own: ' + r.stderr.decode(errors='replace')[-400:])


def check_unit():
    state=run('/usr/bin/systemctl','show','--value','--property=LoadState','ftesurf-zonepub.service').stdout.decode().strip()
    if state!='not-found': raise RuntimeError('Existing loaded unit requires owner inspection')


def service_witness(release):
    pid=int(run('/usr/bin/systemctl','show','--value','--property=MainPID','ftesurf-zonepub.service').stdout)
    if pid<2: raise RuntimeError('New service has no live master')
    proc=Path('/proc')/str(pid)
    start=proc.joinpath('stat').read_text().rpartition(')')[2].split()[19]
    if proc.joinpath('cwd').resolve()!=release.resolve() or proc.joinpath('exe').resolve()!=Path('/usr/bin/python3').resolve():
        raise RuntimeError('New service process origin differs')
    if b'zonepub_wsgi:app' not in proc.joinpath('cmdline').read_bytes(): raise RuntimeError('Unexpected service application')
    listening={line.split()[9] for line in Path('/proc/net/tcp').read_text().splitlines()[1:]
               if line.split()[1]=='0100007F:1F97' and line.split()[3]=='0A'}
    owned=set()
    for fd in proc.joinpath('fd').iterdir():
        try: target=os.readlink(fd)
        except FileNotFoundError: continue
        if target.startswith('socket:['): owned.add(target[8:-1])
    if len(listening)!=1 or not listening.issubset(owned): raise RuntimeError('Loopback listener is not owned by this service')
    return pid,start


def probe_app(commit, url='http://127.0.0.1:8087/api/zones/challenge'):
    request=urllib.request.Request(url, data=json.dumps(dict(map='zonepub_install_probe',sha='0'*64)).encode(),
                                   headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.headers.get('X-Zonepub-Source')!=commit: raise RuntimeError('Unexpected serving source')
        body=json.loads(response.read(4096))
    if body.get('ok') != 1 or not re.fullmatch('[0-9a-f]{32}',body.get('nonce','')):
        raise RuntimeError('New service challenge control did not act')


def unit_text(release, env, writable):
    unit = """[Unit]
Description=World of Surf admin zone uploads (published on acceptance)
After=network.target
[Service]
User=proto
Group=proto
UMask=0077
WorkingDirectory=%s
ExecStart=/usr/bin/python3 -m gunicorn --bind 127.0.0.1:8087 --workers 1 --threads 2 --timeout 15 --access-logfile /dev/null zonepub_wsgi:app
Restart=on-failure
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=%s
[Install]
WantedBy=multi-user.target
""" % (release, ' '.join(writable))
    # systemd quoted Environment syntax: JSON quotes/backslashes are escaped.
    unit += '\n'  # add Environment within Service, not Install
    entries = ''.join('Environment="%s=%s"\n' % (k, v.replace('\\', '\\\\').replace('"', '\\"')) for k, v in env.items())
    return unit.replace('Restart=on-failure\n', entries + 'Restart=on-failure\n')


def upgraded_unit(old, new_commit):
    """P826: the installed unit with only its release swapped -- WorkingDirectory, SURFD_TOOLS and
    ZONEPUB_SOURCE; everything else (games, publish dirs, sandbox) stays as installed."""
    root = ROOT.as_posix()
    m = re.search(r'^WorkingDirectory=%s/([0-9a-f]{40})$' % re.escape(root), old, re.M)
    if not m: raise RuntimeError('The installed unit names no release under ' + root)
    cur = m.group(1)
    if cur == new_commit: raise RuntimeError('That release is already the installed one')
    if old.count('Environment="ZONEPUB_SOURCE=%s"\n' % cur) != 1: raise RuntimeError('The installed unit does not name its source once')
    new = old.replace('%s/%s' % (root, cur), '%s/%s' % (root, new_commit)).replace('ZONEPUB_SOURCE=' + cur, 'ZONEPUB_SOURCE=' + new_commit)
    if sum(1 for x, y in zip(old.splitlines(), new.splitlines()) if x != y) != 3:
        raise RuntimeError('Unexpected unit shape; inspect it before upgrading')
    return cur, new


def healthy(release, commit, url):
    for attempt in range(20):       # a restart's or a reload's old workers answer for a moment
        try:
            witness = service_witness(release); probe_app(commit, url)
            if service_witness(release) != witness: raise RuntimeError('Service master changed during probe')
            return witness
        except (OSError, ValueError, RuntimeError):
            if attempt == 19: raise
            time.sleep(.5)


def upgrade(a):
    """P826: the running service onto a new release. State, role grants, nginx and the unit's other
    lines are kept; a failure puts the old unit back and the old release serving again."""
    if run('git','-C',str(a.source),'rev-parse','HEAD').stdout.decode().strip()!=a.commit: raise RuntimeError('Source ref differs')
    if run('git','-C',str(a.source),'status','--porcelain','--',*FILES).stdout: raise RuntimeError('Service source is not clean at the inspected commit')
    blobs={dest:(a.source/src).read_bytes() for src,dest in FILES.items()}
    if UNIT.is_symlink() or not UNIT.is_file() or not STATE.is_dir() or not SNIPPET.is_file():
        raise RuntimeError('No installed zone service to upgrade (unit, state and nginx snippet)')
    old=UNIT.read_text()
    cur,new=upgraded_unit(old,a.commit)
    release=ROOT/a.commit
    if release.exists() or release.is_symlink(): raise RuntimeError('That release directory already exists')
    if run('/usr/bin/systemctl','show','--value','--property=ActiveState','ftesurf-zonepub.service').stdout.decode().strip()!='active':
        raise RuntimeError('The installed service is not running; inspect it before upgrading')
    check_imports(blobs)
    probe_app(cur)                  # the starting point answers as the release its unit names
    print('Preflight: clean source; installed release %s answers; state, grants and nginx are kept' % cur[:12])
    if not a.apply:
        print('DRY RUN: no changes; owner may rerun under sudo with --apply')
        return
    if os.geteuid()!=0: raise RuntimeError('Owner sudo/root is required for --apply')
    release.mkdir(mode=0o755)
    for dest,body in blobs.items():
        p=release/dest;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body);p.chmod(0o644)
    (release/'SOURCE.json').write_text(json.dumps(dict(commit=a.commit,files={k:sha(v) for k,v in blobs.items()}),indent=2)+'\n')
    # The schema is CREATE ... IF NOT EXISTS: a release's new tables, nothing else.
    run('/usr/sbin/runuser','-u','proto','--','/usr/bin/python3',str(release/'zonepub.py'),'--store',str(STATE/'zones.sqlite3'),'init')
    def put(text):
        tmp=UNIT.with_name(UNIT.name+'.upgrade-tmp'); tmp.write_text(text); tmp.chmod(0o644); os.replace(tmp,UNIT)
        run('/usr/bin/systemctl','daemon-reload'); run('/usr/bin/systemctl','restart','ftesurf-zonepub.service')
    put(new)
    try:
        healthy(release,a.commit,'http://127.0.0.1:8087/api/zones/challenge')
        healthy(release,a.commit,'https://play.proto.bar/api/zones/challenge')
    except Exception:
        put(old)
        healthy(ROOT/cur,cur,'http://127.0.0.1:8087/api/zones/challenge')
        print('Upgrade failed: release %s is serving again; %s is kept for inspection' % (cur[:12], release))
        raise
    print('Upgraded the zone service to %s; release %s stays on disk as the way back' % (a.commit[:12], cur[:12]))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--commit', required=True)
    ap.add_argument('--expected-nginx-sha256')
    ap.add_argument('--account-db', type=Path, default=Path('/srv/nvme/surfd/data/surfd.db'))
    ap.add_argument('--game', type=Path, action='append')
    ap.add_argument('--publish-dir', type=Path, action='append',
                    help="repeatable; default the lobbies' and the site's zone folders")
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--upgrade', action='store_true', help='move the installed service onto --commit (P826)')
    a=ap.parse_args()
    if not re.fullmatch('[0-9a-f]{40}',a.commit): ap.error('Expected full inspected source SHA')
    if a.upgrade:
        safe_path(a.source)
        return upgrade(a)
    if not a.expected_nginx_sha256 or not a.game: ap.error('A new install needs --expected-nginx-sha256 and --game')
    if not re.fullmatch('[0-9a-f]{64}',a.expected_nginx_sha256): ap.error('Expected exact predecessor nginx SHA256')
    publish=tuple(a.publish_dir or PUBLISH)
    for p in (a.source,a.account_db,*a.game,*publish): safe_path(p)
    # P815: a proof names the csprogs that signed it; a .prev is the pre-publish client,
    # whose upload flow (any server, any click) must not reach the publish directories.
    if any(p.name != 'csprogs.dat' for p in a.game): raise RuntimeError('--game takes deployed csprogs.dat files only, no .prev')
    for d in publish:
        if d.is_symlink() or not d.is_dir() or d.stat().st_uid!=pwd.getpwnam('proto').pw_uid:
            raise RuntimeError('Publish folder must be a real directory owned by proto: %s'%d)
    if run('git','-C',str(a.source),'rev-parse','HEAD').stdout.decode().strip()!=a.commit: raise RuntimeError('Source ref differs')
    status=run('git','-C',str(a.source),'status','--porcelain','--',*FILES).stdout
    if status: raise RuntimeError('Service source is not clean at the inspected commit')
    blobs={dest:(a.source/src).read_bytes() for src,dest in FILES.items()}
    before=SITE.read_bytes()
    if sha(before)!=a.expected_nginx_sha256: raise RuntimeError('nginx changed; inspect again')
    anchor=b'include snippets/surfd.conf;'
    if before.count(anchor)!=1: raise RuntimeError('Expected one existing public surfd include')
    if any(p.exists() or p.is_symlink() for p in (SNIPPET,UNIT,STATE,ROOT/a.commit)):
        raise RuntimeError('Destination already exists; do not overwrite a peer/previous installation')
    if not a.account_db.is_file() or any(not p.is_file() for p in a.game): raise RuntimeError('Configured DB/game absent')
    check_accounts(a.account_db)
    check_port()
    check_unit()
    check_imports(blobs)
    backup=BACKUPS/(SITE.name+'.pre-zonepub-'+a.commit[:12])
    if backup.exists(): raise RuntimeError('nginx backup collision; nothing overwritten')
    run('/usr/bin/python3','-c','import flask,gunicorn')
    print('Preflight: clean source, exact nginx predecessor, separate new service/state, no role grants')
    print('Publishes accepted admin uploads into: '+', '.join(str(p) for p in publish))
    if not a.apply:
        print('DRY RUN: no changes; owner may rerun under sudo with --apply')
        return
    if os.geteuid()!=0: raise RuntimeError('Owner sudo/root is required for --apply')
    release=ROOT/a.commit
    release.mkdir(parents=True,mode=0o755)
    for dest,body in blobs.items():
        p=release/dest;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body);p.chmod(0o644)
    (release/'SOURCE.json').write_text(json.dumps(dict(commit=a.commit,files={k:sha(v) for k,v in blobs.items()}),indent=2)+'\n')
    owner=pwd.getpwnam('proto');STATE.mkdir(mode=0o700);os.chown(STATE,owner.pw_uid,owner.pw_gid)
    run('/usr/sbin/runuser','-u','proto','--','/usr/bin/python3',str(release/'zonepub.py'),'--store',str(STATE/'zones.sqlite3'),'init')
    env=dict(ZONEPUB_STORE=str(STATE/'zones.sqlite3'),ZONEPUB_ACCOUNTS=str(a.account_db),
             ZONEPUB_GAMES=json.dumps([str(p) for p in a.game],separators=(',',':')),SURFD_TOOLS=str(release/'tools'),ZONEPUB_SOURCE=a.commit,
             ZONEPUB_PUBLISH=json.dumps([str(p) for p in publish],separators=(',',':')))
    unit=unit_text(release,env,[str(p) for p in (STATE,*publish)])
    snippet=NGINX.encode(); wanted=before.replace(anchor,anchor+b'\n    include snippets/ftesurf-zonepub.conf;')
    backup.write_bytes(before);backup.chmod(0o600)
    written=unit_written=False
    try:
        with UNIT.open('x') as f: f.write(unit)
        unit_written=True
        with SNIPPET.open('xb') as f: f.write(snippet)
        run('/usr/bin/systemctl','daemon-reload')
        run('/usr/bin/systemctl','enable','--now','ftesurf-zonepub.service')
        run('/usr/bin/systemctl','is-active','--quiet','ftesurf-zonepub.service')
        for attempt in range(20):
            try:
                witness=service_witness(release);probe_app(a.commit)
                if service_witness(release)!=witness: raise RuntimeError('New service master changed during probe')
                break
            except (OSError, ValueError, RuntimeError):
                if attempt==19: raise
                time.sleep(.25)
        if SITE.read_bytes()!=before: raise RuntimeError('nginx changed during service setup')
        SITE.write_bytes(wanted);written=True
        run('/usr/sbin/nginx','-t')
        # The route must be in the configuration nginx loads, not only in the file written.
        if b'location ^~ /api/zones/' not in run('/usr/sbin/nginx','-T').stdout:
            raise RuntimeError('nginx -T does not show the zone route; nothing is public')
        run('/usr/bin/systemctl','reload','nginx')
        for attempt in range(20):       # a reload's old workers answer for a moment
            try:
                probe_app(a.commit,'https://play.proto.bar/api/zones/challenge'); break
            except (OSError, ValueError, RuntimeError):
                if attempt==19: raise
                time.sleep(0.5)
        if service_witness(release)!=witness: raise RuntimeError('Service master changed during public verification')
    except Exception:
        if written and SITE.read_bytes()==wanted:
            SITE.write_bytes(before)
            run('/usr/sbin/nginx','-t');run('/usr/bin/systemctl','reload','nginx')
        if unit_written:
            if UNIT.read_text()!=unit: raise RuntimeError('Unit changed; foreign service not stopped')
            run('/usr/bin/systemctl','disable','--now','ftesurf-zonepub.service')
        # Keep exact source/state/unit/snippet and backup for inspection; do not
        # blanket-remove a partially installed service or any operator data.
        raise
    print('Installed independent zone service; all accounts still denied until explicit grants')


if __name__=='__main__': main()
