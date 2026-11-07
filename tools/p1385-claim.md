# P1385 claim -- ftesurf-b8, 8 Nov 2026 ~03:45 local

Lex, 8 Nov: surf_centipedes' spawn text ("Press E (+use) in any startzone to toggle the pixel shader", a
game_text) draws at a resampled size that "scales weirdly" and looks bad on the lobbies. cl_mapmsg.qc:
game_text and env_hudhint drawn with the native (pixels=1) font slot at a baked pixel size, pixel-aligned.
QC only. Root C:\FTESurf-worktrees\lexbugs-20261108-b8.
