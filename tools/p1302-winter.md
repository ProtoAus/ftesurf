# P1302 — provisional holiday props and bounded mist

## State

Implemented/content-built and offline-controlled, NOT renderer-qualified or
deployed. Mist deliberately defaults **OFF** until the moving-view performance
budget is verified; `r_mist 1` / Display Info > Light mist is an opt-in preview.
Decorations use `r_winter_props` (default1). Both reset through Display Info's
existing Reset All walk. No native pin/tag, physics/evidence or Build change.

Owner approved Kenney and agent-chosen temporary maps; provisional layouts are
surf_christmas, surf_frost and surf_bluewinter. Each has six prop candidates and
12 light/wisp candidates. These are editable sidecar records, not modified BSPs.
Actual flat-floor/light-wall validation can reject candidates; no count is
claimed as successfully rendered yet. New clients need the accompanying assets;
clients missing models safely skip them, rather than drawing ERROR art.

## Assets

The exact original Kenney Holiday Kit2.0 archive SHA is checked before conversion
(see winter-assets.md). Bundled CC0 license is retained with the native assets.
Two snowmen, two snowy trees and two gift styles total5038 triangles, one ordinary
lit palette material. `tools/holiday_assets.py --archive <original zip>` emits
small static IQMs; it preserves winding/normals, converts to Quake Z-up and avoids
runtime OBJ deduplication. No full holiday pack is required at runtime.

`tools/winter_placements.py` uses the existing BSP/entity parser, not a fresh map
parser or install copy. Models never affect collision, triggers, timers or damage.
Only explicit manifests get decorations; this is not an all-map effect.

## Mist cost guards (not a performance claim)

- Independent GPU-opened impostors:12 triangular puffs/field, at most4 submitted
  fields (48puffs), two small tiling noise samples/fragment, one blended pass.
- Radius24..64, distance192..1100, near/lens and far fades, frustum/depth culling.
- Summed conservative projected-area proxy<=.12; it is NOT an exact screen-area
  or GPU-time measurement. Close screen-filling fields are not submitted.
- No per-frame simulation, allocations, traces, light queries, readbacks, depth
  captures or raymarch. At most28 setup traces and128 input records per map.
- White/blue light tint/positions are baked, not full volumetric light transport.
- `winter_info` reports loaded and actually submitted counts/area. Off must show
  zero submissions; a performance arm with zero mist submitted is NOT a pass.

## Verification and limits

`python tools/test_holiday.py`:5pass, actual IQM layout/index/bound checks,
right-handed rotation, nonfinite rejection, deterministic12-puff field, manifest
caps/no-light/no-spawn controls and overdraw-cap arithmetic. QC via the existing
build.ps1 NoDeploy entrypoint: zero NEW warnings (two existing CL F333 VF227).
No clangd diagnostic is substituted for fteqcc or an actual shader compile.

The bounded real-client off/on/off arm did NOT start: no shared quiet/4096MiB
interval occurred before its300s deadline. It held no gate while waiting, left no
children, and no runtime/performance pass is inferred. Candidate input hashes
and untouched failure log stay in the owned task artifacts. Do not repeatedly
extend this wait or weaken it; use a small owner visual check when appropriate.

Default-on acceptance prediction: same resolution/renderer/camera movement,
actual mist submissions>0, no shader/model errors; average added cost no more
than max(.10ms,1% of controls), p99.9 not over .5ms above both controls and no new
recurring >2ms spikes. Blocked/noisy/failed measurement => remain opt-in0. Passing
one machine would still not guarantee no FPS cost on all hardware.

## Follow-up scope

Santa hat will be a permanent account gift for trusted in-game event presence,
not a web/profile grant; event activation defaults OFF. Snow accumulation remains
with the existing P1287 reservation. Frozen liquid visuals, winter audio/thunder,
sky lightning and expanded demo collection remain in ROADMAP, not delivered by
this props/mist patch.

Historical harness correction: the borrowed original guard used20quiet seconds,
not the60 claimed in old P1300 prose. The original three stale-sky checks remain
functional evidence only. This task's current guard really uses60, rechecks free
memory at the execution boundary and fails closed at a bounded deadline. Do not
rewrite old logs or reinterpret them as a numerical performance pass.
