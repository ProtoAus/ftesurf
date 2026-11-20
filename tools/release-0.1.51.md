# World of Surf 0.1.51 delivery

Published 20 Nov 2026, completing at **11:24:30 UTC** (worldofsurf-75) from the Linux PC: one sealed Windows/Linux
candidate, no rebuild after sealing. Lex asked for it: "when you're done, push a new release please" (after his
bkz_goldbhop_gs report, fixed by P1664/P1665). Page: <https://proto.bar/ftesurf>.

- Version **0.1.51** (`0.1.51+b89.p1665`), QC build 89. Frozen QC `2133769a` = main at the cut (branch
  `release-0.1.51`, tag `v0.1.51`). Everything under `## next` shipped: 20 patch entries (P1636-P1665).
- Shipped progs (Windows = Linux): qwprogs `16d8d397`, csprogs `276e5566` (appended to tasrevd `codes.txt`, backup
  `.pre0151-20261120T112621Z`), menu `0de592e4`. Online play uses each lobby's own csprogs.
- Engine main `7cb1d4f36` (= tag `patch-1665` `a9b79ba73` + its ENGINE_PATCHES records), stamp
  `git-8920-patch-1665-1-g7cb1d4f36` on both platforms.
  - Windows: `ftesurf64.exe` `299a3a56`, a clean mingw cross-build from this PC (release0151-75/tools/build-win64.sh).
  - Linux: `ftesurf64` `c6a64b2e`, built in an isolated Debian 11 rootfs (tools/linux/build.sh); gates all PASS, glibc
    2.30+. The drop also holds `fteplug_ui_imgui_amd64.so` (built by GCC 10 for the first time, gates PASS); it does
    not ship (`$LinuxShipImgui` off: installed launchers refuse a feed naming it).
- Launchers unchanged: the Windows bootstrap reused from 0.1.50 (`c8ce46f0`), the Linux one rebuilt in the rootfs from
  the same source (`6b0c39c2`, byte-identical to 0.1.49/0.1.50's).
- Prepared `1db0afa8c9ebbbdd4a9400315dca1dd0bd752ca9dad4466da3dab3ae2fb590dd`; receipt
  `7bc5ec85753e13c8399bf4c65386d2de123c18f7d210d5a015a62eeb843f719f`; signed feed `28e6fea8` (prev 0.1.50 `a96333f3`),
  1282 objects. Overrides: none.

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.51.7z` | 79,080,578 | `b9686eb16240bcb49975f6224a49e6c77b88ff8339bb3cc0164f1b0596a06e6d` |
| `ftesurf-0.1.51-linux-x86_64.tar.xz` | 79,052,704 | `6124342a3e0abbac6be695331738fe04e4a5e6090e10937a55215443de15f863` |
| `WOS-Launcher-0.1.51.exe` | 3,600,384 | `c8ce46f06b53ed9f5cbb35e55948b52e17dbcf01b84e6668e8325a0df46f83ff` |
| `WOS-Launcher-0.1.51-linux-x86_64` | 4,083,864 | `6b0c39c242ccfd369d054a2cef69442f59604f447e0d597ae4df5433a34628b6` |

## Acceptance

- Preparation (`-Bump patch -DryRun`, artifacts/prepare-0151.log): gates 1-4 PASS, Linux gates PASS, engine patch 1665,
  R2 write probe OK. `-PublishPrepared -DryRun`: 1282 objects verified locally.
- Before publishing, the staged Windows game ran under Wine from the prefix's `C:` (headless labwc; tools/winsmoke.sh):
  menu says 0.1.51, surf_prelude loads, bkz_goldbhop_gs loads as a Counter-Strike map with pm_viewheight 17, clean quit.
- `-PublishPrepared -VerifyFull` rc 0: both archives round-tripped with a full re-hash, edge serves byte ranges, both
  launchers and all 1282 objects round-tripped, Pi publish, page byte-verified, served feed exact and no-cache.
- `release_smoke.py` (default HTTPS, fresh synthetic installs, no game launch): linux64 1378 / win64 1379 managed files
  rehashed, 3 sentinels preserved each.

## On this cut

- Seeded the untracked ship files from 0.1.50's sealed stage (895 files: zones, particles, thumbnails, tables), plus
  `scripts/wadcolours.txt` (P1660, new) from the shared install. The install's own mapmeta/mapwr/matcolours have drifted
  since 0.1.50; they were not shipped.
- The preflight found a 259-character P1657 point (split on main, 2de605da) and two GoldSrc catalogue cache paths the
  ship guard did not know (runtime paths, 2133769a).
- release.ps1 takes the Linux engine label from the built commit's own ENGINE_PATCHES.md, so binaries built at the
  `patch-1665` tag (before its records commit) would have shipped as "engine patch 1663". Both platforms were rebuilt at
  the records commit. An incremental Windows build after a moved checkout kept the old stamp; build from a clean
  `engine/release`.
- The Wine smoke needs the game under the prefix's `drive_c` (from `Z:` the updater's link guard refuses) and a short
  XDG_RUNTIME_DIR (Wayland socket path limit).

## Scope and limits

Automated checks only; the in-game check is pending (lextest.md). Root `FTESurf-worktrees/release0151-75` keeps
`qc/dist`, `artifacts/` and `inputs/` until the next release.
