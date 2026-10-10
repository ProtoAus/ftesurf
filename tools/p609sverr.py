#!/usr/bin/env python3
"""Patch 609: the Windows dedicated server's fatal-error path.

    python tools/p609sverr.py --control <pre-609 fteqwsv64.exe> --subject <609 fteqwsv64.exe>
    python tools/p609sverr.py --subject C:\\FTEQuake\\fteqwsv64.exe          (installed build only)

Two things are graded, one server per arm, no client, -plugin with a piped stdin.

SV_ERROR.  From the install root, `+map` naming a map nobody has: the server asks
cl_download_mapsrc, gets 404 and raises SV_Error.
    pre-609, log_enable 1   access violation 0xC0000005 and a crash record   (Log_String)
    pre-609, log_enable 0   exit 0 -- a fatal error reported as success
    609, either             exit 1, no crash record, the log ends on the SV_Error line

THE CRASH RECORD.  From a scratch basedir holding nothing but the install's manifest, so the
owner's crashaddr.txt is never written: a thread is started at address 5 inside the server.
    pre-609   the record goes to C:\\FTEQuake\\quakers\\crashaddr.txt, hard-coded
    609       it goes to <basedir>\\crashaddr.txt, names the exe, and honours -basedir;
              a basedir that cannot be written falls back to beside the exe

--respawn adds the SV_Error arms about what happens next. Before 609 Sys_Error waited 10 s
and CreateProcess()ed its own command line unless -noreset: a second server that is nobody's
child, every 13 s on a mistyped map. 609 makes that -autoreset's; without it a console gets
its 10 s and the process ends, and a stdin that is not a console ends at once. These arms
leave a copy running by design and stop it themselves, found by the arm's own log name on
its command line. The console arm opens a hidden console window for 13 s.

Each SV_Error arm makes one request for a nonexistent file to whatever cl_download_mapsrc names.
"""
import argparse
import ctypes
import hashlib
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = Path(r'C:\FTEQuake\quakers\crashaddr.txt')
AV = 0xC0000005
fails = []


def size(p):
    return p.stat().st_size if p.exists() else 0


def port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def check(name, ok, detail):
    print(f"{'PASS' if ok else 'FAIL'} {name}: {detail}")
    if not ok:
        fails.append(name)


def copies(tag):
    """Servers carrying this arm's own log name: the arm's child, or a copy it respawned."""
    out = subprocess.run(['powershell', '-NoProfile', '-Command',
                          "Get-CimInstance Win32_Process -Filter \"Name='fteqwsv64.exe'\" | "
                          "ForEach-Object { \"$($_.ProcessId)|$($_.CommandLine)\" }"],
                         capture_output=True, text=True).stdout
    return [int(line.split('|')[0]) for line in out.splitlines() if '|' in line and tag in line]


def sv_error(name, root, exe, log_enable, flags, want_rc, want_crash, console=False,
             want_secs=(0, 9), want_copy=False):
    """flags: extra arguments. console: give it a hidden console of its own as stdin."""
    tag = f'p609_{int(time.time() * 1000)}'
    log = root / 'ftesurf' / 'logs' / f'{tag}.log'
    files = (LEGACY, root / 'crashaddr.txt')
    args = [str(exe), *([] if console else ['-plugin']), *flags,
            '+set', 'cfg_save_auto', '0', '+log_enable', str(log_enable), '+log_dir', 'logs',
            '+log_name', tag, '-port', str(port()), '+sv_public', '0', '+map', 'no_such_map_zz']
    before = [size(f) for f in files]
    t0 = time.monotonic()
    if console:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0                          # SW_HIDE
        p = subprocess.Popen(args, cwd=root, startupinfo=si, creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        p = subprocess.Popen(args, cwd=root, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        rc = p.wait(45) & 0xffffffff
    except subprocess.TimeoutExpired:
        p.terminate()
        p.wait(10)
        rc = None
    secs = time.monotonic() - t0
    time.sleep(1.5)                                 # a respawned copy is started just before the exit
    left = copies(tag)
    for pid in left:                                # nobody's child: this arm made it, this arm ends it
        subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True)
    grew = sum(size(f) - b for f, b in zip(files, before))
    last = log.read_text(errors='replace').splitlines()[-1][20:] if log.exists() else ''
    ok = rc == want_rc and (grew > 0) == want_crash and want_secs[0] <= secs <= want_secs[1] \
        and bool(left) == want_copy
    if log_enable and rc is not None:
        # the server printed its own action (a respawned copy appends to the same log after it)
        ok = ok and 'SV_Error: ' in log.read_text(errors='replace')
    check(name, ok, f"exit {'STILL RUNNING' if rc is None else f'0x{rc:08x}'} in {secs:.1f} s, "
                    f"crash records +{grew} bytes, respawned copies {left or 'none'}, "
                    f"log ends: {last or '(no log)'}")
    time.sleep(0.5)
    if copies(tag):
        check(name + ' -- cleanup', False, f'still running: {copies(tag)}')
    return log


def fault(name, install, exe, where, legacy):
    """where: 'cwd', 'basedir' (a second dir named by -basedir) or 'exe' (basedir unwritable)."""
    scratch = Path(tempfile.mkdtemp(prefix='p609-'))
    try:
        base = scratch / 'cwd'
        other = scratch / 'other'
        for d in (base, other):
            (d / 'ftesurf').mkdir(parents=True)
            shutil.copy2(install / 'default.fmf', d / 'default.fmf')
        extra = {'cwd': [], 'basedir': ['-basedir', str(other)],
                 'exe': ['-basedir', str(scratch / 'missing' / 'deeper')]}[where]
        beside = exe.parent / 'crashaddr.txt'
        expect = {'cwd': base / 'crashaddr.txt', 'basedir': other / 'crashaddr.txt', 'exe': beside}[where]
        watched = [LEGACY, base / 'crashaddr.txt', other / 'crashaddr.txt', beside]
        before = [size(f) for f in watched]
        # -allowmapless: a dedicated server with no map SV_Errors by itself after 3 s.
        p = subprocess.Popen([str(exe), '-plugin', '-noreset', '-allowmapless', *extra,
                              '-port', str(port()), '+sv_public', '0', '+set', 'cfg_save_auto', '0'], cwd=base,
                             stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        rc = None
        try:
            rc = p.wait(5) & 0xffffffff             # it must still be up: the fault is ours to cause
            early = True
        except subprocess.TimeoutExpired:
            early = False
            # The release build has no way to fault on request (`crashme` is _DEBUG only, and
            # sv-dbg does not link in this fork), so start a thread at address 5 in our own
            # child. It faults there, and the engine's vectored handler runs like any other.
            k = ctypes.WinDLL('kernel32', use_last_error=True)
            k.CreateRemoteThread.restype = ctypes.c_void_p
            k.CreateRemoteThread.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                             ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
            if not k.CreateRemoteThread(int(p._handle), None, 0, 5, None, 0, None):
                print('   CreateRemoteThread failed:', ctypes.get_last_error())
            try:
                rc = p.wait(20) & 0xffffffff
            except subprocess.TimeoutExpired:
                p.terminate()
                p.wait(10)
        grew = {str(f): size(f) - b for f, b in zip(watched, before) if size(f) - b}
        want = LEGACY if legacy else expect
        ok = rc == AV and not early and list(grew) == [str(want)]
        if ok and not legacy:
            text = want.read_bytes()[-grew[str(want)]:].decode('ascii', 'replace')
            ok = f'exe {exe}' in text and 'fteqwsv64.exe+0x' in text
            if where == 'exe':
                # beside the exe is a real folder, not scratch: take back exactly this record
                with open(want, 'r+b') as f:
                    f.truncate(size(want) - grew[str(want)])
                if size(want) == 0:
                    want.unlink()
        short = {('...' + k[-44:] if len(k) > 47 else k): v for k, v in grew.items()}
        check(name, ok, f"exit {'none' if rc is None else f'0x{rc:08x}'}"
                        + (' BEFORE the fault was injected' if early else '')
                        + f", records grew: {short or 'nowhere'}"
                        + ('' if legacy or not ok else ', names the exe and its frames'))
    finally:
        shutil.rmtree(scratch, ignore_errors=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--control', type=Path, help='a server built before Patch 609')
    ap.add_argument('--subject', type=Path, required=True, help='a server with Patch 609')
    ap.add_argument('--root', type=Path, default=ROOT, help='install root (cwd of the SV_Error arms)')
    ap.add_argument('--respawn', action='store_true', help='also run the SV_Error arm without -noreset')
    a = ap.parse_args()
    for label, exe in (('control', a.control), ('subject', a.subject)):
        if exe:
            print(label, exe, hashlib.sha256(exe.read_bytes()).hexdigest()[:16])
    logs = []
    nr = ['-noreset']
    if a.control:
        logs.append(sv_error('control SV_Error, log_enable 1', a.root, a.control, 1, nr, AV, True))
        logs.append(sv_error('control SV_Error, log_enable 0', a.root, a.control, 0, nr, 0, False))
        fault('control fault: the hard-coded file', a.root, a.control, 'cwd', True)
    logs.append(sv_error('subject SV_Error, log_enable 1', a.root, a.subject, 1, nr, 1, False))
    logs.append(sv_error('subject SV_Error, log_enable 0', a.root, a.subject, 0, nr, 1, False))
    fault('subject fault: the record is in the cwd', a.root, a.subject, 'cwd', False)
    fault('subject fault: -basedir is honoured', a.root, a.subject, 'basedir', False)
    fault('subject fault: unwritable basedir, beside the exe', a.root, a.subject, 'exe', False)
    if a.respawn:
        if a.control:
            # the old default, visible only with logging off: with it on, the fault came first
            logs.append(sv_error('control, no flag, log_enable 0: it respawns', a.root, a.control, 0, [],
                                 0, False, want_secs=(10, 20), want_copy=True))
        logs.append(sv_error('subject, no flag, piped stdin: exits at once, no copy', a.root, a.subject,
                             1, [], 1, False))
        logs.append(sv_error('subject, no flag, a console: 10 s to read it, no copy', a.root, a.subject,
                             1, [], 1, False, console=True, want_secs=(10, 20)))
        logs.append(sv_error('subject, -autoreset: it respawns', a.root, a.subject, 1, ['-autoreset'],
                             1, False, want_secs=(10, 20), want_copy=True))
    for log in logs:
        if log.exists():
            log.unlink()
    print(f'{len(fails)} failed', fails or '')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
