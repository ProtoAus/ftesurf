#!/usr/bin/env python3
"""Falsifiers for conbridge.py's guards that need no engine. python tools/test_conbridge.py

Every child is an idle python, and STATE and the gamedir are a scratch directory, so the real
bridge state and the real install are never touched. Takes about 30 s: one case waits out
the 20 s a stuck engine is given to quit. What only a running game can show -- that the
engine takes the session manifest, that run_resume 0 survives the QC registering it, send,
wait, info, shot -- has no arm here; it was driven by hand on surf_kitsune.
"""
import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

script = str(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).with_name('conbridge.py'))


scratch = Path(tempfile.mkdtemp(prefix='cbtest-'))
(scratch / 'state').mkdir()
# Inherited by every child, the detached daemon included: a first cut patched STATE in this
# process only, and the daemon `start` spawned wrote its state file into the real directory.
os.environ['CONBRIDGE_STATE'] = str(scratch / 'state')
spec = importlib.util.spec_from_file_location('conbridge', script)
cb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb)
assert cb.STATE == scratch / 'state'
fails = []
IDLE = ['-c', 'import time; time.sleep(300)']
OWNER = 'cfg_save_auto "1"\n'


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  [{detail}]' if detail else ''))
    if not ok:
        fails.append(name)


def ns(**kw):
    base = dict(name='t', root=str(scratch / 'root'), gamedir='g', window='free', resume=False,
                idle=0, boot_timeout=5, map='m', size='640x480')
    base.update(kw)
    return argparse.Namespace(**base)


def idle(log):
    # argv[0] is not the executable, as in a real session.
    return cb.Engine('cl', sys.executable, 'python', IDLE, scratch, game / 'logs' / log, True)


def cli(path, *args):
    # cp1252 is what a piped stdout gets on a stock Windows Python; forced, so the encoding
    # case exists whatever this shell exports.
    env = {**os.environ, 'PYTHONIOENCODING': 'cp1252', 'PYTHONUTF8': '0'}
    p = subprocess.run([sys.executable, str(path), *args], capture_output=True, env=env)
    return p.returncode, (p.stdout + p.stderr).decode('cp1252', 'replace')


root = scratch / 'root'
game = root / 'g'
(game / 'data' / 'resume').mkdir(parents=True)
(game / 'logs').mkdir()
(game / 'one.cfg').write_text(OWNER)
(root / 'default.fmf').write_text('FTEMANIFEST 1\nGAME "X"\nMAINCONFIG one\nset sv_mintic 0.015\n')

# -- an engine that never reads its stdin: the pipe takes ~4 KB, then a write blocks ------
eng = idle('x.log')
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
sess.plumb()
check('the session manifest is the install\'s with one line changed',
      sess.fmf.read_text() == f'FTEMANIFEST 1\nGAME "X"\nMAINCONFIG {sess.tag}\nset sv_mintic 0.015\n')
check('the session config starts as the owner\'s', sess.cfg.read_text() == OWNER)
sess.engines['cl'] = eng
t0 = time.monotonic()
rep = sess.shutdown(False)
check('shutdown of that engine terminates it and returns',
      'TERMINATED' in rep['ends']['cl'] and not eng.alive() and time.monotonic() - t0 < 40,
      f'{time.monotonic() - t0:.1f} s; {rep["ends"]["cl"]}')
check('and that stop is not a clean exit', cb.troubled(rep))
check('shutdown removes the session manifest and config', not sess.fmf.exists() and not sess.cfg.exists())
check('unchanged config: the copy is removed', not sess.bak.exists() and rep['cfg_changed'] == [])

# -- the owner's config changes during the session: whose write was it? -------------------
sess = cb.Session(ns(name='u'))
sess.snapshot()
sess.plumb()
check('the session config is not counted as a change to the owner\'s', sess.cfg_changed() == [])
(game / 'one.cfg').write_text('cfg_save_auto "1"\nvolume "0.3"\n')
rep = sess.shutdown(False)
check('a change without the session marker is reported, and is not this session\'s',
      rep['cfg_changed'] == [str(game / 'one.cfg')] and rep['cfg_ours'] == [] and not cb.troubled(rep))
check('so no copy is kept', not sess.bak.exists() and cb.kept('u') == [])
(game / 'one.cfg').write_text(OWNER)
time.sleep(1.1)                                   # a fresh tag; it is to the second
sess = cb.Session(ns(name='u'))
sess.snapshot()
(game / 'one.cfg').write_text(f'cfg_save_auto "0"\nseta {cb.MARKER} "{sess.tag}"\n')
rep = sess.shutdown(False)
copy = Path(rep['cfg_backup']) / 'one.cfg' if rep['cfg_backup'] else None
check('a change carrying this session\'s marker is this session\'s',
      rep['cfg_ours'] == [str(game / 'one.cfg')] and cb.troubled(rep))
check('the bytes from the start are kept', bool(copy) and copy.read_text() == OWNER)
check('kept() lists the copy for the next start', [p.name for p in cb.kept('u')] == [sess.bak.name])
check('kept() does not match another name', cb.kept('t') == [] and cb.kept('u_2') == [])
(game / 'one.cfg').write_text(OWNER)
time.sleep(1.1)
sess = cb.Session(ns(name='u'))
sess.snapshot()
(game / 'one.cfg').write_text(f'seta {cb.MARKER} "bridge_u_20200101T000000"\n')
rep = sess.shutdown(False)
check('another session\'s marker is not this session\'s', rep['cfg_ours'] == [] and len(rep['cfg_changed']) == 1)
(game / 'one.cfg').write_text(OWNER)

# -- the stop report sees the files beside data/: a data/-only listing missed conhistory.txt --
sess = cb.Session(ns(name='s'))
sess.snapshot()
(game / 'conhistory.txt').write_text('x')
(game / 'data' / 'new.txt').write_text('x')
rep = sess.shutdown(False)
check('a new top-level file and a new data/ file are both reported',
      rep['install']['added'] == [os.path.join('g', 'conhistory.txt'), os.path.join('g', 'data', 'new.txt')],
      str(rep['install']['added']))
(game / 'conhistory.txt').unlink()
(game / 'data' / 'new.txt').unlink()

# -- never snapshotted must not read as "everything changed", nor as "unchanged" -----------
rep = cb.Session(ns(name='v')).shutdown(False)
check('no snapshot: no verdict, and a note saying so',
      rep['cfg_changed'] == [] and any('never snapshotted' in n for n in rep['notes']))

# -- a manifest the tool cannot rewrite must stop the start, not fall back -----------------
(root / 'default.fmf').write_text('FTEMANIFEST 1\nGAME "X"\n')
sess = cb.Session(ns(name='w'))
sess.snapshot()
try:
    sess.plumb()
    check('no MAINCONFIG line: refused', False)
except cb.Boot as e:
    check('no MAINCONFIG line: refused', 'MAINCONFIG' in str(e) and not sess.fmf.exists())
sess.shutdown(False)
(root / 'default.fmf').write_text('FTEMANIFEST 1\nGAME "X"\nMAINCONFIG one\n')

# -- a peer that opens the pipe and says nothing -----------------------------------------
if os.name == 'nt':
    key = os.urandom(16)

    def ask(name, address, seconds):
        cb.save_state(name, {'name': name, 'pid': os.getpid(), 'address': address,
                             'authkey': key.hex(), 'phase': 'ready', 'engines': {}})
        got = {}
        t = threading.Thread(target=lambda: got.update(cb.call(ns(name=name), {'op': 'status'})), daemon=True)
        t.start()
        t.join(seconds)
        return got, t.is_alive()

    address = rf'\\.\pipe\cbtest-{os.getpid()}'
    sess = cb.Session(ns(name='p'))
    threading.Thread(target=sess.accept, args=(cb.Listener(address, family=cb.FAMILY), key), daemon=True).start()
    silent = open(address, 'r+b', buffering=0)
    got, stuck = ask('p', address, 8)
    check('a silent pipe client does not stall a real request', got.get('ok') is True and not stuck)
    # Control: the handshake where it used to be, inside accept().
    inline = cb.Listener(address + '-inline', family=cb.FAMILY, authkey=key)

    def old():
        try:
            while True:
                c = inline.accept()
                c.recv_bytes()
                c.send_bytes(b'{"ok": true}')
                c.close()
        except EOFError:                          # the silent peer closing, at the end
            pass

    threading.Thread(target=old, daemon=True).start()
    silent2 = open(address + '-inline', 'r+b', buffering=0)
    got, stuck = ask('p2', address + '-inline', 4)
    check('CONTROL, handshake inside accept(): the same request stalls', stuck and not got)
    silent.close()
    silent2.close()

# -- stop must not clear a live daemon's state -------------------------------------------
holder = subprocess.Popen([sys.executable, *IDLE])
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

# -- start sweeps a dead session's manifest and config, and only its own name's -----------
dead = [root / 'bridge_boot_20200101T000000.fmf', game / 'bridge_boot_20200101T000000.cfg']
other = [root / 'bridge_boot_2_20200101T000000.fmf', game / 'bridge_bootleg.cfg']
for p in dead + other:
    p.write_text('x')
rc, out = cli(script, '--name', 'boot', 'start', '--map', 'm', '--root', str(root), '--gamedir', 'g',
              '--server', str(scratch / 'no-such.exe'), '--client', str(scratch / 'no-such.exe'))
check('start with no executable fails cleanly', rc == 2 and 'no executable' in out, out.strip()[-80:])
check('and swept the dead session\'s two files', not any(p.exists() for p in dead))
check('but not another name\'s', all(p.exists() for p in other))
check('and left nothing of its own', not list(root.glob('bridge_boot_2026*')) and not list(game.glob('bridge_boot_2026*')))

# -- finish() removes only its own state ---------------------------------------------------
cb.save_state('other', {'name': 'other', 'pid': 1, 'address': 'x', 'authkey': '00',
                        'phase': 'ready', 'engines': {}})
subprocess.run([sys.executable, '-c',
                'import importlib.util;'
                f's=importlib.util.spec_from_file_location("conbridge",r"{script}");'
                'm=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.finish("other",0)'])
check("finish() leaves another daemon's state", cb.state_path('other').exists())

# -- text the console codec cannot encode, with its control --------------------------------
cb.save_state('gone', {'name': 'gone', 'pid': 1, 'address': 'x', 'authkey': '00',
                       'phase': 'failed', 'reason': 'snowman \u2603 in a log line', 'engines': {}})
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
sys.stdout.flush()
# Not sys.exit: the pipe cases leave daemon threads blocked in I/O on purpose, and finalizing
# the interpreter around them aborted it (exit 0xC0000409 with "0 failed" printed).
os._exit(1 if fails else 0)
