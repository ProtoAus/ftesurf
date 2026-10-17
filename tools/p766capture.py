"""Patch 766: does display capture see the borderless window?

    python tools/p766capture.py --cap 0|1 [--exe C:/path/to/fteqw64.exe] [--tag t] [--out dir]

Runs cfg/test/p766capture.cfg (borderless, view turning) with +set vid_borderless_capture
<cap>, and captures the primary monitor through Desktop Duplication (ffmpeg ddagrab = OBS
display capture's "DXGI Desktop Duplication") and Windows Graphics Capture (gfxcapture =
its "Windows 10 1903 and up"), with the game made the foreground window first -- NVIDIA
only takes an active window off the compositor, so a background window captures either
way and proves nothing.
  on1  as launched               cap 1: a window one row past the screen, live
                                 cap 0, or a build before 766: exactly the screen, no frames
  rest minimized and restored    the same again (the alt-tab path)
A frame is black (YMAX <= 20), stale (YDIF < 0.05: the turning view did not change it) or
live. A failed capture is restarted until the phase's seconds are used, as OBS does; one
that delivers nothing is killed. The exe is started as argv[0] ftesurf64.exe, so it reads
the install's manifest wherever it lives; cwd is C:\\FTESurf.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import os
import re
import subprocess
import sys
import time

ROOT = r"C:\FTESurf"
LOG = os.path.join(ROOT, "ftesurf", "logs", "p766capture.log")
FF = r"C:\tools\ffmpeg\bin\ffmpeg.exe"
SECS = 6

user32 = ctypes.windll.user32
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))     # per-monitor v2: physical pixels


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]


def find_hwnd(pid):
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        p = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd):
            r = wt.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            found.append(((r.right - r.left) * (r.bottom - r.top), hwnd))
        return True
    user32.EnumWindows(cb, 0)
    return max(found)[1] if found else None


def foreground(hwnd):
    a = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
    b = ctypes.windll.kernel32.GetCurrentThreadId()
    user32.AttachThreadInput(b, a, True)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    user32.AttachThreadInput(b, a, False)


def state(hwnd):
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(mi)
    hmon = user32.MonitorFromWindow(hwnd, 2)
    user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
    m = mi.rcMonitor
    return {"rect": (r.left, r.top, r.right, r.bottom), "monitor": (m.left, m.top, m.right, m.bottom),
            "zoomed": bool(user32.IsZoomed(hwnd)), "iconic": bool(user32.IsIconic(hwnd)),
            "foreground": user32.GetForegroundWindow() == hwnd, "hmon": hmon}


def capture(out, tag, src, hmon, hwnd):
    t0 = time.time()
    fg0 = user32.GetForegroundWindow() == hwnd
    inp = ("ddagrab=output_idx=0:framerate=30:draw_mouse=0" if src == "dda"
           else "gfxcapture=hmonitor=%d:max_framerate=30:capture_cursor=0" % hmon)
    png = tag + ".png"
    if os.path.exists(os.path.join(out, png)):
        os.remove(os.path.join(out, png))
    frames, errs, attempts, hung = [], [], 0, 0
    while time.time() - t0 < SECS - 0.5:
        left = SECS - (time.time() - t0)
        stats = "%s_%d.txt" % (tag, attempts)
        attempts += 1
        if os.path.exists(os.path.join(out, stats)):
            os.remove(os.path.join(out, stats))
        graph = ("[0]hwdownload,format=bgra,split[a][b];"
                 "[a]format=yuv420p,signalstats,metadata=print:file=%s[s];"
                 "[b]select='eq(n\\,15)'[p]" % stats)
        cmd = [FF, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", inp, "-t", "%.2f" % left,
               "-filter_complex", graph, "-map", "[s]", "-f", "null", "-",
               "-map", "[p]", "-frames:v", "1", "-y", png]
        p = subprocess.Popen(cmd, cwd=out, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        try:
            _, err = p.communicate(timeout=left + 3)
        except subprocess.TimeoutExpired:
            p.kill()
            _, err = p.communicate()
            hung += 1
        errs += [re.sub(r" @ [0-9A-Fa-f]+", "", e) for e in err.strip().splitlines() if "non monotonically" not in e]
        cur = {}
        if os.path.exists(os.path.join(out, stats)):
            for line in open(os.path.join(out, stats)):
                if line.startswith("frame:"):
                    if cur:
                        frames.append(cur)
                    cur = {}
                m = re.match(r"lavfi\.signalstats\.(YMAX|YDIF)=([\d.]+)", line)
                if m:
                    cur[m.group(1)] = float(m.group(2))
            if cur:
                frames.append(cur)
            os.remove(os.path.join(out, stats))
        if hung:
            break
        time.sleep(0.1)
    pattern = "".join("B" if f.get("YMAX", 255) <= 20 else "s" if i and f.get("YDIF", 99) < 0.05 else "L"
                      for i, f in enumerate(frames))
    fg = fg0 and user32.GetForegroundWindow() == hwnd
    edges = ""
    if os.path.exists(os.path.join(out, png)):
        from PIL import Image                   # one frame at 1:1: are the screen's first and last rows drawn?
        im = Image.open(os.path.join(out, png)).convert("L")
        w, h = im.size
        row = lambda y: sum(im.getpixel((x, y)) for x in range(0, w, 4)) / len(range(0, w, 4))
        edges = "  %dx%d rows: top %.1f, 2nd %.1f, last-1 %.1f, last %.1f" % (w, h, row(0), row(1), row(h - 2), row(h - 1))
    print("  %-8s %-3s frames %3d  live %3d  stale %3d  black %3d  attempts %2d  hung %d  foreground %s"
          % (tag, src, len(frames), pattern.count("L"), pattern.count("s"), pattern.count("B"),
             attempts, hung, fg) + edges, flush=True)
    for e in sorted(set(errs))[:3]:
        print("           ffmpeg (x%d): %s" % (errs.count(e), e), flush=True)
    return pattern


def wait_marker(p, marker, timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if p.poll() is not None:
            raise RuntimeError("the client exited before '%s'" % marker)
        if os.path.exists(LOG) and marker in open(LOG, errors="replace").read():
            return
        time.sleep(0.3)
    raise RuntimeError("no '%s' in %d s" % (marker, timeout))


def phase(p, out, tag, wgc):
    hwnd = find_hwnd(p.pid)
    foreground(hwnd)
    time.sleep(2)
    s = state(hwnd)
    print("%s window %s" % (tag, {k: v for k, v in s.items() if k != "hmon"}), flush=True)
    capture(out, tag, "dda", s["hmon"], hwnd)
    if wgc:
        capture(out, tag + "w", "wgc", s["hmon"], hwnd)
    return hwnd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", required=True, choices=("0", "1"))
    ap.add_argument("--exe", default=os.path.join(ROOT, "ftesurf64.exe"))
    ap.add_argument("--tag", default="p766")
    ap.add_argument("--out", default=os.path.join(ROOT, "ftesurf", "screenshots"))
    ap.add_argument("--set", nargs=2, action="append", default=[], metavar=("CVAR", "VALUE"),
                    help="another +set before the cfg, e.g. --set vid_srgb 2 (expect no overhang)")
    a = ap.parse_args()
    if os.path.exists(LOG):
        os.remove(LOG)
    extra = [x for name, value in a.set for x in ("+set", name, value)]
    p = subprocess.Popen(["ftesurf64.exe", "+set", "vid_borderless_capture", a.cap] + extra + ["+exec", "test/p766capture.cfg"],
                         executable=a.exe, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("launched %s cap %s %s pid %d" % (a.exe, a.cap, " ".join(extra), p.pid), flush=True)
    try:
        wait_marker(p, "OBSCAP on1", 180)
        hwnd = phase(p, a.out, a.tag + "_on1", True)
        user32.ShowWindow(hwnd, 6)                  # SW_MINIMIZE
        time.sleep(1)
        user32.ShowWindow(hwnd, 9)                  # SW_RESTORE, as a taskbar click
        phase(p, a.out, a.tag + "_rest", True)
        p.wait(timeout=90)
    except RuntimeError as e:
        print(e)
    finally:
        if p.poll() is None:
            p.kill()
            print("killed the client")
        else:
            print("client exit code 0x%08x" % (p.returncode & 0xffffffff))
    print("--- client log")
    for line in open(LOG, errors="replace"):
        if re.search(r"(?i)setting .*mode|vid_borderless_capture|vid_srgb|colour buffer|unknown command|couldn't load plugin|"
                     r"\[focus\]|OBSCAP", line):
            print("  " + line.rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
