#!/usr/bin/python3.11 -I -B
"""P1702 Pi side of tools/publish_board.py, run as proto. Stdlib only.

Input: one JSON payload line on stdin (publish_board.py streams this file over ssh), or `--follow [--dry-run]`, which
the ftesurf-board-follow timer runs from /srv/nvme/ftesurf-ops/board/: when the live generation differs from the one
board/state.json was published against, publish that generation's own web/ files. Output: one JSON line; rc 3 refused.

board/releases/<id>/ holds the eight files; board/current -> releases/<id> flips atomically; the two releases most
recently made current stay. nginx (src/release/ftesurf.nginx) serves board/current.
"""
import ast
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile

FILES = ('board.html', 'board.css', 'board.js', 'link.css', 'runview.js', 'watch.css', 'watch.html', 'watch.js')
PATHS = dict(board='/srv/nvme/ftesurf-site/board', runsh='/srv/nvme/surfd/run.sh', snippet='/etc/nginx/snippets/ftesurf.conf')
KEEP = 2
TEMP = re.compile(r'^\.(live|commit)-[0-9a-f]{12}-')
sha = lambda raw: hashlib.sha256(raw).hexdigest()


class Refused(Exception):
    pass


def literal(node, env):
    """surfd.py's WEB_CSP family: string constants, names bound earlier, `+` and str.replace -- nothing else."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and node.id in env:
        return env[node.id]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return literal(node.left, env) + literal(node.right, env)
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'replace' and
            len(node.args) == 2 and not node.keywords):
        return literal(node.func.value, env).replace(literal(node.args[0], env), literal(node.args[1], env))
    raise Refused('surfd.py WEB_CSP is not a plain string expression')


def csp_of(source):
    env = {}
    for n in ast.parse(source).body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and \
                n.targets[0].id in ('WEB_CSP', 'WEB_R2_ORIGIN', 'WEB_CSP_WATCH'):
            env[n.targets[0].id] = literal(n.value, env)
    if 'WEB_CSP' not in env or 'WEB_CSP_WATCH' not in env:
        raise Refused('surfd.py has no WEB_CSP / WEB_CSP_WATCH')
    return env['WEB_CSP'], env['WEB_CSP_WATCH']


def live(paths):
    """The live generation: run.sh's one exec line -> --state-dir -> manifest.json."""
    tails = [shlex.split(x[5:]) for x in Path(paths['runsh']).read_text().splitlines() if x.startswith('exec ')]
    if len(tails) != 1 or '--state-dir' not in tails[0]:
        raise Refused('run.sh: one exec line with --state-dir expected')
    argv = tails[0]
    m = json.loads((Path(argv[argv.index('--state-dir') + 1]) / 'manifest.json').read_bytes())
    return m, Path(m['source_home'])


def snippet_check(path, csp):
    """Each static board location in the installed snippet must carry this surfd.py's CSP (watch.html: WEB_CSP_WATCH)."""
    try:
        snip = Path(path).read_text()
    except FileNotFoundError:
        return 'no nginx snippet installed yet (install.sh)'
    except OSError as e:
        raise Refused('cannot read the installed nginx snippet %s: %r' % (path, e))
    if '/srv/nvme/ftesurf-site/board/current' not in snip:
        return 'static board not installed in nginx yet (install.sh)'
    blocks = dict(re.findall(r'\nlocation = (/[a-z]+/board/[a-z.]*) \{(.*?)\n\}', snip, re.S))
    for base in ('ftesurf', 'worldofsurf'):
        for f in ('',) + FILES[1:]:
            got = re.findall(r'add_header Content-Security-Policy "([^"]*)" always;', blocks.get('/%s/board/%s' % (base, f), ''))
            if got != [csp[1] if f == 'watch.html' else csp[0]]:
                raise Refused('installed nginx snippet: /%s/board/%s carries another CSP than this surfd.py '
                              '(update ftesurf.nginx and run install.sh)' % (base, f))
    return 'snippet CSP matches'


def take_lock(p):
    """Every writer holds board/.publish.lock for its whole read-decide-write (the follow timer included)."""
    board = Path(p['paths']['board'])
    for d in (board, board / 'releases'):
        d.mkdir(exist_ok=True)
        os.chmod(d, 0o755)                                  # nginx (www-data) must read; umask must not decide
    lock = os.open(board / '.publish.lock', os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise Refused('another board publish is running')
    return lock


def publish(p, files, rid, generation, csp, extra):
    board = Path(p['paths']['board'])
    plan = {'release': rid, 'generation': generation, 'sha256': {f: sha(files[f]) for f in FILES},
            'snippet': snippet_check(p['paths']['snippet'], csp)}
    if p.get('dry_run'):
        return dict(plan, dry_run=True)
    for d in os.listdir(board / 'releases'):                # a crashed earlier write
        path = board / 'releases' / d
        if TEMP.match(d) and path.is_dir() and not path.is_symlink():
            for e in path.iterdir():
                e.unlink()
            path.rmdir()
    dest = board / 'releases' / rid
    if dest.exists():
        have = {f: sha((dest / f).read_bytes()) for f in FILES if (dest / f).is_file()}
        if have != plan['sha256'] or sorted(os.listdir(dest)) != sorted(FILES):
            raise Refused('release %s exists with other bytes' % rid)
    else:
        tmp = Path(tempfile.mkdtemp(prefix='.' + rid + '-', dir=board / 'releases'))
        for f in FILES:
            fd = os.open(tmp / f, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            with os.fdopen(fd, 'wb') as out:
                out.write(files[f]); out.flush(); os.fsync(out.fileno())
            os.chmod(tmp / f, 0o644)
        os.chmod(tmp, 0o755)
        os.rename(tmp, dest)
    os.utime(dest)                                          # pruning keeps the releases most recently made current
    link = board / '.current.new'
    if os.path.lexists(link):
        os.unlink(link)
    os.symlink('releases/' + rid, link)
    os.replace(link, board / 'current')
    state = board / '.state.json.new'
    state.write_text(json.dumps(dict(extra, release=rid, generation=generation), sort_keys=True) + '\n')
    os.chmod(state, 0o644)
    os.replace(state, board / 'state.json')
    fd = os.open(board, os.O_RDONLY | os.O_DIRECTORY)
    os.fsync(fd); os.close(fd)
    current = os.readlink(board / 'current').split('/')[-1]
    rel = [d for d in os.listdir(board / 'releases') if not d.startswith('.') and
           (board / 'releases' / d).is_dir() and not (board / 'releases' / d).is_symlink()]
    rel.sort(key=lambda d: (d == current, (board / 'releases' / d).stat().st_mtime), reverse=True)
    removed = []
    for d in rel[p.get('keep', KEEP):]:
        path = board / 'releases' / d
        if d == current or any(not e.is_file() or e.is_symlink() for e in path.iterdir()):
            continue
        for e in path.iterdir():
            e.unlink()
        path.rmdir(); removed.append(d)
    return dict(plan, current=current, removed=removed)


def live_csp(m, home):
    surfd = (home / 'surfd.py').read_bytes()
    if sha(surfd) != m['hashes'].get('surfd.py'):
        raise Refused('live surfd.py does not match the live manifest')
    return csp_of(surfd)


def live_publish(p, m, home):
    files = {}
    for f in FILES:
        raw = (home / 'web' / f).read_bytes()
        if sha(raw) != m['hashes'].get('web/' + f):
            raise Refused('live web/%s does not match the live manifest' % f)
        files[f] = raw
    return publish(p, files, 'live-' + m['generation'][:12], m['generation'], live_csp(m, home), {'mode': 'live'})


def run(p):
    mode = p['mode']
    if mode == 'live-info':
        m, home = live(p['paths'])
        ident = json.loads((home.parent / 'generation-identity.json').read_bytes())
        return {'generation': m['generation'], 'source_ref': ident.get('source_ref', ''), 'hashes': m['hashes'],
                'external_python': {k: v.get('sha256', '') for k, v in m.get('external_python', {}).items()}}
    if mode not in ('live', 'follow', 'commit'):
        raise Refused('unknown mode %r' % mode)
    if not p.get('dry_run'):
        try:
            take_lock(p)                                    # held until exit: read state, decide and write as one
        except Refused:
            if mode == 'follow':
                return {'action': 'none', 'busy': True}
            raise
    m, home = live(p['paths'])                              # read under the lock
    if mode == 'live':
        return live_publish(p, m, home)
    if mode == 'follow':
        # Every tick checks the installed snippet against the live surfd.py: drift fails the unit.
        snippet = snippet_check(p['paths']['snippet'], live_csp(m, home))
        try:
            state = json.loads((Path(p['paths']['board']) / 'state.json').read_bytes())
        except (OSError, ValueError):
            state = {}
        if state.get('generation') == m['generation']:
            return {'action': 'none', 'generation': m['generation'], 'snippet': snippet, 'quiet': True}
        return dict(live_publish(p, m, home), action='would publish' if p.get('dry_run') else 'published')
    if p['live_generation'] != m['generation']:
        raise Refused('the live generation changed since planning')
    if tuple(p['csp']) != live_csp(m, home):
        raise Refused('REF\'s surfd.py CSP differs from the live surfd.py\'s')
    files = {f: base64.b64decode(p['files'][f]) for f in FILES}
    if set(p['files']) != set(FILES) or any(sha(files[f]) != p['expect'][f] for f in FILES):
        raise Refused('payload file set')
    return publish(p, files, 'commit-' + p['commit'][:12], m['generation'], tuple(p['csp']),
                   {'mode': 'commit', 'commit': p['commit']})


def main(argv):
    if '--follow' in argv:
        payload = dict(mode='follow', paths=PATHS, keep=KEEP, dry_run='--dry-run' in argv)
    else:
        payload = json.loads(sys.stdin.readline())
    try:
        out = dict(run(payload), ok=True)
    except Refused as e:
        print(json.dumps({'ok': False, 'error': str(e)}))
        return 3
    if not (out.pop('quiet', False) and '--follow' in argv):    # a no-op timer tick logs nothing
        print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
