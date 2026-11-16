#!/usr/bin/env python3
"""Patch 1586: the .hid names patches below the journal.

One windowed client on a fresh basedir writes journal A, then this driver patches the running client the
way an outside tool would -- a jump and an int3 in the exe's code padding, a jump over an unused user32
input export, one exe import slot and one user32 export entry redirected, an executable region allocated --
and the client writes journal B. Graded on the files: A names nothing (overlay hooks on the two draw
functions excepted, printed), B names each planted patch with where it leads, its region count rose, and
hidcheck (this tree's and, with --oldreader, an older one) reads both with no fault. --control with a
pre-1586 build: no hook lines at all. Run under the rig lock.
"""
import argparse
import ctypes
import ctypes.wintypes as W
import hashlib
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p762keys import Client  # noqa: E402

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
psapi = ctypes.WinDLL('psapi', use_last_error=True)
k32.OpenProcess.restype = W.HANDLE
k32.VirtualAllocEx.restype = ctypes.c_void_p
k32.VirtualAllocEx.argtypes = [W.HANDLE, ctypes.c_void_p, ctypes.c_size_t, W.DWORD, W.DWORD]
k32.VirtualProtectEx.argtypes = [W.HANDLE, ctypes.c_void_p, ctypes.c_size_t, W.DWORD, ctypes.POINTER(W.DWORD)]
k32.WriteProcessMemory.argtypes = [W.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.ReadProcessMemory.argtypes = [W.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.FlushInstructionCache.argtypes = [W.HANDLE, ctypes.c_void_p, ctypes.c_size_t]
k32.GetModuleHandleW.restype = ctypes.c_void_p
k32.GetProcAddress.restype = ctypes.c_void_p
k32.GetProcAddress.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
k32.LoadLibraryW.restype = ctypes.c_void_p
k32.GetModuleHandleExW.argtypes = [W.DWORD, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
k32.GetModuleFileNameW.argtypes = [ctypes.c_void_p, W.LPWSTR, W.DWORD]
psapi.EnumProcessModulesEx.argtypes = [W.HANDLE, ctypes.POINTER(ctypes.c_void_p), W.DWORD, ctypes.POINTER(W.DWORD), W.DWORD]
psapi.GetModuleBaseNameW.argtypes = [W.HANDLE, ctypes.c_void_p, W.LPWSTR, W.DWORD]
NOPS = set(b'\x66\x2e\x0f\x1f\x84\x00\x40\x44\x80\x90')
DRAW = ('gdi32!SwapBuffers', 'opengl32!wglSwapBuffers')


def pe_sections(d):
    o = struct.unpack_from('<I', d, 0x3c)[0]
    nsec, optsz = struct.unpack_from('<H', d, o + 6)[0], struct.unpack_from('<H', d, o + 20)[0]
    opt = o + 24
    dirs = [struct.unpack_from('<II', d, opt + 112 + 8 * i) for i in range(16)]
    secs = []
    for i in range(nsec):
        so = opt + optsz + 40 * i
        vsz, va, rsz, raw = struct.unpack_from('<IIII', d, so + 8)
        secs.append((d[so:so + 8].rstrip(b'\0').decode('latin-1'), va, vsz, raw, rsz,
                     struct.unpack_from('<I', d, so + 36)[0]))
    return secs, dirs


def rva2off(secs, rva):
    for _n, va, vsz, raw, rsz, _c in secs:
        if va <= rva < va + rsz:
            return raw + rva - va
    raise ValueError(hex(rva))


def import_slot(d, dll, names):
    """(name, IAT rva) of the first of names the exe imports from dll."""
    secs, dirs = pe_sections(d)
    o = rva2off(secs, dirs[1][0])
    while True:
        oft, _ts, _fc, name, ft = struct.unpack_from('<IIIII', d, o)
        if not name:
            break
        if d[rva2off(secs, name):].split(b'\0')[0].decode().lower() == dll:
            i = 0
            while True:
                ent = struct.unpack_from('<Q', d, rva2off(secs, oft) + 8 * i)[0]
                if not ent:
                    break
                if not ent >> 63:
                    fn = d[rva2off(secs, ent) + 2:].split(b'\0')[0].decode()
                    if fn in names:
                        return fn, ft + 8 * i
                i += 1
        o += 20
    raise SystemExit('the exe imports none of %r from %s' % (names, dll))


def pads(d, count):
    """rva of `count` 15-byte code pads (a ret at a 16-byte boundary, then GCC's nops), 64+ bytes apart."""
    secs, _ = pe_sections(d)
    out = []
    for _n, va, vsz, raw, rsz, ch in secs:
        if not ch & 0x20000000:
            continue
        for i in range(raw, raw + min(vsz, rsz) - 16, 16):
            if d[i] == 0xc3 and all(b in NOPS for b in d[i + 1:i + 16]) and (not out or va + i - raw - out[-1] > 64):
                out.append(va + i - raw + 1)
                if len(out) == count:
                    return out
    raise SystemExit('no code pads found')


class Target:
    def __init__(self, pid):
        self.h = k32.OpenProcess(0x0008 | 0x0010 | 0x0020 | 0x0400, False, pid)
        if not self.h:
            raise SystemExit('OpenProcess %d failed: %d' % (pid, ctypes.get_last_error()))
        mods = (ctypes.c_void_p * 1024)()
        need = W.DWORD()
        psapi.EnumProcessModulesEx(self.h, mods, ctypes.sizeof(mods), ctypes.byref(need), 3)
        self.mods = {}
        for m in mods[:need.value // 8]:
            name = ctypes.create_unicode_buffer(260)
            psapi.GetModuleBaseNameW(self.h, m, name, 260)
            self.mods[name.value.lower()] = m
        self.exe = mods[0]

    def write(self, addr, data):
        old = W.DWORD()
        ok = k32.VirtualProtectEx(self.h, addr, len(data), 0x40, ctypes.byref(old))
        got = ctypes.c_size_t()
        ok = ok and k32.WriteProcessMemory(self.h, addr, data, len(data), ctypes.byref(got))
        k32.VirtualProtectEx(self.h, addr, len(data), old.value, ctypes.byref(old))
        k32.FlushInstructionCache(self.h, addr, len(data))
        if not ok or got.value != len(data):
            raise SystemExit('write at %x failed: %d' % (addr, ctypes.get_last_error()))

    def alloc(self):
        a = k32.VirtualAllocEx(self.h, None, 4096, 0x3000, 0x40)
        if not a:
            raise SystemExit('VirtualAllocEx failed: %d' % ctypes.get_last_error())
        return a


def user32_export_entry(name):
    """(address of name's AddressOfFunctions entry, rva of GetKeyState) in this process's user32.
    Not GetCursorPos: on Windows 11 it and GetPhysicalCursorPos are one function (one rva)."""
    base = k32.GetModuleHandleW('user32.dll') or k32.LoadLibraryW('user32.dll')
    mem = ctypes.string_at(base, 0x1000)
    o = struct.unpack_from('<I', mem, 0x3c)[0]
    erva = struct.unpack_from('<I', mem, o + 24 + 112)[0]
    ed = ctypes.string_at(base + erva, 40)
    nfn, nnames, afn, anames, aord = struct.unpack_from('<IIIII', ed, 20)
    found = {}
    for i in range(nnames):
        nr = struct.unpack('<I', ctypes.string_at(base + anames + 4 * i, 4))[0]
        n = ctypes.string_at(base + nr).decode()
        if n in (name, 'GetKeyState'):
            found[n] = struct.unpack('<H', ctypes.string_at(base + aord + 2 * i, 2))[0]
    entry = base + afn + 4 * found[name]
    other = struct.unpack('<I', ctypes.string_at(base + afn + 4 * found['GetKeyState'], 4))[0]
    if other == struct.unpack('<I', ctypes.string_at(entry, 4))[0]:
        raise SystemExit('%s and GetKeyState share an address: the redirect would change nothing' % name)
    return entry, other


def written(path, timeout=20):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        lines = path.read_bytes().rstrip().splitlines() if path.exists() else []
        if lines and lines[-1].startswith(b'end '):
            return
        time.sleep(0.1)
    raise SystemExit('not written: %s' % path)


def owner_of(addr):
    """The file name of the module holding addr in this process, lower case."""
    mod = ctypes.c_void_p()
    k32.GetModuleHandleExW(4 | 2, ctypes.c_void_p(addr), ctypes.byref(mod))
    path = ctypes.create_unicode_buffer(520)
    k32.GetModuleFileNameW(mod, path, 520)
    return Path(path.value).name.lower()


def follow(addr):
    """Where the engine's hop loop ends from addr, through jmp rel32/rel8 and jmp [rip+x]: (owner, jumps)."""
    jumps = 0
    while jumps < 4:
        b = ctypes.string_at(addr, 16)
        if b[0] == 0xe9:
            addr += 5 + struct.unpack('<i', b[1:5])[0]
        elif b[0] == 0xeb:
            addr += 2 + struct.unpack('<b', b[1:2])[0]
        elif b[:2] == b'\xff\x25':
            addr = struct.unpack('<Q', ctypes.string_at(addr + 6 + struct.unpack('<i', b[2:6])[0], 8))[0]
        elif b[:3] == b'\x48\xff\x25':
            addr = struct.unpack('<Q', ctypes.string_at(addr + 7 + struct.unpack('<i', b[3:7])[0], 8))[0]
        else:
            break
        jumps += 1
    return owner_of(addr), jumps


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--exe', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--oldreader', type=Path, help='an older tools/hidcheck.py: must not fault the new lines')
    ap.add_argument('--control', action='store_true', help='--exe is a pre-1586 build: no hook lines expected')
    a = ap.parse_args()
    a.exe, a.out = a.exe.resolve(), a.out.resolve()
    exe_bytes = a.exe.read_bytes()
    out = a.out / time.strftime('p1586-%Y%m%dT%H%M%S')
    base = out / 'client'
    game = base / 'ftesurf'
    for folder in ('cfg', 'glsl', 'scripts', 'gfx/fonts', 'gfx/ui'):
        if (a.content / 'ftesurf' / folder).is_dir():
            shutil.copytree(a.content / 'ftesurf' / folder, game / folder)
    for folder in ('logs', 'data'):
        (game / folder).mkdir(parents=True, exist_ok=True)
    for leaf in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
        shutil.copy2(a.content / 'ftesurf' / leaf, game / leaf)
    (base / 'default.fmf').write_text('FTEMANIFEST 1\nGAME FTESurfP1586Fixture\nBASEGAME ftesurf\n'
                                      'DISABLEHOMEDIR 1\nMAINCONFIG p1586cfg\n')
    (game / 'probe.cfg').write_text('\n'.join([
        'cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs', 'log_name probe',
        'log_readable 1', 'set cl_idlefps 0', 'set update_autocheck 0', 'set milk_enable 0', 'developer 1', 'log_developer 1']) + '\n')
    secs, _ = pe_sections(exe_bytes)
    textbytes = sum(min(vsz, rsz) for _n, _va, vsz, _raw, rsz, ch in secs if ch & 0x20000000)
    pad1, pad2 = pads(exe_bytes, 2)
    iatname, iatrva = import_slot(exe_bytes, 'user32.dll', ('MessageBoxA', 'MessageBoxW', 'GetClipboardData'))
    eat_entry, cursor_rva = user32_export_entry('GetPhysicalCursorPos')
    sleep = k32.GetProcAddress(k32.GetModuleHandleW('kernel32.dll'), b'Sleep')
    rib = k32.GetProcAddress(k32.GetModuleHandleW('user32.dll'), b'GetRawInputBuffer')
    gks = k32.GetProcAddress(k32.GetModuleHandleW('user32.dll'), b'GetKeyState')
    sleepdll, sleepj = follow(sleep)        # a finding through the region ends where Sleep's own jumps end
    gksdll, gksj = follow(gks)
    print('exe', a.exe, hashlib.sha256(exe_bytes).hexdigest()[:8], 'out', out, flush=True)
    print('plan: pads exe+%x exe+%x, iat %s at exe+%x, code bytes %d' % (pad1, pad2, iatname, iatrva, textbytes), flush=True)
    cl = Client(a.exe, base, 'probe.cfg')
    try:
        time.sleep(6)
        cl.send('in_journal_begin')
        time.sleep(0.5)
        cl.send('developer 1')
        cl.send('in_journal_end data/p1586_a.hid')
        written(game / 'data/p1586_a.hid')
        t = Target(cl.proc.pid)
        if t.mods.get('kernel32.dll') != k32.GetModuleHandleW('kernel32.dll') or \
                t.mods.get('user32.dll') != k32.GetModuleHandleW('user32.dll'):
            raise SystemExit('system DLL bases differ between this process and the client')
        region = t.alloc()
        t.write(region, b'\xff\x25\0\0\0\0' + struct.pack('<Q', sleep))
        jmp = b'\xff\x25\0\0\0\0' + struct.pack('<Q', region)
        t.write(t.exe + pad1, jmp)                                  # code: an outside jump in padding
        t.write(t.exe + pad2, b'\xcc')                              # code: a breakpoint
        t.write(rib, jmp)                                           # api: over an export the engine never calls
        t.write(t.exe + iatrva, struct.pack('<Q', region))          # iat: one slot redirected
        t.write(eat_entry, struct.pack('<I', cursor_rva))           # eat: the export now resolves elsewhere
        print('patched: region %x' % region, flush=True)
        cl.send('in_journal_begin')
        time.sleep(1.0)
        cl.send('in_journal_end data/p1586_b.hid')
        written(game / 'data/p1586_b.hid')
    finally:
        cl.stop()
    results = []

    def check(ok, name, detail=''):
        results.append(ok)
        print(('PASS ' if ok else 'FAIL ') + name + (' -- ' + detail if detail else ''), flush=True)

    files = {k: game / ('data/p1586_%s.hid' % k) for k in 'ab'}
    parsed = {}
    for k, hid in files.items():
        check(hid.exists(), 'journal %s written' % k.upper(), str(hid))
        if not hid.exists():
            return 1
        lines = hid.read_text(encoding='utf-8', errors='replace').splitlines()
        sums = [l.split()[1:] for l in lines if l.startswith('hooks ')]
        found = [[w.lower() if i == 3 else w for i, w in enumerate(l.split()[1:])] for l in lines if l.startswith('hook ')]
        skips = [l for l in lines if l.startswith('hookskip ')] + \
            (['(no hookscan header)'] if 'hookscan 1' not in lines and not a.control else []) + \
            (['(hookscan header)'] if 'hookscan 1' in lines and a.control else [])
        for l in [l for l in lines if l.startswith('hook')]:
            print('     %s: %s' % (k.upper(), l), flush=True)
        parsed[k] = (sums, found, skips)
    for m in re.finditer(r'hook scan: .*', cl.text()):
        print('     log: ' + m.group(0), flush=True)
    if a.control:
        check(all(not s and not f and not k for s, f, k in parsed.values()), 'control: no hook lines in either journal')
    else:
        sa, fa, ka = parsed['a']
        sb, fb, kb = parsed['b']
        check(len(sa) == 1 and len(sb) == 1, 'one hooks summary in each journal')
        if len(sa) != 1 or len(sb) != 1:
            return 1
        va, vb = [int(x) for x in sa[0]], [int(x) for x in sb[0]]
        check(len(va) == 10 and len(vb) == 10, 'the summary has ten fields')
        check(va[1] == textbytes and vb[1] == textbytes, 'the whole exe code was compared', '%d, %d of %d' % (va[1], vb[1], textbytes))
        check(va[2] >= 40 and va[3] >= 400, 'functions and slots were checked', 'funcs %d, slots %d' % (va[2], va[3]))
        check(va[7] >= 1 and vb[7] >= 1 and va[8] == 0 and vb[8] == 0 and va[6] == 0 and vb[6] == 0,
              'each journal saw a finished scan, nothing unread, no debugger', 'scans %d/%d unread %d/%d dbg %d/%d'
              % (va[7], vb[7], va[8], vb[8], va[6], vb[6]))
        check(not ka and not kb, 'nothing skipped, and the header promised the scan', '%r %r' % (ka, kb))
        check(all(f[0] == 'draw' for f in fa) and va[0] == len(fa), 'A: nothing below the journal (draw hooks aside)',
              '%d found' % va[0])
        via = ['windows', sleepdll, str(2 + sleepj)]
        planted = {
            'code jump': lambda f: f[0] == 'code' and f[1].startswith('exe+%x/' % pad1) and f[2:] == via,
            'code int3': lambda f: f == ['code', 'exe+%x/1' % pad2, 'int3', '-', '0'],
            'api jump': lambda f: f == ['api', 'user32!GetRawInputBuffer'] + via,
            'iat slot': lambda f: f == ['iat', 'user32!' + iatname] + via,
            'eat entry': lambda f: f == ['eat', 'user32!GetPhysicalCursorPos', 'windows', gksdll, str(1 + gksj)],
        }
        for name, test in planted.items():
            check(any(test(f) for f in fb), 'B names the %s' % name)
        extra = [f for f in fb if not any(t(f) for t in planted.values()) and f[0] != 'draw']
        check(not extra and vb[0] == len(fb), 'B: nothing else, and the count matches', '%r' % extra)
        check(vb[4] >= va[4] + 1 and vb[5] >= va[5] + 4, 'B: the allocated region is counted',
              'regions %d -> %d, KiB %d -> %d' % (va[4], vb[4], va[5], vb[5]))
    for label, reader in (('this tree', Path(__file__).resolve().parent / 'hidcheck.py'), ('older', a.oldreader)):
        if reader is None:
            continue
        for k, hid in files.items():
            p = subprocess.run([sys.executable, '-B', str(reader), '-v', str(hid)], capture_output=True, text=True)
            ok = p.returncode == 0 and ' 0 with faults' in p.stdout
            check(ok, 'hidcheck (%s) reads %s with no fault' % (label, k.upper()),
                  p.stdout.strip().splitlines()[-1] if p.stdout else p.stderr[-200:])
            for l in p.stdout.splitlines():
                if 'hook' in l.lower():
                    print('     reader: ' + l.strip(), flush=True)
    print('%d/%d checks passed' % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
