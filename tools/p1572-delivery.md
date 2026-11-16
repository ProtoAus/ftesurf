# P1572 Jargon follows trigger_push; Results and Tuning tabs -- delivery (16 Nov 2026, ftesurf-dc)

Lex, 16 Nov: Jargon is slow and completes little; does it know push triggers; give numbers to adjust. Task root
C:\FTESurf-worktrees\jargon4-20261116-dc (rigs/ and artifacts/ hold every run below).

## On main

FTESurf 97619078 (code) + a43c9021 (notes, lextest, BACKLOG, ENGINE.txt pin). Engine 7cdc24da4 (code) + dad3668be
(ENGINE_PATCHES entry), tag patch-1572, on P1576/P1577 (648dfb366). Patch log: engine ENGINE_PATCHES.md Patch 1572.

## Verified

- QC: three VMs 0 warnings (fteqcc 1f2efd06). Engine: full rebuild, 0 errors (warnings all pre-existing), single
  stamp git-8791-patch-1572-0-gdad3668be; check_tls_refptr 369 objects, 0 plain-address uses.
- Exact: every played landing bit-equal to its prediction: surf_rookie stage 1 4/4 (c1), surf_tensor2 stage 2 17/17
  (b2, c2, f3), surf_rookie main 121/121 (e1, before kind 6) and 92/92 (f1).
- Discriminates (same build, tas_jargon_off 4194304): surf_rookie main reached stretch 9 of 64 with pushes followed (f1);
  without, every search after the stage-1 portal stopped before one candidate and the chain ended stuck (f2).
- Control: surf_tensor2 stage 2 on the installed build before this patch (exe 0f69250e server, QC 52f3c098): 0:12.165,
  4 backtracks (g1) -- the same as the WIP, review-1 and final builds of this patch.
- Tabs, read by eye on the shipped client (4fffcfb1) with main's QC (rigs/g2-tabs/.../screenshots): Tuning draws its 12
  numbers and the push switch with the two moved values highlighted; Results draws five waypoint rows (result, tries,
  time, what ended the lines) and the hint under them; nothing cut off. Driver checks 5/5.
- Reviews: round 1 two reviewers; round 2 one reviewer, six findings, all real and fixed. Speed: a StartFrame search
  path was measured to change nothing (the time between search frames is tape playback) and removed; see the patch log.

## Delivery

- Both installs, 16 Nov ~02:56Z: client 4fffcfb1 (C:\FTESurf\ftesurf64.exe, C:\FTEQuake\fteqw64.exe), fteqwsv64 a34a3459,
  fteplug_hl2 d76cf34a, fteplug_ui_imgui deef40eb; qwprogs 56f3de88, csprogs fc726221, menu 76d94dfd (tree a43c9021).
  .prev = client 27697bbc (patch-1574), fteqwsv64 0f69250e, hl2 563a1a39, imgui 8c873087, QC 52f3c098 / 71f708cf / 4561e872.
  Carries ftesurf-31's P1576/P1577 engine and QC (their OK; they make no separate install).
  build.ps1 run from the worktree (-Engine -Full -FteRoot <engine worktree>) deploys its own root and C:\FTEQuake; the
  same files were copied into C:\FTESurf with .prev kept, and both installs hashed equal to the release outputs.
- Lobbies: one combined deploy by ftesurf-06 from main (P1572 + P1576 + P1582), qwprogs and csprogs together:
  ~03:18Z, build.ps1 -Pi from main 8b5d560e, nobody on, warned, swapped, all 12 restarted: live qwprogs 56f3de88 /
  csprogs 92f9604e (.prev 52f3c098 / 71f708cf = P1573). The same deploy moved both installs' csprogs to 92f9604e (.prev
  fc726221) and seeded csprogsvers a05e0981; tasrevd codes.txt gained 92f9604e (P1573's 71f708cf and this install's
  fc726221 were never listed there: a TAS upload from those csprogs between 02:56Z and 03:18Z would not have matched).
- The Pi's server engine is unchanged (p1383-arm): it has no push fields, so lobby searches end at pushes as before.

## Owner check

lextest.md "P1572 Jargon pushes, Results and Tuning". The stage 2 start on surf_rookie after its teleport is P1579's.
