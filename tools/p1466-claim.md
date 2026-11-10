# P1466 claim (ftesurf-b8, 10 Nov 2026)

tas_rollout reports a wall or ceiling clipped on ramp and ground ticks too, behind an opt-in row flag (2048; out[7] bit 2),
so P1449's autosurf can score a ride that rubs a side wall: today kind 4 (wall) is only set off a ramp, and Lex sees
the bot rubbing walls and losing speed. Engine sv_tas_rollout.inc (+ QC sv_tasoptimize.qc on the p1449-wall branch).
