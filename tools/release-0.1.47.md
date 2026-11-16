# World of Surf 0.1.47 delivery

## Published

Published 16 Nov 2026, completing at **07:33:59 UTC** (ftesurf-06), from one successfully previewed, sealed
Windows/Linux candidate, without rebuilding, repacking or resigning. Page: <https://proto.bar/ftesurf>.

- Game version **0.1.47**, qcbuild **89** unchanged.
- Frozen QC `6b310233` (main: 0.1.47 claim and the P1582-P1584 notes). Its client and server game code are
  byte-identical to the lobbies' live pair: csprogs `97e47c88` and qwprogs `ccf0d9a4`. The menu is `9e68b80a`
  because it carries the version.
- Frozen engine `a75914b9d76014d9e7ec1c228fcddae7f67e211a`, `patch-1581`, stamp `git-8800-patch-1581-0-ga75914b9d`.
  The installs ran the patch-1578 client; patch-1578..1581 changes only `sv_ccmds.c` (pm_verify). Peers'
  P1585-P1587 are not in it.
- Bootstrap source `8de1339` (0.1.46's, unchanged).
- 11 player-facing patch entries: P1584, P1583, P1582, P1579, P1575, P1578, P1572, P1576, P1577, P1574, P1573.
- Prepared candidate SHA256 `8f7d5ecc9c176cfee347c0bee6dc84aba2ad836b30d5df9ca417cdd8bd93a1ac`.
- Public receipt SHA256 `5be032036b21394587e3f81f431ed871eb6ac7b89d89a835fc36ca85e8bde3bc`.
- Signed default feed SHA256 `d141c5ccdf62d25edff99b72e2d8c6d0861a629fd406347b5a6acb131c608e66` (prev 0.1.46
  `0b2468d5`): 1145 files, 1041 objects.
- Receipt overrides: **none**.

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `ftesurf-0.1.47.7z` | 78,762,097 | `3f94a02f4e377471b5a9cd1514c47125fddea0839ca87210c4ed7f519425ff75` |
| `ftesurf-0.1.47-linux-x86_64.tar.xz` | 78,849,300 | `3ae936c61c7bd854ce52c4448cd9d08014569f71e740f347b4659989ac7bfec9` |

## Qualification and acceptance

- Three QC VMs compile with 0 warnings.
- Windows full native build (client, server and five plugins):
  - the same 47 distinct warning messages as 0.1.45's build, none new;
  - DLL imports identical to 0.1.46's published exe/plugins (0.1.45's complete SDK reused read-only by
    junction, per P1571).
- Linux: the 10 gates pass.
- Stage 126.9 MB, inside the normal 128 MB budget.
- Staged-build arm (`tools/p1384lead.py` via `tmp/staged_arm.py`: the staged exe, hl2 plugin, qwprogs and menu,
  with a dedicated server, on surf_dune):
  - a fresh config reads back `cl_sl_leadin 0` (`_rev 1582`);
  - a real 0.2 s load press lands by the first frame at delay 0 (game line "save 1 -- run resumed");
  - at 250 ms delay, one 239 u teleport at +0.018 s;
  - prederr 0, no frame gaps, no "Loading save" text.
- `release_smoke.py` (default HTTPS, fresh synthetic installs, no game):
  - win64: 1138 managed files rehashed;
  - linux64: 1137 managed files rehashed;
  - 3 sentinels preserved per platform.
- Upgrade path: the published **0.1.46** archive, unpacked, updated itself to 0.1.47 with its own
  `WOS-Launcher.exe` (`--yes --no-launch`). All 1139 game files are byte-identical to the 0.1.47 stage; `WOS-Launcher.exe` is left
  as the feed intends (launchers are omitted from it).
- TAS credit list: csprogs 97e47c88 was already in `tasrevd-state/codes.txt` (from the P1579 lobby deploy).
- Both local installs received the release's exe, both plugins, `fteqwsv64.exe` (patch-1581) and menu at
  07:35Z, each with `.prev`; csprogs/qwprogs were already these bytes. No game was running from either.

## Traps hit on this cut

- PATCHNOTES: three `## next` points ran past 250 characters (P1572 x2, P1576), which the preflight refuses.
  They were split at sentence ends, words unchanged.
- `mapmedia_refresh.py` run from a release worktree treats that worktree's `ftesurf/` as the install: it pushed
  the worktree's mapmeta to C:\FTEQuake and fetched 55 MB of mapshots into the tree. Fixed by:
  - a rerun with `--gamedir C:/FTESurf/ftesurf`;
  - syncing C:\FTEQuake from the main install (30 media files equal across main, release and second);
  - dropping 0.1.46's orphan `hd17.jpg` (all 2840 hd cells are on pages 0-16).
- `build.ps1 -Engine -Full` launched hidden and detached with `*>` hung three times at about 20 s:
  - the link-step make re-exec idled with no compiler;
  - memory was not the cause, nor was the jobserver style;
  - from the tool shell with `2>&1 | Tee-Object` it built in about 4 min.
- The hl2 header `mat_vmt_progs.h` regenerates with the builder's path in its banner. Content is identical; it
  was restored before the preview, whose clean-input check refuses it.

## Scope and limits

Automated checks only: the in-game version/menu/save-load check is **pending** in `lextest.md`. Root
`C:\FTESurf-worktrees\release0147-06` keeps `qc/dist` (sealed graph, receipts, proofs), `artifacts/` and
`inputs/` until the next release.
