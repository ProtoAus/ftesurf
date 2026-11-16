# P1592 delivery -- "segmented" for shadow runs (Lex, 17 Nov 2026)

## Part 1 -- what players read (LIVE 16 Nov 2026 ~17:04Z = 17 Nov 04:04 local)
- Main dee2d7a3 (with P1590's centring follow-up 7d6cd080): HUD tag, load/finish chat lines, replay info row and
  `cmd timer` say segmented/resumed; `Scores_FinStyle` maps a TAS finish to "tas" and the follow opens TAS mode.
- Lobbies: build.ps1 -Pi from the task worktree, 0 players, 12/12 restarted. Live cs 489fca3a, qw 3287648a
  (.prev e393efdc / d5774a9f). tasrevd codes.txt 150 -> 151 (.pre1592).
- Both installs: cs 489fca3a, qw 3287648a, menu 78254538 (C:\FTESurf by hand, .prev = P1589's); csprogsvers seeded.
- pi_lobby_smoke on the 0.1.48 exe: PASS (served 489fca3a, board drew, no QC error).

## Part 2 -- file names (LIVE locally 16 Nov ~18:10Z; lobbies keep `shadow` until part 3)
- Main 18d1199e..6d228cb1 (+ reviews: control flow, evidence/readers, fix round -- no high/medium finding);
  engine 466abb0d8 + 50635cfe0 = tag patch-1592 (git-8822-patch-1592-0-g50635cfe0).
- Both installs: client 10e7f1bf (C:\FTESurf ftesurf64.exe, C:\FTEQuake fteqw64.exe), fteqwsv64 d1c26c49, hl2
  1c9f6409, ui_imgui 25cd528c; C:\FTEQuake cod 6cc213a2, box3d e169ecac, ode c10b000e (.prev = P1591's).
- QC: lobbies 12/12 cs bb7e209e / qw 78a5f4c5 (.prev 489fca3a / 3287648a), both installs + menu f43460fe;
  tasrevd codes.txt 152 (.pre1592b). pi_lobby_smoke on the released 0.1.48 exe: PASS.
- Arm tools/p1592seg.py (resume + finish on surf_dune): new engine + new QC `_segmented.rec`; P1591 engine + new QC
  `_shadow.rec`; new engine + part-1 QC `_shadow.rec`; installed exe + installed QC `_segmented.rec`; flags 133257.

## Part 3 -- lobbies (pending: surfd generation shared with P1595)
surfd `_LEAF_OK` takes history leaves (`-<32 hex>`, REC_LEAF_MAX 96) and `segmented`; live today it drops every
lobby history leaf (11 on 16 Nov). After it is live, drop SV_RecTagName's lobby gate. BACKLOG has the rest.
