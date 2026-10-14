#!/usr/bin/env python3
"""Acted Windows resize/Yes-No/black-phase/four-worker launcher controls.

Fresh hidden consoles and signed loopback fixtures only. No real game, owner
terminal, release publication or player directory is used. Signing key is read
inside the existing signing helper and never printed or put in subprocess args.
"""
import argparse
from collections import Counter
import ctypes as c
from ctypes import wintypes as w
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src/release'))
import updatefeed


def wait_for(predicate, message, seconds=12):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(.025)
    raise AssertionError(message)


class Coord(c.Structure):
    _fields_ = [('X', w.SHORT), ('Y', w.SHORT)]
class Rect(c.Structure):
    _fields_ = [('Left', w.SHORT), ('Top', w.SHORT), ('Right', w.SHORT), ('Bottom', w.SHORT)]
class Info(c.Structure):
    _fields_ = [('size', Coord), ('cursor', Coord), ('attr', w.WORD), ('window', Rect), ('max', Coord)]
class Char(c.Union):
    _fields_ = [('unicode', w.WCHAR), ('ascii', c.c_char)]
class Cell(c.Structure):
    _fields_ = [('char', Char), ('attr', w.WORD)]
class Key(c.Structure):
    _fields_ = [('down', w.BOOL), ('repeat', w.WORD), ('vk', w.WORD), ('scan', w.WORD), ('char', Char), ('control', w.DWORD)]
class Data(c.Union):
    _fields_ = [('key', Key), ('pad', c.c_byte * 16)]
class Record(c.Structure):
    _fields_ = [('type', w.WORD), ('event', Data)]


class Startup(c.Structure):
    _fields_ = [('cb',w.DWORD),('reserved',w.LPWSTR),('desktop',w.LPWSTR),('title',w.LPWSTR),
                ('x',w.DWORD),('y',w.DWORD),('width',w.DWORD),('height',w.DWORD),
                ('chars_x',w.DWORD),('chars_y',w.DWORD),('fill',w.DWORD),('flags',w.DWORD),
                ('show',w.WORD),('reserved_size',w.WORD),('reserved_data',c.c_void_p),
                ('stdin',w.HANDLE),('stdout',w.HANDLE),('stderr',w.HANDLE)]
class StartupEx(c.Structure):
    _fields_ = [('startup',Startup),('attributes',c.c_void_p)]
class ProcessInfo(c.Structure):
    _fields_ = [('process',w.HANDLE),('thread',w.HANDLE),('pid',w.DWORD),('tid',w.DWORD)]


class PtyProcess:
    """A uniquely owned Windows Terminal-compatible ConPTY, not a shared window."""
    def __init__(self, args, cwd, log):
        self.k=c.WinDLL('kernel32',use_last_error=True)
        def bind(name,types,result):
            f=getattr(self.k,name);f.argtypes,f.restype=types,result;return f
        close=bind('CloseHandle',[w.HANDLE],w.BOOL)
        pipe=bind('CreatePipe',[c.POINTER(w.HANDLE),c.POINTER(w.HANDLE),c.c_void_p,w.DWORD],w.BOOL)
        create_pty=bind('CreatePseudoConsole',[Coord,w.HANDLE,w.HANDLE,w.DWORD,c.POINTER(w.HANDLE)],c.c_long)
        self.resize_pty=bind('ResizePseudoConsole',[w.HANDLE,Coord],c.c_long)
        self.close_pty=bind('ClosePseudoConsole',[w.HANDLE],None)
        init=bind('InitializeProcThreadAttributeList',[c.c_void_p,w.DWORD,w.DWORD,c.POINTER(c.c_size_t)],w.BOOL)
        update=bind('UpdateProcThreadAttribute',[c.c_void_p,w.DWORD,c.c_size_t,c.c_void_p,c.c_size_t,c.c_void_p,c.c_void_p],w.BOOL)
        delete=bind('DeleteProcThreadAttributeList',[c.c_void_p],None)
        create=bind('CreateProcessW',[w.LPCWSTR,w.LPWSTR,c.c_void_p,c.c_void_p,w.BOOL,w.DWORD,c.c_void_p,w.LPCWSTR,c.POINTER(StartupEx),c.POINTER(ProcessInfo)],w.BOOL)
        get_std=bind('GetStdHandle',[w.DWORD],w.HANDLE)
        set_std=bind('SetStdHandle',[w.DWORD,w.HANDLE],w.BOOL)
        self.get_exit=bind('GetExitCodeProcess',[w.HANDLE,c.POINTER(w.DWORD)],w.BOOL)
        self.wait_handle=bind('WaitForSingleObject',[w.HANDLE,w.DWORD],w.DWORD)
        self.terminate=bind('TerminateProcess',[w.HANDLE,w.UINT],w.BOOL)
        read=bind('ReadFile',[w.HANDLE,c.c_void_p,w.DWORD,c.POINTER(w.DWORD),c.c_void_p],w.BOOL)
        self.close_handle=close
        in_read,self.in_write,self.out_read,out_write=w.HANDLE(),w.HANDLE(),w.HANDLE(),w.HANDLE()
        assert pipe(c.byref(in_read),c.byref(self.in_write),None,0)
        assert pipe(c.byref(self.out_read),c.byref(out_write),None,0)
        self.pty=w.HANDLE()
        assert create_pty(Coord(80,30),in_read,out_write,0,c.byref(self.pty))==0
        assert close(in_read) and close(out_write)
        self.data=bytearray();self.log=log
        def drain():
            data=c.create_string_buffer(8192);n=w.DWORD()
            while read(self.out_read,data,len(data),c.byref(n),None) and n.value:
                self.data.extend(data.raw[:n.value])
        self.reader=threading.Thread(target=drain);self.reader.start()
        size=c.c_size_t()
        init(None,1,0,c.byref(size))
        attributes=c.create_string_buffer(size.value)
        assert init(attributes,1,0,c.byref(size))
        pi=ProcessInfo();thread_closed=False
        try:
            assert update(attributes,0,0x00020016,self.pty,c.sizeof(w.HANDLE),None,None),c.get_last_error()
            si=StartupEx();si.startup.cb=c.sizeof(si);si.attributes=c.cast(attributes,c.c_void_p)
            command=c.create_unicode_buffer(subprocess.list2cmdline(args))
            # The harness itself has redirected API pipes. Do not let Windows
            # copy those valid std handles over the child's ConPTY handles.
            std_ids=[(-10)&0xffffffff,(-11)&0xffffffff,(-12)&0xffffffff]
            saved=[get_std(i) for i in std_ids]
            try:
                for i in std_ids:assert set_std(i,None)
                assert create(args[0],command,None,None,False,0x00080000,None,str(cwd),c.byref(si),c.byref(pi)),c.get_last_error()
            finally:
                for i,h in zip(std_ids,saved):assert set_std(i,h)
            self.handle,self.pid=pi.process,pi.pid
            assert close(pi.thread)
            thread_closed=True
        except BaseException:
            # A launch failure must not leave our ConPTY or drain thread alive.
            if pi.process:
                assert self.terminate(pi.process,1)
                assert self.wait_handle(pi.process,5000)==0
                assert close(pi.process)
            if pi.thread and not thread_closed:assert close(pi.thread)
            self.close_pty(self.pty)
            assert close(self.in_write)
            self.reader.join(5);assert not self.reader.is_alive()
            assert close(self.out_read)
            self.log.write_bytes(self.data)
            raise
        finally:
            delete(attributes)

    def poll(self):
        code=w.DWORD();assert self.get_exit(self.handle,c.byref(code))
        return None if code.value==259 else code.value
    def wait(self,timeout):
        status=self.wait_handle(self.handle,int(timeout*1000))
        if status==258:raise subprocess.TimeoutExpired('owned ConPTY fixture',timeout)
        assert status==0;return self.poll()
    def kill(self):
        assert self.terminate(self.handle,1)
    def resize(self,width,height):
        assert self.resize_pty(self.pty,Coord(width,height))==0
    def close(self):
        self.close_pty(self.pty)
        assert self.close_handle(self.in_write)
        self.reader.join(5);assert not self.reader.is_alive(),'owned ConPTY output did not drain'
        assert self.close_handle(self.out_read) and self.close_handle(self.handle)
        self.log.write_bytes(self.data)


class Console:
    def __init__(self, exe, install, feed, root, extra=()):
        self.k = c.WinDLL('kernel32', use_last_error=True)
        def bind(name, args, result):
            f = getattr(self.k, name)
            f.argtypes, f.restype = args, result
            return f
        self.free = bind('FreeConsole', [], w.BOOL)
        attach = bind('AttachConsole', [w.DWORD], w.BOOL)
        create = bind('CreateFileW', [w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p, w.DWORD, w.DWORD, w.HANDLE], w.HANDLE)
        self.create = create
        self.close = bind('CloseHandle', [w.HANDLE], w.BOOL)
        self.info = bind('GetConsoleScreenBufferInfo', [w.HANDLE, c.POINTER(Info)], w.BOOL)
        self.read = bind('ReadConsoleOutputW', [w.HANDLE, c.POINTER(Cell), Coord, Coord, c.POINTER(Rect)], w.BOOL)
        self.mode = bind('GetConsoleMode', [w.HANDLE, c.POINTER(w.DWORD)], w.BOOL)
        self.write = bind('WriteConsoleInputW', [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD)], w.BOOL)
        window = bind('GetConsoleWindow', [], w.HWND)
        user = c.WinDLL('user32', use_last_error=True)
        user.IsWindowVisible.argtypes, user.IsWindowVisible.restype = [w.HWND], w.BOOL
        self.free()  # Only this helper's attachment, never an owner terminal.
        self.p = PtyProcess([str(exe), '--dir', str(install), '--allow-insecure',
                             '--manifest-url', feed, *extra], root, install/'console-vt.log')
        (install / 'fixture-process.json').write_text(json.dumps({'pid': self.p.pid, 'synthetic_hidden': True}))
        self.hin = self.hout = None
        self.stop = threading.Event()
        self.raw_failures = []
        self.monitor = None
        try:
            wait_for(lambda: attach(self.p.pid), 'cannot attach owned console')
            assert window() and not user.IsWindowVisible(window()), 'fixture console must be hidden'
            self.hin = create('CONIN$', 0xC0000000, 3, None, 3, 0, None)
            self.hout = create('CONOUT$', 0xC0000000, 3, None, 3, 0, None)
            assert self.hin != c.c_void_p(-1).value and self.hout != c.c_void_p(-1).value
        except BaseException:
            self.cleanup()
            raise

    def raw(self):
        value = w.DWORD()
        assert self.mode(self.hin, c.byref(value)), c.get_last_error()
        return value.value & 7

    def watch_raw(self):
        assert self.raw() == 0
        def watch():
            while not self.stop.wait(.01):
                value = w.DWORD()
                if self.mode(self.hin, c.byref(value)) and value.value & 7:
                    self.raw_failures.append(value.value)
        self.monitor = threading.Thread(target=watch)
        self.monitor.start()

    def stop_watch(self):
        self.stop.set()
        if self.monitor:
            self.monitor.join(3)
            assert not self.monitor.is_alive()
        assert not self.raw_failures, ('interactive phase dropped raw session', self.raw_failures)

    def refresh_output(self):
        # CONOUT$ names the currently active buffer, not the pre-TUI buffer.
        h = self.create('CONOUT$', 0xC0000000, 3, None, 3, 0, None)
        assert h != c.c_void_p(-1).value
        if self.hout:
            assert self.close(self.hout)
        self.hout = h

    def screen(self):
        self.refresh_output()
        info = Info()
        assert self.info(self.hout, c.byref(info)), c.get_last_error()
        width = info.window.Right - info.window.Left + 1
        height = info.window.Bottom - info.window.Top + 1
        cells = (Cell * (width * height))()
        rect = Rect(info.window.Left, info.window.Top, info.window.Right, info.window.Bottom)
        assert self.read(self.hout, cells, Coord(width, height), Coord(0, 0), c.byref(rect)), c.get_last_error()
        text = '\n'.join(''.join(cells[y * width + x].char.unicode or ' ' for x in range(width)) for y in range(height))
        return width, height, cells, text

    def contains(self, text):
        assert self.p.poll() is None, 'fixture launcher exited before expected page: ' + text
        return text in self.screen()[3]

    def resize(self, width, height):
        # Default Terminal hosts ignore classic SetConsoleWindowInfo; resize the
        # actual uniquely owned ConPTY using its explicit Windows Terminal API.
        self.p.resize(width,height)
        wait_for(lambda:self.screen()[:2]==(width,height),'ConPTY resize did not ACT')

    def key(self, vk, char='\0'):
        record = Record()
        record.type = 1
        record.event.key.down, record.event.key.repeat = True, 1
        record.event.key.vk, record.event.key.char.unicode = vk, char
        count = w.DWORD()
        assert self.write(self.hin, c.byref(record), 1, c.byref(count)) and count.value == 1

    def snapshot(self, output, phase, full_logo=True):
        width, height, cells, text = self.screen()
        assert self.raw() == 0
        assert all((cell.attr >> 4) & 15 == 0 for cell in cells), 'nonblack background: ' + phase
        if full_logo:
            assert '███████╗██╗   ██╗██████╗ ███████╗' in text, 'full logo prematurely collapsed: ' + phase
        assert '\\\\?\\' not in text and 'CONFIRM' not in text and 'LIVE TRANSFERS' not in text
        output.write_text(json.dumps({'phase': phase, 'width': width, 'height': height,
                                      'text': text, 'black_background': True, 'raw': 0}, ensure_ascii=False), encoding='utf-8')
        return text

    def finish(self, expected):
        self.stop_watch()
        code = self.p.wait(timeout=15)
        assert code == expected, (code, expected)
        assert self.raw() == 7, 'raw input mode was not restored at exit'
        self.cleanup()
        vt = self.p.log.read_bytes()
        assert vt.count(b'\x1b[?1049h') == 1 and vt.count(b'\x1b[?1049l') == 1, 'phase re-entered or leaked the alternate screen'

    def cleanup(self):
        self.stop.set()
        if self.monitor:
            self.monitor.join(3)
        for h in [self.hin, self.hout]:
            if h and h != c.c_void_p(-1).value:
                assert self.close(h)
        self.hin = self.hout = None
        self.free()
        if self.p.poll() is None:
            self.p.kill()  # Only exact registered synthetic launcher PID, never owner processes.
            self.p.wait(timeout=5)
        self.p.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--launcher', type=Path, required=True)
    ap.add_argument('--control', type=Path)
    ap.add_argument('--work-root', type=Path, required=True)
    ap.add_argument('--seed-file', type=Path, default=Path('C:/FTESurf-private/keys/ftesurf-updates/seed'))
    a = ap.parse_args()
    assert os.name == 'nt'
    root = a.work_root.resolve()
    root.mkdir(exist_ok=False)
    (root / 'OWNER.md').write_text('Synthetic signed Windows launcher UI controls; no real game/player data.\n')
    stage = root / 'stage'
    stage.mkdir()
    contents = {'default.fmf': b'synthetic manifest\n', 'ftesurf64.exe': b'inert non-executable synthetic fixture\n',
                'ftesurf/menu.dat': b'M' * (1024 * 1024), 'ftesurf/csprogs.dat': b'C' * (1024 * 1024),
                'ftesurf/qwprogs.dat': b'Q' * (1024 * 1024)}
    for path, data in contents.items():
        p = stage / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    hits = Counter()
    lock = threading.Lock()
    stats = {'active': 0, 'max': 0, 'sent': 0}
    feed_seen, feed_release, object_release = threading.Event(), threading.Event(), threading.Event()
    serverdir = root / 'feed'

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            with lock:
                hits[self.path] += 1
            p = serverdir / self.path.lstrip('/')
            if not p.is_file():
                self.send_error(404)
                return
            obj = '/objects/' in self.path
            if obj:
                with lock:
                    stats['active'] += 1
                    # Grade requests frozen before response bodies: a provider
                    # callback can linger after the client already received its
                    # final byte, which is not an extra active download worker.
                    if not object_release.is_set():
                        stats['max'] = max(stats['max'], stats['active'])
                assert object_release.wait(20), 'fixture objects were not released'
            else:
                feed_seen.set()
                assert feed_release.wait(20), 'fixture feed was not released'
            try:
                data = p.read_bytes()
                self.send_response(200)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                for offset in range(0, len(data), 16384):
                    self.wfile.write(data[offset:offset+16384])
                    self.wfile.flush()
                    if obj:
                        with lock:
                            stats['sent'] += min(16384, len(data)-offset)
                        time.sleep(.015)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass  # Deliberate cancellation; active-count/drain oracle still acts below.
            finally:
                if obj:
                    with lock:
                        stats['active'] -= 1

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    worker = threading.Thread(target=server.serve_forever)
    base = f'http://127.0.0.1:{server.server_port}'
    updatefeed.build({'win64': stage}, serverdir, '0.1.25', [base], a.seed_file.read_bytes())
    (serverdir/'update-bad.json').write_bytes(b'{"invalid":"unsigned UI fixture"}')
    worker.start()
    results = []
    current = None
    def fresh(name):
        d = root / name
        d.mkdir()
        return d
    def reset():
        wait_for(lambda: stats['active'] == 0, 'server fixture did not drain')
        with lock:
            hits.clear()
            stats.update(active=0, max=0, sent=0)
        feed_seen.clear()
        feed_release.clear()
        object_release.clear()
    try:
        d = fresh('decline-empty')
        current = Console(a.launcher.resolve(), d, base + '/update.json', root)
        current.resize(60, 24)
        wait_for(lambda: current.contains('Download World of Surf?'), 'empty-install prompt missing')
        current.snapshot(d/'prompt.json', 'initial choice')
        current.key(0x28)
        wait_for(lambda: current.contains('› No'), 'Down did not select No')
        current.key(0x0D, '\r')
        current.finish(0)
        current = None
        assert not hits and not (d/'.ftesurf-updater/consent').exists()
        assert all(not (d/p).exists() for p in contents)
        results.append({'case':'decline-empty','down_enter_no':True,'zero_requests':True,'no_game_files':True})
        reset()
        d = fresh('install-and-decline-play')
        current = Console(a.launcher.resolve(), d, base + '/update.json', root)
        current.resize(80, 30)
        wait_for(lambda: current.contains('Download World of Surf?'), 'first-install prompt missing')
        current.watch_raw()
        current.snapshot(d/'prompt-80x30.json','initial choice')
        current.key(0x28)
        wait_for(lambda: current.contains('› No'), 'Down did not act')
        current.key(0x26)
        wait_for(lambda: current.contains('› Yes'), 'Up did not act')
        current.resize(60, 24)
        time.sleep(.3)
        text = current.snapshot(d/'prompt-60x24.json','resized initial choice')
        assert 'services see your IP' in text and 'proto.bar / dl.proto.bar' in text
        current.key(0x0D, '\r')
        wait_for(feed_seen.is_set,'first Yes did not request signed feed')
        wait_for(lambda: current.contains('Checking for updates'), 'checking phase missing')
        current.resize(40, 20)
        time.sleep(.3)
        current.snapshot(d/'check-40x20.json','resized checking')
        feed_release.set()
        wait_for(lambda: stats['active']==4, 'production launcher did not ACT four simultaneous requests')
        wait_for(lambda: current.contains('Downloading World of Surf'), 'download phase missing')
        current.resize(60, 24)
        time.sleep(.3)
        text = current.snapshot(d/'download-60x24.json','four downloads awaiting provider')
        assert '04  ' in text and 'Downloaded' in text
        current.resize(80, 30)
        time.sleep(.3)
        current.snapshot(d/'download-80x30.json','expanded downloading')
        object_release.set()
        wait_for(lambda: stats['sent'] > 32768, 'byte transfers did not ACT')
        current.resize(40, 20)
        time.sleep(.3)
        current.snapshot(d/'download-40x20.json','small active downloading')
        wait_for(lambda: current.contains('Play World of Surf?'), 'downloaded install did not reach play choice')
        current.resize(60, 24)
        time.sleep(.3)
        current.snapshot(d/'play-60x24.json','ready choice, same styling')
        current.stop_watch()
        current.key(0x28)
        wait_for(lambda: current.contains('› No'), 'ready No selection did not act')
        current.key(0x0D, '\r')
        current.finish(0)
        current = None
        assert hits['/update.json']==1 and sum(n for p,n in hits.items() if '/objects/' in p)==5
        assert stats['max']==4
        assert all((d/p).read_bytes()==data for p,data in contents.items())
        assert not (d/'.ftesurf-updater/pending.json').exists()
        results.append({'case':'fresh-install','one_download_yes':True,'up_down_acted':True,'max_parallel_objects':4,
                        'resize_matrix':['80x30','60x24','40x20'],'all_phases_black':True,'continuous_raw_session':True,'single_alternate_screen_pair':True,
                        'signed_files_match':True,'play_no_acted':True})
        reset()
        feed_release.set()
        object_release.set()
        d = fresh('cancel-transfer')
        current = Console(a.launcher.resolve(), d, base+'/update.json', root, ('--yes',))
        current.resize(60,24)
        wait_for(lambda: current.contains('Downloading World of Surf'), 'cancel arm did not download')
        wait_for(lambda: stats['sent']>32768, 'cancel before ACTUAL bytes is not a control')
        current.snapshot(d/'before-cancel.json','active transfer cancellation')
        current.key(0x1B, '\x1b')
        current.finish(1)
        current=None
        wait_for(lambda: stats['active']==0, 'cancelled object providers did not drain')
        assert all(not (d/p).exists() for p in contents)
        assert not (d/'.ftesurf-updater/pending.json').exists()
        parts=list((d/'.ftesurf-updater/download').rglob('*.part'))
        assert parts and any(p.stat().st_size>0 for p in parts)
        results.append({'case':'cancel-transfer','real_bytes_before_cancel':True,'no_live_promotion':True,'parts_retained':True,'providers_drained':True})
        reset()
        feed_release.set()
        object_release.set()
        d=fresh('styled-error')
        current=Console(a.launcher.resolve(),d,base+'/update-bad.json',root)
        current.resize(60,24)
        wait_for(lambda:current.contains('Download World of Surf?'),'error arm initial choice missing')
        current.watch_raw()
        current.key(0x0D,'\r')
        wait_for(lambda:current.contains('Unable to continue'),'styled signature error missing')
        current.snapshot(d/'error.json','signature error, same styling')
        current.stop_watch()
        current.key(0x0D,'\r')
        current.finish(1)
        current=None
        assert hits['/update-bad.json']==1 and not any('/objects/' in p for p in hits)
        assert all(not (d/p).exists() for p in contents)
        results.append({'case':'styled-error','unsigned_feed_refused':True,'error_black_same_header':True,
                        'continuous_raw_session':True,'enter_closes':True,'no_objects_or_game_files':True})
        if a.control:
            reset()
            feed_release.set()
            d=fresh('prior-three-worker-control')
            p=subprocess.Popen([str(a.control.resolve()),'--dir',str(d),'--yes','--no-launch','--allow-insecure','--manifest-url',base+'/update.json'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            (d/'fixture-process.json').write_text(json.dumps({'pid':p.pid,'synthetic':True}))
            try:
                wait_for(lambda:stats['active']==3,'old launcher did not ACT three requests')
                time.sleep(.3)
                assert stats['max']==3
                object_release.set()
                stdout,stderr=p.communicate(timeout=20)
                (d/'run.log').write_text(stdout+stderr)
                assert p.returncode==0 and stats['max']==3
            finally:
                object_release.set()
                if p.poll() is None:
                    p.kill();p.wait(5)
            results.append({'case':'prior-control','max_parallel_objects':3,'four_worker_oracle_rejects_prior':True})
        report={'code':0,'cases':results,'limits':'Uniquely owned native ConPTY with actual ResizePseudoConsole, not a physical Windows Terminal window or real game session.'}
        (root/'result.json').write_text(json.dumps(report,indent=2))
        print('PASS real Windows choice/resize/black/continuous-session/four-worker/cancel controls')
        print(json.dumps(results,indent=2))
    finally:
        if current:
            current.cleanup()
        feed_release.set();object_release.set()
        server.shutdown();server.server_close();worker.join(5)
        assert not worker.is_alive()


if __name__=='__main__':
    main()
