# World of Surf 0.1.44 -- published 10 Nov 2026 ~11:29Z (ftesurf-b8, at Lex's request)

Public page: https://proto.bar/ftesurf/

Lex: "publish a new release with all the new patches for people to download". Cut after Jargon's rounds 2-3 and
P1476 were delivered to both installs and the lobbies. P1477 (forced water captures staggered, ftesurf-1d) was not
installed at the cut and rides the next release.

## Exact delivered snapshot

- QC/release source `644dc343` (main), annotated tag `v0.1.44`. QC Build 89 kept (not bumped). Three VMs 0 warnings,
  fteqcc 73f9a1a4 (P1412). csprogs 01d9d44e / qwprogs 91ef42d5 are the lobbies' live pair (deployed 10 Nov ~22:20 local
  from main 60ccc0e7, the same game code; codes.txt already had the csprogs); menu 06a1ee1f (carries the version).
- 20 patch entries since 0.1.43: P1475, P1474, P1472, P1470, P1465/P1463/P1457, P1464, P1462, P1461, P1460, P1459,
  P1458, P1454, P1453, P1452, P1451, P1449 (Jargon, with P1466/P1467/P1476's engine side), P1447, P1446, P1448, P1443.
- Native `0b223e6148922c36687e6abc5aa4b5122df7634e` = tag `patch-1476` (P1476/P1467/P1466 on patch-1475). Windows built
  clean in the release root: exe 2c585d12, hl2 1338e1ed, imgui 1dbe1541 (git-8646-patch-1476-0-g0b223e614). Linux built
  in-root by tools/linux/build-linux.ps1: fteqw64 ff99fa30, hl2 e3de13bc, sv acf9ade6, gates all PASS.
- Launcher Quakers-Launcher `1538d9c` (unchanged since 0.1.37).
- Ignored inputs: allowlisted assets seeded from the public 0.1.43 archive (892 files, archive sha256 d2fecd51...),
  then only data/mapdl.txt overlaid from the install (newer); the install's Colin roof and winter .wav masters were not
  taken, as for 0.1.43. mapmedia refresh --atlas --export: 3288 tiers, 811 deps, 1 new hd thumbnail.

## Immutable publication

| Artifact | Bytes | SHA256 |
|---|---:|---|
| [Windows](https://dl.proto.bar/ftesurf/ftesurf-0.1.44.7z) | 78430499 | `97298d6c863f46e7196c3fef46764ae0392d7ac81c9cfd012b1976d89900fe94` |
| [Linux x86-64](https://dl.proto.bar/ftesurf/ftesurf-0.1.44-linux-x86_64.tar.xz) | 78518800 | `dcfabde3213cf3be390d083bfa26f6b42eda957684ee0f32a33143aa4d14b727` |

Prepared candidate SHA256 `0a0a914897d91ead523bcc33add4d5d86d47c788f45e723abde47242df764a93` (one passing preview,
sealed, published as is). Receipt SHA256 `4cd64a0f2b70716935785f2f72135e6a57834b4d5371ba6b432ba3693111a308`.
Signed update feed 5dfd406f... (previous 4f85c6b7..., the live 0.1.43 feed), 1142 files / 1038 objects. Both archives
round-tripped in full; both standalone launchers matched their verified bootstraps; all 1038 objects verified before
promotion; page bytes exact, feed exact and no-cache. All lobbies empty during the upload.

Default-HTTPS launcher acceptance (tools/release_smoke.py, fresh synthetic installs, no game): win64 1135 and
linux64 1134 managed files rehashed, 3 sentinels preserved on each.

## Preflight fixes made for this cut (main)

- ENGINE.txt pin block's patch line 1475 -> 1476 (771bb712).
- PATCHNOTES: P1446's first point over releaselib's 250-character limit split at its sentence end (84463e53).
- shipguard: DENY for P1453's loading-screen sample models (models/props/de_dust/dust_crate.mdl, a CS:S prop;
  models/disres_models/dagger.mdl, a map's own) and P1448/P1449's cfg/ksfreplays/ (per-player downloads) (644dc343).
- Release-root traps (not source): the build rewrites plugins/hl2/mat_vmt_progs.h's banner in the engine worktree, and
  the prepare refuses a dirty input (`git checkout --` it); release_smoke.py needs its own folder on sys.path (no
  `python -I`) and a work root that does not exist yet.

Limits: archive/update acceptance, not a visual, frame-rate or play pass. Root C:/FTESurf-worktrees/release0144-b8
keeps the candidate, logs and inputs.
