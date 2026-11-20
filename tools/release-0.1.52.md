# World of Surf 0.1.52 delivery

Published 20 Nov 2026 (21 Nov local), completing at **13:52 UTC** (worldofsurf-75) from the Linux PC, one sealed Windows/Linux candidate,
no rebuild after sealing. Lex asked for a launcher auto-updater ("make a auto updater for the launcher or whatever you need
please"); P1667 was found while testing it, and a friend's log (20 Nov) showed the same abort on a real desktop.
Page: <https://proto.bar/ftesurf>.

- Version **0.1.52** (`0.1.52+b89.p1667`), QC build 89. Frozen QC `c6e6102c` = main at the cut (branch `release-0.1.52`,
  tag `v0.1.52`). Two patch entries: P1667 (Linux starts on Wayland compositors with wl_compositor v6), P1666 (the game
  keeps the launcher current).
- Shipped progs (Windows = Linux): qwprogs `9879822f`, csprogs `b915c60f` (appended to tasrevd `codes.txt`, backup
  `.pre0152-20261120T135516Z`), menu `84b30795`.
- Engine main `db8de41f0` (tags patch-1666 `b5ee0e1c3`, patch-1667 `9e23c98c7`, + records), stamp
  `git-8928-patch-1666-1-gdb8de41f0` on both platforms. Windows `ftesurf64.exe` `5eea3fde` (clean mingw cross-build);
  Linux `ftesurf64` `debb1eae` (Debian 11 rootfs, gates all PASS, glibc 2.30+).
- Launchers unchanged (Windows bootstrap reused, Linux rebuilt byte-identical). The signed feed now names them in
  "launcher" for the first time (blake2b win64 `8025e42f`, linux64 `223754d7`), so 1284 objects (was 1282).
- Prepared `a56833b36a9c4661be5dfc777009ae808ef163d0fe93773bbab8e711769b4b94`; receipt
  `71453f61df1e6804e374a30e861aaaf6456b012bf4be67a0b476fb7d055c14ae`; signed feed `76014d86` (prev 0.1.51 `28e6fea8`).
  Overrides: none.

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.52.7z` | 79,081,167 | `a7167fc40008b26171d7b566126ae4018701f363d13e865ff1ec646a51f8956f` |
| `ftesurf-0.1.52-linux-x86_64.tar.xz` | 79,092,740 | `7b54a76ae7fcf783337a5e48cb09d067646f88ed61d39806096ac8df5922596b` |
| `WOS-Launcher-0.1.52.exe` | 3,600,384 | `c8ce46f06b53ed9f5cbb35e55948b52e17dbcf01b84e6668e8325a0df46f83ff` |
| `WOS-Launcher-0.1.52-linux-x86_64` | 4,083,864 | `6b0c39c242ccfd369d054a2cef69442f59604f447e0d597ae4df5433a34628b6` |

## Acceptance

- Preflight PASS (2 patches); preparation gates 1-4 PASS, Linux gates PASS, engine patch 1667, R2 probe OK; the sealed
  feed's "launcher" entries match the staged launchers and pass the kind check; `-PublishPrepared -DryRun` 1284 objects.
- NEW Linux game smoke (release0152-75/tools/linuxsmoke.py): a copy of the Linux stage under headless labwc (Wayland,
  gles2) loads surf_prelude and bkz_goldbhop_gs (eye 17), screenshots, quits rc 0. The same smoke on the published 0.1.51
  stage aborts ("listener function for opcode 2 of wl_surface is NULL", SIGABRT): it discriminates.
- Wine smoke of the Windows stage from the prefix's C:: 0.1.52 menu, both maps, eye 17, clean quit.
- `-PublishPrepared -VerifyFull` rc 0; `release_smoke.py` linux64 1378 / win64 1379 managed files, 3 sentinels each.
- Production P1666 check (tools/p1666prod.py): an install of the Linux stage installed by its launcher from the live feed,
  WOS-Launcher made stale, the 0.1.52 engine's check replaced it from dl.proto.bar ("update: launcher updated WOS-Launcher").

## Scope and limits

Automated checks only; the in-game owner check is pending (lextest.md). The Linux ImGui plugin still does not ship
(BACKLOG P1666-P1667: the new Linux launcher can now reach players through P1666, but the Windows launcher build path is
the blocker). Root `FTESurf-worktrees/release0152-75` keeps `qc/dist`, `artifacts/` and `inputs/` until the next release.
