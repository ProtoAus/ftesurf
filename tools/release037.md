# 0.1.37 — P1201-P1213 as delivered, with the P1211 + P1213 engine

Published **0.1.37** on 2 Nov 2026 at ~13:00Z, at Lex's request ("push a new update so everyone can
have it via launcher"). 13 patch entries; see PATCHNOTES.md `## 0.1.37`.

## What shipped

- QC = the delivered set: origin/deploy/p1211-gravity 82ec7e1c (live on the 12 lobbies and both
  installs) over main's tooling. Frozen tree: tag v0.1.37 = 15b39135 (release/0137-20261102T1233Z):
  main cbc6826e's tooling, docs and site with every src file that differs taken from 82ec7e1c (13
  files; src/build.ps1 and src/release/ stay main's). `## next` there = P1201-P1213.
- Left out (still under `## next`): P1169, P1161, P1154 and Collectors, as for 0.1.35/0.1.36.
- Engine patch-1211 = 1d0c8c897: P1211 (gravity prediction, per-command gravity) merged with
  2b's patch-1213 (radial fog, vmt/unlit) on patch-1212 (e2's P1201/P1209/P1212). Windows:
  build.ps1 -Engine -Full -NoDeploy in the release engine worktree, stamp
  git-8090-patch-1211-0-g1d0c8c897; exe 6fbf7e74 (World of Surf version info, r_fog_radial,
  predinput_version), hl2 c75a26f5 (hl2_unlitprogram), imgui 443b30a4. Linux drop linux-build-0137
  (BUILDINFO gates all PASS, glibc 2.29 <= 2.35).
- Launcher Quakers-Launcher 1538d9c (e2's P1208/P1209/P1212): WOS-Launcher-0.1.37.exe, CompanyName
  World of Surf; the feed omits both launcher names.
- Data: mapmedia_refresh found nothing new; 680 allowlisted assets copied from the dev install.

## Evidence

- Prepared SHA256 `66c28d2c648f5bbce1afa916d9cce063a3c4d4bc16b2b1dd775b1c4c4603c550`; receipt
  `6b09aabf237e064041209f416fe445c792944a977231a72c426af515fa33bc54`.
- Windows `ftesurf-0.1.37.7z` 57.6 MB, sha256 `71A1C68F590F6F5D61001AB66A9A55977E3923141A94AB4D2889E1145B1B167A`.
- Linux `ftesurf-0.1.37-linux-x86_64.tar.xz` 57.5 MB, sha256 `54AE22B449E5DE347549CC7955F883A7DF7141DE4759B6468DBD8B149BAD3555`.
- Two prepares refused before sealing (the -BuildEngine filter; a regenerated header dirtying the
  engine worktree; BACKLOG), then one clean prepare, one -PublishPrepared -DryRun (790 objects),
  one -PublishPrepared -VerifyFull -Tag. One warning: ENGINE.txt pin drift (1213 vs the release
  line's journal 1195), expected.
- release_smoke: fresh default-HTTPS installs, Windows 882 / Linux 881 managed files rehashed, 3
  sentinels each, no game launch.
- The 0.1.36 launcher (ftesurf-launcher-0.1.36.exe --dir <empty> --yes --no-launch) installed
  0.1.37 (exe 6fbf7e74; no launcher file, as the feed omits it).
- e2's acceptance with the release launcher: test_update_wrappers PASS, test_launcher_dev_handoff
  exit 0; the menu restart handoff run by e2.
- Both installs run the release engine (exes and plugins, `.prev` = e2's patch-1212 a2a97860).
- Task root: C:\FTESurf-worktrees\release0137-20261102T1233Z (OWNER.md, artifacts/, qc/dist candidate).
