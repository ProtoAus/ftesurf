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

WHAT IT DELIBERATELY DOES NOT CHECK, yet.  That the recorded view angles are the
integral of the recorded mouse deltas.  That is the check this format exists for,
and it needs m_filter, m_accel* and sensitivity inverted, against a mouse column
that IN_MoveMouse consumes summed rather than per-report.  It is not worth
writing until a real capture says the input data is what we think it is; see
Item 5 of the build 22 plan.

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

# kind -> number of payload fields AFTER the dt.  'end' and 'truncated' are
# trailers rather than events and are handled separately.
KINDS = {
    "f": 2,     # abs seq
    "m": 3,     # dev dx dy
    "a": 3,     # dev x y
    "+": 2,     # dev scancode
    "-": 2,     # dev scancode
    "x": 1,     # dev            (scancode suppressed -- console/menu had focus)
    "j": 3,     # dev axis value
    "#": None,  # free text
    "!": 1,     # n
}

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
    i = 1
    while i < len(lines):
        parts = lines[i].split(None, 1)
        if not parts:
            i += 1
            continue
        if parts[0] == "begin":
            i += 1
            break
        head[parts[0]] = parts[1] if len(parts) > 1 else ""
        if parts[0] not in HEAD_V1:
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

    rawkbd = head.get("rawkbd", "?")
    r.info["rawkbd"] = rawkbd
    if rawkbd == "0":
        r.note("rawkbd 0 -- keys came from the legacy WM_KEYDOWN path, which "
               "AUTO-REPEATS. A held key produces '+' lines at the OS repeat "
               "rate with no intervening '-', so do not pair downs with ups "
               "naively in this file.")

    if head.get("synth", "0") != "0":
        r.info["synth"] = head["synth"]
        r.note("synth 1 -- this journal contains events injected by "
               "in_journal_synth. It is a test artifact and is NOT admissible "
               "as a record of anything a person did.")

    # ---- body --------------------------------------------------------------
    clock = 0.0          # running sum of dt, seconds since base
    events = 0
    frames = 0
    dropped = 0
    hidden = 0
    trailer = None
    truncated = None
    first_f = None
    last_f = None
    seqs = []
    notes_seen = []
    dts = []

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
            if len(tok) != 7:
                r.fault("line %d: 'end' has %d fields, expected 7"
                        % (lineno + 1, len(tok)))
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
        elif kind == "#":
            notes_seen.append(" ".join(tok[2:]))
        else:
            events += 1
            if kind == "x":
                hidden += 1

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
        t_abs, t_events, t_frames, t_dropped, t_hidden = trailer
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

    for n in notes_seen:
        r.note("mark: %s" % n)
    if notes_seen:
        r.info["marks"] = len(notes_seen)

    if events == 0:
        r.note("no input events at all. That is the EXPECTED result for a "
               "scripted config: a console +forward is a command-buffer entry "
               "and never passes through in_newevent, so it cannot appear here.")

    return r


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
        for k in ("version", "map", "rawinput", "rawkbd", "synth", "time", "events",
                  "frames", "dropped", "hidden", "marks", "truncated_at",
                  "frame_rate", "events_per_sec", "events_per_frame",
                  "movesequence", "view_movesequence", "view_hid", "view_span"):
            if k in r.info:
                v = r.info[k]
                if isinstance(v, float):
                    print("       %-18s %.4f" % (k, v))
                else:
                    print("       %-18s %s" % (k, v))
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
