# P1592 delivery -- "segmented" for shadow runs (Lex, 17 Nov 2026)

## Part 1 -- what players read (LIVE 17 Nov 2026 ~17:04Z)
- Main dee2d7a3 (with P1590's centring follow-up 7d6cd080): HUD tag, load/finish chat lines, replay info row and
  `cmd timer` say segmented/resumed; `Scores_FinStyle` maps a TAS finish to "tas" and the follow opens TAS mode.
- Lobbies: build.ps1 -Pi from the task worktree, 0 players, 12/12 restarted. Live cs 489fca3a, qw 3287648a
  (.prev e393efdc / d5774a9f). tasrevd codes.txt 150 -> 151 (.pre1592).
- Both installs: cs 489fca3a, qw 3287648a, menu 78254538 (C:\FTESurf by hand, .prev = P1589's); csprogsvers seeded.
- pi_lobby_smoke on the 0.1.48 exe: PASS (served 489fca3a, board drew, no QC error).

## Part 2 -- file names (pending)
New files `_segmented.rec/.view/.hid`; readers keep `_shadow`. Needs, in order: engine held-close accepting both
words (sv_held_prepare.inc tags[3]) on the Pi and installs, surfd `_LEAF_OK` (a guarded generation), reccheck TAGS,
then the QC writer gated on the engine.
