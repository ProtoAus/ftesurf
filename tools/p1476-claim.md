# P1476 claim: wider strafe weaves for Jargon's flights (ftesurf-b8, 10 Nov)

Lex (10 Nov): "a setting that doesn't do the hyper wiggle where the player strafes back and forth every frame ... more
realistic to be a bit wider, slightly less accuracy for visuals." tas_rollout's AIM steering (P1449) flips the strafe side
each tick the heading crosses the bearing. Plan: an opt-in row bit (AIMWIDE, 4096) holds the side until the bearing is a
few degrees past the other way and several ticks have passed; default unchanged. QC: autosurf/optimize `wide`, the
Jargon panel's strafing choice, probe-gated (an engine without it refuses the row). Engine side rides with P1466/P1467
(eng branch p1449); needs review before install.
