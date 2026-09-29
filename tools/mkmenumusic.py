#!/usr/bin/env python3
"""mkmenumusic.py -- FTESurf's menu loop, synthesised.  Patch 467.

Writes ftesurf/music/ftesurf_dream.wav: 32 bars at 100 BPM (76.8 s), 44.1 kHz
16-bit stereo, built so its end runs straight back into its start -- the
engine's `music` command loops a track, and the menu's autoplay picks the
first file in music/.

Generated rather than shipped as audio so there is no licence question and no
13 MB blob in git.  numpy only (no scipy): pads are additive, so "filtering" is
per-harmonic amplitude; the reverb is one circular FFT convolution, which is
also what makes the loop seamless (the tail wraps onto the head).

The kick lands on every beat on purpose: the visualizer's beat detector
(snd_getvis) keys on bass onsets, and a menu track that never gives it one
leaves the space looking like it is ignoring the music.

    python tools/mkmenumusic.py [out.wav]
"""
import sys
import wave
import numpy as np

SR = 44100
BPM = 100.0
BEAT = 60.0 / BPM
BAR = 4 * BEAT
NBARS = 32
N = int(round(NBARS * BAR * SR))
rng = np.random.default_rng(467)

# vi - IV - I - V in D: Bm9, Gmaj7, Dmaj7, A6 -- two bars each.
CHORDS = [[59, 62, 66, 69, 73], [55, 59, 62, 66, 69], [50, 54, 57, 61, 64], [57, 61, 64, 66, 69]]
ROOTS = [35, 31, 38, 33]


def hz(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


def add(buf, start, sig):
    """Mix sig into buf at start, wrapping past the end (the loop is circular)."""
    start %= N
    n = len(sig)
    first = min(n, N - start)
    buf[start:start + first] += sig[:first]
    if first < n:
        buf[:n - first] += sig[first:]


def pads(L, R):
    seglen = int(2 * BAR * SR)
    over = int(0.9 * SR)
    n = seglen + 2 * over
    t = np.arange(n) / SR
    win = np.ones(n)
    ramp = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, 2 * over))
    win[:2 * over] = ramp
    win[-2 * over:] = ramp[::-1]
    for c in range(NBARS // 2):
        ch = CHORDS[c % 4]
        t0 = c * seglen / SR - over / SR
        # Brightness breathes over eight bars: how far up the harmonics reach.
        bright = 2.6 + 1.6 * np.sin(2 * np.pi * (t0 + t) / (8 * BAR))
        for vi, det in enumerate((-0.08, 0.0, 0.08)):
            v = np.zeros(n)
            for note in ch:
                f = hz(note + det)
                for k in range(1, 11):
                    if f * k > 16000:
                        break
                    v += (1.0 / k) * np.exp(-k / bright) * np.sin(2 * np.pi * f * k * t + rng.uniform(0, 2 * np.pi))
            v *= win * 0.030
            pan = (0.8, 0.5, 0.2)[vi]
            add(L, c * seglen - over, v * pan)
            add(R, c * seglen - over, v * (1 - pan))


def sub(L, R):
    seglen = int(2 * BAR * SR)
    t = np.arange(seglen) / SR
    env = np.minimum(1, t / 0.08) * np.minimum(1, (t[-1] - t) / 0.08)
    for c in range(NBARS // 2):
        s = np.sin(2 * np.pi * hz(ROOTS[c % 4]) * t) * env * 0.16
        add(L, c * seglen, s)
        add(R, c * seglen, s)


def kick(L, R):
    t = np.arange(int(0.42 * SR)) / SR
    f = 44 + 120 * np.exp(-t / 0.032)
    ph = 2 * np.pi * np.cumsum(f) / SR
    k = np.sin(ph) * np.exp(-t / 0.26) * 0.55
    k[:int(0.002 * SR)] += rng.normal(0, 0.15, int(0.002 * SR))
    for b in range(NBARS * 4):
        # First eight bars: half-time, so the loop opens gently.
        if b < 32 and b % 2:
            continue
        add(L, int(b * BEAT * SR), k)
        add(R, int(b * BEAT * SR), k)


def pump():
    """Sidechain gain: pads duck under every beat and swell back."""
    tb = (np.arange(N) / SR) % BEAT
    return 1 - 0.42 * np.exp(-tb / 0.17)


def hats(L, R):
    for closed in (True, False):
        n = int((0.05 if closed else 0.25) * SR)
        t = np.arange(n) / SR
        for s in range(NBARS * 8):
            if closed and s % 2 == 0:
                continue                        # off-beat eighths
            if not closed and s % 8 != 7:
                continue                        # the "and" of four
            x = rng.normal(0, 1, n)
            x = np.diff(np.diff(x, prepend=0), prepend=0)   # crude high-pass
            x *= np.exp(-t / (0.012 if closed else 0.08)) * (0.022 if closed else 0.018)
            lr = 0.65 if (s // 2) % 2 else 0.35
            add(L, int(s * BEAT / 2 * SR), x * lr)
            add(R, int(s * BEAT / 2 * SR), x * (1 - lr))


def arp(L, R):
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    pat = [0, 2, 4, 3, 1, 3, 4, 2]
    delay = int(0.75 * BEAT * SR)               # dotted eighth
    for s in range(NBARS * 16):
        bar = s // 16
        if bar < 4:
            continue
        ch = CHORDS[(bar // 2) % 4]
        note = ch[pat[s % 8]] + 12
        vel = 0.75 if s % 4 == 0 else 0.45
        f = hz(note)
        x = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)) * np.exp(-t / 0.22)
        x *= np.minimum(1, t / 0.004) * 0.05 * vel
        at = int(s * BEAT / 4 * SR)
        add(L, at, x * 0.6)
        add(R, at, x * 0.4)
        add(R, at + delay, x * 0.30)
        add(L, at + 2 * delay, x * 0.12)


def reverb(x, secs=2.4, wet=0.26):
    n = int(secs * SR)
    ir = rng.normal(0, 1, n) * np.exp(-np.arange(n) / (0.75 * SR))
    ir = np.convolve(ir, np.ones(24) / 24, mode="same")           # darker tail
    ir /= np.sqrt(np.sum(ir ** 2))
    pad = np.zeros(N)
    pad[:n] = ir
    y = np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(pad), N)       # circular
    return x + wet * y


def main(out=None):
    out = out or (sys.argv[1] if len(sys.argv) > 1 else "ftesurf/music/ftesurf_dream.wav")
    padL, padR = np.zeros(N), np.zeros(N)
    pads(padL, padR)
    sub(padL, padR)
    p = pump()
    L, R = padL * p, padR * p
    arp(L, R)
    hats(L, R)
    L, R = reverb(L), reverb(R)
    kick(L, R)
    peak = max(np.abs(L).max(), np.abs(R).max())
    L, R = np.tanh(L / peak * 1.3) * 0.89, np.tanh(R / peak * 1.3) * 0.89
    pcm = (np.stack([L, R], axis=1) * 32767).astype("<i2")
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"{out}: {N / SR:.1f} s, {len(pcm.tobytes()) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
