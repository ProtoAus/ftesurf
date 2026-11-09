#!/usr/bin/env python3
"""Synthetic Linux-only admission checks. Run after copying beside the QC tools.

Requires Gunicorn exactly 20.1.0. --out is mandatory and must not exist. Nothing
uses a system temporary directory, production app, environment selector, or peer
process signal. Evidence (including failed commands) stays under --out.
"""
import argparse
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
GUARD = HERE / 'surfd_transition_guard.py'
HELPER = HERE / 'surfd_http_admission.py'
GEN = '1' * 40
FILES = ('surfd.py', 'ksfimport.py', 'ksfgrab.py', 'ksfprofile.py',
         'tools/ksfconvert.py', 'tools/ksfreplay_info.py')


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Reuse only bounded, side-effect-free helpers; do not invoke the older suite.
def helpers():
    return load(HERE / 'test_surfd_transition_guard.py', 'guard_test_helpers')


APP = '''import sqlite3
from pathlib import Path
DB = Path(__file__).with_name('fixture.sqlite')
def app(environ, start_response):
    path = environ.get('PATH_INFO')
    status, body = '200 OK', b'healthy'
    if path == '/health':
        pass
    elif path == '/heartbeat' and environ.get('REQUEST_METHOD') == 'POST' and environ.get('HTTP_AUTHORIZATION') == 'Bearer synthetic-fixture-only':
        size = int(environ.get('CONTENT_LENGTH', '0'))
        if not 0 < size <= 128: raise ValueError('bounded synthetic payload required')
        value = environ['wsgi.input'].read(size).decode('ascii')
        with sqlite3.connect(DB) as db:
            db.execute('INSERT INTO heartbeat VALUES (?)', (value,))
        body = b'written'
    elif path == '/representative':
        with sqlite3.connect(DB) as db:
            db.execute('UPDATE counter SET value = value + 1')
            body = str(db.execute('SELECT value FROM counter').fetchone()[0]).encode()
    else:
        status, body = '403 Forbidden', b'forbidden'
    start_response(status, [('Content-Length', str(len(body)))])
    return [body]
'''


class Harness:
    def __init__(self, root, h):
        self.root, self.h = root, h
        self.processes, self.commands, self.cases = [], [], []
        self.home = root / 'home'
        self.home.mkdir(mode=0o700)
        (self.home / 'tools').mkdir(mode=0o700)
        (self.home / 'surfd.py').write_text(APP)
        for name in FILES[1:]:
            (self.home / name).write_text('# synthetic manifest sentinel\n')
        self.state = root / 'state'
        self.db = self.home / 'fixture.sqlite'
        with sqlite3.connect(self.db) as db:
            db.execute('CREATE TABLE heartbeat(value TEXT UNIQUE)')
            db.execute('CREATE TABLE counter(value INTEGER)')
            db.execute('INSERT INTO counter VALUES (0)')
        self.portfile = root / 'selected-port.json'
        self.config = root / 'gunicorn.conf.py'
        self.manifest = {'generation': GEN, 'source_home': str(self.home),
                         'hashes': {n: hashlib.sha256((self.home / n).read_bytes()).hexdigest()
                                    for n in FILES},
                         'routes': {'server': [str(Path(sys.executable).resolve()), '-m',
                                             'gunicorn', '--bind', '127.0.0.1:0', '-c',
                                             str(self.config), 'surfd:app']}}
        manifest = root / 'manifest.json'
        h.save(manifest, self.manifest)
        self.run('init', '--manifest', str(manifest))
        # Hook inputs are exact absolute paths plus raw hashes, never env/argv selectors.
        bindings = {'guard': [str(GUARD), hashlib.sha256(GUARD.read_bytes()).hexdigest()],
                    'helper': [str(HELPER), hashlib.sha256(HELPER.read_bytes()).hexdigest()]}
        digest = hashlib.sha256((self.state / 'manifest.json').read_bytes()).hexdigest()
        self.config.write_text(
            "import hashlib, importlib.util, json\nfrom pathlib import Path\n"
            "workers = 1\nworker_class = 'gthread'\nthreads = 4\n"
            "timeout = 10\ngraceful_timeout = 2\nkeepalive = 1\n"
            "def when_ready(server):\n"
            f"    Path({str(self.portfile)!r}).write_text(json.dumps(server.LISTENERS[0].getsockname()[1]))\n"
            "def post_worker_init(worker):\n"
            f"    bindings = {bindings!r}\n"
            "    modules = {}\n"
            "    for name, (path, digest) in bindings.items():\n"
            "        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:\n"
            "            raise ValueError('sealed hook source changed')\n"
            "        spec = importlib.util.spec_from_file_location('sealed_' + name, path)\n"
            "        module = importlib.util.module_from_spec(spec)\n"
            "        spec.loader.exec_module(module)\n"
            "        modules[name] = module\n"
            f"    modules['helper'].install(worker, guard=modules['guard'], state_dir={str(self.state)!r}, generation={GEN!r}, manifest_sha256={digest!r})\n")
        self.config.chmod(0o600)

    def argv(self, *args, timeout=3):
        return [sys.executable, str(GUARD), '--state-dir', str(self.state),
                '--timeout', str(timeout), *args]

    def run(self, *args):
        argv = self.argv(*args)
        result = subprocess.run(argv, capture_output=True, text=True, timeout=8)
        self.commands.append({'argv': argv, 'returncode': result.returncode,
                              'stdout': result.stdout, 'stderr': result.stderr})
        self.h.check(result.returncode == 0, 'guard command failed: ' + repr(self.commands[-1]))
        return result

    def spawn(self, argv, name):
        with (self.root / (name + '.log')).open('w') as log:
            p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=log,
                                 stderr=subprocess.STDOUT)
        self.processes.append(p)
        return p

    def stop(self, p):
        # Signal only this exact Popen master. Gunicorn gracefully owns its workers.
        if p.poll() is None:
            p.terminate()
        try:
            p.wait(timeout=6)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=3)
            raise RuntimeError('own master failed bounded graceful shutdown; inspect log')

    def state_value(self):
        return json.loads((self.state / 'state.json').read_text())

    def candidate(self, name):
        self.portfile.unlink(missing_ok=True)
        grant = self.root / (name + '-authorization.json')
        self.h.save(grant, {'generation': self.manifest['generation'],
                            'closure': self.state_value()['closure'],
                            'route': 'server', 'authorized': True})
        p = self.spawn(self.argv('candidate', '--generation', self.manifest['generation'], '--route', 'server',
                                 '--authorization', str(grant)), name)
        self.h.wait_for(lambda: self.portfile.exists() or p.poll() is not None,
                        'candidate listener', timeout=5)
        self.h.check(p.poll() is None, 'candidate died: inspect ' + name + '.log')
        self.port = json.loads(self.portfile.read_text())
        def ready():
            try:
                return self.request('GET', '/health')[0] == 200
            except (OSError, http.client.HTTPException):
                return False
        self.h.wait_for(ready, 'candidate health', timeout=5)
        return p

    def request(self, method, path, payload=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=2)
        try:
            conn.request(method, path, body=payload,
                         headers={'Authorization': 'Bearer synthetic-fixture-only'})
            response = conn.getresponse()
            return response.status, response.read(1024)
        finally:
            conn.close()

    def snapshot(self):
        with sqlite3.connect(self.db) as db:
            return (db.execute('SELECT value FROM heartbeat ORDER BY value').fetchall(),
                    db.execute('SELECT value FROM counter').fetchall())

    def reopen(self, name):
        receipt = self.root / (name + '-receipt.json')
        record = json.loads((self.state / 'candidate.json').read_text())
        self.h.save(receipt, {'generation': self.manifest['generation'],
                             'closure': self.state_value()['closure'],
                             'source_home': str(self.home), 'hashes': self.manifest['hashes'],
                             'schema': self.manifest.get('target_schema', 19),
                             'accepted': True, 'process': record['process']})
        self.run('reopen', '--generation', self.manifest['generation'], '--receipt', str(receipt))

    def closed_oracle(self):
        before = self.snapshot()
        self.h.check(self.request('POST', '/heartbeat', 'closed-unique')[0] == 503,
                     'CLOSED heartbeat must be explicitly refused')
        self.h.check(self.request('GET', '/representative')[0] == 503,
                     'CLOSED GET side effect was admitted')
        self.h.check(self.request('GET', '/health')[0] == 200, 'CLOSED health failed')
        for method, path in [('HEAD', '/health'), ('GET', '/health?write=1')]:
            self.h.check(self.request(method, path)[0] == 503, 'health exception too broad')
        self.h.check(self.snapshot() == before, 'CLOSED mutated protected DB')


def lifecycle(t, guard, admission):
    """Direct-module real flock checks against a copy of an actually receipted state.

    Fault injection touches only this private unit copy; live server state always
    transitions through guard CLI. No synthetic OPEN is fabricated.
    """
    import fcntl
    root = t.root / 'unit-state'
    shutil.copytree(t.state, root)
    root.chmod(0o700)
    digest = hashlib.sha256((root / 'manifest.json').read_bytes()).hexdigest()
    baseline = (root / 'state.json').read_bytes()
    calls = []
    def app(env, start):
        calls.append(env)
        start('200 OK', [])
        return [b'ok']
    def wrap(fn=app):
        return admission.Admission(fn, guard=guard, state_dir=root, generation=GEN,
                                   manifest_sha256=digest, timeout=0.02)
    env = {'REQUEST_METHOD': 'POST', 'PATH_INFO': '/heartbeat', 'QUERY_STRING': ''}
    def invoke(w):
        statuses = []
        response = w(env, lambda status, headers: statuses.append(status))
        return response, statuses
    def locked(expected):
        fd = guard.lock_file(root, 'admission.lock')
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                held = False
            except BlockingIOError:
                held = True
            t.h.check(held == expected, 'independent lease oracle mismatch')
        finally:
            os.close(fd)
    w = wrap()
    a, _ = invoke(w)
    b, _ = invoke(w)
    t.h.check(a.fd != b.fd, 'responses share fd')
    locked(True)
    a.close()
    locked(True)
    b.close()
    locked(False)
    t.cases.append('independent concurrent response file descriptions')

    events = []
    def generator():
        try:
            yield b'body'
        finally:
            locked(True)
            events.append('finally')
    response, _ = invoke(wrap(lambda e, s: generator()))
    next(response)
    response.close()
    t.h.check(events == ['finally'], 'generator finally missing')
    locked(False)
    t.cases.append('lease held through generator finally and response close')

    for label in ('application', 'iteration', 'close'):
        class Broken:
            def __iter__(self):
                return self
            def __next__(self):
                raise RuntimeError('synthetic iteration failure')
            def close(self):
                locked(True)
                if label == 'close':
                    raise RuntimeError('synthetic close failure')
        def broken_app(e, s):
            if label == 'application':
                raise RuntimeError('synthetic application failure')
            return Broken()
        try:
            response, _ = invoke(wrap(broken_app))
            if label == 'iteration':
                next(response)
            else:
                response.close()
        except RuntimeError:
            pass
        else:
            raise RuntimeError('expected ' + label + ' failure')
        locked(False)
        t.cases.append(label + ' exception releases lease')

    for fault in ('mode', 'hardlink'):
        w = wrap()
        path = root / 'admission.lock'
        extra = root / 'extra-lock-link'
        before_calls = len(calls)
        before_fds = len(os.listdir('/proc/self/fd'))
        try:
            if fault == 'mode':
                path.chmod(0o644)
            else:
                os.link(path, extra)
            for _ in range(32):
                response, statuses = invoke(w)
                t.h.check(statuses == ['503 Service Unavailable'] and
                          len(calls) == before_calls, 'unsafe lock reached app')
                t.h.check(b'closed' in b''.join(response), 'missing lock refusal')
            t.h.check(len(os.listdir('/proc/self/fd')) == before_fds,
                      'unsafe lock validation leaks descriptors: ' + fault)
        finally:
            path.chmod(0o600)
            if extra.exists():
                extra.unlink()
        response, statuses = invoke(w)
        t.h.check(statuses == ['200 OK'] and b''.join(response) == b'ok',
                  'repaired lock control did not act')
        locked(False)
        t.cases.append('unsafe lock ' + fault + ' refuses without descriptor leak')

    for fault in ('missing', 'malformed', 'generation', 'closure'):
        w = wrap()
        path = root / 'state.json'
        if fault == 'missing':
            path.unlink()
        elif fault == 'malformed':
            path.write_text('{')
        else:
            value = json.loads(baseline)
            value[fault] = ('2' * 40 if fault == 'generation' else '2' * 32)
            t.h.save(path, value)
        before = len(calls)
        try:
            response, statuses = invoke(w)
            t.h.check(statuses == ['503 Service Unavailable'] and len(calls) == before,
                      fault + ' did not fail before app')
            t.h.check(b'closed' in b''.join(response), 'missing refusal body')
            locked(False)
        finally:
            path.write_bytes(baseline)
            path.chmod(0o600)
        t.cases.append(fault + ' state fails closed before app')

    worker = SimpleNamespace(wsgi=app)
    binding = dict(guard=guard, state_dir=root, generation=GEN, manifest_sha256=digest)
    admission.install(worker, **binding)
    try:
        admission.install(worker, **binding)
    except ValueError:
        pass
    else:
        raise RuntimeError('duplicate install accepted')
    t.cases.append('duplicate install rejected')


def end_to_end(t, guard, admission):
    primary = t.candidate('primary')
    t.closed_oracle()
    t.reopen('primary')
    t.h.check(t.request('POST', '/heartbeat', 'open-control-unique')[0] == 200,
              'OPEN control failed')
    t.h.check(('open-control-unique',) in t.snapshot()[0], 'OPEN did not actually write')
    t.h.check(t.request('GET', '/representative') == (200, b'1'), 'GET write control failed')
    lifecycle(t, guard, admission)

    # Hold a real admission lease while supported close publishes a fresh closure.
    digest = hashlib.sha256((t.state / 'manifest.json').read_bytes()).hexdigest()
    direct = admission.Admission(lambda e, s: [b'held'], guard=guard, state_dir=t.state,
                                 generation=GEN, manifest_sha256=digest)
    held = direct({'REQUEST_METHOD': 'GET', 'PATH_INFO': '/held'}, lambda s, h: None)
    close = t.spawn(t.argv('close', timeout=7), 'drain')
    t.h.wait_for(lambda: t.state_value()['admission'] == 'CLOSED', 'durable CLOSED')
    t.h.check(t.request('POST', '/heartbeat', 'after-close-unique')[0] == 503,
              'new request admitted after close')
    t.h.check(close.poll() is None, 'drain ignored response lease')
    held.close()
    time.sleep(0.1)
    t.h.check(close.poll() is None, 'drain ignored candidate lifetime')
    t.stop(primary)
    t.h.check(close.wait(timeout=8) == 0, 'close did not drain own candidate')
    t.cases.append('CLOSED publishes before response and candidate lifetime drain')

    # Forced pre-accept validation failure: receipt must not be created/consumed.
    rejected = t.candidate('rejected-primary')
    t.closed_oracle()
    flag = t.root / 'force-preaccept-failure.json'
    t.h.save(flag, {'force_failure': True})
    accepted = not json.loads(flag.read_text())['force_failure']
    t.h.check(not accepted and t.state_value()['admission'] == 'CLOSED',
              'forced preaccept failure opened admission')
    before = t.snapshot()
    close = t.spawn(t.argv('close', timeout=7), 'rejected-drain')
    old_closure = json.loads((t.state / 'candidate.json').read_text())['closure']
    t.h.wait_for(lambda: t.state_value()['closure'] != old_closure, 'rejected CLOSED publication')
    t.stop(rejected)
    t.h.check(close.wait(timeout=8) == 0, 'rejected candidate did not drain')
    fallback = t.candidate('fallback')
    t.closed_oracle()
    t.h.check(t.snapshot() == before, 'fallback startup changed same DB')
    t.reopen('fallback')
    t.h.check(t.request('POST', '/heartbeat', 'fallback-open-unique')[0] == 200,
              'fallback reopen heartbeat failed')
    t.h.check(('fallback-open-unique',) in t.snapshot()[0], 'fallback did not actually write')
    t.stop(fallback)
    t.run('close')
    t.cases.append('real Gunicorn CLOSED/receipt OPEN, forced rejection, same-DB fallback')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    if sys.platform != 'linux' or os.name != 'posix':
        parser.error('UNSUPPORTED: Linux POSIX flock and candidate identity required')
    out = Path(args.out)
    if not out.is_absolute() or str(out) != str(out.resolve()):
        parser.error('--out must be canonical absolute, without symlinks')
    out.mkdir(mode=0o700)  # Exclusive owned fixture tree; never adopt an existing directory.
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    sys.dont_write_bytecode = True
    t = None
    report = {'passed': False, 'cases': [], 'error': None}
    try:
        import gunicorn
        if gunicorn.__version__ != '20.1.0':
            raise RuntimeError('requires Gunicorn exactly 20.1.0')
        h = helpers()
        guard = load(GUARD, 'actual_guard')
        admission = load(HELPER, 'actual_admission')
        t = Harness(out, h)
        end_to_end(t, guard, admission)
        report['passed'] = True
    except BaseException as exc:
        report['error'] = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        if t is not None:
            errors = []
            for p in reversed(t.processes):
                try:
                    t.stop(p)
                except Exception as exc:
                    errors.append(str(exc))
            report.update(cases=t.cases, commands=t.commands, cleanup_errors=errors)
            if errors:
                report['passed'] = False
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    if not report['passed']:
        raise RuntimeError('cleanup failed; inspect report.json')
    print('PASS: ' + str(len(t.cases)) + ' focused checks; evidence: ' + str(out))


if __name__ == '__main__':
    main()
