# Native font-quality baseline (Patch 570)

This is a **structural pixel falsifier and matched gallery**, not an automatic
beauty score. Apple-like appearance, weight/spacing judgement, real monitor/DPI
acceptance, CPU/GPU percentiles and native ImGui remain separate roadmap gates.
No outline, blur, shadow, gamma trick or multi-pass smoothing is added.

## Run

From an inspected FTESurf checkout, with Windows FTE, fteqcc and Pillow:

```text
python tools/font_quality.py --engine C:/FTESurf/ftesurf64.exe
python tools/font_quality.py --engine C:/FTESurf/ftesurf64.exe --conscale 1.5
python tools/font_quality.py --engine C:/FTESurf/ftesurf64.exe --conscale 2
python tools/font_quality.py --linear 0
python tools/font_quality.py grade <rig-dir>
python tools/font_quality.py compare <scale1-rig> <scale2-rig> --require-identical
python tools/test_font_quality_unit.py
```

Every launch makes a unique ignored `rig/font-quality-*` install and compiles a
standalone MQC gallery. No server, Steam content, live menu, personal config or
player data is used. It copies three existing OFL fonts and the selected engine;
`--compiler` selects fteqcc. Processes are owned by this launch, including timeout
termination; it never finds/kills an existing game. Do not run GUI captures
concurrently: the active window/focus is a fixture prerequisite.

The manifest disables the home directory; automatic saving is off. Resolution
is fixed at 1280x720, maximization disabled, OpenGL selected, gamma/contrast 1,
sRGB 0, mono/outline postprocess 0 and `dpcompat_smallerfonts` 0. `r_font_linear`
is selected **before renderer/font initialization**, not toggled on an existing
atlas (it also affects glyph padding). Console scale is the only geometry arm.
The probe uses the actual physical/virtual screen dimensions, including the
853-pixel virtual width at scale 1.5, not an assumed equal-axis ratio.

## Predictions registered before the correction

- An untouched same-process repeat must be pixel-identical, including geometry
  and the 0.5-alpha line; a silent draw is not a pass.
- Each of 24 crops (three faces, four sizes, black/white backgrounds) must contain
  visible neutral antialiased glyphs, without touching the crop boundary. Known
  colour/geometry markers prove the gallery itself acted. Faces at 16px must
  differ, catching a collapse to a shared default slot.
- The deliberate `+0.75` physical-pixel request must change **every** sample.
  These requests are absent from the baked ladders. Passing this arm does not
  mean stretching is acceptable; it proves the reader can see it.
- With the pre-patch engine, matched native requests at console scale 1 versus 2
  must differ. With the correction, scale 1 / 1.5 / 2 must be **exactly identical**.
  The scale-1 approved rendering must not change.
- `menu_restart` and `vid_restart` must restore identical native images and
  retain bounded font initialization. Their probes/screenshots are required.

The reader thresholds establish activity/crop containment/half-alpha composition,
not a quality ranking. The 16 reader tests include blank/bitmap/collapsed-font,
wrong-size/scale/setting, absent/duplicate probes, colour fringe, double
premultiplication, inert stretch, unstable repeat and lifecycle mutants.

## Actual engine contract

`Font_LoadFont` takes a **virtual** height and multiplies it by the console-to-
pixel ratio. A QC conversion back to virtual units alone cannot make a virtual
loadfont ladder physically native. The initial selection-only trial was rejected:
changing selection without changing the bake units made the gallery worse.

Patch 570 adds `pixels=1` to the loadfont size-list options. The ladder numbers
then denote physical pixels, including on font reload. `Font_NativeSlot` lazily
creates separate physical mirrors for modern text, while legacy `Font_Set`
callers keep their original virtual ladders and larger scaled bakes. Selection
uses the **actual physical bake height**; horizontal scale uses its own axis;
float round-trips cannot turn native scale 1 or integer origins into resampling
or a one-pixel floor drift. Deliberately non-native requests still resample.

The QC option requires the matching engine pin for the corrected quality. Older
engines ignore `pixels=1`, remaining usable but retaining the old scaling defect.
This is not an ImGui ABI or renderer integration.

## Evidence and interpretation

Each rig retains compiler/client logs, source/engine/font/DLL/config hashes,
UTC launch interval, exact command/ref and dirty-source status in
`provenance.json`, all five screenshots and `grade.json`. Inputs must still hash-
match on regrade. `compare` requires matched QC/font hashes and writes raw per-
crop difference counts, `comparison.json` and `baseline-diff.png` in its second
rig. Differences are **not** automatically called better/worse. Use
`--require-identical` only for native-size/scale invariance and repeat controls,
not arbitrary future font/atlas/gamma candidates.

Final pre-patch control at scale 1 versus 2: 30,764 changed pixels, with both
individual rigs reaching their controls; strict comparison correctly fails.
Corrected 1 / 1.5 / 2 gallery: zero changed pixels, including labels/half-alpha.
Corrected scale 1 is also pixel-identical to the pre-patch scale-1 control.
The actual CSQC editor route is tested separately with `tools/test_ui_modern.py`;
synthetic MQC samples are not proof of OS-delivered input, gameplay performance,
other renderers, arbitrary DPI or every font/reload/atlas-failure case.
