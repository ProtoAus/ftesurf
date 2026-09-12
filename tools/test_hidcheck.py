#!/usr/bin/env python3
"""
test_hidcheck.py -- the falsifier for hidcheck.py's yaw identity (engine Patch 293).

    python3 test_hidcheck.py

WHY THIS EXISTS.  check_identity() passing on every file we own proves nothing on
its own: a check that always says "ok" also passes every clean file.  What has to
be shown is that it FAILS on the thing it claims to catch, and that it stays quiet
on the four legitimate shapes that look similar.  So every case below is built
from the grammar in in_generic.c's Patch 293 essay, not from the writer, and
asserts a specific verdict rather than merely running.

WHAT "case_mutated_delta" DOES AND DOES NOT REPRESENT.  It is a journal in which
the angle moved further than the recorded counts allow.  That is a real failure
mode and the check catches it -- but it is NOT a model of the momentum.dll sample
ported to FTE.  A port detours IN_MoveMouse, which runs BEFORE the 'v' record is
written, so it rewrites mouse->delta[] upstream of the capture and the resulting
journal is self-consistent.  These cases prove the checker does what it says; they
do not prove the checker catches that cheat, because it does not.  See the
ENGINE_PATCHES.md entry for Patch 293.

The synthetic journals here are what a 293 engine would emit.  They carry the
`synth 0` header key and are never written to data/ -- nothing in this file
produces something that could be mistaken for a recording of a person.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hidcheck

CHECKS = 0
FAILED = []


def check(cond, what):
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILED.append(what)
        print("  FAIL  %s" % what)
    else:
        print("  ok    %s" % what)


# ---------------------------------------------------------------------------
# A journal builder that keeps the file's own self-checks satisfied, so a case
# fails for the reason it is testing and not because the clock drifted.
# ---------------------------------------------------------------------------
class Journal:
    def __init__(self, sens=0.3, myaw=0.022, scale=1.0, mfilter=0.0, maccel=0.0,
                 p293=True, nolegacy=None, nolegacylive=None,
                 rawkbds=None, devices=None, render=None, synth=0,
                 inputcvars=None):
        self.sens, self.myaw, self.scale = sens, myaw, scale
        self.lines = []
        self.clock = 0.0          # seconds since base, as the sum of emitted dt
        self.events = 0
        self.frames = 0
        self.injected = 0         # Patch 306: summed by rejected(), checked by end()
        self.unenum = 0
        self.legacybtn = 0        # Patch 307: summed by legacypress()
        head = ["FTESURF-HID 1", "map test_identity", "base 100.000000",
                "rawinput 1", "rawkbd 0"]
        # Patch 307: omitted entirely unless asked for, so the pre-307 grammar
        # stays the default and keeps being exercised.
        # Patch 303 device tables + Patch 301's bound-keyboard count, so the
        # attribution checks have something to attribute against.
        if rawkbds is not None:
            head.append("rawkbds %d" % rawkbds)
        if devices is not None:
            for dtype, did, name in devices:
                head.append('dev %s %s "%s"' % (dtype, did, name))
        # Patch 310: the render-integrity table, (name, value, default).
        if render is not None:
            for nm, val, dfl in render:
                head.append('render %s "%s" "%s"' % (nm, val, dfl))
        # Patch 312: the input-pipeline table, (name, value, default). Omitted
        # unless asked for, so the pre-312 grammar stays the default and keeps
        # being exercised -- the rule the 307 and 310 tables already follow. Its
        # PRESENCE is what tells hidcheck this file can answer the counts join;
        # without it a difference is unanswerable rather than a break.
        if inputcvars is not None:
            for nm, val, dfl in inputcvars:
                head.append('input %s "%s" "%s"' % (nm, val, dfl))
        self.devices = devices
        if nolegacy is not None:
            head.append("nolegacy %d" % nolegacy)
        if nolegacylive is not None:
            head.append("nolegacylive %d" % nolegacylive)
        head.append("synth %d" % synth)
        if p293:
            head += ["sensitivity %.9g" % sens,
                     "sensitivityscale %.9g" % scale,
                     "m_yaw %.9g" % myaw,
                     "m_pitch 0.022",
                     "m_filter %.9g" % mfilter,
                     "m_accel %.9g" % maccel,
                     "m_accel_style 1",
                     "m_accel_power 2",
                     "m_accel_offset 0",
                     "m_accel_senscap 0"]
        head.append("begin")
        self.lines.extend(head)

    @property
    def k(self):
        """degrees of yaw per count, signed as the engine applies it"""
        return -self.myaw * self.sens * self.scale

    def _adv(self, us):
        self.clock += us / 1000000.0

    def frame(self, seq, us=1200):
        self._adv(us)
        self.lines.append("f %d %.6f %d" % (us, self.clock, seq))
        self.frames += 1

    def mouse(self, dx, dy, us=0, dev=0):
        self._adv(us)
        self.lines.append("m %d %d %g %g" % (us, dev, dx, dy))
        self.events += 1

    def view(self, dx, dy, pitch, yaw, flags=0, us=30, kpitch=0.0, kyaw=0.0):
        """A CURRENT 'v' record: nine fields, the last two being Patch 305's
        keyboard turn.

        DEFAULTING TO THE CURRENT GRAMMAR IS THE FIX FOR A REAL REGRESSION.
        These fixtures wrote seven-field lines, and after Patch 305 that made
        every one of them a PRE-305 file -- on which a residual cannot be
        attributed (keyboard turn and a mutated delta look identical without
        this column), so hidcheck correctly downgrades the identity to a note.
        The suite was therefore asserting a fault on files that can no longer
        raise one, and three checks flipped to FAIL: the tool was right and the
        tests were stale. The pre-305 behaviour is still pinned, by
        case_pre305_downgrade below, which asks for it explicitly.
        """
        self._adv(us)
        self.lines.append("v %d %g %g %d %.6f %.6f %.6f %.6f"
                          % (us, dx, dy, flags, pitch, yaw, kpitch, kyaw))

    def view_pre305(self, dx, dy, pitch, yaw, flags=0, us=30):
        """The seven-field line an engine before Patch 305 wrote."""
        self._adv(us)
        self.lines.append("v %d %g %g %d %.6f %.6f" % (us, dx, dy, flags, pitch, yaw))

    def raw(self, dx, dy, us=0):
        """Patch 312's 'd' record: the counts the RING delivered for the frame
        the next 'v' describes, written only when the pipeline changed them."""
        self._adv(us)
        self.lines.append("d %d %g %g" % (us, dx, dy))

    def abspos(self, x, y, us=0, dev=0):
        """An 'a' record. A window holding one cannot be joined: the engine
        derives a delta from successive absolute positions, so those counts
        entered the view having been journalled as 'a' and never as 'm'."""
        self._adv(us)
        self.lines.append("a %d %d %g %g" % (us, dev, x, y))
        self.events += 1

    def rejected(self, injected, unenum=0, us=0):
        """Patch 306's 'i' record: reports raw input threw away."""
        self._adv(us)
        self.lines.append("i %d %d %d" % (us, injected, unenum))
        self.injected += injected
        self.unenum += unenum

    def key(self, down, scancode, prev=None, us=0, dev=0):
        """A '+'/'-' record.  Patch 309's `prev` is appended unless omitted,
        so the pre-309 grammar stays testable."""
        self._adv(us)
        kind = "+" if down else "-"
        if prev is None:
            self.lines.append("%s %d %d %d" % (kind, us, dev, scancode))
        else:
            self.lines.append("%s %d %d %d %d" % (kind, us, dev, scancode, prev))
        self.events += 1

    def legacypress(self, n, us=0):
        """Patch 307's 'b' record: a press raw input could not corroborate."""
        self._adv(us)
        self.lines.append("b %d %d" % (us, n))
        self.legacybtn += n

    def note(self, text, us=0):
        """A '#' annotation record."""
        self._adv(us)
        self.lines.append("# %d %s" % (us, text))

    def cvarchange(self, name, value, us=0):
        """Patch 310's 'c' record: a render cvar was changed mid-journal."""
        self._adv(us)
        self.lines.append('c %d %s "%s"' % (us, name, value))

    def legacystate(self, state, us=0):
        """Patch 307's 'g' record: the effective suppression state changed."""
        self._adv(us)
        self.lines.append("g %d %d" % (us, state))

    def end(self, us=100, injected=None, unenum=None, legacybtn=None,
            pre306=False, pre307=False):
        # the closing devmap table, which is where the attribution check reads
        # its claims from.
        if getattr(self, "devices", None):
            for dtype, did, name in self.devices:
                self.lines.append('devmap %s %s "%s"' % (dtype, did, name))
        self._adv(us)
        if pre306:
            self.lines.append("end %d %.6f %d %d 0 0"
                              % (us, self.clock, self.events, self.frames))
        else:
            if injected is None:
                injected = self.injected
            if unenum is None:
                unenum = self.unenum
            if pre307:
                self.lines.append("end %d %.6f %d %d 0 0 %d %d"
                                  % (us, self.clock, self.events, self.frames,
                                     injected, unenum))
            else:
                if legacybtn is None:
                    legacybtn = self.legacybtn
                self.lines.append("end %d %.6f %d %d 0 0 %d %d %d"
                                  % (us, self.clock, self.events, self.frames,
                                     injected, unenum, legacybtn))
        return "\n".join(self.lines) + "\n"


def run(text):
    fd, path = tempfile.mkstemp(suffix=".hid")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        return hidcheck.check_hid(path)
    finally:
        os.unlink(path)


def has_fault(r, needle):
    return any(needle in f for f in r.faults)


def has_note(r, needle):
    return any(needle in n for n in r.notes)


# ---------------------------------------------------------------------------
def case_clean():
    """A clean client: every frame's yaw is exactly k*dx."""
    j = Journal()
    yaw = 0.0
    for i in range(50):
        dx = (i % 7) - 3
        j.frame(3000 + i)
        if dx:
            j.mouse(dx, 0)
        yaw += j.k * dx
        j.view(dx, 0, 10.0, yaw)
    r = run(j.end())
    check(r.ok, "clean run: no faults (%s)" % (r.faults[:1] or "none"))
    check(r.info.get("identity", "").startswith("exact"),
          "clean run: identity reported exact")
    check(abs(r.info.get("deg_per_count", 0) - 0.0066) < 1e-9,
          "clean run: deg_per_count is sensitivity*m_yaw = 0.0066")


def case_mutated_delta():
    """momentum.dll's shape: the angle is nudged past what the counts justify.

    The cheat blends the human delta toward the optimal strafe angle and then
    re-quantises onto the sensitivity lattice, so the ANGLE moves further than
    the recorded counts allow while still looking like a plausible mouse value.
    """
    j = Journal()
    yaw = 0.0
    for i in range(50):
        dx = 5
        j.frame(3000 + i)
        j.mouse(dx, 0)
        applied = dx if i < 40 else dx * 1.4    # the assist engages late in the run
        yaw += j.k * applied
        j.view(dx, 0, 10.0, yaw)
    r = run(j.end())
    check(has_fault(r, "YAW IDENTITY BROKEN"),
          "mutated delta: identity fault raised")
    check(r.info.get("identity_violations", 0) == 10,
          "mutated delta: exactly the 10 assisted frames flagged (got %s)"
          % r.info.get("identity_violations"))


def case_subtle_mutation():
    """The same attack at low opti_power -- one lattice step, every frame.

    This is the case that matters: a strength so low it would vanish into any
    statistical test still has to move the angle off the lattice to do anything
    at all, and the identity is arithmetic rather than statistical.
    """
    j = Journal()
    yaw = 0.0
    for i in range(50):
        dx = 12
        j.frame(3000 + i)
        j.mouse(dx, 0)
        yaw += j.k * (dx + 1)          # ONE extra count's worth of turn
        j.view(dx, 0, 10.0, yaw)
    r = run(j.end())
    check(has_fault(r, "YAW IDENTITY BROKEN"),
          "one-count mutation: still caught (this is the whole point)")


def case_strafe_not_governed():
    """+strafe sends the counts to sidemove, so yaw must NOT be expected to move."""
    j = Journal()
    for i in range(20):
        j.frame(3000 + i)
        j.mouse(9, 0)
        j.view(9, 0, 10.0, 45.0, flags=hidcheck.VF_STRAFE_X)
    r = run(j.end())
    check(r.ok, "+strafe frames: no fault (%s)" % (r.faults[:1] or "none"))
    check(r.info.get("frames_not_governed") == 20,
          "+strafe frames: all 20 reported as not governed")


def case_ghost_turn():
    """Yaw moving with zero counts: a note, never a fault.

    It is what a console +left, a cl_yawspeed script or a server angle set looks
    like -- legitimate in itself -- but it is also what an injected turn looks
    like, so it must be surfaced without being called cheating.
    """
    j = Journal()
    yaw = 0.0
    for i in range(20):
        j.frame(3000 + i)
        yaw += 0.5
        j.view(0, 0, 10.0, yaw)
    r = run(j.end())
    check(r.ok, "ghost turn: not a fault (%s)" % (r.faults[:1] or "none"))
    check(has_note(r, "ZERO mouse counts"), "ghost turn: reported as a note")


def case_wrap():
    """Yaw crossing 180/-180 is a wrap, not a 360-degree violation."""
    j = Journal()
    yaw = 179.9
    for i in range(10):
        dx = 20
        j.frame(3000 + i)
        j.mouse(dx, 0)
        yaw += j.k * dx
        if yaw <= -180.0:
            yaw += 360.0
        j.view(dx, 0, 10.0, yaw)
    r = run(j.end())
    check(r.ok, "angle wrap: not mistaken for a violation (%s)" % (r.faults[:1] or "none"))


def case_filter_skips():
    """m_filter is a shape this tool does not model, so it must SKIP, not fault."""
    j = Journal(mfilter=1.0)
    yaw = 0.0
    for i in range(20):
        j.frame(3000 + i)
        j.mouse(5, 0)
        yaw += j.k * 5 * 0.5          # deliberately not the plain identity
        j.view(5, 0, 10.0, yaw)
    r = run(j.end())
    check(r.ok, "m_filter 1: skipped rather than failed (%s)" % (r.faults[:1] or "none"))
    check(has_note(r, "identity is NOT "),
          "m_filter 1: says the identity was not checked")
    check("identity" not in r.info,
          "m_filter 1: does NOT claim an exact result it did not compute")


def case_pre293():
    """A pre-293 journal must still pass, and must say why it proves nothing."""
    j = Journal(p293=False)
    for i in range(20):
        j.frame(3000 + i)
        j.mouse(4, 1)
    r = run(j.end())
    check(r.ok, "pre-293 file: still passes (%s)" % (r.faults[:1] or "none"))
    check(has_note(r, "NOT CHECKABLE"),
          "pre-293 file: says the identity is not checkable")


def case_stripped_header():
    """'v' records with the scale terms removed is an EDITED file, not an old one."""
    j = Journal()
    yaw = 0.0
    for i in range(10):
        j.frame(3000 + i)
        j.mouse(3, 0)
        yaw += j.k * 3
        j.view(3, 0, 10.0, yaw)
    text = j.end()
    text = "\n".join(l for l in text.split("\n")
                     if not l.startswith(("sensitivity", "m_yaw")))
    r = run(text)
    check(has_fault(r, "has been edited"),
          "stripped header: 'v' without scale terms is a fault")


def case_pre305_downgrade():
    """A pre-305 file CANNOT fault on the identity, and that is deliberate.

    Without the keyboard column a residual has two readings -- a mutated mouse
    delta, or +left/+right, which are shipped default binds this game's
    prestrafe is calibrated around. Faulting would accuse a player of the
    game's own core mechanic. So the same mutation that faults on a current
    file must come back as an unresolved NOTE on an old one.

    This pins behaviour that would otherwise only exist by accident, and it is
    the counterpart to the fixture now defaulting to the 305 grammar.
    """
    j = Journal()
    yaw = 0.0
    for i in range(50):
        dx = 12
        j.frame(3000 + i)
        j.mouse(dx, 0)
        yaw += j.k * (dx + 1)
        j.view_pre305(dx, 0, 10.0, yaw)
    r = run(j.end(pre306=True))
    check(not has_fault(r, "YAW IDENTITY BROKEN"),
          "pre-305 file: the same mutation does NOT fault")
    check(has_note(r, "identity unresolved"),
          "pre-305 file: reported as unresolved rather than clean")
    check(r.info.get("identity_violations") == 49,
          "pre-305 file: the residual is still COUNTED (got %s)"
          % r.info.get("identity_violations"))


def case_rejected_reports():
    """Patch 306: synthesized reports raw input threw away are counted."""
    j = Journal()
    yaw = 0.0
    for i in range(20):
        j.frame(3000 + i)
        j.mouse(4, 0)
        yaw += j.k * 4
        j.view(4, 0, 10.0, yaw)
        if i % 4 == 0:
            j.rejected(10)
    r = run(j.end())
    check(r.ok, "rejected reports: not a fault (%s)" % (r.faults[:1] or "none"))
    check(r.info.get("injected") == 50,
          "rejected reports: 50 counted (got %s)" % r.info.get("injected"))
    check(has_note(r, "REJECTED by raw input"),
          "rejected reports: surfaced as a note")
    check(not has_fault(r, "injected"),
          "rejected reports: NEVER auto-accuses -- injection is not a fault")


def case_rejected_trailer_mismatch():
    """The 'i' records and the trailer state one quantity twice; they must agree."""
    j = Journal()
    for i in range(5):
        j.frame(3000 + i)
        j.mouse(1, 0)
        j.view(1, 0, 10.0, j.k * (i + 1))
    j.rejected(10)
    r = run(j.end(injected=99))       # the trailer disagrees with the body
    check(has_fault(r, "injected reports"),
          "trailer mismatch: an inconsistent edit is a fault")


def case_pre306_journal():
    """Absent is not zero: an old file cannot be described as injection-free."""
    j = Journal()
    for i in range(5):
        j.frame(3000 + i)
        j.mouse(1, 0)
        j.view(1, 0, 10.0, j.k * (i + 1))
    r = run(j.end(pre306=True))
    check(r.ok, "pre-306 file: still passes (%s)" % (r.faults[:1] or "none"))
    check(has_note(r, "predates engine Patch 306"),
          "pre-306 file: says the question cannot be asked")
    check("injected" not in r.info,
          "pre-306 file: does NOT report an injected count it never measured")


def case_rejected_backend_silent():
    """-1 means the backend does not count -- also not a measurement of zero."""
    j = Journal()
    for i in range(5):
        j.frame(3000 + i)
        j.mouse(1, 0)
        j.view(1, 0, 10.0, j.k * (i + 1))
    r = run(j.end(injected=-1, unenum=-1))
    check(r.ok, "backend silent: not a fault (%s)" % (r.faults[:1] or "none"))
    check(has_note(r, "does not count rejected reports"),
          "backend silent: says so explicitly")
    check("injected" not in r.info,
          "backend silent: reports no count")


def _clickrun(**kw):
    """A short journal with a couple of real frames, for the 307 cases."""
    j = Journal(**kw)
    for i in range(5):
        j.frame(3000 + i)
        j.mouse(1, 0)
        j.view(1, 0, 10.0, j.k * (i + 1))
    return j


def case_legacy_press_counted():
    """Patch 307: an uncorroborated press is COUNTED and reported, never faulted.

    It cannot be faulted, because a Windows precision touchpad produces no raw
    button reports at all -- every honest click on such a machine lands here.
    """
    j = _clickrun(nolegacy=0, nolegacylive=0)
    j.legacypress(20)
    r = run(j.end())
    check(r.ok, "legacy press: not a fault (%s)" % (r.faults[:1] or "none"))
    check(r.info.get("legacy_presses") == 20,
          "legacy press: 20 counted (got %s)" % r.info.get("legacy_presses"))
    check(has_note(r, "could not corroborate"),
          "legacy press: surfaced as a note")
    check(str(r.info.get("legacy_path", "")).startswith("open"),
          "legacy press: the path is reported OPEN (got %r)"
          % r.info.get("legacy_path"))


def case_legacy_trailer_mismatch():
    """The 'b' records and the trailer state one quantity twice."""
    j = _clickrun(nolegacy=0, nolegacylive=0)
    j.legacypress(5)
    r = run(j.end(legacybtn=77))
    check(has_fault(r, "uncorroborated legacy presses"),
          "legacy mismatch: an inconsistent edit is a fault")


def case_legacy_suppressed_throughout():
    """Only a run with no gap may be described as protected."""
    j = _clickrun(nolegacy=1, nolegacylive=1)
    r = run(j.end())
    check(r.ok, "suppressed: not a fault (%s)" % (r.faults[:1] or "none"))
    check(r.info.get("legacy_path") == "suppressed for the whole journal",
          "suppressed: reported as protected throughout (got %r)"
          % r.info.get("legacy_path"))


def case_legacy_reopened_midrun():
    """THE CASE A HEADER ALONE CANNOT ANSWER, and it is not hypothetical.

    in_rawinput_nolegacy is grab-scoped, so every alt-tab reopens the legacy
    path. This patch's own first falsifier run flipped it four times in three
    seconds, and the header -- a snapshot at begin -- said 0 for an arm in which
    the block demonstrably worked. A run with a gap must NOT read as protected.
    """
    j = _clickrun(nolegacy=1, nolegacylive=1)
    j.legacystate(0)
    j.frame(4000)
    j.mouse(1, 0)
    j.view(1, 0, 10.0, j.k * 6)   # stay ON the lattice: this case is about 'g'
    j.legacystate(1)
    r = run(j.end())
    check(r.ok, "reopened: not a fault (%s)" % (r.faults[:1] or "none"))
    check(r.info.get("nolegacy_changes") == 2,
          "reopened: both transitions recorded (got %s)"
          % r.info.get("nolegacy_changes"))
    check(has_note(r, "open for part of this"),
          "reopened: says the path was open for part of the run")
    check("legacy_path" not in r.info,
          "reopened: does NOT describe the run as protected")


def case_pre307_journal():
    """Absent is not zero, again: an old file cannot be called protected."""
    j = _clickrun()
    r = run(j.end(pre307=True))
    check(r.ok, "pre-307 file: still passes (%s)" % (r.faults[:1] or "none"))
    check("legacy_presses" not in r.info,
          "pre-307 file: reports no legacy-press count")
    check("legacy_path" not in r.info,
          "pre-307 file: makes no claim about the legacy path")


def case_autorepeat_separated():
    """Patch 309: a held key's repeat train is no longer counted as presses.

    The numbers here are the shape of the real finding: one press and nine
    repeats read as TEN presses before this column existed.
    """
    j = Journal()
    j.frame(3000)
    j.key(True, 101, prev=0)              # the real press
    for _ in range(9):
        j.key(True, 101, prev=1)          # OS auto-repeat
    j.key(False, 101, prev=1)
    j.view(0, 0, 10.0, 0.0)
    r = run(j.end())
    check(r.ok, "autorepeat: not a fault (%s)" % (r.faults[:1] or "none"))
    check(r.info.get("key_presses") == 1,
          "autorepeat: exactly ONE real press (got %s)" % r.info.get("key_presses"))
    check(r.info.get("key_repeats") == 9,
          "autorepeat: nine repeats (got %s)" % r.info.get("key_repeats"))
    check(abs(r.info.get("key_repeat_pct", 0) - 90.0) < 1e-9,
          "autorepeat: 90%% of the down records were phantom (got %s)"
          % r.info.get("key_repeat_pct"))


def case_orphan_release():
    """A '-' whose key was not down is a release with no press."""
    j = Journal()
    j.frame(3000)
    j.key(False, 101, prev=0)
    j.view(0, 0, 10.0, 0.0)
    r = run(j.end())
    check(r.ok, "orphan: not a fault (%s)" % (r.faults[:1] or "none"))
    check(r.info.get("orphan_releases") == 1,
          "orphan: counted (got %s)" % r.info.get("orphan_releases"))
    check(has_note(r, "not down"), "orphan: surfaced as a note")


def case_release_everything_not_orphan():
    """scancode -1 is the release-everything sweep, not a key anyone pressed.

    prev is -1 there -- NOT 0 -- so it must not be counted as an orphan
    release. This is the same three-state rule the rest of the format follows.
    """
    j = Journal()
    j.frame(3000)
    j.key(False, -1, prev=-1)
    j.view(0, 0, 10.0, 0.0)
    r = run(j.end())
    check(r.ok, "release-all: not a fault (%s)" % (r.faults[:1] or "none"))
    check("orphan_releases" not in r.info,
          "release-all: NOT counted as an orphan release")
    check(r.info.get("key_presses") is None or r.info.get("key_presses") == 0,
          "release-all: not counted as a press")


def case_pre309_journal():
    """An old file's '+' records cannot be counted as presses at all."""
    j = Journal()
    j.frame(3000)
    j.key(True, 101)                      # no prev column
    j.key(False, 101)
    j.view(0, 0, 10.0, 0.0)
    r = run(j.end())
    check(r.ok, "pre-309 file: still passes (%s)" % (r.faults[:1] or "none"))
    check("key_presses" not in r.info,
          "pre-309 file: reports no press count it cannot compute")
    check(has_note(r, "MIXTURE of real presses"),
          "pre-309 file: says the records cannot be counted as presses")


MOUSE0 = ("mouse", "0", "\\?\HID#VID_DEAD&PID_BEEF")


def case_key_devid_is_not_the_mouse():
    """THE PATCH 303 FALSE POSITIVE.

    On the legacy keyboard path -- in_rawinput_keyboard 0, the shipped default
    -- every key event is dispatched with a HARDCODED devid 0, while the
    enumerated system keyboard is written '-' (cannot carry a devid). So devid
    0 is used by every keystroke and claimed by no keyboard.

    Two failures came out of that. The loud one: the attribution check reported
    the player's own keyboard as hardware the file could not account for. The
    silent and worse one: when a mouse HAS devid 0 -- the common case, it is the
    first handed out -- the table positively asserts devid 0 IS that mouse, so
    every keystroke read as having come from it, and nothing said otherwise.
    """
    j = Journal(rawkbds=0, devices=[MOUSE0])
    j.frame(3000)
    j.key(True, 101, prev=0, dev=0)
    j.key(False, 101, prev=1, dev=0)
    j.mouse(2, 0)
    j.view(2, 0, 10.0, j.k * 2)
    r = run(j.end())
    check(r.ok, "key devid: not a fault (%s)" % (r.faults[:1] or "none"))
    check(not has_note(r, "no device in the table claims it"),
          "key devid: the false positive is GONE")
    check("key_attribution" in r.info,
          "key devid: says attribution is unavailable rather than guessing")
    check("NOT the mouse" in str(r.info.get("key_attribution", "")),
          "key devid: says explicitly it is not the mouse holding devid 0")


def case_pointer_devid_still_unclaimed():
    """THE REGRESSION GUARD, and it is the point of this pair.

    The fix NARROWS the attribution check to pointer devices. A narrowing can
    silently become a deletion, and the failure would look exactly like a clean
    file -- so an unclaimed POINTER devid must still be reported.
    """
    j = Journal(rawkbds=0, devices=[MOUSE0])
    j.frame(3000)
    j.mouse(2, 0, dev=7)                  # no device in the table claims 7
    j.view(2, 0, 10.0, j.k * 2)
    r = run(j.end())
    check(has_note(r, "no device in the table claims it"),
          "pointer devid: an unclaimed POINTER devid is still reported")
    check("7 produced" in " ".join(r.notes),
          "pointer devid: names the right devid (7)")


def case_key_devid_unclaimed_when_raw_is_live():
    """With raw keyboard bound, a key devid IS an identity and must be claimed."""
    j = Journal(rawkbds=1, devices=[MOUSE0])
    j.frame(3000)
    j.key(True, 101, prev=0, dev=3)
    j.view(0, 0, 10.0, 0.0)
    r = run(j.end())
    check(has_note(r, "should have been a real keyboard"),
          "raw keyboard: an unclaimed key devid IS reported when raw is live")


DEFAULTS = [("r_fog_progless", "1", "1"), ("r_fullbright", "0", "0")]


def _renderrun(render, changes=()):
    j = Journal(render=render)
    j.frame(3000)
    j.mouse(1, 0)
    j.view(1, 0, 10.0, j.k)
    for nm, val in changes:
        j.cvarchange(nm, val)
    return run(j.end())


def case_render_all_default():
    r = _renderrun(DEFAULTS)
    check(r.ok, "render default: not a fault (%s)" % (r.faults[:1] or "none"))
    check("0 not at default" in str(r.info.get("render_cvars", "")),
          "render default: reports nothing off-default (got %r)"
          % r.info.get("render_cvars"))
    check(not has_note(r, "not its default"),
          "render default: says nothing about settings that are normal")


def case_render_nondefault():
    """r_fog_progless 0 is CVAR_ARCHIVE and not CVAR_CHEAT -- nothing gates it."""
    r = _renderrun([("r_fog_progless", "0", "1"), ("r_fullbright", "0", "0")])
    check(r.ok, "render off-default: NOT a fault -- this tool records, it does "
                "not decide the rules (%s)" % (r.faults[:1] or "none"))
    check(has_note(r, "not its default"),
          "render off-default: surfaced as a note")
    check("render[r_fog_progless]" in r.info,
          "render off-default: named in the report")


def case_render_set_and_set_back():
    """THE CASE THE DESIGN EXISTS FOR.

    The header says 1 and the final value is 1, so a reader comparing start
    against end concludes nothing happened. The engine tracks modifiedcount
    rather than the value precisely so that "it was briefly something else"
    survives into the record.
    """
    r = _renderrun(DEFAULTS, changes=[("r_fog_progless", "0"),
                                      ("r_fog_progless", "1")])
    check(r.info.get("render_changes") == 2,
          "set-and-back: both changes recorded (got %s)"
          % r.info.get("render_changes"))
    check(has_note(r, "was changed DURING"),
          "set-and-back: reported even though start == end")
    check("0 not at default" in str(r.info.get("render_cvars", "")),
          "set-and-back: the OPENING table is still reported as normal, which "
          "is exactly why the change records are needed")


def case_render_cvar_absent_in_build():
    """`-` means no such cvar in that build. It is not a value, least of all 0."""
    r = _renderrun([("r_fog_progless", "1", "1"), ("r_madeup", "-", "-")])
    check(r.ok, "absent cvar: not a fault (%s)" % (r.faults[:1] or "none"))
    check(has_note(r, "do not exist in the build"),
          "absent cvar: reported as unreadable rather than as 0")
    check(not has_note(r, "r_madeup is -"),
          "absent cvar: NOT reported as differing from its default")


def case_pre310_journal():
    r = _renderrun(None)
    check(r.ok, "pre-310 file: still passes (%s)" % (r.faults[:1] or "none"))
    check("render_cvars" not in r.info,
          "pre-310 file: claims no render table it does not have")
    check(has_note(r, "predates engine Patch 310"),
          "pre-310 file: says the question cannot be asked")


def case_synth_names_its_source():
    """Patch 311: the poison says WHO injected, not just that someone did.

    `synth 1` alone is the same flag for "a developer ran in_journal_synth to
    test the format" and "a plugin forged input", which are very different
    facts about a run.
    """
    j = Journal(synth=1)
    j.frame(3000)
    j.note("SYNTH source plugin")
    j.mouse(3, 0)
    j.view(3, 0, 10.0, j.k * 3)
    r = run(j.end())
    check(r.info.get("synth_source") == "plugin",
          "synth source: reported (got %s)" % r.info.get("synth_source"))
    check(has_note(r, "source: plugin"), "synth source: named in the note")
    check(has_note(r, "NOT admissible"),
          "synth source: still says the file is inadmissible")


def case_synth_unsourced_names_nobody():
    """A PRE-311 FILE MUST NOT HAVE A SOURCE INVENTED FOR IT.

    This tool used to say every synth-flagged journal came from
    in_journal_synth, because before Patch 311 that was the only thing that
    could set the flag. Patch 311 makes a PLUGIN able to set it too -- so the
    old sentence became a false attribution on exactly the files that matter,
    and it would have named the innocent source. A message that was true when
    written turns into a wrong answer when the world widens; the same shape as
    "absent is not zero".
    """
    j = Journal(synth=1)
    j.frame(3000)
    j.mouse(3, 0)
    j.view(3, 0, 10.0, j.k * 3)
    r = run(j.end())
    check("synth_source" not in r.info,
          "unsourced synth: claims no source it does not have")
    check(has_note(r, "SOURCE is not recorded"),
          "unsourced synth: says the source is unknown")
    check(not has_note(r, "source: in_journal_synth"),
          "unsourced synth: does NOT name the innocent source")


def case_no_synth_no_noise():
    j = Journal()
    j.frame(3000)
    j.mouse(1, 0)
    j.view(1, 0, 10.0, j.k)
    r = run(j.end())
    check("synth" not in r.info, "clean file: no synth key")
    check(not has_note(r, "NOT admissible"),
          "clean file: says nothing about injection")


# ---------------------------------------------------------------------------
# Patch 312 -- the counts join (plan item P294b)
# ---------------------------------------------------------------------------
# The header table a post-312 engine writes. Only in_xflip matters to these
# cases; the rest are carried so the fixture looks like a real file.
P312_INPUT = [("in_xflip", "0", "0"), ("sensitivity", "0.3", "0.3"),
              ("m_yaw", "0.022", "0.022"), ("leftisright", "0", "0")]


def case_join_holds():
    """The honest case: every view delta equals the reports behind it."""
    j = Journal(inputcvars=P312_INPUT)
    yaw = 0.0
    for i in range(30):
        dx = (i % 5) + 1
        j.frame(4000 + i)
        j.mouse(dx, 0)
        yaw += j.k * dx
        j.view(dx, 0, 10.0, yaw)
    r = run(j.end())
    check(r.ok, "join holds: no faults (%s)" % (r.faults[:1] or "none"))
    check(r.info.get("join_checked") == 29,
          "join holds: 29 windows checked, first exempt (got %s)"
          % r.info.get("join_checked"))
    check(r.info.get("join_broke") == 0, "join holds: nothing broken")


def case_join_catches_what_the_identity_cannot():
    """THE WHOLE REASON PATCH 312 EXISTS.

    A hook that rewrites the accumulated delta runs UPSTREAM of mx, so the
    engine then does its own arithmetic on the doctored value and BOTH sides of
    the Patch 293 identity move together -- it closes perfectly. The 'm' records
    were written earlier, straight off the ring, and did not move. So 293 must
    report exact and the join must fail, on the same file.
    """
    j = Journal(inputcvars=P312_INPUT)
    yaw = 0.0
    for i in range(30):
        dx = 12
        j.frame(4000 + i)
        j.mouse(dx, 0)                  # what the ring delivered
        applied = dx + 1                # what the hook handed to the pipeline
        yaw += j.k * applied            # the engine's own honest multiplication
        j.view(applied, 0, 10.0, yaw)
    r = run(j.end())
    check(r.info.get("identity_violations") == 0,
          "faithful hook: the Patch 293 identity sees NOTHING (violations=%s)"
          % r.info.get("identity_violations"))
    check(has_fault(r, "COUNTS JOIN BROKEN"),
          "faithful hook: the counts join catches it")
    check(r.info.get("join_broke") == 29,
          "faithful hook: all 29 joinable windows flagged (got %s)"
          % r.info.get("join_broke"))


def case_join_declared_transform_is_not_a_break():
    """in_xflip 1: the sign is inverted, the engine SAYS so, and it is fine.

    Before Patch 312 this player produced sum(m).dx == -v.dx on every frame with
    nothing in the file to explain it -- a 100% failure of the flagship check
    against someone who set a cvar that is not even archived. That is the Patch
    305 failure mode, and this case is here so it cannot come back.
    """
    j = Journal(inputcvars=[("in_xflip", "1", "0")])
    yaw = 0.0
    for i in range(20):
        dx = 7
        j.frame(4000 + i)
        j.mouse(dx, 0)              # the ring delivered +7 ...
        j.raw(dx, 0)                # ... the engine states it got +7 ...
        yaw += j.k * (-dx)          # ... and applied -7, because in_xflip
        j.view(-dx, 0, 10.0, yaw)
    r = run(j.end())
    check(r.ok, "declared transform: no fault (%s)" % (r.faults[:1] or "none"))
    check(r.info.get("join_transforms") == 19,
          "declared transform: 19 'd' records seen (got %s)"
          % r.info.get("join_transforms"))
    check(has_note(r, "in_xflip is 1, not its default 0"),
          "declared transform: in_xflip reported as off-default")


def case_join_pre312_is_unanswerable_not_broken():
    """ABSENT IS NOT ZERO. The same divergence, in a file with no 'input' table.

    A pre-312 engine wrote no 'd' records, so an honest in_xflip player and a
    sign-flipping hook produce byte-identical files. Naming that a fault would
    accuse every recording made before the patch existed.
    """
    j = Journal()                       # no inputcvars -> pre-312 grammar
    yaw = 0.0
    for i in range(20):
        dx = 7
        j.frame(4000 + i)
        j.mouse(dx, 0)
        yaw += j.k * (-dx)
        j.view(-dx, 0, 10.0, yaw)
    r = run(j.end())
    check(not has_fault(r, "COUNTS JOIN BROKEN"),
          "pre-312: divergence does NOT raise a fault")
    check(has_note(r, "PREDATES engine Patch 312"),
          "pre-312: reported as unanswerable")
    check(has_note(r, "no input-pipeline table"),
          "pre-312: the missing table is named")


def case_join_absolute_window_not_joinable():
    """An 'a' in the window: counts can enter the view having never been an 'm'."""
    j = Journal(inputcvars=P312_INPUT)
    yaw = 0.0
    for i in range(20):
        dx = 4
        j.frame(4000 + i)
        j.mouse(dx, 0)
        if i % 2:
            j.abspos(500 + i, 300)      # the pointer is being driven absolutely
        yaw += j.k * dx
        j.view(dx, 0, 10.0, yaw)
    r = run(j.end())
    check(r.ok, "absolute window: no fault (%s)" % (r.faults[:1] or "none"))
    check(has_note(r, "could not be joined"),
          "absolute window: reported as unjoinable rather than broken")


def case_join_first_window_exempt():
    """Counts that arrived before `begin` are not a finding.

    The engine deliberately does not clear the pending delta at in_journal_begin
    to make this go away -- that would discard counts the player already made,
    and the engine must not alter a player's aim to tidy its own evidence.
    """
    j = Journal(inputcvars=P312_INPUT)
    j.frame(4000)
    j.mouse(5, 0)
    j.mouse(6, 0)
    j.view(99, 0, 10.0, 0.0)            # short by an unknowable amount
    yaw = 0.0
    for i in range(10):
        j.frame(4001 + i)
        j.mouse(3, 0)
        yaw += j.k * 3
        j.view(3, 0, 10.0, yaw)
    r = run(j.end())
    check(not has_fault(r, "COUNTS JOIN BROKEN"),
          "first window: the opening frame is exempt, not a break")
    check(r.info.get("join_broke") == 0,
          "first window: nothing else flagged (got %s)" % r.info.get("join_broke"))


def main():
    print("test_hidcheck.py -- the Patch 293 yaw identity\n")
    for fn in (case_clean, case_mutated_delta, case_subtle_mutation,
               case_strafe_not_governed, case_ghost_turn, case_wrap,
               case_filter_skips, case_pre293, case_stripped_header,
               case_pre305_downgrade, case_rejected_reports,
               case_rejected_trailer_mismatch, case_pre306_journal,
               case_rejected_backend_silent, case_legacy_press_counted,
               case_legacy_trailer_mismatch, case_legacy_suppressed_throughout,
               case_legacy_reopened_midrun, case_pre307_journal,
               case_autorepeat_separated, case_orphan_release,
               case_release_everything_not_orphan, case_pre309_journal,
               case_key_devid_is_not_the_mouse, case_pointer_devid_still_unclaimed,
               case_key_devid_unclaimed_when_raw_is_live,
               case_render_all_default, case_render_nondefault,
               case_render_set_and_set_back, case_render_cvar_absent_in_build,
               case_pre310_journal, case_synth_names_its_source,
               case_synth_unsourced_names_nobody, case_no_synth_no_noise,
               case_join_holds, case_join_catches_what_the_identity_cannot,
               case_join_declared_transform_is_not_a_break,
               case_join_pre312_is_unanswerable_not_broken,
               case_join_absolute_window_not_joinable,
               case_join_first_window_exempt):
        print("%s:" % fn.__name__)
        fn()
        print("")
    print("%d checks, %d failed" % (CHECKS, len(FAILED)))
    for f in FAILED:
        print("  FAILED: %s" % f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
