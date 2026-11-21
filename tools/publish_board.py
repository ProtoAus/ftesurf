#!/usr/bin/env python3
"""P1702: publish the web board's eight page files to the NanoPi's static board folder (as proto, no root).

    python3 -B tools/publish_board.py --live            # the LIVE generation's own web/ files
    python3 -B tools/publish_board.py --commit REF      # a UI-only change ahead of a generation
    python3 -B tools/publish_board.py --install-follow  # the 5-minute timer that keeps the board on the live generation
    add --dry-run to print the plan only

nginx (src/release/ftesurf.nginx) serves /ftesurf/board/ and /worldofsurf/board/ (page + seven assets) from
/srv/nvme/ftesurf-site/board/current; every API path stays on surfd. The Pi side is tools/board_publish_pi.py.
The follow timer republishes the live generation's own files within 5 minutes of a swap or rollback; a --commit
publish holds until the live generation changes.

--commit is a BYTE rule, not a history one: the live generation must carry its source_ref's board files exactly, REF
must descend from source_ref, and `git diff source_ref REF` must touch no live member outside web/ (tests aside;
surfd/<name>, the four tools/ copies, the external converters; each must exist at source_ref). So REF's board meets
the same server code the live board was shipped with. A member the live generation deliberately holds at other bytes
than source_ref (mapwatch.py today) is listed as `held`: the live board already runs against it. Outside the rule:
SURFD_TOOLS in the game install, the database, surfd.env switches. A --commit fix cut from source_ref must also land
on main, or the next generation drops it.
Both modes refuse when the installed snippet's CSP for any board file differs from the live surfd.py's.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PI_PROGRAM = Path(__file__).with_name('board_publish_pi.py')
FILES = ('board.html', 'board.css', 'board.js', 'link.css', 'runview.js', 'watch.css', 'watch.html', 'watch.js')
PATHS = dict(board='/srv/nvme/ftesurf-site/board', runsh='/srv/nvme/surfd/run.sh', snippet='/etc/nginx/snippets/ftesurf.conf')
# Live members that the generation kit takes from the game's top-level tools/ (build_candidate.TOOLS_SOURCED).
TOOLS_SOURCED = {'momfetch.py': 'tools/momfetch.py', 'msml.py': 'tools/msml.py',
                 'tools/ksfconvert.py': 'tools/ksfconvert.py', 'tools/ksfreplay_info.py': 'tools/ksfreplay_info.py'}
FOLLOW_DIR = '/srv/nvme/ftesurf-ops/board'
KEEP = 2


def git(*args, root=None):
    return subprocess.run(['git', '-C', str(root or ROOT)] + list(args), check=True, capture_output=True).stdout


def remote(payload, pi, runner=None):
    """Run the Pi program with payload over ssh (or with `runner`, a local interpreter argv, in tests)."""
    program = PI_PROGRAM.read_text()
    argv = (runner + ['-c', program] if runner else
            ['ssh', '-o', 'BatchMode=yes', '-T', pi, '/usr/bin/python3.11 -I -B -c ' + shlex.quote(program)])
    done = subprocess.run(argv, input=(json.dumps(payload) + '\n').encode(), capture_output=True, timeout=120)
    try:
        out = json.loads(done.stdout.decode().strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise SystemExit('remote failed (rc %d): %s' % (done.returncode, done.stderr.decode()[-800:]))
    if not out.get('ok'):
        raise SystemExit('REFUSED: ' + out.get('error', '?'))
    return out


def ui_only(info, ref, root=None):
    """The byte rule (module docstring). Returns the member paths compared."""
    source_ref = info['source_ref']
    if not re.fullmatch('[0-9a-f]{40}', source_ref):
        raise SystemExit('REFUSED: the live generation names no full source_ref (%r)' % source_ref)
    if subprocess.run(['git', '-C', str(root or ROOT), 'merge-base', '--is-ancestor', source_ref, ref]).returncode:
        raise SystemExit('REFUSED: the live source_ref %s is not an ancestor of %s' % (source_ref[:8], ref[:8]))
    for f in FILES:
        if hashlib.sha256(git('show', '%s:surfd/web/%s' % (source_ref, f), root=root)).hexdigest() != info['hashes'].get('web/' + f):
            raise SystemExit('REFUSED: the live generation does not carry its source_ref\'s web/%s; publish --commit only '
                             'once a generation carries its own board (until then: --live)' % f)
    live = {TOOLS_SOURCED.get(n, 'surfd/' + n): h for n, h in info['hashes'].items()
            if not n.startswith('web/') and not Path(n).name.startswith('test_')}
    live.update({'tools/%s.py' % name: h for name, h in info.get('external_python', {}).items()})
    paths = sorted(live)
    missing = [x for x in paths if subprocess.run(['git', '-C', str(root or ROOT), 'cat-file', '-e', '%s:%s' % (source_ref, x)],
                                                  capture_output=True).returncode]
    if missing:
        raise SystemExit('REFUSED: live members with no git source at source_ref (a change would go unseen): %r' % missing)
    changed = git('diff', '--name-only', '--no-renames', source_ref, ref, '--', *paths, root=root).decode().split()
    if changed:
        raise SystemExit('REFUSED: server code changed since the live generation (%s): this board rides a generation, '
                         'then the follow timer publishes it' % ', '.join(changed))
    return sorted(x for x in paths if hashlib.sha256(git('show', '%s:%s' % (source_ref, x), root=root)).hexdigest() != live[x])


def csp_of(source):
    ns = {'__name__': 'board_publish_pi'}
    exec(compile(PI_PROGRAM.read_bytes(), str(PI_PROGRAM), 'exec'), ns)
    return ns['csp_of'](source)


def install_follow(pi):
    """Install the Pi program and the user timer as proto (no root; proto lingers), then publish once."""
    units = ROOT / 'tools/board-follow'
    script = 'set -eu\nD=%s\numask 022\nmkdir -p "$D" ~/.config/systemd/user\n' % FOLLOW_DIR
    for path, dest in ((PI_PROGRAM, '"$D/board_publish_pi.py"'),
                       (units / 'ftesurf-board-follow.service', '~/.config/systemd/user/ftesurf-board-follow.service'),
                       (units / 'ftesurf-board-follow.timer', '~/.config/systemd/user/ftesurf-board-follow.timer')):
        raw = path.read_bytes()
        script += 'printf %%s %s | base64 -d > %s.new\n' % (shlex.quote(base64.b64encode(raw).decode()), dest)
        script += 'test "$(sha256sum < %s.new | cut -c1-64)" = %s\nmv %s.new %s\n' % (dest, hashlib.sha256(raw).hexdigest(), dest, dest)
    script += ('echo %s > "$D/SOURCE.txt"\n' % git('rev-parse', 'HEAD').decode().strip() +
               'systemctl --user daemon-reload\nsystemctl --user enable --now ftesurf-board-follow.timer\n'
               'systemctl --user is-active --quiet ftesurf-board-follow.timer\n'
               'test "$(loginctl show-user "$(id -un)" -p Linger --value)" = yes   # else the timer dies at logout\n'
               '/usr/bin/python3.11 -I -B "$D/board_publish_pi.py" --follow\n'
               'test -f /srv/nvme/ftesurf-site/board/current/board.html\necho FOLLOW INSTALLED\n')
    done = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-T', pi, 'sh -s'], input=script.encode(), capture_output=True, timeout=180)
    sys.stdout.write(done.stdout.decode()); sys.stderr.write(done.stderr.decode())
    if done.returncode or 'FOLLOW INSTALLED' not in done.stdout.decode():
        raise SystemExit('install-follow failed (rc %d)' % done.returncode)


def main(argv=None, runner=None, paths=None, root=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--live', action='store_true')
    mode.add_argument('--commit')
    mode.add_argument('--install-follow', action='store_true')
    ap.add_argument('--pi', default='nanopi')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    if a.install_follow:
        if a.dry_run:
            raise SystemExit('--install-follow has no dry run: it installs and publishes')
        return install_follow(a.pi)
    base = dict(paths=paths or PATHS, keep=KEEP, dry_run=a.dry_run)
    if a.live:
        out = remote(dict(base, mode='live'), a.pi, runner)
    else:
        ref = git('rev-parse', a.commit + '^{commit}', root=root).decode().strip()
        info = remote(dict(base, mode='live-info'), a.pi, runner)
        held = ui_only(info, ref, root)
        files = {f: git('show', '%s:surfd/web/%s' % (ref, f), root=root) for f in FILES}
        out = remote(dict(base, mode='commit', commit=ref, live_generation=info['generation'],
                          files={f: base64.b64encode(raw).decode() for f, raw in files.items()},
                          expect={f: hashlib.sha256(raw).hexdigest() for f, raw in files.items()},
                          csp=list(csp_of(git('show', ref + ':surfd/surfd.py', root=root)))), a.pi, runner)
        out['held'] = held
    print(json.dumps(out, indent=1, sort_keys=True))
    return out


if __name__ == '__main__':
    main()
