#!/usr/bin/env python3
"""Producer/packaging checks and falsifiers for the SUI grader, not runtime proof."""
import contextlib
import io
from pathlib import Path
import shutil
import tempfile
import unittest
from PIL import Image
import shipguard
import test_ui_modern as driver
import ui_assets


class UiTests(unittest.TestCase):
    def test_mask(self):
        im = ui_assets.roundmask()
        self.assertEqual(im.size, (32, 32))
        self.assertEqual(im.mode, "RGBA")
        alpha = im.getchannel("A")
        self.assertEqual(alpha.getpixel((0, 0)), 0)
        self.assertEqual(alpha.getpixel((16, 0)), 255)
        self.assertEqual(alpha.getpixel((16, 16)), 255)
        self.assertTrue(any(0 < value < 255 for value in alpha.tobytes()))
        self.assertEqual(im.tobytes(), im.transpose(Image.Transpose.FLIP_LEFT_RIGHT).tobytes())

    def test_real_ship_entry_and_mutant(self):
        release = (driver.ROOT / "src/release/release.ps1").read_text(encoding="utf-8-sig")
        files = shipguard.ps_strings(shipguard.ps_array(release, "ShipGameFiles"))
        name = "ftesurf/gfx/ui/roundmask.png"
        self.assertIn(name, files)
        live = {value.removeprefix("ftesurf/") for value in files}
        self.assertEqual(shipguard.classify(name.removeprefix("ftesurf/"), "drawsubpic", live, set())[0], "SHIPPED")
        live.remove(name.removeprefix("ftesurf/"))
        self.assertEqual(shipguard.classify(name.removeprefix("ftesurf/"), "drawsubpic", live, set())[0], "MISS")

    def test_cfg_guard(self):
        import cfgguard
        text = (driver.ROOT / "ftesurf/cfg/test/ui_modern.cfg").read_text()
        cmds = [(n, command.strip()) for n, line in enumerate(text.splitlines(), 1)
                for command in line.split("//", 1)[0].split(";") if command.strip()]
        guard = next(n for n, cmd in cmds if cfgguard.GUARD.match(cmd))
        reach = next(n for n, cmd in cmds if cfgguard.REACH.match(cmd))
        self.assertLess(guard, reach)

    def fixture(self, rig):
        game = rig / "ftesurf"
        (game / "logs").mkdir(parents=True)
        (game / "screenshots").mkdir()
        (game / "ftesurf.cfg").write_text("// disposable saved config\n")
        names = ("A", "B", "delayed", "visible", "cached", "held", "action", "focuslost", "focusback", "keyboardlost", "keyboardback", "edge", "closed1", "closed2", "done")
        lines = []
        for name in names:
            lines.append(f"=== sui {name} ===")
            if name == "done":
                continue
            visible = int(name in ("visible", "cached", "focusback", "keyboardback", "edge"))
            # Stage A is the closed editor; the selection click lands in `action`.
            shut = name == "A" or name.startswith("closed")
            opened = int(name != "A")
            picked = -1 if name in ("A", "B", "delayed", "visible", "cached", "held") else 2
            lines += [f"sui_probe round {opened*2} asset {opened} tip {visible} lines 2 wraps 1",
                      f"sui_work frames 100 quads 200 screen 100 100 focused 1",
                      "sui_font native 8 ratio 1 1 glyph 8 8 calls 50",
                      "sui_tip [he_fontfx] 40 40 30 20",
                      f"sui_panel open {int(not shut)} selected {picked} dirty 0 cursor {0 if shut else 4} held 0",
                      "sui_tip_line 0 width 20 limit 50", "sui_tip_line 1 width 30 limit 50"]
            if name == "B":
                lines += ["sui_element [he_panel] 10 10 20 20"]
            if name == "closed1":
                lines += ["hud_edit: layout saved"]
        log = game / "logs/ui_modern.log"
        log.write_text("\n".join(lines) + "\n")
        for name in ("sui_A", "sui_A_repeat", "sui_B", "sui_B_repeat", "sui_tip", "sui_edge"):
            im = Image.new("RGB", (100, 100))
            im.paste((20, 20, 20) if name.startswith("sui_A") else (40, 40, 40), (10, 10, 30, 30))
            im.save(game / "screenshots" / (name + ".png"))
        return log

    def graded(self, rig):
        with contextlib.redirect_stdout(io.StringIO()):
            return driver.grade(rig)

    def test_good_and_falsified_tip(self):
        with tempfile.TemporaryDirectory(prefix="sui-grader-") as tmp:
            rig = Path(tmp)
            log = self.fixture(rig)
            self.assertEqual(self.graded(rig), 0)
            text = log.read_text()
            bad = text.replace("=== sui visible ===\nsui_probe round 2 asset 1 tip 1", "=== sui visible ===\nsui_probe round 2 asset 1 tip 0")
            self.assertNotEqual(bad, text)
            log.write_text(bad)
            self.assertEqual(self.graded(rig), 1)

    def test_selection_that_did_not_move(self):
        with tempfile.TemporaryDirectory(prefix="sui-grader-") as tmp:
            rig = Path(tmp)
            log = self.fixture(rig)
            text = log.read_text()
            start = text.index("=== sui action ===")
            bad = text[:start] + text[start:].replace("selected 2", "selected -1", 1)
            self.assertNotEqual(bad, text)
            log.write_text(bad)
            self.assertEqual(self.graded(rig), 1)

    def test_editor_that_drew_nothing(self):
        with tempfile.TemporaryDirectory(prefix="sui-grader-") as tmp:
            rig = Path(tmp)
            self.fixture(rig)
            for name in ("sui_B", "sui_B_repeat"):
                shutil.copyfile(rig / "ftesurf/screenshots/sui_A.png", rig / "ftesurf/screenshots" / (name + ".png"))
            self.assertEqual(self.graded(rig), 1)

    def test_missing_probes_are_not_a_pass(self):
        with tempfile.TemporaryDirectory(prefix="sui-grader-") as tmp:
            rig = Path(tmp)
            log = self.fixture(rig)
            log.write_text("\n".join(line for line in log.read_text().splitlines() if not line.startswith("sui_probe")))
            self.assertEqual(self.graded(rig), 2)

    def test_non_native_font_mutant(self):
        with tempfile.TemporaryDirectory(prefix="sui-grader-") as tmp:
            rig = Path(tmp)
            log = self.fixture(rig)
            log.write_text(log.read_text().replace("sui_font native 8", "sui_font native 9"))
            self.assertEqual(self.graded(rig), 1)

    def test_closed_work_mutant(self):
        with tempfile.TemporaryDirectory(prefix="sui-grader-") as tmp:
            rig = Path(tmp)
            log = self.fixture(rig)
            text = log.read_text()
            start = text.index("=== sui closed2 ===")
            log.write_text(text[:start] + text[start:].replace("frames 100", "frames 101", 1))
            self.assertEqual(self.graded(rig), 1)


if __name__ == "__main__":
    unittest.main()
