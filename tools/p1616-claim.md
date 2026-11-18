# P1616 claim

- Owner: Claude Code session worldofsurf-15 (for Lex), 2026-11-19.
- Work: the look follows the Steam account (Lex: "belt and body colour doesn't save ... check the player trail, knife,
  and paint options and ensure they are tied to the players steam account and the info loads every time they connect
  to a server"). (a) Knife: P970's account sync posted to cvar `lobby_url`, which nothing sets, so it never reached
  surfd (account_viewmodels: 0 rows on 19 Nov); it uses `lobby_master` like every other social call. (b) Body, belt,
  trail and paint options: kept per account by the lobbies in their shared gamedir (data/looks/<who>.txt), loaded on
  every connect with P970's handshake (look_setup / look_profile load|ack).
- Files: src/server/sv_viewmodel.qc, src/server/sv_player.qc; src/client/cl_viewmodel.qc; ENGINE.txt, PATCHNOTES.md,
  lextest.md, AGENT_NOTES.md; engine ENGINE_PATCHES.md (QC-only entry).
- Root: FTESurf-worktrees/asks-20261119-15
