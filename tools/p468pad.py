#!/usr/bin/env python3
"""
p468pad.py -- grade cfg/test/p468pad.cfg: a Windows precision touchpad's motion
is accepted on its digitizer's say-so and journalled as the touchpad's.

    python tools/p468pad.py [--data ftesurf/data]

Reads data/p468_A.hid, p468_B.hid and p468_C.hid and holds each to the
predictions pre-registered in the cfg's header.  Exit status 0 when every one
held.  The arm needs the owner's hand on the pad, so this only grades.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import hidcheck  # noqa: E402

FAILED = []
# hidcheck faults a journal that drained nothing ("no frame markers"); on the
# arms whose whole point is that nothing reaches the game, that fault is the
# expected result and the only one allowed.
NO_EVENTS = "no frame markers"


def check(cond, what):
    print("  %s  %s" % ("ok  " if cond else "FAIL", what))
    if not cond:
        FAILED.append(what)


def parse(path):
    """-> (header, [dev types], {devmap type: id}, {devid: m}, {devid: +/-}, p sums, trailer)."""
    head, devs, devmaps, m_by_dev, b_by_dev, trailer = {}, [], {}, {}, {}, None
    psum = [0, 0]
    inbody = False
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            t = line.split()
            if not t:
                continue
            if not inbody:
                if t[0] == "begin":
                    inbody = True
                elif t[0] == "dev" and len(t) >= 3:
                    devs.append(t[1])
                elif len(t) >= 2:
                    head[t[0]] = t[1]
                continue
            if t[0] == "m" and len(t) >= 5:          # m <dt> <dev> <dx> <dy>
                m_by_dev[t[2]] = m_by_dev.get(t[2], 0) + 1
            elif t[0] in ("+", "-") and len(t) >= 4:  # +/- <dt> <dev> <key> [prev]
                b_by_dev[t[2]] = b_by_dev.get(t[2], 0) + 1
            elif t[0] == "p" and len(t) >= 4:        # p <dt> <accepted> <digitizer>
                psum[0] += int(t[2])
                psum[1] += int(t[3])
            elif t[0] == "devmap" and len(t) >= 3:
                devmaps[t[1]] = t[2]
            elif t[0] == "end":
                trailer = t[1:]
    return head, devs, devmaps, m_by_dev, b_by_dev, psum, trailer


def arm(data, letter, events_expected):
    path = os.path.join(data, "p468_%s.hid" % letter)
    print("ARM %s  %s" % (letter, path))
    if not os.path.exists(path):
        check(False, "journal exists")
        return None
    head, devs, devmaps, m_by_dev, b_by_dev, psum, trailer = parse(path)
    # end <dt> <abs> <events> <frames> <dropped> <hidden> <inj> <unenum> <lgb> <pad> <dig>
    if trailer is None or len(trailer) < 11:
        check(False, "trailer has the two Patch 468 fields (got %r)" % (trailer,))
        return None
    injected, unenum = int(trailer[6]), int(trailer[7])
    accepted, digitizer = int(trailer[9]), int(trailer[10])
    paddev = devmaps.get("touchpad", "-")
    resolved = paddev not in ("-", "unset")
    m_pad = m_by_dev.get(paddev, 0) if resolved else 0
    b_pad = b_by_dev.get(paddev, 0) if resolved else 0
    m_other = sum(n for d, n in m_by_dev.items() if d != paddev)
    print("      rawpads %s  dev-table touchpad %s  devmap touchpad %s  m[pad] %d  buttons[pad] %d  m[other] %d"
          % (head.get("rawpads", "?"), "yes" if "touchpad" in devs else "NO", paddev, m_pad, b_pad, m_other))
    print("      trailer: injected %d  unenum %d  accepted %d  digitizer %d   'p' records sum: %d %d"
          % (injected, unenum, accepted, digitizer, psum[0], psum[1]))
    r = hidcheck.check_hid(path)
    for n in r.notes:
        if "touchpad" in n or "REJECTED" in n:
            print("      hidcheck: %s" % n[:160])
    if events_expected:
        check(not r.faults, "hidcheck finds no fault (%s)" % (r.faults[:1] or "none"))
    else:
        other = [f for f in r.faults if NO_EVENTS not in f]
        check(not other, "hidcheck finds no fault beyond the expected %r (%s)"
              % (NO_EVENTS, other[:1] or "none"))
    check(head.get("rawpads") == "1", "header rawpads 1 (bound)")
    check("touchpad" in devs, "opening dev table lists a touchpad")
    check(unenum == 0, "unenumerated stays 0")
    return {"injected": injected, "accepted": accepted, "digitizer": digitizer,
            "m_pad": m_pad, "b_pad": b_pad, "m_other": m_other, "resolved": resolved}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(ROOT, "ftesurf", "data"))
    a = ap.parse_args()

    A = arm(a.data, "A", events_expected=True)
    if A:
        check(A["resolved"], "A: the touchpad resolved a devid")
        check(A["digitizer"] > 0, "A: the pad reported (%d digitizer reports)" % A["digitizer"])
        check(A["m_pad"] > 0, "A: the touchpad produced motion events (%d)" % A["m_pad"])
        check(A["accepted"] >= A["m_pad"] and A["accepted"] > 0,
              "A: accepted covers the touchpad's motion events (%d >= %d)" % (A["accepted"], A["m_pad"]))
        check(A["injected"] * 10 < max(1, A["accepted"]),
              "A: injected under a tenth of accepted (%d vs %d)" % (A["injected"], A["accepted"]))
    B = arm(a.data, "B", events_expected=False)
    if B:
        check(B["digitizer"] > 0, "B: the pad reported (%d digitizer reports)" % B["digitizer"])
        check(B["m_pad"] == 0 and B["b_pad"] == 0,
              "B: no event from the touchpad devid (%d motion, %d button)" % (B["m_pad"], B["b_pad"]))
        check(B["accepted"] == 0, "B: accepted 0 (%d)" % B["accepted"])
        check(B["injected"] > 0, "B: injected > 0 (%d)" % B["injected"])
        if A and A["accepted"]:
            lo, hi = A["accepted"] / 4.0, A["accepted"] * 4.0
            check(lo <= B["injected"] <= hi,
                  "B: injected within 4x of A's accepted (%d vs %d)" % (B["injected"], A["accepted"]))
    C = arm(a.data, "C", events_expected=False)
    if C:
        check(C["digitizer"] == 0, "C: a resting pad reports nothing (%d)" % C["digitizer"])
        check(C["accepted"] == 0 and C["injected"] == 0,
              "C: nothing accepted, nothing injected (%d, %d)" % (C["accepted"], C["injected"]))
        check(C["m_pad"] == 0 and C["m_other"] == 0 and C["b_pad"] == 0, "C: no events at all")

    print("\n%d prediction(s) failed" % len(FAILED))
    for f in FAILED:
        print("  FAILED: %s" % f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
