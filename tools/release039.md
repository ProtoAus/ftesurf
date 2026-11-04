# 0.1.39 -- P1268-P1292 as delivered, with the patch-1292 engine

Published **0.1.39** on 4 Nov 2026 at ~11:55Z, at Lex's request ("Can you and the other bot wrap up and create a new
release with everything new added please"), cut by ftesurf-2b (e2, ac and 48 frozen). 24 patch entries; see
PATCHNOTES.md `## 0.1.39`.

## What shipped

- QC = the delivered set, as 0.1.38. Frozen tree: tag v0.1.39 = bd24f211 (release/0139-20261104T1033Z): main's tooling,
  docs, site and menu (through P1294 b6bb690c), with the 11 client/server files that differ taken from the lobby line
  origin/deploy/p1289-replayzero ad09e488 (= deploy/p1293-gfxbakes 96e44570 for those files): cl_fog, cl_main,
  sv_entities, sv_player, sv_pose, sv_resume, sv_saveloc, sv_taslegal, sv_tasproject, sv_timer, sv_zones. fteqcc
  c24ede65, 0 warnings x3. Left out (still under `## next`): P1161 and P1154, main-only TAS work.
- Engine tag patch-1292 = 82d3bebc5 (every install tag since patch-1266 is an ancestor). Windows: build.ps1 -Engine -Full
  -NoDeploy -Jobs 3 in the release engine worktree, stamp git-8211-patch-1292-0-g82d3bebc5 (16 hits); exe 98ad73d5,
  hl2 d9a913ab, imgui 67dd8620. Linux drop linux-build-0139: all gates PASS.
- Launcher Quakers-Launcher 1538d9c (unchanged since 0.1.37).
- Data: mapmedia_refresh packed 9 hd thumbnails; 737 + 56 allowlisted assets copied from the dev install, including
  ramp wear (23 maps) and the snow masks (5 maps) under gfx/ (P1293).

## Two blockers found and fixed before the cut

- P1293: the ramp-wear and snow-mask bakes lived in data/ and textures/ subfolders no installed launcher manages; a
  feed naming them is refused whole by every launcher. Moved under gfx/ (QC, tools, ship globs, both installs, the
  lobbies via deploy/p1293-gfxbakes).
- P1294: the feed listed every file per platform and came to ~214 MiB against the launchers' 160 MiB. Shared files
  are now "all" entries (supported by every launcher since 5c60f69 and the engine updater): 117 MiB, 953 entries.
  Real 0.1.38/0.1.39 launchers on Windows and Linux update a per-platform install to a merged feed with 0 objects;
  both engines' updaters apply one. Reviewed (no findings).

## Evidence

- Preflight PASS (24 patches, ship set 961 files). Prepare, exit 0: trusted SHA256
  `7cf829f66aa466b2c8ec1ddecfe255e53d177025fbf87d411f87af4fee9fd99c`. Two earlier prepares failed before sealing (a 96 MB
  stage tripwire, raised to 128 for the new assets; then the feed limit, which P1294 fixed).
- -PublishPrepared -DryRun: 854 objects verified. -PublishPrepared -VerifyFull -Tag: 854 objects round-tripped, page and
  no-cache feed verified byte for byte.
- Windows `ftesurf-0.1.39.7z` 72.4 MB, sha256 `EB5CBB91FBD04717422D7172D5342CD809CF461CE86D2DEF99E55A81EDBC5C22`.
- Linux `ftesurf-0.1.39-linux-x86_64.tar.xz` 72.4 MB, sha256 `AA39E600B9B70374F3E7B94C8CB4BCC7711A9E1CF82EEE0DB5A7DCEFE86C66EF`.
- release_smoke: fresh default-HTTPS installs, Windows 946 / Linux 945 managed files rehashed, 3 sentinels each, no game
  launch.
- Both installs run the release natives since 12:03Z (backups *.pre0139-20261104T120323Z; ac's patch-1292 exe 16408c21
  and plugin d8b18216 before them).

Task root: C:\FTESurf-worktrees\release0139-20261104T1033Z (OWNER.md, artifacts/, qc/dist candidate).
