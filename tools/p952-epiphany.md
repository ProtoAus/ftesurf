# P952 — Epiphany's black world is a failed colour-correction lookup

Development feature, not a release/Build bump or owner visual acceptance.

## Actual root cause

The winning Momentum Epiphany BSP has valid corresponding LDR/HDR faces and an
active global colour-correction entity naming `materials/cc`. Its embedded asset
is `materials/cc.raw`, a valid 98,304-byte 32-cube RGB lookup table. Generic texture
extension search does not guess that raw file. The active weight1 colour-correction
shader therefore sampled a failed 3D texture and blacked out the entire 3D scene;
the later HUD still drew. More fullbright/PVS/collision guesses could not repair it.

A matched native control proves the distinction: correction1 produces black;
correction0 and separately clearing only `r_colourcorrection` show the textured
world immediately. Actual cvar/program/body readback names the generated
`vmt/ccorrect` program and extensionless 3D sampler. Those are acting controls,
not assumptions that body+22 equals the real camera or that HDR-lump counts prove
rendering. Prior unknown-command/readiness/black-view failures remain failures.

## Bounded repair, preserving the authored appearance

Add the default `.raw` suffix only to extensionless LUT basenames in the Source
colour-correction entity context. Explicit extensions remain unchanged; dots in
parent directories and either separator do not masquerade as a filename suffix.
No change to generic image extension search or the existing strict `.raw` AND
98,304-byte decoder gate. No global correction disable, replacement BSP, shipped
Valve asset, input API, evidence/physics/verifier/backend or data policy change.
Genuinely invalid or absent LUTs are not relabelled valid by this fix.

## Acting causal and subject checks

- Frozen qualified native950, actual unmodified Epiphany: three inspected PNGs,
  correction1 black versus correction0/bypass fully visible; wrapper exit0.
- Same native/CFG/content root: exact original map copy versus ONE entity-filename
  mutation to explicit `.raw`. Original stays black, explicit raw gives authored
  cyan/green grading with correction1. Both exit0, both PNGs and exact shader
  sampler readbacks inspected. All geometry/assets unchanged. Original map hash
  preserved; only the hash-owned ignored synthetic BSP removed before build.
- Changed native on the ORIGINAL unmodified winning map: correction1 now shows
  the authored graded world, correction0 is visibly different/ungraded; inspected
  PNGs and native sampler name `.raw`, wrapper exit0 without command/VM errors.
- Prototype incremental build:3VM0warnings/3inherited native warnings,0new.
  Exact-tag qualification then correctly REFUSED the stale950 EXE stamps, despite
  a successful link/build. Revision compile flags did not invalidate cached stamp
  objects. Failure retained; no stamp/freshness check weakened. Supported clean
  `src/build.ps1 -Engine -Full -NoDeploy -Jobs 1` fixes that boundary: exit0,
  3VM0warnings and EXACT74-warning qualified950/P939 Full multiset,0new.
  All7freshAMD64PEs, both exact clean952EXEstamps, all5resourceZIPs valid.
  Final exact-cohort Epiphany and CSS+Momentum Phantasia scenes exit0, PNGs read.
  No engine-header/ABI change; full clean was needed for metadata provenance.
- Native950's explicit Refract_DX90/glass/report features remain in the source;
  its immutable seven-image staging is preserved while this independent fix is
  prepared. No uncommitted peer source is a deployment input.

## Delivery boundary

Engine source `d982f43de1eb18a89c844c6be1d0733cc049d51b`, tag `patch-952`,
EXE stamp `git-7758-patch-952-0-gd982f43de`, clean compiled/qualified cohort.
Source/tag pushed. BOTH Windows delivered23Oct2026 17:03:39Z after the owner
closed the game;14native client/dedicated/plugin destination hashes match.
All33snapshotted protected program/config/content/save bytes remain unchanged;
.prev/backups preserved. No kill, data/menu/progs swap, Pi operation or backend
change. One update carries BOTH950+952. Post-copy installed-image actor controls
(primary Epiphany, secondary CSS+Momentum Phantasia) both exit0; PNGs inspected,
14hashes and33protected hashes rechecked. These isolated installed-image copies
are not an owner manual pass. Human acceptance pending in lextest.md. Original
practice-clock/social/content requests remain explicitly unfinished.
