# World of Surf 0.1.50 delivery

Published 20 Nov 2026 ~10:20 UTC (worldofsurf-ed) from the Linux PC, one sealed candidate, no rebuild. A QC-only
release on 0.1.49's engine and launchers that brings the tournament menu (P1651) to players; Lex's go: "publish
anything you need" (and the stream request). Page: <https://proto.bar/ftesurf>.

- Version **0.1.50** (`0.1.50+b89.p1634`), QC build 89. Frozen QC `0d643dac` on `release-0.1.50` = `release-0.1.49`
  (`5aaca356`) + `sv_tournament.qc`, `cl_tournament.qc`, `cl_main.qc`, `m_tournament.qc` byte-identical to main
  `08f6ee47`. Main's other unreleased QC (settings page, zone editor, HUD, console, GoldSrc, P1643/P1652/P1657) is NOT
  in it; it stays under `## next`.
- Shipped progs (Windows = Linux): qwprogs `10660374`, csprogs `53ab066e` (appended to tasrevd `codes.txt`, backup
  `.pre0150-20261120T101530Z`), menu `79c9aeb4`. Online play uses each lobby's own csprogs.
- Engine `patch-1634` `352f4fed1` unchanged: `ftesurf64.exe` `69b16910`, `ftesurf64` `52f208d7`.
- Prepared `5ce2ff6d57e8c26867fbce21bb9b5184050d14fa49ece5027b55b83c186b6d04`; receipt
  `2892d5298b42ebf8fab35f4f7bce122abeb3a906a919c2f6d56cc0554e765188`; signed feed `a96333f3` (prev 0.1.49 `64aee340`),
  1281 objects. Overrides: none.

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.50.7z` | 79,007,861 | `f9023ed4b8c450c630ccd722a9ccd076761f2fae8632e27571ed6f709d65b77c` |
| `ftesurf-0.1.50-linux-x86_64.tar.xz` | 78,980,696 | `f7b3e2b474a1183bec99e0f6d0502a13cef16b087ef517e6f0222ad7cf09b60c` |

Acceptance: `-PublishPrepared -VerifyFull` rc 0 (archives and 1281 objects round-tripped, Pi publish, page byte-verified,
served feed exact and no-cache); `release_smoke.py` win64 1378 / linux64 1377 managed files rehashed, no game launch.
Root `FTESurf-worktrees/release0150-ed` (OWNER.md, artifacts/prepare-0150.log, publish-0150.log); R2 through
`RCLONE_CONFIG=~/.config/rclone/release.conf`. Owner check: lextest.md.
