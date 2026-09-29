#!/usr/bin/env python3
"""p468react.py -- replay a snd_vis trace through the milk visuals' beat gates.

    python tools/p468react.py ftesurf/logs/p468react.log

The log is from cfg/test/p468react.cfg: every analysis (snd_vis_trace 2) of each
generated track, split by REACT_TRACK markers.  This samples the trace at the
QC's 60 Hz tick and runs src/milk_sys.qc's Milk_Audio gates on it, so the counts
are what the menu would have done with the same audio:

  onsets   the engine's own bass / treble onsets (what milk_beat pulsed on)
  kick     milk_kick crossing 0.5 -- a bass onset well above the track's average
  hit      milk_hit crossing 0.5  -- a kick, or a snare (treble onset with mids)
  flash    the full-screen flash's mean and peak, old (milk_beat, react 2 = x2,
           x0.18) against new (milk_hit, "wild" = Milk_ReactCurve(2) = x1.0, x0.12)

KEEP THE GATES HERE IN STEP WITH Milk_Audio.
"""
import re, sys

RX = re.compile(r'snd_vis t=([\d.]+) b ([\d.]+) m ([\d.]+) t ([\d.]+) ba ([\d.]+) ma ([\d.]+) ta ([\d.]+) '
                r'v ([\d.]+) va ([\d.]+) beat ([\d.]+) bb ([\d.]+) bt ([\d.]+)')


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def tracks(path):
    cur, out = None, {}
    for ln in open(path, encoding='utf-8', errors='replace'):
        if 'REACT_TRACK' in ln:
            cur = ln.split('REACT_TRACK', 1)[1].strip()
            out[cur] = []
            continue
        if 'REACT_DONE' in ln:
            cur = None
            continue
        m = RX.search(ln)
        if m and cur:
            out[cur].append([float(x) for x in m.groups()])
    return out


def replay(rows):
    """Tick at 60 Hz of audio time, reading the newest analysis, as the QC does."""
    if len(rows) < 2:
        return None
    t0, t1 = rows[0][0], rows[-1][0]
    if t1 <= t0:
        return None
    kick = hit = 0.0
    k_on = h_on = 0
    k_prev = h_prev = 0.0
    old_sum = new_sum = old_pk = new_pk = 0.0
    ticks = 0
    j = 0
    prev_bb = prev_bt = 0.0
    b_on = t_on = any_on = 0
    prev_beat = 0.0
    snare = 0
    tau = t0
    while tau <= t1:
        while j + 1 < len(rows) and rows[j + 1][0] <= tau:
            j += 1
        r = rows[j]
        b, mid = clamp(r[1], 0, 3), clamp(r[2], 0, 3)
        beat, bb, bt = clamp(r[9], 0, 1), clamp(r[10], 0, 1), clamp(r[11], 0, 1)
        # A pulse is 1 at its onset and decays over 0.15 s; a 60 Hz tick can miss
        # the 1.0 itself, so an onset is the jump.
        if bb > prev_bb + 0.2:
            b_on += 1
        if bt > prev_bt + 0.2:
            t_on += 1
        if beat > prev_beat + 0.2:
            any_on += 1
        prev_beat = beat
        prev_bb, prev_bt = bb, bt
        kick = max(kick * 0.86, bb * clamp((b - 1.3) / 0.9, 0, 1))
        sn = 0.8 * bt * clamp((mid - 1.2) / 0.8, 0, 1)
        hit = max(hit * 0.86, max(kick, sn))
        if kick >= 0.5 and k_prev < 0.5:
            k_on += 1
        if hit >= 0.5 and h_prev < 0.5:
            h_on += 1
            if sn >= 0.5 and kick < 0.5:
                snare += 1
        k_prev, h_prev = kick, hit
        old = beat * 2 * 0.18
        new = hit * 1.0 * 0.12
        old_sum += old
        new_sum += new
        old_pk = max(old_pk, old)
        new_pk = max(new_pk, new)
        ticks += 1
        tau += 1 / 60.0
    secs = ticks / 60.0
    return dict(secs=secs, any_on=any_on / secs, bass_on=b_on / secs, treb_on=t_on / secs, kick=k_on / secs, hit=h_on / secs,
                snare=snare / secs, old_mean=old_sum / ticks, new_mean=new_sum / ticks, old_pk=old_pk, new_pk=new_pk)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    tr = tracks(sys.argv[1])
    if not tr:
        print('no REACT_TRACK sections in', sys.argv[1])
        return 1
    print('%-18s %6s | %6s %6s %6s | %6s %6s %7s | %-17s %s' % (
        'track', 'secs', 'beat/s', 'bass/s', 'treb/s', 'kick/s', 'hit/s', 'snare/s', 'flash mean o->n', 'peak o->n'))
    bad = 0
    for name, rows in tr.items():
        r = replay(rows)
        if r is None:
            print('%-18s  NO TRACE (%d lines) -- the arm measured nothing' % (name, len(rows)))
            bad += 1
            continue
        print('%-18s %6.1f | %6.2f %6.2f %6.2f | %6.2f %6.2f %7.2f | %.4f -> %.4f   %.3f -> %.3f' % (
            name, r['secs'], r['any_on'], r['bass_on'], r['treb_on'], r['kick'], r['hit'], r['snare'],
            r['old_mean'], r['new_mean'], r['old_pk'], r['new_pk']))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
