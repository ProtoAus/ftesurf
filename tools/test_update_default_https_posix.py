#!/usr/bin/env python3
"""Linux native default-HTTPS/menu acceptance with the real published archive.

Run inside an owned private PID/mount namespace and tmpfs/Xvfb runtime. No key,
URL/pin/policy override, bootstrap adapter, publication or player install writes.
strace follows forks/execs through orphan adoption; raw task exits precede grading.
"""
import argparse
import ast
from datetime import datetime, timezone
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import pty
import re
import shutil
import signal
import stat
import subprocess
import tarfile
import time

import updatefeed

FEED = 'https://proto.bar/ftesurf/update.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(data):
    return hashlib.blake2b(data, digest_size=32).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def namespace_members():
    rows = {}
    for p in Path('/proc').glob('[0-9]*/stat'):
        try:
            fields = p.read_text().rsplit(')', 1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            continue
        rows[int(p.parent.name)] = {'state': fields[0], 'ppid': int(fields[1]),
                                   'group': int(fields[2]), 'start': int(fields[19])}
    return rows


def group_members(pgid):
    return {pid: row for pid, row in namespace_members().items() if row['group'] == pgid}


def stop_owned_group(process):
    # A reaped tracer/leader is not proof that its group is empty.
    if group_members(process.pid):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=10)
    until = time.monotonic() + 10
    while True:
        while True:
            try:
                pid, _ = os.waitpid(-process.pid, os.WNOHANG)
            except ChildProcessError:
                break
            if not pid:
                break
        if not group_members(process.pid):
            return
        assert time.monotonic() < until, 'owned process group survived containment'
        time.sleep(.02)


def contain_tracees(process, baseline):
    """Terminate only new private-namespace tracees; never kill their observer."""
    assert os.environ.get('FTESURF_OWNED_PID_NAMESPACE') == '1'
    assert Path('/proc/1/comm').read_text().strip() == 'bash', 'containment requires owned private namespace'
    until = time.monotonic() + 10
    while process.poll() is None:
        current = namespace_members()
        for pid, row in current.items():
            if pid == process.pid or (pid in baseline and row['start'] == baseline[pid]['start']):
                continue
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if time.monotonic() >= until:
            # This is explicitly a failed observer, not a complete exit receipt.
            process.kill()
            process.wait(timeout=10)
            raise AssertionError('observer did not finish after tracee containment')
        time.sleep(.02)
    process.wait(timeout=10)
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            break
        if not pid:
            break
    assert not group_members(process.pid), 'tracee group survived containment'
    current = namespace_members()
    assert not {pid: row for pid, row in current.items()
                if pid not in baseline or baseline[pid]['start'] != row['start']}, 'new namespace processes survived containment'


def parse_trace_text(text, pid):
    """Parse only full successful exec vectors and one terminal task outcome."""
    row = {'pid': pid, 'execs': [], 'children': [], 'errors': [], 'exit': None, 'terminal': None}
    pending = None
    for line in text.splitlines():
        if line.endswith('<unfinished ...>'):
            match = re.match(r'(\w+)\(', line)
            if pending or not match:
                row['errors'].append('unmatched unfinished syscall: ' + line)
            else:
                pending = (match.group(1), line[:-len('<unfinished ...>')])
            continue
        resumed = re.fullmatch(r'<\.\.\. (\w+) resumed>(.*)', line)
        if resumed:
            if not pending or resumed.group(1) != pending[0]:
                row['errors'].append('unmatched resumed syscall: ' + line)
                continue
            line = pending[1] + resumed.group(2)
            pending = None
        if re.match(r'(?:clone3?|fork|vfork)\(', line):
            created = re.fullmatch(r'(?:clone3?|fork|vfork)\(.*\)\s+= (-?\d+)(.*)', line)
            if not created:
                row['errors'].append('unparsed task creation: ' + line)
            elif int(created.group(1)) > 0:
                row['children'].append(int(created.group(1)))
        if line.startswith('execve('):
            # strace strings here are ASCII C/Python-compatible quoted literals.
            execmatch = re.fullmatch(r'execve\(("(?:[^"\\]|\\.)*"), (\[.*\]), [^\n]*\) = 0', line)
            if not execmatch or '...' in execmatch.group(2):
                row['errors'].append('failed/truncated/unparsed exec: ' + line)
                continue
            try:
                image, argv = ast.literal_eval(execmatch.group(1)), ast.literal_eval(execmatch.group(2))
                assert isinstance(image, str) and isinstance(argv, list) and all(isinstance(x, str) for x in argv)
            except (AssertionError, SyntaxError, ValueError) as error:
                row['errors'].append('invalid exec vector: ' + repr(error))
                continue
            row['execs'].append({'image': image, 'argv': argv})
        elif 'execveat(' in line or ('execve' in line and 'resumed>' in line):
            row['errors'].append('unsupported exec record: ' + line)
        if line.startswith('+++'):
            match = re.fullmatch(r'\+\+\+ exited with (\d+) \+\+\+', line)
            if row['terminal'] is not None or not match:
                row['errors'].append('non-normal/duplicate terminal record: ' + line)
            row['terminal'] = line
            if match:
                row['exit'] = int(match.group(1))
    if pending:
        row['errors'].append('unfinished syscall at end of trace: ' + pending[0])
    return row


def read_trace(prefix):
    rows = []
    for p in sorted(prefix.parent.glob(prefix.name + '.*')):
        assert p.suffix[1:].isdigit(), 'unexpected trace filename: ' + str(p)
        rows.append(parse_trace_text(p.read_text(), int(p.suffix[1:])))
    return rows


def grade_chain(rows, engine, dest, restart, initial_argv=None):
    assert rows, 'no traced native tasks'
    assert all(not r['errors'] and r['exit'] == 0 for r in rows), ('incomplete/nonzero task census', rows)
    execs = [(r['pid'], e) for r in rows for e in r['execs']]
    assert execs, 'no successful native exec'
    initial = [(pid, e) for pid, e in execs if Path(e['image']).resolve() == engine]
    assert len(initial) == 1, ('initial exec census', execs)
    assert initial[0][1]['argv'][0] == str(engine)
    if initial_argv is not None:
        assert initial[0][1]['argv'] == initial_argv, 'initial argv changed'
    ids = {r['pid'] for r in rows}
    assert len(ids) == len(rows), 'duplicate task receipt'
    edges = [(r['pid'], child) for r in rows for child in r['children']]
    parents = {child: parent for parent, child in edges}
    assert len(parents) == len(edges), 'duplicate/reused child PID'
    assert set(parents) <= ids, 'referenced task trace missing'
    assert ids - set(parents) == {initial[0][0]}, 'trace tree must have exactly the initial root'
    visited = set()
    pending = [initial[0][0]]
    while pending:
        pid = pending.pop()
        assert pid not in visited, 'cyclic task ancestry'
        visited.add(pid)
        pending.extend(child for parent, child in edges if parent == pid)
    assert visited == ids, 'unreachable task trace'
    launchers = [(pid, e) for pid, e in execs if Path(e['image']).resolve() == dest / 'ftesurf-launcher']
    returns = [(pid, e) for pid, e in execs if Path(e['image']).resolve() == dest / 'ftesurf64']
    assert len(execs) == (3 if restart else 1), ('unexpected executable census', execs)
    if restart:
        assert len(launchers) == len(returns) == 1
        pid, launch = launchers[0]
        argv = launch['argv']
        assert len(argv) == 5 and Path(argv[0]).resolve() == dest / 'ftesurf-launcher', argv
        assert argv[1] == '--dir' and Path(argv[2]).resolve() == dest, argv
        assert argv[3:] == ['--wait-for-game', '--yes'], argv
        returned = returns[0][1]['argv']
        assert len(returned) == 3 and Path(returned[0]).resolve() == dest / 'ftesurf64', returned
        assert returned[1:] == ['-manifest', 'default.fmf'], returned
        assert len({initial[0][0], pid, returns[0][0]}) == 3, 'actors must be distinct processes'
        ancestor = returns[0][0]
        ancestors = []
        while ancestor in parents:
            ancestor = parents[ancestor]
            ancestors.append(ancestor)
        assert pid in ancestors, 'returning game is not a descendant of the launcher'
    else:
        assert not launchers and not returns


def has_actor(text, actor):
    if actor.startswith('HTTPS_'):
        # POSIX console logs also echo the typed command before its output.
        return any(re.fullmatch(r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ' + re.escape(actor), line)
                   for line in text.splitlines())
    return actor in text


def grade_return(text):
    assert has_actor(text, 'HTTPS_REAL_RETURNING_GAME')
    assert 'ui_update_probe: consent=1 state=uptodate screen=0 client=1' in text
    assert 'manifest     : ' + FEED in text


EXPORT_DIRS = ['ftesurf/logs', 'ftesurf/screenshots', 'ftesurf/cfg/test', '.ftesurf-updater']


def no_links(root, path, optional=False):
    """Static no-follow check, including the scan root and every owned ancestor.

    This is not an openat/hostile ancestor-swap race certificate.
    """
    rel = path.relative_to(root)
    current = root
    for part in [None] + list(rel.parts):
        if part is not None:
            current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            if optional:
                return False
            raise
        assert stat.S_ISDIR(mode) or stat.S_ISREG(mode), 'linked/special owned path: ' + str(current)
    return True


def export_runtime(dest, evidence):
    # No identity.pfx/private generated credentials or mounted content exports.
    for directory in EXPORT_DIRS:
        source = dest / directory
        if not no_links(dest, source, optional=True):
            continue
        for p in source.rglob('*'):
            no_links(dest, p)
            if p.is_file():
                rel = p.relative_to(dest)
                out = evidence / 'runtime-evidence' / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                no_links(evidence, out.parent)
                no_links(evidence, out, optional=True)
                shutil.copyfile(p, out)


def export_sentinels(dest, evidence, protected):
    for path in protected:
        source = dest / path
        no_links(dest, source)
        out = evidence / 'sentinels' / path
        out.parent.mkdir(parents=True, exist_ok=True)
        no_links(evidence, out.parent)
        no_links(evidence, out, optional=True)
        out.write_bytes(source.read_bytes())


def preserve_recovery(dest, evidence, protected):
    """Independent verified, persistent non-secret bundle before fragile exports.

    Unsafe sources are named, never followed. If this also fails, the wrapper
    retains the private namespace instead of destroying its tmpfs recovery source.
    """
    import io
    data, unsafe = {}, []
    for directory in EXPORT_DIRS:
        source = dest / directory
        try:
            if not no_links(dest, source, optional=True):
                continue
            candidates = list(source.rglob('*'))
        except AssertionError:
            unsafe.append(directory)
            continue
        for p in candidates:
            rel = p.relative_to(dest).as_posix()
            try:
                no_links(dest, p)
                if p.is_file():
                    data[rel] = p.read_bytes()
            except AssertionError:
                unsafe.append(rel)
    for path in protected:
        try:
            no_links(dest, dest / path)
            data[path] = (dest / path).read_bytes()
        except (AssertionError, FileNotFoundError):
            unsafe.append(path)
    index = {'files': {p: {'sha256': sha(b), 'bytes': len(b)} for p, b in sorted(data.items())},
             'unsafe_sources_not_followed': sorted(set(unsafe))}
    bundle = evidence / 'recovery-runtime.tar'
    temporary = evidence / 'recovery-runtime.tar.tmp'
    assert not bundle.exists() and not temporary.exists()
    with tarfile.open(temporary, 'w') as tar:
        for path, raw in {**data, 'RECOVERY.json': json.dumps(index, sort_keys=True).encode()}.items():
            member = tarfile.TarInfo(path); member.mode = 0o644; member.size = len(raw)
            tar.addfile(member, io.BytesIO(raw))
    with tarfile.open(temporary) as tar:
        assert {m.name for m in tar} == set(data) | {'RECOVERY.json'}
        for path, raw in data.items():
            assert tar.extractfile(path).read() == raw, 'recovery bundle verification failed'
        assert json.loads(tar.extractfile('RECOVERY.json').read()) == index
    temporary.rename(bundle)
    receipt = {'verified': True, 'path': str(bundle), 'sha256': sha(bundle.read_bytes()), **index}
    (evidence / 'recovery-verified.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return verify_recovery(evidence)


def verify_recovery(evidence):
    receipt_path = evidence / 'recovery-verified.json'
    bundle = evidence / 'recovery-runtime.tar'
    no_links(evidence, receipt_path); no_links(evidence, bundle)
    receipt = json.loads(receipt_path.read_text())
    assert receipt['verified'] and receipt['path'] == str(bundle) and sha(bundle.read_bytes()) == receipt['sha256']
    with tarfile.open(bundle) as tar:
        members = tar.getmembers()
        assert all(m.isfile() and m.mode == 0o644 and m.uid == m.gid == 0 for m in members)
        assert len(members) == len(receipt['files']) + 1
        assert {m.name for m in members} == set(receipt['files']) | {'RECOVERY.json'}
        assert json.loads(tar.extractfile('RECOVERY.json').read()) == {
            'files': receipt['files'], 'unsafe_sources_not_followed': receipt['unsafe_sources_not_followed']}
        for path, row in receipt['files'].items():
            raw = tar.extractfile(path).read()
            assert len(raw) == row['bytes'] and sha(raw) == row['sha256']
    return receipt


class OwnedGame:
    def __init__(self, args, engine, dest, evidence, name):
        self.engine, self.dest, self.evidence, self.name = engine, dest, evidence, name
        self.prefix = evidence / (name + '-trace')
        self.baseline = namespace_members()
        self.out = (evidence / (name + '-stdout.log')).open('wb')
        self.master, slave = pty.openpty()
        self.p = None
        self.receipt = {'status': 'FAIL', 'started_utc': utc(), 'initial_argv': args}
        try:
            self.p = subprocess.Popen(['strace', '-f', '-ff', '-q', '-s', '65535', '-e', 'trace=process',
                                       '-o', str(self.prefix), '--'] + args,
                                      cwd=dest, stdin=subprocess.PIPE, stdout=self.out,
                                      stderr=slave, start_new_session=True)
            self.receipt['tracer_pid'] = self.p.pid
        except BaseException:
            os.close(self.master)
            self.out.close()
            raise
        finally:
            os.close(slave)

    def drain(self):
        os.set_blocking(self.master, False)
        while True:
            try:
                data = os.read(self.master, 65536)
            except BlockingIOError:
                break
            except OSError as error:
                if error.errno != errno.EIO:
                    raise
                break
            if not data:
                break
            self.out.write(data)
        self.out.flush()

    def logs(self, prefix=None):
        return '\n'.join(p.read_text(errors='replace') for p in
                         (self.dest / 'ftesurf/logs').glob((prefix or self.name) + '*.log'))

    def wait(self, actor, prefix=None, timeout=60):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            self.drain()
            text = self.logs(prefix)
            if has_actor(text, actor):
                return text
            assert self.p.poll() is None, 'tracee chain exited before ' + actor
            time.sleep(.05)
        raise AssertionError('missing actor: ' + actor)

    def send(self, command):
        assert len(command.encode()) < 255
        assert self.p.poll() is None
        self.p.stdin.write((command + '\n').encode())
        self.p.stdin.flush()

    def save(self):
        (self.evidence / (self.name + '-processes.json')).write_text(json.dumps(self.receipt, indent=2) + '\n')

    def finish(self, restart=False):
        self.p.wait(timeout=90)  # strace follows the complete real descendant chain.
        self.drain()
        # Reap adopted children after tracer has exited, retaining trace exit truth.
        while True:
            try:
                pid, _ = os.waitpid(-self.p.pid, os.WNOHANG)
            except ChildProcessError:
                break
            if not pid:
                break
        current = namespace_members()
        unexpected = {pid: row for pid, row in current.items()
                      if pid not in self.baseline or self.baseline[pid]['start'] != row['start']}
        self.receipt.update(tracer_exit=self.p.returncode, tasks=read_trace(self.prefix),
                            group_before_cleanup=group_members(self.p.pid),
                            unexpected_namespace_before_cleanup=unexpected)
        self.save()  # Complete raw census before even initial/descendant grading.
        assert self.p.returncode == 0
        assert not self.receipt['group_before_cleanup'] and not unexpected, 'live/zombie owned descendants remain'
        grade_chain(self.receipt['tasks'], self.engine, self.dest, restart, self.receipt['initial_argv'])
        self.receipt['status'] = 'PASS'
        self.save()
        return self.receipt.copy()

    def close(self):
        try:
            try:
                self.receipt.update(namespace_before_cleanup=namespace_members(),
                                    group_before_containment=group_members(self.p.pid))
                self.save()
                self.receipt['tasks_before_containment'] = read_trace(self.prefix)
                self.save()
                export_runtime(self.dest, self.evidence)
            finally:
                # Keep the tracer alive to record each tracee's real termination.
                contain_tracees(self.p, self.baseline)
                self.drain()
                self.receipt.update(group_after_cleanup=group_members(self.p.pid), tracer_exit=self.p.returncode,
                                    tasks=read_trace(self.prefix))
        except BaseException as error:
            self.receipt.update(status='FAIL', cleanup_error=repr(error))
            raise
        finally:
            self.save()
            self.p.stdin.close()
            os.close(self.master)
            self.out.close()


def extract_archive(archive, dest):
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        for m in members:
            path = PurePosixPath(m.name)
            assert path.parts[0] == 'FTESurf' and not path.is_absolute() and '..' not in path.parts
            assert m.uid == m.gid == 0 and (m.isfile() or m.isdir()), 'unsafe archive member: ' + m.name
            rel = Path(*path.parts[1:])
            out = dest / rel
            if m.isdir():
                assert m.mode == 0o755
                out.mkdir(parents=True, exist_ok=True)
                out.chmod(m.mode)
            else:
                expected = 0o755 if rel.as_posix() in ['ftesurf64', 'ftesurf-launcher', 'ftesurf.sh'] else 0o644
                assert m.mode == expected, ('archive mode', m.name, m.mode)
                assert not out.exists(), 'duplicate archive member'
                out.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(m) as stream:
                    out.write_bytes(stream.read())
                out.chmod(m.mode)


def retire_runtime(dest, evidence):
    no_links(dest, dest)
    paths = sorted(dest.rglob('*'), key=lambda p: len(p.parts), reverse=True)
    inventory = []
    for p in paths:
        assert not p.is_symlink(), 'linked runtime not disposable: ' + str(p)
        inventory.append({'path': p.relative_to(dest).as_posix(), 'bytes': p.stat().st_size if p.is_file() else None})
    (evidence / 'runtime-inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
    for p in paths:
        if p.is_file():
            p.unlink()
        else:
            p.rmdir()
    dest.rmdir()
    assert not dest.exists()


def finalize_runtime(dest, evidence, result, protected, baseline):
    try:
        result['recovery'] = preserve_recovery(dest, evidence, protected)
        export_runtime(dest, evidence)
        export_sentinels(dest, evidence, protected)
        current = namespace_members()
        result['unexpected_namespace_before_retirement'] = {pid: row for pid, row in current.items()
            if pid not in baseline or baseline[pid]['start'] != row['start']}
        assert not result['unexpected_namespace_before_retirement'], 'namespace still contains owned descendants'
        retire_runtime(dest, evidence)
        result['runtime_retired'] = True
    except BaseException as error:
        result.update(verdict='FAIL', retirement_error=repr(error), runtime_retired=False, runtime_root=str(dest),
                      runtime_disposition='tmpfs recovery source; wrapper must retain namespace unless verified recovery bundle exists')
        raise
    finally:
        result['finished_utc'] = utc()
        (evidence / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({'verdict': result['verdict'], 'arms': len(result['arms']), 'evidence': str(evidence), 'failure': result.get('failure'), 'retirement_error': result.get('retirement_error')}))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ['engine', 'archive', 'receipt', 'feed', 'runtime-root', 'evidence']:
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--engine-sha256', required=True)
    a = ap.parse_args()
    assert os.name == 'posix' and os.environ.get('FTESURF_OWNED_PID_NAMESPACE') == '1'
    assert os.getpid() != 1 and Path('/proc/1/comm').read_text().strip() == 'bash', 'expected owned namespace init'
    assert os.environ.get('DISPLAY') and 'WAYLAND_DISPLAY' not in os.environ
    import ctypes
    assert ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) == 0, 'subreaper required'
    engine, archive = a.engine.resolve(strict=True), a.archive.resolve(strict=True)
    dest, evidence = a.runtime_root.absolute(), a.evidence.absolute()
    assert not dest.exists() and not evidence.exists() and dest.parent.is_dir() and evidence.parent.is_dir()
    dest.mkdir(); evidence.mkdir()
    (dest / 'OWNER.md').write_text('Owned synthetic Linux HTTPS acceptance. Evidence: ' + str(evidence) + '\n')
    result = {'verdict': 'FAIL', 'started_utc': utc(), 'harness_sha256': sha(Path(__file__).read_bytes()), 'arms': []}
    baseline = namespace_members()
    protected = {}
    try:
        assert sha(engine.read_bytes()) == a.engine_sha256
        receipt = json.loads(a.receipt.read_text(encoding='utf-8-sig'))
        linux = receipt['linux']
        assert archive.name == linux['archive']['name'] and archive.stat().st_size == linux['archive']['bytes']
        assert sha(archive.read_bytes()).upper() == linux['archive']['sha256'].upper()
        signed = a.feed.read_bytes()
        assert sha(signed) == receipt['update_feed']['sha256']
        import urllib.request
        with urllib.request.urlopen(FEED, timeout=30) as response:
            assert response.url == FEED and response.read(2*1024*1024+1) == signed, 'production feed drift'
        manifest = updatefeed.verify(signed)
        assert manifest['version'] == receipt['version']
        assert all(f['size'] <= 32*1024*1024 for f in manifest['files'])
        assert all(url.startswith('https://') for url in manifest['mirrors'])
        extract_archive(archive, dest)
        actual = {p.relative_to(dest).as_posix(): sha(p.read_bytes()).upper() for p in dest.rglob('*')
                  if p.is_file() and p.name != 'OWNER.md'}
        (evidence / 'archive-hashes.json').write_text(json.dumps(actual, indent=2) + '\n')
        assert len(actual) == linux['content']['file_count']
        assert sum((dest / p).stat().st_size for p in actual) == linux['content']['raw_bytes']
        assert all(actual.get(p) == h.upper() for p, h in linux['content']['hashes'].items())
        assert actual['ftesurf-launcher'] == linux['bootstrap']['sha256'].upper()
        assert actual['notices/bootstrap.txt'] == linux['bootstrap']['notices_sha256'].upper()
        files = {f['path']: f for f in manifest['files'] if f['platform'] in ('all', 'linux64')}
        assert set(actual) == set(files) | {'ftesurf-launcher'}
        assert 'DISABLEHOMEDIR 1' in (dest / 'default.fmf').read_text()
        assert all(digest((dest / p).read_bytes()) == f['hash'] and (dest / p).stat().st_size == f['size'] for p, f in files.items())
        result.update(engine_sha256=sha(engine.read_bytes()), archive_sha256=sha(archive.read_bytes()),
                      feed_sha256=sha(signed), version=manifest['version'], bootstrap_sha256=actual['ftesurf-launcher'],
                      returning_engine_sha256=actual['ftesurf64'])
        meta = dest / '.ftesurf-updater'; meta.mkdir()
        state = {'version': manifest['version'], 'files': {p: f['hash'] for p, f in files.items()}}
        (meta / 'state.json').write_text(json.dumps(state)); (meta / 'installed.json').write_bytes(signed)
        cfgdir = dest / 'ftesurf/cfg/test'; cfgdir.mkdir(parents=True)
        (cfgdir / 'https-return.cfg').write_text('cfg_save_auto 0\n')
        zone = next(p for p in files if p.startswith('ftesurf/maps/zones/local/'))
        protected = {'ftesurf/ftesurf.cfg': b'cfg_save_auto 0\nexec cfg/test/https-return.cfg\n// owned player settings\n',
                     'ftesurf/fs_addons.txt': b'// owned local mounts\n', zone: b'// owned edited zone\n',
                     'ftesurf/data/runs/player-sentinel.rec': b'owned recording\n', 'hl2/player-sentinel.txt': b'owned mounted content\n'}
        for path, data in protected.items():
            p = dest / path; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
        (dest / 'ftesurf/data/consent.txt').write_text('version 1\n')
        def guard():
            for path, data in protected.items():
                no_links(dest, dest / path)
                assert (dest / path).read_bytes() == data, 'changed sentinel: ' + path
            assert sha((dest / 'ftesurf-launcher').read_bytes()).upper() == actual['ftesurf-launcher']
        def start(name):
            (cfgdir / 'https-return.cfg').write_text('cfg_save_auto 0\n')
            (cfgdir / (name + '.cfg')).write_text('cfg_save_auto 0\ncl_idlefps 0\ncl_maxfps 100\nvid_fullscreen 0\nvid_width 1280\nvid_height 720\n'
                'volume 0\nmusicvolume 0\ncon_savehistory 0\ndeveloper 1\nlog_developer 1\n'
                f'log_name {name}\nlog_enable 1\nruleset_allow_in 1\nin 4 exec cfg/test/{name}-steps.cfg\n')
            (cfgdir / (name + '-steps.cfg')).write_text('cfg_save_auto 0\nmenu_restart\nwait 100\nwait 200\necho HTTPS_READY\n')
            return OwnedGame([str(engine), '-plugin', '-nohome', '-basedir', str(dest), '-manifest', str(dest / 'default.fmf'),
                              '-window', '+set', 'cfg_save_auto', '0', '+exec', 'cfg/test/' + name + '.cfg'], engine, dest, evidence, name)
        def probe(game, marker):
            game.send('ui_update_probe; update_info; update_manifest_url; update_allow_insecure; echo ' + marker)
            text = game.wait(marker)
            assert 'manifest     : ' + FEED in text and '"update_allow_insecure" is "0"' in text
            assert 'client=1' in text and 'screen=0' in text and 'ui_hover: no control' not in text
            return text
        def click(game, button, marker):
            # P823: no Updates screen; its buttons were these engine commands.
            cmd = {'mu_off': 'update_permission 0', 'mu_enable': 'update_permission 1; update_check auto'}.get(button)
            game.send((cmd if cmd else 'ui_hover @' + button + '; ui_mouse down; ui_mouse up') + '; echo ' + marker)
            return game.wait(marker)
        g = start('https-control')
        try:
            g.wait('HTTPS_READY')
            assert 'consent=-1' in probe(g, 'HTTPS_UNDECIDED') and not (meta / 'consent').exists()
            before = (meta / 'state.json').read_bytes()
            click(g, 'mu_off', 'HTTPS_OFF_CLICKED')
            assert 'consent=0 state=disabled' in probe(g, 'HTTPS_OFF_PROBED')
            assert (meta / 'consent').read_bytes() == b'0\n' and (meta / 'state.json').read_bytes() == before
            click(g, 'mu_enable', 'HTTPS_ENABLE_CLICKED'); g.wait('up to date')
            assert 'consent=1 state=uptodate' in probe(g, 'HTTPS_ENABLED') and (meta / 'consent').read_bytes() == b'1\n'
            g.send('screenshot https-control.png; echo HTTPS_CONTROL_DONE; quit')
            row = g.finish(); row['arm'] = 'consent-control'; result['arms'].append(row); guard()
        finally:
            g.close()
        for name, target, verdict in [('https-content', 'ftesurf/gfx/env/milk.png', 'restart'), ('https-engine', 'ftesurf64', 'launcher')]:
            original = (dest / target).read_bytes(); corrupt = b'owned default-HTTPS subject\n'
            (dest / target).write_bytes(corrupt)
            state = json.loads((meta / 'state.json').read_text()); state['version'] = '0.1.24'; state['files'][target] = '0'*64
            (meta / 'state.json').write_text(json.dumps(state))
            g = start(name)
            try:
                g.wait('HTTPS_READY'); g.wait('installed 1 file' if verdict == 'restart' else 'update includes engine binaries')
                text = probe(g, 'HTTPS_SUBJECT_PLANNED')
                assert 'consent=1 state=' + verdict in text
                assert (dest / target).read_bytes() == (original if verdict == 'restart' else corrupt)
                g.send('screenshot ' + name + '.png; echo HTTPS_PANE_CAPTURED'); g.wait('HTTPS_PANE_CAPTURED')
                ret = name + '-return'
                (cfgdir / 'https-return.cfg').write_text('cfg_save_auto 0\ncl_idlefps 0\ncl_maxfps 100\nvid_fullscreen 0\nvolume 0\nmusicvolume 0\ncon_savehistory 0\n'
                    f'log_name {ret}\nlog_enable 1\ndeveloper 1\nlog_developer 1\nruleset_allow_in 1\n'
                    f'echo HTTPS_REAL_RETURNING_GAME\nin 4 exec cfg/test/{ret}-steps.cfg\n')
                (cfgdir / (ret + '-steps.cfg')).write_text('cfg_save_auto 0\nmenu_restart\nwait 100\nwait 200\n'
                    'ui_update_probe\nupdate_info\necho HTTPS_RETURN_PANE_READY\n'
                    f'screenshot {ret}.png\nwait 60\nquit\n')
                click(g, 'mu_restart', 'HTTPS_RESTART_CLICKED')
                g.wait('HTTPS_REAL_RETURNING_GAME', prefix=ret)
                row = g.finish(restart=True); returned = g.logs(ret); grade_return(returned)
                assert has_actor(returned, 'HTTPS_RETURN_PANE_READY') and (dest / target).read_bytes() == original
                assert json.loads((meta / 'state.json').read_text())['version'] == manifest['version']
                assert (meta / 'installed.json').read_bytes() == signed and not (meta / 'ingame/journal.json').exists()
                assert digest((dest / target).read_bytes()) == files[target]['hash']
                assert (dest / 'ftesurf64').stat().st_mode & 0o111 == 0o111
                if verdict == 'restart':
                    assert 'update: installed 1 files' in text
                row.update(arm=name, target=target, target_blake2b256=files[target]['hash'])
                result['arms'].append(row); guard()
            finally:
                g.close()
        for name in ['https-control', 'https-content', 'https-content-return', 'https-engine', 'https-engine-return']:
            assert (dest / 'ftesurf/screenshots' / (name + '.png')).is_file(), 'pane pixels missing: ' + name
        guard()
        assert all(digest((dest / p).read_bytes()) == f['hash'] for p, f in files.items() if p not in protected)
        result['sentinels'] = {p: sha(data) for p, data in protected.items()}
        result['verdict'] = 'PASS'
    except BaseException as error:
        result['failure'] = repr(error)
        raise
    finally:
        finalize_runtime(dest, evidence, result, protected, baseline)


if __name__ == '__main__':
    main()
