# P1596 claim (ftesurf-64, 17 Nov 2026)

Lex: under the HL movement modes teleports put the player half into the ground; and bhop platforms that are
func_door/func_button should not move but reset you if you do not hop off, when a reset trigger is below.
1. Teleports place Source's feet point; a GoldSrc profile's origin is the hull centre, so every placement adds
   -mins_z (trigger_teleport, _relative, point_teleport, AddOutput origin, func_bhop) -- server and client mirror.
2. A Touch Opens func_door / Touch Activates func_button moving straight down over a teleport trigger within its
   travel (1,444 such doors on 87 of 597 bhop/kz/ahop maps here) fires that teleport after sv_bhop_time_limit
   standing on it. Doors stay put. QC only (qwprogs + csprogs). Root C:\FTESurf-worktrees\lexlist-pool-20261117-64.
