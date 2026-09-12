#!/usr/bin/env python3
"""
hidcheck.py -- read a raw input journal and say whether it is well formed.

WHY THIS EXISTS, and it is the same argument reccheck.py makes for the .rec.  The
.hid has one writer (IN_Journal_* in engine/client/in_generic.c) and no reader in
the game at all, so nothing has ever disagreed with it.  This is written from the
FORMAT COMMENT above IN_Commands rather than from that code, so a writer which
drifts from its own documentation is caught rather than matched.

WHAT A .hid IS FOR, because it decides what is worth checking.  It is an
anti-cheat artifact, not a playback one: the .rec already holds the authoritative
positions and the .view already holds angles at render rate.  What the journal
adds is the individual mouse reports BEFORE in_generic.c sums them per frame --
so the things worth validating are the ones a forgery would have to get right:
that the time base is self-consistent from two independent counters, that nothing
was silently lost, and that the file agrees with the .view sitting next to it.

WHAT IT CHECKS

  * magic, version, header keys, begin/end;
  * that every dt is a non-negative integer of microseconds;
  * THE TIME BASE, which is the load-bearing one: every line carries a dt and
    only 'f' lines carry an absolute, so the running sum of dt must arrive at
    each f's abs.  Those are written from two separate counters in the engine,
    so a disagreement means one of them is wrong;
  * that the trailer's event/frame/drop/hidden counts match what is actually in
    the file, for the same reason;
  * '!' drop markers and 'truncated', reported rather than faulted -- a journal
    that says it lost events is doing its job; one that lost them silently would
    be the bug, and that is exactly what cannot be detected from outside;
  * 'synth 1', which makes a file INADMISSIBLE as evidence and is reported that
    way rather than quietly;
  * 'rawinput 0', which means the mouse column is per-frame OS-summed deltas
    rather than per-report ones, so no timing conclusion may be drawn from it.

And, when the .view sidecar is beside it, that the two describe the same run:
that the .view's `hid` key agrees that a journal was taken, that the movesequence
ranges overlap, and -- reported as a measurement, not asserted to be zero -- the
start gap, which is the two-video-frame cost of localcmd's deferral.

THE ANGLE/DELTA CHECK IS NOW IMPLEMENTED -- see check_identity() -- but read what
it is before relying on it.  Engine Patch 293 added a per-frame 'v' record
carrying the frame's raw counts AND the viewangles they produced, which is what
made it possible: the old plan of inverting sensitivity against the 'm' column
could not work, because IN_MoveMouse consumes the deltas summed rather than
per-report and the '.view' sidecar cannot be aligned to this file at all (the 'f'
marker is emitted only on a non-empty drain, so frames here are a SUBSET of
rendered frames).

WHAT IT DELIBERATELY DOES NOT CHECK, and this is the important sentence in this
docstring.  It does NOT establish that a human produced the counts, and it is not
attestation.  Both sides of the identity are computed by the engine from the
engine's own mx, so it tests the engine's multiplication.  Anything that alters
the counts UPSTREAM of the capture -- _GRID (in_win.c:296, one static pointer
holding GetRawInputData), the event ring, or IN_MoveMouse itself, which is the
FTE analogue of the CInput::ApplyMouse that the known sample cheat detours --
produces a conforming record for free.  A replayed or synthesised input stream
satisfies it perfectly.

What a PASS means: the angle came from the counts as recorded.  Nothing more.
What a FAIL means: it did not, and that is arithmetic rather than suspicion.

Usage:
    python hidcheck.py                        # every .hid in data/runs
    python hidcheck.py <file> [<file> ...]
    python hidcheck.py --verbose
"""

import argparse
import glob
import os
import sys

SURFDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(SURFDIR, "ftesurf", "data", "runs")

# Header keys the version is allowed to write.  Unknown keys are SKIPPED by a
# reader rather than rejected, so an unexpected one is a note and not a fault --
# the same additive rule the .rec and .view headers follow.
HEAD_V1 = {"map", "base", "rawinput", "rawkbd", "synth"}

# Engine Patch 293 appended the scale terms so the 'v' record's identity can be
# checked against a KNOWN constant rather than merely against itself.  They are
# additive, so a pre-293 file simply has none of them and the identity check is
# skipped rather than failed.
HEAD_P293 = {"sensitivity", "sensitivityscale", "m_yaw", "m_pitch", "m_filter",
             "m_accel", "m_accel_style", "m_accel_power", "m_accel_offset",
             "m_accel_senscap"}

# Engine Patch 301 appended the GRANT beside the request: `rawinput`/`rawkbd` are
# the cvars this client asked for, `rawmice`/`rawkbds` are what INS_RawInput_Init
# actually bound.  Additive, so a pre-301 file simply has neither and the check
# below is skipped -- which is the honest outcome, because for those files the
# question genuinely cannot be answered from the header.
HEAD_P301 = {"rawmice", "rawkbds"}

# Engine Patch 303 appended the device table:
#   dev <type> <devid|unset|-> "<name>"
# repeated, one line per enumerated device, between the scale terms and `begin`,
# and repeated again as `devmap` immediately before the trailer.
#
# THIS IS THE ONLY REPEATING HEADER KEY, so it does not go in `head` -- a dict
# would keep the last line and silently discard every other device, which for a
# two-mouse machine is precisely the evidence the patch exists to record.
#
# THE TWO TABLES ARE NOT REDUNDANT.  Devids are allocated lazily at first use, so
# `dev` is written before most devices have one and answers "what hardware was
# PRESENT at the start"; `devmap` is written at the end and answers "which device
# owns which devid".  A device in one and not the other was plugged or unplugged
# mid-run.
#
# `-` means the device cannot carry a devid at all (the "system" pseudo-devices);
# `unset` means it can but never produced an event.  NEITHER IS 0, and 0 is a
# real devid owned by a real device -- reading either as 0 would attribute one
# device's motion to another, which is the exact error this table exists to
# prevent.
HEAD_P303 = {"dev"}
# Patch 307: the injected-click block -- the request, and what it actually got.
HEAD_P307 = {"nolegacy", "nolegacylive"}

# Engine Patch 310 appended the render-integrity table:
#   render <cvar> "<value>" "<default>"
# repeated, one line per cvar, beside the device table and before `begin`.
#
# REPEATING, SO IT IS NOT A HEADER KEY -- a key/value header is a dict to every
# reader that parses one, and a dict keeps the LAST of a repeated key, so eleven
# cvars would arrive as one. The `dev` table learned this first.
#
# THE DEFAULT IS ON THE LINE WITH THE VALUE on purpose. A reader that knows only
# the value needs its own table of what is normal; that table drifts from the
# engine's, and the check silently starts measuring the wrong thing. With both
# here, "differs from default" is answerable with no model in the reader at all.
HEAD_P310 = {"render"}

# Engine Patch 312 added the matching `input` table -- the cvars that change what
# the counts BECOME rather than what the player could see -- and with it the 'd'
# record. Its presence is how this reader tells a journal that CAN answer the
# counts join from one that predates the question: a pre-312 file has no 'd', so
# a legitimate transform in it is indistinguishable from a mutated delta, and the
# join must be reported as unanswerable rather than as a break. Absent is not
# zero, for the sixth time.
HEAD_P312 = {"input"}

# Names that are not physical devices: FTE's own fallback paths, enumerated
# alongside the real hardware.  Excluded when counting mice against `rawmice`.
PSEUDO_DEVICES = {"system", "di", "di7"}


def _unquote_pair(rest):
    """'"1" "0"' -> ('1', '0').  The writer quotes with COM_QuotedString because
    a cvar value can contain spaces, so this cannot just be split()."""
    out = []
    i = 0
    while len(out) < 2 and i < len(rest):
        while i < len(rest) and rest[i] == " ":
            i += 1
        if i < len(rest) and rest[i] == '"':
            j = i + 1
            buf = []
            while j < len(rest) and rest[j] != '"':
                if rest[j] == "\\" and j + 1 < len(rest):
                    j += 1
                buf.append(rest[j])
                j += 1
            out.append("".join(buf))
            i = j + 1
        else:
            j = rest.find(" ", i)
            if j < 0:
                j = len(rest)
            out.append(rest[i:j])
            i = j
    while len(out) < 2:
        out.append("")
    return out[0], out[1]


def parse_dev_line(line):
    """'dev mouse unset "\\\\?\\HID#..."' -> ('mouse', 'unset', '\\\\?\\HID#...').

    Returns None if the line is not shaped like a device line.  The name is
    quoted by the writer (COM_QuotedString) because a Windows device path carries
    backslashes, braces and '#', so it is taken as the whole remainder rather
    than split on whitespace."""
    parts = line.split(None, 3)
    if len(parts) < 3:
        return None
    name = parts[3] if len(parts) > 3 else ""
    if len(name) >= 2 and name[0] == '"' and name[-1] == '"':
        name = name[1:-1]
    return parts[1], parts[2], name

# kind -> number of payload fields AFTER the dt.  'end' and 'truncated' are
# trailers rather than events and are handled separately.
KINDS = {
    "f": 2,     # abs seq
    "m": 3,     # dev dx dy
    "a": 3,     # dev x y
    # Patch 309 appended `prev`, "the key was already down before this event":
    # on '+' that separates a real press from OS auto-repeat, on '-' it exposes
    # an orphan release. -1 where the question does not apply (scancode -1 is
    # the release-everything sweep, 0 the unicode-only dead-key path). Variable,
    # so the length is checked in the branch.
    "+": None,  # dev scancode [prev]
    "-": None,  # dev scancode [prev]
    "x": 1,     # dev            (scancode suppressed -- console/menu had focus)
    "j": 3,     # dev axis value
    # dx dy flags pitch yaw [kpitch kyaw]  -- Patch 293 wrote the first five,
    # Patch 305 appended the last two (the non-mouse angle change). Variable, so
    # the length is checked in the branch rather than here.
    "v": None,
    "#": None,  # free text
    "!": 1,     # n
    # Patch 306: WM_INPUT reports the raw path REJECTED since the last such
    # record -- <injected> with no device handle at all, <unenum> from a real
    # device that was never enumerated. An annotation, not an event: nothing
    # here reached the game, which is the entire point of it.
    "i": 2,     # injected unenum
    # Patch 307: legacy mouse buttons ACCEPTED although raw input -- which was
    # live -- could not corroborate them. Unlike 'i', these DID reach the game.
    "b": 1,     # n
    # Patch 307: the effective legacy-suppression state CHANGED to this. The
    # header carries the state at begin; these carry every change after it,
    # because the setting is grab-scoped and therefore not constant over a run.
    "g": 1,     # nolegacylive
    # Patch 310: a render-integrity cvar was CHANGED mid-journal. Tracked by the
    # engine's modifiedcount rather than by value, so a set-and-set-back leaves
    # two of these and a start-vs-end comparison would have seen nothing.
    "c": 2,     # cvar value
    # Patch 312: the counts AS THE RING DELIVERED THEM for the frame described by
    # the 'v' that follows, written ONLY when the pipeline changed them on the way
    # through. Its ABSENCE is therefore the positive claim "nothing touched them",
    # which is the case on 100.000000% of measured honest frames.
    "d": 2,     # rawdx rawdy
}

# 'v' flag bits.  A frame with any of these set is one the yaw identity does NOT
# apply to, and saying which is the whole reason the column exists.
VF_STRAFE_X = 1     # counts went to sidemove, not yaw (+strafe / lookstrafe)
VF_STRAFE_Y = 2     # counts went to forwardmove, not pitch
VF_FREE     = 4     # the cursor was free (menu/console); counts reached neither

# Kinds that are input events, i.e. what the trailer's `events` counts.  'f' is a
# frame, '#' and '!' are annotations, and none of the three is an event.
EVENT_KINDS = {"m", "a", "+", "-", "x", "j"}

# How far the running sum of dt may sit from an absolute, in seconds.  This is a
# FIXED number and not a per-line allowance: the writer carries its truncation
# remainder forward, so the residual is under one microsecond for any file
# length.  Two of those covers the %.6f the absolute is printed at.
TIME_EPS = 2e-6


class Report:
    def __init__(self, path):
        self.path = path
        self.faults = []
        self.notes = []
        self.info = {}

    def fault(self, msg):
        self.faults.append(msg)

    def note(self, msg):
        self.notes.append(msg)

    @property
    def ok(self):
        return not self.faults


def check_hid(path, verbose=False):
    r = Report(path)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = [l.rstrip("\n").rstrip("\r") for l in f]

    if not lines:
        r.fault("empty file")
        return r

    magic = lines[0].split()
    if len(magic) != 2 or magic[0] != "FTESURF-HID":
        r.fault("first line is not 'FTESURF-HID <version>': %r" % lines[0][:60])
        return r
    try:
        ver = int(magic[1])
    except ValueError:
        r.fault("version is not a number: %r" % magic[1])
        return r
    if ver != 1:
        r.fault("unknown version %d (this tool knows 1)" % ver)
        return r
    r.info["version"] = ver

    # ---- header ------------------------------------------------------------
    head = {}
    devs = []              # Patch 303: repeating, so a list and not `head`
    rendercvars = []       # Patch 310: (name, value, default)
    inputcvars = []        # Patch 312: (name, value, default) -- the input pipeline
    cvar_changes = []      # Patch 310/312: (name, value), in order
    i = 1
    while i < len(lines):
        parts = lines[i].split(None, 1)
        if not parts:
            i += 1
            continue
        if parts[0] == "begin":
            i += 1
            break
        if parts[0] in ("render", "input"):
            # render/input <cvar> "<value>" "<default>"; `-` where the cvar does
            # not exist in that build -- NOT 0, which would be a real value.
            # Patch 312 added `input` in the identical shape but under its own
            # key, because the two answer different questions -- what the player
            # could SEE, versus what their counts BECAME -- and a reader must be
            # able to tell them apart without a table of its own.
            rp = lines[i].split(None, 3)
            if len(rp) < 4:
                r.fault("malformed %r line: %r" % (parts[0], lines[i]))
            else:
                val, dfl = _unquote_pair(rp[2] + " " + rp[3])
                (rendercvars if parts[0] == "render"
                 else inputcvars).append((rp[1], val, dfl))
            i += 1
            continue
        if parts[0] == "dev":
            d = parse_dev_line(lines[i])
            if d is None:
                r.fault("malformed 'dev' line: %r" % lines[i])
            else:
                devs.append(d)
            i += 1
            continue
        head[parts[0]] = parts[1] if len(parts) > 1 else ""
        if parts[0] not in HEAD_V1 and parts[0] not in HEAD_P293 \
           and parts[0] not in HEAD_P301 and parts[0] not in HEAD_P303 \
           and parts[0] not in HEAD_P307 and parts[0] not in HEAD_P310:
            r.note("unknown header key %r" % parts[0])
        i += 1
    else:
        r.fault("no 'begin' line")
        return r

    for k in ("map", "base"):
        if k not in head:
            r.fault("header has no %r" % k)
    if r.faults:
        return r

    r.info["map"] = head["map"]
    try:
        r.info["base"] = float(head["base"])
    except ValueError:
        r.fault("base is not a number: %r" % head["base"])
        return r

    raw = head.get("rawinput", "?")
    r.info["rawinput"] = raw
    if raw == "0":
        r.note("rawinput 0 -- the mouse column is per-FRAME deltas already summed "
               "by the OS (GetCursorPos recentre), not per-report. No conclusion "
               "about report rate or delta shape may be drawn from this file.")
    elif raw not in ("1",):
        r.note("rawinput %r -- unknown mode" % raw)

    # Patch 301.  THE REQUEST AND THE GRANT, and the pair is the point.
    #
    # `rawinput 1` with `rawmice 0` is the case this key was added for: the cvar
    # was set, INS_RawInput_Init enumerated and bound nothing (no enumerable
    # mouse, an RDP session, a missing user32 export, a refused registration),
    # and the engine silently fell back to the GetCursorPos recentre.  Every
    # delta in the file is then OS-summed and OS-ACCELERATED while the header's
    # own `rawinput` key says otherwise.  Before 301 this file was indisguishable
    # from a strict-profile recording.
    #
    # It is a FAULT and not a note, unlike bare `rawinput 0`.  A player who turns
    # raw input off has made a visible choice and the file says so; this is a file
    # whose two statements about its own provenance CONTRADICT each other, and the
    # identity check further down would be validating arithmetic against
    # accelerated deltas without knowing it.
    #
    # -1 IS NOT 0.  It means the platform backend does not report the figure --
    # in_generic.c is cross-platform and only in_win.c maintains these -- so an
    # SDL or X11 journal says -1 and must not be read as "found no mouse".
    # Absence of a measurement is not a measurement of zero.
    if "rawmice" in head:
        try:
            mice = int(head["rawmice"])
            kbds = int(head.get("rawkbds", -1))
        except ValueError:
            r.fault("header 'rawmice'/'rawkbds' are not numbers: %r / %r"
                    % (head.get("rawmice"), head.get("rawkbds")))
        else:
            r.info["rawmice"] = "not reported by backend" if mice < 0 else str(mice)
            r.info["rawkbds"] = "not reported by backend" if kbds < 0 else str(kbds)
            if raw == "1" and mice == 0:
                r.fault("rawinput 1 but rawmice 0 -- raw input was REQUESTED and "
                        "never granted, so every delta here is an OS-summed, "
                        "OS-accelerated GetCursorPos delta. The header's own "
                        "'rawinput 1' does not describe this file.")
            if raw == "0" and mice > 0:
                r.fault("rawinput 0 but rawmice %d -- the cvar and the bound "
                        "device count disagree in the impossible direction; one "
                        "of the two was written from stale state." % mice)

    rawkbd = head.get("rawkbd", "?")
    r.info["rawkbd"] = rawkbd
    # The auto-repeat warning applies only to a file that cannot separate them
    # itself. Engine Patch 309 added the `prev` column, so on a current file the
    # counts are exact and repeating this caveat would tell a reader to distrust
    # a number that is now correct. Emitted from the body, where `saw_prev` is
    # known -- see the press/repeat section.
    r.info["rawkbd_legacy"] = (rawkbd == "0")

    # The synth flag is read here but REPORTED in the body section, because
    # engine Patch 311 names the source in a note and the notes are not parsed
    # until then. Before 311 the only thing that could set this flag was the
    # in_journal_synth command, so the old wording asserted that -- and it would
    # now be wrong on exactly the files that matter, because 311 made a PLUGIN
    # able to set it too. Same trap as "absent is not zero": a message that was
    # true when written becomes a false attribution when the world widens.
    synthflag = head.get("synth", "0") != "0"

    # ---- body --------------------------------------------------------------
    clock = 0.0          # running sum of dt, seconds since base
    events = 0
    frames = 0
    dropped = 0
    hidden = 0
    injected = 0        # Patch 306: summed from the 'i' records
    unenum = 0
    saw_i = False
    legacybtn = 0       # Patch 307: summed from the 'b' records
    saw_b = False
    presses = 0         # Patch 309: '+' with prev 0 -- a key actually pressed
    repeats = 0         # Patch 309: '+' with prev 1 -- OS auto-repeat
    orphan_rel = 0      # Patch 309: '-' with prev 0 -- a release with no press
    saw_prev = False
    legacy_states = []  # Patch 307: every 'g' transition, in order
    trailer = None
    truncated = None
    first_f = None
    last_f = None
    seqs = []
    notes_seen = []
    dts = []
    views = []           # (lineno, dx, dy, flags, pitch, yaw)  -- Patch 293
    # Patch 312: one entry per closed 'v' window --
    # (lineno, sum_mx, sum_my, raw_x, raw_y, flags, n_m, n_a, had_d)
    joins = []
    j_mx = j_my = 0.0    # running sum of this window's 'm' counts
    j_nm = j_a = 0       # how many 'm' and 'a' records fell in it
    j_raw = None         # the window's 'd' record, if it had one
    devmaps = []         # (type, id, name) -- Patch 303, the resolved table
    # devid -> event count, for the attribution check below.  SPLIT BY CLASS,
    # and that split is a bug fix rather than tidiness -- see the device section.
    # A key event's devid is not a device identity at all on the legacy path.
    devids_used = {}        # pointer devices: m / a / j
    devids_key = {}         # keyboards: + / - / x

    for lineno in range(i, len(lines)):
        s = lines[lineno].strip()
        if not s:
            continue
        tok = s.split()
        kind = tok[0]

        if kind == "end":
            if trailer is not None:
                r.fault("line %d: a second 'end' record" % (lineno + 1))
                continue
            # end <dt> <abs> <events> <frames> <dropped> <hidden>
            #                                  [<injected> <unenum>]
            # Patch 306 appended the last two. A pre-306 file has 7 tokens and
            # is not faulted for it -- absent is NOT zero, and a reader that
            # treated it as zero would report "no injection seen" about a file
            # that could not see any.
            if len(tok) not in (7, 9, 10):
                r.fault("line %d: 'end' has %d fields, expected 7 (pre-306), "
                        "9 (pre-307) or 10" % (lineno + 1, len(tok)))
                continue
            try:
                dt = int(tok[1])
                trailer = [float(tok[2])] + [int(x) for x in tok[3:]]
            except ValueError:
                r.fault("line %d: 'end' has a non-numeric field" % (lineno + 1))
                continue
            clock += dt / 1000000.0
            continue

        if kind == "truncated":
            # truncated <dt> <abs>
            if len(tok) != 3:
                r.fault("line %d: 'truncated' has %d fields, expected 3"
                        % (lineno + 1, len(tok)))
                continue
            try:
                clock += int(tok[1]) / 1000000.0
                truncated = float(tok[2])
            except ValueError:
                r.fault("line %d: 'truncated' has a non-numeric field" % (lineno + 1))
            continue

        if kind == "devmap":
            # Patch 303: the resolved devid->device table, written immediately
            # before the trailer.  UNTIMESTAMPED, like the header's `dev` lines,
            # so it is taken here rather than falling through to the dt parse
            # below -- which would read "devmap keyboard - ..." as a record whose
            # dt is the word `keyboard`.
            if trailer is not None:
                r.fault("line %d: 'devmap' after 'end'" % (lineno + 1))
                continue
            d = parse_dev_line(lines[lineno])
            if d is None:
                r.fault("line %d: malformed 'devmap' line" % (lineno + 1))
            else:
                devmaps.append(d)
            continue

        if kind not in KINDS:
            r.note("line %d: unknown record kind %r" % (lineno + 1, kind))
            continue

        if trailer is not None:
            r.fault("line %d: %r record after 'end'" % (lineno + 1, kind))
            continue

        if len(tok) < 2:
            r.fault("line %d: %r has no dt" % (lineno + 1, kind))
            continue
        try:
            dt = int(tok[1])
        except ValueError:
            r.fault("line %d: dt is not an integer: %r" % (lineno + 1, tok[1]))
            continue
        if dt < 0:
            r.fault("line %d: negative dt %d -- time does not run backwards"
                    % (lineno + 1, dt))
            continue
        dts.append(dt)
        clock += dt / 1000000.0

        want = KINDS[kind]
        if want is not None and len(tok) != 2 + want:
            r.fault("line %d: %r has %d fields, expected %d"
                    % (lineno + 1, kind, len(tok), 2 + want))
            continue

        # Patch 312: the counts join. Accumulated here, beside the 'v' snapshot it
        # feeds, rather than down in the catch-all -- 'm' has never had its dx/dy
        # parsed by anything before now.  'd' MUST be handled with its own
        # `continue`: the catch-all counts every unclaimed kind as an event, and a
        # 'd' is an annotation, so letting it fall through would inflate `events`
        # and break the trailer agreement it has nothing to do with.
        if kind == "m" and len(tok) == 5:
            try:
                j_mx += float(tok[3])
                j_my += float(tok[4])
                j_nm += 1
            except ValueError:
                pass    # the catch-all below already faults on a bad payload
        elif kind == "a":
            # An abs position can put counts into the view that were journalled
            # as 'a' and never as 'm' (the engine derives a delta from successive
            # positions), so a window holding one cannot be joined.
            j_a += 1
        elif kind == "d":
            try:
                j_raw = (float(tok[2]), float(tok[3]))
            except ValueError:
                r.fault("line %d: 'd' has a non-numeric field" % (lineno + 1))
            continue

        if kind == "v":
            # v <dt> <dx> <dy> <flags> <pitch> <yaw>   -- engine Patch 293
            try:
                if len(tok) not in (7, 9):
                    r.fault("line %d: 'v' has %d fields, expected 7 (pre-305) "
                            "or 9" % (lineno + 1, len(tok)))
                    continue
                kp = float(tok[7]) if len(tok) == 9 else None
                ky = float(tok[8]) if len(tok) == 9 else None
                views.append((lineno + 1, float(tok[2]), float(tok[3]),
                              int(tok[4]), float(tok[5]), float(tok[6]), kp, ky))
                # Patch 312: close the window this 'v' ends. The expected raw is
                # the 'd' record if the frame had one and the v's own delta if it
                # did not -- a missing 'd' IS the claim that they are equal.
                exp = j_raw if j_raw is not None else (float(tok[2]), float(tok[3]))
                joins.append((lineno + 1, j_mx, j_my, exp[0], exp[1],
                              int(tok[4]), j_nm, j_a, j_raw is not None))
            except ValueError:
                r.fault("line %d: 'v' has a non-numeric field" % (lineno + 1))
            j_mx = j_my = 0.0
            j_nm = j_a = 0
            j_raw = None
            continue

        if kind == "f":
            frames += 1
            try:
                abst = float(tok[2])
                seq = int(tok[3])
            except ValueError:
                r.fault("line %d: 'f' has a non-numeric field" % (lineno + 1))
                continue
            seqs.append(seq)
            if first_f is None:
                first_f = abst
            last_f = abst

            # THE TIME BASE, and this is the check the whole format is shaped
            # around.  The running sum of dt and the absolute on the f line are
            # written from two independent counters in the engine, so if they
            # disagree one of them is wrong.
            #
            # THE TOLERANCE DOES NOT GROW WITH THE FILE, deliberately.  The
            # writer carries its sub-microsecond truncation remainder forward
            # instead of dropping it, so the residual is bounded below one
            # microsecond however long the journal runs.  Allowing a
            # length-proportional slack here would hide exactly the class of
            # bug that made that necessary: the first build of this format drifted
            # 1.8 ms per 5500 lines and a proportional tolerance called it fine.
            if abs(abst - clock) > TIME_EPS:
                r.fault("line %d: frame says t=%.6f but the dt sum is %.6f "
                        "(off by %.6f) -- the two clocks disagree"
                        % (lineno + 1, abst, clock, abst - clock))
                # resync so one bad line does not fault every line after it
                clock = abst
        elif kind == "!":
            try:
                dropped += int(tok[2])
            except ValueError:
                r.fault("line %d: '!' count is not a number" % (lineno + 1))
        elif kind == "i":
            # Patch 306. Deliberately NOT counted as an event: these reports
            # were thrown away by the backend and never became input.
            try:
                injected += int(tok[2])
                unenum += int(tok[3])
                saw_i = True
            except ValueError:
                r.fault("line %d: 'i' counts are not numbers" % (lineno + 1))
        elif kind == "b":
            # Patch 307. NOT an event: the K_MOUSE1 it produced is journalled
            # separately as its own '+' record and is counted there. This line
            # says only that raw input could not vouch for that press.
            try:
                legacybtn += int(tok[2])
                saw_b = True
            except ValueError:
                r.fault("line %d: 'b' count is not a number" % (lineno + 1))
        elif kind == "c":
            # Patch 310: a render-integrity cvar changed mid-journal.
            nm, val = tok[2], _unquote_pair(" ".join(tok[3:]))[0]
            cvar_changes.append((nm, val))
        elif kind == "g":
            try:
                legacy_states.append(int(tok[2]))
            except ValueError:
                r.fault("line %d: 'g' state is not a number" % (lineno + 1))
        elif kind == "#":
            notes_seen.append(" ".join(tok[2:]))
        else:
            events += 1
            if kind == "x":
                hidden += 1
            if kind in ("+", "-"):
                # Patch 309. Two or three payload fields; three is current.
                if len(tok) not in (4, 5):
                    r.fault("line %d: %r has %d fields, expected 4 (pre-309) "
                            "or 5" % (lineno + 1, kind, len(tok)))
                elif len(tok) == 5:
                    try:
                        prev = int(tok[4])
                    except ValueError:
                        r.fault("line %d: %r prev is not a number"
                                % (lineno + 1, kind))
                        prev = -1
                    if prev >= 0:
                        saw_prev = True
                        if kind == "+":
                            if prev:
                                repeats += 1
                            else:
                                presses += 1
                        elif not prev:
                            orphan_rel += 1
            # Patch 303: every event kind carries its devid as the first payload
            # field, so remember which devids actually produced events. The
            # device table is only worth having if it accounts for them.
            try:
                d = int(tok[2])
            except (ValueError, IndexError):
                pass
            else:
                if kind in ("+", "-", "x"):
                    devids_key[d] = devids_key.get(d, 0) + 1
                else:
                    devids_used[d] = devids_used.get(d, 0) + 1

    # ---- trailer agreement -------------------------------------------------
    if truncated is not None:
        r.info["truncated_at"] = truncated
        r.note("TRUNCATED at t=%.3f -- the journal hit in_journal_maxkb and "
               "stops there. A truncated journal cannot audit the run it "
               "belongs to." % truncated)

    if trailer is None:
        r.fault("no 'end' trailer -- the journal was never closed, so the run "
                "it belongs to has no admissible input record")
    else:
        t_abs, t_events, t_frames, t_dropped, t_hidden = trailer[:5]
        t_injected = trailer[5] if len(trailer) > 5 else None
        t_unenum = trailer[6] if len(trailer) > 6 else None
        t_legacybtn = trailer[7] if len(trailer) > 7 else None
        r.info["events"] = t_events
        r.info["frames"] = t_frames
        r.info["dropped"] = t_dropped
        r.info["hidden"] = t_hidden
        r.info["time"] = t_abs

        # A TRUNCATED FILE CANNOT MATCH ITS OWN TRAILER, by construction: the
        # counters keep running after the cap stops the writing, so the trailer
        # reports what HAPPENED while the body holds what FIT.  Demanding
        # equality there would fault every truncated journal for being
        # truncated, which the 'truncated' marker already says.  What must still
        # hold is the direction -- the trailer can only be ahead.
        if truncated is None:
            if t_events != events:
                r.fault("trailer says %d events, the file has %d"
                        % (t_events, events))
            if t_frames != frames:
                r.fault("trailer says %d frames, the file has %d"
                        % (t_frames, frames))
        else:
            if t_events < events:
                r.fault("trailer says %d events but the file already holds %d"
                        % (t_events, events))
            if t_frames < frames:
                r.fault("trailer says %d frames but the file already holds %d"
                        % (t_frames, frames))
        if truncated is None and t_hidden != hidden:
            r.fault("trailer says %d hidden keys, the file has %d"
                    % (t_hidden, hidden))
        # The '!' markers report drops as they are NOTICED, and the last batch
        # can arrive after the final frame marker, so the trailer is allowed to
        # be ahead of them -- but never behind.
        if t_dropped < dropped:
            r.fault("trailer says %d dropped, but the '!' markers already "
                    "account for %d" % (t_dropped, dropped))
        elif t_dropped:
            r.note("%d input events were LOST by the engine's event ring during "
                   "this journal. The file is not admissible across those gaps; "
                   "the drop time is unknown by construction." % t_dropped)

        if truncated is None and abs(t_abs - clock) > TIME_EPS:
            r.fault("trailer says t=%.6f but the dt sum is %.6f (off by %.6f)"
                    % (t_abs, clock, t_abs - clock))

        # ---- rejected reports (engine Patch 306) ---------------------------
        #
        # THREE STATES, and the middle one is the whole reason this reads the
        # way it does. A missing field means the engine predates the patch; -1
        # means the backend does not count (in_generic.c is cross-platform and
        # only in_win.c maintains these); 0 is an actual measurement. Only the
        # third supports the sentence "nothing was injected", and saying it
        # about either of the other two would be drawing the strictest possible
        # conclusion from the least possible evidence.
        if t_injected is None:
            if saw_i:
                r.fault("'i' records are present but the trailer has no "
                        "injected totals -- the file mixes two grammars")
            else:
                r.note("no injected-report counters: this journal predates "
                       "engine Patch 306, so whether synthesized input was "
                       "REJECTED during it cannot be asked of this file.")
        elif t_injected < 0 or t_unenum < 0:
            r.note("the input backend does not count rejected reports "
                   "(injected=%d unenum=%d); this is not Windows raw input, "
                   "and no claim either way can be made." % (t_injected, t_unenum))
            if saw_i:
                r.fault("'i' records are present although the trailer says "
                        "the backend does not count them")
        else:
            r.info["injected"] = t_injected
            r.info["unenum"] = t_unenum

            # Two independent statements of one quantity, so an edit has to be
            # made consistently in two places. Exempted on a truncated file for
            # the same reason as events/frames above: the counters keep running
            # after the writing stops, so the trailer can only be AHEAD.
            if truncated is None:
                if t_injected != injected:
                    r.fault("trailer says %d injected reports, the 'i' records "
                            "account for %d" % (t_injected, injected))
                if t_unenum != unenum:
                    r.fault("trailer says %d unenumerated reports, the 'i' "
                            "records account for %d" % (t_unenum, unenum))
            else:
                if t_injected < injected or t_unenum < unenum:
                    r.fault("trailer says %d/%d rejected reports but the 'i' "
                            "records already hold %d/%d"
                            % (t_injected, t_unenum, injected, unenum))

            # A NOTE, NEVER A FAULT, and the distinction is the point.
            #
            # A non-zero count means synthesized input was REJECTED -- these
            # reports never reached the view, which is exactly why they were
            # countable. It is evidence of an attempt that FAILED, and it can
            # also be produced by software the player did not choose to run:
            # remote-desktop and accessibility tools, screen sharing, some
            # tablet and macro drivers, and a laptop's own touchpad utility all
            # synthesize input legitimately. Auto-rejecting a run on this would
            # accuse a named person over their screen reader.
            if t_injected:
                r.note("%d synthesized input reports (no device handle) were "
                       "REJECTED by raw input during this journal. They did "
                       "NOT reach the view. This is evidence of an attempt, "
                       "not of a successful cheat, and it has innocent causes "
                       "(remote desktop, accessibility and screen-sharing "
                       "tools all synthesize input) -- review, never auto-"
                       "reject." % t_injected)
            if t_unenum:
                r.note("%d reports came from a real device that was never "
                       "enumerated -- a mouse plugged in after startup, or an "
                       "RDP device excluded by in_rawinput_rdp. That device's "
                       "motion is going nowhere, which is a usability bug and "
                       "not a cheating signal." % t_unenum)

        # ---- the legacy click path (engine Patch 307) ----------------------
        #
        # Two different facts, kept apart on purpose:
        #   'b' / t_legacybtn -- presses raw input could NOT corroborate, which
        #                        DID reach the game. Unlike 'i', these were acted on.
        #   header nolegacylive + 'g' -- whether the legacy path was even open,
        #                        and WHEN. The setting is grab-scoped, so this is
        #                        not constant over a run and a single value at
        #                        `begin` cannot describe it.
        if t_legacybtn is None:
            if saw_b:
                r.fault("'b' records are present but the trailer has no "
                        "legacy-button total -- the file mixes two grammars")
        elif t_legacybtn < 0:
            if saw_b:
                r.fault("'b' records are present although the trailer says "
                        "the backend does not count them")
        else:
            r.info["legacy_presses"] = t_legacybtn
            if truncated is None and t_legacybtn != legacybtn:
                r.fault("trailer says %d uncorroborated legacy presses, the "
                        "'b' records account for %d" % (t_legacybtn, legacybtn))
            elif truncated is not None and t_legacybtn < legacybtn:
                r.fault("trailer says %d uncorroborated legacy presses but the "
                        "'b' records already hold %d" % (t_legacybtn, legacybtn))

            # A NOTE. The engine genuinely cannot name the cause here: a Windows
            # precision touchpad is a HID digitizer with no raw button reports
            # at all, so on such a machine EVERY honest click lands in this
            # count. The Patch 303 device table is what separates the two, and
            # that is a judgement for a reviewer holding both, not for this tool.
            if t_legacybtn:
                r.note("%d mouse press(es) were accepted although raw input "
                       "was live and could not corroborate them. These DID "
                       "reach the game. Innocent on a machine with a precision "
                       "touchpad or a non-RIM_TYPEMOUSE pointer (no raw button "
                       "reports exist for those); otherwise this is the shape "
                       "of an injected click. Check the device table above "
                       "before concluding anything." % t_legacybtn)

        if "nolegacylive" in head:
            try:
                live0 = int(head["nolegacylive"])
            except ValueError:
                live0 = None
            if live0 is not None:
                states = [live0] + legacy_states
                r.info["nolegacy_at_start"] = live0
                if legacy_states:
                    r.info["nolegacy_changes"] = len(legacy_states)
                # "Was the legacy click path open at any point" is the question
                # that matters, and only the union of the header and the 'g'
                # records answers it. A run that was protected throughout is the
                # only one that may be described that way.
                if all(st == 1 for st in states):
                    r.info["legacy_path"] = "suppressed for the whole journal"
                elif any(st == 1 for st in states):
                    r.note("the legacy mouse path was open for part of this "
                           "journal (%d state change(s) recorded). "
                           "in_rawinput_nolegacy is grab-scoped, so anything "
                           "that ungrabs the mouse reopens it; an injected "
                           "click landing in one of those spans would be "
                           "accepted." % len(legacy_states))
                else:
                    r.info["legacy_path"] = ("open -- injected clicks are not "
                                             "blocked in this session")
        elif t_legacybtn is not None:
            r.note("no nolegacylive key: this journal predates engine Patch "
                   "307's header, so whether the legacy click path was open "
                   "cannot be read from it.")

    # ---- render integrity (engine Patch 310) -------------------------------
    #
    # These settings change what the player could SEE. r_fog_progless 0 restores
    # the pre-266 behaviour in which program-less surfaces take no distance fog,
    # which on a fogged map means seeing through it across much of the world --
    # and it is CVAR_ARCHIVE, not CVAR_CHEAT, so nothing gates it. r_fullbright
    # and r_drawflat carry no flags at all.
    #
    # REPORTED, NEVER FAULTED. This tool records what a run was played with; a
    # ranked GATE is a policy decision made elsewhere, with a client-cvar
    # channel that does not exist yet. Faulting here would be this tool deciding
    # the rules on its own.
    if rendercvars:
        nondefault = [(n, v, d) for (n, v, d) in rendercvars
                      if d != "-" and v != d]
        r.info["render_cvars"] = "%d recorded, %d not at default" % (
            len(rendercvars), len(nondefault))
        for n, v, d in nondefault:
            r.info["render[%s]" % n] = "%s (default %s)" % (v, d)
            r.note("%s is %s, not its default %s -- this changes what the "
                   "player could see. Recorded, not judged." % (n, v, d))
        missing = [n for (n, v, d) in rendercvars if d == "-"]
        if missing:
            # `-` is "no such cvar in that build", which is NOT the same as 0
            # and must not be read as one.
            r.note("%d render cvar(s) do not exist in the build that wrote this "
                   "file (%s) -- no value can be read for them either way."
                   % (len(missing), ", ".join(missing)))
    else:
        r.note("no render-integrity table: this journal predates engine Patch "
               "310, so what the player could SEE -- fog, fullbright, vis -- "
               "is not recorded and cannot be asked of this file.")

    # Patch 312: the same treatment for the cvars that change what the counts
    # BECOME. in_xflip is the one that forced this table to exist -- it negates
    # mx upstream of both journal taps, so with it set every frame reads
    # sum(m).dx == -v.dx while dy is untouched, and before 312 nothing in the
    # file said so. An honest player was indistinguishable from a sign-flipping
    # hook, which is the Patch 305 failure mode exactly.
    if inputcvars:
        nondefault = [(n, v, d) for (n, v, d) in inputcvars
                      if d != "-" and v != d]
        r.info["input_cvars"] = "%d recorded, %d not at default" % (
            len(inputcvars), len(nondefault))
        for n, v, d in nondefault:
            r.info["input[%s]" % n] = "%s (default %s)" % (v, d)
            r.note("%s is %s, not its default %s -- this changes what the "
                   "player's counts become. Recorded, not judged." % (n, v, d))
        missing = [n for (n, v, d) in inputcvars if d == "-"]
        if missing:
            r.note("%d input cvar(s) do not exist in the build that wrote this "
                   "file (%s) -- no value can be read for them either way."
                   % (len(missing), ", ".join(missing)))
    else:
        r.note("no input-pipeline table: this journal predates engine Patch "
               "312, so in_xflip and leftisright -- either of which silently "
               "inverts a sign the checks depend on -- cannot be asked of this "
               "file.")

    if cvar_changes:
        # THE POINT OF TRACKING modifiedcount RATHER THAN THE VALUE. A cvar set
        # and set back leaves the header and the final state identical, so a
        # reader comparing start against end concludes nothing happened. These
        # records say it did, and when.
        r.info["render_changes"] = len(cvar_changes)
        seen = {}
        for n, v in cvar_changes:
            seen.setdefault(n, []).append(v)
        for n, vals in sorted(seen.items()):
            r.note("%s was changed DURING this journal (%s). A run is not "
                   "described by its opening settings if they did not hold."
                   % (n, " -> ".join(vals)))

    # ---- key presses vs auto-repeat (engine Patch 309) ---------------------
    #
    # WHY THIS MATTERS MORE THAN IT LOOKS.  Before Patch 309 a '+' meant "a
    # key-down was dispatched", and OS auto-repeat dispatches one every ~30ms
    # for as long as a key is held.  Measured on a clean bhop_eazy PB: 326 downs
    # against 130 releases, and on the two turn keys alone 144 downs against 15
    # releases -- 89.6% of the turn-key press records described presses that
    # never happened.  The shape that invents (a fast, perfectly even train) is
    # the shape a scripted turn has, so the record was manufacturing the
    # signature it exists to look for.
    if saw_prev:
        r.info["key_presses"] = presses
        r.info["key_repeats"] = repeats
        if presses + repeats:
            r.info["key_repeat_pct"] = 100.0 * repeats / (presses + repeats)
        if orphan_rel:
            # A release whose key was not down.  Ordinary after a focus change:
            # the engine's scancode -1 'release everything' sweep clears the
            # state, and any key still physically held then reports its own
            # release as an orphan.  Worth surfacing, never a fault.
            r.info["orphan_releases"] = orphan_rel
            r.note("%d release(s) for a key that was not down. Expected after "
                   "a focus change (the release-everything sweep clears the "
                   "state while a key is still physically held); otherwise it "
                   "means a press went missing from this record." % orphan_rel)
    elif any(k in head for k in HEAD_P293):
        if r.info.get("rawkbd_legacy"):
            r.note("no press/repeat column: this journal predates engine Patch "
                   "309 AND rawkbd is 0, so its keys came from the legacy "
                   "WM_KEYDOWN path, which AUTO-REPEATS. The '+' records are a "
                   "MIXTURE of real presses and repeats at the OS repeat rate, "
                   "cannot be counted as presses, and must not be paired with "
                   "the '-' records naively.")
        else:
            r.note("no press/repeat column: this journal predates engine Patch "
                   "309, so its '+' records cannot be separated from any OS "
                   "auto-repeat and cannot be counted as presses.")
    r.info.pop("rawkbd_legacy", None)

    # ---- devices (engine Patch 303) ----------------------------------------
    #
    # A pre-303 file has no tables at all.  That is reported and never faulted:
    # the question simply cannot be asked of those files, and "absent" must not
    # be allowed to read as "no devices found".
    if not devs and not devmaps:
        r.info["devices"] = "not recorded (pre-303 journal)"
    else:
        real = [d for d in devs if d[2] not in PSEUDO_DEVICES]
        # Broken down by type rather than totalled as "physical", because this
        # tool cannot tell a plugged-in controller from an empty XInput slot --
        # the backend enumerates xi0..xi3 either way. Counting those as physical
        # hardware would be asserting something the file does not say.
        bytype = {}
        for dtype, _did, _name in real:
            bytype[dtype] = bytype.get(dtype, 0) + 1
        r.info["devices"] = "%d enumerated: %s (+%d pseudo)" % (
            len(devs),
            ", ".join("%d %s" % (n, t) for t, n in sorted(bytype.items())) or "none",
            len(devs) - len(real))
        # Indexed by POSITION, not by (type, devid).  Keying on the devid would
        # collapse every device that still reads `unset` onto one entry and show
        # a two-mouse machine as having one -- which is the same "a dict keeps
        # only the last one" mistake the `dev` lines are kept in a list to avoid.
        for idx, (dtype, did, name) in enumerate(real):
            r.info["device[%d]" % idx] = "%-8s devid %-5s %s" % (dtype, did, name)

        # A devid claimed by two devices makes EVERY attribution in the file
        # ambiguous, so this one is a fault rather than a note.
        claimed = {}
        for dtype, did, name in devmaps:
            if did in ("-", "unset"):
                continue
            if did in claimed and claimed[did] != name:
                r.fault("devid %s is claimed by two devices (%r and %r) -- no "
                        "event in this file can be attributed to either"
                        % (did, claimed[did], name))
            claimed[did] = name

        # THE CHECK THE TABLE EXISTS FOR: an event carrying a devid that no
        # device accounts for.  A NOTE and not a fault -- a device unplugged
        # mid-run legitimately leaves its events behind with nothing left to
        # enumerate, and that is a fact about the run rather than a forgery.
        #
        # POINTER DEVICES ONLY, and that restriction fixes a false positive this
        # check had from the day it was written.  On the legacy keyboard path --
        # in_rawinput_keyboard 0, the SHIPPED DEFAULT -- every key event is
        # dispatched with a HARDCODED devid 0 (gl_vidnt.c passes the literal),
        # while the enumerated system keyboard is written `-`, meaning "cannot
        # carry a devid at all".  So devid 0 is used by every keystroke and
        # claimed by no keyboard, and this check would report the player's own
        # keyboard as hardware the file cannot account for.
        #
        # The other half is worse and silent: when a mouse HAS been allocated
        # devid 0 -- the common case, it is the first one handed out -- the
        # table positively asserts that devid 0 is that mouse, and every
        # keystroke in the file then reads as having come from it.  Nothing
        # warned about that because nothing looked.
        #
        # The saving grace is that the RECORD KIND already separates them: a
        # '+'/'-'/'x' is a key and an 'm'/'a'/'j' is a pointer, whatever devid
        # they share.  So attribution is still possible per kind, and the fix is
        # to stop asking the pointer question about keyboard events.
        for did, n in sorted(devids_used.items()):
            if str(did) not in claimed:
                r.note("devid %d produced %d pointer events but no device in "
                       "the table claims it -- it was unplugged mid-run, or "
                       "the file is not describing its own hardware." % (did, n))

        # The keyboard side, asked correctly.
        try:
            kbds_live = int(head.get("rawkbds", -1))
        except ValueError:
            kbds_live = -1
        if devids_key:
            r.info["key_devids"] = ", ".join(
                "%d(%d)" % (d, n) for d, n in sorted(devids_key.items()))
            if kbds_live > 0:
                # Raw keyboard IS bound, so these devids are real identities and
                # the table must account for them.
                for did, n in sorted(devids_key.items()):
                    if str(did) not in claimed:
                        r.note("devid %d produced %d key events but no device "
                               "in the table claims it, and raw keyboard was "
                               "live (rawkbds %d) -- so this devid should have "
                               "been a real keyboard." % (did, n, kbds_live))
            else:
                # The legacy path. devid 0 is a constant, not an identity.
                if set(devids_key) - {0}:
                    r.note("key events carry devid(s) other than 0 although raw "
                           "keyboard was not bound -- the legacy path dispatches "
                           "a hardcoded 0, so this file does not match the "
                           "engine it claims to come from.")
                else:
                    r.info["key_attribution"] = (
                        "not available -- raw keyboard is not bound, so every "
                        "key event carries a hardcoded devid 0 that names no "
                        "device (and is NOT the mouse that may hold devid 0)")

        # The two tables disagreeing means the device set changed mid-run.
        before = set((d[0], d[2]) for d in devs)
        after = set((d[0], d[2]) for d in devmaps)
        for dtype, name in sorted(after - before):
            r.note("%s %r appeared DURING the run -- it is in the closing table "
                   "and not the opening one." % (dtype, name))
        for dtype, name in sorted(before - after):
            r.note("%s %r VANISHED during the run -- it was enumerated at the "
                   "start and is gone from the closing table." % (dtype, name))

        # Patch 301's bound-device count and Patch 303's table are written from
        # the same rawmice[] array, so they agree unless the device set changed
        # between raw-input init and the journal opening.  Worth saying when it
        # does; not worth accusing anyone over.
        if "rawmice" in head:
            try:
                mice_hdr = int(head["rawmice"])
            except ValueError:
                mice_hdr = -1
            mice_tbl = len([d for d in real if d[0] == "mouse"])
            if mice_hdr >= 0 and mice_hdr != mice_tbl:
                r.note("header says rawmice %d but the device table lists %d "
                       "physical mice -- the device set changed between raw "
                       "input initialising and this journal opening."
                       % (mice_hdr, mice_tbl))

        resolved = len([d for d in devmaps if d[1] not in ("-", "unset")])
        if not resolved:
            r.info["devices_resolved"] = ("none -- no ENUMERATED device was ever "
                                          "allocated a devid. Note this says "
                                          "nothing about whether the file has "
                                          "events: injected ones carry a devid "
                                          "no device owns.")

    # THE IDENTITY IS CHECKED BEFORE THE FRAME-MARKER BAIL-OUT, deliberately.
    # It reads 'v' records, which are written per accumulate-frame by the client;
    # 'f' markers are written per non-empty EVENT DRAIN. Those are independent,
    # and a file can legitimately have the first without the second -- a journal
    # in which the view turned but no input event arrived, which is exactly what
    # a +left/+right arm produces. Returning early here meant the whole Patch 305
    # falsifier reported nothing at all: the check that had to be tested was the
    # one being skipped, and its silence read as "nothing to say".
    check_identity(r, head, views)
    # Patch 312, and ABOVE the same bail-out for the same reason -- plus its own:
    # the join is the one check whose most interesting subject is a file with
    # counts that reached no view at all.
    check_counts_join(r, joins, bool(inputcvars))

    if not frames:
        r.fault("no frame markers -- nothing was ever drained while the journal "
                "was open")
        return r

    span = (last_f - first_f) if (first_f is not None and last_f is not None) else 0
    r.info["first_frame_at"] = first_f
    if span > 0:
        r.info["frame_rate"] = frames / span
        if events:
            r.info["events_per_sec"] = events / span
            r.info["events_per_frame"] = events / float(frames)

    if seqs:
        r.info["movesequence"] = "%d..%d" % (min(seqs), max(seqs))
        back = sum(1 for a, b in zip(seqs, seqs[1:]) if b < a)
        if back:
            r.fault("movesequence goes backwards %d times -- a journal spans one "
                    "run and cl.movesequence only resets on a map change, which "
                    "drops the journal" % back)

    # ---- the synth poison (engine Patch 202, sourced by Patch 311) ---------
    if synthflag:
        r.info["synth"] = "1"
        src = [n.split("SYNTH source", 1)[1].strip()
               for n in notes_seen if "SYNTH source" in n]
        if src:
            r.info["synth_source"] = ", ".join(sorted(set(src)))
            r.note("synth 1 (source: %s) -- this journal contains INJECTED "
                   "events and is NOT admissible as a record of anything a "
                   "person did. `plugin` means a native DLL called the engine's "
                   "own input API; `in_journal_synth` means the format test "
                   "command. They are the same flag and very different facts."
                   % r.info["synth_source"])
        else:
            # Pre-311: the flag exists but nothing recorded who set it. Do NOT
            # say "in_journal_synth" here, which is what this tool used to do --
            # on a pre-311 file the source is genuinely unknown, and naming the
            # innocent one would be an attribution the file does not support.
            r.note("synth 1 -- this journal contains INJECTED events and is NOT "
                   "admissible. The SOURCE is not recorded: this file predates "
                   "engine Patch 311, so it cannot say whether the test command "
                   "or a plugin put them there.")

    for n in notes_seen:
        r.note("mark: %s" % n)
    if notes_seen:
        r.info["marks"] = len(notes_seen)

    if events == 0:
        r.note("no input events at all. That is the EXPECTED result for a "
               "scripted config: a console +forward is a command-buffer entry "
               "and never passes through in_newevent, so it cannot appear here.")

    return r


# ---------------------------------------------------------------------------
# THE COUNTS JOIN -- engine Patch 312 (plan item P294b)
# ---------------------------------------------------------------------------
# WHAT IT IS FOR, and why the yaw identity below is not enough on its own.
#
# Patch 293 proves the angle is a fixed multiple of the counts. But BOTH of its
# sides are computed by the engine from the same mx, so it tests the engine's
# multiplication and not the player: a hook that rewrites the accumulated delta
# UPSTREAM of mx gets a conforming 293 record for free, and the yaw it produces
# is the doctored one. That is the FTE shape of what momentum.dll already does to
# CInput::ApplyMouse, and 293's own essay says so.
#
# This joins the other end. The 'm' records are transcribed straight off the
# event ring during the drain; the counts on the 'd'/'v' pair are read out of
# mouse->delta[] in IN_MoveMouse. Those are the two ends of exactly the window
# such a hook occupies, so a disagreement between them IS that hook.
#
#     sum(m.dx over the window)  ==  raw
#       where raw is the 'd' record if the frame had one, and the 'v' record's
#       own dx if it did not -- a missing 'd' being the engine's positive claim
#       that the pipeline passed the counts through untouched.
#
# MEASURED BEFORE THE PATCH WAS WRITTEN, on every journal in the tree: 45,447 'v'
# records including one real 4976-tick PB, and the join holds on 45,384 of 45,384
# covered frames, 100.000000%. So it needed no new key to join on.
#
# Simulated against that same PB, a delta-mutating hook touching 93.68% of frames
# moves 293's median residual from 0.121000 to 0.121001 degrees -- the sixth
# decimal -- and moves this check from 0.00% to 93.68%. Detection is integer-exact
# per frame against a measured false-positive floor of zero, so one frame is
# enough. The two checks are complementary rather than redundant: a hook that
# faithfully re-emits the counts and mutates only the angle passes this and fails
# 293 instead.
#
# WHAT IT DOES NOT COVER, because overselling it would be worse than not having
# it: an edit to the event ring BEFORE the drain is recorded as truth by the 'm'
# record itself, and so is an overwrite of the _GRID GetRawInputData pointer.
# Anyone who can hook the journal's own writer authors the whole file. This check
# spans the ring read to the delta read, and claims nothing outside it.
#
# EXEMPTIONS, both of which the file discloses itself rather than the reader
# assuming them:
#   - the FIRST window of a file, which began before `begin` and is short by an
#     unknowable amount. The engine deliberately does NOT fix this by clearing
#     the pending delta at in_journal_begin: that would throw away counts the
#     player already made, and the engine must not alter a player's aim to tidy
#     its own evidence.
#   - a window holding an 'a' record. An absolute position can put counts into
#     the view that were journalled as 'a' and never as 'm', so the two sides are
#     not measuring the same thing there. Reported, never faulted.
def check_counts_join(r, joins, post312):
    if not joins:
        return
    # The comparison is between integer device counts and wants to be exact. The
    # tolerance exists only because the engine writes the raw pair with %g, i.e.
    # six significant digits, so a large sum could round in the file; it is three
    # orders below one count and cannot mask a real mutation, whose smallest
    # possible size is exactly one.
    TOL = 1e-3
    checked = broke = unjoinable = withd = 0
    worst = []
    for (ln, mx, my, rx, ry, flags, nm, na, had_d) in joins[1:]:
        if had_d:
            withd += 1
        if na:
            unjoinable += 1
            continue
        checked += 1
        if abs(mx - rx) > TOL or abs(my - ry) > TOL:
            broke += 1
            if len(worst) < 8:
                worst.append((ln, mx, my, rx, ry, nm))
    r.info["join_checked"] = checked
    r.info["join_broke"] = broke
    r.info["join_transforms"] = withd

    if withd:
        r.note("%d of %d view frames carry a 'd' record: the input pipeline "
               "changed the counts on the way through (in_xflip, a discard "
               "while the cursor was free, the touch-path boost, or a menu or "
               "CSQC consumer). Disclosed, not suspicious -- the engine states "
               "what it did and the join is made against the stated value."
               % (withd, len(joins) - 1))
    if unjoinable:
        r.note("%d view frames could not be joined because an absolute-position "
               "record fell in the same window: those counts entered the view "
               "as 'a' and never as 'm', so the two sides are not measuring the "
               "same quantity. Not a finding." % unjoinable)
    if not checked:
        r.note("no joinable view frames -- the counts join had nothing to test.")
        return

    if not broke:
        r.note("counts join HOLDS on all %d joinable view frames: every view "
               "delta equals the raw reports the ring delivered for it."
               % checked)
        return

    pct = 100.0 * broke / checked
    detail = "; ".join("line %d: sum(m)=(%g,%g) but raw=(%g,%g) over %d report(s)"
                       % (ln, mx, my, rx, ry, nm) for (ln, mx, my, rx, ry, nm) in worst)
    if not post312:
        # ABSENT IS NOT ZERO. Without the 'd' record this file cannot say whether
        # a difference was a legitimate transform or a mutated delta, and naming
        # it a fault would accuse every pre-312 recording that merely had
        # in_xflip set or a console opened mid-run.
        r.note("counts join differs on %d of %d view frames (%.2f%%), but this "
               "journal PREDATES engine Patch 312 and carries no 'd' records, so "
               "a legitimate pipeline transform cannot be told from a mutated "
               "delta. Unanswerable rather than failed. %s"
               % (broke, checked, pct, detail))
        return
    # A post-312 file states its own transforms, so a residual difference is two
    # statements of one quantity disagreeing -- the definition this tool reserves
    # a fault for.
    r.fault("COUNTS JOIN BROKEN on %d of %d view frames (%.2f%%): the view delta "
            "does not equal the raw reports the ring delivered, and the journal "
            "declared no transform for them. This is the signature of something "
            "rewriting the accumulated mouse delta between the event ring and "
            "IN_MoveMouse. %s" % (broke, checked, pct, detail))


# ---------------------------------------------------------------------------
# THE YAW IDENTITY -- engine Patch 293
# ---------------------------------------------------------------------------
# With m_filter 0 and m_accel 0 the engine's mouse path is one exact line:
#
#     viewanglechange[YAW] -= m_yaw * (sensitivity * in_sensitivityscale) * dx
#
# so for an unmodified client every frame's yaw change is a FIXED multiple of the
# integer device counts that frame drained.  Anything that sits between the
# device and the angle and changes the number -- which is where this class of
# cheat lives, because it is the only place the value is both final and still a
# mouse delta -- breaks the equality on every frame it touches.
#
# WHAT THIS IS AND IS NOT.  It is an algebraic identity, not a statistic: a
# violation is arithmetic, not a probability.  It says nothing whatever about
# whether a HUMAN produced the counts -- a replayed or synthesised stream
# satisfies it perfectly.  It answers only "did the angle come from the counts".
#
# WHY THE CHECK IS SKIPPED RATHER THAN FAILED in several cases below: a check
# that reports a fault it cannot distinguish from a configuration is worse than
# no check, because the first false accusation is what people remember.
def check_identity(r, head, views):
    if not views:
        if "sensitivity" in head:
            r.note("no 'v' records, but the header carries Patch 293's scale "
                   "terms -- the journal was opened by a 293 engine and the "
                   "player never moved the mouse, or every frame was idle.")
        else:
            r.note("no 'v' records: pre-Patch-293 journal. The yaw identity is "
                   "NOT CHECKABLE from this file, and it cannot be recovered by "
                   "cross-checking the .view either -- the 'f' marker is written "
                   "only on a non-empty drain, so .hid frames are a subset of "
                   "rendered frames and the two cannot be aligned.")
        return

    r.info["view_records"] = len(views)

    missing = [k for k in ("sensitivity", "sensitivityscale", "m_yaw") if k not in head]
    if missing:
        r.fault("'v' records present but the header is missing %s -- a 293 "
                "engine always writes them together, so this file has been "
                "edited or assembled" % ", ".join(missing))
        return

    try:
        sens = float(head["sensitivity"])
        scale = float(head["sensitivityscale"])
        myaw = float(head["m_yaw"])
        mfilter = float(head.get("m_filter", "0"))
        maccel = float(head.get("m_accel", "0"))
    except ValueError:
        r.fault("a Patch 293 header scale term is not a number")
        return

    k = -myaw * sens * scale
    r.info["deg_per_count"] = abs(k)

    if mfilter != 0 or maccel != 0:
        # Both are still deterministic functions of (dx, dy, frametime), so this
        # is a "not implemented here" rather than a "cannot be done" -- but
        # m_accel needs the frametime, which this file does not carry per frame.
        r.note("m_filter %g / m_accel %g -- the yaw path is not the plain linear "
               "one and this tool does not model it, so the identity is NOT "
               "checked. A ranked run must pin both to 0." % (mfilter, maccel))
        return

    if k == 0:
        r.note("m_yaw*sensitivity is zero -- no yaw can be produced from counts, "
               "identity vacuous")
        return

    # Frames the identity does not govern, each for a stated reason.
    applicable = [v for v in views if not (v[3] & (VF_STRAFE_X | VF_FREE))]
    skipped = len(views) - len(applicable)
    if skipped:
        r.info["frames_not_governed"] = skipped

    if len(applicable) < 2:
        r.note("fewer than two governed frames -- nothing to test")
        return

    # THE TOLERANCE IS MAGNITUDE-SCALED, AND THE FIXED ONE WAS A BUG.
    #
    # It used to be a flat 2e-6, on the reasoning that the angle is printed at
    # %.6f so two half-steps is the resolution floor. That reasoning is right
    # about the PRINT and wrong about the VALUE: viewangles is a float32, whose
    # ulp at |yaw| = 180 is 1.526e-5 -- seven times the old epsilon. Differencing
    # two of them cannot be more exact than the type, so the old floor demanded
    # precision the engine could not physically carry.
    #
    # Measured on bhop_eazy 0004976_pb: 12,751 of the 22,844 frames this check
    # faulted on (55.8%) had NO turn key held at all and a residual whose maximum
    # was 2.30e-5 deg -- 0.0021 of a single mouse count. They were float32 ulps
    # being reported as evidence of a cheat.
    #
    # 2**-22 of |yaw| is about 1.5 ulp, i.e. 4.3e-5 at 180 deg, roughly twice the
    # worst residual actually observed on a clean run.
    def yaw_eps(a, b):
        return max(2e-6, max(abs(a), abs(b)) * (2.0 ** -22))

    # Pre-305 files carry no keyboard term, and ABSENT IS NOT ZERO. Treating a
    # missing column as 0 would re-create the very false positive Patch 305 was
    # written to remove, so those files get a note instead of a fault.
    have_kbd = all(v[7] is not None for v in applicable)

    violations = []
    ghost = []          # yaw moved with nothing recorded behind it
    for idx in range(1, len(applicable)):
        p, c = applicable[idx - 1], applicable[idx]
        dyaw = c[5] - p[5]
        if dyaw > 180.0:
            dyaw -= 360.0
        elif dyaw < -180.0:
            dyaw += 360.0
        kyaw = c[7] if c[7] is not None else 0.0
        pred = k * c[1] + kyaw
        err = abs(dyaw - pred)
        if err > yaw_eps(p[5], c[5]) + abs(pred) * 1e-6:
            if c[1] == 0 and kyaw == 0.0:
                ghost.append((c[0], dyaw))
            else:
                violations.append((c[0], c[1], dyaw, pred, err))

    r.info["identity_frames"] = len(applicable) - 1
    r.info["identity_violations"] = len(violations)

    if ghost and not have_kbd:
        # On a pre-305 file a "ghost" is almost certainly just keyboard turn.
        # Measured on 0004976_pb: 1,938 ghost frames, and 100% of them fell
        # inside a +left or +right hold -- 0 under neither. Calling those
        # suspicious would be calling the prestrafe suspicious.
        r.note("%d frame(s) where the yaw moved with zero mouse counts (first at "
               "line %d). On a pre-305 file this is EXPECTED and not a finding: "
               "+left/+right are default binds and their contribution was not "
               "recorded, so it cannot be told from an injected turn here. "
               "Patch 305 separates the two." % (len(ghost), ghost[0][0]))
    elif ghost:
        # Post-305 this MEANS something: the engine recorded the keyboard term
        # and it was zero, so the angle moved with nothing accounted for.
        r.note("%d frame(s) where the yaw moved with ZERO mouse counts AND zero "
               "recorded keyboard turn (first at line %d). The engine recorded "
               "no cause for that motion. A server angle set looks like this and "
               "so does an injected turn -- corroborate against the .rec before "
               "concluding either." % (len(ghost), ghost[0][0]))

    if violations and not have_kbd:
        # PRE-305 FILE. The engine did not record the keyboard turn, so a
        # residual here is unattributable: +left/+right are SHIPPED DEFAULT BINDS
        # (default.cfg:794,805) and the prestrafe this game is built around is
        # performed with them, so on a real run most of these are legitimate
        # play. Measured on 0004976_pb: 10,093 of 10,093 non-noise residuals fell
        # inside a +left or +right hold, with the sign matching CL_AdjustAngles
        # 8,433 times out of 8,437. Faulting here would accuse the player of the
        # game's own core mechanic.
        r.note("identity unresolved on %d of %d governed frames, and this file "
               "CANNOT SETTLE IT: it is pre-305, so the non-mouse angle change "
               "(+left/+right, in_rotate) was never recorded. Those keys are "
               "default binds and the prestrafe uses them, so a residual here is "
               "not evidence of anything. Re-record on engine patch 305 or later "
               "to make this checkable."
               % (len(violations), len(applicable) - 1))
    elif violations:
        worst = max(violations, key=lambda v: v[4])
        r.fault("YAW IDENTITY BROKEN on %d of %d governed frames. The angle did "
                "not come from the counts OR the recorded keyboard turn. Worst: "
                "line %d, %g counts should give %.6f deg, file says %.6f "
                "(off by %.6f)."
                % (len(violations), len(applicable) - 1,
                   worst[0], worst[1], worst[3], worst[2], worst[4]))
    elif ghost:
        # "exact on all N" WHILE N FRAMES HAVE NO RECORDED CAUSE IS A CONTRADICTION,
        # and it printed exactly that during the Patch 305 falsifier: the zeroed
        # control reported "exact on all 150" and "150 frames with no recorded
        # cause" in the same block, about the same 150 frames. Ghosts are excluded
        # from `violations` because they are a different shape of wrong -- they
        # must not then be silently counted as passes.
        r.info["identity"] = ("holds on the %d frame(s) with a recorded cause; "
                              "%d frame(s) had NONE (see the note below)"
                              % (len(applicable) - 1 - len(ghost), len(ghost)))
    elif have_kbd:
        r.info["identity"] = ("exact on all %d governed frames (mouse + recorded "
                              "keyboard turn)" % (len(applicable) - 1))
    else:
        r.info["identity"] = "exact on all %d governed frames" % (len(applicable) - 1)


def cross_check(hid, viewpath):
    """Does the .hid agree with the .view sitting next to it?"""
    if not os.path.exists(viewpath):
        return
    with open(viewpath, "r", encoding="utf-8", errors="replace") as f:
        lines = [l.rstrip("\n").rstrip("\r") for l in f]
    if not lines or not lines[0].startswith("FTESURF-VIEW"):
        return

    head = {}
    i = 1
    while i < len(lines) and lines[i].strip() != "begin":
        p = lines[i].split(None, 1)
        if p:
            head[p[0]] = p[1] if len(p) > 1 else ""
        i += 1
    i += 1

    frames = []
    for s in lines[i:]:
        t = s.split()
        if len(t) == 6:
            try:
                frames.append([float(x) for x in t])
            except ValueError:
                pass
    if not frames:
        return

    # The .view's own claim about whether a journal was taken.  A .hid beside a
    # sidecar that says hid 0 means the two files disagree about the run they
    # both describe, which is worse than either being wrong alone.
    if "hid" in head:
        hid.info["view_hid"] = head["hid"]
        if head["hid"].strip() == "0":
            hid.fault("the .view beside this journal says 'hid 0' -- the sidecar "
                      "claims no journal was taken for this run, and here one is")

    vseq = [f[1] for f in frames]
    hid.info["view_movesequence"] = "%d..%d" % (int(min(vseq)), int(max(vseq)))
    if "movesequence" in hid.info:
        lo, hi = (int(x) for x in hid.info["movesequence"].split(".."))
        if hi < min(vseq) or lo > max(vseq):
            hid.fault("the journal's movesequence range %s does not overlap the "
                      "sidecar's %s -- these are two different runs"
                      % (hid.info["movesequence"], hid.info["view_movesequence"]))

    # THE START GAP, measured rather than assumed.  Rec_HidBegin issues its
    # in_journal_begin through localcmd, which the Cbuf runs on the NEXT frame --
    # after that frame's IN_Commands has already drained.  So the journal starts
    # about two video frames after the sidecar.  Reported, not faulted: it is a
    # known and documented cost, and the number is the useful part (~6 ms at 300
    # fps, ~500 ms at a headless 4 fps).
    if "first_frame_at" in hid.info and hid.info["first_frame_at"] is not None:
        # Both are seconds from their own zero, so only the SHAPE is comparable;
        # the .view's cltime zero is the map load, the .hid's base is the run.
        # What is comparable is duration, and a journal covering more wall time
        # than the sidecar means it was left open across something.
        vspan = frames[-1][0] - frames[0][0]
        hid.info["view_span"] = vspan
        if "time" in hid.info and hid.info["time"] > vspan + 1.0:
            hid.note("the journal covers %.2fs against the sidecar's %.2fs. More "
                     "than a frame or two of difference means it stayed open "
                     "across a save/load splice -- check the marks."
                     % (hid.info["time"], vspan))


def emit(r, verbose):
    tag = "ok  " if r.ok else "FAIL"
    print("%s %s" % (tag, os.path.basename(r.path)))
    if verbose or not r.ok:
        # THIS LIST IS AN ORDERING, NOT A FILTER, AND THAT DISTINCTION IS A BUG
        # FIX. It used to be a filter, and it silently swallowed two separate
        # features: Patch 301's 'rawmice'/'rawkbds' (the raw-input grant was
        # checked and then never shown) and Patch 293's 'identity' (a PASSING
        # identity check printed nothing at all, so the only way to see the check
        # existed was to break it). Both were invisible for the same reason, and
        # in both cases the falsifier still passed because faults print
        # unconditionally -- so nothing ever pointed at the omission.
        #
        # Anything not named here now prints after the ordered keys instead of
        # vanishing. A reporter that can silently drop a result is the wrong
        # shape for a tool whose whole job is to report results.
        ORDER = ("version", "map", "rawinput", "rawkbd", "rawmice", "rawkbds",
                 "synth", "synth_source", "devices", "devices_resolved", "identity",
                 "identity_frames", "identity_violations", "frames_not_governed",
                 "time", "events", "frames", "dropped", "hidden",
                 "render_cvars", "render_changes", "key_devids", "key_attribution", "key_presses", "key_repeats", "key_repeat_pct",
                 "orphan_releases", "injected", "unenum", "legacy_presses",
                 "legacy_path", "nolegacy_at_start", "nolegacy_changes", "marks",
                 "truncated_at", "frame_rate", "events_per_sec",
                 "events_per_frame", "movesequence", "view_movesequence",
                 "view_hid", "view_span")

        def show(k):
            v = r.info[k]
            if isinstance(v, float):
                print("       %-20s %.4f" % (k, v))
            else:
                print("       %-20s %s" % (k, v))

        for k in ORDER:
            if k in r.info:
                show(k)
        for k in sorted(r.info):
            if k not in ORDER:
                show(k)
    for m in r.faults:
        print("       FAULT  %s" % m)
    if verbose or not r.ok:
        for m in r.notes:
            print("       note   %s" % m)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    paths = args.files
    if not paths:
        # Build 23's data/runs/<map>/<leg>/ first, then the old flat layout --
        # both, so a tree that has not been through tools/migrate_runs.py is
        # still swept rather than silently reported clean because it is empty.
        paths = sorted(glob.glob(os.path.join(RUNS, "*", "*", "*.hid")) +
                       glob.glob(os.path.join(RUNS, "*.hid")))
        if not paths:
            print("no .hid files in %s" % RUNS)
            return 0

    bad = 0
    for p in paths:
        if not os.path.exists(p):
            print("FAIL %s -- no such file" % p)
            bad += 1
            continue
        r = check_hid(p, args.verbose)
        cross_check(r, os.path.splitext(p)[0] + ".view")
        emit(r, args.verbose)
        if not r.ok:
            bad += 1

    print("\n%d file(s), %d with faults" % (len(paths), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
