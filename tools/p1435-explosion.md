# P1435 -- env_explosion's Explode drawn as Source's client effect

ftesurf-b8, 9 Nov 2026 (entgap-20261108, look-only group). Root C:\FTESurf-worktrees\xhair-20261108-b8
(tools/p1435arms.sh, armsc.sh, xp1.cfg, rigs/bm-xp*).

## What

- env_explosion (412 on 48 maps; Explode fired on 47) drew and sounded nothing. src/client/cl_explode.qc copies
  C_BaseExplosionEffect (fx_explosion.cpp) as a CSQC particle sim drawn with polygons: smoke filler, inner core
  and a flat ground ring of particle_noisesphere lit by the world (no SF 256), 16 embers and 32 fire_cloud2
  fireballs (no SF 4), 8-16 spark streaks and 16-32 bouncing cement flecks (no SF 512); CExplosionParticle's
  velocity decay, roll damping and (1 - t)^2 colour and alpha; SetNearClip(64, 128). The blast direction is
  GetForceDirection's six probes, iMagnitude long. BaseExplosionEffect.Sound is Momentum's weapons/explode3-5
  (hl2_dir.vpk), CS:S's debris1-2 if that is all there is; none with SF 64. The first Explode leaves a Scorch
  decal on the floor the ground trace found (no SF 16).
- The server keeps a named one (SV_FxKeep) and sends Explode as an event on ENTWIRE_FXSTATE2 class
  FX_CLS_EXPLODE 8; without SF 2 (Repeatable) it takes no more inputs 0.3 s after its last (explode.cpp Smoke).
  The client places it from the lump at load: pulled 24 off the floor or water surface below (InputExplode's
  trace), its light and direction sampled once.
- vbsp_explosions 0 turns them off.

## Measured (client C:\FTEQuake\fteqw64.exe c61f874b, bhop_maya boom5: two repeatable explosions; 0 QC errors)

- Review-1 build (cs a2e7bf8f, qw 23bcf6b5), tools/xp1.cfg: "explosions: 2 of 2 env_explosion kept, sound
  explode3-5"; 9 Explode inputs fired both each time (18 "explode:" lines, 18 class-8 states). 150 ms after an
  Explode, 45862 px changed (fireball, embers, smoke: rigs/bm-xp2-new q2); 7 s later the frame is the start
  frame again (0 px). A stream of explosions every 0.4 s: 10386 px.
- First build (cs before review 1): the same pictures, and "sound none" -- whichpack answers "" for a file inside
  a .vpk (review 1's finding), so every explosion was silent; now probed with search_begin.
- Control (P1433 build, no explosion code): 0 px after Explode.
- Mixed (new qwprogs + P1433 csprogs, rigs-mix1435): the old client logs 18 class-8 states, draws nothing, 0
  errors -- Fx_Net's loop matches no class-8 source.

## Review

One round (one reviewer, the code not the conclusion). Fixed: the silent sound (whichpack inside a VPK); no
scorch decal; the ground trace now stops at water as MASK_WATER does and only CONTENTS_WATER is wet; the 0.3 s
window in which a non-repeatable one can still fire; flecks rest on floors with Source's 0.4-0.6 bounce and
reversed roll; the CS:S fallback sound's 85 dB falloff. Admitted in the file's header instead: no PAS filter
(every client gets every explosion, drawn within 8000 units), material passes rather than a depth sort, grey
smoke where the light lookup gives nothing, no pitch on the fallback sound.

## Left

- Parented env_explosions (51 are point_template members on 2 maps, all parented -- 3a's census) are declined;
  per-copy explosions need P1432's copies.
- Source's water explosion (WaterExplosionEffect) is not drawn; the refraction bulge (CExplosionOverlay).
- Two Explode inputs before the edict's first send arrive as one, and a first send more than 1 s late fires
  nothing (the effect-state wire's fresh flag, as for the other classes).
- env_physexplosion draws nothing in Source; its "Push players" flag is gameplay (3a's side).
