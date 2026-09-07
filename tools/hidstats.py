#!/usr/bin/env python3
"""
hidstats.py -- what a .hid journal actually says about the input device.

hidcheck.py answers "is this file well formed".  This answers the question the
file exists for: is the mouse column one record per REPORT, or one per frame?

The distinction is the whole premise.  At in_rawinput 0 the engine reads the
mouse through GetCursorPos/SetCursorPos and gets one already-summed delta per
call, so a journal is a slightly finer .view and nothing more.  At 1 it should
see the device's own reports.  Those two look identical in a line count and are
told apart by the SHAPE of the events-per-frame distribution:

  per-frame-summed  ->  at most ONE m line per f line, always.  A frame with two
                        is structurally impossible.
  per-report        ->  events per frame varies with (poll rate / frame rate),
                        and frames with 2, 3, 4+ appear whenever the frame ran
                        long.

So the headline is not the mean.  It is `max events in one frame` and the tail
of the histogram: a single frame carrying 3 mouse records is proof the summation
is not happening, and no amount of averaging can fake it.

The intra-frame dt histogram answers the second question, and it is expected to
look BAD: Windows delivers WM_INPUT to the thread message queue and
Sys_SendKeyEvents drains a frame's worth in one PeekMessage loop, so reports that
the device spaced 1 ms apart are stamped microseconds apart.  A dt distribution
piled at ~0 is that pump artifact, not a fault, and it is the measurement that
decides whether GetMessageTime() is worth a patch.

Usage:  python tools/hidstats.py <file.hid> [...]
"""

import sys
import os


def load(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read().splitlines()


def stats(path):
    lines = load(path)
    if not lines or not lines[0].startswith("FTESURF-HID"):
        print("%s: not a .hid" % os.path.basename(path))
        return

    head = {}
    i = 1
    while i < len(lines) and lines[i].strip() != "begin":
        f = lines[i].split(None, 1)
        if f:
            head[f[0]] = f[1] if len(f) > 1 else ""
        i += 1
    i += 1

    kinds = {}
    # per-frame accumulators.  A "frame" is the span from one f line to the next.
    frame_ev = []          # total events in each frame
    frame_mouse = []       # mouse records only
    cur_ev = cur_mouse = None
    intra_dt = []          # dt of every non-f line, i.e. spacing WITHIN a drain
    frame_dt = []          # dt of every f line, i.e. the frame period
    mag = []               # |dx|+|dy| per m line
    trailer = None
    span = 0.0

    for ln in lines[i:]:
        f = ln.split()
        if not f:
            continue
        k = f[0]
        kinds[k] = kinds.get(k, 0) + 1

        if k == "end":
            trailer = f
            continue
        if k == "truncated":
            continue

        try:
            dt = int(f[1])
        except (IndexError, ValueError):
            continue

        if k == "f":
            if cur_ev is not None:
                frame_ev.append(cur_ev)
                frame_mouse.append(cur_mouse)
            cur_ev = cur_mouse = 0
            frame_dt.append(dt)
            if len(f) > 2:
                try:
                    span = float(f[2])
                except ValueError:
                    pass
            continue

        if cur_ev is None:
            continue                    # events before the first frame marker
        # The FIRST event of a drain is excluded, and that exclusion is the
        # whole validity of this histogram.  IN_Journal_Frame stamps the f line
        # at the time of that first event, so its dt is 0 BY CONSTRUCTION -- it
        # is this format's own convention, not anything the mouse did.  Counting
        # it would report ~80% "simultaneous" on any file whatever, which is a
        # property of the writer being measured by the reader and not a finding.
        cur_ev += 1
        if cur_ev > 1:
            intra_dt.append(dt)
        if k == "m":
            cur_mouse += 1
            try:
                mag.append(abs(int(f[3])) + abs(int(f[4])))
            except (IndexError, ValueError):
                pass

    if cur_ev is not None:
        frame_ev.append(cur_ev)
        frame_mouse.append(cur_mouse)

    if trailer:
        try:
            span = float(trailer[2])
        except (IndexError, ValueError):
            pass

    nf = len(frame_ev)
    ne = sum(frame_ev)
    nm = sum(frame_mouse)

    print("=" * 68)
    print(os.path.basename(path))
    print("=" * 68)
    print("  map %s   rawinput %s   rawkbd %s   synth %s"
          % (head.get("map", "?"), head.get("rawinput", "?"),
             head.get("rawkbd", "?"), head.get("synth", "?")))
    if head.get("synth") == "1":
        print("  !! synth 1 -- contains injected events, INADMISSIBLE")
    print("  %.3f s,  %d frames,  %d events  (%d mouse)" % (span, nf, ne, nm))
    if span > 0:
        print("  %.1f frames/s,  %.1f events/s,  %.1f mouse records/s"
              % (nf / span, ne / span, nm / span))
    print("  line census: %s"
          % "  ".join("%s=%d" % (k, v) for k, v in sorted(kinds.items())))

    # --- the discriminator ------------------------------------------------
    if frame_mouse:
        hi = max(frame_mouse)
        print()
        print("  MOUSE RECORDS PER FRAME  (the per-report test)")
        tot = len(frame_mouse)
        for n in range(0, min(hi, 9) + 1):
            c = frame_mouse.count(n)
            if c:
                print("    %d  %7d  %5.1f%%  %s"
                      % (n, c, 100.0 * c / tot, "#" * int(60.0 * c / tot)))
        over = sum(1 for v in frame_mouse if v > 9)
        if over:
            print("    >9 %7d  %5.1f%%" % (over, 100.0 * over / tot))
        print("    max in one frame: %d" % hi)
        print("    mean: %.3f" % (float(nm) / tot))
        if hi <= 1:
            print("    ==> AT MOST ONE per frame.  This is the OS-summed path;")
            print("        the file carries no more mouse detail than a .view.")
        else:
            print("    ==> frames carrying %d records exist, so the per-frame" % hi)
            print("        summation is NOT what produced this column.")

    # --- the pump ---------------------------------------------------------
    if intra_dt:
        intra_dt.sort()
        n = len(intra_dt)
        zero = sum(1 for v in intra_dt if v == 0)
        print()
        print("  SPACING WITHIN A FRAME  (microseconds; SECOND and later records")
        print("  of a drain only -- the first one's dt is 0 by convention)")
        print("    n=%d   zero=%d (%.1f%%)   median=%d   p90=%d   p99=%d   max=%d"
              % (n, zero, 100.0 * zero / n, intra_dt[n // 2],
                 intra_dt[int(n * 0.90)], intra_dt[int(n * 0.99)], intra_dt[-1]))
        for lo, hi2 in ((0, 0), (1, 9), (10, 99), (100, 499),
                        (500, 999), (1000, 1999), (2000, 10 ** 9)):
            c = sum(1 for v in intra_dt if lo <= v <= hi2)
            if c:
                lbl = "%d" % lo if lo == hi2 else ("%d-%d" % (lo, hi2) if hi2 < 10 ** 9 else "%d+" % lo)
                print("    %-10s %7d  %5.1f%%  %s"
                      % (lbl, c, 100.0 * c / n, "#" * int(60.0 * c / n)))
        # The test, stated rather than eyeballed: if the device really produced
        # these records at the observed rate, consecutive ones should sit about
        # (1 / rate) apart.  They sit far closer, because Sys_SendKeyEvents
        # drains a whole frame's worth of WM_INPUT in one PeekMessage loop and
        # RAWMOUSE carries no hardware timestamp -- so the stamp is when the
        # ENGINE saw the report.  Ratio is the size of that lie.
        if span > 0 and nm > 0:
            expect = 1e6 * span / nm
            med = intra_dt[n // 2]
            print("    implied report interval %.0f us;  observed median gap %d us"
                  % (expect, med))
            if med * 4 < expect:
                print("    ==> gaps are %.0fx tighter than the rate implies: these"
                      % (expect / max(1, med)))
                print("        were drained in one pump, so intra-frame SPACING is")
                print("        an artifact.  Sequence, count and magnitude are real;")
                print("        sub-frame TIMING is not.  GetMessageTime() (1 ms) is")
                print("        the upgrade that would make it real.")
            else:
                print("    ==> gaps are consistent with the report rate: sub-frame")
                print("        timing carries real information.")

    if frame_dt:
        frame_dt.sort()
        n = len(frame_dt)
        print()
        print("  FRAME PERIOD  median=%d us (%.0f fps)   p99=%d us   max=%d us"
              % (frame_dt[n // 2], 1e6 / max(1, frame_dt[n // 2]),
                 frame_dt[int(n * 0.99)], frame_dt[-1]))

    if mag:
        mag.sort()
        n = len(mag)
        print()
        print("  MOUSE DELTA |dx|+|dy|   median=%d   p90=%d   p99=%d   max=%d"
              % (mag[n // 2], mag[int(n * 0.90)], mag[int(n * 0.99)], mag[-1]))
        ones = sum(1 for v in mag if v == 1)
        print("    counts of exactly 1: %d (%.1f%%) -- a high share means the"
              % (ones, 100.0 * ones / n))
        print("    device is being read at close to its own resolution")

    if trailer and len(trailer) >= 7:
        print()
        print("  trailer: events=%s frames=%s dropped=%s hidden=%s"
              % (trailer[3], trailer[4], trailer[5], trailer[6]))
        if trailer[5] != "0":
            print("  !! %s events were LOST before reaching the journal --" % trailer[5])
            print("     the file is not admissible across those gaps")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    for p in argv[1:]:
        stats(p)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
