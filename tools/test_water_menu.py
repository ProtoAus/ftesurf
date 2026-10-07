#!/usr/bin/env python3
"""Source contracts for P523/P528; runtime needs separate old/new native controls.
Run: python tools/test_water_menu.py --engine <FTE checkout>
"""
from pathlib import Path
import argparse
import re

ROOT = Path(__file__).resolve().parents[1]


def contracts(product: Path, engine: Path) -> list[str]:
    failures = []

    def check(condition: bool, description: str) -> None:
        if not condition:
            failures.append(description)

    menu = (product / "src/client/cl_gfx.qc").read_text(encoding="utf-8")
    rows = {
        int(number): definition.split("|")
        for number, definition in re.findall(
            r'if \(row == (\d+)\)\s+return "([^"\n]+)";', menu
        )
    }
    water_defs = re.findall(r'return "(hl2_water\|[^"\n]+)";', menu)
    check(len(water_defs) == 2, "capability selects exactly budget and legacy rows")
    if water_defs:
        rows[1] = water_defs[0].split("|")
    check(set(rows) == set(range(1, 29)), "all 28 stable row numbers")
    for number, fields in rows.items():
        check(len(fields) == 5, f"row {number}: five fields")
        if len(fields) != 5:
            continue
        values, names = fields[2].split(), fields[3].split(";")
        check(len(values) == len(names), f"row {number}: value/name counts")
        check(all(names), f"row {number}: nonempty names")
        check(fields[4] in ("", "*"), f"row {number}: application marker")
    water = rows.get(1, ["", "", "", "", "*"])
    check(water[0] == "hl2_water", "water cvar")
    check(water[2].split() == ["0", "1", "2", "3", "4"], "water mode cycle")
    check(water[3].split(";")[-1] == "Budget (no captures)", "budget meaning")
    check(water[4] == "", "capable water live policy")
    legacy = water_defs[1].split("|") if len(water_defs) == 2 else []
    check(legacy == ["hl2_water", "Water", "0 1 2 3",
                     "Flat sheet;Cheap reflect;Full reflect;Dithered", "*"],
          "legacy only offers 0..3 and marks rebuild")
    check('ui_gfx_waterbudget = checkextension("FTE_CSQC_HL2_WATER_BUDGET")' in menu
          and "if (ui_gfx_waterbudget)" in menu,
          "menu gates budget on local native extension")
    check('if (cvar("hl2_water") == 4)' in menu
          and 'cvar_set("hl2_water", "3")' in menu
          and 'localcmd("flushshaders\\n")' in menu,
          "unsupported archived 4 falls back and rebuilds cached shaders")
    check(menu.count("Gfx_WaterSupport();") >= 2, "refresh at init and console entry")
    milk = (product / "src/client/cl_milk.qc").read_text(encoding="utf-8")
    restart = re.search(r'CSQC_RendererRestarted\s*=\s*\{([^}]+)\}', milk)
    check(restart is not None and "Milk_Invalidate();" in restart[1]
          and "Gfx_WaterSupport();" in restart[1],
          "renderer refresh keeps milk invalidation and refreshes water")
    glass = rows.get(2, ["", "", "", "", ""])
    check(glass[3].split(";")[0] == "Translucent", "glass 0 is translucent")
    for number in (2, 3, 4, 5, 6, 10):
        check(rows.get(number, ["", "", "", "", ""])[4] == "*",
              f"row {number}: masked material flag not called live")
    check("retry may reuse cached data" in menu, "retry cache caveat")
    check("all instant" not in menu, "no blanket instant claim")
    check('localcmd(sprintf("seta %s %s\\n", Gfx_Cvar(row), argv(i)))' in menu,
          "menu choices still archive via seta")

    renderer = (engine / "engine/client/renderer.c").read_text(encoding="utf-8")
    check(bool(re.search(r'hl2_water_shaderpolicy\s*=\s*CVARFD\("hl2_water", "3", CVAR_SHADERSYSTEM', renderer)),
          "renderer owns default 3 and narrow shader-policy opt-in")
    check("Cvar_Register (&hl2_water_shaderpolicy," in renderer,
          "renderer registers water policy")
    ext = (engine / "engine/common/pr_bgcmd.c").read_text(encoding="utf-8")
    check('{"FTE_CSQC_HL2_WATER_BUDGET", check_hl2_waterbudget' in ext
          and "return R_HL2WaterBudgetSupported();" in ext,
          "native extension uses renderer predicate")
    shader = (engine / "engine/gl/gl_shader.c").read_text(encoding="utf-8")
    predicate = re.search(r'R_HL2WaterBudgetSupported\(void\)\s*\{(.*?)\n\}', shader, re.S)
    body = predicate[1] if predicate else ""
    check("qrenderer != QR_OPENGL || !sh_config.progs_supported" in body
          and "materialloader[l].funcs->builtinshaders" in body
          and 'strcmp(progs->name, "vmt/waterbudget")' in body,
          "programmable OpenGL and embedded plugin budget source required")
    check("Cvar_" not in body and bool(body), "predicate not spoofed by a cvar")
    plugin = (engine / "engine/common/plugin.c").read_text(encoding="utf-8")
    mask = re.search(r'^#define PLUG_CVAR_FLAGS \(([^)]+)\)', plugin, re.M)
    check(mask is not None and "CVAR_SHADERSYSTEM" not in mask[1]
          and "flags&PLUG_CVAR_FLAGS" in plugin,
          "do not widen the general plugin shader flag")

    budget_path = engine / "plugins/hl2/glsl/vmt/waterbudget.glsl"
    check(budget_path.is_file(), "budget shader exists")
    budget = budget_path.read_text(encoding="utf-8") if budget_path.is_file() else ""
    check("!!samps =BUMP normalmap" in budget, "normal-map optional permutation")
    check("!!samps =REFLECTCUBEMASK reflectcube" in budget, "cubemap optional permutation")
    check(not re.search(r'!!samps[^\n]*(?:refract|depth|reflect=)', budget),
          "budget declares no scene/depth sampler")
    check("textureCube(s_reflectcube, reflect(-viewdir, normal))" in budget
          and "viewdir = normalize(eye)" in budget,
          "view-dependent baked reflection")
    vmt = (engine / "plugins/hl2/mat_vmt.c").read_text(encoding="utf-8")
    check("wmode == 4" in vmt and "vmt/waterbudget" in vmt,
          "budget generator branch")
    make = (engine / "plugins/hl2/Makefile").read_text(encoding="utf-8")
    embedded = (engine / "plugins/hl2/mat_vmt_progs.h").read_text(encoding="utf-8")
    check(bool(re.search(r'^VMTPROGSBASE=.*\bwaterbudget\b', make, re.M)),
          "generator includes budget shader")
    check('"vmt/waterbudget"' in embedded, "generated header embeds budget shader")
    check("FTESurf-private" not in embedded, "generated header has no private build path")
    return failures


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--product", type=Path, default=ROOT)
    args = parser.parse_args()
    problems = contracts(args.product, args.engine)
    for problem in problems:
        print("FAIL:", problem)
    print(f"water/menu source contracts: {len(problems)} failed")
    raise SystemExit(bool(problems))
