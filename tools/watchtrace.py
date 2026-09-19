#!/usr/bin/env python3
"""
watchtrace.py -- the replay viewer's load tables, modelled outside the game, and
the analyser for its `replay trace` dumps.  Patches 378 and 379.

    python tools/watchtrace.py --model REC [--noview]
        the fit / snap / duck / view counters `replay status` prints
    python tools/watchtrace.py --model REC --check LOG
        ...and compares them with every `replay status` block for REC in LOG
    python tools/watchtrace.py --sim new|old REC --at T --n N --dt DT [--noview]
        the `wtr` lines cl_watch.qc should print (old = 378's drawing)
    python tools/watchtrace.py --analyse LOG [--gamedir ftesurf]
        P1-P9 of p379wsm.cfg over every wtr/wtf block in LOG
    python tools/watchtrace.py --compare new|old LOG [--gamedir ftesurf]
        every wtr line in LOG against the simulator: MATCH or SUSPECT
    python tools/watchtrace.py --windows REC
        the snap, unduck and air-duck times a harness window wants
    python tools/watchtrace.py --corpus DIR
        the counters for every .rec under DIR

KEEP IN STEP WITH cl_watch.qc.  scan_rec / scan_view mirror Watch_ScanRecord,
Watch_ScanPair and Watch_ViewMap statement for statement, and float32 is
emulated wherever the QC tests a threshold -- the VM's floats are 32-bit, and a
pair that sits on a threshold is decided by the rounding.  A count that differs
from the game's is SUSPECT until one side is shown wrong.
Stdlib only.
"""

import bisect
import math
import os
import re
import struct
import sys

# cl_watch.qc / sh_interp.qc constants
WT_SNAPMAX = 256
WT_DKMAX = 256
WT_VKMAX = 256
WT_VKSPAN = 192         # knots the file's extent is divided into
WT_VGAP = 0.1           # s of cltime: a longer .view gap starts a span
WT_DUCK_T = 0.4         # pm_source.c PMSRC_TIME_TO_DUCK
WT_UNDUCK_T = 0.2       # pm_source.c PMSRC_TIME_TO_UNDUCK
WT_ASNAP = 45.0         # degrees: a bigger step between two samples is held
INTERP_SNAP, INTERP_LINEAR, INTERP_HERMITE = 0, 1, 2
PM_TICK = 0.015

F_ONGROUND, F_DUCKED, F_RAMP = 1, 2, 16
FSI_DUCK = 32

FORCE_KINDS = ('tele', 'telerel', 'bhop', 'zone')
NEVER_KINDS = ('speed', 'push', 'lift')


def f32(x):
    return struct.unpack('f', struct.pack('f', x))[0]


F01 = f32(0.1)


def is_sample(s):
    """FS_IsSample: a digit or a minus first."""
    if not s:
        return False
    c = s[0]
    return c == '-' or ('0' <= c <= '9')


def atof(s):
    """C atof: the leading number, 0 when there is none."""
    m = re.match(r'\s*([-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?)', s)
    return float(m.group(1)) if m else 0.0


def stof(s):
    return f32(atof(s))


# ---- vector maths in float32, as the QC VM does it ------------------------

def vsub(a, b):
    return (f32(a[0] - b[0]), f32(a[1] - b[1]), f32(a[2] - b[2]))


def vadd(a, b):
    return (f32(a[0] + b[0]), f32(a[1] + b[1]), f32(a[2] + b[2]))


def vmul(a, s):
    return (f32(a[0] * s), f32(a[1] * s), f32(a[2] * s))


def vlen(a):
    d = f32(f32(f32(a[0] * a[0]) + f32(a[1] * a[1])) + f32(a[2] * a[2]))
    return f32(math.sqrt(d))


def interp_fit(p0, v0, p1, v1, dt):
    """sh_interp.qc Interp_Fit."""
    d = vsub(p1, p0)
    r = vlen(vsub(d, vmul(vadd(v0, v1), f32(0.5 * dt))))
    lim = f32(f32(f32(0.5 * f32(vlen(v0) + vlen(v1))) * dt) + 64)
    if r > lim:
        return INTERP_SNAP
    if r > f32(1 + f32(0.05 * vlen(d))):
        return INTERP_LINEAR
    return INTERP_HERMITE


def fit_resid(p0, v0, p1, v1, dt):
    d = [p1[i] - p0[i] for i in range(3)]
    e = [d[i] - (v0[i] + v1[i]) * 0.5 * dt for i in range(3)]
    return math.sqrt(sum(x * x for x in e))


def wrap(a):
    return a - math.floor((a + 180) / 360) * 360


def arc(a, b):
    return wrap(b - a)


def smooth(x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    return x * x * (3 - 2 * x)


def hermite(p0, v0, p1, v1, dt, s):
    s2 = s * s
    s3 = s2 * s
    h00 = 2 * s3 - 3 * s2 + 1
    h10 = dt * (s3 - 2 * s2 + s)
    h01 = 3 * s2 - 2 * s3
    h11 = dt * (s3 - s2)
    return tuple(p0[i] * h00 + v0[i] * h10 + p1[i] * h01 + v1[i] * h11
                 for i in range(3))


# ---- the files ------------------------------------------------------------

def read_lines(path):
    with open(path, 'r', errors='replace') as f:
        return [l.rstrip('\r\n') for l in f]


class Sample(object):
    __slots__ = ('line', 't', 'o', 'v', 'pit', 'yaw', 'fl', 'keys', 'mv')


class Model(object):
    pass


def parse_sample(line, i):
    tok = line.split()
    s = Sample()
    s.line = i
    g = lambda k: stof(tok[k]) if k < len(tok) else 0.0
    s.t = g(0)
    s.o = (g(1), g(2), g(3))
    s.v = (g(4), g(5), g(6))
    s.pit = g(7)
    s.yaw = g(8)
    s.fl = int(g(9))
    s.keys = int(g(10))
    s.mv = (g(11), g(12), g(13))
    return s


def scan_rec(path):
    """Watch_Scan's header and pass two, with the 378 tables."""
    lines = read_lines(path)
    m = Model()
    m.path = path
    m.lines = lines
    m.ver = 0
    m.tickrate = 0.0
    m.vh = 0.0
    m.dvh = 0.0
    m.vhsrc = 0
    m.gravity = 800.0
    rec0 = len(lines)
    for i, s in enumerate(lines):
        tok = s.split()
        if not tok:
            continue
        if tok[0] == 'begin':
            rec0 = i + 1
            break
        if len(tok) < 2:
            continue
        if tok[0] == 'FTESURF-REC':
            m.ver = stof(tok[1])
        if tok[0] == 'tickrate':
            m.tickrate = stof(tok[1])
        if tok[0] == 'pmpin':
            p = s.find(' viewheight=')
            q = s.find(' duckviewheight=')
            if p >= 0 and q >= 0:
                m.vh = stof(s[p + 12:p + 28])
                m.dvh = stof(s[q + 16:q + 32])
                m.vhsrc = 2
            g = s.find(' gravity=')
            if g >= 0:
                m.gravity = atof(s[g + 9:g + 25])
    if m.tickrate <= 0:
        m.tickrate = f32(PM_TICK)
    if m.vhsrc == 0:
        # serverkey pm_viewheight / pm_duckviewheight: default.cfg's 64 / 47
        m.vh, m.dvh, m.vhsrc = 64.0, 47.0, 1
    m.rec0 = rec0

    m.samples = []
    m.snt, m.snk = [], []
    m.snover = 0
    m.snrec = 0
    m.snkin = 0
    m.nfit = [0, 0, 0]
    m.nveto = 0
    m.dks, m.dke, m.dku, m.dkr = [], [], [], []
    m.dkover = 0
    m.dkfix = 0
    m.unducks = []          # (t, prev t) ground hull falls: P4's windows
    m.airducks = []         # (ta, tb) air hull rises: P5's windows
    m.ivfit = {}            # ta -> the verdict Watch_Sample uses (378: informational)

    frc = veto = dkreset = ride = 0
    phase = 0
    press = 0.0
    prev = None

    def seg(ts, te, u0, rate):
        if len(m.dks) >= WT_DKMAX:
            m.dkover += 1
            return
        m.dks.append(f32(ts))
        m.dke.append(f32(te))
        m.dku.append(f32(u0))
        m.dkr.append(f32(rate))

    for i in range(rec0, len(lines)):
        s = lines[i]
        if not is_sample(s):
            # Watch_ScanRecord: only w / p / r lines are tokenized
            if s[:1] not in ('w', 'p', 'r'):
                continue
            tok = s.split()
            if not tok:
                continue
            k = tok[0]
            if k == 'warp' and len(tok) >= 4:
                kind = tok[3]
                if is_sample(kind) and len(tok) >= 5:
                    kind = tok[4]
                if kind in FORCE_KINDS:
                    frc = 1
                elif kind in NEVER_KINDS:
                    veto = 1
            elif k == 'portal':
                frc = 1
            elif k in ('restart', 'resume', 'retry'):
                frc = 1
                dkreset = 1
            elif k == 'ride' and len(tok) >= 7:
                veto = 1
                bv = (stof(tok[4]), stof(tok[5]), stof(tok[6]))
                ride = 1 if (tok[3] == 'arm' and bv != (0.0, 0.0, 0.0)) else 0
            continue

        cur = parse_sample(s, i)
        m.samples.append(cur)
        if prev is not None:
            # ---- Watch_ScanPair ----
            if ride:
                veto = 1
            dt = f32(cur.t - prev.t)
            if dt > 0:
                fit = interp_fit(prev.o, prev.v, cur.o, cur.v, dt)
                m.nfit[fit] += 1
                snap = 0
                if frc:
                    snap = 1
                elif fit == INTERP_SNAP:
                    if veto:
                        m.nveto += 1
                    else:
                        snap = 2
                if snap:
                    if snap == 1:
                        m.snrec += 1
                    else:
                        m.snkin += 1
                    if len(m.snt) < WT_SNAPMAX:
                        m.snt.append(prev.t)
                        m.snk.append(snap)
                    else:
                        m.snover += 1
                    m.ivfit[prev.t] = INTERP_SNAP
                else:
                    if fit == INTERP_SNAP:
                        fit = INTERP_LINEAR
                    if (cur.fl & F_DUCKED) != (prev.fl & F_DUCKED):
                        fit = INTERP_LINEAR
                    m.ivfit[prev.t] = fit

            # the duck-slide machine: PMSrc_Duck at sample resolution
            g = cur.fl & F_ONGROUND
            h = 1 if cur.fl & F_DUCKED else 0
            key = 1 if cur.keys & FSI_DUCK else 0
            pg = prev.fl & F_ONGROUND
            ph = 1 if prev.fl & F_DUCKED else 0
            pkey = 1 if prev.keys & FSI_DUCK else 0
            if dkreset:
                phase = 0
            if h and not ph:
                if phase == 1:
                    seg(press, cur.t if pg else prev.t, 0, f32(1 / WT_DUCK_T))
                    phase = 0
                elif pg:
                    m.dkfix += 1
                if not pg:
                    m.airducks.append((prev.t, cur.t))
            elif ph and not h:
                if pg:
                    seg(f32(cur.t - WT_UNDUCK_T), cur.t, 1, f32(-1 / WT_UNDUCK_T))
                    m.unducks.append((cur.t, prev.t))
                phase = 0
            elif not h:
                if phase == 1 and pkey and not key:
                    u0 = f32(f32(cur.t - press) / WT_DUCK_T)
                    if u0 > 1:
                        u0 = 1.0
                    seg(press, cur.t, 0, f32(1 / WT_DUCK_T))
                    seg(cur.t, f32(cur.t + f32(u0 * WT_UNDUCK_T)), u0,
                        f32(-1 / WT_UNDUCK_T))
                    phase = 0
                elif phase == 0 and key and not pkey and g:
                    phase = 1
                    press = cur.t
        frc = veto = dkreset = 0
        prev = cur

    m.ts = [x.t for x in m.samples]
    return m


def scan_view(m, noview=False):
    """Watch_ViewMap."""
    m.vk = []                   # (line, end, c0, c1, off, brk)
    m.vkover = 0
    m.vspans = 0
    m.vshort = 0
    m.vstall = 0
    m.vlines = None
    m.vstep = 0.0
    vpath = m.path[:-4] + '.view'
    if noview or not os.path.exists(vpath):
        return
    vl = read_lines(vpath)
    m.vlines = vl
    n = len(vl)
    view0 = n
    for i in range(n):
        if is_sample(vl[i]):
            view0 = i
            break
    m.view0 = view0
    if view0 >= n:
        return
    tick = f32(m.tickrate)
    t0 = m.ts[0] if m.ts else 0.0
    if t0 < 0:
        t0 = 0.0
    stride = f32(f32((m.ts[-1] if m.ts else 0.0) - t0) / WT_VKSPAN)
    if stride < 1:
        stride = 1.0
    short = f32(3 * tick)

    st = {'in': 0, 'k0': 0, 'sc0': 0.0, 'kn': None}
    vk = m.vk

    def close_knot():
        kn = st['kn']
        if len(vk) < WT_VKMAX:
            vk.append(tuple(kn))
        else:
            m.vkover += 1

    def close_span():
        close_knot()
        st['in'] = 0
        if f32(st['kn'][3] - st['sc0']) < short:
            del vk[st['k0']:]
            m.vshort += 1
        else:
            m.vspans += 1

    ghost = 0
    pend = 1
    prevc = 0.0
    prevk = -1.0
    kc = 0.0
    for i in range(view0, n):
        s = vl[i]
        if not is_sample(s):
            tok = s.split()
            if tok and tok[0] == 'ghost' and len(tok) >= 2:
                ghost = 1 if stof(tok[1]) != 0 else 0
            if st['in']:
                close_span()
            pend = 1
            continue
        if ghost:
            continue
        tok = s.split()
        if len(tok) < 6:
            continue
        c = stof(tok[0])
        k = stof(tok[2])
        if k != prevk:
            kc = c
        elif f32(c - kc) > F01:
            if st['in']:
                close_span()
            pend = 1
            m.vstall += 1
            prevc = c
            continue
        if st['in']:
            if f32(c - prevc) > F01 or c < prevc or k < prevk:
                close_span()
                pend = 1
        o = f32(c - f32(k * tick))
        if pend:
            st['k0'] = len(vk)
            st['sc0'] = c
            st['kn'] = [i, i, c, c, o, 1]
            st['in'] = 1
            pend = 0
        elif f32(c - st['kn'][2]) >= stride:
            close_knot()
            st['kn'] = [i, i, c, c, o, 0]
        else:
            kn = st['kn']
            kn[1] = i
            kn[3] = c
            if o < kn[4]:
                kn[4] = o
        prevc = c
        prevk = k
    if st['in']:
        close_span()

    for j in range(1, len(vk)):
        if not vk[j][5]:
            d = abs(f32(vk[j][4] - vk[j - 1][4]))
            if d > m.vstep:
                m.vstep = d


def model(path, noview=False):
    m = scan_rec(path)
    scan_view(m, noview)
    return m


def status_lines(m):
    """What Watch_Status prints for the 378 counters (the fixed half)."""
    out = []
    out.append("  fit %d hermite  %d linear  %d snap   snaps %d rec  %d kin  "
               "(%d vetoed, +%d over)" %
               (m.nfit[2], m.nfit[1], m.nfit[0],
                m.snrec, m.snkin, m.nveto, m.snover))
    out.append("  duck %d slide(s)  %d fix  (+%d over)  eye %g / %g  src %d" %
               (len(m.dks), m.dkfix, m.dkover, m.vh, m.dvh, m.vhsrc))
    if m.vlines is not None:
        out.append("  view %d span(s)  %d knot(s)  (+%d over)  %d short  "
                   "%d stalled  step %.1f ms" %
                   (m.vspans, len(m.vk), m.vkover, m.vshort, m.vstall,
                    m.vstep * 1000))
    else:
        out.append("  view none")
    return out


# ---- per-frame simulation: the wtr line each build should print -----------

class Sim(object):
    """Watch_Sample, 378 (old) or 379 (new), as a pure function of T."""

    def __init__(self, m, new, eye_old=(64.0, 47.0)):
        self.m = m
        self.new = new
        self.eye_old = eye_old
        if m.vlines is not None:
            self._view_cache()

    # .view lines, tokenized once for the simulator's own convenience
    def _view_cache(self):
        m = self.m
        self.vc = {}
        for j, kn in enumerate(m.vk):
            for ln in range(kn[0], kn[1] + 1):
                self.vc[ln] = j
        self.vrow = {}
        self.ktau = {}

    def vline(self, ln):
        r = self.vrow.get(ln)
        if r is None:
            tok = self.m.vlines[ln].split()
            r = (stof(tok[0]), stof(tok[2]), stof(tok[3]), stof(tok[4]),
                 int(stof(tok[5])))
            self.vrow[ln] = r
        return r

    def bracket(self, T):
        ts = self.m.ts
        i = bisect.bisect_right(ts, T) - 1
        if i < 0:
            i = 0
        j = i + 1 if i + 1 < len(ts) else -1
        return i, j

    def tau(self, ln, j):
        """c - off, the knot offset lerped toward a same-span next knot."""
        vk = self.m.vk
        c = self.vline(ln)[0]
        off = vk[j][4]
        if j + 1 < len(vk) and not vk[j + 1][5]:
            off = off + (vk[j + 1][4] - vk[j][4]) * (c - vk[j][2]) / \
                (vk[j + 1][2] - vk[j][2])
        return c - off

    def view_new(self, T, rate=False):
        """(pitch, yaw, keys) from the .view, or None when no knot covers T.
        rate: the bracketing line pair's yaw rate instead (None at a hold)."""
        m = self.m
        if m.vlines is None or not m.vk or T < 0:
            return None
        vk = m.vk
        hold = 2 * m.tickrate
        j = 0
        while j + 1 < len(vk) and vk[j + 1][2] - vk[j + 1][4] <= T:
            j += 1
        ts = vk[j][2] - vk[j][4]
        te = vk[j][3] - vk[j][4]
        if T < ts - hold:
            return None
        if T > te + hold and (j + 1 >= len(vk) or vk[j + 1][5]):
            return None
        # the bracket: the last line of knot j at or before T (tau is monotone)
        taus = self.ktau.get(j)
        if taus is None:
            taus = [self.tau(ln, j) for ln in range(vk[j][0], vk[j][1] + 1)]
            self.ktau[j] = taus
        q = bisect.bisect_right(taus, T) - 1
        if q < 0:
            q = 0
        ln = vk[j][0] + q
        kj = j
        a = self.vline(ln)
        ta = self.tau(ln, kj)
        nl = ln + 1
        nk = kj
        ok = True
        if nl > vk[kj][1]:
            if kj + 1 < len(vk) and not vk[kj + 1][5]:
                nk = kj + 1
            else:
                ok = False
        if not ok:
            return None if rate else (a[2], wrap(a[3]), a[4])
        b = self.vline(nl)
        tb = self.tau(nl, nk)
        f = 0.0 if tb <= ta else min(1.0, max(0.0, (T - ta) / (tb - ta)))
        if abs(arc(a[2], b[2])) > WT_ASNAP or abs(arc(a[3], b[3])) > WT_ASNAP:
            return None if rate else (a[2], wrap(a[3]), a[4])
        if rate:
            return abs(arc(a[3], b[3])) / (tb - ta) if tb > ta else None
        return (wrap(a[2] + arc(a[2], b[2]) * f),
                wrap(a[3] + arc(a[3], b[3]) * f), a[4])

    def view_rate(self, T):
        """deg/s of the .view line pair bracketing T, None when uncovered or
        the pair is a >45 degree hold."""
        r = self.view_new(T, True)
        return r

    def duck_frac(self, t, fallback):
        m = self.m
        for k in range(len(m.dks)):
            if m.dks[k] <= t <= m.dke[k]:
                return smooth(m.dku[k] + (t - m.dks[k]) * m.dkr[k]), True
        return fallback, False

    def frame(self, T):
        m = self.m
        i, j = self.bracket(T)
        a = m.samples[i]
        b = m.samples[j] if j >= 0 else None
        s = 0.0
        dt = 0.0
        if b is not None and b.t > a.t:
            dt = b.t - a.t
            s = min(1.0, max(0.0, (T - a.t) / dt))
        fit = m.ivfit.get(a.t, INTERP_LINEAR) if b is not None else INTERP_LINEAR
        if not self.new:
            org = a.o if b is None else tuple(a.o[k] + (b.o[k] - a.o[k]) * s
                                              for k in range(3))
            eyeh = self.eye_old[1] if a.fl & F_DUCKED else self.eye_old[0]
            src = 0
            if m.vlines is not None and T >= 0:
                src = 1
                p, y = self.view_old(T)
            else:
                p, y = a.pit, wrap(a.yaw)
            return (T, org[0], org[1], org[2] + eyeh, p, y, src, fit, eyeh)
        # 379
        if b is None or dt <= 0:
            org = a.o
        elif fit == INTERP_SNAP:
            if s < 0.5:
                org = tuple(a.o[k] + a.v[k] * (T - a.t) for k in range(3))
            else:
                org = tuple(b.o[k] - b.v[k] * (b.t - T) for k in range(3))
        elif fit == INTERP_HERMITE:
            org = hermite(a.o, a.v, b.o, b.v, dt, s)
        else:
            org = tuple(a.o[k] + (b.o[k] - a.o[k]) * s for k in range(3))
        da = 1.0 if a.fl & F_DUCKED else 0.0
        db = (1.0 if b.fl & F_DUCKED else 0.0) if b is not None else da
        fa, _ = self.duck_frac(a.t, da)
        f, cov = self.duck_frac(T, 0)
        if not cov:
            f = fa + (db - fa) * s
        eyeh = m.vh + (m.dvh - m.vh) * f
        v = self.view_new(T)
        if v is not None:
            src = 1
            p, y = v[0], v[1]
        else:
            src = 0
            if b is None:
                p, y = a.pit, wrap(a.yaw)
            elif fit == INTERP_SNAP or abs(arc(a.pit, b.pit)) > WT_ASNAP or \
                    abs(arc(a.yaw, b.yaw)) > WT_ASNAP:
                h = a if s < 0.5 else b
                p, y = wrap(h.pit), wrap(h.yaw)
            else:
                p = wrap(a.pit + arc(a.pit, b.pit) * s)
                y = wrap(a.yaw + arc(a.yaw, b.yaw) * s)
        return (T, org[0], org[1], org[2] + eyeh, p, y, src, fit, eyeh)

    # 378's Watch_ViewBlock pick
    def view_old(self, T):
        m = self.m
        vl = m.vlines
        if not hasattr(self, 'vxl'):
            self._old_index()
        tick = T / m.tickrate
        if tick < 0:
            tick = 0
        ti = math.floor(tick)
        jline = m.view0
        for q in range(len(self.vxl)):
            if self.vxt[q] <= ti:
                jline = self.vxl[q]
        n = len(vl)
        i = jline
        while i < n:
            if is_sample(vl[i]) and stof(vl[i].split()[2]) >= ti:
                break
            i += 1
        if i >= n:
            i = n - 1
        b0 = i
        tk = stof(vl[i].split()[2])
        jj = i + 1
        while jj < n:
            if not is_sample(vl[jj]) or stof(vl[jj].split()[2]) != tk:
                break
            jj += 1
        k = max(1, jj - b0)
        pick = b0 + math.floor((tick - math.floor(tick)) * k)
        if pick >= jj:
            pick = jj - 1
        if pick < m.view0:
            pick = m.view0
        tok = vl[pick].split()
        return stof(tok[3]), stof(tok[4])

    def _old_index(self):
        m = self.m
        vl = m.vlines
        n = len(vl) - m.view0
        step = max(1, math.ceil(n / 511))
        self.vxl, self.vxt = [], []
        nextix = m.view0
        for i in range(m.view0, len(vl)):
            if not is_sample(vl[i]):
                if i == nextix:
                    nextix = i + 1
                continue
            if i != nextix:
                continue
            nextix = i + step
            if len(self.vxl) >= 512:
                break
            self.vxl.append(i)
            self.vxt.append(stof(vl[i].split()[2]))


def wtr_line(r):
    return "wtr %.6f %.3f %.3f %.3f %.3f %.3f %d %d %.3f" % r


# ---- the analyser ---------------------------------------------------------

MARK = re.compile(r'(?:^|\s)(wtrb|wtre|wtr|wtfb|wtfe|wtf)\s(.*)$')


def parse_log(path):
    """[(kind, header tokens, [row tokens])] for every wtr / wtf block."""
    blocks = []
    cur = None
    with open(path, 'r', errors='replace') as f:
        for line in f:
            mm = MARK.search(line.rstrip('\r\n'))
            if not mm:
                continue
            tag, rest = mm.group(1), mm.group(2).split()
            if tag in ('wtrb', 'wtfb'):
                cur = [tag[:3], rest, []]
                blocks.append(cur)
            elif tag in ('wtre', 'wtfe'):
                cur = None
            elif cur is not None and tag == cur[0]:
                try:
                    cur[2].append([float(x) for x in rest])
                except ValueError:
                    pass
    return blocks


class RecRef(object):
    """The .rec quantities the predictions are measured against."""

    def __init__(self, m):
        self.m = m
        self.s = m.samples
        self.ts = m.ts
        self.sim = None
        self.snaps = None

    def at(self, T):
        i = bisect.bisect_right(self.ts, T) - 1
        if i < 0:
            i = 0
        j = min(i + 1, len(self.s) - 1)
        return self.s[i], self.s[j]

    def yawrate(self, T):
        a, b = self.at(T)
        if b.t <= a.t:
            return 0.0
        return abs(arc(a.yaw, b.yaw)) / (b.t - a.t)

    def yawrate_hold(self, T):
        a, b = self.at(T)
        if b.t <= a.t or abs(arc(a.yaw, b.yaw)) > WT_ASNAP:
            return None
        return abs(arc(a.yaw, b.yaw)) / (b.t - a.t)

    def vrate(self, T):
        if self.sim is None:
            self.sim = Sim(self.m, True)
        return self.sim.view_rate(T)

    def rate_at(self, T, view):
        """P1's reference yaw rate: the .view pair's on the 379 map where it
        covers T, else the .rec pair's; None at a >45 degree hold."""
        if view and T >= 0:
            r = self.vrate(T)
            if r is not None:
                return r
        return self.yawrate_hold(T)

    def vel(self, T):
        a, b = self.at(T)
        s = 0.0 if b.t <= a.t else min(1, max(0, (T - a.t) / (b.t - a.t)))
        return tuple(a.v[k] + (b.v[k] - a.v[k]) * s for k in range(3))

    def near_snap(self, T):
        """Within 50 ms of a snap interval: a teleport sets the view angles, and
        the .view shows it a frame or two after the .rec does."""
        if self.snaps is None:
            self.snaps = []
            for k, x in enumerate(self.s[:-1]):
                if self.m.ivfit.get(x.t) == INTERP_SNAP:
                    self.snaps.append((x.t - 0.05, self.s[k + 1].t + 0.05))
        for a, b in self.snaps:
            if a <= T <= b:
                return True
        return False

    def snap_iv(self, T):
        a, b = self.at(T)
        return a.t if self.m.ivfit.get(a.t) == INTERP_SNAP else None


def analyse_wtr(rows, ref, dtn, view):
    """Metrics of one synthetic block.  rows: T ex ey ez pit yaw src fit eyeh.

    P1's reference rate is the source's own: the .view line pair's rate on the
    379 time map in a view block (where T >= 0 and a knot covers it), else the
    .rec sample pair's.  A frame that straddles a sample takes the larger of
    its two ends' rates, so piecewise-linear yaw scores R <= 1.
    P3 is z'' over steps of about 3 ms: over 1 ms steps the float32 feet (ulp
    0.001 to 0.002 u) alone reach 2.5 g.  A lerp's kink then reads tick/h."""
    out = {}
    m = ref.m
    g = m.gravity
    R = []
    zero = 0
    nturn = 0
    anom = {}
    stray = 0
    curv = []
    zmove = 0
    kh = max(1, int(round(0.003 / dtn))) if dtn > 0 else 1

    def yrate(T):
        return ref.rate_at(T, view)

    for i in range(1, len(rows)):
        p, q = rows[i - 1], rows[i]
        dT = q[0] - p[0]
        if dT <= 0:
            continue
        a, b = ref.at(q[0])
        pa, pb = ref.at(p[0])
        snap = ref.snap_iv(q[0])
        psnap = ref.snap_iv(p[0])
        ra, rb = yrate(p[0]), yrate(q[0])
        dy = abs(arc(p[5], q[5]))
        if ra is not None and rb is not None and dy < WT_ASNAP and                 not ref.near_snap(p[0]) and not ref.near_snap(q[0]):
            rate = max(ra, rb)
            if min(ra, rb) > 100:
                nturn += 1
                R.append(dy / (rate * dT))
                if dy < 1e-4:
                    zero += 1
        v = ref.vel(q[0])
        fp = (p[1], p[2], p[3] - p[8])
        fq = (q[1], q[2], q[3] - q[8])
        res = math.sqrt(sum((fq[k] - fp[k] - v[k] * dT) ** 2 for k in range(3)))
        # a snap is crossed by the frame whose bracket interval is the snap's
        if snap is not None or (pa.t != a.t and psnap is not None):
            key = snap if snap is not None else pa.t
            if res > 8:
                anom[key] = anom.get(key, 0) + 1
            else:
                anom.setdefault(key, 0)
        elif res > 8 and (a.fl & F_DUCKED) == (pa.fl & F_DUCKED):
            stray += 1
        spd = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
        if spd > 100 and fp == fq and snap is None:
            zmove += 1
        if i >= 2 * kh:
            o = rows[i - 2 * kh]
            p2 = rows[i - kh]
            ok = True
            for r in rows[i - 2 * kh:i + 1]:
                aa, bb = ref.at(r[0])
                if r[7] != INTERP_HERMITE or (aa.fl | bb.fl) & (F_ONGROUND | F_RAMP) \
                        or (aa.fl & F_DUCKED) != (bb.fl & F_DUCKED):
                    ok = False
                    break
            h1 = p2[0] - o[0]
            h2 = q[0] - p2[0]
            if ok and h1 > 0 and h2 > 0:
                # z'' on uneven spacing: float32 T at 100 s moves 7.6 us a frame
                z0, z1, z2 = o[3] - o[8], p2[3] - p2[8], q[3] - q[8]
                zdd = 2 * ((z2 - z1) / h2 - (z1 - z0) / h1) / (h1 + h2)
                curv.append(abs(zdd) / g)
    out['turn_frames'] = nturn
    out['R'] = max(R) if R else None
    out['zero'] = (zero / nturn) if nturn else None
    out['snaps'] = anom
    out['stray'] = stray
    out['curv'] = max(curv) if curv else None
    out['zmove'] = zmove
    return out


def unduck_metric(rows, ref):
    """P4 over the ground unducks inside a block: max per-frame eye change and
    the RMS against the S-curve anchored on the hull-fall sample."""
    m = ref.m
    res = []
    for (t, pt) in m.unducks:
        sel = [r for r in rows if t - 0.3 <= r[0] <= t + 0.05]
        if len(sel) < 3:
            continue
        mx = max(abs(sel[k][8] - sel[k - 1][8]) for k in range(1, len(sel)))
        se = 0.0
        for r in sel:
            if r[0] >= t:
                ideal = m.vh
            elif r[0] <= t - WT_UNDUCK_T:
                ideal = m.dvh
            else:
                f = smooth(1 - (r[0] - (t - WT_UNDUCK_T)) / WT_UNDUCK_T)
                ideal = m.vh + (m.dvh - m.vh) * f
            se += (r[8] - ideal) ** 2
        res.append((t, mx, math.sqrt(se / len(sel))))
    return res


def airduck_metric(rows, ref):
    """P5: over each air duck in the block, the head's rise against the
    recorded vertical velocity, and its largest one-frame drop."""
    res = []
    for (ta, tb) in ref.m.airducks:
        sel = [r for r in rows if ta - 0.005 <= r[0] <= tb + 0.02]
        if len(sel) < 3:
            continue
        rise = 0.0
        drop = 0.0
        total = 0.0
        for k in range(1, len(sel)):
            p, q = sel[k - 1], sel[k]
            dT = q[0] - p[0]
            vz = ref.vel(q[0])[2]
            r = (q[3] - p[3]) - vz * dT
            total += r
            if r > 0:
                rise += r
            drop = max(drop, -r)
        res.append((ta, tb, rise, drop, total))
    return res


def bias_metric(rows, ref):
    """P6: when the drawn yaw passes each fast-turning .rec sample's yaw,
    relative to that sample's t (ms)."""
    out = []
    for s in ref.s:
        if s.t < rows[0][0] + 0.02 or s.t > rows[-1][0] - 0.02:
            continue
        if ref.yawrate(s.t) < 200:
            continue
        best = None
        for k in range(1, len(rows)):
            p, q = rows[k - 1], rows[k]
            if abs(q[0] - s.t) > 0.02:
                continue
            da = arc(p[5], s.yaw)
            db = arc(q[5], s.yaw)
            if da == 0 or (da > 0) != (db > 0) or db == 0:
                step = arc(p[5], q[5])
                if step == 0:
                    continue
                T = p[0] + (q[0] - p[0]) * (da / step)
                if best is None or abs(T - s.t) < abs(best - s.t):
                    best = T
        if best is not None:
            out.append((best - s.t) * 1000)
    return out


def median(x):
    x = sorted(x)
    if not x:
        return None
    n = len(x)
    return x[n // 2] if n % 2 else 0.5 * (x[n // 2 - 1] + x[n // 2])


def resolve(p, gamedir):
    for base in (gamedir, '.', os.path.join('ftesurf')):
        q = os.path.join(base, p)
        if os.path.exists(q):
            return q
    return p


def analyse(log, gamedir):
    blocks = parse_log(log)
    models = {}
    ok = True
    for kind, head, rows in blocks:
        if not rows:
            continue
        path = head[-1] if head else ''
        noview = False
        if kind == 'wtr':
            # wtrb n dt T0 view path
            view = int(float(head[3]))
            noview = not view
        key = (path, noview)
        if key not in models:
            models[key] = model(resolve(path, gamedir), noview)
        m = models[key]
        ref = RecRef(m)
        if kind == 'wtr':
            dtn = float(head[1])
            a = analyse_wtr(rows, ref, dtn, not noview)
            label = "wtr %s T0 %s dt %s %s" % (os.path.basename(path), head[2],
                                               head[1], 'view' if view else 'noview')
            print(label)
            if a['turn_frames']:
                print("   P1 yaw   %4d turn frames  R %.2f  zero-step %.3f" %
                      (a['turn_frames'], a['R'], a['zero']))
            for ta, n in sorted(a['snaps'].items()):
                k = ref.ts.index(ta)
                sa, sb = ref.s[k], ref.s[min(k + 1, len(ref.s) - 1)]
                r = fit_resid(sa.o, sa.v, sb.o, sb.v, sb.t - sa.t)
                print("   P2 snap  %.4f  %d jump frame(s)  (jump %.1f u; want %s)" %
                      (ta, n, r, '1' if r > 16 else '0 or 1'))
            if a['stray']:
                print("   P2 stray %d frame(s) off the recorded velocity outside "
                      "any snap" % a['stray'])
            if a['curv'] is not None:
                print("   P3 curv  %.2f  (|d2z| / g dt^2, Hermite air)" % a['curv'])
            for t, mx, rms in unduck_metric(rows, ref):
                print("   P4 unduck %.4f  max step %.3f u  S-curve rms %.3f u" %
                      (t, mx, rms))
            for ta, tb, rise, drop, total in airduck_metric(rows, ref):
                print("   P5 airduck %.4f..%.4f  rise %.2f  max drop %.2f  net %.2f" %
                      (ta, tb, rise, drop, total))
            b = bias_metric(rows, ref)
            if len(b) >= 5 and view:
                print("   P6 bias  median %.2f ms over %d sample(s)" %
                      (median(b), len(b)))
            if a['zmove']:
                print("   P7 %d still frame(s) at speed" % a['zmove'])
            if len(rows) == 1:
                r = rows[0]
                s = None
                for x in m.samples:
                    if abs(x.t - r[0]) < 1e-5:
                        s = x
                if s is not None:
                    d = math.sqrt((r[1] - s.o[0]) ** 2 + (r[2] - s.o[1]) ** 2 +
                                  (r[3] - r[8] - s.o[2]) ** 2)
                    da = max(abs(arc(r[4], s.pit)), abs(arc(r[5], s.yaw)))
                    print("   P9 exact sample: origin off %.3f u  angles off %.3f deg%s" %
                          (d, da, '' if noview else ' (view: angles are the .view\'s)'))
        else:
            # wtfb n view path ; wtf dtcl dtfr T ez yaw turnrate rate paused
            r = []
            for k in range(1, len(rows)):
                p, q = rows[k - 1], rows[k]
                if len(q) < 8 or q[7] or q[6] <= 0 or q[1] <= 0:
                    continue
                dT = q[2] - p[2]
                if dT <= 0:
                    continue
                r.append((dT / q[6]) / q[1])
            label = "wtf %s  %d frame(s)" % (os.path.basename(path), len(rows))
            print(label)
            if r:
                mu = sum(r) / len(r)
                sd = math.sqrt(sum((x - mu) ** 2 for x in r) / len(r))
                print("   P8 clock (dT/rate)/clframetime mean %.4f  cv %.4f" %
                      (mu, sd / mu if mu else 0))
            dcl = [q[0] for q in rows if q[0] > 0]
            dfr = [q[1] for q in rows if q[1] > 0]
            if dcl and dfr:
                print("   dtcl mean %.3f ms  dtfr mean %.3f ms" %
                      (1000 * sum(dcl) / len(dcl), 1000 * sum(dfr) / len(dfr)))
            view = int(float(head[1])) if len(head) >= 3 else 0
            ys = []
            for k in range(1, len(rows)):
                p, q = rows[k - 1], rows[k]
                dT = q[2] - p[2]
                if dT <= 0 or len(q) < 8 or q[7]:
                    continue
                ra = ref.rate_at(p[2], view)
                rb = ref.rate_at(q[2], view)
                dy = abs(arc(p[4], q[4]))
                if ra is None or rb is None or dy >= WT_ASNAP or                         ref.near_snap(p[2]) or ref.near_snap(q[2]):
                    continue
                if min(ra, rb) > 100:
                    ys.append((dy / (max(ra, rb) * dT), dy < 1e-4))
            if ys:
                print("   P1 yaw   %4d turn frames  R %.2f  zero-step %.3f  (%s)" %
                      (len(ys), max(x[0] for x in ys),
                       sum(1 for x in ys if x[1]) / len(ys),
                       'view' if view else 'noview'))
    return 0 if ok else 1


# ---- status comparison -----------------------------------------------------

def compare(log, new, gamedir):
    """Every wtr line in LOG against the simulator's (new = 379, old = 378).
    Differences past float32 noise are SUSPECT: one of the two is wrong."""
    tol = (0.05, 0.1, 0.02)             # feet u, angle deg, eye height u
    models = {}
    worst = [0.0, 0.0, 0.0]
    bad = 0
    n = 0
    for kind, head, rows in parse_log(log):
        if kind != 'wtr' or not rows:
            continue
        path = head[-1]
        nv = not int(float(head[3]))
        key = (path, nv)
        if key not in models:
            models[key] = Sim(model(resolve(path, gamedir), nv), new)
        sim = models[key]
        ts = sim.m.ts
        for r in rows:
            # a frame on a sample's t is decided by one float32 ulp either way
            k = bisect.bisect_left(ts, r[0])
            if any(abs(ts[j] - r[0]) < 1e-5 for j in (k - 1, k) if 0 <= j < len(ts)):
                continue
            e = sim.frame(f32(r[0]))
            n += 1
            # the printed T is good to 0.5 us: allow the pair's chord speed for it
            a = sim.m.samples[max(0, k - 1)]
            b = sim.m.samples[min(k, len(ts) - 1)]
            sp = 0.0 if b.t <= a.t else \
                math.sqrt(sum((b.o[j] - a.o[j]) ** 2 for j in range(3))) / (b.t - a.t)
            d = (math.sqrt((r[1] - e[1]) ** 2 + (r[2] - e[2]) ** 2 +
                           ((r[3] - r[8]) - (e[3] - e[8])) ** 2),
                 max(abs(arc(r[4], e[4])), abs(arc(r[5], e[5]))),
                 abs(r[8] - e[8]))
            for k in range(3):
                worst[k] = max(worst[k], d[k])
            if d[0] > tol[0] + sp * 2e-6 or d[1] > tol[1] or d[2] > tol[2] or \
                    r[6] != e[6] or r[7] != e[7]:
                bad += 1
                if bad <= 20:
                    print("SUSPECT %s T %.6f  game %s\n%s  sim  %s" %
                          (os.path.basename(path), r[0],
                           ' '.join('%g' % x for x in r[1:]), ' ' * 18,
                           ' '.join('%g' % x for x in e[1:])))
    print("%s  %d frame(s), %d past tolerance; worst feet %.3f u  angle %.3f deg  "
          "eye %.3f u" % ('MATCH' if not bad else 'SUSPECT', n, bad,
                          worst[0], worst[1], worst[2]))
    return 1 if bad else 0


def check(m, log):
    want = status_lines(m)
    got = []
    blk = None
    name = m.path.replace('\\', '/')
    with open(log, 'r', errors='replace') as f:
        for line in f:
            line = line.rstrip('\r\n')
            mm = re.search(r'replay: (\S+\.rec)$', line)
            if mm:
                blk = [] if name.endswith(mm.group(1)) else None
                if blk is not None:
                    got.append(blk)
                continue
            if blk is None:
                continue
            for w in ('  fit ', '  duck ', '  view '):
                k = line.find(w)
                if k >= 0 and (w != '  view ' or 'span' in line or 'none' in line):
                    blk.append(line[k:])
    if not got:
        print("check: no `replay status` block for %s in %s" % (name, log))
        return 2
    m.vlines, keep = None, m.vlines
    want_nv = status_lines(m)
    m.vlines = keep
    bad = 0
    for n, blk in enumerate(got):
        if not blk:
            continue
        nv = any(x.startswith('view none') or x.strip() == 'view none' for x in blk)
        for w in (want_nv if nv else want):
            head = w.split()[0]
            g = [x for x in blk if x.split()[0] == head]
            if not g:
                continue
            if g[0] != w:
                bad += 1
                print("SUSPECT block %d\n  model: %s\n  game:  %s" % (n, w, g[0]))
    if not bad:
        print("MATCH  %d status block(s) agree with the model" % len(got))
    return 1 if bad else 0


def windows(m):
    print("snap intervals (ta tb kind):")
    for ta, k in zip(m.snt, m.snk):
        i = m.ts.index(ta)
        tb = m.ts[i + 1] if i + 1 < len(m.ts) else ta
        print("  %.4f %.4f %s" % (ta, tb, 'rec' if k == 1 else 'kin'))
    print("ground unducks (hull-fall t):")
    for t, pt in m.unducks:
        print("  %.4f" % t)
    print("air ducks (ta tb):")
    for ta, tb in m.airducks:
        print("  %.4f %.4f" % (ta, tb))
    print("duck slides (ts te u0 rate):")
    for k in range(len(m.dks)):
        print("  %.4f %.4f %.3f %.3f" % (m.dks[k], m.dke[k], m.dku[k], m.dkr[k]))


def main():
    a = sys.argv[1:]

    def opt(name, default=None):
        if name in a:
            k = a.index(name)
            if k + 1 < len(a):
                return a[k + 1]
        return default

    noview = '--noview' in a
    gamedir = opt('--gamedir', 'ftesurf')
    if '--model' in a:
        m = model(opt('--model'), noview)
        if '--check' in a:
            return check(m, opt('--check'))
        print("replay: %s" % m.path)
        for s in status_lines(m):
            print(s)
        return 0
    if '--windows' in a:
        windows(model(opt('--windows'), noview))
        return 0
    if '--sim' in a:
        k = a.index('--sim')
        which, path = a[k + 1], a[k + 2]
        m = model(path, noview)
        sim = Sim(m, which == 'new')
        T0 = float(opt('--at', '0'))
        n = int(opt('--n', '1'))
        dt = float(opt('--dt', '0.004'))
        print("wtrb %d %g %.5f %d %s" % (n, dt, T0, 0 if noview else 1,
                                       opt('--name', path)))
        for i in range(n):
            print(wtr_line(sim.frame(T0 + i * dt)))
        print("wtre")
        return 0
    if '--analyse' in a:
        return analyse(opt('--analyse'), gamedir)
    if '--compare' in a:
        k = a.index('--compare')
        return compare(a[k + 2], a[k + 1] == 'new', gamedir)
    if '--corpus' in a:
        root = opt('--corpus')
        for dp, _, names in os.walk(root):
            for n in sorted(names):
                if n.endswith('.rec'):
                    p = os.path.join(dp, n)
                    m = model(p, noview)
                    print(os.path.relpath(p, root).replace('\\', '/'))
                    for s in status_lines(m):
                        print(s)
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main())
