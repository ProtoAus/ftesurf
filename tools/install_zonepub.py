#!/usr/bin/env python3
"""Owner/root installation of a NEW isolated zone upload/publish service; default dry run.

Requires a clean inspected source commit, an exact nginx predecessor hash, and
--apply. Never changes/restarts surfd, its DB/schema, or a lobby. No role grants.
Refuses existing destination files rather than taking ownership of a peer service.
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
import time
import urllib.request

ROOT = Path('/srv/nvme/ftesurf-ops/zonepub')
STATE = Path('/srv/nvme/ftesurf-ops/zonepub-state')
SITE = Path('/etc/nginx/sites-available/play.proto.bar.conf')
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
         'surfd/accounts.py':'accounts.py', 'tools/ed25519.py':'tools/ed25519.py'}


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


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--commit', required=True)
    ap.add_argument('--expected-nginx-sha256', required=True)
    ap.add_argument('--account-db', type=Path, default=Path('/srv/nvme/surfd/data/surfd.db'))
    ap.add_argument('--game', type=Path, action='append', required=True)
    ap.add_argument('--publish-dir', type=Path, action='append',
                    help="repeatable; default the lobbies' and the site's zone folders")
    ap.add_argument('--apply', action='store_true')
    a=ap.parse_args()
    if not re.fullmatch('[0-9a-f]{40}',a.commit): ap.error('Expected full inspected source SHA')
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
    backup=SITE.with_name(SITE.name+'.pre-zonepub-'+a.commit[:12])
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
    unit='''[Unit]
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
'''%(release,' '.join(str(p) for p in (STATE,*publish)))
    # systemd quoted Environment syntax: JSON quotes/backslashes are escaped.
    unit+='\n'  # add Environment within Service, not Install
    entries=''.join('Environment="%s=%s"\n'%(k,v.replace('\\','\\\\').replace('"','\\"')) for k,v in env.items())
    unit=unit.replace('Restart=on-failure\n',entries+'Restart=on-failure\n')
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
        run('/usr/bin/systemctl','reload','nginx')
        probe_app(a.commit,'https://play.proto.bar/api/zones/challenge')
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
