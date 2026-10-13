#!/usr/bin/env python3
"""Generate the original Perfect-board cues (no sampled/third-party audio).

16-bit mono PCM, 22050 Hz. Rounded attack and tapered tail avoid clicks; short,
low-level partials keep these reward cues soft. Playback pitch/volume is CSQC's
job. Run --check to verify the committed assets without writing anything.
"""
from pathlib import Path
import argparse
import io
import math
import struct
import wave

RATE = 22050
ROOT = Path(__file__).resolve().parents[1]
# name: fundamental Hz, duration seconds, (ratio, amplitude, decay seconds)
TONES = {
    "dong": (392, 0.65, ((1, 0.80, 0.22), (2.02, 0.13, 0.12), (3.98, 0.07, 0.08))),
    "bong": (196, 0.70, ((1, 0.68, 0.26), (2, 0.22, 0.15), (3.02, 0.10, 0.10))),
    "bell": (784, 0.55, ((1, 0.66, 0.18), (2.76, 0.22, 0.11), (4.1, 0.12, 0.07))),
}


def render(name):
    hz, duration, partials = TONES[name]
    frames = round(duration * RATE)
    samples = []
    for i in range(frames):
        t = i / RATE
        attack = 0.5 - 0.5 * math.cos(math.pi * min(t / 0.015, 1))
        tail = 0.5 - 0.5 * math.cos(math.pi * min((frames - 1 - i) / RATE / 0.04, 1))
        value = sum(amp * math.exp(-t / decay) * math.sin(2 * math.pi * hz * ratio * t)
                    for ratio, amp, decay in partials)
        samples.append(value * attack * tail)
    scale = 0.45 * 32767 / max(map(abs, samples))
    pcm = b"".join(struct.pack("<h", round(x * scale)) for x in samples)
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(pcm)
    return out.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "ftesurf/sound/ftesurf")
    args = parser.parse_args()
    for name in TONES:
        path = args.output_dir / ("board_" + name + ".wav")
        data = render(name)
        if args.check:
            if not path.is_file() or path.read_bytes() != data:
                raise SystemExit("Missing or changed generated cue: " + str(path))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        print(f"{name}: {len(data)} bytes, {'verified' if args.check else 'generated'}")


if __name__ == "__main__":
    main()
