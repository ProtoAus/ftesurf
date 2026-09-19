#!/usr/bin/env python3
"""
spectrace.py -- verdicts for Patch 385's spectate harness (cfg/test/p385view.cfg).

Reads the viewer log.  Line shapes (after the log's timestamp):

  spt <cltime> <stat> <mode> <tslot> <posebits> <clr> <dcur> <want>
      <cam x y z> <cam pitch> <cam yaw>
      <feet x y z> <eye> <body pitch> <body yaw> <rtick>
      <aim pitch> <aim yaw> <own eye x y z> <hideslot> [<allow>]
        one frame (client/cl_spectate.qc Spec_Trace); tslot -1 = your camera;
        clr -1 outside third person; allow = the distance the map allows
        (-1 outside third person; absent in pre-allow logs); rtick = the watched body's render clock in
        ticks (an integer = drawn on a sample), -1 none
  bt <cltime> <rtick> <org x y z> <yaw> <pitch> <eye> <st> <keys> <kraw>
     <slot> <flags>
        the first stream body, printed by Body_Frame just before the same
        frame's spt line (client/cl_body.qc Body_Trace) -- P3's reference
  vote key: scan S down D took T ...       (a key through the input chain)
  spectate look: took T, ...               (a mouse delta through the chain)
  setpos x y z pitch yaw roll              (`cmd viewpos`)
  spectate: stat S ... board B            (`spectate status`, first line)
  ... hud H run R                          (`spectate status`, while watching)
  p385view: <ID> ...                       the markers; every line is tagged
                                           with the latest one

--server adds the server log (P11 eye lines, P12's release reason, P17's
anti-hover lines).  Prints one verdict per prediction the cfg registers,
controls included: a control reads FAILS when it fails the gate as registered.

usage: python tools/spectrace.py <viewer log> [--server <log>] [--tick 0.015]
"""

import math
import re
import sys

STAMP = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ")
MARK = re.compile(r"p385view: (\S+)")
VOTE = re.compile(r"vote key: scan (-?\d+) down (\d+) took (\d+)")
LOOK = re.compile(r"spectate look: took (\d+)")
SETPOS = re.compile(r"^setpos (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)")
STATUS = re.compile(r"hud (\d+) run (\d+)")
STATL = re.compile(r"spectate: stat (-?[\d.]+) .*board (\d+)")
SNAP = 32

K = dict(t=0, stat=1, mode=2, ts=3, bp=4, clr=5, dcur=6, want=7, cx=8, cy=9, cz=10,
         cp=11, cyaw=12, fx=13, fy=14, fz=15, eye=16, bpitch=17, byaw=18, rt=19,
         ap=20, ay=21, ox=22, oy=23, oz=24, hide=25, allow=26)


class Frame:
    __slots__ = ("v", "lab", "bt")

    def __init__(self, v, lab, bt):
        self.v = v
        self.lab = lab
        self.bt = bt        # this frame's bt: [t rt ox oy oz yaw pitch eye st keys kraw slot flags]

    def __getattr__(self, name):
        return self.v[K[name]]


def wrap(a):
    return a - 360.0 * math.floor((a + 180.0) / 360.0)


def parse(path):
    frames, votes, looks, setpos, status, stl, text = [], [], [], [], [], [], []
    lab = ""
    bt = None
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = STAMP.sub("", raw.strip())
            text.append((lab, line))
            m = MARK.search(line)
            if m:
                lab = m.group(1)
                continue
            f = line.split()
            if f and f[0] == "bt" and len(f) >= 14:
                try:
                    bt = [float(x) for x in f[1:14]]
                except ValueError:
                    bt = None
                continue
            if f and f[0] == "spt" and len(f) >= 27:
                try:
                    v = [float(x) for x in f[1:28]]
                    if len(v) < 27:
                        v.append(-1.0)
                    frames.append(Frame(v, lab, bt if bt and abs(bt[0] - v[0]) < 1e-5 else None))
                except ValueError:
                    pass
                continue
            m = VOTE.search(line)
            if m:
                votes.append((lab, int(m.group(1)), int(m.group(2)), int(m.group(3))))
                continue
            m = LOOK.search(line)
            if m:
                looks.append((lab, int(m.group(1))))
                continue
            m = SETPOS.search(line)
            if m:
                setpos.append((lab, [float(m.group(i)) for i in range(1, 7)]))
                continue
            m = STATL.search(line)
            if m:
                stl.append((lab, float(m.group(1)), int(m.group(2))))
                continue
            m = STATUS.search(line)
            if m:
                status.append((lab, int(m.group(1)), int(m.group(2))))
    return frames, votes, looks, setpos, status, stl, text


def marktimes(path):
    """{marker: the wall-clock stamp of its first line} from the viewer log."""
    out = {}
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            m = MARK.search(raw)
            if m and STAMP.match(raw):
                out.setdefault(m.group(1), raw[:19])
    return out


def seg(frames, *labs):
    return [f for f in frames if f.lab in labs]


def segp(frames, *labs):
    """seg() plus the frame drawn just before it: a marker's command runs before
    the next frame, so a change it causes can sit on the segment's first frame."""
    for j, f in enumerate(frames):
        if f.lab in labs:
            return frames[max(0, j - 1):j] + [g for g in frames[j:] if g.lab in labs]
    return []


def dedupe(vals):
    out = []
    for v in vals:
        if not out or out[-1] != v:
            out.append(v)
    return out


def edges(frames):
    """[(cltime, stat)] at each change of stat, the first frame included."""
    out, last = [], None
    for f in frames:
        if f.stat != last:
            out.append((f.t, f.stat))
            last = f.stat
    return out


def verdict(name, ok, msg):
    print("%-4s %-5s %s" % (name, ok, msg))


def took(votes, lab, scan, down):
    return [t for (l, s, d, t) in votes if l == lab and s == scan and d == down]


def btdist(f):
    b = f.bt
    return math.sqrt((f.cx - b[2]) ** 2 + (f.cy - b[3]) ** 2 + (f.cz - b[4] - b[7]) ** 2)


def yawspan(fr):
    acc, lo, hi = 0.0, 0.0, 0.0
    for a, b in zip(fr, fr[1:]):
        acc += wrap(b.ay - a.ay)
        lo, hi = min(lo, acc), max(hi, acc)
    return hi - lo


def printed(text, labs, what):
    return any(what in s for (l, s) in text if l in labs)


def owndist(f):
    return math.sqrt((f.cx - f.ox) ** 2 + (f.cy - f.oy) ** 2 + (f.cz - f.oz) ** 2)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    tick = 0.015
    server = None
    i = 2
    while i < len(argv):
        if argv[i] == "--server":
            server = argv[i + 1]
            i += 2
        elif argv[i] == "--tick":
            tick = float(argv[i + 1])
            i += 2
        else:
            print("unknown argument %r" % argv[i])
            return 2

    frames, votes, looks, setpos, status, stl, text = parse(argv[1])
    labs = dedupe([f.lab for f in frames])
    print("frames %d  markers %s" % (len(frames), " ".join(labs)))
    if not frames:
        verdict("ALL", "FAIL", "no spt lines")
        return 1
    dist = 110.0
    for (l, line) in text:
        m = re.search(r"\"spec_dist\" is \"([\d.]+)\"", line)
        if m:
            dist = float(m.group(1))

    # ---- P1 entry ------------------------------------------------------------
    own = two = None
    t_req = t_in = t_rel = None
    e = seg(frames, "E", "TK", "L")
    for f in e:
        if t_req is None and f.want > 0:
            t_req, w = f.t, f.want
        if t_req is not None and f.stat > 0:
            t_in, own = f.t, f.stat
            break
    if t_req is None or t_in is None:
        verdict("P1", "FAIL", "no request/entry in E")
    else:
        lat = t_in - t_req
        verdict("P1", "PASS" if lat <= 1.0 and own == w else "FAIL",
                "entry %.3f s after the request (want %g -> stat %g)" % (lat, w, own))

    # ---- the first window: entry .. the X release -----------------------------
    for f in frames:
        if f.lab in ("X", "X2", "XE") and f.stat == 0:
            t_rel = f.t
            break
    win = [f for f in frames if t_in is not None and t_rel is not None and t_in + 0.3 <= f.t < t_rel]

    # ---- P2 frozen body ------------------------------------------------------
    if not win:
        verdict("P2", "FAIL", "no held window (entry %s, release %s)" % (t_in, t_rel))
    else:
        o0 = win[0]
        dev = max(math.sqrt((f.ox - o0.ox) ** 2 + (f.oy - o0.oy) ** 2 + (f.oz - o0.oz) ** 2) for f in win)
        path = 0.0
        for a, b in zip(win, win[1:]):
            if a.ts == b.ts and a.ts >= 0 and not (int(b.bp) & SNAP):
                path += math.sqrt((b.fx - a.fx) ** 2 + (b.fy - a.fy) ** 2 + (b.fz - a.fz) ** 2)
        sp = {l: v for (l, v) in setpos}
        spok = all(k in sp for k in ("V0", "E", "XE"))
        if spok:
            spdev = max(abs(sp[k][j] - sp["V0"][j]) for k in ("E", "XE") for j in range(6))
        verdict("P2", "PASS" if dev <= 0.1 and spok and spdev <= 0.15 else "FAIL",
                "own eye moved %.4f u over %.1f s; setpos V0/E/XE %s" %
                (dev, win[-1].t - win[0].t, ("max diff %.2f" % spdev) if spok else "MISSING"))
        verdict("P2c", "FAILS" if path >= 100 else "VOID",
                "CONTROL: the target's feet travelled %.0f u in the same frames" % path)

    # ---- P3 first-person position, against the stream's own print (bt) ---------
    fp = [f for f in frames if f.mode == 0 and f.ts >= 0 and f.bt is not None and f.bt[11] >= 0]
    same = [f for f in fp if int(f.bt[11]) == int(f.ts)]
    other = [f for f in fp if int(f.bt[11]) != int(f.ts)]
    bad = [f for f in same if btdist(f) > 0.5]
    verdict("P3", "PASS" if same and not bad else "FAIL",
            "%d/%d first-person frames off the bt body's eye by > 0.5 u (max %.3f); %d without a bt line" %
            (len(bad), len(same), max([btdist(f) for f in same] or [0]),
             sum(1 for f in frames if f.mode == 0 and f.ts >= 0 and f.bt is None)))
    off = [f for f in other if btdist(f) > 0.5]
    verdict("P3c", ("FAILS" if 2 * len(off) > len(other) else "PASSES") if other else "VOID",
            "CONTROL: %d/%d frames watching the other body are > 0.5 u off the bt body's eye" %
            (len(off), len(other)))

    # ---- P4 smoothness against the sampled motion -------------------------------
    table = {}
    for f in frames:
        if f.ts >= 0 and f.rt >= 0 and abs(f.rt - round(f.rt)) < 0.03:
            table.setdefault(f.ts, {})[int(round(f.rt))] = f.byaw
    keys = {ts: sorted(d) for ts, d in table.items()}

    def srate(ts, rt):
        ks = keys.get(ts)
        if not ks:
            return None
        lo, hi = 0, len(ks) - 1
        if rt < ks[0] or rt >= ks[-1]:
            return None
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if ks[mid] <= rt:
                lo = mid
            else:
                hi = mid
        k1, k2 = ks[lo], ks[hi]
        # 60 ticks: at a frame rate near the tick rate, on-tick frames come in clumps
        # one beat (~0.6 s) apart; the owner turns at a constant cl_yawspeed.
        if k2 - k1 > 60 or k2 <= k1:
            return None
        return wrap(table[ts][k2] - table[ts][k1]) / ((k2 - k1) * tick)

    def smooth(pairs):
        n = band = zero = 0
        for a, b in pairs:
            dt = b.t - a.t
            if dt <= 0 or dt > 0.05:
                continue
            r = srate(b.ts, 0.5 * (a.rt + b.rt))
            if r is None or abs(r) < 60:
                continue
            dy = wrap(b.cyaw - a.cyaw)
            n += 1
            if abs(dy) < 1e-4:
                zero += 1
            if 0.8 <= (dy / dt) / r <= 1.2:
                band += 1
        return n, band, zero

    def fpairs(sel):
        out = []
        for a, b in zip(frames, frames[1:]):
            if sel(a) and sel(b) and a.ts == b.ts and a.ts >= 0 and a.mode == 0 and b.mode == 0 \
               and not (int(b.bp) & SNAP):
                out.append((a, b))
        return out

    n, band, zero = smooth(fpairs(lambda f: f.lab not in ("C1",)))
    if n:
        verdict("P4", "PASS" if band >= 0.9 * n and zero <= 0.01 * n else "FAIL",
                "%d frames: %.1f%% in 0.8..1.2 of the sampled rate, %.2f%% without a yaw step" %
                (n, 100.0 * band / n, 100.0 * zero / n))
    else:
        verdict("P4", "FAIL", "no first-person frames with a sampled rate >= 60 deg/s")
    n, band, zero = smooth(fpairs(lambda f: f.lab == "C1"))
    if n:
        fails = band < 0.9 * n or zero > 0.01 * n
        verdict("P4c", "FAILS" if fails else "PASSES",
                "CONTROL cl_body_raw 1: %d frames, %.1f%% in band, %.1f%% without a step" %
                (n, 100.0 * band / n, 100.0 * zero / n))
    else:
        verdict("P4c", "VOID", "CONTROL: no C1 frames")

    # ---- P5 third person -------------------------------------------------------
    th = [f for f in frames if f.mode == 1 and f.ts >= 0 and f.lab not in ("TN",)]
    nclr = [f for f in th if f.clr != 1]
    verdict("P5", "PASS" if th and not nclr else "FAIL",
            "%d/%d third-person frames not clear" % (len(nclr), len(th)))
    tw = [f for f in frames if f.lab == "TW" and f.mode == 1]
    if tw:
        m = min(f.dcur for f in tw)
        verdict("P5w", "PASS" if m < 0.9 * dist else "VOID",
                "TW: min dcur %.1f (spec_dist %g) -- the floor %s" % (m, dist, "pulled it in" if m < 0.9 * dist else "was never met"))
    else:
        verdict("P5w", "FAIL", "no TW frames")
    te = [f for f in frames if f.lab == "TE" and f.mode == 1]
    if te:
        top = max(f.dcur for f in te)
        drops = [(a, b) for a, b in zip(te, te[1:]) if b.dcur < a.dcur - 0.01]
        # A fall onto the map's limit is the pull-in; only a fall above it is the ease's.
        pulls = sum(1 for a, b in drops if b.allow >= 0 and abs(b.dcur - b.allow) <= 0.01)
        eases = len(drops) - pulls
        reach = next((f.t - te[0].t for f in te if f.dcur >= 0.95 * dist), None)
        ok = not eases and reach is not None and reach <= 0.6
        if drops and te[0].allow < 0:
            state = "VOID"      # a pre-allow log cannot tell the two apart
        else:
            state = "PASS" if ok else "FAIL"
        verdict("P5e", state,
                "TE: from %.1f to %.1f, %d falls onto the map's limit, %d ease falls, 95%% of %g after %s s" %
                (te[0].dcur, top, pulls, eases, dist, ("%.3f" % reach) if reach is not None else "never"))
    else:
        verdict("P5e", "FAIL", "no TE frames")
    tn = [f for f in frames if f.lab == "TN" and f.mode == 1 and f.ts >= 0]
    blk = [f for f in tn if f.clr == 0 and abs(f.dcur - dist) <= 0.01]
    verdict("P5c", "FAILS" if blk else "VOID",
            "CONTROL spec_notrace 1: %d/%d frames at spec_dist and not clear" % (len(blk), len(tn)))

    # ---- P6 SPACE --------------------------------------------------------------
    def modesteps(labsel):
        fr = segp(frames, *labsel)
        return [(int(a.mode), int(b.mode)) for a, b in zip(fr, fr[1:]) if a.mode != b.mode]

    s1 = took(votes, "S1", 32, 1) + took(votes, "S1", 32, 0)
    st1 = modesteps(("S1",))
    s1u = took(votes, "S1U", 32, 0)
    verdict("P6", "PASS" if s1 == [1, 1, 1] and st1 == [(0, 1)] and modesteps(("S2", "F", "FE")) == [(1, 2)]
            and modesteps(("S3",)) == [(2, 0)] else "FAIL",
            "S1 took %s steps %s; S2..FE %s; S3 %s" % (s1, st1, modesteps(("S2", "F", "FE")), modesteps(("S3",))))
    verdict("P6c", "FAILS" if s1u == [0] and not modesteps(("S1U",)) else "PASSES",
            "CONTROL unpaired up: took %s, steps %s" % (s1u, modesteps(("S1U",))))

    # ---- P7 MOUSE1 / MOUSE2 ----------------------------------------------------
    m1 = segp(frames, "M1")
    m2 = seg(frames, "M2")
    ok7 = False
    msg = "no M1/M2 frames"
    if m1 and m2:
        s0 = m1[0].stat
        ch = next((f for f in m1 if f.stat != s0), None)
        two = ch.stat if ch else None
        back = next((f for f in m2 if f.stat != two), None)
        vals = set(f.stat for f in m1 + m2)
        lat1 = (ch.t - m1[0].t) if ch else 99
        lat2 = (back.t - m2[0].t) if back else 99
        tk = took(votes, "M1", 512, 1) + took(votes, "M1", 512, 0) + took(votes, "M2", 513, 1) + took(votes, "M2", 513, 0)
        ok7 = (ch is not None and back is not None and back.stat == s0 and lat1 <= 1.0 and lat2 <= 1.0
               and all(v > 0 for v in vals) and tk == [1, 1, 1, 1])
        msg = "stat %g -> %s in %.3f s -> %s in %.3f s; took %s" % (s0, two, lat1, back.stat if back else None, lat2, tk)
    verdict("P7", "PASS" if ok7 else "FAIL", msg)
    c = took(votes, "C-M1", 512, 1) + took(votes, "C-M1", 512, 0)
    verdict("P7c", "FAILS" if c == [0, 0] else "PASSES", "CONTROL not spectating: took %s" % c)

    # ---- P8 turn keys ----------------------------------------------------------
    t8 = took(votes, "TK", 130, 1)
    c8 = took(votes, "C-TK", 130, 1)
    verdict("P8", "PASS" if t8 == [1] else "FAIL", "turn key down while watching: took %s" % t8)
    verdict("P8c", "FAILS" if c8 == [0] else "PASSES", "CONTROL not spectating: took %s" % c8)

    # ---- P9 the countdown ------------------------------------------------------
    xf = seg(frames, "X", "X2", "XE")
    ed = edges(xf)
    seq = [s for (_, s) in ed]
    iv = [b[0] - a[0] for a, b in zip(ed[1:], ed[2:])]
    cd = [f for f in xf if f.stat < 0]
    offown = [f for f in cd if f.ts != -1 or owndist(f) > 0.5]
    x2 = took(votes, "X2", 27, 1)
    ok9 = (len(seq) == 5 and seq[1:] == [-3, -2, -1, 0] and seq[0] > 0 and len(iv) == 3
           and all(0.85 <= x <= 1.15 for x in iv) and cd and not offown and x2 == [1])
    verdict("P9", "PASS" if ok9 else "FAIL",
            "stat %s, intervals %s, %d countdown frames off your eye, X2 took %s" %
            (seq, ["%.3f" % x for x in iv], len(offown), x2))
    c9 = took(votes, "C-ESC", 27, 1)
    verdict("P9c", "FAILS" if c9 == [0] else "PASSES", "CONTROL esc not spectating: took %s" % c9)

    # ---- P10 the aim -----------------------------------------------------------
    ref = None
    for f in frames:
        if f.want > 0 and f.lab == "E":
            break
        ref = f
    aw = [f for f in frames if t_in is not None and t_rel is not None and t_in <= f.t <= t_rel + 0.5]
    if ref is None or not aw:
        verdict("P10", "FAIL", "no reference or window")
    else:
        d = max(max(abs(f.ap - ref.ap), abs(wrap(f.ay - ref.ay))) for f in aw)
        lk = [t for (l, t) in looks if l in ("L", "T", "TW", "TE", "TL", "TN")]
        verdict("P10", "PASS" if d <= 1e-3 and lk and all(t == 1 for t in lk) else "FAIL",
                "aim moved %.5f deg over %d frames; %d looks, took %s" % (d, len(aw), len(lk), sorted(set(lk))))
    cl = [t for (l, t) in looks if l == "C-L"]
    verdict("P10l", "FAILS" if cl == [0] else "PASSES", "CONTROL a look while not spectating: took %s" % cl)
    g = seg(frames, "G")
    if g:
        un, acc = [], 0.0
        for a, b in zip(g, g[1:]):
            acc += wrap(b.ay - a.ay)
            un.append(acc)
        rng = (max(un) - min(un)) if un else 0
        verdict("P10c", "FAILS" if rng >= 90 else "VOID", "CONTROL ghost + +left: the aim yaw spans %.1f deg" % rng)
    else:
        verdict("P10c", "VOID", "CONTROL: no G frames")

    # ---- P11 the free camera ---------------------------------------------------
    def flew(lab):
        ff = [f for f in frames if f.lab == lab and f.mode == 2 and f.stat > 0]
        if not ff:
            return 0
        return math.sqrt((ff[-1].cx - ff[0].cx) ** 2 + (ff[-1].cy - ff[0].cy) ** 2 + (ff[-1].cz - ff[0].cz) ** 2)

    mv, mfx = flew("F"), flew("FX")
    msg = "camera flew %.0f u (F), %.0f u (FX, to the ESC)" % (mv, mfx)
    ok11 = mv >= 900 and mfx >= 300
    if server:
        sv = open(server, "r", encoding="utf-8", errors="replace").read().splitlines()

        def n(what):
            return sum(1 for s in sv if ("P385View " + what) in s)

        cl, rl, cdn, stale, ig = (n("eye -> client"), n("eye -> server (released)"),
                                  n("eye -> server (countdown)"), n("eye -> server (stale)"),
                                  n("eye claim ignored (countdown)"))
        ok11 = ok11 and cl == 2 and rl == 1 and cdn == 1 and stale == 0 and ig == 1
        msg += "; server: %d '-> client', %d '(released)', %d '(countdown)', %d '(stale)', %d 'ignored'" % (
            cl, rl, cdn, stale, ig)
        verdict("P11c", "FAILS" if ig >= 1 else "VOID",
                "CONTROL X2's typed claim inside the countdown: %d 'claim ignored' line(s)" % ig)
    else:
        msg += "; (no --server: eye lines unchecked)"
    verdict("P11", "PASS" if ok11 else "FAIL", msg)

    # ---- P12 the target leaves -------------------------------------------------
    lv = seg(frames, "LV", "DONE")
    seq = dedupe([f.stat for f in lv])
    # 0, Two, Own, -3, -2, -1, 0
    ok12 = (len(seq) == 7 and seq[0] == 0 and seq[1] > 0 and seq[2] > 0 and seq[1] != seq[2]
            and seq[3:] == [-3, -2, -1, 0])
    msg = "stat %s" % seq
    if server:
        nt = sum(1 for s in sv if "P385View released (notarget)" in s)
        ok12 = ok12 and nt == 1
        msg += "; %d 'released (notarget)'" % nt
    verdict("P12", "PASS" if ok12 else "FAIL", msg)

    # ---- P13 a server refusal --------------------------------------------------
    rf = seg(frames, "R")
    wt = [f for f in rf if f.want > 0]
    span = None
    if wt:
        after = next((f for f in rf if f.t > wt[0].t and f.want == 0), None)
        span = (after.t - wt[0].t) if after else None
    said = any("stop the replay first" in s for (l, s) in text if l == "R")
    noans = any("the server did not answer" in s for (l, s) in text)
    ok13 = span is not None and span <= 0.5 and all(f.stat == 0 for f in rf) and said and not noans
    verdict("P13", "PASS" if ok13 else "FAIL",
            "pending for %s s, refusal %s, 'did not answer' %s" %
            (("%.3f" % span) if span is not None else "never cleared/never set", "logged" if said else "MISSING",
             "PRESENT" if noans else "absent"))

    # ---- P14 back to held ------------------------------------------------------
    hs = dedupe([f.stat for f in seg(frames, "H")])
    os_ = dedupe([f.stat for f in seg(frames, "O")])
    first = next((j for j, s in enumerate(hs) if s > 0), None)
    ok14 = False
    if first is not None:
        rest = hs[first:]
        neg = [j for j, s in enumerate(rest) if s < 0]
        ok14 = (0 not in rest and neg and rest[-1] == rest[0] and rest[-1] > 0
                and os_[-4:] == [-3, -2, -1, 0])
    verdict("P14", "PASS" if ok14 else "FAIL", "H stat %s; O stat %s" % (hs, os_))

    # ---- P15 the HUD feed ------------------------------------------------------
    st = [(h, r) for (l, h, r) in status if l in ("E", "TK")]
    verdict("P15", "PASS" if st and st[0] == (1, 1) else "FAIL", "status after E: hud/run %s" % (st[:1],))

    # ---- P16 SPACE held into the window ---------------------------------------
    sr = took(votes, "SR0", 32, 1) + took(votes, "SR", 32, 1) + took(votes, "SRU", 32, 0)
    # SR runs in the same frame as SRU; the window holds for SRU's first 0.4 s.
    sru = seg(frames, "SR", "SRU")
    srs = [f.stat for f in sru if f.t - sru[0].t < 0.4]
    stp = modesteps(("SR", "SRU"))
    verdict("P16", "PASS" if sr == [0, 0, 0] and not stp and srs and all(s > 0 for s in srs) else "FAIL",
            "took %s, mode steps %s, watching through SR %s" % (sr, stp, bool(srs) and all(s > 0 for s in srs)))
    rep = took(votes, "S1", 32, 1)[1:2]
    verdict("P16c", "FAILS" if rep == [1] else "PASSES", "CONTROL a repeat of a taken press (S1): took %s" % rep)

    # ---- P17 no time in the window ---------------------------------------------
    if server:
        mt = marktimes(argv[1])
        lo, hi = mt.get("E"), mt.get("XE")

        def forced(who, windowed):
            n = 0
            for s in sv:
                if who + ": forcing" in s and "anti-hover" in s:
                    if not windowed or (lo and hi and lo <= s[:19] <= hi):
                        n += 1
            return n

        hv, hall = forced("P385View", True), forced("P385View", False)
        ho = forced("P385Own", False)
        verdict("P17", "PASS" if hv > 0 else "FAIL",
                "%d anti-hover lines for P385View between E (%s) and XE (%s); %d in the whole log" %
                (hv, lo, hi, hall))
        verdict("P17c", "FAILS" if ho == 0 else "PASSES", "CONTROL: %d for P385Own" % ho)
    else:
        verdict("P17", "FAIL", "needs --server")

    # ---- P18 a held turn key refuses the entry ----------------------------------
    tk = seg(frames, "TKR")
    r18 = printed(text, ("TKR",), "let go of the turn key first")
    ok18 = r18 and tk and all(f.want == 0 and f.stat == 0 for f in tk)
    verdict("P18", "PASS" if ok18 else "FAIL", "refusal %s; %d TKR frames, want/stat nonzero on %d" % (
        "printed" if r18 else "MISSING", len(tk), sum(1 for f in tk if f.want or f.stat)))

    # ---- P19 the room-list click's hand-off --------------------------------------
    pks = [(a, b) for (l, a, b) in stl if l == "PKS"]
    pk = [(a, b) for (l, a, b) in stl if l == "PK"]
    pkf = seg(frames, "PK")
    ent = next((f for f in pkf if f.stat > 0), None)
    lat = (ent.t - pkf[0].t) if ent else None
    ok19 = (printed(text, ("PKS",), "you cannot watch yourself") and pks[:1] == [(0, 1)]
            and lat is not None and lat <= 1.0 and pk and pk[0][0] > 0 and pk[0][1] == 0)
    verdict("P19", "PASS" if ok19 else "FAIL", "PKS status %s; PK entry after %s s, status %s" % (
        pks[:1], ("%.3f" % lat) if lat is not None else "never", pk[:1]))

    # ---- P20 ESC with the board pinned while watching ----------------------------
    bf = seg(frames, "B", "BE", "CD")
    be = [(a, b) for (l, a, b) in stl if l == "BE"]
    t20 = took(votes, "BE", 27, 1) + took(votes, "CD", 27, 1)
    ok20 = (t20 == [1, 1] and bf and len(set(f.stat for f in bf)) == 1 and bf[0].stat > 0
            and be and be[0][1] == 0)
    verdict("P20", "PASS" if ok20 else "FAIL", "took %s (board, draft); stat through B/BE/CD %s; status %s" % (
        t20, dedupe([f.stat for f in bf]), be[:1]))

    # ---- P21 ghost and ESC while asking ------------------------------------------
    ep = seg(frames, "EP")
    seq = dedupe([f.stat for f in ep])
    end = None
    if seq and min(seq) < 0:
        neg = next(i for i, f in enumerate(ep) if f.stat < 0)
        z = next((f for f in ep[neg:] if f.stat == 0), None)
        end = (z.t - ep[0].t) if z else None
    gr = printed(text, ("EP",), "stop spectating first")
    lg = printed(text, ("EP", "SP", "SPR", "TC", "TCR", "TCE"), "leave ghost first")
    t21 = took(votes, "EP", 27, 1)
    ok21 = (gr and printed(text, ("EP",), "asked for off") and not lg and t21 == [1]
            and seq and seq[0] == 0 and end is not None and end <= 4.5)
    verdict("P21", "PASS" if ok21 else "FAIL",
            "ghost refused %s, esc took %s, stat %s, back at 0 after %s s, 'leave ghost first' %s" % (
                gr, t21, seq, ("%.3f" % end) if end is not None else "never", "PRESENT" if lg else "absent"))

    # ---- P22 SPACE taken while asking, held into the window ----------------------
    t22 = took(votes, "SP", 32, 1) + took(votes, "SPR", 32, 1) + took(votes, "SPR", 32, 0)
    st22 = modesteps(("SP", "SPR"))
    spr = seg(frames, "SPR")
    w22 = [f.stat for f in spr if f.t - spr[0].t < 0.4] if spr else []
    ok22 = t22 == [1, 1, 1] and not st22 and w22 and all(x > 0 for x in w22)
    verdict("P22", "PASS" if ok22 else "FAIL", "took %s, mode steps %s, watching through SPR %s" % (
        t22, st22, bool(w22) and all(x > 0 for x in w22)))

    # ---- P23 a console turn, stopped by the bare release -------------------------
    tcr = seg(frames, "TCR", "TCE")
    j = next((i for i, f in enumerate(tcr) if f.stat != 0), None)
    if j is None:
        verdict("P23", "FAIL", "no TCR frame with stat != 0")
    else:
        w = tcr[j:]
        d = max(abs(wrap(f.ay - w[0].ay)) for f in w)
        verdict("P23", "PASS" if d <= 1e-3 else "FAIL",
                "aim yaw moved %.5f deg over %.1f s from the entry" % (d, w[-1].t - w[0].t))
    sp23 = yawspan(seg(frames, "TC"))
    verdict("P23c", "FAILS" if sp23 >= 30 else "VOID", "CONTROL +left over TC: the aim yaw spans %.1f deg" % sp23)

    # ---- P24 turn routes the literal check missed ---------------------------------
    rp = seg(frames, "RP")
    al, ms, kl = took(votes, "AL", 111, 1), took(votes, "MS", 112, 1), took(votes, "KL", 107, 1)
    w24 = bool(rp) and all(f.stat > 0 for f in rp)
    verdict("P24", "PASS" if al == [1] and ms == [1, 1] and kl == [1] and w24 else "FAIL",
            "alias %s, shift+p then p %s, klook %s; watching %s" % (al, ms, kl, w24))
    c24 = took(votes, "C-AL", 111, 1) + took(votes, "C-MS", 112, 1) + took(votes, "C-KL", 107, 1)
    verdict("P24c", "FAILS" if c24 == [0, 0, 0] else "PASSES", "CONTROL not spectating: took %s" % c24)

    # ---- P25 local refusals ---------------------------------------------------------
    rg, rt = seg(frames, "RG"), seg(frames, "RT")
    g25 = printed(text, ("RG",), "leave ghost first") and rg and all(f.stat == 0 and f.want == 0 for f in rg)
    t25 = printed(text, ("RT",), "not with cl_threadedphysics on") and rt and all(f.stat == 0 and f.want == 0 for f in rt)
    p25 = printed(text, ("RP",), "stop spectating first") and w24 and len(set(f.stat for f in rp)) == 1
    verdict("P25", "PASS" if g25 and t25 and p25 else "FAIL",
            "ghost %s, cl_threadedphysics %s, replay %s" % (bool(g25), bool(t25), bool(p25)))

    # ---- P26 a release a panel took ---------------------------------------------------
    kh, kh2 = seg(frames, "KH"), segp(frames, "KH2")
    t26 = took(votes, "KH", 512, 1) + took(votes, "KH", 512, 0) + took(votes, "KH2", 512, 1)
    st26 = None
    if kh2:
        ch = next((f for f in kh2 if f.stat != kh2[0].stat), None)
        st26 = (ch.t - kh2[0].t) if ch else None
    ok26 = t26 == [1, 1, 1] and kh and kh[-1].stat > 0 and st26 is not None and st26 <= 1.0
    verdict("P26", "PASS" if ok26 else "FAIL", "took %s (KH down, its up to the draft, KH2 down); KH2 step %s" % (
        t26, ("after %.3f s" % st26) if st26 is not None else "NONE"))

    # ---- P27 a repeat into the countdown ------------------------------------------------
    krr = segp(frames, "KRR")
    t27 = took(votes, "KR", 32, 1) + took(votes, "KRR", 32, 1) + took(votes, "KRR", 32, 0)
    cnt = bool(krr) and krr[0].stat < 0
    verdict("P27", "PASS" if t27 == [1, 1, 1] and cnt else "FAIL",
            "took %s (KR press, KRR repeat, KRR up); in the countdown %s (stat %s)" % (
                t27, cnt, krr[0].stat if krr else None))

    # ---- P28/P29 right-hand modifiers; a quoted ; --------------------------------------
    ra, cra = took(votes, "RA", -245, 1), took(votes, "C-RA", -245, 1)
    verdict("P28", "PASS" if ra == [1] else "FAIL", "right alt while watching: took %s" % ra)
    verdict("P28c", "FAILS" if cra == [0] else "PASSES", "CONTROL not spectating: took %s" % cra)
    qs = took(votes, "QS", 106, 1)
    verdict("P29", "PASS" if qs == [0] and w24 else "FAIL", "say \"a;b\" while watching: took %s" % qs)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
