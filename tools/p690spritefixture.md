# P690 native sprite-overlap preservation — bounded PASS

One authored SPR32 billboard overlaps two world-alpha panes. Exact retained
production P688 / merged P689+P690 / P688-return preserve sprite-present images,
while removing the sprite allows the mode2 static-plane correction to act.
**This proves preservation around this overlap, not correct sprite ordering,
arbitrary sprite/model/weapon certification, performance or default2 promotion.**
No engine/QC build, product patch, default, binary or deployment changed.

## Self-contained fixture generator

```text
python -B tools/p690spritefixture.py --output <new-owned-directory>/fixture
python -B tools/test_p690spritefixture.py --output <new-owned-directory>/fixture-tests
```

Python3.10+, standard library only. Both outputs must be fresh operator-owned
directories; existing outputs are refused before writing payloads. The generator
writes three small files plus a size/SHA256 manifest, never a game install:

- maps/mv16_sprite_overlap.bsp: BSP29, black background x600; half-alpha red
  x256,y[-32,32],z[0,128]; blue x=128+y,y[-64,384],z[0,128]. Single empty
  visible leaf, no external textures, lightmaps, BSP compiler or map library.
- scripts/mv16-sprite.shader: black/red/blue unprogrammed material definitions.
  Both panes use alpha.5/SRC_ALPHA/ONE_MINUS_SRC_ALPHA.
- progs/mv16_green.spr: SPR32, one64x64 RGBA(0,255,0,128) frame; camera-facing
  billboard type2, frame origin(-32,32). prop_dynamic at(272,0,64), scale1,
  solid0 loads the actual sprite through production precache_model/setmodel.

Use prop_dynamic, **not env_sprite**: this QC removes env_sprite and
env_sprite_oriented (`src/server/sv_entities.qc`). No temporary CSQC fixture or
synthetic draw is involved. Production `gl_model.c:Mod_LoadSpriteModel` consumes
SPR32's RGBA frame; `Mod_LoadSpriteFrameShader` chooses the default sprite shader.
Set **gl_blendsprites1 BEFORE loading the map**, or its default alpha-test variant
can turn the intended half-alpha sprite into a different subject. r_shaderpasses
must report the main sprite's defaultsprite program and ordinary premultiplied
ONE/ONE_MINUS_SRC_ALPHA blend bits, without alpha testing. A separately registered
beam shader is NOT evidence of a drawn beam.

The focused test has four methods: sprite header/frame/payload; BSP lump bounds,
geometry/actor; shader/determinism; manifest hashes and acted collision refusal
with all existing bytes unchanged. Tests also pass under Python `-O`; generated
bytes and synthetic format checks alone are NOT native renderer coverage.

## Native protocol and binding

Evidence retained at
`C:/FTESurf-worktrees/mapvisual-01a13061/artifacts/sprite-overlap-20261013/`.
PREDICTIONS.md and capture.py were frozen before launch; generation and runtime
staging are separate. Exact bundle pins reuse [p690cache.py](p690cache.py):
P68873322dff5b6898511d62ed775286b23a91b8aad0 and delivered
mergeda8e705787fad1b60661da5e8dd43c9138cc69b1b. There is no diagnostic executable.

One bounded BLOCKING/serialized capture, about three minutes, three production
client/dedicated-server pairs, two modes,24 full960x720 PNGs. No concurrent agent
sampling/builds/tests/image/hash/corpus work, no native retries or timing matrix.
The owner/peer processes were not stopped; this is not OS-wide isolation.

Each arm/mode records sprite on twice, entity-off once, sprite return once.
Actual model allocation, sprite/pane shader readbacks, version/bundle hashes and
r_drawentities1/0/1 bind pixels to the production actor. Body/aim are exactly
(0,0,0)/(0,0,0), velocity0, timer idle on the correct fixture map. The all-zero
viewpos warning alone is not spawn proof; actual model/material/pixels and
correct-world timer provide the complementary controls. No diagnostic rendered-eye
or sorter-admission counter was collected, and none is claimed.

Explicit GL/cache0/quiet HUD/FOV100/sRGB0/render-scale2/fullbright1/viewmodel0,
with gl_blendsprites1. All images are full-frame; no masks, trims, tolerance or
shader-time freezing. Hash receipts are local trusted-capture evidence, not a
cryptographically attested execution. Native-grade.json audits every captured
state/hash/image/closure; three in-memory negative replays reject changed repeat,
changed P688-return and absent sprite action without editing native evidence.

## Observed results

| Comparison | Mode1 | Mode2 |
|---|---:|---:|
| Every sprite-on repeat and on-return | 0pixels | 0pixels |
| Merged vs P688, sprite ON | 0pixels | 0pixels |
| P688 initial vs return, ON and OFF | 0pixels | 0pixels |
| Merged vs P688, sprite OFF | 0pixels | **20,604pixels** |

Every sprite-on frame introduces **9,216 green-bearing pixels**, bounds
[432,312,527,407], where off images have no green. P688 and merged mode1 on/off
change9,216pixels; P688 mode2 does too. Merged mode2's toggle changes20,604pixels
because removing the sprite also allows the world panes to reorder: that delta
is **not a pure sprite-area measurement**. The green-channel footprint isolates
visible sprite action, while the full-frame delta records the entire consequence.

Center RGB is mode1 ON(32,127,63)/OFF(64,0,127) in all arms. Mode2 sprite ON is
(127,64,32) in all arms; OFF is P688(127,0,64) vs merged(64,0,127). Sprite-present
mode2 preserves the legacy image; **preservation does not make its inherited
ordering correct**. The source fallback's internal reason/count was not measured.
Positive sprite pixels plus the sprite-off plane correction prevent a vacuous
"everything stayed identical because nothing drew" result.

All six owned native processes quitrc0. Native8, protected config/data/content
fixtures and two installed client hashes restore/remain unchanged. Runtime
fixture files are removed only after source/target hash checks; newly created
maps/progs directories return to absent. Unique source/protocol/PNGs/rawlogs/
failed-test/negative replay receipts are retained. Only inventoried current-created
byte-identical backup/log duplicates may retire. Canonical peer work is untouched.

## Remaining gates

This one billboard test narrows a native preservation gap but does not close
arbitrary animated/oriented/lit sprite, alias/studio model, weapon/depthhack,
rotated-brush or portal/reflection capture coverage. The existing
[quiet ordinary gate](p690ordinary.md) remains Kitsune-only; representative
moving/time-aligned ordinary service/tails and default2 promotion remain OPEN.
Tensor/Demise stationary ineligibility and earlier failed matrices are unchanged.
