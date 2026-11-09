# World of Surf 0.1.43 -- published 9 Nov 2026 (ftesurf-3a, at Lex's request)

Public page: https://proto.bar/ftesurf/

Lex: "push a new release now and get it over with" -- after P1440's crate fix. The collision follow-up (P1445) was
left out by Lex's choice: collision feeds run verification, so it needs a pm_sourceversion bump (TAS pins refuse, no
lobby rollback past it, an evidence review); it is parked on engine branch p1445-collision.

## Exact delivered snapshot

- QC/release source `6f4439ad` (main), annotated tag `v0.1.43`. QC Build 89 kept (not bumped). Three VMs 0 warnings,
  fteqcc 73f9a1a4 (P1412). csprogs e84310b0 / qwprogs cafb0be2 are the lobbies' live pair (codes.txt already had the
  csprogs); the lobbies were not restarted.
- 17 patch entries since 0.1.42, all live before the cut: P1422, P1425, P1426, P1428, P1430-P1433, P1435-P1442 and
  P1444 (a diagnostic cvar, off by default). P1443's engine op (local) and P1445 (parked) are not in.
- Native `18f0514b4a42c97953559d92dcf4e8c1e6d88c0c` = tag `patch-1444` (P1444 on P1440 on P1442). Windows built clean in
  the release root: exe 174131c2, hl2 73bd8616, imgui 3eb11549 (git-8574-patch-1444-0-g18f0514b4, 16/10 stamps). Linux
  built in-root by tools/linux/build-linux.ps1: fteqw64 d7deba97, hl2 d64b10cd, sv e25247e7, gates all PASS.
- Launcher Quakers-Launcher `1538d9c` (unchanged since 0.1.37).
- Ignored inputs: allowlisted assets seeded from the public 0.1.42 archive (892 files, archive sha256 5088aceb...),
  then only data/mapdl.txt overlaid from the install (newer); the install's Colin roof and winter .wav masters were
  not taken, as for 0.1.42. mapmedia refresh --atlas --export: 3282 tiers (6 maps gone from the API), 811 deps, 0 new
  hd thumbnails.

## Immutable publication

| Artifact | Bytes | SHA256 |
|---|---:|---|
| [Windows](https://dl.proto.bar/ftesurf/ftesurf-0.1.43.7z) | 78082124 | `d2fecd51c6fe466661328777178eff8e4dc9d6e02512073363d8511ab941c0c8` |
| [Linux x86-64](https://dl.proto.bar/ftesurf/ftesurf-0.1.43-linux-x86_64.tar.xz) | 78173500 | `77224dba835509a52011cf74904dfc98b6e54a21323b1b75321e12391754e23a` |

Prepared candidate SHA256 `44bf050671b782c1ff94d23b45c64eb609975b70cd3489674979bd1b57f6939c` (one passing preview,
sealed, published as is). Receipt SHA256 `278608cafd20bbd9617349fe556868a7163423baa5b2b618c340cb3b4bef5c02`.
Signed update feed 4f85c6b7... (previous c23243ef..., the live 0.1.42 feed), 1128 files / 1028 objects. Both archives
round-tripped in full; both standalone launchers matched their verified bootstraps; all 1028 objects verified before
promotion; page bytes exact, feed exact and no-cache. Upload at --bwlimit 3M (all lobbies empty).

Default-HTTPS launcher acceptance (tools/release_smoke.py, fresh synthetic installs, no game): win64 1121 and
linux64 1120 managed files rehashed, 3 sentinels preserved on each.

## Preflight fixes made for this cut (main)

- ENGINE.txt pin moved to 18f0514b4 / patch-1444 (76fccd30).
- PATCHNOTES: four points over releaselib's 250-character limit split at sentence ends (5e89052c, 9f148c2a).
- shipguard: DENY_EXACT for P1435's mounted explosion sounds sound/weapons/explode3.wav and debris1.wav (6f4439ad).
- Release-root traps (not source): the P1412 fteqcc copied into qc/src, the Windows natives into qc/ under the
  ShipRootFiles names.

Limits: archive/update acceptance, not a visual, frame-rate or play pass. Root C:/FTESurf-worktrees/release0143-3a
keeps the candidate, logs and inputs.
