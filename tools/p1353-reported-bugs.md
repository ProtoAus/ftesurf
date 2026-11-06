# P1353: reported prediction, label, zone-editor and texture fixes

Engine source/tag: `09262667df5afe01a9487809ebc868cd56caca4c` / `patch-1353`.
QC source is the feature commit containing this document. Build number unchanged.

## Changes

- **GoldSrc illusionary prediction:** the matching `bhop_goldsrc2` save at
  1:01.070 is beside authored skin=-1 `func_illusionary` model *304. The NanoPi's
  Q1 snapshot converted a negative float directly to unsigned: AArch64 clamps it
  to zero, so P919's existing client EMPTY-content rule never saw the tag.
  Convert negative skins through signed int; keep the nonnegative unsigned range.
  Server movement/collision rules and recording formats are unchanged.
- **Independent board labels:** `hud_lines_board` now controls board strokes and
  teleport joins, not the independently enabled number/name passes. Existing
  name/number settings still hide labels. Replay, trail and ghost switches remain
  separate. Hidden board strokes no longer enter native or QC path drawing.
- **Boarding energy:** preserve the existing pre-contact main label, retain the
  first contact sample's squared velocity, and draw its mechanical-energy change
  on a second row. The row obeys the energy/number settings and reserves its full
  height for label placement/final decluttering. It is a sample-to-sample change,
  not a claim of sub-tick collision-only loss. Stitches, breaks and non-ramp
  contacts do not invent a pair.
- **Clip snapping:** a guarded optional `getworldbrushfacepoint` CSQC builtin cuts
  the actual world collision-brush winding using the same plane cutter as
  `surf_view`. Queries are finite/bounded, world/map/host-frame scoped and capped
  at 64 vertices. An editor-only nonsolid trace probe includes player clip; both
  geometry and grid modes aim at the same face. Old engines retain render-face
  snapping. Existing real-corner/flat-plane filtering also applies to clip faces.
- **Teleport labels:** snap the requested size onto the loaded font's baked
  ladder and center at integer coordinates instead of drawing fractional sizes
  and fractional origins.
- **Dragonfall:** the saved view points along the alpha-tested, point-sampled
  `makkon/gothic_stone/{stn_gr02_sand1` floor. Its VTF has ten mips. Authored point
  filtering no longer disables user-selected mip blending or opt-in anisotropy
  on mipmapped world images. Nearest magnification is retained. UI/nonmip images
  keep their prior filtering; existing anisotropy factor 1 remains an opt-out.

## Acting verification

Public task evidence: `C:/FTESurf-worktrees/bugs6-01a1b058/artifacts/` and the build
logs in its parent. No private player identities, raw rollout inventories or
preservation archives belong in this public report.

- Supported `build.ps1 -Engine -Full -NoDeploy` native base, then rebuilt changed
  targets. Final candidate uses qualified compiler SHA256
  `c24ede65e98b88a69c28b64afb163943a3d826108558f21f1ca4cefeeb1cc731`:
  all three VMs compile with **zero warnings**. The inherited native
  `PF_resourcestatus` address warning is not repaired as unrelated work.
- `tools/p1353_skin.c` has ten independent constant-bit expectations. On actual
  AArch64, all five original negative inputs become zero; corrected values pass
  all ten and leave the five nonnegative controls unchanged, including 2^31.
  Windows also passes the corrected expectations. This is an acting producer
  conversion control, not fabricated owner movement acceptance.
- Windows `pm_selftest` actually runs **1608 checks, zero failures**. A first empty
  stdout/exit-zero invocation did not establish execution and is retained as
  unmeasured; the later interactive command has all individual checks and the
  positive completion marker.
- A real dedicated socket and `reported_bugs.cfg` load the same public voyager
  fixture. Board path on/off retains two name labels; disabling labels removes
  them. The independent numeric label remains visible without the path.
- **32 boarding rows** agree with `(z_post-z_pre)+(v_post^2-v_pre^2)/(2*g)`, with
  gravity explicitly 800 and ordinary integer-display/printed-height rounding.
  Maximum display discrepancy is 0.47219 height units. A screenshot shows
  `boarding dE -24` below the existing main contact information.
- On `surf_sinsane_ez`, **four reached invisible clip corners** snap to exact
  coordinates with no render surface. **Four grid controls** stay on that same
  collision plane when geometry snapping is off. An earlier too-close camera
  correctly failed to reach the screen-space snap radius; four other probes hit
  an intervening face and are not counted. Existing render-surface snap regression
  also passed. Teleport text is inspected in the editor.
- Recreated the matching Dragonfall saved view. The grazing pattern improves on
  the tested NVIDIA OpenGL driver. A **280,000-pixel magnified crop is byte-identical**
  before/after; this proves the tested close-up pixel detail is preserved, not a
  frame-rate improvement or all-GPU acceptance. Older Intel behavior is untested.
- The initial install compiler `7ccb93d1` produced two familiar warnings and is
  explicitly **not** the qualified final compiler. Those early controls/logs are
  retained; final candidate UI/clip verification uses c24 and freshly seeded CSQC.
  Source was advanced to include the published P1350–P1352 changes before final
  qualification; no unrelated canonical dirty work is included.

## Delivery state and limits

Feature source is verified; exact clean-commit Windows/ARM qualification and
ordinary dual-install/fleet rollout are the next execution steps, not yet claimed
by this source receipt. Deployment evidence will be appended after actual hash,
process, dependency and data-preservation readbacks. Owner feel/visual confirmation
is pending in `lextest.md`. No Build/release, new evidence signal, detector policy,
backend generation or owner-data/config change is requested or claimed.
