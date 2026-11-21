#!/usr/bin/env python3
"""P1702: backup rotation on the Pi. Lex, 21 Nov 2026: "I like backups and I like safety, but sensible, I don't need
every backup ever made, maybe like the last 2 at most" and "ensure proper rotation".

Runs as proto, daily (systemd --user ftesurf-retention.timer; tools/pi-retention.md). Dry run unless --apply.

- Backup copies (NAME.pre<N|->..., NAME.bak..., NAME-pre<N>...) directly in BACKUP_DIRS: the newest KEEP per
  (directory, NAME) by modification time; a copy's -shm/-wal/-journal go with it.
- Task roots in AGENT_WORK: removed once nothing in them changed for IDLE_DAYS and nothing live names them. The
  newest KEEP gen<N>-* roots (the live generation and its rollback) and a root holding a RETAIN file always stay.
- tasupd-src-* checkouts in OPS: the newest KEEP and any whose commit has a release in TASUPD_RELEASES.

Never removed: a path the live configuration names (any systemd unit, drop-in, nginx, cron, the surfd home's own
files, the live generation's manifest and identity, the namespace observer's policy); a file any process has open,
maps or runs; a symlink; anything outside these directories. Root-owned leftovers are reported, not forced
(installers prune their own: tools/install_tasupd.py)."""
import argparse
import glob
import os
import re
import shutil
import stat
import subprocess
import sys
import time

KEEP = 2
IDLE_DAYS = 14
AGENT_WORK = '/srv/nvme/agent-work'
OPS = '/srv/nvme/ftesurf-ops'
TASUPD_RELEASES = '/opt/ftesurf-tasupd'
BACKUP_DIRS = ('/srv/nvme/surfd', '/srv/nvme/surfd/data', '/srv/nvme/ftesurf-server', '/srv/nvme/ftesurf-server/game',
               '/srv/nvme/ftesurf-server/game/ftesurf', '/srv/nvme/ftesurf-server/game/tools', '/srv/nvme/ftesurf-server/fteqw',
               '/srv/nvme/ftesurf-site') + tuple(sorted(glob.glob('/srv/nvme/ftesurf-site/releases/*')))
# Where live configuration lives; logs, bytecode caches and backup copies only name dead paths (old tracebacks).
CONFIG_TREES = ('/etc/systemd', '/etc/nginx', '/etc/cron.d', '/srv/nvme/surfd', os.path.expanduser('~/.config/systemd'))
CONFIG_FILES = ('/usr/local/sbin/ftesurf-namespace-observer/policy.json',)
SKIP_TREES = ('/srv/nvme/surfd/data',)

BACKUP = re.compile(r'^(?P<name>.+?)(?:\.pre(?=[0-9]|-)|\.bak(?=$|[0-9]|-|\.)|-pre(?=[0-9]))')
COMPANION = re.compile(r'-(?:shm|wal|journal)$')
AW_NAME = re.compile(r'/srv/nvme/agent-work/([A-Za-z0-9._-]+)')
GEN = re.compile(r'^gen([0-9]+)-')
COMMIT = re.compile(r'[0-9a-f]{7,40}')


def config_text():
    """Every live configuration file's text, plus the crontab and the live generation records it names."""
    parts = []
    def read(p):
        try:
            if os.path.isfile(p) and not os.path.islink(p) and os.path.getsize(p) < 4 << 20:
                with open(p, errors='replace') as f: parts.append(f.read())
        except OSError: pass
    for top in CONFIG_TREES:
        for dp, dn, fn in os.walk(top):
            if dp.startswith(SKIP_TREES): dn[:] = []; continue
            dn[:] = [d for d in dn if d not in ('logs', '__pycache__')]
            for f in fn:
                if f.endswith('.log') or BACKUP.match(f): continue
                read(os.path.join(dp, f))
    for p in CONFIG_FILES: read(p)
    try: parts.append(subprocess.run(['crontab', '-l'], capture_output=True, text=True, timeout=30).stdout)
    except (OSError, subprocess.SubprocessError): pass
    for root in sorted(set(AW_NAME.findall('\n'.join(parts)))):
        for p in glob.glob('%s/%s/backend/*/control/manifest.json' % (AGENT_WORK, root)) + \
                 glob.glob('%s/%s/backend/*/generation-identity.json' % (AGENT_WORK, root)):
            read(p)
    return '\n'.join(parts)


def in_use():
    """Paths any process we can see runs, maps or holds open, and its working directory."""
    used = set()
    for pid in os.listdir('/proc'):
        if not pid.isdigit(): continue
        base = '/proc/' + pid
        for link in ['cwd', 'exe'] + ['fd/' + f for f in (os.listdir(base + '/fd') if os.access(base + '/fd', os.R_OK) else [])]:
            try: used.add(os.readlink(base + '/' + link).removesuffix(' (deleted)'))
            except OSError: pass
        try:
            with open(base + '/maps') as maps:
                for line in maps:
                    f = line.split(None, 5)
                    if len(f) == 6 and f[5].startswith('/'): used.add(f[5].strip())
        except OSError: pass
        try:
            with open(base + '/cmdline', 'rb') as f: used.update(a for a in f.read().decode(errors='replace').split('\0') if a.startswith('/'))
        except OSError: pass
    return used


def named(path, text, used):
    """True when the configuration names this path, or a process uses it or anything under it."""
    if path in text or path in used: return True
    return any(u.startswith(path + '/') for u in used)


def backup_plan(text, used):
    """(remove, keep) lists of backup copies past the newest KEEP of each (directory, name)."""
    remove, kept = [], []
    for d in BACKUP_DIRS:
        try: names = os.listdir(d)
        except OSError: continue
        groups = {}
        for n in names:
            m = BACKUP.match(n)
            p = os.path.join(d, n)
            if not m or not stat.S_ISREG(os.lstat(p).st_mode): continue
            groups.setdefault(m.group('name'), {}).setdefault(COMPANION.sub('', n), []).append(p)
        for name, copies in groups.items():
            newest = sorted(copies, key=lambda c: max(os.lstat(p).st_mtime for p in copies[c]), reverse=True)
            for i, c in enumerate(newest):
                files = copies[c]
                if i < KEEP or any(named(p, text, used) for p in files): kept.extend(files)
                else: remove.extend(files)
    return remove, kept


def recent(root, cut):
    if os.lstat(root).st_mtime > cut: return True
    for dp, dn, fn in os.walk(root):
        for n in dn + fn:
            try:
                if os.lstat(os.path.join(dp, n)).st_mtime > cut: return True
            except OSError: pass
    return False


def root_plan(text, used, now):
    """(remove, keep) task roots in AGENT_WORK; keep carries the reason."""
    refd = set(AW_NAME.findall(text)) | {m.group(1) for u in used for m in [AW_NAME.match(u)] if m}
    try: names = sorted(os.listdir(AGENT_WORK))
    except OSError: return [], []
    gens = sorted((n for n in names if GEN.match(n)), key=lambda n: int(GEN.match(n).group(1)), reverse=True)[:KEEP]
    cut = now - IDLE_DAYS * 86400
    remove, kept = [], []
    for n in names:
        p = os.path.join(AGENT_WORK, n)
        if os.path.islink(p) or not os.path.isdir(p): kept.append((p, 'not a directory')); continue
        why = ('named by the live configuration or a process' if n in refd else 'one of the newest generations' if n in gens
               else 'holds RETAIN' if os.path.lexists(os.path.join(p, 'RETAIN')) else
               'changed in the last %d days' % IDLE_DAYS if recent(p, cut) else None)
        if why: kept.append((p, why))
        else: remove.append(p)
    return remove, kept


def checkout_plan(text, used):
    try: names = [n for n in os.listdir(OPS) if n.startswith('tasupd-src-')]
    except OSError: return []
    try: releases = os.listdir(TASUPD_RELEASES)
    except OSError: releases = []
    paths = sorted((os.path.join(OPS, n) for n in names if not os.path.islink(os.path.join(OPS, n))),
                   key=lambda p: os.lstat(p).st_mtime, reverse=True)
    out = []
    for i, p in enumerate(paths):
        c = p.rsplit('tasupd-src-', 1)[1]
        live = COMMIT.fullmatch(c) and any(r.startswith(c) for r in releases)
        if i >= KEEP and not live and not named(p, text, used): out.append(p)
    return out


def remove_tree(p, failed):
    def unlock(fn, path, exc):
        try:
            os.chmod(os.path.dirname(path), 0o700)
            if not os.path.islink(path): os.chmod(path, 0o700 if os.path.isdir(path) else 0o600)
            fn(path)
        except OSError as e: failed.append('%s: %s' % (path, e))
    shutil.rmtree(p, onerror=unlock)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--apply', action='store_true', help='remove; without it, only list')
    ap.add_argument('--log', help='append the summary here (kept to its last 2000 lines)')
    a = ap.parse_args(argv)
    now = time.time()
    text, used = config_text(), in_use()
    files, _ = backup_plan(text, used)
    roots, _ = root_plan(text, used, now)
    checkouts = checkout_plan(text, used)
    size = 0
    for p in files: size += os.lstat(p).st_size
    lines = ['%s %s: %d backup copies (%.1f MB), %d task roots, %d checkouts' % (
        time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now)), 'removed' if a.apply else 'would remove',
        len(files), size / 1e6, len(roots), len(checkouts))]
    lines += ['  ' + p for p in files + roots + checkouts]
    failed = []
    if a.apply:
        for p in files:
            try: os.unlink(p)
            except OSError as e: failed.append('%s: %s' % (p, e))
        for p in roots + checkouts: remove_tree(p, failed)
        lines += ['  NOT REMOVED ' + f for f in failed]
    print('\n'.join(lines))
    if a.log:
        try:
            old = []
            if os.path.exists(a.log):
                with open(a.log) as f: old = f.read().splitlines()
            with open(a.log + '.tmp', 'w') as f: f.write('\n'.join((old + lines)[-2000:]) + '\n')
            os.replace(a.log + '.tmp', a.log)
        except OSError as e: print('(log not written: %s)' % e, file=sys.stderr)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
