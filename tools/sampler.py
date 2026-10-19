"""Sample one FTE client's main thread: where the CPU is, by function.

usage: python -I sampler.py <rig-dir-substring> <marker> <seconds> <exe.db> <hl2 plugin dll> [out.txt]

Waits for an ftesurf64/fteqw64 process whose command line contains the substring, then for
<marker> in its runlines_smoke.log, then suspends the busiest thread ~1000 times a second and
reads RIP. Self time: the function RIP is in (exe, hl2 plugin, or the module name). Caller:
for a sample outside the exe and the plugin (driver, CRT, kernel), the first return address
on the stack that lands in the exe or plugin text, so driver time is charged to its caller.
"""
import bisect
import collections
import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import subprocess
import sys
import time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)
winmm = ctypes.WinDLL("winmm")
NM = r"C:/msys64/ucrt64/bin/nm.exe"
PROCESS_ALL = 0x1F0FFF
THREAD_ALL = 0x1F03FF
CONTEXT_FLAGS = 0x100000 | 0x1 | 0x2      # AMD64 | CONTROL | INTEGER
TH32CS_SNAPTHREAD = 0x4


class THREADENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ThreadID", wt.DWORD),
                ("th32OwnerProcessID", wt.DWORD), ("tpBasePri", wt.LONG), ("tpDeltaPri", wt.LONG),
                ("dwFlags", wt.DWORD)]


class MODULEINFO(ctypes.Structure):
    _fields_ = [("lpBaseOfDll", ctypes.c_void_p), ("SizeOfImage", wt.DWORD), ("EntryPoint", ctypes.c_void_p)]


def find_process(sub):
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='ftesurf64.exe' or Name='fteqw64.exe'\" | "
          "Select-Object ProcessId,CommandLine | ConvertTo-Json")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout.strip()
    if not out:
        return None, None
    rows = json.loads(out)
    rows = rows if isinstance(rows, list) else [rows]
    for r in rows:
        cl = r.get("CommandLine") or ""
        if sub in cl:
            m = re.search(r'-basedir\s+"?([^"]+?)"?\s+-manifest', cl)
            return int(r["ProcessId"]), (m.group(1) if m else None)
    return None, None


def threads(pid):
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    te = THREADENTRY32()
    te.dwSize = ctypes.sizeof(te)
    out = []
    ok = k32.Thread32First(snap, ctypes.byref(te))
    while ok:
        if te.th32OwnerProcessID == pid:
            out.append(te.th32ThreadID)
        ok = k32.Thread32Next(snap, ctypes.byref(te))
    k32.CloseHandle(snap)
    return out


def thread_cpu(h):
    c, e, kt, ut = (wt.FILETIME() for _ in range(4))
    k32.GetThreadTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(kt), ctypes.byref(ut))
    return (ut.dwHighDateTime << 32 | ut.dwLowDateTime) + (kt.dwHighDateTime << 32 | kt.dwLowDateTime)


def modules(hp):
    arr = (ctypes.c_void_p * 1024)()
    need = wt.DWORD()
    psapi.EnumProcessModulesEx(hp, arr, ctypes.sizeof(arr), ctypes.byref(need), 3)
    out = []
    for i in range(need.value // ctypes.sizeof(ctypes.c_void_p)):
        name = ctypes.create_unicode_buffer(512)
        psapi.GetModuleFileNameExW(hp, ctypes.c_void_p(arr[i]), name, 512)
        mi = MODULEINFO()
        psapi.GetModuleInformation(hp, ctypes.c_void_p(arr[i]), ctypes.byref(mi), ctypes.sizeof(mi))
        out.append((mi.lpBaseOfDll, mi.SizeOfImage, os.path.basename(name.value).lower()))
    return sorted(out)


def symbols(path):
    """(addresses, names, image base) of text symbols, from nm -n."""
    out = subprocess.run([NM, "-n", path], capture_output=True, text=True).stdout
    addrs, names = [], []
    for line in out.splitlines():
        p = line.split()
        if len(p) == 3 and p[1] in "Tt":
            addrs.append(int(p[0], 16))
            names.append(p[2])
    ob = subprocess.run([NM.replace("nm.exe", "objdump.exe"), "-p", path], capture_output=True, text=True).stdout
    base = int(re.search(r"ImageBase\s+([0-9a-fA-F]+)", ob).group(1), 16)
    return addrs, names, base


def main():
    sub, marker, secs, exedb, plug = sys.argv[1:6]
    out_path = sys.argv[6] if len(sys.argv) > 6 else None
    secs = float(secs)
    t0 = time.time()
    pid = rig = None
    while time.time() - t0 < 300 and not pid:
        pid, rig = find_process(sub)
        if not pid:
            time.sleep(1)
    if not pid:
        print("no process"); return 2
    log = os.path.join(rig, "ftesurf", "logs", "runlines_smoke.log")
    while time.time() - t0 < 400:
        if os.path.exists(log) and marker in open(log, errors="replace").read():
            break
        time.sleep(0.5)
    else:
        print("no marker"); return 2
    hp = k32.OpenProcess(PROCESS_ALL, False, pid)
    mods = modules(hp)
    hs = {tid: k32.OpenThread(THREAD_ALL, False, tid) for tid in threads(pid)}
    a = {tid: thread_cpu(h) for tid, h in hs.items()}
    time.sleep(1.0)
    b = {tid: thread_cpu(h) for tid, h in hs.items()}
    tid = max(hs, key=lambda t: b[t] - a[t])
    busy = (b[tid] - a[tid]) / 1e7
    h = hs[tid]
    exe_syms = symbols(exedb)
    plug_syms = symbols(plug)
    exe_mod = next(m for m in mods if m[2] in ("ftesurf64.exe", "fteqw64.exe"))
    plug_mod = next((m for m in mods if m[2] == os.path.basename(plug).lower()), None)
    bases = [m[0] for m in mods]

    def name_of(addr):
        i = bisect.bisect_right(bases, addr) - 1
        if i < 0 or addr >= mods[i][0] + mods[i][1]:
            return None, "?"
        m = mods[i]
        for mod, syms in ((exe_mod, exe_syms), (plug_mod, plug_syms)):
            if mod and m[0] == mod[0]:
                va = addr - mod[0] + syms[2]
                j = bisect.bisect_right(syms[0], va) - 1
                return m[2], (syms[1][j] if j >= 0 else "?")
        return m[2], "[" + m[2] + "]"

    ctx_raw = ctypes.create_string_buffer(1232 + 16)
    ctx_addr = (ctypes.addressof(ctx_raw) + 15) & ~15
    SCAN = 65536
    stack = ctypes.create_string_buffer(SCAN)
    nread = ctypes.c_size_t()
    code = ctypes.create_string_buffer(8)
    callsite = {}

    def is_return(v):
        """v follows a call instruction: E8 rel32, FF 15 disp32, or FF /2 through a register."""
        r = callsite.get(v)
        if r is None:
            got = ctypes.c_size_t()
            r = False
            if k32.ReadProcessMemory(hp, ctypes.c_void_p(v - 7), code, 7, ctypes.byref(got)) and got.value == 7:
                b = code.raw[:7]
                r = (b[2] == 0xE8 or (b[1] == 0xFF and b[2] == 0x15)
                     or (b[5] == 0xFF and (b[6] & 0x38) == 0x10 and b[6] >= 0xC0)
                     or (b[4] == 0xFF and (b[5] & 0x38) == 0x10 and (b[5] & 0xC0) == 0x40)
                     or (b[1] == 0xFF and (b[2] & 0x38) == 0x10 and (b[2] & 0xC0) == 0x80))
            callsite[v] = r
        return r
    selfc, callc, n = collections.Counter(), collections.Counter(), 0
    winmm.timeBeginPeriod(1)
    end = time.time() + secs
    while time.time() < end:
        if k32.SuspendThread(h) == 0xFFFFFFFF:
            break
        ctypes.c_uint32.from_address(ctx_addr + 0x30).value = CONTEXT_FLAGS
        ok = k32.GetThreadContext(h, ctypes.c_void_p(ctx_addr))
        rip = ctypes.c_uint64.from_address(ctx_addr + 0xF8).value
        rsp = ctypes.c_uint64.from_address(ctx_addr + 0x98).value
        caller = None
        mod, fn = name_of(rip) if ok else (None, "?")
        if ok and mod not in (exe_mod[2], plug_mod[2] if plug_mod else None):
            got = ctypes.c_size_t()
            # Page by page: a read that runs off the stack's top fails whole.
            page = rsp
            for _ in range(SCAN // 4096):
                n_ = 4096 - (page & 4095)
                if not k32.ReadProcessMemory(hp, ctypes.c_void_p(page), stack, n_, ctypes.byref(got)):
                    break
                words = memoryview(stack.raw[:got.value - got.value % 8]).cast("Q")
                for v in words:
                    for m2 in (exe_mod, plug_mod):
                        if m2 and m2[0] + 0x1000 <= v < m2[0] + m2[1] and is_return(v):
                            caller = name_of(v)[1]
                            break
                    if caller:
                        break
                if caller:
                    break
                page += n_
        k32.ResumeThread(h)
        selfc[fn] += 1
        callc[(fn, caller) if caller else (fn, "")] += 1
        n += 1
        time.sleep(0.0008)
    winmm.timeEndPeriod(1)
    lines = ["pid %d thread %d (busiest: %.2f s CPU in 1 s), %d samples over %.1f s" % (pid, tid, busy, n, secs),
             "SELF (function or [module]), share of samples:"]
    for fn, c in selfc.most_common(45):
        lines.append("  %5.1f%%  %s" % (100.0 * c / n, fn))
    lines.append("OUTSIDE THE ENGINE, by the engine function nearest on the stack:")
    for (fn, caller), c in callc.most_common(60):
        if caller:
            lines.append("  %5.1f%%  %s  <-  %s" % (100.0 * c / n, fn, caller))
    text = "\n".join(lines)
    print(text)
    if out_path:
        open(out_path, "w").write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
