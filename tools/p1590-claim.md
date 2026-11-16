# P1590 claim -- ftesurf-06 (Claude Code), 2026-11-16

Lex's list of 16 Nov (leaderboards and stats):

- Groups: Momentum's G1-G6 rank ladder measured on the imported Momentum/KSF
  board (surfd `/api/board?groups=<map>&style=&me=`), coloured divider lines on
  the TAB board, your own group as a badge on the leg list.
- Stats page: a map and its clone build (`_css`/KSF port of the same map, from
  mapwatch's catalogue) count once in maps finished / totals.
- TAB board: the server's players float right of the board with their main PB
  in their player colour.
- Board modes as one exclusive row: Segmented (blue), TAS (purple), Normal,
  Sideways, Half-Sideways, Backwards; TAS tab removed (TAB board and menu board).

Files: surfd/surfd.py (+ tests), src/client/cl_scores.qc, cl_online.qc,
cl_players.qc, src/menu/m_board.qc, src/shared/sh_boardstyle.qc; docs
PATCHNOTES.md, BACKLOG.md, lextest.md, AGENT_NOTES.md, engine ENGINE_PATCHES.md,
ENGINE.txt. Root: C:\FTESurf-worktrees\groups-20261116-c7.
