# P690 rotated inline-brush fixture — frozen native gate REJECTED

A self-contained BSP29 fixture now binds a real production `func_wall` alpha
pane to yaw0/yaw45 images. Rotation and entity drawing ACTED, but the complete
P688/merged/P688-return preservation gate **failed its mode1 control return**.
Do not relabel the matrix as accepted or blame the candidate for a baseline
that did not return. No engine/QC build, patch, default, install or deployment
changed. Mode2 observations below are a measured subset, not a replacement gate.

## Reusable fixture tooling

```text
python -B tools/p690brushfixture.py --output <new-owned-directory>/fixture
python -B tools/test_p690brushfixture.py --output <new-owned-directory>/fixture-tests
```

Python3.10+, standard library only. Fresh operator-owned directories are required;
existing outputs are refused before payload writes. No launcher, BSP compiler,
asset downloads or install writes. Three resources plus a size/SHA256 manifest:

- maps/mv17_brush_yaw0.bsp and maps/mv17_brush_yaw45.bsp: identical geometry and
  materials, differing only in the func_wall entity's `angles` string. World
  black background x600, red half-alpha x256,y[-32,32],z[0,128], tilted blue
  x=128+y,y[-64,384],z[0,128]. Model*1 has one local quad at x0,y/z[-32,32],
  translated to(272,0,64), yaw0 or45. World/model surface/node ranges are separate.
- scripts/mv17-brush.shader: unprogrammed black/red/blue/green materials;
  colored panes use alpha.5/SRC_ALPHA/ONE_MINUS_SRC_ALPHA, cull disabled.

This deliberately minimal fixture has empty collision hulls and no external
textures/lightmaps. It is a renderer station, not a playable/collision-certified
map. Explicit noclip after each load is required to hold the body at origin0.
Production `src/server/sv_entities.qc:func_wall` loads the inline model via
setmodel and keeps the authored angles; no fixture QC or synthetic CSQC draw.

Four focused tests check lump bounds, local quad/inline-model/node/edge ranges,
angle-only entity difference, shader/determinism and acted collision refusal
with existing bytes unchanged. Normal and exact-committed `-O` tests pass and
emit byte-identical resources. These format tests are NOT native acceptance.

## Frozen native capture

Evidence retained at
`C:/FTESurf-worktrees/mapvisual-01a13061/artifacts/brush-overlap-20261013/`.
PREDICTIONS.md/capture.py/generator/helpers/fixtures and the original grader were
frozen BEFORE launch. Retained bundle pins reuse [p690cache.py](p690cache.py):
production P68873322dff5b6898511d62ed775286b23a91b8aad0 and delivered
mergeda8e705787fad1b60661da5e8dd43c9138cc69b1b. No diagnostic executable.

One BLOCKING/serialized capture: P688 yaw0,yaw45; merged yaw0,yaw45; P688-return
 yaw0,yaw45. Six real dedicated socket/client pairs,48 full960x720 PNGs/36 states,
about six minutes. No concurrent parent/child tests/builds/analysis/corpus work,
no native retry or timing matrix. Owner/peer processes were not stopped; this
is not OS-wide isolation.

Each angle/mode records entity-on twice, entity-off, entity-return. Runtime
version/native hashes, loaded `*1:<map>` batch with one mv17_green surface and
r_shaderpasses sort11/no-program/ordinary-alpha bits bind the real actor.
Body/aim0, velocity0 and correct-world timer are recorded with explicit GL/cache0,
quiet HUD, FOV100/sRGB0/render-scale2/fullbright1/viewmodel0. No mask, tolerance,
trim, shader-time freeze or rendered-eye/sorter-admission diagnostic is claimed.
Hashes are local capture receipts, not cryptographic execution attestation.

## What acted, and what failed

Every within-boot ON repeat and entity-return is fullframe exact. OFF images
have no green; visible ON green footprint is:

| Actor angle | Green pixels | Bounds | Size |
|---|---:|---|---|
| yaw0 | 9,216 | [432,312,527,407] | 96x96 |
| yaw45 | 6,532 | [443,308,510,411] | 68x104 |

The projected shape changes in every production arm. Mode2 yaw0/yaw45 ON images
change3,150pixels, and corresponding OFF images are exact across the two maps.
This proves visible transform action; it does not measure internal eligibility.

| Fullframe comparison, both ON and OFF unless specified | yaw0 | yaw45 |
|---|---:|---:|
| Mode1 P688 initial vs P688-return | 0 | **20,604** |
| Mode1 P688 initial vs merged | 0 | **20,604** |
| Mode2 P688 initial vs P688-return | 0 | 0 |
| Mode2 P688 vs merged, brush ON | 0 | 0 |
| Mode2 P688 vs merged, brush OFF | **20,604** | **20,604** |

The yaw45 mode1 initial P688 and its return differ over the entire red/blue
intersection [429,259,530,460], including with the brush OFF. P688 mode1 OFF
also changes20,604pixels across the two yaw-map boots; merged and P688-return
mode1 OFF do not. Direct PNG inspection shows two world-pane blend orders.
Thus the frozen angle-only world-parity and baseline-return premises failed.
A legacy mode1 interbatch-order variation was observed previously too, but this
capture alone does not identify its root cause or establish a candidate bug.

Mode2 ON preserves the inherited P688 image at both angles. OFF changes20,604
pixels in merged, demonstrating the existing world-plane correction ACTED.
Merged mode2's ON/OFF delta includes world reordering, **not just brush area**.
Neither inherited ordering correctness nor the internal fallback reason was
measured. No default2 promotion or all-brush/model/GPU/performance claim.

The original frozen grade_native.py still rejects under normal and `-O` and
remains unchanged. Its empty failed stdout files are not accepted JSON reports.
A separately authored post-capture report_native.py checks source/state/image/
closure and enumerates all nine failed frozen predicates; normal/`-O` diagnostics
are byte-identical and explicitly say **REJECTED**, not PASS. Four in-memory
controls add their own onepixel repeat, onepixel control-return, absent-green
and collapsed-yaw violations; they cannot pass merely because the native matrix
already has other failures. Native files/manifests were never mutated.

All twelve owned processes quitrc0; native8,1,223 protected fixture files and
both canonical client hashes restore/remain unchanged. Three staged resources
and the newly created maps directory return to absent. Unique source/protocol/
raw/PNG/failure/diagnostic/exact-commit receipts retained; only inventoried
current-created byte-identical backup/log duplicates may retire. Parent source
review only; no independent verdict is claimed.

## Next gate

Do not retry until a separately frozen protocol proves the mode1 P688 world
returns. Prefer a same-loaded-world actor-angle control, with actual actor state
and pixels observed, or establish the cause of the two legacy world orders.
Do not widen the exact gate, mask the intersection or call mode2 subset agreement
a completed arbitrary rotated-brush acceptance. Broader animated/oriented/lit
sprites, alias/studio models, weapons/depthhack, portal/reflection captures and
moving/time-aligned ordinary service/tails remain OPEN; r_blendsort default stays1.
See [the completed billboard lane](p690spritefixture.md) and
[quiet ordinary scope](p690ordinary.md).
