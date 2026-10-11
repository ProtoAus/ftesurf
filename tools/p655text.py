#!/usr/bin/env python3
"""p655text.py -- a menu text field's caret, selection, copy and cut; and that nothing pastes (Patch 655).

    python tools/p655text.py --progs <build dir> --output-dir <owned dir>

A private rig with no server: the menu's name screen (`ui_name screen`) and
its one field.  Keys are window messages on the client's own queue, the way a
keyboard's arrive; the mouse is `ui_hover`, `ui_mouse` and `ui_click`.  THE
DESKTOP'S CLIPBOARD IS WRITTEN, and put back at the end.  Graded on the
field's own text and caret (`ui_name field`), sui's selection and modifiers
(`ui_name sel`) and what the desktop's clipboard then holds; four screenshots
are kept for LOOKING AT.

A CHORD IS ITS CONTROL CODE, which Windows makes from the keyboard's real
state: a posted Ctrl is not one.  So copy, cut and select-all are fed as
`ui_key c down 3` and the like (the console's key, with the code a keyboard
would have given).  For the one press that must be a keyboard's own, Ctrl+V,
this process's input state is attached to the game's (class Chord), so the
engine's own ToUnicode makes the 22.

  N  NOTHING PASTES: not a keyboard's Ctrl+V, not Shift+Insert, not a fed 22;
     and neither VM's code names the engine's clipboard_get at all.
"""
import argparse
import pathlib
import re
import shutil
import subprocess
import tempfile
import time

import p615link as L

VK = {"tab": 0x09, "left": 0x25, "right": 0x27, "end": 0x23, "home": 0x24, "ins": 0x2D,
      "enter": 0x0D, "shift": 0x10, "ctrl": 0x11, "alt": 0x12, "v": 0x56}
EXT = {"left", "right", "end", "home", "ins"}


class Chord(object):
    """Ctrl held as the game's thread sees a keyboard hold it: this thread's input
    state is attached to the window's and the Ctrl bits set in it, for one press."""
    def __init__(self, keys):
        import ctypes
        self.c, self.keys = ctypes, keys
        self.k32 = ctypes.windll.kernel32
        self.tid = keys.u.GetWindowThreadProcessId(keys.hwnd, None)

    def ctrl(self, post, name):
        c, u = self.c, self.keys.u
        me = self.k32.GetCurrentThreadId()
        if not u.AttachThreadInput(me, self.tid, True):
            raise RuntimeError("AttachThreadInput failed")
        try:
            state = (c.c_ubyte * 256)()
            u.GetKeyboardState(state)
            saved = bytes(state)
            state[0x11] = state[0xA2] = 0x80        # VK_CONTROL, VK_LCONTROL
            u.SetKeyboardState(state)
            post("ctrl", True)
            post(name, True)
            post(name, False)
            post("ctrl", False)
            time.sleep(0.25)
            u.SetKeyboardState((c.c_ubyte * 256).from_buffer_copy(saved))
        finally:
            u.AttachThreadInput(me, self.tid, False)
        time.sleep(0.2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--progs", type=pathlib.Path, required=True)
    ap.add_argument("--content", type=pathlib.Path, default=pathlib.Path("C:/FTESurf"))
    ap.add_argument("--client", type=pathlib.Path)
    ap.add_argument("--output-dir", type=pathlib.Path)
    a = ap.parse_args()
    a.client = a.client or a.content / "ftesurf64.exe"
    a.progs = a.progs.resolve()
    a.output_dir = (a.output_dir or pathlib.Path(tempfile.gettempdir())).resolve()
    a.output_dir.mkdir(parents=True, exist_ok=True)

    rig, gd, junctions = L.build_rig(a)
    print("rig", rig)
    (gd / "data").mkdir(exist_ok=True)
    (gd / "data" / "consent.txt").write_text("FTESURF-CONSENT 1\nversion 1\naccepted 20261012-000000\n")
    held = L.clipboard()
    client = None
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 4
        client = subprocess.Popen(
            [str(a.client), "-plugin", "-nobrowse", "-basedir", str(rig),
             "-manifest", str(rig / "default.fmf"), "+set", "cfg_save_auto", "0",
             "+set", "log_enable", "1", "+set", "log_dir", "logs", "+set", "log_name", "p655text",
             "-window", "-nosound", "+set", "con_savehistory", "0", "+set", "cl_idlefps", "0",
             "+set", "cl_maxfps", "60", "+set", "vid_fullscreen", "0"],
            cwd=a.content, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, startupinfo=si)
        log = L.Log(gd / "logs/p655text.log")

        def send(line, wait=0.4):
            client.stdin.write(line.encode("ascii") + b"\n")
            client.stdin.flush()
            time.sleep(wait)

        time.sleep(12)
        keys = L.Keys(client.pid)

        def post(name, down):
            vk = VK[name]
            lparam = 1 | (keys.u.MapVirtualKeyW(vk, 0) << 16) | ((1 << 24) if name in EXT else 0)
            if not down:
                lparam |= (1 << 30) | (1 << 31)
            keys.u.PostMessageW(keys.hwnd, 0x0100 if down else 0x0101, vk, lparam)
            time.sleep(0.05)

        def press(*names):
            for n in names[:-1]:
                post(n, True)
            post(names[-1], True)
            post(names[-1], False)
            for n in reversed(names[:-1]):
                post(n, False)
            time.sleep(0.3)

        def state():
            """(the field's text, its caret, sui's anchor) by the menu's own two prints."""
            n = log.text().count("ui_name: sel ")
            send("ui_name field", 0.15)
            send("ui_name sel", 0.15)
            log.count("ui_name: sel ", n + 1, 5)
            text = log.text()
            f = re.findall(r'ui_name: field "(.*)" caret (-?\d+)', text)
            s = re.findall(r"ui_name: sel (-?\d+) mods (\d+)", text)
            if not f or not s:
                return None
            return f[-1][0], int(f[-1][1]), int(s[-1][0])

        def mods():
            send("ui_name sel", 0.3)
            return re.findall(r"ui_name: sel -?\d+ mods (\d+)", log.text())[-1:]

        def shot(name):
            send("screenshot " + name, 1.2)

        def fed(name, code):
            send("ui_key %s down %d" % (name, code), 0.4)

        def aim(dx):
            """Park sui's cursor on the field, `dx` from its middle; -> where that is."""
            n = log.text().count("ui_hover: ")
            send("ui_hover @nm_field %d 0" % dx, 0.3)
            log.count("ui_hover: ", n + 1, 5)
            at = re.findall(r"ui_hover: (-?[\d.]+) (-?[\d.]+)", log.text())
            return at[-1] if at else None

        send("ui_name screen", 1.5)
        press("tab")                            # the screen's one field takes the keyboard
        keys.type("surfer")
        time.sleep(0.4)
        L.check("T  TAB gives the field the keyboard and typing lands", state(), ("surfer", 6, -1))
        shot("p655_1_typed")                    # a caret and a focus ring, by TAB alone

        press("shift", "left")
        press("shift", "left")
        L.check("S  Shift+Left twice selects the last two", state(), ("surfer", 4, 6))
        shot("p655_2_two_selected")
        L.clipboard("not what was copied")
        fed("c", 3)
        L.check("C  Ctrl+C puts them on the desktop's clipboard and leaves the field alone "
                "(a screenshot's stall later, the selection is still held)",
                (L.clipboard(), state()), ("er", ("surfer", 4, 6)))
        press("end")
        L.check("E  End without Shift ends the selection", state(), ("surfer", 6, -1))

        L.clipboard("PASTED")
        Chord(keys).ctrl(post, "v")             # a keyboard's own Ctrl+V: control code 22
        real = state()
        press("shift", "ins")
        fed("v", 22)
        dats = {n: (a.progs / n).read_bytes() for n in ("menu.dat", "csprogs.dat")}
        L.check("N  NOTHING PASTES: a keyboard's Ctrl+V, Shift+Insert and a fed Ctrl+V leave the field "
                "as it was, and neither VM's code names clipboard_get (control: both name clipboard_set)",
                (real, state(), [n for n, b in sorted(dats.items()) if b"clipboard_get" in b],
                 [n for n, b in sorted(dats.items()) if b"clipboard_set" in b]),
                (("surfer", 6, -1), ("surfer", 6, -1), [], ["csprogs.dat", "menu.dat"]))

        fed("a", 1)
        L.check("A  Ctrl+A selects everything", state(), ("surfer", 6, 0))
        shot("p655_3_all_selected")
        keys.type("xyz")
        time.sleep(0.3)
        L.check("R  typing replaces the selection", state(), ("xyz", 3, -1))
        press("ctrl", "v")
        L.check("V  a Ctrl this VM saw and a V that arrives as a letter (a Ctrl whose release was "
                "missed looks so) is typed", state(), ("xyzv", 4, -1))
        press("shift", "home")
        L.check("H  Shift+Home selects back to the start", state(), ("xyzv", 0, 4))
        L.clipboard("not what was cut")
        fed("x", 24)
        L.check("X  Ctrl+X cuts it to the clipboard", (state(), L.clipboard()), (("", 0, -1), "xyzv"))

        keys.type("dragme")
        time.sleep(0.4)
        aim(-229)                               # the text's origin: the field is 472 wide
        send("ui_mouse down")
        aim(-196)
        st = state()
        send("ui_mouse up")
        end = state()
        L.check("D  a press at the text's start and a drag right selects from 0 to under the cursor",
                (st is not None and st[0] == "dragme" and st[2] == 0 and 1 <= st[1] <= 6, st == end),
                (True, True))
        shot("p655_4_dragged")
        aim(-196)
        send("ui_mouse down")
        send("ui_mouse up")
        st = state()
        L.check("K  a click is a caret and no selection",
                st is not None and st[2] == -1 and 1 <= st[1] <= 5, True)
        under = st and st[1]
        press("end")
        at = aim(-196)
        send("ui_click %s %s" % at, 0.5)        # down and up between two draws: a tap
        L.check("Q  a press and release inside one frame still puts the caret under it",
                (state(), bool(under)), (("dragme", under, -1), True))
        press("end")
        aim(-196)                               # the pointer rests on the field...
        post("enter", True)                     # ...and a confirm key is held: a press to sui, not a drag
        time.sleep(0.5)
        during = state()
        post("enter", False)
        time.sleep(0.4)
        L.check("J  Enter held with the pointer on the field moves no caret and selects nothing",
                (during, state()), (("dragme", 6, -1), ("dragme", 6, -1)))

        send("ui_strip_test screen main", 1.0)  # the field goes (the name screen comes back empty)...
        post("shift", True)                     # ...and Shift is down before it has the keyboard again
        send("ui_name screen", 1.0)
        press("tab")
        keys.type("abc")                        # the desktop's keyboard has no Shift: small letters
        time.sleep(0.3)
        post("left", True)
        post("left", False)
        time.sleep(0.3)
        st = state()
        post("shift", False)
        L.check("Z  a field that takes the keyboard under a Shift already held selects with it at once",
                st, ("abc", 2, 3))

        post("shift", True)                     # down, and the menu sees it...
        seen = mods()
        send("togglemenu", 0.8)                 # ...closed with it held
        post("shift", False)                    # the release is the game's
        send("togglemenu", 0.8)
        L.check("M  a modifier held when the menu closed is not held when it opens again",
                (seen, mods()), (["1"], ["0"]))
        L.check("no VM error, unknown command or sui warning in the log",
                [w for w in ("Unknown command", "QC VM error", "Cannot call", "sui warning",
                             "stack overflow") if w in log.text()], [])
        try:
            send("quit")
            client.wait(timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            pass
        for s in sorted((gd / "screenshots").glob("p655_*")):
            shutil.copyfile(s, a.output_dir / s.name)
            print("kept", a.output_dir / s.name)
        return 1 if L.FAILED else 0
    finally:
        if client is not None and client.poll() is None:
            client.terminate()
            client.wait(timeout=10)
        if held is not None and L.clipboard() != held:
            L.clipboard(held)
            print("\nthe desktop's clipboard was put back as it was")
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
