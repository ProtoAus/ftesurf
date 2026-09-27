"""p453q.py -- grade Patch 453's air-control colouring against the .rec.

The client prints ln_q itself (the grade the colour is drawn from) for every
nth point, plus the movement settings it measured against.  This reimplements
sh_strafe.qc's closed forms and the strafe bar's regime choice from the
documented rules, and compares sample by sample.

WHAT IT CANNOT CHECK, said plainly: the movement settings come from the client,
because the .rec does not carry them (a v9 `pmpin` block would, and a later
patch could read it).  So this grades the ARITHMETIC and the REGIME CHOICE --
which is where a wrong answer would be plausible rather than obvious -- and not
whether the right cvars were read.

  python tools/p453q.py [ftesurf/logs/p453q.log]
"""
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p449mark                                     # noqa: E402

DEG = 180.0 / math.pi
PM_STANDABLE = 0.7                                   # sh_defs.qc:56
PM_NONJUMP_VEL = 140                                 # sh_defs.qc:57
F_DUCKED = 2


# --- sh_strafe.qc, ported ----------------------------------------------------

def air_gain(airaccel, wishspeed, tick, friction, aircap):
    return min(airaccel * wishspeed * tick * friction, aircap)


def cap_binds(airaccel, maxspeed, tick, friction, aircap):
    return (airaccel * maxspeed * tick * friction) >= aircap


def ideal_turn(speed, gain, tick):
    speed = max(speed, 1)
    tick = tick if tick >= 0.0001 else 0.015
    return (math.atan2(gain, speed) * DEG) / tick


def after_friction(speed, fric, stopspeed, tick):
    if speed <= 0:
        return 0
    drop = (stopspeed if speed < stopspeed else speed) * fric * tick
    return 0 if drop >= speed else speed - drop


def ground_gain(accel, wishspeed, tick, friction):
    return accel * tick * wishspeed * friction


def ideal_turn_ground(speed, gain, wishspeed, tick):
    if speed < 1:
        return 0
    tick = tick if tick >= 0.0001 else 0.015
    c = 1.0 if speed < 1 else max(-1.0, min(1.0, (wishspeed - gain) / speed))
    s = 1 - c * c
    s = math.sqrt(s) if s > 0 else 0
    return (math.atan2(gain * s, speed + gain * c) * DEG) / tick


def ideal_turn_plane(speed, tick, gain, gravity, nz, wn):
    speed = max(speed, 1)
    tick = tick if tick >= 0.0001 else 0.015
    wn = max(-1.0, min(1.0, wn))
    rot = gain * (1 - wn * wn) + (gravity * tick) * nz * wn
    if rot <= 0:
        return 0
    return (math.atan2(rot, speed) * DEG) / tick


def cscale(gravity, tick, nz, wn, aircap):
    tick = tick if tick >= 0.0001 else 0.015
    wn = max(-1.0, min(1.0, wn))
    denom = 1 - wn * wn
    if denom < 0.05:
        return aircap
    s = aircap + (gravity * tick) * nz * wn / denom
    return max(aircap * 0.5, min(aircap * 4.0, s))


def quality(turn, ideal, cs, aircap):
    if ideal <= 0.001 or turn < 0:
        return -1
    if cs <= 0.001:
        cs = aircap
    m = (1 - turn / ideal) * (cs / aircap)
    return max(0.0, min(1.0, 1 - m * m))


# --- the file ----------------------------------------------------------------

def wishdir(yaw, fwdmove, sidemove):
    """Watch_WishOf: forward and side against the yaw, flattened then normalised."""
    if fwdmove == 0 and sidemove == 0:
        return (0.0, 0.0, 0.0)
    a = yaw / DEG
    f = (math.cos(a), math.sin(a), 0.0)
    r = (math.sin(a), -math.cos(a), 0.0)          # makevectors' right is -y
    w = (f[0] * fwdmove + r[0] * sidemove, f[1] * fwdmove + r[1] * sidemove, 0.0)
    n = math.hypot(w[0], w[1])
    return (0.0, 0.0, 0.0) if n < 0.001 else (w[0] / n, w[1] / n, 0.0)


def samples(recpath):
    out, body = [], False
    for line in open(recpath, "r", errors="replace"):
        if not body:
            if line.startswith("begin"):
                body = True
            continue
        if line[:1].isdigit() or line[:1] == "-":
            f = line.split()
            nrm = ((float(f[14]), float(f[15]), float(f[16]))
                   if len(f) > 16 else (0.0, 0.0, 0.0))
            out.append({"t": p449mark.f32(float(f[0])),
                        "v": (float(f[4]), float(f[5]), float(f[6])),
                        "yaw": float(f[8]), "fl": int(float(f[9])),
                        "mv": (float(f[11]), float(f[12])), "n": nrm})
    return out


def grades(rows, mv):
    """The grade of every sample, and the ground-phase gate that goes with it."""
    out, pyaw, pt, gsince, pkind = [], 0.0, 0.0, 0.0, -1
    ron, rlast = False, 0.0
    for i, r in enumerate(rows):
        t, v, fl = r["t"], r["v"], r["fl"]
        # the contact kind, for the ground-phase clock only
        raw = fl & p449mark.F_RAMP
        held = bool(raw) or (ron and rlast > 0 and t >= rlast
                             and p449mark.f32(t - rlast) <= p449mark.f32(0.08))
        if raw:
            rlast = t
        ron = held
        kind = 0 if (fl & p449mark.F_ONGROUND) else (2 if held else 1)

        dt = t - pt
        if i < 1 or dt <= 0:
            q = -1
        else:
            turn = r["yaw"] - pyaw
            while turn > 180:
                turn -= 360
            while turn < -180:
                turn += 360
            turn = abs(turn) / dt
            speed = math.hypot(v[0], v[1])
            ong = bool(fl & p449mark.F_ONGROUND)
            if ong and mv["ghold"] > 0 and (t - gsince) < mv["ghold"]:
                ong = False
            ws = mv["maxspeed"]
            if ong and (fl & F_DUCKED) and mv["duck"] > 0:
                ws = mv["maxspeed"] * mv["duck"]
            fric = 0.25 if (not ong and 0 < v[2] <= PM_NONJUMP_VEL) else 1.0
            cs = mv["aircap"]
            if ong:
                g = ground_gain(mv["accel"], ws, mv["tick"], fric)
                vf = after_friction(speed, mv["gfric"], mv["stopspeed"], mv["tick"])
                ideal = ideal_turn_ground(vf, g, ws, mv["tick"])
                q = -1 if ideal <= 10 else quality(turn, ideal, cs, mv["aircap"])
            elif not cap_binds(mv["airaccel"], mv["maxspeed"], mv["tick"], fric,
                               mv["aircap"]):
                q = -1
            else:
                g = air_gain(mv["airaccel"], ws, mv["tick"], fric, mv["aircap"])
                w = wishdir(r["yaw"], r["mv"][0], r["mv"][1])
                nz = r["n"][2]
                wn = sum(w[k] * r["n"][k] for k in range(3))
                if 0.05 <= nz <= PM_STANDABLE and wn != 0:
                    ideal = ideal_turn_plane(speed, mv["tick"], g, mv["gravity"],
                                             nz, wn)
                    cs = cscale(mv["gravity"], mv["tick"], nz, wn, mv["aircap"])
                    q = -1 if ideal <= 0.001 else quality(turn, ideal, cs,
                                                          mv["aircap"])
                else:
                    ideal = ideal_turn(speed, g, mv["tick"])
                    q = quality(turn, ideal, cs, mv["aircap"])
        out.append(q)
        if kind == 0 and pkind != 0:
            gsince = t
        pkind, pyaw, pt = kind, r["yaw"], t
    return out


def main():
    log = sys.argv[1] if len(sys.argv) > 1 else "ftesurf/logs/p453q.log"
    mv, pts, recpath, n_client = {}, [], None, 0
    for raw in open(log, "r", errors="replace"):
        line = re.sub(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ", "", raw.rstrip("\n"))
        f = line.split()
        if line.startswith("lnmv ") and len(f) >= 7:
            mv.update(tick=float(f[1]), airaccel=float(f[2]), accel=float(f[3]),
                      maxspeed=float(f[4]), aircap=float(f[5]), gravity=float(f[6]))
        elif line.startswith("lnmv2 ") and len(f) >= 5:
            mv.update(gfric=float(f[1]), stopspeed=float(f[2]), duck=float(f[3]),
                      ghold=float(f[4]))
        elif line.startswith("lncb ") and len(f) >= 5 and int(float(f[2])) == 4:
            n_client = int(float(f[3]))
            pts = []
        elif line.startswith("lnc ") and len(f) >= 7:
            pts.append((int(float(f[1])), float(f[2]), float(f[6])))
        elif line.startswith("lnmb ") and len(f) >= 8:
            recpath = f[7]
    if not pts or not mv or not recpath:
        print("FAIL nothing to grade: %d points, %d settings, rec %s"
              % (len(pts), len(mv), recpath))
        return 1

    rows = samples("ftesurf/" + recpath)
    want = grades(rows, mv)
    bad, graded, nograde = [], 0, 0
    for i, t, q in pts:
        if i >= len(want):
            continue
        graded += 1
        if q < 0 or want[i] < 0:
            if (q < 0) != (want[i] < 0):
                bad.append("point %d: client %.4f, file %.4f (one says no answer)"
                           % (i, q, want[i]))
            else:
                nograde += 1
            continue
        if abs(q - want[i]) > 0.01:
            bad.append("point %d: client %.4f, file %.4f" % (i, q, want[i]))

    ok = graded > 20 and not bad
    print("%s Q1  %d points graded, %d agreed, %d 'no answer' both ways, %d wrong%s"
          % ("PASS" if ok else "FAIL", graded, graded - nograde - len(bad),
             nograde, len(bad), "  " + bad[0] if bad else ""))
    for b in bad[1:4]:
        print("        %s" % b)
    # A grade that is -1 everywhere would agree with a model that is -1
    # everywhere: say how much of the line actually carries a number.
    live = sum(1 for _, _, q in pts if q >= 0)
    ok2 = live >= 10
    print("%s Q2  %d of %d sampled points carry a grade (the rest are grey)"
          % ("PASS" if ok2 else "FAIL", live, len(pts)))
    print("%d check(s), %d failed" % (2, (0 if ok else 1) + (0 if ok2 else 1)))
    return 0 if (ok and ok2) else 1


if __name__ == "__main__":
    sys.exit(main())
