#!/usr/bin/env python3
"""P1702: publish the web board's eight page files to the NanoPi's static board folder (as proto, no root).

    python3 -B tools/publish_board.py --live          # the LIVE generation's own web/ bytes (after every generation)
    python3 -B tools/publish_board.py --commit REF    # a UI-only change from git, ahead of a generation
    add --dry-run to print the plan only

nginx (src/release/ftesurf.nginx) serves /ftesurf/board/ and /worldofsurf/board/ (page + seven assets) from
/srv/nvme/ftesurf-site/board/current; every API path stays on surfd. A release lands in board/releases/<id>, `current`
flips atomically, and the newest two releases stay (Lex: keep the newest 2).

--commit refuses unless the live generation's source_ref is an ancestor of REF and no commit in source_ref..REF that
touches a board file also touches a live surfd Python member: a board change that needs new surfd code rides a
generation (then --live). Both modes refuse when the installed nginx snippet's CSP differs from that surfd.py's
WEB_CSP / WEB_CSP_WATCH (a CSP change needs ftesurf.nginx + install.sh).
"""
import argparse
import ast
import base64
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FILES = ('board.html', 'board.css', 'board.js', 'link.css', 'runview.js', 'watch.css', 'watch.html', 'watch.js')
PATHS = dict(board='/srv/nvme/ftesurf-site/board', runsh='/srv/nvme/surfd/run.sh',
             snippet='/etc/nginx/snippets/ftesurf.conf')
KEEP = 2

# Runs on the Pi as proto (python3.11 -I -B -c REMOTE); the payload is one JSON line on stdin.
REMOTE = r'''
import ast, base64, fcntl, hashlib, json, os, re, shlex, stat, sys, tempfile, time
from pathlib import Path
FILES = ('board.html', 'board.css', 'board.js', 'link.css', 'runview.js', 'watch.css', 'watch.html', 'watch.js')
sha = lambda raw: hashlib.sha256(raw).hexdigest()
def fail(msg): print(json.dumps({'ok': False, 'error': msg})); sys.exit(3)
p = json.loads(sys.stdin.readline())
P = p['paths']; board = Path(P['board'])

def csp_of(source):
    env = {}
    for n in ast.parse(source).body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and \
                n.targets[0].id in ('WEB_CSP', 'WEB_R2_ORIGIN', 'WEB_CSP_WATCH'):
            env[n.targets[0].id] = eval(compile(ast.Expression(n.value), 'surfd.py', 'eval'), {'__builtins__': {}}, dict(env))
    return env['WEB_CSP'], env['WEB_CSP_WATCH']

def live():
    tails = [shlex.split(x[5:]) for x in Path(P['runsh']).read_text().splitlines() if x.startswith('exec ')]
    if len(tails) != 1: fail('run.sh: one exec line expected')
    argv = tails[0]; state = argv[argv.index('--state-dir') + 1]
    m = json.loads((Path(state) / 'manifest.json').read_bytes())
    home = Path(m['source_home'])
    ident = json.loads((home.parent / 'generation-identity.json').read_bytes())
    return m, home, ident.get('source_ref', '')

m, home, source_ref = live()
if p['mode'] == 'live-info':
    print(json.dumps({'ok': True, 'generation': m['generation'], 'source_ref': source_ref,
                      'members': sorted(m['hashes'])})); sys.exit(0)
if p['mode'] == 'live':
    files = {}
    for f in FILES:
        raw = (home / 'web' / f).read_bytes()
        if sha(raw) != m['hashes'].get('web/' + f): fail('live web/%s does not match the live manifest' % f)
        files[f] = raw
    csp = csp_of((home / 'surfd.py').read_bytes())
    rid = 'live-' + m['generation'][:12]
else:
    if p['live_generation'] != m['generation']: fail('the live generation changed since planning')
    files = {f: base64.b64decode(p['files'][f]) for f in FILES}
    csp = tuple(p['csp'])
    rid = 'commit-' + p['commit'][:12]
if set(files) != set(FILES) or any(sha(files[f]) != p['expect'].get(f, sha(files[f])) for f in FILES): fail('file set')
snippet_note = 'snippet not readable'
try:
    snip = Path(P['snippet']).read_text()
    if '/srv/nvme/ftesurf-site/board/current' in snip:
        want = {csp[0]: 14, csp[1]: 2}                     # 2 bases x (page + 6 assets) and 2 x watch.html
        got = re.findall(r'add_header Content-Security-Policy "([^"]*)" always;', snip)
        if sorted(set(got)) != sorted(want) or any(got.count(k) != n for k, n in want.items()):
            fail('the installed nginx snippet carries a different CSP than this surfd.py: update ftesurf.nginx + install.sh')
        snippet_note = 'snippet CSP matches'
    else:
        snippet_note = 'static board not installed in nginx yet (install.sh)'
except OSError as e:
    snippet_note = 'snippet unreadable: ' + repr(e)
plan = {'release': rid, 'sha256': {f: sha(files[f]) for f in FILES}, 'snippet': snippet_note}
if p['dry_run']:
    print(json.dumps(dict(plan, ok=True, dry_run=True))); sys.exit(0)
for d in (board, board / 'releases'):
    d.mkdir(mode=0o755, exist_ok=True)
lock = os.open(board / '.publish.lock', os.O_RDWR | os.O_CREAT, 0o644)
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
dest = board / 'releases' / rid
if dest.exists():
    have = {f: sha((dest / f).read_bytes()) for f in FILES if (dest / f).is_file()}
    if have != plan['sha256'] or sorted(os.listdir(dest)) != sorted(FILES): fail('release %s exists with other bytes' % rid)
else:
    tmp = Path(tempfile.mkdtemp(prefix='.' + rid + '-', dir=board / 'releases'))
    for f in FILES:
        fd = os.open(tmp / f, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, 'wb') as out: out.write(files[f]); out.flush(); os.fsync(out.fileno())
        os.chmod(tmp / f, 0o644)
    os.chmod(tmp, 0o755); os.rename(tmp, dest)
link = board / '.current.new'
if os.path.lexists(link): os.unlink(link)
os.symlink('releases/' + rid, link); os.replace(link, board / 'current')
fd = os.open(board, os.O_RDONLY | os.O_DIRECTORY); os.fsync(fd); os.close(fd)
current = os.readlink(board / 'current').split('/')[-1]
rel = [d for d in os.listdir(board / 'releases') if not d.startswith('.') and (board / 'releases' / d).is_dir()
       and not (board / 'releases' / d).is_symlink()]
rel.sort(key=lambda d: (d == current, (board / 'releases' / d).stat().st_mtime), reverse=True)
removed = []
for d in rel[p['keep']:]:
    path = board / 'releases' / d
    if any(not e.is_file() or e.is_symlink() for e in path.iterdir()): continue
    for e in path.iterdir(): e.unlink()
    path.rmdir(); removed.append(d)
print(json.dumps(dict(plan, ok=True, current=current, removed=removed)))
'''


def git(*args):
    return subprocess.run(['git', '-C', str(ROOT)] + list(args), check=True, capture_output=True).stdout


def csp_of(source):
    env = {}
    for n in ast.parse(source).body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and \
                n.targets[0].id in ('WEB_CSP', 'WEB_R2_ORIGIN', 'WEB_CSP_WATCH'):
            env[n.targets[0].id] = eval(compile(ast.Expression(n.value), 'surfd.py', 'eval'), {'__builtins__': {}}, dict(env))
    return env['WEB_CSP'], env['WEB_CSP_WATCH']


def remote(payload, pi, runner=None):
    """Run REMOTE with payload on the Pi (or with `runner`, a local argv, in tests)."""
    argv = (runner + ['-c', REMOTE] if runner else
            ['ssh', '-o', 'BatchMode=yes', '-T', pi, '/usr/bin/python3.11 -I -B -c ' + shlex.quote(REMOTE)])
    done = subprocess.run(argv, input=(json.dumps(payload) + '\n').encode(), capture_output=True, timeout=120)
    try:
        out = json.loads(done.stdout.decode().strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise SystemExit('remote failed (rc %d): %s' % (done.returncode, done.stderr.decode()[-800:]))
    if not out.get('ok'):
        raise SystemExit('REFUSED: ' + out.get('error', '?'))
    return out


def ui_only(source_ref, ref, members):
    """Commits in source_ref..ref that touch a board file must not touch a live surfd Python member."""
    if subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', source_ref, ref]).returncode:
        raise SystemExit('REFUSED: the live source_ref %s is not an ancestor of %s' % (source_ref[:8], ref[:8]))
    py = {'surfd/' + n for n in members if n.endswith('.py') and not Path(n).name.startswith('test_')}
    web = ['surfd/web/' + f for f in FILES]
    bad = []
    for c in git('log', '--format=%H', source_ref + '..' + ref, '--', *web).decode().split():
        touched = set(git('show', '--name-only', '--format=', c).decode().split())
        if touched & py:
            bad.append('%s (%s)' % (c[:8], ', '.join(sorted(touched & py))))
    if bad:
        raise SystemExit('REFUSED: board changes that come with surfd code ride a generation, then --live: ' + '; '.join(bad))


def main(argv=None, runner=None, paths=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--live', action='store_true')
    mode.add_argument('--commit')
    ap.add_argument('--pi', default='nanopi')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    base = dict(paths=paths or PATHS, keep=KEEP, dry_run=a.dry_run)
    if a.live:
        out = remote(dict(base, mode='live', expect={}), a.pi, runner)
    else:
        ref = git('rev-parse', a.commit + '^{commit}').decode().strip()
        info = remote(dict(base, mode='live-info'), a.pi, runner)
        ui_only(info['source_ref'], ref, info['members'])
        files = {f: git('show', '%s:surfd/web/%s' % (ref, f)) for f in FILES}
        out = remote(dict(base, mode='commit', commit=ref, live_generation=info['generation'],
                          files={f: base64.b64encode(raw).decode() for f, raw in files.items()},
                          expect={f: hashlib.sha256(raw).hexdigest() for f, raw in files.items()},
                          csp=list(csp_of(git('show', ref + ':surfd/surfd.py')))), a.pi, runner)
    print(json.dumps(out, indent=1, sort_keys=True))
    return out


if __name__ == '__main__':
    main()
