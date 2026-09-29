#!/usr/bin/env python3
"""p467visprobe.py -- the snd_vis falsifier (Patch 467's engine half).

    python tools/p467visprobe.py                 # write ftesurf/music/visprobe.wav
    python tools/p467visprobe.py --grade LOG     # grade a cfg/test/p467sndvis*.cfg log

The WAV (48 kHz, 16 s loop): 0-2 s silence, 2-6 kick 120 BPM, 6-10 hats 8/s,
10-14 both, 14-16 silence.  Kick 55 Hz at -40 dBFS peak, hats 8 kHz at -60 dBFS,
so a laptop's speakers stay effectively silent -- note `volume 0` does NOT mute
music (musicvolume * mastervolume scale it before the tap).  The grader aligns
every loop by its own kicks and counts detected / missed / extra onsets.
Written by the session that built snd_vis.c; kept because the probe needs its
WAV and the WAV is not in git (music/ is ignored).
"""
import os, re, sys, wave
import numpy as np

RATE = 48000
N = RATE * 16
KICK_AMP = 328 / 32768.0     # -40 dBFS peak: 55 Hz, below what laptop speakers reproduce
HAT_AMP = 32 / 32768.0       # -60 dBFS peak
sig = np.zeros(N)

def kick(t0):
    n = int(0.35 * RATE); i = np.arange(n); att = int(0.002 * RATE)
    env = np.exp(-i / RATE / 0.1)
    env[:att] *= 0.5 - 0.5 * np.cos(np.pi * i[:att] / att)   # 2 ms attack: no click
    s0 = int(round(t0 * RATE))
    sig[s0:s0 + n] += KICK_AMP * np.sin(2 * np.pi * 55 * i / RATE) * env

def hat(t0):
    n = int(0.06 * RATE); i = np.arange(n)
    s0 = int(round(t0 * RATE))
    sig[s0:s0 + n] += HAT_AMP * np.sin(2 * np.pi * 8000 * i / RATE) * np.exp(-i / RATE / 0.015)

kicks = [2.0 + 0.5 * k for k in range(8)] + [10.0 + 0.5 * k for k in range(8)]
hats = [6.0 + 0.125 * k for k in range(32)] + [10.0 + 0.125 * k for k in range(32)]
for t in kicks: kick(t)
for t in hats: hat(t)


def write_wav(path):
    pcm = np.clip(np.round(sig * 32767), -32768, 32767).astype('<i2')
    st = np.repeat(pcm[:, None], 2, axis=1)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(st.tobytes())
    print('wrote', path, os.path.getsize(path), 'bytes; peak int16', int(np.abs(pcm).max()))


def grade(log):
    kicks_ = np.array(kicks); hats_ = np.array(hats)
    LOOP = 16.0
    tr = []; ons = []; info = []; markers = []; lastinfo = None
    rx = re.compile(r'snd_vis t=([\d.]+) b ([\d.]+) m ([\d.]+) t ([\d.]+) ba ([\d.]+) ma ([\d.]+) ta ([\d.]+) v ([\d.]+) va ([\d.]+) beat ([\d.]+) bb ([\d.]+) bt ([\d.]+) rms ([\d.]+) lat ([\d.]+)')
    for ln in open(log, encoding='utf-8', errors='replace'):
        m = rx.search(ln)
        if m:
            tr.append([float(x) for x in m.groups()]); continue
        m = re.search(r'snd_vis onset (bass|treb) t=([\d.]+) r=([\d.]+)', ln)
        if m:
            ons.append((m.group(1), float(m.group(2)), float(m.group(3)))); continue
        m = re.search(r'SNDVIS_(POLL|LOWPASS|PROBE) (.*)', ln)
        if m:
            markers.append((m.group(1), m.group(2).strip(), tr[-1][0] if tr else None)); continue
        m = re.search(r'lowpass target ([\d.]+) Hz, (effective ([\d.]+) Hz|bypassed)(, output/input ([-+\d.]+) dB over the last (\d+) filtered frames)?', ln)
        if m:
            info.append(dict(t=tr[-1][0] if tr else None, target=float(m.group(1)), eff=float(m.group(3)) if m.group(3) else None,
                             db=float(m.group(5)) if m.group(5) else None, frames=int(m.group(6)) if m.group(6) else 0))
        m = re.search(r'cost ([\d.]+) us avg, ([\d.]+) us max over (\d+) analyses(; at most (\d+) in one call)?', ln)
        if m: cost = m.groups()
        m = re.search(r'latency ([\d.]+) ms \((.*)\)', ln)
        if m: lat = (float(m.group(1)), m.group(2))
        m = re.search(r'Audio Device: (.*)', ln)
        if m: dev = m.group(1)
    
    tr = np.array(tr); t = tr[:, 0]
    print('analyses traced %d, clock %.3f..%.3f s; spacing (audio ms) median %.2f, max %.2f  -> a fixed grid' %
          (len(t), t[0], t[-1], np.median(np.diff(t))*1000, np.diff(t).max()*1000))
    bass_on = np.array([o[1] for o in ons if o[0] == 'bass']); treb_on = np.array([o[1] for o in ons if o[0] == 'treb'])
    
    # per-loop alignment by kicks
    offs = []
    guess = bass_on[0] - kicks[0]
    period = LOOP
    while guess + 2.0 < t[-1]:
        d = []
        for k in kicks:
            near = bass_on[np.abs(bass_on - (k + guess)) < 0.15]
            if len(near): d.append(near[0] - k)
        off = float(np.median(d)) if len(d) >= 3 else guess	# a trailing partial loop keeps the extrapolated start
        if offs: period = off - offs[-1]
        offs.append(off); guess = off + period
    print('loops aligned: %d; offsets %s; loop periods %s s' % (len(offs), ['%.3f' % o for o in offs], ['%.3f' % x for x in np.diff(offs)]))
    
    def loop_of(x):
        L = None
        for i, o in enumerate(offs):
            if x >= o - 0.5: L = i
        return L
    def track(x):
        L = loop_of(x)
        return (None, None) if L is None else (L, x - offs[L])
    
    # filter state per analysis: on from the on-marker (+0.5 s settle) to the off-marker; the off glide ends at the first 'bypassed'
    mk = {b: c for a, b, c in markers if a == 'LOWPASS'}
    t_on = mk.get('on 500'); t_off = mk.get('off')
    t_byp = next((i['t'] for i in info if t_off and i['t'] and i['t'] > t_off and i['eff'] is None), None)
    print('lowpass: on at clock %.2f (loop %s track %.2f), off at %.2f (loop %s track %.2f), bypassed again by %.2f' %
          (t_on, *track(t_on), t_off, *track(t_off), t_byp or -1))
    def filt(x):
        if t_on is None: return 'off'
        if t_on + 0.5 <= x < t_off: return 'on'
        if x < t_on or (t_byp and x >= t_byp): return 'off'
        return 'transition'
    
    # onset matching per loop and filter state
    res = {}
    for L, o in enumerate(offs):
        for name, arr, truthset, lo, hi in [('kick', bass_on, kicks, 0, 16), ('hat', treb_on, hats, 0, 16)]:
            for x in truthset:
                T = o + x
                if T > t[-1] - 0.2: continue
                key = (name, 'hats-only' if 6 <= x < 10 else 'both' if 10 <= x < 14 else 'kick-only', filt(T))
                r = res.setdefault(key, [0, 0, []])
                r[0] += 1
                c = arr[(arr - T > -0.03) & (arr - T < 0.1)]
                if len(c): r[1] += 1; r[2].append(c[0] - T)
    print('onsets vs truth (per section and filter state; delay = onset clock - aligned true time):')
    for k in sorted(res):
        n, h, d = res[k]
        print('  %-4s %-9s filter %-10s %3d true, %3d detected (%.0f%%)%s' % (k[0], k[1], k[2], n, h, 100.0*h/n,
              '' if not d else ', delay %.1f ms (sd %.1f)' % (np.mean(d)*1000, np.std(d)*1000)))
    # extras: onsets not within [-0.03, 0.1] of any true event of their kind
    def extras(arr, truthset):
        ex = []
        for x in arr:
            L, tt = track(x)
            if L is None or tt < 0: continue
            if not np.any(((tt - truthset) > -0.03) & ((tt - truthset) < 0.1)): ex.append(round(tt, 3))
        return ex
    eb = extras(bass_on, kicks); et = extras(treb_on, hats)
    print('  extra bass onsets (track times): %d %s' % (len(eb), eb[:20]))
    print('  extra treb onsets (track times): %d %s' % (len(et), et[:20]))
    
    # section means by filter state
    print('section means of the outputs (bass/mid/treb = imm/long_avg; att smoothed):')
    rows = {}
    for row in tr:
        L, tt = track(row[0])
        if L is None: continue
        sec = 'silence-start' if tt < 1.9 and L == 0 else 'kick-only' if 2.5 <= tt < 6 else 'hats-only' if 6.5 <= tt < 10 else 'both' if 10.5 <= tt < 14 else 'silence-end' if 14.6 <= tt < 16 else None
        if sec is None: continue
        rows.setdefault((sec, filt(row[0])), []).append(row)
    for k in sorted(rows):
        s = np.array(rows[k]); m = s.mean(axis=0); mx = s.max(axis=0)
        print('  %-13s filter %-10s n=%4d bass %.3f mid %.3f treb %.3f | att %.3f %.3f %.3f | vol %.3f | rms mean %.6f max %.6f | lat %.1f ms'
              % (k[0], k[1], len(s), m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[12], mx[12], m[13]))
    print('per loop (mean over the section; filter state of the majority of its analyses):')
    for L in range(len(offs)):
        parts = []
        for sec, lo, hi in [('kick', 2.5, 6), ('hats', 6.5, 10), ('both', 10.5, 14)]:
            sel = tr[(t - offs[L] >= lo) & (t - offs[L] < hi)]
            if not len(sel): continue
            states = [filt(x) for x in sel[:, 0]]
            st = max(set(states), key=states.count)
            m = sel.mean(axis=0)
            parts.append('%s[%s] b %.2f m %.2f t %.2f v %.2f' % (sec, st, m[1], m[2], m[3], m[7]))
        print('  loop %d: %s' % (L, ' | '.join(parts)))
    print('snd_visinfo lowpass lines while filtering or gliding (clock -> loop/track time):')
    for i in info:
        if i['eff'] is not None or (t_off and i['t'] and t_off <= i['t'] <= (t_byp or 1e9) + 0.3):
            L, tt = track(i['t'])
            print('   clock %.2f (loop %s, track %5.2f)  target %g  eff %s  %s' % (i['t'], L, tt if tt is not None else -1, i['target'], i['eff'],
                  '' if i['db'] is None else 'output/input %+.1f dB over %d frames' % (i['db'], i['frames'])))
    print('device:', dev, '| last latency line:', lat, '| cost:', cost)


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--grade':
        grade(sys.argv[2])
    else:
        write_wav(os.path.join('ftesurf', 'music', 'visprobe.wav'))
