#!/usr/bin/env python3
"""Falsifiers for conbridge.py's guards that need no engine. python tools/test_conbridge.py

Every child is an idle python, and STATE and the gamedir are a scratch directory, so the real
bridge state and the real install are never touched. Takes about 25 s: one case waits out
the 20 s a stuck engine is given to quit. The live half (send, wait, info, shot against a
running game) has no arm here; it was driven by hand on surf_kitsune.
"""
import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

script = str(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).with_name('conbridge.py'))


def load(path, state):
    spec = importlib.util.spec_from_file_location('conbridge', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.STATE = state
    return mod


scratch = Path(tempfile.mkdtemp(prefix='cbtest-'))
(scratch / 'state').mkdir()
cb = load(script, scratch / 'state')
fails = []
IDLE = [sys.executable, '-c', 'import time; time.sleep(300)']


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail else ''))
    if not ok:
        fails.append(name)


def ns(**kw):
    base = dict(name='t', root=str(scratch / 'root'), gamedir='g', window='free', resume=False,
                idle=0, boot_timeout=5, map='m', size='640x480')
    base.update(kw)
    return argparse.Namespace(**base)


def cli(path, *args):
    # cp1252 is what a piped stdout gets on a stock Windows Python; forced, so the encoding
    # case exists whatever this shell exports.
    code = ('import importlib.util,sys;from pathlib import Path;'
            f's=importlib.util.spec_from_file_location("conbridge",r"{path}");'
            'm=importlib.util.module_from_spec(s);s.loader.exec_module(m);'
            f'm.STATE=Path(r"{cb.STATE}");sys.argv=["conbridge.py"]+{list(args)!r};sys.exit(m.main())')
    env = {**os.environ, 'PYTHONIOENCODING': 'cp1252', 'PYTHONUTF8': '0'}
    p = subprocess.run([sys.executable, '-c', code], capture_output=True, env=env)
    return p.returncode, (p.stdout + p.stderr).decode('cp1252', 'replace')


game = scratch / 'root' / 'g'
(game / 'data' / 'resume').mkdir(parents=True)
(game / 'logs').mkdir()
(game / 'one.cfg').write_text('cfg_save_auto "1"\n')

# -- an engine that never reads its stdin: the pipe takes ~4 KB, then a write blocks ------
eng = cb.Engine('cl', IDLE, scratch, game / 'logs' / 'x.log', True)
t0, sent, err = time.monotonic(), 0, ''
try:
    for _ in range(400):
        eng.send('x' * 200)
        sent += 1
        time.sleep(0.002)
except ValueError as e:
    err = str(e)
check('send to a non-reading engine refuses instead of blocking',
      'not reading its console' in err and time.monotonic() - t0 < 10,
      f'{sent} lines accepted in {time.monotonic() - t0:.1f} s')
sess = cb.Session(ns())
sess.snapshot()
sess.engines['cl'] = eng
t0 = time.monotonic()
rep = sess.shutdown(False)
check('shutdown of that engine terminates it and returns',
      'TERMINATED' in rep['ends']['cl'] and not eng.alive() and time.monotonic() - t0 < 40,
      f'{time.monotonic() - t0:.1f} s; {rep["ends"]["cl"]}')
check('and that stop is not a clean exit', cb.troubled(rep))
check('unchanged config: the copy is removed', not sess.bak.exists() and rep['cfg_changed'] == [])

# -- the config changes during the session ----------------------------------------------
sess = cb.Session(ns(name='u'))
sess.snapshot()
(game / 'one.cfg').write_text('cfg_save_auto "0"\nvid_width "640"\n')
rep = sess.shutdown(False)
copy = Path(rep['cfg_backup']) / 'one.cfg' if rep['cfg_backup'] else None
check('a changed config is reported', rep['cfg_changed'] == [str(game / 'one.cfg')], str(rep['cfg_changed']))
check('the bytes from the start are kept', bool(copy) and copy.read_text() == 'cfg_save_auto "1"\n')
check('and that stop is not a clean exit', cb.troubled(rep))
check('kept() lists the copy for the next start', [p.name for p in cb.kept('u')] == [sess.bak.name])
check('kept() does not match another name', cb.kept('t') == [] and cb.kept('u_2') == [])

# -- never snapshotted must not read as "everything changed", nor as "unchanged" -----------
rep = cb.Session(ns(name='v')).shutdown(False)
check('no snapshot: no verdict, and a note saying so',
      rep['cfg_changed'] == [] and any('never snapshotted' in n for n in rep['notes']))

# -- a map on the client is a listen server without the run_resume guard -------------------
live = cb.Engine('cl', IDLE, scratch, game / 'logs' / 'y.log', True)
sess = cb.Session(ns(name='w'))
sess.engines['cl'] = live
for line, refused in (('map surf_dune', True), ('echo a; map x', True), ('changelevel x', True),
                      ('devmap x', True), ('cmd mapvote x', False), ('echo map', False),
                      ('mapname', False), ('+forward; waitms 200; -forward', False)):
    try:
        sess.push(live, line)
        got = False
    except ValueError as e:
        got = 'listen server' in str(e)
    check(f'client line {line!r} refused={refused}', got == refused)
sess = cb.Session(ns(name='w2', resume=True))
sess.engines['cl'] = live
try:
    sess.push(live, 'map surf_dune')
    check('--resume allows it', True)
except ValueError as e:
    check('--resume allows it', False, str(e))
live.proc.terminate()
live.proc.wait(10)
rc, out = cli(script, 'start')
check('start with a server and no --map is refused', rc == 2 and 'needs --map' in out, out.strip()[-90:])

# -- stop must not clear a live daemon's state -------------------------------------------
holder = subprocess.Popen(IDLE)
cb.save_state('boot', {'name': 'boot', 'pid': holder.pid, 'address': 'x', 'authkey': '00',
                       'phase': 'booting', 'engines': {}})
rc, out = cli(script, '--name', 'boot', 'stop')
check('stop on a booting session with a live daemon keeps the state',
      rc == 2 and cb.state_path('boot').exists() and 'state stays' in out)
rc, out = cli(script, '--name', 'boot', 'start', '--map', 'm')
check('start refuses beside it', rc == 2 and 'already booting' in out)
holder.terminate()
holder.wait(10)
rc, out = cli(script, '--name', 'boot', 'stop')
check('with the daemon gone, stop clears it',
      rc == 2 and not cb.state_path('boot').exists() and 'daemon is gone' in out)

# -- finish() removes only its own state ---------------------------------------------------
cb.save_state('other', {'name': 'other', 'pid': 1, 'address': 'x', 'authkey': '00',
                        'phase': 'ready', 'engines': {}})
subprocess.run([sys.executable, '-c',
                'import importlib.util;from pathlib import Path;'
                f's=importlib.util.spec_from_file_location("conbridge",r"{script}");'
                'm=importlib.util.module_from_spec(s);s.loader.exec_module(m);'
                f'm.STATE=Path(r"{cb.STATE}");m.finish("other",0)'])
check("finish() leaves another daemon's state", cb.state_path('other').exists())

# -- text the console codec cannot encode, with its control --------------------------------
cb.save_state('gone', {'name': 'gone', 'pid': 1, 'address': 'x', 'authkey': '00',
                       'phase': 'failed', 'reason': 'snowman ☃ in a log line', 'engines': {}})
rc, out = cli(script, '--name', 'gone', 'status')
check('an unencodable message exits 2, not a traceback',
      rc == 2 and 'Traceback' not in out and 'snowman' in out)
src = Path(script).read_text(encoding='utf-8')
needle = "        stream.reconfigure(errors='backslashreplace')\n"
assert src.count(needle) == 1, 'the control cannot find the line it removes'
mutant = scratch / 'conbridge_mutant.py'
mutant.write_text(src.replace(needle, '        pass\n'), encoding='utf-8')
rc, out = cli(mutant, '--name', 'gone', 'status')
check('CONTROL, that line removed: UnicodeEncodeError and exit 1', rc == 1 and 'UnicodeEncodeError' in out)

shutil.rmtree(scratch)
print(f'\n{len(fails)} failed', fails or '')
sys.exit(1 if fails else 0)
