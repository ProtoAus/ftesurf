#!/usr/bin/env python3
"""Live console bridge: one client and one dedicated server kept running, driven a line at a time.

    python tools/conbridge.py start --map surf_dune   launch both, connect, wait for the spawn
    python tools/conbridge.py send "cmd zone_goto 1"  one console line to the client (--sv: server)
    python tools/conbridge.py wait "running"          block until a new log line matches
    python tools/conbridge.py log                     what the client logged since the last `log`
    python tools/conbridge.py info                    the server's word on position, speed, timer
    python tools/conbridge.py shot                    screenshot; prints the PNG path
    python tools/conbridge.py status
    python tools/conbridge.py stop                    quit both, list what the session left behind

FOR EXPLORING, NOT FOR GRADING. A step from an agent takes seconds and nothing here is
repeatable; freeze what you find into a cfg/test arm with a control.

An engine started with -plugin reads console lines from a piped stdin (engine
client/sys_win.c Sys_SendKeyEvents, server/sv_sys_win.c Sys_ConsoleInput) and quits when
that pipe closes, so a dead bridge leaves no game behind. Output is the two log files. A
command has no reply -- output arrives frames later and SSQC prints land in the SERVER
log -- hence `send` then `wait`, never "run and return".

It runs in the real install by default, as the owner's own profile, and shares
<gamedir>/data with the owner. `stop` diffs that tree and the gamedir's *.cfg against a
listing taken at start; it reports and does not undo. The server is given `run_resume 0`
before the client joins, so the session can neither park over nor drop the owner's
data/resume/<map> slot. The client window is put behind the others and off the foreground
at start (`window`); a vid_restart brings it forward again. Windows-tested only.

Exit status: 0 done, 1 a negative answer (timeout, not connected), 2 could not ask.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from multiprocessing.connection import AuthenticationError, Client, Listener
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = Path(tempfile.gettempdir()) / 'ftesurf-bridge'
FAMILY = 'AF_PIPE' if os.name == 'nt' else 'AF_UNIX'
# The engine's stdin buffer is char[256]; a line that fills it with no newline never
# completes (sys_win.c:2977, sv_sys_win.c:1059).
MAXLINE = 240
SVPREFIX = 'echo;'
STAMP = re.compile(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ')
NAME = re.compile(r'^[A-Za-z0-9_-]+$')
WINDOW = ('back', 'min', 'free')
WINDOW_HELP = ('back: visible behind the other windows, never the foreground; min: minimized, '
               'which renders nothing; free: left alone, and it takes the foreground. Applied '
               'at start and by this command, not continuously')
POS = re.compile(r'^setpos (\S+) (\S+) (\S+) (\S+) (\S+) (\S+)$')
VEL = re.compile(r'^velocity (\S+) (\S+) (\S+)\s+horizontal (\S+)$')
TIMER = re.compile(r'timer\S*: (\w+) on (\S+), tick (\S+),')
RECORDING = re.compile(r'practice (\d+)\s+recording (\d+)')


class Boot(Exception):
    pass


class NoSession(Exception):
    pass


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def pid_alive(pid: int) -> bool:
    # NOT os.kill(pid, 0): on Windows that is TerminateProcess.
    if os.name != 'nt':
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            pass
        return True
    import ctypes
    k = ctypes.windll.kernel32
    k.OpenProcess.restype = ctypes.c_void_p
    k.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    h = k.OpenProcess(0x1000, False, pid)       # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    code = ctypes.c_ulong()
    ok = k.GetExitCodeProcess(h, ctypes.byref(code))
    k.CloseHandle(h)
    return bool(ok) and code.value == 259       # STILL_ACTIVE


def windows(pid: int) -> tuple[list, bool]:
    """([(hwnd, minimized)] for the process's visible top-level windows, is-foreground)."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    u.EnumWindows.argtypes = [proto, wintypes.LPARAM]
    u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    u.IsWindowVisible.argtypes = [wintypes.HWND]
    u.IsIconic.argtypes = [wintypes.HWND]
    u.GetForegroundWindow.restype = wintypes.HWND
    found = []

    def each(hwnd, _):
        owner = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and u.IsWindowVisible(hwnd):
            found.append((hwnd, bool(u.IsIconic(hwnd))))
        return True

    u.EnumWindows(proto(each), 0)
    fg = wintypes.DWORD()
    u.GetWindowThreadProcessId(u.GetForegroundWindow(), ctypes.byref(fg))
    return found, fg.value == pid


def window(pid: int) -> tuple[str, bool]:
    """(minimized|visible|none|unknown, is-foreground)."""
    if os.name != 'nt':
        return 'unknown', False
    found, fg = windows(pid)
    return ('none' if not found else 'minimized' if all(m for _, m in found) else 'visible'), fg


def set_window(pid: int, state: str) -> None:
    """back: visible, behind everything, not the foreground. min: minimized (renders nothing).

    The engine shows its window and takes the foreground on every mode set (gl_vidnt.c:1628,
    :1727), so STARTUPINFO alone does not keep it out of the owner's way. The Async calls
    post and return: the plain ones block until the engine pumps messages.
    """
    if os.name != 'nt':
        return
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    u.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
    u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND] + [ctypes.c_int] * 4 + [wintypes.UINT]
    found, fg = windows(pid)
    for hwnd, iconic in found:
        if fg or (state == 'min' and not iconic):
            u.ShowWindowAsync(hwnd, 6)          # SW_MINIMIZE: the next window gets the foreground
            iconic = True
        if state == 'back':
            if iconic:
                u.ShowWindowAsync(hwnd, 4)      # SW_SHOWNOACTIVATE
            # HWND_BOTTOM, SWP_NOSIZE | NOMOVE | NOACTIVATE | ASYNCWINDOWPOS
            u.SetWindowPos(hwnd, 1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010 | 0x4000)


def listing(base: Path) -> dict:
    """Every dir (None) and file ((size, mtime_ns)) under base; dirs matter, see stop."""
    out = {}
    for d, dirs, files in os.walk(base):
        for n in dirs:
            out[os.path.join(d, n)] = None
        for n in files:
            p = os.path.join(d, n)
            try:
                st = os.stat(p)
            except FileNotFoundError:       # gone between scandir and stat: not there
                continue
            out[p] = (st.st_size, st.st_mtime_ns)
    return out


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def placed(line: str) -> bool:
    """A `setpos` reply whose six numbers are not all zero."""
    for word in POS.match(STAMP.sub('', line)).groups():
        try:
            if float(word):
                return True
        except ValueError:
            return True
    return False


class Engine:
    def __init__(self, key: str, argv: list, cwd: Path, log: Path, show: bool):
        self.key, self.argv, self.log = key, argv, log
        si, flags = None, 0
        if os.name == 'nt':
            if key == 'sv':
                flags = subprocess.CREATE_NO_WINDOW
            elif not show:
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = 7              # SW_SHOWMINNOACTIVE: leaves the owner's focus alone
        self.proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.PIPE,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     startupinfo=si, creationflags=flags)
        self.lock = threading.Lock()
        self.cursor = 0
        self.typed: list[str] = []

    def alive(self) -> bool:
        return self.proc.poll() is None

    def size(self) -> int:
        try:
            return self.log.stat().st_size
        except FileNotFoundError:
            return 0

    def send(self, line: str) -> None:
        with self.lock:
            if self.key == 'sv':
                # The server logs a typed line with NO newline (sv_main.c:5369), so a reply's
                # first line would glue onto it. A bare echo prints that newline first, and
                # read() takes the typed text back out.
                line = SVPREFIX + line
                if line not in self.typed:
                    self.typed = [line] + self.typed[:63]
            self.proc.stdin.write(line.encode() + b'\n')
            self.proc.stdin.flush()

    def untyped(self, text: str) -> str:
        found = True
        while found and text:
            found = False
            for line in sorted(self.typed, key=len, reverse=True):
                if text.startswith(line):
                    text, found = text[len(line):], True
                    break
        return text

    def read(self, offset: int, typed: bool = False) -> list:
        """Complete lines from byte offset: (text without timestamp, raw line, end offset).

        text has the server's echo of our own sends removed; a line that was nothing else
        is left out unless typed is set.
        """
        try:
            with self.log.open('rb') as f:
                f.seek(offset)
                data = f.read()
        except FileNotFoundError:
            return []
        out, pos = [], offset
        for piece in data.split(b'\n')[:-1]:    # the last piece has no newline yet
            pos += len(piece) + 1
            raw = piece.decode('utf-8', 'replace').rstrip('\r')
            stamped = STAMP.sub('', raw)
            text = self.untyped(stamped)
            if typed or text or not stamped:
                out.append((text, raw, pos))
        return out


class Session:
    def __init__(self, a: argparse.Namespace):
        self.a = a
        self.root = Path(a.root).resolve()
        self.game = self.root / a.gamedir
        self.tag = f'bridge_{a.name}_{time.strftime("%Y%m%dT%H%M%S")}'
        self.engines: dict[str, Engine] = {}
        self.mark: dict[str, int] = {}
        self.shots: list[Path] = []
        self.guards: list[str] = []
        self.port = 0
        self.spawn = ''
        self.policy = a.window
        self.last = time.monotonic()
        self.t0 = time.monotonic()
        self.stoplock = threading.Lock()
        self.report = None
        self.before = None
        self.cfgs = {}

    # ---- boot -----------------------------------------------------------------------

    def boot(self) -> None:
        a = self.a
        if not self.game.is_dir():
            raise Boot(f'no gamedir {self.game}')
        self.before = listing(self.game / 'data')
        self.cfgs = {p: sha(p) for p in sorted(self.game.glob('*.cfg'))}
        common = ['-plugin', '+set', 'cfg_save_auto', '0', '+log_enable', '1', '+log_dir', 'logs']
        if not a.no_server:
            self.port = a.port or free_port()
            argv = [a.server, *common, '+log_name', self.tag + '_sv', '-port', str(self.port),
                    '+sv_public', '0', *a.server_args.split()]
            if a.map:
                argv += ['+map', a.map]
            self.launch('sv', argv)
            if a.map and not a.resume:
                # After the map: registercvar resets a value set before it. Unknown here
                # means the server QC never loaded, i.e. the map did not.
                self.expect('sv', ['set run_resume 0', 'run_resume'], r'^"run_resume" is "0"$',
                            'run_resume 0 not read back -- did the map load?')
                self.guards.append('run_resume 0 (sv, read back)')
        if not a.no_client:
            w, h = a.size.lower().split('x')
            argv = [a.client, *common, '+log_name', self.tag + '_cl', '-window',
                    '+set', 'vid_fullscreen', '0', '+set', 'vid_winmaximize', '0',
                    '+set', 'vid_width', w, '+set', 'vid_height', h,
                    '+set', 'cl_idlefps', '0', '+set', 'cl_maxfps', '100',
                    *([] if a.sound else ['-nosound']), *a.client_args.split()]
            self.launch('cl', argv)
            self.expect('cl', ['cfg_save_auto'], r'^"cfg_save_auto" is "0"$',
                        'cfg_save_auto is not 0: this client would write the owner\'s config')
            self.guards.append('cfg_save_auto 0 (cl, read back)')
            if a.map and not a.no_server:
                self.connect()
        self.mark = {k: e.size() for k, e in self.engines.items()}

    def launch(self, key: str, argv: list) -> None:
        if not Path(argv[0]).is_file():
            raise Boot(f'no executable {argv[0]}')
        log = self.game / 'logs' / f'{self.tag}_{key}.log'
        eng = self.engines[key] = Engine(key, argv, self.root, log, self.policy == 'free')
        marker = 'BRIDGE-READY-' + secrets.token_hex(4)
        t0 = time.monotonic()
        while True:
            # Re-sent until echoed: a line the client reads while it is still starting
            # is dropped without a word (measured: one early send, 40 s, no echo).
            eng.send('echo ' + marker)
            r = self.poll(key, f'^{marker}$', 0)
            if r['verdict'] == 'match':
                break
            if r['verdict'] == 'exited' or time.monotonic() - t0 >= self.a.boot_timeout:
                r['secs'] = time.monotonic() - t0
                raise Boot(f'{key} never echoed the ready marker: {self.why(r)}; log {log}')

    def expect(self, key: str, lines: list, pattern: str, why: str) -> dict:
        mark = self.engines[key].size()
        for line in lines:
            self.engines[key].send(line)
        r = self.wait(key, pattern, mark, 10)
        if r['verdict'] != 'match':
            raise Boot(f'{why} ({key}: {self.why(r)})')
        return r

    def connect(self) -> None:
        cl, sv = self.engines['cl'], self.engines['sv']
        svmark, clmark = sv.size(), cl.size()
        cl.send(f'connect 127.0.0.1:{self.port}')
        r = self.wait('sv', r'^client .* connected$', svmark, self.a.boot_timeout)
        if r['verdict'] != 'match':
            raise Boot(f'the server never logged the connection: {self.why(r)}')
        # The join lines are behind a lobby setting, and the server QC answers cmd viewpos
        # BEFORE the spawn with an unplaced body (measured: 0 0 0 twice, then the spawn point
        # 4 s later). So ask until the body is somewhere.
        t0, zero = time.monotonic(), None
        while True:
            clmark = cl.size()
            cl.send('cmd viewpos')
            r = self.poll('cl', POS.pattern, clmark)
            now = time.monotonic()
            if r['verdict'] == 'match':
                if placed(r['line']):
                    self.spawn = r['line']
                    break
                zero = zero or now
                if now - zero >= 10:
                    self.spawn = 'NOT PROVEN, the body is still at the origin: ' + r['line']
                    break
                time.sleep(0.5)                 # an answer is instant; do not flood the console
            elif r['verdict'] == 'exited' or now - t0 >= self.a.boot_timeout:
                r['secs'] = now - t0
                raise Boot(f'connected, but the server never answered cmd viewpos: {self.why(r)}')
        if not self.a.keep_menu:
            # The builtin menu is open from boot and hides the whole HUD stack (AGENT_NOTES).
            cl.send('menu_restart')
            cl.send('ui_close')
        self.park()

    def park(self) -> None:
        eng = self.engines.get('cl')
        if self.policy != 'free' and eng and eng.alive():
            set_window(eng.proc.pid, self.policy)

    def poll(self, key: str, pattern: str, since: int) -> dict:
        """One second of wait, parking the window every quarter: boot is when it grabs focus."""
        for _ in range(4):
            r = self.wait(key, pattern, since, 0.25)
            self.park()
            if r['verdict'] != 'timeout':
                break
        return r

    @staticmethod
    def why(r: dict) -> str:
        last = f'; last: {r["tail"][-1]}' if r.get('tail') else ''
        if r['verdict'] == 'exited':
            return f'process exited rc {r["rc"]} after {r["scanned"]} log lines{last}'
        return f'{r["verdict"]} after {r["secs"]:.1f} s and {r["scanned"]} new log lines{last}'

    # ---- primitives -----------------------------------------------------------------

    def wait(self, key: str, pattern: str, since: int, timeout: float) -> dict:
        eng, rx = self.engines[key], re.compile(pattern)
        t0, off, scanned, tail = time.monotonic(), since, 0, []
        while True:
            dead = not eng.alive()              # sampled before the read, so a last line still counts
            for text, raw, end in eng.read(off):
                off, scanned = end, scanned + 1
                tail = (tail + [raw])[-5:]
                if rx.search(text):
                    return {'verdict': 'match', 'line': raw, 'offset': end, 'scanned': scanned,
                            'secs': time.monotonic() - t0}
            secs = time.monotonic() - t0
            if dead:
                return {'verdict': 'exited', 'rc': eng.proc.returncode, 'scanned': scanned,
                        'tail': tail, 'secs': secs}
            if secs >= timeout:
                return {'verdict': 'timeout', 'scanned': scanned, 'tail': tail, 'secs': secs}
            time.sleep(0.05)

    def engine(self, req: dict) -> Engine:
        key = req.get('target', 'cl')
        if key not in self.engines:
            raise ValueError(f'this session has no {key}')
        return self.engines[key]

    def push(self, eng: Engine, line: str) -> dict:
        if '\n' in line or '\r' in line:
            raise ValueError('one line per send')
        room = MAXLINE - (len(SVPREFIX) if eng.key == 'sv' else 0)
        if len(line.encode()) > room:
            raise ValueError(f'line is {len(line.encode())} bytes; the engine stdin buffer takes '
                             f'{room} -- split it')
        if not eng.alive():
            raise ValueError(f'{eng.key} has exited, rc {eng.proc.returncode}')
        self.mark = {k: e.size() for k, e in self.engines.items()}
        eng.send(line)
        return dict(self.mark)

    # ---- requests -------------------------------------------------------------------

    def op_send(self, req: dict) -> dict:
        eng = self.engine(req)
        return {'ok': True, 'target': eng.key, 'mark': self.push(eng, req['line'])}

    def op_wait(self, req: dict) -> dict:
        eng = self.engine(req)
        since = req.get('since')
        r = self.wait(eng.key, req['pattern'], self.mark[eng.key] if since is None else since,
                      float(req.get('timeout', 10)))
        return {'ok': True, 'target': eng.key, **r}

    def op_log(self, req: dict) -> dict:
        eng, mode = self.engine(req), req.get('mode', 'new')
        start = {'new': eng.cursor, 'send': self.mark[eng.key], 'all': 0}[mode]
        rows = eng.read(start, typed=True)
        if mode == 'new' and rows:
            eng.cursor = rows[-1][2]
        rx = re.compile(req['grep']) if req.get('grep') else None
        lines = [raw for text, raw, _ in rows if not rx or rx.search(text)]
        limit = int(req.get('limit', 200))
        return {'ok': True, 'target': eng.key, 'lines': lines[-limit:],
                'omitted': max(0, len(lines) - limit), 'read': len(rows)}

    def op_shot(self, req: dict) -> dict:
        if 'cl' not in self.engines:
            raise ValueError('this session has no cl')
        eng = self.engines['cl']
        name = req.get('name') or f'{self.tag}_{len(self.shots) + 1:03d}'
        if not NAME.match(name):
            raise ValueError('screenshot name: letters, digits, _ and - only')
        if window(eng.proc.pid)[0] == 'minimized':
            # Measured: 1280x720 of black, 2759 bytes, and a `Wrote` line all the same.
            raise ValueError('the client window is minimized and renders nothing; `window back` first')
        shots = self.game / 'screenshots'
        if list(shots.glob(name + '.*')):
            raise ValueError(f'{name} already exists in {shots}')
        mark = self.push(eng, 'screenshot ' + name)['cl']
        r = self.wait('cl', rf'^Wrote .*[/\\]{re.escape(name)}\.\w+$', mark, float(req.get('timeout', 20)))
        if r['verdict'] != 'match':
            return {'ok': True, **r}
        path = shots / r['line'].rsplit('/', 1)[-1].rsplit('\\', 1)[-1]
        if not path.is_file():
            return {'ok': True, 'verdict': 'missing', 'line': r['line'], 'path': str(path)}
        self.shots.append(path)
        return {'ok': True, 'verdict': 'match', 'path': str(path), 'bytes': path.stat().st_size,
                'window': window(eng.proc.pid)[0]}

    def op_info(self, req: dict) -> dict:
        if 'cl' not in self.engines:
            raise ValueError('this session has no cl')
        eng = self.engines['cl']
        off = self.push(eng, 'cmd viewpos')['cl']
        self.push(eng, 'cmd timer')
        out, lines, t0 = {'ok': True}, [], time.monotonic()
        timeout = float(req.get('timeout', 5))
        settle = None
        while True:
            dead = not eng.alive()
            for text, _, end in eng.read(off):
                off = end
                lines.append(text)
                if 'not connected' in text:
                    return {**out, 'verdict': 'not connected', 'lines': lines}
                if m := POS.match(text):
                    out['origin'], out['angles'] = list(m.groups()[:3]), list(m.groups()[3:])
                elif m := VEL.match(text):
                    out['velocity'], out['speed'] = list(m.groups()[:3]), m.group(4)
                elif m := TIMER.search(text):
                    out['timer'] = {'state': m.group(1), 'map': m.group(2), 'tick': m.group(3)}
                elif (m := RECORDING.search(text)) and 'timer' in out:
                    out['timer'].update(practice=int(m.group(1)), recording=int(m.group(2)))
            if settle is None and 'speed' in out and 'recording' in out.get('timer', {}):
                settle = time.monotonic() + 0.3     # the rest of the timer block follows
            if settle is not None and time.monotonic() >= settle:
                return {**out, 'verdict': 'ok', 'lines': lines}
            if dead:
                return {**out, 'verdict': 'exited', 'rc': eng.proc.returncode, 'lines': lines}
            if time.monotonic() - t0 >= timeout:
                # NOT idle and NOT stopped: the question was not answered.
                return {**out, 'verdict': 'no reply', 'lines': lines}
            time.sleep(0.05)

    def op_status(self, req: dict) -> dict:
        engines = {}
        for key, eng in self.engines.items():
            row = {'pid': eng.proc.pid, 'alive': eng.alive(), 'rc': eng.proc.returncode,
                   'log': str(eng.log), 'log_bytes': eng.size()}
            if key == 'cl':
                row['window'], row['foreground'] = window(eng.proc.pid) if eng.alive() else ('none', False)
                row['focus_lines'] = [raw for text, raw, _ in eng.read(0) if '[focus]' in text][-5:]
            engines[key] = row
        return {'ok': True, 'name': self.a.name, 'tag': self.tag, 'root': str(self.root),
                'port': self.port, 'map': self.a.map, 'size': self.a.size, 'engines': engines,
                'guards': self.guards, 'spawn': self.spawn, 'shots': len(self.shots),
                'uptime': time.monotonic() - self.t0, 'idle_minutes': self.a.idle,
                'cfg_changed': self.cfg_changed()}

    def op_window(self, req: dict) -> dict:
        if 'cl' not in self.engines:
            raise ValueError('this session has no cl')
        self.policy = req['state']
        self.park()
        time.sleep(0.5)                         # the calls are posted, not done
        state, fg = window(self.engines['cl'].proc.pid)
        return {'ok': True, 'window': state, 'foreground': fg}

    def cfg_changed(self) -> list:
        now = {p: sha(p) for p in sorted(self.game.glob('*.cfg'))}
        return sorted(str(p) for p in set(now) | set(self.cfgs) if now.get(p) != self.cfgs.get(p))

    def op_stop(self, req: dict) -> dict:
        with self.stoplock:
            if self.report is None:
                self.report = self.shutdown(bool(req.get('purge')))
            return self.report

    def shutdown(self, purge: bool) -> dict:
        ends, notes = {}, []
        for key in ('cl', 'sv'):                # the client first, so it leaves the server cleanly
            eng = self.engines.get(key)
            if not eng:
                continue
            if eng.alive():
                try:
                    if key == 'cl':
                        eng.send('cfg_save_auto 0')     # quit writes the config when it is on
                    eng.send('quit')
                    eng.proc.wait(20)
                    ends[key] = f'quit, rc {eng.proc.returncode}'
                except subprocess.TimeoutExpired:
                    eng.proc.terminate()
                    eng.proc.wait(10)
                    ends[key] = 'did not quit in 20 s; TERMINATED'
                except OSError as e:
                    eng.proc.wait(10)
                    ends[key] = f'exited as quit was sent ({e}), rc {eng.proc.returncode}'
            else:
                ends[key] = f'had already exited, rc {eng.proc.returncode}'
            try:
                eng.proc.stdin.close()
            except OSError as e:
                notes.append(f'{key} stdin close: {e}')
        made = [e.log for e in self.engines.values() if e.log.exists()] + \
               [p for p in self.shots if p.exists()]
        rep = {'ok': True, 'ends': ends, 'notes': notes, 'cfg_changed': self.cfg_changed(),
               'focus_lines': [], 'purged': [], 'purge_errors': []}
        if 'cl' in self.engines:
            rep['focus_lines'] = [raw for text, raw, _ in self.engines['cl'].read(0) if '[focus]' in text]
        if self.before is not None:
            after = listing(self.game / 'data')
            rel = lambda p: os.path.relpath(p, self.root)
            rep['data'] = {
                'added': sorted(rel(p) for p in after if p not in self.before),
                'removed': sorted(rel(p) for p in self.before if p not in after),
                'changed': sorted(rel(p) for p in after if p in self.before and after[p] != self.before[p]),
            }
        if purge:
            for p in made:
                try:
                    p.unlink()
                    rep['purged'].append(str(p))
                except OSError as e:
                    rep['purge_errors'].append(f'{p}: {e}')
            made = [p for p in made if p.exists()]
        rep['files'] = [str(p) for p in made]
        return rep

    # ---- daemon ---------------------------------------------------------------------

    def serve_one(self, conn) -> None:
        req, rep = {}, None
        try:
            with conn:
                try:
                    req = json.loads(conn.recv_bytes())
                    self.last = time.monotonic()
                    op = getattr(self, 'op_' + str(req.get('op')), None)
                    rep = op(req) if op else {'ok': False, 'error': f'no such op {req.get("op")!r}'}
                except (ValueError, KeyError, re.error) as e:
                    rep = {'ok': False, 'error': str(e)}
                except Exception as e:          # the daemon must outlive one bad request
                    traceback.print_exc()
                    rep = {'ok': False, 'error': f'{type(e).__name__}: {e}'}
                conn.send_bytes(json.dumps(rep).encode())
                if req.get('op') == 'stop' and rep.get('ok'):
                    conn.poll(5)                # let the caller read the report before we go
        except (OSError, EOFError):
            traceback.print_exc()
        if req.get('op') == 'stop' and rep and rep.get('ok'):
            finish(self.a.name, 0)

    def watchdog(self) -> None:
        while True:
            time.sleep(5)
            if self.a.idle and time.monotonic() - self.last > self.a.idle * 60:
                print(f'idle {self.a.idle} min: stopping', flush=True)
                print(json.dumps(self.op_stop({}), indent=1), flush=True)
                finish(self.a.name, 0)


def state_path(name: str) -> Path:
    return STATE / f'{name}.json'


def load_state(name: str):
    try:
        return json.loads(state_path(name).read_text())
    except FileNotFoundError:
        return None


def save_state(name: str, st: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    tmp = state_path(name).with_suffix('.tmp')
    tmp.write_text(json.dumps(st))
    os.replace(tmp, state_path(name))


def finish(name: str, rc: int) -> None:
    state_path(name).unlink(missing_ok=True)
    sys.stdout.flush()
    os._exit(rc)


def cmd_serve(a: argparse.Namespace) -> int:
    address = rf'\\.\pipe\ftesurf-bridge-{a.name}-{secrets.token_hex(4)}' if os.name == 'nt' \
        else str(STATE / f'{a.name}.sock')
    st = {'name': a.name, 'pid': os.getpid(), 'address': address,
          'authkey': secrets.token_hex(16), 'phase': 'booting', 'engines': {}}
    save_state(a.name, st)
    sess = Session(a)
    try:
        sess.boot()
    except Exception as e:
        if not isinstance(e, Boot):
            traceback.print_exc()
        rep = sess.shutdown(False)
        print(f'boot failed: {e}\n{json.dumps(rep, indent=1)}', flush=True)
        save_state(a.name, {**st, 'phase': 'failed', 'reason': f'{type(e).__name__}: {e}',
                            'files': rep['files']})
        return 2
    listener = Listener(address, family=FAMILY, authkey=bytes.fromhex(st['authkey']))
    save_state(a.name, {**st, 'phase': 'ready',
                        'engines': {k: e.proc.pid for k, e in sess.engines.items()}})
    print(f'ready: {sess.tag}', flush=True)
    threading.Thread(target=sess.watchdog, daemon=True).start()
    try:
        while True:
            try:
                conn = listener.accept()
            except (AuthenticationError, EOFError, OSError) as e:
                print(f'refused a connection: {type(e).__name__}: {e}', flush=True)
                continue
            threading.Thread(target=sess.serve_one, args=(conn,), daemon=True).start()
    except KeyboardInterrupt:
        print(json.dumps(sess.op_stop({}), indent=1), flush=True)
        finish(a.name, 0)
    return 0


def call(a: argparse.Namespace, req: dict) -> dict:
    st = load_state(a.name)
    if not st:
        raise NoSession(f"no bridge session '{a.name}' -- start one")
    if st['phase'] != 'ready':
        raise NoSession(f"session '{a.name}' is {st['phase']}: {st.get('reason', 'still launching')}")
    try:
        conn = Client(st['address'], family=FAMILY, authkey=bytes.fromhex(st['authkey']))
    except (OSError, AuthenticationError) as e:
        gone = {k: pid_alive(p) for k, p in {'daemon': st['pid'], **st['engines']}.items()}
        raise NoSession(f"session '{a.name}' did not answer ({type(e).__name__}: {e}); "
                        f'processes alive: {gone}. `stop` clears the stale state.')
    with conn:
        conn.send_bytes(json.dumps(req).encode())
        rep = json.loads(conn.recv_bytes())
    if not rep.get('ok'):
        raise NoSession(rep.get('error', 'bridge error'))
    return rep


def launch_args(a: argparse.Namespace) -> list:
    out = ['--root', a.root, '--gamedir', a.gamedir, '--client', a.client, '--server', a.server,
           '--size', a.size, '--port', str(a.port), '--idle', str(a.idle),
           '--boot-timeout', str(a.boot_timeout),
           '--client-args=' + a.client_args, '--server-args=' + a.server_args]
    if a.map:
        out += ['--map', a.map]
    out += ['--window', a.window]
    for flag in ('no_server', 'no_client', 'sound', 'resume', 'keep_menu'):
        if getattr(a, flag):
            out.append('--' + flag.replace('_', '-'))
    return out


def cmd_start(a: argparse.Namespace) -> int:
    st = load_state(a.name)
    if st and st['phase'] != 'failed' and pid_alive(st['pid']):
        print(f"session '{a.name}' is already {st['phase']} (daemon pid {st['pid']}); "
              f'stop it or pick another --name')
        return 2
    state_path(a.name).unlink(missing_ok=True)
    STATE.mkdir(parents=True, exist_ok=True)
    dlog = STATE / f'{a.name}.daemon.log'
    flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == 'nt' else 0
    with dlog.open('w') as out:
        daemon = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--name', a.name,
                                   'serve', *launch_args(a)], stdin=subprocess.DEVNULL, stdout=out,
                                  stderr=subprocess.STDOUT, creationflags=flags,
                                  start_new_session=(os.name != 'nt'))
    while True:
        st = load_state(a.name)
        if st and st['phase'] == 'ready':
            return show_status(call(a, {'op': 'status'}), a)
        if st and st['phase'] == 'failed':
            print(f"start failed: {st['reason']}")
            for f in st.get('files', []):
                print('  left:', f)
            state_path(a.name).unlink()
            return 2
        if daemon.poll() is not None:
            print(f'daemon exited rc {daemon.returncode} before it was ready; see {dlog}')
            return 2
        time.sleep(0.2)


def show_status(r: dict, a: argparse.Namespace) -> int:
    if a.json:
        print(json.dumps(r, indent=1))
        return 0
    print(f"bridge '{r['name']}' up {r['uptime']:.0f} s in {r['root']} "
          f"(auto-stops after {r['idle_minutes']} min idle)")
    for key, e in r['engines'].items():
        state = 'alive' if e['alive'] else f"EXITED rc {e['rc']}"
        extra = f"port {r['port']} map {r['map'] or '-'}" if key == 'sv' else \
            f"window {e['window']}{' FOREGROUND' if e['foreground'] else ''} {r['size']}"
        print(f"  {key} pid {e['pid']} {state}  {extra}  log {e['log']} ({e['log_bytes']} bytes)")
        for line in e.get('focus_lines', []):
            print('     ', line)
    print('  guards:', '; '.join(r['guards']) or 'none')
    if r['spawn']:
        print('  spawn:', r['spawn'])
    for p in r['cfg_changed']:
        print('  CONFIG CHANGED SINCE START:', p)
    return 0


def show_wait(r: dict) -> int:
    if r['verdict'] == 'match':
        print(f"MATCH {r['target']} after {r['secs']:.2f} s: {r['line']}")
        return 0
    if r['verdict'] == 'exited':
        print(f"EXITED: {r['target']} is gone (rc {r['rc']}); {r['scanned']} new lines, none matched")
    else:
        print(f"TIMEOUT {r['target']} after {r['secs']:.1f} s: {r['scanned']} new lines, none matched")
    for line in r['tail']:
        print('  |', line)
    return 2 if r['verdict'] == 'exited' else 1


def show_log(r: dict) -> None:
    if r['omitted']:
        print(f"({r['omitted']} earlier lines omitted; --limit raises the cap)")
    for line in r['lines']:
        print(line)
    if not r['lines']:
        print(f"(no lines; {r['read']} read from {r['target']})")


def cmd_send(a: argparse.Namespace) -> int:
    target = 'sv' if a.sv else 'cl'
    r = call(a, {'op': 'send', 'target': target, 'line': a.line})
    if a.wait:
        on = 'sv' if a.on_sv else 'cl' if a.on_cl else target
        return show_wait(call(a, {'op': 'wait', 'target': on, 'pattern': a.wait,
                                  'since': r['mark'][on], 'timeout': a.timeout}))
    print(f'sent to {target}: {a.line}')
    if a.read:
        time.sleep(a.read)
        show_log(call(a, {'op': 'log', 'target': target, 'mode': 'send'}))
    return 0


def cmd_wait(a: argparse.Namespace) -> int:
    return show_wait(call(a, {'op': 'wait', 'target': 'sv' if a.sv else 'cl', 'pattern': a.pattern,
                              'timeout': a.timeout}))


def cmd_log(a: argparse.Namespace) -> int:
    mode = 'all' if a.all else 'send' if a.since_send else 'new'
    show_log(call(a, {'op': 'log', 'target': 'sv' if a.sv else 'cl', 'mode': mode, 'grep': a.grep,
                      'limit': a.limit}))
    return 0


def cmd_shot(a: argparse.Namespace) -> int:
    r = call(a, {'op': 'shot', 'name': a.shotname})
    if r['verdict'] == 'match':
        print(f"{r['path']}  ({r['bytes']} bytes, window {r['window']})")
        return 0
    if r['verdict'] == 'missing':
        print(f"engine said `{r['line']}` but {r['path']} is not there")
        return 2
    return show_wait({'target': 'cl', **r})


def cmd_info(a: argparse.Namespace) -> int:
    r = call(a, {'op': 'info'})
    if a.json:
        print(json.dumps(r, indent=1))
    elif r['verdict'] == 'ok':
        t = r['timer']
        print(f"origin {' '.join(r['origin'])}  angles {' '.join(r['angles'])}")
        print(f"velocity {' '.join(r['velocity'])}  horizontal {r['speed']}")
        print(f"timer {t['state']} on {t['map']}, practice {t['practice']}, "
              f"recording {t['recording']}")
    else:
        print(f"NO ANSWER ({r['verdict']}): the server's reply did not arrive; this says nothing "
              f'about the player')
        for line in r['lines']:
            print('  |', line)
    return {'ok': 0, 'not connected': 1, 'no reply': 2, 'exited': 2}[r['verdict']]


def cmd_status(a: argparse.Namespace) -> int:
    return show_status(call(a, {'op': 'status'}), a)


def cmd_window(a: argparse.Namespace) -> int:
    r = call(a, {'op': 'window', 'state': a.state})
    print(f"window {r['window']}{' FOREGROUND' if r['foreground'] else ''}")
    return 0


def cmd_stop(a: argparse.Namespace) -> int:
    st = load_state(a.name)
    try:
        r = call(a, {'op': 'stop', 'purge': a.purge})
    except NoSession as e:
        if not st:
            raise
        # The engines quit by themselves when the daemon's end of their stdin closes.
        alive = {k: pid_alive(p) for k, p in {'daemon': st['pid'], **st['engines']}.items()}
        print(f'{e}\nclearing stale state; processes alive: {alive}')
        state_path(a.name).unlink(missing_ok=True)
        return 2
    if a.json:
        print(json.dumps(r, indent=1))
        return 1 if r['purge_errors'] else 0
    for key, how in r['ends'].items():
        print(f'{key}: {how}')
    for note in r['notes']:
        print('note:', note)
    for p in r['cfg_changed']:
        print('CONFIG CHANGED DURING THE SESSION:', p)
    if not r['cfg_changed']:
        print('gamedir *.cfg: unchanged')
    if r['focus_lines']:
        print(f"{len(r['focus_lines'])} [focus] lines in the client log, last: {r['focus_lines'][-1]}")
    d = r.get('data', {})
    print('data/ during the session (this session, the owner or a peer): '
          + ', '.join(f'{len(d.get(k, []))} {k}' for k in ('added', 'removed', 'changed')))
    for k in ('added', 'removed', 'changed'):
        for p in d.get(k, [])[:40]:
            print(f'  {k}: {p}')
        if len(d.get(k, [])) > 40:
            print(f'  ... {len(d[k]) - 40} more {k} (--json lists all)')
    for p in r['purged']:
        print('purged:', p)
    for e in r['purge_errors']:
        print('PURGE FAILED:', e)
    for p in r['files']:
        print('left:', p)
    t0 = time.monotonic()
    while pid_alive(st['pid']) and time.monotonic() - t0 < 10:     # it holds its log open
        time.sleep(0.1)
    try:
        (STATE / f'{a.name}.daemon.log').unlink(missing_ok=True)
    except OSError as e:
        print(f'note: daemon log kept ({e})')
    return 1 if r['purge_errors'] else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--name', default='main', help='session name; one bridge per name')
    ap.add_argument('--json', action='store_true', help='raw replies (status, info, stop)')
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('start', 'serve'):
        p = sub.add_parser(name, help='launch detached' if name == 'start' else 'launch in the foreground')
        p.add_argument('--map', help='server map; the client connects and start waits for the spawn')
        p.add_argument('--root', default=str(ROOT), help='basedir and cwd of both processes')
        p.add_argument('--gamedir', default='ftesurf')
        p.add_argument('--client', default=str(ROOT / 'ftesurf64.exe'))
        p.add_argument('--server', default=r'C:\FTEQuake\fteqwsv64.exe')
        p.add_argument('--client-args', default='', help='extra arguments, split on spaces')
        p.add_argument('--server-args', default='', help='extra arguments, split on spaces')
        p.add_argument('--port', type=int, default=0, help='server UDP port; 0 picks a free one')
        p.add_argument('--size', default='1280x720', help='client window, WxH')
        p.add_argument('--idle', type=float, default=30, help='stop after this many minutes with no request; 0 never')
        p.add_argument('--boot-timeout', type=float, default=120)
        p.add_argument('--no-server', action='store_true', help='client only (menus)')
        p.add_argument('--no-client', action='store_true')
        p.add_argument('--window', choices=WINDOW, default='back', help=WINDOW_HELP)
        p.add_argument('--sound', action='store_true')
        p.add_argument('--resume', action='store_true', help='leave run_resume alone (the session may then park over or drop data/resume/<map>)')
        p.add_argument('--keep-menu', action='store_true', help='do not menu_restart + ui_close after the spawn')
        p.set_defaults(fn=cmd_start if name == 'start' else cmd_serve)
    p = sub.add_parser('send', help='one console line')
    p.add_argument('line')
    p.add_argument('--sv', action='store_true', help='to the server instead of the client')
    p.add_argument('--wait', metavar='REGEX', help='then wait for a matching line')
    p.add_argument('--on-sv', action='store_true', help='--wait watches the server log')
    p.add_argument('--on-cl', action='store_true', help='--wait watches the client log')
    p.add_argument('--timeout', type=float, default=10)
    p.add_argument('--read', type=float, metavar='SECS', help='then sleep and print what the target logged')
    p.set_defaults(fn=cmd_send)
    p = sub.add_parser('wait', help='block until a log line since the last send matches')
    p.add_argument('pattern', help='regex, searched in each line without its timestamp')
    p.add_argument('--sv', action='store_true')
    p.add_argument('--timeout', type=float, default=10)
    p.set_defaults(fn=cmd_wait)
    p = sub.add_parser('log', help='log lines since the last `log`')
    p.add_argument('--sv', action='store_true')
    p.add_argument('--all', action='store_true', help='the whole log')
    p.add_argument('--since-send', action='store_true', help='since the last send; keeps the cursor')
    p.add_argument('--grep', metavar='REGEX')
    p.add_argument('--limit', type=int, default=200)
    p.set_defaults(fn=cmd_log)
    p = sub.add_parser('shot', help='screenshot')
    p.add_argument('shotname', nargs='?')
    p.set_defaults(fn=cmd_shot)
    sub.add_parser('info', help='cmd viewpos + cmd timer, parsed').set_defaults(fn=cmd_info)
    sub.add_parser('status').set_defaults(fn=cmd_status)
    p = sub.add_parser('window', help=WINDOW_HELP)
    p.add_argument('state', choices=WINDOW)
    p.set_defaults(fn=cmd_window)
    p = sub.add_parser('stop', help='quit both and report')
    p.add_argument('--purge', action='store_true', help="delete this session's own logs and screenshots")
    p.set_defaults(fn=cmd_stop)
    a = ap.parse_args()
    if not NAME.match(a.name):
        ap.error('--name: letters, digits, _ and - only')
    if a.cmd in ('start', 'serve'):
        if a.no_server and a.no_client:
            ap.error('nothing to launch')
        if a.map and a.no_server:
            ap.error('--map needs the dedicated server (prediction, and the run_resume guard)')
        if not re.fullmatch(r'\d+x\d+', a.size.lower()):
            ap.error('--size is WxH')
    try:
        return a.fn(a)
    except NoSession as e:
        print(e)
        return 2


if __name__ == '__main__':
    sys.exit(main())
