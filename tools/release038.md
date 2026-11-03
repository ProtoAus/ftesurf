# 0.1.38 — P1214-P1267 as delivered, with the patch-1266 engine

Published **0.1.38** on 3 Nov 2026 at ~14:25Z, at Lex's request ("bundle up all the updates please and push a
new release"). 51 patch entries; see PATCHNOTES.md `## 0.1.38`.

## What shipped

- QC = the delivered set. Frozen tree: tag v0.1.38 = 32bdd5ac (release/0138-20261103T1319Z): main fa153cfd's
  tooling, docs, site and menu, with the 11 client/server files that differ taken from origin/deploy/p1263-orbits
  c71e6e19 (live on the 12 lobbies): cl_fog, cl_main, sv_entities, sv_player, sv_pose, sv_resume, sv_saveloc,
  sv_taslegal, sv_tasproject, sv_timer, sv_zones. csprogs/qwprogs sources are byte-identical to the lobby line;
  menu.dat equals the installs' d92320af but for the compile date (P1244/P1258/P1265, and P1169, which only main's
  menu has). fteqcc c24ede65, 0 warnings x3.
- Left out (still under `## next`): P1161 and P1154, main-only TAS server work the lobby line has older versions of.
- Engine tag patch-1266 = 9e6c5806b (P1266 on 48's patch-1267, ac's patch-1264, 48's patch-1265, e2's patch-1262 ...;
  every engine tag since patch-1212 is an ancestor). Windows: build.ps1 -Engine -Full -NoDeploy -Jobs 3 in the
  release engine worktree, stamp git-8171-patch-1266-0-g9e6c5806b (16 hits); exe 60ef259c, hl2 205bf373,
  imgui 82f96e45. Linux drop linux-build-0138: all ten gates PASS, Debian 11 builder.
- Launcher Quakers-Launcher 1538d9c (unchanged since 0.1.37).
- Data: mapmedia_refresh found nothing new (25 files exported); 681 allowlisted assets copied from the dev install,
  including ac's P1263 ring bake (particles/surf_fantasy.cfg, data/mapparticles.txt); the three particles/*.pre*
  hand backups were skipped.

## Evidence

- Preflight PASS (51 patches, ship set 898 files). One prepare, exit 0: trusted SHA256
  `ad750d1c78e3db33fe651e07afb6d972d67395ae9167dd8ff6e3a2592329c595`; receipt
  `a42aec896fcc00ea5863f9d3a489ecfb18545ab48ee109a79a9312ef9880e080`. One warning: ENGINE.txt pin drift (1229 vs
  the release line's journal 1195), expected as for 0.1.37.
- -PublishPrepared -DryRun: 792 objects verified. -PublishPrepared -VerifyFull -Tag: 792 objects round-tripped,
  page and no-cache feed verified byte for byte.
- Windows `ftesurf-0.1.38.7z` 57.6 MB, sha256 `0712A12F6D528FA5D51B334C45CBD52F7D4111263E616A32D9E8BFE724F50872`.
- Linux `ftesurf-0.1.38-linux-x86_64.tar.xz` 57.6 MB, sha256 `B4446AEC0F3699B11D34E6BF912DB207743E83C8F46807340A8BF07C68644305`.
- release_smoke: fresh default-HTTPS installs, Windows 884 / Linux 883 managed files rehashed, 3 sentinels each,
  no game launch.

## Traps this time

- The background engine build was reaped twice for low memory (Firefox, Steam, Discord and four agent sessions on
  16 GB). It finished in the foreground at -Jobs 3 in under ten minutes.
- A fresh engine worktree has no engine/libs-x86_64-w64-mingw32: m-rel died on opus.h/speex.h. Copied the 72 MB
  cache from release0137's engine worktree (gitignored, tree stays clean).
- After the Linux build, vmmemWSL held 1.8 GB with no distribution running (free memory 755 MB); `wsl --shutdown`
  of the idle VM brought it to 4.4 GB before the prepare.
- The plugin build rewrites mat_vmt_progs.h's banner in the release engine worktree; restored before the prepare.

Task root: C:\FTESurf-worktrees\release0138-20261103T1319Z (OWNER.md, artifacts/, qc/dist candidate).
