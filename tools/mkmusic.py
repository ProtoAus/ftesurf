#!/usr/bin/env python3
"""mkmusic.py -- every generated FTESurf sound: the menu worlds' tracks and the
menu's sound effects.  numpy only.

    python tools/mkmusic.py                   everything
    python tools/mkmusic.py monolith sfx      just those

Tracks go to ftesurf/music/ftesurf_<name>.wav (44.1 kHz 16-bit stereo), and
loop seamlessly: every note and every reverb tail wraps round the end of the
buffer.  Effects go to ftesurf/sound/milk/<name>.wav (mono).  Both
directories are git-ignored: the files are generated, deterministic (fixed
seeds) and free of any licence question; this script is what is kept.

    dream     the lattice world's, 100 BPM  (tools/mkmenumusic.py, unchanged)
    monolith  a chant in a cathedral: a male choir by formant synthesis over a
              drone, strings and timpani -- the monolith world's
    vessel    a heartbeat at 64, blood-flow swells, monitor pings -- the vessel's
    canopy    a forest: kalimba, a stream, birds, hand drums
    void      the PS2's boot: a sub drone, glass bells, a whoosh and a boom
    drive     synthwave at 120 to surf to

Every track keeps a bass onset on a beat most of the time: the visualizer's
beat detector (snd_getvis) keys on them.
"""
import os
import sys
import wave
import numpy as np

SR = 44100
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
MUSIC = os.path.join(ROOT, 'ftesurf', 'music')
SFX = os.path.join(ROOT, 'ftesurf', 'sound', 'milk')
TAU = 2.0 * np.pi


def hz(m):
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=float) - 69.0) / 12.0)


def tax(n):
    return np.arange(n) / SR


# ------------------------------------------------------------------ buffers --
class Mix:
    """A circular stereo buffer: anything added past the end wraps to the start."""

    def __init__(self, secs, seed):
        self.N = int(round(secs * SR))
        self.L = np.zeros(self.N)
        self.R = np.zeros(self.N)
        self.rng = np.random.default_rng(seed)

    def add(self, at, sig, pan=0.5, gain=1.0):
        i = int(round(at * SR)) % self.N
        sig = np.asarray(sig) * gain
        n = len(sig)
        while n > 0:
            m = min(n, self.N - i)
            self.L[i:i + m] += sig[:m] * np.sqrt(1.0 - pan)
            self.R[i:i + m] += sig[:m] * np.sqrt(pan)
            sig = sig[m:]
            n -= m
            i = 0

    def add2(self, at, sl, sr, gain=1.0):
        self.add(at, sl, 0.0, gain)
        self.add(at, sr, 1.0, gain)


def fft_filter(x, lo=0.0, hi=None, n=None):
    """Brick-wall band-pass in the frequency domain (circular)."""
    n = n or len(x)
    X = np.fft.rfft(x, n)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    keep = (f >= lo) & (f <= (hi if hi else SR))
    return np.fft.irfft(X * keep, n)[:len(x)]


def smooth(x, secs):
    """One-pole-ish smoothing by FFT convolution with a normalised exponential."""
    k = int(max(1, secs * SR))
    h = np.exp(-np.arange(k * 5) / k)
    h /= h.sum()
    n = len(x)
    return np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(h, n), n)


def ir(rng, secs, rt_lo, rt_hi, pre=0.02, split=1800.0):
    """A stereo room: decorrelated noise, the lows decaying slower than the highs."""
    n = int(secs * SR)
    t = tax(n)
    out = []
    for _ in range(2):
        x = rng.normal(0, 1, n)
        X = np.fft.rfft(x)
        f = np.fft.rfftfreq(n, 1.0 / SR)
        lo = np.fft.irfft(X * (f < split), n)
        hi = np.fft.irfft(X * (f >= split), n)
        h = lo * np.exp(-6.91 * t / rt_lo) + hi * np.exp(-6.91 * t / rt_hi)
        h[:int(pre * SR)] = 0.0
        h /= np.sqrt(np.sum(h ** 2))
        out.append(h)
    return out


def reverb(mix, room, wet, dry=1.0):
    N = mix.N

    def conv(x, h):
        pad = np.zeros(N)
        m = min(len(h), N)
        pad[:m] = h[:m]
        return np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(pad), N)

    wl, wr = conv(mix.L, room[0]), conv(mix.R, room[1])
    mix.L = mix.L * dry + wet * wl
    mix.R = mix.R * dry + wet * wr


def master(mix, drive=1.0, ceiling=0.89, target=-15.0):
    """To a common loudness (RMS, dBFS), then a soft clip under the ceiling:
    the menu can move between tracks without one leaping out."""
    rms = np.sqrt((0.5 * (mix.L ** 2 + mix.R ** 2)).mean()) + 1e-12
    g = 10 ** (target / 20.0) / rms * drive / ceiling
    return np.tanh(mix.L * g) * ceiling, np.tanh(mix.R * g) * ceiling


def write(path, L, R=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = L if R is None else np.stack([L, R], axis=1)
    pcm = (np.clip(data, -1, 1) * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(1 if R is None else 2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f'{os.path.relpath(path, ROOT)}: {len(pcm) / SR:.1f} s, {len(pcm.tobytes()) / 1e6:.1f} MB')


# -------------------------------------------------------------- instruments --
def env(n, a, r, curve=1.0):
    e = np.ones(n)
    na, nr = min(n, int(a * SR)), min(n, int(r * SR))
    if na:
        e[:na] = np.linspace(0, 1, na) ** curve
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr) ** curve
    return e


def boom(rng, dur=3.5, f0=64.0, f1=38.0, decay=1.1, click=0.25):
    """Timpani / a deep hit: a falling sine, its octave, a noise attack."""
    n = int(dur * SR)
    t = tax(n)
    f = f1 + (f0 - f1) * np.exp(-t / 0.22)
    ph = TAU * np.cumsum(f) / SR
    x = np.sin(ph) * np.exp(-t / decay) + 0.35 * np.sin(2 * ph + 0.3) * np.exp(-t / (decay * 0.3))
    na = int(0.02 * SR)
    x[:na] += rng.normal(0, 1, na) * np.linspace(1, 0, na) * click
    return x * env(n, 0.002, 0.3)


def pad(rng, midis, dur, cutoff=1600.0, det=(-0.09, 0.0, 0.09), attack=1.8, release=2.2, bright=None):
    """Band-limited saws, detuned, gently low-passed: strings or a synth pad."""
    n = int(dur * SR)
    t = tax(n)
    out = np.zeros(n)
    for m in midis:
        for d in det:
            f = float(hz(m + d))
            k = 1
            while f * k < min(cutoff * 3.0, 9000.0):
                a = (1.0 / k) / (1.0 + (f * k / cutoff) ** 4)
                out += a * np.sin(TAU * f * k * t + rng.uniform(0, TAU))
                k += 1
    return out * env(n, attack, release, 1.5) / max(1, len(midis) * len(det))


def bell(f, dur, ratio=3.5, index=2.4, decay=2.0, idx_decay=0.5):
    """FM bell: an inharmonic modulator whose depth dies fast -- glass, not tin."""
    n = int(dur * SR)
    t = tax(n)
    mod = index * np.exp(-t / idx_decay) * np.sin(TAU * f * ratio * t)
    return np.sin(TAU * f * t + mod) * np.exp(-t / decay) * env(n, 0.002, 0.05)


def kalimba(f, dur=1.6):
    n = int(dur * SR)
    t = tax(n)
    x = np.sin(TAU * f * t) * np.exp(-t / 0.55) + 0.35 * np.sin(TAU * f * 5.93 * t) * np.exp(-t / 0.06)
    x += 0.1 * np.sin(TAU * f * 2.0 * t) * np.exp(-t / 0.3)
    return x * env(n, 0.001, 0.05)


def rising_noise(rng, n, f0, f1, width=0.3, bands=16):
    """Noise whose pitch climbs from f0 to f1 over its length: a whoosh."""
    tt = np.arange(n) / n
    X = np.fft.rfft(rng.normal(0, 1, n))
    f = np.fft.rfftfreq(n, 1 / SR)
    x = np.zeros(n)
    for c in np.linspace(0, 1, bands):
        fc = f0 * (f1 / f0) ** c
        band = np.fft.irfft(X * np.exp(-((np.log(f + 1) - np.log(fc)) ** 2) / width), n)
        x += band * np.exp(-((tt - c) ** 2) / (0.8 / bands) ** 2)
    return x / (np.abs(x).max() + 1e-9)


def kick(dur=0.42, f0=150.0, f1=44.0, bend=0.035, decay=0.28):
    n = int(dur * SR)
    t = tax(n)
    f = f1 + (f0 - f1) * np.exp(-t / bend)
    return np.sin(TAU * np.cumsum(f) / SR) * np.exp(-t / decay) * env(n, 0.001, 0.03)


def noise_hit(rng, dur, lo, hi, decay):
    n = int(dur * SR)
    x = fft_filter(rng.normal(0, 1, n), lo, hi)
    return x / (np.abs(x).max() + 1e-9) * np.exp(-tax(n) / decay)


def saw_notes(rng, notes, n_total, cut0=2200.0, cut1=260.0, cut_decay=0.12, kmax=40):
    """A mono synth line of short notes: [(start_s, dur_s, midi, vel)], each with
    its own filter envelope.  Additive, so the 'filter' is per-harmonic gain."""
    out = np.zeros(n_total)
    for (st, du, m, vel) in notes:
        n = int(du * SR)
        t = tax(n)
        f = float(hz(m))
        cut = cut1 + (cut0 - cut1) * np.exp(-t / cut_decay)
        x = np.zeros(n)
        for k in range(1, kmax):
            if f * k > 10000:
                break
            x += (1.0 / k) / (1.0 + (f * k / cut) ** 4) * np.sin(TAU * f * k * t)
        x *= env(n, 0.003, min(0.05, du * 0.4)) * vel
        i = int(st * SR) % n_total
        j = min(n, n_total - i)
        out[i:i + j] += x[:j]
        if j < n:
            out[:n - j] += x[j:]
    return out


# Male voice formants, (Hz, bandwidth Hz, gain dB): F1..F4.
VOWELS = {
    'a': [(730, 90, 0), (1090, 110, -5), (2440, 170, -20), (3300, 250, -26)],
    'o': [(570, 80, 0), (840, 100, -7), (2410, 170, -24), (3300, 250, -30)],
    'u': [(320, 70, 0), (870, 100, -14), (2240, 170, -28), (3000, 250, -34)],
    'e': [(530, 80, 0), (1840, 120, -12), (2480, 170, -18), (3300, 250, -26)],
}


def sing(rng, n_total, notes, detune=0.0, vib=0.0045, vib_hz=5.1, kmax_hz=4200.0, breath=0.012):
    """A sung legato line through a formant filter.

    notes: [(start_s, dur_s, midi, vowel)].  f0 glides between notes, vibrato
    creeps in over each note, pitch and formants drift a little, and the
    harmonics are weighted by the vowel's resonances -- evaluated at a control
    rate and interpolated, since only the sines need the full rate."""
    CR = 64
    nc = n_total // CR + 2
    tc = np.arange(nc) * CR / SR
    lf0 = np.full(nc, np.nan)
    amp = np.zeros(nc)
    Fs = np.zeros((4, nc))
    for (st, du, m, v) in notes:
        a, b = int(st * SR / CR), int((st + du) * SR / CR)
        idx = np.arange(a, b) % nc
        lf0[idx] = np.log2(hz(m + detune / 100.0))
        e = np.ones(b - a)
        na, nr = int(0.14 * SR / CR), int(0.32 * SR / CR)
        e[:na] *= np.linspace(0, 1, min(na, len(e)))[:len(e[:na])]
        e[-nr:] *= np.linspace(1, 0, min(nr, len(e)))[-len(e[-nr:]):]
        amp[idx] = np.maximum(amp[idx], e)
        for i in range(4):
            Fs[i, idx] = VOWELS[v][i][0]
    # Hold pitch and formants through the gaps, then glide.
    for arr in [lf0] + [Fs[i] for i in range(4)]:
        good = ~np.isnan(arr) & (arr != 0)
        if good.any():
            ii = np.nonzero(good)[0]
            arr[:] = np.interp(np.arange(nc), ii, arr[ii], period=nc)
    k = int(0.07 * SR / CR)
    h = np.exp(-np.arange(k * 5) / k)
    h /= h.sum()
    lf0 = np.fft.irfft(np.fft.rfft(lf0) * np.fft.rfft(h, nc), nc)
    for i in range(4):
        Fs[i] = np.fft.irfft(np.fft.rfft(Fs[i]) * np.fft.rfft(h, nc), nc)
    drift = np.cumsum(rng.normal(0, 1, nc))
    drift = (drift - np.linspace(drift[0], drift[-1], nc))
    drift = drift / (np.abs(drift).max() + 1e-9) * 0.002
    f0c = 2.0 ** lf0 * (1.0 + drift) * (1.0 + vib * np.sin(TAU * vib_hz * tc + rng.uniform(0, TAU)) * np.clip(amp, 0, 1))
    # Up to the full rate.
    tf = np.arange(n_total) / CR
    f0 = np.interp(tf, np.arange(nc), f0c)
    A = np.interp(tf, np.arange(nc), amp)
    ph = TAU * np.cumsum(f0) / SR
    out = np.zeros(n_total)
    fmax = f0c.max()
    K = int(kmax_hz / max(f0c.min(), 60.0)) + 1
    for kk in range(1, K + 1):
        fk = kk * f0c
        g = np.zeros(nc)
        for i in range(4):
            F, B, gd = VOWELS['a'][i]
            g += 10 ** (VOWELS['a'][i][2] / 20.0) / (1.0 + ((fk - Fs[i]) / (B * 0.5)) ** 2)
        g = (g + 0.015) / kk ** 0.6 * (fk < kmax_hz)
        out += np.interp(tf, np.arange(nc), g) * np.sin(kk * ph + rng.uniform(0, TAU))
    # Breath: noise shaped by the first two formants.
    bn = fft_filter(rng.normal(0, 1, n_total), 300, 3500)
    out = out / (np.abs(out).max() + 1e-9) + breath * bn / (np.abs(bn).max() + 1e-9)
    return out * A


# ------------------------------------------------------------------- tracks --
def t_monolith():
    """D Dorian, 60 BPM, 84 s.  Drone and wind, then the chant enters; strings
    swell under its second half, timpani mark every other bar."""
    beat = 1.0
    bars = 21
    mx = Mix(bars * 4 * beat, 7001)
    rng = mx.rng
    N = mx.N
    # Drone: D2 and A2, slow beating.
    t = tax(N)
    dr = (np.sin(TAU * float(hz(38)) * t) + 0.6 * np.sin(TAU * float(hz(45)) * 1.0015 * t)
          + 0.25 * np.sin(TAU * float(hz(50)) * t)) * (0.6 + 0.4 * np.sin(TAU * t / (N / SR)) ** 2)
    mx.add(0, dr * 0.06, 0.5)
    # Wind in the shaft: filtered noise, breathing.
    w = fft_filter(rng.normal(0, 1, N), 80, 900)
    w *= smooth(np.abs(rng.normal(0, 1, N)), 1.5) ** 2
    mx.add2(0, w * 0.02, np.roll(w, SR // 3) * 0.02)
    # The chant: an original modal line, long notes, in unison and octaves.
    phrase = [(69, 2, 'a'), (67, 1, 'a'), (65, 1, 'o'), (67, 2, 'a'), (69, 2, 'a'),
              (72, 2, 'o'), (71, 1, 'a'), (69, 1, 'a'), (67, 4, 'o'),
              (69, 2, 'a'), (65, 1, 'e'), (67, 1, 'a'), (69, 2, 'a'), (74, 2, 'o'),
              (72, 2, 'a'), (71, 1, 'o'), (69, 1, 'a'), (69, 4, 'u')]
    notes = []
    at = 16.0
    for rep in range(2):
        for (m, d, v) in phrase:
            notes.append((at, d * beat * 0.98, m - 12, v))
            at += d * beat
    for i, (dt, pan) in enumerate([(-7, 0.3), (5, 0.7), (-3, 0.45), (8, 0.6)]):
        v = sing(np.random.default_rng(100 + i), N, [(s + 0.02 * i, d, m, vw) for (s, d, m, vw) in notes], detune=dt)
        mx.add(0, v * 0.16, pan)
    # The octave above for the second time through, softer.
    hi = sing(np.random.default_rng(200), N, [(s, d, m + 12, v) for (s, d, m, v) in notes if s >= 16.0 + 40.0], detune=4)
    mx.add(0, hi * 0.06, 0.55)
    # Strings: Dm - Bb - F - C, two bars each, from bar 12.
    chords = [[50, 57, 62, 65], [46, 53, 58, 62], [41, 53, 57, 60], [48, 55, 60, 64]]
    for i in range(4):
        c = pad(rng, chords[i], 8.6, cutoff=1300, attack=2.5, release=2.5)
        mx.add(48 + i * 8, c * 0.35, 0.35 + 0.1 * i)
    # Timpani on the one of every other bar, a roll into the chant.
    for b in range(0, bars, 2):
        mx.add(b * 4 * beat, boom(rng, 4.0, 70, 42, 1.3) * 0.4, 0.5)
    for i in range(8):
        mx.add(14.0 + i * 0.25, boom(rng, 1.2, 80, 60, 0.35, 0.4) * (0.1 + 0.04 * i), 0.5)
    reverb(mx, ir(rng, 7.0, 6.5, 3.2, 0.045), 0.55, 0.85)
    return master(mx, 1.0)


def t_vessel():
    """A heartbeat at 64, blood-flow swells on each beat, a monitor ping, minor
    ninth pads and, later, a glass arpeggio.  72 bars of 1 beat = 67.5 s."""
    bpm = 64.0
    beat = 60.0 / bpm
    nb = 72
    mx = Mix(nb * beat, 7002)
    rng = mx.rng
    N = mx.N
    for b in range(nb):
        at = b * beat
        lub = boom(rng, 0.5, 72, 48, 0.11, 0.35)
        dub = boom(rng, 0.4, 88, 58, 0.08, 0.25)
        mx.add(at, lub * 0.8, 0.5)
        mx.add(at + 0.2, dub * 0.55, 0.5)
        # The rush after each beat.
        sw = fft_filter(rng.normal(0, 1, int(0.7 * SR)), 120, 1400) * np.sin(np.linspace(0, np.pi, int(0.7 * SR))) ** 2
        mx.add2(at + 0.05, sw * 0.035, np.roll(sw, 400) * 0.035)
        if b % 2 == 0:
            p = bell(float(hz(93)), 1.2, ratio=1.0, index=0.3, decay=0.35) * 0.05
            mx.add(at + beat * 0.5, p, 0.7)
            mx.add(at + beat * 1.0, p * 0.4, 0.3)
    chords = [[57, 64, 67, 71, 72], [53, 60, 64, 67, 69], [50, 57, 60, 64, 65], [52, 59, 62, 64, 68]]
    span = 8 * beat
    for i in range(nb // 8):
        c = pad(rng, chords[i % 4], span + 1.5, cutoff=1100, attack=2.0, release=1.8)
        mx.add(i * span, c * 0.30, 0.5)
    t = tax(N)
    mx.add(0, np.sin(TAU * float(hz(33)) * t) * 0.07, 0.5)
    arp = [69, 72, 76, 79, 76, 72]
    for i in range(nb // 2, nb):
        for j in range(2):
            m = arp[(i * 2 + j) % len(arp)] + 12
            mx.add(i * beat + j * beat * 0.5, bell(float(hz(m)), 1.5, 2.0, 1.2, 0.8) * 0.035, 0.3 + 0.4 * j)
    reverb(mx, ir(rng, 3.5, 2.6, 1.4, 0.02), 0.4)
    return master(mx, 1.0)


def t_canopy():
    """A forest: wind, a stream, birds, a kalimba in A minor pentatonic and hand
    drums at 84.  32 bars = 91.4 s."""
    bpm = 84.0
    beat = 60.0 / bpm
    bars = 32
    mx = Mix(bars * 4 * beat, 7003)
    rng = mx.rng
    N = mx.N
    w = fft_filter(np.cumsum(rng.normal(0, 1, N)), 40, 700)
    w = w / np.abs(w).max() * smooth(np.abs(rng.normal(0, 1, N)), 2.5)
    mx.add2(0, w * 0.05, np.roll(w, SR) * 0.05)
    # The stream: hiss and bubbles -- short rising blips.
    hiss = fft_filter(rng.normal(0, 1, N), 500, 5000)
    mx.add2(0, hiss / np.abs(hiss).max() * 0.03, np.roll(hiss, 999) / np.abs(hiss).max() * 0.03)
    for _ in range(int(N / SR * 22)):
        n = int(rng.uniform(0.01, 0.04) * SR)
        f = rng.uniform(500, 1800)
        tt = tax(n)
        blip = np.sin(TAU * np.cumsum(f * (1 + 3.5 * tt / tt[-1])) / SR) * np.exp(-tt / (tt[-1] * 0.4))
        mx.add(rng.uniform(0, N / SR), blip * 0.025, rng.uniform(0.2, 0.8))
    # Birds: phrases of warbling chirps.
    for _ in range(int(N / SR / 4.5)):
        at = rng.uniform(0, N / SR)
        pan = rng.uniform(0.1, 0.9)
        base = rng.uniform(2200, 4200)
        for c in range(int(rng.integers(3, 7))):
            n = int(rng.uniform(0.05, 0.12) * SR)
            tt = tax(n)
            f = base * (1 + 0.25 * np.sin(TAU * rng.uniform(8, 18) * tt)) * (1 + rng.uniform(-0.3, 0.5) * tt / tt[-1])
            ch = np.sin(TAU * np.cumsum(f) / SR) * np.sin(np.pi * tt / tt[-1]) ** 2
            mx.add(at + c * rng.uniform(0.09, 0.16), ch * 0.05, pan)
    # Kalimba: a two-bar figure, varied.
    scale = [57, 60, 62, 64, 67, 69, 72, 74, 76]
    fig = [0, 2, 4, 5, 4, 2, 3, 1, 0, 2, 4, 6, 5, 4, 2, 4]
    for bar in range(4, bars):
        for i in range(8):
            j = fig[((bar % 2) * 8 + i)] + (1 if bar % 8 >= 4 and i % 4 == 3 else 0)
            m = scale[min(j, len(scale) - 1)]
            at = bar * 4 * beat + i * beat * 0.5
            mx.add(at, kalimba(float(hz(m))) * (0.11 if i % 2 == 0 else 0.07), 0.35 + 0.3 * (i % 2))
            mx.add(at + beat * 0.75, kalimba(float(hz(m))) * 0.03, 0.8)
    # Hand drums: low on 1 and the and-of-2, a tap on 3, shaker eighths.
    for bar in range(bars):
        b0 = bar * 4 * beat
        mx.add(b0, boom(rng, 0.6, 130, 95, 0.18, 0.3) * 0.5, 0.45)
        mx.add(b0 + 1.5 * beat, boom(rng, 0.5, 150, 110, 0.14, 0.3) * 0.35, 0.55)
        mx.add(b0 + 2 * beat, noise_hit(rng, 0.12, 300, 2500, 0.03) * 0.12, 0.6)
        for e in range(8):
            mx.add(b0 + e * beat * 0.5, noise_hit(rng, 0.06, 5000, 12000, 0.012) * (0.06 if e % 2 else 0.04), 0.7)
    chords = [[60, 64, 67, 71], [57, 60, 64, 67], [53, 57, 60, 64], [55, 59, 62, 64]]
    span = 2 * 4 * beat
    for i in range(bars // 2):
        mx.add(i * span, pad(rng, chords[i % 4], span + 1.0, cutoff=900, attack=1.5, release=1.5) * 0.2, 0.5)
    reverb(mx, ir(rng, 3.0, 2.2, 1.2, 0.015), 0.3)
    return master(mx, 1.0)


def t_void():
    """The PS2's boot, remembered: a sub drone, glass bells in E Lydian through
    a long room, a whoosh that rises into a boom every 16 s, and a shimmer.
    80 s."""
    mx = Mix(80.0, 7004)
    rng = mx.rng
    N = mx.N
    t = tax(N)
    sub = (np.sin(TAU * 41.2 * t) + 0.5 * np.sin(TAU * 82.4 * 1.002 * t)) * (0.7 + 0.3 * np.sin(TAU * t / 20.0))
    mx.add(0, sub * 0.07, 0.5)
    lyd = [64, 66, 68, 70, 71, 73, 75]
    motif = [(0, 4), (2, 4), (6, 8), (4, 4), (7, 6), (3, 10)]
    at = 2.0
    while at < N / SR - 1:
        for (deg, gap) in motif:
            m = lyd[deg % 7] + 12 * (1 + deg // 7) + 12
            # 2026-09-30: -8 dB and a softer strike.  They were a third of the
            # track's energy, at 1-3 kHz, and the RMS master is led by the sub,
            # so this was the loudest track by ear (-20 dB(A) against -23..-28).
            mx.add(at, bell(float(hz(m)), 5.0, 3.5, 1.5, 2.8) * 0.07, rng.uniform(0.25, 0.75))
            mx.add(at + 0.37, bell(float(hz(m)), 5.0, 3.5, 1.5, 2.8) * 0.02, rng.uniform(0.2, 0.8))
            at += gap * 0.5
    for k in range(5):
        at = k * 16.0
        n = int(4.0 * SR)
        tt = tax(n)
        sweep = rising_noise(rng, n, 180.0, 4200.0) * (tt / tt[-1]) ** 2.0
        mx.add2(at, sweep * 0.08, np.roll(sweep, 300) * 0.08)
        mx.add(at + 4.0, boom(rng, 5.0, 58, 34, 1.8, 0.2) * 0.6, 0.5)
    sh = np.zeros(N)
    for m in [88, 92, 95, 99]:
        sh += np.sin(TAU * float(hz(m)) * t + rng.uniform(0, TAU)) * (0.5 + 0.5 * np.sin(TAU * t / rng.uniform(5, 9)))
    mx.add2(0, sh * 0.006, np.roll(sh, 2000) * 0.006)
    reverb(mx, ir(rng, 8.0, 7.0, 4.0, 0.06), 0.6, 0.8)
    return master(mx, 1.0)


def t_drive():
    """Synthwave, 120 BPM, A minor: intro, main with lead, break with arp, main.
    48 bars = 96 s."""
    bpm = 120.0
    beat = 60.0 / bpm
    bars = 48
    mx = Mix(bars * 4 * beat, 7005)
    rng = mx.rng
    N = mx.N
    prog = [(45, [57, 60, 64]), (41, [53, 57, 60]), (48, [55, 60, 64]), (43, [55, 59, 62])]
    k = kick()
    snare_t = np.sin(TAU * 185 * tax(int(0.25 * SR))) * np.exp(-tax(int(0.25 * SR)) / 0.05)

    def section(bar):
        return 'intro' if bar < 8 else ('break' if 24 <= bar < 32 else 'main')

    for bar in range(bars):
        b0 = bar * 4 * beat
        sect = section(bar)
        root, ch = prog[(bar // 2) % 4]
        notes = [(b0 + s * beat / 4, beat / 4 * 0.9, root + (12 if s % 2 else 0), 0.9 if s % 4 == 0 else 0.7) for s in range(16)]
        if sect != 'break':
            mx.add(0, saw_notes(rng, notes, N, 1800, 220, 0.09, 24) * 0.11, 0.5)
        if bar % 2 == 0:
            p = pad(rng, [m + 12 for m in ch] + [ch[0] + 24], 8 * beat + 0.3, cutoff=2400, attack=0.3, release=0.4)
            mx.add(b0, p * 0.22, 0.5)
    # Sidechain pump on the pads and bass, keyed to the kick; the drums go
    # in after it, so the kick itself is not ducked.
    tb = (tax(N) % beat)
    pump = 1 - 0.5 * np.exp(-tb / 0.12)
    mx.L *= pump
    mx.R *= pump
    for bar in range(bars):
        b0 = bar * 4 * beat
        sect = section(bar)
        for q in range(4):
            if sect != 'break' or q == 0:
                mx.add(b0 + q * beat, k * 0.7, 0.5)
            if q % 2 == 1 and sect != 'intro':
                sn = noise_hit(rng, 0.25, 1200, 9000, 0.07) * 0.45 + snare_t * 0.3
                mx.add(b0 + q * beat, sn * 0.7, 0.5)
            for s in range(4):
                if sect != 'break' or s % 2:
                    mx.add(b0 + q * beat + s * beat / 4, noise_hit(rng, 0.04, 7000, 16000, 0.01) * (0.14 if s % 2 else 0.09), 0.65)
    # Lead melody over the mains: an original eight-bar tune, twice per section.
    tune = [(0, 76, 1.5), (1.5, 74, 0.5), (2, 72, 1), (3, 74, 1), (4, 76, 2), (6, 79, 1), (7, 76, 1),
            (8, 77, 1.5), (9.5, 76, 0.5), (10, 74, 1), (11, 72, 1), (12, 72, 3), (15, 71, 1),
            (16, 72, 1.5), (17.5, 74, 0.5), (18, 76, 1), (19, 79, 1), (20, 81, 2), (22, 79, 1), (23, 76, 1),
            (24, 77, 1.5), (25.5, 76, 0.5), (26, 74, 1), (27, 71, 1), (28, 69, 4)]
    lead = np.zeros(N)
    for start in list(range(8, 24, 8)) + list(range(32, 48, 8)):
        for (bt, m, d) in tune:
            at = start * 4 * beat + bt * beat
            n = int(d * beat * SR)
            tt = tax(n)
            f = float(hz(m)) * (1 + 0.005 * np.sin(TAU * 5.5 * tt) * np.clip(tt / 0.3, 0, 1))
            ph = TAU * np.cumsum(f) / SR
            x = sum(np.sin(h * ph) / h for h in (1, 3, 5, 7, 9)) * env(n, 0.01, 0.08)
            i = int(at * SR) % N
            j = min(n, N - i)
            lead[i:i + j] += x[:j]
    mx.add(0, lead * 0.07, 0.45)
    mx.add(3 * beat / 4, lead * 0.03, 0.8)
    arp = [0, 3, 7, 12, 7, 3]
    for bar in range(24, 32):
        root, ch = prog[(bar // 2) % 4]
        for s in range(16):
            m = ch[0] + 12 + arp[s % len(arp)]
            mx.add(bar * 4 * beat + s * beat / 4, bell(float(hz(m)), 0.6, 2.0, 1.0, 0.25) * 0.06, 0.3 + 0.4 * (s % 2))
    reverb(mx, ir(rng, 2.5, 1.8, 0.9, 0.012), 0.22)
    return master(mx, 1.0)


# ---------------------------------------------------------------- effects --
def one_shot(secs, seed):
    return Mix(secs, seed)


def fx_room(mx, rt, wet):
    reverb(mx, ir(mx.rng, rt * 1.2, rt, rt * 0.55, 0.02), wet)


def mono(mx, peak=0.7):
    x = (mx.L + mx.R) * 0.5
    # The effects are one-shots: no wrap.  Their buffers are sized so the tail
    # has died before it could come round.
    return x / (np.abs(x).max() + 1e-9) * peak


def sfx_all():
    out = {}
    m = one_shot(1.4, 8001)
    m.add(0.0, bell(2200.0, 0.4, 2.76, 1.1, 0.12, 0.05) * 0.5, 0.5)
    fx_room(m, 0.9, 0.35)
    out['hover'] = mono(m, 0.35)

    m = one_shot(3.2, 8002)
    m.add(0.0, boom(m.rng, 0.8, 120, 55, 0.25, 0.3) * 0.8, 0.5)
    m.add(0.01, bell(880.0, 1.6, 3.5, 1.6, 0.6) * 0.25 + bell(1320.0, 1.6, 3.5, 1.2, 0.5) * 0.15, 0.5)
    fx_room(m, 2.4, 0.5)
    out['click'] = mono(m, 0.6)

    m = one_shot(3.0, 8003)
    m.add(0.0, bell(1320.0, 1.0, 2.0, 1.0, 0.35) * 0.3, 0.5)
    m.add(0.12, bell(880.0, 1.4, 2.0, 1.0, 0.5) * 0.3, 0.5)
    fx_room(m, 2.2, 0.5)
    out['back'] = mono(m, 0.5)

    m = one_shot(3.4, 8004)
    n = int(2.2 * SR)
    tt = tax(n)
    nz = m.rng.normal(0, 1, n)
    X = np.fft.rfft(nz)
    f = np.fft.rfftfreq(n, 1 / SR)
    x = np.zeros(n)
    for c in np.linspace(0, 1, 12):
        band = np.fft.irfft(X * np.exp(-((np.log(f + 1) - np.log(250 + 2600 * np.sin(np.pi * c))) ** 2) / 0.35), n)
        w = np.exp(-((tt / tt[-1] - c) ** 2) / 0.012)
        x += band * w
    x *= np.sin(np.pi * tt / tt[-1])
    m.add(0.0, x * 0.3, 0.5)
    m.add(0.0, boom(m.rng, 2.0, 50, 36, 0.8, 0.0) * 0.2, 0.5)
    fx_room(m, 1.8, 0.4)
    out['whoosh'] = mono(m, 0.5)

    m = one_shot(6.0, 8005)
    n = int(2.6 * SR)
    tt = tax(n)
    nz = m.rng.normal(0, 1, n)
    X = np.fft.rfft(nz)
    f = np.fft.rfftfreq(n, 1 / SR)
    x = np.zeros(n)
    for c in np.linspace(0, 1, 16):
        band = np.fft.irfft(X * np.exp(-((np.log(f + 1) - np.log(200 + 5000 * c * c)) ** 2) / 0.3), n)
        x += band * np.exp(-((tt / tt[-1] - c) ** 2) / 0.01)
    x *= (tt / tt[-1]) ** 1.5
    m.add(0.0, x * 0.3, 0.5)
    m.add(1.2, boom(m.rng, 4.0, 60, 30, 1.4, 0.3) * 0.7, 0.5)
    m.add(1.25, bell(1760.0, 3.0, 3.5, 2.0, 1.5) * 0.12, 0.5)
    fx_room(m, 3.0, 0.55)
    out['dive'] = mono(m, 0.65)
    return out


TRACKS = {
    'monolith': t_monolith,
    'vessel': t_vessel,
    'canopy': t_canopy,
    'void': t_void,
    'drive': t_drive,
}


def main(argv):
    want = argv or (['dream'] + list(TRACKS) + ['sfx'])
    for name in want:
        if name == 'dream':
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import mkmenumusic
            mkmenumusic.main(os.path.join(MUSIC, 'ftesurf_dream.wav'))
        elif name == 'sfx':
            for k, x in sfx_all().items():
                write(os.path.join(SFX, k + '.wav'), x)
        elif name in TRACKS:
            L, R = TRACKS[name]()
            write(os.path.join(MUSIC, f'ftesurf_{name}.wav'), L, R)
        else:
            sys.exit(f'unknown: {name} (have: dream {" ".join(TRACKS)} sfx)')


if __name__ == '__main__':
    main(sys.argv[1:])
