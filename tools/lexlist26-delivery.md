# Lex's second list of 25 Oct 2026 -- delivery record (P986, P991-P994, P996, P998-P1001)

Session ftesurf-7e (Claude Code), task root `C:\FTESurf-worktrees\lexlist26-20261025T0113Z`.
Hashes are SHA-256 prefixes. Times UTC, 25 Oct 2026.

## What the list asked, and where it went

| Item | Patch | State |
|---|---|---|
| xhair4 (42 px CS:S style) replaces xhair3, centred | P986 | built, tested (pixels), deploy below |
| Play screen: Esc closes the whole menu | P991 | built, tested (ui_key) |
| Profile from Play: messed-up font, one map time | P991 | built, tested (min() int bug; 12 rows) |
| Friends list doesn't load in a lobby | P992 | built, tested (direct fallback after 8 s) |
| Underline a friend's map on hover | P991 | built, tested (pixel diff) |
| Announce connects / PBs / WRs in lobby chat | -- | already live (Patch 371: joins, leaves, others' online bests with time) |
| ...and in the main menu lobby chat | P996 | surfd + menu built and tested; backend NOT deployed (guarded generation handoff) |
| Save-load in a start zone tags the run segmented | P993 | built, tested (stage boxes; origin rounding), integrity-reviewed twice |
| Remove "F1 cursor" on the results card | P994 | built |
| m_accel / controller cheating? | -- | answer only (BACKLOG) |
| Ramp touchdown speed/energy 1 tick earlier | P1001 | built, tested (surf_ace replay marks) |
| Launch lag loading update data | P999 | built, measured 722 -> 278 ms (map list); updater hashing in BACKLOG |
| Stage completion slows the game; upload stage data | P998 | built, measured ~45-58 -> ~28 ms per stage close; evidence-reviewed twice |
| Profiles in private lobbies | P1000 | built, tested (self mark; others self-reported) |
| Glock single fire has kick | -- | already fixed by P955 (live 23 Oct); nothing changed |

## Deployed

- ~04:36Z Pi lobbies 1-12 (`build.ps1 -Pi` from main 28dfc228, nobody on any lobby, all 12
  restarted): qwprogs 02837107 / csprogs a7a2b239. Second install C:\FTEQuake by the same run,
  menu 2a0a3f80 copied with .prev; C:\FTESurftesurf qwprogs/csprogs/menu copied with .prev
  (previous: qwprogs 2a9882a9, csprogs 7495db35, menu 2ccef27b). gfx/crosshairs/xhair4.png
  3d0426e3 in both installs (C:\FTESurf already had it; it is in the next release's archive).
- Lobby smoke on 27520 with the installed exe: served csprogs = build, board drew, no QC error.
- NOT deployed: P996's surfd half (social.py/surfd.py) -- the live backend runs a pinned
  generation behind the transition guard; a new generation needs its own approved handoff.

## Not done / limits

- P996's backend half waits for the guarded surfd generation handoff (AGENT_NOTES: review
  acceptance does not authorize replacing it); the menu renders the lines once surfd sends them.
- See BACKLOG.md "Lex's list of 25 Oct (second): what is still open".
- None of it is owner-checked: lextest.md has the checks.
