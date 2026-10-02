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


def check(cond, what):
    print("  %s  %s" % ("ok  " if cond else "FAIL", what))
    if not cond:
        FAILED.append(what)


def parse(path):
    """-> (header dict, [dev types], {devmap type: id}, {devid: m count}, trailer)."""
    head, devs, devmaps, m_by_dev, trailer = {}, [], {}, {}, None
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
            elif t[0] == "devmap" and len(t) >= 3:
                devmaps[t[1]] = t[2]
            elif t[0] == "end":
                trailer = t[1:]
    return head, devs, devmaps, m_by_dev, trailer


def arm(data, letter):
    path = os.path.join(data, "p468_%s.hid" % letter)
    print("ARM %s  %s" % (letter, path))
    if not os.path.exists(path):
        check(False, "journal exists")
        return None
    head, devs, devmaps, m_by_dev, trailer = parse(path)
    # end <dt> <abs> <events> <frames> <dropped> <hidden> <inj> <unenum> <lgb> <pad>
    if trailer is None or len(trailer) < 10:
        check(False, "trailer has the Patch 468 field (got %r)" % (trailer,))
        return None
    injected, unenum, accepted = int(trailer[6]), int(trailer[7]), int(trailer[9])
    paddev = devmaps.get("touchpad", "-")
    m_pad = m_by_dev.get(paddev, 0) if paddev not in ("-", "unset") else 0
    m_other = sum(n for d, n in m_by_dev.items() if d != paddev)
    print("      rawpads %s  dev-table touchpad %s  devmap touchpad %s  m[pad] %d  m[other] %d"
          % (head.get("rawpads", "?"), "yes" if "touchpad" in devs else "NO", paddev, m_pad, m_other))
    print("      trailer: injected %d  unenum %d  accepted %d" % (injected, unenum, accepted))
    r = hidcheck.check_hid(path)
    for n in r.notes:
        if "touchpad" in n or "REJECTED" in n:
            print("      hidcheck: %s" % n[:160])
    check(not r.faults, "hidcheck finds no fault (%s)" % (r.faults[:1] or "none"))
    check(head.get("rawpads") == "1", "header rawpads 1")
    check("touchpad" in devs, "opening dev table lists a touchpad")
    check(unenum == 0, "unenumerated stays 0")
    return {"injected": injected, "accepted": accepted, "m_pad": m_pad, "m_other": m_other,
            "paddev": paddev}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(ROOT, "ftesurf", "data"))
    a = ap.parse_args()

    A = arm(a.data, "A")
    if A:
        check(A["paddev"] not in ("-", "unset"), "A: the touchpad resolved a devid")
        check(A["m_pad"] > 0, "A: the touchpad produced motion events (%d)" % A["m_pad"])
        check(A["accepted"] > 0, "A: accepted > 0 (%d)" % A["accepted"])
        check(A["accepted"] == A["m_pad"],
              "A: accepted == touchpad 'm' records (%d vs %d)" % (A["accepted"], A["m_pad"]))
        check(A["injected"] * 10 < max(1, A["accepted"]),
              "A: injected under a tenth of accepted (%d vs %d)" % (A["injected"], A["accepted"]))
    B = arm(a.data, "B")
    if B:
        check(B["m_pad"] == 0, "B: no motion event from the touchpad devid (%d)" % B["m_pad"])
        check(B["accepted"] == 0, "B: accepted 0 (%d)" % B["accepted"])
        check(B["injected"] > 0, "B: injected > 0 (%d)" % B["injected"])
        if A and A["accepted"]:
            lo, hi = A["accepted"] / 4.0, A["accepted"] * 4.0
            check(lo <= B["injected"] <= hi,
                  "B: injected within 4x of A's accepted (%d vs %d)" % (B["injected"], A["accepted"]))
    C = arm(a.data, "C")
    if C:
        check(C["accepted"] == 0 and C["injected"] == 0,
              "C: nothing accepted, nothing injected (%d, %d)" % (C["accepted"], C["injected"]))
        check(C["m_pad"] == 0 and C["m_other"] == 0, "C: no motion events at all")

    print("\n%d prediction(s) failed" % len(FAILED))
    for f in FAILED:
        print("  FAILED: %s" % f)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
