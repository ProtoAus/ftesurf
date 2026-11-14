# P1563 claim (ftesurf-16, 15 Nov 2026)

Lex's 15 Nov list: surf_tendies' booster (trigger_multiple, name filter, OnStartTouch AddOutput targetname,
OnEndTouch AddOutput basevelocity) lags a round trip at high ping. Client prediction: a predicted player
name (renames the mirror fires, held until *tn catches up) and name-filtered event triggers whose own rows
the mirror pays judged per touch, keeping one already inside as SV_TouchFilter does. File:
src/client/cl_triggers.qc. Prediction only (no evidence change). Root C:/FTESurf-worktrees/lexlist-20261115-16.
