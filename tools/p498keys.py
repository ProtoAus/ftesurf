#!/usr/bin/env python3
"""p498keys.py -- driver and grader for cfg/test/p498keys.cfg (Patch 498: a text
field the keyboard can reach, and one that gives the navigation keys back).

    python tools/p498keys.py [--exe ftesurf64.exe] [--grade-only] [--timeout 240]

THE DEFECT is two halves of one rule: sui moves its cursor by hit test, so a text
field -- which is not an element the cursor can land on and click -- cannot be
focused by any key the menu VM consumes; and `sui_text_input_focused`, the flag
that suppresses the WASD navigation keys, is set from a MOUSE hit, so nothing the
keyboard does can ever set it.

THE FIX is a claim rather than a flag: TAB claims the screen's field, the field's
own draw takes the claim, and sui_begin clears the flag every frame -- so a claim
cannot outlive the screen that made it.

THE SCREEN UNDER TEST IS THE NAME ONE, and that is a measurement rather than a
preference: the create screen has 58 elements and a scroll view that calls
sui_reread_input and DRAINS THE INPUT BUFFER every frame, so a keystroke there is
consumed before the field can read it (the TAB that claimed the focus was eaten by
the frame that claimed it).  Its field is unreachable by any key -- a separate
finding, in BACKLOG.  The name screen has three elements, no scroll view, and a
cursor whose moves are reproducible (RIGHT (960,570)->(1146,626), LEFT ->(839,626),
UP ->(960,570)), which is what makes "did this key navigate" observable.

THE OBSERVABLES are all lines the menu VM prints, and all three handles are new in
this patch (`ui_key`, `ui_focus`, `ui_cursor`).  That is the honest limit of this
arm and it is stated in the cfg: `ui_key` calls Menu_InputEvent, which is what
keys.c calls (and keys.c RETURNS after Menu_KeyEvent for every non-F1..F15 key,
keys.c:4056-4063, so with the menu up a bind never runs) -- but _sui_kb_move_dir's
consumption of _cursor_kb_move is driven from m_draw, so a navigation key is graded
by the CURSOR it moved, and a keystroke by the TEXT it produced.

THE CONTROL cannot print at all: `ui_key`/`ui_focus`/`ui_cursor` do not exist on
the previous commit, so every section reads "Unknown command" and the grader
returns CANNOT GRADE (2) rather than scoring a pass.  That is the correct verdict
for "the feature did not exist", and the grader prints the unrecognised lines so
the difference between a control and a broken subject is visible.

Exit 0 pass, 1 fail, 2 cannot grade.
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMEDIR = os.path.join(ROOT, "ftesurf")
LOG = os.path.join(GAMEDIR, "logs", "p498keys.log")
MENU = os.path.join(GAMEDIR, "menu.dat")


def run(exe, timeout):
    if os.path.exists(LOG):
        os.remove(LOG)
    flags = 0x08000000 if os.name == "nt" else 0
    p = subprocess.Popen([os.path.join(ROOT, exe), "-WindowStyle", "Minimized",
                          "+exec", "test/p498keys.cfg"], cwd=ROOT,
                         creationflags=flags, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    t0 = time.time()
    while p.poll() is None and time.time() - t0 < timeout:
        time.sleep(1)
    if p.poll() is None:
        p.kill()
        print("the run did not exit in %g s -- killed" % timeout)


def parse(log):
    """Sections in cfg order, each a list of the lines printed inside it."""
    secs, cur = {}, None
    for raw in open(log, "r", errors="replace"):
        line = re.sub(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ", "", raw.rstrip("\n"))
        m = re.search(r"=== p498 (\w+) ===", line)
        if m:
            cur = m.group(1)
            secs.setdefault(cur, [])
            continue
        if cur is not None:
            secs[cur].append(line)
    return secs


def cursor(lines, i):
    """The i'th `ui_cursor: x y hover hx hy elements n` in a section."""
    got = [l for l in lines if l.startswith("ui_cursor:")]
    if i >= len(got):
        return None
    m = re.match(r"ui_cursor: (\S+) (\S+)\s+hover (\S+) (\S+)\s+elements (\S+)",
                 got[i])
    if not m:
        return None
    return tuple(float(g) for g in m.groups())


def focus(lines, i=0):
    """The i'th `ui_focus: field 'x'  flag n  held n  keydest k` -> (field, held,
    keydest).  `flag` is sui's per-frame record and is NOT comparable to `held`
    across a wait: a claim is consumed by the field's own draw, so the flag is
    whatever the last draw left behind -- see the cfg's B2 note."""
    got = [l for l in lines if l.startswith("ui_focus:")]
    if i >= len(got):
        return None
    m = re.match(r"ui_focus: field '([^']*)'\s+flag (\S+)\s+held (\S+)\s+keydest (\S+)",
                 got[i])
    if not m:
        return None
    return m.group(1), float(m.group(3)), float(m.group(4))


def took(lines, key, i=0):
    """The i'th `ui_key: <name> ... took n` for that key name."""
    got = [l for l in lines if l.startswith("ui_key: %s " % key)]
    if i >= len(got):
        return None
    m = re.search(r"took (\S+)$", got[i])
    return float(m.group(1)) if m else None


def unknown(lines):
    return [l for l in lines if "Unknown command" in l]


def grade():
    if not os.path.exists(LOG):
        print("CANNOT GRADE: no log at %s" % LOG)
        return 2
    s = parse(LOG)
    if "done" not in s:
        print("CANNOT GRADE: the cfg did not reach its done marker")
        return 2

    # A control build has none of the three handles.  Say so as the thing it is
    # rather than scoring zero passes and twenty failures.
    miss = []
    for k in ("A", "B", "C"):
        if k in s:
            miss += unknown(s[k])
    if miss:
        print("CANNOT GRADE: %d line(s) the menu VM did not recognise -- this is "
              "the control build, whose ui_key/ui_focus/ui_cursor do not exist:"
              % len(miss))
        for l in sorted(set(miss))[:6]:
            print("    %s" % l)
        return 2
    for k in ("A", "B", "C"):
        if k not in s:
            print("CANNOT GRADE: no %s section in the log" % k)
            return 2

    fails = 0

    def verdict(ok, text):
        nonlocal fails
        fails += 0 if ok else 1
        print("%s %s" % ("PASS" if ok else "FAIL", text))

    a, b, c = s["A"], s["B"], s["C"]

    def fieldtext(lines, i=0):
        """The i'th `ui_name: field "x" caret n` -> (text, caret)."""
        got = [l for l in lines if l.startswith("ui_name: field")]
        if i >= len(got):
            return None
        m = re.match(r'ui_name: field "(.*)" caret (\S+)', got[i])
        if not m:
            return None
        return m.group(1), float(m.group(2))

    # ---- A: nothing focused, so the navigation keys navigate -----------------
    f = focus(a)
    verdict(f is not None and f[0] == "" and f[1] == 0 and f[2] == 2,
            "A1  no field focused at boot: ui_focus reads %s (field, held, "
            "keydest -- 2 is PF_cl_getkeydest's 'the menu has it')" % (f,))
    verdict(took(a, "rightarrow") == 0,
            "A2  `ui_key rightarrow` took %s -- Menu_InputEvent did not consume "
            "it, so it fell through to _sui_kb_move_dir" % took(a, "rightarrow"))
    cs = [cursor(a, i) for i in range(4)]
    steps = [("RIGHT", 0, 1), ("LEFT", 1, 2), ("UP", 2, 3)]
    moved = [n for n, i, j in steps
             if cs[i] is None or cs[j] is None or cs[i][:2] == cs[j][:2]]
    verdict(not moved,
            "A3  the cursor moved for %s: %s"
            % (", ".join(n for n, _, _ in steps),
               " -> ".join(str(x[:2]) if x else "none" for x in cs)))
    # ---- B: the field focused, the keys suppressed, text goes in ------------
    click = [l for l in b if l.startswith("ui_click:")]
    verdict(len(click) == 2,
            "B1  the click was delivered: %s" % (click or "no ui_click line"))
    f0 = focus(b, 0)
    # held 1 is the whole observable for a MOUSE focus: `field` names the id a
    # keyboard CLAIM recorded, and a click goes through sui_is_last_clicked, which
    # sets the flag without naming an id.  Printing the id for a click would be a
    # lie about where the focus came from.
    verdict(f0 is not None and f0[1] == 1,
            "B2  a click on the field focuses it: %s (want held 1; the id column is "
            "the keyboard claim's, not a click's)" % (f0,))
    ft = fieldtext(b, 0)
    verdict(ft is not None,
            "B3  and the field reports its own text: %s" % (ft,))
    # ONE RIGHT IS SPENT BEFORE THE FIELD IS CLICKED, and B4's base is the sample
    # after it: the first navigation key following a click moves nothing whatever
    # the focus does, because _cursor_kb_move put the cursor in mouse mode.  See
    # the cfg's B-section note for the measurement.
    bs = [cursor(b, i) for i in range(2)]
    verdict(all(x is not None for x in bs) and bs[0][:2] == bs[1][:2],
            "B4  RIGHT did NOT move the cursor with the field focused: %s -> %s "
            "-- the key that moved it in A3, on a cursor already at an element's "
            "centre" % tuple(str(x[:2]) if x else "none" for x in bs))
    ft2 = fieldtext(b, 1)
    verdict(ft2 is not None and ft2[0] == "wat" and ft2[1] == 3,
            "B5  w/a/t typed into the field: %s (want text 'wat', caret 3)"
            % (ft2,))
    ft3 = fieldtext(b, 2)
    verdict(ft3 is not None and ft3[0] == "watwasd" and ft3[1] == 7,
            "B7  the BIND-bearing letters reached the field too: %s (want "
            "'watwasd', caret 7 -- w/a/s/d are +forward/+back/+moveleft/"
            "+moveright, so a build whose sui_menu_nav still drains the buffer "
            "reads 'wat' here and looks like it passed B5)" % (ft3,))
    nm = [l for l in b if l.startswith("ui_name:") and not l.startswith("ui_name: field")]
    # "committed" means `name` IS NOT "watwasd", and that is a negative reading
    # worth stating: ENTER reaches sui_handle_text_input's commit branch (char 13
    # = "commit and deselect") but ui_name_take is not wired to it, so the field's
    # text is not adopted -- the run leaves the committed name at its default.  The
    # positive half of this check is B7's: text arrived in the field.  ENTER not
    # being swallowed AS TEXT is what is graded, and it is the arm's "a keystroke
    # reached the handler" probe, which `took` is not (see the cfg's A4 note).
    verdict(len(nm) >= 1 and "chosen" in nm[-1] and "watwasd" not in nm[-1],
            "B6  ENTER committed rather than being swallowed as text: %s -- and the "
            "name is NOT the field's, because ui_name_take is not wired to char 13 "
            "(pre-existing, BACKLOG)" % (nm[-1:] or "none"))

    # ---- C: the other screen, and leaving a panel gives the keys back -------
    tab2 = [l for l in c if l.startswith("ui_tab:")]
    fc = [focus(c, i) for i in range(4)]
    verdict(tab2 and tab2[0].endswith("cs_search"),
            "C1  TAB claims the create screen's OWN field: %s (that screen cannot "
            "show more -- its scroll view drains the input buffer, see the cfg "
            "header and BACKLOG)" % (tab2[:1] or "no ui_tab line"))
    verdict(fc[0] is not None and fc[0][0] == "cs_search",
            "C2  and the claim is recorded for it: %s" % (fc[0],))
    verdict(fc[1] is not None and fc[1][0] == "" and fc[1][1] == 0,
            "C3  the create screen's ESC dropped the claim: %s" % (fc[1],))
    verdict(fc[2] is not None and fc[2][1] == 1,
            "C4  the name screen's click focuses its own field again: %s" % (fc[2],))
    verdict(fc[3] is not None and fc[3][0] == "" and fc[3][1] == 0,
            "C5  and its ESC drops it: %s" % (fc[3],))
    # TWO keys, for the same reason B4 spends one: the cursor is in mouse mode
    # until a navigation key runs through _cursor_kb_move, and the click that
    # focused the field put it there.  What is graded is that navigation happens
    # at all after the ESC, and one key cannot show that.
    # THREE SAMPLES FOR TWO KEYS, and the second key is DOWN: the ESC lands on the
    # main menu, whose four elements are a vertical list, so RIGHT has nowhere to go
    # from mm_play.  What is graded is that navigation happens at all after the ESC.
    c0, c1, c2 = cursor(c, 0), cursor(c, 1), cursor(c, 2)
    verdict(all(x is not None for x in (c0, c1, c2)) and c1[:2] != c2[:2],
            "C6  and the keys navigate again after that ESC (RIGHT then DOWN): %s "
            "-> %s -> %s -- the first key has no element to its right on a "
            "vertical list, the second moves"
            % tuple(str(x[:2]) if x else "none" for x in (c0, c1, c2)))

    print("16 check(s), %d failed" % fails)
    return 0 if fails == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default="ftesurf64.exe")
    ap.add_argument("--grade-only", action="store_true")
    ap.add_argument("--timeout", type=float, default=420)
    a = ap.parse_args()
    if not a.grade_only:
        with open(MENU, "rb") as f:
            print("menu.dat %s" % hashlib.sha256(f.read()).hexdigest()[:16].upper())
        run(a.exe, a.timeout)
    return grade()


if __name__ == "__main__":
    sys.exit(main())
