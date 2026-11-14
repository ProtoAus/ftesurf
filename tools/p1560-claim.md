# P1560 claim (ftesurf-e7, 15 Nov 2026)

Lex (15 Nov): surf_ferros prints "2 material(s) did not resolve" -- fix the cause or remove the error.
Cause: luna_tag_0.mdl draws two Elden Ring textures the map never shipped (neither surf_ferros nor
surf_ferros_css packs them; mapdeps.py: no pack has them).

- P1560 (hl2 plugin): the map-load warning stays for what a player can act on (a pack to mount, the asset
  cache) and goes to developer 1 when no pack supplies the content; a models/ material that exists nowhere
  draws a neutral lit colour instead of the checker (hl2_missingtint 0 keeps the checker).
  Files: plugins/hl2/mod_vbsp.c (the warning block after VBSP's material census), plugins/hl2/mat_vmt.c
  (the P1548 no-VMT fallback). P1559 (ftesurf-16) also edits these two files: different blocks.
Shared docs: PATCHNOTES.md, BACKLOG.md, engine ENGINE_PATCHES.md. Task root C:/FTESurf-worktrees/reports-20261114.
