# P941 — owner feedback on Source presentation

23Oct2026 owner: P940 walking rock and turning sway are much too strong;
surf_axiom does not change floor sound like CSS; lighting differs; idle looks
absent; spawn should start unarmed. No human acceptance is claimed below.
Reserved before concurrent P942; ENGINE.txt retains highest patch942/native939.

## Pre-registered controls and ownership

Reused owned C:/FTESurf-worktrees/source-polish-20261022T0746Z. No owner game,
config, data or canonical map edited. Real dedicated socket27579, explicit
cl_maxfps100/cl_idlefps0, cfg_save_auto0, cl_viewweapon1/cl_game_sfx1.
1. Motion: old scale1 must visibly act, scale0.2 must reduce nonzero offsets;
   only the model moves, never view angles, aim, body or input.
2. Spawn/respawn: selection0 even with cl_viewweapon1; give knife remains valid.
3. Real unmodified Axiom: identify the full contact VMT/property and actual WAV,
   not only P940's synthetic fixtures. CSS aliases must beat Momentum variants.
4. Idle: late elapsed age exceeds the raw12.5833s clip while pose time wraps.
5. Lighting: compare asset/map/camera provenance before any brightness change.

## Findings and changes

- Default bob/sway multipliers0.2, individually tunable with cl_viewweapon_bob
  and cl_viewweapon_sway (0 disables,1 restores P940 strength). Existing FOV70,
  depth, handedness, smoothing and warp/replay gates remain.
- PutClientInServer selects0. Unsupported/unarmed selection now clears client
  ready/drawing/motion state instead of leaving stale diagnostic state. Explicit
  selection still enables the model; personal cl_viewweapon choice is not reset.
- The MDL raw animation exposes flags0, not its sequence's looping flag. The
  engine therefore clamps an unwrapped elapsed pose. Wrap idle frame time by its
  actual duration; draw/fire one-shots retain their existing timing.
- Native collision exposes only `maps/surf_axiom` (16bytes), surface-id0. The
  rendering polygon retains `maps/surf_axiom/skyppy4/new/tile_floor01_-2720_0_-32`.
  Read the actual nearby clipped contact polygon's full material name, reject a
  distant face, and preserve local transforms/vector globals. Cache the polygon
  only while the next point still projects onto it; crossing an edge rescans.
- That VMT declares metal. Ordinary VFS script order chose Momentum variants;
  scoped existing search_getpackagename/search_fopen reads the mounted cstrike
  physics aliases afterward. No inactive-package force or pack-order mutation.
  Existing bounded parsing, metadata/material caches and missing-content fallback
  remain; repeated same-floor cues need neither new file reads nor a full scan.

## Actual native controls

- Actual unmodified Momentum Axiom emitted `player/footsteps/metal2.wav`, full
  VMT above, surface metal via VMT,111profiles/67aliases/CSS-samples1. No authored
  test VMT was involved in this real-map fix.
- Same-face forward/back movement: calls3 ->6, cache-hits2 ->5, metadata-reads14
  unchanged, surface-scans1 unchanged. This proves reuse ACTED, not an FPS claim.
- CSS-BSP control:135.2u/s walking left total calls3 unchanged;260u/s produced
  actual steps. Scale1 turning lateral0.937459 -> scale0.2 lateral0.187492;
  scale0.2 bob at260 produced nonzero offset0.0830284/0.155239, roll-0.0970247.
- Knife at age378.81s posed at1.30991s inside duration12.5833; later age386.888
  posed9.38803. Screenshots show distinct authored hand/blade poses after many
  cycles. This is real animation, not just printed modulo arithmetic.
- Existing synthetic selector controls separately choose CSS wood_tile1, glass1
  and concrete1 with all referenced files present. They do NOT claim traversal
  of those real materials on Axiom or owner ear acceptance.
- A reconnect timed too early lost its info query; not a respawn pass. Old `kill`
  and `cmd goto_spawn` attempts are not accepted spawn evidence. `cmd respawn`
  did expose stale client ready/type diagnostics; final unsupported-model gate
  addresses that state explicitly. Final corrected respawn control recorded below.
- First draft compile used unavailable pmove_mins_z: FAILED, retained as
  p941-first-compile-error.log. Fixed to the existing bounded foot-contact ray.
  The final code edits are validated by real fteqcc, not clangd (no QC parser).

## Lighting — open matched-reference question, not a claimed fix

FTE loads Momentum's surf_axiom; CSS's installed BSP is a different build.
A single owned exact CSS BSP fixture (SHA256
2e08b68bedaf41537970dcb58c3bc41d8130dfe53274a90fbd211618b1921e61) was loaded
in native FTE for screenshots, then hash-checked/removed after stopping ONLY our
actors. Original absence/Momentum priority restored; no live map replacement.
Camera and idle phase were NOT matched to the owner's CSS view, so those images
cannot prove residual shader parity. A no-sky reflection toggle also changed
idle pose and is NOT a valid isolated lighting comparison. No global lighting
hack, native flag rewrite or map-priority change was made. CSS knife/hands VMTs
use ordinary VertexLitGeneric/env_cubemap, not Phong. The no-bob flag is additive:
RF_WEAPONMODEL remains set, so a supposed lost weapon-lighting flag is falsified.
Owner was asked for CSS `getpos` at that spot. Remaining matched-map/camera/pose
comparison and human look are explicit in BACKLOG.md/lextest.md.

## Final source/build/delivery

Final candidate23Oct06:31–06:32UTC (console timestamps are local UTC+11): all three VMs0warnings. Actual socket
sequence with cl_viewweapon1: fresh0/ready0 -> give knife1/ready1 -> cmd respawn
0/ready0/model empty -> give knife1/ready1. Unarmed screenshot inspected; no
model drawn. After18.8297s idle, pose6.24638s and an authored changed pose were
visible. Actual unmodified Momentum Axiom still resolved metal2/metal3, full VMT,
CSS-samples1,14reads/1scan across repeated contacts. Native939 unchanged.

Final QW SHA256:c37d568a9de6463838d57e1d0f56605d2118147dfb238da56227abe9485d6338
Final CSQC SHA256:5b1500f1ca021514889998d8b1de6ee52640665c0bf40249be45c2a243d31242
Exact clean source commits, destination/live readbacks and UTC delivery are
recorded in tools/p941-delivery.md (BOTH Windows and all12lobbies verified). No release/Build-number/
engine-pin change, recorder/evidence modification, collection activation or PvP
feature is involved. All owned actors stopped; CSS map fixture remains absent.
