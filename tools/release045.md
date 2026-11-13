# World of Surf 0.1.45 -- published 13 Nov 2026 04:38Z (ftesurf-16, at Lex's request)

Public page: https://proto.bar/ftesurf/

Lex: "deploy and release an release" -- cut right after P1531 was delivered to both installs and the lobbies.

## Exact delivered snapshot

- QC/release source `b2a562e5` (branch `release-0145` = main 1bda992c plus one notes-only commit), annotated tag
  `v0.1.45`. QC Build 89 kept. Three VMs 0 warnings, fteqcc 1f2efd06 (P1505). csprogs 3a52a7c9 / qwprogs 3fb10353 are
  the lobbies' live pair (P1531, deployed 13 Nov 01:47Z; codes.txt already had the csprogs); menu 23939878 (carries the
  version).
- 47 patch entries since 0.1.44, P1478 to P1535. Left out, still under `## next`: P1521, P1524 and P1529, whose native
  parts (in_generic.c, pm_source.c) come after patch-1517 and whose review and rollout were pending (P1529's record
  says so); the release tree dropped their entries. P1536 landed on main after the cut.
- Native `9aa225a8f3c19070b9b7a18fd004603a98604a1d` = tag `patch-1517`, the commit both installs run (exe 1799454a, built
  elsewhere). Windows built clean in the release root with build.ps1 -Engine -Full -NoDeploy: exe 9c1e5275, hl2
  8be64184, imgui 08358c8e (git-8709-patch-1517-0-g9aa225a8f, 16 stamps in the exe); the same 74 standing C warnings as
  0.1.44's build; engine/tools/check_tls_refptr.py 0 plain-address uses. Linux built in-root by
  tools/linux/build-linux.ps1: fteqw64 232a268a, hl2 66f114ff, sv ddda8aff, gates G1-G10 PASS. ENGINE.txt's pin
  (2274050a, patch 1535) left as is; the prepare's drift warning is the one its comment describes.
- Launcher Quakers-Launcher `1538d9c` (unchanged since 0.1.37).
- Ignored inputs: allowlisted assets seeded from the public 0.1.44 archive (893 files, sha256 97298d6c...), then only
  data/mapdl.txt overlaid from the install; the install's Colin roof and winter .wav masters not taken, as before.
  mapmedia_refresh --atlas --export: 3289 tiers, 811 deps, 3 new hd thumbnails (both installs updated).

## Immutable publication

| Artifact | Bytes | SHA256 |
|---|---:|---|
| [Windows](https://dl.proto.bar/ftesurf/ftesurf-0.1.45.7z) | 78468659 | `9ce5af7bee1750fb7aae2e5e9320567f5ac419be12f0708d23ad2308602c1704` |
| [Linux x86-64](https://dl.proto.bar/ftesurf/ftesurf-0.1.45-linux-x86_64.tar.xz) | 78589920 | `b1c33dbc79efada8a7b972702d4919ed6e41434da2fa685a4328842c41552e9c` |

Prepared candidate SHA256 `e899b7a4481b26b86e3c58b8ae240197011ae68e847ebb280e0f8c5f6fb68214` (one passing preview,
sealed, published as is). Receipt SHA256 `fd2a4abdfc13c6c2c786e320fcbad0709396785748b14997002d21d38d1787c7`.
Signed update feed 41e7a976... (previous 5dfd406f..., the live 0.1.44 feed), 1143 files / 1039 objects, 138191684 bytes
(131.8 of the launchers' 160 MiB). Both archives round-tripped in full; both standalone launchers matched their verified
bootstraps; all 1039 objects verified before promotion; page bytes exact, feed exact and no-cache.

Before publication: the Jargon panel test (tools/jgpanel.py in jargon-courses-1111a) passed 27/27 on the staged Windows
exe, hl2 plugin and game code. Default-HTTPS launcher acceptance (tools/release_smoke.py, fresh synthetic installs, no
game): win64 1136 and linux64 1135 managed files rehashed, 3 sentinels preserved on each.

## Notes fixes

- Before the cut (main): P1497's and P1486's points split under 250 characters (4979c0dc); P1512's headingless point
  given its heading (1bda992c).
- Published defect: P1483's points were wrapped over indented lines, which the parser skipped, so four of its five points
  are cut mid-sentence on the 0.1.45 page (0.1.38's P1237 and P1233 the same since 0.1.38). Main now has them as one-line
  points, so the next release's page renders them whole, and ConvertFrom-PatchNotes refuses an indented line inside a
  patch.

Limits: archive/update acceptance plus one panel run, not a visual, frame-rate or full play pass. The old-launcher
upgrade path was not run separately (launcher source unchanged; release_smoke ran it). Root
C:/FTESurf-worktrees/release0145-16 keeps the candidate, logs and inputs.
