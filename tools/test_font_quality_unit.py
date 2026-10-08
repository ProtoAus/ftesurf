#!/usr/bin/env python3
"""Reader falsifiers: synthetic pixels/logs are controls, not runtime evidence."""
import unittest
from PIL import Image, ImageDraw
import font_quality as fq


def log_text():
    lines = []
    for phase, mode in zip(fq.PHASES, fq.MODES):
        lines.append(f"FQ_PHASE {phase}")
        for side in range(2):
            for face in range(3):
                for rung in range(4):
                    x, y = fq.sample_box(side, face, rung)[:2]
                    pixels = fq.SIZES[face][rung] + (.75 if mode else 0)
                    lines.append(f"fq_row {side} {face} {rung} slot {face + 1} physical {pixels} {pixels} origin {x} {y}")
        lines += [f"fq_state mode {mode} frames 10 loads 1 ready 1 calls 24",
                  "fq_native tries 1 0 1 1",
                  "fq_screen physical 1280 720 virtual 1280 720 ratio 1 1",
                  "fq_settings linear 1 mono 0 outline 0 smaller 0 gamma 1 contrast 1 srgb 0"]
    return "\n".join(lines + ["FQ_END"]) + "\n"


def images():
    baseline = Image.new("RGB", fq.SIZE, (20, 20, 20))
    draw = ImageDraw.Draw(baseline)
    draw.rectangle((16, 16, 623, 703), fill=(0, 0, 0))
    draw.rectangle((656, 16, 1263, 703), fill=(255, 255, 255))
    for box, colour in fq.MARKERS:
        draw.rectangle((box[0], box[1], box[2] - 1, box[3] - 1), fill=colour)
    for side in range(2):
        for face in range(3):
            for rung in range(4):
                x, y = fq.sample_box(side, face, rung)[:2]
                for level in range(3):
                    grey = 40 + 45 * level + face * 10
                    draw.rectangle((x + level * 14, y + 2, x + level * 14 + 9, y + 12), fill=(grey,) * 3)
        x = 32 + side * 640
        draw.rectangle((x, 652, x + 20, 660), fill=(127,) * 3)
    resampled = baseline.copy()
    draw = ImageDraw.Draw(resampled)
    for side in range(2):
        for face in range(3):
            for rung in range(4):
                x, y = fq.sample_box(side, face, rung)[:2]
                draw.rectangle((x + 60, y + 2, x + 70, y + 12), fill=(90,) * 3)
    return dict(baseline=baseline, repeat=baseline.copy(), resampled=resampled,
                menu_reload=baseline.copy(), renderer_reload=baseline.copy())


class LogControls(unittest.TestCase):
    def test_acted_log(self):
        self.assertEqual(fq.assess_log(log_text(), 1, 1), [])

    def test_silence_and_partial_end(self):
        self.assertTrue(fq.assess_log("", 1, 1))
        self.assertTrue(fq.assess_log(log_text().replace("FQ_END", ""), 1, 1))

    def test_independent_state_mutants(self):
        for old, new in (("loads 1", "loads 2"), ("ready 1", "ready 0"),
                         ("calls 24", "calls 0"), ("frames 10", "frames 1"),
                         ("linear 1", "linear 0"), ("mono 0", "mono 1"),
                         ("physical 8 8 origin", "physical 9 9 origin"),
                         ("origin 32 72", "origin 32.5 72"),
                         ("fq_native tries 1 0 1 1", "fq_native tries 2 0 1 1"),
                         ("fq_native tries 1 0 1 1", "fq_native tries 0 0 0 0")):
            with self.subTest(mutant=new):
                self.assertTrue(fq.assess_log(log_text().replace(old, new, 1), 1, 1))

    def test_scale_must_act(self):
        self.assertTrue(fq.assess_log(log_text(), 2, 1))
        self.assertTrue(fq.assess_log(log_text().replace("ratio 1 1", "ratio 2 2"), 1, 1))

    def test_duplicate_or_absent_row(self):
        text = log_text()
        row = next(line for line in text.splitlines() if line.startswith("fq_row"))
        self.assertTrue(fq.assess_log(text.replace(row + "\n", "", 1), 1, 1))
        self.assertTrue(fq.assess_log(text.replace(row, row + "\n" + row, 1), 1, 1))

    def test_runtime_error(self):
        self.assertTrue(fq.assess_log(log_text() + 'Unknown command "fq_probe"\n', 1, 1))


class PixelControls(unittest.TestCase):
    def test_acted_images(self):
        errors, samples = fq.assess_images(images())
        self.assertEqual(errors, [])
        self.assertEqual(len(samples), 24)

    def test_missing_and_dimensions(self):
        sample = images()
        del sample["repeat"]
        self.assertTrue(fq.assess_images(sample)[0])
        sample = images()
        sample["baseline"] = sample["baseline"].resize((640, 360))
        self.assertTrue(fq.assess_images(sample)[0])

    def test_marker_inversion(self):
        sample = images()
        sample["baseline"].paste((0, 255, 255), fq.MARKERS[0][0])
        self.assertTrue(fq.assess_images(sample)[0])

    def test_blank_and_bitmap(self):
        for fill in (0, 255):
            sample = images()
            sample["baseline"].paste((fill,) * 3, fq.sample_box(0, 0, 0))
            self.assertTrue(fq.assess_images(sample)[0])

    def test_default_font_collapse(self):
        sample = images()
        box = fq.sample_box(0, 0, 2)
        other = fq.sample_box(0, 1, 2)
        sample["baseline"].paste(sample["baseline"].crop(box), other)
        self.assertTrue(any("collapsed" in e for e in fq.assess_images(sample)[0]))

    def test_coloured_fringe(self):
        sample = images()
        x, y = fq.sample_box(0, 0, 0)[:2]
        sample["baseline"].putpixel((x + 1, y + 2), (70, 80, 90))
        self.assertTrue(any("non-neutral" in e for e in fq.assess_images(sample)[0]))

    def test_half_alpha_is_not_double_premultiplied(self):
        sample = images()
        sample["baseline"].paste((63, 63, 63), (32, 650, 608, 674))
        self.assertTrue(any("half-alpha" in e for e in fq.assess_images(sample)[0]))

    def test_resampling_must_act(self):
        sample = images()
        sample["resampled"] = sample["baseline"].copy()
        self.assertTrue(any("did not visibly act" in e for e in fq.assess_images(sample)[0]))

    def test_lifecycle_must_be_stable(self):
        for phase in ("menu_reload", "renderer_reload"):
            sample = images()
            sample[phase].putpixel((33, 74), (255, 255, 255))
            self.assertTrue(any(phase in e for e in fq.assess_images(sample)[0]))

    def test_repeat_must_be_stable(self):
        sample = images()
        sample["repeat"].putpixel((33, 74), (255, 255, 255))
        self.assertTrue(any("repeat" in e for e in fq.assess_images(sample)[0]))


if __name__ == "__main__":
    unittest.main()
