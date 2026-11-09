# P1457 claim (ftesurf-1d, 10 Nov 2026)

Experiment: sort an opaque batch's meshes by index-buffer position before the r_multidraw submit (gl_backend.c GLBE_SubmitBatch, r_multidraw_sort), so consecutive runs merge into fewer sub-draws (pantheon: 1350 counted draws from 315 batches).
