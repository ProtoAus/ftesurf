#!/usr/bin/env python3
"""p667paste.py -- paste while a server is about: the engine's own question first, in the game's
boxes and in the menu; and the menu's console words kept from a server (Patch 667).

    python tools/p667paste.py --progs <build dir> --output-dir <owned dir> [--client <exe>]

One client on a map of its own (it is the server too); no surfd.  Keys are
window messages on the client's own queue, the way a keyboard's arrive.  THE
DESKTOP'S CLIPBOARD IS WRITTEN, and put back at the end.  Graded on the chat
draft's own text (`chat_rows`) and on the menu's own prints (`ui_name field`);
the prompt is the engine's and says nothing to a log, so a screenshot of it
is kept in --output-dir: LOOK AT IT.  (The menu's paste with NO server about
asks nothing: tools/p655text.py.)

What a client whose exe has no paste does is the control, and the arm knows
which it was given (the exe names `clipboard_paste` or it does not):

  Q  Ctrl+V in a draft pastes nothing by itself: the engine asks first
     (older engine: nothing asks, and the V is a letter)
  Y  Y is the prompt's: the clipboard's FIRST LINE joins the draft, and no y
  R  ...and that Y's own repeats, while it is still held, are nobody's; let
     go and pressed again it is a letter
  N  Enter is a no, and its repeat does not send the draft either
  E  Esc is a no: nothing is pasted and the draft is still being typed
  X  any other key is a no too, and is not typed
  H  a Y in the prompt's first third of a second is a no as well (the next
     key, a letter, is typed: the prompt had gone)
  I  Shift+Insert asks the same question
  M  the menu, opened over the game, asks it too (with a server about a menu
     field is not pasted into at once), and it sees the chord's keys come up
  S  a menu word the SERVER stuffs is not run; the same word typed is (older
     engine: both run, which is the hole)
  A  ...nor through an alias the server makes and tries to raise to the
     player's level: the engine refuses the raise, and the alias's word
"""
import argparse
import pathlib
import re
import shutil
import subprocess
import tempfile
import time

import p615link as L

VK = {"ctrl": 0x11, "shift": 0x10, "v": 0x56, "x": 0x58, "y": 0x59, "m": 0x4D, "ins": 0x2D,
      "enter": 0x0D, "esc": 0x1B, "tab": 0x09}
EXT = {"ins"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--progs", type=pathlib.Path, required=True)
    ap.add_argument("--content", type=pathlib.Path, default=pathlib.Path("C:/FTESurf"))
    ap.add_argument("--client", type=pathlib.Path)
    ap.add_argument("--output-dir", type=pathlib.Path)
    ap.add_argument("--map", default="bhop_eazy")
    a = ap.parse_args()
    a.client = a.client or a.content / "ftesurf64.exe"
    a.progs = a.progs.resolve()
    a.output_dir = (a.output_dir or pathlib.Path(tempfile.gettempdir())).resolve()
    a.output_dir.mkdir(parents=True, exist_ok=True)
    pastes = b"clipboard_paste" in a.client.read_bytes()
    print("this client's exe %s the paste builtins" % ("has" if pastes else "does NOT have"))

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
             "+set", "log_enable", "1", "+set", "log_dir", "logs", "+set", "log_name", "p667paste",
             "-window", "-nosound", "+set", "con_savehistory", "0", "+set", "cl_idlefps", "0",
             "+set", "cl_maxfps", "60", "+set", "vid_fullscreen", "0", "+set", "name", "p667rig",
             "+set", "developer", "1", "+set", "log_developer", "1"],
            cwd=a.content, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, startupinfo=si)
        log = L.Log(gd / "logs/p667paste.log")

        def send(line, wait=0.4):
            client.stdin.write(line.encode("ascii") + b"\n")
            client.stdin.flush()
            time.sleep(wait)

        time.sleep(12)
        send("map " + a.map, 1.0)
        up = log.wait("FTESurf CSQC loaded", 60)
        L.check("the client is on its own map and its game code loaded", bool(up), True)
        if not up:
            return 1
        send("closemenu")
        send("con_notifytime 0")
        send("con_notifylines 0")
        time.sleep(3.0)
        keys = L.Keys(client.pid)

        def post(name, down, repeat=False):
            vk = VK[name]
            lparam = 1 | (keys.u.MapVirtualKeyW(vk, 0) << 16) | ((1 << 24) if name in EXT else 0)
            if repeat:
                lparam |= 1 << 30               # "was down before": the OS's auto-repeat
            if not down:
                lparam |= (1 << 30) | (1 << 31)
            keys.u.PostMessageW(keys.hwnd, 0x0100 if down else 0x0101, vk, lparam)
            time.sleep(0.06)

        def press(*names):
            for n in names[:-1]:
                post(n, True)
            post(names[-1], True)
            post(names[-1], False)
            for n in reversed(names[:-1]):
                post(n, False)
            time.sleep(0.6)

        def draft():
            """The draft as chat prints it: its text, or None when nothing is being typed."""
            n = log.text().count("chat_rows: draft n ")
            send("chat_rows", 0.3)
            log.count("chat_rows: draft n ", n + 1, 5)
            text = log.text()
            at = text.rfind("chat_rows: draft n ")
            if not re.search(r"typing 1", text[at:at + 200]):
                return None
            rows = re.findall(r"chat_rows: draft \d+ w [\d.]+ \|(.*)\|", text[at:])
            got = "".join(rows)
            return got[2:-1] if got.startswith("> ") and got.endswith("_") else got

        def field():
            """The menu's name field, by its own print."""
            n = log.text().count('ui_name: field "')
            send("ui_name field", 0.3)
            log.count('ui_name: field "', n + 1, 5)
            f = re.findall(r'ui_name: field "(.*)" caret (-?\d+)', log.text())
            return f[-1][0] if f else None

        def mods():
            """The menu's own count of the modifiers it thinks are held."""
            n = log.text().count("ui_name: sel ")
            send("ui_name sel", 0.3)
            log.count("ui_name: sel ", n + 1, 5)
            return re.findall(r"ui_name: sel -?\d+ mods (\d+)", log.text())[-1:]

        def shot(name):
            send("screenshot " + name, 1.5)

        send("chat_say ab", 0.8)                # a draft, as the chat key opens one, with two letters in it
        L.check("a draft is being typed", draft(), "ab")
        L.clipboard("XY Z\nnot this line")
        press("ctrl", "v")
        asked = draft()
        if not pastes:
            L.check("Q  CONTROL an engine with no paste asks nothing: that V is a letter in the draft",
                    asked, "abv")
            press("esc")
        else:
            L.check("Q  Ctrl+V pastes nothing by itself: the draft is as it was while the engine asks",
                    asked, "ab")
            shot("p667_2_prompt")               # LOOK: the engine's question, over the game
            post("y", True)                     # yes, and the key stays down...
            time.sleep(0.5)
            first = draft()
            post("y", True, repeat=True)        # ...so the OS repeats it
            post("y", True, repeat=True)
            time.sleep(0.4)
            repeated = draft()
            post("y", False)
            time.sleep(0.3)
            press("y")
            L.check("Y  a Y was the prompt's yes: the clipboard's first line joined the draft, and no y",
                    first, "abXY Z")
            L.check("R  that Y's repeats while held were nobody's; let go and pressed again it is a letter",
                    (repeated, draft()), ("abXY Z", "abXY Zy"))
            press("ctrl", "v")
            post("enter", True)                 # Enter is the chat key: a no, held...
            time.sleep(0.4)
            post("enter", True, repeat=True)    # ...and its repeat would send the draft
            time.sleep(0.4)
            post("enter", False)
            time.sleep(0.4)
            L.check("N  Enter is a no, and its repeat does not send the draft: nothing pasted, still "
                    "being typed", draft(), "abXY Zy")
            press("ctrl", "v")
            press("esc")
            L.check("E  Esc was the prompt's: nothing pasted, and the draft is still being typed",
                    draft(), "abXY Zy")
            press("ctrl", "v")
            press("x")
            L.check("X  another key is a no as well, and is not typed", draft(), "abXY Zy")
            post("ctrl", True)                  # the chord, and Y hard on its heels
            post("v", True)
            post("v", False)
            post("ctrl", False)
            post("y", True)
            post("y", False)
            time.sleep(0.6)
            press("x")
            L.check("H  a Y that comes at once is a no: nothing is pasted, the prompt is gone "
                    "(the x after it is typed)", draft(), "abXY Zyx")
            L.clipboard("!")
            press("shift", "ins")
            press("y")
            L.check("I  Shift+Insert asks the same question", draft(), "abXY Zyx!")
            shot("p667_3_pasted")
            press("esc")                        # no prompt is up: this one is the draft's, and ends it
        L.check("the draft is given up with Esc and nothing was said", (draft(), log.text().count("p667rig: ab")),
                (None, 0))

        if pastes:
            send("togglemenu", 1.0)             # the menu, over the game...
            send("ui_name screen", 1.5)         # ...on its name screen
            press("tab")                        # its one field takes the keyboard
            press("m")
            L.clipboard("MENU")
            press("ctrl", "v")
            asked = field()
            shot("p667_4_menu_prompt")
            press("y")
            time.sleep(0.5)
            L.check("M  the menu over a game asks first too: nothing in the field until the Y, then "
                    "the clipboard's line; and the menu saw the chord's keys come up (no modifier "
                    "is left held in it)", (asked, field(), mods()), ("m", "mMENU", ["0"]))
            L.clipboard("2")
            press("shift", "ins")
            press("y")
            time.sleep(0.5)
            L.check("M  ...the same after Shift+Insert, whose Shift came up under the prompt",
                    (field(), mods()), ("mMENU2", ["0"]))
            send("ui_close", 0.5)
            send("closemenu", 0.5)

        n = log.text().count('ui_name: field "')
        send("ui_name field", 0.6)
        typed = log.text().count('ui_name: field "') - n
        send("stuffcmd p667rig ui_name field", 1.2)     # this client is its own server: stuffed text
        stuffed = log.text().count('ui_name: field "') - n - typed
        refused = log.text().count("is not a server's or game code's to run")
        L.check("S  a menu word the server stuffs is %s; typed by the player it runs (the engine says "
                "so in its developer line)" % ("NOT RUN" if pastes else "run, on an engine before 667"),
                (typed, stuffed, refused > 0), (1, 0, True) if pastes else (1, 1, False))
        n = log.text().count('ui_name: field "')
        send('stuffcmd p667rig alias p667a "ui_name field"', 0.8)
        send("stuffcmd p667rig aliaslevel p667a 29", 0.8)
        send("stuffcmd p667rig p667a", 1.2)
        ran = log.text().count('ui_name: field "') - n
        L.check("A  an alias the server makes, tries to raise to the player's level, and runs: the "
                "raise is refused and its menu word %s" % ("is not run" if pastes else "runs, on an engine before 667"),
                (ran, log.text().count("allowed to raise a command above your own level") > 0,
                 log.text().count("is not a server's or game code's to run") > refused),
                (0, True, True) if pastes else (1, False, False))
        L.check("no VM error or unknown menu builtin in the log",
                [w for w in ("QC VM error", "Cannot call", "stack overflow", "sui warning") if w in log.text()], [])
        try:
            send("quit")
            client.wait(timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            pass
        for s in sorted((gd / "screenshots").glob("p667_*")):
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
