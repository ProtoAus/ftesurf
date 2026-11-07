# P1388 claim -- ftesurf-b8, 8 Nov 2026 ~05:20 local

Lex, 8 Nov ("do the backlog"): P1378's passable func_tracktrains follow their path_tracks' speeds, as Source
does -- each node's on arrival under No User Control (ArriveAtNode, Find's first node too), or blended
toward each node's for velocitytype 1/2 (UpdateTrainVelocity). 32 trains on 11 maps carry node speeds.
QC only (sh_trk.qc shared by both progs). Root C:\FTESurf-worktrees\lexbugs-20261108-b8.
