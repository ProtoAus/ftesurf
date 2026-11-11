# P1489 claim (ftesurf-18, Claude Code, 11 Nov 2026)

The sprite/glow/spotlight/fx and emitter loaders run while CSQC_WorldLoaded runs (behind the loading screen), keyed
by the world that just loaded, instead of in the first drawn frame after spawn: on a first connect serverkey("map")
is still "" in WorldLoaded (P948), so Sprite_LoadForMap and Emit_LoadForMap returned and their per-frame safety nets
loaded everything after the player could see the world -- Lex's fairy dump: 77 + 51 ms csqc frames right after
spawn; the rig's spawn probe named Emit/Sprite/Fx loads with getentitytoken, getlight and strtolower. QC
cl_sprites.qc, cl_emit.qc, cl_main.qc. Root C:\FTESurf-worktrees\lows2-20261107-opus.
