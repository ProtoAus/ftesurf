#!/usr/bin/env python3
"""Windows launcher dev protection + detached Enter handoff, synthetic actors only.

No production keys, game processes or player directories. A hidden, uniquely owned
console receives actual Enter input; the persistent actor proves the launcher exits
without waiting and that its console disappears. The baseline wait can be falsified
with --control. Build the actor with the explicitly supplied --cc.
"""
import argparse
from collections import Counter
import ctypes as c
from ctypes import wintypes as w
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

ACTOR = r'''
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char **argv) {
    const char *report = getenv("LAUNCH_TEST_REPORT");
    const char *stop = getenv("LAUNCH_TEST_STOP");
    char cwd[32768];
    if (!report || !stop || !GetCurrentDirectoryA(sizeof(cwd), cwd)) return 2;
    FILE *f = fopen(report, "wb");
    if (!f) return 3;
    fprintf(f, "%lu\n%d\n%s\n", GetCurrentProcessId(), GetConsoleWindow() != NULL, cwd);
    for (int i = 1; i < argc; ++i) fprintf(f, "%s\n", argv[i]);
    fclose(f);
    for (int i = 0; i < 300; ++i) {
        if (GetFileAttributesA(stop) != INVALID_FILE_ATTRIBUTES) return 0;
        Sleep(100);
    }
    return 4;
}
'''


def wait_for(predicate, message, seconds=8):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.02)
    raise AssertionError(message)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--launcher', type=Path, required=True)
    ap.add_argument('--control', type=Path)
    ap.add_argument('--cc', type=Path, required=True)
    ap.add_argument('--work-root', type=Path, required=True)
    a = ap.parse_args()
    assert os.name == 'nt', 'actual Windows console controls require Windows'
    a.launcher = a.launcher.resolve()
    root = a.work_root.resolve()
    root.mkdir(exist_ok=False)
    (root / 'OWNER.md').write_text('Synthetic launcher acceptance; no real game/player data.\n')
    hits = Counter()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits[self.path] += 1
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"invalid":"unsigned control"}')
        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    feed = f'http://127.0.0.1:{server.server_port}/update.json'
    results = []

    def run(install, *extra, good=True):
        p = subprocess.run([str(a.launcher), '--dir', str(install), '--no-launch',
                            '--allow-insecure', '--manifest-url', feed, *extra],
                           capture_output=True, text=True, timeout=15)
        (root / f'run-{len(list(root.glob("run-*.log"))):02d}.log').write_text(p.stdout + p.stderr)
        assert (p.returncode == 0) == good, (p.returncode, p.stdout, p.stderr)
        return p

    def install(name, git=None):
        d = root / name
        d.mkdir()
        (d / 'default.fmf').write_bytes(b'synthetic manifest\n')
        (d / 'ftesurf64.exe').write_bytes(b'dev executable sentinel\n')
        if git == 'file':
            (d / '.git').write_text('gitdir: synthetic worktree\n')
        elif git == 'directory':
            (d / '.git').mkdir()
        return d

    try:
        for kind in ('file', 'directory'):
            d = install('dev-' + kind, kind)
            meta = d / '.ftesurf-updater'
            meta.mkdir()
            (meta / 'consent').write_bytes(b'1\n')
            before = (d / 'ftesurf64.exe').read_bytes()
            for options in ((), ('--yes',), ('--enable-updates', '--verify')):
                hits.clear()
                p = run(d, *options)
                assert 'Development checkout:' in p.stdout
                assert not hits
                assert (meta / 'consent').read_bytes() == b'1\n'
                assert (d / 'ftesurf64.exe').read_bytes() == before
            (meta / 'pending.json').write_bytes(b'pending sentinel, must not parse/promote\n')
            hits.clear()
            p = run(d, '--yes', good=False)
            assert 'unfinished release update in a development checkout' in p.stderr
            assert not hits and (d / 'ftesurf64.exe').read_bytes() == before
            assert (meta / 'pending.json').read_bytes() == b'pending sentinel, must not parse/promote\n'
            (meta / 'pending.json').unlink()
            (meta / 'ingame').mkdir()
            (meta / 'ingame/journal.json').write_bytes(b'in-game pending sentinel\n')
            hits.clear()
            p = run(d, '--yes', good=False)
            assert 'unfinished in-game update' in p.stderr and not hits
            results.append({'dev_marker': kind, 'zero_network': True, 'refusals_acted': 2})
        d = install('player')
        hits.clear()
        p = run(d, '--yes', good=False)
        assert hits == Counter({'/update.json': 1}), hits
        assert 'signed envelope missing payload' in p.stderr or 'missing field' in p.stderr
        results.append({'player_feed_request': 1, 'unsigned_refused': True})
    finally:
        server.shutdown()
        server.server_close()
        worker.join(5)
        assert not worker.is_alive()

    source = root / 'actor.c'
    source.write_text(ACTOR)
    actor = root / 'actor.exe'
    build = subprocess.run([str(a.cc), '-Os', '-s', '-static-libgcc', '-Wall', '-Wextra',
                            str(source), '-o', str(actor)], capture_output=True, text=True,
                           env=dict(os.environ, PATH=str(a.cc.resolve().parent) + os.pathsep + os.environ['PATH']))
    (root / 'actor-build.log').write_text(f'exit={build.returncode}\n' + build.stdout + build.stderr)
    assert build.returncode == 0 and not build.stderr, (build.returncode, build.stdout, build.stderr)

    k = c.WinDLL('kernel32', use_last_error=True)
    user = c.WinDLL('user32', use_last_error=True)
    def bind(name, args, result):
        f = getattr(k, name)
        f.argtypes, f.restype = args, result
        return f
    free = bind('FreeConsole', [], w.BOOL)
    attach = bind('AttachConsole', [w.DWORD], w.BOOL)
    window = bind('GetConsoleWindow', [], w.HWND)
    create = bind('CreateFileW', [w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p, w.DWORD, w.DWORD, w.HANDLE], w.HANDLE)
    close = bind('CloseHandle', [w.HANDLE], w.BOOL)
    mode = bind('GetConsoleMode', [w.HANDLE, c.POINTER(w.DWORD)], w.BOOL)
    write = bind('WriteConsoleInputW', [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD)], w.BOOL)
    open_process = bind('OpenProcess', [w.DWORD, w.BOOL, w.DWORD], w.HANDLE)
    wait = bind('WaitForSingleObject', [w.HANDLE, w.DWORD], w.DWORD)
    console_pids = bind('GetConsoleProcessList', [c.POINTER(w.DWORD), w.DWORD], w.DWORD)
    terminate = bind('TerminateProcess', [w.HANDLE, w.UINT], w.BOOL)
    user.IsWindow.argtypes, user.IsWindow.restype = [w.HWND], w.BOOL
    user.IsWindowVisible.argtypes, user.IsWindowVisible.restype = [w.HWND], w.BOOL
    class Char(c.Union):
        _fields_ = [('unicode', w.WCHAR), ('ascii', c.c_char)]
    class Key(c.Structure):
        _fields_ = [('down', w.BOOL), ('repeat', w.WORD), ('vk', w.WORD), ('scan', w.WORD), ('char', Char), ('control', w.DWORD)]
    class Data(c.Union):
        _fields_ = [('key', Key), ('pad', c.c_byte * 16)]
    class Record(c.Structure):
        _fields_ = [('type', w.WORD), ('event', Data)]
    free()  # This helper only, never a user's terminal or game.

    def handoff(name, exe, enter, expect_wait=False, batch=False):
        d = install(name)
        shutil.copyfile(actor, d / 'ftesurf64.exe')
        (d / '.ftesurf-updater').mkdir()
        (d / '.ftesurf-updater/consent').write_bytes(b'0\n')
        report, stop = d / 'actor-report.txt', d / 'stop'
        env = dict(os.environ, LAUNCH_TEST_REPORT=str(report), LAUNCH_TEST_STOP=str(stop))
        si = subprocess.STARTUPINFO()
        si.dwFlags, si.wShowWindow = subprocess.STARTF_USESHOWWINDOW, 0
        cmd = [str(exe.resolve()), '--dir', str(d), '--offline', '--', '+map', 'fixture_map', 'space value']
        if batch:
            shutil.copyfile(exe, d / 'ftesurf-launcher.exe')
            (d / 'ftesurf').mkdir()
            (d / 'ftesurf/fs_addons.txt').write_bytes(b'fixture\n')
            shutil.copyfile(Path(__file__).resolve().parent.parent / 'ftesurf.bat', d / 'ftesurf.bat')
            cmd = [os.environ['COMSPEC'], '/c', str(d / 'ftesurf.bat'), '+map', 'fixture_map', 'space value']
        p = subprocess.Popen(cmd, cwd=root, env=env, creationflags=0x10 | 0x40, startupinfo=si)
        (d / 'owner.json').write_text(json.dumps({'launcher_pid': p.pid, 'synthetic': True, 'hidden': True}))
        attached, hin, process = False, None, None
        child_handles = []
        try:
            def attached_now():
                nonlocal attached
                attached = bool(attach(p.pid))
                assert p.poll() is None, 'launcher exited before console attachment'
                return attached
            wait_for(attached_now, 'AttachConsole failed')
            hwnd = window()
            assert hwnd and not user.IsWindowVisible(hwnd), 'owned console must remain hidden'
            hin = create('CONIN$', 0xC0000000, 3, None, 3, 0, None)
            assert hin != c.c_void_p(-1).value
            if enter:
                def raw():
                    value = w.DWORD()
                    assert mode(hin, c.byref(value))
                    assert p.poll() is None
                    return value.value & 7 == 0
                wait_for(raw, 'interactive Enter prompt never acted')
                # This fresh hidden console belongs only to this fixture. Register
                # a batch-created launcher too, so a failure cannot orphan it.
                pids = (w.DWORD * 16)()
                count = console_pids(pids, len(pids))
                assert 0 < count <= len(pids)
                children = [pid for pid in pids[:count] if pid not in (os.getpid(), p.pid)]
                (d / 'console-children.json').write_text(json.dumps(children))
                for pid in children:
                    h = open_process(0x100001, False, pid)
                    assert h
                    child_handles.append(h)
                rec = Record()
                rec.type = 1
                rec.event.key.down, rec.event.key.repeat = True, 1
                rec.event.key.vk, rec.event.key.char.unicode = 0x0D, '\r'
                n = w.DWORD()
                assert write(hin, c.byref(rec), 1, c.byref(n)) and n.value == 1
            wait_for(report.exists, 'persistent actor did not start')
            lines = report.read_text().splitlines()
            pid = int(lines[0])
            process = open_process(0x100000, False, pid)
            assert process and wait(process, 0) == 258, 'actor is not live'
            assert Path(lines[2]).resolve() == d
            assert lines[3:] == ['-manifest', 'default.fmf', '+map', 'fixture_map', 'space value'], lines
            if expect_wait:
                time.sleep(.4)
                assert p.poll() is None, 'baseline did not reproduce waiting'
                stop.write_text('stop only this owned actor\n')
                assert p.wait(timeout=8) == 0
            else:
                assert p.wait(timeout=8) == 0, 'launcher did not exit after spawn'
                assert wait(process, 0) == 258, 'actor died when launcher exited'
                assert lines[1] == '0', 'actor inherited/created the launcher console'
            assert close(hin)
            hin = None
            assert free()
            attached = False
            wait_for(lambda: not user.IsWindow(hwnd), 'launcher-owned console stayed open')
            results.append({'case': name, 'enter_acted': enter, 'baseline_wait': expect_wait,
                            'console_closed': True, 'actor_survived': not expect_wait, 'args_cwd_exact': True})
        finally:
            if hin:
                assert close(hin)
            if attached:
                assert free()
            stop.write_text('stop only this owned actor\n')
            if process:
                assert wait(process, 8000) == 0, 'owned actor did not exit'
                assert close(process)
            for h in child_handles:
                if wait(h, 1000) == 258:
                    assert terminate(h, 1)  # Exact registered child in our fresh hidden console.
                    assert wait(h, 5000) == 0
                assert close(h)
            if p.poll() is None:
                p.kill()  # Only our exact registered launcher/fixture PID.
                p.wait(timeout=5)

    if a.control:
        handoff('baseline-waits', a.control, True, expect_wait=True)
    handoff('enter-detached', a.launcher, True)
    handoff('batch-enter-detached', a.launcher, True, batch=True)
    d = install('invalid-engine')
    p = subprocess.run([str(a.launcher), '--dir', str(d), '--offline', '--yes'],
                       capture_output=True, text=True, timeout=10)
    assert p.returncode != 0 and 'could not start FTESurf' in p.stderr
    results.append({'invalid_executable_spawn_refused': True})
    (root / 'result.json').write_text(json.dumps({'code': 0, 'cases': results}, indent=2))
    print('PASS development/network/refusal and persistent-actor Windows handoff controls')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
