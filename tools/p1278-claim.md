# P1278 claim

ftesurf-ac, 20261104, Lex (4 Nov): ramp wear -- where players ride and board a ramp, the ramp looks used:
dirt cleared along the ride line, scratches where they board (more at steeper impact angles). Baked
offline from Momentum replays (tools/rampwear.py) into a per-map overlay mesh + mask; CSQC draws it
(cl_rampwear.qc), GLSL composes it (ftesurf/glsl/ftesurf_rampwear.glsl). Root
C:/FTESurf-worktrees/rampwear-20261104.
State: prototype on surf_classics3.
