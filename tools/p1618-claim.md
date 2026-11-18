# P1618 claim

- Owner: Claude Code session worldofsurf-15 (for Lex), 2026-11-19.
- Work: map downloads -- r2gateway redirects verified objects to the Cloudflare-cached custom domain maps.proto.bar
  (Lex connected it to ftesurf-public and added a cache rule, 19 Nov), uses the Pi's 1 MiB/s copy only after repeated
  R2 probe failures, and logs each origin decision with its reason. Lex: download complaints; the Pi served
  Markbeaton54's surf_pride at ~240 KB/s on 18 Nov 17:46-17:52Z where the retry 4 min later went to R2 (30 s).
- Files: tools/r2gateway.py, tools/test_r2gateway.py, tools/r2gateway.md; ENGINE.txt, PATCHNOTES.md, AGENT_NOTES.md;
  engine ENGINE_PATCHES.md. Pi: the ftesurf-r2gateway runtime (installer, Lex's sudo).
- Root: FTESurf-worktrees/asks-20261119-15
