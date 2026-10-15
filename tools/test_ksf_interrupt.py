#!/usr/bin/env python3
"""Offline P717 process-death controls; never point this at an existing home.

    python tools/test_ksf_interrupt.py --out <owned-task-root>/artifacts/cuts

Each arm creates a fresh synthetic database, pauses our subprocess at an acted
SQLite/profile boundary, kills only that subprocess, then recovers with a fresh
interpreter and no network. This is NOT a storage/power-loss or live-fleet test.
"""
import argparse
import json
import os
from pathlib import Path
import queue
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLAYER = '76561197960265974'  # synthetic STEAM_0:0:123 fixture identity
CUTS = ('pb-update', 'marker-insert', 'pb-commit', 'cursor-update', 'ack-commit')
ARGS = None


def snapshot(home):
    with sqlite3.connect(str(home / 'test.db')) as db:
        return {
            'runs': db.execute('SELECT map,track,leg,style,player,millis,submitted,runid,replay_id,tier '
                               'FROM runs ORDER BY map,player').fetchall(),
            'markers': db.execute('SELECT map,track,leg,style,player,seconds,millis,submitted '
                                  'FROM ksf_unbound ORDER BY map,player').fetchall(),
            'controls': db.execute("SELECT * FROM runs WHERE map!='surf_cut' ORDER BY map,player").fetchall(),
            'profile': db.execute('SELECT mode,cursor,state,pages FROM ksfprofiles').fetchone(),
            'integrity': db.execute('PRAGMA integrity_check').fetchone()[0],
        }


def worker(home, action, cut):
    # The audit control uses separately owned sentinels, never owner files.
    forbidden = {os.path.normcase(os.path.abspath(p))
                 for p in json.loads(os.environ.pop('KSF_INTERRUPT_FORBIDDEN_PATHS', '[]'))}
    attempts = []
    def audit(event, args):
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            path = os.path.normcase(os.path.abspath(os.fsdecode(args[0])))
            if path in forbidden:
                attempts.append(path)
                raise PermissionError('synthetic must-not-read sentinel')
    sys.addaudithook(audit)
    for path in forbidden:
        try:
            with open(path, 'rb'):
                pass
        except PermissionError:
            pass
        else:
            raise AssertionError('file-open audit control did not act')
    assert len(attempts) == len(forbidden)
    attempts.clear()
    # Import migrates the DB and reads configuration/game code. Do not inherit
    # ANY real app setting; redirect its read-only inputs as well as outputs.
    for name in tuple(os.environ):
        if name.startswith('SURFD_'):
            del os.environ[name]
    code = home / 'synthetic-code.fixture'
    code.write_bytes(b'not real game code: offline interruption fixture\n')
    os.environ.update(SURFD_HOME=str(home), SURFD_DB=str(home / 'test.db'),
                      SURFD_ENV=str(home / 'synthetic.env'),
                      SURFD_GAME=str(home / 'game'), SURFD_GAME_CODE=str(code),
                      SURFD_RUNS=str(home / 'runs'), SURFD_EVIDENCE=str(home / 'evidence'),
                      SURFD_KEEP=str(home / 'keep'), SURFD_MOMENTUM=str(home / 'momentum'),
                      SURFD_KSF_RUNS=str(home / 'ksfruns'))
    sys.path.insert(0, str(ROOT / 'surfd'))
    import surfd as S
    import ksfimport as K
    import ksfprofile as P
    assert not attempts, 'import attempted to open inherited configuration/code sentinels'
    assert S.ENV_PATH == str(home / 'synthetic.env')
    assert S.setting('SURFD_TEST_MARKER') == 'ksf-interrupt-only'
    assert S.setting('SURFD_GAME_CODE') == str(code)
    assert S.KSF_DIR == str(home / 'ksfruns')
    if forbidden:
        print('ISOLATION ' + json.dumps({'blocked_control_opens': len(forbidden),
              'import_sentinel_opens': len(attempts), 'env': S.ENV_PATH,
              'marker': S.setting('SURFD_TEST_MARKER')}), flush=True)

    def row(mp='surf_cut', seconds=.0601, rid=111):
        return K.rec_row(mp, 0, 0, dict(steamID=PLAYER, name='synthetic',
                         time=seconds, date=1700000000, record_id=rid))

    def pause(phase, db=None):
        if phase != cut:
            return 0
        witness = {'cut': phase}
        if db is not None:
            witness['pb'] = tuple(db.execute("SELECT millis,runid FROM runs WHERE map='surf_cut'").fetchone())
            witness['markers'] = db.execute('SELECT count(*) FROM ksf_unbound').fetchone()[0]
        print(json.dumps(witness), flush=True)
        # Parent owns stdin. Do not poll, sleep, or signal an external process.
        if sys.stdin.buffer.read(1) != b'!':
            raise RuntimeError('cut worker was resumed without explicit release')
        return 0

    if action == 'seed':
        K.write_rows([row(), row('surf_control', .2, 222), row('surf_native', .3, 444)])
        with S.connect() as db:
            db.execute("UPDATE runs SET tier='community',player='synthetic-native',node='synthetic-native',runid='native-control' "
                       "WHERE map='surf_native'")
            db.commit()
            assert P.enqueue(db, PLAYER, 1000)['state'] == 'queued'
        return

    real_connect = S.connect

    class SplitConnection:
        """Intentional test-only broken transaction; prove the oracle can fail."""
        def __init__(self, db):
            self.db = db

        def execute(self, sql, *args):
            result = self.db.execute(sql, *args)
            if sql.startswith('INSERT INTO runs '):
                self.db.commit()
                pause('split-commit', self.db)
            return result

        def __enter__(self):
            self.db.__enter__()
            return self

        def __exit__(self, *args):
            return self.db.__exit__(*args)

        def close(self):
            self.db.close()

    def connect():
        db = real_connect()
        db.create_function('cut_here', 1, lambda phase: pause(phase, db))
        return SplitConnection(db) if cut == 'split-commit' else db

    S.connect = connect
    with real_connect() as db:
        db.executescript("""
            CREATE TRIGGER IF NOT EXISTS cut_pb AFTER UPDATE ON runs
            WHEN NEW.map='surf_cut'
            BEGIN SELECT cut_here('pb-update'); END;
            CREATE TRIGGER IF NOT EXISTS cut_marker AFTER INSERT ON ksf_unbound
            WHEN NEW.map='surf_cut'
            BEGIN SELECT cut_here('marker-insert'); END;
            CREATE TRIGGER IF NOT EXISTS cut_cursor AFTER UPDATE ON ksfprofiles
            BEGIN SELECT cut_here('cursor-update'); END;
        """)
    real_write = K.write_rows

    def write(rows):
        result = real_write(rows)
        pause('pb-commit')
        return result

    K.write_rows = write
    cache = str(home / 'cache')
    calls = []

    def fetch(url):
        if action == 'recover':
            raise AssertionError('recovery must use the durable source page, not HTTP')
        calls.append(url)
        return json.dumps(dict(records=[dict(mapName='surf_cut', time=.0599,
                               date=1700000000, record_id=None, stage_id=None, zone_id=None)],
                               pagination=dict(offset=0, limit=5), total=None))

    K.fetch = fetch
    before = snapshot(home)
    if before['profile'][3] == 0:
        assert P.step(K, cache, K.Pacer(0, 1), {'surf_cut'}, 1001, 1) == 1
    else:
        assert action == 'recover' and before['profile'] == (1, 1, 'partial', 1)
    if action != 'recover':
        assert len(calls) == 1
        pause('ack-commit')
    else:
        assert calls == []
    after = snapshot(home)
    assert after['profile'] == (1, 1, 'partial', 1), after
    assert len(after['markers']) == 1 and after['markers'][0][5:] == (.0599, 60, 1700000000), after
    pb = next(r for r in after['runs'] if r[0] == 'surf_cut')
    assert pb[5:9] == (60, 1700000000, '', 0), pb
    # A stale same-millisecond cache and a slower newly fetched identity cannot
    # erase authority. A genuinely matching fresh identified record can bind.
    stale = row()
    stale['binding'] = 'cache'
    assert real_write([stale]) == 0
    assert real_write([row()]) == 0
    assert real_write([row(seconds=.0599, rid=333)]) == 1
    with real_connect() as db:
        assert db.execute('SELECT count(*) FROM ksf_unbound').fetchone()[0] == 0
    # Save the pre-binding state, so every parent arm shares the same oracle.
    print('RESULT ' + json.dumps(after), flush=True)


def command(home, action, cut='none'):
    return [sys.executable, str(Path(__file__).resolve()), '--worker', action,
            '--home', str(home), '--cut', cut]


class InterruptTests(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix=self._testMethodName + '-', dir=str(ARGS.out)))

    def run_worker(self, action, cut='none', extra_env=None):
        if action == 'seed':
            (self.home / 'synthetic.env').write_text('SURFD_TEST_MARKER=ksf-interrupt-only\n', encoding='utf-8')
        env = dict(os.environ, **(extra_env or {}))
        run = subprocess.run(command(self.home, action, cut), text=True, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=45)
        (self.home / (action + '.log')).write_text(run.stdout, encoding='utf-8')
        self.assertEqual(run.returncode, 0, run.stdout)
        results = [json.loads(x[7:]) for x in run.stdout.splitlines() if x.startswith('RESULT ')]
        return results[-1] if results else None

    def kill_at(self, cut):
        proc = subprocess.Popen(command(self.home, 'step', cut), stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        messages = queue.Queue()
        prefix = []

        def reader():
            for line in proc.stdout:
                prefix.append(line)
                if line.startswith('{"cut":'):
                    messages.put(json.loads(line))
                    return
            messages.put(None)

        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        try:
            witness = messages.get(timeout=45)
            self.assertIsNotNone(witness, ''.join(prefix))
            self.assertEqual(witness['cut'], cut)
            proc.kill()  # This exact Popen is our blocked synthetic worker only.
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            tail, _ = proc.communicate(timeout=15)
            self.assertNotEqual(proc.returncode, 0)
            (self.home / 'killed.log').write_text(''.join(prefix) + tail, encoding='utf-8')
            (self.home / 'witness.json').write_text(json.dumps(witness, indent=2) + '\n', encoding='utf-8')
            return witness
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=15)
            for stream in (proc.stdin, proc.stdout):
                if stream and not stream.closed:
                    stream.close()

    def controls_unchanged(self, before, after):
        self.assertEqual(before['controls'], after['controls'])
        self.assertEqual(after['integrity'], 'ok')

    def test_inherited_configuration_is_not_opened(self):
        outside = Path(tempfile.mkdtemp(prefix='sentinels-', dir=str(ARGS.out)))
        envfile, code = outside / 'foreign.env', outside / 'foreign.dat'
        envfile.write_text('SURFD_TEST_MARKER=must-not-use\n', encoding='utf-8')
        code.write_bytes(b'must-not-read')
        self.run_worker('seed', extra_env={
            'SURFD_ENV': str(envfile), 'SURFD_GAME_CODE': str(code),
            'SURFD_KSF_RUNS': str(outside / 'foreign-runs'),
            'KSF_INTERRUPT_FORBIDDEN_PATHS': json.dumps([str(envfile), str(code)]),
        })
        lines = (self.home / 'seed.log').read_text(encoding='utf-8').splitlines()
        proof = json.loads(next(x[10:] for x in lines if x.startswith('ISOLATION ')))
        self.assertEqual(proof, {'blocked_control_opens': 2, 'import_sentinel_opens': 0,
                                'env': str(self.home / 'synthetic.env'),
                                'marker': 'ksf-interrupt-only'})

    def test_uninterrupted_positive(self):
        self.run_worker('seed')
        before = snapshot(self.home)
        result = self.run_worker('step')
        self.assertEqual(result['profile'], [1, 1, 'partial', 1])
        self.controls_unchanged(before, snapshot(self.home))

    def test_process_death_at_each_transaction_boundary(self):
        original = self.home
        for cut in CUTS:
            with self.subTest(cut=cut):
                self.home = original / cut
                self.home.mkdir()
                self.run_worker('seed')
                before = snapshot(self.home)
                witness = self.kill_at(cut)
                after = snapshot(self.home)
                self.controls_unchanged(before, after)
                if cut in ('pb-update', 'marker-insert'):
                    self.assertEqual(witness['pb'], [60, ''])
                    self.assertEqual(witness['markers'], int(cut == 'marker-insert'))
                    self.assertEqual(after, before)
                else:
                    self.assertEqual(len(after['markers']), 1)
                    self.assertEqual(after['markers'][0][5:], (.0599, 60, 1700000000))
                    pb = next(r for r in after['runs'] if r[0] == 'surf_cut')
                    self.assertEqual(pb[7:9], ('', 0))
                    self.assertEqual(after['profile'], (1, 1, 'partial', 1) if cut == 'ack-commit'
                                     else (0, 1, 'queued', 0))
                self.assertEqual(len(list((self.home / 'cache' / 'profiles').glob('*/*.json'))), 1)
                recovered = self.run_worker('recover')
                self.assertEqual(recovered['profile'], [1, 1, 'partial', 1])
                self.controls_unchanged(before, snapshot(self.home))
        self.home = original

    def test_intentional_split_transaction_is_detected(self):
        self.run_worker('seed')
        before = snapshot(self.home)
        witness = self.kill_at('split-commit')
        self.assertEqual(witness['pb'], [60, ''])
        self.assertEqual(witness['markers'], 0)
        broken = snapshot(self.home)
        self.assertNotEqual(broken['runs'], before['runs'])
        self.assertEqual(broken['markers'], [])
        self.assertEqual(broken['profile'], before['profile'])
        self.controls_unchanged(before, broken)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--worker', choices=('seed', 'step', 'recover'), help=argparse.SUPPRESS)
    parser.add_argument('--home', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--cut', choices=(*CUTS, 'none', 'split-commit'), default='none', help=argparse.SUPPRESS)
    ARGS, rest = parser.parse_known_args()
    if not __debug__:
        parser.error('run without Python optimization: worker assertions are controls')
    if ARGS.worker:
        if not ARGS.home or not (ARGS.home / 'synthetic.env').is_file():
            parser.error('worker requires a parent-created synthetic home')
        worker(ARGS.home, ARGS.worker, ARGS.cut)
    else:
        if not ARGS.out or not any((p / 'OWNER.md').is_file() for p in (ARGS.out, *ARGS.out.parents)):
            parser.error('--out requires an owned task root with OWNER.md')
        ARGS.out.mkdir(parents=True, exist_ok=True)
        # setUp creates fresh homes; never reuse a caller's existing database.
        unittest.main(argv=[sys.argv[0], *rest], verbosity=2)
