# World of Surf 0.1.42 -- published 8 Nov 2026 (ftesurf-3a, at Lex's request)

Public page: https://proto.bar/ftesurf/

## Exact delivered snapshot

- QC/release source `d41e7226f2106677860440aa541ba32e09d798d3` (main), annotated tag `v0.1.42`. QC Build 89
  kept (not bumped, as 0.1.40/0.1.41). Three VMs 0 warnings, fteqcc 73f9a1a4 (P1412, -Fomitarraydefs).
  csprogs 0f0b5ae6 / qwprogs e1190bdf are the lobbies' live pair (codes.txt already had the csprogs); menu 0aa87c80.
- 52 patch entries under ## next since 0.1.41 (P1349-P1423), all shipped; P1422 (1d) and P1424 (b9) were not
  on main/tagged at the cut and ride the next release.
- Native `14f993f8525ee4a5013825378743f20d40be21a0` = tag `patch-1421` (P1410, P1413, P1417, P1421 under it).
  Windows set reused from ftesurf-b8's clean full build of that commit (exe 5798b897, sv d99cbbcb, hl2 2636df76,
  imgui 3ce587a2; hash-checked). Linux built in the release root by tools/linux/build-linux.ps1 from the same
  commit: fteqw64 f1fc5b76, hl2 c571ab92, sv 14959e6c, gates all PASS, glibc 2.30+.
- Launcher Quakers-Launcher `1538d9c` (unchanged since 0.1.37).
- Ignored inputs: allowlisted assets seeded from the public 0.1.41 archive (773 files, archive sha256 73aaadbb...),
  then only named newer install files overlaid: 118 particle bakes + data/mapparticles.txt (b587cb81, P1411/P1416)
  and data/mapdl.txt; the install's winter .wav masters and its older Colin roof were not taken. mapmedia
  refresh --atlas --export: 3288 tiers, 811 deps, 11 new hd thumbnails, 0 lost.

## Immutable publication

| Artifact | Bytes | SHA256 |
|---|---:|---|
| [Windows](https://dl.proto.bar/ftesurf/ftesurf-0.1.42.7z) | 78009372 | `5088aceb6cc073944a9fa37617aa3fd899ac6b0e27afe6dec4a2e12e5096ef67` |
| [Linux x86-64](https://dl.proto.bar/ftesurf/ftesurf-0.1.42-linux-x86_64.tar.xz) | 78097516 | `13bdab7814db2cabae08db0f825d45e2411867a78f6f6e90abbc7986c27fc750` |

Prepared candidate SHA256 `00998e9355f6a08fcb2ed1caf2f6c193dc96cbc5fce8bba9b1278c5727dfff69` (one preview, sealed,
published as is). Receipt SHA256 `ca4e9110c5c28043958f6fd6268265bb48441335a3d001a3c1092ccdd6c6ae2d`.
Signed update feed `c23243effc31a4259e9d5a9d26caf82f8cbbbe801266ec81c0cbd7ac1f5b1387` (previous `39eb63a0...`,
the live 0.1.41 feed), 1128 files / 1028 objects, 133.8 MB (launcher cap 160 MiB). Both archives downloaded back
in full and matched; both standalone launchers round-tripped; all 1028 objects verified before promotion; page
bytes exact, feed exact and no-cache. Upload ran at --bwlimit 512k (a player was online).

Default-HTTPS launcher acceptance (tools/release_smoke.py, fresh synthetic installs, no game): win64 1121 and
linux64 1120 managed files rehashed, 3 sentinels preserved on each.

## Preflight fixes made for this cut (main)

- PATCHNOTES: 12 points over releaselib's 250-character limit split at sentence ends (a41062a2).
- shipguard: DENY_EXACT for P1418's runtime crash record data/crash/error.txt (d41e7226).
- ENGINE.txt `commit` pin moved to 14f993f85 (it still named 9b4142baf while tag/patch said 1421).

Limits: archive/update acceptance, not a visual, frame-rate or play pass. Lobbies were not restarted for this
release (they already run the same game code). Root C:/FTESurf-worktrees/release0142-3a keeps the candidate,
logs and inputs.
