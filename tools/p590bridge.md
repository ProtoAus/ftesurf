# Patch 593 — explicit VM-owned native UI dispatch prerequisite

## Pre-registered scope and falsifiers

Inspected initial game base: a7c9496; engine checkout: c88d76d5c, with published
P589 implementation 837c5c568. Before commit, fetched/fast-forwarded to game
1d15289 and engine 0e0928958; intervening engine changes are documentation only
and the game changes are surfd/tooling, not QC or native renderer source.
Working trees: C:/FTESurf-ui-integration and C:/msys64/home/Lex/fteqw-ui-bridge.
The primary game/engine trees contain peer work and are not build/deploy sources.
Final claim: 593, after fetching both origins and checking patch headings and
untracked pNNN claims in the affected and predecessor checkouts. Initial provisional
590 was superseded by peers' published 590-592. `p590bridge` fixture names/traces
are deliberately retained; there is one product patch, not a claimed range.

A copied, exact-size `NativeUI/1` service table, named optional MQC/CSQC builtins,
and synchronous dispatch at the caller's explicit QC draw site. One live owner
per frontend VM; distinct non-reused float-exact handles; one dispatch per owner
per host frame. Physical framebuffer and virtual-screen dimensions, frontend,
owner/generation/frame identity and inherited physical clip are supplied without
QC memory pointers. No widgets, model transport, input capture, ImGui, real-panel
migration, preference/default change or new renderer-backend acceptance.

Predictions (all arms must log actual QC/native/legacy action):

- P589 baseline lacks the named bridge; guarded QC still draws the legacy panel.
- Subject without service also draws legacy; exact ABI accepts, wrong sizes,
  version/capabilities/missing callbacks and duplicate registration reject.
- MQC and CSQC actually execute QC-before -> native -> QC-after. Overlap pixels
  prove order, inherited clip and unchanged caller state. Run at two virtual
  scales with physical coordinates converted independently on each axis.
- Draw outside an engine-bracketed draw callback, duplicate draw in a host frame,
  stale/fractional/foreign-VM handles and invalid owner IDs reject without native
  action. Opening does not authorize Tick/Sbar/Menu/input callback rendering.
- Failed open/draw releases partial owner state and permits same-frame QC fallback.
- Explicit close, VM teardown/menu_restart, disconnect, plugin unload and renderer
  teardown release owners once; reopening gets a new handle, never stale aliasing.
- Renderer teardown releases native owner resources before P589 texture cleanup.
- Acting legacy-2D sentinels and the P589 gallery stay green after the bridge.

Tests use one-shot marked disposable installs, explicit executable/plugin hashes,
fresh logs and only their own process handles. No owner configs/data/production
progs are replaced. Build with pwsh 7 from src; -Engine builds use explicit owned
integration-tree output and an owned QuakeDir because this build script derives
SurfDir from its location and does not implement -NoDeploy. Header
changes require -Full. No claim is made from LSP cleanliness alone.

## Results

Candidate verified with `rig/p590-bridge-z7lgogbi`: five acting arms, 52
screenshots, zero failed. P589 native regression passes in `p589-mesh-4jpv7z06`.
24 portable grader controls and 149 actual-core host assertions pass, including
caller colour/flags/scissor restoration, reentrant bracket rejection, target
refusal and exact-handle exhaustion. The isolated published predecessor and
subject full builds have identical 74 compiler warning message/count fingerprints;
all QC compiles have zero warnings. Engine commit `25ad9d56e582e60d8d03fadf56c4dcfa4a049bc1`,
published tag `patch-593`; game feature `d3b7174`. Clean frozen rebuild is stamped
`git-7115-patch-593-0-g25ad9d56e`; bridge `p590-bridge-3nyqfybl` and mesh
`p589-mesh-hei0vtp6` pass. Actual installed Windows executable paths ACT in
`p590-bridge-hmrva9oz` / `-gvq91c1r`, zero failed, at 2026-10-08T11:00:43Z.
Guarded native+CSQC+MQC swaps retained rollback; unchanged SSQC was not replaced;
configs/data/server/DLL digests remain unchanged. Pi progs swap kept `.prev` with
zero players; 12 fresh lobbies advertise the exact new cached CSQC CRC/size,
protected engine/config hashes match and health is 12 (2026-10-08T10:54:38Z).
No fixture DLL was shipped. No Build-number or release operation.

Final review's non-finite inherited-clip correction is separately P594; see
`tools/p594clip.md`. The P593 source/tag is immutable. Current installed native
is P594; original P593 progs remain unchanged.

Retained initial failures: Bash-to-pwsh argument conversion and inherited MSYS
conversion exclusions broke Make paths; a clean worktree lacked the ignored SDK
headers/libraries. Copied only SDK/build prerequisites into the owned worktree,
never another worktree's objects. Fixture setup exposed actual plugin command/API
names, snprintf macros, implicit QC const initialization and the required CSQC
input stub. One P589 regression used a P589 binary in its P581-control slot and
correctly failed; rerunning with the retained acting P581 binary passed. The first
renderer-restart fixture tried an alternate owner before reacquiring its stale
handle, thereby creating a valid wrong owner itself; idempotent same-owner open
before probes fixes the fixture without weakening lifetime/pixel criteria.

No ImGui, input/model/widgets, actual panel migration, preference or Build-number
change; no non-GL parity, target rendering, device input or CPU/GPU cost approval.
Trusted callbacks may not retain frame pointers or reenter engine services;
Open/Close allocate/release only. Renderer targets fail to usable QC fallback.

Commands:

```
python tools/test_p590bridge_unit.py
python tools/p590bridge.py
python tools/p590bridge.py grade <retained-rig>
```

The launcher owns only marked disposable installs and process handles. The P590
fixture name is retained after forward-renumbering the product patch to 593.
