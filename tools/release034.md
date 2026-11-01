# 0.1.34 — P1133-P1174 as delivered

Published **0.1.34** on 1 Nov 2026 at 12:51Z, at Lex's request ("combine the updates and push a new
update for the game for the launcher"). 23 patch entries; see PATCHNOTES.md `## 0.1.34`.

## What shipped, and how it was chosen

main held undelivered QC, so this is the DELIVERED set, not a blanket main build:
- QC source = 3cc4fec7 (P1170 6d132181 + P1171), live on both installs and all 12 lobbies since
  11:46Z. A c24ede65 NoDeploy build of it was byte-identical to the installed menu 14ecde0a, cs
  974f0ce9 and qw e487377c. The release's csprogs/qwprogs ARE those bytes; menu.dat differs only by
  the release version. Frozen tree: tag v0.1.34 = 71de8c24 (release/0134-20261101T1137Z): main
  4f231eb0's tooling/docs, src/ (except build.ps1) from 3cc4fec7, ENGINE.txt pinned to P1173.
- Left out (still under `## next`): P1169 Maps fonts (1/51 added lines in the shipped menu), P1154
  (TAS clock binding 3ef2327b absent), P1161 (cold TAS loads cd12d607/062a12dc absent), and the
  Collectors note (backend, says it is not active).
- Engine 117124a41 (patch-1173). Windows stamp 16x git-8074-patch-1173-0-g117124a41; the exe equals the
  installed addf0956 except 28 build-path strings (.pdata/.xdata/.reloc identical). Linux: Bullseye
  BUILDINFO gates all PASS, same stamp, glibc floor 2.30 with the bootstrap.
- Launcher 646c8d1, same as 0.1.33 (launcher origin/main). Data: ftesurf-2b's 9 P1174 zones (sha1 =
  its receipt), atlas10, mapmeta/mapdl. QC build 89 unchanged.

## Evidence

- Prepared SHA256 `6081e1c2ca1faebf3de71337ec04f9e1a24443cedf4573ea0f665a8c88bb1314`; receipt
  `e50ed4eb700914bf6ae019daf2f8696b4dcfdee4d563dc2d683026d4a988fdf5`; feed `27c212fd8d6b016e…`.
- Windows `ftesurf-0.1.34.7z` 42.7 MB, sha256 `53926dc2756c40dacc03271c081c96dc5a24a471ab048a5dad3fdab533c689b1`.
- Linux `ftesurf-0.1.34-linux-x86_64.tar.xz` 42.6 MB, sha256 `c2f0ea52e25faa8d9678b08ce3a6a6ea0b5f8d6624abde5ab59e32f7af07b04a`.
- One prepare, one -PublishPrepared: 778 objects round-tripped, both launchers and archives match,
  page and no-cache feed byte for byte, live predecessor 0.1.33 checked. Feed vs 0.1.33: +10 files
  per platform (9 zones, atlas10), 13/11 changed, none removed.
- release_smoke: fresh default-HTTPS installs, Windows 870 / Linux 869 managed files rehashed, 3
  sentinels each, no game launch. The 0.1.33 launcher (`--dir <empty> --yes --no-launch`) installed
  0.1.34 from the live feed: exe, three progs, a P1174 zone and atlas10 = the release stage.
- Not claimed: in-game, real-account or Linux desktop acceptance (lextest.md).

## Traps

- A fresh engine worktree needs a libs cache (copied from fteqw-imgui-input/engine/libs-x86_64-w64-mingw32);
  without it m-rel fails on opus.h, and under -Jobs 2 that looked like a make stall.
- build.ps1 rewrites the comment in plugins/hl2/mat_vmt_progs.h with the worktree path; the prepare
  then refuses the engine as dirty. Restore the file (comment only) before preparing.
- release_smoke.py needs an OWNER.md in an ancestor of --work-root.
- Task root: C:\FTESurf-worktrees\release0134-20261101T1137Z (OWNER.md, artifacts/, qc/dist candidate).
