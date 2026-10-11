#!/usr/bin/env python3
"""p653box.py -- the Steam link box: its look, its cursor and the click on its address.

    python tools/p653box.py --progs <build dir> --output-dir <owned dir>

p615link's rig (a lobby, a surfd in this process, a client with -nobrowse so
the engine prints the address it was asked to open).  Keys and clicks are
window messages on the client's own queue, as a device's arrive: nothing here
is a console command but the screenshots.  THE DESKTOP'S POINTER IS MOVED for
each click and put back (class Mouse): about two seconds a run.  What is graded is what the box and
the engine printed themselves (the box's lines are developer prints):

  P  the prompt that comes up by itself draws, and has NOT taken the mouse
  T  nor does a typed code's box (`link`, then a letter): a console line can
     raise that one, and it must not freeze the view
  G  Enter starts the link: the box takes the mouse and says where its address is
  C  a click on the address: the box says it was clicked there, and the ENGINE
     is asked for the page a second time (a click is a press to it)
  D  two more clicks a moment apart: the box still says a page opened
  B  the mouse's other button runs no bind while the box has the cursor
  O  a click beside the box gives the mouse back, and Enter takes it again
  N  a browser signs in; the number is typed a digit at a time; between no
     digit and four, nothing moves on screen outside the four cells
  L  Enter links it

Screenshots of each state go to --output-dir: LOOK AT THEM.  A build without
Patch 653 fails G, C and O (run it against the installed progs to see).
"""
import argparse
import pathlib
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import p615link as L


class Mouse(object):
    """Left clicks for the client's window, at a point of its client area.

    The click is a window message, as the keys are.  WHERE it lands is not: with
    a free cursor the engine reads the desktop's pointer (GetCursorPos), so the
    real pointer is put there for the click and put back by restore().  The
    owner's pointer jumps for about two seconds a run."""
    def __init__(self, keys):
        import ctypes
        from ctypes import wintypes
        self.c, self.w = ctypes, wintypes
        self.u, self.hwnd = keys.u, keys.hwnd
        # The game's window is in physical pixels; an unaware process is told a
        # scaled size (1536 for 1920) and would aim short.
        self.u.SetProcessDPIAware()
        rect = wintypes.RECT()
        self.u.GetClientRect(self.hwnd, ctypes.byref(rect))
        self.size = (rect.right, rect.bottom)
        self.was = wintypes.POINT()
        self.u.GetCursorPos(ctypes.byref(self.was))
        self.moved = False

    def move(self, x, y):
        p = self.w.POINT(int(x), int(y))
        self.u.ClientToScreen(self.hwnd, self.c.byref(p))
        self.u.SetCursorPos(p.x, p.y)
        self.moved = True
        time.sleep(0.35)                        # frames for the engine to read it

    def click(self, x, y, right=False, settle=0.25):
        self.move(x, y)
        lparam = (int(y) << 16) | (int(x) & 0xFFFF)
        down, up, held = (0x0204, 0x0205, 2) if right else (0x0201, 0x0202, 1)  # WM_?BUTTONDOWN/UP, MK_?BUTTON
        if not self.u.PostMessageW(self.hwnd, down, held, lparam):
            raise RuntimeError("PostMessage failed")
        time.sleep(0.06)
        self.u.PostMessageW(self.hwnd, up, 0, lparam)
        time.sleep(settle)

    def restore(self):
        if self.moved:
            self.u.SetCursorPos(self.was.x, self.was.y)
            self.moved = False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--progs", type=pathlib.Path, required=True)
    ap.add_argument("--content", type=pathlib.Path, default=pathlib.Path("C:/FTESurf"))
    ap.add_argument("--client", type=pathlib.Path)
    ap.add_argument("--server", type=pathlib.Path, default=pathlib.Path("C:/FTEQuake/fteqwsv64.exe"))
    ap.add_argument("--output-dir", type=pathlib.Path)
    ap.add_argument("--map", default="bhop_eazy")
    a = ap.parse_args()
    a.client = a.client or a.content / "ftesurf64.exe"
    a.progs = a.progs.resolve()
    a.output_dir = (a.output_dir or pathlib.Path(tempfile.gettempdir())).resolve()
    a.foreign_code = a.refuse_address = a.taken = a.receipt = False

    rig, gd, junctions = L.build_rig(a)
    print("rig", rig)
    server = client = web = None
    held = L.clipboard()
    try:
        gport = None
        for cand in range(27621, 27640):
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                try:
                    probe.bind(("127.0.0.1", cand))
                    gport = cand
                    break
                except OSError:
                    continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            hport = probe.getsockname()[1]
        a.hport = hport
        web, _db = L.start_surfd(rig, hport, "127.0.0.1")
        common = ["-basedir", str(rig), "-manifest", str(rig / "default.fmf"),
                  "+set", "cfg_save_auto", "0", "+set", "log_enable", "1", "+set", "log_dir", "logs"]
        server = subprocess.Popen(
            [str(a.server), *common, "+set", "log_name", "p653sv", "+set", "developer", "1",
             "+set", "sv_public", "0", "+set", "sv_port", str(gport),
             "+set", "sv_guidkey", "p653-probe", "+set", "sv_maxrate", "0",
             "+set", "sv_maxdownloadrate", "0",
             "+set", "lobby_master", "http://127.0.0.1:%d" % hport,
             "+set", "lobby_master_key", L.KEY, "+set", "lobby_master_rate", "30",
             "+map", a.map], cwd=a.content, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(4)
        if server.poll() is not None:
            raise RuntimeError("the server exited at start (code %s)" % server.returncode)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 4                      # shown, focus left alone (a minimised one may not draw)
        client = subprocess.Popen(
            [str(a.client), "-plugin", "-nobrowse", *common, "+set", "log_name", "p653cl",
             "-window", "-nosound", "+set", "con_savehistory", "0", "+set", "cl_idlefps", "0",
             "+set", "cl_maxfps", "100", "+set", "rate", "2000000", "+set", "drate", "5000000",
             # the box's own lines are developer prints, which the log leaves out unless asked
             "+set", "developer", "1", "+set", "log_developer", "1"],
            cwd=a.content, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, startupinfo=si)

        def send(line):
            client.stdin.write(line.encode("ascii") + b"\n")
            client.stdin.flush()

        def shot(name):
            """-> the kept file, or None if nothing was drawn."""
            send("screenshot " + name)
            end = time.time() + 15
            while time.time() < end:
                found = list((gd / "screenshots").glob(name + ".*"))
                if found:
                    time.sleep(0.8)
                    from PIL import Image
                    if len(Image.open(found[0]).convert("RGB").getcolors(1 << 22) or [0, 0]) < 2:
                        return None
                    kept = a.output_dir / (name + found[0].suffix)
                    shutil.copyfile(found[0], kept)
                    return kept
                time.sleep(0.5)
            return None

        cl = L.Log(gd / "logs/p653cl.log")
        time.sleep(8)
        up = None
        for _ in range(3):
            send("connect 127.0.0.1:%d" % gport)
            up = cl.wait("FTESurf CSQC loaded", 40)
            if up:
                break
        L.check("the client connected and its game code loaded", bool(up), True)
        if not up:
            return 1
        send("closemenu")
        send("con_notifytime 0")                # developer lines are for the log, not the pictures
        send("con_notifylines 0")
        send("in_focusgrab 0")                  # a window that is not in front still reads the pointer
        keys = L.Keys(client.pid)
        mouse = Mouse(keys)

        def said(text):
            return cl.text().count(text)

        prompt = cl.wait("press Enter to link your Steam account", 30)
        time.sleep(1.5)
        L.check("P  the prompt came up by itself, draws, and has not taken the mouse",
                (bool(prompt), bool(shot("p653_1_prompt")), said("steam: the box has the mouse")),
                (True, True, 0))

        keys.press("esc")                       # later
        time.sleep(0.5)
        send("link")
        opened = cl.wait("link box open", 10)
        time.sleep(0.5)
        keys.type("a")                          # a code's first letter: the box is now the keyboard's
        time.sleep(0.8)
        L.check("T  a typed code's box draws its cells and does not take the mouse",
                (bool(opened), bool(shot("p653_1b_code")), said("steam: the box has the mouse")),
                (True, True, 0))
        keys.press("esc")
        time.sleep(3.2)                         # the lobby's gap between one player's asks
        send("link")
        time.sleep(0.8)
        send('bind mouse2 "echo gamekey-m2"')
        cancels = said("link cancelled")
        keys.press("enter")
        m = cl.wait(L.GO, 20)
        at = cl.wait(r"steam: the address is drawn at ([\d.]+),([\d.]+) ([\d.]+)x([\d.]+) "
                     r"on a ([\d.]+)x([\d.]+) screen", 10)
        time.sleep(0.5)
        L.check("G  Enter starts the link: the box takes the mouse and says where its address is",
                (bool(m), bool(at), said("steam: the box has the mouse"), said("acct_browse: https://")),
                (True, True, 1, 1))
        if not at:
            return 1
        lx, ly, lw, lh, sx, sy = [float(v) for v in at.groups()]
        # the box's units to the window's client pixels
        fx, fy = mouse.size[0] / sx, mouse.size[1] / sy
        ax, ay = (lx + lw * 0.5) * fx, (ly + lh * 0.5) * fy
        print("  window %dx%d, screen %gx%g, the address centre at client %d,%d" %
              (mouse.size[0], mouse.size[1], sx, sy, ax, ay))
        shot("p653_2_wait")
        try:
            mouse.move(ax, ay)
            shot("p653_3_hover")
            mouse.click(ax, ay)
        finally:
            mouse.restore()
        hit = cl.wait(r"steam: the address was clicked at ([\d.]+),([\d.]+): browser (\d), clipboard (\d)", 8)
        time.sleep(0.5)
        inside = bool(hit) and lx <= float(hit.group(1)) < lx + lw and ly <= float(hit.group(2)) < ly + lh
        L.check("C  a click on the address: the box says so, at a point inside it, the ENGINE is "
                "asked for the page a second time, and the mouse stays the box's",
                (bool(hit), inside, said("acct_browse: https://"), said("steam: a click beside the box")),
                (True, True, 2, 0))
        time.sleep(1.0)                         # the engine opens one page a second

        try:
            mouse.click(ax, ay, settle=0.1)     # D: two clicks inside the engine's one second
            mouse.click(ax, ay)
        finally:
            mouse.restore()
        time.sleep(0.4)
        marks = re.findall(r"the address was clicked at [\d.]+,[\d.]+: browser (\d)", cl.text())
        print("  the engine was asked for the page %d times in all, for 1 Enter and 3 clicks"
              % said("acct_browse: https://"))
        L.check("D  two more clicks a moment apart: every one of the box's lines still says a page opened",
                marks, ["1", "1", "1"])
        try:
            mouse.click(ax, ay + 60, right=True)    # B: the other button, on the box
            mouse.click(6, 300, right=True)         # ...and beside it
        finally:
            mouse.restore()
        time.sleep(0.4)
        L.check("B  the mouse's other button runs no bind while the box has the cursor, and "
                "gives nothing back", (said("gamekey-m2"), said("steam: a click beside the box")), (0, 0))

        try:
            mouse.click(6, 6)                   # the window's corner: beside the box
        finally:
            mouse.restore()
        cl.wait("steam: a click beside the box", 8)
        time.sleep(0.5)
        L.check("O  a click beside the box gives the mouse back; the start is still waited on",
                (said("steam: a click beside the box"), said("steam: the box does not have the mouse"),
                 said("link cancelled") - cancels), (1, 1, 0))
        try:
            mouse.click(ax, ay)                 # the game's click now, not the box's
        finally:
            mouse.restore()
        time.sleep(0.6)
        L.check("O  CONTROL without the cursor a click on the same pixels is not the box's",
                said("steam: the address was clicked"), 3)
        try:
            mouse.click(6, 300, right=True)     # the game's button again
        finally:
            mouse.restore()
        time.sleep(0.4)
        L.check("B  CONTROL with the mouse given back, that button's bind runs", said("gamekey-m2"), 1)
        browses = said("acct_browse: https://")
        time.sleep(1.0)                         # the engine opens one page a second
        keys.press("enter")
        time.sleep(0.8)
        L.check("O  Enter opens the page again and takes the mouse again",
                (said("steam: the box has the mouse"), said("acct_browse: https://") - browses), (2, 1))

        number = L.code_on(L.browser(hport, L.SIDS[0], "198.51.100.9", L.address(m)))
        asked = cl.wait(r"link this game to \S+\? Type the number from the sign-in page", 15)
        time.sleep(1.0)                         # the question ignores keys for 0.6 s
        s0 = shot("p653_4_number0")
        keys.type(number[:2])
        time.sleep(0.4)
        shot("p653_5_number2")
        keys.type(number[2:])
        time.sleep(0.4)
        s4 = shot("p653_6_number4")
        moved = None
        if s0 and s4:
            from PIL import Image, ImageChops
            w, h = Image.open(s0).size
            # The link box's own rectangle (it is centred, from 56% down), so the
            # HUD's moving parts are not in the comparison.
            crop = (int(w * 0.36), int(h * 0.55), int(w * 0.64), int(h * 0.80))
            box = ImageChops.difference(Image.open(s0).convert("RGB").crop(crop),
                                        Image.open(s4).convert("RGB").crop(crop)).getbbox()
            if box:
                # what changed must be a short band round the box's middle: the four cells
                moved = (round((crop[0] + (box[0] + box[2]) / 2) / w, 2), box[2] - box[0] < 0.1 * w,
                         box[3] - box[1] < 0.06 * h)
            print("  between no digit and four, inside the box's rectangle the changed pixels span", box)
        L.check("N  the browser's number is asked for, and typing it changes only a narrow band "
                "at the screen's middle (centre, narrow, short)",
                (bool(asked), len(number), moved), (True, 4, (0.5, True, True)))
        keys.press("enter")
        linked = bool(cl.wait("now linked to ", 20))
        time.sleep(0.6)
        shot("p653_7_linked")
        L.check("L  Enter links it, and the mouse is the game's again when the box has ended",
                (linked, said("steam: the box does not have the mouse") >= 2), (True, True))
        keys.press("back")
        L.check("no VM error or unknown command in the client's log",
                [w for w in ("Unknown command", "QC VM error", "Cannot call", "stack overflow")
                 if w in cl.text()], [])
        try:
            send("quit")
            client.wait(timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            pass
        return 1 if L.FAILED else 0
    finally:
        for process in (client, server):
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
        if web is not None:
            web.shutdown()
        if "mouse" in locals():
            mouse.restore()
        now = L.clipboard()
        if held is not None and now is not None and now != held and "board/link?k=" in now:
            L.clipboard(held)
            print("\nthe desktop's clipboard held one of this rig's addresses; put back what was there")
        for path in junctions:
            if not path.lstat().st_file_attributes & 0x400:
                raise RuntimeError("refusing removal: not our junction: %s" % path)
            path.rmdir()
        print("\nrig kept (junctions removed):", rig)
        if L.FAILED:
            print("%d FAILURE(S):" % len(L.FAILED))
            for f in L.FAILED:
                print("  " + f)


if __name__ == "__main__":
    raise SystemExit(main())
