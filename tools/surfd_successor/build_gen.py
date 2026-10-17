#!/usr/bin/env python3
"""P770: build a code-only successor surfd generation beside the serving one (same file
set, schema 20, same guard and witness), from a staged git archive of an inspected commit.

  python3 build_gen.py <root> <40-hex sha> <serving generation root>

<root>/stage holds the archive, plus EXPECTED.json ({path: sha256} of every runtime file
at <sha>, from git) and COMMIT, written by the operator from the commit. Writes <root>/runtime, <root>/control and, via the
guard's own init, <root>/state (CLOSED). Touches nothing outside <root>.
"""
import ast
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

P = pathlib.Path
GUARD_SHA = 'af6c26b5df1e72cc0943c8ee8df4a124a202295fdc9e46ba7647672c93746a75'
PI_ONLY = {'momfetch.py', 'msml.py'}     # on the Pi only, never in surfd/
DISPATCH_SHA = '787373937cd6d2afc66f3ae9ef073e3f4e9b7e55f9d42c4af7ade52fde7eda49'
HOME = P('/srv/nvme/surfd')
# /srv/nvme/surfd's entrypoints are import stubs that run the generation's code
# under its guard (tools/surfd_import_dispatch.py); run.sh restarts its server.
STUBS = ('surfd.py', 'ksfimport.py', 'ksfgrab.py', 'ksfprofile.py',
         'tools/ksfconvert.py', 'tools/ksfreplay_info.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root, gen, OLD = P(sys.argv[1]), sys.argv[2], P(sys.argv[3])
    OLDGEN = json.loads((OLD / 'state/manifest.json').read_text())['generation']
    assert re.fullmatch(r'[0-9a-f]{40}', gen), gen
    assert root.resolve() == root and str(root).startswith('/srv/nvme/agent-work/'), root
    stage, rt, ctl = root / 'stage', root / 'runtime', root / 'control'
    assert stage.is_dir() and not rt.exists() and not ctl.exists() and not (root / 'state').exists()
    os.umask(0o077)
    # agent-work is setgid; the guard wants exactly 0700 on its state dir, which inherits it.
    os.chmod(root, 0o700)

    assert (stage / 'COMMIT').read_text().strip() == gen, 'stage is not this commit'
    expected = json.loads((stage / 'EXPECTED.json').read_text())
    rels = sorted(str(p.relative_to(OLD / 'runtime')) for p in (OLD / 'runtime').rglob('*')
                  if p.is_file() and '__pycache__' not in p.parts)
    origin = {}
    rt.mkdir(mode=0o700)
    for rel in rels:
        if rel.startswith('tools/'):
            src = stage / rel
        elif rel in PI_ONLY:
            src = OLD / 'runtime' / rel
        else:
            src = stage / 'surfd' / rel
        assert src.is_file(), rel
        assert rel in PI_ONLY or sha(src) == expected[rel], 'stage file differs from git: ' + rel
        origin[rel] = str(src)
        dst = rt / rel
        dst.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    hashes = {rel: sha(rt / rel) for rel in rels}

    ctl.mkdir(mode=0o700)
    guard = OLD / 'control/surfd_transition_guard.py'
    assert sha(guard) == GUARD_SHA
    shutil.copyfile(guard, ctl / 'surfd_transition_guard.py')
    assert (OLD / 'control/gunicorn.conf.py').read_bytes() == b''
    shutil.copyfile(OLD / 'control/gunicorn.conf.py', ctl / 'gunicorn.conf.py')

    m = json.loads((OLD / 'control/guard-manifest.json').read_text())
    assert m['generation'] == OLDGEN and m['target_schema'] == 20
    sub = lambda v: (str(root) + v[len(str(OLD)):]) if v.startswith(str(OLD) + '/') else v
    m['generation'] = gen
    m['source_home'] = str(rt)
    m['hashes'] = {k: hashes[k] for k in m['hashes']}
    m['routes'] = {k: [sub(a) for a in v] for k, v in m['routes'].items()}
    for argv in m['routes'].values():
        for a in argv:
            assert str(OLD) not in a, a
            assert not a.startswith(str(root) + '/') or P(a).exists(), 'route path missing: ' + a
    (ctl / 'guard-manifest.json').write_text(json.dumps(m, sort_keys=True) + '\n')

    w = (OLD / 'control/witness_wsgi.py').read_text()
    line = [l for l in w.splitlines() if l.startswith('expected={')]
    assert len(line) == 1
    assert set(ast.literal_eval(line[0][len('expected='):])) == set(rels), 'witness file set'
    w = w.replace(line[0], 'expected=' + repr(hashes))
    assert w.count(str(OLD)) == 1 and w.count(OLDGEN) == 1
    w = w.replace(str(OLD), str(root)).replace(OLDGEN, gen)
    (ctl / 'witness_wsgi.py').write_text(w)

    for p in sorted(rt.rglob('*'), reverse=True):
        p.chmod(0o500 if p.is_dir() else 0o400)
    rt.chmod(0o500)
    for name in ('surfd_transition_guard.py', 'gunicorn.conf.py', 'guard-manifest.json', 'witness_wsgi.py'):
        (ctl / name).chmod(0o400)

    # The live stubs must be exactly what the dispatcher renders for OLD: then the
    # successor's are the same template with its own bindings. pre/ keeps the live
    # bytes, which the cutover compares before replacing and rollback restores.
    disp = OLD / 'control/surfd_import_dispatch.py'
    assert sha(disp) == DISPATCH_SHA
    shutil.copyfile(disp, ctl / 'surfd_import_dispatch.py')
    (ctl / 'surfd_import_dispatch.py').chmod(0o400)
    ns = {'__name__': '_p770_dispatch'}
    exec(compile((ctl / 'surfd_import_dispatch.py').read_bytes(), 'surfd_import_dispatch.py', 'exec'), ns)
    def render(where, generation, rel):
        return ns['render_wrapper'](dispatch_path=str(where / 'control/surfd_import_dispatch.py'),
                                    dispatch_sha256=DISPATCH_SHA,
                                    guard_path=str(where / 'control/surfd_transition_guard.py'),
                                    guard_sha256=GUARD_SHA, state_dir=str(where / 'state'),
                                    generation=generation, source_relative=rel)
    for rel in STUBS:
        live = (HOME / rel).read_bytes()
        assert live == render(OLD, OLDGEN, rel), 'live stub is not its rendering: ' + rel
        for sub_dir, data in (('pre', live), ('stubs', render(root, gen, rel))):
            out = ctl / sub_dir / rel
            out.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            out.write_bytes(data)
            out.chmod(0o600)
    run = (HOME / 'run.sh').read_bytes()
    assert run.count(str(OLD).encode()) == 2 and run.count(OLDGEN.encode()) == 1, 'run.sh shape'
    (ctl / 'pre/run.sh').write_bytes(run)
    (ctl / 'stubs/run.sh').write_bytes(run.replace(str(OLD).encode(), str(root).encode())
                                       .replace(OLDGEN.encode(), gen.encode()))
    (ctl / 'pre/run.sh').chmod(0o700)
    (ctl / 'stubs/run.sh').chmod(0o700)
    (ctl / 'build.json').write_text(json.dumps({'generation': gen, 'origin': origin, 'hashes': hashes},
                                               indent=1, sort_keys=True) + '\n')
    r = subprocess.run(['/usr/bin/python3.11', '-I', str(ctl / 'surfd_transition_guard.py'),
                        '--state-dir', str(root / 'state'), 'init', '--manifest', str(ctl / 'guard-manifest.json')],
                       capture_output=True, text=True)
    print(r.stdout.strip(), r.stderr.strip())
    assert r.returncode == 0
    changed = sorted(k for k in hashes if hashes[k] != json.loads(
        json.dumps(ast.literal_eval([l for l in (OLD / 'control/witness_wsgi.py').read_text().splitlines()
                                     if l.startswith('expected={')][0][len('expected='):])))[k])
    print('files', len(rels), 'changed from the serving generation:', ' '.join(changed))


if __name__ == '__main__':
    main()
