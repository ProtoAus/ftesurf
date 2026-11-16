# World of Surf 0.1.48 delivery

## Published

Published 16 Nov 2026, completing at **09:02:44 UTC** (ftesurf-06), from one successfully previewed, sealed
Windows/Linux candidate, without rebuilding, repacking or resigning. Lex asked for it so P1588 (local games predict save
loads) reaches players. Page: <https://proto.bar/ftesurf>.

- Game version **0.1.48**, qcbuild **89** unchanged.
- Frozen QC `a7f81bf8` (main: the P1588 records and this claim).
  - qwprogs `ccf0d9a4` is the lobbies' live one.
  - csprogs is `cc032a87`, which carries P1587's config move and P1588's text rule.
  - The menu is `39d64915` (P1586's tier-9 terms; the version).
- Frozen engine `aa3294bab126df50480b6c92ca609854ad10ee86`, `patch-1588`, stamp `git-8811-patch-1588-0-gaa3294bab`.
  It carries P1586 (hook scan), P1587 (water/glass defaults) and P1588 on 0.1.47's patch-1581. P1585 is not in it.
- Bootstrap source `8de1339` (unchanged).
- 3 player-facing patch entries: P1588, P1587, P1586.
- Prepared candidate SHA256 `cfee2483f186e2e89a106672ae4fe2dcedc3420dea7b7d27c983d88e6a3994dd`.
- Public receipt SHA256 `51f837f531978f0ee24d1b8d03ce3497685d91dcc32fe351cdd7f78955b66b95`.
- Signed default feed SHA256 `e1799f4e4d1358ff9e275fac4b07e6327782a31688c824223c50117b45a35992` (prev 0.1.47
  `d141c5cc`): 1145 files, 1041 objects.
- Receipt overrides: **none**.

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.48.7z` | 78,768,058 | `06a85344aeaebcc9fead996f4c88f7d4d3181f0fbb2f1a7589c9eea3bede1dbc` |
| `ftesurf-0.1.48-linux-x86_64.tar.xz` | 78,854,668 | `7b6b21be6763397ca2f343898538ace70e545a94351341ab3cb3125aac199e03` |

## Qualification and acceptance

- QC 0 warnings.
- Windows full build: the same 47 distinct warning messages as 0.1.47's, DLL imports identical to 0.1.47's. Linux: the
  10 gates pass. Stage 126.9 MB.
- Staged save-lock arm, dedicated server + client (tmp/staged_arm.py, the staged exe, plugin, qwprogs and menu):
  - lead-in reads back 0;
  - at delay 0, one 242 u teleport at +0.018 s;
  - at 250 ms, landed before the first frame;
  - prederr 0, no text.
- Staged local game (tmp/listen_arm.py, the staged exe hosting surf_dune, real 0.2 s presses):
  - sv_minping 0 and 300: every held row predicted (19/19, 21/21);
  - moving 0.01-0.02 s after release;
  - no "Loading save", prederr 0.
  - 0.1.47 froze to +0.61 s there and flashed the text (tools/p1588-localload.md).
- `release_smoke.py`: win64 1138 / linux64 1137 managed files rehashed, 3 sentinels each.
- Upgrade path: the published 0.1.47 archive, unpacked, updated itself with its own launcher. All 1139 game files are
  identical to the 0.1.48 stage; the launcher is omitted from the feed, as intended.
- TAS credit list: csprogs cc032a87 appended to `tasrevd-state/codes.txt` (147 -> 148, `.pre1588`).
- Both installs received the exe, both plugins, `fteqwsv64.exe` (patch-1588), menu and csprogs at 09:03Z, each with
  `.prev` (the main install was on ftesurf-31's P1586 exe 31354ac0; C:\FTEQuake on 0.1.47's d3b7d673).

## On this cut

- PATCHNOTES: P1587's and P1586's points were over 250 characters. They were split at sentence ends in P1588's records
  commit, words unchanged.
- The first Linux build stamped `patch-1587-4-gaa3294bab`. `patch-1588` had been made as a lightweight tag, and the
  Linux builder's describe sees only annotated ones; every earlier patch tag is annotated. The tag was re-made
  annotated (same commit) and Linux rebuilt.

## Owed after this release

BACKLOG "Hooks below the journal" (P1586, ftesurf-31, whose session has ended): FS_TERMS_ONLINE 9 for
csprogs/qwprogs too (drop the `#ifdef MENU` in sh_defs.qc) and deploy the lobbies, so a lobby requires the new terms.
Menus older than 0.1.48 then lose online until they update. Not done here: Lex to say when.

## Scope and limits

Automated checks only: the in-game check is **pending** in `lextest.md`. Root `C:\FTESurf-worktrees\release0148-06`
keeps `qc/dist`, `artifacts/` and `inputs/` until the next release.
