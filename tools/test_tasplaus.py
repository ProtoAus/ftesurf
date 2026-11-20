#!/usr/bin/env python3
"""Falsifiers for tasplaus.py: a simulated legal run passes; each edit a cheater would make is caught.

The real-run side (no false HOLD on honest runs) needs recordings: set TASPLAUS_CORPUS to a
directory of .rec files and TASPLAUS_ZONES to their map's zone JSON. 20 Nov 2026: 117 KSF +
Momentum replays of surf_sandtrap2 bonus 4, 117 PASS.
"""
import glob
import json
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tasplaus as tp  # noqa: E402

RATE = 0.015


def box(x0, x1, y0, y1, bottom, height):
    return {"points": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], "bottom": bottom, "height": height}


def zones_for(rows):
    """Start box ends where the clock starts (t=0); the end box begins where the run is at t=1.2."""
    x0 = next(o for t, o, v in rows if t >= 0)[0]
    xe = next(o for t, o, v in rows if t >= 1.2)[0]
    return {"maxVelocity": 3500, "tracks": {"main": {"zones": {
        "segments": [{"limitStartGroundSpeed": True, "checkpoints": [{"regions": [
            box(x0 - 300, x0 + 1, -200, 200, -8, 200)]}]}],
        "end": {"regions": [box(xe, xe + 2000, -3000, 3000, -5000, 10000)]}}}}}


def simulate():
    """Ground prestrafe from rest, jump at the zone edge, then air-strafe on the 30 u/s cap."""
    o = [0.0, 0.0, 0.0]
    v = [0.0, 0.0, 0.0]
    rows = []
    t = -0.6
    tick = 0
    jumped = False
    finish = None
    while t < 1.6:
        rows.append((t, list(o), list(v)))
        if finish is None and t >= 1.2:
            finish = round(t / RATE)
        vo = list(v)
        h = math.hypot(v[0], v[1])
        if not jumped and t >= -0.105:
            v[2] = 289.99
            jumped = True
        elif not jumped:
            nh = min(250.0, h + 18.0)
            v[0], v[1] = nh, 0.0
        else:
            # wishdir with v.w = 2: |v'|^2 = |v|^2 + 900 - 4, just under the cap
            side = 1 if tick % 40 < 20 else -1
            ang = math.atan2(v[1], v[0]) + side * math.acos(2.0 / max(h, 2.0))
            wx, wy = math.cos(ang), math.sin(ang)
            vw = v[0] * wx + v[1] * wy
            add = 30.0 - vw
            v[0] += add * wx
            v[1] += add * wy
            v[2] -= 800.0 * RATE
        for i in range(3):
            o[i] += (vo[i] + v[i]) * 0.5 * RATE if jumped else v[i] * RATE
        t = round(t + RATE, 6)
        tick += 1
    return rows, finish


def text(rows, finish, rate=RATE, extra=""):
    out = ["FTESURF-REC 5", "map synth", "track 0", f"tickrate {rate}", f"movetickrate {rate}", extra, "begin"]
    for t, o, v in rows:
        out.append(f"{t:.4f} {o[0]:.6f} {o[1]:.6f} {o[2]:.6f} {v[0]:.6f} {v[1]:.6f} {v[2]:.6f} 0 0 0 0 0 0 0 0 0 0")
    out.append(f"end {finish} {len(rows)} 0 0")
    return "\n".join(out) + "\n"


ZONES = zones_for(simulate()[0])


def verdict(rows, finish, zones=ZONES, **kw):
    return tp.check(tp.read(text=text(rows, finish, **kw)), zones)


class Synthetic(unittest.TestCase):
    def setUp(self):
        self.rows, self.fin = simulate()
        self.assertIsNotNone(self.fin)
        self.i0 = next(i for i, r in enumerate(self.rows) if r[0] >= 0.3)

    def reasons(self, r):
        return " | ".join(x["what"] for x in r["reasons"])

    def test_clean_passes(self):
        r = verdict(self.rows, self.fin)
        self.assertEqual(r["verdict"], "PASS", self.reasons(r))
        self.assertGreater(r["stats"]["worst_air_ratio"], 0.95)   # the control works the cap
        self.assertEqual(r["stats"]["jumps"], 1)

    def test_speed_edit(self):
        rows = [(t, list(o), list(v)) for t, o, v in self.rows]
        for j in range(self.i0, len(rows)):
            rows[j][2][0] *= 1.05
            rows[j][2][1] *= 1.05
        for j in range(self.i0 + 1, len(rows)):   # positions follow the edited speed
            dt = rows[j][0] - rows[j - 1][0]
            for c in range(3):
                rows[j][1][c] = rows[j - 1][1][c] + (rows[j - 1][2][c] + rows[j][2][c]) * 0.5 * dt
        r = verdict(rows, self.fin)
        self.assertEqual(r["verdict"], "HOLD")
        self.assertIn("energy", self.reasons(r))

    def test_slow_speedhack(self):
        rows = [(t, list(o), list(v)) for t, o, v in self.rows]
        for j in range(self.i0, len(rows)):
            f = 1.0 + 0.004 * (j - self.i0 + 1)
            rows[j][2][0] = self.rows[j][2][0] * f
            rows[j][2][1] = self.rows[j][2][1] * f
        for j in range(self.i0 + 1, len(rows)):
            dt = rows[j][0] - rows[j - 1][0]
            for c in range(3):
                rows[j][1][c] = rows[j - 1][1][c] + (rows[j - 1][2][c] + rows[j][2][c]) * 0.5 * dt
        r = verdict(rows, self.fin)
        self.assertEqual(r["verdict"], "HOLD", self.reasons(r))
        self.assertIn("energy", self.reasons(r))

    def test_deleted_tick(self):
        k = self.i0 + 5
        rows = self.rows[:k] + [(round(t - RATE, 6), o, v) for t, o, v in self.rows[k + 1:]]
        r = verdict(rows, self.fin - 1)
        self.assertEqual(r["verdict"], "HOLD")
        self.assertRegex(self.reasons(r), "ticks of gravity|missing or edited")

    def test_deleted_tick_with_speed_fixed_up(self):
        # vz edited back to a one-tick gravity drop, so only the free-flight position test sees it
        k = self.i0 + 5
        rows = self.rows[:k] + [(round(t - RATE, 6), o, [v[0], v[1], v[2] + 800.0 * RATE]) for t, o, v in self.rows[k + 1:]]
        r = verdict(rows, self.fin - 1)
        self.assertEqual(r["verdict"], "HOLD", self.reasons(r))
        self.assertIn("free-flight position", self.reasons(r))

    def test_teleport_off_zone(self):
        rows = [(t, [o[0], o[1] + (200 if i >= self.i0 else 0), o[2]], v) for i, (t, o, v) in enumerate(self.rows)]
        r = verdict(rows, self.fin)
        self.assertEqual(r["verdict"], "HOLD")
        self.assertIn("not onto a stage start", self.reasons(r))

    def test_teleport_into_the_end(self):
        xe = ZONES["tracks"]["main"]["zones"]["end"]["regions"][0]["points"][0][0]
        k = self.i0
        rows = self.rows[:k] + [(t, [o[0] - self.rows[k][1][0] + xe + 50, o[1], o[2]], v) for t, o, v in self.rows[k:]]
        r = verdict(rows, round(rows[k][0] / RATE))
        self.assertEqual(r["verdict"], "HOLD", self.reasons(r))
        self.assertIn("not onto a stage start", self.reasons(r))

    def test_low_gravity(self):
        rows = [(t, list(o), list(v)) for t, o, v in self.rows]
        j0 = next(i for i, r in enumerate(rows) if r[2][2] > 200)
        for j in range(j0 + 1, len(rows)):
            dt = rows[j][0] - rows[j - 1][0]
            rows[j][2][2] = rows[j - 1][2][2] - 600.0 * dt
            rows[j][1][2] = rows[j - 1][1][2] + (rows[j - 1][2][2] + rows[j][2][2]) * 0.5 * dt
        r = verdict(rows, self.fin)
        self.assertEqual(r["verdict"], "HOLD", self.reasons(r))

    def test_past_maxvelocity_fails(self):
        rows = [(t, o, list(v)) for t, o, v in self.rows]
        rows[self.i0][2][0] = 3600.0
        self.assertEqual(verdict(rows, self.fin)["verdict"], "FAIL")

    def test_claims_a_faster_finish(self):
        r = verdict(self.rows, self.fin - 10)
        self.assertEqual(r["verdict"], "HOLD")
        self.assertIn("never reaches end", self.reasons(r))

    def test_starts_outside(self):
        rows = [(t, [o[0] + 1000, o[1], o[2]], v) for t, o, v in self.rows]
        r = verdict(rows, self.fin)
        self.assertEqual(r["verdict"], "HOLD")
        self.assertIn("outside the start zone", self.reasons(r))

    def test_compressed_clock(self):
        # 1% less time claimed for the same motion; samples off the tick grid, as our own recordings are
        rows = [(round(t * 0.99, 6), o, v) for t, o, v in self.rows]
        r = verdict(rows, round(self.fin * 0.99))
        self.assertEqual(r["verdict"], "HOLD", self.reasons(r))
        self.assertIn("clock edited", self.reasons(r))

    def test_sparse_samples_pass(self):
        # several ticks a sample, as after packet loss: drop every third sample
        rows = [r for i, r in enumerate(self.rows) if i % 3 != 1]
        r = verdict(rows, self.fin)
        self.assertEqual(r["verdict"], "PASS", self.reasons(r))

    def test_native_state_records_hold(self):
        txt = text(self.rows, self.fin).replace("begin\n", "begin\nresume 0 0\n")
        r = tp.check(tp.read(text=txt), ZONES)
        self.assertEqual(r["verdict"], "HOLD")
        self.assertIn("exact verifier", self.reasons(r))

    def test_samples_end_before_finish_fails(self):
        rows = [r for r in self.rows if r[0] <= self.fin * RATE - 0.2]
        self.assertEqual(verdict(rows, self.fin)["verdict"], "FAIL")

    def test_no_zones_is_hold_not_pass(self):
        r = tp.check(tp.read(text=text(self.rows, self.fin)), None)
        self.assertEqual(r["verdict"], "HOLD")
        self.assertIn("no zones", self.reasons(r))

    def test_duck_shifts_cancel(self):
        k = self.i0
        up = [(t, [o[0], o[1], o[2] + (8.5 if k <= i < k + 20 else 0)], v) for i, (t, o, v) in enumerate(self.rows)]
        self.assertEqual(verdict(up, self.fin)["verdict"], "PASS", self.reasons(verdict(up, self.fin)))
        stair = [(t, [o[0], o[1], o[2] + 8.5 * sum(1 for s in (k, k + 10, k + 20) if i >= s)], v)
                 for i, (t, o, v) in enumerate(self.rows)]
        r = verdict(stair, self.fin)
        self.assertEqual(r["verdict"], "HOLD")
        self.assertIn("duck shifts add up", self.reasons(r))

    def test_no_samples_fails(self):
        self.assertEqual(tp.check(tp.read(text="FTESURF-REC 5\ntickrate 0.015\nbegin\nend 5\n"), ZONES)["verdict"], "FAIL")


class Hostile(unittest.TestCase):
    """Uploads are anyone's bytes: a verdict always comes back, and odd numbers never PASS."""

    def setUp(self):
        self.rows, self.fin = simulate()

    def test_nan_tickrate_fails(self):
        body = text(self.rows, self.fin).replace(f"tickrate {RATE}", "tickrate nan")
        self.assertEqual(tp.check(tp.read(text=body), ZONES)["verdict"], "FAIL")

    def test_huge_end_fails(self):
        body = text(self.rows, self.fin).replace(f"end {self.fin} ", "end " + "9" * 4000 + " ")
        self.assertEqual(tp.check(tp.read(text=body), ZONES)["verdict"], "FAIL")
        body = text(self.rows, self.fin).replace(f"end {self.fin} ", "end 100000001 ")
        self.assertEqual(tp.check(tp.read(text=body), ZONES)["verdict"], "FAIL")

    def test_far_position_fails_without_raising(self):
        rows = [(t, list(o), list(v)) for t, o, v in self.rows]
        rows[len(rows) // 2][1][0] = 3.0e38
        self.assertEqual(verdict(rows, self.fin)["verdict"], "FAIL")

    def test_non_finite_sample_is_dropped(self):
        body = text(self.rows, self.fin)
        lines = body.split("\n")
        k = next(i for i, x in enumerate(lines) if x.startswith("0.3000"))
        lines[k] = lines[k].replace(lines[k].split()[4], "nan", 1)
        r = tp.check(tp.read(text="\n".join(lines)), ZONES)
        self.assertEqual(len(tp.read(text="\n".join(lines)).samples), len(self.rows) - 1)
        self.assertIn(r["verdict"], ("PASS", "HOLD"))   # one dropped sample is a 2-tick step

    def test_fuzz_never_raises(self):
        import random
        rnd = random.Random(1120)
        toks = ["nan", "inf", "-inf", "1e39", "-0", "9" * 5000, "0.015", "1e-300", "x", "-", "1", "begin", "end"]
        base = text(self.rows, self.fin).split("\n")
        for _ in range(300):
            lines = list(base)
            for _ in range(rnd.randint(1, 12)):
                i = rnd.randrange(len(lines))
                parts = lines[i].split()
                if parts:
                    parts[rnd.randrange(len(parts))] = rnd.choice(toks + [repr(rnd.uniform(-1e6, 1e6))])
                lines[i] = " ".join(parts)
            r = tp.check(tp.read(text="\n".join(lines)), ZONES)
            self.assertIn(r["verdict"], ("PASS", "HOLD", "FAIL"))


class Review1639(unittest.TestCase):
    """The bypasses P1639's review demonstrated, each now HOLD or FAIL, beside a control that passes."""

    def setUp(self):
        self.rows, self.fin = simulate()
        self.rows = [(t, list(o), list(v)) for t, o, v in self.rows]

    def why(self, r):
        return " | ".join(x["what"] for x in r["reasons"])

    def assertHeld(self, r, phrase):
        self.assertEqual(r["verdict"], "HOLD", self.why(r))
        self.assertIn(phrase, self.why(r))

    def at(self, t):
        return next(i for i, r in enumerate(self.rows) if r[0] >= t - 1e-9)

    def refly(self, i0, fn):
        """Apply fn(t, o, v) -> (o, v) from row i0 on and rebuild positions from the velocities."""
        for j in range(i0, len(self.rows)):
            t, o, v = self.rows[j]
            self.rows[j] = (t, *fn(t, list(o), list(v)))

    def test_header_key_twice_fails(self):
        body = text(self.rows, self.fin).replace("track 0\n", "track 0\ntrack 1\n")
        r = tp.check(tp.read(text=body), ZONES)
        self.assertEqual(r["verdict"], "FAIL")
        self.assertIn("header repeats track", self.why(r))

    def test_hidden_line_break_fails(self):
        for sep in ("\x0b", " ", "\r"):
            body = text(self.rows, self.fin).replace("track 0\n", "track 0" + sep + "movetickrate 0.02\n")
            self.assertEqual(tp.check(tp.read(text=body), ZONES)["verdict"], "FAIL", repr(sep))
        crlf = text(self.rows, self.fin).replace("\n", "\r\n")   # Windows line ends are fine
        self.assertEqual(tp.check(tp.read(text=crlf), ZONES)["verdict"], "PASS")

    def test_samples_between_ticks_hold(self):
        rows = []
        for a, b in zip(self.rows, self.rows[1:]):
            rows.append(a)
            rows.append((round((a[0] + b[0]) / 2, 6), [(x + y) / 2 for x, y in zip(a[1], b[1])],
                         [(x + y) / 2 for x, y in zip(a[2], b[2])]))
        rows.append(self.rows[-1])
        self.assertHeld(verdict(rows, self.fin), "not whole ticks")

    def test_low_precision_holds(self):
        body = text(self.rows, self.fin)
        lines = body.split("\n")
        for i, line in enumerate(lines):
            tok = line.split()
            if tok and tp.is_sample(tok[0]):
                tok[4:7] = ["%de-6" % round(float(x) * 1e6) for x in tok[4:7]]
                lines[i] = " ".join(tok)
        self.assertHeld(tp.check(tp.read(text="\n".join(lines)), ZONES), "decimals")

    def test_fast_ground_slide_holds(self):
        i0 = self.at(0.0)
        rows = self.rows[:i0]
        t, o, v = rows[-1]
        o, v = list(o), [600.0, 0.0, 0.0]
        while t < 1.6:
            nv = [v[0] + 19.0, 0.0, 0.0]          # inside the 20 u/s step, but at 600+ u/s
            o = [o[0] + (v[0] + nv[0]) * 0.5 * RATE, o[1], o[2]]
            t, v = round(t + RATE, 6), nv
            rows.append((t, list(o), list(v)))
        self.assertHeld(verdict(rows, self.fin), "accelerating past run speed")

    def test_mid_air_jump_holds(self):
        # At the top of the arc (vz in [-13, 1]), where a jump from the ground looks the same in vz.
        k = next(i for i, r in enumerate(self.rows) if r[0] > 0 and -13 <= r[2][2] <= 1) + 1
        dz = 289.99 - self.rows[k][2][2]
        self.refly(k, lambda t, o, v: (o, [v[0], v[1], v[2] + dz]))
        for j in range(k + 1, len(self.rows)):   # positions follow the new vertical speed
            a, b = self.rows[j - 1], self.rows[j]
            b[1][2] = a[1][2] + (a[2][2] + b[2][2]) * 0.5 * RATE
        self.assertHeld(verdict(self.rows, self.fin), "energy")

    def test_unexplained_travel_on_a_contact_tick_holds(self):
        k = self.at(0.6)
        self.rows[k][2][2] += 0.06                # no longer exactly free flight
        for j in range(k, len(self.rows)):
            self.rows[j][1][0] += 10.0             # and 10 u further along from here on
        self.assertHeld(verdict(self.rows, self.fin), "more than the velocity change explains")

    def test_air_turn_too_sharp_holds(self):
        k = self.at(0.6)
        self.refly(k, lambda t, o, v: (o, [-v[1], v[0], v[2]]))   # 90 degrees in one tick, same speed
        for j in range(k + 1, len(self.rows)):
            a, b = self.rows[j - 1], self.rows[j]
            for c in range(2):
                b[1][c] = a[1][c] + (a[2][c] + b[2][c]) * 0.5 * RATE
        r = verdict(self.rows, self.fin, zones=None)
        self.assertIn("air control cannot change velocity", self.why(r))

    def test_finish_claimed_early_holds(self):
        # 16 u of hull reaches the zone first: at this run's ~330 u/s that is 3 ticks, so 5 is a false claim.
        self.assertHeld(verdict(self.rows, self.fin - 5), "never reaches end")
        self.assertEqual(verdict(self.rows, self.fin)["verdict"], "PASS")

    def staged(self):
        """ZONES plus a stage 2 start where the run is at t=0.6."""
        z = json.loads(json.dumps(ZONES))
        x6 = self.rows[self.at(0.6)][1][0]
        z["tracks"]["main"]["zones"]["segments"].append(
            {"checkpoints": [{"regions": [box(x6 - 20, x6 + 20, -500, 500, -2000, 4000)]}]})
        return z

    def test_stage_retry_passes_and_skip_holds(self):
        z = self.staged()
        i6, i9 = self.at(0.6), self.at(0.9)
        # A fall at 0.9 s puts the body back on stage 2's start; it rides stage 2 again from there.
        again = [(round(self.rows[i9][0] + RATE * (1 + j - i6), 6), list(o), list(v))
                 for j, (t, o, v) in enumerate(self.rows[i6:], start=i6)]
        rows = self.rows[:i9 + 1] + again
        fin = self.fin + (i9 + 1 - i6)
        r = verdict(rows, fin, zones=z)
        self.assertEqual(r["verdict"], "PASS", self.why(r))
        self.assertEqual(r["stats"]["teleports"], 1)
        # The same fall landing with more speed than it had is not a fall; nor is falling turned into running.
        fast = [(t, o, [c * 1.5 for c in v]) if j == 0 else (t, o, v) for j, (t, o, v) in enumerate(again)]
        self.assertHeld(verdict(self.rows[:i9 + 1] + fast, fin, zones=z), "gaining")
        vz9 = abs(self.rows[i9][2][2])
        turned = [(t, o, [v[0] + vz9 * 0.7, v[1], 0.0]) if j == 0 else (t, o, v) for j, (t, o, v) in enumerate(again)]
        self.assertHeld(verdict(self.rows[:i9 + 1] + turned, fin, zones=z), "gaining")
        # Teleporting onto stage 2's start before reaching it is a skip (or a stage-end teleporter).
        i3 = self.at(0.3)
        skip = self.rows[:i3 + 1] + [(round(self.rows[i3][0] + RATE * (1 + j - i6), 6), list(o), list(v))
                                     for j, (t, o, v) in enumerate(self.rows[i6:], start=i6)]
        self.assertHeld(verdict(skip, self.fin - (i6 - i3 - 1), zones=z), "from stage 1")

    def test_start_speed_rules(self):
        z = json.loads(json.dumps(ZONES))
        z["tracks"]["main"]["zones"]["segments"][0]["limitStartGroundSpeed"] = False
        self.assertEqual(verdict(self.rows, self.fin, zones=z)["verdict"], "PASS")   # opens at rest
        rows = [(t, o, [v[0] + 900.0, v[1], v[2]]) if j == 0 else (t, o, v) for j, (t, o, v) in enumerate(self.rows)]
        self.assertHeld(verdict(rows, self.fin, zones=z), "opens already moving")
        i0 = self.at(0.0)
        rows = [(t, o, [v[0], v[1], -500.0]) if j == i0 else (t, o, v) for j, (t, o, v) in enumerate(self.rows)]
        self.assertIn("counting vertical speed", self.why(verdict(rows, self.fin)))


@unittest.skipUnless(os.environ.get("TASPLAUS_CORPUS"), "set TASPLAUS_CORPUS (+ TASPLAUS_ZONES) to real .rec files")
class Corpus(unittest.TestCase):
    def test_honest_runs_pass(self):
        zones = None
        if os.environ.get("TASPLAUS_ZONES"):
            with open(os.environ["TASPLAUS_ZONES"], encoding="utf-8") as f:
                zones = json.load(f)
        files = []
        for f in sorted(glob.glob(os.path.join(os.environ["TASPLAUS_CORPUS"], "*"))):
            with open(f, "rb") as fh:
                if fh.read(11) == b"FTESURF-REC":
                    files.append(f)
        self.assertTrue(files)
        bad = []
        for f in files:
            r = tp.check(tp.read(f), zones)
            if r["verdict"] != "PASS":
                bad.append((os.path.basename(f), r["verdict"], r["reasons"][:2]))
        self.assertEqual(bad, [], f"{len(bad)} of {len(files)} honest runs not PASS")


if __name__ == "__main__":
    unittest.main()
