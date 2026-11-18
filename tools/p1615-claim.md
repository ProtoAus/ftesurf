# P1615 claim

- Owner: Claude Code session worldofsurf-15 (for Lex), 2026-11-19.
- Work: a segmented run's segment count on the boards, on hover (Lex: "report how many segments a segmented run uses,
  maybe display it on a hover tool tip hovering over the run on the leaderboard"). surfd reads it from the row's
  recording when a board shows it (1 + its `resume` records, as P1569's row_helpers reads `takeover`): row key `segs`
  on segmented rows only. Shown in the TAB board's name tooltip, the menu leaderboard and the website.
- Files: surfd/surfd.py, surfd/web/board.js, surfd/web/board.css, surfd/README.md, surfd/test_segs.py;
  src/client/cl_online.qc, src/client/cl_scores.qc, src/menu/m_board.qc; ENGINE.txt, PATCHNOTES.md, lextest.md,
  tools/backend-pending.md; engine ENGINE_PATCHES.md (QC + backend entry).
- Root: FTESurf-worktrees/asks-20261119-15
