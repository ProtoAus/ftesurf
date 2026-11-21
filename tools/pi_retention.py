#!/usr/bin/env python3
"""P1702: backup rotation on the Pi. Lex, 21 Nov 2026: "I like backups and I like safety, but sensible, I don't need
every backup ever made, maybe like the last 2 at most" and "ensure proper rotation".

Runs as proto, daily (systemd --user ftesurf-retention.timer; tools/pi-retention.md). Dry run unless --apply.

- Backup copies (NAME.pre<N>..., NAME.pre-..., NAME.bak..., NAME-pre<N>...) directly in BACKUP_DIRS: the newest KEEP of
  each (directory, NAME), by the timestamp in the copy's name, else its mtime (never ctime: a chgrp would make an
  October copy "newest"); a copy's -shm/-wal/-journal go with it. Also kept: what a reader picks by its own rule
  (READER_PICKS: tasupd trusts the newest two csprogs.dat.pre[0-9]* by mtime).
- Task roots in AGENT_WORK: removed once nothing in them changed (mtime or ctime: cp -a/rsync -a keep old mtimes) for
  IDLE_DAYS and nothing live names them. The newest KEEP gen<N>-* roots and a root holding RETAIN always stay.
- tasupd-src-* checkouts in OPS: the newest KEEP and any whose commit has a release in TASUPD_RELEASES.

Never removed: a path the live configuration names (systemd units and drop-ins, nginx, cron, the surfd home's own
files, the live generation's manifest and identity, the namespace observer's policy); a file any process has open,
maps or runs; a symlink; anything outside these directories. FAILS CLOSED: configuration it cannot read stops the
run before anything is removed (the surfd drop-in alone keeps ~230 copies); only an unreadable copy no loader picks up
(root's 0600 /etc/nginx/*.conf.pre-*) or TLS material is passed over. Nothing outside a tree being removed has its
permissions changed; a root we could not wholly remove (unreadable parts, another user's files, a mount) is kept."""
import argparse
import calendar
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
# Live configuration, read whole. The surfd home is read one level deep, skipping its logs and backup copies (old
# tracebacks name dead paths); below it are fixtures and the data tree (a whole-tree read held 4.8 GB: OOM, 21 Nov).
CONFIG_TREES = ('/etc/systemd', '/etc/nginx', '/etc/cron.d', os.path.expanduser('~/.config/systemd'))
CONFIG_FLAT = ('/srv/nvme/surfd',)
CONFIG_FILES = ('/usr/local/sbin/ftesurf-namespace-observer/policy.json',)
UNREADABLE_OK = re.compile(r'\.(key|pem|crt)$')           # TLS material names no paths
UNIT_SUFFIXES = ('.service', '.socket', '.timer', '.path', '.mount', '.automount', '.swap', '.target', '.slice', '.scope', '.device')
READER_PICKS = (('/srv/nvme/ftesurf-server/game/ftesurf/csprogs.dat.pre[0-9]*', 2),)   # tasupd.py LOBBY_BACKUPS, by mtime
CRONTAB = ('crontab', '-l')
MOUNTINFO = '/proc/self/mountinfo'
MAX_CONFIG = 32 << 20
MEMORY = 1 << 30      # RLIMIT_AS: a MemoryError here, never the OOM killer choosing among the live services
NOW = time.time

BACKUP = re.compile(r'^(?P<name>.+?)(?P<scheme>\.pre(?=[0-9])|\.pre-|\.bak(?=$|[0-9]|-|\.)|-pre(?=[0-9]))')
COMPANION = re.compile(r'-(?:shm|wal|journal)$')
STAMP = re.compile(r'(?<![0-9])(20[0-9]{2})([01][0-9])([0-3][0-9])[T-]?([0-2][0-9])([0-5][0-9])([0-5][0-9])?Z?(?![0-9])')
AW_NAME = re.compile(r'/srv/nvme/agent-work/([A-Za-z0-9._-]+)')
PATH = re.compile(r'/srv/nvme/[A-Za-z0-9._@+=/-]+')
GEN = re.compile(r'^gen([0-9]+)-')
COMMIT = re.compile(r'[0-9a-f]{7,40}')


class Unreadable(Exception):
    """Configuration that could name a live path could not be read: remove nothing."""


def config_refs():
    """Every /srv/nvme path the live configuration names. Raises Unreadable rather than miss one."""
    refs = set()
    def scan(text): refs.update(m.rstrip('/.') for m in PATH.findall(text))
    def read(p):
        try:
            if os.path.islink(p):
                scan(os.readlink(p))
                try: os.stat(p)
                except FileNotFoundError: return          # dangling: the link text is all it names
            st = os.stat(p)
            if not stat.S_ISREG(st.st_mode): return       # /dev/null masks and the like
            if st.st_size > MAX_CONFIG: raise Unreadable('%s is %d bytes' % (p, st.st_size))
            with open(p, errors='replace') as f: scan(f.read())
        except OSError as e:
            if UNREADABLE_OK.search(p) or (BACKUP.match(os.path.basename(p)) and not loaded(p)): return
            raise Unreadable('%s: %s' % (p, e)) from e
    def fail(e): raise Unreadable('%s: %s' % (e.filename, e))
    for top in CONFIG_TREES:
        if not os.path.exists(top): continue
        seen = set()
        for dp, dn, fn in os.walk(top, onerror=fail, followlinks=True):
            real = os.path.realpath(dp)
            if real in seen: dn[:] = []; continue       # a link loop
            seen.add(real)
            for d in dn:
                if os.path.islink(os.path.join(dp, d)): scan(os.readlink(os.path.join(dp, d)))
            for f in fn: read(os.path.join(dp, f))
    for top in CONFIG_FLAT:
        try: names = os.listdir(top)
        except FileNotFoundError: continue
        except OSError as e: raise Unreadable('%s: %s' % (top, e)) from e
        for f in names:
            p = os.path.join(top, f)
            if f.endswith('.log') or BACKUP.match(f) or (os.path.isdir(p) and not os.path.islink(p)): continue
            read(p)
    for p in CONFIG_FILES:
        if os.path.lexists(p): read(p)
    try: cron = subprocess.run(CRONTAB, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e: raise Unreadable('crontab: %s' % e) from e
    if cron.returncode and 'no crontab' not in cron.stderr:
        raise Unreadable('crontab: rc %d %s' % (cron.returncode, cron.stderr.strip()))
    scan(cron.stdout)
    for root in sorted({m.group(1) for r in list(refs) for m in [AW_NAME.match(r)] if m}):
        for p in glob.glob('%s/%s/backend/*/control/manifest.json' % (AGENT_WORK, root)) + \
                 glob.glob('%s/%s/backend/*/generation-identity.json' % (AGENT_WORK, root)):
            read(p)
    return refs


def loaded(p):
    """Whether systemd or nginx would load this file by its place and name (an unreadable one then stops the run)."""
    base, parent = os.path.basename(p), os.path.basename(os.path.dirname(p))
    return ('/sites-enabled/' in p or base.endswith(UNIT_SUFFIXES) or
            (base.endswith('.conf') and (parent in ('conf.d', 'modules-enabled') or parent.endswith('.d'))))


def reader_picks():
    """The copies a reader trusts by its own rule (newest N by mtime of a glob)."""
    out = set()
    for pattern, n in READER_PICKS:
        got = []
        for p in glob.glob(pattern):
            try: got.append((os.lstat(p).st_mtime, p))
            except FileNotFoundError: pass
        out.update(p for _, p in sorted(got, reverse=True)[:n])
    return out


def in_use():
    """Paths any process we can see runs, maps or holds open, its working directory and its absolute arguments."""
    used = set()
    try: pids = [p for p in os.listdir('/proc') if p.isdigit()]
    except OSError as e: raise Unreadable('/proc: %s' % e) from e
    for pid in pids:
        base = '/proc/' + pid
        try: fds = ['fd/' + f for f in os.listdir(base + '/fd')]
        except OSError: fds = []                          # another user's process, or gone
        for link in ['cwd', 'exe'] + fds:
            try: used.add(os.readlink(base + '/' + link).removesuffix(' (deleted)'))
            except OSError: pass
        try:
            with open(base + '/maps') as maps:
                for line in maps:
                    f = line.split(None, 5)
                    if len(f) == 6 and f[5].startswith('/'): used.add(f[5].strip().removesuffix(' (deleted)'))
        except OSError: pass
        try:
            with open(base + '/cmdline', 'rb') as f:
                used.update(a for a in f.read().decode(errors='replace').split('\0') if a.startswith('/'))
        except OSError: pass
    return used


def named(path, refs, used):
    """True when the configuration or a process names this path or anything under it."""
    under = path + '/'
    return path in refs or path in used or any(r.startswith(under) for r in refs) or any(u.startswith(under) for u in used)


def changed(st): return max(st.st_mtime, st.st_ctime)


def copy_time(copy, files):
    """When this copy was made: the timestamp in its name, else its newest mtime."""
    m = STAMP.search(os.path.basename(copy))
    if m:
        y, mo, d, h, mi, s = (int(x or 0) for x in m.groups())
        if 1 <= mo <= 12 and 1 <= d <= 31 and h < 24: return calendar.timegm((y, mo, d, h, mi, s))
    return max(os.lstat(p).st_mtime for p in files)


def backup_plan(refs, used):
    """(remove, keep) lists of backup copies past the newest KEEP of each (directory, name)."""
    remove, kept, picked = [], [], reader_picks()
    for d in BACKUP_DIRS:
        try: names = os.listdir(d)
        except FileNotFoundError: continue
        groups = {}
        for n in names:
            m = BACKUP.match(n)
            if not m: continue
            p = os.path.join(d, n)
            try:
                if not stat.S_ISREG(os.lstat(p).st_mode): continue
            except FileNotFoundError: continue
            group = groups.setdefault(m.group('name'), {})
            group.setdefault(os.path.join(d, COMPANION.sub('', n)), []).append(p)
        for copies in groups.values():
            try: newest = sorted(copies, key=lambda c: copy_time(c, copies[c]), reverse=True)
            except FileNotFoundError: continue           # a deploy is moving files: next run
            for i, c in enumerate(newest):
                files = copies[c]
                if i < KEEP or any(named(p, refs, used) or p in picked for p in files): kept.extend(files)
                else: remove.extend(files)
    return remove, kept


def mount_points():
    """Every mount point (a bind mount from the same disk keeps st_dev, so it is read from the mount table)."""
    try:
        with open(MOUNTINFO) as f:
            return {re.sub(r'\\([0-7]{3})', lambda m: chr(int(m.group(1), 8)), line.split()[4]) for line in f if line.strip()}
    except (OSError, IndexError) as e: raise Unreadable('%s: %s' % (MOUNTINFO, e)) from e


def blocker(root, cut, mounts):
    """Why `root` must stay: changed after `cut` (None: age not asked), partly unreadable, holding another user's
    files, or holding a mount. None when it is idle and wholly ours to remove."""
    me, top = os.geteuid(), os.lstat(root)
    if any(m == root or m.startswith(root + '/') for m in mounts): return 'holds a mount point'
    if cut is not None and changed(top) > cut: return 'changed in the last %d days' % IDLE_DAYS
    if top.st_uid != me: return 'owned by another user'
    unreadable = []
    for dp, dn, fn in os.walk(root, onerror=unreadable.append):
        for n in dn + fn:
            try: st = os.lstat(os.path.join(dp, n))
            except FileNotFoundError: continue
            if cut is not None and changed(st) > cut: return 'changed in the last %d days' % IDLE_DAYS
            if st.st_uid != me: return 'holds files owned by another user'
            if st.st_dev != top.st_dev: return 'crosses a mount point'
    return 'partly unreadable' if unreadable else None


def root_plan(refs, used, now, mounts=frozenset()):
    """(remove, keep) task roots in AGENT_WORK; keep carries the reason."""
    refd = {m.group(1) for x in refs | used for m in [AW_NAME.match(x)] if m}
    try: names = sorted(os.listdir(AGENT_WORK))
    except FileNotFoundError: return [], []
    gens = sorted((n for n in names if GEN.match(n)), key=lambda n: int(GEN.match(n).group(1)), reverse=True)[:KEEP]
    cut = now - IDLE_DAYS * 86400
    remove, kept = [], []
    for n in names:
        p = os.path.join(AGENT_WORK, n)
        try:
            if os.path.islink(p) or not os.path.isdir(p): kept.append((p, 'not a directory')); continue
            why = ('named by the live configuration or a process' if n in refd else 'one of the newest generations' if n in gens
                   else 'holds RETAIN' if os.path.lexists(os.path.join(p, 'RETAIN')) else blocker(p, cut, mounts))
        except FileNotFoundError: continue
        if why: kept.append((p, why))
        else: remove.append(p)
    return remove, kept


def checkout_plan(refs, used, mounts=frozenset()):
    try: names = [n for n in os.listdir(OPS) if n.startswith('tasupd-src-')]
    except FileNotFoundError: return []
    try: releases = os.listdir(TASUPD_RELEASES)
    except OSError: releases = []
    paths = []
    for n in names:
        p = os.path.join(OPS, n)
        try:
            if not os.path.islink(p) and os.path.isdir(p): paths.append((changed(os.lstat(p)), p))
        except FileNotFoundError: pass
    out = []
    for i, (_, p) in enumerate(sorted(paths, reverse=True)):
        c = p.rsplit('tasupd-src-', 1)[1]
        live = COMMIT.fullmatch(c) and any(r.startswith(c) for r in releases)
        if i >= KEEP and not live and not named(p, refs, used) and not blocker(p, None, mounts): out.append(p)
    return out


def remove_tree(root, failed):
    """Removes `root`: directories inside it that we own get u+rwx first; files and its parent are left as they are."""
    me = os.geteuid()
    for dp, dn, fn in os.walk(root):
        for d in [dp] + [os.path.join(dp, x) for x in dn]:
            try:
                st = os.lstat(d)
                if stat.S_ISDIR(st.st_mode) and st.st_uid == me and st.st_mode & 0o700 != 0o700:
                    os.chmod(d, stat.S_IMODE(st.st_mode) | 0o700)
            except OSError: pass
    def note(fn, path, exc): failed.append('%s: %s' % (path, exc[1] if isinstance(exc, tuple) else exc))
    shutil.rmtree(root, onerror=note)


def log_lines(path, lines):
    if not path: return
    try:
        old = []
        if os.path.exists(path):
            with open(path) as f: old = f.read().splitlines()
        with open(path + '.tmp', 'w') as f: f.write('\n'.join((old + lines)[-2000:]) + '\n')
        os.replace(path + '.tmp', path)
    except OSError as e: print('(log not written: %s)' % e, file=sys.stderr)


def stamp(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--apply', action='store_true', help='remove; without it, only list')
    ap.add_argument('--log', help='append the summary here (kept to its last 2000 lines)')
    a = ap.parse_args(argv)
    now = NOW()
    try: refs, used, mounts = config_refs(), in_use(), mount_points()
    except Unreadable as e:
        lines = ['%s STOPPED, nothing removed: %s' % (stamp(), e)]
        print('\n'.join(lines)); log_lines(a.log, lines)
        return 2
    files, _ = backup_plan(refs, used)
    roots, _ = root_plan(refs, used, now, mounts)
    checkouts = checkout_plan(refs, used, mounts)
    size = 0
    for p in files:
        try: size += os.lstat(p).st_size
        except FileNotFoundError: pass
    lines = ['%s %s: %d backup copies (%.1f MB), %d task roots, %d checkouts' % (
        stamp(), 'removing' if a.apply else 'would remove', len(files), size / 1e6, len(roots), len(checkouts))]
    lines += ['  ' + p for p in files + roots + checkouts]
    print('\n'.join(lines)); log_lines(a.log, lines)          # the plan is on record before anything goes
    if not a.apply: return 0
    failed, done = [], 0
    for p in files:
        try: os.unlink(p); done += 1
        except FileNotFoundError: pass
        except OSError as e: failed.append('%s: %s' % (p, e))
    cut = now - IDLE_DAYS * 86400
    for p, age in [(x, cut) for x in roots] + [(x, None) for x in checkouts]:
        try: why = blocker(p, age, mount_points())
        except FileNotFoundError: continue
        if why: failed.append('%s: %s (found after planning); kept' % (p, why)); continue
        remove_tree(p, failed); done += 1
    out = ['%s done: %d removed, %d problems' % (stamp(), done, len(failed))] + ['  NOT REMOVED ' + f for f in failed]
    print('\n'.join(out)); log_lines(a.log, out)
    return 1 if failed else 0


if __name__ == '__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY, MEMORY))
    sys.exit(main())
