#!/usr/bin/env python3
"""Generate the project's own 32px, radius-8 nine-slice UI mask (Pillow).

--check verifies decoded pixels, independent of PNG compression versions.
No font/third-party artwork is embedded. Only this named asset is written.
"""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "ftesurf/gfx/ui/roundmask.png"


def roundmask():
    scale = 8
    alpha = Image.new("L", (32 * scale, 32 * scale), 0)
    ImageDraw.Draw(alpha).rounded_rectangle(
        (0, 0, 32 * scale - 1, 32 * scale - 1), radius=8 * scale, fill=255
    )
    alpha = alpha.resize((32, 32), Image.Resampling.LANCZOS)
    result = Image.new("RGBA", (32, 32), (255, 255, 255, 255))
    result.putalpha(alpha)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = roundmask()
    if args.check:
        if not ASSET.is_file():
            parser.error(f"missing {ASSET}")
        with Image.open(ASSET) as actual:
            if actual.convert("RGBA").tobytes() != expected.tobytes():
                parser.error("roundmask pixels differ from generator")
        print("PASS roundmask: 32x32 RGBA, radius 8, generated pixels match")
    else:
        ASSET.parent.mkdir(parents=True, exist_ok=True)
        expected.save(ASSET)
        print(f"Wrote {ASSET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
