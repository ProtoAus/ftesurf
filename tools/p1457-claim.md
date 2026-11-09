# P1457 claim (ftesurf-1d, 10 Nov 2026)

Experiment: sort an opaque batch's meshes by index-buffer position before the r_multidraw submit (gl_backend.c GLBE_SubmitBatch, r_multidraw_sort), so consecutive runs merge into fewer sub-draws (pantheon: 1350 counted draws from 315 batches).

SCOPE CHANGED 10 Nov: the multidraw sort and a same-batch blend-face merge measured no CPU gain (parked; ENGINE_PATCHES
"Patch 1457"). P1457 is now r_blendsort 2's overlap proofs skipping face/triangle pairs whose screen boxes are apart
(gl_backend.c GLBE_BlendOverlapOrder, r_blendsort_boxes): surf_fairy's worst view sort 1.2 -> 0.92 ms, same verdicts.
Engine branch p1457-blendboxes (on P1449), in review.
