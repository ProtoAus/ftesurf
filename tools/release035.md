# 0.1.35 — P1175-P1196 as delivered

Published **0.1.35** on 2 Nov 2026 at 05:41Z, at Lex's request (Lex chose "Cut release 0.1.35" after
asking for P1178's Maps rows, authors and sharper pictures, which the Desktop 0.1.34 copy predated).
20 patch entries; see PATCHNOTES.md `## 0.1.35`.

## What shipped, and how it was chosen

The DELIVERED set again, not a blanket main build:
- QC source = origin/deploy/p1193-sirena 96f009ed, live on both installs and all 12 lobbies. Frozen
  tree: tag v0.1.35 = 482649fe (release/0135-20261102T0450Z) = main 012fedcf's tooling, docs and
  site with the 12 QC files that differ taken from 96f009ed; src/build.ps1 and src/release/ (P1176's
  zoning page) stay main's. A c24ede65 NoDeploy build gives qw 6955e756 and cs 7f6adb64 = installed
  (the release's are those bytes); menu.dat matches the installed 339ce08f except its version string.
- Left out (still under `## next`): P1169 (1/47 of its src lines in the tree), P1161 (0/4), P1154
  (1/7) and the Collectors note (backend not active). artifacts/notes_shipped.py measured each entry.
- Engine release-0135 686d42014 = tag patch-1195 (fb3e181d6: P1173 + P1188 + P1195, the installed
  line) + P1191 b164fc896 and P1192 dd570d36c cherry-picked + their journal entries. NOT engine main
  127c62ab5: its first-parent line carries 49 commits never delivered (native TAS fs/sv work, +1638
  lines) and P1195 through an unrun merge. Stamp git-8079-patch-1195-3-g686d42014 (16x, one line);
  Linux Bullseye BUILDINFO gates all PASS, same stamp, glibc floor 2.30 with the bootstrap.
- Launcher 646c8d1, unchanged since 0.1.33. Data from the dev install: mapmeta 0530304f (P1178
  author and hd columns), mapdeps a01b7cd0 (P1188's skyhaven platform line), hd0-11.jpg (+15.6 MB,
  so -MaxTotalMB 96: stage 81.3 MB), the 657 zones exactly as 0.1.34 shipped them. The 20 zones
  published to the lobbies since are not in the client archive (0.1.34 left the Pi's set out too).

## Evidence

- Prepared SHA256 `f697d9ee854fc1c198fe083a6e1ebebca9052f2d2667396f295d52029e73f47b`; receipt
  `ebd32dd613490f582f28cadb9c68c8a758826fa013075b71c40ab63daf363973`; feed `55cbc63825b50378…`.
- Windows `ftesurf-0.1.35.7z` 57.5 MB, sha256 `9432fd95d8c11e5a85025ab7079cbf28ca1fe593449c9eaf056fd1fdd8670508`.
- Linux `ftesurf-0.1.35-linux-x86_64.tar.xz` 57.5 MB, sha256 `1c2ee44ce4d1864b36533482560f941276e9c17527f372e714a353fc6dfe8b4b`.
- One prepare, one -PublishPrepared -VerifyFull: 790 objects round-tripped, both launchers and
  archives match, page and no-cache feed byte for byte. Feed vs 0.1.34: +12 files per platform (hd
  pages), 14/12 changed, none removed.
- release_smoke: fresh default-HTTPS installs, Windows 882 / Linux 881 managed files rehashed, 3
  sentinels each, no game launch. Lex's own launcher 0.1.28 (`--dir <empty> --yes --no-launch`)
  installed 0.1.35: exe, three progs, hd11 and mapmeta = the release stage.
- Before publishing, an owned rig of the release exe/progs/data at 1920x1200 (e2's p1178arm):
  rows the photo plus 8 px, "by Arblarg" in the list and the HUD Map info, `+ 12 hd`, 160x90 cells
  sharp at 1:1, a Source map loaded.
- Not claimed: in-game play on a lobby, real-account or Linux desktop acceptance (lextest.md).

## Traps

- With -Bump the prepare is QC-only and ships the exe/plugins found in the QC root: copy
  engine\release\{fteqw64.exe as ftesurf64.exe, both plugins} there first (gate 3 compares them).
- The stage ceiling (80 MB) is a tripwire, not an override: raise -MaxTotalMB after reading the
  delta against the previous feed.
- Run engine git with Windows git: msys git shows every file of a fresh worktree modified.
- Task root: C:\FTESurf-worktrees\release0135-20261102T0450Z (OWNER.md, artifacts/, qc/dist candidate).
