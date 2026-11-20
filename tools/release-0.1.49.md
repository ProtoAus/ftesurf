# World of Surf 0.1.49 delivery

## Published

Published 20 Nov 2026, completing at **05:12:55 UTC** (worldofsurf-ed). The first release cut and published from the
Linux PC. One sealed Windows/Linux candidate went out without a rebuild, repack or resign. Lex asked for the tournament
rollout ("please start the process!") and gave the go ("publish anything you need"). Page: <https://proto.bar/ftesurf>.

- Game version **0.1.49** (`0.1.49+b89.p1634`), qcbuild **89** unchanged.
- Frozen QC `5aaca356` on branch `release-0.1.49`: main `9e2c109d` (P1635), the Linux-host release tooling, and the
  P1639 code files from `448c6832`.
  - qwprogs `47745243` (P1634 + P1635 + P1639).
  - csprogs `2d0320d9` is the lobbies' live one, already in `tasrevd-state/codes.txt` since the P1635 lobby deploy.
  - The menu is `371f8a15`.
- Engine `patch-1634` `352f4fed1` (`git-8881-patch-1634-0-g352f4fed1`).
  - Windows: `ftesurf64.exe` `69b16910`, a mingw cross-build from this PC.
  - Linux: `ftesurf64` `52f208d7`, built in an isolated Debian 11 rootfs; the receipt's Linux gates all pass; glibc 2.30+.
  - worldofsurf-bb's P1636-P1638 are **not** in it; they stay under `## next`.
- Bootstrap source `8de1339` (unchanged). The Windows launcher is 0.1.48's published bootstrap, reused (same source
  fingerprint); the Linux launcher was built in the same rootfs.
- 37 player-facing patch entries, P1589-P1639.
- Prepared candidate SHA256 `21b61e0334de48fa46e764a1c8c8f9ced6efee03532ee3a3e482a3b47ede7b28`.
- Public receipt SHA256 `82c4067dfcce15f28a339f1e3f3c626a92594b1987b77d6dd5a82f5d2598f0f9`.
- Signed default feed SHA256 `64aee340bff36fced2cd6000c43a77f65114730ae887cc274d4d63e5188f5cdc` (prev 0.1.48
  `e1799f4e`). It references 1281 objects: 1380 Windows files and 1379 Linux files.
- Receipt overrides: **none**.

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.49.7z` | 78,962,269 | `30c27e62b95464e79b350260222979cc2f6750e69d23166aa4fd0292d62b560f` |
| `ftesurf-0.1.49-linux-x86_64.tar.xz` | 78,970,864 | `1658d27dbe55834fdb1f114ade38954a6147dca7d5891bd0c2725f908a62315d` |
| `WOS-Launcher-0.1.49.exe` | 3,600,384 | `c8ce46f06b53ed9f5cbb35e55948b52e17dbcf01b84e6668e8325a0df46f83ff` |
| `WOS-Launcher-0.1.49-linux-x86_64` | 4,083,864 | `6b0c39c242ccfd369d054a2cef69442f59604f447e0d597ae4df5433a34628b6` |

## Acceptance

- `-PublishPrepared -VerifyFull` checks, all of which passed:
  - both archives round-tripped with a full re-hash, and the edge serves byte ranges;
  - both launchers and all 1281 update objects round-tripped;
  - `publish.sh` ran on the Pi;
  - the page and the signed feed were verified byte for byte.
- `release_smoke.py` against default HTTPS, in fresh synthetic installs: win64 1378 / linux64 1377 managed files
  rehashed, 3 sentinels each, no game launch. On Linux, Wine runs the Windows launcher from its own `W:` drive.
- Before sealing, the cross-built Windows game passed a Wine smoke, run from the prefix's `drive_c`: on `Z:` the
  updater's link guard refuses, because Wine reports that drive as a reparse point.

## On this cut

- The first `-VerifyFull` stopped at its first upload: HeadObject returned 403 on `quakers-dl` (dl.proto.bar). This
  PC's rclone `r2` key is the read-only `ftesurf-public` token made on 17 Nov. Nothing had been uploaded.
  - Lex made a release-only token with Object Read & Write on `quakers-dl`. The publish used it through
    `RCLONE_CONFIG=~/.config/rclone/release.conf`; the everyday config stays read-only.
  - An offline preparation (`-Offline`) skips the R2 write probe. Run one online `-DryRun` before asking for the go.
- `release.ps1` needs `FTESURF_FTEROOT` on Linux: the `-FteRoot` default is a `C:\` path.
- After sealing, worldofsurf-bb dropped "such as surf_affliction at 10000" from P1631's point on main (0217caf0).
  - The published 0.1.49 notes still carry the old sentence.
  - The `## 0.1.49` section here keeps main's wording, which the next release republishes.

## Owed after this release

- Tournaments are still off. The backend generation (gen1635) and the lobby switch-on (lobbies 9-11) follow today.
  Until then the TOURNAMENT tab stays hidden.
- BACKLOG P1639 leads: tournament rooms need a 0.1.49+ client (an older menu cannot leave a 100-tick bhop room).
- Owner check pending in `lextest.md`.

## Scope and limits

This release had automated checks only; the in-game check is **pending**. Root
`FTESurf-worktrees/release0149-ed` keeps `qc/dist`, `artifacts/` and `inputs/` until the next release.
