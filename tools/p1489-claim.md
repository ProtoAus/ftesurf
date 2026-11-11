# P1489 claim (ftesurf-18, Claude Code, 11 Nov 2026)

The sprite/glow/spotlight/fx and emitter loaders run while CSQC_WorldLoaded runs (behind the loading screen), keyed
by the world that just loaded, instead of in the first drawn frame after spawn: on a first connect serverkey("map")
is still "" in WorldLoaded (P948), so Sprite_LoadForMap and Emit_LoadForMap returned and their per-frame safety nets
loaded everything after the player could see the world -- Lex's fairy dump: 77 + 51 ms csqc frames right after
spawn; the rig's spawn probe named Emit/Sprite/Fx loads with getentitytoken, getlight and strtolower. QC
cl_sprites.qc, cl_emit.qc, cl_main.qc. Root C:\FTESurf-worktrees\lows2-20261107-opus.

DELIVERED 11 Nov 04:40Z (ftesurf-18): QC on the 12 lobbies and both installs, cs 876a1202 / qw fdce20d0 (main 1aeaf8a2).
Spawn probe on surf_fairy (r_spikes 2 from launch, profiled): the post-spawn frame 547 -> 108 ms; each loader prints
once, before the spawn; a fairy -> jumble map change loads each once. One review (ordering/state across first
connect, map change, restart, reconnect, demos, listen server): no spin, no wrong-world load; overlays/env_shooter/
template keep-state checks switched to the walk's own name (a cvar toggle reset them once per map), short name cut as
svs.name. Zones still load after spawn (they need the server's data).
