# P702 delivery — local KSF playback

## Inspected source and scope

- Product code/review freeze: `b9929205e51a10e58f5692e48f019987e18fe3f0`.
- Engine documentation: `96d27e1108b37b39ad820729fed808c3567e663a`.
- Both pushed to their published main branches. Engine code, binary, tag and
  QC Build were not changed by KSF work. A concurrent published alpha P701
  required renumbering this feature to P702 before publication.
- Conversion/playback instructions and limitations: `tools/ksfplayback.md`.
  Automatic KSF leaderboard Watch is not part of this delivery.

## Verification

- Nine converter tests; existing binary inspector tests; unchanged native-reader
  suite **306 checks / zero failures**.
- All twelve public clips independently match source positions/velocities/
  pitch/yaw, bookmark clocks and raw/resolved-button namespaces, and pass the
  unchanged text-recording reader. Frozen corpus comparison has identical
  baseline/subject fault reasons; existing corpus faults were not repaired.
- Full dedicated on-tick camera traces for all **3 + 5 + 4** clips across
  surf_null, surf_prosurf and surf_monolith. Actual-frame playback, pause/seek/
  finish velocity, native and old Momentum controls, cold wrong-map refusal,
  active missing/wrong-map replacement cleanup, cursor release and real restored
  body movement pass. Acting predecessors fail both the cleanup and tiny-command
  direction/move alignment regression controls.
- Both independent final FORMAT/VIEWER reviewers **ACCEPT** the frozen code.
- All three progs compile with zero warnings. Runtime screenshots inspected.
  Post-install probe uses the exact installed CSQC and actual alias/clip path:
  `ksf_null_farsh` opens `cfg/ksfreplays/ksf_null_farsh.rec`, seeks to 10.005s and
  emits ten camera samples with KSF/import/build-unknown labels. The isolated
  probe's uncopied sound diagnostics are not a playback/VM failure.

## Windows deployment — 2026-10-14 UTC

Guarded install at 12:00:57Z; finish-only destination verification follows.
Both `C:/FTESurf` and `C:/FTEQuake` hold:

- CSQC SHA256
  `a6ce950d7c61d14e4198fc4182227f6b2c86a26309ac835b4e25234d84a7c072`;
- unchanged SSQC SHA256
  `890fb0a08798d1d29b76c1aba31e32080cd8d273c3e8fe74f4061f7d31e25f94`;
- unchanged menu SHA256
  `b07df1f95ba71db09ebbb0b35a6989a1e1597388a03466f313b9eae649eeb198`;
- twelve additive clips under `ftesurf/cfg/ksfreplays/`, the alias cfg and the
  converter/inspector/manifest/docs/test tools, each checked against the inspected
  Git blob or independently checked staging bytes.

CSQC rollback `.prev` is kept in each install. The earlier `.prev` was preserved
as `csprogs.dat.prev.preksfreplay-20261014T120057Z`. The new checksum-named cache
payload was added without sweeping existing `.tmp`, `.dcl` or downloads.

The install's earlier-config hash assertion stopped after the asset copies:
the owner's active `ftesurf.cfg` had changed. The installer never writes that
path. No restoration or second swap was performed: a finish-only verifier
confirmed every package/progs/cache destination and retained the owner's current
config. Other inspected config hashes stayed unchanged; do not claim the shared
active owner config remained constant. Player data and owner processes were
neither edited nor stopped. Reload a local map to use the new CSQC.

## Pi deployment — pending, not claimed

The clean `build.ps1 -Pi` invocation discovered all twelve active lobbies, then
refused **before upload/swap/restart** because one player was connected on
surf_not_so_disaster. No `-PiForce` was used. Readback confirms the fleet still
serves old CSQC SHA256
`eb17be0d6b424c9f8005be345740a0ac6cbbe6dd738632a7d5251bdb2cc0b24a`;
SSQC already matches the tested source. The running owner/lobby was not dropped.
Do not interpret the Windows result as fleet deployment or a served-CSQC smoke.
Resume the ordinary guarded Pi deployment only when every active lobby has a
fresh zero-player heartbeat, then verify destination hashes and a fresh unseeded
client download. No server backend/database/engine rollout is needed here.

## Workspace retention

Owned task root: `C:/FTESurf-worktrees/ksfreplay-20261014T1025Z/`.
Seventeen stopped disposable runtime rigs were archived with all 22286 files
hash-verified, links stored as inert metadata, then retired. The exact junction/
hardlink cleanup control retained its target sentinel. The clean engine-doc
worktree was removed. Clean QC source, compiler/build staging, converted pack,
logs/review diffs and the compressed local evidence archive are retained for the
pending Pi gate. No source/player/library blanket cleaning was performed.
Local evidence can contain generated identities; do not export it unreviewed.
