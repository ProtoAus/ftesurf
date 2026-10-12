"""Grade SSQC brush alpha fixture logs, not pixels. No game launch.

Run source_brush_alpha.cfg in the server console after surf_kitsune spawn.
For a dedicated server this must be a SERVER exec, not a client exec.
Use a fresh log. Missing/duplicate phases fail (not measured), never pass.
Matched-camera pixels and natural button outputs are separate runtime gates.
"""
import re
import sys
import unittest
from pathlib import Path

MODELS = {f"*{n}" for n in (12, 35, 36, 37, 38, 43, 44, 45, 46, 47, 48, 49)}
ROW = re.compile(r"brush-test: step (\d+) model (\S+) mode (\d+) amt ([\d.-]+) "
                 r"alpha ([\d.-]+) solid (\d+) hidden (\d+) disabled (\d+)")
INITIAL = re.compile(r"brush-test: control-initial (\d+) mode (\d+) alpha ([\d.-]+) solid (\d+) hidden (\d+)")


def grade(text):
    rows = {}
    for match in ROW.finditer(text):
        step, model, mode, amt, alpha, solid, hidden, disabled = match.groups()
        key = (int(step), model)
        if key in rows:
            raise AssertionError(f"duplicate measurement {key}; use a fresh log")
        rows[key] = tuple(map(float, (mode, amt, alpha, solid, hidden, disabled)))
    expected_keys = {(step, model) for step in range(1, 10) for model in MODELS}
    expected_keys |= {(step, "*48") for step in range(10, 13)}
    assert set(rows) == expected_keys, f"not measured: missing {expected_keys - set(rows)}, extra {set(rows) - expected_keys}"
    for (step, model), values in rows.items():
        mode, amt, alpha, solid, hidden, disabled = values
        if step < 10:
            expected_amt = 75 if step in (2, 5, 6) else 0
            expected_disabled = int(step in (4, 5, 8))
            expected_hidden = int(expected_disabled or expected_amt == 0)
            expected_solid = 0 if expected_disabled else 4  # SOLID_BSP
            assert values[:2] == (4, expected_amt), (step, model, values)
            assert abs(alpha - expected_amt / 255) < 0.000001, (step, model, values)
            assert (solid, hidden, disabled) == (expected_solid, expected_hidden, expected_disabled), (step, model, values)
        else:
            assert mode == (10 if step == 12 else 0), (step, values)
            assert amt == (75 if step == 12 else 0), (step, values)
            assert alpha == (0 if step == 12 else 1), (step, values)
            assert (solid, hidden, disabled) == (4, int(step == 12), 0), (step, values)
    initial = [tuple(map(float, m.groups())) for m in INITIAL.finditer(text)]
    assert sorted(initial) == [(10, 0, 1, 4, 0), (11, 0, 1, 4, 0), (12, 10, 0, 4, 1)], initial
    return len(rows)


def fixture():
    lines = []
    for step in range(1, 13):
        for model in sorted(MODELS if step < 10 else {"*48"}):
            mode = 10 if step == 12 else 4 if step < 10 else 0
            amt = 75 if step in (2, 5, 6, 12) else 0
            disabled = int(step in (4, 5, 8))
            alpha = amt / 255 if step < 10 else 0 if step == 12 else 1
            hidden = int(disabled or (step < 10 and not amt) or step == 12)
            solid = 0 if disabled else 4
            lines.append(f"brush-test: step {step} model {model} mode {mode} amt {amt} alpha {alpha:.6f} solid {solid} hidden {hidden} disabled {disabled}")
    lines += [f"brush-test: control-initial {s} mode {m} alpha {a:.6f} solid 4 hidden {h}" for s, m, a, h in ((10, 0, 1, 0), (11, 0, 1, 0), (12, 10, 0, 1))]
    return "\n".join(lines)


class TestSourceBrushAlphaGrader(unittest.TestCase):
    def test_complete_state_control(self):
        self.assertEqual(grade(fixture()), 111)

    def test_missing_duplicate_and_mutant_states(self):
        text = fixture()
        mutants = ["", text + "\n" + text.splitlines()[0],
                   text.replace("hidden 1", "hidden 0", 1),
                   text.replace("solid 4", "solid 0", 1),
                   text.replace("alpha 0.294118", "alpha 1.000000", 1),
                   text.replace("mode 0 amt 0 alpha 1.000000 solid 4 hidden 0", "mode 0 amt 0 alpha 1.000000 solid 4 hidden 1", 1)]
        for step in (5, 9, 12):
            mutants.append(re.sub(rf"(brush-test: step {step} model \S+ .* hidden )1", r"\g<1>0", text, count=1))
        for mutant in mutants:
            self.assertNotEqual(mutant, text)
            with self.subTest(mutant=mutant[:80]):
                with self.assertRaises(AssertionError):
                    grade(mutant)


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] != "--self-test":
        print(f"PASS: {grade(Path(sys.argv[1]).read_text(errors='replace'))} brush state measurements (pixels not graded)")
    else:
        unittest.main(argv=[sys.argv[0]])
